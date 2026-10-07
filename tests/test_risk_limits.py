"""LimitState: open-position count, pending-order slots, daily loss, drawdown, position/sector/buying-power caps."""
from __future__ import annotations

from datetime import date

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Position, Side
from swing_engine.risk.limits import OK, LimitState

AS_OF = date(2026, 10, 6)


def intent(symbol: str = "AAPL", qty: int = 100, limit: float | None = 10.1) -> OrderIntent:
    return OrderIntent(
        symbol=symbol, side=Side.LONG, qty=qty, entry_limit=limit, stop=8.0, target=16.0, strategy="s",
        client_order_id=f"c-{symbol}", risk_dollars=qty * 2.0,
    )


def account(equity: float = 50_000.0, **extra) -> dict:
    return {"equity": equity, "as_of": AS_OF, **extra}


def positions(n: int) -> list[Position]:
    return [Position(symbol=f"S{i}", qty=1, avg_entry=1.0, side=Side.LONG) for i in range(n)]


def test_passes_clean_account():
    ok, reason = LimitState(RiskConfig()).check(intent(), account())
    assert ok and reason == OK


def test_max_open_positions_blocks():
    ok, reason = LimitState(RiskConfig(max_open_positions=8)).check(intent(), account(positions=positions(8)))
    assert not ok and "max open positions" in reason


def test_pending_orders_reserve_slots():
    state = LimitState(RiskConfig(max_open_positions=8))
    ok, reason = state.check(intent(), account(positions=positions(7), open_orders=[{"symbol": "ZZZ"}]))
    assert not ok and "max open positions" in reason
    ok, reason = state.check(intent(), account(positions=positions(7), open_orders=[{"symbol": "AAPL"}]))
    assert not ok and "pending order" in reason


def test_duplicate_symbol_blocked():
    open_same = [Position(symbol="AAPL", qty=5, avg_entry=9.0, side=Side.LONG)]
    ok, reason = LimitState(RiskConfig()).check(intent(), account(positions=open_same))
    assert not ok and "already has an open position" in reason


def test_daily_loss_blocks_and_resets_next_day():
    state = LimitState(RiskConfig(max_daily_loss_pct=3.0))
    assert state.check(intent(), account(equity=50_000, last_equity=50_000))[0]
    ok, reason = state.check(intent(), account(equity=48_000, last_equity=50_000))
    assert not ok and "daily loss -4.00%" in reason
    ok, _ = state.check(intent(), {"equity": 48_000, "as_of": date(2026, 10, 7)})
    assert ok  # new baseline on a new day


def test_drawdown_from_peak_blocks():
    state = LimitState(RiskConfig(max_drawdown_pct=15.0))
    assert state.check(intent(), account(equity=100_000))[0]
    ok, reason = state.check(intent(qty=10), {"equity": 84_000, "as_of": date(2026, 10, 8), "last_equity": 84_000})
    assert not ok and "drawdown -16.00%" in reason
    assert state.snapshot()["peak_equity"] == 100_000


def test_position_pct_cap():
    ok, reason = LimitState(RiskConfig(max_position_pct=10.0)).check(intent(qty=600, limit=10.0), account())
    assert not ok and "position 12.00%" in reason


def test_market_order_uses_reference_price_or_skips_notional_checks():
    state = LimitState(RiskConfig(max_position_pct=10.0))
    assert state.check(intent(qty=600, limit=None), account())[0]  # no price known -> notional checks skipped
    ok, reason = state.check(intent(qty=600, limit=None), account(prices={"AAPL": 10.0}))
    assert not ok and "position" in reason


def test_sector_cap():
    held = [Position(symbol="MSFT", qty=140, avg_entry=100.0, side=Side.LONG)]  # $14,000 tech
    state = LimitState(RiskConfig(max_sector_pct=30.0), sector_map={"AAPL": "tech", "MSFT": "tech"})
    ok, reason = state.check(intent(qty=200, limit=10.0), account(positions=held))  # +2,000 = 32%
    assert not ok and "sector tech" in reason
    assert state.check(intent(qty=90, limit=10.0), account(positions=held))[0]  # +900 = 29.8%


def test_buying_power_cap():
    ok, reason = LimitState(RiskConfig()).check(intent(qty=100, limit=10.0), account(buying_power=500))
    assert not ok and "buying power" in reason


def test_bad_account_data_blocks():
    ok, reason = LimitState(RiskConfig()).check(intent(), {})
    assert not ok and "equity" in reason
    ok, reason = LimitState(RiskConfig()).check(intent(qty=0), account())
    assert not ok and "qty" in reason


def test_snapshot_counts_checks_and_blocks():
    state = LimitState(RiskConfig())
    state.check(intent(), account())
    state.check(intent(qty=0), account())
    snap = state.snapshot()
    assert snap["checks"] == 2 and snap["blocks"] == 1 and snap["day"] == AS_OF.isoformat()
