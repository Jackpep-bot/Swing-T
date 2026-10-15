"""data.intraday: session labels (early close included), resampling with no minute after a bar's close, the
resumable per-symbol month ingest (fake client, no network) and UTC anchoring for crypto."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import pytest

from swing_engine.data import intraday as I
from swing_engine.data.store import Store

NY = "America/New_York"


def minutes(symbol: str, start: str, end: str, tz: str = NY) -> pd.DataFrame:
    """One bar for every minute in [start, end); price = minutes since `start`, so aggregates are checkable."""
    ts = pd.date_range(start, end, freq="1min", tz=tz, inclusive="left").tz_convert("UTC")
    px = pd.Series(range(len(ts)), dtype="float64") + 100.0
    df = pd.DataFrame({"symbol": symbol, "ts": ts, "open": px, "high": px + 0.5, "low": px - 0.5, "close": px,
                       "volume": 10.0, "vwap": px, "trade_count": 1})
    df["session"] = I.label_sessions(df["symbol"], df["ts"])
    return df


def ny(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz=NY).tz_convert("UTC")


def test_session_labels_normal_day_early_close_and_crypto() -> None:
    df = minutes("SPY", "2024-11-27 04:00", "2024-11-27 20:00").set_index("ts")["session"]
    assert df[ny("2024-11-27 09:29")] == "pre" and df[ny("2024-11-27 09:30")] == "rth"
    assert df[ny("2024-11-27 15:59")] == "rth" and df[ny("2024-11-27 16:00")] == "post"
    early = minutes("SPY", "2024-11-29 04:00", "2024-11-29 20:00").set_index("ts")["session"]  # 13:00 close
    assert early[ny("2024-11-29 12:59")] == "rth" and early[ny("2024-11-29 13:00")] == "post"
    assert (early == "rth").sum() == 210
    assert set(minutes("SPY", "2024-11-28 10:00", "2024-11-28 10:05")["session"]) == {"closed"}  # Thanksgiving
    assert set(minutes("BTC/USD", "2024-11-28 10:00", "2024-11-28 10:05")["session"]) == {"crypto"}


def test_resample_rth_anchor_values_and_partial_last_bar() -> None:
    day = minutes("SPY", "2024-11-27 04:00", "2024-11-27 20:00")
    h4 = I.resample(day, "4h").set_index("ts")
    assert list(h4.index) == [ny(f"2024-11-27 {t}") for t in ("01:30", "05:30", "09:30", "13:30", "16:00", "17:30")]
    assert list(h4["session"]) == ["pre", "pre", "rth", "rth", "post", "post"]
    assert h4.loc[ny("2024-11-27 13:30"), "ts_close"] == ny("2024-11-27 16:00")  # partial: 150 minutes
    assert h4.loc[ny("2024-11-27 17:30"), "ts_close"] == ny("2024-11-27 20:00")
    first = h4.loc[ny("2024-11-27 09:30")]  # minutes 330..569 of the day
    assert (first["open"], first["close"], first["high"], first["low"]) == (430.0, 669.0, 669.5, 429.5)
    assert first["volume"] == 2400.0 and first["trade_count"] == 240 and first["vwap"] == pytest.approx(549.5)
    m5 = I.resample(day, "5m")
    assert len(m5) == 192 and ny("2024-11-27 09:30") in set(m5["ts"])
    with pytest.raises(ValueError):
        I.resample(day, "3m")


def test_resample_early_close_cuts_bars_at_1300() -> None:
    h1 = I.resample(minutes("SPY", "2024-11-29 09:30", "2024-11-29 14:30"), "1h")
    assert list(h1["ts"]) == [ny(f"2024-11-29 {t}") for t in ("09:30", "10:30", "11:30", "12:30", "13:00", "13:30")]
    assert list(h1["ts_close"])[3:5] == [ny("2024-11-29 13:00"), ny("2024-11-29 13:30")]
    assert list(h1["session"]) == ["rth"] * 4 + ["post"] * 2


@pytest.mark.parametrize("tf", ["2m", "5m", "15m", "30m", "1h", "4h"])
def test_resample_never_uses_a_minute_after_the_close(tf: str) -> None:
    day = pd.concat([minutes("SPY", "2024-11-27 04:00", "2024-11-27 20:00"),
                     minutes("BTC/USD", "2024-11-27 00:00", "2024-11-28 00:00", tz="UTC")], ignore_index=True)
    day = day[day["ts"].dt.minute % 7 != 3]  # quiet minutes have no bar
    full = I.resample(day, tf, as_of=pd.Timestamp("2024-11-29", tz="UTC"))  # the day is over: all complete
    for sym, cut in (("SPY", ny("2024-11-27 11:17")), ("BTC/USD", pd.Timestamp("2024-11-27 11:17", tz="UTC"))):
        one, bars = day[day["symbol"] == sym], full[full["symbol"] == sym]
        for r in bars.itertuples():  # every bar is exactly the minutes in [ts, ts_close) of its own session
            inside = one[(one["ts"] >= r.ts) & (one["ts"] < r.ts_close) & (one["session"] == r.session)]
            assert r.close == inside["close"].iloc[-1] and r.volume == inside["volume"].sum()
        assert bars["volume"].sum() == one["volume"].sum()  # each minute lands in exactly one bar
        # live view: with data only up to `cut`, the bars shown are the finished ones and they never change later
        live = I.resample(one[one["ts"] < cut], tf, as_of=cut)
        assert (live["ts_close"] <= cut).all()
        pd.testing.assert_frame_equal(live, bars[bars["ts_close"] <= cut].reset_index(drop=True))


def test_incomplete_last_bar_is_held_back_until_data_reaches_its_close() -> None:
    part = minutes("SPY", "2024-11-27 09:30", "2024-11-27 09:44")  # last minute 09:43
    assert list(I.resample(part, "5m")["ts"]) == [ny("2024-11-27 09:30"), ny("2024-11-27 09:35")]
    assert len(I.resample(minutes("SPY", "2024-11-27 09:30", "2024-11-27 09:45"), "5m")) == 3


def test_crypto_is_utc_anchored() -> None:
    h4 = I.resample(minutes("BTC/USD", "2024-11-27 22:10", "2024-11-28 09:00", tz="UTC"), "4h")
    assert list(h4["ts"]) == [pd.Timestamp(t, tz="UTC") for t in
                              ("2024-11-27 20:00", "2024-11-28 00:00", "2024-11-28 04:00")]  # 08:00 bar incomplete
    assert set(h4["session"]) == {"crypto"} and h4["volume"].iloc[0] == 1100.0


def api_bar(ts: str, px: float = 1.0) -> dict[str, Any]:
    return {"t": ts, "o": px, "h": px, "l": px, "c": px, "v": 5, "vw": px, "n": 2}


class FakeBars:
    feed = "sip"

    def __init__(self, pages: dict[tuple[str, str], list[list[dict[str, Any]]]], fail: set[str] | None = None):
        self.pages, self.fail, self.calls = pages, fail or set(), []

    def page(self, symbol: str, start: datetime, end: datetime, token: str | None = None) -> dict[str, Any]:
        month = start.strftime("%Y-%m")
        self.calls.append((symbol, month, token, end))
        if month in self.fail:
            raise RuntimeError("boom")
        chunks = self.pages.get((symbol, month), [])
        i = int(token or 0)
        return {"bars": {symbol: chunks[i]} if chunks else {},
                "next_page_token": str(i + 1) if i + 1 < len(chunks) else None}


def test_ingest_paginates_resumes_and_refreshes_the_current_month() -> None:
    store, now = Store(), datetime(2024, 3, 10, 12)
    pages = {("SPY", "2024-01"): [[api_bar("2024-01-02T14:30:00Z")], [api_bar("2024-01-02T14:31:00Z")]],
             ("SPY", "2024-02"): [[api_bar("2024-02-01T21:00:00Z")]],
             ("BTC/USD", "2024-02"): [[api_bar("2024-02-03T00:00:00Z")]]}
    client = FakeBars(pages, fail={"2024-03"})
    res = I.run_intraday_ingest(store, client, symbols=["SPY", "btc/usd"], start=date(2024, 1, 1), now=now)
    assert res["rows"] == 4 and res["pages"] == 5 and res["failed"] == 2 and res["months"] == 4
    bars = store.read_table(I.TABLE).set_index("ts")
    assert bars.loc[pd.Timestamp("2024-01-02T14:30:00Z"), "session"] == "rth"
    assert bars.loc[pd.Timestamp("2024-02-01T21:00:00Z"), "session"] == "post"
    assert bars.loc[pd.Timestamp("2024-02-03T00:00:00Z"), "session"] == "crypto"

    client2 = FakeBars({("SPY", "2024-03"): [[api_bar("2024-03-05T15:00:00Z")]]})
    res2 = I.run_intraday_ingest(store, client2, symbols=["SPY", "BTC/USD"], start=date(2024, 1, 1), now=now)
    assert {c[1] for c in client2.calls} == {"2024-03"} and res2["months_done_before"] == 4  # finished: no refetch
    assert client2.calls[0][3] == datetime(2024, 3, 10, 11, 44)  # never asks inside the 15-minute SIP delay
    meta = store.read_table(I.META_TABLE).set_index(["symbol", "month"])
    assert meta.loc[("SPY", "2024-03"), "status"] == "partial" and meta.loc[("SPY", "2024-01"), "status"] == "ok"

    client3 = FakeBars({})
    I.run_intraday_ingest(store, client3, symbols=["SPY", "BTC/USD"], start=date(2024, 1, 1), now=now, months=1)
    assert [(c[0], c[1]) for c in client3.calls] == [("SPY", "2024-03"), ("BTC/USD", "2024-03")]  # partial again
    assert I.run_intraday_ingest(store, FakeBars({}), symbols=["BTC/USD"], start=date(2016, 1, 1),
                                 now=datetime(2021, 2, 20), months=0)["months"] == 0


def test_client_routes_stock_and_crypto_requests() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []

    class FakeHttp:
        def get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
            seen.append((url, params))
            return {"bars": {}}

    client = I.AlpacaMinuteBars("", "", http=FakeHttp())  # type: ignore[arg-type]
    client.page("SPY", datetime(2024, 1, 1), datetime(2024, 2, 1))
    client.page("BTC/USD", datetime(2024, 1, 1), datetime(2024, 2, 1), "tok")
    assert seen[0][0] == I.STOCK_BARS_URL and seen[0][1]["feed"] == "sip" and seen[0][1]["adjustment"] == "split"
    assert seen[0][1]["end"] == "2024-01-31T23:59:59Z" and seen[0][1]["limit"] == 10_000
    assert seen[1][0] == I.CRYPTO_BARS_URL and "feed" not in seen[1][1] and seen[1][1]["page_token"] == "tok"


def test_read_bars_resamples_on_read_and_hides_the_unfinished_bar() -> None:
    store = Store()
    store.write_table(I.TABLE, minutes("SPY", "2024-11-27 09:00", "2024-11-27 11:07"), I.KEYS, schema=I.SCHEMA)
    out = I.read_bars(store, "spy", "30m", ny("2024-11-27 09:30"), ny("2024-11-27 16:00"))
    assert list(out["ts"]) == [ny(f"2024-11-27 {t}") for t in ("09:30", "10:00", "10:30")]  # 11:00 bar not done
    assert out["open"].iloc[0] == 130.0 and out["close"].iloc[0] == 159.0
    assert I.read_bars(store, "QQQ", "30m", "2024-11-27", "2024-11-28").empty
