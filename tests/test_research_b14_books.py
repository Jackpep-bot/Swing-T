from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.research import b14_books as b14


def test_composite_needs_three_signals_and_is_standardised():
    rng = np.random.default_rng(1)
    sig = pd.DataFrame(rng.normal(size=(50, 4)), columns=list(b14.SIGNALS), index=[f"s{i}" for i in range(50)])
    sig.iloc[0, :2] = np.nan  # two of four: no score
    z = b14.composite(sig)
    assert np.isnan(z.iloc[0]) and z.dropna().mean() == pytest.approx(0.0, abs=1e-9) and z.dropna().std() == pytest.approx(1.0)
    assert np.isfinite(b14.composite(sig, ("momentum",)).iloc[1])  # one-signal books need just that one
    assert list(b14.score_map(pd.Series([1.0, -1.0]))) == pytest.approx([2.0, 0.5])


def test_target_weights_reset_rule_and_drift():
    mcap = pd.Series(np.linspace(100, 1, 120), index=[f"s{i}" for i in range(120)])
    z = pd.Series(np.linspace(2, -2, 120), index=mcap.index)
    w = b14.target_weights(mcap, z, list(mcap.index[:100]))
    assert w.sum() == pytest.approx(1.0) and w.max() <= 0.09 + 1e-12 and "SPY" not in w.index
    assert b14.target_weights(mcap, z, []).to_dict() == {"SPY": 1.0}
    assert not b14.needs_reset(w * 1.1 / (w * 1.1).sum(), w)  # a uniform move: nothing drifts
    bumped = w.copy()
    bumped.iloc[0] *= 1.4
    assert b14.needs_reset(bumped / bumped.sum(), w) and b14.needs_reset(w.drop(w.index[0]), w)
    days = [date(2024, 1, 2), date(2024, 1, 3)]
    closes = pd.DataFrame({"A": [10.0, 20.0], "B": [10.0, 10.0]}, index=days)
    assert b14.drift(pd.Series({"A": 0.5, "B": 0.5}), closes, *days).to_dict() == pytest.approx({"A": 2 / 3, "B": 1 / 3})


def test_scaled_orders_cut_exposure_when_the_base_is_volatile():
    sessions = trading_days("2016-01-04", "2017-12-29")
    closes = pd.DataFrame({"A": 100.0, "B": 100.0}, index=sessions)
    base = {date(2017, 3, 20): pd.Series({"A": 0.5, "B": 0.5})}
    calm = pd.Series(np.where(np.arange(len(sessions)) % 2 == 0, 0.005, -0.005), index=sessions)  # ~8% a year
    wild = pd.Series(np.where(np.arange(len(sessions)) % 2 == 0, 0.025, -0.025), index=sessions)  # ~40% a year
    orders, held = b14.scaled_orders(base, calm.loc[date(2017, 3, 20):], closes, sessions)
    assert set(orders) == {sessions[0], date(2017, 3, 20)} and held.dropna().eq(1.0).all()
    orders, held = b14.scaled_orders(base, wild.loc[date(2017, 3, 20):], closes, sessions)
    cut = [w for d, w in orders.items() if d > date(2017, 3, 20)]
    assert cut and cut[0]["BIL"] == pytest.approx(1 - 0.15 / (0.025 * np.sqrt(252) * np.sqrt(126 / 125)), rel=0.02)


def test_french_parser_and_capm():
    text = "Preamble\n\n,A,B\n196307,  1.00,  -99.99\n196308,  2.00,   0.50\n\n Annual\n,A,B\n1963, 3.0, 1.0\n"
    m = b14.french_monthly(text)
    assert list(m.index) == ["1963-07", "1963-08"] and m.loc["1963-08", "A"] == pytest.approx(0.02) and np.isnan(m.loc["1963-07", "B"])
    rng = np.random.default_rng(2)
    mkt = pd.Series(rng.normal(0.006, 0.04, 600))
    y = 0.002 + 0.9 * mkt + rng.normal(0, 0.01, 600)
    r = b14.capm(y, mkt)
    assert r["alpha_ann"] == pytest.approx(0.024, abs=0.01) and r["beta"] == pytest.approx(0.9, abs=0.05)
    assert r["t_ols"] > 3 and abs(r["t_nw"] / r["t_ols"] - 1) < 0.3
