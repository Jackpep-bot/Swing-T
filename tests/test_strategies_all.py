"""Generic contract over EVERY registered strategy on one synthetic panel (GBM bars on the real NYSE calendar).

For each strategy and 8 as-of sessions spread over the last 400 (plus one pre-holiday session): `signals()` does
not raise, every signal has sane long geometry, signals are point-in-time (the panel truncated at `as_of` gives
the same signals), and the `should_exit` / `trail_stop` hooks survive a panel row (and, when `should_exit` takes it, a
PositionContext built from the day's signal). Strategies needing optional
data columns (sue, insider, revenue surprise, ...) see a panel without them and may return [], but must not raise.
"""
from __future__ import annotations

import math
from datetime import date
from functools import cache

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.interfaces import exit_takes_position
from swing_engine.core.models import EntryType, PositionContext, Side, Signal
from swing_engine.data.calendar import trading_days
from swing_engine.features.extra import ensure_extra, required_extras
from swing_engine.features.panel import build_panel
from swing_engine.strategies._base import PanelStrategy
from tests.features_gbm import NY_TZ, gbm_bars

SESSIONS = 1300
AS_OF_SPAN = 400
N_AS_OF = 8
LAST_DAY = "2026-09-30"
MARKET = "SPY"
SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
# (prefix, mu, sigma, seed): uptrends, downtrends, high-vol and calm names, 10 each
STOCK_GROUPS = [("UP", 0.35, 0.30, 1), ("DN", -0.25, 0.35, 2), ("HV", 0.10, 0.65, 3), ("CA", 0.05, 0.20, 4)]
GROUP_SIZE = 10
SHOCK_PROB = 0.015  # share of stock sessions with a gap (earnings-like jump) and a volume spike
SHOCK_SIGMA = 0.07
SHOCK_VOLUME_MULT = 4.0
IPO_SYMBOL, IPO_SESSIONS = "UP00", 350  # lists late: young-stock code paths and warm-up NaNs
DELISTED_SYMBOL, DELISTED_SESSIONS_AGO = "DN00", 120  # stops trading: must drop out of later scans
HOOK_BARS = 5  # sessions after as_of fed to should_exit / trail_stop
CALENDAR_AS_OF = [date(2025, 12, 23)]  # signal day for the pre-Christmas and Santa-window calendar setups


def _bars() -> pd.DataFrame:
    days = trading_days("2018-01-01", LAST_DAY)[-SESSIONS:]
    idx = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(NY_TZ)
    frames = [
        gbm_bars([f"{p}{i:02d}" for i in range(GROUP_SIZE)], n_bars=SESSIONS, seed=seed, s0=20.0, mu=mu, sigma=sigma)
        for p, mu, sigma, seed in STOCK_GROUPS
    ]
    stocks = pd.concat(frames, ignore_index=True)
    rng = np.random.default_rng(99)
    shock = rng.random(len(stocks)) < SHOCK_PROB
    jump = np.where(shock, rng.normal(0.0, SHOCK_SIGMA, len(stocks)), 0.0)
    factor = np.exp(pd.Series(jump).groupby(stocks["symbol"].to_numpy()).cumsum().to_numpy())
    px = ["open", "high", "low", "close", "vwap", "adj_close"]
    stocks[px] = stocks[px].mul(factor, axis=0)
    stocks.loc[shock, "volume"] *= SHOCK_VOLUME_MULT
    etfs = pd.concat(
        [gbm_bars([MARKET], n_bars=SESSIONS, seed=5, s0=300.0, mu=0.08, sigma=0.16),
         gbm_bars(SECTORS, n_bars=SESSIONS, seed=6, s0=40.0, mu=0.07, sigma=0.22)],
        ignore_index=True,
    )
    bars = pd.concat([stocks, etfs], ignore_index=True)
    bars["ts"] = np.tile(idx, bars["symbol"].nunique())  # gbm_bars uses plain business days; use NYSE sessions
    pos = bars.groupby("symbol").cumcount()
    ipo = (bars["symbol"] == IPO_SYMBOL) & (pos < SESSIONS - IPO_SESSIONS)
    gone = (bars["symbol"] == DELISTED_SYMBOL) & (pos >= SESSIONS - DELISTED_SESSIONS_AGO)
    return bars.loc[~(ipo | gone)].reset_index(drop=True)


@cache
def _base() -> tuple[pd.DataFrame, pd.Series, list[date]]:
    bars = _bars()
    panel = build_panel(bars, bars.loc[bars["symbol"] == MARKET])
    day = panel["ts"].dt.tz_localize(None).dt.normalize()
    sessions = sorted(day.dt.date.unique())
    spread = np.linspace(len(sessions) - AS_OF_SPAN, len(sessions) - 1, N_AS_OF).astype(int)
    as_ofs = sorted({*(sessions[i] for i in spread), *CALENDAR_AS_OF})
    return panel, day, as_ofs


def _panel_for(strat: PanelStrategy) -> pd.DataFrame:
    # only this strategy's extras, as the CLI / nightly attach them: an undeclared dependency fails here
    return ensure_extra(_base()[0], required_extras([strat]))


def _finite(x) -> bool:
    return x is not None and math.isfinite(float(x))


def _check_signal(s: Signal, name: str, as_of: date, present: set[str]) -> None:
    where = f"{name} {as_of} {s.symbol}"
    assert isinstance(s, Signal), where
    assert s.strategy == name and s.side == Side.LONG and s.as_of == as_of, where
    assert isinstance(s.entry_type, EntryType), where
    assert _finite(s.entry) and _finite(s.stop) and s.entry > 0, f"{where}: entry={s.entry} stop={s.stop}"
    assert s.stop < s.entry, f"{where}: stop {s.stop} >= entry {s.entry}"
    assert s.target is None or (_finite(s.target) and s.target > s.entry), f"{where}: target {s.target}"
    assert _finite(s.score), f"{where}: score {s.score}"
    assert s.symbol in present, f"{where}: symbol has no bar on as_of"


def _check_hooks(strat: PanelStrategy, rows: pd.DataFrame, name: str, sigs: dict[str, Signal]) -> None:
    overrides_trail = not getattr(type(strat).trail_stop, "default_hook", False)
    with_position = exit_takes_position(strat.should_exit)
    bars_held = rows.groupby("symbol").cumcount() + 1
    for held, (_, row) in zip(bars_held, rows.iterrows(), strict=True):
        sig = sigs.get(row["symbol"])
        ctx = PositionContext(
            entry_price=sig.entry if sig else float(row["open"]), stop=sig.stop if sig else None, bars_held=int(held),
            best_price=float(row["high"]), entry_features=sig.features if sig else {}, as_of=sig.as_of if sig else None,
        )
        # live (position_manager) passes the panel row; run_backtest passes it indexed by (ts, symbol)
        for r in (row, row.drop(["ts", "symbol"]).rename((row["ts"], row["symbol"]))):
            bool(strat.should_exit(r, held))
            if with_position:
                bool(strat.should_exit(r, held, ctx))
            if overrides_trail:
                level = strat.trail_stop(r)
                assert level is None or (_finite(level) and float(level) > 0), (
                    f"{name} trail_stop={level!r} on {row['symbol']} {row['ts'].date()}"
                )


@pytest.mark.parametrize("name", registry.names("strategy"))
def test_strategy_contract(name: str) -> None:
    strat = registry.get("strategy", name)()
    panel = _panel_for(strat)
    _, day, as_ofs = _base()
    for as_of in as_ofs:
        cutoff = pd.Timestamp(as_of)
        present = set(panel.loc[day == cutoff, "symbol"])
        sigs = strat.signals(panel, as_of)
        for s in sigs:
            _check_signal(s, name, as_of, present)
        truncated = strat.signals(panel.loc[day <= cutoff], as_of)
        assert [s.model_dump_json() for s in truncated] == [s.model_dump_json() for s in sigs], (
            f"{name} {as_of}: future bars changed today's signals"
        )
        held = {s.symbol for s in sigs} or set(sorted(present)[:3])
        after = panel.loc[panel["symbol"].isin(held) & (day > cutoff)]
        _check_hooks(strat, after.groupby("symbol").head(HOOK_BARS), name, {s.symbol: s for s in sigs})
