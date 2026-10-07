"""Alpaca broker adapter on top of alpaca-py's ``TradingClient``.

Paper by default. Live trading needs BOTH ``ALPACA_PAPER=false`` (``Secrets.alpaca_paper``) and the process
environment variable ``SWING_ALLOW_LIVE=yes``; anything else raises :class:`LiveTradingBlocked` at construction.
Entries are bracket orders (stop + target) or OTO (stop only) with GTC legs so the protective legs survive the
entry day. Prices are rounded to cents (Alpaca rejects sub-penny prices on stocks over $1).

Time-in-force choice (https://docs.alpaca.markets/docs/orders-at-alpaca, checked 2026-10-06): bracket/OTO/OCO
orders accept only ``day`` or ``gtc``, the take-profit and stop-loss legs inherit the parent's time_in_force,
and brackets cannot be extended-hours. ``day`` would cancel the protective legs at the close of the entry day,
so a multi-day swing trade uses ``gtc`` (Alpaca auto-cancels GTC orders 90 days after creation, longer than
any strategy's hold). The cost of GTC is that an unfilled entry also persists, so
``execution.position_manager`` cancels entries still unfilled after
``execution.cancel_unfilled_entries_after_sessions`` sessions. Stops are tightened by replacing the stop leg
(PATCH /v2/orders/{id}, https://docs.alpaca.markets/reference/patchorderbyorderid-1; returns a new order id;
not allowed while the order is ``accepted``/``pending_*``). Positions are closed with DELETE
/v2/positions/{symbol} after cancelling the symbol's open legs, which otherwise hold the shares. If that
liquidation fails (halted/not tradable, cancels not settled, network) the cancelled stop legs are re-submitted as
plain GTC stops so the position is never left unprotected; ``place_stop`` arms a stop on a position that has
none (``rearm-*`` client ids, so they are never mistaken for a strategy's ``swing-*`` entry).
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Mapping
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
        ClosePositionRequest,
        GetOrdersRequest,
        LimitOrderRequest,
        MarketOrderRequest,
        ReplaceOrderRequest,
        StopLimitOrderRequest,
        StopLossRequest,
        StopOrderRequest,
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
STOP_ORDER_TYPES = frozenset({"stop", "stop_limit"})
SETTLED_STATUSES = frozenset({"canceled", "filled", "expired", "rejected", "replaced", "done_for_day"})
CANCEL_SETTLE_POLLS = 10  # cancels are asynchronous; legs hold the shares until they are really gone
CANCEL_SETTLE_INTERVAL_S = 0.5
NO_POSITION = "no_position"
REARM_PREFIX = "rearm"  # client ids of re-armed protective stops (not swing-*: never read as a strategy entry)


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


def _flatten(orders: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Top-level orders plus their nested bracket legs (``nested=True`` listings)."""
    out: list[dict[str, Any]] = []
    for order in orders:
        out.append(order)
        for leg in order.get("legs") or []:
            item = _to_dict(leg)
            item.setdefault("symbol", order.get("symbol"))
            out.append(item)
    return out


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
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py is not importable; install it or use the paper_sim broker")
        self.paper = resolve_paper_mode(paper, secrets, env)
        self.stop_limit_band_pct = stop_limit_band_pct
        self.sleep = sleep
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

    # ------------------------------------------------------------ exits (execution.autopilot via OrderManager)
    def close_position(self, symbol: str, qty: int | None = None) -> dict[str, Any]:
        """Cancel the symbol's open orders (bracket legs reserve the shares), wait for the cancels to settle,
        then liquidate with DELETE /v2/positions/{symbol} (a market order; queued for the open outside hours).
        ``qty=None`` flattens the whole live position. If the liquidation raises, every stop leg that was
        cancelled is re-submitted (same side, qty and stop price) before the error propagates."""
        working = [
            o for o in _flatten(self.open_orders())
            if o.get("symbol") == symbol and o.get("id")
            and _status_text(o.get("status")).lower() not in SETTLED_STATUSES  # a filled bracket parent stays listed
        ]
        ids = [str(o["id"]) for o in working]
        stops = [o for o in working if self._is_stop_order(o)]
        for oid in ids:
            try:
                self.client.cancel_order_by_id(oid)
            except APIError as exc:  # already done or not cancelable: the close below says whether it mattered
                log.warning("alpaca_cancel_failed", broker_order_id=oid, error=str(exc))
        unsettled = self._await_settled(ids)
        options = ClosePositionRequest(qty=str(qty)) if qty else None
        try:
            order = _to_dict(self.client.close_position(symbol, close_options=options))
        except APIError as exc:
            if exc.status_code == HTTP_NOT_FOUND:
                log.warning("alpaca_close_no_position", symbol=symbol)
                return {"broker_order_id": "", "client_order_id": None, "status": NO_POSITION,
                        "duplicate": False, "raw": {}, "canceled": ids}
            self._restore_stops(symbol, [s for s in stops if str(s["id"]) not in unsettled])
            raise
        except Exception:
            self._restore_stops(symbol, [s for s in stops if str(s["id"]) not in unsettled])
            raise
        result = self._result(order)
        result["canceled"] = ids
        log.info("alpaca_position_close_submitted", symbol=symbol, qty=qty, canceled=len(ids),
                 broker_order_id=result["broker_order_id"], paper=self.paper)
        return result

    def replace_stop(self, symbol: str, new_stop: float, order_id: str | None = None) -> dict[str, Any]:
        """Move the open stop leg of ``symbol`` to ``new_stop`` (PATCH). Refuses to loosen the stop."""
        legs = [
            o for o in _flatten(self.open_orders())
            if o.get("symbol") == symbol and _status_text(o.get("order_type") or o.get("type")).lower() in STOP_ORDER_TYPES
            and _float_or_none(o.get("stop_price")) is not None
        ]
        if order_id is not None:
            legs = [o for o in legs if str(o.get("id")) == str(order_id)]
        if not legs:
            raise LookupError(f"no open stop order for {symbol}" + (f" with id {order_id}" if order_id else ""))
        leg = legs[0]
        current = float(leg["stop_price"])
        stop = round(new_stop, PRICE_DECIMALS)
        exit_is_sell = _status_text(leg.get("side")).lower() != OrderSide.BUY.value
        if (exit_is_sell and stop <= current) or (not exit_is_sell and stop >= current):
            raise ValueError(f"refusing to loosen or keep the {symbol} stop: {current} -> {stop}")
        limit = None
        if _status_text(leg.get("order_type") or leg.get("type")).lower() == "stop_limit" and self.stop_limit_band_pct:
            band = self.stop_limit_band_pct / PCT
            limit = round(stop * (1 - band) if exit_is_sell else stop * (1 + band), PRICE_DECIMALS)
        request = ReplaceOrderRequest(stop_price=stop, limit_price=limit)
        order = _to_dict(self.client.replace_order_by_id(str(leg["id"]), request))
        result = self._result(order)
        result.update(previous_stop=current, new_stop=stop, replaced_order_id=str(leg["id"]))
        log.info("alpaca_stop_replaced", symbol=symbol, previous_stop=current, new_stop=stop, paper=self.paper)
        return result

    def place_stop(self, symbol: str, stop: float) -> dict[str, Any]:
        """Arm a GTC protective stop for the whole live ``symbol`` position. Refuses (``ValueError``) when an
        open stop order already exists and (``LookupError``) when there is no position."""
        existing = [
            o for o in _flatten(self.open_orders())
            if o.get("symbol") == symbol and self._is_stop_order(o)
            and _status_text(o.get("status")).lower() not in SETTLED_STATUSES
        ]
        if existing:
            raise ValueError(f"{symbol} already has an open stop order {existing[0].get('id')}")
        qty, exit_side = self._position_exit(symbol)
        if qty <= 0:
            raise LookupError(f"no open {symbol} position")
        order = self._submit_stop(symbol, qty, exit_side, stop)
        result = self._result(order)
        result.update(stop=round(stop, PRICE_DECIMALS), qty=qty)
        log.info("alpaca_stop_placed", symbol=symbol, stop=result["stop"], qty=qty, paper=self.paper)
        return result

    @staticmethod
    def _is_stop_order(order: Mapping[str, Any]) -> bool:
        kind = _status_text(order.get("order_type") or order.get("type")).lower()
        return kind in STOP_ORDER_TYPES and _float_or_none(order.get("stop_price")) is not None

    def _position_exit(self, symbol: str) -> tuple[int, OrderSide]:
        try:
            raw = _to_dict(self.client.get_open_position(symbol))
        except APIError as exc:
            if exc.status_code == HTTP_NOT_FOUND:
                raise LookupError(f"no open {symbol} position") from exc
            raise
        qty = int(float(raw.get("qty") or 0))
        short = _status_text(raw.get("side")).lower().endswith(SHORT_SIDE_SUFFIX) or qty < 0
        return abs(qty), (OrderSide.BUY if short else OrderSide.SELL)

    def _submit_stop(self, symbol: str, qty: int, side: OrderSide, stop: float) -> dict[str, Any]:
        stop_px = round(stop, PRICE_DECIMALS)
        cid = f"{REARM_PREFIX}-{symbol}-{time.time_ns()}"
        common: dict[str, Any] = {
            "symbol": symbol, "qty": qty, "side": side, "time_in_force": TimeInForce.GTC, "stop_price": stop_px,
            "client_order_id": cid,
        }
        if self.stop_limit_band_pct:
            band = self.stop_limit_band_pct / PCT
            limit = round(stop_px * (1 - band) if side == OrderSide.SELL else stop_px * (1 + band), PRICE_DECIMALS)
            request: Any = StopLimitOrderRequest(limit_price=limit, **common)
        else:
            request = StopOrderRequest(**common)
        return _to_dict(self.client.submit_order(request))

    def _restore_stops(self, symbol: str, legs: list[dict[str, Any]]) -> list[str]:
        """Re-submit cancelled stop legs after a failed liquidation. Never raises: the close error matters more."""
        restored: list[str] = []
        for leg in legs:
            try:
                qty = int(float(leg["qty"])) if leg.get("qty") else 0
                side = OrderSide.BUY if _status_text(leg.get("side")).lower() == OrderSide.BUY.value else OrderSide.SELL
                if qty <= 0:
                    qty, side = self._position_exit(symbol)
                order = self._submit_stop(symbol, qty, side, float(leg["stop_price"]))
                restored.append(str(order.get("id", "")))
            except Exception as exc:  # noqa: BLE001 - logged loudly; position_manager re-arms next night
                log.error("alpaca_stop_restore_failed", symbol=symbol, leg=str(leg.get("id")), error=str(exc))
        log.warning("alpaca_close_failed_stops_restored", symbol=symbol, restored=restored, legs=len(legs))
        return restored

    def _await_settled(self, order_ids: list[str]) -> list[str]:
        """Poll until the cancels are final; returns the ids that never settled."""
        pending = list(order_ids)
        for _ in range(CANCEL_SETTLE_POLLS):
            if not pending:
                return []
            still: list[str] = []
            for oid in pending:
                status = _status_text(_to_dict(self.client.get_order_by_id(oid)).get("status")).lower()
                if status not in SETTLED_STATUSES:
                    still.append(oid)
            pending = still
            if pending:
                self.sleep(CANCEL_SETTLE_INTERVAL_S)
        if pending:
            log.warning("alpaca_cancels_not_settled", order_ids=pending)
        return pending

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
