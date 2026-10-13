"""data.b5_events: the CEO/CFO purchase value on the session after the filing date, the distress / 5.02 8-K clocks,
the reverse-split clock, and the store join (table by table, unchanged without tables). No network."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.data import b5_events as B5
from swing_engine.data.calendar import trading_days
from swing_engine.data.filings import EIGHTK_TABLE
from swing_engine.data.fundamentals import SPLITS_TABLE
from swing_engine.data.insiders import TRADE_KEYS, TRADES_TABLE
from swing_engine.data.store import Store

TZ = "America/New_York"
DAYS = trading_days("2024-03-01", "2024-03-28")


def index(symbols: tuple[str, ...] = ("AAA",)) -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(TZ)
    return pd.concat([pd.DataFrame({"symbol": s, "ts": ts}) for s in symbols], ignore_index=True)


def trade(n: int, filed: str, title: str, value: float, *, code: str = "P", officer: bool = True, owner: str = "1",
          symbol: str = "AAA", trans: str | None = None) -> dict:
    return {"symbol": symbol, "cik": "9", "accession": f"acc-{n}", "trans_id": trans or f"t{n}",
            "filing_date": date.fromisoformat(filed), "transaction_date": date.fromisoformat(filed), "owner_cik": owner,
            "owner_name": "x", "is_director": False, "is_officer": officer, "officer_title": title, "is_ten_pct": False,
            "code": code, "shares": 1.0, "price": value, "value": value}


TRADES = pd.DataFrame([
    trade(1, "2024-03-07", "Chief Executive Officer", 20_000.0),
    trade(2, "2024-03-07", "EVP, CFO", 10_000.0, owner="2"),
    trade(3, "2024-03-07", "General Counsel", 99_000.0, owner="3"),  # not CEO / CFO
    trade(4, "2024-03-07", "CEO", 99_000.0, code="S"),  # a sale
    trade(5, "2024-03-07", "CEO", 99_000.0, officer=False, owner="4"),  # title without the officer flag
    trade(6, "2024-03-15", "President and CEO", 50_000.0, owner="5"),  # a Friday: visible Monday 03-18
    trade(6, "2024-03-15", "President and CEO", 50_000.0, owner="6", trans="t6"),  # joint filer, same transaction
    trade(7, "2024-03-20", "Chief Financial Officer", 70_000.0, owner="7"),  # routine buyer (label below)
])
LABELS = pd.Series(["opportunistic"] * 7 + ["routine"])


def by_day(frame: pd.DataFrame, col: str) -> dict[date, float]:
    return dict(zip(frame["ts"].dt.date, frame[col], strict=True))


def test_ceo_cfo_value_lands_the_session_after_the_filing_date() -> None:
    f = B5.ceo_cfo_features(TRADES, index(), LABELS)
    total = by_day(f, "ceo_cfo_buy_value")
    assert total[date(2024, 3, 8)] == 30_000.0 and total[date(2024, 3, 7)] == 0.0  # never on the filing date itself
    assert by_day(f, "ceo_buy_value")[date(2024, 3, 8)] == 20_000.0
    assert by_day(f, "cfo_buy_value")[date(2024, 3, 8)] == 10_000.0
    assert total[date(2024, 3, 18)] == 50_000.0  # the joint filer's copy is not counted twice
    assert total[date(2024, 3, 21)] == 0.0 and sum(total.values()) == 80_000.0  # the routine buyer is dropped
    assert B5.ceo_cfo_features(TRADES.iloc[0:0], index())["ceo_cfo_buy_value"].eq(0.0).all()


EIGHTK = pd.DataFrame({
    "symbol": "AAA", "accession": ["a", "b", "c", "d"], "form": ["8-K", "8-K/A", "8-K", "8-K"],
    "session": [date(2024, 3, 6), date(2024, 3, 11), date(2024, 3, 12), date(2024, 3, 19)],
    "items": ["3.01,9.01", "1.03", "5.02", "2.02,9.01"],
})
SPLITS = pd.DataFrame({"symbol": ["aaa", "AAA"], "ex_date": [date(2024, 3, 13), date(2024, 3, 20)], "ratio": [0.1, 4.0]})


def test_eightk_and_reverse_split_clocks() -> None:
    f = B5.eightk_event_features(EIGHTK, index())
    distress, left = by_day(f, "days_since_8k_distress"), by_day(f, "days_since_8k_502")
    assert np.isnan(distress[date(2024, 3, 5)]) and distress[date(2024, 3, 6)] == 0.0
    assert distress[date(2024, 3, 12)] == 4.0  # the 8-K/A with Item 1.03 on 03-11 is not an event
    assert np.isnan(left[date(2024, 3, 11)]) and left[date(2024, 3, 12)] == 0.0 and left[date(2024, 3, 13)] == 1.0
    split = by_day(B5.reverse_split_features(SPLITS, index()), "days_since_reverse_split")
    assert np.isnan(split[date(2024, 3, 12)]) and split[date(2024, 3, 13)] == 0.0
    assert split[date(2024, 3, 21)] == 6.0  # the 4-for-1 forward split on 03-20 does not reset the clock


def test_join_adds_columns_per_table_and_is_a_no_op_without_them() -> None:
    panel = index(("AAA", "BBB"))
    with Store() as store:
        assert B5.join_b5_events(store, panel) is panel  # no tables
        store.write_table(SPLITS_TABLE, SPLITS, ["symbol", "ex_date"])
        assert list(B5.join_b5_events(store, panel).columns) == ["symbol", "ts", *B5.SPLIT_COLUMNS]
        store.write_table(TRADES_TABLE, TRADES.drop_duplicates(TRADE_KEYS), TRADE_KEYS)
        store.write_table(EIGHTK_TABLE, EIGHTK, ["symbol", "accession"])
        out = B5.join_b5_events(store, panel)
        assert set(B5.FEATURE_COLUMNS) <= set(out.columns) and len(out) == len(panel)
        aaa = out.loc[out["symbol"] == "AAA"]
        # owner 7 has no three-year history in the store, so the join labels that buyer unclassified, not routine
        assert by_day(aaa, "ceo_cfo_buy_value")[date(2024, 3, 21)] == 70_000.0
        assert by_day(aaa, "days_since_8k_distress")[date(2024, 3, 7)] == 1.0
        bbb = out.loc[out["symbol"] == "BBB"]
        assert bbb["ceo_cfo_buy_value"].eq(0.0).all() and bbb["days_since_reverse_split"].isna().all()
        assert B5.join_b5_events(store, out) is out  # columns already there
