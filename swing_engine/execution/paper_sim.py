"""In-memory paper broker used by tests, backtests and dry runs of the OrderManager.

Entry orders queue on :meth:`submit` and fill at the next open you pass to :meth:`fill_open`; exits trigger from
:meth:`mark` bars at the stop (stop-market, slippage applied; a gap through the stop fills at the open) or at the
target (limit, no slippage). When both are touched in one bar the stop wins (conservative). Slippage is adverse by
construction: buys pay more, sells receive less. Shorts are supported with simple cash accounting (proceeds are
credited on entry), which is adequate for tests but not a margin model.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import structlog

from swing_engine.core.interfaces import Broker
from swing_engine.core.models import Bar, OrderIntent, Position, Side
from swing_engine.core.registry import register
from swing_engine.execution.ledger import TERMINAL_STATUSES, OrderStatus

log = structlog.get_logger(__name__)

DEFAULT_STARTING_CASH = 100_000.0
DEFAULT_SLIPPAGE_BPS = 5.0
DEFAULT_COMMISSION_PER_SHARE = 0.0
BPS = 10_000.0
PRICE_DECIMALS = 4
ORDER_ID_PREFIX = "sim"
EXIT_STOP = "stop"
EXIT_TARGET = "target"
EXIT_MANUAL = "manual"


def _ohlc(bar: Bar | Mapping[str, float] | float) -> tuple[float, float, float, float]:
    if isinstance(bar, Bar):
        return bar.open, bar.high, bar.low, bar.close
    if isinstance(bar, Mapping):
        close = float(bar["close"])
        return float(bar.get("open", close)), float(bar.get("high", close)), float(bar.get("low", close)), close
    px = float(bar)
    return px, px, px, px


@register("broker", "paper_sim")
class PaperSimBroker(Broker):
    name = "paper_sim"

    def __init__(
        self,
        starting_cash: float = DEFAULT_STARTING_CASH,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
        commission_per_share: float = DEFAULT_COMMISSION_PER_SHARE,
    ) -> None:
        self.cash = float(starting_cash)
        self.starting_cash = float(starting_cash)
        self.slippage_bps = float(slippage_bps)
        self.commission_per_share = float(commission_per_share)
        self._orders: dict[str, dict[str, Any]] = {}
        self._by_client: dict[str, str] = {}
        self._positions: dict[str, Position] = {}
        self._last_prices: dict[str, float] = {}
        self._last_equity = self.cash
        self._seq = 0
        self.fills: list[dict[str, Any]] = []
        self.closed_trades: list[dict[str, Any]] = []

    # ------------------------------------------------------------ Broker API
    def account(self) -> dict[str, Any]:
        equity = self.equity()
        return {
            "equity": equity,
            "last_equity": self._last_equity,
            "cash": self.cash,
            "buying_power": max(self.cash, 0.0),
            "portfolio_value": equity,
            "paper": True,
            "broker": self.name,
        }

    def equity(self) -> float:
        value = 0.0
        for p in self._positions.values():
            px = self._last_prices.get(p.symbol, p.avg_entry)
            value += p.qty * px if p.side == Side.LONG else -p.qty * px
        return self.cash + value

    def positions(self) -> list[Position]:
        return list(self._positions.values())

    def submit(self, intent: OrderIntent) -> dict[str, Any]:
        """Queue an entry order; idempotent on ``client_order_id``."""
        existing_id = self._by_client.get(intent.client_order_id)
        if existing_id is not None:
            return self._result(self._orders[existing_id], duplicate=True)
        self._seq += 1
        oid = f"{ORDER_ID_PREFIX}-{self._seq}"
        order: dict[str, Any] = {
            "id": oid,
            "client_order_id": intent.client_order_id,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "qty": intent.qty,
            "entry_limit": intent.entry_limit,
            "stop": intent.stop,
            "target": intent.target,
            "strategy": intent.strategy,
            "order_class": "bracket" if intent.target is not None else "oto",
            "status": OrderStatus.ACCEPTED.value,
            "filled_qty": 0,
            "filled_avg_price": None,
            "submitted_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "filled_at": None,
            "reason": "",
        }
        self._orders[oid] = order
        self._by_client[intent.client_order_id] = oid
        log.info("paper_sim_order_accepted", order_id=oid, symbol=intent.symbol, qty=intent.qty)
        return self._result(order)

    def open_orders(self) -> list[dict[str, Any]]:
        return [dict(o) for o in self._orders.values() if o["status"] not in TERMINAL_STATUSES]

    def cancel(self, order_id: str) -> None:
        order = self._orders.get(order_id) or self._orders.get(self._by_client.get(order_id, ""))
        if order is None:
            raise KeyError(f"paper_sim: no order {order_id!r}")
        if order["status"] in TERMINAL_STATUSES:
            return
        order["status"] = OrderStatus.CANCELED.value
        order["reason"] = "canceled by client"

    def get_order(self, client_order_id: str) -> dict[str, Any] | None:
        oid = self._by_client.get(client_order_id)
        return dict(self._orders[oid]) if oid is not None else None

    # ------------------------------------------------------------ simulation
    def new_day(self) -> None:
        """Snapshot equity as ``last_equity`` (the daily-loss baseline used by LimitState)."""
        self._last_equity = self.equity()

    def fill_open(self, prices: Mapping[str, float], ts: datetime | None = None) -> list[dict[str, Any]]:
        """Fill every pending entry whose symbol has a price. Non-marketable limits expire (day-order semantics)."""
        fills: list[dict[str, Any]] = []
        stamp = ts or datetime.now(UTC)
        for order in self._orders.values():
            if order["status"] != OrderStatus.ACCEPTED.value:
                continue
            open_px = prices.get(order["symbol"])
            if open_px is None:
                continue
            side = Side(order["side"])
            px = self._slip(float(open_px), buy=side == Side.LONG)
            limit = order["entry_limit"]
            if limit is not None and ((side == Side.LONG and px > limit) or (side == Side.SHORT and px < limit)):
                order["status"] = OrderStatus.EXPIRED.value
                order["reason"] = f"limit {limit} not marketable at open {open_px}"
                continue
            qty = int(order["qty"])
            commission = qty * self.commission_per_share
            if side == Side.LONG:
                cost = qty * px + commission
                if cost > self.cash:
                    order["status"] = OrderStatus.REJECTED.value
                    order["reason"] = f"insufficient cash: need {cost:.2f}, have {self.cash:.2f}"
                    continue
                self.cash -= cost
            else:
                self.cash += qty * px - commission
            self._positions[order["symbol"]] = Position(
                symbol=order["symbol"], qty=qty, avg_entry=px, side=side, stop=order["stop"],
                target=order["target"], strategy=order["strategy"], opened_at=stamp,
            )
            self._last_prices[order["symbol"]] = float(open_px)
            order.update(status=OrderStatus.FILLED.value, filled_qty=qty, filled_avg_price=px,
                         filled_at=stamp.isoformat(timespec="seconds"))
            fill = {"order_id": order["id"], "client_order_id": order["client_order_id"], "symbol": order["symbol"],
                    "side": side.value, "qty": qty, "price": px, "commission": commission, "ts": stamp}
            self.fills.append(fill)
            fills.append(fill)
            log.info("paper_sim_fill", **{k: v for k, v in fill.items() if k != "ts"})
        return fills

    def mark(self, bars: Mapping[str, Bar | Mapping[str, float] | float], ts: datetime | None = None) -> list[dict]:
        """Update last prices from the bars and trigger stop/target exits."""
        exits: list[dict[str, Any]] = []
        for symbol, bar in bars.items():
            o, h, lo, c = _ohlc(bar)
            self._last_prices[symbol] = c
            pos = self._positions.get(symbol)
            if pos is None:
                continue
            if pos.side == Side.LONG:
                if pos.stop is not None and lo <= pos.stop:
                    exit_ = self.close_position(symbol, min(o, pos.stop), ts, reason=EXIT_STOP)
                elif pos.target is not None and h >= pos.target:
                    exit_ = self.close_position(symbol, pos.target, ts, reason=EXIT_TARGET, slip=False)
                else:
                    continue
            else:
                if pos.stop is not None and h >= pos.stop:
                    exit_ = self.close_position(symbol, max(o, pos.stop), ts, reason=EXIT_STOP)
                elif pos.target is not None and lo <= pos.target:
                    exit_ = self.close_position(symbol, pos.target, ts, reason=EXIT_TARGET, slip=False)
                else:
                    continue
            if exit_ is not None:
                exits.append(exit_)
        return exits

    def close_position(
        self, symbol: str, price: float, ts: datetime | None = None, reason: str = EXIT_MANUAL, slip: bool = True
    ) -> dict[str, Any] | None:
        pos = self._positions.pop(symbol, None)
        if pos is None:
            return None
        stamp = ts or datetime.now(UTC)
        px = self._slip(float(price), buy=pos.side == Side.SHORT) if slip else round(float(price), PRICE_DECIMALS)
        commission = pos.qty * self.commission_per_share
        if pos.side == Side.LONG:
            self.cash += pos.qty * px - commission
            pnl = (px - pos.avg_entry) * pos.qty
        else:
            self.cash -= pos.qty * px + commission
            pnl = (pos.avg_entry - px) * pos.qty
        pnl -= 2 * commission
        self._last_prices[symbol] = float(price)
        trade = {"symbol": symbol, "side": pos.side.value, "qty": pos.qty, "entry": pos.avg_entry, "exit": px,
                 "pnl": round(pnl, PRICE_DECIMALS), "reason": reason, "strategy": pos.strategy,
                 "opened_at": pos.opened_at, "closed_at": stamp}
        self.closed_trades.append(trade)
        log.info("paper_sim_exit", symbol=symbol, reason=reason, pnl=trade["pnl"])
        return trade

    # ------------------------------------------------------------ helpers
    def _slip(self, price: float, buy: bool) -> float:
        factor = 1 + self.slippage_bps / BPS if buy else 1 - self.slippage_bps / BPS
        return round(price * factor, PRICE_DECIMALS)

    @staticmethod
    def _result(order: dict[str, Any], duplicate: bool = False) -> dict[str, Any]:
        return {
            "broker_order_id": order["id"],
            "client_order_id": order["client_order_id"],
            "status": order["status"],
            "duplicate": duplicate,
            "raw": dict(order),
        }
