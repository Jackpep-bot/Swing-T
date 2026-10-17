"""Turtle N, unit sizing and unit limits (per symbol / sector / direction); all off by default."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Position, Side, Signal
from swing_engine.risk.limits import LimitState
from swing_engine.risk.sizing import TURTLE_N_FEATURE, size_signal_detail, turtle_n, turtle_unit_shares

AS_OF = date(2026, 10, 6)


def test_turtle_n_is_the_wilder_recursion():
    high = pd.Series([11.0, 12.0, 13.0, 12.5])
    low = pd.Series([9.0, 10.0, 11.0, 11.5])
    close = pd.Series([10.0, 11.0, 12.0, 12.0])
    n = turtle_n(high, low, close, period=2)
    tr = [2.0, 2.0, 2.0, 1.0]  # H-L, max(H-L, |H-PDC|, |L-PDC|)
    prev = tr[0]
    for t in tr[1:]:
        prev = (prev + t) / 2  # (period-1) x PDN + TR, / period
    assert n.iloc[-1] == pytest.approx(prev)


def test_unit_is_one_percent_of_equity_per_n():
    assert turtle_unit_shares(100_000, 2.5, 1.0) == 400  # 1,000 / 2.5
    assert turtle_unit_shares(100_000, 0.0, 1.0) == 0


def test_unit_cap_only_when_configured():
    sig = Signal(strategy="turtle", symbol="AAA", as_of=AS_OF, entry=100.0, stop=90.0, target=150.0,
                 features={TURTLE_N_FEATURE: 5.0})
    cfg = RiskConfig(max_position_pct=100.0, risk_per_trade_pct=2.0)
    off, _ = size_signal_detail(sig, 100_000, cfg)
    on, _ = size_signal_detail(sig, 100_000, cfg.model_copy(update={"turtle_unit_risk_pct": 0.5}))
    assert off is not None and on is not None
    assert "unit=" not in off.notes
    assert on.qty == 100 and "unit=100" in on.notes  # 100,000 x 0.5% / 5


def _intent(symbol: str, side: Side = Side.LONG) -> OrderIntent:
    return OrderIntent(symbol=symbol, side=side, qty=1, entry_limit=10.0, stop=9.0 if side == Side.LONG else 11.0,
                       target=None, strategy="s", client_order_id=f"c-{symbol}", risk_dollars=1.0)


def _pos(symbol: str, side: Side = Side.LONG) -> Position:
    return Position(symbol=symbol, qty=1, avg_entry=10.0, side=side)


def test_unit_limits_off_by_default():
    acct = {"equity": 1e6, "as_of": AS_OF, "positions": [_pos(f"S{i}") for i in range(7)]}
    ok, _ = LimitState(RiskConfig()).check(_intent("NEW"), acct)
    assert ok


def test_units_per_direction():
    cfg = RiskConfig(max_units_per_direction=3)
    acct = {"equity": 1e6, "as_of": AS_OF, "positions": [_pos("A"), _pos("B")], "open_orders": [{"symbol": "C", "side": "buy"}]}
    ok, reason = LimitState(cfg).check(_intent("D"), acct)
    assert not ok and "direction long" in reason
    ok, _ = LimitState(cfg).check(_intent("D", Side.SHORT), acct)
    assert ok


def test_units_per_sector_and_symbol_with_explicit_counts():
    cfg = RiskConfig(max_units_per_sector=6, max_units_per_symbol=4)
    sectors = {"A": "tech", "B": "tech", "X": "energy"}
    acct = {"equity": 1e6, "as_of": AS_OF, "positions": [_pos("A"), _pos("X")], "units": {"A": 4, "X": 4}}
    ok, reason = LimitState(cfg, sector_map=sectors).check(_intent("B"), acct)
    assert ok, reason  # tech 4 + 1 = 5
    acct["units"]["A"] = 5.5
    ok, reason = LimitState(cfg, sector_map=sectors).check(_intent("B"), acct)
    assert not ok and "sector tech" in reason
    # symbol cap: a pending add-on for A (already 4 units) is refused (check() would stop earlier on "pending order")
    acct2 = {"open_orders": [{"symbol": "A", "side": "buy"}], "units": {"A": 4}}
    reason = LimitState(RiskConfig(max_units_per_symbol=4))._unit_violation(_intent("A"), [], acct2)
    assert reason is not None and "symbol A" in reason
