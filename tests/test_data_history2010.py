"""data.history2010: the 2010-2015 research-store extension, offline (fake Tiingo rows, an in-memory Store)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing_engine.data import history2010 as H
from swing_engine.data._common import session_ts
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store

FORM_IDX = """Description:           Master Index of EDGAR Dissemination Feed by Form Type
Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------------
10-K        APPLE INC                                                     320193      2012-10-31  edgar/data/320193/0001193125-12-444068.txt
10-K/A      DEAD CO INC                                                   1111        2011-03-15  edgar/data/1111/0000001111-11-000001.txt
8-K         APPLE INC                                                     320193      2012-10-30  edgar/data/320193/0001193125-12-1.txt
"""


def test_form_index_floats_and_candidates():
    idx = H.parse_form_index(FORM_IDX)
    assert idx["form"].tolist() == ["10-K", "10-K/A"] and idx["cik"].tolist() == ["0000320193", "0000001111"]
    assert idx["company"].tolist() == ["APPLE INC", "DEAD CO INC"] and idx["filed"].iloc[0] == date(2012, 10, 31)
    payload = {"facts": {"dei": {"EntityPublicFloat": {"units": {"USD": [
        {"end": "2011-03-25", "val": 3.0e11, "filed": "2011-10-26"}, {"end": "2012-03-30", "val": 5.0e11, "filed": "2012-10-31"}]}}}}}
    f = H.public_floats(payload, "320193")
    assert len(f) == 2 and f["cik"].iloc[0] == "0000320193"
    floats = pd.concat([f, pd.DataFrame({"cik": ["0000000002", "0000000003"], "period_end": None,
                                         "filed": [date(2011, 6, 1), date(2011, 6, 1)], "value": [4.0e11, 1.0e6]})])
    c = H.candidates(floats, top=2).set_index("cik")
    assert set(c.index) == {"0000320193", "0000000002"} and c.loc["0000320193", "best_rank"] == 1


def test_instance_ticker_and_matching():
    assert H.instance_ticker(["aapl-20120929.xml", "aapl-20120929_cal.xml", "R1.htm"]) == "AAPL"
    assert H.instance_ticker(["d123.htm"]) is None
    spans = pd.DataFrame({"ticker": ["DEAD", "REUSE", "REUSE"], "assetType": "Stock",
                          "startDate": [date(2005, 1, 3), date(2000, 1, 3), date(2015, 1, 2)],
                          "endDate": [date(2011, 9, 30), date(2012, 1, 3), date(2026, 10, 13)]})
    assert H.match_ticker("DEAD", date(2009, 3, 1), date(2011, 3, 15), spans) == ("DEAD", "matched")
    assert H.match_ticker("REUSE", date(2009, 3, 1), date(2011, 3, 15), spans)[0] is None
    assert H.match_ticker("DEAD", date(2009, 3, 1), date(2014, 3, 15), spans)[0] is None  # ends long before


def _raw(days, close, *, div=None, split=None):
    rows = pd.DataFrame({"date": [f"{d}T00:00:00.000Z" for d in days], "open": close, "high": close, "low": close,
                         "close": close, "volume": 1000.0, "adjClose": close, "divCash": 0.0, "splitFactor": 1.0})
    for d, v in (div or {}).items():
        rows.loc[rows["date"].str.startswith(str(d)), "divCash"] = v
    for d, v in (split or {}).items():
        rows.loc[rows["date"].str.startswith(str(d)), "splitFactor"] = v
    return rows


def test_extend_scales_live_names_keys_dead_ones_and_rejects_a_bad_seam():
    store = Store()
    live_days = trading_days("2016-01-04", "2016-06-30")
    store.write_bars(pd.DataFrame({"symbol": "AAA", "ts": [session_ts(d) for d in live_days], "open": 50.0,
                                   "high": 50.0, "low": 50.0, "close": 50.0, "volume": 2000.0, "vwap": None,
                                   "adj_close": 50.0}))
    store.write_bars(pd.DataFrame({"symbol": "BBB", "ts": [session_ts(d) for d in live_days], "open": 50.0,
                                   "high": 50.0, "low": 50.0, "close": 50.0, "volume": 2000.0, "vwap": None,
                                   "adj_close": 50.0}))
    aaa_days = trading_days("2015-11-02", "2016-06-30")
    dead_days = trading_days("2010-01-04", "2012-03-30")
    split_day = date(2011, 1, 3)
    dead_close = [20.0 if d < split_day else 10.0 for d in dead_days]
    bbb = [100.0 + (i % 7) * 5 for i in range(len(aaa_days))]  # not one company: the ratio wanders
    rows = {"AAA": _raw(aaa_days, 100.0, div={date(2015, 12, 10): 1.0}),
            "ZZZ": _raw(dead_days, dead_close, split={split_day: 2.0}), "BBB": _raw(aaa_days, bbb)}
    payload = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"end": "2010-12-31", "val": 1.0e9, "filed": "2011-03-15", "form": "10-K", "accn": "0000001111-11-000001",
         "fy": 2010, "fp": "FY"}]}}}}}
    names = [H.Name("0000000001", "AAA", "AAA"), H.Name("0000001111", "ZZZ"), H.Name("0000000002", "BBB", "BBB")]
    rep = H.extend(store, lambda t, a, b: rows[t], names, facts_for=lambda cik: payload)
    assert "BBB" in rep.rejected and "seam" in rep.rejected["BBB"]
    assert rep.seams["AAA"][0] == pytest.approx(0.5) and rep.written["AAA"] == len([d for d in aaa_days if d < live_days[0]])
    aaa = store.read_bars(["AAA"], date(2015, 1, 1), date(2016, 12, 31))
    assert aaa["close"].max() == pytest.approx(50.0) and len(aaa) == len(aaa_days)  # no duplicate bars on the overlap
    key = "ZZZ~20120330"
    zzz = store.read_bars([key], date(2010, 1, 1), date(2012, 12, 31))
    assert len(zzz) == len(dead_days) and zzz["close"].max() == pytest.approx(10.0)  # split-adjusted in the span
    splits = store.read_table("splits")
    assert splits.loc[splits["symbol"] == key, "ratio"].tolist() == [2.0]
    div = store.read_table("dividends")
    assert div.loc[div["symbol"] == "AAA", "rate"].tolist() == [1.0]
    assert store.read_table("listings")["key"].tolist() == [key]
    fund = store.read_table("fundamentals")
    assert set(fund["symbol"]) == {key} and store.count("fundamental_events") >= 1
