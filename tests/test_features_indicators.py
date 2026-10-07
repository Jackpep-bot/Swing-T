"""Indicators: explicit loop references vs the vectorized pure functions, plus the per-symbol panel path."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import indicators as ind
from tests.features_gbm import gbm_bars

N = 300


@pytest.fixture(scope="module")
def one() -> pd.DataFrame:
    return gbm_bars(["AAA"], n_bars=N, seed=1)


def _ref_sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        out[i] = x[i - n + 1 : i + 1].mean()
    return out


def _ref_ewm(x: np.ndarray, alpha: float, min_periods: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    prev = None
    seen = 0
    for i, v in enumerate(x):
        if np.isnan(v):
            continue
        seen += 1
        prev = v if prev is None else alpha * v + (1 - alpha) * prev
        if seen >= min_periods:
            out[i] = prev
    return out


def _ref_rsi(close: np.ndarray, n: int) -> np.ndarray:
    d = np.diff(close, prepend=np.nan)
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    gain[0] = loss[0] = np.nan
    ag, al = _ref_ewm(gain, 1 / n, n), _ref_ewm(loss, 1 / n, n)
    out = np.full(len(close), np.nan)
    for i in range(len(close)):
        if np.isnan(ag[i]) or np.isnan(al[i]):
            continue
        if al[i] == 0:
            out[i] = 50.0 if ag[i] == 0 else 100.0
        else:
            out[i] = 100 - 100 / (1 + ag[i] / al[i])
    return out


def _ref_atr(h: np.ndarray, lo: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    tr = np.empty(len(h))
    tr[0] = h[0] - lo[0]
    for i in range(1, len(h)):
        tr[i] = max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1]))
    return _ref_ewm(tr, 1 / n, n)


def test_sma_matches_loop(one: pd.DataFrame) -> None:
    c = one.close.to_numpy()
    for w in ind.SMA_WINDOWS:
        np.testing.assert_allclose(ind.sma(one.close, w).to_numpy(), _ref_sma(c, w), rtol=1e-12)


def test_ema_matches_loop(one: pd.DataFrame) -> None:
    c = one.close.to_numpy()
    for s in ind.EMA_SPANS:
        np.testing.assert_allclose(ind.ema(one.close, s).to_numpy(), _ref_ewm(c, 2 / (s + 1), s), rtol=1e-12)


def test_rsi_matches_loop_and_bounds(one: pd.DataFrame) -> None:
    c = one.close.to_numpy()
    for p in ind.RSI_PERIODS:
        got = ind.rsi(one.close, p)
        np.testing.assert_allclose(got.to_numpy(), _ref_rsi(c, p), rtol=1e-10)
        assert got.iloc[:p].isna().all() and got.iloc[p:].notna().all()
        assert got.dropna().between(0, 100).all()


def test_rsi_edge_cases() -> None:
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert (ind.rsi(up, 14).dropna() == 100).all()
    down = pd.Series(np.arange(40, 1, -1, dtype=float))
    assert (ind.rsi(down, 14).dropna() == 0).all()
    flat = pd.Series(np.full(40, 10.0))
    assert (ind.rsi(flat, 14).dropna() == 50).all()


def test_atr_matches_loop(one: pd.DataFrame) -> None:
    got = ind.atr(one.high, one.low, one.close, ind.ATR_PERIOD).to_numpy()
    exp = _ref_atr(one.high.to_numpy(), one.low.to_numpy(), one.close.to_numpy(), ind.ATR_PERIOD)
    np.testing.assert_allclose(got, exp, rtol=1e-10)


def test_macd_and_bollinger_relations(one: pd.DataFrame) -> None:
    m = ind.macd(one.close)
    np.testing.assert_allclose(m.macd_hist.to_numpy(), (m.macd - m.macd_signal).to_numpy())
    fast, slow = ind.ema(one.close, 12), ind.ema(one.close, 26)
    np.testing.assert_allclose(m.macd.to_numpy(), (fast - slow).to_numpy())
    bb = ind.bollinger(one.close)
    mid = one.close.rolling(20).mean()
    sd = one.close.rolling(20).std(ddof=0)
    np.testing.assert_allclose(bb.bb_upper_20.to_numpy(), (mid + 2 * sd).to_numpy())
    np.testing.assert_allclose(bb.bb_lower_20.to_numpy(), (mid - 2 * sd).to_numpy())
    np.testing.assert_allclose(
        bb.bb_width_20.to_numpy(), ((bb.bb_upper_20 - bb.bb_lower_20) / mid).to_numpy()
    )
    assert (bb.bb_upper_20 >= bb.bb_lower_20).loc[bb.bb_upper_20.notna()].all()


def test_add_indicators_matches_pure_functions_per_symbol() -> None:
    bars = gbm_bars(["AAA", "BBB"], n_bars=N, seed=2)
    out = ind.add_indicators(bars)
    assert all(c in out.columns for c in ind.INDICATOR_COLUMNS)
    for _, grp in out.groupby("symbol"):
        close = grp.close
        np.testing.assert_allclose(grp.sma_50.to_numpy(), ind.sma(close, 50).to_numpy())
        np.testing.assert_allclose(grp.ema_21.to_numpy(), ind.ema(close, 21).to_numpy())
        np.testing.assert_allclose(grp.rsi_14.to_numpy(), ind.rsi(close, 14).to_numpy())
        np.testing.assert_allclose(grp.atr_14.to_numpy(), ind.atr(grp.high, grp.low, close).to_numpy())
        np.testing.assert_allclose(
            grp.atr_pct_14.to_numpy(), (ind.atr(grp.high, grp.low, close) / close).to_numpy()
        )
        m = ind.macd(close)
        np.testing.assert_allclose(grp.macd_signal.to_numpy(), m.macd_signal.to_numpy())
        bb = ind.bollinger(close)
        np.testing.assert_allclose(grp.bb_width_20.to_numpy(), bb.bb_width_20.to_numpy())
