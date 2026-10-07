"""Alpaca adapter against a mocked TradingClient: live guard, bracket/OTO requests, idempotency, mapping."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.models import Order, TradeAccount
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

from swing_engine.core.config import Secrets
from swing_engine.core.models import OrderIntent, Side
from swing_engine.core.registry import get as registry_get
from swing_engine.execution.alpaca_broker import (
    LIVE_OVERRIDE_ENV,
    AlpacaBroker,
    LiveTradingBlocked,
    resolve_paper_mode,
)
from swing_engine.execution.order_manager import OrderManager

FIXTURES = Path(__file__).parent / "fixtures" / "execution"
CID = "swing-sr_bounce-AAPL-20261006-long"
ORDER_ID = "904837e3-3b76-47ec-b432-046db621571b"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def api_error(status: int) -> APIError:
    http_error = MagicMock()
    http_error.response.status_code = status
    return APIError('{"code":40410000,"message":"order not found"}', http_error)


def intent(**overrides) -> OrderIntent:
    base = {"symbol": "AAPL", "side": Side.LONG, "qty": 250, "entry_limit": 10.1, "stop": 8.0, "target": 16.0,
            "strategy": "sr_bounce", "client_order_id": CID, "risk_dollars": 500.0}
    base.update(overrides)
    return OrderIntent(**base)


@pytest.fixture
def client() -> MagicMock:
    mock = MagicMock()
    mock.get_order_by_client_id.side_effect = api_error(404)
    mock.submit_order.return_value = Order.model_validate(load("alpaca_order.json"))
    mock.get_all_positions.return_value = [AlpacaPosition.model_validate(load("alpaca_position.json"))]
    mock.get_account.return_value = TradeAccount.model_validate(load("alpaca_account.json"))
    mock.get_orders.return_value = [Order.model_validate(load("alpaca_order.json"))]
    return mock


def test_registered_as_broker():
    assert registry_get("broker", "alpaca") is AlpacaBroker


def test_live_guard_requires_both_flags(monkeypatch):
    monkeypatch.delenv(LIVE_OVERRIDE_ENV, raising=False)
    with pytest.raises(LiveTradingBlocked):
        AlpacaBroker(paper=False, client=MagicMock())
    assert resolve_paper_mode(True) is True
    assert resolve_paper_mode(False, env={LIVE_OVERRIDE_ENV: "yes"}) is False
    with pytest.raises(LiveTradingBlocked):
        resolve_paper_mode(False, env={LIVE_OVERRIDE_ENV: "YES"})
    with pytest.raises(LiveTradingBlocked):
        resolve_paper_mode(False, env={})


def test_paper_flag_comes_from_secrets(monkeypatch):
    monkeypatch.delenv(LIVE_OVERRIDE_ENV, raising=False)
    monkeypatch.setenv("ALPACA_PAPER", "false")
    with pytest.raises(LiveTradingBlocked):
        resolve_paper_mode(None, secrets=Secrets(_env_file=None))
    monkeypatch.setenv("ALPACA_PAPER", "true")
    assert AlpacaBroker(secrets=Secrets(_env_file=None), client=MagicMock()).paper is True


def test_missing_keys_raise(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="ALPACA_API_KEY"):
        AlpacaBroker(paper=True, secrets=Secrets(_env_file=None))


def test_submit_builds_limit_bracket(client):
    broker = AlpacaBroker(paper=True, client=client)
    result = broker.submit(intent())
    assert result["status"] == "accepted" and result["broker_order_id"] == ORDER_ID and result["duplicate"] is False
    request = client.submit_order.call_args.args[0]
    assert isinstance(request, LimitOrderRequest)
    assert request.order_class == OrderClass.BRACKET and request.side == OrderSide.BUY
    assert request.time_in_force == TimeInForce.GTC and request.qty == 250 and request.limit_price == 10.1
    assert request.stop_loss.stop_price == 8.0 and request.stop_loss.limit_price is None
    assert request.take_profit.limit_price == 16.0 and request.client_order_id == CID


def test_submit_market_oto_without_target(client):
    broker = AlpacaBroker(paper=True, client=client)
    broker.submit(intent(entry_limit=None, target=None))
    request = client.submit_order.call_args.args[0]
    assert isinstance(request, MarketOrderRequest)
    assert request.order_class == OrderClass.OTO and request.take_profit is None and request.stop_loss.stop_price == 8.0


def test_short_side_and_stop_limit_band(client):
    broker = AlpacaBroker(paper=True, client=client, stop_limit_band_pct=1.0)
    broker.submit(intent(side=Side.SHORT, entry_limit=9.9, stop=11.0, target=7.0))
    request = client.submit_order.call_args.args[0]
    assert request.side == OrderSide.SELL and request.stop_loss.limit_price == 11.11


def test_known_client_order_id_is_not_resubmitted(client):
    client.get_order_by_client_id.side_effect = None
    client.get_order_by_client_id.return_value = Order.model_validate(load("alpaca_order.json"))
    result = AlpacaBroker(paper=True, client=client).submit(intent())
    assert result["duplicate"] is True and result["broker_order_id"] == ORDER_ID
    client.submit_order.assert_not_called()


def test_non_404_lookup_error_propagates_without_submitting(client):
    client.get_order_by_client_id.side_effect = api_error(500)
    with pytest.raises(APIError):
        AlpacaBroker(paper=True, client=client).submit(intent())
    client.submit_order.assert_not_called()


def test_positions_account_open_orders_cancel(client):
    broker = AlpacaBroker(paper=True, client=client)
    positions = broker.positions()
    assert positions[0].symbol == "AAPL" and positions[0].qty == 250 and positions[0].side == Side.LONG
    assert positions[0].avg_entry == 10.05
    account = broker.account()
    assert account["equity"] == 100_000.0 and account["last_equity"] == 99_000.0 and account["paper"] is True
    assert account["status"] == "ACTIVE" and account["trading_blocked"] is False
    orders = broker.open_orders()
    assert orders[0]["client_order_id"] == CID and orders[0]["status"] == "accepted"
    broker.cancel("abc")
    client.cancel_order_by_id.assert_called_once_with("abc")


def test_order_manager_end_to_end_with_mocked_alpaca(client, tmp_path):
    manager = OrderManager(AlpacaBroker(paper=True, client=client), None, tmp_path / "KILL", ledger_path=":memory:")
    result = manager.submit(intent(), approved_by="owner")
    assert result["status"] == "accepted" and result["broker_order_id"] == ORDER_ID
    assert manager.ledger.get(CID)["broker_order_id"] == ORDER_ID
    assert manager.submit(intent(), approved_by="owner")["status"] == "duplicate"
    client.submit_order.assert_called_once()
    summary = manager.reconcile()
    assert summary["unknown_positions"] == ["AAPL"] and summary["open_orders"] == 1
