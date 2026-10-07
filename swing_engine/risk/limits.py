"""Portfolio-level limits checked before any order leaves the process.

``LimitState.check(intent, account)`` is the single gate. ``account`` is a plain dict so that every broker
(``alpaca``, ``paper_sim``) and the backtester can feed it::

    equity        float, required  current account equity
    last_equity   float, optional  equity at the previous close (Alpaca semantics); seeds the daily-loss baseline
    positions     list[Position]   open positions (optional)
    open_orders   list[dict]       pending orders with a "symbol" key; each distinct symbol reserves a slot
    buying_power  float, optional  hard notional cap for the order
    prices        dict[str,float]  reference prices for notional checks when the intent has no entry_limit
    as_of         date, optional   day for the daily-loss baseline (defaults to today)

State that must persist across calls (day-start equity, peak equity) lives on the instance; everything else is
re-read from ``account`` every time so the check never trusts stale positions.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

import structlog

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Position

log = structlog.get_logger(__name__)

PCT = 100.0
OK = "ok"


def position_notional(position: Position) -> float:
    return abs(position.qty * position.avg_entry)


def sector_exposure_dollars(positions: Iterable[Position], sector: str, sector_map: Mapping[str, str]) -> float:
    """Gross notional (at entry) of open positions in ``sector``."""
    return float(sum(position_notional(p) for p in positions if sector_map.get(p.symbol) == sector))


def intent_notional(intent: OrderIntent, reference_price: float | None = None) -> float | None:
    """Dollar size of an intent at its limit price, or at ``reference_price`` for market orders."""
    price = intent.entry_limit if intent.entry_limit is not None else reference_price
    return None if price is None else intent.qty * price


class LimitState:
    """Max open positions, daily loss, drawdown and sector caps from ``RiskConfig``."""

    def __init__(
        self,
        risk_cfg: RiskConfig,
        sector_map: Mapping[str, str] | None = None,
        day_start_equity: float | None = None,
        peak_equity: float | None = None,
        as_of: date | None = None,
    ) -> None:
        self.cfg = risk_cfg
        self.sector_map: dict[str, str] = dict(sector_map or {})
        self.day_start_equity = day_start_equity
        self.peak_equity = peak_equity
        self.day = as_of
        self.last_equity: float | None = None
        self.checks = 0
        self.blocks = 0

    # ----------------------------------------------------------------- state
    def update_equity(self, equity: float, as_of: date | None = None, last_equity: float | None = None) -> None:
        """Record equity; starts a new daily baseline on a new day, tracks the running peak."""
        today = as_of or date.today()
        if self.day != today or self.day_start_equity is None:
            self.day = today
            self.day_start_equity = last_equity if last_equity is not None else equity
        self.peak_equity = equity if self.peak_equity is None else max(self.peak_equity, equity)
        self.last_equity = equity

    def daily_pnl_pct(self) -> float | None:
        if self.last_equity is None or not self.day_start_equity:
            return None
        return (self.last_equity - self.day_start_equity) / self.day_start_equity * PCT

    def drawdown_pct(self) -> float | None:
        if self.last_equity is None or not self.peak_equity:
            return None
        return (self.last_equity - self.peak_equity) / self.peak_equity * PCT

    def snapshot(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat() if self.day else None,
            "day_start_equity": self.day_start_equity,
            "peak_equity": self.peak_equity,
            "last_equity": self.last_equity,
            "daily_pnl_pct": self.daily_pnl_pct(),
            "drawdown_pct": self.drawdown_pct(),
            "checks": self.checks,
            "blocks": self.blocks,
        }

    # ----------------------------------------------------------------- gate
    def check(self, intent: OrderIntent, account: Mapping[str, Any]) -> tuple[bool, str]:
        """Return ``(True, "ok")`` or ``(False, reason)``. Never raises on bad account data: that blocks."""
        self.checks += 1
        reason = self._first_violation(intent, account)
        if reason is None:
            log.info("limit_check_ok", symbol=intent.symbol, client_order_id=intent.client_order_id)
            return True, OK
        self.blocks += 1
        log.warning("limit_check_blocked", symbol=intent.symbol, client_order_id=intent.client_order_id, reason=reason)
        return False, reason

    def _first_violation(self, intent: OrderIntent, account: Mapping[str, Any]) -> str | None:
        cfg = self.cfg
        if intent.qty <= 0:
            return f"qty must be positive, got {intent.qty}"
        try:
            equity = float(account["equity"])
        except (KeyError, TypeError, ValueError):
            return "account equity unavailable"
        if equity <= 0:
            return f"account equity not positive: {equity}"
        last_equity = account.get("last_equity")
        self.update_equity(equity, account.get("as_of"), float(last_equity) if last_equity is not None else None)

        daily = self.daily_pnl_pct()
        if daily is not None and daily <= -cfg.max_daily_loss_pct:
            return f"daily loss {daily:.2f}% breaches -{cfg.max_daily_loss_pct}%"
        dd = self.drawdown_pct()
        if dd is not None and dd <= -cfg.max_drawdown_pct:
            return f"drawdown {dd:.2f}% breaches -{cfg.max_drawdown_pct}%"

        positions: list[Position] = list(account.get("positions") or [])
        open_symbols = {p.symbol for p in positions}
        if intent.symbol in open_symbols:
            return f"{intent.symbol} already has an open position"
        pending_symbols = {str(o.get("symbol")) for o in (account.get("open_orders") or [])} - open_symbols
        if intent.symbol in pending_symbols:
            return f"{intent.symbol} already has a pending order"
        slots_used = len(open_symbols) + len(pending_symbols)
        if slots_used >= cfg.max_open_positions:
            return f"max open positions reached ({slots_used}/{cfg.max_open_positions})"

        prices: Mapping[str, float] = account.get("prices") or {}
        notional = intent_notional(intent, prices.get(intent.symbol))
        if notional is None:
            log.debug("limit_check_no_price", symbol=intent.symbol)
            return None
        position_pct = notional / equity * PCT
        if position_pct > cfg.max_position_pct:
            return f"position {position_pct:.2f}% of equity exceeds max {cfg.max_position_pct}%"
        sector = self.sector_map.get(intent.symbol)
        if sector is not None:
            exposure = sector_exposure_dollars(positions, sector, self.sector_map) + notional
            sector_pct = exposure / equity * PCT
            if sector_pct > cfg.max_sector_pct:
                return f"sector {sector} exposure {sector_pct:.2f}% exceeds max {cfg.max_sector_pct}%"
        buying_power = account.get("buying_power")
        if buying_power is not None and notional > float(buying_power):
            return f"notional {notional:.2f} exceeds buying power {float(buying_power):.2f}"
        return None
