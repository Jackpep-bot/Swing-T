from __future__ import annotations

from datetime import date

import httpx
import pandas as pd
import respx

from swing_engine.data._common import TZ
from swing_engine.data.quiver import CONGRESS_COLUMNS, INSIDER_COLUMNS, QUIVER_BASE_URL, Quiver
from tests.helpers_data import FakeClock, fixture_json


def _quiver(tmp_path) -> Quiver:
    clock = FakeClock()
    return Quiver("secret", cache_dir=tmp_path, clock=clock, sleep=clock.sleep)


@respx.mock
def test_insiders_point_in_time_and_lookahead_dropped(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        assert request.url.params["ticker"] == "ABCD" and request.url.params["page"] == "1"
        return httpx.Response(200, json=fixture_json("quiver_insiders.json"))

    route = respx.get(f"{QUIVER_BASE_URL}/beta/live/insiders").mock(side_effect=handler)
    df = _quiver(tmp_path).insiders("abcd", since=date(2024, 9, 1))
    assert route.call_count == 1  # fewer rows than page_size ends pagination
    assert list(df.columns[: len(INSIDER_COLUMNS)]) == INSIDER_COLUMNS
    assert len(df) == 2  # the row without fileDate/uploaded has no point-in-time stamp and is dropped
    assert not {"ExcessReturn", "PriceChange"} & set(df.columns)
    row = df.set_index("symbol").loc["ABCD"]
    assert str(df["pit_ts"].dt.tz) == TZ
    assert row["pit_ts"] == pd.Timestamp("2024-09-19T17:00:00Z").tz_convert(TZ)  # max(filed, uploaded)
    assert row["transaction_date"] == date(2024, 9, 18) and row["transaction_code"] == "P"
    buys = Quiver.normalize_insiders(pd.DataFrame(fixture_json("quiver_insiders.json")), buys_only=True)
    assert buys["symbol"].tolist() == ["ABCD"]


@respx.mock
def test_congress_requires_report_date(tmp_path) -> None:
    respx.get(f"{QUIVER_BASE_URL}/beta/live/congresstrading").mock(return_value=httpx.Response(200, json=fixture_json("quiver_congress.json")))
    df = _quiver(tmp_path).congress()
    assert list(df.columns[: len(CONGRESS_COLUMNS)]) == CONGRESS_COLUMNS
    assert df["symbol"].tolist() == ["NVDA"]  # null ReportDate row dropped
    row = df.iloc[0]
    assert row["report_date"] == date(2024, 7, 3) and row["transaction_date"] == date(2024, 6, 24)
    assert row["pit_ts"].date() == date(2024, 7, 3) and row["amount_low"] == 1000001.0
    assert "SPYChange" not in df.columns and "ExcessReturn" not in df.columns
    assert _quiver(tmp_path).congress(since=date(2024, 8, 1)).empty


@respx.mock
def test_congress_per_ticker_path_and_pagination(tmp_path) -> None:
    page = fixture_json("quiver_congress.json")
    q = _quiver(tmp_path)
    q.page_size = 2
    route = respx.get(f"{QUIVER_BASE_URL}/beta/historical/congresstrading/NVDA").mock(
        side_effect=[httpx.Response(200, json=page), httpx.Response(200, json=[])]
    )
    df = q.congress("nvda")
    assert route.call_count == 2 and len(df) == 1
