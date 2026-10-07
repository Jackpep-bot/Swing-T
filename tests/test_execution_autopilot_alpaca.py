"""Autopilot and exit paths on AlpacaBroker with a mocked TradingClient (never a real endpoint): paper vs live
approval, staging, bracket-leg cancel before close, stop-leg replace and the never-loosen guard."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from alpaca.common.exceptions import APIError
from alpaca.trading.models import Order, TradeAccount
from alpaca.trading.requests import ReplaceOrderRequest, StopOrderRequest

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import OrderIntent, Side
from swing_engine.execution.alpaca_broker import NO_POSITION, AlpacaBroker
from swing_engine.execution.autopilot import APPROVER_LIVE, APPROVER_PAPER, AutopilotMode, run_autopilot
from swing_engine.execution.ledger import OrderLedger
from swing_engine.execution.order_manager import OrderManager, OrderRefused
from swing_engine.execution.position_manager import ExitAction, ExitKind, ExitReason

FIXTURES = Path(__file__).parent / "fixtures" / "execution"
AS_OF = date(2026, 9, 30)
SECRETS = Secrets(_env_file=None)
LIVE_ENV = {"SWING_ALLOW_LIVE": "yes"}
PARENT_CID = "swing-sr_bounce-AAPL-20260925-long"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def api_error(status: int) -> APIError:
    http_error = MagicMock()
    http_error.response.status_code = status
    return APIError('{"code":40410000,"message":"not found"}', http_error)


def make_settings(tmp_path: Path, **execution: Any) -> Settings:
    return Settings.model_validate(
        {
            "data": {"store_path": str(tmp_path / "data" / "swing.duckdb")},
            "risk": {
                "kill_switch_file": str(tmp_path / "state" / "KILL"),
                "limits_state_file": str(tmp_path / "state" / "limits.json"),
            },
            "execution": {"ledger_file": str(tmp_path / "state" / "orders.sqlite"), **execution},
        }
    )


def intent(symbol: str = "MSFT") -> OrderIntent:
    return OrderIntent(
        symbol=symbol, side=Side.LONG, qty=50, entry_limit=101.0, stop=95.0, target=120.0, strategy="sr_bounce",
        client_order_id=f"swing-sr_bounce-{symbol}-{AS_OF:%Y%m%d}-long", risk_dollars=300.0,
    )


def bracket(stop_price: str = "95.00") -> dict[str, Any]:
    return {
        "id": "parent-1", "client_order_id": PARENT_CID, "symbol": "AAPL", "status": "filled", "side": "buy",
        "order_type": "limit", "filled_at": "2026-09-25T13:30:02Z",
        "legs": [
            {"id": "leg-tp", "symbol": "AAPL", "status": "new", "side": "sell", "order_type": "limit",
             "limit_price": "120.00"},
            {"id": "leg-stop", "symbol": "AAPL", "status": "held", "side": "sell", "order_type": "stop",
             "stop_price": stop_price},
        ],
    }  # fmt: skip


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.get_order_by_client_id.side_effect = api_error(404)
    mock.submit_order.return_value = Order.model_validate(load("alpaca_order.json"))
    mock.get_all_positions.return_value = []
    mock.get_account.return_value = TradeAccount.model_validate(load("alpaca_account.json"))
    mock.get_orders.return_value = []
    mock.get_order_by_id.return_value = {"status": "canceled"}
    mock.close_position.return_value = {"id": "close-1", "client_order_id": "c1", "status": "accepted"}
    mock.replace_order_by_id.return_value = {"id": "leg-stop-2", "client_order_id": "x", "status": "accepted"}
    return mock


def broker(client: MagicMock, paper: bool = True) -> AlpacaBroker:
    return AlpacaBroker(client=client, paper=paper, env=LIVE_ENV, sleep=lambda _s: None)


# ----------------------------------------------------------------------------------------------------------
# approval mode
# ----------------------------------------------------------------------------------------------------------
def test_alpaca_paper_is_auto_approved(client: MagicMock, tmp_path: Path) -> None:
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker(client), [intent()])
    assert report.mode is AutopilotMode.PAPER and report.approved_by == APPROVER_PAPER and report.submitted == 1
    request = client.submit_order.call_args.args[0]
    assert request.time_in_force.value == "gtc" and request.order_class.value == "bracket"


def test_alpaca_live_is_staged_without_auto_submit_live(client: MagicMock, tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    report = run_autopilot(settings, SECRETS, AS_OF, broker(client, paper=False), [intent()], env=LIVE_ENV)
    assert report.mode is AutopilotMode.STAGED and not report.paper and report.staged_path
    client.submit_order.assert_not_called()
    assert json.loads(Path(report.staged_path).read_text())["intents"][0]["symbol"] == "MSFT"


def test_alpaca_live_needs_both_auto_submit_live_and_env(client: MagicMock, tmp_path: Path) -> None:
    settings = make_settings(tmp_path, auto_submit_live=True)
    no_env = run_autopilot(settings, SECRETS, AS_OF, broker(client, paper=False), [intent()], env={})
    assert no_env.mode is AutopilotMode.STAGED
    client.submit_order.assert_not_called()
    live = run_autopilot(settings, SECRETS, AS_OF, broker(client, paper=False), [intent()], env=LIVE_ENV)
    assert live.mode is AutopilotMode.LIVE and live.approved_by == APPROVER_LIVE and live.submitted == 1
    client.submit_order.assert_called_once()


# ----------------------------------------------------------------------------------------------------------
# exit paths on the adapter
# ----------------------------------------------------------------------------------------------------------
def test_close_position_cancels_legs_waits_then_liquidates(client: MagicMock) -> None:
    client.get_orders.return_value = [bracket(), {"id": "other", "symbol": "MSFT", "status": "new"}]
    statuses = iter([{"status": "pending_cancel"}, {"status": "canceled"}, {"status": "canceled"}])
    client.get_order_by_id.side_effect = lambda oid: next(statuses)
    sleeps: list[float] = []
    b = AlpacaBroker(client=client, paper=True, sleep=sleeps.append)
    result = b.close_position("AAPL")
    cancelled = [c.args[0] for c in client.cancel_order_by_id.call_args_list]
    assert cancelled == ["leg-tp", "leg-stop"] and len(sleeps) == 1  # the filled parent is not cancelable
    client.close_position.assert_called_once_with("AAPL", close_options=None)
    assert result["broker_order_id"] == "close-1" and result["canceled"] == cancelled


def test_close_position_without_a_position_reports_no_position(client: MagicMock) -> None:
    client.close_position.side_effect = api_error(404)
    assert broker(client).close_position("ZZZ")["status"] == NO_POSITION


def test_close_position_tolerates_a_failed_cancel(client: MagicMock) -> None:
    client.get_orders.return_value = [bracket()]
    client.cancel_order_by_id.side_effect = [api_error(422), None]
    result = broker(client).close_position("AAPL", qty=100)
    assert result["status"] == "accepted" and client.cancel_order_by_id.call_count == 2


def test_replace_stop_patches_the_stop_leg_and_never_loosens(client: MagicMock) -> None:
    client.get_orders.return_value = [bracket("95.00")]
    b = broker(client)
    result = b.replace_stop("AAPL", 100.004)
    order_id, request = client.replace_order_by_id.call_args.args
    assert order_id == "leg-stop" and isinstance(request, ReplaceOrderRequest) and request.stop_price == 100.0
    assert result["previous_stop"] == 95.0 and result["new_stop"] == 100.0
    with pytest.raises(ValueError, match="loosen"):
        b.replace_stop("AAPL", 94.0)
    with pytest.raises(LookupError):
        b.replace_stop("MSFT", 50.0)


def test_order_manager_refuses_unapproved_or_loosening_exits(client: MagicMock, tmp_path: Path) -> None:
    client.get_orders.return_value = [bracket("95.00")]
    manager = OrderManager(broker(client), None, tmp_path / "KILL", ledger=OrderLedger(":memory:"))
    with pytest.raises(OrderRefused, match="approval"):
        manager.close_position("AAPL", approved_by=" ")
    with pytest.raises(OrderRefused, match="loosen"):
        manager.replace_stop("AAPL", 90.0, approved_by="jane")
    (tmp_path / "KILL").write_text("x")
    with pytest.raises(OrderRefused, match="kill switch"):
        manager.replace_stop("AAPL", 100.0, approved_by="jane")
    assert manager.close_position("AAPL", approved_by="jane")["status"] == "closed"  # exposure-reducing


def test_autopilot_executes_alpaca_exits_before_entries(client: MagicMock, tmp_path: Path) -> None:
    client.get_orders.return_value = [bracket("95.00")]
    exits = [
        ExitAction(kind=ExitKind.REPLACE_STOP, symbol="AAPL", reason=ExitReason.BREAKEVEN, new_stop=100.0,
                   order_id="leg-stop"),
        ExitAction(kind=ExitKind.CLOSE, symbol="AAPL", reason=ExitReason.EARNINGS, qty=100, ref_price=106.0),
    ]
    calls: list[str] = []
    client.replace_order_by_id.side_effect = lambda *a: calls.append("replace") or {"id": "s2", "status": "new"}
    client.close_position.side_effect = lambda *a, **k: calls.append("close") or {"id": "c", "status": "new"}
    client.submit_order.side_effect = lambda *a: calls.append("submit") or Order.model_validate(load("alpaca_order.json"))
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker(client), [intent()], exit_actions=exits)
    assert [r.status.value for r in report.exits] == ["done", "done"] and report.submitted == 1
    assert calls == ["replace", "close", "submit"]
    _, kwargs = client.close_position.call_args
    assert kwargs["close_options"] is None  # the whole live position is flattened, not the planned snapshot qty


# ----------------------------------------------------------------------------------------------------------
# regressions: a failed liquidation must not leave the position without a stop
# ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("failure", [api_error(403), ConnectionError("reset by peer")])
def test_failed_close_restores_the_cancelled_stop_leg(client: MagicMock, failure: Exception) -> None:
    client.get_orders.return_value = [bracket("95.00")]
    client.get_open_position.return_value = {"symbol": "AAPL", "qty": "100", "side": "long"}
    client.close_position.side_effect = failure
    client.submit_order.return_value = {"id": "rearm-1", "client_order_id": "rearm-AAPL-1", "status": "accepted"}
    with pytest.raises(type(failure)):
        broker(client).close_position("AAPL")
    assert [c.args[0] for c in client.cancel_order_by_id.call_args_list] == ["leg-tp", "leg-stop"]
    request = client.submit_order.call_args.args[0]
    assert isinstance(request, StopOrderRequest) and request.stop_price == 95.0 and request.qty == 100
    assert request.side.value == "sell" and request.time_in_force.value == "gtc"
    assert request.client_order_id.startswith("rearm-AAPL-")  # never parsed as a swing-* strategy entry


def test_failed_close_does_not_restore_a_leg_whose_cancel_never_settled(client: MagicMock) -> None:
    client.get_orders.return_value = [bracket("95.00")]
    client.get_order_by_id.side_effect = lambda oid: {"status": "pending_cancel" if oid == "leg-stop" else "canceled"}
    client.close_position.side_effect = api_error(403)
    with pytest.raises(APIError):
        broker(client).close_position("AAPL")
    client.submit_order.assert_not_called()  # the original stop leg is still working


def test_place_stop_arms_a_stop_only_when_none_is_open(client: MagicMock) -> None:
    client.get_open_position.return_value = {"symbol": "AAPL", "qty": "40", "side": "long"}
    client.submit_order.return_value = {"id": "s1", "client_order_id": "rearm-AAPL-1", "status": "accepted"}
    result = broker(client).place_stop("AAPL", 97.004)
    request = client.submit_order.call_args.args[0]
    assert isinstance(request, StopOrderRequest) and request.qty == 40 and request.stop_price == 97.0
    assert result["stop"] == 97.0 and result["broker_order_id"] == "s1"
    client.get_orders.return_value = [bracket("95.00")]
    with pytest.raises(ValueError, match="already has an open stop"):
        broker(client).place_stop("AAPL", 97.0)
    client.get_orders.return_value = []
    client.get_open_position.side_effect = api_error(404)
    with pytest.raises(LookupError):
        broker(client).place_stop("ZZZ", 1.0)
