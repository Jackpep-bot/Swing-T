"""`swing nightly`: the unattended evening pipeline, one step per CLI command, each timed and isolated.

ingest (incremental) -> features (liquidity-screened panel + market breadth) -> scan (market state ->
playbook router -> allowed strategies) -> rank predict (when a model exists) -> size (when equity is known; the
router's per-strategy multiplier scales risk_per_trade_pct) -> review (ANTHROPIC key, not dry-run) -> shadow
(every signal into the shadow ledger, taken or not, and grading of matured ones) -> positions (exit decisions,
when a broker is injected) -> execute (execution.autopilot, when enabled) -> journal -> weekly (agent.weekly, last session of the ISO
week only). A failing step is recorded and the pipeline carries on with
whatever the earlier steps produced (a broken ingest still scans yesterday's store; a broken scan leaves
nothing to size). The run ends with a JSON report under `<store dir>/runs/nightly/YYYY-MM-DD.json`.

Hand-offs use the same `<store dir>/runs/<kind>/<date>.json` files as the CLI, so `swing size`, `swing paper`
and `swing journal` can pick up where the nightly left off. The broker, when injected, supplies equity and
open positions to `size` and `positions`. Orders leave this module only through `execute`, which hands the
sized intents, the reviews and the exit actions to `execution.autopilot.run_autopilot` (paper-only automatic
approval, kill switch, limits, daily cap, audit). `execute` runs after `review` so Claude's vetoes apply, is
skipped on `dry_run` (never execute when dry), and defaults to `settings.execution.nightly_execute`.
The review step only filters already-sized intents by `Review.decision` (an enum); every price, stop and
share count comes from `strategies/` and `risk/`.

`run_cycle` (`swing autopilot`) runs size -> positions -> execute alone from the latest saved signals.

Fail-closed entry gates in `execute` (exits always still run): entries are held when the review step failed
(nightly), when the saved review outcome for the signals' day says the review failed or never finished
(`runs/review_status/<date>.json`, written by the review step; `run_cycle`), and when the positions step
failed (an exception there means no exit decisions were made, so no new risk is added either).

Regime routing (docs/methods.md sections 0 and 2a: gate first, then select, then trigger): the scan computes
`strategies.playbook.market_state` for `as_of`, runs only the strategies `select_strategies` allows, saves the
state to `runs/regime/<date>.json` (also on `NightlyReport.market_state` and in the journal), and the size step
scales each strategy's risk by its multiplier; `run_cycle` re-applies the saved multipliers. The breadth,
playbook and shadow modules are loaded lazily through `contract_fn`. The router is a veto layer and fails
closed: a playbook that raises (at import or when called), or that is absent, fails the scan step, so nothing
is sized (exits still run); `playbook.enabled: false` is the explicit way to run every enabled strategy at
1.0. Only an absent shadow module merely skips its step.
"""
from __future__ import annotations

import importlib
import inspect
import json
import pickle
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from pydantic import BaseModel, Field

from swing_engine.core import registry
from swing_engine.core.config import ROOT, Secrets, Settings
from swing_engine.core.models import OrderIntent, Review, ReviewDecision, Signal

log = structlog.get_logger(__name__)

# ---- file layout (mirrors swing_engine.cli) ----------------------------------------------------------------
RUNS_DIRNAME = "runs"
NIGHTLY_KIND = "nightly"
SIGNALS_KIND = "signals"
REVIEWS_KIND = "reviews"
INTENTS_KIND = "intents"
FILLS_KIND = "fills"
CONTEXT_KIND = "context"
RANK_KIND = "rank"
EXITS_KIND = "exits"
CYCLE_KIND = "cycle"
REVIEW_STATUS_KIND = "review_status"  # {"status": running|ok|skip|fail, "detail": ...} per signals day
REGIME_KIND = "regime"  # {"market_state": MarketState, "allowed": {strategy: multiplier}, "blocked": {...}}
EARNINGS_TABLE = "earnings"  # optional store table (symbol, report_date) for the close-before-earnings rule
PANEL_TABLE = "panel"
PANEL_KEYS = ["symbol", "ts"]
SYMBOLS_TABLE = "symbols"
RANKER_FILENAME = "ranker.pkl"
MARKET_SYMBOL = "SPY"
BREADTH_TABLE = "breadth"  # features.breadth.market_breadth over the screened panel, one row per session
BREADTH_KEY = "date"
# Always in the panel even when the liquidity screen drops them (ETFs fail the common-stock filter): the market
# gauges docs/methods.md 2a names (SPY vs its 200-day, QQQ vs its 20 EMA) plus IWM for small-cap participation.
INDEX_SYMBOLS = ("SPY", "QQQ", "IWM")
RANK_FEATURE = "rank_score"  # Signal.features key the rank step fills (model output, never LLM output)

# ---- windows -----------------------------------------------------------------------------------------------
DAYS_PER_YEAR = 365
PANEL_WARMUP_CALENDAR_DAYS = 400  # covers sma_200 / mom_12_1 before the first scored session
REGIME_COLUMNS = ("market_trend_state", "market_vol_regime")
ERROR_PREVIEW_CHARS = 200

STEP_NAMES = (
    "ingest", "float", "features", "scan", "rank", "size", "review", "shadow", "positions", "execute", "journal",
    "weekly",
)
REVIEW_RUNNING, REVIEW_OK, REVIEW_SKIP, REVIEW_FAIL = "running", "ok", "skip", "fail"
CYCLE_STEP_NAMES = ("size", "positions", "execute")
ABORTED_MODE = "aborted"  # execution.autopilot.AutopilotMode.ABORTED

# ---- contract modules written alongside this one: loaded lazily, a missing one skips only its part --------
CONTRACT: dict[str, str] = {
    "market_breadth": "features.breadth.market_breadth",
    "market_state": "strategies.playbook.market_state",
    "select_strategies": "strategies.playbook.select_strategies",
    "record_signals": "research.shadow.record_signals",
    "grade_signals": "research.shadow.grade_signals",
}
# playbook multipliers only scale risk down, never above risk.risk_per_trade_pct (docs/methods.md 2e: same risk
# every trade; 3c: "reduced size" is the regime's lever)
MULTIPLIER_MIN, MULTIPLIER_MAX = 0.0, 1.0
TAKEN_KEY_SEP = ":"  # research.shadow `taken` keys are "strategy:symbol" (research.shadow.signal_key)
# strategies.<name>: {enabled: false, shadow_only: true} -> scanned every night and recorded in the shadow ledger
# (never sized, reviewed or executed): how a strategy collects evidence before docs/gates.md lets it trade
SHADOW_ONLY_KEY = "shadow_only"
STRATEGY_META_KEYS = frozenset({"enabled", SHADOW_ONLY_KEY})


class StepStatus(StrEnum):
    OK = "ok"
    FAIL = "fail"
    SKIP = "skip"


class StepResult(BaseModel):
    name: str
    status: StepStatus
    elapsed_s: float = 0.0
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class NightlyReport(BaseModel):
    as_of: date
    provider: str
    dry_run: bool
    started_at: datetime
    finished_at: datetime | None = None
    elapsed_s: float = 0.0
    steps: list[StepResult] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)  # kind -> path written during this run
    report_path: str | None = None
    regime: dict[str, Any] | None = None  # the runs/regime/<date>.json payload: market_state, allowed, blocked

    @property
    def ok(self) -> bool:
        return not any(s.status is StepStatus.FAIL for s in self.steps)

    @property
    def failed(self) -> list[str]:
        return [s.name for s in self.steps if s.status is StepStatus.FAIL]

    def step(self, name: str) -> StepResult | None:
        return next((s for s in self.steps if s.name == name), None)

    def summary(self) -> dict[str, Any]:
        return {s.name: s.status.value for s in self.steps}


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def _load(dotted: str) -> Any:
    """`swing_engine.<module>.<attr>`; ImportError/AttributeError propagate into the step's failure."""
    module_path, _, attr = dotted.rpartition(".")
    return getattr(importlib.import_module(f"swing_engine.{module_path}"), attr)


def _try_load(dotted: str) -> Any | None:
    try:
        return _load(dotted)
    except Exception:
        return None


def _call_supported(fn: Any, *args: Any, **candidates: Any) -> Any:
    """Call `fn(*args, **kw)` keeping only keyword arguments the function accepts (names-only contracts)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(*args)
    accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    kwargs = {k: v for k, v in candidates.items() if accepts_kwargs or k in params}
    return fn(*args, **kwargs)


def _resolve(path: str | Path) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else ROOT / p


def store_dir(settings: Settings) -> Path:
    return _resolve(settings.data.store_path).parent


def run_file(settings: Settings, kind: str, as_of: date) -> Path:
    return store_dir(settings) / RUNS_DIRNAME / kind / f"{as_of.isoformat()}.json"


def _save_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _save_models(path: Path, items: list[BaseModel]) -> Path:
    return _save_json(path, [m.model_dump(mode="json") for m in items])


def _load_models(path: Path, model_cls: type[BaseModel]) -> list[Any]:
    if not path.exists():
        return []
    return [model_cls.model_validate(r) for r in json.loads(path.read_text(encoding="utf-8") or "[]")]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8") or "null") or default


def _naive_ts(frame: pd.DataFrame) -> pd.Series:
    ts = pd.to_datetime(frame["ts"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    return ts


def _on_or_before(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    if frame.empty or "ts" not in frame.columns:
        return frame
    return frame.loc[_naive_ts(frame) < pd.Timestamp(as_of) + pd.Timedelta(days=1)]


def _latest_rows(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    sliced = _on_or_before(frame, as_of)
    if sliced.empty:
        return sliced
    ts = _naive_ts(sliced)
    return sliced.loc[ts == ts.max()]


def _latest_session(frame: pd.DataFrame | None, as_of: date) -> date | None:
    """Session date of the last bar on or before `as_of` (the bar the strategies' `rows_as_of` scans). A run
    before the open (06:30 ET, `as_of` = today) only has the previous session in the store."""
    if frame is None or len(frame) == 0 or "ts" not in frame.columns:
        return None
    sliced = _on_or_before(frame, as_of)
    if sliced.empty:
        return None
    return _naive_ts(sliced).max().date()


def _market_slice(bars: pd.DataFrame) -> pd.DataFrame | None:
    if "symbol" not in bars.columns:
        return None
    market = bars.loc[bars["symbol"] == MARKET_SYMBOL]
    return market if not market.empty else None


def _regime(panel: pd.DataFrame, as_of: date) -> dict[str, Any] | None:
    latest = _latest_rows(panel, as_of)
    cols = [c for c in REGIME_COLUMNS if c in latest.columns]
    if latest.empty or not cols:
        return None
    row = latest.iloc[-1]
    return {c: (None if pd.isna(row[c]) else float(row[c])) for c in cols}


def _error_text(e: BaseException) -> str:
    text = f"{type(e).__name__}: {' '.join(str(e).split())}"
    redact = _try_load("data._http.redact_secrets")
    if redact is not None:
        text = redact(text)
    return text if len(text) <= ERROR_PREVIEW_CHARS else text[: ERROR_PREVIEW_CHARS - 1] + "…"


class _StoreListing:
    """Provider-shaped view over the store's `symbols` table so `data.universe.build_universe` can screen
    the point-in-time universe from stored bars (no network)."""

    name = "store"

    def __init__(self, symbols: pd.DataFrame) -> None:
        self._symbols = symbols

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        return self._symbols

    def daily_bars(self, symbols: Any, start: date, end: date) -> pd.DataFrame:
        raise RuntimeError("the store-backed universe screens the panel's own bars; it never fetches")


def _enabled_strategies(settings: Settings) -> list[str]:
    """Strategies enabled in settings; every registered one only when settings configure none at all (a config
    that disables them all means no strategy trades, never all of them)."""
    if not settings.strategies:
        return registry.names("strategy")
    return [n for n, cfg in settings.strategies.items() if (cfg or {}).get("enabled", True)]


def _shadow_only_strategies(settings: Settings) -> list[str]:
    """Disabled strategies flagged `shadow_only`: scanned and recorded in the shadow ledger, never traded."""
    return [n for n, cfg in settings.strategies.items()
            if not (cfg or {}).get("enabled", True) and (cfg or {}).get(SHADOW_ONLY_KEY)]


def _strategy_params(settings: Settings, name: str) -> dict[str, Any]:
    cfg = settings.strategies.get(name) or {}
    if isinstance(cfg.get("params"), dict):
        return dict(cfg["params"])
    return {k: v for k, v in cfg.items() if k not in STRATEGY_META_KEYS}


def _load_ranker(path: Path) -> Any:
    ranker_cls = _try_load("research.ranker.RankerModel")
    if ranker_cls is not None and hasattr(ranker_cls, "load"):
        try:
            return ranker_cls.load(str(path))
        except TypeError:  # a model saved by another backend; fall through to plain pickle
            pass
    with path.open("rb") as fh:
        return pickle.load(fh)  # noqa: S301 - local file written by `swing rank train`


def _account_equity(account: dict[str, Any]) -> float | None:
    for key in ("equity", "portfolio_value", "last_equity", "cash"):
        value = account.get(key)
        if value is not None:
            return float(value)
    return None


def contract_fn(name: str) -> tuple[Any | None, str]:
    """`(function, "")` for a `CONTRACT` name, or `(None, reason)` only when its module is genuinely absent
    (ModuleNotFoundError naming that very module). Anything else raised while importing it (the playbook's
    regime-drift guard, a missing dependency, a syntax error) or a missing attribute propagates, so a broken
    router fails the step instead of passing for "not installed". Tests monkeypatch this one function to stub
    the breadth / playbook / shadow modules."""
    dotted = CONTRACT[name]
    module_path, _, attr = dotted.rpartition(".")
    module_name = f"swing_engine.{module_path}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:  # the module exists but one of its imports does not: broken, not absent
            raise
        return None, f"swing_engine.{dotted} unavailable ({_error_text(e)})"
    return getattr(module, attr), ""


def _jsonable(obj: Any) -> Any:
    """Plain JSON-able form of a pydantic model / mapping / enum (MarketState is a pydantic model)."""
    if obj is None:
        return None
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return json.loads(json.dumps(obj, default=str))
    return json.loads(json.dumps(getattr(obj, "__dict__", str(obj)), default=str))


def regime_name(state: Any) -> str | None:
    """`MarketState.regime` as plain text (it may be an enum or a Literal string)."""
    value = getattr(state, "regime", None)
    if value is None and isinstance(state, dict):
        value = state.get("regime")
    return None if value is None else str(getattr(value, "value", value))


def route_strategies(
    settings: Settings, multipliers: dict[str, Any], enabled: list[str] | None = None
) -> tuple[dict[str, float], dict[str, str]]:
    """Split the enabled strategies by `select_strategies`' table: `allowed` {name: multiplier clipped to
    [MULTIPLIER_MIN, MULTIPLIER_MAX]} and `blocked` {name: reason}. A name absent from the table, or with a
    multiplier of zero, is not allowed (docs/methods.md 2a: the regime is a veto layer)."""
    names = enabled if enabled is not None else _enabled_strategies(settings)
    allowed: dict[str, float] = {}
    blocked: dict[str, str] = {}
    for name in names:
        raw = multipliers.get(name)
        if raw is None:
            blocked[name] = "not in the playbook table for this regime"
            continue
        mult = min(max(float(raw), MULTIPLIER_MIN), MULTIPLIER_MAX)
        if mult <= MULTIPLIER_MIN:
            blocked[name] = "multiplier 0 in this regime"
        else:
            allowed[name] = mult
    return allowed, blocked


def _scaled_risk(risk_cfg: Any, multiplier: float) -> Any:
    if multiplier >= MULTIPLIER_MAX:
        return risk_cfg
    return risk_cfg.model_copy(update={"risk_per_trade_pct": risk_cfg.risk_per_trade_pct * multiplier})


# ----------------------------------------------------------------------------------------------------------
# pipeline state and runner
# ----------------------------------------------------------------------------------------------------------
@dataclass
class _Context:
    settings: Settings
    secrets: Secrets
    as_of: date
    provider: str
    equity: float | None
    dry_run: bool
    store: Any
    broker: Any | None
    review_client: Any | None
    journal_client: Any | None
    journal_root: Path | None
    report: NightlyReport
    panel: pd.DataFrame | None = None
    signals: list[Signal] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    intents: list[OrderIntent] = field(default_factory=list)
    execute: bool = False
    plan_on_dry_run: bool = False  # `swing autopilot --dry-run` plans through the autopilot; the nightly skips
    exit_actions: list[Any] = field(default_factory=list)
    stale_signals: str | None = None  # why saved signals were not sized (run_cycle only)
    review_hold: str | None = None  # why entries must be held: the saved review failed/never finished (run_cycle)
    universe: list[str] | None = None  # liquidity-screened at as_of by the features step (None = not screened)
    breadth: pd.DataFrame | None = None  # features.breadth.market_breadth over the screened panel
    market_state: Any | None = None  # strategies.playbook.MarketState for as_of
    risk_multipliers: dict[str, float] | None = None  # allowed strategy -> multiplier; None = no routing (full risk)
    signal_day: date | None = None  # session of the bars the scan computed signals from (<= as_of)
    shadow_signals: list[Signal] = field(default_factory=list)  # shadow_only strategies: recorded, never sized

    @property
    def history_start(self) -> date:
        return self.as_of - timedelta(days=DAYS_PER_YEAR * self.settings.data.history_years)

    def file(self, kind: str) -> Path:
        return run_file(self.settings, kind, self.as_of)

    def save(self, kind: str, items: list[BaseModel]) -> Path:
        path = _save_models(self.file(kind), items)
        self.report.files[kind] = str(path)
        return path


class Skip(Exception):
    """Raised inside a step to record it as skipped (with a reason) instead of failed."""


def _run_step(ctx: _Context, name: str, fn: Callable[[_Context], tuple[str, dict[str, Any]]]) -> StepResult:
    t0 = time.perf_counter()
    try:
        detail, data = fn(ctx)
        result = StepResult(name=name, status=StepStatus.OK, detail=detail, data=data)
    except Skip as e:
        result = StepResult(name=name, status=StepStatus.SKIP, detail=str(e))
    except Exception as e:
        result = StepResult(name=name, status=StepStatus.FAIL, detail=_error_text(e))
        log.error("nightly_step_failed", step=name, error=result.detail)
    result.elapsed_s = round(time.perf_counter() - t0, 3)
    log.info("nightly_step", step=name, status=result.status.value, elapsed_s=result.elapsed_s, detail=result.detail)
    ctx.report.steps.append(result)
    return result


# ----------------------------------------------------------------------------------------------------------
# steps
# ----------------------------------------------------------------------------------------------------------
def _step_ingest(ctx: _Context) -> tuple[str, dict[str, Any]]:
    run_ingest = _load("data.ingest.run_ingest")
    result = dict(
        _call_supported(
            run_ingest, ctx.settings, ctx.secrets, ctx.provider, None, ctx.history_start, ctx.as_of, ctx.store, full=False
        )
        or {}
    )
    errors = list(result.get("errors") or [])
    written = int(result.get("bars_written") or 0)
    if errors and not written:
        raise RuntimeError(f"ingest wrote nothing; {len(errors)} chunk errors, first: {errors[0].get('error')}")
    data = {k: v for k, v in result.items() if k != "errors"}
    data["error_count"] = len(errors)
    detail = (
        f"{written:,} bars for {result.get('symbols_with_bars', '?')} of {result.get('symbols_requested', '?')} "
        f"symbols via {ctx.provider}" + (f"; {len(errors)} chunk errors" if errors else "")
    )
    return detail, data


def _store_symbols_table(store: Any) -> pd.DataFrame | None:
    has_table = getattr(store, "has_table", None)
    try:
        if callable(has_table) and not has_table(SYMBOLS_TABLE):
            return None
        symbols = store.read_table(SYMBOLS_TABLE)
    except Exception as e:  # optional reference table: without it the screen is liquidity-only
        log.info("symbols_table_unavailable", error=str(e))
        return None
    if symbols is None or len(symbols) == 0 or "symbol" not in symbols.columns:
        return None
    return symbols


def _liquidity_only_universe(ctx: _Context) -> list[str] | None:
    """`data.universe.liquidity_screen` over the store's lookback window (as-traded through the splits table)
    when there is no `symbols` reference table to drive `build_universe` (a bare bars import)."""
    screen = _try_load("data.universe.liquidity_screen")
    window_fn = _try_load("data.universe.lookback_window")
    if screen is None or window_fn is None:
        return None
    start, end = window_fn(ctx.as_of)
    window = ctx.store.read_bars(None, start, end)
    if window is None or len(window) == 0:
        return []
    has_table = getattr(ctx.store, "has_table", None)
    splits = ctx.store.read_table("splits") if callable(has_table) and has_table("splits") else None
    stats = screen(window, ctx.settings.universe, ctx.as_of, splits)
    passed = stats.loc[stats["passes"].astype(bool)].sort_values(["avg_dollar_volume", "symbol"], ascending=[False, True])
    return sorted(passed["symbol"].astype(str).head(ctx.settings.universe.max_symbols).tolist())


def _screen_universe(ctx: _Context) -> tuple[list[str] | None, str]:
    """Symbols passing the universe screen at `as_of` (static_symbols, else build_universe on the store's
    reference table and liquidity window with split un-adjustment, else a liquidity-only screen)."""
    build_universe = _try_load("data.universe.build_universe")
    if build_universe is None:
        return None, "data.universe unavailable"
    if ctx.settings.universe.static_symbols:
        return sorted({s.upper() for s in ctx.settings.universe.static_symbols}), "static_symbols"
    symbols = _store_symbols_table(ctx.store)
    if symbols is None:
        return _liquidity_only_universe(ctx), "liquidity screen (no symbols table)"
    universe = _call_supported(build_universe, _StoreListing(symbols), ctx.settings, ctx.as_of, store=ctx.store)
    return sorted(str(s) for s in universe), "build_universe"


def _held_symbols(ctx: _Context) -> tuple[set[str], list[str]]:
    """Symbols held or with open orders (broker positions and open orders, plus the ledger's pending rows):
    the positions step needs their panel rows even when they no longer pass the screen. Also returns the
    broker sources that failed: the caller must then not restrict the panel (a filled position is terminal in
    the ledger, so only the broker knows it is still held)."""
    held: set[str] = set()
    failed: list[str] = []
    if ctx.broker is not None:
        for fetch in ("positions", "open_orders"):
            try:
                for item in getattr(ctx.broker, fetch)() or []:
                    sym = item.get("symbol") if isinstance(item, dict) else getattr(item, "symbol", None)
                    if sym:
                        held.add(str(sym).upper())
            except Exception as e:  # noqa: BLE001 - the positions step reports broker trouble itself
                failed.append(fetch)
                log.warning("features_held_symbols_failed", source=fetch, error=_error_text(e))
    ledger_path = _resolve(ctx.settings.execution.ledger_file)
    ledger_cls = _try_load("execution.ledger.OrderLedger")
    if ledger_cls is not None and ledger_path.exists():
        ledger = None
        try:
            ledger = ledger_cls(ledger_path)
            held.update(str(r["symbol"]).upper() for r in ledger.pending() if r.get("symbol"))
        except Exception as e:  # noqa: BLE001
            log.warning("features_ledger_symbols_failed", error=_error_text(e))
        finally:
            if ledger is not None:
                ledger.close()
    return held, failed


def screened_breadth(
    panel: pd.DataFrame, universe: list[str] | None = None, splits: pd.DataFrame | None = None
) -> tuple[pd.DataFrame | None, str]:
    """`features.breadth.market_breadth` over the panel rows of `universe` (all rows when None), with the index
    ETFs left out of the population and the 4% days' share floor on as-traded volume when `splits` (the
    store's splits table) is given; `(None, reason)` when the breadth module is unavailable."""
    market_breadth, why = contract_fn("market_breadth")
    if market_breadth is None:
        return None, why
    screened = panel if universe is None else panel.loc[panel["symbol"].isin(universe)]
    extra = {"splits": splits} if splits is not None else {}
    return _call_supported(market_breadth, screened, exclude=INDEX_SYMBOLS, **extra), ""


def _store_splits(store: Any) -> pd.DataFrame | None:
    has_table = getattr(store, "has_table", None)
    try:
        if not callable(has_table) or not has_table("splits"):
            return None
        splits = store.read_table("splits")
    except Exception as e:  # optional input: without it the share floor reads adjusted volume
        log.info("splits_table_unavailable", error=str(e))
        return None
    return splits if splits is not None and len(splits) else None


def _write_breadth(ctx: _Context, panel: pd.DataFrame) -> tuple[pd.DataFrame | None, str]:
    """`features.breadth.market_breadth` over the screened panel, upserted into the `breadth` table. Sessions
    already stored keep their earlier value (each was computed on that night's universe), except the latest
    stored session, which is recomputed. The first run writes only its latest session: earlier sessions computed
    on today's screen would leave out every name delisted or illiquid since (survivor-only history)."""
    breadth, why = screened_breadth(panel, ctx.universe, _store_splits(ctx.store))
    if why:
        return None, why
    if breadth is None or len(breadth) == 0:
        return breadth, "market_breadth returned no rows"
    frame = breadth.rename_axis(BREADTH_KEY).reset_index()
    frame[BREADTH_KEY] = pd.to_datetime(frame[BREADTH_KEY]).dt.date
    has_table = getattr(ctx.store, "has_table", None)
    last = None
    if callable(has_table) and has_table(BREADTH_TABLE):
        stored = ctx.store.read_table(BREADTH_TABLE)
        if len(stored) and BREADTH_KEY in stored.columns:
            last = pd.to_datetime(stored[BREADTH_KEY]).dt.date.max()
    frame = frame.loc[frame[BREADTH_KEY] >= (last if last is not None else frame[BREADTH_KEY].max())]
    written = ctx.store.write_table(BREADTH_TABLE, frame, [BREADTH_KEY])
    return breadth, f"{written} breadth rows"


def _step_features(ctx: _Context) -> tuple[str, dict[str, Any]]:
    """Panel for the screened universe only (~12,000 grouped-daily tickers in the store, ~1,500 kept), plus the
    index ETFs and anything held or with an open order; full history for each kept symbol."""
    start = ctx.history_start - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS)
    universe, how = _screen_universe(ctx)
    ctx.universe = universe
    held, held_failed = _held_symbols(ctx)
    keep: list[str] | None = None
    if universe is not None and not held_failed:
        keep = sorted(set(universe) | set(INDEX_SYMBOLS) | held)
    elif universe is not None:  # holdings unknown: keep every symbol so a held name never loses its exit checks
        log.warning("features_unrestricted_panel", reason=f"broker {held_failed} failed")
    store_symbols = getattr(ctx.store, "symbols", None)
    in_store = len(store_symbols()) if callable(store_symbols) else None
    log.info("features_universe", how=how, store_symbols=in_store, screened=None if universe is None else len(universe),
             held=len(held), kept=None if keep is None else len(keep))
    bars = ctx.store.read_bars(keep, start, ctx.as_of)
    if bars is None or len(bars) == 0:
        raise RuntimeError(f"no bars in the store for {start}..{ctx.as_of}; ingest first")
    build_panel = _load("features.panel.build_panel")
    ensure_extra, required_extras = _load("features.extra.ensure_extra"), _load("features.extra.required_extras")
    market = _market_slice(bars)
    active = [registry.get("strategy", n)(_strategy_params(ctx.settings, n))  # instances: param-dependent extras
              for n in sorted({*_enabled_strategies(ctx.settings), *_shadow_only_strategies(ctx.settings)})
              if n in registry.names("strategy")]
    panel = ensure_extra(build_panel(bars, market), required_extras(active), market)  # enabled + shadow-only extras
    panel = _load("data.fundamentals.join_edgar")(ctx.store, panel)
    ctx.store.write_table(PANEL_TABLE, panel, PANEL_KEYS)
    ctx.panel = panel
    try:
        ctx.breadth, breadth_note = _write_breadth(ctx, panel)
    except Exception as e:  # breadth is an input to the router, not to the panel: keep the panel step ok
        ctx.breadth, breadth_note = None, f"breadth failed: {_error_text(e)}"
        log.error("breadth_failed", error=breadth_note)
    symbols = int(panel["symbol"].nunique()) if "symbol" in panel.columns else 0
    data = {
        "rows": int(len(panel)), "symbols": symbols, "columns": int(len(panel.columns)), "universe_how": how,
        "store_symbols": in_store, "screened": None if universe is None else len(universe), "held": sorted(held),
        "breadth": breadth_note, "held_fetch_failed": held_failed,
    }
    detail = f"{data['rows']:,} rows x {data['columns']} columns for {symbols} symbols"
    if universe is not None:
        detail += f" ({len(universe)} screened via {how}{f' of {in_store}' if in_store else ''}, {len(held)} held)"
    if held_failed and universe is not None:
        detail += f"; panel not restricted to the screen (broker {', '.join(held_failed)} failed)"
    return detail + f"; {breadth_note}", data


def _panel_for(ctx: _Context) -> pd.DataFrame:
    panel = ctx.panel
    if panel is None:
        panel = ctx.store.read_table(PANEL_TABLE)
    panel = _on_or_before(panel, ctx.as_of)
    if panel is None or len(panel) == 0:
        raise RuntimeError(f"no panel rows on or before {ctx.as_of}; run `swing features`")
    return panel


def _screened(ctx: _Context, panel: pd.DataFrame) -> tuple[pd.DataFrame, int | None]:
    """The panel restricted to the universe screened by the features step, else screened here from the store's
    `symbols` table (None when there is nothing to screen)."""
    universe = ctx.universe
    if universe is None:
        build_universe = _try_load("data.universe.build_universe")
        symbols = _store_symbols_table(ctx.store) if build_universe is not None else None
        if build_universe is None or symbols is None:
            return panel, None
        universe = list(
            _call_supported(build_universe, _StoreListing(symbols), ctx.settings, ctx.as_of, bars=panel, store=ctx.store)
        )
    kept = panel.loc[panel["symbol"].isin(universe)]
    if kept.empty:
        raise RuntimeError(f"no panel rows for the {len(universe)}-name universe as of {ctx.as_of}")
    return kept, len(universe)


def _breadth_for(ctx: _Context, panel: pd.DataFrame) -> pd.DataFrame | None:
    """This run's breadth (features step), else recomputed over the screened panel; None without the module."""
    if ctx.breadth is not None:
        return ctx.breadth
    return screened_breadth(panel, None, _store_splits(ctx.store))[0]


def compute_regime(
    settings: Settings, panel: pd.DataFrame, as_of: date, *, breadth: pd.DataFrame | None = None,
    enabled: list[str] | None = None,
) -> tuple[Any | None, dict[str, Any] | None, str]:
    """`(MarketState, payload, note)` for `as_of`. `payload` (saved as runs/regime/<date>.json) holds the state,
    `allowed` {strategy: multiplier} and `blocked` {strategy: reason}, or no `allowed` key when
    `select_strategies` is unavailable. `(None, None, reason)` when `market_state` is unavailable. Exceptions
    from the playbook propagate: a broken router must not fall back to running every strategy."""
    market_state, why = contract_fn("market_state")
    if market_state is None:
        return None, None, why
    state = _call_supported(market_state, panel, as_of, breadth=breadth, settings=settings)
    payload: dict[str, Any] = {"as_of": as_of.isoformat(), "regime": regime_name(state), "market_state": _jsonable(state)}
    select_strategies, why = contract_fn("select_strategies")
    if select_strategies is None:
        return state, payload, why
    allowed, blocked = route_strategies(settings, dict(select_strategies(state, settings) or {}), enabled)
    payload.update(allowed=allowed, blocked=blocked)
    return state, payload, ""


def _step_scan(ctx: _Context) -> tuple[str, dict[str, Any]]:
    # an empty list first: a scan that fails (broken or missing router, no panel) must not leave `swing autopilot`
    # sizing an older day's saved signals as the latest ones
    ctx.save(SIGNALS_KIND, [])
    names = _enabled_strategies(ctx.settings)
    if not names:
        raise Skip("no strategies enabled in settings and none registered")
    full = _panel_for(ctx)
    panel, universe_size = _screened(ctx, full)
    ctx.signal_day = _latest_session(panel, ctx.as_of)
    regime = _regime(panel, ctx.as_of)
    state, payload, router_note = compute_regime(
        ctx.settings, full, ctx.as_of, breadth=_breadth_for(ctx, panel), enabled=names
    )
    ctx.market_state = state
    if payload is not None:
        path = _save_json(ctx.file(REGIME_KIND), payload)
        ctx.report.files[REGIME_KIND] = str(path)
        ctx.report.regime = payload
    if payload is None or "allowed" not in payload:
        # fail closed: without the router every enabled strategy (including ones enabled only so the router can
        # see them) would run at full risk; playbook.enabled: false is the explicit opt-out
        raise RuntimeError(
            f"strategy routing unavailable ({router_note}); no strategies scanned "
            "(set playbook.enabled: false to run every enabled strategy at 1.0)"
        )
    ctx.risk_multipliers = dict(payload["allowed"])
    names = [n for n in names if n in ctx.risk_multipliers]
    signals, per_strategy, failures = _run_strategies(ctx, names, panel, regime)
    if failures and len(failures) == len(names):
        raise RuntimeError(f"every strategy failed: {failures}")
    signals.sort(key=lambda s: s.score, reverse=True)
    ctx.signals = signals
    ctx.save(SIGNALS_KIND, signals)  # saved even when empty: `swing autopilot` must not size an older day's list
    # shadow-only strategies: every regime (the ledger grades them by regime), kept out of ctx.signals so they are
    # never sized, reviewed or executed; a failure here never fails the scan
    shadow, shadow_counts, shadow_failures = _run_strategies(ctx, _shadow_only_strategies(ctx.settings), panel, regime)
    ctx.shadow_signals = shadow
    data = {
        "signals": len(signals), "per_strategy": per_strategy, "failures": failures, "universe": universe_size,
        "regime": regime, "market_regime": regime_name(state), "allowed": ctx.risk_multipliers,
        "blocked": (payload or {}).get("blocked"), "router": router_note or "ok",
        "shadow_only": shadow_counts, "shadow_only_failures": shadow_failures,
    }
    detail = f"{len(signals)} signals from {len(per_strategy)} strategies" + (f"; failed: {sorted(failures)}" if failures else "")
    if shadow_counts or shadow_failures:
        detail += f"; {len(shadow)} shadow-only signals from {len(shadow_counts)} strategies"
    routed = ", ".join(f"{n} x{m:g}" for n, m in ctx.risk_multipliers.items()) or "none"
    detail += f"; regime {regime_name(state)}: allowed {routed}"
    return detail, data


def _run_strategies(
    ctx: _Context, names: list[str], panel: pd.DataFrame, regime: dict[str, Any] | None
) -> tuple[list[Signal], dict[str, int], dict[str, str]]:
    signals: list[Signal] = []
    failures: dict[str, str] = {}
    per_strategy: dict[str, int] = {}
    for name in names:
        try:
            strategy = registry.get("strategy", name)(_strategy_params(ctx.settings, name))
            found = list(strategy.signals(panel, ctx.as_of, regime))
        except Exception as e:
            failures[name] = _error_text(e)
            log.error("strategy_failed", strategy=name, error=failures[name])
            continue
        per_strategy[name] = len(found)
        signals.extend(found)
    return signals, per_strategy, failures


def _step_rank(ctx: _Context) -> tuple[str, dict[str, Any]]:
    path = store_dir(ctx.settings) / RANKER_FILENAME
    if not path.exists():
        raise Skip(f"no ranker at {path}; run `swing rank train`")
    ranker = _load_ranker(path)
    rows = _latest_rows(_panel_for(ctx), ctx.as_of)
    scores = pd.Series(ranker.predict(rows))
    if len(scores) != len(rows):
        raise RuntimeError(f"ranker returned {len(scores)} scores for {len(rows)} rows")
    frame = pd.DataFrame({"symbol": rows["symbol"].astype(str).to_numpy(), "score": scores.to_numpy(dtype=float)})
    frame = frame.sort_values("score", ascending=False).reset_index(drop=True)
    path_out = _save_json(ctx.file(RANK_KIND), frame.to_dict(orient="records"))
    ctx.report.files[RANK_KIND] = str(path_out)
    by_symbol = dict(zip(frame["symbol"], frame["score"], strict=True))
    tagged = 0
    for s in ctx.signals:
        if s.symbol in by_symbol:
            s.features[RANK_FEATURE] = float(by_symbol[s.symbol])
            tagged += 1
    if ctx.signals:
        ctx.signals.sort(key=lambda s: s.score, reverse=True)
        ctx.save(SIGNALS_KIND, ctx.signals)
    top = frame.head(5)["symbol"].tolist()
    data = {"scored": int(len(frame)), "signals_tagged": tagged, "top": top, "model": type(ranker).__name__}
    return f"{len(frame)} symbols scored, {tagged} signals tagged; top {top}", data


def _step_size(ctx: _Context) -> tuple[str, dict[str, Any]]:
    if ctx.stale_signals:
        raise Skip(ctx.stale_signals)
    if not ctx.signals:
        raise Skip("no signals to size")
    equity = ctx.equity  # explicit --equity, else the broker's account, else risk.account_equity_override
    positions: list[Any] = []
    if ctx.broker is not None:
        if equity is None:
            equity = _account_equity(dict(ctx.broker.account()))
        positions = list(ctx.broker.positions())
    if equity is None:
        equity = ctx.settings.risk.account_equity_override
    if equity is None:
        raise Skip("equity unknown: pass --equity, set risk.account_equity_override, or inject a broker")
    size_detail = _try_load("risk.sizing.size_signal_detail")
    size_signal = None if size_detail is not None else _load("risk.sizing.size_signal")
    floor_for = _try_load("risk.sizing.strategy_min_reward_risk")
    size_eq = equity
    if ctx.settings.risk.drawdown_size_mult:  # Turtle drawdown rule: size on equity shrunk vs the persisted peak
        peak = _load("risk.limits.LimitState")(ctx.settings.risk, state_path=ctx.settings.risk.limits_state_file)
        size_eq = _load("risk.sizing.drawdown_scaled_equity")(equity, peak.peak_equity, ctx.settings.risk.drawdown_size_mult)
    intents: list[OrderIntent] = []
    skipped: dict[str, str] = {}
    multipliers = ctx.risk_multipliers  # None = unrouted: every strategy at full risk_per_trade_pct
    for s in ctx.signals:
        if multipliers is not None and s.strategy not in multipliers:
            skipped[f"{s.strategy}:{s.symbol}"] = "strategy not allowed by the playbook in this regime"
            continue
        risk_cfg = _scaled_risk(ctx.settings.risk, MULTIPLIER_MAX if multipliers is None else multipliers[s.strategy])
        if size_detail is not None:
            floor = floor_for(ctx.settings.strategies, s.strategy) if floor_for is not None else None
            extra = {"min_reward_risk": floor} if floor is not None else {}
            intent, reason = size_detail(s, size_eq, risk_cfg, positions, **extra)
        else:
            intent, reason = size_signal(s, size_eq, risk_cfg, positions), "rejected by risk.sizing"
        if intent is not None:
            intents.append(intent)
        else:
            skipped[f"{s.strategy}:{s.symbol}"] = str(reason)
    ctx.intents = intents
    ctx.save(INTENTS_KIND, intents)
    data = {"equity": float(equity), "sizing_equity": float(size_eq), "intents": len(intents), "skipped": skipped, "open_positions": len(positions),
            "risk_multipliers": multipliers}
    scaled = {n: m for n, m in (multipliers or {}).items() if m < MULTIPLIER_MAX}
    note = f"; risk scaled {scaled}" if scaled else ""
    return (f"{len(intents)} intents from {len(ctx.signals)} signals at equity {equity:,.0f}; "
            f"{len(skipped)} skipped by risk{note}"), data


def _save_review_status(ctx: _Context, status: str, detail: str) -> None:
    payload = {"status": status, "detail": detail, "at": datetime.now(UTC).isoformat(timespec="seconds")}
    path = _save_json(ctx.file(REVIEW_STATUS_KIND), payload)
    ctx.report.files[REVIEW_STATUS_KIND] = str(path)


def _step_review(ctx: _Context) -> tuple[str, dict[str, Any]]:
    """Persists its outcome (``running`` first, so a process that dies mid-review also fails closed) for
    `run_cycle`, which otherwise cannot tell a crashed review from one that never ran."""
    _save_review_status(ctx, REVIEW_RUNNING, "")
    try:
        detail, data = _review_body(ctx)
    except Skip as e:
        _save_review_status(ctx, REVIEW_SKIP, str(e))
        raise
    except Exception as e:
        _save_review_status(ctx, REVIEW_FAIL, _error_text(e))
        raise
    _save_review_status(ctx, REVIEW_OK, detail)
    return detail, data


def _review_body(ctx: _Context) -> tuple[str, dict[str, Any]]:
    if ctx.dry_run:
        raise Skip("dry run: no Claude calls")
    if not ctx.settings.agent.llm_enabled:
        raise Skip("agent.llm_enabled is false: no Claude calls")
    if not ctx.secrets.anthropic_api_key:
        raise Skip("ANTHROPIC_API_KEY not set")
    if not ctx.signals:
        raise Skip("no signals to review")
    review_candidates = _load("agent.review.review_candidates")
    cap = ctx.settings.agent.max_candidates_per_day
    candidates = ctx.signals[:cap]
    context = _load_json(ctx.file(CONTEXT_KIND), {})
    client = ctx.review_client
    if client is None:  # build from Secrets: the SDK alone only reads os.environ, not the .env that Secrets loads
        client = _load("agent.client.get_async_client")(ctx.secrets)
    reviews: list[Review] = list(_call_supported(review_candidates, candidates, context, ctx.settings, client=client))
    ctx.reviews = reviews
    ctx.save(REVIEWS_KIND, reviews)
    decisions: dict[str, int] = {}
    for r in reviews:
        decisions[r.decision.value] = decisions.get(r.decision.value, 0) + 1
    # post-review filter: keep only intents whose signal Claude approved (enum only; sizes are untouched)
    dropped = 0
    if ctx.intents:
        approved = {(r.symbol, r.strategy) for r in reviews if r.decision is ReviewDecision.APPROVE_FOR_RISK_CHECK}
        kept = [i for i in ctx.intents if (i.symbol, i.strategy) in approved]
        dropped = len(ctx.intents) - len(kept)
        ctx.intents = kept
        ctx.save(INTENTS_KIND, kept)
    data = {"reviewed": len(reviews), "decisions": decisions, "intents_dropped": dropped}
    return f"{len(reviews)} reviewed ({decisions}); {dropped} unapproved intents dropped", data


def _step_shadow(ctx: _Context) -> tuple[str, dict[str, Any]]:
    """Every signal of the day into research.shadow's ledger, then grade the signals whose horizons have matured
    on stored bars. Data only: no orders. `taken` holds `strategy:symbol` keys of the sized intents that survived
    review (research.shadow also accepts bare symbols; the key keeps two strategies on one name apart).

    Rows are keyed by the session of the bar the signals were computed from (`signal_day`), not the run date:
    the scheduled run fires at 06:30 ET with `as_of` = today while the store ends at the previous close, and
    grading starts at the first session strictly after the row's date, which must be the session the
    autopilot enters on (same convention as research.replay)."""
    record_signals, why = contract_fn("record_signals")
    grade_signals, why_grade = contract_fn("grade_signals")
    if record_signals is None or grade_signals is None:
        raise Skip(why or why_grade)
    taken = {f"{i.strategy}{TAKEN_KEY_SEP}{i.symbol}" for i in ctx.intents}
    regime = regime_name(ctx.market_state) if ctx.market_state is not None else None
    if regime is not None:  # fired playbook overlays split the shadow ledger like replay's labels
        regime = "+".join([regime, *(getattr(ctx.market_state, "overlays", None) or [])])
    day = ctx.signal_day or _latest_session(ctx.panel, ctx.as_of) or ctx.as_of
    signals = [s if s.as_of == day else s.model_copy(update={"as_of": day}) for s in [*ctx.signals, *ctx.shadow_signals]]
    recorded = int(record_signals(ctx.store, signals, taken, day, regime) or 0) if signals else 0
    graded = int(grade_signals(ctx.store, ctx.as_of) or 0)
    data = {"recorded": recorded, "taken": sorted(taken), "graded": graded, "regime": regime,
            "signal_day": day.isoformat()}
    return f"{recorded} signals recorded ({len(taken)} taken, regime {regime or 'unknown'}); {graded} graded", data


def _earnings_frame(ctx: _Context) -> pd.DataFrame | None:
    has_table = getattr(ctx.store, "has_table", None)
    try:
        if callable(has_table) and not has_table(EARNINGS_TABLE):
            return None
        return ctx.store.read_table(EARNINGS_TABLE)
    except Exception as e:  # optional input: no table means no earnings rule
        log.info("earnings_table_unavailable", error=str(e))
        return None


def _step_positions(ctx: _Context) -> tuple[str, dict[str, Any]]:
    if ctx.broker is None:
        raise Skip("no broker: pass --broker (or set execution.broker) to manage open positions")
    review_positions = _load("execution.position_manager.review_positions")
    _reconcile_ledger(ctx)
    earnings = _earnings_frame(ctx)
    actions = list(review_positions(ctx.settings, ctx.broker, _panel_for(ctx), ctx.as_of, None, earnings))
    ctx.exit_actions = actions
    ctx.save(EXITS_KIND, actions)
    by_kind: dict[str, int] = {}
    for a in actions:
        by_kind[str(a.kind)] = by_kind.get(str(a.kind), 0) + 1
    flagged = sorted({a.symbol for a in actions if str(a.kind) == "flag"})
    data = {"actions": len(actions), "by_kind": by_kind, "flagged": flagged, "earnings_rows": 0 if earnings is None else len(earnings)}
    return f"{len(actions)} exit actions {by_kind or ''}".rstrip() + (f"; flagged {flagged}" if flagged else ""), data


def _reconcile_ledger(ctx: _Context) -> None:
    """Refresh ledger statuses from the broker before exit decisions (a fill since the last run must be the
    ledger row the R ladder reads). Best effort: the autopilot reconciles again and fails closed itself."""
    order_manager = _try_load("execution.order_manager.OrderManager")
    ledger_cls = _try_load("execution.ledger.OrderLedger")
    if order_manager is None or ledger_cls is None:
        return
    ledger = None
    try:
        ledger = ledger_cls(ctx.settings.execution.ledger_file)
        order_manager(ctx.broker, None, ctx.settings.risk.kill_switch_file, ledger=ledger).reconcile()
    except Exception as e:  # noqa: BLE001
        log.warning("positions_reconcile_failed", error=_error_text(e))
    finally:
        if ledger is not None:
            ledger.close()


def _veto_filtered(ctx: _Context, intents: list[OrderIntent]) -> list[OrderIntent]:
    if not ctx.reviews or not ctx.settings.execution.require_review_approval:
        return intents
    vetoed = {(r.symbol, r.strategy) for r in ctx.reviews
              if r.decision in (ReviewDecision.REJECT, ReviewDecision.NEEDS_MORE_INFO)}
    return [i for i in intents if (i.symbol, i.strategy) not in vetoed]


def _step_execute(ctx: _Context) -> tuple[str, dict[str, Any]]:
    if ctx.dry_run and not ctx.plan_on_dry_run:
        raise Skip("dry run: no orders")
    if not ctx.execute:
        raise Skip("execution disabled (settings.execution.nightly_execute / --no-execute)")
    if ctx.broker is None:
        raise Skip("no broker: pass --broker (or set execution.broker) to execute")
    run_autopilot = _load("execution.autopilot.run_autopilot")
    intents = ctx.intents
    unreviewed = 0
    if intents and ctx.reviews and ctx.settings.execution.require_review_approval:
        # with reviews present, only reviewed intents go on (the nightly's review step already did this; saved
        # signals in `swing autopilot` can hold more intents than agent.max_candidates_per_day reviewed)
        reviewed = {(r.symbol, r.strategy) for r in ctx.reviews}
        kept = [i for i in intents if (i.symbol, i.strategy) in reviewed]
        unreviewed, intents = len(intents) - len(kept), kept
        if unreviewed:
            log.warning("execute_entries_held", reason="no review for the signal", intents=unreviewed)
    if ctx.intents and not ctx.dry_run:
        # the intents file holds what a human may send (reviewed, not vetoed), never the raw sized set; the
        # automation holds below do not empty it (a person can still look and approve with `swing paper`)
        ctx.save(INTENTS_KIND, _veto_filtered(ctx, intents))
    held = 0
    review_step = ctx.report.step("review")
    if (
        intents
        and review_step is not None
        and review_step.status == StepStatus.FAIL
        and ctx.settings.execution.require_review_approval
    ):  # fail closed: a crashed review must not let unreviewed entries through; exits still run
        held, intents = len(intents), []
        log.warning("execute_entries_held", reason="review step failed", intents=held)
    if intents and ctx.review_hold and ctx.settings.execution.require_review_approval:
        held, intents = len(intents), []  # run_cycle: the saved review of the signals' day failed or never finished
        log.warning("execute_entries_held", reason=ctx.review_hold, intents=held)
    held_positions = 0
    positions_step = ctx.report.step("positions")
    if intents and positions_step is not None and positions_step.status == StepStatus.FAIL:
        held_positions, intents = len(intents), []  # no exit decisions were made: add no new risk either
        log.warning("execute_entries_held", reason="positions step failed", intents=held_positions)
    report = run_autopilot(
        ctx.settings, ctx.secrets, ctx.as_of, ctx.broker, intents, ctx.reviews or None, ctx.exit_actions,
        dry_run=ctx.dry_run,
    )
    if report.audit_path:
        ctx.report.files["autopilot"] = str(report.audit_path)
    if report.staged_path:
        ctx.report.files["pending"] = str(report.staged_path)
    summary = report.summary()
    if summary["mode"] == ABORTED_MODE:
        raise RuntimeError("; ".join(report.errors) or "autopilot aborted")
    data = {**summary, "submitted": report.submitted, "approved_by": report.approved_by, "errors": report.errors,
            "entries_held_review_failed": held, "entries_held_unreviewed": unreviewed,
            "entries_held_positions_failed": held_positions}
    held_note = f"; {held} entries held ({ctx.review_hold or 'review step failed'})" if held else ""
    held_note += f"; {unreviewed} unreviewed entries held" if unreviewed else ""
    held_note += f"; {held_positions} entries held (positions step failed)" if held_positions else ""
    return f"{summary['mode']}: entries {summary['entries'] or '{}'}; exits {summary['exits'] or '{}'}{held_note}", data


def _step_journal(ctx: _Context) -> tuple[str, dict[str, Any]]:
    write_entry = _load("agent.journal.write_entry")
    fills = _load_json(ctx.file(FILLS_KIND), [])
    narrative = bool(ctx.secrets.anthropic_api_key) and not ctx.dry_run and ctx.settings.agent.llm_enabled
    client = ctx.journal_client
    if client is None and narrative:  # same .env-key reason as the review step
        client = _load("agent.client.get_client")(ctx.secrets)
    extra: dict[str, Any] = {"settings": ctx.settings, "narrative": narrative, "client": client}
    if ctx.journal_root is not None:
        extra["root"] = ctx.journal_root
    if ctx.report.regime is not None:
        extra["market_state"] = ctx.report.regime  # passed through if agent.journal ever takes it
    text = str(_call_supported(write_entry, ctx.as_of, ctx.signals, ctx.reviews, ctx.intents, fills, **extra) or "")
    journal_path = _try_load("agent.journal.journal_path")
    path = str(journal_path(ctx.as_of, ctx.journal_root)) if journal_path is not None else None
    regime_section = False
    if path and ctx.report.regime is not None and not _accepts(write_entry, "market_state"):
        section = regime_markdown(ctx.report.regime)
        with Path(path).open("a", encoding="utf-8") as fh:
            fh.write(section)
        text += section
        regime_section = True
    if path:
        ctx.report.files["journal"] = path
    data = {"narrative": narrative, "chars": len(text), "path": path, "regime_section": regime_section}
    return f"entry written ({'prose' if narrative else 'tables only'}){f' to {path}' if path else ''}", data


def _step_weekly(ctx: _Context) -> tuple[str, dict[str, Any]]:
    """agent.weekly's one-page report, only on the last session of the ISO week (no LLM call)."""
    if not _load("agent.weekly.is_last_session_of_week")(ctx.as_of):
        raise Skip("not the last session of the week")
    path = str(_load("agent.weekly.write_report")(ctx.settings, ctx.as_of, ctx.store, ctx.journal_root))
    ctx.report.files["weekly"] = path
    return f"weekly report written to {path}", {"path": path}


def _accepts(fn: Any, name: str) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return name in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def regime_markdown(payload: dict[str, Any]) -> str:
    """Journal section for a runs/regime/<date>.json payload (codes and enums only, no LLM text)."""
    state = payload.get("market_state") or {}
    lines = ["", "## Market regime", ""]
    lines.append(f"- regime: **{payload.get('regime') or state.get('regime') or 'unknown'}**")
    for key in ("spy_trend", "vol_regime", "breadth"):
        if key in state:
            lines.append(f"- {key}: {state[key]}")
    allowed = payload.get("allowed")
    if allowed is not None:
        routed = ", ".join(f"{name} x{float(mult):g}" for name, mult in allowed.items()) or "none (no new entries)"
        lines.append(f"- allowed strategies (risk multiplier): {routed}")
    blocked = payload.get("blocked") or {}
    if blocked:
        lines.append(f"- blocked: {', '.join(sorted(blocked))}")
    for note in state.get("notes") or []:
        lines.append(f"- note: {note}")
    return "\n".join(lines) + "\n"


SAMPLE_PROVIDER = "sample"  # data.providers sample: deterministic offline bars for tests and smoke runs
FLOAT_REFRESH_MIN_AGE_DAYS = 7  # a float row refreshed this recently is left alone
FLOAT_REFRESH_MAX_PER_NIGHT = 25  # each symbol also costs a Massive free-tier call (5/min): ~5 minutes; the rest roll to later nights
FLOAT_CANDIDATE_MIN_DOLLAR_VOL = 1_000_000.0  # 20-day average dollar volume; illiquid shells are not candidates
FLOAT_CANDIDATE_LOOKBACK_DAYS = 30


def _step_float(ctx: _Context) -> tuple[str, dict[str, Any]]:
    """Refresh float/shares data from SEC filings for the small-cap track's candidates (docs/smallcap-spec.md):
    last close inside [min_price, max_price] with real liquidity, missing or older than
    FLOAT_REFRESH_MIN_AGE_DAYS, at most FLOAT_REFRESH_MAX_PER_NIGHT per run. Without it every live snapshot has
    an unknown float and the runner track can only warn."""
    sc = dict(getattr(ctx.settings.monitor, "smallcap", {}) or {})
    if not sc.get("enabled", True):
        raise Skip("small-cap track disabled")
    if ctx.dry_run:
        raise Skip("dry run")
    if ctx.provider == SAMPLE_PROVIDER:  # synthetic offline bars: SEC / vendor float lookups would be network calls
        raise Skip("sample provider: synthetic symbols, no SEC float lookups")
    lo, hi = float(sc.get("min_price", 1.0)), float(sc.get("max_price", 20.0))
    bars = ctx.store.read_bars(None, ctx.as_of - timedelta(days=FLOAT_CANDIDATE_LOOKBACK_DAYS), ctx.as_of)
    if bars is None or len(bars) == 0:
        raise Skip("no recent bars")
    bars = bars.sort_values("ts")
    last = bars.groupby("symbol").tail(1).set_index("symbol")["close"]
    dvol = (bars["close"] * bars["volume"]).groupby(bars["symbol"]).mean()
    cands = sorted(s for s in last.index if lo <= float(last[s]) <= hi and float(dvol.get(s, 0.0)) >= FLOAT_CANDIDATE_MIN_DOLLAR_VOL)
    fresh: set[str] = set()
    if ctx.store.has_table("float"):
        tbl = ctx.store.read_table("float")
        if "refreshed_on" in tbl.columns and len(tbl):
            ref = pd.to_datetime(tbl["refreshed_on"], errors="coerce").dt.date
            recent = tbl[ref >= ctx.as_of - timedelta(days=FLOAT_REFRESH_MIN_AGE_DAYS)]
            fresh = set(recent["symbol"].astype(str).str.upper())
    todo = [s for s in cands if s.upper() not in fresh][:FLOAT_REFRESH_MAX_PER_NIGHT]
    if not todo:
        return f"{len(cands)} candidates, all refreshed within {FLOAT_REFRESH_MIN_AGE_DAYS} days", {"candidates": len(cands), "refreshed": 0}
    FloatSource = _load("data.float_data.FloatSource")
    src = FloatSource.from_settings(ctx.settings, ctx.secrets)
    result = dict(src.refresh(todo, ctx.store, as_of=ctx.as_of) or {})
    data = {"candidates": len(cands), "attempted": len(todo), "written": int(result.get("written", 0)),
            "unknown": len(result.get("unknown") or []), "errors": len(result.get("errors") or {})}
    left = max(0, len(cands) - len(fresh & set(cands)) - len(todo))
    return (f"{data['written']} floats refreshed of {len(todo)} attempted ({data['unknown']} unknown, "
            f"{data['errors']} errors); {left} candidates left for later nights"), data


STEPS: tuple[tuple[str, Callable[[_Context], tuple[str, dict[str, Any]]]], ...] = (
    ("ingest", _step_ingest),
    ("float", _step_float),
    ("features", _step_features),
    ("scan", _step_scan),
    ("rank", _step_rank),
    ("size", _step_size),
    ("review", _step_review),
    ("shadow", _step_shadow),
    ("positions", _step_positions),
    ("execute", _step_execute),
    ("journal", _step_journal),
    ("weekly", _step_weekly),
)


# ----------------------------------------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------------------------------------
def _open_store(settings: Settings, store: Any | None) -> tuple[Any, bool]:
    if store is not None:
        return store, False
    store_cls = _load("data.store.Store")
    return store_cls(str(_resolve(settings.data.store_path))), True


def _run_steps(
    ctx: _Context,
    steps: tuple[tuple[str, Callable[[_Context], tuple[str, dict[str, Any]]]], ...],
    kind: str,
    own_store: bool,
) -> NightlyReport:
    report = ctx.report
    t0 = time.perf_counter()
    try:
        for name, fn in steps:
            _run_step(ctx, name, fn)
    finally:
        if own_store and hasattr(ctx.store, "close"):
            ctx.store.close()
    report.finished_at = datetime.now(UTC)
    report.elapsed_s = round(time.perf_counter() - t0, 3)
    report_path = run_file(ctx.settings, kind, ctx.as_of)
    report.report_path = str(report_path)
    _save_json(report_path, report.model_dump(mode="json"))
    log.info(f"{kind}_done", ok=report.ok, failed=report.failed, elapsed_s=report.elapsed_s, report=str(report_path))
    return report


def run_nightly(
    settings: Settings,
    secrets: Secrets,
    as_of: date | None = None,
    provider: str | None = None,
    equity: float | None = None,
    dry_run: bool = False,
    *,
    store: Any | None = None,
    broker: Any | None = None,
    execute: bool | None = None,
    review_client: Any | None = None,
    journal_client: Any | None = None,
    journal_root: Path | None = None,
) -> NightlyReport:
    """Run the nightly pipeline for `as_of` (default today) and write the JSON report.

    `dry_run` skips the Claude calls (review, journal prose) and never executes; data steps still run so the
    store stays fresh. `broker` supplies equity and positions and is where `execute` sends orders (through
    execution.autopilot only); `execute=None` means `settings.execution.nightly_execute`. Other keyword
    arguments inject a store, Anthropic clients and the journal root for tests and embedding.
    """
    as_of_d = as_of or date.today()
    provider_name = provider or settings.data.bar_provider
    report = NightlyReport(as_of=as_of_d, provider=provider_name, dry_run=dry_run, started_at=datetime.now(UTC))
    store, own_store = _open_store(settings, store)
    ctx = _Context(
        settings=settings,
        secrets=secrets,
        as_of=as_of_d,
        provider=provider_name,
        equity=equity,
        dry_run=dry_run,
        store=store,
        broker=broker,
        review_client=review_client,
        journal_client=journal_client,
        journal_root=journal_root,
        report=report,
        execute=settings.execution.nightly_execute if execute is None else bool(execute),
    )
    log.info("nightly_start", as_of=str(as_of_d), provider=provider_name, dry_run=dry_run, execute=ctx.execute,
             broker=getattr(broker, "name", None))
    return _run_steps(ctx, STEPS, NIGHTLY_KIND, own_store)


def _saved_review_hold(settings: Settings, signals_day: date) -> str | None:
    """Why `run_cycle` must hold entries for `signals_day`'s signals: the review step recorded a failure, or
    started and never finished. Falls back to that day's nightly report for runs saved before the marker
    existed. A review that was skipped on purpose (no key, dry run) or never attempted (`swing scan`) does not
    hold; `require_review_approval` then works as before (enforced on the reviews that exist)."""
    status = _load_json(run_file(settings, REVIEW_STATUS_KIND, signals_day), {})
    state = status.get("status") if isinstance(status, dict) else None
    if state == REVIEW_FAIL:
        return f"the review of {signals_day} failed: {status.get('detail') or 'see the nightly report'}"
    if state == REVIEW_RUNNING:
        return f"the review of {signals_day} started and never finished"
    if state is None:
        nightly_report = _load_json(run_file(settings, NIGHTLY_KIND, signals_day), {})
        steps = nightly_report.get("steps") if isinstance(nightly_report, dict) else None
        step = next((s for s in steps or [] if isinstance(s, dict) and s.get("name") == "review"), None)
        if step is not None and step.get("status") == StepStatus.FAIL.value:
            return f"the review of {signals_day} failed: {step.get('detail') or 'see the nightly report'}"
    return None


def latest_signals_date(settings: Settings, as_of: date) -> date | None:
    """Most recent `runs/signals/<date>.json` on or before `as_of`."""
    folder = store_dir(settings) / RUNS_DIRNAME / SIGNALS_KIND
    days: list[date] = []
    for path in folder.glob("*.json"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if day <= as_of:
            days.append(day)
    return max(days) if days else None


CYCLE_STEPS: tuple[tuple[str, Callable[[_Context], tuple[str, dict[str, Any]]]], ...] = tuple(
    (name, fn) for name, fn in STEPS if name in CYCLE_STEP_NAMES
)


def run_cycle(
    settings: Settings,
    secrets: Secrets,
    as_of: date | None = None,
    broker: Any | None = None,
    dry_run: bool = False,
    *,
    equity: float | None = None,
    store: Any | None = None,
) -> NightlyReport:
    """`swing autopilot`: size -> positions -> execute from the latest saved signals (and their reviews).

    The playbook multipliers saved with those signals (`runs/regime/<signals day>.json`) scale risk the same
    way the nightly did; a strategy absent from the saved `allowed` table is not sized, and without a saved
    `allowed` table nothing is sized (fail closed: positions and exits still run).

    Signals older than `execution.max_signal_age_days` are not sized, but positions and exits still run.
    `dry_run` plans through the autopilot (nothing reaches the broker). Report: `runs/cycle/<date>.json`.
    """
    as_of_d = as_of or date.today()
    report = NightlyReport(as_of=as_of_d, provider=settings.data.bar_provider, dry_run=dry_run,
                           started_at=datetime.now(UTC))
    signals: list[Signal] = []
    reviews: list[Review] = []
    stale: str | None = None
    signals_day = latest_signals_date(settings, as_of_d)
    max_age = settings.execution.max_signal_age_days
    if signals_day is None:
        stale = f"no saved signals on or before {as_of_d}; run `swing scan` or `swing nightly` first"
    elif (as_of_d - signals_day).days > max_age:
        stale = f"latest saved signals are from {signals_day}, older than execution.max_signal_age_days={max_age}"
    else:
        signals_path = run_file(settings, SIGNALS_KIND, signals_day)
        signals = _load_models(signals_path, Signal)
        reviews = _load_models(run_file(settings, REVIEWS_KIND, signals_day), Review)
        report.files["signals_used"] = str(signals_path)
    review_hold = _saved_review_hold(settings, signals_day) if signals and signals_day is not None else None
    multipliers: dict[str, float] | None = None
    if signals and signals_day is not None:  # re-apply the playbook routing the nightly saved for that day
        regime_path = run_file(settings, REGIME_KIND, signals_day)
        saved = _load_json(regime_path, {})
        if isinstance(saved, dict) and isinstance(saved.get("allowed"), dict):
            multipliers = {str(k): float(v) for k, v in saved["allowed"].items()}
            report.regime = saved
            report.files["regime_used"] = str(regime_path)
        else:  # fail closed: unrouted signals would all be sized at full risk, whatever the regime allows
            stale = (
                f"no saved playbook routing for the {signals_day} signals ({regime_path} is missing or has no "
                "'allowed' table); run `swing nightly` or `swing scan` for that day"
            )
    store, own_store = _open_store(settings, store)
    ctx = _Context(
        settings=settings,
        secrets=secrets,
        as_of=as_of_d,
        provider=settings.data.bar_provider,
        equity=equity,
        dry_run=dry_run,
        store=store,
        broker=broker,
        review_client=None,
        journal_client=None,
        journal_root=None,
        report=report,
        signals=signals,
        reviews=reviews,
        execute=True,
        plan_on_dry_run=True,
        stale_signals=stale,
        review_hold=review_hold,
        risk_multipliers=multipliers,
    )
    log.info("cycle_start", as_of=str(as_of_d), signals_day=str(signals_day), signals=len(signals), dry_run=dry_run,
             broker=getattr(broker, "name", None))
    return _run_steps(ctx, CYCLE_STEPS, CYCLE_KIND, own_store)
