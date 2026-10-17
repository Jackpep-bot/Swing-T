"""features.market_school (IBD M rule reconstruction) and the playbook's risk-reducing overlays."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.config import PlaybookConfig, PlaybookOverlay, Settings
from swing_engine.features.market_school import CONFIRMED, CORRECTION, UNDER_PRESSURE, market_school
from swing_engine.strategies import playbook as pb

BASE_VOL = 1_000_000.0
UP_VOL = 2_000_000.0
DECLINE = [(-0.01, BASE_VOL)] * 10  # equal volume: no distribution days on the way down


def _index(steps: list[tuple[float, float]], s0: float = 100.0) -> pd.DataFrame:
    """Index bars from (return, volume) steps after a flat first bar; high / low = close +- 0.5%."""
    rets = np.array([0.0, *[r for r, _ in steps]])
    close = s0 * np.cumprod(1.0 + rets)
    vol = np.array([BASE_VOL, *[v for _, v in steps]])
    ts = pd.bdate_range("2026-01-02", periods=len(close), tz="America/New_York")
    return pd.DataFrame(
        {"symbol": "SPY", "ts": ts, "open": close, "high": close * 1.005, "low": close * 0.995,
         "close": close, "volume": vol}
    )


def _ftd_path() -> list[tuple[float, float]]:
    # day 1 +0.5%, day 2 +0.3%, day 3 +2% on higher volume (too early), day 4 +1.5% on higher volume = FTD
    return [*DECLINE, (0.005, BASE_VOL), (0.003, BASE_VOL), (0.02, UP_VOL), (0.015, 3 * UP_VOL)]


def test_ftd_on_day_4_not_day_3() -> None:
    ms = market_school(_index(_ftd_path()))
    assert (ms["ms_state"].iloc[:-1] == CORRECTION).all()
    assert ms["ms_rally_day"].iloc[-4:-1].tolist() == [1, 2, 3]
    assert ms["ms_ftd"].iloc[-2] == 0  # +2% on higher volume, but only day 3
    assert ms["ms_ftd"].iloc[-1] == 1 and ms["ms_state"].iloc[-1] == CONFIRMED


def test_ftd_needs_higher_volume_and_the_gain() -> None:
    low_vol = [*_ftd_path()[:-1], (0.015, UP_VOL * 0.5)]
    small = [*_ftd_path()[:-1], (0.01, 3 * UP_VOL)]
    assert market_school(_index(low_vol))["ms_ftd"].sum() == 0
    assert market_school(_index(small))["ms_ftd"].sum() == 0
    assert market_school(_index(small), ftd_min_gain=0.01)["ms_ftd"].sum() == 1


def test_failed_rally_restarts_the_count() -> None:
    steps = [*DECLINE, (0.005, BASE_VOL), (0.005, BASE_VOL), (-0.03, BASE_VOL),  # day 3 undercuts the low
             (0.015, UP_VOL),                                                     # old day 4, new day 1
             (0.002, UP_VOL * 0.5), (0.002, UP_VOL * 0.5), (0.015, UP_VOL)]       # new day 4 = FTD
    ms = market_school(_index(steps))
    assert ms["ms_rally_day"].iloc[-7:].tolist() == [1, 2, 0, 1, 2, 3, 0]
    assert ms["ms_ftd"].iloc[-4] == 0
    assert ms["ms_ftd"].iloc[-1] == 1 and ms["ms_state"].iloc[-1] == CONFIRMED


def _after_ftd(*steps: tuple[float, float]) -> pd.DataFrame:
    return _index([*_ftd_path(), *steps])


def test_distribution_count_pressure_and_correction() -> None:
    dd_cycle = [(-0.003, UP_VOL * 4), (0.003, BASE_VOL)]  # a DD then a quiet up day on lower volume
    ms = market_school(_after_ftd(*dd_cycle * 7))
    dd_rows = ms.iloc[-14::2]
    assert dd_rows["ms_dd"].tolist() == [1] * 7
    assert dd_rows["ms_dd_count"].tolist() == [1, 2, 3, 4, 5, 6, 7]
    assert dd_rows["ms_state"].tolist() == [CONFIRMED] * 4 + [UNDER_PRESSURE] * 2 + [CORRECTION]
    # -0.1% is not a distribution day, nor is -0.3% on lower volume
    quiet = market_school(_after_ftd((-0.001, UP_VOL * 9), (-0.003, BASE_VOL)))
    assert quiet["ms_dd"].iloc[-2:].tolist() == [0, 0]


def test_distribution_days_expire_after_25_sessions() -> None:
    ms = market_school(_after_ftd((-0.003, UP_VOL * 9), *[(0.0, BASE_VOL)] * 26))
    count = ms["ms_dd_count"].iloc[-27:].tolist()
    assert count[:25] == [1] * 25 and count[25:] == [0, 0]


def test_distribution_days_expire_on_a_6pct_rally() -> None:
    ms = market_school(_after_ftd((-0.003, UP_VOL * 9), (0.03, BASE_VOL), (0.025, BASE_VOL)))
    assert ms["ms_dd_count"].iloc[-3:].tolist() == [1, 1, 0]  # high 0.5% above a +5.6% close
    assert market_school(_after_ftd((-0.003, UP_VOL * 9), (0.03, BASE_VOL)), dd_expiry_rally=0.03)[
        "ms_dd_count"
    ].iloc[-1] == 0


def test_close_below_ftd_low_is_a_correction() -> None:
    ms = market_school(_after_ftd((-0.02, BASE_VOL)))
    assert ms["ms_state"].iloc[-1] == CORRECTION


def test_point_in_time() -> None:
    bars = _after_ftd(*[(-0.003, UP_VOL * 2), (0.003, BASE_VOL)] * 5)
    full = market_school(bars)
    for cut in (5, 12, 15, 20, len(bars)):
        pd.testing.assert_frame_equal(market_school(bars.iloc[:cut]), full.iloc[:cut])


# ------------------------------------------------------------------------------------------------ playbook overlays
STRATS = ("pullback_trend", "rsi2_meanrev", "insider_cluster")


def _settings(**overlays: PlaybookOverlay) -> Settings:
    pbc = PlaybookConfig(overlays={**PlaybookConfig().overlays, **overlays})
    return Settings(strategies={n: {"enabled": True} for n in STRATS}, playbook=pbc)


def _panel() -> pd.DataFrame:
    """SPY that never had an FTD (Market School: correction) plus a falling universe."""
    spy = _index(DECLINE * 3)
    stocks = [spy.assign(symbol=f"S{i:02d}", close=spy["close"] * (1 + i / 100)) for i in range(25)]
    return pd.concat([spy, *stocks], ignore_index=True)


def test_overlays_default_off_changes_nothing() -> None:
    panel, day = _panel(), date(2026, 3, 1)
    state = pb.market_state(panel, day, settings=_settings())
    assert state.overlays == []
    assert all(not o.enabled for o in PlaybookConfig().overlays.values())
    bare = Settings(strategies={n: {"enabled": True} for n in STRATS}, playbook=PlaybookConfig(overlays={}))
    assert pb.market_state(panel, day, settings=bare).model_dump() == state.model_dump()
    assert pb.select_strategies(state, _settings()) == pb.select_strategies(state, bare)


def test_market_school_overlay_blocks_in_a_correction() -> None:
    s = _settings(market_school_correction=PlaybookOverlay(enabled=True, multiplier=0.0),
                  market_school_pressure=PlaybookOverlay(enabled=True, multiplier=0.5))
    state = pb.market_state(_panel(), date(2026, 3, 1), settings=s)
    assert state.overlays == ["market_school_correction"]
    assert state.inputs["ms_state"] == -1.0
    assert pb.select_strategies(state, s) == {}


@pytest.mark.parametrize("regime", ["healthy_uptrend", "narrow_uptrend", "choppy", "high_vol_selloff"])
def test_overlays_only_reduce(regime: str) -> None:
    base = _settings()
    on = _settings(
        q25_bearish=PlaybookOverlay(enabled=True, multiplier=0.5),
        mcclellan_negative=PlaybookOverlay(enabled=True, multiplier=1.0, strategies=["rsi2_meanrev"]),
        hill_bearish=PlaybookOverlay(enabled=True, multiplier=0.0, strategies=["insider_cluster"]),
    )
    state = pb.MarketState(as_of=date(2026, 3, 1), regime=regime,
                           overlays=["q25_bearish", "mcclellan_negative", "hill_bearish"])
    before, after = pb.select_strategies(state, base), pb.select_strategies(state, on)
    assert set(after) <= set(before)
    assert all(after[n] <= before[n] for n in after)
    assert "insider_cluster" not in after
    if "rsi2_meanrev" in before:
        assert after["rsi2_meanrev"] == pytest.approx(before["rsi2_meanrev"] * 0.5)


def test_breadth_overlays_fire_on_their_thresholds() -> None:
    cfg = _settings(**{n: PlaybookOverlay(enabled=True) for n in pb.OVERLAYS}).playbook
    bear = pd.Series({"ad_pct_ema10": -35.0, "hl_pct": -12.0, "pct_above_200": 30.0,
                      "mcclellan_osc": -5.0, "q25_ratio": 0.5})
    fired, _, inputs = pb.fired_overlays(pd.DataFrame(), date(2026, 3, 1), bear, False, cfg)
    assert fired == ["hill_bearish", "mcclellan_negative", "q25_bearish"]
    assert inputs["hill_bearish_votes"] == 3.0
    one_vote = bear.copy()
    one_vote[["ad_pct_ema10", "mcclellan_osc", "q25_ratio"]] = [0.0, 1.0, np.nan]  # NaN never fires
    fired, _, _ = pb.fired_overlays(pd.DataFrame(), date(2026, 3, 1), one_vote, True, cfg)
    assert fired == []


def test_unknown_overlay_name_fails_closed() -> None:
    cfg = PlaybookConfig(overlays={"zweig_thrust": PlaybookOverlay(enabled=True)})
    with pytest.raises(ValueError, match="unknown overlay"):
        pb.fired_overlays(pd.DataFrame(), date(2026, 3, 1), None, None, cfg)
