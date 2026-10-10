"""News / filing strategies (strategies/news_filters.py, strategies/activist_13d_drift.py): each no-news variant keeps
exactly the base strategy's signals on no-news sessions and none on news sessions; pullback_trend_avoid_402 drops a
recent 4.02; activist_13d_drift fires only on the 13D reaction session. All return [] without their columns."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from tests.fixtures.strategies.panel import last_date, make_panel, set_last

NO_NEWS = {
    "connors_rsi2_variants_no_news": "connors_rsi2_variants",
    "connors_tps_scale_in_no_news": "connors_tps_scale_in",
    "connors_hpetf_rsi_variants_no_news": "connors_hpetf_rsi_variants",
}
SYMS = tuple(f"S{i:02d}" for i in range(12))


def _day(panel: pd.DataFrame) -> pd.Series:
    return panel["ts"].dt.tz_localize(None).dt.normalize()


def _firing_day(base, panel: pd.DataFrame) -> tuple[date, list]:
    for d in sorted(_day(panel).dt.date.unique())[-120:][::-1]:
        sigs = base.signals(panel, d)
        if sigs:
            return d, sigs
    pytest.skip(f"{base.name} never fires on the synthetic panel")


@pytest.mark.parametrize("name", sorted(NO_NEWS))
def test_no_news_variant_filters_the_base_signals(name: str) -> None:
    strat, base = registry.get("strategy", name)(), registry.get("strategy", NO_NEWS[name])()
    panel = ensure_extra(make_panel(SYMS, n_days=400, seed=3), strat.extra_features)
    assert strat.signals(panel, last_date(panel)) == []  # no news columns: nothing can be shown quiet
    d, base_sigs = _firing_day(base, panel)
    on_day = _day(panel) == pd.Timestamp(d)
    noisy = base_sigs[0].symbol

    quiet = panel.assign(news_flag_1d=0.0, news_8k_flag_1d=0.0)
    quiet.loc[on_day & (quiet["symbol"] == noisy), "news_flag_1d"] = 1.0
    got = strat.signals(quiet, d)
    assert [s.symbol for s in got] == [s.symbol for s in base_sigs if s.symbol != noisy]
    assert all(s.strategy == name for s in got)
    assert [s.entry for s in got] == [s.entry for s in base_sigs if s.symbol != noisy]

    # auto falls back to the 8-K flag where Benzinga is NaN (month not ingested); NaN in both drops the signal
    fallback = quiet.assign(news_flag_1d=np.nan)
    fallback.loc[on_day & (fallback["symbol"] == noisy), "news_8k_flag_1d"] = 1.0
    assert [s.symbol for s in strat.signals(fallback, d)] == [s.symbol for s in got]
    unknown = quiet.assign(news_flag_1d=np.nan, news_8k_flag_1d=np.nan)
    assert strat.signals(unknown, d) == []
    only_8k = registry.get("strategy", name)({**strat.params, "news_source": "8k"})
    assert len(only_8k.signals(quiet, d)) == len(base_sigs)  # 8-K flag is 0 everywhere


def test_pullback_trend_avoid_402() -> None:
    strat, base = registry.get("strategy", "pullback_trend_avoid_402")(), registry.get("strategy", "pullback_trend")()
    panel = make_panel(SYMS, n_days=400, seed=11)
    assert strat.signals(panel, last_date(panel)) == []
    d, base_sigs = _firing_day(base, panel)
    sym = base_sigs[0].symbol
    clean = panel.assign(days_since_402=np.nan)
    assert len(strat.signals(clean, d)) == len(base_sigs)
    hit = clean.copy()
    hit.loc[(_day(hit) == pd.Timestamp(d)) & (hit["symbol"] == sym), "days_since_402"] = 10.0
    assert sym not in {s.symbol for s in strat.signals(hit, d)}
    old = clean.copy()
    old.loc[(_day(old) == pd.Timestamp(d)) & (old["symbol"] == sym), "days_since_402"] = 63.0  # outside the window
    assert sym in {s.symbol for s in strat.signals(old, d)}


def test_activist_13d_drift_fires_on_the_reaction_session_only() -> None:
    strat = registry.get("strategy", "activist_13d_drift")()
    panel = make_panel(("AAA", "BBB"), n_days=60)
    d = last_date(panel)
    assert strat.signals(panel, d) == []
    p = set_last(panel.assign(days_since_13d=np.nan), "AAA", days_since_13d=0.0)
    p = set_last(p, "BBB", days_since_13d=1.0)
    sigs = strat.signals(p, d)
    assert [s.symbol for s in sigs] == ["AAA"]
    s = sigs[0]
    atr = p.loc[p["symbol"] == "AAA", "atr_14"].iloc[-1]
    assert s.target is None and s.entry - s.stop == pytest.approx(2.0 * atr)
    assert strat.should_exit(pd.Series({"close": 1.0}), 10) and not strat.should_exit(pd.Series({"close": 1.0}), 9)
    cheap = set_last(p, "AAA", close=4.0, open=4.0, high=4.1, low=3.9)
    assert strat.signals(cheap, d) == []  # under min_price
