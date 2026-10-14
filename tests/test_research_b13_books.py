from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b13_books as b13


def frame(n: int = 10) -> pd.DataFrame:
    k = np.arange(n, dtype=float)
    return pd.DataFrame({"mcap_pit": 100.0 - k, "net_share_issuance": k, "asset_growth": k, "accruals": k,
                         "gp_assets": -k, "roa": -k}, index=[f"s{i}" for i in range(n)])  # s9 worst on every signal


def test_score_direction_and_minimum_signals():
    f = frame()
    s = b13.mispricing_score(f)
    assert s.idxmax() == "s9" and s.idxmin() == "s0" and s["s9"] == pytest.approx(1.0)
    sparse = f.assign(asset_growth=np.nan, accruals=np.nan, gp_assets=np.where(f.index == "s9", np.nan, f["gp_assets"]))
    assert np.isnan(b13.mispricing_score(sparse)["s9"]) and np.isfinite(b13.mispricing_score(sparse)["s8"])  # 2 vs 3 signals


def test_exclusion_buffer_and_books():
    s = b13.mispricing_score(frame())
    assert b13.exclude(s, set(), 2, 4) == {"s9", "s8"}
    assert b13.exclude(s, {"s6", "s3"}, 2, 4) == {"s9", "s8", "s6"}  # s6 (4th worst) stays out, s3 (7th) returns
    universes = {date(2017, 3, 20): frame(), date(2017, 6, 19): frame()}
    book, gone, whole = b13.plan(universes, date(2017, 1, 3), 2, 4, 0.5)
    assert book[date(2017, 1, 3)].to_dict() == {"SPY": 1.0}
    b = book[date(2017, 3, 20)]
    assert set(b.index) == {f"s{i}" for i in range(8)} and b.sum() == pytest.approx(1.0)
    assert b["s0"] == pytest.approx(100.0 / sum(100.0 - k for k in range(8)))
    assert set(gone[date(2017, 3, 20)].index) == {"s8", "s9"} and whole[date(2017, 3, 20)].sum() == pytest.approx(1.0)
