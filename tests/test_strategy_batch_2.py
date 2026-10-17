"""Catalog batch 2 strategies: one hand-built panel where each must fire, one where it must not, plus geometry and
the generic contract checks of tests/test_strategies_common.py on a panel that carries SPY and every extra."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import EntryType, Side
from swing_engine.features.extra import ensure_extra, is_extra
from swing_engine.features.panel import build_panel
from swing_engine.strategies._base import PanelStrategy
from swing_engine.strategies.darvas_box import darvas_box
from tests.fixtures.strategies.panel import bars_from_closes, bars_from_ohlc

SLUGS = [
    "santa_claus_rally", "heston_sadka_seasonality", "short_term_reversal_1m", "bollinger_squeeze_breakout",
    "calhoun_four_day_breakout", "connors_hpetf_rsi_variants", "darvas_box", "full_gap_continuation_bar",
    "ichimoku_cloud_pullback", "kaufman_stress", "macd_zero_line_swing_points", "pendergast_swingthree",
    "rsi_oversold_macd_confirm", "tko_landry", "donchian_channel_breakout", "katsanos_rsmk", "oscillator_cross_family",
    "sentiment_zone_oscillator", "vervoort_heikin_ashi_family",
]


# ----------------------------------------------------------------------------------------------- helpers
def _strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


def _panel(strat, *frames: pd.DataFrame) -> pd.DataFrame:
    bars = pd.concat(frames, ignore_index=True)
    spy = bars.loc[bars["symbol"] == "SPY"]
    return ensure_extra(build_panel(bars, spy if not spy.empty else None), strat.extra_features)


def _sessions(panel: pd.DataFrame) -> list[date]:
    return sorted({ts.date() for ts in panel["ts"]})


def _scan(strat, panel: pd.DataFrame, last_n: int = 1) -> list:
    out = []
    for d in _sessions(panel)[-last_n:]:
        out.extend(strat.signals(panel, d))
    return out


def _ramp(n: int, start: float = 50.0, growth: float = 0.004) -> np.ndarray:
    return start * (1.0 + growth) ** np.arange(n)


def _check(strat, sigs) -> None:
    """Geometry and exits: stop < entry, target above entry, R:R floor, time exit at max_hold_days."""
    assert sigs
    for s in sigs:
        assert s.strategy == strat.name and s.side == Side.LONG
        assert s.stop < s.entry
        if s.target is not None:
            assert s.target > s.entry and s.reward_risk >= strat.params["min_reward_risk"]
        assert all(isinstance(v, float) for v in s.features.values())
    row = pd.Series({"close": 1.0, "open": 1.0, "high": 1.0, "low": 1.0})
    if type(strat).should_exit is not PanelStrategy.should_exit:  # others exit on the engine's max_hold_days
        assert strat.should_exit(row, int(strat.params["max_hold_days"]))


# ----------------------------------------------------------------------------------------------- contract
@pytest.fixture(scope="module")
def generic_panel() -> pd.DataFrame:
    rng = np.random.default_rng(5)
    frames = []
    for sym in ("AAA", "BBB", "CCC", "SPY"):
        c = 50 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, 320)))
        frames.append(bars_from_closes(sym, c, spread=0.01))
    bars = pd.concat(frames, ignore_index=True)
    names = [n for s in SLUGS for n in _strat(s).extra_features]
    return ensure_extra(build_panel(bars, bars[bars["symbol"] == "SPY"]), names)


@pytest.mark.parametrize("name", SLUGS)
def test_contract(name, generic_panel):
    strat = _strat(name)
    assert strat.name == name and "min_reward_risk" in strat.default_params
    assert all(is_extra(n) for n in strat.extra_features)
    assert not [c for c in strat.required_features() if c not in generic_panel.columns]
    as_of = generic_panel["ts"].max().date() - timedelta(days=40)
    sigs = strat.signals(generic_panel, as_of)
    for s in sigs:
        assert s.stop < s.entry and s.as_of == as_of
    cut = generic_panel.loc[generic_panel["ts"].dt.tz_localize(None).dt.normalize() <= pd.Timestamp(as_of)]
    assert strat.signals(cut, as_of) == sigs, "future bars must not change today's signals"


# ----------------------------------------------------------------------------------------------- calendar / factor
def test_santa_claus_rally():
    strat = _strat("santa_claus_rally")
    n = 60
    start = pd.bdate_range(end="2024-12-23", periods=n)[0].strftime("%Y-%m-%d")  # 6th-to-last NYSE session of 2024
    panel = _panel(strat, bars_from_closes("SPY", _ramp(n), start=start), bars_from_closes("AAA", _ramp(n), start=start))
    sigs = strat.signals(panel, date(2024, 12, 23))
    _check(strat, sigs)
    assert [s.symbol for s in sigs] == ["SPY"]
    assert strat.signals(panel, date(2024, 12, 20)) == []  # 7th-to-last session: window not next


def test_heston_sadka_seasonality():
    strat = _strat("heston_sadka_seasonality")
    days = pd.bdate_range("2020-01-02", "2024-03-01")
    frames = []
    for i in range(10):
        c = np.full(len(days), 100.0 + i)
        if i == 0:
            c = np.where(days.month == 3, 110.0, 100.0)  # S0 rallies every March
        frames.append(bars_from_closes(f"S{i}", c, start="2020-01-02"))
    panel = _panel(strat, *frames)
    sigs = strat.signals(panel, date(2024, 3, 1))  # first session of March
    _check(strat, sigs)
    assert [s.symbol for s in sigs] == ["S0"]
    assert sigs[0].features["seas_month_1_5"] == pytest.approx(0.10)
    assert strat.signals(panel, date(2024, 2, 29)) == []  # not a month's first session


def test_short_term_reversal_1m():
    strat = _strat("short_term_reversal_1m")
    n, start = 300, pd.bdate_range(end="2025-02-21", periods=300)[0].strftime("%Y-%m-%d")  # ends on a Friday
    t = np.arange(n)
    frames = [bars_from_closes(f"S{i}", 50 * np.exp((0.0005 + 0.0002 * i) * t), start=start) for i in range(34)]
    loser = np.where(t < n - 21, 0.01 * t, 0.01 * (n - 21) - 0.008 * (t - (n - 21)))  # top momentum, then -15%
    frames.append(bars_from_closes("LOSER", 50 * np.exp(loser), start=start))
    panel = _panel(strat, *frames)
    sigs = strat.signals(panel, date(2025, 2, 21))
    _check(strat, sigs)
    assert max(sigs, key=lambda s: s.score).symbol == "LOSER"
    assert strat.signals(panel, date(2025, 2, 20)) == []  # Thursday: no rebalance


# ----------------------------------------------------------------------------------------------- breakouts
def test_bollinger_squeeze_breakout():
    strat = _strat("bollinger_squeeze_breakout")
    ramp = _ramp(250, growth=0.003) * (1 + 0.03 * np.sign(np.sin(np.arange(250))))  # noisy uptrend: wide bands
    quiet = ramp[-1] * (1 + 0.001 * np.sign(np.sin(np.arange(40))))  # tight base: BandWidth collapses
    fire = _panel(strat, bars_from_closes("AAA", np.r_[ramp, quiet, quiet[-1] * 1.04]))
    _check(strat, _scan(strat, fire))
    flat = _panel(strat, bars_from_closes("AAA", np.r_[ramp, quiet, quiet[-1]]))
    assert _scan(strat, flat) == []


def test_calhoun_four_day_breakout():
    strat = _strat("calhoun_four_day_breakout")
    fire = _panel(strat, bars_from_closes("AAA", _ramp(260)))  # every ramp bar opens at the prior close: bullish
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert sigs[0].entry_type == EntryType.STOP and sigs[0].entry > float(fire["high"].iloc[-1])
    down = _panel(strat, bars_from_closes("AAA", np.r_[_ramp(259), _ramp(259)[-1] * 0.99]))
    assert _scan(strat, down) == []


def test_darvas_box_machine_and_strategy():
    highs = np.array([10, 11, 12, 11.5, 11.8, 11.6, 11.7, 11.9, 11.4])
    lows = np.array([9, 10, 11, 10.5, 10.2, 10.6, 10.4, 10.5, 10.3])
    box = darvas_box(highs, lows, 3)
    assert box is not None and box.top == 12 and box.bottom == 10.2
    assert darvas_box(highs[:6], lows[:6], 3) is None  # bottom not yet held for 3 bars
    assert darvas_box(np.r_[highs, 12.5], np.r_[lows, 11], 3) is None  # broken out: a new box starts

    strat = _strat("darvas_box")
    ramp = _ramp(260, start=60, growth=0.004)
    top = ramp[-1] * 1.01
    rows = [[c, c * 1.002, c * 0.998, c, 1e6] for c in ramp]
    box_rows = [(top - 0.5, top, top - 2, top - 1), (top - 1, top - 0.6, top - 3, top - 2), (top - 2, top - 1,
                top - 4, top - 3.5), (top - 3, top - 1.5, top - 5, top - 4), (top - 4, top - 2, top - 4.5, top - 3),
                (top - 3, top - 1.5, top - 4.2, top - 2.5), (top - 2.5, top - 1, top - 4.0, top - 2),
                (top - 2, top - 1.2, top - 3.5, top - 2.2)]
    rows += [[o, h, lo, c, 1e6] for o, h, lo, c in box_rows]
    breakout = [top - 1, top + 2, top - 1.2, top + 1.5]
    fire = _panel(strat, bars_from_ohlc("AAA", [*rows, [*breakout, 3e6]]))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert sigs[0].features["box_top"] == pytest.approx(top)
    assert sigs[0].stop < top - 5  # under the box bottom
    quiet = _panel(strat, bars_from_ohlc("AAA", [*rows, [*breakout, 1e6]]))  # no volume expansion
    assert _scan(strat, quiet) == []


def test_full_gap_continuation_bar():
    strat = _strat("full_gap_continuation_bar")
    rows = [[c, c * 1.005, c * 0.995, c, 1e6] for c in _ramp(220)]
    last = rows[-1][3]
    fire = _panel(strat, bars_from_ohlc("AAA", [*rows, [last * 1.03, last * 1.05, last * 1.02, last * 1.04, 2e6]]))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert sigs[0].stop == pytest.approx(rows[-1][1])  # stop at the prior high
    no_gap = _panel(strat, bars_from_ohlc("AAA", [*rows, [last, last * 1.02, last * 0.999, last * 1.01, 1e6]]))
    assert _scan(strat, no_gap) == []


def test_donchian_channel_breakout():
    strat = _strat("donchian_channel_breakout")
    fire = _panel(strat, bars_from_closes("AAA", _ramp(260, growth=0.01)))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    row = fire.iloc[-1]
    assert strat.trail_stop(row) == pytest.approx(fire["low"].iloc[-15:].min())
    assert not strat.engine_trail
    down = _panel(strat, bars_from_closes("AAA", np.r_[_ramp(259), _ramp(259)[-1] * 0.98]))
    assert _scan(strat, down) == []


def test_pendergast_swingthree():
    strat = _strat("pendergast_swingthree")
    fire = _panel(strat, bars_from_closes("AAA", _ramp(260, growth=0.01), spread=0.015))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    row = fire.iloc[-1].copy()
    row["low"] = row["sma_5_of_low"] - 0.01
    assert strat.should_exit(row, 1)
    down = _panel(strat, bars_from_closes("AAA", np.r_[_ramp(259, growth=0.01), _ramp(259, growth=0.01)[-1] * 0.97],
                                          spread=0.015))
    assert _scan(strat, down) == []


def test_tko_landry():
    strat = _strat("tko_landry")
    rows = [[c, c * 1.003, c * 0.997, c, 1e6] for c in _ramp(220, growth=0.003)]
    c = rows[-1][3]
    ko = [c, c * 1.002, c * 0.95, c * 0.955, 2e6]  # wide down bar closing near its low, under the recent lows
    fire = _panel(strat, bars_from_ohlc("AAA", [*rows, ko, [c * 0.96, c * 1.01, c * 0.958, c * 1.005, 1e6]]))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert sigs[0].features["ko_high"] == pytest.approx(c * 1.002)
    stall = _panel(strat, bars_from_ohlc("AAA", [*rows, ko, [c * 0.96, c * 0.99, c * 0.958, c * 0.98, 1e6]]))
    assert _scan(strat, stall) == []


# ----------------------------------------------------------------------------------------------- mean reversion
@pytest.mark.parametrize("variant", ["rsi_25_75", "multiple_days_down", "rsi_10_6"])
def test_connors_hpetf_variants(variant):
    strat = _strat("connors_hpetf_rsi_variants", variant=variant)
    ramp = _ramp(260)
    dip = ramp[-1] * np.array([0.99, 0.98, 0.97, 0.96])
    fire = _panel(strat, bars_from_closes("SPY", np.r_[ramp, dip]))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert _scan(strat, _panel(strat, bars_from_closes("SPY", _ramp(264)))) == []


def test_rsi_oversold_macd_confirm():
    strat = _strat("rsi_oversold_macd_confirm")
    t = np.arange(200)
    waves = 100 * (1 - 0.001 * t) * (1 + 0.05 * np.sin(t / 6.0))  # falling swings: RSI dips under 30 and recovers
    _check(strat, _scan(strat, _panel(strat, bars_from_closes("AAA", waves)), last_n=100))
    assert _scan(strat, _panel(strat, bars_from_closes("AAA", _ramp(200))), last_n=100) == []  # never oversold


def test_kaufman_stress():
    strat = _strat("kaufman_stress")
    n = 320
    t = np.arange(n)
    spy_up = _ramp(n, start=100, growth=0.001)
    stock = 50 * (1 + 0.0015 * t) * (1 + 0.06 * np.sin(t / 7.0))  # swings vs a steadily rising SPY
    fire = _panel(strat, bars_from_closes("SPY", spy_up), bars_from_closes("AAA", stock))
    sigs = _scan(strat, fire, last_n=60)
    _check(strat, sigs)
    assert {s.symbol for s in sigs} == {"AAA"}
    spy_down = _ramp(n, start=100, growth=-0.001)  # index 60-day SMA falling: no entries
    assert _scan(strat, _panel(strat, bars_from_closes("SPY", spy_down), bars_from_closes("AAA", stock)), 60) == []


# ----------------------------------------------------------------------------------------------- trend / momentum
def test_ichimoku_cloud_pullback():
    strat = _strat("ichimoku_cloud_pullback")
    ramp = _ramp(200, start=100, growth=0.004)
    pull = ramp[-1] * np.array([0.985, 0.97, 0.955, 0.945, 0.94, 0.935])
    fire = _panel(strat, bars_from_closes("AAA", np.r_[ramp, pull, ramp[-1] * 0.99]))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert sigs[0].stop < ramp[-1] * 0.935
    assert _scan(strat, _panel(strat, bars_from_closes("AAA", np.r_[ramp, pull, ramp[-1] * 0.93]))) == []


def test_macd_zero_line_swing_points():
    strat = _strat("macd_zero_line_swing_points")
    t = np.arange(260)
    trend = np.where(t < 120, 1 - 0.002 * t, 0.76 * (1 + 0.003 * (t - 120)))  # decline, then a recovery
    fire = _panel(strat, bars_from_closes("AAA", 100 * trend * (1 + 0.06 * np.sin(t / 5.0))))  # in swings
    _check(strat, _scan(strat, fire, last_n=140))
    falling = _panel(strat, bars_from_closes("AAA", _ramp(260, start=100, growth=-0.002)))
    assert _scan(strat, falling, last_n=140) == []


def test_katsanos_rsmk():
    strat = _strat("katsanos_rsmk")
    spy = np.full(200, 100.0)
    lag = 50 * (1 - 0.001) ** np.arange(200)
    fire = _panel(strat, bars_from_closes("SPY", spy), bars_from_closes("AAA", np.r_[lag[:-1], lag[-2] * 1.3]))
    sigs = _scan(strat, fire)
    _check(strat, sigs)
    assert [s.symbol for s in sigs] == ["AAA"]
    assert _scan(strat, _panel(strat, bars_from_closes("SPY", spy), bars_from_closes("AAA", lag)), 15) == []


def test_oscillator_cross_rsi_and_momentum_variants():
    strat = _strat("oscillator_cross_family")
    base = _ramp(100, start=100, growth=0.001)
    fall = base[-1] * (1 - 0.015) ** np.arange(1, 20)
    fire = _panel(strat, bars_from_closes("AAA", np.r_[base, fall, fall[-1] * 1.05, fall[-1] * 1.10]))
    _check(strat, _scan(strat, fire, last_n=2))
    assert _scan(strat, _panel(strat, bars_from_closes("AAA", np.r_[base, fall])), last_n=5) == []

    mom = _strat("oscillator_cross_family", variant="momentum_rising")
    accel = 50 * np.exp(0.00002 * np.arange(200) ** 2)  # accelerating: roc_12 > 0 and rising
    sigs = _scan(mom, _panel(mom, bars_from_closes("AAA", accel)))
    _check(mom, sigs)
    assert sigs[0].entry_type == EntryType.STOP
    decel = 50 * np.exp(0.02 * np.sqrt(np.arange(200)))  # decelerating: momentum falls
    assert _scan(mom, _panel(mom, bars_from_closes("AAA", decel))) == []
    with pytest.raises(ValueError, match="variant"):
        _strat("oscillator_cross_family", variant="nope")


def test_sentiment_zone_oscillator():
    strat = _strat("sentiment_zone_oscillator")
    t = np.arange(260)
    wave = 50 * (1 + 0.002 * t) * (1 + 0.05 * np.sin(t / 9.0))  # uptrend with swings: SMA30(SZO) crosses 0
    sigs = _scan(strat, _panel(strat, bars_from_closes("AAA", wave)), last_n=80)
    _check(strat, sigs)
    falling = 50 * (1 - 0.003) ** t  # every close down: SZO pinned at its floor, close under EMA60
    assert _scan(strat, _panel(strat, bars_from_closes("AAA", falling)), last_n=80) == []


@pytest.mark.parametrize("variant", ["ha_typ_cross", "svesc"])
def test_vervoort_heikin_ashi(variant):
    strat = _strat("vervoort_heikin_ashi_family", variant=variant)
    down = _ramp(80, start=100, growth=-0.01)
    up = down[-1] * (1 + 0.02) ** np.arange(1, 6)
    _check(strat, _scan(strat, _panel(strat, bars_from_closes("AAA", np.r_[down, up])), last_n=5))
    assert _scan(strat, _panel(strat, bars_from_closes("AAA", down)), last_n=5) == []
