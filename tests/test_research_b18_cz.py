import numpy as np
import pandas as pd

from swing_engine.research import b18_cz as b18


def _doc(rows):
    return pd.DataFrame(rows, columns=["Acronym", "Cat.Signal", "Cat.Data", "Stock Weight", "Year", "SampleStartYear",
                                       "SampleEndYear", "LongDescription"])


def test_selection_never_reads_after_the_cutoff(monkeypatch):
    monkeypatch.setattr(b18, "BUILDABLE", {"MaxRet": (True, ""), "RealizedVol": (True, ""), "Mom6m": (True, ""),
                                           "AM": (True, "")})
    doc = _doc([["MaxRet", "Predictor", "Price", "VW", 2005, 1990, 2004, ""],
                ["RealizedVol", "Predictor", "Price", "VW", 2005, 1990, 2004, ""],
                ["Mom6m", "Predictor", "Price", "VW", 1993, 1965, 1989, ""],
                ["AM", "Predictor", "Accounting", "EW", 1992, 1963, 1990, ""]])
    idx = pd.date_range("1990-01-31", "2024-12-31", freq="ME")
    rng = np.random.default_rng(0)
    good = pd.Series(1.0 + rng.normal(0, 1, len(idx)), index=idx)
    good[idx > "2016-12-31"] = -50.0  # would sink it if read
    ret = pd.DataFrame({"MaxRet": good, "RealizedVol": rng.normal(0, 3, len(idx)), "Mom6m": good, "AM": good}, index=idx)
    t = b18.selection(doc, ret)
    assert t.loc["MaxRet", "selected"] and t.loc["MaxRet", "months"] == 12 * 11
    assert not t.loc["Mom6m", "selected"] and "family" in t.loc["Mom6m", "why"]
    assert not t.loc["AM", "selected"] and "equal-weighted" in t.loc["AM", "why"]
    assert not t.loc["RealizedVol", "selected"]
