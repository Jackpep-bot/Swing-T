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
    units         dict[str,float]  optional Turtle units held per symbol (default: 1 per position / pending order)

State that must persist across calls (day-start equity, peak equity, month-start equity and the monthly-stop latch) lives on the instance and, when a
``state_path`` is given, in a small JSON file under ``state/`` so a fresh process (``swing paper`` runs once a
day) starts from the historical peak instead of re-seeding it with today's equity. Everything else is re-read
from ``account`` every time so the check never trusts stale positions.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Position
from swing_engine.risk.killswitch import resolve_state_path

log = structlog.get_logger(__name__)

PCT = 100.0
OK = "ok"
DEFAULT_LIMITS_STATE_FILE: str = RiskConfig.model_fields["limits_state_file"].default
STATE_VERSION = 1
ORDER_SIDE_DIRECTION = {"buy": "long", "sell": "short", "long": "long", "short": "short"}


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


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
    """Max open positions, daily / monthly loss, drawdown, sector and Turtle unit caps from ``RiskConfig``."""

    def __init__(
        self,
        risk_cfg: RiskConfig,
        sector_map: Mapping[str, str] | None = None,
        day_start_equity: float | None = None,
        peak_equity: float | None = None,
        as_of: date | None = None,
        state_path: str | Path | None = None,
    ) -> None:
        self.cfg = risk_cfg
        self.sector_map: dict[str, str] = dict(sector_map or {})
        self.day_start_equity = day_start_equity
        self.peak_equity = peak_equity
        self.day = as_of
        self.last_equity: float | None = None
        self.month: str | None = None  # "YYYY-MM" of month_start_equity
        self.month_start_equity: float | None = None
        self.month_stopped = False  # latched once the monthly loss stop fires; clears on a new month
        self.checks = 0
        self.blocks = 0
        self.state_path: Path | None = resolve_state_path(state_path) if state_path else None
        if self.state_path is not None:
            self._load_state()
        if risk_cfg.max_sector_pct and not self.sector_map:
            log.warning(
                "sector_limit_inactive",
                max_sector_pct=risk_cfg.max_sector_pct,
                reason="no sector_map supplied; the sector cap cannot fire",
            )

    # ----------------------------------------------------------------- persistence
    def _load_state(self) -> None:
        """Seed peak / day-start equity from the state file; explicit constructor values win."""
        assert self.state_path is not None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            log.warning("limits_state_unreadable", path=str(self.state_path), error=str(exc))
            return
        if not isinstance(data, dict):
            return
        if self.peak_equity is None:
            self.peak_equity = _float_or_none(data.get("peak_equity"))
        if self.day is None and data.get("day"):
            try:
                self.day = date.fromisoformat(str(data["day"]))
            except ValueError:
                self.day = None
            if self.day is not None and self.day_start_equity is None:
                self.day_start_equity = _float_or_none(data.get("day_start_equity"))
        self.month = data.get("month")
        self.month_start_equity = _float_or_none(data.get("month_start_equity"))
        self.month_stopped = bool(data.get("month_stopped", False))
        log.info("limits_state_loaded", path=str(self.state_path), peak_equity=self.peak_equity, day=str(self.day))

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        payload = {
            "version": STATE_VERSION,
            "day": self.day.isoformat() if self.day else None,
            "day_start_equity": self.day_start_equity,
            "peak_equity": self.peak_equity,
            "last_equity": self.last_equity,
            "month": self.month,
            "month_start_equity": self.month_start_equity,
            "month_stopped": self.month_stopped,
            "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.state_path)
        except OSError as exc:  # never let bookkeeping block or unblock an order
            log.error("limits_state_write_failed", path=str(self.state_path), error=str(exc))

    # ----------------------------------------------------------------- state
    def update_equity(self, equity: float, as_of: date | None = None, last_equity: float | None = None) -> None:
        """Record equity; starts a new daily baseline on a new day, tracks the running peak (persisted)."""
        today = as_of or date.today()
        if self.day != today or self.day_start_equity is None:
            self.day = today
            self.day_start_equity = last_equity if last_equity is not None else equity
        month = f"{today:%Y-%m}"
        if self.month != month or self.month_start_equity is None:
            self.month, self.month_stopped = month, False
            self.month_start_equity = last_equity if last_equity is not None else equity
        self.peak_equity = equity if self.peak_equity is None else max(self.peak_equity, equity)
        self.last_equity = equity
        self._save_state()

    def daily_pnl_pct(self) -> float | None:
        if self.last_equity is None or not self.day_start_equity:
            return None
        return (self.last_equity - self.day_start_equity) / self.day_start_equity * PCT

    def monthly_pnl_pct(self) -> float | None:
        if self.last_equity is None or not self.month_start_equity:
            return None
        return (self.last_equity - self.month_start_equity) / self.month_start_equity * PCT

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
            "month": self.month,
            "monthly_pnl_pct": self.monthly_pnl_pct(),
            "month_stopped": self.month_stopped,
            "checks": self.checks,
            "blocks": self.blocks,
            "state_path": str(self.state_path) if self.state_path else None,
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

    def _unit_violation(
        self, intent: OrderIntent, positions: list[Position], account: Mapping[str, Any]
    ) -> str | None:
        """Turtle unit limits per symbol / sector / direction; the new intent counts as one unit.

        Held units: ``account["units"][symbol]`` when given, else 1 per open position and per pending entry order
        (a pending order's broker side buy/sell maps to long/short).
        """
        cfg = self.cfg
        if cfg.max_units_per_symbol is None and cfg.max_units_per_sector is None and cfg.max_units_per_direction is None:
            return None
        units: Mapping[str, float] = account.get("units") or {}
        held: list[tuple[str, str | None, float]] = [
            (p.symbol, str(p.side), float(units.get(p.symbol, 1.0))) for p in positions
        ]
        held_symbols = {p.symbol for p in positions}
        for o in account.get("open_orders") or []:
            sym = str(o.get("symbol"))
            if sym not in held_symbols:
                held.append((sym, ORDER_SIDE_DIRECTION.get(str(o.get("side")).lower()), float(units.get(sym, 1.0))))
        side = str(intent.side)
        sector = self.sector_map.get(intent.symbol)
        by_symbol = sum(u for s, _, u in held if s == intent.symbol) + 1
        by_sector = sum(u for s, _, u in held if sector is not None and self.sector_map.get(s) == sector) + 1
        by_direction = sum(u for _, d, u in held if d == side) + 1
        for label, count, cap in (
            (f"symbol {intent.symbol}", by_symbol, cfg.max_units_per_symbol),
            (f"sector {sector}", by_sector, cfg.max_units_per_sector),
            (f"direction {side}", by_direction, cfg.max_units_per_direction),
        ):
            if cap is not None and count > cap:
                return f"{label} would hold {count:g} units, max {cap}"
        return None

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
        monthly = self.monthly_pnl_pct()
        if cfg.max_monthly_loss_pct is not None and monthly is not None and monthly <= -cfg.max_monthly_loss_pct:
            if not self.month_stopped:
                self.month_stopped = True
                self._save_state()
        if cfg.max_monthly_loss_pct is not None and self.month_stopped:
            return f"monthly loss stop hit in {self.month} (-{cfg.max_monthly_loss_pct}%): no new entries this month"
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
        unit_reason = self._unit_violation(intent, positions, account)
        if unit_reason is not None:
            return unit_reason

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
