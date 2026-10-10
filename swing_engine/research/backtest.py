"""Event-style daily backtester for panel-driven swing strategies.

Timeline for each trading day ``t`` (one bar per symbol):

1. entries queued from signals emitted at the close of ``t-1`` fill at today's open (plus slippage);
2. every open position is checked against today's bar: gap-through stop at the open, gap-through target at
   the open (a resting limit fills before any intrabar move), intrabar stop, target (the stop wins when both
   touch in the same bar), time stop, strategy rule exit (``exit_rule`` or ``should_exit``) at the close;
3. trailing stops ratchet on the close (``BacktestConfig.trailing``, then the strategy's ``trail_stop`` hook;
   a strategy with ``engine_trail = False`` skips ``trailing``) and the book is marked to market;
4. the strategy sees the panel up to and including ``t`` (point-in-time slice) and emits signals for
   next-open entry.

One position per symbol. Sizing goes through a pluggable ``Sizer`` whose signature matches
``risk.sizing.size_signal``; the default is a local fixed-fractional sizer so this package has no dependency
on ``risk``. Nothing here reads a model or an LLM: every number comes from the panel, the ``Signal`` and the
configs.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd
import structlog
from pydantic import BaseModel, Field

from swing_engine.core.config import RiskConfig
from swing_engine.core.interfaces import exit_takes_position
from swing_engine.core.models import EntryType, OrderIntent, Position, PositionContext, Side, Signal

log = structlog.get_logger(__name__)

BPS = 10_000.0
PCT = 100.0
ONE_MILLION = 1_000_000.0
TRADING_DAYS_PER_YEAR = 252

#: docs/gates.md cost assumptions: 10 bps per side for large caps, 20 bps otherwise.
LARGE_CAP_SLIPPAGE_BPS = 10.0
SMALL_CAP_SLIPPAGE_BPS = 20.0
#: SEC Section 31 fee, FY2026: $20.60 per $1M sold. FINRA TAF: $0.000195 per share sold, capped at $9.79.
SEC_FEE_PER_MILLION_SOLD = 20.60
FINRA_TAF_PER_SHARE = 0.000195
FINRA_TAF_CAP = 9.79

DEFAULT_INITIAL_EQUITY = 100_000.0
DEFAULT_MAX_HOLD_BARS = 20
#: Strategy ``params`` key that overrides ``BacktestConfig.max_hold_bars`` when present.
STRATEGY_HOLD_PARAM = "max_hold_days"
CLIENT_ORDER_PREFIX = "bt"
#: Chandelier exit (docs/catalog/catalog.json chandelier_exit; LeBeau): highest high - 3 x ATR(22).
CHANDELIER_ATR_PERIOD = 22
CHANDELIER_ATR_MULT = 3.0
#: ``atr_<n>`` trailing columns missing from the panel are computed on the fly (Wilder ATR, per symbol).
ATR_COLUMN_RE = re.compile(r"^atr_(\d+)$")
#: Strategy hooks (strategies._base.PanelStrategy): indicator trail and the engine-overlay opt-out.
TRAIL_STOP_HOOK = "trail_stop"
ENGINE_TRAIL_ATTR = "engine_trail"
#: Microcap control (catalog microcap_control_vw_nyse; Hou-Xue-Zhang 2020): drop names below the NYSE 20th
#: size percentile. ``SIZE_EXCHANGE_COLUMN`` == ``NYSE_LABEL`` rows set the breakpoint when the panel has it.
MICROCAP_SIZE_PCTILE = 20.0
SIZE_EXCHANGE_COLUMN = "exchange"
NYSE_LABEL = "NYSE"

SYMBOL = "symbol"
TS = "ts"
PRICE_COLUMNS = ("open", "high", "low", "close")
MARKET_REGIME_COLUMNS = ("market_trend_state", "market_vol_regime")
#: Column names on a SPY-only ``market`` frame that map onto the regime keys strategies understand.
REGIME_ALIASES = {"trend_state": "market_trend_state", "vol_regime": "market_vol_regime"}

TRADE_COLUMNS = [
    "symbol", "strategy", "side", "entry_ts", "entry_price", "exit_ts", "exit_price", "qty", "initial_stop",
    "stop", "target", "exit_reason", "bars_held", "pnl", "pnl_pct", "r_multiple", "entry_notional",
    "slippage_cost", "fees", "costs", "mfe_r", "mae_r", "score",
]
EQUITY_COLUMNS = ["equity", "cash", "market_value", "exposure", "n_positions", "ret"]


class ExitReason(StrEnum):
    STOP = "stop"
    STOP_GAP = "stop_gap"  # open already through the stop: filled at the open, not at the stop
    TRAIL_STOP = "trail_stop"  # a ratcheted (trailing / breakeven) stop was hit
    TARGET = "target"
    TIME = "time"
    RULE = "rule"  # strategy exit rule fired at the close
    PROFITABLE_CLOSES = "profitable_closes"  # ``BacktestConfig.profitable_closes`` reached, exit at the close
    DELISTED = "delisted"  # no more bars for the symbol: closed at its last close
    END = "end"  # forced close at the end of the backtest window


# ----------------------------------------------------------------------------------------------- costs


class CostModel(BaseModel):
    """Per-side slippage in basis points plus US regulatory fees on every sale.

    Slippage is applied to the fill price (buys fill higher, sells lower). SEC Section 31 and FINRA TAF are
    charged on the sell leg only (long exits and short entries). ``commission_per_share`` applies to both legs.
    """

    slippage_bps: float = LARGE_CAP_SLIPPAGE_BPS
    commission_per_share: float = 0.0
    sec_fee_per_million_sold: float = SEC_FEE_PER_MILLION_SOLD
    finra_taf_per_share: float = FINRA_TAF_PER_SHARE
    finra_taf_cap: float = FINRA_TAF_CAP

    @classmethod
    def large_cap(cls) -> CostModel:
        return cls(slippage_bps=LARGE_CAP_SLIPPAGE_BPS)

    @classmethod
    def small_cap(cls) -> CostModel:
        return cls(slippage_bps=SMALL_CAP_SLIPPAGE_BPS)

    def fill_price(self, price: float, is_buy: bool) -> float:
        """Raw price moved ``slippage_bps`` against us."""
        adj = self.slippage_bps / BPS
        return price * (1.0 + adj) if is_buy else price * (1.0 - adj)

    def regulatory_fees(self, qty: int, sell_notional: float) -> float:
        """SEC fee on the dollar value sold plus the (capped) FINRA TAF on shares sold."""
        sec = sell_notional / ONE_MILLION * self.sec_fee_per_million_sold
        taf = min(qty * self.finra_taf_per_share, self.finra_taf_cap)
        return sec + taf

    def leg_fees(self, qty: int, notional: float, is_sell: bool) -> float:
        fees = qty * self.commission_per_share
        if is_sell:
            fees += self.regulatory_fees(qty, notional)
        return fees

    def round_trip_cost(self, entry_price: float, exit_price: float, qty: int, side: Side = Side.LONG) -> float:
        """Total dollar cost of a round trip versus raw prices: slippage on both legs plus all fees."""
        is_long = side == Side.LONG
        entry_fill = self.fill_price(entry_price, is_buy=is_long)
        exit_fill = self.fill_price(exit_price, is_buy=not is_long)
        slippage = (abs(entry_fill - entry_price) + abs(exit_fill - exit_price)) * qty
        fees = self.leg_fees(qty, entry_fill * qty, is_sell=not is_long)
        fees += self.leg_fees(qty, exit_fill * qty, is_sell=is_long)
        return slippage + fees


# ----------------------------------------------------------------------------------------------- config


class TrailingStop(BaseModel):
    """Optional stop ratchet evaluated on each close (never loosens the stop).

    ``pct``: trail this far below the best price since entry. ``atr_mult``: trail ``atr_mult * atr_column``
    below the best price (the highest high since entry for longs: with ``atr_22`` and 3.0 this is LeBeau's
    chandelier exit, :meth:`chandelier`). ``breakeven_after_r``: move the stop to the entry fill once the close
    is this many R in profit. Several may be combined; the tightest resulting stop wins.

    Extra exits from docs/catalog/catalog.json ``extra_exit_rules`` (TradeStation / thinkorswim built-ins), all
    off by default: ``close_atr_mult`` trails ``close_atr_mult * atr_column`` below each close (VoltyExpanClose
    LX, ratcheted); ``channel_bars`` trails to the lowest low of the last N bars (channel trailing);
    ``giveback_pct`` keeps at least ``100 - giveback_pct`` % of the best open profit (give-back % of open
    profit; only once the best price is beyond the entry).
    """

    pct: float | None = Field(default=None, gt=0)
    atr_mult: float | None = Field(default=None, gt=0)
    atr_column: str = "atr_14"
    breakeven_after_r: float | None = Field(default=None, gt=0)
    close_atr_mult: float | None = Field(default=None, gt=0)
    channel_bars: int | None = Field(default=None, ge=1)
    giveback_pct: float | None = Field(default=None, gt=0, lt=100)

    @classmethod
    def chandelier(
        cls, atr_mult: float = CHANDELIER_ATR_MULT, period: int = CHANDELIER_ATR_PERIOD
    ) -> TrailingStop:
        """Chandelier exit: ``atr_mult`` x ATR(``period``) below the highest high since entry."""
        return cls(atr_mult=atr_mult, atr_column=f"atr_{period}")


class BacktestConfig(BaseModel):
    initial_equity: float = DEFAULT_INITIAL_EQUITY
    max_hold_bars: int = Field(default=DEFAULT_MAX_HOLD_BARS, ge=1)
    trailing: TrailingStop | None = None
    #: bars of history handed to ``strategy.signals`` each day (None = everything up to as_of)
    signal_lookback_bars: int | None = Field(default=None, ge=1)
    allow_short: bool = True
    #: conservative convention when stop and target both touch inside one bar
    stop_first_when_both_hit: bool = True
    #: cancel a queued entry when the open is already through the stop (or through ``entry_limit``)
    skip_entry_if_open_through_stop: bool = True
    #: ``exit_rule(row, position) -> bool`` evaluated on the close with the symbol's panel row (features included)
    exit_rule: Callable[[Any, Any], bool] | None = None
    #: ``trail_rule(row) -> float | None``: indicator stop level ratcheted on the close (never loosened, never
    #: through the close), live from the next bar. Filled from the strategy's ``trail_stop`` hook when unset.
    trail_rule: Callable[[Any], float | None] | None = None
    #: exit at the close once this many closes since entry were in profit (extra_exit_rules; None = off)
    profitable_closes: int | None = Field(default=None, ge=1)


# ----------------------------------------------------------------------------------------------- sizing

Sizer = Callable[[Signal, float, RiskConfig, list[Position]], OrderIntent | None]
"""Same call shape as ``risk.sizing.size_signal(signal, equity, risk_cfg, open_positions)``."""

UniverseAt = Callable[[date], Collection[str] | None]
"""``universe_at(as_of)`` -> symbols admissible for signals emitted at that close (None = no restriction)."""


def fixed_fractional_sizer(
    signal: Signal,
    equity: float,
    risk_cfg: RiskConfig,
    open_positions: Iterable[Position] | None = None,
    sector_map: Mapping[str, str] | None = None,
) -> OrderIntent | None:
    """Default research sizer: risk ``risk_per_trade_pct`` of equity per trade, capped at ``max_position_pct``.

    Schwab example from the API contract: $50,000 x 1% = $500 risk; $2 risk per share -> 250 shares.
    Plug ``risk.sizing.size_signal`` in instead for the production rules (reward/risk gate, vol target,
    sector caps).
    """
    positions = list(open_positions or [])
    rps = signal.risk_per_share()
    if equity <= 0 or signal.entry <= 0 or rps <= 0:
        return None
    if len(positions) >= risk_cfg.max_open_positions or any(p.symbol == signal.symbol for p in positions):
        return None
    qty_risk = math.floor(equity * risk_cfg.risk_per_trade_pct / PCT / rps)
    qty_cap = math.floor(equity * risk_cfg.max_position_pct / PCT / signal.entry)
    qty = min(qty_risk, qty_cap)
    if qty < 1:
        return None
    return OrderIntent(
        symbol=signal.symbol,
        side=signal.side,
        qty=qty,
        entry_limit=None,
        stop=signal.stop,
        target=signal.target,
        strategy=signal.strategy,
        client_order_id=f"{CLIENT_ORDER_PREFIX}-{signal.strategy}-{signal.symbol}-{signal.as_of:%Y%m%d}",
        risk_dollars=qty * rps,
    )


# ----------------------------------------------------------------------------------------------- state


@dataclass
class OpenPosition:
    """Book-keeping for one open trade. Public because ``BacktestConfig.exit_rule`` receives it."""

    symbol: str
    side: Side
    qty: int
    entry_price: float  # fill, slippage included
    entry_ts: pd.Timestamp
    entry_idx: int
    stop: float
    initial_stop: float
    target: float | None
    strategy: str
    score: float
    risk_per_share: float
    last_close: float
    best_price: float  # most favourable extreme since entry
    worst_price: float  # most adverse extreme since entry
    bars_held: int = 0
    slippage_cost: float = 0.0
    fees: float = 0.0
    profitable_closes: int = 0  # closes beyond the entry fill since entry (extra_exit_rules)
    entry_features: dict[str, float] = field(default_factory=dict)  # the entry Signal.features
    signal_as_of: date | None = None  # the entry Signal.as_of

    @property
    def direction(self) -> int:
        return 1 if self.side == Side.LONG else -1

    @property
    def is_long(self) -> bool:
        return self.side == Side.LONG

    def to_position(self) -> Position:
        return Position(
            symbol=self.symbol,
            qty=self.qty,
            avg_entry=self.entry_price,
            side=self.side,
            stop=self.stop,
            target=self.target,
            strategy=self.strategy,
            opened_at=self.entry_ts.to_pydatetime(),
        )

    def context(self, row: Any = None) -> PositionContext:
        """The ``should_exit(row, bars_held, position)`` context; ``row`` (today's bar, checked before
        ``_mark_position``) folds today's extreme into ``best_price``."""
        best = self.best_price
        extreme = row.get("high" if self.is_long else "low") if row is not None else None
        if extreme is not None and math.isfinite(float(extreme)):
            best = max(best, float(extreme)) if self.is_long else min(best, float(extreme))
        return PositionContext(
            entry_price=self.entry_price, stop=self.stop, initial_stop=self.initial_stop, bars_held=self.bars_held,
            best_price=best, entry_features=self.entry_features, as_of=self.signal_as_of,
        )


@dataclass
class BacktestResult:
    strategy: str
    start: date
    end: date
    initial_equity: float
    costs: CostModel
    config: BacktestConfig
    equity: pd.DataFrame  # index ts; columns EQUITY_COLUMNS
    trades: pd.DataFrame  # one row per closed trade; columns TRADE_COLUMNS
    n_signals: int = 0
    n_entries_skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def final_equity(self) -> float:
        return float(self.equity["equity"].iloc[-1]) if len(self.equity) else self.initial_equity

    @property
    def total_return(self) -> float:
        return self.final_equity / self.initial_equity - 1.0

    @property
    def returns(self) -> pd.Series:
        return self.equity["ret"]

    @property
    def exposure(self) -> float:
        """Mean gross exposure (market value / equity) over the window."""
        return float(self.equity["exposure"].mean()) if len(self.equity) else 0.0


# ----------------------------------------------------------------------------------------------- panel view


def _as_date(value: date | datetime | str | pd.Timestamp | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp | datetime):
        return value.date()
    if isinstance(value, str):
        return pd.Timestamp(value).date()
    return value


class _PanelView:
    """Wide numpy price arrays (dates x symbols) plus a point-in-time slicer over the long panel."""

    def __init__(self, panel: pd.DataFrame, extra_columns: Iterable[str] = ()):
        missing = [c for c in (SYMBOL, TS, *PRICE_COLUMNS) if c not in panel.columns]
        if missing:
            raise KeyError(f"panel is missing columns {missing}")
        frame = panel.drop_duplicates([SYMBOL, TS], keep="last")
        frame = frame.sort_values([TS, SYMBOL], kind="stable").reset_index(drop=True)
        self.frame = frame
        self.ts_index = pd.DatetimeIndex(frame[TS])
        self.dates = pd.DatetimeIndex(frame[TS].unique()).sort_values()
        self.day_of = np.array([d.date() for d in self.dates], dtype=object)
        self.symbols: list[str] = sorted(str(s) for s in frame[SYMBOL].unique().tolist())
        self.sym_pos = {s: j for j, s in enumerate(self.symbols)}
        cols = [*PRICE_COLUMNS, *[c for c in extra_columns if c in frame.columns and c not in PRICE_COLUMNS]]
        self.wide: dict[str, np.ndarray] = {}
        for c in cols:
            wide = frame.pivot(index=TS, columns=SYMBOL, values=c)
            self.wide[c] = wide.reindex(index=self.dates, columns=self.symbols).to_numpy(dtype=float)
        has_bar = ~np.isnan(self.wide["close"])
        n_dates = has_bar.shape[0]
        self.last_bar_idx = np.where(has_bar.any(axis=0), n_dates - 1 - np.argmax(has_bar[::-1], axis=0), -1)
        #: symbol -> exit multiplier on the last close when its bars stop (data.delisted.delisting_returns)
        self.delist_mult: dict[str, float] = {}
        self._indexed: pd.DataFrame | None = None

    def delisted_exit(self, symbol: str, last_close: float) -> float:
        """Raw exit price of a position whose symbol has no more bars: the last close, times the delisting-return
        multiplier for a performance delisting (Shumway -30% by default), unchanged for mergers / unknown."""
        return last_close * self.delist_mult.get(symbol, 1.0)

    def index_range(self, start: date | None, end: date | None) -> tuple[int, int]:
        mask = np.ones(len(self.dates), dtype=bool)
        if start is not None:
            mask &= self.day_of >= start
        if end is not None:
            mask &= self.day_of <= end
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            raise ValueError(f"no trading days in panel between {start} and {end}")
        return int(idx[0]), int(idx[-1])

    def upto(self, i: int, lookback: int | None) -> pd.DataFrame:
        """Rows with ts <= dates[i] (and >= dates[i-lookback+1] when a lookback is set)."""
        end = int(self.ts_index.searchsorted(self.dates[i], side="right"))
        if lookback is None:
            return self.frame.iloc[:end]
        first = self.dates[max(0, i - lookback + 1)]
        begin = int(self.ts_index.searchsorted(first, side="left"))
        return self.frame.iloc[begin:end]

    def row(self, i: int, symbol: str) -> pd.Series:
        if self._indexed is None:
            self._indexed = self.frame.set_index([TS, SYMBOL]).sort_index()
        return self._indexed.loc[(self.dates[i], symbol)]

    def bar(self, i: int, j: int) -> tuple[float, float, float, float]:
        return tuple(float(self.wide[c][i, j]) for c in PRICE_COLUMNS)  # type: ignore[return-value]

    def value(self, column: str, i: int, j: int) -> float:
        arr = self.wide.get(column)
        return float(arr[i, j]) if arr is not None else math.nan


class _RegimeLookup:
    """Per-day regime dict for ``Strategy.signals`` from a SPY ``market`` frame or market_* panel columns."""

    def __init__(self, market: pd.DataFrame | None, panel: pd.DataFrame):
        self.table: pd.DataFrame | None = None
        sources: list[tuple[pd.DataFrame, bool]] = []
        if market is not None and TS in market.columns:
            sources.append((market, True))
        sources.append((panel, False))
        # raw SPY bars carry no regime columns: fall back to the panel's market_* columns (built by
        # features.panel) so the backtest applies the same market gate as `swing scan`.
        for source, from_market in sources:
            rename = self._regime_columns(source, from_market)
            if rename:
                table = source[[TS, *rename]].drop_duplicates(TS, keep="last").rename(columns=rename)
                self.table = table.set_index(TS).sort_index()
                return

    @staticmethod
    def _regime_columns(source: pd.DataFrame, from_market: bool) -> dict[str, str]:
        rename: dict[str, str] = {}
        for c in source.columns:
            if c in MARKET_REGIME_COLUMNS:
                rename[c] = c
            elif from_market and c in REGIME_ALIASES and REGIME_ALIASES[c] not in source.columns:
                rename[c] = REGIME_ALIASES[c]
        return rename

    def __call__(self, day: pd.Timestamp) -> dict[str, Any] | None:
        if self.table is None or day not in self.table.index:
            return None
        row = self.table.loc[day]
        return {k: (None if pd.isna(v) else float(v)) for k, v in row.items()}


# ----------------------------------------------------------------------------------------------- mechanics


def _signal_error(signal: Signal, config: BacktestConfig) -> str | None:
    if signal.entry <= 0 or signal.stop <= 0:
        return "bad_prices"
    if signal.side == Side.LONG:
        if signal.stop >= signal.entry:
            return "stop_not_below_entry"
        if signal.target is not None and signal.target <= signal.entry:
            return "target_not_above_entry"
    else:
        if not config.allow_short:
            return "short_disabled"
        if signal.stop <= signal.entry:
            return "stop_not_above_entry"
        if signal.target is not None and signal.target >= signal.entry:
            return "target_not_below_entry"
    return None


def _select_entries(
    signals: list[Signal],
    positions: dict[str, OpenPosition],
    equity: float,
    risk_cfg: RiskConfig,
    sizer: Sizer,
    config: BacktestConfig,
    skipped: Counter[str],
) -> list[tuple[Signal, OrderIntent]]:
    if not signals:
        return []
    free = risk_cfg.max_open_positions - len(positions)
    if free <= 0:
        skipped["no_free_slot"] += len(signals)
        return []
    open_list = [p.to_position() for p in positions.values()]
    taken = set(positions)
    chosen: list[tuple[Signal, OrderIntent]] = []
    for sig in sorted(signals, key=lambda s: s.score, reverse=True):
        if free <= 0:
            skipped["no_free_slot"] += 1
            continue
        if sig.symbol in taken:
            skipped["symbol_busy"] += 1
            continue
        err = _signal_error(sig, config)
        if err:
            skipped[err] += 1
            continue
        intent = sizer(sig, equity, risk_cfg, open_list)
        if intent is None or intent.qty < 1:
            skipped["sizer_rejected"] += 1
            continue
        chosen.append((sig, intent))
        taken.add(sig.symbol)
        free -= 1
    return chosen


def entry_fill(signal: Signal, open_: float, high: float, low: float) -> tuple[float, str | None]:
    """Entry price on the session after the signal for its ``entry_type`` (long side; shorts mirror).

    open: the open. stop: a buy stop at ``entry`` fills at max(open, entry) when the high reaches it. limit: a buy
    limit at ``entry`` fills at min(open, entry) when the low reaches it. Untriggered orders expire after one day.
    """
    kind, level, long = signal.entry_type, float(signal.entry), signal.side == Side.LONG
    if kind == EntryType.STOP:
        if (high < level) if long else (low > level):
            return open_, "not_triggered"
        return (max(open_, level) if long else min(open_, level)), None
    if kind == EntryType.LIMIT:
        if (low > level) if long else (high < level):
            return open_, "not_triggered"
        return (min(open_, level) if long else max(open_, level)), None
    return open_, None


def _fill_entry(
    i: int,
    signal: Signal,
    intent: OrderIntent,
    view: _PanelView,
    costs: CostModel,
    config: BacktestConfig,
    cash: float,
) -> tuple[OpenPosition | None, float, str | None]:
    j = view.sym_pos.get(intent.symbol)
    if j is None:
        return None, cash, "unknown_symbol"
    raw = view.value("open", i, j)
    if math.isnan(raw):
        return None, cash, "no_bar"
    is_long = intent.side == Side.LONG
    raw, why = entry_fill(signal, raw, view.value("high", i, j), view.value("low", i, j))
    if why:
        return None, cash, why
    through_stop = raw <= intent.stop if is_long else raw >= intent.stop
    if through_stop and config.skip_entry_if_open_through_stop:
        return None, cash, "open_through_stop"
    if intent.entry_limit is not None and config.skip_entry_if_open_through_stop:
        through_limit = raw > intent.entry_limit if is_long else raw < intent.entry_limit
        if through_limit:
            return None, cash, "open_through_limit"
    fill = costs.fill_price(raw, is_buy=is_long)
    qty = int(intent.qty)
    affordable = math.floor(cash / fill) if fill > 0 else 0
    if qty > affordable:
        log.debug("backtest.entry_reduced", symbol=intent.symbol, requested=qty, affordable=affordable)
        qty = affordable
    if qty < 1:
        return None, cash, "insufficient_cash"
    notional = qty * fill
    fees = costs.leg_fees(qty, notional, is_sell=not is_long)
    cash += (-notional - fees) if is_long else (notional - fees)
    pos = OpenPosition(
        symbol=intent.symbol,
        side=intent.side,
        qty=qty,
        entry_price=fill,
        entry_ts=view.dates[i],
        entry_idx=i,
        stop=float(intent.stop),
        initial_stop=float(intent.stop),
        target=None if intent.target is None else float(intent.target),
        strategy=intent.strategy,
        score=float(signal.score),
        risk_per_share=abs(fill - float(intent.stop)),
        last_close=fill,
        best_price=fill,
        worst_price=fill,
        slippage_cost=abs(fill - raw) * qty,
        fees=fees,
        entry_features=dict(signal.features),
        signal_as_of=signal.as_of,
    )
    return pos, cash, None


def _check_exit(
    pos: OpenPosition, view: _PanelView, i: int, max_hold: int, config: BacktestConfig
) -> tuple[ExitReason, float, pd.Timestamp] | None:
    """Return (reason, raw exit price, exit ts) when today's bar closes the position."""
    j = view.sym_pos[pos.symbol]
    o, h, lo, c = view.bar(i, j)
    if math.isnan(c) or math.isnan(o):
        if i > view.last_bar_idx[j]:
            last = int(view.last_bar_idx[j])
            pos.bars_held = last - pos.entry_idx + 1
            return ExitReason.DELISTED, view.delisted_exit(pos.symbol, pos.last_close), view.dates[last]
        return None  # data gap: hold
    pos.bars_held = i - pos.entry_idx + 1
    day = view.dates[i]
    is_long = pos.is_long
    if (o <= pos.stop) if is_long else (o >= pos.stop):
        return ExitReason.STOP_GAP, o, day
    tgt = pos.target
    if tgt is not None and ((o >= tgt) if is_long else (o <= tgt)):
        # the resting limit at the target fills at the open, before any intrabar move back to the stop
        return ExitReason.TARGET, o, day
    stop_hit = lo <= pos.stop if is_long else h >= pos.stop
    target_hit = tgt is not None and ((h >= tgt) if is_long else (lo <= tgt))
    if stop_hit and (config.stop_first_when_both_hit or not target_hit):
        ratcheted = pos.stop > pos.initial_stop if is_long else pos.stop < pos.initial_stop
        return (ExitReason.TRAIL_STOP if ratcheted else ExitReason.STOP), pos.stop, day
    if target_hit and tgt is not None:
        return ExitReason.TARGET, tgt, day
    if i - pos.entry_idx + 1 >= max_hold:
        return ExitReason.TIME, c, day
    if config.profitable_closes is not None:
        in_profit = (c > pos.entry_price) if is_long else (c < pos.entry_price)
        if pos.profitable_closes + int(in_profit) >= config.profitable_closes:
            return ExitReason.PROFITABLE_CLOSES, c, day
    if config.exit_rule is not None and config.exit_rule(view.row(i, pos.symbol), pos):
        return ExitReason.RULE, c, day
    return None


def _ratchet_stop(pos: OpenPosition, trailing: TrailingStop, atr: float, channel: float = math.nan) -> None:
    """Tighten ``pos.stop`` from ``trailing``. ``channel`` is the lowest low (highest high for shorts) of the
    last ``trailing.channel_bars`` bars."""
    is_long = pos.is_long
    sign = pos.direction
    cands: list[float] = []
    if trailing.pct is not None:
        f = trailing.pct / PCT
        cands.append(pos.best_price * (1.0 - f) if is_long else pos.best_price * (1.0 + f))
    atr_ok = math.isfinite(atr) and atr > 0
    if trailing.atr_mult is not None and atr_ok:
        cands.append(pos.best_price - trailing.atr_mult * atr if is_long else pos.best_price + trailing.atr_mult * atr)
    if trailing.close_atr_mult is not None and atr_ok:
        cands.append(pos.last_close - sign * trailing.close_atr_mult * atr)
    if trailing.channel_bars is not None and math.isfinite(channel):
        cands.append(channel)
    if trailing.giveback_pct is not None:
        best_profit = sign * (pos.best_price - pos.entry_price)
        if best_profit > 0:
            cands.append(pos.entry_price + sign * best_profit * (1.0 - trailing.giveback_pct / PCT))
    if trailing.breakeven_after_r is not None and pos.risk_per_share > 0:
        open_r = pos.direction * (pos.last_close - pos.entry_price) / pos.risk_per_share
        if open_r >= trailing.breakeven_after_r:
            cands.append(pos.entry_price)
    if not cands:
        return
    new_stop = max(cands) if is_long else min(cands)
    pos.stop = max(pos.stop, new_stop) if is_long else min(pos.stop, new_stop)


def _mark_position(pos: OpenPosition, view: _PanelView, i: int, config: BacktestConfig) -> None:
    j = view.sym_pos[pos.symbol]
    _, h, lo, c = view.bar(i, j)
    if math.isnan(c):
        return
    pos.last_close = c
    pos.bars_held = i - pos.entry_idx + 1
    if pos.is_long:
        pos.best_price = max(pos.best_price, h)
        pos.worst_price = min(pos.worst_price, lo)
    else:
        pos.best_price = min(pos.best_price, lo)
        pos.worst_price = max(pos.worst_price, h)
    if config.trailing is not None:
        channel = math.nan
        n = config.trailing.channel_bars
        if n is not None:
            window = view.wide["low" if pos.is_long else "high"][max(i - n + 1, 0) : i + 1, j]
            if np.isfinite(window).any():
                channel = float(np.nanmin(window) if pos.is_long else np.nanmax(window))
        _ratchet_stop(pos, config.trailing, view.value(config.trailing.atr_column, i, j), channel)
    if config.trail_rule is not None:
        _apply_trail_level(pos, config.trail_rule(view.row(i, pos.symbol)), c)
    if (c > pos.entry_price) if pos.is_long else (c < pos.entry_price):
        pos.profitable_closes += 1


def _apply_trail_level(pos: OpenPosition, level: Any, close: float) -> None:
    """Ratchet ``pos.stop`` to a strategy trail ``level``: never loosened, never at or through ``close``
    (the same rule as ``execution.position_manager._trail_stop``)."""
    try:
        lv = float(level)
    except (TypeError, ValueError):
        return
    if not math.isfinite(lv) or lv <= 0:
        return
    if pos.is_long and lv < close:
        pos.stop = max(pos.stop, lv)
    elif not pos.is_long and lv > close:
        pos.stop = min(pos.stop, lv)


def _close_position(
    pos: OpenPosition, reason: ExitReason, raw: float, exit_ts: pd.Timestamp, costs: CostModel, cash: float
) -> tuple[dict[str, Any], float]:
    is_long = pos.is_long
    fill = costs.fill_price(raw, is_buy=not is_long)
    notional = pos.qty * fill
    fees = costs.leg_fees(pos.qty, notional, is_sell=is_long)
    cash += (notional - fees) if is_long else (-notional - fees)
    pos.slippage_cost += abs(fill - raw) * pos.qty
    pos.fees += fees
    gross = pos.direction * pos.qty * (fill - pos.entry_price)
    pnl = gross - pos.fees
    risk_dollars = pos.risk_per_share * pos.qty
    entry_notional = pos.qty * pos.entry_price
    rps = pos.risk_per_share
    record = {
        "symbol": pos.symbol,
        "strategy": pos.strategy,
        "side": pos.side.value,
        "entry_ts": pos.entry_ts,
        "entry_price": pos.entry_price,
        "exit_ts": exit_ts,
        "exit_price": fill,
        "qty": pos.qty,
        "initial_stop": pos.initial_stop,
        "stop": pos.stop,
        "target": pos.target,
        "exit_reason": reason.value,
        "bars_held": max(pos.bars_held, 1),
        "pnl": pnl,
        "pnl_pct": pnl / entry_notional if entry_notional else math.nan,
        "r_multiple": pnl / risk_dollars if risk_dollars > 0 else math.nan,
        "entry_notional": entry_notional,
        "slippage_cost": pos.slippage_cost,
        "fees": pos.fees,
        "costs": pos.slippage_cost + pos.fees,
        "mfe_r": pos.direction * (pos.best_price - pos.entry_price) / rps if rps > 0 else math.nan,
        "mae_r": -pos.direction * (pos.worst_price - pos.entry_price) / rps if rps > 0 else math.nan,
        "score": pos.score,
    }
    return record, cash


def _max_hold_for(strategy: Any, config: BacktestConfig) -> int:
    params = getattr(strategy, "params", None) or {}
    value = params.get(STRATEGY_HOLD_PARAM) if isinstance(params, Mapping) else None
    return int(value) if value is not None and int(value) >= 1 else config.max_hold_bars


def strategy_trail_rule(strategy: Any) -> Callable[[Any], float | None] | None:
    """The strategy's ``trail_stop(row)`` hook, or None when it has none (or keeps the no-op default)."""
    hook = getattr(strategy, TRAIL_STOP_HOOK, None)
    if not callable(hook) or getattr(hook, "default_hook", False):
        return None
    return hook


def strategy_engine_trail(strategy: Any) -> bool:
    """False when the strategy opts out of the engine trail overlay (``params["engine_trail"]`` wins)."""
    params = getattr(strategy, "params", None) or {}
    if isinstance(params, Mapping) and params.get(ENGINE_TRAIL_ATTR) is not None:
        return bool(params[ENGINE_TRAIL_ATTR])
    return bool(getattr(strategy, ENGINE_TRAIL_ATTR, True))


def with_atr_column(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    """``panel`` plus ``column`` (``atr_<n>``: Wilder ATR over n bars, per symbol, causal) when it is missing."""
    match = ATR_COLUMN_RE.match(column)
    if column in panel.columns or match is None or panel.empty:
        return panel
    from swing_engine.features.indicators import atr

    period = int(match.group(1))
    ordered = panel.sort_values([SYMBOL, TS], kind="stable")
    parts = [
        atr(g["high"].astype(float), g["low"].astype(float), g["close"].astype(float), period)
        for _, g in ordered.groupby(SYMBOL, sort=False)
    ]
    return panel.assign(**{column: pd.concat(parts).reindex(panel.index)})


def chandelier_stop(
    panel: pd.DataFrame, period: int = CHANDELIER_ATR_PERIOD, atr_mult: float = CHANDELIER_ATR_MULT
) -> pd.Series:
    """Classic rolling chandelier level per row: highest high of ``period`` bars - ``atr_mult`` x ATR(``period``).

    For a strategy's ``trail_stop`` hook (the ``TrailingStop.chandelier`` preset uses the high since entry).
    """
    col = f"atr_{period}"
    frame = with_atr_column(panel, col)
    ordered = frame.sort_values([SYMBOL, TS], kind="stable")  # rolling must run in time order per symbol
    hh = ordered.groupby(SYMBOL, sort=False)["high"].transform(lambda s: s.rolling(period, min_periods=period).max())
    return hh.reindex(frame.index) - atr_mult * frame[col]


def size_floor_universe(
    panel: pd.DataFrame, size_column: str, pctile: float = MICROCAP_SIZE_PCTILE
) -> UniverseAt:
    """``universe_at`` for ``run_backtest`` that drops names below the ``pctile`` size breakpoint of the day.

    catalog microcap_control_vw_nyse (Hou-Xue-Zhang): the breakpoint comes from the session's NYSE rows when the
    panel has an ``exchange`` column and that session has NYSE rows, else from every row of the session (an
    approximation, say so in the write-up).
    ``size_column`` is market cap, or a liquidity proxy such as dollar volume when caps are unavailable.
    Point-in-time: each day uses only that session's rows.
    """
    if size_column not in panel.columns:
        raise KeyError(f"panel has no {size_column!r} column for the size floor")
    day = pd.to_datetime(panel[TS])
    if getattr(day.dt, "tz", None) is not None:
        day = day.dt.tz_localize(None)
    frame = panel.assign(_day=day.dt.date)
    q = pctile / PCT
    cut = frame.groupby("_day")[size_column].quantile(q)
    if SIZE_EXCHANGE_COLUMN in frame.columns:  # per day: NYSE rows when that session has them (point-in-time)
        nyse = frame.loc[frame[SIZE_EXCHANGE_COLUMN] == NYSE_LABEL].groupby("_day")[size_column].quantile(q)
        cut.update(nyse)
    keep = frame.loc[frame[size_column].astype(float) >= frame["_day"].map(cut).astype(float)]
    allowed = {d: frozenset(g[SYMBOL].astype(str)) for d, g in keep.groupby("_day")}

    def universe_at(as_of: date) -> Collection[str] | None:
        return allowed.get(as_of, frozenset())

    return universe_at


def _strategy_exit_rule(strategy: Any) -> Callable[[Any, Any], bool] | None:
    """The strategy's rule exit, if it has one.

    Two duck-typed hooks are honoured: ``exit_rule(row, position)`` (the backtester's own shape) and
    ``should_exit(row, bars_held)``, the hook every ``strategies.PanelStrategy`` implements, called as
    ``should_exit(row, bars_held, OpenPosition.context(row))`` when it accepts the third argument. Without this
    adapter a strategy's documented rule exits (``close > sma_10``, ``rsi_2 > 70`` ...) never fire in research.
    """
    exit_rule = getattr(strategy, "exit_rule", None)
    if callable(exit_rule):
        return exit_rule
    should_exit = getattr(strategy, "should_exit", None)
    if not callable(should_exit):
        return None
    if exit_takes_position(should_exit):
        return lambda row, pos: bool(should_exit(row, pos.bars_held, pos.context(row)))
    return lambda row, pos: bool(should_exit(row, pos.bars_held))


# ----------------------------------------------------------------------------------------------- runner


def run_backtest(
    strategy: Any,
    panel: pd.DataFrame,
    start: date | str | None = None,
    end: date | str | None = None,
    risk_cfg: RiskConfig | None = None,
    costs: CostModel | None = None,
    market: pd.DataFrame | None = None,
    *,
    config: BacktestConfig | None = None,
    sizer: Sizer | None = None,
    universe_at: UniverseAt | None = None,
    delist_returns: Mapping[str, float] | None = None,
) -> BacktestResult:
    """Run ``strategy`` over the long feature ``panel`` between ``start`` and ``end`` (inclusive, by date).

    The strategy may use panel history before ``start`` for warm-up; signals are generated from ``start``
    and fill at the next open. Everything still open at ``end`` is closed at that day's close.
    ``universe_at(as_of)`` (optional) returns the symbols admissible on that day: signals for names outside
    the point-in-time membership are dropped (counted under ``skip_reasons["not_in_universe"]``), so a
    universe screened on later data cannot admit a name before it would have qualified live.
    ``delist_returns`` (``data.delisted.delisting_returns``): exit multipliers for performance delistings.
    """
    risk_cfg = risk_cfg or RiskConfig()
    costs = costs or CostModel()
    config = config or BacktestConfig()
    sizer = sizer or fixed_fractional_sizer
    if config.exit_rule is None:
        rule = _strategy_exit_rule(strategy)
        if rule is not None:
            config = config.model_copy(update={"exit_rule": rule})
    if config.trail_rule is None:
        trail = strategy_trail_rule(strategy)
        if trail is not None:
            config = config.model_copy(update={"trail_rule": trail})
    if config.trailing is not None and not strategy_engine_trail(strategy):
        log.info("backtest.engine_trail_off", strategy=getattr(strategy, "name", None))
        config = config.model_copy(update={"trailing": None})
    if config.trailing is not None:
        panel = with_atr_column(panel, config.trailing.atr_column)

    extra = [config.trailing.atr_column] if config.trailing is not None else []
    view = _PanelView(panel, extra)
    view.delist_mult = dict(delist_returns or {})
    i0, i1 = view.index_range(_as_date(start), _as_date(end))
    regime_at = _RegimeLookup(market, panel)
    max_hold = _max_hold_for(strategy, config)
    strategy_name = str(getattr(strategy, "name", type(strategy).__name__))

    cash = float(config.initial_equity)
    positions: dict[str, OpenPosition] = {}
    pending: list[tuple[Signal, OrderIntent]] = []
    trades: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    n_signals = 0

    for i in range(i0, i1 + 1):
        day = view.dates[i]
        # 1. fill yesterday's signals at today's open
        for sig, intent in pending:
            pos, cash, why = _fill_entry(i, sig, intent, view, costs, config, cash)
            if pos is None:
                skipped[why or "unknown"] += 1
                continue
            positions[pos.symbol] = pos
        pending = []
        # 2. exits on today's bar, then mark survivors
        for sym in list(positions):
            pos = positions[sym]
            hit = _check_exit(pos, view, i, max_hold, config)
            if hit is None:
                _mark_position(pos, view, i, config)
                continue
            reason, raw, exit_ts = hit
            record, cash = _close_position(pos, reason, raw, exit_ts, costs, cash)
            trades.append(record)
            del positions[sym]
        # 3. mark to market
        market_value = sum(p.direction * p.qty * p.last_close for p in positions.values())
        gross = sum(abs(p.qty * p.last_close) for p in positions.values())
        equity = cash + market_value
        curve.append(
            {
                TS: day,
                "equity": equity,
                "cash": cash,
                "market_value": market_value,
                "exposure": gross / equity if equity > 0 else math.nan,
                "n_positions": len(positions),
            }
        )
        # 4. signals at the close for next-open entry
        if i < i1:
            signals = list(strategy.signals(view.upto(i, config.signal_lookback_bars), day.date(), regime_at(day)))
            n_signals += len(signals)
            if universe_at is not None:
                allowed = universe_at(day.date())
                if allowed is not None:
                    kept = [s for s in signals if s.symbol in allowed]
                    skipped["not_in_universe"] += len(signals) - len(kept)
                    signals = kept
            pending = _select_entries(signals, positions, equity, risk_cfg, sizer, config, skipped)

    # forced close at the last close of the window
    for sym in list(positions):
        pos = positions.pop(sym)
        raw = view.value("close", i1, view.sym_pos[sym])
        record, cash = _close_position(pos, ExitReason.END, raw if math.isfinite(raw) else pos.last_close, view.dates[i1], costs, cash)
        trades.append(record)
    if curve:
        curve[-1].update(equity=cash, cash=cash, market_value=0.0, exposure=0.0, n_positions=0)

    equity_df = pd.DataFrame(curve).set_index(TS) if curve else pd.DataFrame(columns=EQUITY_COLUMNS)
    if len(equity_df):
        equity_df["ret"] = equity_df["equity"].pct_change().fillna(0.0)
    equity_df = equity_df[EQUITY_COLUMNS]
    trades_df = pd.DataFrame(trades, columns=TRADE_COLUMNS) if trades else pd.DataFrame(columns=TRADE_COLUMNS)
    if len(trades_df):
        trades_df = trades_df.sort_values(["entry_ts", "symbol"], kind="stable").reset_index(drop=True)

    result = BacktestResult(
        strategy=strategy_name,
        start=view.dates[i0].date(),
        end=view.dates[i1].date(),
        initial_equity=float(config.initial_equity),
        costs=costs,
        config=config,
        equity=equity_df,
        trades=trades_df,
        n_signals=n_signals,
        n_entries_skipped=int(sum(skipped.values())),
        skip_reasons=dict(skipped),
    )
    log.info(
        "backtest.done",
        strategy=strategy_name,
        start=str(result.start),
        end=str(result.end),
        days=len(equity_df),
        signals=n_signals,
        trades=len(trades_df),
        final_equity=round(result.final_equity, 2),
        skipped=dict(skipped),
    )
    return result
