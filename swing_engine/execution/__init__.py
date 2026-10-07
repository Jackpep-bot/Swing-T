"""Execution layer: broker adapters and the OrderManager, the only path from an OrderIntent to a broker."""
from swing_engine.execution.alpaca_broker import AlpacaBroker, LiveTradingBlocked
from swing_engine.execution.autopilot import AutopilotReport, run_autopilot
from swing_engine.execution.ledger import OrderLedger, OrderStatus
from swing_engine.execution.order_manager import OrderManager, OrderRefused
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.execution.position_manager import ExitAction, ExitKind, review_positions

__all__ = [
    "AlpacaBroker",
    "AutopilotReport",
    "ExitAction",
    "ExitKind",
    "LiveTradingBlocked",
    "OrderLedger",
    "OrderManager",
    "OrderRefused",
    "OrderStatus",
    "PaperSimBroker",
    "review_positions",
    "run_autopilot",
]
