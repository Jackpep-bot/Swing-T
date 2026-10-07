from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.registry import get
from swing_engine.data._common import BAR_COLUMNS, TZ
from swing_engine.data.massive import MASSIVE_BASE_URL, MassiveProvider
from tests.helpers_data import FakeClock, fixture_json

TICKERS = f"{MASSIVE_BASE_URL}/v3/reference/tickers"
AGGS = f"{MASSIVE_BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-01-04"


def _tickers_handler(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer test-key"
    assert "apiKey" not in str(request.url)
    params = request.url.params
    if params.get("cursor") == "page2":
        return httpx.Response(200, json=fixture_json("massive_tickers_active_p2.json"))
    if params.get("active") == "false":
        return httpx.Response(200, json=fixture_json("massive_tickers_inactive.json"))
    return httpx.Response(200, json=fixture_json("massive_tickers_active_p1.json"))


def _provider(tmp_path, clock: FakeClock, **kw) -> MassiveProvider:
    return MassiveProvider("test-key", cache_dir=tmp_path / "raw", clock=clock, sleep=clock.sleep, today=lambda: date(2024, 10, 1), **kw)


@respx.mock
def test_list_symbols_paginates_and_includes_delisted(tmp_path) -> None:
    route = respx.get(TICKERS).mock(side_effect=_tickers_handler)
    p = _provider(tmp_path, FakeClock())
    df = p.list_symbols(include_delisted=True)
    assert route.call_count == 3
    assert df["symbol"].tolist() == ["AAPL", "MSFT", "PNKX", "SIVB", "SPY"]
    row = df.set_index("symbol").loc["SIVB"]
    assert bool(row["active"]) is False and row["delisted_at"] == date(2023, 3, 28)
    assert df.set_index("symbol").loc["AAPL", "listed_at"] == date(1980, 12, 12)
    assert df.set_index("symbol").loc["PNKX", "exchange"] == "OTCM"
    active_only = p.list_symbols(include_delisted=False)
    assert "SIVB" not in set(active_only["symbol"])
    assert route.call_count == 3  # second listing served from the raw JSON cache


@respx.mock
def test_daily_bars_pagination_timestamps_and_cache(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("cursor") == "aggs2":
            return httpx.Response(200, json=fixture_json("massive_aggs_AAPL_p2.json"))
        assert request.url.params.get("adjusted") == "true"
        return httpx.Response(200, json=fixture_json("massive_aggs_AAPL_p1.json"))

    route = respx.get(AGGS).mock(side_effect=handler)
    respx.get(f"{MASSIVE_BASE_URL}/v2/aggs/ticker/ZZZZ/range/1/day/2024-01-02/2024-01-04").mock(
        return_value=httpx.Response(200, json=fixture_json("massive_aggs_empty.json"))
    )
    p = _provider(tmp_path, FakeClock())
    bars = p.daily_bars(["aapl", "ZZZZ"], date(2024, 1, 2), date(2024, 1, 4))
    assert route.call_count == 2
    assert list(bars.columns) == BAR_COLUMNS and len(bars) == 3
    assert bars["symbol"].unique().tolist() == ["AAPL"]
    assert str(bars["ts"].dt.tz) == TZ
    assert [t.strftime("%Y-%m-%d %H:%M") for t in bars["ts"]] == ["2024-01-02 00:00", "2024-01-03 00:00", "2024-01-04 00:00"]
    assert bars["close"].tolist() == [185.64, 184.25, 181.91]
    assert bars["vwap"].iloc[0] == 185.9465 and bars["adj_close"].equals(bars["close"])
    # immutable range -> cached; a second pull costs no HTTP calls
    again = p.daily_bars(["AAPL"], date(2024, 1, 2), date(2024, 1, 4))
    assert route.call_count == 2 and len(again) == 3
    assert any(tmp_path.joinpath("raw").iterdir())


@respx.mock
def test_rate_limit_paces_requests(tmp_path) -> None:
    respx.get(TICKERS).mock(side_effect=_tickers_handler)
    clock = FakeClock()
    p = _provider(tmp_path, clock, calls_per_min=2)
    p.list_symbols(include_delisted=True)  # 3 requests at 2/min -> one 30 s wait
    assert clock.sleeps == [pytest.approx(30.0)]


@respx.mock
def test_error_status_raises(tmp_path) -> None:
    respx.get(AGGS).mock(return_value=httpx.Response(200, json={"status": "ERROR", "error": "Unknown API Key"}))
    p = _provider(tmp_path, FakeClock())
    with pytest.raises(RuntimeError, match="Unknown API Key"):
        p.daily_bars(["AAPL"], date(2024, 1, 2), date(2024, 1, 4))


def test_registry_and_settings() -> None:
    assert get("bar_provider", "massive") is MassiveProvider
    with pytest.raises(ValueError):
        MassiveProvider.from_settings(Settings(), Secrets(_env_file=None))
    p = MassiveProvider.from_settings(Settings(), Secrets(_env_file=None, massive_api_key="k"))
    assert p.http.bucket is not None and p.http.bucket.capacity == 5
