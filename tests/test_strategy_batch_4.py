"""Catalog batch 4 strategies: per strategy a hand-built panel where it must fire, one where it must not, and the
signal geometry / exit hooks; plus the generic contract checks over a GBM panel."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import EntryType, Side, Signal
from swing_engine.features.extra import ensure_extra, is_extra
from swing_engine.features.panel import build_panel
from tests.features_gbm import gbm_bars

NY = "America/New_York"
BATCH = [
    "turnaround_tuesday", "industry_momentum_overlay", "avwap_pullback_shannon", "boomers_cooper", "cci_correction",
    "connors_rsi2_variants", "eighty_twenty_reversal", "harmonic_gartley", "intermarket_divergence_katsanos",
    "keltner_channel_breakout", "moving_momentum_hill", "pivot_reversal_breakout", "stochastic_pop_and_drop",
    "ttm_squeeze", "wyckoff_spring_accumulation", "elder_triple_screen", "katsanos_trend_strength_filters",
    "pe_valuation_reversion",
]


# ----------------------------------------------------------------------------------------------- helpers
def ohlc(symbol: str, rows, start: str = "2023-01-02") -> pd.DataFrame:
    """Bars from (open, high, low, close, volume) rows on business days."""
    a = np.asarray(rows, dtype=float)
    return pd.DataFrame({
        "symbol": symbol, "ts": pd.bdate_range(start, periods=len(a), tz=NY), "open": a[:, 0], "high": a[:, 1],
        "low": a[:, 2], "close": a[:, 3], "volume": a[:, 4], "vwap": (a[:, 1] + a[:, 2] + a[:, 3]) / 3,
        "adj_close": a[:, 3],
    })


def closes(symbol: str, c, volume=1e6, spread: float = 0.005, start: str = "2023-01-02") -> pd.DataFrame:
    """open = prior close, high / low wrap open and close by ``spread``."""
    c = np.asarray(c, dtype=float)
    o = np.r_[c[0], c[:-1]]
    v = np.broadcast_to(np.asarray(volume, dtype=float), c.shape)
    rows = np.c_[o, np.maximum(o, c) * (1 + spread), np.minimum(o, c) * (1 - spread), c, v]
    return ohlc(symbol, rows, start)


def doji(symbol: str, c, volume=1e6, spread: float = 0.005) -> pd.DataFrame:
    """open = close, high / low = close x (1 +/- spread): strict highs and lows at every turn."""
    return ohlc(symbol, [[x, x * (1 + spread), x * (1 - spread), x, volume] for x in c])


def ramp(n: int, start: float, rate: float) -> list[float]:
    return list(start * (1 + rate) ** np.arange(n))


def strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


def panel_for(s, *frames: pd.DataFrame) -> pd.DataFrame:
    return ensure_extra(build_panel(pd.concat(frames, ignore_index=True)), s.extra_features)


def day(panel: pd.DataFrame, i: int = -1, symbol: str | None = None) -> date:
    sub = panel if symbol is None else panel[panel["symbol"] == symbol]
    return sub["ts"].iloc[i].date() if symbol else sorted(panel["ts"].unique())[i].date()


def row_at(panel: pd.DataFrame, symbol: str, d: date) -> pd.Series:
    sub = panel[(panel["symbol"] == symbol) & (panel["ts"].dt.date == d)]
    return sub.iloc[-1]


def with_(row: pd.Series, **values) -> pd.Series:
    out = row.copy()
    for k, v in values.items():
        out[k] = v
    return out


def geometry(sig: Signal, s) -> None:
    assert sig.side == Side.LONG and sig.strategy == s.name
    assert sig.stop < sig.entry
    if sig.target is not None:
        assert sig.target > sig.entry
        assert sig.reward_risk >= s.params["min_reward_risk"]
    assert all(isinstance(v, float) for v in sig.features.values())


def fire(s, panel: pd.DataFrame, as_of: date, symbol: str = "AAA") -> Signal:
    sigs = [x for x in s.signals(panel, as_of) if x.symbol == symbol]
    assert len(sigs) == 1, f"{s.name} did not fire for {symbol} on {as_of}"
    geometry(sigs[0], s)
    return sigs[0]


def silent(s, panel: pd.DataFrame, as_of: date, symbol: str = "AAA") -> None:
    assert [x for x in s.signals(panel, as_of) if x.symbol == symbol] == []


# ----------------------------------------------------------------------------------------------- generic contract
@pytest.fixture(scope="module")
def gbm_panel() -> pd.DataFrame:
    syms = ["AAA", "BBB", "CCC", "SPY", "XLK", "XLE", "XLV", "XLY", "XLP", "XLI"]
    p = build_panel(gbm_bars(syms, n_bars=330, seed=21))
    names = {n for name in BATCH for n in registry.get("strategy", name).extra_features}
    return ensure_extra(p, sorted(names))


@pytest.mark.parametrize("name", BATCH)
def test_contract(name, gbm_panel):
    cls = registry.get("strategy", name)
    s = cls()
    assert s.name == name and "min_reward_risk" in s.default_params
    assert all(is_extra(n) for n in s.extra_features)
    assert not [c for c in s.required_features() if c not in gbm_panel.columns]
    assert cls({"min_reward_risk": 9.5}).params["min_reward_risk"] == 9.5
    assert s.params["min_reward_risk"] == cls.default_params["min_reward_risk"]
    days = sorted(gbm_panel["ts"].dt.date.unique())
    for as_of in days[-60::7]:
        sigs = s.signals(gbm_panel, as_of)
        for sig in sigs:
            geometry(sig, s)
            assert sig.as_of == as_of
        cut = gbm_panel.loc[gbm_panel["ts"].dt.date <= as_of]
        assert s.signals(cut, as_of) == sigs, "future bars must not change today's signals"
    assert s.signals(gbm_panel.iloc[0:0], days[-1]) == []
    assert s.signals(gbm_panel, date(2000, 1, 3)) == []
    friday = next(d for d in reversed(days) if d.weekday() == 4)
    sat = [x.symbol for x in s.signals(gbm_panel, friday + timedelta(days=1))]
    assert sat == [x.symbol for x in s.signals(gbm_panel, friday)], "a weekend as_of resolves to Friday"


# ----------------------------------------------------------------------------------------------- turnaround_tuesday
def test_turnaround_tuesday():
    s = strat("turnaround_tuesday")
    c = ramp(40, 400.0, 0.001)  # 2023-01-02 is a Monday; bar 25 = Monday 2023-02-06
    c[25] = c[24] * 0.985
    p = panel_for(s, closes("SPY", c), closes("AAA", c))
    monday = day(p, 25)
    assert monday.weekday() == 0
    sig = fire(s, p, monday, "SPY")
    assert sig.target is None and sig.entry_type == EntryType.OPEN
    silent(s, p, monday, "AAA")  # SPY only
    silent(s, p, day(p, 26), "SPY")  # Tuesday
    c2 = list(c)
    c2[25] = c[24] * 0.995
    silent(s, panel_for(s, closes("SPY", c2)), monday, "SPY")  # only -0.5%
    assert s.should_exit(row_at(p, "SPY", monday), 1) and not s.should_exit(row_at(p, "SPY", monday), 0)


# ----------------------------------------------------------------------------------------------- industry_momentum
def test_industry_momentum_overlay():
    s = strat("industry_momentum_overlay")
    etfs = s.params["symbols"]
    frames = [closes(sym, ramp(160, 50.0, 0.0002 * (i + 1)), start="2024-01-02") for i, sym in enumerate(etfs)]
    frames.append(closes("AAA", ramp(160, 50.0, 0.01), start="2024-01-02"))
    p = panel_for(s, *frames)
    month_end = date(2024, 7, 31)
    assert row_at(p, "XLK", month_end)["tom_day"] == -1
    got = {x.symbol for x in s.signals(p, month_end)}
    assert got == set(etfs[-3:])  # top third by 6-month return: the three steepest ramps
    for sig in s.signals(p, month_end):
        geometry(sig, s)
        assert sig.target is None
    assert s.signals(p, date(2024, 7, 17)) == []  # mid-month: no rebalance
    assert s.engine_trail is False
    assert s.should_exit(row_at(p, "XLK", month_end), 21)


# ----------------------------------------------------------------------------------------------- avwap_pullback
def _avwap_bars(trigger: float) -> pd.DataFrame:
    base = ramp(230, 40.0, 0.004)
    a0 = base[-1]
    dip = [a0 * f for f in (0.99, 0.98, 0.97, 0.96, 0.95)]  # bar 234 = pivot low
    rise = ramp(21, dip[-1] * 1.02, 0.02)
    c = base + dip + rise
    top = c[-1]
    c += [top * 0.99, top * 0.98, top * 0.97, top * trigger]
    vol = np.full(len(c), 1e6)
    vol[234] = 1e7  # heavy anchor volume keeps the AVWAP near the pivot low
    vol[-4:-1] = 5e5  # quiet pullback
    df = closes("AAA", c, vol)
    df.loc[len(c) - 5, "high"] = top * 1.03  # swing-high spike on the top bar
    df.loc[234, "low"] *= 0.99  # strict pivot low (the next bar opens at this close)
    return df


def test_avwap_pullback_shannon():
    s = strat("avwap_pullback_shannon")
    p = panel_for(s, _avwap_bars(0.987))
    sig = fire(s, p, day(p))
    assert sig.features["pullback_bars"] == 3 and sig.features["touches"] <= 2
    assert sig.target == pytest.approx(p["high"].iloc[-5])
    p2 = panel_for(s, _avwap_bars(0.982))  # close does not clear the prior high
    silent(s, p2, day(p2))
    last = p.iloc[-1]
    assert s.should_exit(last, 30) and not s.should_exit(last, 1)


# ----------------------------------------------------------------------------------------------- boomers_cooper
def _boomer_rows(second_inside: bool) -> list[list[float]]:
    rows, c = [], 50.0
    for _ in range(60):
        o, c = c, c * 1.01
        rows.append([o, c * 1.004, o * 0.996, c, 1e6])
    h, lo = rows[-1][1], rows[-1][2]
    rows.append([c, h * 0.999, lo * 1.002, c * 1.001, 1e6])  # inside day 1
    h1, l1 = rows[-1][1], rows[-1][2]
    rows.append([c, h1 * (0.999 if second_inside else 1.003), l1 * 1.001, c * 1.0005, 1e6])
    return rows


def test_boomers_cooper():
    s = strat("boomers_cooper")
    p = panel_for(s, ohlc("AAA", _boomer_rows(True)))
    sig = fire(s, p, day(p))
    last = p.iloc[-1]
    assert sig.entry_type == EntryType.STOP and sig.entry > last["high"] and sig.stop < last["low"]
    assert sig.reward_risk == pytest.approx(2.0)
    p2 = panel_for(s, ohlc("AAA", _boomer_rows(False)))
    silent(s, p2, day(p2))
    assert s.should_exit(last, 5) and not s.should_exit(last, 4)


# ----------------------------------------------------------------------------------------------- cci_correction
def _cci_path(trend: float) -> list[float]:
    c = ramp(160, 50.0, trend)
    last = c[-1]
    c += [last * f for f in (0.97, 0.93, 0.89, 0.87, 0.86)]
    c += ramp(15, c[-1] * 1.012, 0.012)
    return c


def _cci_trigger(p: pd.DataFrame) -> date:
    cci = p["cci_26"].to_numpy()
    k = next(i for i in range(165, len(cci)) if cci[i - 1] <= 0 < cci[i])
    return day(p, k)


def test_cci_correction():
    s = strat("cci_correction")
    p = panel_for(s, closes("AAA", _cci_path(0.006)))
    trig = _cci_trigger(p)
    sig = fire(s, p, trig)
    assert sig.target is None and sig.stop < min(p["low"].iloc[160:166])
    silent(s, p, trig - timedelta(days=1))
    down = panel_for(s, closes("AAA", _cci_path(-0.004)))  # bearish bias: CCI(100) last below -100
    silent(s, down, _cci_trigger(down))
    row = pd.Series({"close": 1.0, "cci_26": 90.0, "prev_cci_26": 120.0})
    assert s.should_exit(row, 1) and not s.should_exit(with_(row, prev_cci_26=95.0), 1)


# ----------------------------------------------------------------------------------------------- connors variants
def test_connors_double_7s_cumulative_and_r3():
    up = ramp(230, 50.0, 0.003)
    c = up + [up[-1] * f for f in (0.995, 0.985, 0.97)]
    p = panel_for(strat("connors_rsi2_variants"), closes("AAA", c))
    t = day(p)
    d7 = strat("connors_rsi2_variants", variant="double_7s")
    sig = fire(d7, p, t)
    assert sig.target is None and sig.entry_type == EntryType.OPEN
    fire(strat("connors_rsi2_variants", variant="cumulative_rsi"), p, t)
    fire(strat("connors_rsi2_variants", variant="r3"), p, t)
    silent(d7, p, day(p, -4))  # still at a 7-day closing high
    down = panel_for(d7, closes("AAA", ramp(230, 80.0, -0.002) + [40.0, 39.5, 39.0]))
    silent(d7, down, day(down))  # below the 200-day SMA
    last = p.iloc[-1]
    assert not d7.should_exit(last, 1) and d7.should_exit(with_(last, close=1e9), 1)


def test_connors_crsi_pullback_limit_entry():
    s = strat("connors_rsi2_variants", variant="crsi_pullback")
    c = ramp(130, 80.0, -0.005)
    rows = [[x / 0.99, x / 0.99 * 1.002, x * 0.998, x, 1e6] for x in c]
    prev = c[-1]
    rows.append([prev, prev * 1.001, prev * 0.93, prev * 0.94, 1e6])  # flush: low -7%, close in the bottom of range
    p = panel_for(s, ohlc("AAA", rows))
    sig = fire(s, p, day(p))
    assert sig.entry_type == EntryType.LIMIT and sig.entry == pytest.approx(prev * 0.94 * 0.96)
    rows[-1] = [prev, prev * 1.001, prev * 0.98, prev * 0.985, 1e6]  # only a 2% dip
    silent(s, panel_for(s, ohlc("AAA", rows)), day(p))
    assert s.should_exit(pd.Series({"close": 1.0, "connors_rsi": 60.0}), 1)


# ----------------------------------------------------------------------------------------------- 80-20
def _eighty_rows(close_back: bool) -> list[list[float]]:
    rows = [[50.0, 50.5, 49.5, 50.0, 1e6] for _ in range(30)]
    rows.append([50.4, 50.5, 48.5, 48.6, 1e6])  # opened top 5%, closed bottom 5% of the range
    rows.append([48.6, 49.2, 47.8, 48.9 if close_back else 48.3, 1e6])  # undercut 48.5 by 0.7, back above?
    return rows


def test_eighty_twenty_reversal():
    s = strat("eighty_twenty_reversal")
    p = panel_for(s, ohlc("AAA", _eighty_rows(True)))
    sig = fire(s, p, day(p))
    assert sig.stop == pytest.approx(47.8 - 0.01) and sig.target is None
    p2 = panel_for(s, ohlc("AAA", _eighty_rows(False)))
    silent(s, p2, day(p2))
    assert s.should_exit(p.iloc[-1], 2) and not s.should_exit(p.iloc[-1], 1)


# ----------------------------------------------------------------------------------------------- gartley
def _gartley_closes(d_level: float) -> list[float]:
    pts = [(0, 120.0), (20, 100.0), (35, 140.0), (45, 115.28), (55, 133.28), (65, d_level)]
    c: list[float] = []
    for (i0, v0), (i1, v1) in zip(pts, pts[1:], strict=False):
        c += list(np.linspace(v0, v1, i1 - i0 + 1))[:-1]
    c.append(d_level)
    c.append(d_level + 1.5)  # bar 66 closes above the D-bar high
    return c


def _gartley_bars(d_level: float) -> pd.DataFrame:
    return doji("AAA", _gartley_closes(d_level), spread=0.002)


def test_harmonic_gartley():
    s = strat("harmonic_gartley")
    p = panel_for(s, _gartley_bars(108.56))
    sig = fire(s, p, day(p))
    f = sig.features
    assert f["xa_retrace"] == pytest.approx(0.786, abs=0.05) and 1.27 <= f["cd_bc"] <= 1.618
    assert sig.target == pytest.approx(f["d"] + 0.618 * (f["a"] - f["x"]))
    shallow = panel_for(s, _gartley_bars(120.0))  # D at 0.5 XA: no Gartley
    silent(s, shallow, day(shallow))
    assert s.should_exit(p.iloc[-1], 20)


# ----------------------------------------------------------------------------------------------- intermarket divergence
def _pair(lag: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(3)
    r = rng.normal(0.0005, 0.01, 160)
    spy = list(100 * np.exp(np.cumsum(r)))
    stock = list(50 * np.exp(np.cumsum(r + rng.normal(0, 0.002, 160))))
    for f in (1.01, 1.01, 1.01, 1.01, 1.01):
        spy.append(spy[-1] * f)
    moves = (0.98, 0.99, 1.0, 1.005, 1.015) if lag else (1.01,) * 5
    for f in moves:
        stock.append(stock[-1] * f)
    return closes("SPY", spy), closes("AAA", stock)


def test_intermarket_divergence_katsanos():
    s = strat("intermarket_divergence_katsanos")
    p = panel_for(s, *_pair(lag=True))
    sig = fire(s, p, day(p))
    assert sig.features["bb_div_max3"] > 20 and sig.features["pair_corr_120"] >= 0.5
    silent(s, p, day(p), "SPY")
    p2 = panel_for(s, *_pair(lag=False))
    silent(s, p2, day(p2))
    row = pd.Series({"close": 10.0, "min_15_of_close": 10.0, "corr_market_20": -0.5})  # 15-day low, pair decoupled
    assert s.should_exit(row, 1) and not s.should_exit(with_(row, corr_market_20=0.5), 1)
    cross = pd.Series({"close": 10.0, "macd": 0.1, "macd_signal": 0.2, "prev_macd": 0.3, "prev_macd_signal": 0.2,
                       "stoch_k_14": 90.0})
    assert s.should_exit(cross, 1) and not s.should_exit(with_(cross, stoch_k_14=50.0), 1)


# ----------------------------------------------------------------------------------------------- keltner
def test_keltner_channel_breakout():
    s = strat("keltner_channel_breakout")
    c = [x * (1 + 0.01 * (-1) ** i) for i, x in enumerate(ramp(240, 50.0, 0.002))]
    c.append(c[-1] * 1.05)
    p = panel_for(s, closes("AAA", c))
    sig = fire(s, p, day(p))
    last = p.iloc[-1]
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(last["high"] + 0.01)
    assert sig.stop == pytest.approx(max(last["kc_mid_20"], last["low"] - 0.01))
    flat = panel_for(s, closes("AAA", c[:-1] + [c[-2] * 1.005]))
    silent(s, flat, day(flat))
    assert s.should_exit(with_(last, close=1.0), 1)


# ----------------------------------------------------------------------------------------------- moving momentum
def _mm_panel(s, trend: float):
    c = ramp(200, 50.0, trend)
    last = c[-1]
    c += [last * f for f in (0.985, 0.97, 0.955, 0.945, 0.94)]
    c += ramp(15, c[-1] * 1.008, 0.008)
    return panel_for(s, closes("AAA", c))


def _hist_turn(p: pd.DataFrame) -> date:
    h = p["macd_hist"].to_numpy()
    return day(p, next(i for i in range(201, len(h)) if h[i - 1] <= 0 < h[i]))


def test_moving_momentum_hill():
    s = strat("moving_momentum_hill")
    p = _mm_panel(s, 0.004)
    t = _hist_turn(p)
    sig = fire(s, p, t)
    assert sig.reward_risk >= 1.5 and sig.features["setup_age"] <= 10
    silent(s, p, t - timedelta(days=1))
    down = _mm_panel(s, -0.003)  # SMA20 < SMA150
    silent(s, down, _hist_turn(down))
    row = pd.Series({"close": 1.0, "sma_20": 1.0, "sma_150": 2.0})
    assert s.should_exit(row, 1)


# ----------------------------------------------------------------------------------------------- pivot reversal
def _pivot_closes(broken: bool) -> list[float]:
    c = ramp(220, 40.0, 0.003)
    top = c[-1] * 1.03
    c += [top, top * 0.99, top * 0.98, top * 0.97, top * 0.96, top * 0.955, top * 0.965, top * 0.975, top * 0.98,
          top * 0.985, top * (1.02 if broken else 0.99)]
    return c


def test_pivot_reversal_breakout():
    s = strat("pivot_reversal_breakout")
    p = panel_for(s, doji("AAA", _pivot_closes(False)))
    sig = fire(s, p, day(p))
    pivot_high = p["high"].iloc[220]
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(pivot_high + 0.01)
    assert sig.stop == pytest.approx(p["low"].iloc[225] - 0.01)
    assert s.trail_stop(p.iloc[-1]) == pytest.approx(p["low"].iloc[225] - 0.01)
    broken = panel_for(s, doji("AAA", _pivot_closes(True)))
    silent(s, broken, day(broken))


# ----------------------------------------------------------------------------------------------- stochastic pop
def _pop_closes(pop: float) -> list[float]:
    c = [100 + 2 * np.sin(i / 3) for i in range(200)]
    c += list(np.linspace(100, 90, 15)) + list(np.linspace(90, 100, 15))
    c += [100 + np.sin(2 * np.pi * (i - 41) / 10 - np.pi / 2) for i in range(42)]  # ends at a trough
    c.append(pop)
    return c


def test_stochastic_pop_and_drop():
    s = strat("stochastic_pop_and_drop")
    c = _pop_closes(102.5)
    vol = np.full(len(c), 1e6)
    vol[-1] = 3e6
    p = panel_for(s, closes("AAA", c, vol))
    last = p.iloc[-1]
    assert last["adx_14"] < 20 and last["prev_stoch_k_14"] < 50
    sig = fire(s, p, day(p))
    assert sig.target is None and sig.entry - sig.stop <= 3 * last["atr_14"] + 1e-9
    quiet = panel_for(s, closes("AAA", c))  # same pop on average volume
    silent(s, quiet, day(quiet))
    assert s.should_exit(with_(last, stoch_k_14=40.0), 1)


# ----------------------------------------------------------------------------------------------- ttm squeeze
def _squeeze_rows(jump: float) -> list[list[float]]:
    rows = [[100.0, 100.5, 99.5, 100.0 + 0.05 * ((-1) ** i), 1e6] for i in range(60)]
    rows.append([100.0, 100.0 + jump + 0.3, 99.8, 100.0 + jump, 2e6])
    return rows


def test_ttm_squeeze():
    s = strat("ttm_squeeze")
    p = panel_for(s, ohlc("AAA", _squeeze_rows(5.0)))
    prev = p.iloc[-2]
    assert prev["bb_upper_20"] < prev["kc_upper_20"] and prev["bb_lower_20"] > prev["kc_lower_20"]
    sig = fire(s, p, day(p))
    assert sig.target is None
    still = panel_for(s, ohlc("AAA", _squeeze_rows(0.3)))
    silent(s, still, day(still))
    row = pd.Series({"close": 1.0, "sqz_mom_20": 1.0, "prev_sqz_mom_20": 2.0, "prev_prev_sqz_mom_20": 3.0})
    assert s.should_exit(row, 1)
    assert not s.should_exit(with_(row, sqz_mom_20=2.5), 1)


# ----------------------------------------------------------------------------------------------- wyckoff
def _wyckoff_rows(test_volume: float) -> list[list[float]]:
    rows = []
    for x in ramp(140, 150.0, -0.0025):  # ~ -30% decline
        rows.append([x * 1.002, x * 1.006, x * 0.996, x, 1e6])
    box = [107.5 + 6 * np.sin(2 * np.pi * i / 20) for i in range(60)]  # TR ~ 101-114
    for x in box:
        rows.append([x, x + 0.5, x - 0.5, x, 1e6])
    rows.append([101.5, 101.8, 99.0, 101.2, 1.5e6])  # spring: under the TR low, closes back inside
    rows.append([101.2, 102.5, 100.8, 102.0, 1.5e6])  # rally off the spring on volume (not a test)
    rows.append([102.0, 102.3, 100.5, 101.0, 1e6])
    rows.append([101.0, 102.0, 99.6, 101.8, test_volume])  # test of the spring low on low volume
    return rows


def test_wyckoff_spring_test():
    s = strat("wyckoff_spring_accumulation")
    p = panel_for(s, ohlc("AAA", _wyckoff_rows(4e5)))
    sig = fire(s, p, day(p))
    assert sig.features["lps"] == 0.0 and sig.reward_risk >= 3.0
    assert sig.stop < 99.0
    loud = panel_for(s, ohlc("AAA", _wyckoff_rows(3e6)))
    silent(s, loud, day(loud))
    last = p.iloc[-1]
    assert not s.should_exit(with_(last, close=0.01), 5)
    assert s.should_exit(with_(last, close=0.01), 10)


def test_wyckoff_lps():
    s = strat("wyckoff_spring_accumulation", entries=["lps"])
    rows = _wyckoff_rows(4e5)[:-4]
    rows.append([113.0, 117.5, 112.8, 117.0, 3e6])  # SOS: close over the TR high (~114) on 3x volume
    rows.append([117.0, 117.4, 115.5, 116.0, 8e5])  # pullback, low still above the TR high
    p = panel_for(s, ohlc("AAA", rows))
    sig = fire(s, p, day(p))
    assert sig.features["lps"] == 1.0
    rows[-1] = [117.0, 117.4, 115.5, 116.0, 2e6]  # heavy-volume pullback
    silent(s, panel_for(s, ohlc("AAA", rows)), day(p))


# ----------------------------------------------------------------------------------------------- elder
def _elder_closes(accel: float) -> list[float]:
    rate = 0.001 + accel * np.arange(250)
    c = list(50 * np.cumprod(1 + rate))
    while pd.bdate_range("2023-01-02", periods=len(c))[-1].weekday() != 4:
        c.append(c[-1] * (1 + rate[-1]))
    c += [c[-1] * 0.985, c[-1] * 0.975]  # Monday / Tuesday dip
    return c


def test_elder_triple_screen():
    s = strat("elder_triple_screen")
    p = panel_for(s, closes("AAA", _elder_closes(0.00002)))
    last = p.iloc[-1]
    assert last["wk_macd_hist"] > last["wk_macd_hist_prev"] and last["force_2"] < 0
    sig = fire(s, p, day(p))
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(last["high"] + 0.01)
    assert sig.stop < min(p["low"].iloc[-2:])
    slow = panel_for(s, closes("AAA", _elder_closes(-0.000004)))  # decelerating: weekly histogram falling
    silent(s, slow, day(slow))
    assert s.should_exit(with_(last, wk_macd_hist=last["wk_macd_hist_prev"]), 1)


# ----------------------------------------------------------------------------------------------- katsanos meters
def _katsanos_closes() -> list[float]:
    c = ramp(60, 60.0, -0.004)
    c += ramp(20, c[-1] * 1.0, 0.006)
    return c


def _cross_day(p: pd.DataFrame) -> date:
    c, m = p["close"].to_numpy(), p["sma_20"].to_numpy()
    return day(p, next(i for i in range(21, len(c)) if c[i - 1] <= m[i - 1] and c[i] > m[i]))


@pytest.mark.parametrize("meter", ["er", "vhf"])
def test_katsanos_trend_strength_filters(meter):
    s = strat("katsanos_trend_strength_filters", meter=meter)
    p = panel_for(s, closes("AAA", _katsanos_closes()))
    t = _cross_day(p)
    sig = fire(s, p, t)
    assert sig.target is None
    silent(s, p, t + timedelta(days=1))  # no new cross
    held = row_at(p, "AAA", t).copy()
    held["close"] = held["sma_20"] - 0.01
    assert s.should_exit(held, 1) and not s.should_exit(row_at(p, "AAA", t), 1)


def test_katsanos_gate_blocks_without_trend():
    s = strat("katsanos_trend_strength_filters", meter="er", er_crit=0.99, er_trend=0.99)
    p = panel_for(s, closes("AAA", _katsanos_closes()))
    silent(s, p, _cross_day(p))


def test_katsanos_adx_and_r2_gates():
    row = pd.Series({"close": 100.0, "plus_di_14": 30.0, "minus_di_14": 10.0, "linreg_slope_20": 0.5})
    adx = strat("katsanos_trend_strength_filters", meter="adx")
    strong = np.array([30.0] * 10 + [35.0])  # 25 < ADX < 50
    assert adx.gate(strong, row)
    assert not adx.gate(strong, with_(row, plus_di_14=5.0))  # -DI above +DI
    assert not adx.gate(np.array([60.0] * 11), row)  # above max and not developing
    assert adx.gate(np.array([60.0] * 9 + [15.0, 21.0]), row)  # developing: > 20 and > 1.1 x the prior low
    r2 = strat("katsanos_trend_strength_filters", meter="r2")
    assert r2.gate(np.array([0.3] * 10 + [0.5]), row)
    assert not r2.gate(np.array([0.3] * 10 + [0.5]), with_(row, linreg_slope_20=-0.5))  # falling regression line
    assert not r2.gate(np.array([0.6] * 10 + [0.5]), row)  # R2 not rising


# ----------------------------------------------------------------------------------------------- pe proxy
def test_pe_valuation_reversion():
    s = strat("pe_valuation_reversion")
    c = [100.0] * 30 + [92.0, 85.0]
    p = panel_for(s, closes("AAA", c))
    sig = fire(s, p, day(p))
    assert sig.target is None
    p2 = panel_for(s, closes("AAA", [100.0] * 30 + [97.0, 95.0]))
    silent(s, p2, day(p2))
    assert s.should_exit(pd.Series({"close": 100.0, "sma_12": 99.0}), 1)
