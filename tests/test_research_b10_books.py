import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research.b10_books import cap_weight_orders


def test_select_with_a_smaller_book_and_buffer():
    z = pd.Series(-np.arange(10.0), index=[f"s{i}" for i in range(10)])
    assert b9.select(z, current={"s4", "s6"}, hold=4, enter=3, stay=5) == ["s4", "s0", "s1", "s2"]


def test_universe_slice_screen_and_cap_weights():
    days = trading_days("2023-01-03", "2025-04-30")
    rng = np.random.default_rng(3)
    syms = [f"s{i}" for i in range(12)]
    closes = pd.DataFrame(100.0 * np.cumprod(1 + rng.normal(0.0005, 0.01, (len(days), 12)), axis=0), index=days, columns=syms)
    mcap = pd.Series(np.arange(12, 0, -1) * 1e9, index=syms)  # s0 largest
    universes: dict = {}
    orders = b9.momentum_orders(closes, lambda ref: mcap, days, first=3, last=10, hold=3, enter=3, stay=4,
                                screen=lambda ref: set(syms) - {"s5"}, universes=universes)
    day = sorted(orders)[0]
    assert list(universes[day].index) == ["s2", "s3", "s4", "s6", "s7", "s8", "s9"]  # ranks 3-10 minus the screened s5
    assert set(orders[day].index) <= set(universes[day].index)
    assert orders[day].sum() == pytest.approx(0.27)  # three names under the 9% cap: the rest is cash
    cw = cap_weight_orders(universes)[day]
    assert cw.sum() == pytest.approx(1.0) and cw["s2"] == pytest.approx(10 / 45)
