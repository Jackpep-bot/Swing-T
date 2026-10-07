"""Alpaca stock websocket (`/v2/iex` Basic or `/v2/sip` Plus): statuses (halts), lulds and bars.

Statuses `T="s"` carry sc/sm (status code/message) and rc/rm (reason code/message). Both the UTP letter codes
(H/P/T/Q) and the CTA codes (2 halt, 3 resume, F LULD) become `halt` events; CTA `E` (SSR) becomes an `ssr`
event and the indication/imbalance codes (5-9, A, C, D) are dropped. LULD `T="l"` carries u/d/i.
Bars `T="b"` are turned into `bar_trigger` events by `BarTriggerEngine` when reference data is available.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import structlog

from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import (
    ADVERSE_MOVE_PCT,
    ALPACA_CTA_STATUS_SSR,
    ALPACA_HEARTBEAT_SYMBOL,
    ALPACA_STATUS_HALTED_CODES,
    ALPACA_STATUS_PAUSED_CODES,
    ALPACA_STATUS_RESUMED_CODES,
    ALPACA_STOCKS_WS_IEX,
    ALPACA_STOCKS_WS_SIP,
    BREAKOUT_VOL_RATIO,
    HALT_STATUS_HALTED,
    HALT_STATUS_PAUSED,
    HALT_STATUS_RESUMED,
    MINUTES_IN_SESSION,
    REGULAR_OPEN,
    TRIGGER_ADVERSE,
    TRIGGER_BREAKOUT_52W,
    TRIGGER_GAP,
)
from ..hours import minute_of_session, to_et
from ._base import WebSocketFeed, decode_frame, now_utc, parse_ts, stable_id

log = structlog.get_logger(__name__)
SOURCE = "alpaca_stocks"
PCT = 100.0


def parse_status(msg: dict[str, Any]) -> Event | None:
    if msg.get("T") != "s":
        return None
    sym = str(msg.get("S", "")).upper()
    sc = str(msg.get("sc", "")).upper()
    rc = str(msg.get("rc", "")).upper()
    ts = parse_ts(msg.get("t"))
    if sc in ALPACA_STATUS_RESUMED_CODES:
        status = HALT_STATUS_RESUMED
    elif sc in ALPACA_STATUS_PAUSED_CODES:
        status = HALT_STATUS_PAUSED
    elif sc in ALPACA_STATUS_HALTED_CODES:
        status = HALT_STATUS_HALTED
    elif sc == ALPACA_CTA_STATUS_SSR:
        return Event(
            event_id=stable_id(SOURCE, "ssr", sym, sc, rc, ts.isoformat()),
            source=SOURCE,
            kind="ssr",
            ts_source=ts,
            ts_received=now_utc(),
            symbols=[sym],
            title=f"{sym} short sale restriction {msg.get('sm') or ''}".strip(),
            meta={"status_code": sc, "reason_code": rc, "reason": msg.get("rm"), "tape": msg.get("z")},
        )
    else:  # indications, imbalances, unknown codes: not a halt and not worth an alert
        log.debug("alpaca_status_ignored", symbol=sym, status_code=sc, reason_code=rc)
        return None
    return Event(
        event_id=stable_id(SOURCE, "status", sym, sc, rc, ts.isoformat()),
        source=SOURCE,
        kind="halt",
        ts_source=ts,
        ts_received=now_utc(),
        symbols=[sym],
        title=f"{sym} {msg.get('sm') or status} {rc} {msg.get('rm') or ''}".strip(),
        meta={"status": status, "status_code": sc, "reason_code": rc, "reason": msg.get("rm"), "tape": msg.get("z")},
    )


def parse_luld(msg: dict[str, Any]) -> Event | None:
    if msg.get("T") != "l":
        return None
    sym = str(msg.get("S", "")).upper()
    ts = parse_ts(msg.get("t"))
    return Event(
        event_id=stable_id(SOURCE, "luld", sym, msg.get("u"), msg.get("d"), ts.isoformat()),
        source=SOURCE,
        kind="luld",
        ts_source=ts,
        ts_received=now_utc(),
        symbols=[sym],
        title=f"{sym} LULD band {msg.get('d')}-{msg.get('u')} ({msg.get('i')})",
        meta={"up": msg.get("u"), "down": msg.get("d"), "indicator": msg.get("i"), "tape": msg.get("z")},
    )


REFERENCE_COLUMNS: tuple[str, ...] = ("avg_vol_20d", "avg_vol_50d", "high_52w")


def reference_from_panel(panel: Any) -> dict[str, dict[str, float]]:
    """Per-symbol reference dict for :class:`BarTriggerEngine` from the latest row of a feature panel.

    The last stored close is tomorrow's ``prev_close``; ``avg_vol_20d`` / ``avg_vol_50d`` / ``high_52w`` are
    taken as stored (docs/feature-contract.md). Rows with no usable close are skipped.
    """
    out: dict[str, dict[str, float]] = {}
    if panel is None or len(panel) == 0 or "symbol" not in panel.columns or "close" not in panel.columns:
        return out
    frame = panel.sort_values("ts") if "ts" in panel.columns else panel
    last = frame.groupby("symbol", sort=False).tail(1)
    for row in last.itertuples(index=False):
        close = _finite(getattr(row, "close", None))
        if close is None or close <= 0:
            continue
        ref: dict[str, float] = {"prev_close": close}
        for col in REFERENCE_COLUMNS:
            val = _finite(getattr(row, col, None))
            if val is not None:
                ref[col] = val
        out[str(row.symbol).upper()] = ref
    return out


def _finite(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


class BarTriggerEngine:
    """Turns 1-min bars into bar_trigger events using a reference dict per symbol:
    {prev_close, avg_vol_20d, avg_vol_50d, high_52w}. An optional cumulative-fraction profile
    (symbol -> list[float] indexed by minute of session) replaces the linear default. ``held`` may be the
    live set shared with the pipeline context so adverse-move triggers follow fills.
    """

    def __init__(
        self,
        reference: dict[str, dict[str, float]] | None = None,
        profile: dict[str, list[float]] | None = None,
        held: set[str] | None = None,
    ):
        self.reference = reference or {}
        self.profile = profile or {}
        self.held = held or set()
        self._cum: dict[tuple[str, date], float] = {}
        self._pre: dict[tuple[str, date], float] = {}  # volume before the 09:30 ET open
        self._fired: set[tuple[str, date, str]] = set()

    def volumes(self, symbol: str, day: date) -> tuple[float, float] | None:
        """(cumulative volume, pre-market volume) for ``symbol`` on ET ``day`` from every bar seen so far, or None.
        The small-cap track reads this so float rotation and pre-market exhaustion follow the live tape, not the
        single bar that happened to fire a trigger."""
        key = (symbol.upper(), day)
        if key not in self._cum:
            return None
        return self._cum[key], self._pre.get(key, 0.0)

    def expected_fraction(self, sym: str, minute: int) -> float:
        prof = self.profile.get(sym)
        if prof:
            idx = min(len(prof) - 1, max(0, minute))
            return max(prof[idx], 1.0 / MINUTES_IN_SESSION)
        return max(1, minute) / MINUTES_IN_SESSION

    def on_bar(self, msg: dict[str, Any]) -> list[Event]:
        if msg.get("T") != "b":
            return []
        sym = str(msg.get("S", "")).upper()
        ref = self.reference.get(sym)
        if not ref:
            return []
        ts = parse_ts(msg.get("t"))
        day = to_et(ts).date()
        key = (sym, day)
        vol = float(msg.get("v", 0.0))
        self._cum[key] = self._cum.get(key, 0.0) + vol
        if to_et(ts).time() < REGULAR_OPEN:
            self._pre[key] = self._pre.get(key, 0.0) + vol
        cum = self._cum[key]
        minute = minute_of_session(ts)
        avg20 = float(ref.get("avg_vol_20d") or 0.0)
        rvol = cum / (avg20 * self.expected_fraction(sym, minute)) if avg20 > 0 else 0.0
        prev_close = float(ref.get("prev_close") or 0.0)
        close = float(msg.get("c", 0.0))
        out: list[Event] = []
        if prev_close > 0:
            gap = (float(msg.get("o", close)) / prev_close - 1.0) * PCT
            if (sym, day, TRIGGER_GAP) not in self._fired:
                self._fired.add((sym, day, TRIGGER_GAP))
                out.append(self._event(sym, ts, TRIGGER_GAP, {"gap_pct": gap, "rvol": rvol, "cum_volume": cum}))
            pct = (close / prev_close - 1.0) * PCT
            if sym in self.held and pct <= -ADVERSE_MOVE_PCT and (sym, day, TRIGGER_ADVERSE) not in self._fired:
                self._fired.add((sym, day, TRIGGER_ADVERSE))
                out.append(self._event(sym, ts, TRIGGER_ADVERSE, {"pct": pct, "rvol": rvol}))
        high52 = float(ref.get("high_52w") or 0.0)
        avg50 = float(ref.get("avg_vol_50d") or 0.0)
        if high52 > 0 and close > high52 and (sym, day, TRIGGER_BREAKOUT_52W) not in self._fired:
            vol_ratio = cum / (avg50 * self.expected_fraction(sym, minute)) if avg50 > 0 else 0.0
            if vol_ratio >= BREAKOUT_VOL_RATIO:
                self._fired.add((sym, day, TRIGGER_BREAKOUT_52W))
                out.append(
                    self._event(sym, ts, TRIGGER_BREAKOUT_52W, {"rvol": rvol, "vol_ratio": vol_ratio, "close": close})
                )
        return out

    @staticmethod
    def _event(sym: str, ts: Any, trigger: str, meta: dict[str, Any]) -> Event:
        return Event(
            event_id=stable_id(SOURCE, trigger, sym, to_et(ts).date().isoformat()),
            source=SOURCE,
            kind="bar_trigger",
            ts_source=ts,
            ts_received=now_utc(),
            symbols=[sym],
            title=f"{sym} {trigger} " + " ".join(f"{k}={v:.2f}" for k, v in meta.items() if isinstance(v, float)),
            meta={"trigger": trigger, **meta},
        )


def parse_frame(raw: str | bytes, engine: BarTriggerEngine | None = None) -> list[Event]:
    data = decode_frame(raw)
    msgs = data if isinstance(data, list) else [data]
    out: list[Event] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        t = m.get("T")
        if t == "error":
            raise ConnectionError(f"alpaca stocks error {m.get('code')}: {m.get('msg')}")
        if t == "s":
            ev = parse_status(m)
            if ev is not None:
                out.append(ev)
        elif t == "l":
            ev = parse_luld(m)
            if ev is not None:
                out.append(ev)
        elif t == "b" and engine is not None:
            out.extend(engine.on_bar(m))
    return out


@register("feed", SOURCE)
class AlpacaStocksFeed(WebSocketFeed):
    name = SOURCE

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        symbols: list[str] | None = None,
        sip: bool = False,
        engine: BarTriggerEngine | None = None,
        heartbeat_symbol: str | None = ALPACA_HEARTBEAT_SYMBOL,
        **kw: Any,
    ):
        super().__init__(**kw)
        self.url = ALPACA_STOCKS_WS_SIP if sip else ALPACA_STOCKS_WS_IEX
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbols = symbols or ["*"]
        self.engine = engine
        self.heartbeat_symbol = heartbeat_symbol

    async def _handshake(self, ws: Any) -> None:
        await ws.send(json.dumps({"action": "auth", "key": self.api_key, "secret": self.secret_key}))
        sub: dict[str, Any] = {"action": "subscribe", "statuses": self.symbols, "lulds": self.symbols}
        if self.engine is not None:
            sub["bars"] = self.symbols
        if self.heartbeat_symbol:
            # trades of one liquid name: parse_frame ignores them, but every frame proves the socket is alive
            sub["trades"] = [self.heartbeat_symbol]
        await ws.send(json.dumps(sub))

    def _parse_frame(self, raw: str | bytes) -> list[Event]:
        return parse_frame(raw, self.engine)
