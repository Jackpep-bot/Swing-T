from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest
import respx

from swing_engine.data.edgar import SEC_BASE_URL
from swing_engine.data.float_data import (
    FLOAT_KEYS,
    FLOAT_TABLE,
    METHOD_MASSIVE_SHARES,
    METHOD_PUBLIC_FLOAT_ADJ,
    METHOD_PUBLIC_FLOAT_PRICE,
    METHOD_SHARES_OUTSTANDING,
    METHOD_UNKNOWN,
    METHOD_VENDOR,
    SEC_DATA_BASE_URL,
    SOURCE_EDGAR,
    SOURCE_MASSIVE,
    SOURCE_NONE,
    STALE_AFTER_DAYS,
    FloatInfo,
    FloatSource,
    FMPFloatAdapter,
    VendorFloat,
    VendorFloatAdapter,
    bars_price_lookup,
    float_events_after,
    latest_fact,
    load_float_map,
    stale_reason,
)
from swing_engine.data.massive import MASSIVE_BASE_URL
from swing_engine.data.store import Store
from tests.helpers_data import FakeClock

FIXTURES = Path(__file__).parent / "fixtures" / "float"
UA = "swing-engine test@example.com"
TODAY = date(2026, 10, 6)
COMPANY_TICKERS = f"{SEC_BASE_URL}/files/company_tickers.json"
FACTS_TINY = f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK0001234567.json"
FACTS_NOFL = f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK0000999999.json"
MASSIVE_TINY = f"{MASSIVE_BASE_URL}/v3/reference/tickers/TINY"
MASSIVE_ORPH = f"{MASSIVE_BASE_URL}/v3/reference/tickers/ORPH"
PRICE_ON_FLOAT_DATE = 6.0  # TINY close on 2025-06-30 => 42M USD / 6 = 7.0M float shares


def fx(name: str) -> dict | list:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _source(tmp_path, **kw) -> FloatSource:
    clock = FakeClock()
    return FloatSource(UA, cache_dir=tmp_path / "raw", clock=clock, sleep=clock.sleep, today=lambda: TODAY, **kw)


def _mock_sec(route_facts: bool = True) -> None:
    respx.get(COMPANY_TICKERS).mock(return_value=httpx.Response(200, json=fx("company_tickers.json")))
    if route_facts:
        respx.get(FACTS_TINY).mock(return_value=httpx.Response(200, json=fx("companyfacts_CIK0001234567.json")))
        respx.get(FACTS_NOFL).mock(return_value=httpx.Response(200, json=fx("companyfacts_CIK0000999999.json")))


# ---- constructor / plumbing ---------------------------------------------------------------------------------------
def test_user_agent_must_carry_contact(tmp_path) -> None:
    with pytest.raises(ValueError):
        FloatSource("swing-engine", cache_dir=tmp_path)


@respx.mock
def test_edgar_requests_send_user_agent_and_share_one_bucket(tmp_path) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        if request.url.host == "www.sec.gov":
            return httpx.Response(200, json=fx("company_tickers.json"))
        return httpx.Response(200, json=fx("companyfacts_CIK0001234567.json"))

    tickers = respx.get(COMPANY_TICKERS).mock(side_effect=handler)
    facts = respx.get(FACTS_TINY).mock(side_effect=handler)
    src = _source(tmp_path)
    src.lookup("tiny")
    src.lookup("TINY")  # second call served from the raw cache: no new requests
    assert seen == [UA, UA] and tickers.call_count == 1 and facts.call_count == 1
    assert src.sec.bucket is not None and src.sec.bucket.capacity == 10
    assert src.cik_for("TINY") == "0001234567" and src.cik_for("NOPE") is None


# ---- companyfacts parsing --------------------------------------------------------------------------------------
def test_latest_fact_sums_share_classes_and_drops_duplicates() -> None:
    payload = fx("companyfacts_CIK0001234567.json")
    latest = latest_fact(payload, "EntityCommonStockSharesOutstanding", "shares")
    assert latest is not None
    assert latest["val"] == 12_500_000 and latest["end"] == date(2026, 8, 3) and latest["filed"] == date(2026, 8, 6)
    assert latest["accn"] == "0001234567-26-000030" and latest["form"] == "10-Q"
    pit = latest_fact(payload, "EntityCommonStockSharesOutstanding", "shares", as_of=date(2026, 3, 10))
    assert pit is not None and pit["val"] == 11_000_000 and pit["end"] == date(2026, 3, 2)  # duplicate frame row not double-counted
    pf = latest_fact(payload, "EntityPublicFloat", "USD")
    assert pf is not None and pf["val"] == 42_000_000 and pf["end"] == date(2025, 6, 30)
    assert latest_fact(payload, "EntityPublicFloat", "USD", as_of=date(2026, 3, 4))["end"] == date(2024, 6, 28)
    assert latest_fact(payload, "EntityPublicFloat", "USD", as_of=date(2024, 1, 1)) is None
    assert latest_fact({"facts": {}}, "EntityPublicFloat", "USD") is None


@respx.mock
def test_lookup_edgar_public_float_over_price(tmp_path) -> None:
    _mock_sec()
    asked: list[tuple[str, date]] = []

    def price(symbol: str, on: date) -> float | None:
        asked.append((symbol, on))
        return PRICE_ON_FLOAT_DATE

    info = _source(tmp_path).lookup("TINY", price=price)
    assert asked == [("TINY", date(2025, 6, 30))]  # price is asked for the public-float date, never invented
    assert info.source == SOURCE_EDGAR and info.cik == "0001234567"
    assert info.shares_outstanding == 12_500_000
    # 42M / $6 = 7.0M on 2025-06-30, plus the 2.4M shares issued since (10.1M on 2025-08-04 -> 12.5M on 2026-08-03)
    assert info.float_shares == pytest.approx(9_400_000) and info.float_estimate_method == METHOD_PUBLIC_FLOAT_ADJ
    assert info.public_float_usd == 42_000_000 and info.price_used == PRICE_ON_FLOAT_DATE
    assert info.as_of == date(2026, 8, 3) and info.filed == date(2026, 8, 6) and info.float_as_of == date(2025, 6, 30)
    assert info.float_m == pytest.approx(9.4) and info.known
    assert not info.stale and info.stale_reason is None and info.cross_check == "unavailable"  # no Massive key


@respx.mock
def test_lookup_without_price_falls_back_to_shares_outstanding(tmp_path) -> None:
    _mock_sec()
    src = _source(tmp_path)
    info = src.lookup("TINY")
    assert info.float_shares == 12_500_000 and info.float_estimate_method == METHOD_SHARES_OUTSTANDING
    assert info.public_float_usd == 42_000_000 and info.price_used is None
    scalar = src.lookup("TINY", price=PRICE_ON_FLOAT_DATE)  # a plain number is taken as the price on that date
    assert scalar.float_shares == pytest.approx(9_400_000)
    capped = src.lookup("TINY", price=0.5)  # 42M / 0.5 = 84M > shares outstanding => capped at the count
    assert capped.float_shares == 12_500_000 and capped.float_estimate_method == METHOD_PUBLIC_FLOAT_ADJ
    assert src.lookup("TINY", price=-1.0).float_estimate_method == METHOD_SHARES_OUTSTANDING


@respx.mock
def test_lookup_point_in_time_uses_only_facts_filed_by_as_of(tmp_path) -> None:
    _mock_sec()
    info = _source(tmp_path).lookup("TINY", as_of=date(2025, 6, 1), price=lambda s, d: 3.0)
    # no share count near the 2024-06-28 float date: the estimate keeps the float's own (older) date
    assert info.shares_outstanding == 9_800_000 and info.as_of == date(2024, 6, 28)
    assert info.float_as_of == date(2024, 6, 28) and info.public_float_usd == 30_000_000
    assert info.float_shares == pytest.approx(9_800_000)  # 30M/3 = 10M capped at the 9.8M count
    assert info.stale and info.stale_reason.startswith("age:")  # judged against today, not as_of
    nothing = _source(tmp_path).lookup("TINY", as_of="2024-01-01")
    assert nothing.float_shares is None and nothing.float_estimate_method == METHOD_UNKNOWN and nothing.stale


@respx.mock
def test_lookup_no_public_float_uses_count_only(tmp_path) -> None:
    _mock_sec()
    info = _source(tmp_path).lookup("NOFL", price=lambda s, d: 2.0)
    assert info.shares_outstanding == 15_000_000 and info.float_shares == 15_000_000
    assert info.float_estimate_method == METHOD_SHARES_OUTSTANDING and info.public_float_usd is None
    assert info.as_of == date(2026, 5, 4) and info.stale and info.stale_reason == "age:155d"


@respx.mock
def test_lookup_unknown_symbol_returns_unknown_record_without_raising(tmp_path) -> None:
    _mock_sec()
    info = _source(tmp_path).lookup("ZZZZ")
    assert info == FloatInfo(symbol="ZZZZ", stale=True, stale_reason="no_data")
    assert info.source == SOURCE_NONE and not info.known


@respx.mock
def test_companyfacts_404_is_missing_not_an_error(tmp_path) -> None:
    _mock_sec(route_facts=False)
    respx.get(FACTS_TINY).mock(return_value=httpx.Response(404, text="not found"))
    info = _source(tmp_path).lookup("TINY")
    assert info.cik == "0001234567" and info.float_shares is None and info.source == SOURCE_NONE


@respx.mock
def test_companyfacts_server_error_raises(tmp_path) -> None:
    _mock_sec(route_facts=False)
    respx.get(FACTS_TINY).mock(return_value=httpx.Response(500, text="boom"))
    clock = FakeClock()
    src = FloatSource(UA, cache_dir=tmp_path, clock=clock, sleep=clock.sleep, today=lambda: TODAY)
    with pytest.raises(httpx.HTTPStatusError):
        src.lookup("TINY")


# ---- Massive cross-check ---------------------------------------------------------------------------------------
@respx.mock
def test_massive_cross_check_ok_and_mismatch(tmp_path) -> None:
    _mock_sec()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=fx("massive_ticker_TINY.json"))

    respx.get(MASSIVE_TINY).mock(side_effect=handler)
    src = _source(tmp_path, massive_api_key="test-key")
    info = src.lookup("TINY")
    assert info.cross_check == "ok" and info.source == SOURCE_EDGAR and info.shares_outstanding == 12_500_000
    assert calls[0].headers["Authorization"] == "Bearer test-key" and "apiKey" not in str(calls[0].url)
    respx.get(MASSIVE_TINY).mock(return_value=httpx.Response(200, json=fx("massive_ticker_TINY_mismatch.json")))
    other = _source(tmp_path / "b", massive_api_key="test-key").lookup("TINY")
    assert other.cross_check == "mismatch" and other.shares_outstanding == 12_500_000  # EDGAR stays authoritative


@respx.mock
def test_massive_fallback_when_edgar_has_nothing(tmp_path) -> None:
    _mock_sec()
    respx.get(MASSIVE_ORPH).mock(return_value=httpx.Response(200, json=fx("massive_ticker_ORPH.json")))
    info = _source(tmp_path, massive_api_key="test-key").lookup("ORPH")
    assert info.cik is None and info.source == SOURCE_MASSIVE and info.cross_check == "skipped"
    assert info.shares_outstanding == 8_000_000 and info.float_shares == 8_000_000  # weighted_shares_outstanding
    assert info.float_estimate_method == METHOD_MASSIVE_SHARES and info.as_of == TODAY and not info.stale


@respx.mock
def test_massive_errors_degrade_to_unavailable(tmp_path) -> None:
    _mock_sec()
    respx.get(MASSIVE_TINY).mock(return_value=httpx.Response(404, json={"status": "NOT_FOUND"}))
    info = _source(tmp_path, massive_api_key="test-key").lookup("TINY")
    assert info.cross_check == "unavailable" and info.shares_outstanding == 12_500_000


@respx.mock
def test_massive_cik_resolves_symbols_missing_from_company_tickers(tmp_path) -> None:
    respx.get(COMPANY_TICKERS).mock(return_value=httpx.Response(200, json={}))
    respx.get(MASSIVE_TINY).mock(return_value=httpx.Response(200, json=fx("massive_ticker_TINY.json")))
    respx.get(FACTS_TINY).mock(return_value=httpx.Response(200, json=fx("companyfacts_CIK0001234567.json")))
    info = _source(tmp_path, massive_api_key="test-key").lookup("TINY")
    assert info.cik == "0001234567" and info.source == SOURCE_EDGAR and info.cross_check == "ok"


# ---- vendor adapter --------------------------------------------------------------------------------------------
def test_fmp_adapter_is_a_stub_without_a_key() -> None:
    adapter = FMPFloatAdapter(None)
    assert not adapter.available and adapter.http is None
    with pytest.raises(NotImplementedError):
        adapter.shares_float("TINY")
    with pytest.raises(NotImplementedError):
        VendorFloatAdapter().shares_float("TINY")


def test_fmp_adapter_parses_shares_float_shape() -> None:
    rec = FMPFloatAdapter.parse(fx("fmp_shares_float_TINY.json"), "tiny")
    assert rec == VendorFloat(symbol="TINY", float_shares=6_900_000, shares_outstanding=12_500_000, as_of=date(2026, 9, 30), vendor="fmp")
    assert FMPFloatAdapter.parse([], "TINY") is None and FMPFloatAdapter.parse({"symbol": "OTHER"}, "TINY") is None


@respx.mock
def test_fmp_adapter_with_key_fetches_and_overrides_float(tmp_path) -> None:
    _mock_sec()
    route = respx.get("https://financialmodelingprep.com/api/v4/shares_float").mock(
        return_value=httpx.Response(200, json=fx("fmp_shares_float_TINY.json"))
    )
    clock = FakeClock()
    adapter = FMPFloatAdapter("fmp-test-key", clock=clock, sleep=clock.sleep)
    assert adapter.available
    src = _source(tmp_path, vendor=adapter)
    info = src.lookup("TINY", price=lambda s, d: PRICE_ON_FLOAT_DATE)
    assert route.call_count == 1 and route.calls[0].request.url.params["symbol"] == "TINY"
    assert info.float_shares == 6_900_000 and info.float_estimate_method == METHOD_VENDOR and info.source == "vendor:fmp"
    assert info.shares_outstanding == 12_500_000 and info.as_of == date(2026, 9, 30) and info.float_as_of == date(2026, 9, 30)
    assert info.price_used is None and info.public_float_usd is None and not info.stale
    pit = src.lookup("TINY", as_of=date(2026, 9, 1))  # point-in-time lookups never consult the vendor
    assert pit.float_estimate_method == METHOD_SHARES_OUTSTANDING and route.call_count == 1


class _BrokenVendor(VendorFloatAdapter):
    name = "broken"

    @property
    def available(self) -> bool:
        return True

    def shares_float(self, symbol: str) -> VendorFloat | None:
        raise httpx.ConnectError("down")


@respx.mock
def test_vendor_failure_falls_back_to_edgar(tmp_path) -> None:
    _mock_sec()
    info = _source(tmp_path, vendor=_BrokenVendor()).lookup("TINY")
    assert info.float_estimate_method == METHOD_SHARES_OUTSTANDING and info.source == SOURCE_EDGAR


# ---- staleness --------------------------------------------------------------------------------------------------
def _events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "TINY", "filed_at": "2026-09-01T16:05:00-04:00", "form_type": "424B5", "items": None, "kind": "filing"},
            {"symbol": "TINY", "filed_at": "2026-07-15", "form_type": "8-K", "items": ["3.02", "9.01"], "kind": "filing"},
            {"symbol": "TINY", "filed_at": "2026-09-20", "form_type": "8-K", "items": "7.01,9.01", "kind": "filing"},
            {"symbol": "OTHR", "filed_at": "2026-09-25", "form_type": "424B4", "items": None, "kind": "filing"},
            {"symbol": "TINY", "filed_at": "2026-09-28", "form_type": None, "items": None, "kind": "reverse_split", "ratio": 0.1},
            {"symbol": "TINY", "filed_at": "2026-09-29", "form_type": None, "items": None, "kind": "split", "ratio": 2.0},
        ]
    )


def test_stale_reason_age_and_events() -> None:
    assert stale_reason(None, TODAY, "TINY") == "no_data"
    assert stale_reason(TODAY, TODAY, "TINY") is None
    fresh_edge = date.fromordinal(TODAY.toordinal() - STALE_AFTER_DAYS)
    assert stale_reason(fresh_edge, TODAY, "TINY") is None
    assert stale_reason(date.fromordinal(fresh_edge.toordinal() - 1), TODAY, "TINY") == "age:121d"
    ev = _events()
    hits = float_events_after(ev, "tiny", date(2026, 7, 1))
    assert hits == [
        (date(2026, 7, 15), "8-K 3.02"), (date(2026, 9, 1), "424B5"), (date(2026, 9, 28), "reverse_split"),
    ]  # 7.01-only 8-K and the forward split do not invalidate the float
    assert stale_reason(date(2026, 8, 3), TODAY, "TINY", ev) == "event:reverse_split@2026-09-28"
    assert stale_reason(date(2026, 9, 29), TODAY, "TINY", ev) is None
    assert stale_reason(date(2026, 8, 3), TODAY, "OTHR", ev) == "event:424B4@2026-09-25"
    assert stale_reason(date(2026, 8, 3), TODAY, "NONE", ev) is None
    with pytest.raises(ValueError):
        float_events_after(pd.DataFrame({"symbol": ["TINY"], "form_type": ["424B5"]}), "TINY", date(2026, 1, 1))


@respx.mock
def test_lookup_marks_stale_from_events(tmp_path) -> None:
    _mock_sec()
    info = _source(tmp_path).lookup("TINY", events=_events())
    assert info.stale and info.stale_reason == "event:reverse_split@2026-09-28" and info.float_shares == 12_500_000


# ---- store round-trip -------------------------------------------------------------------------------------------
def _bars(symbol: str, closes: dict[str, float]) -> pd.DataFrame:
    rows = [{"symbol": symbol, "ts": d, "open": c, "high": c, "low": c, "close": c, "volume": 1e5, "vwap": c, "adj_close": c} for d, c in closes.items()]
    return pd.DataFrame(rows)


def test_bars_price_lookup_uses_last_close_on_or_before_date() -> None:
    with Store() as store:
        store.write_bars(_bars("TINY", {"2025-06-27": 5.5, "2025-06-30": PRICE_ON_FLOAT_DATE, "2025-07-01": 9.0}))
        price = bars_price_lookup(store)
        assert price("TINY", date(2025, 6, 30)) == PRICE_ON_FLOAT_DATE
        assert price("TINY", date(2025, 6, 29)) == 5.5
        assert price("TINY", date(2025, 8, 30)) is None  # outside the lookback window
        assert price("NOPE", date(2025, 6, 30)) is None


@respx.mock
def test_refresh_writes_float_table_and_load_float_map_restamps(tmp_path) -> None:
    _mock_sec()
    respx.get(f"{SEC_DATA_BASE_URL}/api/xbrl/companyfacts/CIK0000320193.json").mock(return_value=httpx.Response(404))
    src = _source(tmp_path)
    with Store() as store:
        store.write_bars(_bars("TINY", {"2025-06-30": PRICE_ON_FLOAT_DATE}))
        result = src.refresh(["tiny", "NOFL", "AAPL", "ZZZZ", ""], store)
        assert result == {"written": 2, "unknown": ["AAPL", "ZZZZ"], "errors": {}}
        table = store.read_table(FLOAT_TABLE, order_by="symbol")
        assert table["symbol"].tolist() == ["NOFL", "TINY"] and set(FLOAT_KEYS) <= set(table.columns)
        tiny = table.set_index("symbol").loc["TINY"]
        assert tiny["float_shares"] == pytest.approx(9_400_000) and tiny["price_used"] == PRICE_ON_FLOAT_DATE
        assert pd.Timestamp(tiny["as_of"]).date() == date(2026, 8, 3) and pd.Timestamp(tiny["refreshed_on"]).date() == TODAY
        assert bool(tiny["stale"]) is False and bool(table.set_index("symbol").loc["NOFL", "stale"]) is True
        # idempotent upsert on (symbol, as_of); a mapping of prices works too (42M/$7 = 6.0M + 2.4M issued since)
        assert src.refresh(["TINY"], store, prices={"TINY": 7.0})["written"] == 1
        assert store.count(FLOAT_TABLE) == 2
        assert store.read_table(FLOAT_TABLE, "symbol = ?", ["TINY"])["float_shares"].iloc[0] == pytest.approx(8_400_000)

        fmap = load_float_map(store, today=TODAY)
        assert set(fmap) == {"NOFL", "TINY"}
        assert fmap["TINY"].float_shares == pytest.approx(8_400_000) and fmap["TINY"].as_of == date(2026, 8, 3)
        assert fmap["TINY"].float_estimate_method == METHOD_PUBLIC_FLOAT_ADJ and fmap["TINY"].cik == "0001234567"
        assert fmap["TINY"].filed == date(2026, 8, 6) and fmap["TINY"].float_as_of == date(2025, 6, 30)
        assert not fmap["TINY"].stale and fmap["NOFL"].stale and fmap["NOFL"].stale_reason == "age:155d"
        later = load_float_map(store, today=date(2027, 1, 1))
        assert later["TINY"].stale and later["TINY"].stale_reason == "age:151d"
        with_events = load_float_map(store, today=TODAY, events=_events())
        assert with_events["TINY"].stale_reason == "event:reverse_split@2026-09-28" and not with_events["NOFL"].stale_reason.startswith("event")
    with Store() as empty:
        assert load_float_map(empty) == {}


@respx.mock
def test_refresh_keeps_latest_row_per_symbol(tmp_path) -> None:
    _mock_sec()
    src = _source(tmp_path)
    with Store() as store:
        src.refresh(["TINY"], store, as_of=date(2025, 6, 1))
        src.refresh(["TINY"], store)
        assert store.count(FLOAT_TABLE) == 2
        fmap = load_float_map(store, today=TODAY)
        assert fmap["TINY"].as_of == date(2026, 8, 3) and fmap["TINY"].shares_outstanding == 12_500_000



def test_old_public_float_is_dated_by_its_measurement_not_the_newer_cover_page() -> None:
    """Finding: a year-old float (10M) next to a fresh cover page (60M shares after ATM dilution) was labelled fresh."""
    from swing_engine.data.float_data import FloatInfo, FloatSource

    payload = {"facts": {"dei": {
        "EntityPublicFloat": {"units": {"USD": [{"end": "2025-06-30", "filed": "2025-09-15", "val": 10_000_000, "accn": "a1"}]}},
        "EntityCommonStockSharesOutstanding": {"units": {"shares": [
            {"end": "2026-08-01", "filed": "2026-08-05", "val": 60_000_000, "accn": "a2"},
        ]}},
    }}}
    info = FloatInfo(symbol="DIL")
    FloatSource._apply_edgar(None, info, payload, None, 1.0)  # type: ignore[arg-type]
    assert info.float_shares == pytest.approx(10_000_000) and info.float_estimate_method == METHOD_PUBLIC_FLOAT_PRICE
    assert info.as_of == date(2025, 6, 30)  # measured date wins -> 463 days old on 2026-10-06 -> stale by age
    with_then = {"facts": {"dei": {**payload["facts"]["dei"], "EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2025-08-04", "filed": "2025-08-07", "val": 12_000_000, "accn": "a0"},
        {"end": "2026-08-01", "filed": "2026-08-05", "val": 60_000_000, "accn": "a2"},
    ]}}}}}
    adj = FloatInfo(symbol="DIL")
    FloatSource._apply_edgar(None, adj, with_then, None, 1.0)  # type: ignore[arg-type]
    assert adj.float_shares == pytest.approx(58_000_000) and adj.float_estimate_method == METHOD_PUBLIC_FLOAT_ADJ
    assert adj.as_of == date(2026, 8, 1)  # 10M then + 48M issued since; well above the 20M small-cap gate
