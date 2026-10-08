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
from swing_engine.data.edgar import parse_submissions
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

    def earnings_dates(self, cik: str, symbols: list[str]) -> pd.DataFrame:
        self.calls.append(cik)
        if cik != CIK:
            raise RuntimeError("boom")
        pages = [load("submissions_CIK0000123456.json"), load("CIK0000123456-submissions-001.json")]
        return pd.concat([parse_submissions(p, symbols, cik) for p in pages], ignore_index=True)

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
