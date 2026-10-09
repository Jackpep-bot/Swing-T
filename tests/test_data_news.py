"""data.news: page parsing, the resumable month ingest (fake client, no network) and the point-in-time 24h-before-
close count, including coverage gaps and the early close."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.data import news as N
from swing_engine.data.store import Store

TZ = "America/New_York"


def art(i: int, created: str, *symbols: str) -> dict[str, Any]:
    return {"id": i, "created_at": created, "updated_at": "2030-01-01T00:00:00Z", "symbols": list(symbols),
            "headline": "x", "source": "benzinga"}


def test_parse_news_page_one_row_per_symbol_keyed_on_created_at() -> None:
    df = N.parse_news_page({"news": [art(1, "2024-03-04T20:59:00Z", "aapl", "MSFT"), art(2, "2024-03-04T21:00:00Z")]})
    assert list(df["symbol"]) == ["AAPL", "MSFT"] and set(df["id"]) == {1}
    assert df["published_at"].iloc[0] == pd.Timestamp("2024-03-04T20:59:00Z")
    assert "headline" not in df.columns


class FakeNews:
    def __init__(self, pages: dict[str, list[dict[str, Any]]], fail: set[str] | None = None) -> None:
        self.pages, self.fail, self.calls = pages, fail or set(), []

    def page(self, start: datetime, end: datetime, token: str | None = None) -> dict[str, Any]:
        month = start.strftime("%Y-%m")
        self.calls.append((month, token, end))
        if month in self.fail:
            raise RuntimeError("boom")
        chunks = self.pages.get(month, [])
        i = int(token or 0)
        return {"news": chunks[i] if chunks else [], "next_page_token": str(i + 1) if i + 1 < len(chunks) else None}


def test_run_news_ingest_paginates_resumes_and_marks_partial() -> None:
    store = Store()
    pages = {"2024-01": [[art(1, "2024-01-02T15:00:00Z", "AAA")], [art(2, "2024-01-03T15:00:00Z", "AAA", "BBB")]],
             "2024-02": [[art(3, "2024-02-05T15:00:00Z", "AAA")]]}
    client = FakeNews(pages, fail={"2024-03"})
    res = N.run_news_ingest(store, client, start=datetime(2024, 1, 1).date(), now=datetime(2024, 3, 10, 12))
    assert res["rows"] == 4 and res["pages"] == 3 and res["failed"] == 1
    meta = store.read_table(N.META_TABLE).set_index("month")
    assert meta.loc["2024-01", "status"] == "ok" and meta.loc["2024-03", "status"] == "error"

    client2 = FakeNews({"2024-03": [[art(4, "2024-03-05T15:00:00Z", "AAA")]]})
    res2 = N.run_news_ingest(store, client2, start=datetime(2024, 1, 1).date(), now=datetime(2024, 3, 10, 12))
    assert {c[0] for c in client2.calls} == {"2024-03"} and res2["months_done_before"] == 2
    meta = store.read_table(N.META_TABLE).set_index("month")
    assert meta.loc["2024-03", "status"] == "partial"  # month still running: refetched next time
    assert client2.calls[0][2] == datetime(2024, 3, 10, 12)  # never asks for the future


def idx(symbol: str, *days: str) -> pd.DataFrame:
    return pd.DataFrame({"symbol": symbol, "ts": [pd.Timestamp(d).tz_localize(TZ) for d in days]})


def test_news_count_is_the_24h_before_the_close() -> None:
    # 2024-03-05 close = 21:00Z (EST). (2024-03-04 21:00Z, 2024-03-05 21:00Z] counts for 03-05.
    arts = N.parse_news_page({"news": [
        art(1, "2024-03-04T21:00:00Z", "AAA"),  # exactly 24h before: excluded (belongs to 03-04's window)
        art(2, "2024-03-04T21:00:01Z", "AAA"),
        art(3, "2024-03-05T20:59:59Z", "AAA"),
        art(4, "2024-03-05T21:00:01Z", "AAA"),  # after the close: tomorrow's
        art(5, "2024-03-05T12:00:00Z", "BBB"),
    ]})
    f = N.news_features(arts, idx("AAA", "2024-03-04", "2024-03-05", "2024-03-06"))
    assert list(f["news_count_1d"]) == [1.0, 2.0, 1.0]
    assert list(f["news_flag_1d"]) == [1.0, 1.0, 1.0]
    quiet = N.news_features(arts, idx("CCC", "2024-03-05"))
    assert quiet["news_count_1d"].iloc[0] == 0 and quiet["news_flag_1d"].iloc[0] == 0


def test_early_close_window_and_coverage_gaps() -> None:
    # 2024-11-29 (day after Thanksgiving) closes at 13:00 ET = 18:00Z; a 14:00 ET article is next session's
    arts = N.parse_news_page({"news": [art(1, "2024-11-29T19:00:00Z", "AAA")]})
    f = N.news_features(arts, idx("AAA", "2024-11-29", "2024-12-02"), covered={"2024-11": None, "2024-12": None})
    assert list(f["news_count_1d"]) == [0.0, 0.0]  # 12-02 window starts 12-01 21:00Z: the article is older
    g = N.news_features(arts, idx("AAA", "2024-11-29", "2024-12-02"), covered={"2024-11": None})
    assert g["news_count_1d"].iloc[0] == 0 and np.isnan(g["news_flag_1d"].iloc[1])  # December not ingested
    part = N.news_features(arts, idx("AAA", "2024-11-27", "2024-11-29"),
                           covered={"2024-11": datetime(2024, 11, 28, 12)})
    assert part["news_flag_1d"].iloc[0] == 0.0  # 11-27 closes before the fetch: covered, no news
    assert np.isnan(part["news_flag_1d"].iloc[1])  # closes after the partial fetch


def test_join_news_no_op_without_table_and_joins_with_one() -> None:
    panel = idx("AAA", "2024-03-05").assign(close=1.0)
    assert N.join_news(Store(), panel) is panel
    store = Store()
    N.run_news_ingest(store, FakeNews({"2024-03": [[art(1, "2024-03-05T15:00:00Z", "AAA")]]}),
                      start=datetime(2024, 3, 1).date(), end=datetime(2024, 3, 31).date(),
                      now=datetime(2024, 4, 2))
    out = N.join_news(store, panel)
    assert out["news_count_1d"].iloc[0] == 1 and out["news_flag_1d"].iloc[0] == 1 and "close" in out
