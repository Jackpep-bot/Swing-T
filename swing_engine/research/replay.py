"""Day-by-day replay of the whole decision loop: regime router -> strategies -> shadow ledger -> sizing -> fills
-> position management, on daily bars from the store.

``run_backtest`` tests one strategy in isolation; this replays what the nightly + autopilot would have done, with
every enabled strategy competing for the same slots, the playbook router gating them by market regime and scaling
their risk, and the position manager's exit semantics. Timeline for each NYSE session ``D`` in ``[start, end]``:

1. **open of D**: closes decided at the previous close (time stop, strategy rule exit) fill at the open; then the
   previous close's entries fill at the open with the marketable-limit rule (skipped when the open is above
   ``entry_limit`` or already through the stop, ``risk.sizing.entry_limit_for``);
2. **during D**: resting stops and targets on the daily high/low, stop first when both touch, gap-through fills
   at the open (``research.backtest._check_exit``);
3. **close of D**: ``execution.position_manager`` decides time stops, rule exits (filled at the next open, as the
   autopilot's market closes would be) and breakeven / trailing stop moves from ``settings.execution`` (live from
   the next session); the book is marked to market;
4. **after the close of D**: the router reads the market state from panel rows dated on or before ``D`` only,
   every strategy scans the same point-in-time slice, all signals go to the shadow ledger with a ``taken`` flag,
   and the allowed ones are ranked by score and sized by ``risk.sizing.size_signal_detail`` (per-strategy
   ``min_reward_risk``; ``risk_per_trade_pct`` scaled by the router multiplier), capped by
   ``max_open_positions`` and ``execution.max_new_orders_per_day``.

The feature panel is built once from store bars (features are causal, ``docs/feature-contract.md``) and each day
sees only ``panel[ts <= D]``. Like the nightly, strategies, ``rs_63d_rank``, the strategies' ``<col>_rank`` extras
and breadth see only the point-in-time universe: the nightly's screen (``data.universe.build_universe`` on the store's ``symbols`` table, else
``data.universe.liquidity_screen``; as-traded through the ``splits`` table) on bars dated on or before the session,
refreshed every ``UNIVERSE_REFRESH_SESSIONS`` sessions, with the index ETFs kept out of the breadth population. Costs come from ``research.backtest.CostModel``; each run is logged as a trial
(``research.trials``, feeds the deflated Sharpe of ``docs/gates.md``). Deterministic: same store, same settings,
same result. Not modelled: earnings exits (no point-in-time earnings calendar in the store), intraday entry
triggers, partial exits (``docs/methods.md`` 7a item 4). Nothing here reads a model or an LLM.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog

from swing_engine.core import registry
from swing_engine.core.config import Settings
from swing_engine.core.interfaces import Strategy
from swing_engine.core.models import OrderIntent, Position, Signal
from swing_engine.execution.position_manager import ExitKind, _Held, _review_one, build_strategies
from swing_engine.execution.position_manager import ExitReason as PMExitReason
from swing_engine.research.backtest import (
    EQUITY_COLUMNS,
    TRADE_COLUMNS,
    BacktestConfig,
    BacktestResult,
    CostModel,
    ExitReason,
    OpenPosition,
    _check_exit,
    _close_position,
    _fill_entry,
    _mark_position,
    _PanelView,
    _RegimeLookup,
)
from swing_engine.research.metrics import profit_factor, summarize
from swing_engine.research.shadow import REPLAY_SHADOW_TABLE, grade_signals, record_signals, signal_key
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, log_trial
from swing_engine.risk.sizing import size_signal_detail, sizing_equity, strategy_min_reward_risk

log = structlog.get_logger(__name__)

#: Same warm-up as ops.nightly.PANEL_WARMUP_CALENDAR_DAYS: covers sma_200 / high_52w / mom_12_1 before ``start``.
WARMUP_CALENDAR_DAYS = 400
#: Bars handed to ``Strategy.signals`` each day; >= the longest on-the-fly window a strategy computes (252 bars).
SIGNAL_LOOKBACK_SESSIONS = 300
#: The market proxy whose bars feed ``features.panel.build_panel(bars, market)`` (ops.nightly.MARKET_SYMBOL).
MARKET_SYMBOL = "SPY"
REPLAY_SOURCE = "replay"
TRIAL_NAME = "replay"
DEFAULT_EQUITY = 100_000.0
#: Time stops belong to the position manager (decided at the close, filled next open), not to ``_check_exit``.
NO_BAR_TIME_STOP = 10**9
FULL_RISK = 1.0
#: Order of (strategy) names in ``daily.allowed``: ``name=multiplier`` pairs joined by this separator.
ALLOWED_SEP = ";"
#: Sessions between point-in-time universe screens. The nightly screens every night; weekly keeps a multi-year
#: replay cheap, at the cost of a name entering or leaving the screen up to 4 sessions late.
UNIVERSE_REFRESH_SESSIONS = 5
#: Kept out of the breadth population (ops.nightly.INDEX_SYMBOLS; the playbook's market_symbol is added).
INDEX_SYMBOLS: tuple[str, ...] = ("SPY", "QQQ", "IWM")
#: Kept in the replay panel even when no universe screen admits them: the market proxy, index ETFs and the SPDR
#: sector ETFs that market-relative and sector-rotation strategies read (faber_sector_rotation,
#: industry_momentum_overlay).
ALWAYS_KEEP: tuple[str, ...] = (
    *INDEX_SYMBOLS, "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
)
SYMBOLS_TABLE = "symbols"  # data.universe.SYMBOLS_TABLE
SPLITS_TABLE = "splits"  # data.universe.SPLITS_TABLE
RS_RANK_COLUMN = "rs_63d_rank"  # features.patterns2: same-session percentile of the 63-bar return
RS_RETURN_BARS = 63

PM_TO_TRADE_REASON: dict[str, ExitReason] = {
    PMExitReason.TIME_STOP.value: ExitReason.TIME,
    PMExitReason.STRATEGY_EXIT.value: ExitReason.RULE,
}
EXTRA_TRADE_COLUMNS = ["signal_date", "regime", "risk_mult"]
DAILY_COLUMNS = [
    "date", "regime", "allowed", "n_signals", "n_allowed_signals", "n_orders", "n_filled", "n_entry_skipped",
    "n_exits", "n_positions", "equity", "cash",
]
GROUP_COLUMNS = ["trades", "win_rate", "avg_r", "expectancy_r", "profit_factor", "total_pnl", "avg_hold_bars"]

MarketStateFn = Callable[..., Any]
SelectFn = Callable[..., Mapping[str, float]]


@dataclass
class ReplayResult:
    equity_curve: pd.DataFrame  # index ts; EQUITY_COLUMNS
    trades: pd.DataFrame  # TRADE_COLUMNS + signal_date, regime, risk_mult
    daily: pd.DataFrame  # one row per session; DAILY_COLUMNS
    by_strategy: pd.DataFrame  # index strategy; GROUP_COLUMNS
    by_regime: pd.DataFrame  # index regime (at signal time); GROUP_COLUMNS
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Order:
    signal: Signal
    intent: OrderIntent
    regime: str | None
    risk_mult: float


@dataclass
class _Meta:
    signal_date: date
    regime: str | None
    risk_mult: float


# ----------------------------------------------------------------------------------------------- lazy imports


def _load_router() -> tuple[MarketStateFn, SelectFn] | None:
    """``strategies.playbook`` (market_state, select_strategies), or None when the module is not available."""
    try:
        from swing_engine.strategies.playbook import market_state, select_strategies
    except ImportError:
        return None
    return market_state, select_strategies


def _load_breadth() -> Callable[..., pd.DataFrame] | None:
    try:
        from swing_engine.features.breadth import market_breadth
    except ImportError:
        return None
    return market_breadth


# ----------------------------------------------------------------------------------------------- inputs


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, pd.Timestamp | datetime):
        return value.date()
    if isinstance(value, str):
        return pd.Timestamp(value).date()
    return value


def _enabled_names(settings: Settings) -> list[str]:
    if not settings.strategies:  # no strategy config at all: every registered strategy
        return registry.names("strategy")
    return [n for n, cfg in settings.strategies.items() if (cfg or {}).get("enabled", True)]


def _resolve_strategies(
    settings: Settings, strategies: Mapping[str, Any] | Iterable[Any] | None
) -> dict[str, Strategy]:
    chosen = list(strategies.items()) if isinstance(strategies, Mapping) else list(strategies or [])
    if not chosen:  # None or empty (e.g. the CLI without --strategy): the strategies enabled in settings
        built = build_strategies(settings, _enabled_names(settings))
    else:
        built = build_strategies(settings, dict(chosen) if isinstance(strategies, Mapping) else chosen)
    if not built:
        raise ValueError("no strategies to replay (none enabled in settings and none passed)")
    return dict(sorted(built.items()))


def _session_days() -> Callable[[date, date], list[date]] | None:
    try:
        from swing_engine.data.calendar import trading_days
    except ImportError:  # pragma: no cover - the calendar is a core dependency
        return None
    return trading_days


def build_replay_panel(store: Any, start: date, end: date, settings: Settings | None = None) -> pd.DataFrame:
    """Store bars from ``start - WARMUP_CALENDAR_DAYS`` to ``end`` -> ``features.panel.build_panel`` (SPY as market).

    With ``settings``, symbols no universe screen in ``start..end`` admits (``_screened_symbols_only``) are dropped
    from the bars first: every panel feature is computed per symbol, so the kept rows are unchanged and the
    feature build skips the ~80% of the store that is never scanned."""
    from swing_engine.features.panel import build_panel

    first = start - timedelta(days=WARMUP_CALENDAR_DAYS)
    bars = store.read_bars(None, first, end)
    if bars is None or bars.empty:
        raise ValueError(f"no bars in the store between {first} and {end}")
    if settings is not None:
        screened = _screened_symbols_only(_sessions_only(bars, first, end), settings, store, start, end)
        if len(screened) < len(bars):
            bars = bars.loc[bars["symbol"].isin(set(screened["symbol"]))]
    market = bars.loc[bars["symbol"] == MARKET_SYMBOL]
    return build_panel(bars, market if not market.empty else None)


def _screened_symbols_only(
    panel: pd.DataFrame, settings: Settings, store: Any, start: date, end: date
) -> pd.DataFrame:
    """Drop symbols that no universe screen in ``start..end`` admits (plus ALWAYS_KEEP), before the per-symbol
    feature work. They are never scanned, held or counted in breadth, so results are unchanged; the full store
    (~16,000 symbols, most of them illiquid) otherwise dominates replay memory and time."""
    view = _PanelView(panel[[c for c in ("symbol", "ts", "open", "high", "low", "close", "volume") if c in panel]])
    i0, i1 = view.index_range(start, end)
    schedule = _UniverseSchedule(settings, store, view, list(range(i0, i1 + 1, UNIVERSE_REFRESH_SESSIONS)))
    screened = set().union(*schedule.sets)
    if not screened:  # nothing passes (hand-built test panels): keep everything, as before
        return panel
    keep = screened | set(ALWAYS_KEEP)
    out = panel.loc[panel["symbol"].astype(str).isin(keep)]
    log.info("replay.screened_symbols", kept=len(keep & set(panel["symbol"].astype(str))),
             of=int(panel["symbol"].nunique()))
    return out


def _delisting_returns(store: Any, settings: Settings) -> dict[str, float]:
    """``data.delisted.delisting_returns``: exit multipliers for held entity keys that delisted for performance."""
    from swing_engine.data.delisted import delisting_returns

    return delisting_returns(store, settings)


def _with_edgar(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """EDGAR earnings / fundamentals columns (``data.fundamentals.join_edgar``), the split-adjusted share-count
    columns (``join_share_issuance``) and the VIX / French factor columns
    (``data.market_series.join_market_series``) when the store has them."""
    if store is None:
        return panel
    from swing_engine.data.fundamentals import join_edgar, join_share_issuance
    from swing_engine.data.market_series import join_market_series

    return join_market_series(store, join_share_issuance(store, join_edgar(store, panel)))


def _with_extras(panel: pd.DataFrame, strategies: Any) -> pd.DataFrame:
    """Attach the strategies' ``extra_features`` (``features.extra``) once for the whole replay; the panel's SPY
    rows serve as the market proxy. The base column of each ``<col>_rank`` extra is attached too, so
    ``_rerank_extras`` can re-rank it among the screened universe."""
    from swing_engine.features.extra import ensure_extra, rank_base, required_extras

    names = required_extras(strategies)
    bases = [b for b in map(rank_base, names) if b is not None]
    return ensure_extra(panel, [*bases, *names])


def _sessions_only(panel: pd.DataFrame, first: date, last: date) -> pd.DataFrame:
    """Drop rows dated on non-NYSE sessions (synthetic or bad vendor rows) so the walk is session by session."""
    trading_days = _session_days()
    if trading_days is None:
        return panel
    ts = pd.to_datetime(panel["ts"])
    days = pd.Series([t.date() for t in ts], index=panel.index)
    sessions = set(trading_days(first, last))
    keep = days.isin(sessions)
    dropped = int((~keep).sum())
    if dropped:
        log.warning("replay.non_session_rows_dropped", rows=dropped)
    return panel.loc[keep]


def _with_patterns2(panel: pd.DataFrame) -> pd.DataFrame:
    """Attach ``features.patterns2`` columns once for the whole replay (causal by contract).

    Strategies built on patterns2 compute the columns for the panel object they are handed and cache them per
    object; replay hands them a fresh point-in-time slice every session, so without this the columns would be
    recomputed each day on a 300-bar window (slower, and EMA / ADX would restart their warm-up every day).
    """
    try:
        from swing_engine.features.patterns2 import PATTERNS2_COLUMNS, add_patterns2
    except ImportError:  # pragma: no cover - module ships with the engine
        return panel
    if all(c in panel.columns for c in PATTERNS2_COLUMNS):
        return panel
    ordered = panel.sort_values(["symbol", "ts"], kind="mergesort").reset_index(drop=True)
    return add_patterns2(ordered)


class _BreadthSlicer:
    """Breadth computed once over the panel (per-date, causal by contract); handed out as rows <= as_of."""

    def __init__(self, breadth: pd.DataFrame | None):
        self.frame: pd.DataFrame | None = None
        self.days = np.array([], dtype=object)
        if breadth is None or len(breadth) == 0:
            return
        idx = pd.to_datetime(pd.Index(breadth.index))
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
        order = np.argsort(idx.to_numpy(), kind="stable")
        self.frame = breadth.iloc[order]  # original index kept: market_state reads it as it comes
        self.days = np.array([t.date() for t in idx[order]], dtype=object)

    def upto(self, day: date) -> pd.DataFrame | None:
        if self.frame is None:
            return None
        return self.frame.iloc[: int(np.searchsorted(self.days, day, side="right"))]


def _breadth(
    fn: Callable[..., pd.DataFrame], panel: pd.DataFrame, settings: Settings, splits: pd.DataFrame | None = None
) -> pd.DataFrame:
    """``market_breadth`` over ``panel`` (the point-in-time universe's rows) without the index ETFs, the same
    population as ``ops.nightly.screened_breadth``; ``splits`` puts the 4% days' share floor on as-traded volume."""
    playbook = getattr(settings, "playbook", None)
    market = str(getattr(playbook, "market_symbol", MARKET_SYMBOL))
    exclude = tuple(dict.fromkeys((*INDEX_SYMBOLS, market)))
    return fn(panel, exclude=exclude, splits=splits) if splits is not None else fn(panel, exclude=exclude)


class _StoreListing:
    """Provider-shaped view over the store's ``symbols`` table for ``data.universe.build_universe``; never fetches."""

    name = "store"

    def __init__(self, symbols: pd.DataFrame):
        self._symbols = symbols

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        return self._symbols

    def daily_bars(self, symbols: Any, start: date, end: date) -> pd.DataFrame:
        raise RuntimeError("the replay universe screens the panel's own bars; it never fetches")


def _store_table(store: Any, name: str) -> pd.DataFrame | None:
    has_table = getattr(store, "has_table", None)
    try:
        if not callable(has_table) or not has_table(name):
            return None
        table = store.read_table(name)
    except Exception as exc:  # noqa: BLE001 - optional reference input
        log.info("replay.table_unavailable", table=name, error=str(exc))
        return None
    return table if table is not None and len(table) else None


class _UniverseSchedule:
    """Point-in-time universe per session, screened at ``refresh`` view indices on bars dated on or before each
    one (``ops.nightly._screen_universe``: static_symbols, else build_universe on the store's symbols table, else
    a liquidity-only screen; as-traded through the splits table). Session ``i`` uses the latest screen at or
    before it; warm-up rows before the first screen use the first one."""

    def __init__(self, settings: Settings, store: Any, view: _PanelView, refresh: list[int]):
        from swing_engine.data.universe import build_universe, liquidity_screen, lookback_window

        cfg = settings.universe
        self.refresh = np.asarray(refresh, dtype=int)
        self.sets: list[frozenset[str]] = []
        static = frozenset(s.upper() for s in cfg.static_symbols)
        symbols = None if static else _store_table(store, SYMBOLS_TABLE)
        splits = None if static else _store_table(store, SPLITS_TABLE)
        cols = [c for c in ("symbol", "ts", "open", "high", "low", "close", "volume") if c in view.frame.columns]
        for i in refresh:
            if static:
                self.sets.append(static)
                continue
            day = view.dates[i].date()
            first, _last = lookback_window(day)
            lo = int(view.ts_index.searchsorted(view.dates[int(np.searchsorted(view.day_of, first))], side="left"))
            hi = int(view.ts_index.searchsorted(view.dates[i], side="right"))
            window = view.frame.iloc[lo:hi][cols]
            if symbols is not None:
                names = build_universe(_StoreListing(symbols), settings, day, bars=window, splits=splits)
            else:
                stats = liquidity_screen(window, cfg, day, splits)
                passed = stats.loc[stats["passes"].astype(bool)]
                passed = passed.sort_values(["avg_dollar_volume", "symbol"], ascending=[False, True])
                names = passed["symbol"].astype(str).head(cfg.max_symbols).tolist()
            self.sets.append(frozenset(str(n) for n in names))
        member = np.zeros((len(self.sets), len(view.symbols)), dtype=bool)
        for k, names in enumerate(self.sets):
            for sym in names:
                j = view.sym_pos.get(sym)
                if j is not None:
                    member[k, j] = True
        row_day = view.dates.get_indexer(view.ts_index)
        period = np.clip(np.searchsorted(self.refresh, row_day, side="right") - 1, 0, None)
        sym_idx = view.frame["symbol"].astype(str).map(view.sym_pos).to_numpy(dtype=int)
        #: per view.frame row: the symbol was in the universe screened for that row's session
        self.row_member = pd.Series(member[period, sym_idx], index=view.frame.index)

    def at(self, i: int) -> frozenset[str]:
        return self.sets[max(int(np.searchsorted(self.refresh, i, side="right")) - 1, 0)]

    @property
    def mean_size(self) -> float:
        return float(np.mean([len(s) for s in self.sets])) if self.sets else 0.0


def _universe_rank(values: pd.Series, ts: pd.Series, member: pd.Series) -> pd.Series:
    """Same-session percentile (``rank(pct=True)``) of ``values`` among the universe's rows. A row outside the
    universe (never scanned, but a held name that left the screen still needs its exit rank) is placed among that
    session's members as if it were added, like the nightly ranks held names with its screened panel."""
    v = values.astype(float)
    inside = v.where(member)
    ranked = inside.groupby(ts, sort=False).rank(pct=True)
    outside = ~member & v.notna()
    if outside.any():
        has = inside.notna()
        pool = {k: np.sort(g.to_numpy()) for k, g in inside[has].groupby(ts[has], sort=False)}
        empty = np.array([], dtype=float)
        for k, idx in v[outside].groupby(ts[outside], sort=False).groups.items():
            m, x = pool.get(k, empty), v[idx].to_numpy()
            lo, hi = np.searchsorted(m, x, "left"), np.searchsorted(m, x, "right")
            ranked.loc[idx] = (lo + (hi - lo + 2) / 2) / (len(m) + 1)  # average rank among ties, itself included
    return ranked


def _rerank_rs(frame: pd.DataFrame, member: pd.Series) -> None:
    """``rs_63d_rank`` among the universe's rows of each session (in place), as the nightly ranks its screened
    panel (``_universe_rank``)."""
    if RS_RANK_COLUMN not in frame.columns:
        return
    ret_col = f"ret_{RS_RETURN_BARS}d"
    if ret_col in frame.columns:
        ret = frame[ret_col].astype(float)
    else:
        close = frame["close"].astype(float)
        ret = close / close.groupby(frame["symbol"], sort=False).shift(RS_RETURN_BARS) - 1.0
    frame[RS_RANK_COLUMN] = _universe_rank(ret, frame["ts"], member)


def _rerank_extras(frame: pd.DataFrame, member: pd.Series, strategies: Any) -> None:
    """The strategies' ``<col>_rank`` extras re-ranked among the universe's rows (in place); ``ensure_extra``
    ranked them over every symbol in the store."""
    from swing_engine.features.extra import rank_base, required_extras

    for name in required_extras(strategies):
        base = rank_base(name)
        if base is not None and name in frame.columns and base in frame.columns:
            frame[name] = _universe_rank(frame[base], frame["ts"], member)


def _regime_label(state: Any) -> str | None:
    regime = getattr(state, "regime", None)
    if regime is None:
        return None
    overlays = getattr(state, "overlays", None) or []  # fired playbook overlays split reports: "choppy+q25_bearish"
    return "+".join([str(getattr(regime, "value", regime)), *overlays])


# ----------------------------------------------------------------------------------------------- per-symbol frames


class _SymbolRows:
    """Per-symbol row positions in the view frame plus each row's session index (for position-manager frames)."""

    def __init__(self, view: _PanelView):
        self.view = view
        self.rows = {str(k): np.asarray(v) for k, v in view.frame.groupby("symbol", sort=False).indices.items()}
        self.day_idx = view.dates.get_indexer(pd.DatetimeIndex(view.frame["ts"]))
        naive = view.dates.tz_localize(None) if view.dates.tz is not None else view.dates
        self.naive_days = naive.normalize()

    def frame(self, symbol: str, first: int, last: int) -> pd.DataFrame:
        rows = self.rows.get(symbol)
        if rows is None:
            return pd.DataFrame()
        di = self.day_idx[rows]
        sel = rows[(di >= first) & (di <= last)]
        sub = self.view.frame.iloc[sel]
        return sub.assign(_day=self.naive_days[self.day_idx[sel]])


# ----------------------------------------------------------------------------------------------- mechanics


def _skip_bucket(reason: str) -> str:
    if reason.startswith("reward_risk"):
        return "below_min_reward_risk"
    if reason.startswith("max open positions"):
        return "no_free_slot"
    if reason.startswith("size rounds to zero"):
        return "size_zero"
    if "already has an open position" in reason:
        return "symbol_busy"
    return "sizer_rejected"


def _pending_position(order: _Order) -> Position:
    intent = order.intent
    return Position(
        symbol=intent.symbol, qty=intent.qty, avg_entry=float(intent.entry_limit or order.signal.entry),
        side=intent.side, stop=intent.stop, target=intent.target, strategy=intent.strategy,
    )


def _manage(
    pos: OpenPosition,
    i: int,
    rows: _SymbolRows,
    strategies: Mapping[str, Strategy],
    settings: Settings,
    day: date,
) -> tuple[ExitReason | None, float | None]:
    """Position-manager decision at the close of ``day``: (exit reason for the next open, new stop)."""
    lookback = settings.execution.trail_lookback_days
    frame = rows.frame(pos.symbol, min(pos.entry_idx, i - lookback + 1), i)
    held = _Held(
        position=pos.to_position(), strategy=pos.strategy, entry_day=pos.entry_ts.date(),
        initial_stop=pos.initial_stop, current_stop=pos.stop, entry_features=pos.entry_features,
        signal_as_of=pos.signal_as_of,
    )
    actions = _review_one(held, frame, strategies.get(pos.strategy), settings, day, None)
    for action in actions:
        if action.kind == ExitKind.CLOSE:
            return PM_TO_TRADE_REASON.get(action.reason.value, ExitReason.RULE), None
        if action.kind == ExitKind.REPLACE_STOP and action.new_stop is not None:
            return None, float(action.new_stop)
    return None, None


def _group_stats(trades: pd.DataFrame, key: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=GROUP_COLUMNS).rename_axis(key)
    data = trades.assign(**{key: trades[key].astype(object).where(trades[key].notna(), "unknown")})
    out = []
    for name, g in data.groupby(key, sort=True):
        r = g["r_multiple"].astype(float)
        out.append(
            {
                key: name,
                "trades": len(g),
                "win_rate": float((g["pnl"] > 0).mean()),
                "avg_r": float(r.mean()),
                "expectancy_r": float(r.mean()),
                "profit_factor": profit_factor(g["pnl"]),
                "total_pnl": float(g["pnl"].sum()),
                "avg_hold_bars": float(g["bars_held"].mean()),
            }
        )
    return pd.DataFrame(out).set_index(key)[GROUP_COLUMNS]


def _settings_params(settings: Settings, strategies: Mapping[str, Strategy]) -> dict[str, Any]:
    playbook = getattr(settings, "playbook", None)
    if hasattr(playbook, "model_dump"):
        playbook = playbook.model_dump()
    return {
        "strategies": {n: dict(getattr(s, "params", {}) or {}) for n, s in strategies.items()},
        "risk": settings.risk.model_dump(),
        "execution": settings.execution.model_dump(
            include={"max_new_orders_per_day", "breakeven_after_r", "trail_after_r", "trail_lookback_days"}
        ),
        "playbook": playbook,
    }


# ----------------------------------------------------------------------------------------------- runner


def run_replay(
    settings: Settings,
    store: Any,
    start: date | str,
    end: date | str,
    *,
    strategies: Mapping[str, Any] | Iterable[Any] | None = None,
    use_router: bool = True,
    equity: float = DEFAULT_EQUITY,
    costs: CostModel | None = None,
    panel: pd.DataFrame | None = None,
    record_shadow: bool = True,
    shadow_table: str = REPLAY_SHADOW_TABLE,
    trials_path: str | Path | None = DEFAULT_TRIALS_PATH,
    screen_universe: bool = True,
) -> ReplayResult:
    """Replay the engine over NYSE sessions ``start..end`` (inclusive) on ``store`` bars; see the module docstring.

    ``strategies``: names or instances (None or empty: the ones enabled in ``settings.strategies``). ``use_router=False`` (or no
    ``strategies.playbook`` module) allows every strategy at full risk; the regime label is still recorded when
    the router exists. Extensions beyond the contract: ``panel`` (a pre-built feature panel instead of building
    one from the store), ``record_shadow`` / ``shadow_table`` (shadow ledger target, default
    ``shadow_signals_replay`` so the live nightly's ``shadow_signals`` is never touched; skipped on a read-only store),
    ``trials_path`` (None = do not log a trial) and ``screen_universe`` (False = every panel symbol is scanned and
    counted in breadth, the pre-screen behaviour; for hand-built test panels).
    """
    start_d, end_d = _as_date(start), _as_date(end)
    if end_d < start_d:
        raise ValueError(f"end {end_d} is before start {start_d}")
    costs = costs or CostModel()
    strat_map = _resolve_strategies(settings, strategies)
    screened_bars = panel is None and screen_universe
    if panel is None:
        panel = build_replay_panel(store, start_d, end_d, settings if screen_universe else None)
    panel = _sessions_only(panel, start_d - timedelta(days=WARMUP_CALENDAR_DAYS), end_d)
    if screen_universe and not screened_bars:
        panel = _screened_symbols_only(panel, settings, store, start_d, end_d)
    panel = _with_patterns2(panel)
    panel = _with_edgar(store, panel)
    panel = _with_extras(panel, strat_map.values())
    view = _PanelView(panel)
    panel = None  # view.frame is a sorted copy: let the unsorted one go
    view.delist_mult = _delisting_returns(store, settings)
    i0, i1 = view.index_range(start_d, end_d)
    rows = _SymbolRows(view)
    regime_at = _RegimeLookup(None, view.frame)
    universe: _UniverseSchedule | None = None
    breadth_input = view.frame
    if screen_universe:
        universe = _UniverseSchedule(settings, store, view, list(range(i0, i1 + 1, UNIVERSE_REFRESH_SESSIONS)))
        _rerank_rs(view.frame, universe.row_member)
        _rerank_extras(view.frame, universe.row_member, strat_map.values())
        breadth_input = view.frame.loc[universe.row_member]
    router = _load_router()
    breadth_fn = _load_breadth() if router is not None else None
    breadth_error: str | None = None
    breadth_df: pd.DataFrame | None = None
    if breadth_fn is not None:
        try:
            breadth_df = _breadth(breadth_fn, breadth_input, settings, _store_table(store, SPLITS_TABLE))
        except Exception as exc:  # noqa: BLE001 - the router can still run on trend/vol alone
            breadth_error = f"{type(exc).__name__}: {exc}"
            log.warning("replay.breadth_failed", error=breadth_error)
    breadth = _BreadthSlicer(breadth_df)
    shadow_on = record_shadow and not getattr(store, "read_only", False)
    if record_shadow and not shadow_on:
        log.warning("replay.shadow_skipped", reason="read-only store")

    risk_cfg = settings.risk
    max_new = settings.execution.max_new_orders_per_day
    bt_config = BacktestConfig(initial_equity=float(equity), trailing=None, exit_rule=None)
    cash = float(equity)
    positions: dict[str, OpenPosition] = {}
    meta: dict[str, _Meta] = {}
    pending_entries: list[_Order] = []
    pending_exits: dict[str, ExitReason] = {}
    trades: list[dict[str, Any]] = []
    curve: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    regimes: Counter[str] = Counter()
    n_signals = n_orders = 0

    def close(sym: str, reason: ExitReason, raw: float, ts: pd.Timestamp) -> None:
        nonlocal cash
        pos = positions.pop(sym)
        record, cash = _close_position(pos, reason, raw, ts, costs, cash)
        m = meta.pop(sym)
        record.update(signal_date=m.signal_date, regime=m.regime, risk_mult=m.risk_mult)
        trades.append(record)
        pending_exits.pop(sym, None)

    for i in range(i0, i1 + 1):
        ts = view.dates[i]
        day = ts.date()
        n_exits_before = len(trades)
        # 1. open: yesterday's close decisions, then yesterday's entries (marketable limit)
        for sym in sorted(pending_exits):
            j = view.sym_pos[sym]
            raw = view.value("open", i, j)
            if math.isnan(raw):
                if i > view.last_bar_idx[j]:
                    last = int(view.last_bar_idx[j])
                    close(sym, ExitReason.DELISTED, view.delisted_exit(sym, positions[sym].last_close), view.dates[last])
                continue  # data gap: the market order waits for the next bar
            close(sym, pending_exits[sym], raw, ts)
        n_filled = n_skip = 0
        for order in pending_entries:
            pos, cash, why = _fill_entry(i, order.signal, order.intent, view, costs, bt_config, cash)
            if pos is None:
                skipped[why or "unknown"] += 1
                n_skip += 1
                continue
            positions[pos.symbol] = pos
            meta[pos.symbol] = _Meta(order.signal.as_of, order.regime, order.risk_mult)
            n_filled += 1
        pending_entries = []
        # 2. intraday: stops / targets (stop first), gap-through fills at the open
        for sym in sorted(positions):
            if sym in pending_exits:
                continue
            pos = positions[sym]
            hit = _check_exit(pos, view, i, NO_BAR_TIME_STOP, bt_config)
            if hit is None:
                _mark_position(pos, view, i, bt_config)
                continue
            reason, raw, exit_ts = hit
            close(sym, reason, raw, exit_ts)
        # 3. close: position-manager exits (next open) and stop ratchets (next session)
        for sym in sorted(positions):
            if sym in pending_exits:
                continue
            reason_next, new_stop = _manage(positions[sym], i, rows, strat_map, settings, day)
            if reason_next is not None:
                pending_exits[sym] = reason_next
            elif new_stop is not None:
                positions[sym].stop = new_stop
        market_value = sum(p.direction * p.qty * p.last_close for p in positions.values())
        gross = sum(abs(p.qty * p.last_close) for p in positions.values())
        eq = cash + market_value
        curve.append(
            {"ts": ts, "equity": eq, "cash": cash, "market_value": market_value,
             "exposure": gross / eq if eq > 0 else math.nan, "n_positions": len(positions)}
        )
        # 4. after the close: router, signals, shadow ledger, sizing for the next open
        label: str | None = None
        allowed: dict[str, float] = {}
        day_signals: list[Signal] = []
        taken: set[str] = set()
        if i < i1:
            upto_all = view.upto(i, None)
            allowed = {name: FULL_RISK for name in strat_map}
            if router is not None:
                try:
                    state = router[0](upto_all, day, breadth=breadth.upto(day), settings=settings)
                except Exception as exc:
                    if use_router:
                        raise  # the router gates orders: never trade on a silently missing regime
                    state = None  # label only: keep replaying without one
                    if not failures["market_state"]:
                        log.warning("replay.market_state_failed", day=str(day), error=str(exc))
                    failures["market_state"] += 1
                label = _regime_label(state)
                if use_router:
                    chosen = router[1](state, settings)
                    allowed = {n: float(m) for n, m in sorted(chosen.items()) if n in strat_map and float(m) > 0}
            regimes[label or "unknown"] += 1
            upto = view.upto(i, SIGNAL_LOOKBACK_SESSIONS)
            if universe is not None:
                upto = upto.loc[upto["symbol"].isin(universe.at(i))]
            regime_dict = regime_at(ts)
            for name, strat in strat_map.items():
                try:
                    day_signals.extend(strat.signals(upto, day, regime_dict))
                except Exception as exc:  # noqa: BLE001 - one broken strategy must not end the replay
                    if not failures[name]:
                        log.warning("replay.strategy_failed", strategy=name, day=str(day), error=str(exc))
                    failures[name] += 1
            n_signals += len(day_signals)
            cands = [s for s in day_signals if allowed.get(s.strategy, 0.0) > 0]
            cands.sort(key=lambda s: (-s.score, s.strategy, s.symbol))
            open_list = [p.to_position() for p in positions.values()]
            busy = set(positions)
            size_eq = eq
            if risk_cfg.drawdown_size_mult or risk_cfg.book_vol_target_annual_pct is not None:
                hist = np.array([row["equity"] for row in curve], dtype=float)
                size_eq = sizing_equity(eq, risk_cfg, float(hist.max()), hist[1:] / hist[:-1] - 1.0)
            for sig in cands:
                if len(pending_entries) >= max_new:
                    skipped["daily_order_cap"] += 1
                    continue
                if sig.symbol in busy:
                    skipped["symbol_busy"] += 1
                    continue
                mult = min(max(allowed[sig.strategy], 0.0), FULL_RISK)
                scaled = risk_cfg.model_copy(update={"risk_per_trade_pct": risk_cfg.risk_per_trade_pct * mult})
                rr_floor = strategy_min_reward_risk(settings.strategies, sig.strategy)
                intent, why = size_signal_detail(sig, size_eq, scaled, open_list, None, rr_floor)
                if intent is None:
                    skipped[_skip_bucket(why)] += 1
                    continue
                order = _Order(sig, intent, label, mult)
                pending_entries.append(order)
                open_list.append(_pending_position(order))
                busy.add(sig.symbol)
                taken.add(signal_key(sig))
            n_orders += len(pending_entries)
            if shadow_on and day_signals:
                record_signals(store, day_signals, taken, day, label, source=REPLAY_SOURCE, table=shadow_table)
        daily.append(
            {
                "date": day, "regime": label,
                "allowed": ALLOWED_SEP.join(f"{n}={m:g}" for n, m in allowed.items()),
                "n_signals": len(day_signals),
                "n_allowed_signals": sum(1 for s in day_signals if allowed.get(s.strategy, 0.0) > 0),
                "n_orders": len(pending_entries), "n_filled": n_filled, "n_entry_skipped": n_skip,
                "n_exits": len(trades) - n_exits_before, "n_positions": len(positions), "equity": eq, "cash": cash,
            }
        )

    # forced close at the last close of the window (unfilled orders simply lapse)
    for sym in sorted(positions):
        raw = view.value("close", i1, view.sym_pos[sym])
        close(sym, ExitReason.END, raw if math.isfinite(raw) else positions[sym].last_close, view.dates[i1])
    if curve:
        curve[-1].update(equity=cash, cash=cash, market_value=0.0, exposure=0.0, n_positions=0)
        daily[-1].update(equity=cash, cash=cash, n_positions=0)

    equity_df = pd.DataFrame(curve).set_index("ts")
    equity_df["ret"] = equity_df["equity"].pct_change().fillna(0.0)
    equity_df = equity_df[EQUITY_COLUMNS]
    cols = [*TRADE_COLUMNS, *EXTRA_TRADE_COLUMNS]
    trades_df = pd.DataFrame(trades, columns=cols) if trades else pd.DataFrame(columns=cols)
    if len(trades_df):
        trades_df = trades_df.sort_values(["entry_ts", "symbol"], kind="stable").reset_index(drop=True)
    daily_df = pd.DataFrame(daily, columns=DAILY_COLUMNS)

    shadow_graded = 0
    if shadow_on:
        shadow_graded = grade_signals(store, end_d, table=shadow_table, delist_returns=view.delist_mult)

    bt = BacktestResult(
        strategy=TRIAL_NAME, start=view.dates[i0].date(), end=view.dates[i1].date(), initial_equity=float(equity),
        costs=costs, config=bt_config, equity=equity_df, trades=trades_df, n_signals=n_signals,
        n_entries_skipped=int(sum(skipped.values())), skip_reasons=dict(skipped),
    )
    summary = summarize(bt)
    summary.update(
        {
            "strategies": list(strat_map),
            "use_router": bool(use_router),
            "router_available": router is not None,
            "breadth_available": breadth.frame is not None,
            "breadth_error": breadth_error,
            "universe_screened": universe is not None,
            "universe_mean_size": universe.mean_size if universe is not None else None,
            "sessions": int(i1 - i0 + 1),
            "n_orders": n_orders,
            "skip_reasons": dict(sorted(skipped.items())),
            "strategy_failures": dict(sorted(failures.items())),
            "regime_days": dict(sorted(regimes.items())),
            "shadow_recorded": bool(shadow_on),
            "shadow_resolved": shadow_graded,
        }
    )
    if trials_path is not None:
        params = {"start": start_d, "end": end_d, "use_router": use_router, "equity": equity,
                  "costs": costs.model_dump(), **_settings_params(settings, strat_map)}
        log_trial(TRIAL_NAME, params, summary, trials_path, tags=["replay", *strat_map])
    log.info(
        "replay.done", start=str(summary["start"]), end=str(summary["end"]), trades=summary["trades"],
        signals=n_signals, orders=n_orders, final_equity=round(float(equity_df["equity"].iloc[-1]), 2),
        router=router is not None and use_router,
    )
    return ReplayResult(
        equity_curve=equity_df,
        trades=trades_df,
        daily=daily_df,
        by_strategy=_group_stats(trades_df, "strategy"),
        by_regime=_group_stats(trades_df, "regime"),
        summary=summary,
    )


__all__ = ["ReplayResult", "build_replay_panel", "run_replay"]

