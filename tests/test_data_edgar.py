from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import httpx
import pandas as pd
import pytest
import respx

from swing_engine.data._common import TZ
from swing_engine.data.edgar import FORM4_COLUMNS, SEC_BASE_URL, Edgar
from tests.helpers_data import FakeClock, fixture_json, fixture_text

UA = "swing-engine test@example.com"


def _edgar() -> Edgar:
    clock = FakeClock()
    return Edgar(UA, clock=clock, sleep=clock.sleep)


def test_user_agent_must_carry_contact() -> None:
    with pytest.raises(ValueError):
        Edgar("swing-engine")


@respx.mock
def test_current_filings_parses_atom_and_sends_user_agent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == UA
        assert request.url.params["type"] == "8-K" and request.url.params["output"] == "atom"
        return httpx.Response(200, text=fixture_text("edgar_current_8k.atom"))

    route = respx.get(f"{SEC_BASE_URL}/cgi-bin/browse-edgar").mock(side_effect=handler)
    df = _edgar().current_filings("8-K", count=100)
    assert route.call_count == 1
    assert len(df) == 2  # duplicate accession dropped
    first = df.iloc[0]
    assert first["accession"] == "0001234567-24-000010" and first["form_type"] == "8-K"
    assert first["company"] == "ACME CORP" and first["cik"] == "0000123456"
    assert str(df["filed_at"].dt.tz) == TZ and first["filed_at"].strftime("%H:%M") == "09:58"
    assert "4.02" in df.iloc[1]["summary"] and df.iloc[1]["form_type"] == "8-K/A"


@respx.mock
def test_company_tickers() -> None:
    respx.get(f"{SEC_BASE_URL}/files/company_tickers.json").mock(return_value=httpx.Response(200, json=fixture_json("edgar_company_tickers.json")))
    df = _edgar().company_tickers()
    assert df["symbol"].tolist() == ["AAPL", "AMZN", "MSFT"]
    assert df.set_index("symbol").loc["AAPL", "cik"] == "0000320193"


def _fake_filing(trades: pd.DataFrame, **attrs):
    form4 = SimpleNamespace(market_trades=trades, insider_name="DOE JANE", position="Director", ticker=None)
    filing = SimpleNamespace(
        filing_date=date(2024, 9, 19), accession_number="0001-24-1", cik=123, company="ABCD Inc", ticker="ABCD",
        homepage_url="https://www.sec.gov/x", obj=lambda: form4, **attrs,
    )
    return filing


def test_form4_buys_filters_open_market_purchases(monkeypatch) -> None:
    trades = pd.DataFrame(
        {"Date": ["2024-09-18", "2024-09-18", "2024-09-17"], "Code": ["P", "S", "P"], "AcquiredDisposed": ["A", "D", "A"],
         "Shares": [5000, 100, 10], "Price": [12.1, 13.0, None]}
    )
    broken = SimpleNamespace(obj=lambda: (_ for _ in ()).throw(RuntimeError("bad xml")), accession_number="x")
    e = _edgar()
    monkeypatch.setattr(e, "_fetch_form4_filings", lambda since, until: [_fake_filing(trades), broken])
    df = e.form4_buys(date(2024, 9, 1), date(2024, 9, 30))
    assert list(df.columns) == FORM4_COLUMNS and len(df) == 2
    assert df["symbol"].tolist() == ["ABCD", "ABCD"] and df["cik"].iloc[0] == "0000000123"
    assert df["value"].iloc[1] == pytest.approx(5000 * 12.1) and pd.isna(df["value"].iloc[0])
    assert df["filed_at"].iloc[0] == pd.Timestamp("2024-09-19")  # point-in-time: filing date, not trade date
    assert df["insider"].iloc[0] == "DOE JANE" and df["insider_title"].iloc[0] == "Director"


def test_form4_buys_degrades_to_empty_when_edgartools_fails(monkeypatch) -> None:
    e = _edgar()

    def boom(since, until):
        raise ImportError("no edgartools")

    monkeypatch.setattr(e, "_fetch_form4_filings", boom)
    df = e.form4_buys("2024-09-01")
    assert df.empty and list(df.columns) == FORM4_COLUMNS
