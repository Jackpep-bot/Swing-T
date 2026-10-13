import math
from datetime import date, timedelta

import pandas as pd
import pytest

from swing_engine.research.vrp_overlay import simulate, stats, target_weights

DAYS = [date(2024, 1, 1) + timedelta(days=k) for k in range(14)]


def _px(sleeve_moves: dict[int, tuple[float, float]] | None = None, cost: float = 0.0) -> pd.DataFrame:
    """Flat $100 bars for both ETFs; `sleeve_moves[i] = (open, close)` overrides the sleeve on row i."""
    px = pd.DataFrame({"core_open": 100.0, "core_close": 100.0, "sleeve_open": 100.0, "sleeve_close": 100.0,
                       "core_cost": cost, "sleeve_cost": cost}, index=DAYS[:6])
    for i, (o, c) in (sleeve_moves or {}).items():
        px.iloc[i, [2, 3]] = [o, c]
    return px


def test_target_weight_rules_and_missing_inputs():
    close = pd.Series([100.0 * 1.01 ** (k % 2) for k in range(14)], index=DAYS)  # +1% / -1% alternating
    rv = 100.0 * math.sqrt(252) * close.pct_change().rolling(10).std(ddof=1).iloc[-1]
    assert 15.0 < rv < 17.0
    vix = pd.Series(20.0, index=DAYS)
    w = target_weights(vix, pd.Series(22.0, index=DAYS), close)
    assert w.iloc[:10].isna().all() and w.iloc[-1] == pytest.approx(0.20)  # contango, VIX above realised: VIX / 100
    assert target_weights(vix - 8.0, pd.Series(22.0, index=DAYS), close).iloc[-1] == pytest.approx(0.06)  # below: / 200
    assert target_weights(vix, pd.Series(19.0, index=DAYS), close).iloc[-1] == 0.0  # backwardation: none
    assert math.isnan(target_weights(vix, pd.Series(22.0, index=DAYS[:-1]), close).iloc[-1])  # no VIX3M that day


def test_weight_is_traded_at_the_next_open_and_earns_from_there():
    px = _px({2: (100.0, 110.0)})  # the sleeve gains 10% inside row 2
    target = pd.Series([0.0, 0.2, 0.2, 0.2, 0.2, 0.2], index=px.index)
    book = simulate(px, target)
    assert list(book.index) == DAYS[1:6]
    assert book["weight"].iloc[0] == 0.0 and book["ret"].iloc[0] == 0.0  # row 1 trades row 0's target (none)
    assert book["weight"].iloc[1] == pytest.approx(0.2) and book["ret"].iloc[1] == pytest.approx(0.02)
    late = simulate(px, pd.Series([0.0, 0.0, 0.2, 0.2, 0.2, 0.2], index=px.index))
    assert late["ret"].iloc[1] == 0.0  # a target first known at row 2's close cannot earn row 2's move


def test_band_zero_crossing_and_costs():
    px = _px(cost=10.0)
    book = simulate(px, pd.Series([0.20, 0.21, 0.23, 0.0, 0.01, 0.01], index=px.index))
    assert list(book["weight"]) == pytest.approx([0.20, 0.20, 0.23, 0.0, 0.01])  # 1 point: held; 3: traded; zero both ways
    assert list(book["turnover"] > 0) == [True, False, True, True, True]
    assert book["cost"].iloc[0] == pytest.approx(10.0 / 1e4)  # the whole book bought once at 10 bp
    assert book["ret"].iloc[0] == pytest.approx(-10.0 / 1e4) and book["ret"].iloc[1] == 0.0
    assert book["cost"].iloc[2] == pytest.approx(2 * 0.03 * 10.0 / 1e4, rel=1e-2)  # 3 points sold, 3 bought


def test_stats_income_view():
    daily = pd.Series([0.01, -0.03, 0.01] * 20, index=[date(2024, 1, 1) + timedelta(days=k) for k in range(60)])
    s = stats(daily, 5)
    assert s["worst_day"] == -0.03 and s["max_dd"] > 0.03 and 0.0 <= s["months_up"] <= 1.0 and s["sharpe"] < 0
