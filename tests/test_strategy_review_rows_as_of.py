"""Review regressions for strategies/_base.py rows_as_of and _catalog1.rows: an empty as-of slice still carries the
prior_* / rolling / extra columns, so no registered strategy raises on an empty panel or an as_of before its first bar."""
from datetime import date

import pytest

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from swing_engine.features.panel import build_panel
from swing_engine.features.patterns2 import add_patterns2
from swing_engine.strategies._base import PanelStrategy, RollingSpec
from tests.features_gbm import gbm_bars

OPTIONAL = {"days_since_earnings": 5.0, "sue": 1.0, "rev_surprise": 1.0, "opp_buy_value_21d": 5e4, "opp_buy_flag": 1.0,
            "turnover": 0.01}


@pytest.fixture(scope="module")
def panel():
    bars = gbm_bars(["AAA", "BBB", "SPY"], n_bars=120, seed=21)
    p = build_panel(bars, bars[bars["symbol"] == "SPY"]).sort_values(["symbol", "ts"]).reset_index(drop=True)
    return add_patterns2(p).assign(**OPTIONAL)


@pytest.mark.parametrize("name", registry.names("strategy"))
def test_empty_panel_and_as_of_before_first_bar(name, panel):
    s = registry.get("strategy", name)()
    p = ensure_extra(panel, getattr(s, "extra_features", []))
    assert s.signals(p.iloc[0:0], p["ts"].max().date()) == []
    assert s.signals(p, date(2000, 1, 3)) == []


class _Probe(PanelStrategy):
    name = "probe_empty"
    default_params = {"min_reward_risk": 0.0}

    def signals(self, panel, as_of, regime=None):
        return []


def test_rows_as_of_empty_slice_keeps_helper_columns(panel):
    rows = _Probe().rows_as_of(panel, date(2000, 1, 3), rolling=[RollingSpec("high", "max", 5, prior=True)])
    assert rows.empty and {"prior_close", "prior_max_high_5"} <= set(rows.columns)
