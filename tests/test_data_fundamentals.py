"""data.fundamentals: companyfacts parsing, point-in-time features and the EDGAR ingest. No network: a fake Edgar
serves the fixtures under tests/fixtures/edgar into an in-memory Store."""
from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from swing_engine.data import fundamentals as F
from swing_engine.data._common import TZ
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store

EDGAR_FIXTURES = Path(__file__).parent / "fixtures" / "edgar"
CIK = "0000123456"
SYM = "ACME"
M = 1_000_000
VOLUME = 5 * M
# the quarterly series the companyfacts fixture was built from (Q4 is only reported inside the 10-K annual)
EPS = [1.00, 1.10, 1.20, 1.30, 1.05, 1.20, 1.25, 1.45, 1.20, 1.25, 1.40, 1.50]
REV = [100, 110, 120, 140, 104, 118, 121, 150, 112, 120, 133, 151]
GP = [round(v * 0.4, 1) for v in REV]
TEN_K_FY2025_FILED = date(2026, 2, 20)  # Friday; FY2025 ends 2025-12-31
Q3_2025_FILED = date(2025, 10, 30)


def load(name: str) -> dict[str, Any]:
    return json.loads((EDGAR_FIXTURES / name).read_text(encoding="utf-8"))


def expected_surprise(series: list[float], n: int) -> float:
    """Seasonal random walk surprise of quarter n-1 using quarters [0, n): contiguous quarters, lag 4."""
    diffs = [series[i] - series[i - 4] for i in range(4, n)]
    preceding = diffs[:-1][-F.SURPRISE_STD_QUARTERS:]
    return diffs[-1] / float(np.std(preceding, ddof=1))


class FakeEdgar:
    def __init__(self, facts: dict[str, Any] | None = None) -> None:
        self.facts = facts if facts is not None else load("companyfacts_CIK0000123456.json")
        self.calls: list[str] = []

    def company_tickers(self) -> pd.DataFrame:
        return pd.DataFrame({"cik": [CIK, "0001067983"], "symbol": [SYM, "BRK-B"], "name": ["ACME CORP", "BERKSHIRE"]})

    def submissions(self, cik: str) -> list[dict[str, Any]]:
        self.calls.append(cik)
        if cik != CIK:
            raise RuntimeError("boom")
        return [load("submissions_CIK0000123456.json"), load("CIK0000123456-submissions-001.json")]

    def companyfacts(self, cik: str) -> dict[str, Any] | None:
        return self.facts


@pytest.fixture()
def fund() -> pd.DataFrame:
    return F.parse_companyfacts(load("companyfacts_CIK0000123456.json"), [SYM], CIK)


def ingested(facts: dict[str, Any] | None = None) -> Store:
    store = Store()
    result = F.run_edgar_ingest(store, FakeEdgar(facts), [SYM], today=date(2026, 3, 2))
    assert result["failed"] == 0 and result["fundamentals_rows"] > 0 and result["earnings_rows"] == 6
    return store


def panel_index(start: date, end: date) -> pd.DataFrame:
    days = trading_days(start, end)
    return pd.DataFrame({
        "symbol": SYM, "ts": [pd.Timestamp(d).tz_localize(TZ) for d in days], "volume": float(VOLUME),
    })


def row(feats: pd.DataFrame, day: date) -> pd.Series:
    return feats[feats["ts"] == pd.Timestamp(day).tz_localize(TZ)].iloc[0]


# ---------------------------------------------------------------------------------------------------- parsing
def test_parse_companyfacts_shapes(fund: pd.DataFrame) -> None:
    assert list(fund.columns) == F.FUNDAMENTALS_COLUMNS
    assert set(fund["symbol"]) == {SYM} and set(fund["cik"]) == {CIK}
    assert set(fund["form"]) <= F.FUNDAMENTAL_FORMS  # the 8-K EPS fact is dropped
    rev = fund[(fund["concept"] == F.REVENUE) & (fund["period_end"] == date(2025, 3, 31))]
    assert list(rev["tag"]) == ["us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"]  # priority tag wins
    shares = fund[fund["concept"] == F.SHARES_OUTSTANDING]
    assert (shares["duration_days"] == 0).all() and shares["value"].min() == 989 * M  # two classes summed


def test_quarterly_values_derives_q4_from_annual(fund: pd.DataFrame) -> None:
    q = F.quarterly_values(fund, SYM, F.EPS_DILUTED, TEN_K_FY2025_FILED)
    assert len(q) == len(EPS) and np.allclose(q.values, EPS)
    assert q.index[-1] == date(2025, 12, 31)


def test_operating_cash_flow_is_stored_ytd(fund: pd.DataFrame) -> None:
    """10-Qs report OCF year-to-date: rows are stored as reported (90/181/273-day durations) and only Q1 is a
    quarter, so Q2/Q3/Q4 are not derived (no OCF-based feature yet)."""
    ocf = fund[(fund["concept"] == F.OPERATING_CASH_FLOW) & (fund["period_end"].map(lambda d: d.year) == 2025)]
    assert sorted(ocf["duration_days"]) == [90, 181, 273, 365]
    assert sorted(ocf["value"]) == [20 * M, 45 * M, 75 * M, 110 * M]
    q = F.quarterly_values(fund, SYM, F.OPERATING_CASH_FLOW, TEN_K_FY2025_FILED)
    assert [d.month for d in q.index] == [3, 3, 3] and (q == 20 * M).all()


# ---------------------------------------------------------------------------------- point-in-time *_asof
def test_sue_uses_filed_date_not_period_end(fund: pd.DataFrame) -> None:
    before = F.sue_asof(fund, SYM, date(2026, 2, 19))
    assert before == pytest.approx(expected_surprise(EPS, 11))  # FY2025 Q4 ended 12-31 but is not filed yet
    assert F.sue_asof(fund, SYM, TEN_K_FY2025_FILED) == pytest.approx(expected_surprise(EPS, 12))
    assert F.revenue_surprise_asof(fund, SYM, TEN_K_FY2025_FILED) == pytest.approx(expected_surprise(REV, 12))


def test_sue_nan_with_too_little_history(fund: pd.DataFrame) -> None:
    assert np.isnan(F.sue_asof(fund, SYM, date(2024, 12, 31)))  # only 2 prior seasonal differences
    assert np.isnan(F.sue_asof(fund, SYM, date(2023, 4, 30)))  # nothing filed


def test_gross_profitability_and_shares(fund: pd.DataFrame) -> None:
    assert F.gross_profitability_asof(fund, SYM, TEN_K_FY2025_FILED) == pytest.approx(sum(GP[8:]) / 910)
    assert F.gross_profitability_asof(fund, SYM, Q3_2025_FILED) == pytest.approx(sum(GP[7:11]) / 900)
    assert F.shares_outstanding_asof(fund, SYM, Q3_2025_FILED) == 990 * M
    assert F.turnover_asof(fund, SYM, Q3_2025_FILED, VOLUME) == pytest.approx(VOLUME / (990 * M))


def test_missing_gross_profit_is_nan_without_fallback() -> None:
    facts = copy.deepcopy(load("companyfacts_CIK0000123456.json"))
    del facts["facts"]["us-gaap"]["GrossProfit"]
    fund = F.parse_companyfacts(facts, [SYM], CIK)
    assert F.GROSS_PROFIT not in set(fund["concept"])
    assert np.isnan(F.gross_profitability_asof(fund, SYM, TEN_K_FY2025_FILED))
    assert np.isfinite(F.sue_asof(fund, SYM, TEN_K_FY2025_FILED))


# ------------------------------------------------------------------------------- panel features (store)
def test_edgar_panel_features_visible_the_session_after_filing() -> None:
    store = ingested()
    feats = F.edgar_panel_features(store, panel_index(date(2025, 12, 29), date(2026, 2, 24)))
    assert list(feats.columns) == ["symbol", "ts", *F.FEATURE_COLUMNS]
    old_sue = expected_surprise(EPS, 11)
    # period end (12-31), the days after it, and the 10-K filed date itself still show the Q3 filing
    for d in (date(2025, 12, 31), date(2026, 1, 2), TEN_K_FY2025_FILED):
        r = row(feats, d)
        assert r["sue"] == pytest.approx(old_sue)
        assert r["rev_surprise"] == pytest.approx(expected_surprise(REV, 11))
        assert r["gross_prof"] == pytest.approx(sum(GP[7:11]) / 900)
        assert r["shares_outstanding"] == 990 * M
        assert r["turnover"] == pytest.approx(VOLUME / (990 * M))
    # Monday 2026-02-23 is the first session after the Friday filing
    r = row(feats, date(2026, 2, 23))
    assert r["sue"] == pytest.approx(expected_surprise(EPS, 12))
    assert r["rev_surprise"] == pytest.approx(expected_surprise(REV, 12))
    assert r["gross_prof"] == pytest.approx(sum(GP[8:]) / 910)
    assert r["shares_outstanding"] == 989 * M
    assert r["turnover"] == pytest.approx(VOLUME / (989 * M))


def test_edgar_panel_features_earnings_calendar() -> None:
    store = ingested()
    feats = F.edgar_panel_features(store, panel_index(date(2025, 7, 21), date(2025, 7, 29)))
    got = {r.ts.date(): (r.days_since_earnings, r.is_earnings_window) for r in feats.itertuples()}
    # 2025-04-24 16:05 ET release reacts 04-25; 2025-07-24 08:30 ET release reacts that same session
    assert got[date(2025, 7, 23)] == (len(trading_days(date(2025, 4, 25), date(2025, 7, 23))) - 1.0, False)
    assert got[date(2025, 7, 24)] == (0.0, True)
    assert got[date(2025, 7, 25)] == (1.0, True)
    assert got[date(2025, 7, 28)] == (2.0, False)

    feats = F.edgar_panel_features(store, panel_index(date(2026, 2, 4), date(2026, 2, 9)))
    got = {r.ts.date(): (r.days_since_earnings, r.is_earnings_window) for r in feats.itertuples()}
    assert got[date(2026, 2, 5)][1] is False  # accepted 17:45 ET on the 5th: invisible at that close
    assert got[date(2026, 2, 6)] == (0.0, True)


def test_edgar_panel_features_before_any_filing_is_nan() -> None:
    store = ingested()
    feats = F.edgar_panel_features(store, panel_index(date(2023, 4, 28), date(2023, 5, 2)))
    for d in (date(2023, 4, 28), date(2023, 5, 1)):  # first 10-Q filed Monday 05-01
        assert row(feats, d)[F.FEATURE_COLUMNS[:5]].isna().all()
    first = row(feats, date(2023, 5, 2))
    assert first["shares_outstanding"] == 1000 * M and np.isnan(first["sue"])


def test_edgar_panel_features_missing_gross_profit() -> None:
    facts = copy.deepcopy(load("companyfacts_CIK0000123456.json"))
    del facts["facts"]["us-gaap"]["GrossProfit"]
    feats = F.edgar_panel_features(ingested(facts), panel_index(date(2026, 2, 23), date(2026, 2, 24)))
    assert feats["gross_prof"].isna().all() and feats["sue"].notna().all()


def test_edgar_panel_features_empty_store() -> None:
    feats = F.edgar_panel_features(Store(), panel_index(date(2026, 2, 23), date(2026, 2, 24)))
    assert len(feats) == 2 and feats[F.FEATURE_COLUMNS[:6]].isna().all().all()
    assert not feats["is_earnings_window"].any()


# --------------------------------------------------------------------------------------------- ingest
def test_run_edgar_ingest_maps_ciks_and_is_resumable() -> None:
    store = Store()
    edgar = FakeEdgar()
    result = F.run_edgar_ingest(store, edgar, ["acme", "BRK.B", "OLDCO"], today=date(2026, 3, 2))
    assert result["ciks"] == 2 and result["no_cik"] == 1 and result["no_cik_symbols"] == ["OLDCO"]
    assert result["failed"] == 1 and "0001067983" in result["errors"]  # one failing CIK does not fail the run
    assert F.read_earnings(store, [SYM])["session"].iloc[-1] == date(2026, 2, 6)

    again = F.run_edgar_ingest(store, edgar, ["ACME", "BRK.B"], today=date(2026, 3, 3))
    assert again["skipped_fresh"] == 1 and edgar.calls.count(CIK) == 1  # the failed CIK is retried


def test_ingest_caches_events_and_join_edgar_matches_direct_features() -> None:
    store = ingested()
    assert store.has_table(F.EVENTS_TABLE) and store.count(F.EVENTS_TABLE) > 0
    idx = panel_index(date(2025, 1, 2), date(2026, 3, 2)).assign(volume=1_000_000.0, close=10.0)
    joined = F.join_edgar(store, idx)
    direct = F.edgar_panel_features(store, idx)
    for col in F.FEATURE_COLUMNS:
        pd.testing.assert_series_equal(
            joined[col].reset_index(drop=True).astype("float64"), direct[col].reset_index(drop=True).astype("float64"),
            check_names=False,
        )
    assert list(joined.index) == list(idx.index) and "close" in joined.columns


def test_join_edgar_is_a_no_op_without_edgar_tables() -> None:
    idx = panel_index(date(2026, 2, 23), date(2026, 2, 24))
    assert F.join_edgar(Store(), idx) is idx


# ----------------------------------------------------------------------------------------------- share issuance
def _share_events(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """(symbol, filed, cover-page shares) -> the `fundamental_events` columns the join reads."""
    from swing_engine.data._common import session_ts
    from swing_engine.data.calendar import next_trading_day

    return pd.DataFrame([{"symbol": s, "filed": date.fromisoformat(f), "avail_ts": session_ts(next_trading_day(f)),
                          "shares_outstanding": v} for s, f, v in rows])


def _share_index(symbols: list[str], start: str = "2023-01-03", end: str = "2026-06-30") -> pd.DataFrame:
    days = pd.DatetimeIndex(pd.to_datetime(trading_days(start, end))).tz_localize(TZ)
    return pd.DataFrame([{"symbol": s, "ts": d, "close": 50.0} for s in symbols for d in days])


def test_share_issuance_is_split_adjusted_and_lagged() -> None:
    # BUY retires 10% of its shares in the 10-Q filed 2024-05-01; SPL does a 2:1 split (ex 2024-06-03) and nothing else
    events = _share_events([("BUY", "2023-02-01", 100 * M), ("BUY", "2024-05-01", 90 * M),
                            ("SPL", "2023-02-01", 100 * M), ("SPL", "2024-08-01", 200 * M)])
    splits = pd.DataFrame({"symbol": ["SPL"], "ex_date": [date(2024, 6, 3)], "ratio": [2.0]})
    index = _share_index(["BUY", "SPL"])
    out = pd.concat([index, F.share_issuance_features(events, splits, index)], axis=1)
    days = trading_days("2023-01-03", "2026-06-30")
    at = lambda sym, d: out.loc[(out["symbol"] == sym) & (out["ts"].dt.date == d)].iloc[0]  # noqa: E731
    usable = days.index(date(2024, 5, 2))  # first session after the filing
    # the new count enters the numerator 126 sessions after it became usable, and not one session earlier
    assert at("BUY", days[usable + 126])["net_share_issuance"] == pytest.approx(np.log(0.9))
    assert at("BUY", days[usable + 125])["net_share_issuance"] == pytest.approx(0.0)
    # 378 sessions after: both dates see the new count
    assert at("BUY", days[usable + 378])["net_share_issuance"] == pytest.approx(0.0)
    assert np.isnan(at("BUY", days[300])["net_share_issuance"])  # no count usable 378 sessions earlier
    # the split is not an issuance, before or after the post-split filing is in the window
    spl = out.loc[out["symbol"] == "SPL", "net_share_issuance"].dropna()
    assert len(spl) > 100 and np.allclose(spl, 0.0)
    # market cap = as-traded close x as-traded shares on both sides of the split (the store's close is adjusted)
    before, after = at("SPL", date(2024, 5, 31)), at("SPL", date(2024, 6, 3))
    assert before["close_as_traded"] == pytest.approx(100.0) and after["close_as_traded"] == pytest.approx(50.0)
    assert before["mcap_pit"] == pytest.approx(100.0 * 100 * M) and after["mcap_pit"] == pytest.approx(50.0 * 200 * M)
    # without the splits table the same filings look like a +100% issuance
    raw = F.share_issuance_features(events, None, index)
    assert raw.loc[index["symbol"] == "SPL", "net_share_issuance"].max() == pytest.approx(np.log(2.0))


def test_share_issuance_guard_and_store_join() -> None:
    # ERR: a filing-to-filing jump of +150% (a data error or an unrecorded split) voids the signal while it sits
    # between the two dates; OK: +20% passes
    events = _share_events([("ERR", "2023-02-01", 100 * M), ("ERR", "2024-05-01", 250 * M),
                            ("OK", "2023-02-01", 100 * M), ("OK", "2024-05-01", 120 * M)])
    index = _share_index(["ERR", "OK"])
    feats = F.share_issuance_features(events, None, index)
    err = feats.loc[index["symbol"] == "ERR", "net_share_issuance"].dropna()
    assert len(err) > 0 and np.allclose(err, 0.0)  # only the dates where both counts are on the same side
    ok = feats.loc[index["symbol"] == "OK", "net_share_issuance"]
    assert ok.max() == pytest.approx(np.log(1.2))

    store = Store(":memory:")
    try:
        assert F.join_share_issuance(store, index) is index  # no events table: unchanged
        store.write_table(F.EVENTS_TABLE, events.assign(avail_ts=pd.to_datetime(events["avail_ts"])), F.EVENTS_KEYS)
        joined = F.join_share_issuance(store, index)
        assert list(joined.columns[-3:]) == F.SHARE_COLUMNS
        np.testing.assert_allclose(joined["net_share_issuance"], feats["net_share_issuance"], equal_nan=True)
        assert F.join_share_issuance(store, joined) is joined
    finally:
        store.close()
