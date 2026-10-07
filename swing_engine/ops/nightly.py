"""`swing nightly`: the unattended evening pipeline, one step per CLI command, each timed and isolated.

ingest (incremental) -> features -> scan -> rank predict (when a model exists) -> size (when equity is known)
-> review (ANTHROPIC key, not dry-run) -> journal. A failing step is recorded and the pipeline carries on with
whatever the earlier steps produced (a broken ingest still scans yesterday's store; a broken scan leaves
nothing to size). The run ends with a JSON report under `<store dir>/runs/nightly/YYYY-MM-DD.json`.

Hand-offs use the same `<store dir>/runs/<kind>/<date>.json` files as the CLI, so `swing size`, `swing paper`
and `swing journal` can pick up where the nightly left off. Nothing here submits an order: the only broker
access is reading equity and open positions when a broker object is injected. The review step only filters
already-sized intents by `Review.decision` (an enum); every price, stop and share count comes from
`strategies/` and `risk/`.
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
PANEL_TABLE = "panel"
PANEL_KEYS = ["symbol", "ts"]
SYMBOLS_TABLE = "symbols"
RANKER_FILENAME = "ranker.pkl"
MARKET_SYMBOL = "SPY"
RANK_FEATURE = "rank_score"  # Signal.features key the rank step fills (model output, never LLM output)

# ---- windows -----------------------------------------------------------------------------------------------
DAYS_PER_YEAR = 365
PANEL_WARMUP_CALENDAR_DAYS = 400  # covers sma_200 / mom_12_1 before the first scored session
REGIME_COLUMNS = ("market_trend_state", "market_vol_regime")
ERROR_PREVIEW_CHARS = 200

STEP_NAMES = ("ingest", "features", "scan", "rank", "size", "review", "journal")


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
    names = [n for n, cfg in settings.strategies.items() if (cfg or {}).get("enabled", True)]
    return names or registry.names("strategy")


def _strategy_params(settings: Settings, name: str) -> dict[str, Any]:
    cfg = settings.strategies.get(name) or {}
    if isinstance(cfg.get("params"), dict):
        return dict(cfg["params"])
    return {k: v for k, v in cfg.items() if k != "enabled"}


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


def _step_features(ctx: _Context) -> tuple[str, dict[str, Any]]:
    start = ctx.history_start - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS)
    bars = ctx.store.read_bars(None, start, ctx.as_of)
    if bars is None or len(bars) == 0:
        raise RuntimeError(f"no bars in the store for {start}..{ctx.as_of}; ingest first")
    build_panel = _load("features.panel.build_panel")
    panel = build_panel(bars, _market_slice(bars))
    ctx.store.write_table(PANEL_TABLE, panel, PANEL_KEYS)
    ctx.panel = panel
    symbols = int(panel["symbol"].nunique()) if "symbol" in panel.columns else 0
    data = {"rows": int(len(panel)), "symbols": symbols, "columns": int(len(panel.columns))}
    return f"{data['rows']:,} rows x {data['columns']} columns for {symbols} symbols", data


def _panel_for(ctx: _Context) -> pd.DataFrame:
    panel = ctx.panel
    if panel is None:
        panel = ctx.store.read_table(PANEL_TABLE)
    panel = _on_or_before(panel, ctx.as_of)
    if panel is None or len(panel) == 0:
        raise RuntimeError(f"no panel rows on or before {ctx.as_of}; run `swing features`")
    return panel


def _screened(ctx: _Context, panel: pd.DataFrame) -> tuple[pd.DataFrame, int | None]:
    """Point-in-time universe screen from the store's `symbols` table (None when there is nothing to screen)."""
    build_universe = _try_load("data.universe.build_universe")
    if build_universe is None:
        return panel, None
    try:
        symbols = ctx.store.read_table(SYMBOLS_TABLE)
    except Exception as e:
        log.info("symbols_table_unavailable", error=str(e))
        return panel, None
    if symbols is None or len(symbols) == 0 or "symbol" not in symbols.columns:
        return panel, None
    universe = list(_call_supported(build_universe, _StoreListing(symbols), ctx.settings, ctx.as_of, bars=panel))
    kept = panel.loc[panel["symbol"].isin(universe)]
    if kept.empty:
        raise RuntimeError(f"no panel rows for the {len(universe)}-name universe as of {ctx.as_of}")
    return kept, len(universe)


def _step_scan(ctx: _Context) -> tuple[str, dict[str, Any]]:
    names = _enabled_strategies(ctx.settings)
    if not names:
        raise Skip("no strategies enabled in settings and none registered")
    panel, universe_size = _screened(ctx, _panel_for(ctx))
    regime = _regime(panel, ctx.as_of)
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
    if failures and len(failures) == len(names):
        raise RuntimeError(f"every strategy failed: {failures}")
    signals.sort(key=lambda s: s.score, reverse=True)
    ctx.signals = signals
    ctx.save(SIGNALS_KIND, signals)
    data = {"signals": len(signals), "per_strategy": per_strategy, "failures": failures, "universe": universe_size, "regime": regime}
    detail = f"{len(signals)} signals from {len(per_strategy)} strategies" + (f"; failed: {sorted(failures)}" if failures else "")
    return detail, data


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
    if not ctx.signals:
        raise Skip("no signals to size")
    equity = ctx.equity if ctx.equity is not None else ctx.settings.risk.account_equity_override
    positions: list[Any] = []
    if ctx.broker is not None:
        if equity is None:
            equity = _account_equity(dict(ctx.broker.account()))
        positions = list(ctx.broker.positions())
    if equity is None:
        raise Skip("equity unknown: pass --equity, set risk.account_equity_override, or inject a broker")
    size_detail = _try_load("risk.sizing.size_signal_detail")
    size_signal = None if size_detail is not None else _load("risk.sizing.size_signal")
    floor_for = _try_load("risk.sizing.strategy_min_reward_risk")
    intents: list[OrderIntent] = []
    skipped: dict[str, str] = {}
    for s in ctx.signals:
        if size_detail is not None:
            floor = floor_for(ctx.settings.strategies, s.strategy) if floor_for is not None else None
            extra = {"min_reward_risk": floor} if floor is not None else {}
            intent, reason = size_detail(s, equity, ctx.settings.risk, positions, **extra)
        else:
            intent, reason = size_signal(s, equity, ctx.settings.risk, positions), "rejected by risk.sizing"
        if intent is not None:
            intents.append(intent)
        else:
            skipped[f"{s.strategy}:{s.symbol}"] = str(reason)
    ctx.intents = intents
    ctx.save(INTENTS_KIND, intents)
    data = {"equity": float(equity), "intents": len(intents), "skipped": skipped, "open_positions": len(positions)}
    return f"{len(intents)} intents from {len(ctx.signals)} signals at equity {equity:,.0f}; {len(skipped)} skipped by risk", data


def _step_review(ctx: _Context) -> tuple[str, dict[str, Any]]:
    if ctx.dry_run:
        raise Skip("dry run: no Claude calls")
    if not ctx.secrets.anthropic_api_key:
        raise Skip("ANTHROPIC_API_KEY not set")
    if not ctx.signals:
        raise Skip("no signals to review")
    review_candidates = _load("agent.review.review_candidates")
    cap = ctx.settings.agent.max_candidates_per_day
    candidates = ctx.signals[:cap]
    context = _load_json(ctx.file(CONTEXT_KIND), {})
    reviews: list[Review] = list(_call_supported(review_candidates, candidates, context, ctx.settings, client=ctx.review_client))
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


def _step_journal(ctx: _Context) -> tuple[str, dict[str, Any]]:
    write_entry = _load("agent.journal.write_entry")
    fills = _load_json(ctx.file(FILLS_KIND), [])
    narrative = bool(ctx.secrets.anthropic_api_key) and not ctx.dry_run
    extra: dict[str, Any] = {"settings": ctx.settings, "narrative": narrative, "client": ctx.journal_client}
    if ctx.journal_root is not None:
        extra["root"] = ctx.journal_root
    text = _call_supported(write_entry, ctx.as_of, ctx.signals, ctx.reviews, ctx.intents, fills, **extra)
    journal_path = _try_load("agent.journal.journal_path")
    path = str(journal_path(ctx.as_of, ctx.journal_root)) if journal_path is not None else None
    if path:
        ctx.report.files["journal"] = path
    data = {"narrative": narrative, "chars": len(str(text or "")), "path": path}
    return f"entry written ({'prose' if narrative else 'tables only'}){f' to {path}' if path else ''}", data


STEPS: tuple[tuple[str, Callable[[_Context], tuple[str, dict[str, Any]]]], ...] = (
    ("ingest", _step_ingest),
    ("features", _step_features),
    ("scan", _step_scan),
    ("rank", _step_rank),
    ("size", _step_size),
    ("review", _step_review),
    ("journal", _step_journal),
)


# ----------------------------------------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------------------------------------
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
    review_client: Any | None = None,
    journal_client: Any | None = None,
    journal_root: Path | None = None,
) -> NightlyReport:
    """Run the nightly pipeline for `as_of` (default today) and write the JSON report. Never submits orders.

    `dry_run` skips the Claude calls (review, journal prose); data steps still run so the store stays fresh.
    Keyword arguments inject a store, a read-only broker (equity/positions), Anthropic clients and the
    journal root for tests and embedding.
    """
    as_of_d = as_of or date.today()
    provider_name = provider or settings.data.bar_provider
    started = datetime.now(UTC)
    report = NightlyReport(as_of=as_of_d, provider=provider_name, dry_run=dry_run, started_at=started)
    own_store = store is None
    if own_store:
        store_cls = _load("data.store.Store")
        store = store_cls(str(_resolve(settings.data.store_path)))
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
    )
    log.info("nightly_start", as_of=str(as_of_d), provider=provider_name, dry_run=dry_run)
    t0 = time.perf_counter()
    try:
        for name, fn in STEPS:
            _run_step(ctx, name, fn)
    finally:
        if own_store and hasattr(store, "close"):
            store.close()
    report.finished_at = datetime.now(UTC)
    report.elapsed_s = round(time.perf_counter() - t0, 3)
    report_path = run_file(settings, NIGHTLY_KIND, as_of_d)
    report.report_path = str(report_path)
    _save_json(report_path, report.model_dump(mode="json"))
    log.info("nightly_done", ok=report.ok, failed=report.failed, elapsed_s=report.elapsed_s, report=str(report_path))
    return report
