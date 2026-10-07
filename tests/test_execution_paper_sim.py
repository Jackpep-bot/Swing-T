"""paper_sim broker: fills at next open with adverse slippage, stop/target exits, idempotency, cash accounting."""
from __future__ import annotations

import pytest

from swing_engine.core.models import OrderIntent, Side
from swing_engine.core.registry import get as registry_get
from swing_engine.execution.paper_sim import PaperSimBroker


def intent(
    symbol: str = "AAPL", side: Side = Side.LONG, qty: int = 100, limit: float | None = 10.1,
    stop: float = 8.0, target: float | None = 16.0, cid: str = "c1",
) -> OrderIntent:
    return OrderIntent(symbol=symbol, side=side, qty=qty, entry_limit=limit, stop=stop, target=target,
                       strategy="s", client_order_id=cid, risk_dollars=qty * abs(10.0 - stop))


def test_registered_as_broker():
    assert registry_get("broker", "paper_sim") is PaperSimBroker


def test_fill_with_slippage_then_exit_at_target():
    broker = PaperSimBroker(starting_cash=10_000, slippage_bps=10)
    result = broker.submit(intent())
    assert result["status"] == "accepted" and result["duplicate"] is False
    assert broker.open_orders()[0]["client_order_id"] == "c1"

    fills = broker.fill_open({"AAPL": 10.0})
    assert len(fills) == 1 and fills[0]["price"] == 10.01  # 10 bps adverse
    assert broker.cash == pytest.approx(10_000 - 1001)
    position = broker.positions()[0]
    assert position.qty == 100 and position.avg_entry == 10.01 and position.stop == 8.0
    assert broker.open_orders() == [] and broker.get_order("c1")["status"] == "filled"

    assert broker.mark({"AAPL": {"open": 10, "high": 12, "low": 9.5, "close": 11}}) == []
    assert broker.account()["equity"] == pytest.approx(10_000 - 1001 + 1100)

    exits = broker.mark({"AAPL": {"open": 12, "high": 16.5, "low": 11.5, "close": 16}})
    assert exits[0]["reason"] == "target" and exits[0]["exit"] == 16.0
    assert broker.positions() == [] and broker.cash == pytest.approx(10_000 - 1001 + 1600)
    assert broker.closed_trades[0]["pnl"] == pytest.approx(599.0)


def test_stop_wins_over_target_and_gap_fills_at_open():
    broker = PaperSimBroker(slippage_bps=0)
    broker.submit(intent())
    broker.fill_open({"AAPL": 10.0})
    exits = broker.mark({"AAPL": {"open": 7.5, "high": 17.0, "low": 7.0, "close": 9.0}})
    assert exits[0]["reason"] == "stop" and exits[0]["exit"] == 7.5
    assert exits[0]["pnl"] == pytest.approx(-250.0)


def test_non_marketable_limit_expires():
    broker = PaperSimBroker()
    broker.submit(intent(limit=10.1))
    assert broker.fill_open({"AAPL": 10.2}) == []
    assert broker.get_order("c1")["status"] == "expired" and broker.positions() == []


def test_duplicate_submit_and_cancel():
    broker = PaperSimBroker()
    first = broker.submit(intent())
    again = broker.submit(intent())
    assert again["duplicate"] is True and again["broker_order_id"] == first["broker_order_id"]
    assert len(broker.open_orders()) == 1
    broker.cancel(first["broker_order_id"])
    assert broker.get_order("c1")["status"] == "canceled"
    assert broker.fill_open({"AAPL": 10.0}) == []
    with pytest.raises(KeyError):
        broker.cancel("nope")


def test_insufficient_cash_rejects_fill():
    broker = PaperSimBroker(starting_cash=500)
    broker.submit(intent())
    broker.fill_open({"AAPL": 10.0})
    assert broker.get_order("c1")["status"] == "rejected" and broker.positions() == []


def test_short_round_trip():
    broker = PaperSimBroker(starting_cash=10_000, slippage_bps=0)
    broker.submit(intent(side=Side.SHORT, limit=9.9, stop=11.0, target=7.0))
    broker.fill_open({"AAPL": 10.0})
    assert broker.cash == pytest.approx(11_000) and broker.account()["equity"] == pytest.approx(10_000)
    exits = broker.mark({"AAPL": {"open": 8.0, "high": 8.5, "low": 6.9, "close": 7.2}})
    assert exits[0]["reason"] == "target" and exits[0]["pnl"] == pytest.approx(300.0)
    assert broker.cash == pytest.approx(10_300)


def test_commission_and_new_day_baseline():
    broker = PaperSimBroker(starting_cash=1_000, slippage_bps=0, commission_per_share=0.01)
    broker.submit(intent(qty=10))
    broker.fill_open({"AAPL": 10.0})
    assert broker.cash == pytest.approx(1_000 - 100 - 0.10)
    broker.new_day()
    assert broker.account()["last_equity"] == pytest.approx(broker.account()["equity"])
    trade = broker.close_position("AAPL", 11.0, reason="time")
    assert trade["pnl"] == pytest.approx(10 - 0.20) and trade["reason"] == "time"
