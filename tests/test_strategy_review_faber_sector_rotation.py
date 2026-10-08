"""Review fix for faber_sector_rotation: exit on the month-end rebalance close so a still-top-3 sector is re-bought."""
from __future__ import annotations

import pandas as pd

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from swing_engine.research.backtest import run_backtest
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, make_bars, trend_rows


def test_top_sector_held_every_month_including_short_months():
    # XLK ranks first every month and SPY trends up. With the old 21-bar time stop a pick bought in a month of
    # <= 20 sessions (Jan/Feb/Jun 2025) was still held at its month-end, so that day's re-buy was skipped as busy
    # and the position time-stopped a session or two later: the following month went unheld.
    s = registry.get("strategy", "faber_sector_rotation")()
    n = 480  # 2024-01-02 .. 2025-10
    xlk = bars_from_ohlc("XLK", trend_rows(n, start=100.0, step=0.3))
    spy = bars_from_ohlc("SPY", trend_rows(n, start=300.0, step=0.5))
    others = make_bars(("XLE", "XLF", "XLV"), n_days=n, seed=4)
    p = ensure_extra(add_features(pd.concat([xlk, spy, others], ignore_index=True)), s.extra_features)
    p.loc[p["symbol"] == "XLK", "ret_63d"] = 1.0
    res = run_backtest(s, p, start="2024-12-02", end="2025-10-31")
    assert "symbol_busy" not in res.skip_reasons
    xlk_trades = res.trades.loc[res.trades["symbol"] == "XLK"]
    entry_months = pd.to_datetime(xlk_trades["entry_ts"]).dt.tz_localize(None).dt.to_period("M")
    assert list(entry_months) == list(pd.period_range("2025-01", "2025-10", freq="M"))
    closed = xlk_trades.iloc[:-1]  # the last one is force-closed at the window end
    assert (closed["exit_reason"] == "rule").all()
