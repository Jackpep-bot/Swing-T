from __future__ import annotations

import time
from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core.registry import get
from swing_engine.data._common import BAR_COLUMNS, SYMBOL_COLUMNS, TZ
from swing_engine.data.sample import DELISTINGS, LATE_IPOS, MARKET_SYMBOL, SPLITS, SampleProvider


def test_registered_and_deterministic() -> None:
    assert get("bar_provider", "sample") is SampleProvider
    a = SampleProvider(seed=1).all_bars()
    b = SampleProvider(seed=1).all_bars()
    pd.testing.assert_frame_equal(a, b)
    c = SampleProvider(seed=2).all_bars()
    assert not np.allclose(a["close"].to_numpy()[:500], c["close"].to_numpy()[:500])


def test_shape_and_schema() -> None:
    t0 = time.perf_counter()
    p = SampleProvider()
    bars = p.all_bars()
    assert time.perf_counter() - t0 < 5.0
    assert list(bars.columns) == BAR_COLUMNS
    assert str(bars["ts"].dt.tz) == TZ
    syms = p.list_symbols()
    assert list(syms.columns[: len(SYMBOL_COLUMNS)]) == SYMBOL_COLUMNS
    assert 55 <= len(syms) <= 65 and MARKET_SYMBOL in set(syms["symbol"])
    spy = bars[bars["symbol"] == MARKET_SYMBOL]
    years = (spy["ts"].max() - spy["ts"].min()).days / 365.25
    assert 5.8 <= years <= 6.1
    assert (bars["high"] >= bars[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (bars["low"] <= bars[["open", "close"]].min(axis=1) + 1e-9).all()
    assert (bars["low"] > 0).all() and (bars["volume"] > 0).all()
    assert ((bars["vwap"] >= bars["low"] - 1e-9) & (bars["vwap"] <= bars["high"] + 1e-9)).all()
    assert not bars.duplicated(subset=["symbol", "ts"]).any()


def test_delistings_ipos_and_split_adjustment() -> None:
    p = SampleProvider()
    bars = p.all_bars()
    syms = p.list_symbols().set_index("symbol")
    for sym, (reason, last_day) in DELISTINGS.items():
        s = bars[bars["symbol"] == sym]
        assert s["ts"].max().date() <= last_day
        assert syms.loc[sym, "active"] is np.False_ or not syms.loc[sym, "active"]
        assert syms.loc[sym, "delisted_at"] == s["ts"].max().date()
        if reason == "bankruptcy":
            assert s["close"].iloc[-1] < s["close"].iloc[0] * 0.2
    for sym, ipo in LATE_IPOS.items():
        s = bars[bars["symbol"] == sym]
        assert s["ts"].min().date() >= ipo
    assert set(p.list_symbols(include_delisted=False)["symbol"]).isdisjoint(DELISTINGS)
    assert len(p.delistings()) == len(DELISTINGS)
    for sym, events in SPLITS.items():
        ex_date, ratio = events[0]
        adj = p.daily_bars([sym], date(2020, 1, 1), date(2030, 1, 1))
        raw = p.daily_bars([sym], date(2020, 1, 1), date(2030, 1, 1), adjusted=False)
        before = adj["ts"] < pd.Timestamp(ex_date, tz=TZ)
        assert np.allclose(raw.loc[before, "close"], adj.loc[before, "close"] * ratio)
        assert np.allclose(raw.loc[~before, "close"], adj.loc[~before, "close"])
        assert np.allclose(raw.loc[before, "volume"], np.floor(adj.loc[before, "volume"] / ratio))
    assert set(p.splits()["symbol"]) == set(SPLITS)


def test_daily_bars_filters_and_regimes_exist() -> None:
    p = SampleProvider()
    out = p.daily_bars(["spy", "ACME", "NOPE"], date(2024, 1, 1), date(2024, 1, 31))
    assert set(out["symbol"]) == {"SPY", "ACME"}
    assert out["ts"].min().date() >= date(2024, 1, 2) and out["ts"].max().date() <= date(2024, 1, 31)
    assert p.daily_bars(["NOPE"], date(2024, 1, 1), date(2024, 1, 31)).empty
    # regimes: 63-day returns across the universe should include clear up, down and flat stretches
    spy = p.daily_bars(["SPY"], date(2020, 1, 1), date(2030, 1, 1)).set_index("ts")["close"]
    r63 = spy.pct_change(63).dropna()
    assert r63.max() > 0.10 and r63.min() < -0.10 and (r63.abs() < 0.03).any()
