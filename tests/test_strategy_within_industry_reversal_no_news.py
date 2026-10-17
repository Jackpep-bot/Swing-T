"""within_industry_reversal_no_news (docs/proposals/swing-methods-2026-10/batch6/within_industry_reversal_no_news.md)
on a hand-built month end: two industries that count, one too small, and the names the card drops."""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import within_industry_reversal_no_news as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2024-09-03", "2025-11-04")  # month end 2025-10-31, then two sessions of November
MONTH_END, BEFORE = date(2025, 10, 31), date(2025, 10, 30)
K, END = len(DAYS), trading_days("2024-09-03", "2025-11-04").index(date(2025, 10, 31))
# symbol -> (sic2, drift per session over the last 21 sessions)
NAMES = {**{f"A{i}": (36.0, 0.002 * (i - 3)) for i in range(6)},  # A0 lags most ... A5 leads
         **{f"B{i}": (60.0, 0.001 * (i - 2)) for i in range(5)},
         **{f"C{i}": (73.0, -0.004) for i in range(4)},  # four members: the industry is skipped
         "NOSIC": (np.nan, -0.004)}


def make_panel(**cols) -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = []
    for j, (sym, (sic, drift)) in enumerate(NAMES.items()):
        r = np.where(np.arange(K) % 2 == 0, 0.005, -0.005)
        r[END - 20:END + 1] += drift
        close = 30.0 * np.cumprod(1.0 + r)
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "open": close, "high": close * 1.01, "low": close * 0.99,
                                    "close": close, "volume": 1e6, "mcap_pit": 1e10 - j, "sic2": sic,
                                    "days_since_earnings": 40.0, "news_flag_1d": 0.0, "news_8k_flag_1d": 0.0}))
    p = pd.concat(frames, ignore_index=True)
    for col, (sym, day, value) in cols.items():
        p.loc[(p["symbol"] == sym) & (p["ts"].dt.date == day), col] = value
    return p


def strat(**over):
    return mod.WithinIndustryReversalNoNews({"buy_count": 2, "hold_count": 4, **over})


def by_hand(panel: pd.DataFrame, sym: str, peers: list[str]) -> float:
    c = panel.loc[panel["ts"].dt.date <= MONTH_END].pivot(index="ts", columns="symbol", values="close")
    ret = c.iloc[-1] / c.iloc[-22] - 1.0
    vol = c[sym].pct_change().iloc[-252:].std(ddof=1)
    return float((ret[sym] - ret[peers].mean()) / (vol * math.sqrt(21)))


def test_ranks_against_the_other_members_of_the_industry():
    panel, s = make_panel(), strat()
    sigs = sorted(s.signals(panel, MONTH_END), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == ["A0", "A1"]  # the worst laggards of industry 36; C* and NOSIC have no score
    assert sigs[0].features["score"] == pytest.approx(by_hand(panel, "A0", ["A1", "A2", "A3", "A4", "A5"]))
    assert sigs[0].stop == pytest.approx(sigs[0].entry * 0.80) and sigs[0].target is None
    assert s.signals(panel, BEFORE) == [] and s.signals(panel, DAYS[END + 1]) == []


def test_news_and_earnings_drop_a_name_but_keep_it_in_its_industry_mean():
    s = strat()
    news = make_panel(news_flag_1d=("A0", DAYS[END - 5], 1.0))
    sigs = sorted(s.signals(news, MONTH_END), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == ["A1", "B0"]
    assert sigs[0].features["score"] == pytest.approx(by_hand(news, "A1", ["A0", "A2", "A3", "A4", "A5"]))  # A0 still a peer
    old = make_panel(news_flag_1d=("A0", DAYS[END - 21], 1.0))  # 22 sessions back: outside the window
    assert [x.symbol for x in sorted(s.signals(old, MONTH_END), key=lambda x: -x.score)] == ["A0", "A1"]
    uncovered = make_panel(news_flag_1d=("A0", DAYS[END - 5], np.nan), news_8k_flag_1d=("A0", DAYS[END - 5], 1.0))
    assert "A0" not in [x.symbol for x in s.signals(uncovered, MONTH_END)]  # an 8-K stands in where news is unknown
    unknown = make_panel(news_flag_1d=("A0", DAYS[END - 5], np.nan))
    assert "A0" in [x.symbol for x in s.signals(unknown, MONTH_END)]
    earn = make_panel().assign(days_since_earnings=lambda p: p["days_since_earnings"].where(p["symbol"] != "A0", 20.0))
    assert "A0" not in [x.symbol for x in s.signals(earn, MONTH_END)]


def test_universe_cut_point_in_time_and_silence_without_the_joins():
    panel, s = make_panel(), strat()
    small = strat(universe_top=5).signals(panel, MONTH_END)  # A0..A4 only: still five members
    assert [x.symbol for x in sorted(small, key=lambda x: -x.score)] == ["A0", "A1"]
    assert strat(universe_top=4).signals(panel, MONTH_END) == []  # four members: skipped
    later = panel["ts"].dt.date > MONTH_END
    shocked = panel.assign(close=panel["close"].where(~later, 1.0), news_flag_1d=panel["news_flag_1d"].where(~later, 1.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, MONTH_END)]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    assert s.signals(panel.loc[panel["ts"].dt.date >= DAYS[END - 251]], MONTH_END) == []  # 252 closes: one return short
    for col in ("mcap_pit", "sic2", "days_since_earnings", "news_flag_1d", "news_8k_flag_1d"):
        assert s.signals(panel.drop(columns=col), MONTH_END) == []
