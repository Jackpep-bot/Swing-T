"""data.edgar.parse_filings / data.filings: every 8-K item list and Schedule 13D from a submissions fixture, dated by
acceptance (UTC decoded, after-close rolls forward, no time -> next session), the point-in-time panel clocks, and the
ingest wiring (`run_edgar_ingest`, including `--8k-only`). No network."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.data import filings as FL
from swing_engine.data import fundamentals as F
from swing_engine.data.edgar import (
    EIGHTK_COLUMNS,
    EIGHTK_FORMS,
    SCHED13D_COLUMNS,
    SCHED13D_FORMS,
    parse_filings,
    submission_tables,
)
from swing_engine.data.store import Store

FIX = Path(__file__).parent / "fixtures" / "edgar" / "submissions_filings_sample.json"
CIK, SYM, TZ = "0000777777", "TGT", "America/New_York"


def payload() -> dict[str, Any]:
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_parse_eightk_items_sessions_and_amendments() -> None:
    df = parse_filings(payload(), [SYM], CIK, EIGHTK_FORMS, EIGHTK_COLUMNS)
    got = {r.accession: (r.form, r.session, r.items) for r in df.itertuples()}
    assert got["0001193125-24-000008"] == ("8-K", date(2024, 6, 11), "4.02,9.01")  # 17:30 EDT -> next session
    assert got["0001193125-24-000005"] == ("8-K", date(2024, 3, 13), "5.02")  # no acceptance -> after filing date
    assert got["0001193125-24-000004"][0] == "8-K/A"
    assert got["0001193125-24-000003"][1] == date(2024, 2, 2)  # 16:10 EST is after the close
    assert df["acceptance"].iloc[-1].tz is not None and len(df) == 4


def test_parse_sched13d_forms_filer_and_session() -> None:
    df = parse_filings(payload(), [SYM], CIK, SCHED13D_FORMS, SCHED13D_COLUMNS)
    assert sorted(df["form"]) == ["SC 13D", "SC 13D/A", "SCHEDULE 13D"]  # SC 13G is not a 13D
    orig = df[df["form"] == "SC 13D"].iloc[0]
    assert orig["session"] == date(2024, 4, 16) and orig["filer"] == "0000921895"  # 16:59 EDT -> next session
    assert df.loc[df["form"] == "SCHEDULE 13D", "session"].iloc[0] == date(2024, 12, 20)  # 10:00 EST, same day


def index(*days: str) -> pd.DataFrame:
    return pd.DataFrame({"symbol": SYM, "ts": [pd.Timestamp(d).tz_localize(TZ) for d in days]})


def test_eightk_and_13d_clocks_are_point_in_time() -> None:
    _, eightk, sched = submission_tables([payload()], CIK, [SYM])
    f = FL.eightk_features(eightk, index("2024-02-01", "2024-02-02", "2024-03-08", "2024-03-13", "2024-06-10",
                                         "2024-06-11", "2024-06-12"))
    assert list(f["news_8k_flag_1d"]) == [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]  # the 8-K/A on 03-08 is no event
    assert np.isnan(f["days_since_8k"].iloc[0]) and f["days_since_8k"].iloc[2] == 24
    assert np.isnan(f["days_since_402"].iloc[4]) and list(f["days_since_402"].iloc[5:]) == [0.0, 1.0]
    g = FL.sched13d_features(sched, index("2024-04-15", "2024-04-16", "2024-04-17", "2024-05-03", "2024-12-20"))
    assert np.isnan(g["days_since_13d"].iloc[0]) and list(g["days_since_13d"].iloc[1:3]) == [0.0, 1.0]
    assert g["days_since_13d"].iloc[3] == 13  # the 13D/A on 05-02 does not reset the clock
    assert g["days_since_13d"].iloc[4] == 0  # the new-format "SCHEDULE 13D" does


class FakeEdgar:
    def __init__(self) -> None:
        self.facts_calls = 0

    def company_tickers(self) -> pd.DataFrame:
        return pd.DataFrame({"cik": [CIK], "symbol": [SYM], "name": ["TARGETCO"]})

    def submissions(self, cik: str) -> list[dict[str, Any]]:
        return [payload()]

    def companyfacts(self, cik: str) -> dict[str, Any] | None:
        self.facts_calls += 1
        return None


def test_ingest_fills_tables_and_join_edgar_adds_columns() -> None:
    store, edgar = Store(), FakeEdgar()
    res = F.run_edgar_ingest(store, edgar, [SYM], today=date(2025, 1, 2))
    assert res["eightk_rows"] == 4 and res["sched13d_rows"] == 3 and res["earnings_rows"] == 1
    assert edgar.facts_calls == 1
    again = F.run_edgar_ingest(store, edgar, [SYM], today=date(2025, 1, 3), eightk_only=True)
    assert again["skipped_fresh"] == 0 and again["eightk_rows"] == 4 and edgar.facts_calls == 1  # own meta, no facts
    assert F.run_edgar_ingest(store, edgar, [SYM], today=date(2025, 1, 3), eightk_only=True)["skipped_fresh"] == 1
    panel = index("2024-06-11", "2024-12-20").assign(close=10.0, volume=1.0)
    out = F.join_edgar(store, panel)
    assert list(out["days_since_402"]) == [0.0, 134.0] and list(out["days_since_13d"])[-1] == 0.0
    assert list(out["news_8k_flag_1d"]) == [1.0, 0.0]


def test_join_filings_no_op_without_tables() -> None:
    panel = index("2024-06-11")
    assert FL.join_filings(Store(), panel) is panel
