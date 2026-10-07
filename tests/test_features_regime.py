"""Trend / volatility regime states and the market broadcast."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import cross_section as cs
from swing_engine.features import regime as rg
from swing_engine.features.panel import build_panel
from tests.features_gbm import gbm_bars


def test_trend_state_on_lines() -> None:
    n = 260
    up = rg.trend_state(pd.Series(100 + np.arange(n, dtype=float)))
    assert up.iloc[:199].isna().all() and (up.iloc[199:] == 1).all()
    down = rg.trend_state(pd.Series(1000 - np.arange(n, dtype=float)))
    assert (down.iloc[199:] == -1).all()
    flat = rg.trend_state(pd.Series(np.full(n, 100.0)))
    assert (flat.iloc[199:] == 0).all()


def test_vol_regime_values_and_extremes() -> None:
    bars = gbm_bars(["AAA"], n_bars=400, seed=8)
    vr = rg.vol_regime(cs.realized_vol(bars.close, 21))
    assert vr.iloc[:272].isna().all() and vr.iloc[272:].notna().all()
    assert set(vr.dropna().unique()) <= {0.0, 1.0, 2.0}
    rising = rg.vol_regime(pd.Series(np.arange(300, dtype=float)))
    assert (rising.dropna() == 2).all()
    falling = rg.vol_regime(pd.Series(np.arange(300, 0, -1, dtype=float)))
    assert (falling.dropna() == 0).all()


def test_add_regime_uses_panel_columns_or_computes_them() -> None:
    bars = gbm_bars(["AAA", "BBB"], n_bars=400, seed=9)
    bare = rg.add_regime(bars)
    for _, grp in bare.groupby("symbol"):
        np.testing.assert_allclose(grp.trend_state.to_numpy(), rg.trend_state(grp.close).to_numpy())
        np.testing.assert_allclose(
            grp.vol_regime.to_numpy(), rg.vol_regime(cs.realized_vol(grp.close, 21)).to_numpy()
        )
    panel = build_panel(bars)
    np.testing.assert_allclose(panel.trend_state.to_numpy(), bare.trend_state.to_numpy())
    np.testing.assert_allclose(panel.vol_regime.to_numpy(), bare.vol_regime.to_numpy())


def test_market_regime_broadcast_and_absence() -> None:
    bars = gbm_bars(["AAA", "BBB"], n_bars=400, seed=10)
    market = gbm_bars(["SPY"], n_bars=400, seed=11)
    panel = build_panel(bars, market)
    mk = rg.market_regime(market).set_index("_session")
    sessions = panel.ts.dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
    np.testing.assert_allclose(
        panel.market_trend_state.to_numpy(), mk.market_trend_state.loc[sessions].to_numpy()
    )
    np.testing.assert_allclose(
        panel.market_vol_regime.to_numpy(), mk.market_vol_regime.loc[sessions].to_numpy()
    )
    for _, grp in panel.groupby("symbol"):
        assert (
            grp.market_trend_state.iloc[199:].notna().all() and grp.market_vol_regime.iloc[272:].notna().all()
        )
    spy_only = build_panel(market)
    np.testing.assert_allclose(spy_only.trend_state.to_numpy(), mk.market_trend_state.to_numpy())
    none = build_panel(bars)
    assert none.market_trend_state.isna().all() and none.market_vol_regime.isna().all()


def test_market_regime_rejects_multi_symbol() -> None:
    with pytest.raises(ValueError):
        rg.market_regime(gbm_bars(["SPY", "QQQ"], n_bars=50, seed=1))
