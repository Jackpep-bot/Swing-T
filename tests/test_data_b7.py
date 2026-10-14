import pandas as pd

from swing_engine.data.b7 import event_features, join_b7, run_form_ingest
from swing_engine.data.store import Store


def _page(rows):
    """A submissions page with `rows` = (form, filing date, acceptance UTC)."""
    return {"filings": {"recent": {"form": [r[0] for r in rows], "filingDate": [r[1] for r in rows],
                                   "acceptanceDateTime": [r[2] for r in rows],
                                   "accessionNumber": [f"000000000{i}-24-00000{i}" for i in range(len(rows))],
                                   "items": [""] * len(rows)}}}


class FakeEdgar:
    def __init__(self, pages):
        self.pages = pages

    def submissions(self, cik, include_older=True, since=None):
        return self.pages.get(cik, [])


PAGES = {
    "1": [_page([("DEFM14A", "2025-03-03", "2025-03-03T14:00:00.000Z"),  # 09:00 ET: reacts the same session
                 ("DEFM14A", "2025-06-02", "2025-06-02T14:00:00.000Z"),  # within 365 days of the first: no event
                 ("10-K", "2025-02-01", "2025-02-01T14:00:00.000Z")])],
    "2": [_page([("424B5", "2025-04-01", "2025-04-01T21:30:00.000Z"),  # 17:30 ET: reacts the next session
                 ("424B3", "2025-05-01", "2025-05-01T14:00:00.000Z"),
                 ("424B4", "2025-06-02", "2025-06-02T14:00:00.000Z"),  # a 424B3 32 days before: no event
                 ("424B4", "2025-10-01", "2025-10-01T14:00:00.000Z")])],  # 153 days later: an event
}


def test_ingest_and_first_event_rules():
    with Store() as store:
        store.write_table("eightk_ingest_meta", pd.DataFrame({"cik": ["1", "2"], "symbols": ["TGT", "ISS"]}), ["cik"])
        assert run_form_ingest(store, FakeEdgar(PAGES)) == {"ciks": 2, "rows": 6}  # the 10-K is not kept
        assert run_form_ingest(store, FakeEdgar(PAGES))["ciks"] == 0
        days = pd.DatetimeIndex(pd.to_datetime(["2025-03-03", "2025-04-01", "2025-04-02", "2025-06-02", "2025-10-01"])
                                ).tz_localize("America/New_York")
        panel = pd.DataFrame({"symbol": ["TGT"] * 5 + ["ISS"] * 5, "ts": list(days) * 2})
        out = join_b7(store, panel)
    tgt, iss = out.loc[out["symbol"] == "TGT"], out.loc[out["symbol"] == "ISS"]
    assert list(tgt["deal_event"]) == [1.0, 0.0, 0.0, 0.0, 0.0] and tgt["offer_event"].sum() == 0.0
    assert list(iss["offer_event"]) == [0.0, 0.0, 1.0, 0.0, 1.0] and iss["deal_event"].sum() == 0.0


def test_no_table_no_change_and_empty_events():
    panel = pd.DataFrame({"symbol": ["A"], "ts": pd.DatetimeIndex([pd.Timestamp("2025-01-02", tz="America/New_York")])})
    with Store() as store:
        assert join_b7(store, panel) is panel
    assert event_features(pd.DataFrame(), panel)[["deal_event", "offer_event"]].sum().sum() == 0.0
