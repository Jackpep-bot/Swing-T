"""The pre-registered group of three (docs/preregistration/2026-10-09-three-picks.md): ath_trend_following_wide_stop,
composite_cost_aware_rank, earnings_seasonality, plus the data/feature pieces they read (pre-panel high join,
ath_close / hist_bars, EarnRank, expected-announcement clock). Point-in-time is also covered by
tests/test_strategies_all.py and tests/test_features_extra.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.data import fundamentals as F
from swing_engine.data.market_series import join_market_series, join_pre_panel_high
from swing_engine.data.store import Store
from swing_engine.execution.position_manager import _hold_limit
from swing_engine.features.extra import ensure_extra
from swing_engine.research.backtest import (
    DEFAULT_MAX_HOLD_BARS,
    CostModel,
    ExitReason,
    _max_hold_for,
    run_backtest,
)
from swing_engine.risk.selection import rank_hysteresis

TZ = "America/New_York"
FREE = CostModel(slippage_bps=0.0, sec_fee_per_million_sold=0.0, finra_taf_per_share=0.0)


def with_(row: pd.Series, **kw) -> pd.Series:
    return pd.Series({**row.to_dict(), **kw})


def strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


def trend_bars(symbol: str, closes: np.ndarray, start: str = "2022-01-03") -> pd.DataFrame:
    ts = pd.bdate_range(start, periods=len(closes), tz=TZ)
    prev = np.r_[closes[0], closes[:-1]]
    return pd.DataFrame({"symbol": symbol, "ts": ts, "open": prev, "high": np.maximum(prev, closes) * 1.005,
                         "low": np.minimum(prev, closes) * 0.995, "close": closes, "volume": 1e6})


# ----------------------------------------------------------------------------------------------- ATH
def ath_panel(closes: np.ndarray, **cols) -> pd.DataFrame:
    return ensure_extra(trend_bars("AAA", closes).assign(**cols), ["ath_close", "hist_bars", "atr_42"])


def test_ath_fires_on_new_all_time_high_only():
    s = strat("ath_trend_following_wide_stop")
    up = 20.0 * np.exp(0.002 * np.arange(300))
    p = ath_panel(up)
    last = p["ts"].iloc[-1].date()
    (sig,) = s.signals(p, last)
    row = p.iloc[-1]
    assert sig.entry == pytest.approx(row["close"]) and sig.target is None
    assert sig.stop == pytest.approx(row["close"] - 10.0 * row["atr_42"])  # ATH = close on the signal day
    dip = np.r_[up[:-1], up[-2] * 0.99]
    assert s.signals(ath_panel(dip), last) == []  # below the high: no signal
    assert s.signals(ath_panel(up, pre_panel_high=up[-1] * 2), last) == []  # an older store high still counts
    young = ath_panel(up[:200])
    assert s.signals(young, young["ts"].iloc[-1].date()) == []  # < 252 bars of history
    old = ath_panel(up[:200], pre_panel_bars=100.0)
    assert len(s.signals(old, old["ts"].iloc[-1].date())) == 1


def test_ath_trail_is_ten_atr_below_the_high():
    s = strat("ath_trend_following_wide_stop")
    row = pd.Series({"ath_close": 100.0, "atr_42": 2.0, "close": 90.0})
    assert s.trail_stop(row) == pytest.approx(100.0 * (1 - 10 * 2.0 / 90.0))
    assert s.trail_stop(with_(row, atr_42=10.0)) is None  # level <= 0
    assert s.trail_stop(row.drop("ath_close")) is None
    assert s.engine_trail is False


def test_long_hold_is_not_truncated():
    """A 400+ session winner runs to the window end: no 20-bar backtest default, no position-manager time stop."""
    s = strat("ath_trend_following_wide_stop")
    panel = ath_panel(20.0 * np.exp(0.001 * np.arange(700)))
    res = run_backtest(s, panel, costs=FREE)
    t = res.trades
    assert len(t) == 1 and t["exit_reason"].iloc[0] == ExitReason.END.value
    assert int(t["bars_held"].iloc[0]) > 305
    for name in ("ath_trend_following_wide_stop", "composite_cost_aware_rank"):
        assert _max_hold_for(strat(name), None) > 305 > DEFAULT_MAX_HOLD_BARS
        assert _hold_limit(strat(name)) > 305


# ----------------------------------------------------------------------------------------------- pre-panel join
def test_pre_panel_high_from_store_bars_before_the_panel():
    store = Store()
    bars = trend_bars("AAA", np.r_[np.arange(1.0, 8.0), [5.0, 6.0, 4.0]])
    store.write_bars(bars)
    panel = bars.iloc[7:].reset_index(drop=True)
    out = join_pre_panel_high(store, panel)
    assert out["pre_panel_high"].tolist() == [7.0] * 3 and out["pre_panel_bars"].tolist() == [7.0] * 3
    assert join_market_series(store, panel)["pre_panel_high"].tolist() == [7.0] * 3
    other = join_pre_panel_high(store, panel.assign(symbol="ZZZ"))
    assert other["pre_panel_high"].isna().all() and (other["pre_panel_bars"] == 0).all()
    ath = ensure_extra(out, ["ath_close", "hist_bars"])
    assert ath["ath_close"].tolist() == [7.0] * 3 and ath["hist_bars"].tolist() == [8.0, 9.0, 10.0]


# ----------------------------------------------------------------------------------------------- composite
def ccr_panel(scores: dict[date, dict[str, float]]) -> pd.DataFrame:
    rows = []
    for d, by_sym in scores.items():
        rank = pd.Series(by_sym).rank(pct=True)
        for sym, sc in by_sym.items():
            rows.append({"symbol": sym, "ts": pd.Timestamp(d, tz=TZ), "open": 10.0, "high": 10.0, "low": 10.0,
                         "close": 10.0, "volume": 1e6, "atr_63": 0.2, "month_end": 1.0, "ccr_score": sc,
                         "ccr_score_rank": rank[sym]})
    return pd.DataFrame(rows)


def test_composite_band_equals_rank_hysteresis():
    s = strat("composite_cost_aware_rank")
    rng = np.random.default_rng(3)
    syms = [f"S{i:02d}" for i in range(30)]
    months = [d.date() for d in pd.bdate_range("2025-01-31", periods=12, freq="BME")]
    walk = rng.normal(size=30)
    scores = {}
    for d in months:
        walk = 0.7 * walk + rng.normal(size=30)
        scores[d] = dict(zip(syms, walk, strict=True))
    panel = ccr_panel(scores)
    held: list[str] = []
    for d in months:
        rows = panel[panel["ts"].dt.date == d].set_index("symbol")
        exits = {sym for sym in held if s.should_exit(rows.loc[sym], 21)}
        buys = {sig.symbol for sig in s.signals(panel, d)}
        new = (set(held) - exits) | buys
        ranked = sorted(syms, key=lambda x: -scores[d][x])
        assert new == set(rank_hysteresis(ranked, held, 0.10, 0.20)), d
        held = sorted(new)


def test_composite_only_on_month_end_and_exit_on_missing_rank():
    s = strat("composite_cost_aware_rank")
    d = date(2025, 1, 30)
    panel = ccr_panel({d: {f"S{i}": float(i) for i in range(20)}}).assign(month_end=0.0)
    assert s.signals(panel, d) == []
    row = pd.Series({"month_end": 1.0, "ccr_score_rank": np.nan})
    assert s.should_exit(row, 5) and not s.should_exit(with_(row, month_end=0.0), 5)
    assert not s.should_exit(with_(row, ccr_score_rank=0.85), 5) and s.should_exit(with_(row, ccr_score_rank=0.8), 5)


def test_ccr_score_excludes_illiquid_and_small_names():
    days = pd.bdate_range("2023-01-02", periods=300, tz=TZ)
    rng = np.random.default_rng(0)
    frames = []
    for i in range(10):
        close = 50 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
        vol = 1e3 if i == 0 else 1e6  # S0: $50k a day
        frames.append(pd.DataFrame({"symbol": f"S{i}", "ts": days, "open": close, "high": close * 1.01,
                                    "low": close * 0.99, "close": close, "volume": vol,
                                    "gross_prof": 0.1 * i, "shares_outstanding": 1e6 * (1 + i)}))
    from swing_engine.features.panel import build_panel

    p = ensure_extra(build_panel(pd.concat(frames, ignore_index=True)), ["ccr_score", "ccr_score_rank"])
    last = p[p["ts"] == days[-1]].set_index("symbol")
    assert np.isnan(last.loc["S0", "ccr_score"])  # median dollar volume < $20M
    assert np.isnan(last.loc["S1", "ccr_score"])  # smallest market cap (bottom 20%)
    assert last["ccr_score"].notna().sum() == 8 and last["ccr_score_rank"].notna().sum() == 8


# ----------------------------------------------------------------------------------------------- seasonality
def quarters(values: list[float], start: str = "2020-03-31", gap: int = 91) -> pd.Series:
    idx = [(pd.Timestamp(start) + pd.Timedelta(days=gap * i)).date() for i in range(len(values))]
    return pd.Series(values, index=idx, dtype=float)


def test_earnings_seasonality_rank():
    vals = [1.0] * 23
    for k, i in enumerate((3, 7, 11, 15, 19)):  # t-20 .. t-4 within the 20-quarter window
        vals[i] = 10.0 + k
    assert F.earnings_seasonality(quarters(vals)) == pytest.approx(3.0)  # the five largest: ranks 1..5
    flat = F.earnings_seasonality(quarters([1.0] * 23))
    assert flat == pytest.approx(10.5)  # all tied
    assert np.isnan(F.earnings_seasonality(quarters(vals[:22])))
    assert np.isnan(F.earnings_seasonality(quarters(vals, gap=200)))
    # the three newest quarters (t-3 .. t-1) are outside the ranked window
    assert F.earnings_seasonality(quarters([*vals[:20], 99.0, 99.0, 99.0])) == pytest.approx(3.0)


def test_expected_earnings_is_last_years_date_in_sessions():
    ann = [date(2025, 1, 28), date(2025, 4, 29), date(2025, 7, 29), date(2025, 10, 28)]
    earnings = pd.DataFrame({"symbol": "AAA", "session": ann})
    index = pd.DataFrame({"symbol": "AAA", "ts": [pd.Timestamp(date(2026, 1, 16), tz=TZ),
                                                  pd.Timestamp(date(2025, 1, 10), tz=TZ)]})
    cal = F.earnings_calendar_features(earnings, index)
    assert cal["expected_earnings"].iloc[0] == pd.Timestamp("2026-01-27")  # 2025-01-28 + 364 days (Tuesday)
    assert cal["sessions_to_expected_earnings"].iloc[0] == 6.0  # 01-20 (01-19 holiday), 21, 22, 23, 26, 27
    assert np.isnan(cal["sessions_to_expected_earnings"].iloc[1])  # no announcement known yet


def season_panel(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    d = pd.Timestamp(date(2026, 1, 16), tz=TZ)
    return pd.DataFrame([{"symbol": sym, "ts": d, "open": 20.0, "high": 20.0, "low": 20.0, "close": 20.0,
                          "volume": 2e6, "atr_14": 0.5, "med_dv_63": 4e7, "earn_season": season,
                          "sessions_to_expected_earnings": to, "days_since_earnings": since}
                         for sym, season, to, since in rows])


def test_earnings_seasonality_fires_top_quintile_six_sessions_out():
    s = strat("earnings_seasonality")
    filler = [(f"F{i}", 10.0 + i * 0.1, 10.0, 40.0) for i in range(10)]
    panel = season_panel([("A", 3.0, 6.0, 40.0), ("B", 18.0, 6.0, 40.0), ("C", 3.5, 6.0, 10.0),
                          ("D", 3.2, 7.0, 40.0), *filler])
    (sig,) = s.signals(panel, date(2026, 1, 16))
    assert sig.symbol == "A" and sig.stop == pytest.approx(20.0 - 1.5) and sig.target is None
    assert s.signals(panel.drop(columns=["earn_season"]), date(2026, 1, 16)) == []
    assert s.signals(panel.assign(med_dv_63=1e6), date(2026, 1, 16)) == []  # illiquid


def test_earnings_seasonality_exit_after_the_announcement():
    s = strat("earnings_seasonality")
    row = pd.Series({"days_since_earnings": 2.0})
    assert s.should_exit(row, 5)  # announced on the 3rd held session, now 2 sessions later
    assert not s.should_exit(with_(row, days_since_earnings=1.0), 5)
    assert not s.should_exit(with_(row, days_since_earnings=30.0), 5)  # last quarter's report, before entry
    assert not s.should_exit(pd.Series({"days_since_earnings": np.nan}), 5)
    assert s.params["max_hold_days"] == 25


@pytest.mark.parametrize(("last_q_end", "kept"), [("2025-09-30", True), ("2025-06-30", False)])
def test_earn_season_only_for_the_quarter_the_expected_report_covers(last_q_end, kept):
    ann = [date(2025, 1, 28), date(2025, 4, 29), date(2025, 7, 29), date(2025, 10, 28)]
    earnings = pd.DataFrame({"symbol": "AAA", "session": ann})
    events = pd.DataFrame({"symbol": ["AAA"], "filed": [date(2025, 11, 7)],
                           "avail_ts": [pd.Timestamp(date(2025, 11, 10), tz=TZ)], "sue": [0.0],
                           "rev_surprise": [0.0], "gross_prof": [0.1], "shares_outstanding": [1e6],
                           "earn_season": [3.0], "eps_last_q_end": [pd.Timestamp(last_q_end)]})
    index = pd.DataFrame({"symbol": "AAA", "ts": [pd.Timestamp(date(2026, 1, 16), tz=TZ)]})
    feats = F.fundamental_features(None, earnings, index, events=events)
    assert feats["sessions_to_expected_earnings"].iloc[0] == 6.0
    assert (feats["earn_season"].iloc[0] == 3.0) if kept else np.isnan(feats["earn_season"].iloc[0])
    stale = F.fundamental_features(None, earnings, index, events=events.drop(columns=["earn_season", "eps_last_q_end"]))
    assert np.isnan(stale["earn_season"].iloc[0])  # a cache built before the column existed: NaN, not an error
