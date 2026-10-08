"""features.extra: on-demand feature registry (hand-checked values, name parser, idempotence, causality)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import extra as ex
from swing_engine.features.indicators import ema, rsi
from swing_engine.features.panel import build_panel
from tests.features_gbm import gbm_bars

NY = "America/New_York"


def _bars(highs, lows, closes, opens=None, symbol="AAA", start="2024-01-02", volume=1e6) -> pd.DataFrame:
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({
        "symbol": symbol,
        "ts": pd.bdate_range(start, periods=len(c), tz=NY),
        "open": np.asarray(opens if opens is not None else closes, dtype=float),
        "high": np.asarray(highs, dtype=float),
        "low": np.asarray(lows, dtype=float),
        "close": c,
        "volume": float(volume),
    })


def _col(frame: pd.DataFrame, name: str) -> list[float]:
    return frame[name].tolist()


def _close(actual, expected) -> None:
    np.testing.assert_allclose(np.asarray(actual, dtype=float), np.asarray(expected, dtype=float), rtol=1e-9,
                               atol=1e-12, equal_nan=True)


# ----------------------------------------------------------------------------------------------- hand-checked values
def test_psar_hand_checked():
    bars = _bars(highs=[10, 11, 12, 11.5, 10], lows=[9, 10, 11, 8, 7.5], closes=[9.5, 10.5, 11.5, 9, 8])
    out = ex.ensure_extra(bars, ["psar", "psar_dir", "psar_af"])
    # t1: ep 11, af .04, 9 + .04*2 = 9.08 clamped to min(low1, low0) = 9; t2: 9 + .06*3 = 9.18;
    # t3: low 8 < 9.18 reverses to short at the prior EP 12; 12 + .02*(8-12) = 11.92 -> max(high3, high2) = 12;
    # t4: new EP 7.5, af .04: 12 + .04*(7.5-12) = 11.82
    _close(_col(out, "psar"), [np.nan, 9.0, 9.18, 12.0, 11.82])
    _close(_col(out, "psar_dir"), [np.nan, 1, 1, -1, -1])
    _close(_col(out, "psar_af"), [np.nan, 0.04, 0.06, 0.02, 0.04])


def test_supertrend_hand_checked():
    bars = _bars(highs=[11, 12, 14, 13, 11], lows=[9, 10, 12, 11, 9], closes=[10, 11, 13.5, 11.2, 9.5])
    out = ex.ensure_extra(bars, ["st_line_2_1", "st_dir_2_1", "atr_2"])
    # Wilder ATR(2): 2, 2, 2.5, 2.5, 2.35; bands hl2 +/- 1 x ATR
    _close(_col(out, "atr_2"), [np.nan, 2.0, 2.5, 2.5, 2.35])
    # t1 start down (line = upper 13); t2 close 13.5 > upper 13 -> up, line = lower 10.5; t3 lower holds 10.5;
    # t4 upper resets to 10 + 2.35 = 12.35 (prior close was above the old upper), close 9.5 < 10.5 -> down
    _close(_col(out, "st_line_2_1"), [np.nan, 13.0, 10.5, 10.5, 12.35])
    _close(_col(out, "st_dir_2_1"), [np.nan, -1, 1, 1, -1])


def test_kama_and_efficiency_ratio_hand_checked():
    closes = [10, 11, 12, 11, 13]
    out = ex.ensure_extra(_bars(closes, closes, closes), ["er_2", "kama_2"])
    _close(_col(out, "er_2"), [np.nan, np.nan, 1.0, 0.0, 1 / 3])
    fast, slow = 2 / 3, 2 / 31
    k1 = 10.5  # SMA seed
    k2 = k1 + fast**2 * (12 - k1)
    k3 = k2 + slow**2 * (11 - k2)
    k4 = k3 + ((1 / 3) * (fast - slow) + slow) ** 2 * (13 - k3)
    _close(_col(out, "kama_2"), [np.nan, k1, k2, k3, k4])


def test_streak_and_connors_rsi_against_components():
    closes = [10, 11, 12, 12, 11, 10, 11]
    out = ex.ensure_extra(_bars(closes, closes, closes), ["streak", "up_streak", "down_streak"])
    _close(_col(out, "streak"), [np.nan, 1, 2, 0, -1, -2, 1])
    _close(_col(out, "up_streak"), [np.nan, 1, 2, 0, 0, 0, 1])
    _close(_col(out, "down_streak"), [np.nan, 0, 0, 0, 1, 2, 0])

    rng = np.random.default_rng(5)
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 140))))
    out = ex.ensure_extra(_bars(c, c, c), ["connors_rsi"])
    streak = [np.nan]
    for i in range(1, len(c)):
        s = streak[-1] if i > 1 else 0
        d = c[i] - c[i - 1]
        streak.append((s + 1 if s > 0 else 1) if d > 0 else (s - 1 if s < 0 else -1) if d < 0 else 0)
    ret = c.pct_change()
    t = len(c) - 1
    pct_rank = 100 * sum(ret[t - k] < ret[t] for k in range(1, 101)) / 100
    expected = (rsi(c, 3).iloc[t] + rsi(pd.Series(streak), 2).iloc[t] + pct_rank) / 3
    assert out["connors_rsi"].iloc[t] == pytest.approx(expected, rel=1e-12)
    assert out["connors_rsi"].iloc[:100].isna().all()


def test_nr7_and_id_nr4():
    ranges = [5, 4, 6, 3, 7, 4, 2, 2.5]
    highs = [100 + r / 2 for r in ranges]
    lows = [100 - r / 2 for r in ranges]
    out = ex.ensure_extra(_bars(highs, lows, [100] * 8), ["nr7", "nr4", "id_nr4"])
    _close(_col(out, "nr7"), [np.nan] * 6 + [1.0, 0.0])
    # nr4 at t6: 2 < min(3, 7, 4); t7: 2.5 is not below 2. inside day t6: range 2 inside the prior range 4
    _close(_col(out, "nr4"), [np.nan] * 3 + [1.0, 0.0, 0.0, 1.0, 0.0])
    _close(_col(out, "id_nr4"), [np.nan] * 3 + [1.0, 0.0, 0.0, 1.0, 0.0])


def test_mansfield_rs_from_market_frame_and_panel_spy():
    n = 260
    c = 100.0 + np.arange(n)
    stock = _bars(c, c, c)
    spy = stock.assign(symbol="SPY", open=100.0, high=100.0, low=100.0, close=100.0)
    rs_last = (100 + n - 1) / 100
    mean_rs = 1 + np.arange(n - 252, n).mean() / 100
    expected = 100 * (rs_last / mean_rs - 1)
    via_market = ex.ensure_extra(stock, ["mansfield_rs", "rs_line"], market=spy)
    assert via_market["mansfield_rs"].iloc[-1] == pytest.approx(expected)
    assert via_market["mansfield_rs"].iloc[:250].isna().all()
    via_panel = ex.ensure_extra(pd.concat([stock, spy], ignore_index=True), ["mansfield_rs"])
    assert via_panel.loc[via_panel["symbol"] == "AAA", "mansfield_rs"].iloc[-1] == pytest.approx(expected)
    no_market = ex.ensure_extra(stock, ["mansfield_rs"])
    assert no_market["mansfield_rs"].isna().all()


def test_calendar_flags_from_nyse_calendar():
    days = pd.bdate_range("2024-01-02", "2025-01-10", tz=NY)
    bars = _bars([1.0] * len(days), [1.0] * len(days), [1.0] * len(days))
    out = ex.ensure_extra(bars, ["tom_day", "tom_window", "pre_holiday_1", "pre_holiday_2", "santa_window",
                                 "day_of_week"]).set_index(days.date)
    get = lambda col, d: out.loc[pd.Timestamp(d).date(), col]  # noqa: E731
    assert [get("tom_day", d) for d in ("2024-01-29", "2024-01-30", "2024-01-31", "2024-02-01", "2024-02-07")] == [
        -3, -2, -1, 1, 5]
    assert np.isnan(get("tom_day", "2024-02-08"))  # sixth session of February
    assert get("tom_window", "2024-01-31") == 1 and get("tom_window", "2024-01-30") == 0
    assert get("pre_holiday_1", "2024-07-03") == 1  # July 4 (Thursday) closed
    assert get("pre_holiday_2", "2024-07-02") == 1
    assert get("pre_holiday_1", "2024-07-05") == 0  # an ordinary weekend is not a holiday
    assert get("pre_holiday_1", "2024-12-24") == 1
    assert np.isnan(get("tom_day", "2024-07-04"))  # not a session: no calendar value
    assert get("santa_window", "2024-12-24") == 1 and get("santa_window", "2024-12-23") == 0
    assert get("santa_window", "2025-01-03") == 1 and get("santa_window", "2025-01-06") == 0
    assert get("day_of_week", "2024-07-05") == 4


def test_gap_momentum_hand_checked():
    closes = [10.0] * 6
    opens = [10, 11, 9.5, 10.5, 10, 9]
    highs = [max(o, c) for o, c in zip(opens, closes, strict=True)]
    lows = [min(o, c) for o, c in zip(opens, closes, strict=True)]
    out = ex.ensure_extra(_bars(highs, lows, closes, opens), ["gapm_ratio_3_2", "gapm_signal_3_2", "gapm_slope_3_2"])
    _close(_col(out, "gapm_ratio_3_2"), [np.nan, np.nan, np.nan, 300.0, 100.0, 50.0])
    _close(_col(out, "gapm_signal_3_2"), [np.nan] * 4 + [200.0, 75.0])
    _close(_col(out, "gapm_slope_3_2"), [np.nan] * 5 + [-1.0])
    only_up = ex.ensure_extra(_bars([10.5] * 5, [10] * 5, [10] * 5, [10, 10.5, 10.5, 10.5, 10.5]), ["gapm_ratio_3_2"])
    assert only_up["gapm_ratio_3_2"].iloc[-1] == 1.0  # no down gaps: 1 (published code)
    assert ex.is_extra("gapm_slope")  # defaults 40 / 20


# ----------------------------------------------------------------------------------------------- name parser
@pytest.mark.parametrize("name", [
    "ema_8", "sma_5", "wma_10", "hma_16", "sma_30_of_obv", "ema_3_of_force_2", "prev_ema_8", "ema_8_rank",
    "mom_12_1_rank", "prev_close", "st_dir", "st_line_10_2.5", "gapm_slope", "dc_low_10", "stoch_d_14_3_3",
    "adx_10", "plus_di_7", "nr7", "tom_day", "connors_rsi",
])
def test_name_parser_accepts(name):
    assert ex.is_extra(name)


@pytest.mark.parametrize("name", ["foo", "sma_x", "ema_8w", "prev_nope", "nope_rank", "sma_10_of_nope", "stoch_d_14"])
def test_name_parser_rejects(name):
    assert not ex.is_extra(name)


def test_parsed_moving_averages_match_reference():
    panel = build_panel(gbm_bars(["AAA", "BBB"], n_bars=60, seed=2))
    out = ex.ensure_extra(panel, ["ema_8", "sma_5", "prev_ema_8"])
    for _, g in out.groupby("symbol"):
        _close(g["ema_8"], ema(g["close"], 8))
        _close(g["sma_5"], g["close"].rolling(5).mean())
        _close(g["prev_ema_8"], g["ema_8"].shift(1))


def test_unknown_name_raises():
    with pytest.raises(KeyError, match="nope"):
        ex.ensure_extra(build_panel(gbm_bars(["AAA"], n_bars=30)), ["nope"])


# ----------------------------------------------------------------------------------------------- ensure_extra contract
def test_ensure_extra_idempotent_and_order_preserving():
    panel = build_panel(gbm_bars(["AAA", "BBB", "SPY"], n_bars=80, seed=4))
    names = ["rsi_3", "psar", "mansfield_rs", "atr_14"]  # atr_14 is already a panel column
    out = ex.ensure_extra(panel, names)
    assert list(out.columns[: len(panel.columns)]) == list(panel.columns)
    assert ex.ensure_extra(out, names) is out
    shuffled = panel.sample(frac=1.0, random_state=0)
    out_s = ex.ensure_extra(shuffled, names)
    assert list(out_s.index) == list(shuffled.index)
    _close(out_s.loc[out.index, ["rsi_3", "psar"]].to_numpy(), out[["rsi_3", "psar"]].to_numpy())


def test_required_extras_collects_in_order():
    class A:
        extra_features = ["ema_8", "psar"]

    class B:
        extra_features = ["psar", "tom_day"]

    assert ex.required_extras([A, B(), object()]) == ["ema_8", "psar", "tom_day"]
    assert all(ex.is_extra(n) for n in ex.required_extras())  # every registered strategy resolves


# ----------------------------------------------------------------------------------------------- causality
ALL_NAMES = [*ex.EXTRA_FEATURES, *(example for _rx, _fn, example, _inner in ex.EXTRA_PATTERNS)]


@pytest.fixture(scope="module")
def full_and_cut():
    bars = gbm_bars(["AAA", "BBB", "CCC", "SPY"], n_bars=320, seed=9)
    cutoff = bars["ts"].sort_values().unique()[289]
    full = ex.ensure_extra(build_panel(bars), ALL_NAMES)
    cut = ex.ensure_extra(build_panel(bars.loc[bars["ts"] <= cutoff]), ALL_NAMES)
    return full.loc[full["ts"] <= cutoff].reset_index(drop=True), cut


@pytest.mark.parametrize("name", ALL_NAMES)
def test_future_bars_do_not_change_past_values(name, full_and_cut):
    full, cut = full_and_cut
    assert cut[name].notna().any(), f"{name} never warms up in 290 bars"
    _close(full[name], cut[name])
