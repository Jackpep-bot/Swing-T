"""Intraday chain cards: plans, refusals, 1-minute walker, grader and report (video-model plan P1 items 7 and 8).

The spec is ``docs/preregistration/2026-10-13-intraday-chains.md``; this module implements it and nothing else.
Every place the spec left a choice open is listed in ``READINGS`` (printed in the results file). Run once::

    uv run python -m swing_engine.research.intraday_chains --settings config/live.yaml \
        --out docs/preregistration/2026-10-13-intraday-chains-results.md

Shape: ``build_ctx`` (one symbol's 1-minute bars -> 15m events, 2m rejections, arrays), ``chain_outcome`` (pure:
one sweep -> a trade plan or a refusal naming the step), ``simulate`` (daily cap, one position, the walker),
``walk`` (stop / target / time exit on 1-minute bars), ``run`` (all symbols, parquet, trials, markdown).

No look-ahead: a 15m or 2m event is used only once its bar has closed (``k`` = the bar's ``ts_close``), and every
quantity of a plan is fixed by bars that closed at or before the entry instant.
"""
from __future__ import annotations

import argparse
import math
import time
from bisect import bisect_right
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.data.intraday import DEFAULT_SYMBOLS, TABLE, _bounds, is_crypto, resample
from swing_engine.features.market_structure import (
    BAR_COLUMNS,
    EXTRACTOR_VERSION,
    extract_events,
    extract_zones,
    rejections,
)
from swing_engine.research.leaderboard import MIN_BLOCKS
from swing_engine.research.metrics import haircut_sharpe
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-13-intraday-chains.md"
OUT = "docs/preregistration/2026-10-13-intraday-chains-results.md"
DATA_DIR = "data/research/intraday_chains"
TAG = "intraday-chains"

CARD_OB, CARD_FVG, CARD_CONTROL = "lit_chain_ob", "lit_chain_fvg", "sweep_reversal_control"
CARDS = (CARD_OB, CARD_FVG, CARD_CONTROL)
STRUCTURE_TF, TRIGGER_TF = "15m", "2m"
ZONE_LAG = pd.Timedelta(minutes=13)  # 15m bar length minus 2m bar length (spec, step 4)
RETRACE_MAX_BARS = 26  # price must trade back into the zone within this many 15m bars of the shift
FVG_BARS_AFTER_SHIFT = 1  # card 2: the gap's ts_event is at most this many bars after the shift
CONTROL_POOLS = ("PDH", "PDL")
TICK = {"SPY": 0.01, "QQQ": 0.01, "IWM": 0.01, "GLD": 0.01, "BTC/USD": 1.0}
BTC_TAKER_BPS, BTC_SLIPPAGE_BPS = 25.0, 5.0
COST_BPS_PER_SIDE = {"SPY": 1.0, "QQQ": 1.0, "IWM": 1.0, "GLD": 1.5, "BTC/USD": BTC_TAKER_BPS + BTC_SLIPPAGE_BPS}
BPS = 1e4
MIN_STOP_FRAC = 0.0005  # stop_too_tight: stop distance under 0.05% of the entry price
MIN_TARGET_R = 1.0  # a pool target must be at least this far from entry
FALLBACK_TARGET_R = 2.0  # no such pool (and always for the control): this multiple of R
MAX_ENTRIES_PER_DAY = 5
ENTRY_CUTOFF_BEFORE_CLOSE = pd.Timedelta(minutes=30).value  # ETFs: no entry after 15:30 on a 16:00 close
FLAT_BEFORE_CLOSE = pd.Timedelta(minutes=5).value  # ETFs: out at the open of the 15:55 bar
CRYPTO_MAX_HOLD = pd.Timedelta(hours=24).value
WINDOWS: dict[str, tuple[date, date]] = {"A": (date(2016, 1, 1), date(2023, 12, 31)),
                                         "B": (date(2024, 1, 1), date(2026, 10, 9))}
N_GROUP_TRIALS = 6  # 3 cards x 2 windows
MIN_TRADES = 200  # pass rule 1, per window
MIN_SYMBOLS_POSITIVE_B = 3  # pass rule 4
REGIME_SMA_DAYS = 200
REFUSAL_STEPS = ("no_shift", "shift_failed", "no_zone", "no_retrace", "zone_dead", "no_trigger", "stop_too_tight",
                 "no_room", "daily_cap", "position_open", "too_late")

INF = np.iinfo(np.int64).max
MINUTE = pd.Timedelta(minutes=1).value
DAY = pd.Timedelta(days=1).value
EPOCH_ORDINAL = date(1970, 1, 1).toordinal()

READINGS: tuple[str, ...] = (
    "ETF structure is built from regular-hours minutes only (pre- and post-market bars are dropped before "
    "resampling), so PDH / PDL are regular-session highs and lows. BTC uses every minute; its day is the UTC date.",
    "`extract_events` gets only ts/open/high/low/close/volume at default parameters, so there are no session "
    "events and no PSH / PSL pools: the pools are EQH, EQL, PDH, PDL.",
    "An event is usable once its bar has closed (docs/market-structure.md), not at the bar's open. Entry is at or "
    "after the close of every 15m and 2m bar the plan used.",
    "'At or after the mitigation' (step 4): the 2m rejection bar must close at or after the close of the 15m bar "
    "that mitigated the zone. A rejection inside the mitigating 15m bar does not count unless it closes with it.",
    "'A rejection at that zone' is a `rejection` event whose `ref_event_id` is the zone. The extractor attributes a "
    "bar to the newest matching zone only, so a wick into two overlapping zones counts for the newer one.",
    "Step 2 takes the first `mss` whose `ref_event_id` is the sweep. `shift_failed` / `zone_dead`: the `mss_failed` "
    "or the zone's terminal event (ob_invalidated / ob_consumed / ob_expired, fvg_inverted) is known at or before "
    "the entry instant, or before the step at which the chain would otherwise have stopped (the 26-bar deadline for "
    "`no_retrace`; any time for `no_trigger`). If both apply the earlier one is logged; a tie logs `shift_failed`.",
    "'Within 26 15m bars of the shift' counts bars of the 15m frame (for ETFs 26 bars is one regular session), not "
    "clock time.",
    "Card 2: the gap is the latest bullish/bearish `fvg_formed` whose bar is from the sweep bar to one bar after the "
    "shift bar, inclusive. 'Trade back into the gap' is the first 15m bar after both the gap and the shift whose low "
    "is at or below the gap's top (longs; mirrored for shorts), at most 26 bars after the shift. A gap that ages out "
    "(300 bars) without a rejection logs `no_trigger`.",
    "Card 3: a closed-back sweep qualifies when any pool the bar took (`meta.pool_ids`) is a PDH or PDL.",
    "Stop distance is signed: an entry price at or beyond the stop also logs `stop_too_tight`.",
    "Target pools: `pool_formed` levels on the opposite side (buy-side pools for longs) whose forming bar closed by "
    "entry, not pierced by any 15m bar closed by entry (a level whose pool the extractor replaced with a wider "
    "cluster still counts while unpierced), at least 1R beyond entry; the nearest one. Otherwise 2R.",
    "Refusal order when several apply: `stop_too_tight`, `too_late`, `daily_cap`, `position_open`. A refused chain "
    "does not count towards the daily cap. Cap and one-position rule are per card and symbol.",
    "ETF clock rules are measured from that day's close: no entry later than 30 minutes before it (15:30 on a "
    "normal day, 12:30 on a 13:00 close), out at the open of the minute 5 minutes before it (15:55 / 12:55). An "
    "entry bar that falls on a later day than its trigger (trigger in the day's last bar) logs `too_late`.",
    "Time exits fill at the open of the first 1-minute bar at or after the exit instant (BTC: entry + 24h). If the "
    "data has no such bar before the close, the last bar's close is used.",
    "The stop is checked before the target in every minute, including the entry minute. A minute that opens "
    "through the stop fills at its open; the target fills at the target price, never better.",
    "A position is open through the minute in which its stop or target filled; a new entry needs a later minute. "
    "After a fill at a minute's open (gap, time exit) an entry at that same open is allowed.",
    "Round-trip cost = per-side rate x (entry price + exit price). Win rate is the share of trades with net R > 0.",
    "MFE / MAE use the full range of every minute before the exit minute, plus the exit minute's open and the exit "
    "price. MAE is reported as a positive number of R.",
    "A trade belongs to the window of its entry day (New York date for ETFs, UTC date for BTC); a refusal to the "
    "window of its entry day if the chain got that far, else of its sweep bar. Daily blocks pool all symbols by that date. Sharpe = t / sqrt(window years), haircut "
    "as in research.leaderboard (no t below 8 trading days; a non-positive Sharpe is reported unhaircut).",
    "Rule 4 counts a symbol with no window-B trades as not above 0.",
    "Regime: SPY's last regular-session close against its 200-session simple average, both as of the session before "
    "the entry day (from the 1-minute data). 'unknown' for the first 200 sessions.",
)


def _ns(values: Any) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit("ns").asi8


def _ts(ns: int) -> pd.Timestamp:
    return pd.Timestamp(int(ns), tz="UTC")


def _day(ordinal: int) -> date:
    return date.fromordinal(EPOCH_ORDINAL + int(ordinal))


# ============================================================================================ context
class Ctx:
    """One symbol: 15m bars and events, 2m bars and rejections at the 15m zones, 1m bars, as arrays and lookups.

    ``i`` is a bar index of the event's own frame and ``k`` the instant (ns) that bar closed.
    """

    def __init__(self, symbol: str, bars15: pd.DataFrame, events15: pd.DataFrame, bars2: pd.DataFrame,
                 rej2: pd.DataFrame, bars1: pd.DataFrame) -> None:
        self.symbol, self.crypto = symbol, is_crypto(symbol)
        self.tick, self.cost = TICK[symbol], COST_BPS_PER_SIDE[symbol] / BPS
        self.t15, self.c15 = _ns(bars15["ts"]), _ns(bars15["ts_close"])
        self.o15, self.h15, self.l15 = (bars15[c].to_numpy(dtype=float) for c in ("open", "high", "low"))
        self.t2, self.c2, self.o2 = _ns(bars2["ts"]), _ns(bars2["ts_close"]), bars2["open"].to_numpy(dtype=float)
        self.t1 = _ns(bars1["ts"])
        self.o1, self.h1, self.l1, self.cl1 = (bars1[c].to_numpy(dtype=float) for c in ("open", "high", "low", "close"))
        self.day15, self.close15 = self._sessions(self.t15)
        self.day2, self.close2 = self._sessions(self.t2)

        self.sweeps: list[dict] = []  # closed-back sweeps: the chain starts
        self.mss: dict[str, dict] = {}  # sweep id -> first mss that refers to it
        self.failed: dict[str, int] = {}  # mss id -> k of its mss_failed
        self.ob: dict[str, dict] = {}  # structure_break id -> ob_confirmed
        self.mit: dict[str, dict] = {}  # ob id -> ob_mitigated
        self.dead: dict[str, int] = {}  # zone id -> k of its terminal event
        self.fvg: dict[str, tuple[list[int], list[dict]]] = {"bull": ([], []), "bear": ([], [])}
        self.pool_label: dict[str, str] = {}
        pools: dict[str, list[tuple]] = {"BSL": [], "SSL": []}
        swept: dict[str, int] = {}
        ev = events15
        idx = np.searchsorted(self.t15, _ns(ev["ts_event"]))
        cols = ("event_id", "kind", "direction", "label", "level", "high", "low", "zone_low", "zone_high",
                "strength", "ref_event_id", "meta")
        for i, *vals in zip(idx.tolist(), *(ev[c].tolist() for c in cols), strict=True):
            r = dict(zip(("id", "kind", "d", "label", "level", "high", "low", "zl", "zh", "strength", "ref", "meta"),
                         vals, strict=True))
            r["i"], r["k"] = i, int(self.c15[i])
            kind, ref = r["kind"], r["ref"]
            if kind == "sweep":
                if r["label"] == "closed_back":
                    self.sweeps.append(r)
            elif kind == "mss":
                if ref is not None:
                    self.mss.setdefault(ref, r)
            elif kind == "mss_failed":
                self.failed.setdefault(ref, r["k"])
            elif kind == "ob_confirmed":
                self.ob.setdefault(ref, r)
            elif kind == "ob_mitigated":
                self.mit.setdefault(ref, r)
            elif kind in ("ob_invalidated", "ob_consumed", "ob_expired", "fvg_inverted"):
                self.dead.setdefault(ref, r["k"])
            elif kind == "fvg_formed":
                self.fvg[r["d"]][0].append(i)
                self.fvg[r["d"]][1].append(r)
            elif kind == "pool_formed":
                self.pool_label[r["id"]] = r["label"]
                pools[r["meta"]["side"]].append((r["level"], i, r["k"], r["id"]))
            elif kind == "pool_swept":
                swept.setdefault(ref, r["k"])
        self.pools = {side: self._pool_arrays(side, rows, swept) for side, rows in pools.items()}

        rej = rej2.loc[rej2["kind"] == "rejection"] if len(rej2) else rej2
        self.rej: dict[str, tuple[list[int], list[str]]] = {}  # zone id -> (2m bar indices, rejection ids), in time order
        if len(rej):
            ridx = np.searchsorted(self.t2, _ns(rej["ts_event"])).tolist()
            for j, zid, rid in zip(ridx, rej["ref_event_id"].tolist(), rej["event_id"].tolist(), strict=True):
                slot = self.rej.setdefault(zid, ([], []))
                slot[0].append(j)
                slot[1].append(rid)

    def _sessions(self, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(day number, that day's session close in ns) per bar: New York dates and the NYSE close for ETFs, UTC
        dates and no close for crypto."""
        if self.crypto or not len(t):
            return t // DAY, np.full(len(t), INF, dtype=np.int64)
        day, _, close = _bounds(pd.Series(pd.DatetimeIndex(t, tz="UTC")))
        return day.to_numpy().astype("datetime64[D]").astype(np.int64), _ns(close)

    def _pool_arrays(self, side: str, rows: list[tuple], swept: dict[str, int]) -> dict[str, np.ndarray]:
        """Pool levels of one side with the instant each was first pierced (``gone``; INF = never). A live pool's
        pierce is its ``pool_swept`` event; a pool the extractor replaced has none, so its level is scanned."""
        gone = []
        for level, i, _, pid in rows:
            k = swept.get(pid)
            if k is None:
                hit = self.h15[i:] > level if side == "BSL" else self.l15[i:] < level
                j = int(hit.argmax()) if hit.size else 0
                k = int(self.c15[i + j]) if hit.size and hit[j] else INF
            gone.append(k)
        return {"level": np.array([r[0] for r in rows], dtype=float), "k": np.array([r[2] for r in rows], dtype=np.int64),
                "gone": np.array(gone, dtype=np.int64), "id": np.array([r[3] for r in rows], dtype=object)}


def build_ctx(symbol: str, bars_1m: pd.DataFrame) -> Ctx:
    """Resample one symbol's ``bars_1m`` rows (ETFs: regular hours only) and extract everything the cards read."""
    b1 = bars_1m if is_crypto(symbol) else bars_1m.loc[bars_1m["session"] == "rth"]
    b1 = b1.sort_values("ts").reset_index(drop=True)
    b15, b2 = resample(b1, STRUCTURE_TF), resample(b1, TRIGGER_TF)
    ohlcv = list(BAR_COLUMNS)
    events = extract_events(b15[ohlcv], symbol, STRUCTURE_TF)
    zones = extract_zones(b15[ohlcv], symbol, STRUCTURE_TF)
    rej = rejections(b2[ohlcv], symbol, TRIGGER_TF, zones, zone_lag=ZONE_LAG)
    return Ctx(symbol, b15, events, b2, rej, b1)


# ============================================================================================== cards
def _refuse(out: dict, step: str) -> dict:
    out["refusal"] = step
    return out


def chain_outcome(cx: Ctx, card: str, sw: dict) -> dict:
    """One chain start (a closed-back 15m sweep) -> a trade plan, or the same dict with ``refusal`` = the step.

    Pure: no state from other chains (the daily cap and the one-position rule are applied in ``simulate``).
    """
    s = 1 if sw["d"] == "bull" else -1
    pool = cx.pool_label.get(sw["ref"], "?")
    out: dict[str, Any] = {"card": card, "symbol": cx.symbol, "direction": "long" if s > 0 else "short",
                           "refusal": None, "sweep_id": sw["id"], "sweep_ts": _ts(cx.t15[sw["i"]]), "sweep_pool": pool,
                           "_day": int(cx.day15[sw["i"]])}
    trail = f"sweep {pool} {sw['level']:.2f} closed_back"
    if card == CARD_CONTROL:
        i = sw["i"] + 1
        if i >= len(cx.t15):
            return _refuse(out, "too_late")
        return _finish(cx, out, sw, s, int(cx.t15[i]), float(cx.o15[i]), int(cx.day15[i]), int(cx.close15[i]),
                       cx.day15[i] != cx.day15[sw["i"]], False, trail)

    m = cx.mss.get(sw["id"])
    if m is None:
        return _refuse(out, "no_shift")
    out.update(mss_id=m["id"], mss_ts=_ts(cx.t15[m["i"]]))
    trail += f" → MSS@15m lvl {m['level']:.2f} disp {m['strength']:.2f}"
    fail_k = cx.failed.get(m["id"], INF)
    deadline = m["i"] + RETRACE_MAX_BARS
    if card == CARD_OB:
        z = cx.ob.get(m["meta"].get("structure_break_id"))
        mit = cx.mit.get(z["id"]) if z else None
        mit_i = mit["i"] if mit is not None and mit["i"] <= deadline else None
    else:
        at, rows = cx.fvg[sw["d"]]
        j = bisect_right(at, m["i"] + FVG_BARS_AFTER_SHIFT) - 1
        z = rows[j] if j >= 0 and at[j] >= sw["i"] else None
        mit_i = None
        if z is not None:
            a = max(z["i"], m["i"]) + 1
            touch = cx.l15[a:deadline + 1] <= z["zh"] if s > 0 else cx.h15[a:deadline + 1] >= z["zl"]
            if touch.any():
                mit_i = a + int(touch.argmax())
    if z is None:
        return _refuse(out, "no_zone")
    out.update(zone_id=z["id"], zone_ts=_ts(cx.t15[z["i"]]), zone_low=z["zl"], zone_high=z["zh"])
    trail += f" → {'OB' if card == CARD_OB else 'FVG'} zone {z['zl']:.2f}–{z['zh']:.2f}"
    dead_k = cx.dead.get(z["id"], INF)

    step, when, trigger = "no_trigger", INF, None
    if mit_i is None:
        step, when = "no_retrace", int(cx.c15[deadline]) if deadline < len(cx.c15) else INF
    else:
        out["retrace_ts"] = _ts(cx.t15[mit_i])
        bars, ids = cx.rej.get(z["id"], ((), ()))
        for j, rid in zip(bars, ids, strict=True):
            if cx.c2[j] >= cx.c15[mit_i] and j + 1 < len(cx.t2):
                trigger, when = (j, rid), int(cx.t2[j + 1])
                break
    if min(fail_k, dead_k) != INF and min(fail_k, dead_k) <= when:
        return _refuse(out, "shift_failed" if fail_k <= dead_k else "zone_dead")
    if trigger is None:
        return _refuse(out, step)
    j, rid = trigger
    out.update(trigger_id=rid, trigger_ts=_ts(cx.t2[j]))
    trail += f" → rejection@2m {_ts(cx.t2[j]):%H:%M}Z"
    return _finish(cx, out, sw, s, when, float(cx.o2[j + 1]), int(cx.day2[j + 1]), int(cx.close2[j + 1]),
                   cx.day2[j + 1] != cx.day2[j], True, trail)


def _finish(cx: Ctx, out: dict, sw: dict, s: int, e_ns: int, price: float, day: int, sclose: int, next_day: bool,
            pool_target: bool, trail: str) -> dict:
    """Entry, stop and target of a chain that reached its entry bar; ``stop_too_tight`` / ``too_late`` if refused."""
    stop = sw["low"] - cx.tick if s > 0 else sw["high"] + cx.tick
    risk = (price - stop) * s
    out.update(entry_ts=_ts(e_ns), entry=price, stop=stop, risk=risk, _e=e_ns, _day=day, _sclose=sclose)
    if risk < MIN_STOP_FRAC * price:
        return _refuse(out, "stop_too_tight")
    if not cx.crypto and (next_day or e_ns > sclose - ENTRY_CUTOFF_BEFORE_CLOSE):
        return _refuse(out, "too_late")
    target, kind, pid = price + s * FALLBACK_TARGET_R * risk, f"{FALLBACK_TARGET_R:g}R", None
    if pool_target:
        p = cx.pools["BSL" if s > 0 else "SSL"]
        dist = (p["level"] - price) * s
        ok = np.flatnonzero((p["k"] <= e_ns) & (p["gone"] > e_ns) & (dist >= MIN_TARGET_R * risk))
        if ok.size:
            j = ok[dist[ok].argmin()]
            target, kind, pid = float(p["level"][j]), "pool " + cx.pool_label[p["id"][j]], p["id"][j]
    out.update(target=target, target_kind=kind, target_pool_id=pid)
    out["lineage"] = (f"{_ts(e_ns):%Y-%m-%d %H:%M}Z {cx.symbol} {STRUCTURE_TF} {out['card']} {out['direction']} — "
                      f"{trail} → entry {price:.2f} sl {stop:.2f} tp {target:.2f} ({kind})")
    return out


def chain_outcomes(cx: Ctx, card: str) -> list[dict]:
    """Every chain start of ``card`` on this symbol, each as a plan or a refusal (before the cap and position rules)."""
    starts = cx.sweeps
    if card == CARD_CONTROL:
        starts = [sw for sw in starts
                  if any(cx.pool_label.get(pid) in CONTROL_POOLS for pid in sw["meta"].get("pool_ids") or [sw["ref"]])]
    return [chain_outcome(cx, card, sw) for sw in starts]


# ============================================================================================= walker
def walk(t: np.ndarray, o: np.ndarray, h: np.ndarray, lo: np.ndarray, c: np.ndarray, entry_ns: int, entry: float,
         stop: float, target: float, s: int, exit_ns: int, hard_ns: int = INF, cost: float = 0.0) -> dict:
    """Walk 1-minute bars from the entry minute. Stop before target in the same minute; a minute that opens
    through the stop fills at its open; at ``exit_ns`` the position is closed at that minute's open (or at the last
    close before ``hard_ns`` / the end of the data). ``cost`` is the per-side rate. Returns exit and R figures;
    ``free_ns`` is the first instant a new entry is allowed."""
    risk = (entry - stop) * s
    i0, ix = int(np.searchsorted(t, entry_ns)), int(np.searchsorted(t, exit_ns))
    adverse = ((lo if s > 0 else h)[i0:ix] - stop) * s <= 0
    hit = np.flatnonzero(adverse | (((h[i0:ix] if s > 0 else lo[i0:ix]) - target) * s >= 0))
    if hit.size:
        j = i0 + int(hit[0])
        if not adverse[j - i0]:
            price, reason, free = target, "target", int(t[j]) + MINUTE
        elif (o[j] - stop) * s < 0:
            price, reason, free = float(o[j]), "stop_gap", int(t[j])
        else:
            price, reason, free = stop, "stop", int(t[j]) + MINUTE
    elif ix < len(t) and t[ix] < hard_ns:
        j, price, reason, free = ix, float(o[ix]), "time", int(t[ix])
    else:
        j = max(ix - 1, i0)
        j = min(j, len(t) - 1)
        price, reason, free = float(c[j]), "time_last_close", int(t[j]) + MINUTE
    path = [entry, price, float(o[j])]
    hi = max(float(h[i0:j].max(initial=-math.inf)), *path)
    low = min(float(lo[i0:j].min(initial=math.inf)), *path)
    gross = (price - entry) * s / risk
    cost_r = cost * (entry + price) / risk
    return {"exit_ts": _ts(t[j]), "exit": price, "exit_reason": reason, "gross_r": gross, "cost_r": cost_r,
            "net_r": gross - cost_r, "mfe_r": ((hi - entry) if s > 0 else (entry - low)) / risk,
            "mae_r": ((entry - low) if s > 0 else (hi - entry)) / risk, "free_ns": free}


def simulate(cx: Ctx, card: str) -> tuple[list[dict], list[dict]]:
    """Trades and refusals of one card on one symbol: plans in entry order, at most ``MAX_ENTRIES_PER_DAY`` entries
    a day, one open position, ETFs flat before the close, BTC out after 24 hours."""
    trades, refusals, plans = [], [], []
    for out in chain_outcomes(cx, card):
        (plans if out["refusal"] is None else refusals).append(out)
    plans.sort(key=lambda p: (p["_e"], p["sweep_ts"]))
    free, per_day = -INF, Counter()
    for p in plans:
        if per_day[p["_day"]] >= MAX_ENTRIES_PER_DAY:
            refusals.append(_refuse(p, "daily_cap"))
        elif p["_e"] < free:
            refusals.append(_refuse(p, "position_open"))
        else:
            s = 1 if p["direction"] == "long" else -1
            exit_ns = p["_e"] + CRYPTO_MAX_HOLD if cx.crypto else p["_sclose"] - FLAT_BEFORE_CLOSE
            res = walk(cx.t1, cx.o1, cx.h1, cx.l1, cx.cl1, p["_e"], p["entry"], p["stop"], p["target"], s, exit_ns,
                       p["_sclose"], cx.cost)
            free = res.pop("free_ns")
            per_day[p["_day"]] += 1
            trades.append({**p, **res})
    for row in trades + refusals:
        row["day"] = _day(row.pop("_day"))
        row.pop("_e", None)
        row.pop("_sclose", None)
    return trades, refusals


# ============================================================================================ grading
def window_of(day: date) -> str | None:
    return next((name for name, (lo, hi) in WINDOWS.items() if lo <= day <= hi), None)


def edge_stats(tr: pd.DataFrame, years: float, n_trials: int) -> dict[str, float]:
    """Trades, win rate, mean R figures, and t / Sharpe / Harvey-Liu haircut on daily blocks (mean net R per day)."""
    out = {"trades": float(len(tr)), "win": math.nan, "gross_r": math.nan, "net_r": math.nan, "mfe_r": math.nan,
           "mae_r": math.nan, "days": 0.0, "t": math.nan, "sharpe": math.nan, "haircut_sharpe": math.nan}
    if tr.empty:
        return out
    means = tr.groupby("day")["net_r"].mean()
    out.update(win=float((tr["net_r"] > 0).mean()), days=float(len(means)),
               **{c: float(tr[c].mean()) for c in ("gross_r", "net_r", "mfe_r", "mae_r")})
    if len(means) >= MIN_BLOCKS and means.std(ddof=1) > 0:
        t = float(means.mean() / means.std(ddof=1) * math.sqrt(len(means)))
        sr = t / math.sqrt(years)
        out.update(t=t, sharpe=sr, haircut_sharpe=haircut_sharpe(sr, years, n_trials)[0] if sr > 0 else sr)
    return out


def grade(trades: pd.DataFrame, n_trials: int, symbols: Sequence[str]) -> dict[str, dict]:
    """Per card: the stats of each window, per-symbol net R in window B, and PASS / FAIL by the spec's four rules."""
    res: dict[str, dict] = {}
    for card in CARDS:
        tr = trades.loc[trades["card"] == card]
        st = {w: edge_stats(tr.loc[tr["window"] == w], ((hi - lo).days + 1) / 365.25, n_trials)
              for w, (lo, hi) in WINDOWS.items()}
        by_sym = tr.loc[tr["window"] == "B"].groupby("symbol")["net_r"].mean()
        n_pos = int(sum(by_sym.get(sym, -1.0) > 0 for sym in symbols))
        rules = [all(s["trades"] >= MIN_TRADES for s in st.values()), all(s["net_r"] > 0 for s in st.values()),
                 all(s["haircut_sharpe"] > 0 for s in st.values()), n_pos >= MIN_SYMBOLS_POSITIVE_B]
        res[card] = {"stats": st, "symbols_positive_b": n_pos, "rules": rules, "verdict": "PASS" if all(rules) else "FAIL"}
    ctrl = res[CARD_CONTROL]["stats"]
    for card in (CARD_OB, CARD_FVG):
        res[card]["beats_control"] = all(res[card]["stats"][w]["net_r"] > ctrl[w]["net_r"] for w in WINDOWS)
    return res


def _f(x: Any, spec: str = "+.3f") -> str:
    return "-" if x is None or not math.isfinite(x) else format(x, spec)


def _table(head: Sequence[str], rows: list[Sequence[str]]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *("| " + " | ".join(r) + " |" for r in rows), ""]


def _stat_cells(tr: pd.DataFrame) -> list[str]:
    if tr.empty:
        return ["0", "-", "-", "-", "-", "-"]
    return [str(len(tr)), _f((tr["net_r"] > 0).mean(), ".1%"), _f(tr["gross_r"].mean()), _f(tr["net_r"].mean()),
            _f(tr["mfe_r"].mean(), ".2f"), _f(tr["mae_r"].mean(), ".2f")]


def render(trades: pd.DataFrame, refusals: pd.DataFrame, res: dict[str, dict], n_trials: int, n_before: int,
           symbols: Sequence[str], note: str = "") -> list[str]:
    """The results markdown: verdicts first, then the pooled, refusal, per-symbol, direction and regime tables."""
    passed = [c for c in CARDS if res[c]["verdict"] == "PASS"]
    lines = ["# Intraday chain cards: results", "",
             f"Graded per `{SPEC}`. One run. Haircut over n_trials = {n_trials} ({n_before} logged before this group "
             f"+ {N_GROUP_TRIALS}). Extractor version {EXTRACTOR_VERSION}. R is |entry - stop|; net R is after the "
             "spec's per-side costs. No sizing, no equity curve.", *([note] if note else []), "",
             "## Verdict", "",
             ("**Nothing passes.** No card meets the pre-registered rule." if not passed else
              "Passed: " + ", ".join(f"`{c}`" for c in passed) + ". A pass allows walk-forward and shadow tracking "
              "only (see the spec)."), ""]
    rows = []
    for c in CARDS:
        r, a, b = res[c], res[c]["stats"]["A"], res[c]["stats"]["B"]
        marks = ["ok" if x else "no" for x in r["rules"]]
        beats = "-" if c == CARD_CONTROL else ("yes" if r["beats_control"] else "no")
        rows.append([f"`{c}`", f"**{r['verdict']}**", f"{a['trades']:.0f} / {b['trades']:.0f} ({marks[0]})",
                     f"{_f(a['net_r'])} / {_f(b['net_r'])} ({marks[1]})",
                     f"{_f(a['haircut_sharpe'], '+.2f')} / {_f(b['haircut_sharpe'], '+.2f')} ({marks[2]})",
                     f"{r['symbols_positive_b']} of {len(symbols)} ({marks[3]})", beats])
    lines += _table(["card", "verdict", "1. trades A / B (>= 200)", "2. net R per trade A / B (> 0)",
                     "3. haircut Sharpe A / B (> 0)", "4. symbols with net R > 0 in B (>= 3)",
                     "net R beats control in both windows"], rows)

    lines += ["## Pooled, per card and window", "",
              "Win = net R above 0. t is on daily blocks (mean net R per day with a trade, all symbols pooled); "
              "Sharpe = t / sqrt(window years).", ""]
    rows = []
    for c in CARDS:
        for w, (lo, hi) in WINDOWS.items():
            s = res[c]["stats"][w]
            rows.append([f"`{c}`", f"{w} {lo:%Y-%m}..{hi:%Y-%m}", f"{s['trades']:.0f}", _f(s["win"], ".1%"),
                         _f(s["gross_r"]), _f(s["net_r"]), _f(s["mfe_r"], ".2f"), _f(s["mae_r"], ".2f"),
                         f"{s['days']:.0f}", _f(s["t"], "+.2f"), _f(s["sharpe"], "+.2f"), _f(s["haircut_sharpe"], "+.2f")])
    lines += _table(["card", "window", "trades", "win rate", "gross R", "net R", "MFE R", "MAE R", "days", "t",
                     "Sharpe", "haircut Sharpe"], rows)

    lines += ["## Chains and refusals by step", "",
              "Every closed-back 15m sweep starts a chain (card 3: PDH / PDL sweeps only). `no_room` cannot occur "
              "(2R fallback).", ""]
    steps = [s for s in REFUSAL_STEPS if s != "no_room"]
    rows = []
    for c in CARDS:
        for w in WINDOWS:
            ref = refusals.loc[(refusals["card"] == c) & (refusals["window"] == w), "refusal"].value_counts()
            n = int(((trades["card"] == c) & (trades["window"] == w)).sum())
            rows.append([f"`{c}`", w, str(n + int(ref.sum())), str(n), *(str(int(ref.get(s, 0))) for s in steps)])
    lines += _table(["card", "window", "chains", "traded", *steps], rows)

    for title, col, note_ in (("By symbol", "symbol", "Descriptive, except that rule 4 reads window B here."),
                              ("By direction", "direction", "Descriptive only."),
                              ("By SPY daily regime", "regime", "Descriptive only. SPY's prior regular-session close "
                               f"against its {REGIME_SMA_DAYS}-session average, both known before the entry day."),
                              ("By exit", "exit_reason", "How trades ended: target, stop, stop_gap (opened through "
                               "the stop), time (15:55 / 24h).")):
        lines += [f"## {title}", "", note_, ""]
        rows = []
        for c in CARDS:
            for w in WINDOWS:
                sub = trades.loc[(trades["card"] == c) & (trades["window"] == w)]
                for key in (symbols if col == "symbol" else sorted(sub[col].dropna().unique())):
                    rows.append([f"`{c}`", w, str(key), *_stat_cells(sub.loc[sub[col] == key])])
        lines += _table(["card", "window", col.replace("_", " "), "trades", "win rate", "gross R", "net R", "MFE R",
                         "MAE R"], rows)

    lines += ["## Costs", ""]
    rows = [[sym, f"{COST_BPS_PER_SIDE[sym]:g} bp", _f(trades.loc[trades["symbol"] == sym, "cost_r"].mean(), ".3f"),
             _f((trades.loc[trades["symbol"] == sym, "risk"] / trades.loc[trades["symbol"] == sym, "entry"]).median()
                * BPS, ".1f")] for sym in symbols]
    lines += _table(["symbol", "cost per side", "mean round-trip cost in R", "median stop distance (bp of price)"], rows)
    lines += ["## How the spec was read", "",
              "Each point is a choice the spec left open, fixed in code before the run.", "",
              *(f"{n}. {text}" for n, text in enumerate(READINGS, 1)), ""]
    return lines


# ============================================================================================= runner
def spy_regime(store: Any) -> tuple[np.ndarray, np.ndarray]:
    """(session dates, 'above' / 'below' / 'unknown' as of each session's close) for SPY against its
    ``REGIME_SMA_DAYS``-session average, from the regular-hours minutes."""
    d = store.sql(f"SELECT CAST(ts AS DATE) AS day, arg_max(close, ts) AS close FROM {TABLE} "
                  "WHERE symbol = 'SPY' AND session = 'rth' GROUP BY 1 ORDER BY 1")
    sma = d["close"].rolling(REGIME_SMA_DAYS).mean()
    state = np.where(sma.isna(), "unknown", np.where(d["close"] > sma, "above", "below"))
    return np.array([pd.Timestamp(x).date() for x in d["day"]], dtype=object), state


def _frame(rows: list[dict], regime: tuple[np.ndarray, np.ndarray]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["card", "symbol", "direction", "refusal", "day", "window", "regime", "net_r",
                                     "gross_r", "mfe_r", "mae_r", "cost_r", "risk", "entry", "exit_reason"])
    days, state = regime
    prev = np.searchsorted(days, df["day"].to_numpy(), side="left") - 1  # the last SPY session before the day
    df["regime"] = np.where(prev >= 0, state[np.clip(prev, 0, None)], "unknown") if len(days) else "unknown"
    df["window"] = df["day"].map(window_of)
    return df


def run(store_path: str | Path, out: str | Path = OUT, data_dir: str | Path = DATA_DIR,
        trials_path: str | Path = DEFAULT_TRIALS_PATH, symbols: Sequence[str] = tuple(DEFAULT_SYMBOLS)) -> dict[str, dict]:
    """The whole pre-registered run: every symbol and card, parquet, the 6 trials (once), the results markdown."""
    from swing_engine.data.store import Store

    t0 = time.time()
    trades: list[dict] = []
    refusals: list[dict] = []
    with Store(str(store_path), read_only=True) as store:
        regime = spy_regime(store)
        for sym in symbols:
            cx = build_ctx(sym, store.read_table(TABLE, "symbol = ?", [sym], order_by="ts"))
            print(f"{sym}: {len(cx.t1)} 1m, {len(cx.t2)} 2m, {len(cx.t15)} 15m bars, {len(cx.sweeps)} closed-back "
                  f"sweeps ({time.time() - t0:.0f}s)", flush=True)
            for card in CARDS:
                tr, ref = simulate(cx, card)
                trades += tr
                refusals += ref
                print(f"  {card}: {len(tr)} trades, {len(ref)} refusals ({time.time() - t0:.0f}s)", flush=True)
            del cx
    tdf, rdf = _frame(trades, regime), _frame(refusals, regime)
    folder = Path(data_dir) if Path(data_dir).is_absolute() else ROOT / data_dir
    folder.mkdir(parents=True, exist_ok=True)
    tdf.to_parquet(folder / "trades.parquet", index=False)
    rdf.to_parquet(folder / "refusals.parquet", index=False)

    logged = list(iter_trials(trials_path))
    mine = sum(TAG in (r.get("tags") or []) for r in logged)
    n_before = len(logged) - mine
    n_trials = n_before + N_GROUP_TRIALS
    res = grade(tdf, n_trials, symbols)
    if mine == 0:
        for card in CARDS:
            for w, (lo, hi) in WINDOWS.items():
                log_trial(card, {"window": w, "start": lo, "end": hi, "symbols": list(symbols), "spec": SPEC,
                                 "extractor_version": EXTRACTOR_VERSION, "n_trials": n_trials},
                          res[card]["stats"][w], trials_path, tags=[TAG, f"window-{w}"],
                          notes=f"pre-registered intraday chain card; group verdict {res[card]['verdict']}")
    last = max((r["entry_ts"] for r in trades), default=None)
    note = (f"Trades: {len(tdf)} (last entry {last:%Y-%m-%d}); refusals: {len(rdf)}. Rows in "
            f"`{DATA_DIR}/trades.parquet` and `refusals.parquet`, each trade with its chain lineage line."
            if last is not None else "No trades.")
    lines = render(tdf, rdf, res, n_trials, n_before, symbols, note)
    out_path = Path(out) if Path(out).is_absolute() else ROOT / out
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done in {time.time() - t0:.0f}s; trials {'logged' if mine == 0 else 'already logged, not repeated'}; "
          f"wrote {out_path}", flush=True)
    print("\n".join(lines[: lines.index("## Pooled, per card and window")]), flush=True)
    return res


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/live.yaml")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    run(ROOT / settings.data.intraday_store_path, args.out)


if __name__ == "__main__":
    main()
