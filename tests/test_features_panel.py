"""build_panel: contract columns, the no-look-ahead truncation test, symbol isolation, determinism."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import FEATURE_COLUMNS, build_panel
from tests.features_gbm import gbm_bars

# Hard-coded from docs/feature-contract.md on purpose: independent of the module's own column list.
CONTRACT_COLUMNS = (
    "sma_10 sma_20 sma_50 sma_200 ema_9 ema_21 rsi_2 rsi_14 macd macd_signal macd_hist "
    "bb_upper_20 bb_lower_20 bb_width_20 atr_14 atr_pct_14 "
    "ret_1d ret_5d ret_21d ret_63d ret_126d ret_252d mom_12_1 rev_5d rev_21d vol_21d vol_63d dollar_vol_20d "
    "avg_vol_20d avg_vol_50d amihud_21d high_52w low_52w dist_52w_high rvol_day gap_pct range_pct close_pos "
    "up_days_3 prev_close "
    "support_1 resistance_1 range_width level_touch_pct level_break "
    "vcp_contraction base_len burst_4pct breakout_52w inside_day key_reversal "
    "trend_state vol_regime market_trend_state market_vol_regime"
).split()
BAR_COLUMNS = ["symbol", "ts", "open", "high", "low", "close", "volume", "vwap", "adj_close"]
SYMBOLS = ["AAA", "BBB", "CCC", "DDD"]
N = 420
FLAGS = ["burst_4pct", "breakout_52w", "inside_day", "key_reversal", "level_break"]


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    return gbm_bars(SYMBOLS, n_bars=N, seed=7)


@pytest.fixture(scope="module")
def market() -> pd.DataFrame:
    return gbm_bars(["SPY"], n_bars=N, seed=11)


@pytest.fixture(scope="module")
def panel(bars: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    return build_panel(bars, market)


def _sessions(df: pd.DataFrame) -> list[pd.Timestamp]:
    return sorted(pd.Series(df.ts.unique()).tolist())


def test_contract_columns_present_and_exported(panel: pd.DataFrame) -> None:
    assert [c for c in CONTRACT_COLUMNS if c not in panel.columns] == []
    assert set(FEATURE_COLUMNS) == set(CONTRACT_COLUMNS) and len(FEATURE_COLUMNS) == len(CONTRACT_COLUMNS)
    assert list(panel.columns[: len(BAR_COLUMNS)]) == BAR_COLUMNS
    assert len(panel) == len(SYMBOLS) * N


def test_no_look_ahead_random_symbol_random_dates(
    bars: pd.DataFrame, market: pd.DataFrame, panel: pd.DataFrame
) -> None:
    rng = np.random.default_rng(2026)
    sym = str(rng.choice(SYMBOLS))
    sessions = _sessions(bars)
    for i in rng.choice(np.arange(300, len(sessions)), size=3, replace=False):
        t_cut = sessions[int(i)]
        truncated = build_panel(bars[bars.ts <= t_cut], market[market.ts <= t_cut])
        full_part = panel[(panel.symbol == sym) & (panel.ts <= t_cut)].reset_index(drop=True)
        trunc_part = truncated[truncated.symbol == sym].reset_index(drop=True)
        assert len(full_part) == len(trunc_part) == int(i) + 1
        pd.testing.assert_frame_equal(
            full_part[CONTRACT_COLUMNS], trunc_part[CONTRACT_COLUMNS], rtol=1e-9, atol=1e-12
        )


def test_no_look_ahead_every_symbol(bars: pd.DataFrame, market: pd.DataFrame, panel: pd.DataFrame) -> None:
    t_cut = _sessions(bars)[350]
    truncated = build_panel(bars[bars.ts <= t_cut], market[market.ts <= t_cut])
    full_part = panel[panel.ts <= t_cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(full_part, truncated, rtol=1e-9, atol=1e-12)


def test_symbols_do_not_leak_into_each_other(bars: pd.DataFrame) -> None:
    together = build_panel(bars)
    for sym in SYMBOLS:
        alone = build_panel(bars[bars.symbol == sym])
        part = together[together.symbol == sym].reset_index(drop=True)
        pd.testing.assert_frame_equal(part, alone)


def test_deterministic(bars: pd.DataFrame, market: pd.DataFrame, panel: pd.DataFrame) -> None:
    pd.testing.assert_frame_equal(panel, build_panel(bars, market))


def test_sorts_and_dedupes_input(bars: pd.DataFrame, panel: pd.DataFrame, market: pd.DataFrame) -> None:
    shuffled = bars.sample(frac=1.0, random_state=1)
    with_dup = pd.concat([shuffled, shuffled.iloc[[0]]], ignore_index=True)
    out = build_panel(with_dup, market)
    pd.testing.assert_frame_equal(out, panel)
    assert out.groupby("symbol").ts.is_monotonic_increasing.all()


def test_optional_columns_added_and_missing_required_raise(bars: pd.DataFrame) -> None:
    out = build_panel(bars.drop(columns=["vwap", "adj_close"]))
    assert out.vwap.isna().all() and out.adj_close.isna().all()
    with pytest.raises(ValueError, match="missing columns"):
        build_panel(bars.drop(columns=["volume"]))


def test_flag_dtypes_and_state_ranges(panel: pd.DataFrame) -> None:
    for c in FLAGS:
        assert panel[c].dtype == np.int64 and set(panel[c].unique()) <= {0, 1}
    assert set(panel.trend_state.dropna().unique()) <= {-1.0, 0.0, 1.0}
    assert set(panel.vol_regime.dropna().unique()) <= {0.0, 1.0, 2.0}
    assert set(panel.market_vol_regime.dropna().unique()) <= {0.0, 1.0, 2.0}
    assert panel.close_pos.between(0, 1).all()
    assert set(panel.up_days_3.dropna().unique()) <= {0.0, 1.0, 2.0, 3.0}
    assert (panel.rsi_14.dropna().between(0, 100)).all()
    assert (panel.dist_52w_high.dropna() <= 0).all()


def test_warmup_is_nan_then_filled(panel: pd.DataFrame) -> None:
    for _, grp in panel.groupby("symbol"):
        assert grp.sma_200.iloc[:199].isna().all() and grp.sma_200.iloc[199:].notna().all()
        assert grp.ret_252d.iloc[:252].isna().all() and grp.ret_252d.iloc[252:].notna().all()
        assert grp.vol_regime.iloc[:272].isna().all() and grp.vol_regime.iloc[272:].notna().all()
        assert grp.vcp_contraction.iloc[:59].isna().all() and grp.vcp_contraction.iloc[59:].notna().all()
