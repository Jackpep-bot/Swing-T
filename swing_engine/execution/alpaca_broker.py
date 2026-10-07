"""Alpaca broker adapter on top of alpaca-py's ``TradingClient``.

Paper by default. Live trading needs BOTH ``ALPACA_PAPER=false`` (``Secrets.alpaca_paper``) and the process
environment variable ``SWING_ALLOW_LIVE=yes``; anything else raises :class:`LiveTradingBlocked` at construction.
Entries are bracket orders (stop + target) or OTO (stop only) with GTC legs so the protective legs survive the
entry day. Prices are rounded to cents (Alpaca rejects sub-penny prices on stocks over $1).
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import structlog

from swing_engine.core.config import Secrets, load_secrets
from swing_engine.core.interfaces import Broker
from swing_engine.core.models import OrderIntent, Position, Side
from swing_engine.core.registry import register
from swing_engine.risk.limits import PCT

try:
    from alpaca.common.exceptions import APIError
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
    from alpaca.trading.requests import (
        GetOrdersRequest,
        LimitOrderRequest,
        MarketOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
    )

    ALPACA_AVAILABLE = True
except ImportError:  # pragma: no cover - alpaca-py is a hard dependency, guarded like lightgbm for safety
    ALPACA_AVAILABLE = False

log = structlog.get_logger(__name__)

LIVE_OVERRIDE_ENV = "SWING_ALLOW_LIVE"
LIVE_OVERRIDE_VALUE = "yes"
PRICE_DECIMALS = 2
HTTP_NOT_FOUND = 404
SHORT_SIDE_SUFFIX = "short"


class LiveTradingBlocked(RuntimeError):
    """Raised when a non-paper Alpaca session is requested without the explicit live override."""


def resolve_paper_mode(
    paper: bool | None = None, secrets: Secrets | None = None, env: Mapping[str, str] | None = None
) -> bool:
    """True for paper. Returns False (live) only with ``ALPACA_PAPER=false`` AND ``SWING_ALLOW_LIVE=yes``."""
    if paper is None:
        paper = (secrets or load_secrets()).alpaca_paper
    if paper:
        return True
    environ: Mapping[str, str] = os.environ if env is None else env
    if environ.get(LIVE_OVERRIDE_ENV) != LIVE_OVERRIDE_VALUE:
        raise LiveTradingBlocked(
            f"ALPACA_PAPER is false but {LIVE_OVERRIDE_ENV}={LIVE_OVERRIDE_VALUE!r} is not set; refusing to trade live"
        )
    log.warning("alpaca_live_mode_enabled")
    return False


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, Mapping):
        return dict(obj)
    return dict(vars(obj))


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _status_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


@register("broker", "alpaca")
class AlpacaBroker(Broker):
    name = "alpaca"

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        paper: bool | None = None,
        secrets: Secrets | None = None,
        client: Any | None = None,
        stop_limit_band_pct: float | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py is not importable; install it or use the paper_sim broker")
        self.paper = resolve_paper_mode(paper, secrets, env)
        self.stop_limit_band_pct = stop_limit_band_pct
        if client is None:
            sec = secrets or load_secrets()
            api_key = api_key or sec.alpaca_api_key
            secret_key = secret_key or sec.alpaca_secret_key
            if not api_key or not secret_key:
                raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required for the alpaca broker")
            client = TradingClient(api_key, secret_key, paper=self.paper)
        self.client = client
        log.info("alpaca_broker_ready", paper=self.paper)

    # ------------------------------------------------------------ Broker API
    def account(self) -> dict[str, Any]:
        raw = _to_dict(self.client.get_account())
        out: dict[str, Any] = {
            key: _float_or_none(raw.get(key)) for key in ("equity", "last_equity", "cash", "buying_power", "portfolio_value")
        }
        out.update(
            status=_status_text(raw.get("status")),
            trading_blocked=bool(raw.get("trading_blocked", False)),
            paper=self.paper,
            broker=self.name,
            raw=raw,
        )
        return out

    def positions(self) -> list[Position]:
        out: list[Position] = []
        for item in self.client.get_all_positions():
            raw = _to_dict(item)
            qty = int(float(raw["qty"]))
            is_short = _status_text(raw.get("side")).lower().endswith(SHORT_SIDE_SUFFIX) or qty < 0
            out.append(
                Position(
                    symbol=str(raw["symbol"]),
                    qty=abs(qty),
                    avg_entry=float(raw["avg_entry_price"]),
                    side=Side.SHORT if is_short else Side.LONG,
                )
            )
        return out

    def submit(self, intent: OrderIntent) -> dict[str, Any]:
        """Bracket (or OTO) entry; returns the existing order instead of resubmitting a known client_order_id."""
        existing = self.get_order(intent.client_order_id)
        if existing is not None:
            log.info("alpaca_duplicate_order", client_order_id=intent.client_order_id, status=existing.get("status"))
            return self._result(existing, duplicate=True)
        request = self.build_request(intent)
        order = _to_dict(self.client.submit_order(request))
        result = self._result(order)
        log.info("alpaca_order_submitted", symbol=intent.symbol, qty=intent.qty, status=result["status"],
                 broker_order_id=result["broker_order_id"], paper=self.paper)
        return result

    def open_orders(self) -> list[dict[str, Any]]:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN, nested=True)
        return [_to_dict(o) for o in self.client.get_orders(request)]

    def cancel(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)
        log.info("alpaca_order_canceled", broker_order_id=order_id)

    def get_order(self, client_order_id: str) -> dict[str, Any] | None:
        try:
            return _to_dict(self.client.get_order_by_client_id(client_order_id))
        except APIError as exc:
            if exc.status_code == HTTP_NOT_FOUND:
                return None
            raise

    # ------------------------------------------------------------ helpers
    def build_request(self, intent: OrderIntent) -> Any:
        side = OrderSide.BUY if intent.side == Side.LONG else OrderSide.SELL
        stop_loss = StopLossRequest(stop_price=round(intent.stop, PRICE_DECIMALS), limit_price=self._stop_limit_price(intent))
        take_profit = (
            TakeProfitRequest(limit_price=round(intent.target, PRICE_DECIMALS)) if intent.target is not None else None
        )
        common: dict[str, Any] = {
            "symbol": intent.symbol,
            "qty": intent.qty,
            "side": side,
            "time_in_force": TimeInForce.GTC,
            "order_class": OrderClass.BRACKET if take_profit is not None else OrderClass.OTO,
            "client_order_id": intent.client_order_id,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        if intent.entry_limit is not None:
            return LimitOrderRequest(limit_price=round(intent.entry_limit, PRICE_DECIMALS), **common)
        return MarketOrderRequest(**common)

    def _stop_limit_price(self, intent: OrderIntent) -> float | None:
        if self.stop_limit_band_pct is None:
            return None
        band = self.stop_limit_band_pct / PCT
        px = intent.stop * (1 - band) if intent.side == Side.LONG else intent.stop * (1 + band)
        return round(px, PRICE_DECIMALS)

    @staticmethod
    def _result(order: dict[str, Any], duplicate: bool = False) -> dict[str, Any]:
        return {
            "broker_order_id": str(order.get("id", "")),
            "client_order_id": order.get("client_order_id"),
            "status": _status_text(order.get("status")).lower(),
            "duplicate": duplicate,
            "raw": order,
        }
