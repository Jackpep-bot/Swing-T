"""data.edgar earnings 8-K parsing (submissions JSON) and the acceptance-time decode. No network: respx + fixtures
under tests/fixtures/edgar."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest
import respx

from swing_engine.data._common import TZ
from swing_engine.data.edgar import (
    SEC_DATA_BASE_URL,
    Edgar,
    _acceptance_ts,
    earnings_session,
    parse_submissions,
)
from tests.helpers_data import FakeClock

EDGAR_FIXTURES = Path(__file__).parent / "fixtures" / "edgar"
UA = "swing-engine test@example.com"
CIK = "0000123456"


def load(name: str) -> dict:
    return json.loads((EDGAR_FIXTURES / name).read_text(encoding="utf-8"))


def _edgar() -> Edgar:
    clock = FakeClock()
    return Edgar(UA, clock=clock, sleep=clock.sleep)


def et(text: str) -> pd.Timestamp:
    return pd.Timestamp(text).tz_localize(TZ)


@pytest.mark.parametrize(
    ("raw", "eastern"),
    [
        ("2026-07-29T20:04:53.000Z", "2026-07-29 16:04:53"),  # MSFT, EDT: UTC - 4h
        ("2026-01-28T21:04:38.000Z", "2026-01-28 16:04:38"),  # MSFT, EST: UTC - 5h
        ("2026-07-31T00:30:28.000Z", "2026-07-30 20:30:28"),  # AAPL: next UTC day, still the filing date in ET
        ("2025-07-24T12:30:00.000Z", "2025-07-24 08:30:00"),  # pre-market
    ],
)
def test_acceptance_ts_is_utc(raw: str, eastern: str) -> None:
    assert _acceptance_ts(raw) == et(eastern)


def test_acceptance_ts_blank_is_nat() -> None:
    assert pd.isna(_acceptance_ts("")) and pd.isna(_acceptance_ts(None))


@pytest.mark.parametrize(
    ("accepted", "session"),
    [
        ("2025-07-24 08:30", date(2025, 7, 24)),  # pre-market: same session
        ("2025-07-24 15:59", date(2025, 7, 24)),  # intraday: that close reacts
        ("2025-07-24 16:00", date(2025, 7, 25)),  # at the close: next session
        ("2025-07-24 17:30", date(2025, 7, 25)),
        ("2025-07-25 18:00", date(2025, 7, 28)),  # Friday evening -> Monday
        ("2025-07-26 10:00", date(2025, 7, 28)),  # Saturday
        ("2025-11-28 13:30", date(2025, 12, 1)),  # day after Thanksgiving closes 13:00
    ],
)
def test_earnings_session(accepted: str, session: date) -> None:
    assert earnings_session(et(accepted)) == session


def test_real_aapl_rows_map_to_next_session() -> None:
    """Shapes copied from data.sec.gov/submissions/CIK0000320193.json (2026-10-07): after-close filings."""
    df = parse_submissions(load("submissions_aapl_8k_sample.json"), ["AAPL"])
    assert list(df["accepted_at"]) == [et("2026-01-29 21:30:33"), et("2026-07-30 20:30:28")]
    assert list(df["session"]) == [date(2026, 1, 30), date(2026, 7, 31)]
    assert (df["accepted_at"].dt.date == df["filing_date"]).all()  # acceptance day matches EDGAR's filing date


def test_parse_submissions_keeps_only_8k_item_202() -> None:
    df = parse_submissions(load("submissions_CIK0000123456.json"), ["acme"], CIK)
    assert list(df["accession"]) == [
        "0000123456-25-000011", "0000123456-25-000022", "0000123456-25-000030", "0000123456-26-000004",
    ]  # 5.02-only 8-K, 8-K/A, 10-Q, Form 4 and the row without an acceptance time are dropped
    assert set(df["symbol"]) == {"ACME"} and set(df["cik"]) == {CIK} and set(df["form"]) == {"8-K"}
    assert str(df["accepted_at"].dt.tz) == TZ
    by_acc = df.set_index("accession")
    assert by_acc.loc["0000123456-25-000011", "session"] == date(2025, 4, 25)  # 16:05 ET -> next session
    assert by_acc.loc["0000123456-25-000022", "session"] == date(2025, 7, 24)  # 08:30 ET -> same session
    assert by_acc.loc["0000123456-25-000030", "session"] == date(2025, 10, 24)
    # 17:45 ET Thursday: EDGAR dates it Friday; the reaction session is Friday, never Thursday
    assert by_acc.loc["0000123456-26-000004", "accepted_at"] == et("2026-02-05 17:45")
    assert by_acc.loc["0000123456-26-000004", "filing_date"] == date(2026, 2, 6)
    assert by_acc.loc["0000123456-26-000004", "session"] == date(2026, 2, 6)
    # point-in-time: no row reacts before it was accepted
    assert all(pd.Timestamp(s).tz_localize(TZ) >= a.normalize() for s, a in zip(df["session"], df["accepted_at"], strict=True))


def test_session_is_floored_at_filing_date() -> None:
    payload = {"filings": {"recent": {
        "form": ["8-K"], "items": ["2.02"], "accessionNumber": ["x"],
        "acceptanceDateTime": ["2025-07-24T16:30:00.000Z"],  # 12:30 ET Thursday (intraday)
        "filingDate": ["2025-07-25"],  # but EDGAR dated it Friday
    }}}
    assert parse_submissions(payload, ["A"], "1").loc[0, "session"] == date(2025, 7, 25)


def test_parse_submissions_one_row_per_share_class() -> None:
    df = parse_submissions(load("submissions_CIK0000123456.json"), ["ACME", "ACME.B"], CIK)
    assert len(df) == 8 and df.groupby("symbol").size().to_dict() == {"ACME": 4, "ACME.B": 4}


def test_parse_submissions_empty_payload() -> None:
    assert parse_submissions({}, ["A"]).empty


@respx.mock
def test_earnings_dates_reads_older_pages_and_sends_user_agent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == UA
        name = request.url.path.rsplit("/", 1)[-1]
        fixture = "submissions_CIK0000123456.json" if name == f"CIK{CIK}.json" else name
        return httpx.Response(200, json=load(fixture))

    route = respx.get(url__startswith=f"{SEC_DATA_BASE_URL}/submissions/").mock(side_effect=handler)
    df = _edgar().earnings_dates("123456", ["ACME"])
    assert route.call_count == 2
    assert list(df["session"]) == [
        date(2024, 10, 25), date(2025, 2, 7), date(2025, 4, 25), date(2025, 7, 24), date(2025, 10, 24), date(2026, 2, 6),
    ]


@respx.mock
def test_unknown_cik_is_empty_not_an_error() -> None:
    respx.get(url__startswith=f"{SEC_DATA_BASE_URL}/").mock(return_value=httpx.Response(404))
    edgar = _edgar()
    assert edgar.earnings_dates("999", ["ZZZ"]).empty
    assert edgar.companyfacts("999") is None
