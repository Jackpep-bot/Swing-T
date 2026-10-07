"""Position sizing: deterministic fixed-fractional risk with portfolio caps.

Every number here comes from the ``Signal`` (strategy code) and ``RiskConfig``; nothing is read from a model
or an LLM. The Schwab example in ``docs/sources-schwab-massive.md``: $50,000 x 1% = $500 risk; $2 risk per
share -> 250 shares.

Caps applied, in order (the smallest wins): fixed-fractional risk, ``max_position_pct`` of equity, optional
volatility target (``vol_target_annual_pct`` against ``signal.features["vol_21d"]``, annualized decimal), and
the remaining room under ``max_sector_pct`` when a ``sector_map`` is supplied.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping

import structlog

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Position, Side, Signal
from swing_engine.risk.limits import PCT, sector_exposure_dollars

log = structlog.get_logger(__name__)

ENTRY_LIMIT_BUFFER_PCT = 1.0
"""Marketable limit: this far through the reference entry (worse for us) so normal opens fill, bad gaps do not."""
PRICE_DECIMALS = 2
CLIENT_ORDER_ID_MAX_LEN = 48
CLIENT_ORDER_ID_PREFIX = "swing"
CLIENT_ORDER_ID_HASH_LEN = 8
VOL_FEATURE = "vol_21d"
_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def effective_equity(account_equity: float, risk_cfg: RiskConfig) -> float:
    """Equity used for sizing: ``risk_cfg.account_equity_override`` when set, else the account's."""
    if risk_cfg.account_equity_override is not None and risk_cfg.account_equity_override > 0:
        return float(risk_cfg.account_equity_override)
    return float(account_equity)


def make_client_order_id(signal: Signal) -> str:
    """Stable id per (strategy, symbol, as_of, side) so re-running a day's scan cannot double-submit."""
    raw = f"{CLIENT_ORDER_ID_PREFIX}-{signal.strategy}-{signal.symbol}-{signal.as_of:%Y%m%d}-{signal.side.value}"
    cleaned = _UNSAFE_ID_CHARS.sub("_", raw)
    if len(cleaned) <= CLIENT_ORDER_ID_MAX_LEN:
        return cleaned
    digest = hashlib.sha1(cleaned.encode()).hexdigest()[:CLIENT_ORDER_ID_HASH_LEN]
    return f"{cleaned[: CLIENT_ORDER_ID_MAX_LEN - CLIENT_ORDER_ID_HASH_LEN - 1]}-{digest}"


def entry_limit_for(signal: Signal) -> float:
    """Reference entry pushed ``ENTRY_LIMIT_BUFFER_PCT`` against us (up for longs, down for shorts)."""
    factor = 1 + ENTRY_LIMIT_BUFFER_PCT / PCT if signal.side == Side.LONG else 1 - ENTRY_LIMIT_BUFFER_PCT / PCT
    return round(signal.entry * factor, PRICE_DECIMALS)


def reward_risk_for(signal: Signal) -> float | None:
    """Signal's own reward_risk, else derived from target/stop, else None (cannot be verified)."""
    if signal.reward_risk is not None:
        return float(signal.reward_risk)
    rps = signal.risk_per_share()
    if signal.target is None or rps <= 0:
        return None
    return abs(signal.target - signal.entry) / rps


def _geometry_error(signal: Signal) -> str | None:
    if signal.entry <= 0 or signal.stop <= 0:
        return "entry and stop must be positive"
    if signal.side == Side.LONG:
        if signal.stop >= signal.entry:
            return "long stop must be below entry"
        if signal.target is not None and signal.target <= signal.entry:
            return "long target must be above entry"
    else:
        if signal.stop <= signal.entry:
            return "short stop must be above entry"
        if signal.target is not None and signal.target >= signal.entry:
            return "short target must be below entry"
    return None


def size_signal_detail(
    signal: Signal,
    equity: float,
    risk_cfg: RiskConfig,
    open_positions: Iterable[Position] | None = None,
    sector_map: Mapping[str, str] | None = None,
    min_reward_risk: float | None = None,
) -> tuple[OrderIntent | None, str]:
    """Like :func:`size_signal` but also returns the reason (useful for the CLI and the journal).

    ``min_reward_risk`` overrides ``risk_cfg.min_reward_risk`` for this signal; strategies that exit on a rule
    rather than a fixed target (e.g. RSI-2 mean reversion) declare a lower floor in ``settings.strategies``.
    """
    positions = list(open_positions or [])
    rr_floor = risk_cfg.min_reward_risk if min_reward_risk is None else float(min_reward_risk)
    if equity <= 0:
        return None, f"equity not positive: {equity}"
    err = _geometry_error(signal)
    if err:
        return None, err
    rps = signal.risk_per_share()
    if rps <= 0:
        return None, "risk per share is zero"
    rr = reward_risk_for(signal)
    if rr is None:
        return None, "reward_risk unknown (signal has neither reward_risk nor target)"
    if rr < rr_floor:
        return None, f"reward_risk {rr:.2f} below min {rr_floor}"
    if any(p.symbol == signal.symbol for p in positions):
        return None, f"{signal.symbol} already has an open position"
    if len(positions) >= risk_cfg.max_open_positions:
        return None, f"max open positions reached ({len(positions)}/{risk_cfg.max_open_positions})"

    limit = entry_limit_for(signal)
    risk_budget = equity * risk_cfg.risk_per_trade_pct / PCT
    qty_ff = math.floor(risk_budget / rps)
    qty_cap = math.floor(equity * risk_cfg.max_position_pct / PCT / limit)
    caps: dict[str, int] = {"ff": qty_ff, "cap": qty_cap}

    if risk_cfg.vol_target_annual_pct is not None:
        vol = signal.features.get(VOL_FEATURE)
        if vol is not None and vol > 0:
            per_position_budget = equity * (risk_cfg.vol_target_annual_pct / PCT) / risk_cfg.max_open_positions
            caps["vol"] = math.floor(per_position_budget / vol / limit)
        else:
            log.debug("vol_target_skipped", symbol=signal.symbol, reason=f"{VOL_FEATURE} missing")

    if sector_map:
        sector = sector_map.get(signal.symbol)
        if sector is not None:
            room = equity * risk_cfg.max_sector_pct / PCT - sector_exposure_dollars(positions, sector, sector_map)
            caps["sector"] = max(math.floor(room / limit), 0)

    qty = min(caps.values())
    if qty < 1:
        binding = min(caps, key=caps.get)  # type: ignore[arg-type]
        return None, f"size rounds to zero (binding cap: {binding})"

    notes = " ".join(f"{k}={v}" for k, v in caps.items()) + f" rr={rr:.2f} rps={rps:.4f}"
    intent = OrderIntent(
        symbol=signal.symbol,
        side=signal.side,
        qty=qty,
        entry_limit=limit,
        stop=round(signal.stop, PRICE_DECIMALS),
        target=round(signal.target, PRICE_DECIMALS) if signal.target is not None else None,
        strategy=signal.strategy,
        client_order_id=make_client_order_id(signal),
        risk_dollars=round(qty * rps, PRICE_DECIMALS),
        notes=notes,
    )
    return intent, "ok"


def strategy_min_reward_risk(strategies_cfg: Mapping[str, Mapping[str, object]] | None, strategy: str) -> float | None:
    """Per-strategy ``min_reward_risk`` from ``settings.strategies[<name>]``, or None to use the portfolio floor."""
    cfg = (strategies_cfg or {}).get(strategy) or {}
    value = cfg.get("min_reward_risk")
    return None if value is None else float(value)  # type: ignore[arg-type]


def size_signal(
    signal: Signal,
    equity: float,
    risk_cfg: RiskConfig,
    open_positions: Iterable[Position] | None = None,
    sector_map: Mapping[str, str] | None = None,
    min_reward_risk: float | None = None,
) -> OrderIntent | None:
    """Turn a Signal into an OrderIntent, or None (reason logged) when the signal fails a risk rule."""
    intent, reason = size_signal_detail(signal, equity, risk_cfg, open_positions, sector_map, min_reward_risk)
    if intent is None:
        log.info("signal_rejected", symbol=signal.symbol, strategy=signal.strategy, reason=reason)
    else:
        log.info("signal_sized", symbol=signal.symbol, qty=intent.qty, risk_dollars=intent.risk_dollars, notes=reason)
    return intent
