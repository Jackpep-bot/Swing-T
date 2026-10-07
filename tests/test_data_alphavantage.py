from __future__ import annotations

from datetime import date

import httpx
import pandas as pd
import pytest
import respx

from swing_engine.data.alphavantage import (
    ALPHAVANTAGE_URL,
    EARNINGS_COLUMNS,
    earnings_calendar,
    parse_earnings_csv,
)
from tests.helpers_data import FakeClock, fixture_text


def test_parse_csv_drops_rows_without_report_date() -> None:
    df = parse_earnings_csv(fixture_text("alphavantage_earnings.csv"))
    assert list(df.columns) == EARNINGS_COLUMNS and len(df) == 2
    assert df["symbol"].tolist() == ["MSFT", "AAPL"]  # sorted by report_date
    assert df["report_date"].iloc[1] == date(2024, 10, 31)
    assert pd.isna(df["estimate"].iloc[0]) and df["estimate"].iloc[1] == 1.53
    assert parse_earnings_csv("").empty


@respx.mock
def test_earnings_calendar_request_and_json_error() -> None:
    clock = FakeClock()

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.params
        assert p["function"] == "EARNINGS_CALENDAR" and p["horizon"] == "3month" and p["apikey"] == "k"
        if p.get("symbol") == "THROTTLED":
            return httpx.Response(200, json={"Information": "rate limit"})
        return httpx.Response(200, text=fixture_text("alphavantage_earnings.csv"))

    respx.get(ALPHAVANTAGE_URL).mock(side_effect=handler)
    df = earnings_calendar("k", sleep=clock.sleep)
    assert len(df) == 2
    assert earnings_calendar("k", symbol="throttled", sleep=clock.sleep).empty
    with pytest.raises(ValueError):
        earnings_calendar("k", horizon="2month")
    with pytest.raises(ValueError):
        earnings_calendar("")
