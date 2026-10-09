"""connors_cvr3_vix (docs/strategies/connors_cvr3_vix.md): fires on SPY only, needs all three VIX conditions, exits on
the prior day's VIX SMA(10) or the time stop, and returns [] without the joined VIX columns."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from tests.fixtures.strategies.panel import last_date, make_panel

NAME = "connors_cvr3_vix"
N_DAYS = 60
CALM = 15.0


def _strat(params: dict | None = None):
    return registry.get("strategy", NAME)(params)


def _panel(last_bar: tuple[float, float, float, float]) -> pd.DataFrame:
    """SPY + AAA with a flat VIX at 15, then (open, high, low, close) on the last session for every symbol."""
    p = make_panel(("SPY", "AAA"), n_days=N_DAYS)
    vix = np.tile(np.r_[np.full(N_DAYS - 1, CALM), np.nan], 2)
    p = p.assign(vix_open=vix, vix_high=vix, vix_low=vix, vix_close=vix)
    last = p.groupby("symbol").tail(1).index
    p.loc[last, ["vix_open", "vix_high", "vix_low", "vix_close"]] = last_bar
    return ensure_extra(p, _strat().extra_features)


def test_fires_on_spy_when_all_three_hold():
    # SMA10 = (9 x 15 + 18) / 10 = 15.3; low 17 > 15.3, close 18 >= 1.10 x 15.3 = 16.83, close 18 < open 19
    p = _panel((19.0, 20.0, 17.0, 18.0))
    sigs = _strat().signals(p, last_date(p))
    assert [s.symbol for s in sigs] == ["SPY"]
    s = sigs[0]
    assert s.target is None and s.stop < s.entry
    assert s.entry - s.stop == pytest.approx(3.0 * p.loc[p["symbol"] == "SPY", "atr_14"].iloc[-1])
    assert s.score == pytest.approx(18.0 / 15.3 - 1.0)


@pytest.mark.parametrize("bar", [
    (17.0, 20.0, 17.0, 18.0),  # close above open (fear still rising)
    (19.0, 20.0, 15.0, 18.0),  # low below the SMA
    (17.0, 17.5, 16.5, 16.6),  # close < 1.10 x SMA (16.6 / 15.16 < 1.10) -- and close < open
])
def test_any_condition_missing_blocks(bar):
    p = _panel(bar)
    assert _strat().signals(p, last_date(p)) == []


def test_three_day_window_variant():
    p = _panel((19.0, 20.0, 17.0, 18.0))
    spy_last = p.index[p["symbol"] == "SPY"][-1]
    p.loc[spy_last, "vix_open"] = 17.5  # today closes above its open: no black candle today
    assert _strat().signals(p, last_date(p)) == []
    prior = p.index[p["symbol"] == "SPY"][-2]
    p.loc[prior, ["vix_open", "vix_close"]] = [CALM + 0.5, CALM]  # yesterday: black candle within 3 bars
    assert [s.symbol for s in _strat({"window": 3}).signals(p, last_date(p))] == ["SPY"]


def test_without_vix_columns_returns_nothing():
    p = make_panel(("SPY",), n_days=N_DAYS)
    assert _strat().signals(ensure_extra(p, _strat().extra_features), last_date(p)) == []


def test_exits_on_prior_sma_or_time():
    s = _strat()
    row = pd.Series({"vix_close": 15.0, "prev_vix_sma_10": 16.0})
    assert s.should_exit(row, 1)
    assert not s.should_exit(pd.Series({"vix_close": 17.0, "prev_vix_sma_10": 16.0}), 1)
    assert s.should_exit(pd.Series({"vix_close": 17.0, "prev_vix_sma_10": 16.0}), 4)
    assert not s.should_exit(pd.Series({"vix_close": np.nan, "prev_vix_sma_10": 16.0}), 1)
    assert s.engine_trail is False


def test_disabled_in_settings():
    from swing_engine.core.config import load_settings

    assert load_settings().strategies[NAME]["enabled"] is False
