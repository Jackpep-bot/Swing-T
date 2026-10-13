"""data.b5_fundamentals: the batch-5 point-in-time columns (F-score, book-to-market, TTM cash flow, Code 33, dividend
and buyback yield) on hand-built filings in an in-memory Store. No network."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from swing_engine.data import b5_fundamentals as B
from swing_engine.data import fundamentals as F
from swing_engine.data._common import TZ
from swing_engine.data.calendar import next_trading_day, trading_days
from swing_engine.data.dividends import SCHEMA as DIV_SCHEMA
from swing_engine.data.dividends import TABLE as DIV_TABLE
from swing_engine.data.store import Store

YEARS = (2022, 2023, 2024, 2025)
Q_END = [(3, 31), (6, 30), (9, 30), (12, 31)]
FILING_LAG = timedelta(days=40)
# 16 quarters, 2022Q1..2025Q4: flat for three years, then accelerating in 2025
REV = [100.0] * 8 + [110.0] * 4 + [121.0, 132.0, 143.0, 154.0]  # y/y +10%, +20%, +30%, +40%
EPS = [1.0] * 12 + [1.2, 1.5, 1.9, 2.4]  # y/y +20%, +50%, +90%, +140%; EPS / revenue rising too
GP = [0.40 * r for r in REV[:12]] + [0.45 * r for r in REV[12:]]
OCF = [30.0] * 12 + [60.0] * 4
ASSETS, EQUITY, SHARES = [1000.0] * 16, [400.0] * 12 + [500.0] * 4, [10.0] * 16
TEN_K_2025 = date(2025, 12, 31) + FILING_LAG  # 2026-02-09


def filings(symbol: str, *, eps=EPS, rev=REV, gp=GP, ocf=OCF, equity=EQUITY, shares=SHARES) -> pd.DataFrame:
    """`fundamentals` rows as a calendar-year filer reports them: 10-Q = the quarter and the year-to-date (cash
    flow year-to-date only), 10-K = the annual figure only; balance sheet and cover-page shares in both."""
    rows = []
    for i in range(16):
        year, q = YEARS[i // 4], i % 4
        end, jan1 = date(year, *Q_END[q]), date(year, 1, 1)
        start = jan1 if q == 0 else date(year, *Q_END[q - 1]) + timedelta(days=1)
        filed, form, accn = end + FILING_LAG, "10-K" if q == 3 else "10-Q", f"{symbol}-{i:02d}"
        first = i - q  # the fiscal year's first quarter

        def add(concept, value, s=None, *, e=end, filed=filed, form=form, accn=accn):
            rows.append({"symbol": symbol, "cik": "1", "concept": concept, "period_end": e, "fp": "", "form": form,
                         "filed": filed, "value": float(value), "period_start": s,
                         "duration_days": (e - s).days + 1 if s else 0, "fy": e.year, "tag": concept, "accession": accn})

        for concept, series in ((F.EPS_DILUTED, eps), (F.REVENUE, rev), (F.GROSS_PROFIT, gp), (F.OPERATING_CASH_FLOW, ocf)):
            if series is None:
                continue
            if q < 3 and concept != F.OPERATING_CASH_FLOW:
                add(concept, series[i], start)
            if q > 0 or concept == F.OPERATING_CASH_FLOW:
                add(concept, sum(series[first:i + 1]), jan1)  # year-to-date; the annual figure in the 10-K
        add(F.TOTAL_ASSETS, ASSETS[i])
        add(F.TOTAL_EQUITY, equity[i])
        add(F.SHARES_OUTSTANDING, shares[i], e=filed - timedelta(days=5))
    return pd.DataFrame(rows, columns=F.FUNDAMENTALS_COLUMNS)


def at(vals: pd.DataFrame, symbol: str, filed: date) -> pd.Series:
    return vals.loc[(vals["symbol"] == symbol) & (vals["filed"] == pd.Timestamp(filed))].iloc[0]


def events_of(fund: pd.DataFrame) -> pd.DataFrame:
    return F.fundamental_events(fund)


def test_event_values_fscore_ttm_and_code33_by_hand():
    slow = EPS[:12] + [1.2, 1.5, 1.4, 1.3]  # 2025 y/y growth +20%, +50%, +40%, +30%: not rising
    tiny = [1.0] * 8 + [0.01] * 4 + EPS[12:]  # |EPS a year ago| < $0.05: growth undefined
    fund = pd.concat([filings("GOOD"), filings("BURN", ocf=OCF[:12] + [-10.0] * 4), filings("BANK", gp=None),
                      filings("SLOW", eps=slow), filings("TINY", eps=tiny)], ignore_index=True)
    vals = B.event_values(fund, events_of(fund))
    good = at(vals, "GOOD", TEN_K_2025)
    assert good["f7"] == 7 and good["code33"] == 1.0 and good["equity"] == 500.0
    assert good["ocf_ttm"] == pytest.approx(240.0)  # the 10-K's annual figure
    q3 = at(vals, "GOOD", date(2025, 9, 30) + FILING_LAG)
    assert q3["ocf_ttm"] == pytest.approx(180.0 + 120.0 - 90.0)  # 9 months + FY2024 - 9 months of 2024
    assert q3["f7"] == 7 and q3["code33"] == 1.0  # quarters Q3, Q2, Q1 of 2025
    # FY2024 10-K: against 2023 only revenue rose (points 1, 2, 4, 9) and growth did not accelerate
    flat = at(vals, "GOOD", date(2024, 12, 31) + FILING_LAG)
    assert flat["f7"] == 4 and flat["code33"] == 0.0
    burn = at(vals, "BURN", TEN_K_2025)
    assert burn["ocf_ttm"] == pytest.approx(-40.0) and burn["f7"] == 5  # CFO > 0 and CFO > net income fail
    assert np.isnan(at(vals, "BANK", TEN_K_2025)["f7"])  # no gross profit: excluded, not scored 0
    assert at(vals, "BANK", TEN_K_2025)["code33"] == 1.0  # Code 33 needs EPS and revenue only
    assert at(vals, "SLOW", TEN_K_2025)["code33"] == 0.0
    assert np.isnan(at(vals, "TINY", TEN_K_2025)["code33"])
    # the first year has no year-ago figures: unknown, not zero
    assert np.isnan(at(vals, "GOOD", date(2022, 12, 31) + FILING_LAG)["f7"])


def test_event_values_use_only_filings_on_or_before_each_date():
    fund = filings("GOOD")
    base = B.event_values(fund, events_of(fund))
    # a 10-K/A filed in March 2026 triples FY2024 revenue
    late = date(2026, 3, 2)
    fix = fund.loc[(fund["accession"] == "GOOD-11") & (fund["concept"] == F.REVENUE)].assign(
        filed=late, form="10-K/A", accession="GOOD-99", value=lambda d: d["value"] * 3.0)
    both = pd.concat([fund, fix], ignore_index=True)
    vals = B.event_values(both, events_of(both))
    before = vals.loc[vals["filed"] < pd.Timestamp(late)].reset_index(drop=True)
    pd.testing.assert_frame_equal(before, base)
    amended = at(vals, "GOOD", late)  # the amendment reports no new period: FY2025 stays the current one
    assert amended["ocf_ttm"] == pytest.approx(240.0)
    assert amended["f7"] == 6  # against the restated year-ago revenue, asset turnover is now down
    # truncating the facts at a date leaves every earlier filing's values unchanged
    cut = pd.Timestamp("2025-06-30")
    early = fund.loc[pd.to_datetime(fund["filed"]) <= cut]
    pd.testing.assert_frame_equal(B.event_values(early, events_of(early)),
                                  base.loc[base["filed"] <= cut].reset_index(drop=True))
    # `first` keeps each symbol's last filing before that day and everything after
    tail = B.event_values(fund, events_of(fund), first=date(2025, 6, 1))
    pd.testing.assert_frame_equal(tail, base.loc[base["filed"] >= pd.Timestamp("2025-05-10")].reset_index(drop=True))


def test_event_values_put_eps_on_one_split_basis():
    # 2:1 split on 2025-07-01: filings after it report half the EPS and twice the shares, older facts stay as filed
    fund = filings("SPL")
    after = pd.to_datetime(fund["filed"]) > pd.Timestamp("2025-07-01")
    fund.loc[after & (fund["concept"] == F.EPS_DILUTED), "value"] /= 2.0
    fund.loc[after & (fund["concept"] == F.SHARES_OUTSTANDING), "value"] *= 2.0
    splits = pd.DataFrame({"symbol": ["SPL"], "ex_date": [date(2025, 7, 1)], "ratio": [2.0]})
    adjusted = at(B.event_values(fund, events_of(fund), splits), "SPL", TEN_K_2025)
    assert adjusted["f7"] == 7 and adjusted["code33"] == 1.0  # the same company as GOOD
    raw = at(B.event_values(fund, events_of(fund)), "SPL", TEN_K_2025)
    assert raw["code33"] == 0.0  # without the splits table the halved EPS reads as a collapse


def test_dividend_yield_counts_regular_dividends_by_ex_date():
    days = trading_days("2023-01-03", "2025-12-31")
    ex = [date(2024, m, 15) for m in (2, 5, 8, 11)]
    div = pd.DataFrame({"store_symbol": ["PAY"] * 6 + ["OLD"], "rate_adj": [0.5] * 4 + [5.0, 9.0, 0.1],
                        "ex_date": [*ex, date(2024, 6, 3), date(2024, 6, 4), date(2023, 1, 3)],
                        "special": [False] * 4 + [True, False, False], "foreign": [False] * 5 + [True, False]})
    n = len(days)
    sym = pd.Series(["PAY"] * n + ["NONE"] * n)
    day = pd.Series(pd.to_datetime(days * 2))
    out = pd.Series(B.dividend_yield(div, sym, day, pd.Series(50.0, index=sym.index)))
    pay = dict(zip(days, out[:n], strict=True))
    assert pay[date(2024, 2, 14)] == 0.0 and pay[date(2024, 2, 15)] == pytest.approx(0.5 / 50.0)  # from the ex-date
    assert pay[date(2024, 12, 31)] == pytest.approx(2.0 / 50.0)  # four regular payments; special and foreign left out
    i = days.index(date(2024, 2, 15))
    assert pay[days[i + 251]] == pytest.approx(2.0 / 50.0) and pay[days[i + 252]] == pytest.approx(1.5 / 50.0)
    assert np.isnan(pay[days[100]])  # the 252-session window starts before the feed's first ex-date
    assert out[n:].dropna().eq(0.0).all() and out[n:].notna().sum() > 400  # a non-payer inside the feed: zero


def test_buyback_yield_and_its_jump_guard():
    n = 600
    ts = pd.Series(pd.to_datetime(trading_days("2023-01-03", "2026-06-30")[:n]))
    adj = lambda new: pd.Series(np.r_[np.full(300, 100.0), np.full(n - 300, new)])  # noqa: E731
    sym = pd.Series(["A"] * n)
    buy = B.buyback_yield(sym, ts, adj(90.0))
    assert np.isnan(buy[:252]).all() and np.allclose(buy[252:300], 0.0)
    assert np.allclose(buy[300:552], -np.log(0.9)) and np.allclose(buy[552:], 0.0)  # in the window for 252 bars
    err = B.buyback_yield(sym, ts, adj(250.0))  # +150% in one filing: void while it sits between the two dates
    assert np.isnan(err[300:552]).all() and np.allclose(err[552:], 0.0)
    # two symbols, shuffled rows: each row gets its own symbol's value back
    order = np.random.default_rng(0).permutation(2 * n)
    two = B.buyback_yield(pd.concat([sym, sym.str.replace("A", "B")]).iloc[order], pd.concat([ts, ts]).iloc[order],
                          pd.concat([adj(90.0), adj(100.0)]).iloc[order])
    np.testing.assert_allclose(two, np.r_[buy, B.buyback_yield(sym, ts, adj(100.0))][order], equal_nan=True)


def test_join_is_point_in_time_and_leaves_a_bare_panel_alone():
    days = trading_days("2024-01-02", "2026-03-31")
    panel = pd.concat([pd.DataFrame({"symbol": s, "ts": [pd.Timestamp(d).tz_localize(TZ) for d in days], "open": 50.0,
                                     "high": 50.0, "low": 50.0, "close": 50.0, "volume": 1e6})
                       for s in ("GOOD", "BANK", "NOFILE")], ignore_index=True)
    store = Store(":memory:")
    try:
        assert B.join_b5_fundamentals(store, panel) is panel  # no EDGAR tables
        fund = pd.concat([filings("GOOD"), filings("BANK", gp=None)], ignore_index=True)
        store.write_table(F.FUNDAMENTALS_TABLE, fund, F.FUNDAMENTALS_KEYS, schema=F.FUNDAMENTALS_SCHEMA)
        assert F.build_fundamental_events(store) == 32
        no_div = B.join_b5_fundamentals(store, panel)
        assert no_div[B.DIV_YIELD].isna().all() and no_div[B.FSCORE].notna().any()  # no dividends table yet
        ex = [date(y, m, 15) for y in (2023, 2024, 2025) for m in (2, 5, 8, 11)]
        store.write_table(DIV_TABLE, pd.DataFrame({
            "id": [f"d{i}" for i in range(len(ex))], "symbol": "GOOD", "ex_date": ex, "rate": 0.25, "special": False,
            "foreign": False, "process_date": ex, "payable_date": ex, "record_date": ex}), ["id"], schema=DIV_SCHEMA)
        out = B.join_b5_fundamentals(store, panel)
        assert list(out.columns[-len(B.B5_COLUMNS):]) == B.B5_COLUMNS and len(out) == len(panel)
        assert "mcap_pit" not in out.columns  # only its own columns are added
        assert B.join_b5_fundamentals(store, out) is out
        row = lambda s, d: out.loc[(out["symbol"] == s) & (out["ts"].dt.date == d)].iloc[0]  # noqa: E731
        usable = next_trading_day(TEN_K_2025)
        new, old = row("GOOD", usable), row("GOOD", TEN_K_2025)  # the filing counts from the session after it
        assert new[B.FSCORE] == 8 and new[B.OCF_TTM] == pytest.approx(240.0) and new[B.CODE33] == 1.0
        assert new[B.BOOK_TO_MARKET] == pytest.approx(500.0 / (50.0 * 10.0))
        assert old[B.OCF_TTM] == pytest.approx(210.0) and old[B.BOOK_TO_MARKET] == pytest.approx(1.0)
        assert new[B.DIV_YIELD] == pytest.approx(1.0 / 50.0) and new[B.BUYBACK_YIELD] == pytest.approx(0.0)
        assert np.isnan(row("BANK", usable)[B.FSCORE]) and row("BANK", usable)[B.DIV_YIELD] == 0.0
        assert out.loc[out["symbol"] == "NOFILE", [B.FSCORE, B.BOOK_TO_MARKET, B.CODE33, B.BUYBACK_YIELD]].isna().all().all()
        # a panel cut at a date carries the same values up to it
        cut = panel.loc[panel["ts"].dt.date <= date(2025, 12, 1)]
        np.testing.assert_allclose(B.join_b5_fundamentals(store, cut)[B.B5_COLUMNS].to_numpy(dtype=float),
                                   out.loc[cut.index, B.B5_COLUMNS].to_numpy(dtype=float), equal_nan=True)
    finally:
        store.close()
