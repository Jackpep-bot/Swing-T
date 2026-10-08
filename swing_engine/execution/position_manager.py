"""Position manager: decide exits for open positions and stale entry orders. Pure decisions, no broker writes.

``review_positions(settings, broker, panel, as_of, strategies, earnings=None)`` reads the broker's positions and
open orders and returns :class:`ExitAction` items that ``execution.autopilot`` executes (exits before entries):

* ``cancel_order``  an unfilled ``swing-*`` entry that has been live for ``cancel_unfilled_entries_after_sessions``
  NYSE sessions. Entries are GTC brackets (see ``execution.alpaca_broker``) so their stop/target legs persist
  across days; the flip side is that an unfilled GTC entry would also persist, so it is cancelled here. The
  unfilled remainder of a partially filled entry is cancelled on the same clock (the filled part is a position
  and keeps its legs; if the broker drops them, ``place_stop`` below re-arms one the next night).
  :func:`entry_cancels_on_kill` lists every unfilled entry regardless of age for the kill-switch path.
* ``close``  earnings within ``earnings_exit_days`` sessions, the strategy's time stop (``max_hold_days`` or
  ``time_stop_days`` param), or the strategy's rule exit (``exit_rule(row, position)`` or
  ``should_exit(row, bars_held)``) evaluated on the ``as_of`` panel row.
* ``place_stop``  a strategy-owned position with no open stop order (a leg that expired at Alpaca's 90-day GTC
  limit, a failed close that had already cancelled the legs, legs dropped after a partial fill) gets a fresh
  protective stop at the ledger's intent stop (or the R-ladder stop when tighter). When that stop is already
  through the close the position is closed instead (``reason=no_stop``).
* ``replace_stop``  breakeven at ``breakeven_after_r`` and a trailing stop (lowest low of ``trail_lookback_days``
  sessions, never below breakeven) from ``trail_after_r`` (the engine overlay; a strategy opts out with
  ``engine_trail = False`` as a class attribute or param), and the strategy's own indicator trail
  (``trail_stop(row) -> float | None`` on the ``as_of`` row: supertrend, PSAR, chandelier, swing low). The tightest
  candidate wins; a stop is only ever tightened, never loosened, and never placed through the close.
* ``flag``  an orphan position (no strategy recoverable from the position, the ``swing-<strategy>-...``
  client_order_id or the order ledger), a position without panel data, an unprotected position with no recorded
  stop, or a position whose review raised (``reason=error``; the other positions are still reviewed). Flags are
  reported, never executed: an orphan may be a manual trade.

Every number (R multiple, new stop, qty) is arithmetic on broker positions, the order ledger and the feature
panel; nothing here reads LLM output.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import structlog
from pydantic import BaseModel

from swing_engine.core import registry
from swing_engine.core.config import Settings
from swing_engine.core.interfaces import Strategy
from swing_engine.core.models import Position, Side
from swing_engine.execution.ledger import OrderLedger, OrderStatus
from swing_engine.risk.killswitch import resolve_state_path

log = structlog.get_logger(__name__)

NY = ZoneInfo("America/New_York")
SESSION_CLOSE_ET = time(16, 0)  # fallback when the exchange calendar is unavailable
CLIENT_ORDER_ID_PREFIX = "swing"  # risk.sizing.CLIENT_ORDER_ID_PREFIX; ids look like swing-<strategy>-<symbol>-...
PRICE_DECIMALS = 2  # Alpaca rejects sub-penny stops on stocks over $1
HOLD_PARAMS = ("max_hold_days", "time_stop_days")  # strategy params read as the per-strategy time stop
#: Strategy class attribute / param that opts out of the engine-wide breakeven + N-day-low overlay
#: (docs/strategies/qullamaggie_flag.md, episodic_pivot.md: the overlay cuts the winners those methods need).
ENGINE_TRAIL_ATTR = "engine_trail"
#: Strategy hook ``trail_stop(row) -> float | None``: an indicator stop the engine ratchets to (never down).
TRAIL_STOP_HOOK = "trail_stop"
EARNINGS_DATE_COLUMNS = ("report_date", "earnings_date", "date")
STOP_ORDER_TYPES = frozenset({"stop", "stop_limit", "trailing_stop"})
FILLED = frozenset({OrderStatus.FILLED.value, OrderStatus.PARTIALLY_FILLED.value})
DEAD_LEDGER_STATUSES = frozenset(
    {OrderStatus.CANCELED.value, OrderStatus.EXPIRED.value, OrderStatus.REJECTED.value, OrderStatus.ERROR.value}
)
_CID_RE = re.compile(r"^swing-(?P<strategy>[^-]+)-")


class ExitKind(StrEnum):
    CLOSE = "close"
    REPLACE_STOP = "replace_stop"
    PLACE_STOP = "place_stop"  # re-arm a protective stop on a position that has none
    CANCEL_ORDER = "cancel_order"
    FLAG = "flag"  # reported only; the autopilot never acts on it


class ExitReason(StrEnum):
    STRATEGY_EXIT = "strategy_exit"
    TIME_STOP = "time_stop"
    EARNINGS = "earnings"
    BREAKEVEN = "breakeven"
    TRAIL = "trail"
    STRATEGY_TRAIL = "strategy_trail"  # the strategy's own indicator trail (``trail_stop`` hook)
    STALE_ENTRY = "stale_entry"
    KILL_SWITCH = "kill_switch"  # unfilled entry cancelled because the kill switch is tripped
    NO_STOP = "no_stop"  # position without an open protective stop
    ORPHAN = "orphan"
    NO_DATA = "no_data"
    ERROR = "error"  # reviewing this position raised; reported, never acted on


KIND_ORDER = {
    ExitKind.CANCEL_ORDER: 0, ExitKind.CLOSE: 1, ExitKind.PLACE_STOP: 2, ExitKind.REPLACE_STOP: 3, ExitKind.FLAG: 4,
}


class ExitAction(BaseModel):
    kind: ExitKind
    symbol: str
    reason: ExitReason
    qty: int | None = None
    new_stop: float | None = None
    order_id: str | None = None  # broker order id: the entry to cancel or the stop leg to replace
    client_order_id: str | None = None  # the entry's swing-* id when known (ledger bookkeeping)
    strategy: str | None = None
    side: Side | None = None
    ref_price: float | None = None  # as_of panel close (deterministic); prices a paper_sim close
    detail: str = ""


@dataclass
class _Held:
    position: Position
    strategy: str | None = None
    client_order_id: str | None = None
    entry_day: date | None = None
    initial_stop: float | None = None
    current_stop: float | None = None
    stop_order_id: str | None = None


# ----------------------------------------------------------------------------------------------------------
# small helpers
# ----------------------------------------------------------------------------------------------------------
def _float(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


def _parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        ts = value
    else:
        try:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _ny_day(ts: datetime | None) -> date | None:
    return ts.astimezone(NY).date() if ts is not None else None


def strategy_from_client_order_id(client_order_id: str | None, known: Iterable[str] = ()) -> str | None:
    """``swing-<strategy>-<symbol>-<yyyymmdd>-<side>`` -> strategy. Known names win (longest first)."""
    if not client_order_id or not client_order_id.startswith(f"{CLIENT_ORDER_ID_PREFIX}-"):
        return None
    for name in sorted(known, key=len, reverse=True):
        if client_order_id.startswith(f"{CLIENT_ORDER_ID_PREFIX}-{name}-"):
            return name
    match = _CID_RE.match(client_order_id)
    return match.group("strategy") if match else None


def flatten_orders(open_orders: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Top-level orders plus nested bracket legs (Alpaca ``nested=True``), each leg tagged with its parent."""
    out: list[dict[str, Any]] = []
    for order in open_orders:
        parent = dict(order)
        out.append(parent)
        for leg in parent.get("legs") or []:
            item = dict(leg)
            item["_parent_client_order_id"] = parent.get("client_order_id")
            item.setdefault("symbol", parent.get("symbol"))
            out.append(item)
    return out


def is_engine_entry(order: Mapping[str, Any]) -> bool:
    """A top-level ``swing-*`` order (an entry this engine placed), not a nested bracket leg."""
    cid = order.get("client_order_id")
    return "_parent_client_order_id" not in order and bool(cid) and str(cid).startswith(f"{CLIENT_ORDER_ID_PREFIX}-")


def _filled_qty(order: Mapping[str, Any]) -> float:
    return _float(order.get("filled_qty")) or 0.0


def _is_unfilled(order: Mapping[str, Any]) -> bool:
    return _text(order.get("status")) not in FILLED and _filled_qty(order) <= 0


def _is_partial(order: Mapping[str, Any]) -> bool:
    """Some quantity filled and some still working (the remainder can fill weeks later at a stale limit)."""
    if _text(order.get("status")) == OrderStatus.FILLED.value:
        return False
    filled, qty = _filled_qty(order), _float(order.get("qty"))
    return filled > 0 and (qty is None or filled < qty)


def entry_cancels_on_kill(open_orders: Iterable[Mapping[str, Any]]) -> list[ExitAction]:
    """Kill switch: cancel every resting ``swing-*`` entry with nothing filled, whatever its age. Cancelling only
    removes exposure that has not happened yet; filled parents and their protective legs are left alone."""
    out: list[ExitAction] = []
    for o in flatten_orders(open_orders):
        if not is_engine_entry(o) or not _is_unfilled(o):
            continue
        cid = str(o.get("client_order_id"))
        out.append(
            ExitAction(
                kind=ExitKind.CANCEL_ORDER, symbol=str(o.get("symbol")), reason=ExitReason.KILL_SWITCH,
                order_id=str(o.get("id")) if o.get("id") else None, client_order_id=cid,
                strategy=strategy_from_client_order_id(cid), detail="unfilled entry cancelled under the kill switch",
            )
        )
    return out


def _is_stop_leg(order: Mapping[str, Any], position: Position) -> bool:
    kind = _text(order.get("order_type") or order.get("type"))
    if kind not in STOP_ORDER_TYPES or _float(order.get("stop_price")) is None:
        return False
    exit_side = "sell" if position.side == Side.LONG else "buy"
    side = _text(order.get("side"))
    return side in ("", exit_side)


def _session_closes(start: date, end: date) -> list[datetime]:
    """Session close timestamps (UTC) for NYSE sessions in [start, end]; weekday 16:00 ET without a calendar."""
    if end < start:
        return []
    try:
        from swing_engine.data.calendar import schedule

        sched = schedule(start, end)
        return [pd.Timestamp(ts).to_pydatetime().astimezone(UTC) for ts in sched["market_close"]]
    except Exception as exc:  # noqa: BLE001 - calendar is optional for this estimate
        log.debug("calendar_unavailable", error=str(exc))
        days = pd.bdate_range(start, end)
        return [datetime.combine(d.date(), SESSION_CLOSE_ET, tzinfo=NY).astimezone(UTC) for d in days]


def sessions_between(since: datetime, until: datetime) -> int:
    """NYSE sessions that closed after ``since`` and on or before ``until``."""
    if until <= since:
        return 0
    closes = _session_closes(_ny_day(since) or since.date(), _ny_day(until) or until.date())
    return sum(1 for c in closes if since < c <= until)


def trading_sessions_until(as_of: date, target: date) -> int:
    """Sessions after ``as_of`` up to and including ``target`` (0 when ``target`` is ``as_of``)."""
    if target <= as_of:
        return 0
    try:
        from swing_engine.data.calendar import trading_days

        return len([d for d in trading_days(as_of + timedelta(days=1), target) if d <= target])
    except Exception as exc:  # noqa: BLE001
        log.debug("calendar_unavailable", error=str(exc))
        return int(np.busday_count(as_of + timedelta(days=1), target + timedelta(days=1)))


def _default_now(as_of: date) -> datetime:
    if as_of >= datetime.now(NY).date():
        return datetime.now(UTC)
    return datetime.combine(as_of, time.max, tzinfo=NY).astimezone(UTC)


def _strategy_params(settings: Settings, name: str) -> dict[str, Any]:
    cfg = settings.strategies.get(name) or {}
    if isinstance(cfg.get("params"), dict):
        return dict(cfg["params"])
    return {k: v for k, v in cfg.items() if k != "enabled"}


def build_strategies(
    settings: Settings, strategies: Mapping[str, Any] | Iterable[Any] | None = None
) -> dict[str, Strategy]:
    """Name -> instance. ``None`` = every registered strategy (a disabled one may still hold positions)."""
    if isinstance(strategies, Mapping):
        return {str(k): v for k, v in strategies.items()}
    items = list(strategies) if strategies is not None else registry.names("strategy")
    out: dict[str, Strategy] = {}
    for item in items:
        if not isinstance(item, str):
            out[str(getattr(item, "name", type(item).__name__))] = item
            continue
        try:
            out[item] = registry.get("strategy", item)(_strategy_params(settings, item))
        except Exception as exc:  # noqa: BLE001 - an unknown name just has no rule exits
            log.warning("position_strategy_unavailable", strategy=item, error=str(exc))
    return out


def _open_ledger(settings: Settings) -> OrderLedger | None:
    path = resolve_state_path(settings.execution.ledger_file)
    return OrderLedger(path) if path.exists() else None


def _symbol_frame(panel: pd.DataFrame | None, symbol: str, as_of: date) -> pd.DataFrame:
    if panel is None or panel.empty or "symbol" not in panel.columns:
        return pd.DataFrame()
    sub = panel.loc[panel["symbol"] == symbol]
    if sub.empty:
        return sub
    ts = pd.to_datetime(sub["ts"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    day = ts.dt.normalize()
    sub = sub.assign(_day=day).loc[day <= pd.Timestamp(as_of)].sort_values("ts", kind="stable")
    return sub


def _earnings_day(earnings: pd.DataFrame | None, symbol: str, as_of: date) -> date | None:
    if earnings is None or len(earnings) == 0 or "symbol" not in earnings.columns:
        return None
    col = next((c for c in EARNINGS_DATE_COLUMNS if c in earnings.columns), None)
    if col is None:
        return None
    days = pd.to_datetime(earnings.loc[earnings["symbol"] == symbol, col], errors="coerce").dropna()
    upcoming = sorted(d.date() for d in days if d.date() >= as_of)
    return upcoming[0] if upcoming else None


# ----------------------------------------------------------------------------------------------------------
# position facts
# ----------------------------------------------------------------------------------------------------------
def _ledger_row(ledger: OrderLedger | None, symbol: str, client_order_id: str | None = None) -> dict[str, Any] | None:
    """The ledger row of the live trade: by the position's own client_order_id first (an older, closed trade in
    the same symbol stays ``filled`` in the ledger forever), else the newest live row for the symbol."""
    if ledger is None:
        return None
    if client_order_id:
        row = ledger.get(client_order_id)
        if row is not None and row["symbol"] == symbol:
            return row
    rows = [r for r in ledger.all() if r["symbol"] == symbol and r["status"] not in DEAD_LEDGER_STATUSES]
    filled = [r for r in rows if r["status"] in FILLED]
    pick = filled or rows
    return pick[-1] if pick else None


def _held_facts(
    position: Position,
    orders: list[dict[str, Any]],
    ledger: OrderLedger | None,
    broker: Any,
    known: Iterable[str],
) -> _Held:
    held = _Held(position=position, strategy=position.strategy, current_stop=position.stop)
    sym_orders = [o for o in orders if o.get("symbol") == position.symbol]
    for o in sym_orders:
        cid = o.get("client_order_id") or o.get("_parent_client_order_id")
        name = strategy_from_client_order_id(cid, known)
        if name and held.client_order_id is None:
            held.client_order_id = str(cid)
            held.strategy = held.strategy or name
        if held.entry_day is None and _text(o.get("status")) in FILLED:
            held.entry_day = _ny_day(_parse_ts(o.get("filled_at")))
        if _is_stop_leg(o, position):
            stop = _float(o.get("stop_price"))
            if held.current_stop is None or (stop is not None and held.stop_order_id is None):
                held.current_stop = stop
                held.stop_order_id = str(o.get("id")) if o.get("id") else None
    row = _ledger_row(ledger, position.symbol, held.client_order_id)
    if row is not None:
        held.strategy = held.strategy or row["strategy"]
        held.client_order_id = held.client_order_id or row["client_order_id"]
        held.initial_stop = _float((row.get("intent") or {}).get("stop"))
        if held.entry_day is None:
            broker_json = row.get("broker") or {}
            raw = broker_json.get("raw", broker_json) if isinstance(broker_json, Mapping) else {}
            held.entry_day = _ny_day(_parse_ts(raw.get("filled_at"))) or _ny_day(_parse_ts(row.get("created_at")))
    if held.entry_day is None and position.opened_at is not None:
        held.entry_day = _ny_day(_parse_ts(position.opened_at))
    if held.initial_stop is None and held.client_order_id and callable(getattr(broker, "get_order", None)):
        try:
            original = broker.get_order(held.client_order_id) or {}
        except Exception:  # noqa: BLE001 - the original stop is a nice-to-have
            original = {}
        held.initial_stop = _original_stop(original, position)
    if held.initial_stop is None:
        held.initial_stop = held.current_stop
    return held


def _original_stop(order: Mapping[str, Any], position: Position) -> float | None:
    """Stop of a broker order: paper_sim keeps ``stop`` on the order; Alpaca keeps it on the stop leg."""
    direct = _float(order.get("stop"))
    if direct is not None:
        return direct
    for leg in order.get("legs") or []:
        leg_d = dict(leg) if isinstance(leg, Mapping) else {}
        if _is_stop_leg(leg_d, position):
            return _float(leg_d.get("stop_price"))
    return None


# ----------------------------------------------------------------------------------------------------------
# decisions
# ----------------------------------------------------------------------------------------------------------
def _stale_entries(
    orders: list[dict[str, Any]], held_symbols: set[str], settings: Settings, now: datetime
) -> list[ExitAction]:
    after = settings.execution.cancel_unfilled_entries_after_sessions
    out: list[ExitAction] = []
    for o in orders:
        cid = o.get("client_order_id")
        if not is_engine_entry(o):
            continue  # legs and orders this engine did not place are left alone
        partial = _is_partial(o)
        if not partial and (not _is_unfilled(o) or o.get("symbol") in held_symbols):
            continue  # filled parents stay listed while their legs work; their legs are the protection
        submitted = _parse_ts(o.get("submitted_at") or o.get("created_at"))
        if submitted is None:
            continue
        live = sessions_between(submitted, now)
        if live < after:
            continue
        what = f"unfilled remainder of a partial fill ({_filled_qty(o):g} filled)" if partial else "unfilled"
        out.append(
            ExitAction(
                kind=ExitKind.CANCEL_ORDER, symbol=str(o.get("symbol")), reason=ExitReason.STALE_ENTRY,
                order_id=str(o.get("id")) if o.get("id") else None, client_order_id=str(cid),
                strategy=strategy_from_client_order_id(str(cid)),
                detail=f"{what} after {live} session(s) (limit {after})",
            )
        )
    return out


def _hold_limit(strategy: Strategy | None) -> int | None:
    params = getattr(strategy, "params", None) or {}
    for key in HOLD_PARAMS:
        value = params.get(key)
        if value is not None and int(value) >= 1:
            return int(value)
    return None


def _rule_exit(strategy: Strategy | None, row: pd.Series, held: _Held, bars_held: int) -> bool:
    if strategy is None:
        return False
    exit_rule = getattr(strategy, "exit_rule", None)
    if callable(exit_rule):
        pos = SimpleNamespace(
            symbol=held.position.symbol, side=held.position.side, entry=held.position.avg_entry,
            stop=held.current_stop, bars_held=bars_held, strategy=held.strategy,
        )
        return bool(exit_rule(row, pos))
    should_exit = getattr(strategy, "should_exit", None)
    return bool(should_exit(row, bars_held)) if callable(should_exit) else False


def engine_trail_enabled(strategy: Any) -> bool:
    """False when the strategy opts out of the engine overlay (param ``engine_trail`` wins over the attribute)."""
    params = getattr(strategy, "params", None) or {}
    if isinstance(params, Mapping) and params.get(ENGINE_TRAIL_ATTR) is not None:
        return bool(params[ENGINE_TRAIL_ATTR])
    return bool(getattr(strategy, ENGINE_TRAIL_ATTR, True))


def strategy_trail_level(strategy: Any, row: pd.Series) -> float | None:
    """The strategy's ``trail_stop(row)`` as a finite positive float, or None (no hook, no level, or it raised)."""
    hook = getattr(strategy, TRAIL_STOP_HOOK, None)
    if not callable(hook):
        return None
    try:
        level = _float(hook(row))
    except Exception as exc:  # noqa: BLE001 - a broken trail must not block the other exits
        log.warning("strategy_trail_failed", strategy=getattr(strategy, "name", None), error=str(exc))
        return None
    return level if level is not None and np.isfinite(level) and level > 0 else None


def _engine_candidate(
    frame: pd.DataFrame, settings: Settings, entry: float, risk: float, close: float, long: bool
) -> tuple[float, ExitReason, str] | None:
    cfg = settings.execution
    r_now = ((close - entry) if long else (entry - close)) / risk
    window = frame.tail(cfg.trail_lookback_days)
    if cfg.trail_after_r is not None and r_now >= cfg.trail_after_r:
        extreme = float(window["low"].min()) if long else float(window["high"].max())
        return (max(entry, extreme) if long else min(entry, extreme)), ExitReason.TRAIL, f"{r_now:.2f}R"
    if cfg.breakeven_after_r is not None and r_now >= cfg.breakeven_after_r:
        return entry, ExitReason.BREAKEVEN, f"{r_now:.2f}R"
    return None


def _trail_stop(
    held: _Held, frame: pd.DataFrame, settings: Settings, strategy: Strategy | None = None
) -> tuple[float, ExitReason, str] | None:
    """New (tighter) stop from the R ladder and/or the strategy's indicator trail, or None. Long/short mirrored."""
    pos = held.position
    entry, init, cur = pos.avg_entry, held.initial_stop, held.current_stop
    close = float(frame["close"].iloc[-1])
    long = pos.side == Side.LONG
    cands: list[tuple[float, ExitReason, str]] = []
    if init is not None and engine_trail_enabled(strategy):
        risk = entry - init if long else init - entry
        if risk > 0:
            engine = _engine_candidate(frame, settings, entry, risk, close, long)
            if engine is not None:
                cands.append(engine)
    if strategy is not None:
        level = strategy_trail_level(strategy, frame.iloc[-1].drop(labels="_day", errors="ignore"))
        if level is not None:
            cands.append((level, ExitReason.STRATEGY_TRAIL, f"{getattr(strategy, 'name', 'strategy')} trail"))
    # a candidate at/through the market is dropped (next session decides); it must not mask a valid one
    cands = [
        (round(c, PRICE_DECIMALS), r, w) for c, r, w in cands
        if (long and round(c, PRICE_DECIMALS) < close) or (not long and round(c, PRICE_DECIMALS) > close)
    ]
    if not cands:
        return None
    candidate, reason, why = max(cands, key=lambda c: c[0]) if long else min(cands, key=lambda c: c[0])
    if cur is not None:
        cur_r = round(cur, PRICE_DECIMALS)
        if (long and candidate <= cur_r) or (not long and candidate >= cur_r):
            return None  # never loosen (or no-op)
    return candidate, reason, f"{why} at close {close:.2f}; stop {cur} -> {candidate}"


def _missing_stop(
    held: _Held,
    frame: pd.DataFrame,
    settings: Settings,
    ref: float,
    base: Mapping[str, Any],
    strategy: Strategy | None = None,
) -> ExitAction | None:
    """A strategy-owned position with no open stop order: re-arm one, or close when it would already be hit."""
    if held.current_stop is not None:
        return None
    long = held.position.side == Side.LONG
    stop = held.initial_stop
    if stop is None:
        return ExitAction(kind=ExitKind.FLAG, reason=ExitReason.NO_STOP, **base,
                          detail="no open stop order and no recorded stop; protect it by hand")
    trail = _trail_stop(held, frame, settings, strategy)
    if trail is not None:
        stop = max(stop, trail[0]) if long else min(stop, trail[0])
    stop = round(stop, PRICE_DECIMALS)
    if (long and stop >= ref) or (not long and stop <= ref):
        return ExitAction(kind=ExitKind.CLOSE, reason=ExitReason.NO_STOP, ref_price=ref, **base,
                          detail=f"no open stop order; recorded stop {stop} is already through the close {ref:.2f}")
    return ExitAction(kind=ExitKind.PLACE_STOP, reason=ExitReason.NO_STOP, new_stop=stop, ref_price=ref, **base,
                      detail=f"no open stop order; re-arm at {stop}")


def _review_one(
    held: _Held,
    frame: pd.DataFrame,
    strategy: Strategy | None,
    settings: Settings,
    as_of: date,
    earnings: pd.DataFrame | None,
) -> list[ExitAction]:
    pos = held.position
    base: dict[str, Any] = {
        "symbol": pos.symbol, "qty": pos.qty, "strategy": held.strategy, "side": pos.side,
        "client_order_id": held.client_order_id,
    }
    eday = _earnings_day(earnings, pos.symbol, as_of)
    until = trading_sessions_until(as_of, eday) if eday is not None else None
    near_earnings = until is not None and until <= settings.execution.earnings_exit_days
    if held.strategy is None:
        note = f"; earnings {eday} in {until} session(s)" if near_earnings else ""
        return [ExitAction(kind=ExitKind.FLAG, reason=ExitReason.ORPHAN, **base,
                           detail=f"no strategy recoverable; not auto-closed{note}")]
    if frame.empty:
        return [ExitAction(kind=ExitKind.FLAG, reason=ExitReason.NO_DATA, **base, detail=f"no panel rows <= {as_of}")]
    row = frame.iloc[-1]
    ref = float(row["close"])
    if near_earnings:
        return [ExitAction(kind=ExitKind.CLOSE, reason=ExitReason.EARNINGS, ref_price=ref, **base,
                           detail=f"earnings {eday} in {until} session(s)")]
    bars_held: int | None = None
    if held.entry_day is not None:
        bars_held = int((frame["_day"] >= pd.Timestamp(held.entry_day)).sum())
    limit = _hold_limit(strategy)
    if limit is not None and bars_held is not None and bars_held >= limit:
        return [ExitAction(kind=ExitKind.CLOSE, reason=ExitReason.TIME_STOP, ref_price=ref, **base,
                           detail=f"held {bars_held} sessions >= {limit}")]
    if _rule_exit(strategy, row.drop(labels="_day"), held, bars_held or 0):
        return [ExitAction(kind=ExitKind.CLOSE, reason=ExitReason.STRATEGY_EXIT, ref_price=ref, **base,
                           detail=f"{held.strategy} exit rule fired (held {bars_held} sessions)")]
    unprotected = _missing_stop(held, frame, settings, ref, base, strategy)
    if unprotected is not None:
        return [unprotected]
    trail = _trail_stop(held, frame, settings, strategy)
    if trail is None:
        return []
    new_stop, reason, detail = trail
    return [ExitAction(kind=ExitKind.REPLACE_STOP, reason=reason, new_stop=new_stop, order_id=held.stop_order_id,
                       ref_price=ref, **base, detail=detail)]


def review_positions(
    settings: Settings,
    broker: Any,
    panel: pd.DataFrame | None,
    as_of: date,
    strategies: Mapping[str, Any] | Iterable[Any] | None = None,
    earnings: pd.DataFrame | None = None,
    *,
    ledger: OrderLedger | None = None,
    now: datetime | None = None,
) -> list[ExitAction]:
    """Exit decisions for every open position and stale entry, ordered cancel -> close -> replace_stop -> flag.

    ``ledger`` defaults to ``settings.execution.ledger_file`` when that file exists; ``now`` (for the stale
    entry clock) defaults to the wall clock when ``as_of`` is today, else the end of ``as_of`` in New York.
    """
    strategy_map = build_strategies(settings, strategies)
    own_ledger = ledger is None
    if own_ledger:
        ledger = _open_ledger(settings)
    try:
        positions = list(broker.positions())
        orders = flatten_orders(broker.open_orders())
        actions = _stale_entries(orders, {p.symbol for p in positions}, settings, now or _default_now(as_of))
        for position in positions:
            try:
                held = _held_facts(position, orders, ledger, broker, strategy_map)
                frame = _symbol_frame(panel, position.symbol, as_of)
                strategy = strategy_map.get(held.strategy) if held.strategy else None
                actions.extend(_review_one(held, frame, strategy, settings, as_of, earnings))
            except Exception as exc:  # noqa: BLE001 - one bad position must not hide every other exit
                log.error("position_review_failed", symbol=position.symbol, error=f"{type(exc).__name__}: {exc}")
                actions.append(
                    ExitAction(kind=ExitKind.FLAG, symbol=position.symbol, reason=ExitReason.ERROR,
                               qty=position.qty, side=position.side, strategy=position.strategy,
                               detail=f"review failed: {type(exc).__name__}: {exc}")
                )
    finally:
        if own_ledger and ledger is not None:
            ledger.close()
    actions.sort(key=lambda a: KIND_ORDER[a.kind])
    log.info(
        "positions_reviewed", as_of=str(as_of), positions=len(positions),
        actions={k.value: sum(a.kind == k for a in actions) for k in ExitKind},
    )
    return actions
