"""Catalog strategy batch 0: one fire / no-fire hand-built case per strategy plus the cross-strategy contract checks
(tests/test_strategies_common.py) run over these modules on a panel that carries SPY and their extra features."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import EntryType, Side, Signal
from swing_engine.features.extra import ensure_extra, is_extra
from swing_engine.features.patterns2 import PATTERNS2_COLUMNS
from tests.fixtures.strategies.panel import (
    add_features,
    bars_from_closes,
    bars_from_ohlc,
    last_date,
    make_panel,
    set_last,
    trend_rows,
)
from tests.test_strategies_common import CONTRACT_COLUMNS

BATCH = [
    "earnings_announcement_premium", "opportunistic_insider_purchases_cmp", "residual_momentum",
    "bollinger_band_mean_reversion", "calhoun_adx_breakout", "connors_3day_high_low", "consecutive_bars",
    "expansion_pivot_cooper", "ibd_other_bases", "katsanos_vpn_breakout", "landry_bow_tie", "open_volatility_breakout",
    "pullback_ema_zone", "the_anti", "vcp_sepa_breakout", "apirine_roc_bands", "fundamental_setup_technical_trigger",
    "last_stochastic_weekly", "radge_weekend_trend_trader", "tac_dmi_trend_start",
]
# short windows so the generic panel (320 bars) warms up; the default is the card's 756-bar fit
SMALL_PARAMS = {"residual_momentum": {"beta_bars": 120, "formation_bars": 60, "skip_bars": 10}}
OPTIONAL_COLUMNS = {"days_since_earnings": 53.0, "sue": 1.0, "opp_buy_value_21d": 50_000.0, "opp_buy_flag": 1.0}


def strat(name: str, params: dict | None = None):
    return registry.get("strategy", name)(params)


def run(s, panel: pd.DataFrame, as_of=None) -> list[Signal]:
    return s.signals(ensure_extra(panel, s.extra_features), as_of or last_date(panel))


def set_tail(panel: pd.DataFrame, symbol: str, col: str, values) -> pd.DataFrame:
    out = panel.copy()
    idx = out.index[out["symbol"] == symbol][-len(values) :]
    out[col] = out[col].astype(float) if col in out else np.nan
    out.loc[idx, col] = np.asarray(values, dtype=float)
    return out


def uptrend(n: int = 260) -> pd.DataFrame:
    return add_features(bars_from_ohlc("AAA", trend_rows(n)))


def only(sigs: list[Signal]) -> Signal:
    assert len(sigs) == 1, sigs
    s = sigs[0]
    assert s.side == Side.LONG and s.stop < s.entry and s.risk_per_share() > 0
    if s.target is not None:
        assert s.target > s.entry
    return s


# ----------------------------------------------------------------------------------------------- generic contract
@pytest.fixture(scope="module")
def generic_panel() -> pd.DataFrame:
    p = make_panel(("AAA", "BBB", "CCC", "DDD", "SPY"), n_days=320, seed=11)
    return p.assign(**OPTIONAL_COLUMNS)


@pytest.mark.parametrize("name", BATCH)
def test_defaults_params_and_required_features(name):
    cls = registry.get("strategy", name)
    s = cls()
    assert s.name == name and s.default_params and "min_reward_risk" in s.default_params
    # ibd_other_bases inherits base_breakout's patterns2 columns, which `as_of_view` attaches itself
    assert set(s.required_features()) <= CONTRACT_COLUMNS | set(PATTERNS2_COLUMNS) | set(s.extra_features)
    assert all(is_extra(n) for n in s.extra_features) and all(is_extra(n) for n in cls.extra_features)
    assert cls({"min_reward_risk": 9.75}).params["min_reward_risk"] == 9.75
    assert s.params["min_reward_risk"] == cls.default_params["min_reward_risk"]


@pytest.mark.parametrize("name", BATCH)
def test_signals_well_formed_point_in_time_and_warm(name, generic_panel):
    s = strat(name, SMALL_PARAMS.get(name))
    panel = ensure_extra(generic_panel, s.extra_features)
    tail = panel.groupby("symbol").tail(1)
    warm = [c for c in s.required_features() if c in panel.columns]  # patterns2 columns come from as_of_view
    assert tail[warm].notna().any().all()
    day = panel["ts"].dt.tz_localize(None).dt.normalize()
    for back in (40, 20, 7):
        as_of = last_date(panel) - timedelta(days=back)
        sigs = s.signals(panel, as_of)
        for sig in sigs:
            assert sig.strategy == name and sig.as_of == as_of and sig.stop < sig.entry
            if sig.target is not None:
                assert sig.reward_risk == pytest.approx((sig.target - sig.entry) / (sig.entry - sig.stop))
                assert sig.reward_risk >= s.params["min_reward_risk"]
            assert all(isinstance(v, float) for v in sig.features.values())
        assert s.signals(panel.loc[day <= pd.Timestamp(as_of)], as_of) == sigs
        saturday = as_of + timedelta(days=(5 - as_of.weekday()) % 7)
        assert [x.symbol for x in s.signals(panel, saturday)] == [
            x.symbol for x in s.signals(panel, saturday - timedelta(days=1))
        ]


# ----------------------------------------------------------------------------------------------- optional-column
def test_earnings_announcement_premium_window():
    s = strat("earnings_announcement_premium")
    p = uptrend()
    assert run(s, p) == []  # no days_since_earnings column -> nothing
    sig = only(run(s, set_last(p.assign(days_since_earnings=0.0), "AAA", days_since_earnings=53)))
    assert sig.target is None and sig.entry - sig.stop == pytest.approx(2 * p["atr_14"].iloc[-1])
    assert run(s, set_last(p.assign(days_since_earnings=0.0), "AAA", days_since_earnings=52)) == []
    assert s.should_exit(pd.Series(dtype=float), 15) and not s.should_exit(pd.Series(dtype=float), 14)


def test_opportunistic_insider_purchases_threshold():
    s = strat("opportunistic_insider_purchases_cmp")
    p = uptrend()
    assert run(s, p) == []
    sig = only(run(s, set_last(p.assign(opp_buy_value_21d=0.0), "AAA", opp_buy_value_21d=30_000, opp_buy_flag=1)))
    assert sig.reward_risk == pytest.approx(2.0)
    assert run(s, set_last(p.assign(opp_buy_value_21d=0.0), "AAA", opp_buy_value_21d=30_000, opp_buy_flag=0)) == []
    assert run(s, set_last(p.assign(opp_buy_value_21d=0.0), "AAA", opp_buy_value_21d=10_000)) == []
    assert s.should_exit(pd.Series(dtype=float), 21)


def test_fundamental_setup_technical_trigger():
    s = strat("fundamental_setup_technical_trigger")
    p = uptrend(60)
    assert run(s, p) == []
    sig = only(run(s, p.assign(sue=1.0)))
    atr = p["atr_14"].iloc[-1]
    assert sig.target is None and sig.entry - sig.stop >= atr - 1e-9
    assert run(s, p.assign(sue=-1.0)) == []
    row = ensure_extra(p, s.extra_features).iloc[-1].copy()
    row["close"] = row["dc_low_6"] - 1
    assert s.should_exit(row, 1)


# ----------------------------------------------------------------------------------------------- factor / calendar
def test_residual_momentum_month_start_top_decile():
    s = strat("residual_momentum")
    col, rank = s.extra_features[0], s.extra_features[2]  # capm score / rank (no ff_* columns: auto -> capm)
    p = uptrend().assign(**{col: 1.0, rank: 0.5})
    ts = p["ts"]
    first = ts[ts.dt.month != ts.shift().dt.month].iloc[5]  # a first session of a month
    mid = first + pd.offsets.BDay(3)
    p.loc[ts.isin([first, mid]), rank] = 0.95
    assert only(run(s, p, first.date())).target is None
    assert run(s, p, mid.date()) == []  # not a rebalance day
    p.loc[ts == first, rank] = 0.5
    assert run(s, p, first.date()) == []


def test_residual_momentum_uses_ff3_scores_when_present():
    s = strat("residual_momentum")
    capm, ff3, capm_rank, ff3_rank = s.extra_features
    assert ff3 == "ff3_resid_mom_756_231"
    p = uptrend()
    ts = p["ts"]
    first = ts[ts.dt.month != ts.shift().dt.month].iloc[5]
    p = p.assign(**{capm: 1.0, capm_rank: 0.95, ff3: 2.0, ff3_rank: 0.5})
    assert run(s, p, first.date()) == []  # ff3 present: its rank (0.5) decides, not the capm one
    p.loc[ts == first, ff3_rank] = 0.95
    sig = only(run(s, p, first.date()))
    assert ff3 in sig.features and "(ff3)" in sig.notes
    capm_only = strat("residual_momentum", {"factor_model": "capm"})
    assert "(capm)" in only(run(capm_only, p.assign(**{ff3_rank: 0.5}), first.date())).notes
    no_ff = p.assign(**{ff3: np.nan, ff3_rank: np.nan})  # SPY fallback when the factors are absent
    assert "(capm)" in only(run(s, no_ff, first.date())).notes


def test_last_stochastic_weekly_cross():
    s = strat("last_stochastic_weekly")
    p = ensure_extra(uptrend(), s.extra_features)
    vals = {"wk_fresh": 1, "wk_stoch_39_3": 55, "prev_wk_stoch_39_3": 45, "wk_close": 101, "wk_close_max_1": 100}
    sig = only(run(s, set_last(p, "AAA", **vals)))
    assert sig.entry - sig.stop <= 2.5 * p["atr_14"].iloc[-1] + 1e-9
    assert run(s, set_last(p, "AAA", **{**vals, "prev_wk_stoch_39_3": 52})) == []
    assert run(s, set_last(p, "AAA", **{**vals, "wk_fresh": 0})) == []
    sell = set_last(p, "AAA", **{**vals, "wk_stoch_39_3": 45, "prev_wk_stoch_39_3": 55, "wk_close": 99}).iloc[-1]
    assert s.should_exit(sell, 3) and s.engine_trail is False


def test_radge_weekend_trend_trader_entry_and_trail():
    s = strat("radge_weekend_trend_trader")
    p = ensure_extra(uptrend(), s.extra_features)
    vals = {"wk_fresh": 1, "wk_close": 120, "wk_close_max_20": 115, "wk_roc_20": 35, "mkt_wk_above_10": 1}
    sig = only(run(s, set_last(p, "AAA", **vals)))
    assert sig.stop == pytest.approx(sig.entry * 0.6) and sig.target is None
    assert run(s, set_last(p, "AAA", **{**vals, "mkt_wk_above_10": 0})) == []
    assert run(s, set_last(p, "AAA", **{**vals, "wk_roc_20": 20})) == []
    up, down = pd.Series(vals), pd.Series({**vals, "mkt_wk_above_10": 0})
    assert s.trail_stop(up) == pytest.approx(72.0) and s.trail_stop(down) == pytest.approx(108.0)
    assert s.trail_stop(pd.Series({**vals, "wk_fresh": 0})) is None


# ----------------------------------------------------------------------------------------------- indicator triggers
def test_calhoun_adx_breakout_buy_stop():
    s = strat("calhoun_adx_breakout")
    p = ensure_extra(add_features(bars_from_ohlc("AAA", trend_rows(60, start=50, step=1.5))), s.extra_features)
    vals = {"adx_14": 42, "prev_adx_14": 38, "plus_di_14": 30, "minus_di_14": 10}
    sig = only(run(s, set_last(p, "AAA", **vals)))
    atr = p["atr_14"].iloc[-1]
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(p["high"].iloc[-1] + 0.15 * atr)
    assert sig.reward_risk == pytest.approx(2.0)
    assert run(s, set_last(p, "AAA", **{**vals, "prev_adx_14": 41})) == []


def test_katsanos_vpn_breakout_cross():
    s = strat("katsanos_vpn_breakout")
    p = ensure_extra(uptrend(), s.extra_features)
    vals = {"vpn_30": 12, "prev_vpn_30": 8, "rsi_14": 60, "avg_vol_50d": 1.2e6}
    sig = only(run(s, set_last(p, "AAA", **vals)))
    assert sig.entry - sig.stop == pytest.approx(3 * p["atr_14"].iloc[-1]) and sig.target is None
    assert run(s, set_last(p, "AAA", **{**vals, "prev_vpn_30": 11})) == []
    assert run(s, set_last(p, "AAA", **{**vals, "avg_vol_50d": 1e6})) == []  # flat average volume
    row = set_last(p, "AAA", vpn_30=1, sma_30_of_vpn_30=5, max_20_of_close=1e6).iloc[-1]
    assert s.should_exit(row, 2)


def test_the_anti_hook():
    s = strat("the_anti")
    p = ensure_extra(uptrend(), s.extra_features)
    p = set_tail(p, "AAA", "stoch_d_7_4_10", [56, 58, 60, 62, 64])
    sig = only(run(s, set_tail(p, "AAA", "stoch_k_7_4", [80, 75, 70, 65, 68])))
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(p["high"].iloc[-1] + 0.01)
    assert sig.stop == pytest.approx(p["low"].iloc[-1] - 0.01)
    assert run(s, set_tail(p, "AAA", "stoch_k_7_4", [80, 75, 70, 65, 64])) == []


def test_tac_dmi_trend_start_cluster():
    s = strat("tac_dmi_trend_start")
    p = ensure_extra(uptrend(), s.extra_features)
    vals = {"adx_3": 60, "adx_4": 62, "adx_5": 65, "prev_adx_3": 70, "prev_adx_4": 72, "prev_adx_5": 75,
            "plus_di_3": 4, "plus_di_4": 6, "plus_di_5": 8, "minus_di_3": 30, "minus_di_4": 30, "minus_di_5": 30}
    sig = only(run(s, set_last(p, "AAA", **vals)))
    assert sig.reward_risk == pytest.approx(2.0)
    assert run(s, set_last(p, "AAA", **{**vals, "plus_di_5": 12})) == []
    short = {**vals, "plus_di_3": 30, "plus_di_4": 30, "plus_di_5": 30, "minus_di_3": 4, "minus_di_4": 6, "minus_di_5": 8}
    assert s.should_exit(set_last(p, "AAA", **short).iloc[-1], 1)


def test_apirine_roc_bands_lower_band_cross():
    s = strat("apirine_roc_bands")
    avg, rms, pavg, prms = s.extra_features
    p = ensure_extra(uptrend(), s.extra_features)
    sig = only(run(s, set_last(p, "AAA", **{avg: -3, rms: 4, pavg: -5, prms: 4})))
    assert sig.reward_risk == pytest.approx(3.0)
    assert run(s, set_last(p, "AAA", **{avg: -4.5, rms: 4, pavg: -5, prms: 4})) == []
    row = set_last(p, "AAA", **{avg: 3, rms: 4, pavg: 5, prms: 4}).iloc[-1]
    assert s.should_exit(row, 1)  # avgROC crossed below the upper band


def test_bollinger_reentry_buy_stop_at_band():
    s = strat("bollinger_band_mean_reversion")
    base = [100.0, 100.5] * 130
    sig = only(run(s, add_features(bars_from_closes("AAA", [*base, 97.0, 100.0]))))
    assert sig.entry_type == EntryType.OPEN and sig.entry == pytest.approx(100.0) and sig.target is None
    assert run(s, add_features(bars_from_closes("AAA", [*base, 97.0, 97.5]))) == []


# ----------------------------------------------------------------------------------------------- price patterns
def test_connors_3day_high_low():
    s = strat("connors_3day_high_low")
    tail = [[182.0, 182.5, 181.0, 181.2, 1e6], [181.0, 181.8, 180.0, 180.3, 1e6], [180.2, 181.0, 179.0, 179.5, 1e6]]
    sig = only(run(s, add_features(bars_from_ohlc("AAA", trend_rows(257) + tail))))
    assert sig.target is None
    tail[-1][1] = 181.9  # higher high on the last bar
    assert run(s, add_features(bars_from_ohlc("AAA", trend_rows(257) + tail))) == []
    assert run(strat("connors_3day_high_low", {"symbols": ["SPY"]}),
               add_features(bars_from_ohlc("AAA", trend_rows(257) + tail))) == []


def test_consecutive_bars_exact_run():
    s = strat("consecutive_bars")
    base = [100.0, 99.0] * 130
    sig = only(run(s, add_features(bars_from_closes("AAA", [*base, 100.0, 101.0, 102.0]))))
    assert sig.reward_risk == pytest.approx(2.0)
    assert run(s, add_features(bars_from_closes("AAA", [*base, 100.0, 101.0, 102.0, 103.0]))) == []


def test_expansion_pivot_cooper():
    s = strat("expansion_pivot_cooper")
    flat = [[100.0, 100.5, 99.5, 100.0, 1e6]] * 60
    sig = only(run(s, add_features(bars_from_ohlc("AAA", [*flat, [99.8, 103.0, 99.4, 102.5, 1e6]]))))
    assert sig.entry_type == EntryType.STOP
    assert (sig.entry, sig.stop) == (pytest.approx(103.01), pytest.approx(99.39))
    assert run(s, add_features(bars_from_ohlc("AAA", [*flat, [99.8, 103.0, 99.4, 99.9, 1e6]]))) == []


def test_open_volatility_breakout_levels():
    s = strat("open_volatility_breakout")
    p = uptrend()
    sig = only(run(s, p))
    rng = p["high"].iloc[-1] - p["low"].iloc[-1]
    assert sig.entry_type == EntryType.STOP
    assert sig.entry == pytest.approx(p["close"].iloc[-1] + 0.5 * rng)
    assert sig.stop == pytest.approx(p["close"].iloc[-1] - 0.5 * rng)
    assert run(s, add_features(bars_from_ohlc("AAA", trend_rows(260, start=200, step=-0.4)))) == []


def test_landry_bow_tie_first_pullback():
    s = strat("landry_bow_tie")
    rows = [[100.0, 100.5, 99.5, 100.0, 1e6]] * 60
    rows += [[100.0 + i, 101.0 + i + 0.3, 99.7 + i, 101.0 + i, 1e6] for i in range(8)]  # fan-out into proper order
    pull = [[108.0, 108.2, 106.0, 106.5, 1e6], [106.5, 106.8, 105.0, 105.5, 1e6]]
    sig = only(run(s, add_features(bars_from_ohlc("AAA", rows + pull))))
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(106.81)
    assert sig.reward_risk == pytest.approx(2.0)
    assert run(s, add_features(bars_from_ohlc("AAA", rows + pull[:1]))) == []  # one lower low only


def _zone_panel(touches: list[int]) -> pd.DataFrame:
    n, rows = 102, []
    for i in range(n):
        e20 = 95 + 0.1 * i
        low = e20 if i in touches else e20 + 3
        vol = 0.8e6 if i in touches else 1e6
        rows.append([e20 + 4, e20 + 6, low, e20 + 5, vol])
    rows[-1] = [rows[-2][3], 112.5, 108.0, 111.5, 1e6]  # close over the touch bar's high (111)
    p = add_features(bars_from_ohlc("AAA", rows))
    i = np.arange(n)
    return p.assign(ema_20=95 + 0.1 * i, ema_50=90 + 0.1 * i, trend_state=1.0)


def test_pullback_ema_zone_third_test():
    s = strat("pullback_ema_zone")
    sig = only(run(s, _zone_panel([40, 60, 80, 100])))
    assert sig.features["prior_tests"] == 3.0 and sig.target is None and s.engine_trail is False
    assert run(s, _zone_panel([60, 100])) == []  # only one earlier test
    assert run(s, _zone_panel([60, 99, 100])) == []  # multi-bar dip is not a prior test


def _vcp_closes(breakout_volume: float) -> pd.DataFrame:
    legs = [(100, 80, 9), (80, 97, 9), (97, 87, 7), (87, 95, 7), (95, 90.5, 6), (90.5, 94, 6)]
    closes = list(np.linspace(50, 100, 270))
    for a, b, k in legs:
        closes += list(np.linspace(a, b, k)[1:])
    bars = bars_from_closes("AAA", [*closes, 96.5])
    bars.loc[bars.index[-1], "volume"] = breakout_volume
    return add_features(bars)


def test_vcp_sepa_breakout():
    s = strat("vcp_sepa_breakout")
    sig = only(run(s, _vcp_closes(3e6)))
    assert sig.features["contractions"] == 3.0 and sig.target is None
    assert sig.stop == pytest.approx(90.5 * 0.995 * 0.995)
    assert run(s, _vcp_closes(1e6)) == []


def _double_bottom(breakout_volume: float) -> pd.DataFrame:
    closes = list(np.linspace(50, 100, 200))
    for a, b, k in [(100, 85, 11), (85, 95, 11), (95, 83, 11), (83, 94, 13)]:
        closes += list(np.linspace(a, b, k)[1:])
    bars = bars_from_closes("AAA", [*closes, 96.5])
    bars.loc[bars.index[-1], "volume"] = breakout_volume
    return add_features(bars)


def test_ibd_double_bottom_breakout():
    s = strat("ibd_other_bases")
    sig = only(run(s, _double_bottom(3e6)))
    assert sig.notes.startswith("double_bottom")
    assert sig.features["pivot"] == pytest.approx(95 * 1.005)
    assert sig.stop == pytest.approx(96.5 * 0.93) and sig.target == pytest.approx(96.5 * 1.2)
    assert run(s, _double_bottom(1e6)) == []


def test_ibd_ascending_base_detector():
    s = strat("ibd_other_bases")
    closes = list(np.linspace(50, 90, 150))
    for a, b in [(90, 100), (100, 88), (88, 104), (104, 92), (92, 108), (108, 95), (95, 104)]:
        closes += list(np.linspace(a, b, 11)[1:])
    w = {c: bars_from_closes("AAA", [*closes, 110.0])[c].to_numpy() for c in ("high", "low", "close")}
    base = s._ascending(w, len(w["close"]) - 2)
    assert base is not None and base.variant == "ascending_base"
    assert base.pivot == pytest.approx(108 * 1.005) and base.floor == pytest.approx(95 * 0.995)
