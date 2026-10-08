"""Position sizing: deterministic fixed-fractional risk with portfolio caps.

Every number here comes from the ``Signal`` (strategy code) and ``RiskConfig``; nothing is read from a model
or an LLM. The Schwab example in ``docs/sources-schwab-massive.md``: $50,000 x 1% = $500 risk; $2 risk per
share -> 250 shares at the reference entry. The engine sizes on the worst-case fill at its marketable limit
(entry + 1%), so the same trade is 238 shares ($500 / $2.10) and a fill anywhere up to the limit risks <= $500.

Caps applied, in order (the smallest wins): fixed-fractional risk, ``max_position_pct`` of equity, optional
volatility target (``vol_target_annual_pct`` against ``signal.features["vol_21d"]``, annualized decimal), and
the remaining room under ``max_sector_pct`` when a ``sector_map`` is supplied, and an optional Turtle unit
(``turtle_unit_risk_pct`` against ``signal.features["turtle_n"]``).

:func:`sizing_equity` is the equity callers should size on when the drawdown or book-vol rules are on: it shrinks
account equity by ``drawdown_size_mult`` x drawdown (Turtle) and by the book vol-target scale (Barroso-Santa-Clara),
so every cap above scales with it. Both are off (identity) by default.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd
import structlog

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Position, Side, Signal
from swing_engine.features.indicators import atr
from swing_engine.risk.limits import PCT, sector_exposure_dollars

log = structlog.get_logger(__name__)

ENTRY_LIMIT_BUFFER_PCT = 1.0
"""Marketable limit: this far through the reference entry (worse for us) so normal opens fill, bad gaps do not."""
PRICE_DECIMALS = 2
CLIENT_ORDER_ID_MAX_LEN = 48
CLIENT_ORDER_ID_PREFIX = "swing"
CLIENT_ORDER_ID_HASH_LEN = 8
VOL_FEATURE = "vol_21d"
TURTLE_N_FEATURE = "turtle_n"
TURTLE_N_PERIOD = 20
"""Turtle N = (19 x prior N + TR) / 20: Wilder smoothing of true range over 20 sessions."""
TRADING_DAYS = 252
_UNSAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def effective_equity(account_equity: float, risk_cfg: RiskConfig) -> float:
    """Equity used for sizing: ``risk_cfg.account_equity_override`` when set, else the account's."""
    if risk_cfg.account_equity_override is not None and risk_cfg.account_equity_override > 0:
        return float(risk_cfg.account_equity_override)
    return float(account_equity)


def turtle_n(high: pd.Series, low: pd.Series, close: pd.Series, period: int = TURTLE_N_PERIOD) -> pd.Series:
    """Turtle N (Faith): Wilder-smoothed true range, ``N = ((period - 1) x prior N + TR) / period``."""
    return atr(high, low, close, period)


def turtle_unit_shares(equity: float, n: float, unit_risk_pct: float, point_value: float = 1.0) -> int:
    """Shares in one Turtle unit: ``equity x unit_risk_pct% / (N x point value)``; 0 when N is not positive."""
    if not (n > 0 and point_value > 0 and equity > 0):
        return 0
    return math.floor(equity * unit_risk_pct / PCT / (n * point_value))


def drawdown_scaled_equity(equity: float, peak_equity: float | None, mult: float | None) -> float:
    """Equity reduced by ``mult`` x the drawdown from ``peak_equity`` (Turtle mult 2: -10% trades as -20%)."""
    if not mult or not peak_equity or peak_equity <= 0:
        return float(equity)
    dd = max(0.0, 1.0 - equity / peak_equity)
    return float(equity) * max(0.0, 1.0 - mult * dd)


def book_vol_scale(book_returns: pd.Series | np.ndarray | None, risk_cfg: RiskConfig) -> float:
    """Gross-exposure multiplier ``target / trailing realized annual vol``, capped at ``book_vol_max_scale``.

    ``book_returns`` are daily book (equity) returns, oldest first; only the last ``book_vol_lookback_days`` are
    used. Returns 1.0 when the rule is off or there are fewer than ``lookback`` returns / zero vol.
    """
    target = risk_cfg.book_vol_target_annual_pct
    if target is None or book_returns is None:
        return 1.0
    lookback = risk_cfg.book_vol_lookback_days
    rets = np.asarray(book_returns, dtype=float)[-lookback:]
    rets = rets[np.isfinite(rets)]
    if len(rets) < lookback:
        return 1.0
    vol = float(np.std(rets, ddof=1)) * math.sqrt(TRADING_DAYS)
    if vol <= 0:
        return 1.0
    return min(risk_cfg.book_vol_max_scale, target / PCT / vol)


def sizing_equity(
    equity: float,
    risk_cfg: RiskConfig,
    peak_equity: float | None = None,
    book_returns: pd.Series | np.ndarray | None = None,
) -> float:
    """Equity to size on: drawdown-scaled (``drawdown_size_mult``) times the book vol scale. Identity when off."""
    scaled = drawdown_scaled_equity(equity, peak_equity, risk_cfg.drawdown_size_mult)
    return scaled * book_vol_scale(book_returns, risk_cfg)


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


#: float slack on the reward/risk floor (strategies._base.RR_TOLERANCE)
RR_TOLERANCE = 1e-9


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
    if rr is None and rr_floor > 0:
        return None, "reward_risk unknown (signal has neither reward_risk nor target)"
    if rr is not None and rr < rr_floor - RR_TOLERANCE:
        return None, f"reward_risk {rr:.2f} below min {rr_floor}"
    if any(p.symbol == signal.symbol for p in positions):
        return None, f"{signal.symbol} already has an open position"
    if len(positions) >= risk_cfg.max_open_positions:
        return None, f"max open positions reached ({len(positions)}/{risk_cfg.max_open_positions})"

    limit = entry_limit_for(signal)
    # Size on the worst-case fill: the marketable limit sits ENTRY_LIMIT_BUFFER_PCT through the reference entry,
    # so a fill at the limit must still lose no more than the risk budget at the stop.
    rps_worst = abs(limit - signal.stop)
    risk_budget = equity * risk_cfg.risk_per_trade_pct / PCT
    qty_ff = math.floor(risk_budget / rps_worst)
    qty_cap = math.floor(equity * risk_cfg.max_position_pct / PCT / limit)
    caps: dict[str, int] = {"ff": qty_ff, "cap": qty_cap}

    if risk_cfg.vol_target_annual_pct is not None:
        vol = signal.features.get(VOL_FEATURE)
        if vol is not None and vol > 0:
            per_position_budget = equity * (risk_cfg.vol_target_annual_pct / PCT) / risk_cfg.max_open_positions
            caps["vol"] = math.floor(per_position_budget / vol / limit)
        else:
            log.debug("vol_target_skipped", symbol=signal.symbol, reason=f"{VOL_FEATURE} missing")

    if risk_cfg.turtle_unit_risk_pct is not None:
        n = signal.features.get(TURTLE_N_FEATURE)
        if n is not None and n > 0:
            caps["unit"] = turtle_unit_shares(equity, float(n), risk_cfg.turtle_unit_risk_pct)
        else:
            log.debug("turtle_unit_skipped", symbol=signal.symbol, reason=f"{TURTLE_N_FEATURE} missing")

    if sector_map:
        sector = sector_map.get(signal.symbol)
        if sector is not None:
            room = equity * risk_cfg.max_sector_pct / PCT - sector_exposure_dollars(positions, sector, sector_map)
            caps["sector"] = max(math.floor(room / limit), 0)

    qty = min(caps.values())
    if qty < 1:
        binding = min(caps, key=caps.get)  # type: ignore[arg-type]
        return None, f"size rounds to zero (binding cap: {binding})"

    notes = " ".join(f"{k}={v}" for k, v in caps.items()) + (f" rr={rr:.2f}" if rr is not None else " rr=rule-exit") + f" rps={rps:.4f} rps_at_limit={rps_worst:.4f}"
    intent = OrderIntent(
        symbol=signal.symbol,
        side=signal.side,
        qty=qty,
        entry_limit=limit,
        stop=round(signal.stop, PRICE_DECIMALS),
        target=round(signal.target, PRICE_DECIMALS) if signal.target is not None else None,
        strategy=signal.strategy,
        client_order_id=make_client_order_id(signal),
        risk_dollars=round(qty * rps_worst, PRICE_DECIMALS),
        entry_type=signal.entry_type,
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
