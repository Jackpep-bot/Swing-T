"""strategies.playbook: market regime classification and the regime -> strategy router."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from swing_engine.core import registry
from swing_engine.core.config import (
    PLAYBOOK_REGIMES,
    PlaybookConfig,
    Settings,
    default_playbook_table,
)
from swing_engine.features.breadth import BREADTH_COLUMNS, market_breadth
from swing_engine.features.panel import build_panel
from swing_engine.strategies import playbook as pb

ROOT = Path(__file__).resolve().parents[1]
NY = "America/New_York"
N_BARS = 320
OCT_6_2026 = date(2026, 10, 6)
DATES = pd.bdate_range(end=OCT_6_2026.isoformat(), periods=N_BARS, tz=NY)
ALL_STRATEGIES = (
    "breakout_52w",
    "sr_breakout",
    "momentum_burst",
    "pullback_trend",
    "sr_bounce",
    "rsi2_meanrev",
    "insider_cluster",
)
BREAKOUT_FAMILY = ("breakout_52w", "sr_breakout", "momentum_burst")
N_STOCKS = 40


def _alt(n: int, amp: float) -> np.ndarray:
    return amp * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)


def _returns(*parts: tuple[int, float, float]) -> np.ndarray:
    """Concatenated (bars, drift per bar, alternating amplitude) segments: deterministic, controllable vol."""
    return np.concatenate([np.full(n, drift) + _alt(n, amp) for n, drift, amp in parts])


def _bars(symbol: str, rets: np.ndarray, s0: float, volume: float = 1_000_000.0) -> pd.DataFrame:
    c = s0 * np.exp(np.cumsum(rets))
    o = np.concatenate([[s0], c[:-1]])
    return pd.DataFrame(
        {
            "symbol": symbol,
            "ts": DATES[-len(c) :],
            "open": o,
            "high": np.maximum(o, c) * 1.002,
            "low": np.minimum(o, c) * 0.998,
            "close": c,
            "volume": volume,
        }
    )


SPY_PATHS: dict[str, np.ndarray] = {
    # steady advance, last close within 1% of the 52-week high (Oct 6 2026: index at a record)
    "bull": _returns((N_BARS, 0.0008, 0.006)),
    # downtrend: close < sma_50 < sma_200, sma_50 falling, calm into the as-of date
    "downtrend": _returns((N_BARS - 40, -0.0008, 0.012), (40, -0.0008, 0.002)),
    # quick, low-volatility slide below the 200-day while sma_50 is still above sma_200 (trend "mixed")
    "below_200": _returns((300, 0.001, 0.003), (20, -0.012, 0.001)),
    # violent drop below the 50-day on the highest realized vol of the year
    "selloff": _returns((290, 0.0008, 0.004), (30, -0.004, 0.03)),
    # above the 200-day, dipped under a flattening 50-day, quiet
    "chop": _returns((280, 0.001, 0.004), (40, -0.001, 0.002)),
}


def _stocks(n_above_50: int, n_above_200: int) -> list[pd.DataFrame]:
    """N_STOCKS names: ``n_above_50`` leaders above both MAs, then names below the 50-day but above the
    200-day up to ``n_above_200``, the rest below both."""
    out = []
    for i in range(N_STOCKS):
        if i < n_above_50:
            rets = _returns((N_BARS, 0.001, 0.004))
        elif i < n_above_200:
            rets = _returns((295, 0.001, 0.004), (25, -0.002, 0.004))
        else:
            rets = _returns((240, 0.0, 0.004), (80, -0.004, 0.004))
        out.append(_bars(f"S{i:02d}", rets, s0=40.0 + i))
    return out


def _panel(spy: str | None, n_above_50: int, n_above_200: int | None = None) -> pd.DataFrame:
    frames = _stocks(n_above_50, n_above_200 if n_above_200 is not None else n_above_50)
    if spy is not None:
        frames.append(_bars("SPY", SPY_PATHS[spy], s0=400.0, volume=5e7))
    return build_panel(pd.concat(frames, ignore_index=True))


def _settings(**playbook: object) -> Settings:
    return Settings(
        strategies={name: {"enabled": True} for name in ALL_STRATEGIES},
        playbook=PlaybookConfig(**playbook),
    )


@pytest.fixture(scope="module")
def settings() -> Settings:
    return _settings()


@pytest.fixture(scope="module")
def oct6_panel() -> pd.DataFrame:
    # 11 / 40 = 27.5% above the 50-day, 16 / 40 = 40% above the 200-day (doc 06: 26.9% / 39.7% on Oct 6 2026)
    return _panel("bull", n_above_50=11, n_above_200=16)


# ------------------------------------------------------------------------------------------- Oct 6 2026
def test_oct_6_2026_index_at_highs_with_27pct_breadth_is_narrow_uptrend(oct6_panel, settings) -> None:
    state = pb.market_state(oct6_panel, OCT_6_2026, settings=settings)
    assert state.as_of == OCT_6_2026
    assert state.spy_trend == "up"
    assert state.breadth == "weak"
    assert state.regime == "narrow_uptrend"
    assert state.inputs["pct_above_50"] == pytest.approx(27.5)
    assert state.inputs["pct_above_200"] == pytest.approx(40.0)
    assert state.inputs["n_symbols"] == N_STOCKS, "SPY is excluded from the stock breadth population"
    assert state.inputs["spy_dist_52w_high_pct"] > -settings.playbook.near_high_pct
    assert any("bifurcated" in n for n in state.notes)

    allowed = pb.select_strategies(state, settings)
    assert allowed["pullback_trend"] > 0, "leaders-only pullbacks stay on"
    assert "sr_bounce" not in allowed, "no leader / RS gate: not a leaders-only pullback (methods.md 3b, 3c)"
    assert allowed["rsi2_meanrev"] > 0, "index mean reversion is the diversifier"
    assert not set(BREAKOUT_FAMILY) & set(allowed), "no broad breakouts in a narrow tape"
    assert all(0 < m < 1 for m in allowed.values()), "reduced size in a narrow uptrend"


def test_oct_6_2026_published_breadth_numbers(settings) -> None:
    """The real Oct 6 2026 all-US readings (4,806 stocks: 26.9% above the 50-day, 39.7% above the 200-day)
    passed as a precomputed breadth frame over an SPY-only panel at its high."""
    spy_only = build_panel(_bars("SPY", SPY_PATHS["bull"], s0=400.0, volume=5e7))
    breadth = pd.DataFrame(
        [[26.9, 39.7, 180, 150, 1.2, 60, 240, 4806]],
        columns=list(BREADTH_COLUMNS[:8]),
        index=pd.DatetimeIndex([pd.Timestamp(OCT_6_2026)], name="session"),
    )
    state = pb.market_state(spy_only, OCT_6_2026, breadth=breadth, settings=settings)
    assert (state.spy_trend, state.breadth, state.regime) == ("up", "weak", "narrow_uptrend")
    allowed = pb.select_strategies(state, settings)
    assert "pullback_trend" in allowed and not set(BREAKOUT_FAMILY) & set(allowed)


# ------------------------------------------------------------------------------------------- other regimes
@pytest.mark.parametrize(
    ("spy", "n_above", "regime", "trend"),
    [
        ("bull", N_STOCKS, "healthy_uptrend", "up"),
        ("downtrend", N_STOCKS, "correction", "down"),
        ("below_200", N_STOCKS, "correction", "mixed"),
        ("selloff", 11, "high_vol_selloff", "mixed"),
        ("chop", N_STOCKS, "choppy", "mixed"),
    ],
)
def test_regimes(spy, n_above, regime, trend, settings) -> None:
    state = pb.market_state(_panel(spy, n_above), OCT_6_2026, settings=settings)
    assert (state.regime, state.spy_trend) == (regime, trend), state.notes
    assert state.regime in PLAYBOOK_REGIMES


def test_router_tables_per_regime(settings) -> None:
    healthy = pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime="healthy_uptrend"), settings)
    assert set(healthy) == set(ALL_STRATEGIES) and set(healthy.values()) == {1.0}
    assert pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime="correction"), settings) == {}
    selloff = pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime="high_vol_selloff"), settings)
    assert set(selloff) == {"rsi2_meanrev"} and selloff["rsi2_meanrev"] < 1.0
    chop = pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime="choppy"), settings)
    assert set(chop) == {"rsi2_meanrev"}
    for regime in PLAYBOOK_REGIMES:
        allowed = pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime=regime), settings)
        assert all(0.0 < m <= 1.0 for m in allowed.values())
        assert list(allowed) == sorted(allowed), "deterministic order"
        if regime != "healthy_uptrend":
            assert not set(BREAKOUT_FAMILY) & set(allowed), "breakouts only in healthy_uptrend"


def test_high_vol_selloff_classification_inputs(settings) -> None:
    state = pb.market_state(_panel("selloff", 11), OCT_6_2026, settings=settings)
    assert state.vol_regime == "high"
    assert state.inputs["spy_vol_pct"] >= settings.playbook.vol_high_pct
    assert state.inputs["spy_close"] < state.inputs["spy_sma_50"]


# ------------------------------------------------------------------------------------------- breadth rules
@pytest.mark.parametrize(
    ("pct", "ratio", "n", "expect", "pct200"),
    [
        (65.0, 1.0, 500, "neutral", 50.0),  # > 60% above the 50-day alone is an unconfirmed thrust
        (65.0, 1.0, 500, "strong", 65.0),  # ... confirmed by the 200-day line above its on-threshold
        (55.0, 2.5, 500, "strong", 50.0),  # ratio >= 2 with Keller's 50% line held
        (45.0, 2.5, 500, "neutral", 50.0),  # ratio >= 2 but under 50% above the 50-day
        (45.0, 1.0, 500, "neutral", 70.0),  # 200-day line on but under Keller's 50% line
        (50.0, 1.0, 500, "neutral", 50.0),
        (39.9, 3.0, 500, "weak", 50.0),  # < 40% above the 50-day
        (70.0, 0.5, 500, "weak", 70.0),  # Stockbee ratio <= 0.5
        (np.nan, 0.4, 500, "weak", 50.0),
        (np.nan, 3.0, 500, "neutral", 50.0),  # ratio alone never reads strong
        (70.0, np.nan, 500, "neutral", 50.0),  # no 4% day and the 200-day line off: not confirmed
        (70.0, np.nan, 500, "strong", 61.0),
        (np.nan, np.nan, 500, "neutral", 50.0),
        (80.0, 3.0, 5, "neutral", 80.0),  # too few names: unavailable
    ],
)
def test_classify_breadth(pct, ratio, n, expect, pct200, settings) -> None:
    row = pd.Series({"pct_above_50": pct, "pct_above_200": pct200, "ratio_10d": ratio, "n_symbols": n})
    state, notes = pb.classify_breadth(row, settings.playbook)
    assert state == expect and notes


def test_jan_14_2026_thrust_without_confirmation_keeps_breakouts_off(settings) -> None:
    """methods.md 2a: 63.1% above the 50-day on Jan 14 2026 preceded a six-week slide. With ratio_10d 1.2 and
    45% above the 200-day the breakout gate (ratio >= 2 or the 200-day line on) is not met."""
    row = pd.Series({"pct_above_50": 63.1, "pct_above_200": 45.0, "ratio_10d": 1.2, "n_symbols": 500})
    state, notes = pb.classify_breadth(row, settings.playbook)
    assert state == "neutral" and any("unconfirmed thrust" in n for n in notes)
    spy = pb._Spy()
    spy.trend_code, spy.close, spy.sma_fast, spy.sma_slow = 1.0, 110.0, 105.0, 100.0
    regime, _ = pb.classify_regime(spy, "up", "normal", state)
    assert regime == "narrow_uptrend"
    assert not set(NEW_BREAKOUT_FAMILY) & set(pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime=regime),
                                                                   Settings()))


def test_slow_line_hysteresis_turns_on_above_60_and_off_below_40(settings) -> None:
    days = pd.DatetimeIndex(pd.bdate_range("2026-01-05", periods=6), name="session")
    frame = pd.DataFrame({"pct_above_200": [55.0, 61.0, 50.0, 45.0, 39.0, 55.0], "n_symbols": 500}, index=days)
    on = [pb.slow_line_on(frame, d.date(), settings.playbook) for d in days]
    assert on == [False, True, True, True, False, False]  # 50 and 45 hold the "on" state; 55 after 39 stays off
    row = pd.Series({"pct_above_50": 55.0, "pct_above_200": 50.0, "ratio_10d": 1.0, "n_symbols": 500})
    assert pb.classify_breadth(row, settings.playbook, slow_on=True)[0] == "strong"
    assert pb.classify_breadth(row, settings.playbook, slow_on=False)[0] == "neutral"
    with pytest.raises(ValidationError, match="off_pct_above_200"):
        PlaybookConfig(breadth_off_pct_above_200=70.0)


def test_breadth_thresholds_come_from_settings() -> None:
    row = pd.Series({"pct_above_50": 35.0, "ratio_10d": 2.5, "n_symbols": 100})
    assert pb.classify_breadth(row, PlaybookConfig())[0] == "weak"
    loose = PlaybookConfig(breadth_weak_pct_above_50=30.0, breadth_strong_pct_above_50=34.0,
                           breadth_confirm_pct_above_50=34.0)
    assert pb.classify_breadth(row, loose)[0] == "strong"
    assert pb.classify_breadth(None, PlaybookConfig())[0] == "neutral"


# ------------------------------------------------------------------------------------------- point in time
def test_point_in_time(oct6_panel, settings) -> None:
    as_of = DATES[-30].date()
    full = pb.market_state(oct6_panel, as_of, settings=settings)
    cut = oct6_panel.loc[oct6_panel["ts"].dt.tz_localize(None).dt.normalize() <= pd.Timestamp(as_of)]
    assert pb.market_state(cut, as_of, settings=settings) == full
    later = oct6_panel.copy()
    later.loc[later["ts"].dt.tz_localize(None).dt.normalize() > pd.Timestamp(as_of), "close"] *= 0.5
    assert pb.market_state(later, as_of, settings=settings) == full, "rows after as_of are never read"


def test_precomputed_breadth_matches_computed(oct6_panel, settings) -> None:
    breadth = market_breadth(oct6_panel, exclude=("SPY",))
    for as_of in (DATES[-1].date(), DATES[-60].date()):
        assert pb.market_state(oct6_panel, as_of, breadth=breadth, settings=settings) == pb.market_state(
            oct6_panel, as_of, settings=settings
        )


def test_weekend_as_of_uses_prior_session(oct6_panel, settings) -> None:
    friday = next(d.date() for d in reversed(DATES) if d.dayofweek == 4)
    saturday = pd.Timestamp(friday) + pd.Timedelta(days=1)
    a = pb.market_state(oct6_panel, saturday.date(), settings=settings)
    b = pb.market_state(oct6_panel, friday, settings=settings)
    assert a.model_dump(exclude={"as_of"}) == b.model_dump(exclude={"as_of"})


# ------------------------------------------------------------------------------------------- fallbacks
def test_falls_back_to_broadcast_market_columns(settings) -> None:
    stocks = pd.concat(_stocks(N_STOCKS, N_STOCKS), ignore_index=True)
    spy = _bars("SPY", SPY_PATHS["bull"], s0=400.0, volume=5e7)
    panel = build_panel(stocks, market=spy)
    assert "SPY" not in set(panel["symbol"])
    state = pb.market_state(panel, OCT_6_2026, settings=settings)
    assert state.spy_trend == "up" and state.regime == "healthy_uptrend"
    assert any("market_trend_state" in n for n in state.notes)


def test_no_market_data_is_conservative(settings) -> None:
    panel = _panel(None, N_STOCKS).drop(columns=["market_trend_state", "market_vol_regime"])
    state = pb.market_state(panel, OCT_6_2026, settings=settings)
    assert state.regime == pb.REGIME_WITHOUT_MARKET == "choppy"
    assert state.spy_trend == "mixed" and state.vol_regime == "normal"
    assert set(pb.select_strategies(state, settings)) == {"rsi2_meanrev"}


def test_market_symbol_is_a_setting(oct6_panel) -> None:
    renamed = oct6_panel.replace({"symbol": {"SPY": "IVV"}})
    spy_state = pb.market_state(oct6_panel, OCT_6_2026, settings=_settings())
    ivv_state = pb.market_state(renamed, OCT_6_2026, settings=_settings(market_symbol="IVV"))
    assert ivv_state == spy_state


# ------------------------------------------------------------------------------------------- router config
def test_select_respects_enabled_flags_and_router_switch() -> None:
    state = pb.MarketState(as_of=OCT_6_2026, regime="healthy_uptrend")
    s = Settings(
        strategies={
            "breakout_52w": {"enabled": False},
            "pullback_trend": {},
            "rsi2_meanrev": {"enabled": True},
        }
    )
    assert set(pb.select_strategies(state, s)) == {"pullback_trend", "rsi2_meanrev"}
    off = s.model_copy(update={"playbook": PlaybookConfig(enabled=False)})
    assert pb.select_strategies(pb.MarketState(as_of=OCT_6_2026, regime="correction"), off) == {
        "pullback_trend": 1.0,
        "rsi2_meanrev": 1.0,
    }
    zero = s.model_copy(
        update={"playbook": PlaybookConfig(regimes={"healthy_uptrend": {"pullback_trend": 0.0}})}
    )
    assert pb.select_strategies(state, zero) == {}
    # nothing listed under strategies: every name in the table counts as enabled
    assert set(pb.select_strategies(state, Settings())) == set(default_playbook_table()["healthy_uptrend"])


def test_playbook_config_validation() -> None:
    with pytest.raises(ValidationError, match="unknown regime"):
        PlaybookConfig(regimes={"bull_market": {"pullback_trend": 1.0}})
    with pytest.raises(ValidationError, match="outside"):
        PlaybookConfig(regimes={"choppy": {"rsi2_meanrev": 1.5}})
    with pytest.raises(ValidationError, match="weak_pct"):
        PlaybookConfig(breadth_weak_pct_above_50=70.0)
    with pytest.raises(ValidationError, match="ratio"):
        PlaybookConfig(breadth_weak_ratio_10d=3.0)


def test_settings_yaml_playbook_block_matches_defaults() -> None:
    raw = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())
    cfg = Settings.model_validate(raw).playbook
    assert cfg.regimes == default_playbook_table()
    assert cfg.model_dump() == PlaybookConfig().model_dump()


def test_defaults_follow_methods_md() -> None:
    table = default_playbook_table()
    assert set(table) == set(PLAYBOOK_REGIMES)
    breakout_regimes = {r for r, t in table.items() if set(BREAKOUT_FAMILY) & set(t)}
    assert breakout_regimes == {"healthy_uptrend"}
    assert {r for r, t in table.items() if "pullback_trend" in t} == {"healthy_uptrend", "narrow_uptrend"}
    assert {r for r, t in table.items() if "rsi2_meanrev" in t} == {
        "healthy_uptrend",
        "narrow_uptrend",
        "choppy",
        "high_vol_selloff",
    }
    assert table["correction"] == {}
    assert table["high_vol_selloff"]["rsi2_meanrev"] < table["choppy"]["rsi2_meanrev"]


NEW_BREAKOUT_FAMILY = ("base_breakout", "power_gap", "qullamaggie_flag", "episodic_pivot")


def test_every_enabled_strategy_is_routable() -> None:
    """A strategy enabled in settings.yaml but absent from every regime would never be selected by the router."""
    raw = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text())
    settings = Settings.model_validate(raw)
    table = settings.playbook.regimes
    for name in pb.enabled_strategy_names(settings):
        assert any(name in t for t in table.values()), f"{name} is enabled but in no playbook regime"
    # methods.md 0 item 3: breakout families only with confirmed participation; Holy Grail follows pullback_trend
    assert {r for r, t in table.items() if set(NEW_BREAKOUT_FAMILY) & set(t)} == {"healthy_uptrend"}
    assert {r for r, t in table.items() if "pullback_holy_grail" in t} == {"healthy_uptrend", "narrow_uptrend"}
    assert table["narrow_uptrend"]["pullback_holy_grail"] == table["narrow_uptrend"]["pullback_trend"]


def test_market_state_model_round_trip(oct6_panel, settings) -> None:
    state = pb.market_state(oct6_panel, OCT_6_2026, settings=settings)
    assert pb.MarketState.model_validate_json(state.model_dump_json()) == state
    with pytest.raises(ValidationError):
        pb.MarketState(as_of=OCT_6_2026, regime="bear_market")


def test_playbook_is_not_a_registered_strategy() -> None:
    names = registry.names("strategy")
    assert "playbook" not in names
    modules = {registry.get("strategy", n).__module__ for n in names}
    assert "swing_engine.strategies.playbook" not in modules
