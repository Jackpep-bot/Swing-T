from __future__ import annotations

import numpy as np
import pytest

from swing_engine.strategies.insider_cluster import InsiderCluster
from tests.fixtures.strategies.panel import last_date, make_panel, set_last


@pytest.fixture(scope="module")
def panel():
    return make_panel(("AAA", "BBB"), n_days=320, seed=5)


def test_returns_nothing_without_the_optional_column(panel):
    assert "insider_cluster_score" not in panel.columns
    assert InsiderCluster().signals(panel, last_date(panel)) == []


def test_signal_from_cluster_score(panel):
    scored = panel.assign(insider_cluster_score=np.nan)
    scored = set_last(scored, "AAA", insider_cluster_score=3.0, atr_14=2.0, trend_state=-1.0)
    sigs = InsiderCluster().signals(scored, last_date(scored))
    assert [s.symbol for s in sigs] == ["AAA"]
    s = sigs[0]
    close = float(scored[scored["symbol"] == "AAA"]["close"].iloc[-1])
    assert s.entry == pytest.approx(close)
    assert s.stop == pytest.approx(close - 2.0 * 2.0)
    assert s.target == pytest.approx(close + 2.0 * 4.0)
    assert s.reward_risk == pytest.approx(2.0)
    assert s.score == 3.0 and s.features["insider_cluster_score"] == 3.0


def test_min_score_and_trend_params(panel):
    scored = set_last(panel.assign(insider_cluster_score=0.0), "AAA", insider_cluster_score=3.0, trend_state=-1.0)
    as_of = last_date(scored)
    assert InsiderCluster({"min_score": 4.0}).signals(scored, as_of) == []
    assert InsiderCluster({"min_trend_state": 0}).signals(scored, as_of) == []
    assert len(InsiderCluster({"min_trend_state": -1}).signals(scored, as_of)) == 1


def test_custom_score_column(panel):
    strat = InsiderCluster({"score_column": "form4_cluster"})
    assert strat.signals(panel, last_date(panel)) == []
    scored = set_last(panel.assign(form4_cluster=0.0), "BBB", form4_cluster=2.0)
    assert [s.symbol for s in strat.signals(scored, last_date(scored))] == ["BBB"]
