"""Market-regime playbook: classify the tape, then say which strategies may open trades and at what risk.

NOT a registered strategy. ``registry.discover()`` imports every module in this package; this one has no
``@register`` so it adds nothing to the strategy registry (it only defines functions and a model).

``market_state(panel, as_of)`` reads three deterministic inputs, each from rows dated on or before ``as_of``:

- **Index trend** (``spy_trend``): the ``settings.playbook.market_symbol`` rows of the panel (SPY), same
  rule as ``features.regime.trend_state``: ``up`` = close > sma_50 > sma_200 with sma_50 above its value
  5 bars earlier, ``down`` = the mirror, else ``mixed``. Falls back to the broadcast ``market_trend_state``
  column when the panel has no SPY rows. The SPY 200-day filter (docs/methods.md 2a) separately marks a
  close below sma_200.
- **Volatility** (``vol_regime``): percentile of SPY's vol_21d within its trailing ``vol_lookback`` bars,
  ``<= vol_low_pct`` low, ``>= vol_high_pct`` high (the features/regime.py bands); fallback
  ``market_vol_regime``.
- **Breadth** (``breadth``): ``features.breadth.market_breadth`` on the session: % above the 50-day, the
  Stockbee 10-day 4% ratio and % above the 200-day (Hill's on/off hysteresis over the breadth history) against
  the settings thresholds (docs/methods/06-breadth-regime-filters.md C, D). "strong", the state that allows
  breakouts, needs the ratio >= 2 or the 200-day line on (docs/methods.md 7a #1), confirmed by Keller's 50% line.

Regime, first match wins (docs/methods.md 0 item 5, 2a, 3c):

1. ``high_vol_selloff``  volatility high and SPY below its 50-day (or in a downtrend)
2. ``correction``        SPY in a downtrend or below its 200-day: no new longs
3. ``healthy_uptrend``   SPY uptrend and strong breadth: breakouts allowed
4. ``narrow_uptrend``    SPY uptrend without strong breadth (index at highs, average stock lagging: Oct 2026)
5. ``choppy``            everything else (SPY above its 200-day without a clean trend, or no index data)

``select_strategies(state, settings)`` maps the regime through ``settings.playbook.regimes`` to
``{strategy: risk multiplier in [0, 1]}`` for enabled strategies; a name absent from the table is not
allowed.
Every number here is arithmetic on panel columns and settings; nothing calls a model.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Literal

import numpy as np
import pandas as pd
import structlog
from pydantic import BaseModel, Field

from swing_engine.core.config import PLAYBOOK_REGIMES, PlaybookConfig, Settings, load_settings
from swing_engine.features._common import session_key
from swing_engine.features.breadth import breadth_as_of, market_breadth
from swing_engine.features.cross_section import VOL_WINDOWS, WINDOW_52W, realized_vol
from swing_engine.features.indicators import sma
from swing_engine.features.regime import (
    TREND_DOWN,
    TREND_FAST_WINDOW,
    TREND_SLOPE_LOOKBACK,
    TREND_SLOW_WINDOW,
    TREND_UP,
    trend_state_from,
)

log = structlog.get_logger(__name__)

SpyTrend = Literal["up", "down", "mixed"]
VolState = Literal["low", "normal", "high"]
BreadthState = Literal["strong", "neutral", "weak"]
Regime = Literal["healthy_uptrend", "narrow_uptrend", "choppy", "correction", "high_vol_selloff"]

HEALTHY_UPTREND: Regime = "healthy_uptrend"
NARROW_UPTREND: Regime = "narrow_uptrend"
CHOPPY: Regime = "choppy"
CORRECTION: Regime = "correction"
HIGH_VOL_SELLOFF: Regime = "high_vol_selloff"
#: With no index data at all the router stays conservative: mean reversion only (docs/methods.md 0 item 1).
REGIME_WITHOUT_MARKET: Regime = CHOPPY

SYMBOL = "symbol"
TS = "ts"
CLOSE = "close"
HIGH = "high"
FAST_MA = f"sma_{TREND_FAST_WINDOW}"
SLOW_MA = f"sma_{TREND_SLOW_WINDOW}"
VOL_COL = f"vol_{VOL_WINDOWS[0]}d"
MARKET_TREND_COL = "market_trend_state"
MARKET_VOL_COL = "market_vol_regime"
#: features/regime.py encodings: vol_regime 0 low / 1 normal / 2 high
VOL_CODES: dict[int, VolState] = {0: "low", 1: "normal", 2: "high"}
PCT = 100.0

if set(PLAYBOOK_REGIMES) != {HEALTHY_UPTREND, NARROW_UPTREND, CHOPPY, CORRECTION, HIGH_VOL_SELLOFF}:
    raise RuntimeError("strategies.playbook regimes drifted from core.config.PLAYBOOK_REGIMES")


class MarketState(BaseModel):
    """Deterministic read of the tape on ``as_of``. ``inputs`` carries the numbers behind each call."""

    as_of: date
    spy_trend: SpyTrend = "mixed"
    vol_regime: VolState = "normal"
    breadth: BreadthState = "neutral"
    regime: Regime = REGIME_WITHOUT_MARKET
    notes: list[str] = Field(default_factory=list)
    inputs: dict[str, float] = Field(default_factory=dict)


# --------------------------------------------------------------------------------------------- helpers
def _finite(x: Any) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _as_date(as_of: date | datetime | pd.Timestamp | str) -> date:
    ts = pd.Timestamp(as_of)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    return ts.date()


def _on_or_before(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Rows whose New York session is on or before ``as_of`` (point-in-time cut)."""
    if frame.empty:
        return frame
    return frame.loc[session_key(pd.to_datetime(frame[TS])) <= pd.Timestamp(as_of)]


def _f(x: Any) -> float:
    return float(x) if _finite(x) else math.nan


class _Spy:
    """The SPY numbers the classification needs (NaN where unknown)."""

    def __init__(self) -> None:
        self.session: date | None = None
        self.close = math.nan
        self.sma_fast = math.nan
        self.sma_slow = math.nan
        self.sma_fast_lag = math.nan
        self.trend_code = math.nan
        self.vol_pct = math.nan
        self.vol_code = math.nan
        self.dist_52w_high = math.nan


def _spy_snapshot(panel: pd.DataFrame, as_of: date, cfg: PlaybookConfig) -> _Spy | None:
    """SPY's last bar on or before ``as_of`` with trend / vol inputs, from its own rows of the panel."""
    if SYMBOL not in panel.columns:
        return None
    rows = _on_or_before(panel.loc[panel[SYMBOL] == cfg.market_symbol], as_of)
    if rows.empty:
        return None
    rows = rows.sort_values(TS, kind="mergesort")
    close = rows[CLOSE].astype("float64").reset_index(drop=True)
    fast = (
        rows[FAST_MA].astype("float64").reset_index(drop=True)
        if FAST_MA in rows
        else sma(close, TREND_FAST_WINDOW)
    )
    slow = (
        rows[SLOW_MA].astype("float64").reset_index(drop=True)
        if SLOW_MA in rows
        else sma(close, TREND_SLOW_WINDOW)
    )
    vol = (
        rows[VOL_COL].astype("float64").reset_index(drop=True)
        if VOL_COL in rows
        else realized_vol(close, VOL_WINDOWS[0])
    )
    spy = _Spy()
    spy.session = session_key(pd.to_datetime(rows[TS])).iloc[-1].date()
    spy.close, spy.sma_fast, spy.sma_slow = _f(close.iloc[-1]), _f(fast.iloc[-1]), _f(slow.iloc[-1])
    if len(fast) > TREND_SLOPE_LOOKBACK:
        spy.sma_fast_lag = _f(fast.iloc[-1 - TREND_SLOPE_LOOKBACK])
    spy.trend_code = float(
        trend_state_from(
            pd.Series([spy.close]),
            pd.Series([spy.sma_fast]),
            pd.Series([spy.sma_slow]),
            pd.Series([spy.sma_fast_lag]),
        ).iloc[0]
    )
    window = vol.dropna().iloc[-cfg.vol_lookback :]
    if len(window) >= cfg.vol_lookback and _finite(vol.iloc[-1]):
        spy.vol_pct = float(window.rank(pct=True).iloc[-1])
    if HIGH in rows:
        high_52w = rows[HIGH].astype("float64").iloc[-WINDOW_52W:].max()  # available history up to 252 bars
        if _finite(high_52w) and float(high_52w) > 0 and _finite(spy.close):
            spy.dist_52w_high = (spy.close / float(high_52w) - 1.0) * PCT
    for col, attr in ((MARKET_TREND_COL, "trend_code"), (MARKET_VOL_COL, "vol_code")):
        if not _finite(getattr(spy, attr)) and col in rows and _finite(rows[col].iloc[-1]):
            setattr(spy, attr, float(rows[col].iloc[-1]))
    return spy


def _market_columns_snapshot(panel: pd.DataFrame, as_of: date) -> _Spy | None:
    """Fallback without SPY rows: the broadcast market_trend_state / market_vol_regime on the last session."""
    cols = [c for c in (MARKET_TREND_COL, MARKET_VOL_COL) if c in panel.columns]
    if not cols or TS not in panel.columns:
        return None
    rows = _on_or_before(panel[[TS, *cols]], as_of)
    if rows.empty:
        return None
    last = rows.loc[pd.to_datetime(rows[TS]) == pd.to_datetime(rows[TS]).max()]
    spy = _Spy()
    spy.session = session_key(pd.to_datetime(last[TS])).iloc[-1].date()
    if MARKET_TREND_COL in last and last[MARKET_TREND_COL].notna().any():
        spy.trend_code = float(last[MARKET_TREND_COL].dropna().iloc[-1])
    if MARKET_VOL_COL in last and last[MARKET_VOL_COL].notna().any():
        spy.vol_code = float(last[MARKET_VOL_COL].dropna().iloc[-1])
    if not (_finite(spy.trend_code) or _finite(spy.vol_code)):
        return None
    return spy


# --------------------------------------------------------------------------------------------- classifiers
def classify_trend(spy: _Spy | None) -> tuple[SpyTrend, list[str]]:
    """``up`` / ``down`` / ``mixed`` from the SPY trend code (features.regime rule)."""
    if spy is None or not _finite(spy.trend_code):
        return "mixed", ["spy trend unknown (no market rows or SMA warm-up): mixed"]
    code = int(spy.trend_code)
    trend: SpyTrend = "up" if code == TREND_UP else "down" if code == TREND_DOWN else "mixed"
    if _finite(spy.close) and _finite(spy.sma_fast) and _finite(spy.sma_slow):
        slope = "rising" if _finite(spy.sma_fast_lag) and spy.sma_fast > spy.sma_fast_lag else "not rising"
        note = (
            f"spy {spy.session}: close {spy.close:.2f}, sma_50 {spy.sma_fast:.2f} ({slope}), "
            f"sma_200 {spy.sma_slow:.2f} -> {trend}"
        )
    else:
        note = f"spy trend from market_trend_state={code} -> {trend}"
    return trend, [note]


def classify_vol(spy: _Spy | None, cfg: PlaybookConfig) -> tuple[VolState, list[str]]:
    """``low`` / ``normal`` / ``high`` from SPY's vol_21d percentile (else the market_vol_regime code)."""
    if spy is not None and _finite(spy.vol_pct):
        state: VolState = (
            "low"
            if spy.vol_pct <= cfg.vol_low_pct
            else "high"
            if spy.vol_pct >= cfg.vol_high_pct
            else "normal"
        )
        return state, [f"spy vol_21d percentile {spy.vol_pct:.2f} over {cfg.vol_lookback} bars -> {state}"]
    if spy is not None and _finite(spy.vol_code) and int(spy.vol_code) in VOL_CODES:
        state = VOL_CODES[int(spy.vol_code)]
        return state, [f"vol from market_vol_regime={int(spy.vol_code)} -> {state}"]
    return "normal", ["volatility unknown (warm-up or no market data): normal"]


def slow_line_on(breadth: pd.DataFrame | None, as_of: date, cfg: PlaybookConfig) -> bool | None:
    """Hill's hysteresis on ``pct_above_200`` over the breadth rows dated on or before ``as_of``: on once it
    closes above ``breadth_on_pct_above_200``, off once it closes below ``breadth_off_pct_above_200``, else the
    prior state (off before the first crossing). None when the frame has no ``pct_above_200``."""
    if breadth is None or len(breadth) == 0 or "pct_above_200" not in breadth.columns:
        return None
    idx = pd.to_datetime(pd.Index(breadth.index))
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    order = np.argsort(idx.to_numpy(), kind="stable")
    keep = np.asarray(idx[order].normalize() <= pd.Timestamp(as_of))
    values = breadth["pct_above_200"].to_numpy(dtype="float64")[order][keep]
    if "n_symbols" in breadth.columns:  # a session from too few names reads as unavailable: no crossing
        n = breadth["n_symbols"].to_numpy(dtype="float64")[order][keep]
        values = np.where(n >= cfg.min_breadth_symbols, values, np.nan)
    flips = np.where(values > cfg.breadth_on_pct_above_200, 1.0,
                     np.where(values < cfg.breadth_off_pct_above_200, 0.0, np.nan))
    known = flips[~np.isnan(flips)]
    return bool(known[-1]) if known.size else False


def classify_breadth(
    row: pd.Series | None, cfg: PlaybookConfig, *, slow_on: bool | None = None
) -> tuple[BreadthState, list[str]]:
    """Breadth state from % above the 50-day, the Stockbee 10-day ratio and % above the 200-day (doc 06, C/D).

    weak   : pct_above_50 < weak threshold (40) or ratio_10d <= weak ratio (0.5)
    strong : pct_above_50 at or above Keller's 50% line AND (ratio_10d >= strong ratio (2.0) OR the 200-day
             line on: ``slow_on`` from :func:`slow_line_on`, else pct_above_200 > its on-threshold (60) on this
             row). pct_above_50 > 60 alone is a thrust, not confirmation (docs/methods.md 2a, 7a #1)
    neutral: otherwise, or when breadth is unavailable (no row, fewer than ``min_breadth_symbols`` names)
    """
    if row is None:
        return "neutral", ["breadth unavailable: neutral"]
    n = _f(row.get("n_symbols"))
    if not _finite(n) or n < cfg.min_breadth_symbols:
        return "neutral", [
            f"breadth from {0 if not _finite(n) else int(n)} symbols < {cfg.min_breadth_symbols}: neutral"
        ]
    pct, ratio = _f(row.get("pct_above_50")), _f(row.get("ratio_10d"))
    pct200 = _f(row.get("pct_above_200"))
    if slow_on is None:
        slow_on = _finite(pct200) and pct200 > cfg.breadth_on_pct_above_200
    desc = (
        f"breadth: {_fmt(pct)}% above 50-day, {_fmt(pct200)}% above 200-day "
        f"(line {'on' if slow_on else 'off'}), 10d 4% ratio {_fmt(ratio)} over {int(n)} symbols"
    )
    weak = (_finite(pct) and pct < cfg.breadth_weak_pct_above_50) or (
        _finite(ratio) and ratio <= cfg.breadth_weak_ratio_10d
    )
    ratio_ok = _finite(ratio) and ratio >= cfg.breadth_strong_ratio_10d
    strong = _finite(pct) and pct >= cfg.breadth_confirm_pct_above_50 and (ratio_ok or bool(slow_on))
    state: BreadthState = "weak" if weak else "strong" if strong else "neutral"
    notes = [f"{desc} -> {state}"]
    if state == "neutral" and _finite(pct) and pct > cfg.breadth_strong_pct_above_50:
        notes.append(
            f"{_fmt(pct)}% above the 50-day without ratio >= {cfg.breadth_strong_ratio_10d:g} or the 200-day line "
            "on: an unconfirmed thrust, breakouts stay off"
        )
    return state, notes


def _fmt(x: float) -> str:
    return "nan" if not _finite(x) else f"{x:.1f}" if abs(x) >= 10 else f"{x:.2f}"


def classify_regime(
    spy: _Spy | None, trend: SpyTrend, vol: VolState, breadth: BreadthState
) -> tuple[Regime, list[str]]:
    """First match of high_vol_selloff, correction, healthy_uptrend, narrow_uptrend, choppy (see module)."""
    known = spy is not None and _finite(spy.trend_code)
    close = spy.close if spy is not None else math.nan
    below_fast = spy is not None and _finite(close) and _finite(spy.sma_fast) and close < spy.sma_fast
    below_slow = spy is not None and _finite(close) and _finite(spy.sma_slow) and close < spy.sma_slow
    if vol == "high" and (below_fast or trend == "down"):
        return HIGH_VOL_SELLOFF, [
            "high volatility with SPY below its 50-day / in a downtrend -> high_vol_selloff"
        ]
    if trend == "down" or below_slow:
        why = "SPY downtrend" if trend == "down" else "SPY below its 200-day"
        return CORRECTION, [f"{why} -> correction (no new longs)"]
    if trend == "up":
        if breadth == "strong":
            return HEALTHY_UPTREND, ["SPY uptrend with strong breadth -> healthy_uptrend"]
        return NARROW_UPTREND, [f"SPY uptrend but breadth {breadth} -> narrow_uptrend (no broad breakouts)"]
    if not known:
        return REGIME_WITHOUT_MARKET, [f"no index trend available -> {REGIME_WITHOUT_MARKET} (conservative)"]
    return CHOPPY, ["SPY above its 200-day without a clean trend -> choppy"]


# --------------------------------------------------------------------------------------------- public API
def market_state(
    panel: pd.DataFrame,
    as_of: date | datetime | pd.Timestamp | str,
    breadth: pd.DataFrame | None = None,
    settings: Settings | None = None,
) -> MarketState:
    """Classify the tape on ``as_of`` using only panel rows dated on or before it.

    ``breadth`` is a precomputed ``features.breadth.market_breadth`` frame (pass one when calling this every
    day); when None it is computed from the panel rows up to ``as_of`` excluding the market symbol.
    """
    settings = settings if settings is not None else load_settings()
    cfg = settings.playbook
    day = _as_date(as_of)
    spy = _spy_snapshot(panel, day, cfg) or _market_columns_snapshot(panel, day)
    if breadth is None:
        breadth = market_breadth(_on_or_before(panel, day), exclude=(cfg.market_symbol,))
    brow = breadth_as_of(breadth, day)
    slow_on = slow_line_on(breadth, day, cfg)

    trend, t_notes = classify_trend(spy)
    vol, v_notes = classify_vol(spy, cfg)
    bstate, b_notes = classify_breadth(brow, cfg, slow_on=slow_on)
    regime, r_notes = classify_regime(spy, trend, vol, bstate)
    notes = [*t_notes, *v_notes, *b_notes, *r_notes]
    if (
        spy is not None
        and _finite(spy.dist_52w_high)
        and spy.dist_52w_high >= -cfg.near_high_pct
        and bstate == "weak"
    ):
        notes.append(
            f"bifurcated market: SPY {spy.dist_52w_high:.1f}% from its 52w high with weak breadth "
            "(docs/methods/06 chart signature 3): leaders-only, reduced size"
        )
    if brow is not None and spy is not None and spy.session is not None and brow.name.date() != spy.session:
        notes.append(f"breadth session {brow.name.date()} differs from SPY session {spy.session}")

    inputs: dict[str, float] = {}
    if spy is not None:
        for key, val in (
            ("spy_close", spy.close),
            ("spy_sma_50", spy.sma_fast),
            ("spy_sma_200", spy.sma_slow),
            ("spy_sma_50_lag", spy.sma_fast_lag),
            ("spy_trend_state", spy.trend_code),
            ("spy_vol_pct", spy.vol_pct),
            ("spy_vol_regime", spy.vol_code),
            ("spy_dist_52w_high_pct", spy.dist_52w_high),
        ):
            if _finite(val):
                inputs[key] = float(val)
    if brow is not None:
        for key, val in brow.items():
            if _finite(val):
                inputs[str(key)] = float(val)
    if slow_on is not None:
        inputs["pct_above_200_on"] = 1.0 if slow_on else 0.0

    state = MarketState(
        as_of=day, spy_trend=trend, vol_regime=vol, breadth=bstate, regime=regime, notes=notes, inputs=inputs
    )
    log.debug(
        "playbook.market_state",
        as_of=str(day),
        regime=regime,
        spy_trend=trend,
        vol=vol,
        breadth=bstate,
    )
    return state


def enabled_strategy_names(settings: Settings) -> list[str]:
    """Names enabled in ``settings.strategies`` (``enabled`` defaults to True for a listed name); when none
    are listed, every name in the playbook table (ops.nightly likewise falls back to every registered one).
    """
    listed = [n for n, c in settings.strategies.items() if (c or {}).get("enabled", True)]
    if settings.strategies:
        return sorted(listed)
    return sorted({n for table in settings.playbook.regimes.values() for n in table})


def select_strategies(state: MarketState, settings: Settings | None = None) -> dict[str, float]:
    """``{strategy: risk multiplier in (0, 1]}`` allowed to open new trades in ``state.regime``, by name.

    Only enabled strategies present in ``settings.playbook.regimes[state.regime]`` with a multiplier above 0
    are returned; absent means not allowed. With ``playbook.enabled = false`` every enabled strategy gets 1.0.
    """
    settings = settings if settings is not None else load_settings()
    enabled = enabled_strategy_names(settings)
    if not settings.playbook.enabled:
        return {name: 1.0 for name in enabled}
    table = settings.playbook.regimes.get(state.regime, {})
    out = {
        name: float(np.clip(float(table[name]), 0.0, 1.0))
        for name in enabled
        if name in table and _finite(table[name]) and float(table[name]) > 0.0
    }
    log.debug("playbook.select", regime=state.regime, allowed=out)
    return out


__all__ = [
    "CHOPPY",
    "CORRECTION",
    "HEALTHY_UPTREND",
    "HIGH_VOL_SELLOFF",
    "NARROW_UPTREND",
    "MarketState",
    "classify_breadth",
    "classify_regime",
    "classify_trend",
    "classify_vol",
    "enabled_strategy_names",
    "market_state",
    "select_strategies",
    "slow_line_on",
]
