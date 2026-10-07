"""build_universe over grouped bars in the store with Massive's typed (common-stock) reference lists."""
from __future__ import annotations

import re
from datetime import date

import httpx
import pandas as pd
import pytest
import respx

from swing_engine.core.config import Settings
from swing_engine.data._common import normalize_symbols
from swing_engine.data.calendar import trading_days
from swing_engine.data.ingest import write_symbols
from swing_engine.data.massive import MASSIVE_BASE_URL, MassiveProvider
from swing_engine.data.sample import SampleProvider
from swing_engine.data.store import Store
from swing_engine.data.universe import LIQUIDITY_LOOKBACK_SESSIONS, build_universe, lookback_window
from tests.helpers_data import FakeClock
from tests.test_data_massive_grouped import reference_handler

TICKERS = f"{MASSIVE_BASE_URL}/v3/reference/tickers"
GROUPED_RE = re.escape(f"{MASSIVE_BASE_URL}/v2/aggs/grouped/locale/us/market/stocks") + r"/(?P<day>\d{4}-\d{2}-\d{2})"
FIRST, LAST = date(2024, 1, 2), date(2024, 2, 23)
OLDCO_LAST_SESSION = date(2024, 2, 20)  # matches delisted_utc in the inactive reference fixture
#: ticker -> (close, volume); defaults are min_price 5, min_avg_volume 500k, min_avg_dollar_volume 5M
MARKET = {
    "AAPL": (180.0, 50_000_000),
    "MSFT": (370.0, 20_000_000),
    "SPY": (470.0, 60_000_000),  # ETF
    "BACPB": (25.0, 1_000_000),  # preferred: liquid, but not common stock (no reference row)
    "ABCDW": (6.0, 2_000_000),  # warrant: no reference row
    "OLDCO": (40.0, 3_000_000),  # common stock delisted 2024-02-20 (inactive list)
    "PENNY": (2.0, 9_000_000),  # fails min_price
    "THIN": (50.0, 10_000),  # fails volume / dollar volume
    "PNKX": (30.0, 2_000_000),  # OTC
    "LEGACY": (20.0, 1_000_000),  # only in the store's symbols table (seen in an earlier snapshot)
}


def _grouped_frame(day: date) -> pd.DataFrame:
    rows = [(s, c, v) for s, (c, v) in MARKET.items() if s != "OLDCO" or day <= OLDCO_LAST_SESSION]
    return pd.DataFrame(
        {
            "symbol": [r[0] for r in rows], "ts": [pd.Timestamp(day)] * len(rows), "open": [r[1] for r in rows],
            "high": [r[1] for r in rows], "low": [r[1] for r in rows], "close": [r[1] for r in rows],
            "volume": [float(r[2]) for r in rows], "vwap": [r[1] for r in rows], "adj_close": [r[1] for r in rows],
        }
    )


@pytest.fixture
def store():
    with Store(":memory:") as st:
        for d in trading_days(FIRST, LAST):
            st.write_bars(_grouped_frame(d))
        legacy = normalize_symbols(pd.DataFrame({"symbol": ["LEGACY"], "type": ["CS"], "exchange": ["XNYS"],
                                                 "active": [True], "listed_at": ["2001-01-02"]}))
        write_symbols(st, legacy)
        yield st


def _provider(tmp_path, today: date = date(2024, 3, 1)) -> MassiveProvider:
    clock = FakeClock()
    return MassiveProvider("test-key", cache_dir=tmp_path / "raw", clock=clock, sleep=clock.sleep, today=lambda: today)


@respx.mock
def test_universe_from_store_keeps_common_stock_only(tmp_path, store: Store) -> None:
    reference = respx.get(TICKERS).mock(side_effect=reference_handler)
    grouped = respx.get(url__regex=GROUPED_RE).mock(side_effect=AssertionError("store holds the window"))
    aggs = respx.get(url__regex=r".*/v2/aggs/ticker/.*").mock(side_effect=AssertionError("no per-symbol fetches"))
    prov = _provider(tmp_path)
    as_of = date(2024, 2, 7)
    universe = build_universe(prov, Settings(), as_of, store=store)
    # preferred / warrant (no reference row), penny, thin and OTC names are screened out; SPY is an ETF
    assert universe == ["AAPL", "LEGACY", "MSFT", "OLDCO"]
    assert grouped.call_count == 0 and aggs.call_count == 0
    calls = reference.call_count
    with_etfs = build_universe(prov, Settings.model_validate({"universe": {"include_etfs": True}}), as_of, store=store)
    assert with_etfs == ["AAPL", "LEGACY", "MSFT", "OLDCO", "SPY"]
    assert reference.call_count == calls + 2  # just the ETF lists; CS/ADRC came from the 7-day disk cache
    capped = build_universe(prov, Settings.model_validate({"universe": {"max_symbols": 2}}), as_of, store=store)
    assert capped == ["AAPL", "MSFT"]  # ranked by average dollar volume


@respx.mock
def test_delisted_common_stock_kept_while_listed_and_dropped_after(tmp_path, store: Store) -> None:
    respx.get(TICKERS).mock(side_effect=reference_handler)
    prov = _provider(tmp_path)
    # kept through the session before its last trade date (no next-open entry is possible after that)
    assert "OLDCO" in build_universe(prov, Settings(), date(2024, 2, 16), store=store)
    assert "OLDCO" not in build_universe(prov, Settings(), OLDCO_LAST_SESSION, store=store)
    after = build_universe(prov, Settings(), date(2024, 2, 23), store=store)
    assert "OLDCO" not in after and "AAPL" in after


@respx.mock
def test_without_store_the_window_comes_from_grouped_days(tmp_path) -> None:
    respx.get(TICKERS).mock(side_effect=reference_handler)

    def grouped(request: httpx.Request, day: str) -> httpx.Response:
        frame = _grouped_frame(date.fromisoformat(day))
        rows = [{"T": r.symbol, "o": r.open, "h": r.high, "l": r.low, "c": r.close, "v": r.volume, "vw": r.vwap,
                 "t": 0, "n": 1} for r in frame.itertuples()]
        return httpx.Response(200, json={"status": "OK", "resultsCount": len(rows), "results": rows})

    route = respx.get(url__regex=GROUPED_RE).mock(side_effect=grouped)
    aggs = respx.get(url__regex=r".*/v2/aggs/ticker/.*").mock(side_effect=AssertionError("no per-symbol fetches"))
    universe = build_universe(_provider(tmp_path), Settings(), date(2024, 2, 7))
    assert universe == ["AAPL", "MSFT", "OLDCO"]  # no store: LEGACY has no reference row
    assert route.call_count == LIQUIDITY_LOOKBACK_SESSIONS and aggs.call_count == 0
    first, last = lookback_window(date(2024, 2, 7))
    assert len(trading_days(first, last)) == LIQUIDITY_LOOKBACK_SESSIONS and last == date(2024, 2, 7)


def test_listing_providers_screen_store_bars_like_explicit_bars() -> None:
    p = SampleProvider()
    as_of = date(2025, 6, 2)
    settings = Settings.model_validate(
        {"universe": {"min_price": 1.0, "min_avg_dollar_volume": 1.0, "min_avg_volume": 1.0}}
    )
    first, last = lookback_window(as_of)
    with Store(":memory:") as st:
        st.write_bars(p.daily_bars(p.list_symbols()["symbol"], first, last))
        from_store = build_universe(p, settings, as_of, store=st)
    assert from_store and from_store == build_universe(p, settings, as_of, bars=p.all_bars())
