import numpy as np
import pandas as pd
import pytest

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


def test_div_yield_st_uses_the_dividend_expected_next_month():
    from datetime import date

    div = pd.DataFrame({"store_symbol": ["Q"] * 4 + ["A", "M"] + ["M"] * 7,
                        "ex_date": pd.to_datetime(["2016-09-10", "2016-12-10", "2017-03-10", "2017-06-10",
                                                   "2016-06-15", "2016-11-01", *[f"2017-0{i}-01" for i in range(1, 8)]]),
                        "rate_adj": [0.5, 0.5, 0.6, 0.6, 1.0, 0.1, *[0.1] * 7], "special": [False] * 13})
    close = pd.Series({"Q": 100.0, "A": 50.0, "M": 10.0, "N": 20.0})
    got = b18.div_yield_st(div, date(2017, 5, 31), close)
    # quarterly payer: the March dividend (2 months back) 0.6 / 100 = 0.6% -> bucket 2; annual: June 2016 (11 back)
    # 1 / 50 = 2% -> 3; monthly payer and non-payer -> 0
    assert got.to_dict() == {"Q": 2.0, "A": 3.0, "M": 0.0, "N": 0.0}


def test_volume_trend_slope_over_mean_and_minimum_months():
    from datetime import date

    months = list(range(b18._month(date(2014, 1, 1)), b18._month(date(2017, 5, 1)) + 1))
    up = pd.Series([100.0 + 2 * i for i in range(len(months))], index=months)
    short = pd.Series([np.nan] * (len(months) - 10) + [100.0] * 10, index=months)
    got = b18.volume_trend(pd.DataFrame({"UP": up, "SHORT": short}), date(2017, 5, 31))
    assert got["UP"] == pytest.approx(2.0 / up.mean()) and np.isnan(got["SHORT"])


def test_composite_needs_half_and_orients_signs():
    s = pd.DataFrame({"DivYieldST": [3.0, 0.0, np.nan], "VolumeTrend": [-1.0, 1.0, np.nan]}, index=["a", "b", "c"])
    z = b18.composite_score(s)
    assert z["a"] > z["b"] and np.isnan(z["c"])
