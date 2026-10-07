"""OrderManager: approval required, kill switch blocks, ledger idempotency, limits, reconcile."""
from __future__ import annotations

import pytest

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Side
from swing_engine.execution.ledger import OrderLedger, OrderStatus
from swing_engine.execution.order_manager import OrderManager, OrderRefused, validate_intent
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.risk import killswitch
from swing_engine.risk.limits import LimitState

CID = "swing-s-AAPL-20261006-long"


def intent(qty: int = 100, cid: str = CID, **overrides) -> OrderIntent:
    base = {"symbol": "AAPL", "side": Side.LONG, "qty": qty, "entry_limit": 10.1, "stop": 8.0, "target": 16.0,
            "strategy": "s", "client_order_id": cid, "risk_dollars": qty * 2.0}
    base.update(overrides)
    return OrderIntent(**base)


@pytest.fixture
def manager(tmp_path) -> OrderManager:
    broker = PaperSimBroker(starting_cash=50_000)
    return OrderManager(broker, LimitState(RiskConfig()), killswitch_path=tmp_path / "KILL", ledger_path=":memory:")


def test_requires_non_empty_approval(manager):
    with pytest.raises(OrderRefused, match="approval required"):
        manager.submit(intent(), approved_by="")
    with pytest.raises(OrderRefused, match="approval required"):
        manager.submit(intent(), approved_by="   ")
    assert manager.broker.open_orders() == []
    assert manager.ledger.get(CID) is None


def test_kill_switch_blocks(manager, tmp_path):
    killswitch.trip(tmp_path / "KILL", "test")
    with pytest.raises(OrderRefused, match="kill switch"):
        manager.submit(intent(), approved_by="owner")
    assert manager.broker.open_orders() == [] and manager.ledger.get(CID) is None
    killswitch.reset(tmp_path / "KILL")
    assert manager.submit(intent(), approved_by="owner")["status"] == "accepted"


def test_submit_then_duplicate_never_hits_broker_twice(manager):
    first = manager.submit(intent(), approved_by="owner")
    assert first["status"] == "accepted" and first["broker_order_id"] == "sim-1" and first["approved_by"] == "owner"
    again = manager.submit(intent(), approved_by="someone-else")
    assert again["status"] == "duplicate" and again["broker_order_id"] == "sim-1" and again["approved_by"] == "owner"
    assert len(manager.broker.open_orders()) == 1
    row = manager.ledger.get(CID)
    assert row["status"] == "accepted" and row["intent"]["qty"] == 100 and row["broker"]["id"] == "sim-1"


def test_limit_failure_refuses(manager):
    with pytest.raises(OrderRefused, match="limit check failed: position"):
        manager.submit(intent(qty=10_000), approved_by="owner")
    assert manager.ledger.get(CID) is None and manager.broker.open_orders() == []


def test_invalid_intent_refused(manager):
    with pytest.raises(OrderRefused, match="invalid intent"):
        manager.submit(intent(stop=12.0), approved_by="owner")
    assert validate_intent(intent(target=9.0)) == "long target must be above the entry"
    assert validate_intent(intent(side=Side.SHORT, entry_limit=9.9, stop=11.0, target=7.0)) is None
    assert validate_intent(intent(side=Side.SHORT, entry_limit=9.9, stop=9.0, target=7.0)) is not None


def test_ledger_persists_across_processes(tmp_path):
    path = tmp_path / "orders.sqlite"
    first = OrderManager(PaperSimBroker(), None, killswitch_path=tmp_path / "KILL", ledger_path=path)
    first.submit(intent(), approved_by="owner")
    first.ledger.close()
    second = OrderManager(PaperSimBroker(), None, killswitch_path=tmp_path / "KILL", ledger_path=path)
    assert second.submit(intent(), approved_by="owner")["status"] == "duplicate"
    assert second.broker.open_orders() == []


def test_broker_error_is_recorded_and_blocks_resubmit(manager, monkeypatch):
    def boom(_intent):
        raise RuntimeError("api down")

    monkeypatch.setattr(manager.broker, "submit", boom)
    with pytest.raises(RuntimeError, match="api down"):
        manager.submit(intent(), approved_by="owner")
    row = manager.ledger.get(CID)
    assert row["status"] == OrderStatus.ERROR and row["broker"] == {"error": "api down"}
    assert [r["client_order_id"] for r in manager.ledger.pending()] == [CID]
    monkeypatch.undo()
    assert manager.submit(intent(), approved_by="owner")["status"] == "duplicate"


def test_reconcile_updates_fill_status_and_flags_unknown_positions(manager):
    manager.submit(intent(), approved_by="owner")
    manager.broker.fill_open({"AAPL": 10.0})
    manager.broker.submit(intent(cid="rogue", symbol="TSLA"))  # placed outside the manager
    manager.broker.fill_open({"TSLA": 10.0})
    summary = manager.reconcile()
    assert summary["updated"] == [{"client_order_id": CID, "from": "accepted", "to": "filled"}]
    assert summary["unknown_positions"] == ["TSLA"] and summary["kill_switch"] is False
    assert manager.ledger.get(CID)["status"] == "filled" and manager.ledger.pending() == []
    assert {p["symbol"] for p in summary["positions"]} == {"AAPL", "TSLA"}


def test_reconcile_reports_unresolved_rows(manager):
    manager.ledger.reserve(intent(cid="ghost"), "owner")
    summary = manager.reconcile()
    assert summary["unresolved"] == ["ghost"] and summary["checked"] == 1


def test_cancel_goes_through_ledger(manager):
    manager.submit(intent(), approved_by="owner")
    result = manager.cancel(CID)
    assert result["status"] == "canceled" and manager.broker.open_orders() == []
    assert manager.ledger.get(CID)["status"] == "canceled"
    with pytest.raises(KeyError):
        manager.cancel("missing")


def test_ledger_reserve_is_atomic():
    ledger = OrderLedger(":memory:")
    assert ledger.reserve(intent(), "owner") is True
    assert ledger.reserve(intent(), "owner") is False
    assert ledger.get(CID)["status"] == "submitting"
    ledger.update(CID, "FILLED", broker_order_id="x", broker_json={"ok": True})
    assert ledger.get(CID)["status"] == "filled" and ledger.pending() == []
    assert ledger.all()[0]["broker"] == {"ok": True}
