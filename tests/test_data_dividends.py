"""data.dividends: ingest pages, ticker-on-the-day mapping, split-adjusted rates, the DivSeason rule (no look-ahead)
and the total-return copy. No network."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing_engine.data import dividends as D
from swing_engine.data._common import session_ts
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store


def div(symbol: str, ex: str, rate: float = 0.5, special: bool = False, i: int = 0) -> dict:
    return {"id": f"{symbol}-{ex}-{i}", "symbol": symbol, "ex_date": ex, "rate": rate, "special": special, "foreign": False}


def frame(rows: list[dict]) -> pd.DataFrame:
    return D.parse_page({"corporate_actions": {"cash_dividends": rows}})


def bars(symbol: str, start: str, end: str, close: float = 100.0) -> pd.DataFrame:
    days = trading_days(date.fromisoformat(start), date.fromisoformat(end))
    return pd.DataFrame({"symbol": symbol, "ts": [session_ts(d) for d in days], "open": close, "high": close,
                         "low": close, "close": close, "volume": 1e6, "vwap": close, "adj_close": close})


class Pages:
    def __init__(self, by_month: dict[str, list[list[dict]]]) -> None:
        self.by_month, self.calls = by_month, []

    def page(self, start: date, end: date, token: str | None = None) -> dict:
        self.calls.append((start, end, token))
        pages = self.by_month.get(start.strftime("%Y-%m"), [[]])
        i = int(token or 0)
        return {"corporate_actions": {"cash_dividends": pages[i]}, "next_page_token": str(i + 1) if i + 1 < len(pages) else None}


def test_ingest_pages_months_once_and_refetches_the_current_month():
    store = Store()
    client = Pages({"2016-01": [[div("AAA", "2016-01-15")], [div("BBB", "2016-01-20")]], "2016-03": [[div("AAA", "2016-03-02")]]})
    res = D.run_dividend_ingest(store, client, start=date(2016, 1, 1), today=date(2016, 3, 10))
    assert res["rows"] == 3 and res["months"] == 3 and store.count(D.TABLE) == 3
    assert client.calls[-1][:2] == (date(2016, 3, 1), date(2016, 3, 10))
    again = D.run_dividend_ingest(store, client, start=date(2016, 1, 1), today=date(2016, 3, 10))
    assert again["months_done_before"] == 2 and again["months"] == 1 and store.count(D.TABLE) == 3  # only March again


def test_rows_follow_the_security_not_the_ticker():
    d = frame([div("OLDT", "2025-03-03"), div("NEWT", "2025-03-04"), div("NEWT", "2025-09-02"), div("OLDT", "2026-03-10"),
               div("DEAD", "2020-03-02"), div("DEAD", "2022-03-02"), div("SOLO", "2025-03-03")])
    repairs = pd.DataFrame([
        {"action": "merge_duplicate", "symbol": "OLDT", "new_symbol": "NEWT", "date_to": date(2025, 5, 30), "reverted": False},
        {"action": "merge_duplicate", "symbol": "DEAD~20200630", "new_symbol": "LIVE", "date_to": date(2020, 6, 30), "reverted": False},
        {"action": "merge_duplicate", "symbol": "GONE", "new_symbol": "SOLO", "date_to": date(2030, 1, 1), "reverted": True},
    ])
    listings = pd.DataFrame([{"key": "DEAD~20211231", "ticker": "DEAD", "first_bar": date(2021, 1, 4), "last_bar": date(2022, 6, 30)}])
    got = D.store_symbols(d, repairs, listings).tolist()
    #       OLDT before the rename -> NEWT; NEWT's own row before it: another company; after: NEWT; OLDT's next owner
    assert got == ["NEWT", None, "NEWT", "OLDT", "LIVE", "DEAD~20211231", "SOLO"]


def test_rates_are_put_on_the_split_adjusted_basis():
    d = frame([div("AAPL", "2020-08-07", 0.82), div("AAPL", "2020-11-06", 0.205)]).assign(store_symbol="AAPL")
    splits = pd.DataFrame([{"symbol": "AAPL", "ex_date": date(2020, 8, 31), "ratio": 4.0}])
    assert D.split_adjusted_rates(d, splits).tolist() == pytest.approx([0.205, 0.205])


def test_div_season_follows_the_frequency_and_reads_nothing_after_the_month():
    q = [div("QTR", f"{y}-{m:02d}-10") for y, m in ((2023, 2), (2023, 5), (2023, 8), (2023, 11), (2024, 2))]
    rows = q + [div("ANN", "2023-06-15"), div("SEMI", "2023-03-15"), div("SEMI", "2023-09-15"),
                div("SPEC", "2023-06-15", special=True)] + [div("MON", f"2023-{m:02d}-05") for m in range(1, 13)]
    table = D.season_table(frame(rows).assign(store_symbol=lambda f: f["symbol"]))
    made_in = lambda s: sorted(table.loc[table["symbol"] == s, "month"] - 2023 * 12)  # noqa: E731  (0 = Jan 2023)
    # QTR: by end of April 2023 it has paid once (annual pattern: predicted 12 months on); with three or more
    # ex-months in the last 12 it is quarterly: predicted for May 2024 at the end of April 2024 (index 15)
    assert 15 in made_in("QTR") and 14 not in made_in("QTR")
    assert made_in("ANN") == [16]  # end of May 2024 -> June 2024, 12 months after its one payment
    # after one payment a semi-annual payer still looks annual; once two ex-months are on record it is predicted
    # every six months: end of Feb 2024 -> March, end of Aug 2024 -> September
    assert made_in("SEMI") == [13, 19]
    assert made_in("SPEC") == []
    # a monthly payer is left out while six or more of the last twelve months have an ex-date (its first months
    # and the months after it stops still look quarterly: frequency is read from history, not declared)
    assert not [m for m in made_in("MON") if 5 <= m <= 17]
    cut = D.season_table(frame([r for r in rows if r["ex_date"] < "2023-12-01"]).assign(store_symbol=lambda f: f["symbol"]))
    early = lambda t: set(map(tuple, t.loc[t["month"] <= 2023 * 12 + 10].to_numpy()))  # noqa: E731
    assert early(cut) == early(table)  # predictions made up to November 2023 do not need later dividends


def test_join_marks_month_end_rows_of_common_stocks_only():
    store = Store()
    store.write_bars(pd.concat([bars(s, "2024-01-02", "2024-03-15") for s in ("QTR", "FUND")]))
    rows = [div(s, d) for s in ("QTR", "FUND") for d in ("2023-02-10", "2023-05-10", "2023-08-10", "2023-11-10")]
    store.write_table(D.TABLE, frame(rows), ["id"], schema=D.SCHEMA)
    store.write_table("symbols", pd.DataFrame({"symbol": ["QTR", "FUND"], "type": ["CS", "ETF"]}), ["symbol"])
    out = D.join_dividends(store, store.read_bars()).set_index(["symbol", "ts"])[D.DIV_SEASON]
    jan_end, feb_end = session_ts("2024-01-31"), session_ts("2024-02-29")
    assert out[("QTR", jan_end)] == 1.0 and out[("QTR", feb_end)] == 0.0  # February is the predicted ex-month
    assert out[("FUND", jan_end)] == 0.0
    assert out.notna().sum() == 4 and pd.isna(out[("QTR", session_ts("2024-03-15"))])  # the panel ends mid-month


def test_total_return_copy_turns_the_ex_day_drop_into_a_flat_return():
    store = Store()
    b = bars("PAY", "2024-01-02", "2024-01-31", 100.0)
    b.loc[b["ts"] >= session_ts("2024-01-16"), ["open", "high", "low", "close", "vwap", "adj_close"]] = 99.0  # ex-day
    store.write_bars(pd.concat([b, bars("NOPE", "2024-01-02", "2024-01-31", 50.0)]))
    store.write_table(D.TABLE, frame([div("PAY", "2024-01-15", 1.0), div("PAY", "2024-01-20", 60.0, i=1)]), ["id"], schema=D.SCHEMA)
    res = D.total_return_adjust(store)  # 2024-01-15 is a holiday: the dividend lands on the 16th
    assert res["dividends"] == 1 and res["skipped"] == 1  # the $60 "dividend" on a $99 stock is not applied
    close = store.read_bars(["PAY"]).set_index("ts")["close"]
    assert close[session_ts("2024-01-12")] == pytest.approx(99.0) and close[session_ts("2024-01-16")] == 99.0
    assert store.read_bars(["NOPE"])["close"].eq(50.0).all()
    with pytest.raises(ValueError, match="already"):
        D.total_return_adjust(store)
    with pytest.raises(ValueError, match="live store"):
        D.total_return_adjust(Store(), live_path=":memory:")
