from datetime import date

import numpy as np
import pandas as pd

from swing_engine.data.b8 import candidates, deal_features, parse_header, run_header_ingest
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store

HEADER = """<SEC-HEADER>
<TYPE>SC TO-T
<SUBJECT-COMPANY>
<COMPANY-DATA>
<CONFORMED-NAME>Target Inc
<CIK>0001531048
</COMPANY-DATA>
<FILED-BY>
<COMPANY-DATA>
<CONFORMED-NAME>Bidder Corp
<CIK>0000310764
"""
SESSIONS = trading_days("2025-01-02", "2025-12-31")
POS = {d: i for i, d in enumerate(SESSIONS)}


def _ev(symbol, cik, accession, form, day):
    return {"symbol": symbol, "cik": cik, "accession": accession, "form": form, "filing_date": day, "session": day}


def test_parse_header_roles():
    assert parse_header(HEADER) == [("subject", "0001531048"), ("filer", "0000310764")]
    assert parse_header("<FILER>\n<CIK>0000000042\n") == [("filer", "0000000042")] and parse_header("") == []


def test_candidates_target_side_only_agreement_window_and_quiet_year():
    d = lambda s: date.fromisoformat(s)  # noqa: E731
    events = pd.DataFrame([
        _ev("TGT", "0000000001", "acc-1", "SC TO-T", d("2025-03-03")),  # TGT is the subject: a candidate
        _ev("BID", "0000000002", "acc-1", "SC TO-T", d("2025-03-03")),  # the bidder's copy: not
        _ev("TGT", "0000000001", "acc-2", "SC TO-T", d("2025-06-02")),  # within 365 days of TGT's first: dropped
        _ev("PRX", "0000000003", "acc-3", "DEFM14A", d("2025-09-02")),  # own proxy after an 8-K 1.01: a candidate
        _ev("LATE", "0000000004", "acc-4", "DEFM14A", d("2025-12-01")),  # 8-K 1.01 more than 120 sessions before
    ])
    parties = pd.DataFrame([
        {"accession": "acc-1", "role": "subject", "cik": "0000000001"}, {"accession": "acc-1", "role": "filer", "cik": "0000000002"},
        {"accession": "acc-2", "role": "subject", "cik": "0000000001"}, {"accession": "acc-2", "role": "filer", "cik": "0000000002"},
        {"accession": "acc-3", "role": "filer", "cik": "0000000003"}, {"accession": "acc-4", "role": "filer", "cik": "0000000004"},
    ])
    eightk = pd.DataFrame([
        {"symbol": "PRX", "form": "8-K", "items": "1.01,9.01", "session": d("2025-07-01")},
        {"symbol": "PRX", "form": "8-K", "items": "1.01", "session": d("2025-08-01")},  # later: the earliest is the anchor
        {"symbol": "LATE", "form": "8-K", "items": "1.01", "session": d("2025-01-02")},
    ])
    c = candidates(events, parties, eightk, SESSIONS)
    got = {r.symbol: (r.s, r.a) for r in c.itertuples()}
    assert got == {"TGT": (POS[d("2025-03-03")],) * 2, "PRX": (POS[d("2025-09-02")], POS[d("2025-07-01")])}
    days = pd.DatetimeIndex(pd.to_datetime([SESSIONS[POS[d("2025-09-02")] + k] for k in (-1, 0, 20, 21)])
                            ).tz_localize("America/New_York")
    f = deal_features(c, pd.DataFrame({"symbol": "PRX", "ts": days}), SESSIONS)
    assert np.isnan(f["deal_v2_days"].iloc[0]) and list(f["deal_v2_days"].iloc[1:3]) == [0.0, 20.0]
    assert np.isnan(f["deal_v2_days"].iloc[3]) and f["deal_v2_anchor"].iloc[1] == POS[d("2025-09-02")] - POS[d("2025-07-01")]


def test_header_ingest_is_resumable():
    with Store() as store:
        store.write_table("form_events", pd.DataFrame([_ev("TGT", "0001531048", "0001193125-25-008416", "SC TO-T",
                                                           date(2025, 1, 17))]), ["symbol", "accession"])
        asked: list[str] = []
        fetch = lambda url: asked.append(url) or HEADER  # noqa: E731
        assert run_header_ingest(store, fetch) == {"accessions": 1} and run_header_ingest(store, fetch) == {"accessions": 0}
        assert asked == ["https://www.sec.gov/Archives/edgar/data/1531048/000119312525008416/0001193125-25-008416.hdr.sgml"]
        assert len(store.read_table("form_parties")) == 2
