import math

import pandas as pd

from swing_engine.data.sic import join_sic, parse_sic, run_sic_ingest, sic2
from swing_engine.data.store import Store


class FakeEdgar:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def submissions(self, cik, include_older=True):
        self.asked.append(cik)
        return self.pages.get(cik, [])


def test_parse_sic_and_major_group():
    assert parse_sic({"sic": "3674"}) == "3674" and parse_sic({"sic": 100}) == "0100"
    assert parse_sic({"sic": ""}) is None and parse_sic({}) is None and parse_sic(None) is None
    assert sic2("3674") == 36.0 and sic2("0100") == 1.0 and math.isnan(sic2(None)) and math.isnan(sic2(float("nan")))


def test_ingest_is_resumable_and_join_adds_sic2():
    with Store() as store:
        store.write_table("eightk_ingest_meta", pd.DataFrame({"cik": ["1", "2", "3"], "symbols": ["AAA", "BBB,BBB.W", "CCC"]}),
                          ["cik"])
        edgar = FakeEdgar({"1": [{"sic": "3674"}], "2": [{"sic": "6021"}]})  # CIK 3 is unknown to EDGAR
        assert run_sic_ingest(store, edgar) == {"ciks": 3, "rows": 4, "with_sic": 3}
        assert run_sic_ingest(store, edgar)["ciks"] == 0 and sorted(edgar.asked) == ["1", "2", "3"]  # nothing fetched twice
        panel = pd.DataFrame({"symbol": ["AAA", "BBB", "CCC", "ZZZ"], "ts": pd.Timestamp("2024-01-02")})
        out = join_sic(store, panel)["sic2"]
        assert out.iloc[0] == 36.0 and out.iloc[1] == 60.0 and out.iloc[2:].isna().all()
    with Store() as empty:
        assert "sic2" not in join_sic(empty, panel).columns  # no table: unchanged
