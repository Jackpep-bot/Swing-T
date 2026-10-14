from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from swing_engine.research.weights_book import simulate

DAYS = [date(2024, 1, 1) + timedelta(days=k) for k in range(6)]


def frames(a_close, b_close, a_open=None, b_open=None):
    closes = pd.DataFrame({"A": a_close, "B": b_close}, index=DAYS)
    opens = pd.DataFrame({"A": a_open or a_close, "B": b_open or b_close}, index=DAYS)
    return opens, closes


def test_weights_trade_at_the_open_drift_and_cost():
    opens, closes = frames([10, 10, 11, 11, 11, 11], [20.0] * 6, a_open=[10, 10, 10, 11, 11, 11])
    book = simulate(opens, closes, None, {DAYS[1]: pd.Series({"A": 0.5, "B": 0.5})})
    assert list(book.index) == DAYS[1:]  # from the first order on
    assert book["ret"].iloc[0] == pytest.approx(-10.0 / 1e4)  # bought the whole book at the 10 bp default
    assert book["ret"].iloc[1] == pytest.approx(0.05 / (1 - 10.0 / 1e4), rel=1e-6)  # A +10% on half, over equity net of the cost
    assert book["n_held"].iloc[-1] == 2 and book["turnover"].iloc[0] == pytest.approx(1.0)
    costs = pd.DataFrame({"A": [5.0] * 6, "B": [30.0] * 6}, index=DAYS)
    priced = simulate(opens, closes, costs, {DAYS[1]: pd.Series({"A": 0.5, "B": 0.5})})
    assert priced["cost"].iloc[0] == pytest.approx((0.5 * 5 + 0.5 * 30) / 1e4)


def test_cash_part_rebalance_and_delisting():
    opens, closes = frames([10.0] * 6, [20.0, 20.0, 20.0, np.nan, np.nan, np.nan])
    orders = {DAYS[0]: pd.Series({"A": 0.25, "B": 0.5}), DAYS[4]: pd.Series({"A": 1.0})}
    book = simulate(opens, closes, None, orders, delist_mult={"B": 0.7})
    assert book["n_held"].iloc[0] == 2  # 25% cash earns nothing
    assert book["ret"].iloc[3] == pytest.approx(-0.5 * 0.3 / (1 - 0.75 * 10 / 1e4), rel=1e-3)  # B sold at 70% after its last bar
    assert book["n_held"].iloc[3] == 1 and book["n_held"].iloc[4] == 1 and book["turnover"].iloc[4] > 0.5
