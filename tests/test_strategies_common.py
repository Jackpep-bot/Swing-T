"""Cross-strategy contract tests: registry, params, feature columns, signal geometry, point-in-time."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import Side, Signal
from swing_engine.features.extra import ensure_extra, is_extra
from swing_engine.strategies._base import PanelStrategy, RollingSpec
from tests.fixtures.strategies.panel import add_features, last_date, make_bars, make_panel

STRATEGIES = {
    "sr_bounce", "sr_breakout", "pullback_trend", "breakout_52w", "momentum_burst", "rsi2_meanrev", "insider_cluster",
}
# docs/feature-contract.md column names (plus bar columns); strategies may read only these
CONTRACT_COLUMNS = {
    "symbol", "ts", "open", "high", "low", "close", "volume", "vwap", "adj_close",
    "sma_10", "sma_20", "sma_50", "sma_200", "ema_9", "ema_21", "rsi_2", "rsi_14", "macd", "macd_signal", "macd_hist",
    "bb_upper_20", "bb_lower_20", "bb_width_20", "atr_14", "atr_pct_14",
    "ret_1d", "ret_5d", "ret_21d", "ret_63d", "ret_126d", "ret_252d", "mom_12_1", "rev_5d", "rev_21d", "vol_21d",
    "vol_63d", "dollar_vol_20d", "avg_vol_20d", "avg_vol_50d", "amihud_21d", "high_52w", "low_52w", "dist_52w_high",
    "rvol_day", "gap_pct", "range_pct", "close_pos", "up_days_3", "prev_close",
    "support_1", "resistance_1", "range_width", "level_touch_pct", "level_break",
    "vcp_contraction", "base_len", "burst_4pct", "breakout_52w", "inside_day", "key_reversal",
    "trend_state", "vol_regime", "market_trend_state", "market_vol_regime",
}


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return make_panel(("AAA", "BBB", "CCC", "DDD"), n_days=320, seed=11)


def test_registry_lists_all_strategies():
    assert STRATEGIES <= set(registry.names("strategy"))


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_defaults_params_and_required_features(name):
    cls = registry.get("strategy", name)
    strat = cls()
    assert strat.name == name
    assert strat.default_params, "every threshold must be a default_params entry"
    assert "min_reward_risk" in strat.default_params
    # contract columns plus on-demand `features.extra` columns the strategy declares in `extra_features`
    assert set(strat.required_features()) <= CONTRACT_COLUMNS | set(strat.extra_features)
    assert all(is_extra(n) for n in strat.extra_features), "extra_features must resolve in features.extra"
    assert "symbol" not in strat.required_features()
    override = cls({"min_reward_risk": 9.75})
    assert override.params["min_reward_risk"] == 9.75
    assert strat.params["min_reward_risk"] == cls.default_params["min_reward_risk"], "defaults are not mutated"


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_generator_panel_has_required_columns(name, panel):
    strat = registry.get("strategy", name)()
    panel = ensure_extra(panel, strat.extra_features)
    missing = [c for c in strat.required_features() if c not in panel.columns]
    assert not missing
    tail = panel.groupby("symbol").tail(1)
    # level columns are NaN by contract when no pivot exists above/below; every column must be warm somewhere
    assert tail[strat.required_features()].notna().any().all()


def _day(panel: pd.DataFrame) -> pd.Series:
    return panel["ts"].dt.tz_localize(None).dt.normalize()


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_signals_are_well_formed_and_point_in_time(name, panel):
    strat = registry.get("strategy", name)()
    if name == "insider_cluster":
        panel = panel.assign(insider_cluster_score=2.0)
    as_of = last_date(panel) - timedelta(days=40)
    sigs = strat.signals(panel, as_of)
    for s in sigs:
        assert isinstance(s, Signal)
        assert s.strategy == name and s.side == Side.LONG and s.as_of == as_of
        assert s.stop < s.entry
        assert s.risk_per_share() > 0
        if s.target is not None:
            assert s.target > s.entry
            assert s.reward_risk == pytest.approx((s.target - s.entry) / (s.entry - s.stop))
            assert s.reward_risk >= strat.params["min_reward_risk"]
        assert all(isinstance(v, float) for v in s.features.values())
    truncated = panel.loc[_day(panel) <= pd.Timestamp(as_of)]
    assert strat.signals(truncated, as_of) == sigs, "future bars must not change today's signals"
    # a weekend as_of resolves to the last session before it
    saturday = as_of + timedelta(days=(5 - as_of.weekday()) % 7)
    friday = saturday - timedelta(days=1)
    assert [s.symbol for s in strat.signals(panel, saturday)] == [s.symbol for s in strat.signals(panel, friday)]


def test_missing_required_column_raises(panel):
    strat = registry.get("strategy", "sr_bounce")()
    with pytest.raises(KeyError, match="atr_14"):
        strat.signals(panel.drop(columns=["atr_14"]), last_date(panel))


def test_empty_panel_gives_no_signals(panel):
    strat = registry.get("strategy", "sr_bounce")()
    assert strat.signals(panel.iloc[0:0], last_date(panel)) == []
    assert strat.signals(panel, date(2000, 1, 1)) == []


class _Probe(PanelStrategy):
    name = "probe"
    default_params = {"min_reward_risk": 0.0, "min_market_trend_state": 0}
    features_required = ["atr_14"]

    def signals(self, panel, as_of, regime=None):
        return []


def test_rows_as_of_prior_and_rolling_columns():
    bars = make_bars(("AAA", "BBB"), n_days=30, seed=3)
    stale = bars[~((bars["symbol"] == "BBB") & (bars["ts"] >= bars["ts"].iloc[20]))]  # BBB stops trading
    panel = add_features(stale)
    probe = _Probe()
    as_of = last_date(panel)
    rows = probe.rows_as_of(panel, as_of, rolling=[RollingSpec("high", "max", 5, prior=True), RollingSpec("low", "min", 3)])
    assert list(rows["symbol"]) == ["AAA"], "symbols without a bar on the as-of session are dropped"
    aaa = panel[panel["symbol"] == "AAA"].reset_index(drop=True)
    row = rows.iloc[0]
    assert row["prior_close"] == aaa["close"].iloc[-2]
    assert row["prior_high"] == aaa["high"].iloc[-2]
    assert row["prior_max_high_5"] == aaa["high"].iloc[-6:-1].max()
    assert row["min_low_3"] == aaa["low"].iloc[-3:].min()


def test_market_regime_gate():
    probe = _Probe()
    assert probe.market_ok(None)
    assert probe.market_ok({})
    assert probe.market_ok({"market_trend_state": 1})
    assert probe.market_ok({"market_trend_state": 0})
    assert not probe.market_ok({"market_trend_state": -1})
    assert _Probe({"min_market_trend_state": -1}).market_ok({"market_trend_state": -1})


def test_build_signal_rejects_bad_geometry():
    probe = _Probe({"min_reward_risk": 2.0})
    row = pd.Series({"symbol": "AAA"})
    today = date(2024, 6, 3)
    assert probe.build_signal(row, today, entry=100.0, stop=101.0, target=110.0, score=1.0) is None
    assert probe.build_signal(row, today, entry=100.0, stop=95.0, target=99.0, score=1.0) is None
    assert probe.build_signal(row, today, entry=100.0, stop=95.0, target=105.0, score=1.0) is None  # rr 1 < 2
    assert probe.build_signal(row, today, entry=float("nan"), stop=95.0, target=105.0, score=1.0) is None
    sig = probe.build_signal(row, today, entry=100.0, stop=95.0, target=110.0, score=1.0, features={"x": float("nan"), "y": 2})
    assert sig is not None and sig.reward_risk == pytest.approx(2.0) and sig.features == {"y": 2.0}
    open_ended = probe.build_signal(row, today, entry=100.0, stop=95.0, target=None, score=1.0)
    assert open_ended is not None and open_ended.target is None and open_ended.reward_risk is None


def test_stop_closer_than_the_floor_is_rejected() -> None:
    from datetime import date

    from swing_engine.strategies._base import MIN_STOP_FRACTION, PanelStrategy

    class Probe(PanelStrategy):
        name = "probe"
        default_params = {"min_reward_risk": 0.0}

        def signals(self, panel, as_of):  # noqa: ANN001, ANN201 - not used
            return []

    row = pd.Series({"symbol": "AAA"})
    s = Probe({})
    assert s.build_signal(row, date(2026, 1, 2), entry=100.0, stop=100.0 * (1 - MIN_STOP_FRACTION / 2),
                          target=None, score=1.0) is None
    assert s.build_signal(row, date(2026, 1, 2), entry=100.0, stop=99.0, target=None, score=1.0) is not None
    assert Probe({"min_stop_pct": 0.0}).build_signal(row, date(2026, 1, 2), entry=100.0, stop=99.99, target=None,
                                                    score=1.0) is not None
