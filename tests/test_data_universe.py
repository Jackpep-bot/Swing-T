from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from swing_engine.core.config import Settings
from swing_engine.data._common import normalize_symbols
from swing_engine.data.sample import DELISTINGS, SampleProvider
from swing_engine.data.universe import build_universe, filter_symbols, liquidity_screen


def _settings(**universe) -> Settings:
    base = {"min_price": 1.0, "min_avg_dollar_volume": 1.0, "min_avg_volume": 1.0, "max_symbols": 1500}
    return Settings.model_validate({"universe": {**base, **universe}})


def test_static_symbols_override() -> None:
    s = _settings(static_symbols=["spy", "aapl", "AAPL"])
    assert build_universe(SampleProvider(), s, date(2024, 6, 3)) == ["AAPL", "SPY"]


def test_delisted_names_kept_while_active_and_dropped_after() -> None:
    p = SampleProvider()
    sym, (_, last_day) = next(iter(DELISTINGS.items()))
    before = build_universe(p, _settings(), last_day - timedelta(days=90))
    after = build_universe(p, _settings(), last_day + timedelta(days=60))
    assert sym in before and sym not in after
    assert "SPY" not in before  # ETFs excluded by default
    assert "SPY" in build_universe(p, _settings(include_etfs=True), last_day)


def test_ipo_not_in_universe_before_listing() -> None:
    p = SampleProvider()
    assert "IPOX" not in build_universe(p, _settings(), date(2024, 6, 3))
    assert "IPOX" in build_universe(p, _settings(), date(2025, 6, 2))


def test_liquidity_filters_and_cap() -> None:
    p = SampleProvider()
    as_of = date(2025, 6, 2)
    bars = p.all_bars()
    everyone = build_universe(p, _settings(), as_of, bars=bars)
    strict = build_universe(p, _settings(min_avg_dollar_volume=5e8), as_of, bars=bars)
    assert 0 < len(strict) < len(everyone)
    capped = build_universe(p, _settings(max_symbols=5), as_of, bars=bars)
    assert len(capped) == 5
    stats = liquidity_screen(bars, _settings().universe, as_of)
    stats = stats[stats["symbol"] != "SPY"]  # ETFs are excluded by the reference filter
    top5 = stats[stats["passes"]].nlargest(5, "avg_dollar_volume")["symbol"]
    assert sorted(top5) == capped


def test_reference_filters_exchange_type_and_dates() -> None:
    syms = normalize_symbols(
        pd.DataFrame(
            {
                "symbol": ["GOOD", "PINK", "ETFX", "LATE", "DEAD", "UNKN"],
                "name": ["g", "p", "e", "l", "d", "u"],
                "exchange": ["XNAS", "OTCM", "ARCX", "XNYS", "XNYS", None],
                "type": ["CS", "CS", "ETF", "CS", "CS", None],
                "active": [True, True, True, True, False, True],
                "listed_at": ["2020-01-01", "2020-01-01", "2020-01-01", "2025-01-01", "2020-01-01", None],
                "delisted_at": [None, None, None, None, "2023-06-01", None],
            }
        )
    )
    cfg = _settings().universe
    out = filter_symbols(syms, cfg, date(2024, 1, 2))
    assert set(out["symbol"]) == {"GOOD", "UNKN"}
    out2 = filter_symbols(syms, _settings(include_etfs=True, exclude_otc=False).universe, date(2024, 1, 2))
    assert set(out2["symbol"]) == {"GOOD", "PINK", "ETFX", "UNKN"}
    assert "DEAD" in set(filter_symbols(syms, cfg, date(2023, 1, 2))["symbol"])


def test_liquidity_screen_requires_recent_bars() -> None:
    p = SampleProvider()
    bars = p.all_bars()
    sym, (_, last_day) = next(iter(DELISTINGS.items()))
    stats = liquidity_screen(bars, _settings().universe, last_day + timedelta(days=90)).set_index("symbol")
    assert not bool(stats.loc[sym, "passes"])
    assert bool(stats.loc["SPY", "passes"])
