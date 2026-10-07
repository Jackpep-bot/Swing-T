"""MassiveProvider grouped-daily, per-ticker details, cached universe reference and plan-rate settings."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pytest
import respx

from swing_engine.core.config import Secrets, Settings
from swing_engine.data._common import BAR_COLUMNS, TZ
from swing_engine.data.massive import (
    CALLS_PER_MIN_ENV,
    MASSIVE_BASE_URL,
    REFERENCE_CACHE_DAYS,
    MassiveProvider,
    resolve_calls_per_min,
)
from tests.helpers_data import FakeClock, fixture_json

TICKERS = f"{MASSIVE_BASE_URL}/v3/reference/tickers"
GROUPED = f"{MASSIVE_BASE_URL}/v2/aggs/grouped/locale/us/market/stocks"


class Today:
    def __init__(self, d: date) -> None:
        self.d = d

    def __call__(self) -> date:
        return self.d


def _provider(tmp_path, today: date = date(2024, 3, 1), **kw) -> MassiveProvider:
    clock = FakeClock()
    return MassiveProvider(
        "test-key", cache_dir=tmp_path / "raw", clock=clock, sleep=clock.sleep, today=kw.pop("today_fn", Today(today)), **kw
    )


def reference_handler(request: httpx.Request) -> httpx.Response:
    """Dispatch the typed reference listings the way Massive pages them."""
    assert request.headers["Authorization"] == "Bearer test-key"
    p = request.url.params
    cursor = p.get("cursor")
    if cursor == "cs2":
        return httpx.Response(200, json=fixture_json("massive_grouped_ref_cs_active_p2.json"))
    if cursor == "csinactive2":
        return httpx.Response(200, json=fixture_json("massive_grouped_ref_cs_inactive_p2.json"))
    if cursor == "csinactive3":
        return httpx.Response(200, json=fixture_json("massive_grouped_ref_empty.json"))
    if cursor is not None:
        raise AssertionError(f"unexpected cursor {cursor}")
    assert p.get("market") == "stocks" and p.get("limit") == "1000"
    kind, active = p.get("type"), p.get("active")
    if active == "false":
        assert p.get("sort") == "delisted_utc" and p.get("order") == "desc"
    if kind == "CS" and active == "true":
        return httpx.Response(200, json=fixture_json("massive_grouped_ref_cs_active_p1.json"))
    if kind == "CS" and active == "false":
        return httpx.Response(200, json=fixture_json("massive_grouped_ref_cs_inactive_p1.json"))
    if kind == "ETF" and active == "true":
        return httpx.Response(200, json=fixture_json("massive_grouped_ref_etf_active.json"))
    return httpx.Response(200, json=fixture_json("massive_grouped_ref_empty.json"))


@respx.mock
def test_grouped_daily_parses_every_ticker_for_the_session(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key" and "apiKey" not in str(request.url)
        assert request.url.params.get("adjusted") == "true" and request.url.params.get("include_otc") == "false"
        return httpx.Response(200, json=fixture_json("massive_grouped_2024-01-03.json"))

    route = respx.get(f"{GROUPED}/2024-01-03").mock(side_effect=handler)
    bars = _provider(tmp_path).grouped_daily(date(2024, 1, 3))
    assert route.call_count == 1
    assert list(bars.columns) == BAR_COLUMNS and len(bars) == 6
    assert str(bars["ts"].dt.tz) == TZ
    assert {t.strftime("%Y-%m-%d %H:%M") for t in bars["ts"]} == {"2024-01-03 00:00"}  # session key, not window end
    aapl = bars.set_index("symbol").loc["AAPL"]
    assert aapl["close"] == 184.25 and aapl["volume"] == 58414500 and aapl["vwap"] == 184.3226
    assert aapl["adj_close"] == aapl["close"]
    assert "BACPB" in set(bars["symbol"])  # every ticker in the response; the universe screens types later


@respx.mock
def test_grouped_daily_empty_session_and_opt_in_cache(tmp_path) -> None:
    empty = respx.get(f"{GROUPED}/2024-01-15").mock(
        return_value=httpx.Response(200, json=fixture_json("massive_grouped_empty.json"))
    )
    full = respx.get(f"{GROUPED}/2024-01-03").mock(
        return_value=httpx.Response(200, json=fixture_json("massive_grouped_2024-01-03.json"))
    )
    p = _provider(tmp_path, cache_grouped=True)
    assert p.grouped_daily("2024-01-15").empty and p.grouped_daily("2024-01-15").empty
    assert empty.call_count == 2  # an empty (holiday / unpublished) answer is never cached
    assert len(p.grouped_daily(date(2024, 1, 3))) == len(p.grouped_daily(date(2024, 1, 3))) == 6
    assert full.call_count == 1  # opted-in cache serves the immutable day
    q = _provider(tmp_path / "other")  # default: no grouped cache (the store ledger makes backfills resumable)
    q.grouped_daily(date(2024, 1, 3))
    q.grouped_daily(date(2024, 1, 3))
    assert full.call_count == 3


@respx.mock
def test_grouped_daily_plan_limit_raises_status_error(tmp_path) -> None:
    respx.get(f"{GROUPED}/2019-01-02").mock(
        return_value=httpx.Response(403, json=fixture_json("massive_grouped_not_authorized.json"))
    )
    with pytest.raises(httpx.HTTPStatusError) as err:
        _provider(tmp_path).grouped_daily(date(2019, 1, 2))
    assert err.value.response.status_code == 403


@respx.mock
def test_grouped_daily_error_status_in_body_raises(tmp_path) -> None:
    respx.get(f"{GROUPED}/2024-01-03").mock(
        return_value=httpx.Response(200, json={"status": "ERROR", "error": "Unknown API Key"})
    )
    with pytest.raises(RuntimeError, match="Unknown API Key"):
        _provider(tmp_path).grouped_daily(date(2024, 1, 3))


@respx.mock
def test_symbol_details_fetches_only_the_named_tickers(tmp_path) -> None:
    aapl = respx.get(f"{TICKERS}/AAPL").mock(
        return_value=httpx.Response(200, json=fixture_json("massive_grouped_ticker_AAPL.json"))
    )
    missing = respx.get(f"{TICKERS}/ZZZZ").mock(return_value=httpx.Response(404, json={"status": "NOT_FOUND"}))
    listing = respx.get(TICKERS).mock(side_effect=AssertionError("must not page the full reference list"))
    df = _provider(tmp_path).symbol_details(["aapl", "ZZZZ", "AAPL"])
    assert aapl.call_count == 1 and missing.call_count == 1 and listing.call_count == 0
    assert df["symbol"].tolist() == ["AAPL"]
    row = df.iloc[0]
    assert row["type"] == "CS" and row["exchange"] == "XNAS" and row["listed_at"] == date(1980, 12, 12)


@respx.mock
def test_symbol_details_other_errors_raise(tmp_path) -> None:
    respx.get(f"{TICKERS}/AAPL").mock(return_value=httpx.Response(401, json={"status": "ERROR"}))
    with pytest.raises(httpx.HTTPStatusError):
        _provider(tmp_path).symbol_details(["AAPL"])


@respx.mock
def test_universe_reference_pages_typed_lists_once_and_stops_delisted_paging_early(tmp_path) -> None:
    route = respx.get(TICKERS).mock(side_effect=reference_handler)
    p = _provider(tmp_path)
    ref = p.universe_reference(include_etfs=False, delisted_since=date(2023, 1, 1))
    # CS active (2 pages) + ADRC active + CS inactive (2 pages: the 2nd is all older -> stop) + ADRC inactive
    assert route.call_count == 6
    assert ref["symbol"].tolist() == ["AAPL", "MSFT", "OLDCO", "PENNY", "PNKX", "THIN"]
    old = ref.set_index("symbol").loc["OLDCO"]
    assert bool(old["active"]) is False and old["delisted_at"] == date(2024, 2, 20) and old["type"] == "CS"
    assert "SPY" not in set(ref["symbol"]) and "GONE" not in set(ref["symbol"])
    # cached on disk for REFERENCE_CACHE_DAYS: a second build costs nothing
    again = p.universe_reference(include_etfs=False, delisted_since=date(2023, 6, 1))
    assert route.call_count == 6 and again["symbol"].tolist() == ref["symbol"].tolist()
    assert any(f.name.startswith("reference_tickers_CS_active") for f in (tmp_path / "raw").iterdir())
    # ETFs only when the universe allows them (one more type: active + inactive listings)
    with_etf = p.universe_reference(include_etfs=True, delisted_since=date(2023, 1, 1))
    assert "SPY" in set(with_etf["symbol"]) and route.call_count == 8


@respx.mock
def test_universe_reference_cache_expiry_and_deeper_window(tmp_path) -> None:
    route = respx.get(TICKERS).mock(side_effect=reference_handler)
    today = Today(date(2024, 3, 1))
    p = _provider(tmp_path, today_fn=today)
    p.universe_reference(delisted_since=date(2023, 1, 1))
    assert route.call_count == 6
    p.universe_reference(delisted_since=date(2018, 1, 1))  # older window than cached -> inactive lists refetched
    assert route.call_count == 6 + 4  # CS inactive now pages to the end (3 pages) + ADRC inactive
    today.d = date(2024, 3, 1 + REFERENCE_CACHE_DAYS)
    p.universe_reference(delisted_since=date(2023, 1, 1))
    assert route.call_count == 10 + 6  # stale after REFERENCE_CACHE_DAYS
    no_delisted = p.universe_reference()  # no window -> no inactive paging at all
    assert route.call_count == 16 and "OLDCO" not in set(no_delisted["symbol"])


def test_calls_per_min_from_env_or_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_calls_per_min(Settings(), env={}) == 5.0
    assert resolve_calls_per_min(SimpleNamespace(data=SimpleNamespace(massive_calls_per_min=100)), env={}) == 100.0
    assert resolve_calls_per_min(Settings(), env={CALLS_PER_MIN_ENV: "300"}) == 300.0
    with pytest.raises(ValueError):
        resolve_calls_per_min(Settings(), env={CALLS_PER_MIN_ENV: "0"})
    monkeypatch.setenv(CALLS_PER_MIN_ENV, "100")
    p = MassiveProvider.from_settings(Settings(), Secrets(_env_file=None, massive_api_key="k"))
    assert p.calls_per_min == 100.0 and p.http.bucket is not None and p.http.bucket.capacity == 100
    monkeypatch.delenv(CALLS_PER_MIN_ENV)
    p = MassiveProvider.from_settings(Settings(), Secrets(_env_file=None, massive_api_key="k"))
    assert p.calls_per_min == 5.0
