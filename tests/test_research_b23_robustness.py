import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b23_robustness as b23


def test_reading_rule():
    assert b23.reading(0.03, [0.01] * 6, [0.01] * 5 + [-0.01]) == "ROBUST"
    assert b23.reading(0.03, [0.01] * 6, [0.01] * 4 + [-0.01] * 2) == "MIXED"
    assert b23.reading(0.009, [0.01] * 6, [0.01] * 6) == "FRAGILE"
    assert b23.reading(0.03, [0.01] * 3 + [0.0] * 3, [0.01] * 6) == "FRAGILE"


def test_tranched_is_the_average_of_values():
    idx = pd.RangeIndex(3)
    a = pd.DataFrame({"ret": [0.1, 0.0, 0.0], "cost": 0.0, "turnover": [1.0, 0.0, 0.0], "n_held": 10}, index=idx)
    b = pd.DataFrame({"ret": [0.0, 0.1, 0.0], "cost": 0.0, "turnover": [0.0, 1.0, 0.0], "n_held": 20}, index=idx)
    t = b23.tranched([a, b])
    assert (1 + t["ret"]).prod() == pytest.approx((1.1 + 1.1) / 2)
    assert t["n_held"].iloc[0] == pytest.approx(15.0)


def test_bootstrap_alpha_centres_on_the_sample_alpha():
    rng = np.random.default_rng(1)
    days = pd.RangeIndex(500)
    spy = pd.Series(rng.normal(0.0004, 0.01, 500), index=days)
    book = spy * 1.0 + 0.0002 + pd.Series(rng.normal(0, 0.002, 500), index=days)
    out = b23.bootstrap_alpha(book, spy, pd.Series(0.0, index=days), draws=400, block=10, seed=3)
    beta, alpha = np.polyfit(spy, book, 1)
    assert abs(np.median(out) - alpha * 252) < 0.01 and np.percentile(out, 5) < alpha * 252 < np.percentile(out, 95)
