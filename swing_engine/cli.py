"""`swing` command-line interface.

Every command is a thin shell over the module APIs in docs/api-contract.md. Other modules are imported
lazily inside the command that needs them, so a missing or broken module produces a clear error for that
command instead of breaking the whole CLI.

Hard rule kept here: nothing in this file lets a number produced by the LLM layer reach an order.
`size` reads only `Review.decision` (an enum) to filter candidates; prices, stops and share counts come
from `strategies/` (Signal) and `risk/` (OrderIntent). `paper` refuses to submit without `--approve NAME`.

Scan -> review -> size -> paper hand-offs are JSON files under `<store dir>/runs/<kind>/<date>.json`
(gitignored with the rest of `data/`).
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
import pickle
import sys
from bisect import bisect_right
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, NoReturn

import pandas as pd
import structlog
import typer
from pydantic import BaseModel
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from swing_engine import __version__
from swing_engine.core import registry
from swing_engine.core.config import ROOT, Secrets, Settings, load_secrets, load_settings
from swing_engine.core.models import OrderIntent, Review, ReviewDecision, Signal

# ----------------------------------------------------------------------------------------------------------
# Constants (no magic numbers in command bodies)
# ----------------------------------------------------------------------------------------------------------
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_MISSING_MODULE = 3
EXIT_REFUSED = 4
EXIT_NO_DATA = 5

TRIALS_PATH = "data/trials.jsonl"  # default of research.trials.log_trial (docs/api-contract.md)
PANEL_TABLE = "panel"  # store table that `swing features` caches to and `scan`/`backtest` read from
PANEL_KEYS = ["symbol", "ts"]
SYMBOLS_TABLE = "symbols"  # reference table `swing ingest` writes; drives the point-in-time universe
MARKET_SYMBOL = "SPY"
RUNS_DIRNAME = "runs"  # <store dir>/runs/{signals,reviews,intents,fills,context}/<date>.json
RANKER_FILENAME = "ranker.pkl"
REVIEW_SYSTEM_PROMPT = "agent/prompts/review_system.md"  # relative to the swing_engine package
LIVE_OVERRIDE_ENV = "SWING_ALLOW_LIVE"
LIVE_OVERRIDE_VALUE = "yes"
INGEST_MODE_AUTO = "auto"  # values data.ingest.run_ingest(mode=) accepts: auto | symbols | grouped
INGEST_MODE_ALIASES = {"auto": "auto", "grouped": "grouped", "per-symbol": "symbols", "symbols": "symbols"}
INGEST_MODE_CHOICES = ("auto", "grouped", "per-symbol")

DAYS_PER_YEAR = 365
PANEL_WARMUP_CALENDAR_DAYS = 400  # covers sma_200 / mom_12_1 (252 trading days) before `start`
DEFAULT_RANK_HORIZON = 10
DEFAULT_TOP_N = 25
DEFAULT_MONITOR_REPORT_DAYS = 7
RATE_REASON_UNKNOWN_EVENT = "unknown_event"  # monitor.rate.RatingResult.reason when the event id is not logged
DEFAULT_TRIALS_SHOWN = 20
DEFAULT_PAPER_BROKER = "alpaca"
MIN_APPROVER_LEN = 2  # "--approve x" is not a name
THESIS_PREVIEW_CHARS = 60
PARAMS_PREVIEW_CHARS = 60
TABLE_PREVIEW_ROWS = 40
RUN_HINT_DATES = 5  # most recent saved run dates listed in a 'nothing saved for <date>' hint
NORMAL_KURTOSIS = 3.0  # deflated_sharpe takes raw (non-excess) kurtosis; pandas .kurt() is excess
TRIAL_METRIC_KEYS = ("trades", "win_rate", "avg_r", "profit_factor", "cagr", "max_dd", "sharpe")
EQUITY_ACCOUNT_KEYS = ("equity", "portfolio_value", "last_equity", "cash")
REGIME_COLUMNS = ("market_trend_state", "market_vol_regime")
PRODUCTION_SIZER = "risk.sizing.size_signal_detail"  # the sizer `swing size` / paper use; backtests use it too
RESEARCH_SIZER = "research.backtest.fixed_fractional_sizer"  # fallback when risk.sizing is unavailable
REPLAY_KIND = "replay"  # runs/replay/<start>_<end>.json written by `swing replay`
DEFAULT_REPLAY_EQUITY = 100_000.0  # research.replay.run_replay's default starting equity
SHADOW_GROUP_BY = "strategy,regime"  # research.shadow.shadow_report's default grouping
# `swing replay` grades its signals in a table of its own so research runs never overwrite or mix with the live
# nightly's `shadow_signals` rows (same key: strategy, symbol, as_of); `swing shadow report --replay` reads it.
# Same value as research.shadow.REPLAY_SHADOW_TABLE (run_replay's default); kept literal so the CLI imports lazily.
REPLAY_SHADOW_TABLE = "shadow_signals_replay"
# the columns `swing shadow report` prints by default (research.shadow.summarize_outcomes; --all-columns for every one)
SHADOW_REPORT_COLUMNS = (
    "n_signals", "n_taken", "n_pending", "n", "win_rate", "avg_r", "expectancy", "profit_factor", "avg_mfe_r",
    "avg_mae_r",
)

log = structlog.get_logger("swing.cli")

# ----------------------------------------------------------------------------------------------------------
# App skeleton
# ----------------------------------------------------------------------------------------------------------
app = typer.Typer(
    name="swing",
    help="swing-engine: research, live monitoring and paper execution for US-equity swing trading.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)
rank_app = typer.Typer(help="Train or apply the cross-sectional ranker (research.ranker).")
monitor_app = typer.Typer(help="Live monitor: run the service, report on alerts, or replay the event log.")
shadow_app = typer.Typer(help="Shadow ledger: forward outcomes of every signal, taken or not (research.shadow).")
app.add_typer(rank_app, name="rank")
app.add_typer(monitor_app, name="monitor")
app.add_typer(shadow_app, name="shadow")


@dataclass
class AppState:
    settings: Settings
    settings_path: Path | None
    verbose: bool


class _StderrLogger:
    """structlog sink that writes to whatever `sys.stderr` is at call time.

    Binding the stream at configure time would leak a closed stream after typer's CliRunner swaps it
    during tests, breaking every later test that logs.
    """

    def msg(self, message: str) -> None:
        print(message, file=sys.stderr)

    log = debug = info = warning = warn = error = critical = exception = fatal = msg


def _configure_logging(level: int) -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=lambda *args: _StderrLogger(),
        cache_logger_on_first_use=False,
    )


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    settings: Annotated[
        Path | None,
        typer.Option(
            "--settings",
            envvar="SWING_SETTINGS",
            help="Path to settings.yaml (default: config/settings.yaml).",
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="INFO logging to stderr.")] = False,
    debug: Annotated[bool, typer.Option("--debug", help="DEBUG logging to stderr.")] = False,
    version: Annotated[bool, typer.Option("--version", help="Print the version and exit.")] = False,
) -> None:
    """Research, monitoring and paper execution. Run `swing <command> --help` for details."""
    level = logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING
    _configure_logging(level)
    if ctx.invoked_subcommand is None:
        if version:
            typer.echo(f"swing-engine {__version__}")
            raise typer.Exit(EXIT_OK)
        typer.echo(ctx.get_help())
        raise typer.Exit(EXIT_USAGE)
    ctx.obj = AppState(settings=load_settings(settings), settings_path=settings, verbose=verbose or debug)


# ----------------------------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------------------------
def _state(ctx: typer.Context) -> AppState:
    obj = ctx.obj
    if not isinstance(
        obj, AppState
    ):  # pragma: no cover - only when a command is invoked without the callback
        obj = AppState(settings=load_settings(None), settings_path=None, verbose=False)
    return obj


def _console() -> Console:
    return Console()


def _fail(message: str, code: int = EXIT_FAILED) -> NoReturn:
    Console(stderr=True).print(f"[bold red]error:[/bold red] {message}")
    raise typer.Exit(code=code)


def _load(dotted: str) -> Any:
    """Return `swing_engine.<module>.<attr>` or exit with a clear message if the module is missing/broken."""
    module_path, _, attr = dotted.rpartition(".")
    full = f"swing_engine.{module_path}"
    try:
        mod = importlib.import_module(full)
    except ImportError as e:
        _fail(f"{full} is not available ({e}). Is that module implemented yet?", EXIT_MISSING_MODULE)
    except Exception as e:  # a half-written module with a runtime error at import
        _fail(f"{full} failed to import: {type(e).__name__}: {e}", EXIT_MISSING_MODULE)
    try:
        return getattr(mod, attr)
    except AttributeError:
        _fail(f"{full} has no attribute {attr!r} (expected by docs/api-contract.md)", EXIT_MISSING_MODULE)


def _try_load(dotted: str) -> Any | None:
    """Like `_load` but returns None instead of exiting (for optional helpers)."""
    module_path, _, attr = dotted.rpartition(".")
    try:
        return getattr(importlib.import_module(f"swing_engine.{module_path}"), attr, None)
    except Exception:
        return None


def _construct(cls: type, **candidates: Any) -> Any:
    """Instantiate `cls` passing only the keyword arguments its constructor accepts.

    Modules are written concurrently against a names-only contract, so constructor signatures vary.
    """
    try:
        params = inspect.signature(cls).parameters
    except (TypeError, ValueError):
        return cls()
    accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    kwargs = {k: v for k, v in candidates.items() if accepts_kwargs or k in params}
    return cls(**kwargs)


def _call_supported(fn: Any, *args: Any, **candidates: Any) -> Any:
    """Call `fn(*args, **kw)` keeping only keyword arguments the function accepts."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(*args)
    accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    kwargs = {k: v for k, v in candidates.items() if accepts_kwargs or k in params}
    return fn(*args, **kwargs)


def _parse_date(value: str | None, default: date | None = None) -> date | None:
    if value is None or value == "":
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"expected an ISO date (YYYY-MM-DD), got {value!r}") from e


def _parse_params(items: list[str] | None) -> dict[str, Any]:
    """Parse repeated `k=v` options; values are JSON when they parse (1, 2.5, true, [1,2]) else strings."""
    out: dict[str, Any] = {}
    for item in items or []:
        key, sep, raw = item.partition("=")
        key = key.strip()
        if not sep or not key:
            raise typer.BadParameter(f"expected key=value, got {item!r}")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def _split_list(items: list[str] | None) -> list[str] | None:
    """Accept `-s a -s b` and `-s a,b`; None when nothing was given."""
    if not items:
        return None
    out = [part.strip() for item in items for part in item.split(",") if part.strip()]
    return out or None


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _store_path(settings: Settings) -> Path:
    return _resolve(settings.data.store_path)


def _run_file(settings: Settings, kind: str, as_of: date) -> Path:
    return _store_path(settings).parent / RUNS_DIRNAME / kind / f"{as_of.isoformat()}.json"


def _save_models(path: Path, items: list[BaseModel]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([m.model_dump(mode="json") for m in items], indent=2))
    return path


def _load_models(path: Path, model_cls: type[BaseModel]) -> list[Any]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text() or "[]")
    return [model_cls.model_validate(r) for r in raw]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text() or "null") or default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            log.warning("trials_bad_line", path=str(path), line=line[:PARAMS_PREVIEW_CHARS])
    return rows


def _compact(obj: Any, limit: int = PARAMS_PREVIEW_CHARS) -> str:
    """Short, markup-safe preview of a value for a table cell (JSON for containers)."""
    text = json.dumps(obj, default=str, separators=(",", ":")) if not isinstance(obj, str) else obj
    return escape(text if len(text) <= limit else text[: limit - 1] + "…")


def _fmt(value: Any) -> str:
    """Markup-safe cell text: data (symbols, notes, params) must never be parsed as rich tags."""
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.4f}" if abs(value) < 1 else f"{value:,.2f}"
    if isinstance(value, (dict, list)):
        return _compact(value)
    return escape(str(value))


def _print_mapping(title: str, mapping: dict[str, Any]) -> None:
    table = Table(title=title, show_lines=False)
    table.add_column("key", style="cyan")
    table.add_column("value")
    for key, value in mapping.items():
        table.add_row(escape(str(key)), value if isinstance(value, Text) else _fmt(value))
    _console().print(table)


def _print_frame(title: str, frame: pd.DataFrame, limit: int = TABLE_PREVIEW_ROWS) -> None:
    table = Table(title=f"{title} ({len(frame)} rows)")
    for col in frame.columns:
        table.add_column(str(col))
    for _, row in frame.head(limit).iterrows():
        table.add_row(*[_fmt(v) for v in row.tolist()])
    _console().print(table)


def _print_any(title: str, obj: Any) -> None:
    if obj is None:
        _console().print(f"{title}: (nothing returned)")
    elif isinstance(obj, pd.DataFrame):
        _print_frame(title, obj)
    elif isinstance(obj, dict):
        _print_mapping(title, obj)
    elif isinstance(obj, list) and obj and all(isinstance(r, dict) for r in obj):
        _print_frame(title, pd.DataFrame(obj))
    else:
        _console().print(f"[bold]{escape(title)}[/bold]")
        _console().print(str(obj), markup=False, highlight=False)


# ----------------------------------------------------------------------------------------------------------
# Data / panel helpers
# ----------------------------------------------------------------------------------------------------------
def _anthropic_client(secrets: Secrets, *, async_client: bool) -> Any | None:
    """Claude client built from the .env key (the SDK by itself only reads os.environ). None without a key."""
    if not secrets.anthropic_api_key:
        return None
    factory = _try_load("agent.client.get_async_client" if async_client else "agent.client.get_client")
    return factory(secrets) if factory is not None else None


def _open_store(settings: Settings, must_exist: bool = True) -> Any:
    path = _store_path(settings)
    if must_exist and not path.exists():
        _fail(f"store {path} does not exist; run `swing ingest` first", EXIT_NO_DATA)
    store_cls = _load("data.store.Store")
    path.parent.mkdir(parents=True, exist_ok=True)
    return store_cls(str(path))


def _default_start(settings: Settings, end: date) -> date:
    return end - timedelta(days=DAYS_PER_YEAR * settings.data.history_years)


def _naive_ts(frame: pd.DataFrame) -> pd.Series:
    ts = pd.to_datetime(frame["ts"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    return ts


def _slice_dates(frame: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if "ts" not in frame.columns or frame.empty:
        return frame
    ts = _naive_ts(frame)
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= ts >= pd.Timestamp(start)
    if end is not None:
        mask &= ts < pd.Timestamp(end) + pd.Timedelta(days=1)
    return frame.loc[mask]


def _latest_rows(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Rows of the last bar date on or before `as_of` (point-in-time slice for predict/regime)."""
    sliced = _slice_dates(frame, None, as_of)
    if sliced.empty:
        return sliced
    ts = _naive_ts(sliced)
    return sliced.loc[ts == ts.max()]


def _market_slice(bars: pd.DataFrame) -> pd.DataFrame | None:
    if "symbol" not in bars.columns:
        return None
    market = bars.loc[bars["symbol"] == MARKET_SYMBOL]
    return market if not market.empty else None


class _StoreListing:
    """Provider-shaped view over the store's `symbols` reference table so `data.universe.build_universe`
    can screen a point-in-time universe from stored bars without a network provider."""

    name = "store"

    def __init__(self, symbols: pd.DataFrame):
        self._symbols = symbols

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        return self._symbols

    def daily_bars(self, symbols: Any, start: date, end: date) -> pd.DataFrame:
        raise RuntimeError("the store-backed universe screens the panel's own bars; it never fetches")


def _store_listing(store: Any) -> _StoreListing | None:
    """None when the store has no reference table (a bare bars import): the caller then skips the screen."""
    try:
        symbols = store.read_table(SYMBOLS_TABLE)
    except Exception as e:
        log.info("symbols_table_unavailable", error=str(e))
        return None
    if symbols is None or len(symbols) == 0 or "symbol" not in symbols.columns:
        return None
    return _StoreListing(symbols)


def _universe_window(
    provider: Any, settings: Settings, dates: Iterable[date], bars: pd.DataFrame | None = None
) -> list[str] | None:
    """Union of the screened universe at each anchor date (`data.universe.build_universe`).

    A scan passes one date (point-in-time). A backtest passes its start and end so a name that was live
    at either anchor stays in even if it delisted in between (CLAUDE.md rule 3: delisted symbols stay in
    the universe; the backtester books the delisting exit). None when the data module is unavailable.
    """
    build_universe = _try_load("data.universe.build_universe")
    if build_universe is None:
        return None
    found: set[str] = set()
    for d in dates:
        found.update(_call_supported(build_universe, provider, settings, d, bars=bars))
    return sorted(found)


def _month_anchors(days: Iterable[date], start: date, end: date) -> list[date]:
    """The first session on/after `start` and the first session of every later month through `end`."""
    anchors: list[date] = []
    months: set[tuple[int, int]] = set()
    for d in sorted({d for d in days if start <= d <= end}):
        key = (d.year, d.month)
        if key not in months:
            anchors.append(d)
            months.add(key)
    return anchors or [start]


def _universe_memberships(
    provider: Any, settings: Settings, anchors: Iterable[date], bars: pd.DataFrame | None = None
) -> dict[date, frozenset[str]] | None:
    """Point-in-time universe at each anchor (`data.universe.build_universe`), keyed by anchor date.

    A backtest screens membership month by month so a name is only admitted once it passes the price /
    liquidity screen on data available then (never on its end-of-window success); names that qualified at an
    earlier anchor and delisted later stay in (CLAUDE.md rule 3). None when the data module is unavailable.
    """
    build_universe = _try_load("data.universe.build_universe")
    if build_universe is None:
        return None
    return {d: frozenset(_call_supported(build_universe, provider, settings, d, bars=bars)) for d in anchors}


def _membership_lookup(memberships: Mapping[date, frozenset[str]]) -> Callable[[date], frozenset[str]]:
    """`universe_at(day)`: the membership screened at the latest anchor on or before `day`."""
    anchors = sorted(memberships)

    def universe_at(day: date) -> frozenset[str]:
        i = bisect_right(anchors, day)
        return memberships[anchors[i - 1 if i else 0]]

    return universe_at


def _strategy_rr_floor(settings: Settings, strategy: str) -> float | None:
    """Per-strategy reward:risk floor from settings.strategies[<name>].min_reward_risk (None = portfolio floor)."""
    helper = _try_load("risk.sizing.strategy_min_reward_risk")
    if helper is None:
        return None
    return helper(settings.strategies, strategy)


def _production_sizer(size_detail: Any, settings: Settings | None = None) -> Any | None:
    """Adapt `risk.sizing.size_signal_detail` to the backtester's `Sizer` shape (intent only, no logging)."""
    if size_detail is None:
        return None

    def sizer(signal: Any, equity: float, risk_cfg: Any, open_positions: Any = None, sector_map: Any = None) -> Any:
        floor = _strategy_rr_floor(settings, signal.strategy) if settings is not None else None
        extra = {"min_reward_risk": floor} if floor is not None else {}
        intent, _reason = size_detail(signal, equity, risk_cfg, open_positions, sector_map, **extra)
        return intent

    return sizer


def _restrict_to_universe(panel: pd.DataFrame, universe: list[str] | None, label: str) -> pd.DataFrame:
    if universe is None:
        return panel
    kept = panel.loc[panel["symbol"].isin(universe)]
    log.info("universe_applied", universe=len(universe), symbols=int(kept["symbol"].nunique()), when=label)
    if kept.empty:
        _fail(f"no panel rows for the {len(universe)}-name universe ({label})", EXIT_NO_DATA)
    return kept


def _available_runs(settings: Settings, kind: str) -> str:
    """Dates that have a saved runs/<kind>/<date>.json, for 'nothing saved for <date>' hints."""
    folder = _store_path(settings).parent / RUNS_DIRNAME / kind
    dates = sorted(f.stem for f in folder.glob("*.json")) if folder.exists() else []
    return f"; saved {kind}: {', '.join(dates[-RUN_HINT_DATES:])}" if dates else ""


def _read_bars(
    store: Any, settings: Settings, symbols: list[str] | None, start: date, end: date
) -> pd.DataFrame:
    bars = store.read_bars(symbols, start, end)
    if bars is None or len(bars) == 0:
        _fail(f"no bars in {_store_path(settings)} for {start}..{end}; run `swing ingest`", EXIT_NO_DATA)
    return bars


def _with_extras(
    panel: pd.DataFrame, settings: Settings, strategies: list[Any] | None, market: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Attach the `extra_features` of ``strategies`` (names or instances; names are built with their settings
    params, so non-default lengths resolve) that the panel lacks. Cached panels carry none."""
    if not strategies:
        return panel
    ensure_extra, required_extras = _load("features.extra.ensure_extra"), _load("features.extra.required_extras")
    objs = [_make_strategy(s, settings) if isinstance(s, str) else s for s in strategies]
    return ensure_extra(panel, required_extras(objs), market)


def _read_panel(
    store: Any, settings: Settings, start: date | None, end: date | None, strategies: list[Any] | None = None
) -> pd.DataFrame:
    """Cached `panel` table when present, else build it from bars on the fly; plus ``strategies``' extras."""
    panel: pd.DataFrame | None = None
    try:
        panel = store.read_table(PANEL_TABLE)
    except Exception as e:  # table missing or store API differs; fall back to bars
        log.info("panel_table_unavailable", error=str(e))
    if panel is None or len(panel) == 0:
        log.info("building_panel_from_bars", hint="run `swing features` to cache it")
        end_d = end or date.today()
        start_d = (start or _default_start(settings, end_d)) - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS)
        bars = _read_bars(store, settings, None, start_d, end_d)
        build_panel = _load("features.panel.build_panel")
        panel = build_panel(bars, _market_slice(bars))
    panel = _load("data.market_series.join_market_series")(store, panel)  # before extras: ff3_resid_mom reads it
    panel = _with_extras(panel, settings, strategies)
    panel = _load("data.fundamentals.join_edgar")(store, panel)
    panel = _slice_dates(panel, start, end)
    if panel.empty:
        _fail(f"panel has no rows for {start}..{end}", EXIT_NO_DATA)
    return panel


def _registry_get(kind: str, name: str) -> type:
    try:
        return registry.get(kind, name)
    except KeyError as e:
        _fail(str(e), EXIT_USAGE)
    except Exception as e:  # a broken plugin module breaks discovery
        _fail(
            f"plugin discovery failed while looking for {kind} {name!r}: {type(e).__name__}: {e}",
            EXIT_MISSING_MODULE,
        )


def _registry_names(kind: str) -> list[str] | str:
    try:
        return registry.names(kind)
    except Exception as e:
        return f"discovery failed: {type(e).__name__}: {e}"


def _instantiate_plugin(cls: type, settings: Settings, secrets: Secrets, **extra: Any) -> Any:
    """Providers/brokers expose `from_settings(settings, secrets)`; otherwise pass what the ctor accepts."""
    factory = getattr(cls, "from_settings", None)
    if callable(factory):
        return factory(settings, secrets)
    return _construct(cls, settings=settings, secrets=secrets, **extra)


def _make_provider(name: str, settings: Settings, secrets: Secrets) -> Any:
    make_provider = _try_load("data.ingest.make_provider")
    if make_provider is not None:
        try:
            return make_provider(name, settings, secrets)
        except KeyError as e:  # unknown provider name
            _fail(str(e), EXIT_USAGE)
    cls = _registry_get("bar_provider", name)
    return _instantiate_plugin(cls, settings, secrets, config=settings.data)


def _make_broker(name: str, settings: Settings, secrets: Secrets) -> Any:
    cls = _registry_get("broker", name)
    return _instantiate_plugin(cls, settings, secrets, risk=settings.risk, risk_cfg=settings.risk)


def _strategy_params(settings: Settings, name: str) -> dict[str, Any]:
    cfg = settings.strategies.get(name) or {}
    if isinstance(cfg.get("params"), dict):
        return dict(cfg["params"])
    return {k: v for k, v in cfg.items() if k != "enabled"}


def _enabled_strategies(settings: Settings) -> list[str]:
    if settings.strategies:  # configured: exactly the enabled ones (all disabled = none, never all)
        return [n for n, cfg in settings.strategies.items() if (cfg or {}).get("enabled", True)]
    known = _registry_names("strategy")
    return known if isinstance(known, list) else []


def _make_strategy(name: str, settings: Settings, overrides: dict[str, Any] | None = None) -> Any:
    cls = _registry_get("strategy", name)
    return cls({**_strategy_params(settings, name), **(overrides or {})})


def _regime_from_panel(panel: pd.DataFrame, as_of: date) -> dict[str, Any] | None:
    latest = _latest_rows(panel, as_of)
    cols = [c for c in REGIME_COLUMNS if c in latest.columns]
    if latest.empty or not cols:
        return None
    row = latest.iloc[-1]
    return {c: (None if pd.isna(row[c]) else float(row[c])) for c in cols}


def _run_scan(settings: Settings, panel: pd.DataFrame, as_of: date, names: list[str]) -> list[Signal]:
    regime = _regime_from_panel(panel, as_of)
    signals: list[Signal] = []
    failures = 0
    for name in names:
        strategy = _make_strategy(name, settings)
        try:
            found = list(strategy.signals(panel, as_of, regime))
        except Exception as e:
            failures += 1
            log.error("strategy_failed", strategy=name, error=f"{type(e).__name__}: {e}")
            Console(stderr=True).print(f"[yellow]{name}: {type(e).__name__}: {e}[/yellow]")
            continue
        log.info("strategy_scanned", strategy=name, signals=len(found))
        signals.extend(found)
    if failures and failures == len(names):
        _fail("every strategy failed; see messages above")
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals


def _print_signals(signals: list[Signal], as_of: date) -> None:
    table = Table(title=f"Signals as of {as_of} ({len(signals)})")
    for col in ("strategy", "symbol", "side", "entry", "stop", "target", "R:R", "score", "notes"):
        table.add_column(col)
    for s in signals:
        table.add_row(
            s.strategy,
            s.symbol,
            s.side.value,
            _fmt(s.entry),
            _fmt(s.stop),
            _fmt(s.target),
            _fmt(s.reward_risk),
            _fmt(s.score),
            _compact(s.notes, THESIS_PREVIEW_CHARS),
        )
    _console().print(table)


# ----------------------------------------------------------------------------------------------------------
# status
# ----------------------------------------------------------------------------------------------------------
def _store_counts(path: Path) -> dict[str, Any]:
    """Row counts straight from DuckDB (read-only) so `status` works without the data module."""
    import duckdb  # local import: keeps CLI import light

    counts: dict[str, Any] = {}
    try:
        con = duckdb.connect(str(path), read_only=True)
    except Exception as e:
        return {"store": f"could not open: {type(e).__name__}: {e}"}
    try:
        tables = [
            r[0]
            for r in con.execute(
                "select table_name from information_schema.tables where table_schema = 'main' order by 1"
            ).fetchall()
        ]
        for name in tables:
            counts[f"rows[{name}]"] = con.execute(f'select count(*) from "{name}"').fetchone()[0]
        if "bars" in tables:
            n_sym, lo, hi = con.execute(
                "select count(distinct symbol), min(ts), max(ts) from bars"
            ).fetchone()
            counts["bars.symbols"] = n_sym
            counts["bars.range"] = f"{lo} .. {hi}"
    except Exception as e:
        counts["store"] = f"query failed: {type(e).__name__}: {e}"
    finally:
        con.close()
    return counts


@app.command()
def status(ctx: typer.Context) -> None:
    """Show configured keys/providers, store path and counts, kill switch and trial log. No network."""
    st = _state(ctx)
    settings = st.settings
    secrets = load_secrets()

    keys = Table(title="Secrets (.env) - values are never printed")
    keys.add_column("key", style="cyan")
    keys.add_column("status")
    for name, field in Secrets.model_fields.items():
        value = getattr(secrets, name)
        if isinstance(value, bool):
            shown = str(value)
        elif value in (None, ""):
            shown = "[red]missing[/red]"
        elif value == field.default:
            shown = "[yellow]default[/yellow]"
        else:
            shown = "[green]set[/green]"
        keys.add_row(name.upper(), shown)
    _console().print(keys)

    store_path = _store_path(settings)
    kill_path = _resolve(settings.risk.kill_switch_file)
    trials_path = ROOT / TRIALS_PATH
    config: dict[str, Any] = {
        "settings file": str(st.settings_path or ROOT / "config" / "settings.yaml"),
        "bar provider": settings.data.bar_provider,
        "store path": str(store_path),
        "store exists": store_path.exists(),
        "event log": str(_resolve(settings.data.event_log_path)),
        "paper mode (ALPACA_PAPER)": secrets.alpaca_paper,
        "kill switch": Text(f"TRIPPED ({kill_path})", style="bold red")
        if kill_path.exists()
        else Text(f"clear ({kill_path})"),
        "trials logged": len(_read_jsonl(trials_path)),
        "enabled strategies": ", ".join(_enabled_strategies(settings)) or "-",
        "monitor feeds": ", ".join(settings.monitor.feeds) or "-",
    }
    if store_path.exists():
        config.update(_store_counts(store_path))
    _print_mapping("Configuration", config)

    plugins = Table(title="Registered plugins")
    plugins.add_column("kind", style="cyan")
    plugins.add_column("names")
    for kind in ("bar_provider", "strategy", "broker", "feed", "rule", "deliverer"):
        found = _registry_names(kind)
        plugins.add_row(kind, ", ".join(found) if isinstance(found, list) and found else str(found or "-"))
    _console().print(plugins)


# ----------------------------------------------------------------------------------------------------------
# ingest / universe / features
# ----------------------------------------------------------------------------------------------------------
@app.command()
def ingest(
    ctx: typer.Context,
    provider: Annotated[
        str | None, typer.Option("--provider", "-p", help="bar provider (default settings.data.bar_provider)")
    ] = None,
    start: Annotated[
        str | None, typer.Option("--start", help="YYYY-MM-DD (default: history_years before end)")
    ] = None,
    end: Annotated[str | None, typer.Option("--end", help="YYYY-MM-DD (default: today)")] = None,
    symbols: Annotated[
        list[str] | None, typer.Option("--symbols", "-s", help="repeat or comma-separate; default universe")
    ] = None,
    full: Annotated[bool, typer.Option("--full", help="full refresh instead of incremental")] = False,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="auto | grouped | per-symbol. auto = grouped (one call per session for the whole market) when "
            "the provider supports it and no symbols are named, else per-symbol",
        ),
    ] = INGEST_MODE_AUTO,
) -> None:
    """Fetch daily bars through a provider into the DuckDB store (data.ingest.run_ingest)."""
    settings = _state(ctx).settings
    secrets = load_secrets()
    provider_name = provider or settings.data.bar_provider
    end_d = _parse_date(end, date.today())
    start_d = _parse_date(start, _default_start(settings, end_d))
    mode_value = INGEST_MODE_ALIASES.get(mode.strip().lower())
    if mode_value is None:
        _fail(f"--mode must be one of {', '.join(INGEST_MODE_CHOICES)}, got {mode!r}", EXIT_USAGE)
    run_ingest = _load("data.ingest.run_ingest")
    store = _open_store(settings, must_exist=False)
    log.info("ingest_start", provider=provider_name, start=str(start_d), end=str(end_d), mode=mode_value)
    try:
        result = _call_supported(
            run_ingest, settings, secrets, provider_name, _split_list(symbols), start_d, end_d, store,
            full=full, mode=mode_value, progress=_ingest_progress,
        )
    except ValueError as e:  # e.g. --mode grouped with --symbols, or a provider without grouped-daily
        _fail(str(e), EXIT_USAGE)
    _print_mapping(f"Ingest via {provider_name}", dict(result or {}))


@app.command("ingest-edgar")
def ingest_edgar(
    ctx: typer.Context,
    symbols: Annotated[
        list[str] | None, typer.Option("--symbols", "-s", help="repeat or comma-separate; default every stored symbol")
    ] = None,
    limit: Annotated[int | None, typer.Option("--limit", help="fetch at most N CIKs this run")] = None,
    refresh_days: Annotated[
        int | None, typer.Option("--refresh-days", help="skip CIKs fetched OK within N days (default 7)")
    ] = None,
) -> None:
    """Fetch SEC 8-K earnings dates and XBRL fundamentals into the store (data.fundamentals.run_edgar_ingest)."""
    settings = _state(ctx).settings
    edgar = _edgar_client()
    run_edgar_ingest = _load("data.fundamentals.run_edgar_ingest")
    syms = _split_list(symbols)
    store = _open_store(settings, must_exist=syms is None)  # the default universe is the stored bars
    extra = {"refresh_days": refresh_days} if refresh_days is not None else {}
    result = run_edgar_ingest(store, edgar, syms, limit=limit, progress=_ingest_progress, **extra)
    _print_mapping("EDGAR ingest (ticker -> CIK)", dict(result or {}))


def _edgar_client() -> Any:
    agent = load_secrets().edgar_user_agent or ""
    if "@" not in agent or agent == Secrets.model_fields["edgar_user_agent"].default:
        _fail("set EDGAR_USER_AGENT in .env to 'name contact-email' (SEC fair-access policy); the placeholder is refused",
              EXIT_REFUSED)
    return _load("data.edgar.Edgar")(agent)


@app.command("ingest-insiders")
def ingest_insiders(
    ctx: typer.Context,
    start_year: Annotated[int, typer.Option("--start-year", help="first year of quarterly Form 4 data sets")] = 2006,
    quarters: Annotated[int | None, typer.Option("--quarters", help="fetch at most N quarters this run")] = None,
) -> None:
    """Fetch SEC Insider Transactions Data Sets (Form 4 P/S trades) into `insider_trades` (data.insiders)."""
    settings = _state(ctx).settings
    edgar = _edgar_client()
    store = _open_store(settings, must_exist=False)
    result = _load("data.insiders.run_insider_ingest")(
        store, edgar, start_year=start_year, quarters=quarters, progress=_ingest_progress
    )
    _print_mapping("Insider ingest (Form 4 quarterly data sets)", dict(result or {}))


@app.command("ingest-vix")
def ingest_vix(ctx: typer.Context) -> None:
    """Fetch Cboe VIX / VIX9D / VIX3M daily history (free, no key) into the `vix` table (data.market_series)."""
    store = _open_store(_state(ctx).settings, must_exist=False)
    _print_mapping("Cboe VIX ingest", dict(_load("data.market_series.run_vix_ingest")(store) or {}))


@app.command("ingest-french")
def ingest_french(ctx: typer.Context) -> None:
    """Fetch Kenneth French daily FF3 + momentum factors (free, no key) into `ff_factors` (data.market_series)."""
    store = _open_store(_state(ctx).settings, must_exist=False)
    _print_mapping("Ken French factors ingest", dict(_load("data.market_series.run_french_ingest")(store) or {}))


@app.command("repair-store")
def repair_store(
    ctx: typer.Context,
    apply: Annotated[bool, typer.Option("--apply/--dry-run", help="write the repair (default: dry run, no writes)")] = False,
    undo: Annotated[str | None, typer.Option("--undo", help="reverse one applied run by its run_id")] = None,
) -> None:
    """Drop pre-2024-10-07 zero-volume filler and split ticker-reuse joins into TICKER~YYYYMMDD keys
    (data.repair; every change logged in `repairs`). Run on a backup copy first."""
    store = _open_store(_state(ctx).settings)
    repair = importlib.import_module("swing_engine.data.repair")
    if undo:
        _print_mapping(f"Repair {undo} reverted", repair.undo_repair(store, undo))
        return
    result = repair.apply(store) if apply else repair.plan(store)
    _print_frame("Zero-volume filler by symbol", result["filler"])
    _print_frame("Ticker-reuse splits", result["splits"])
    _print_mapping("Store repair" + (" APPLIED" if apply else " (dry run, nothing written)"),
                   {k: v for k, v in result.items() if k not in ("filler", "splits")})


@app.command("ingest-delisted")
def ingest_delisted(
    ctx: typer.Context,
    refresh: Annotated[bool, typer.Option("--refresh", help="re-enumerate the candidates (Massive + Alpha Vantage)")] = False,
    limit: Annotated[int | None, typer.Option("--limit", help="fetch at most N candidates this run")] = None,
) -> None:
    """Delisted 2017-2024 US common stocks: enumerate (Massive inactive tickers + AV dated delisted lists), fetch
    Alpaca SIP bars, store under TICKER~YYYYMMDD keys with `listings` rows (data.delisted). Resumable."""
    settings = _state(ctx).settings
    secrets = load_secrets()
    store = _open_store(settings)
    alpaca = _make_provider("alpaca", settings, secrets)
    alpaca.feed = "sip"  # historical SIP bars older than 15 minutes are free
    massive = _make_provider("massive", settings, secrets) if secrets.massive_api_key else None
    result = _load("data.delisted.run_delisted_ingest")(
        store, alpaca, massive=massive, av_key=secrets.alphavantage_api_key, refresh=refresh, limit=limit,
        progress=_ingest_progress,
    )
    _print_mapping("Delisted ingest", dict(result or {}))


def _ingest_progress(line: str) -> None:
    """`run_ingest(progress=)` sink: estimate and every-N-sessions progress lines go to the console."""
    _console().print(escape(line))


@app.command()
def universe(
    ctx: typer.Context,
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="symbols to print; --all prints every one")
    ] = DEFAULT_TOP_N,
    show_all: Annotated[bool, typer.Option("--all")] = False,
) -> None:
    """Build the screened universe for a date (data.universe.build_universe) and print it."""
    settings = _state(ctx).settings
    provider_name = provider or settings.data.bar_provider
    as_of_d = _parse_date(as_of, date.today())
    prov = _make_provider(provider_name, settings, load_secrets())
    build_universe = _load("data.universe.build_universe")
    symbols = list(build_universe(prov, settings, as_of_d))
    shown = symbols if show_all else symbols[:limit]
    _print_mapping(
        f"Universe as of {as_of_d} via {provider_name}",
        {"symbols": len(symbols), "shown": len(shown), "list": " ".join(shown)},
    )


@app.command()
def features(
    ctx: typer.Context,
    start: Annotated[
        str | None, typer.Option("--start", help="YYYY-MM-DD (default: full history incl. warm-up)")
    ] = None,
    end: Annotated[str | None, typer.Option("--end", help="YYYY-MM-DD (default: today)")] = None,
    symbols: Annotated[
        list[str] | None, typer.Option("--symbols", "-s", help="repeat or comma-separate")
    ] = None,
) -> None:
    """Build the feature panel from stored bars and cache it to the store table 'panel'."""
    settings = _state(ctx).settings
    end_d = _parse_date(end, date.today())
    start_d = _parse_date(start, _default_start(settings, end_d) - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS))
    store = _open_store(settings)
    bars = _read_bars(store, settings, _split_list(symbols), start_d, end_d)
    build_panel = _load("features.panel.build_panel")
    panel = build_panel(bars, _market_slice(bars))
    store.write_table(PANEL_TABLE, panel, PANEL_KEYS)
    ts = _naive_ts(panel) if "ts" in panel.columns else None
    _print_mapping(
        "Feature panel cached",
        {
            "table": PANEL_TABLE,
            "rows": len(panel),
            "symbols": int(panel["symbol"].nunique()) if "symbol" in panel.columns else "-",
            "columns": len(panel.columns),
            "range": f"{ts.min().date()} .. {ts.max().date()}" if ts is not None and len(ts) else "-",
        },
    )


# ----------------------------------------------------------------------------------------------------------
# scan / backtest / rank
# ----------------------------------------------------------------------------------------------------------
@app.command()
def scan(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    strategies: Annotated[
        list[str] | None, typer.Option("--strategies", "-s", help="repeat or comma-separate")
    ] = None,
    top: Annotated[int, typer.Option("--top", help="rows to print (all are saved)")] = DEFAULT_TOP_N,
    save: Annotated[
        bool, typer.Option("--save/--no-save", help="write runs/signals/<date>.json for review/size")
    ] = True,
) -> None:
    """Run enabled strategies on the point-in-time panel and print the Signals."""
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    names = _split_list(strategies) or _enabled_strategies(settings)
    if not names:
        _fail("no strategies enabled in settings and none registered", EXIT_USAGE)
    store = _open_store(settings)
    panel = _read_panel(store, settings, None, as_of_d, names)
    full_panel, universe = panel, None
    listing = _store_listing(store)
    if listing is not None:  # screened, point-in-time universe (ETFs/OTC/delisted-before-as_of drop out)
        universe = _universe_window(listing, settings, [as_of_d], bars=panel)
        panel = _restrict_to_universe(panel, universe, f"as of {as_of_d}")
        if universe is not None:
            _console().print(f"universe as of {as_of_d}: {len(universe)} symbols")
    signals = _run_scan(settings, panel, as_of_d, names)
    _print_signals(signals[:top], as_of_d)
    if save:
        path = _save_models(_run_file(settings, "signals", as_of_d), signals)
        _console().print(f"saved {len(signals)} signals to {path}")
        _save_scan_routing(settings, full_panel, universe, as_of_d, store)


def _save_scan_routing(
    settings: Settings, panel: pd.DataFrame, universe: list[str] | None, as_of_d: date, store: Any = None
) -> None:
    """Save the playbook routing for saved scan signals (`runs/regime/<date>.json`, as the nightly does) so
    `swing autopilot` sizes them by the regime's multipliers. Without it `swing autopilot` refuses to size them
    (fail closed), so a routing failure here only warns."""
    note = "ops.nightly unavailable"
    payload: dict[str, Any] | None = None
    compute_regime = _try_load("ops.nightly.compute_regime")
    screened_breadth = _try_load("ops.nightly.screened_breadth")
    store_splits = _try_load("ops.nightly._store_splits")
    if compute_regime is not None and screened_breadth is not None:
        try:
            splits = store_splits(store) if store_splits is not None and store is not None else None
            breadth, _why = screened_breadth(panel, universe, splits)
            _state_obj, payload, note = compute_regime(settings, panel, as_of_d, breadth=breadth)
        except Exception as e:  # noqa: BLE001 - reported below; autopilot then refuses these signals
            payload, note = None, f"{type(e).__name__}: {e}"
    if payload is None or not isinstance(payload.get("allowed"), dict):
        Console(stderr=True).print(
            f"[yellow]playbook routing not saved ({escape(note or 'no allowed table')}); "
            "`swing autopilot` will not size these signals[/yellow]"
        )
        return
    path = _run_file(settings, "regime", as_of_d)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    allowed = ", ".join(f"{n} x{float(m):g}" for n, m in payload["allowed"].items()) or "none"
    _console().print(f"saved regime {escape(str(payload.get('regime')))} routing (allowed {escape(allowed)}) to {path}")


def _panel_from_provider(
    name: str,
    settings: Settings,
    secrets: Secrets,
    symbols: list[str] | None,
    start: date,
    end: date,
    strategies: list[Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    prov = _make_provider(name, settings, secrets)
    if symbols is None:
        symbols = _universe_window(prov, settings, (start, end))
        if symbols is None:
            listing = prov.list_symbols()
            symbols = list(listing["symbol"]) if "symbol" in listing.columns else []
    if not symbols:
        _fail(f"provider {name} returned no symbols", EXIT_NO_DATA)
    warm_start = start - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS)
    bars = prov.daily_bars(symbols, warm_start, end)
    if bars is None or len(bars) == 0:
        _fail(f"provider {name} returned no bars for {warm_start}..{end}", EXIT_NO_DATA)
    market = _market_slice(bars)
    if market is None:
        try:
            market = prov.daily_bars([MARKET_SYMBOL], warm_start, end)
        except Exception as e:  # market context is optional
            log.info("market_bars_unavailable", provider=name, error=str(e))
            market = None
    build_panel = _load("features.panel.build_panel")
    return _with_extras(build_panel(bars, market), settings, strategies, market), market


def _returns_moments(result: Any, metrics: dict[str, Any]) -> tuple[int, float, float]:
    """(n_obs, skew, raw kurtosis) for deflated Sharpe; from metrics when provided, else from the equity curve."""

    def _num(value: Any) -> float | None:
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        return None if pd.isna(out) else out

    n_obs = int(_num(metrics.get("n_obs")) or 0)
    skew = _num(metrics.get("skew"))
    kurt = _num(metrics.get("kurt", metrics.get("kurtosis")))
    curve = getattr(result, "equity", None)
    if curve is None:
        curve = getattr(result, "equity_curve", None)
    if curve is not None and len(curve) > 1:
        series = (
            curve["equity"] if isinstance(curve, pd.DataFrame) and "equity" in curve else pd.Series(curve)
        )
        rets = pd.to_numeric(series, errors="coerce").pct_change().dropna()
        n_obs = n_obs or int(len(rets))
        if skew is None and len(rets):
            skew = _num(rets.skew())
        if kurt is None and len(rets):
            kurt = _num(rets.kurt() + NORMAL_KURTOSIS)
    n_obs = n_obs or int(_num(metrics.get("trades")) or 0)
    return n_obs, skew if skew is not None else 0.0, kurt if kurt is not None else NORMAL_KURTOSIS


@app.command()
def backtest(
    ctx: typer.Context,
    strategy: Annotated[str, typer.Argument(help="registered strategy name")],
    start: Annotated[
        str | None, typer.Option("--start", help="YYYY-MM-DD (default: history_years ago)")
    ] = None,
    end: Annotated[str | None, typer.Option("--end", help="YYYY-MM-DD (default: today)")] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="fetch bars from this provider instead of the store"),
    ] = None,
    param: Annotated[
        list[str] | None, typer.Option("--param", "-P", help="strategy param override k=v (repeatable)")
    ] = None,
    cost: Annotated[
        list[str] | None, typer.Option("--cost", help="CostModel field override k=v (repeatable)")
    ] = None,
    symbols: Annotated[
        list[str] | None, typer.Option("--symbols", "-s", help="repeat or comma-separate")
    ] = None,
    no_log: Annotated[
        bool, typer.Option("--no-log", help="do not append this run to data/trials.jsonl")
    ] = False,
) -> None:
    """Walk-forward backtest one strategy, log the trial, print metrics with deflated Sharpe and trial count."""
    settings = _state(ctx).settings
    secrets = load_secrets()
    end_d = _parse_date(end, date.today())
    start_d = _parse_date(start, _default_start(settings, end_d))
    overrides = _parse_params(param)
    strat = _make_strategy(strategy, settings, overrides)
    universe_at: Callable[[date], frozenset[str]] | None = None
    delist_returns: dict[str, float] | None = None

    if provider:
        panel, market = _panel_from_provider(
            provider, settings, secrets, _split_list(symbols), start_d, end_d, [strat]
        )
    else:
        store = _open_store(settings)
        delist_returns = _load("data.delisted.delisting_returns")(store, settings)
        panel = _read_panel(store, settings, start_d - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS), end_d, [strat])
        market = _market_slice(panel)  # before the universe screen drops the ETF
        wanted = _split_list(symbols)
        if wanted:
            panel = panel.loc[panel["symbol"].isin(wanted)]
        else:
            listing = _store_listing(store)
            if listing is not None:
                anchors = _month_anchors(_naive_ts(panel).dt.date, start_d, end_d)
                memberships = _universe_memberships(listing, settings, anchors, bars=panel)
                if memberships:
                    universe = sorted(set().union(*memberships.values()))
                    panel = _restrict_to_universe(
                        panel, universe, f"{start_d}..{end_d}, {len(memberships)} monthly anchors"
                    )
                    universe_at = _membership_lookup(memberships)

    cost_model = _load("research.backtest.CostModel")
    costs = cost_model(**_parse_params(cost))
    run_backtest = _load("research.backtest.run_backtest")
    summarize = _load("research.metrics.summarize")
    deflated_sharpe = _load("research.metrics.deflated_sharpe")
    log_trial = _load("research.trials.log_trial")
    trial_count = _load("research.trials.trial_count")
    # the production sizer (reward/risk floor, marketable entry limit) so research counts the trades paper takes
    size_detail = _try_load(PRODUCTION_SIZER)
    sizer = _production_sizer(size_detail, settings)
    sizer_name = PRODUCTION_SIZER if sizer is not None else RESEARCH_SIZER

    log.info(
        "backtest_start", strategy=strategy, start=str(start_d), end=str(end_d), params=strat.params, sizer=sizer_name
    )
    result = _call_supported(
        run_backtest, strat, panel, start_d, end_d, settings.risk, costs,
        market=market, sizer=sizer, universe_at=universe_at, delist_returns=delist_returns,
    )
    metrics = dict(summarize(result))
    if not no_log:
        log_trial(strategy, dict(strat.params), metrics)
    n_trials = int(trial_count(strategy) or 0)
    n_obs, skew, kurt = _returns_moments(result, metrics)
    sharpe = float(metrics.get("sharpe") or 0.0)
    n_trials_all = int(trial_count(None) or 0)  # gate 2: deflate by EVERY logged trial, not just this strategy's
    deflated = deflated_sharpe(sharpe, max(n_trials_all, 1), n_obs, skew, kurt) if n_obs else None

    _print_mapping(
        f"Backtest {strategy} {start_d}..{end_d}",
        {
            "params": strat.params,
            "sizer": sizer_name,
            "universe": "point-in-time (monthly anchors)" if universe_at is not None else "as given",
            "costs": _compact(
                costs.model_dump()
                if hasattr(costs, "model_dump")
                else getattr(costs, "__dict__", repr(costs))
            ),
            **metrics,
        },
    )
    _print_mapping(
        "Significance (trial-count aware)",
        {
            "sharpe": sharpe,
            "deflated sharpe": deflated,
            "trials logged for this strategy": n_trials,
            "trials logged in total": n_trials_all,
            "n_obs / skew / kurtosis": f"{n_obs} / {skew:.3f} / {kurt:.3f}",
        },
    )


def _ranker_path(settings: Settings) -> Path:
    return _store_path(settings).parent / RANKER_FILENAME


def _save_ranker(model: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(model, "save"):
        model.save(str(path))
        return
    with path.open("wb") as fh:
        pickle.dump(model, fh)


def _load_ranker(path: Path) -> Any:
    if not path.exists():
        _fail(f"no ranker at {path}; run `swing rank train` first", EXIT_NO_DATA)
    ranker_cls = _try_load("research.ranker.RankerModel")
    if ranker_cls is not None and hasattr(ranker_cls, "load"):
        return ranker_cls.load(str(path))
    with path.open("rb") as fh:
        return pickle.load(fh)  # noqa: S301 - local file written by `swing rank train`


@rank_app.command("train")
def rank_train(
    ctx: typer.Context,
    start: Annotated[str | None, typer.Option("--start")] = None,
    end: Annotated[str | None, typer.Option("--end")] = None,
    horizon: Annotated[
        int, typer.Option("--horizon", help="forward-return horizon in bars")
    ] = DEFAULT_RANK_HORIZON,
    out: Annotated[
        Path | None, typer.Option("--out", help="model file (default <store dir>/ranker.pkl)")
    ] = None,
) -> None:
    """Train the cross-sectional ranker on the cached panel and save it."""
    settings = _state(ctx).settings
    end_d = _parse_date(end, date.today())
    start_d = _parse_date(start, _default_start(settings, end_d))
    store = _open_store(settings)
    panel = _read_panel(store, settings, start_d - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS), end_d)
    train_ranker = _load("research.ranker.train_ranker")
    model = train_ranker(panel, horizon=horizon, start=start_d, end=end_d)
    path = out or _ranker_path(settings)
    _save_ranker(model, path)
    info: dict[str, Any] = {"model": type(model).__name__, "saved": str(path), "horizon": horizon}
    importance = getattr(model, "feature_importance", None)
    if importance is not None:
        info["top features"] = _compact(importance() if callable(importance) else importance)
    _print_mapping("Ranker trained", info)


@rank_app.command("predict")
def rank_predict(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of")] = None,
    top: Annotated[int, typer.Option("--top")] = DEFAULT_TOP_N,
    model: Annotated[
        Path | None, typer.Option("--model", help="model file (default <store dir>/ranker.pkl)")
    ] = None,
) -> None:
    """Score the latest panel rows with the saved ranker and print the top symbols."""
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    ranker = _load_ranker(model or _ranker_path(settings))
    store = _open_store(settings)
    panel = _read_panel(store, settings, None, as_of_d)
    rows = _latest_rows(panel, as_of_d)
    scores = pd.Series(ranker.predict(rows))
    if len(scores) != len(rows):
        _fail(f"ranker returned {len(scores)} scores for {len(rows)} rows")
    frame = pd.DataFrame({"symbol": rows["symbol"].to_numpy(), "score": scores.to_numpy()})
    frame = frame.sort_values("score", ascending=False).head(top).reset_index(drop=True)
    _print_frame(f"Ranker scores as of {as_of_d}", frame, limit=top)


# ----------------------------------------------------------------------------------------------------------
# review / size / paper
# ----------------------------------------------------------------------------------------------------------
def _signals_for(settings: Settings, as_of: date, strategies: list[str] | None) -> list[Signal]:
    signals = _load_models(_run_file(settings, "signals", as_of), Signal)
    if signals:
        if strategies:
            signals = [s for s in signals if s.strategy in strategies]
        return sorted(signals, key=lambda s: s.score, reverse=True)  # cap keeps the best candidates
    names = strategies or _enabled_strategies(settings)
    store = _open_store(settings)
    panel = _read_panel(store, settings, None, as_of, names)
    return _run_scan(settings, panel, as_of, names)


def _render_review_prompt(signals: list[Signal], context: dict[str, Any], settings: Settings) -> str:
    for helper in ("agent.review.build_prompt", "agent.review.render_prompt"):
        fn = _try_load(helper)
        if fn is not None:
            rendered = _call_supported(fn, signals, context, settings=settings)
            return rendered if isinstance(rendered, str) else json.dumps(rendered, indent=2, default=str)
    prompt_path = Path(__file__).resolve().parent / REVIEW_SYSTEM_PROMPT
    system = (
        prompt_path.read_text() if prompt_path.exists() else f"(system prompt not found at {prompt_path})"
    )
    payload = {
        "as_of": signals[0].as_of.isoformat() if signals else None,
        "candidates": [s.model_dump(mode="json") for s in signals],
        "context_by_symbol": context,
    }
    return f"# SYSTEM ({settings.agent.review_model})\n{system}\n\n# USER\n{json.dumps(payload, indent=2)}"


@app.command()
def review(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    strategies: Annotated[list[str] | None, typer.Option("--strategies", "-s")] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="print the prompt that would be sent; no API call")
    ] = False,
    limit: Annotated[
        int | None, typer.Option("--limit", help="max candidates (default agent.max_candidates_per_day)")
    ] = None,
) -> None:
    """Run agent.review on today's scan. Reviews carry enums and text only, never prices or sizes."""
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    signals = _signals_for(settings, as_of_d, _split_list(strategies))
    cap = limit or settings.agent.max_candidates_per_day
    signals = signals[:cap]
    context = _load_json(_run_file(settings, "context", as_of_d), {})
    if not signals:
        _console().print(f"no signals for {as_of_d}; nothing to review")
        return
    if dry_run:
        _console().print(_render_review_prompt(signals, context, settings), markup=False, highlight=False)
        return
    secrets = load_secrets()
    if not secrets.anthropic_api_key:
        _fail("ANTHROPIC_API_KEY is not set; use --dry-run to see the prompt", EXIT_USAGE)
    review_candidates = _load("agent.review.review_candidates")
    reviews: list[Review] = list(
        _call_supported(
            review_candidates, signals, context, settings, client=_anthropic_client(secrets, async_client=True)
        )
    )
    table = Table(title=f"Reviews as of {as_of_d} ({len(reviews)})")
    for col in ("symbol", "strategy", "decision", "catalyst", "contradicted", "liquidity", "flags", "thesis"):
        table.add_column(col)
    for r in reviews:
        table.add_row(
            r.symbol,
            r.strategy,
            r.decision.value,
            str(r.catalyst_within_hold_window),
            str(r.news_contradicts_setup),
            str(r.liquidity_concern),
            _compact(r.event_risk_flags),
            _compact(r.thesis, THESIS_PREVIEW_CHARS),
        )
    _console().print(table)
    path = _save_models(_run_file(settings, "reviews", as_of_d), reviews)
    _console().print(f"saved {len(reviews)} reviews to {path}")


def _account_equity(account: dict[str, Any]) -> float | None:
    for key in EQUITY_ACCOUNT_KEYS:
        value = account.get(key)
        if value is not None:
            return float(value)
    return None


@app.command()
def size(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    equity: Annotated[
        float | None, typer.Option("--equity", help="account equity (default risk.account_equity_override)")
    ] = None,
    broker: Annotated[
        str | None, typer.Option("--broker", help="read equity and open positions from this broker")
    ] = None,
    ignore_reviews: Annotated[
        bool, typer.Option("--ignore-reviews", help="size every signal, not only approved ones")
    ] = False,
    save: Annotated[bool, typer.Option("--save/--no-save")] = True,
) -> None:
    """Turn saved Signals into OrderIntents with risk.sizing (deterministic; reviews only filter by decision)."""
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    signals = _load_models(_run_file(settings, "signals", as_of_d), Signal)
    if not signals:
        _fail(
            f"no saved signals for {as_of_d}; run `swing scan --as-of {as_of_d}` first"
            f"{_available_runs(settings, 'signals')}",
            EXIT_NO_DATA,
        )
    reviews = _load_models(_run_file(settings, "reviews", as_of_d), Review)
    if reviews and not ignore_reviews:
        approved = {
            (r.symbol, r.strategy) for r in reviews if r.decision is ReviewDecision.APPROVE_FOR_RISK_CHECK
        }
        signals = [s for s in signals if (s.symbol, s.strategy) in approved]
        log.info("filtered_by_reviews", approved=len(signals), reviewed=len(reviews))

    equity_value = equity if equity is not None else settings.risk.account_equity_override
    positions: list[Any] = []
    if broker:
        b = _make_broker(broker, settings, load_secrets())
        if equity_value is None:
            equity_value = _account_equity(dict(b.account()))
        positions = list(b.positions())
    if equity_value is None:
        _fail(
            "account equity unknown: pass --equity, set risk.account_equity_override, or --broker", EXIT_USAGE
        )

    size_detail = _try_load("risk.sizing.size_signal_detail")
    size_signal = None if size_detail is not None else _load("risk.sizing.size_signal")
    intents: list[OrderIntent] = []
    skipped: list[tuple[Signal, str]] = []
    for s in signals:
        if size_detail is not None:
            floor = _strategy_rr_floor(settings, s.strategy)
            extra = {"min_reward_risk": floor} if floor is not None else {}
            intent, reason = size_detail(s, equity_value, settings.risk, positions, **extra)
        else:
            intent, reason = size_signal(s, equity_value, settings.risk, positions), "rejected by risk.sizing"
        if intent is not None:
            intents.append(intent)
        else:
            skipped.append((s, str(reason)))
    table = Table(
        title=f"Order intents as of {as_of_d} ({len(intents)} of {len(signals)} signals; equity {equity_value:,.0f})"
    )
    for col in (
        "symbol",
        "side",
        "qty",
        "entry_limit",
        "stop",
        "target",
        "risk $",
        "strategy",
        "client_order_id",
    ):
        table.add_column(col)
    for i in intents:
        table.add_row(
            i.symbol,
            i.side.value,
            str(i.qty),
            _fmt(i.entry_limit),
            _fmt(i.stop),
            _fmt(i.target),
            _fmt(i.risk_dollars),
            i.strategy,
            i.client_order_id,
        )
    _console().print(table)
    if skipped:
        why = Table(title=f"Skipped by risk.sizing ({len(skipped)})")
        for col in ("symbol", "strategy", "reason"):
            why.add_column(col)
        for s, reason in skipped:
            why.add_row(s.symbol, s.strategy, escape(reason))
        _console().print(why)
    if save:
        path = _save_models(_run_file(settings, "intents", as_of_d), intents)
        _console().print(f"saved {len(intents)} intents to {path}")


@app.command()
def paper(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    approve: Annotated[
        str | None, typer.Option("--approve", help='human approver name, e.g. --approve "jane"; REQUIRED')
    ] = None,
    broker: Annotated[
        str, typer.Option("--broker", help="alpaca (paper) or paper_sim")
    ] = DEFAULT_PAPER_BROKER,
    reconcile: Annotated[
        bool, typer.Option("--reconcile", help="also run OrderManager.reconcile() afterwards")
    ] = False,
    from_intents: Annotated[
        bool,
        typer.Option("--from-intents", help="submit runs/intents/<date>.json even when a staged plan exists"),
    ] = False,
) -> None:
    """Submit saved OrderIntents through execution.OrderManager. Refuses without --approve NAME.

    When the autopilot staged a plan for the date (runs/pending/<date>.json: a live account without automatic
    approval), that plan is executed exactly (its exits, then its review-vetted and capped entries) through
    execution.autopilot.run_pending instead of the intents file; --from-intents overrides.
    """
    approver = (approve or "").strip()
    if len(approver) < MIN_APPROVER_LEN:
        _fail('refusing to submit orders: a human must approve with --approve "<your name>"', EXIT_REFUSED)
    settings = _state(ctx).settings
    secrets = load_secrets()
    as_of_d = _parse_date(as_of, date.today())
    if (
        broker == DEFAULT_PAPER_BROKER
        and not secrets.alpaca_paper
        and os.environ.get(LIVE_OVERRIDE_ENV) != LIVE_OVERRIDE_VALUE
    ):
        _fail(
            f"ALPACA_PAPER is false and {LIVE_OVERRIDE_ENV} != {LIVE_OVERRIDE_VALUE!r}; see docs/gates.md",
            EXIT_REFUSED,
        )
    pending_path = _run_file(settings, "pending", as_of_d)
    if pending_path.exists() and not from_intents:
        _paper_pending(settings, secrets, as_of_d, broker, approver, pending_path)
        return
    intents = _load_models(_run_file(settings, "intents", as_of_d), OrderIntent)
    if not intents:
        _fail(
            f"no saved intents for {as_of_d}; run `swing size --as-of {as_of_d}` first"
            f"{_available_runs(settings, 'intents')}",
            EXIT_NO_DATA,
        )

    kill_path = _resolve(settings.risk.kill_switch_file)
    is_tripped = _load("risk.killswitch.is_tripped")
    if is_tripped(str(kill_path)):
        _fail(f"kill switch tripped ({kill_path}); remove the file to resume", EXIT_REFUSED)

    b = _make_broker(broker, settings, secrets)
    limit_state = _load("risk.limits.LimitState")
    limits = _construct(
        limit_state,
        risk=settings.risk,
        risk_cfg=settings.risk,
        cfg=settings.risk,
        config=settings.risk,
        settings=settings,
        state_path=_resolve(settings.risk.limits_state_file),  # peak equity survives across daily runs
    )
    order_manager = _load("execution.order_manager.OrderManager")
    manager = order_manager(b, limits, str(kill_path))

    results: list[dict[str, Any]] = []
    for intent in intents:
        try:
            res = manager.submit(intent, approved_by=approver)
            results.append(
                {
                    "symbol": intent.symbol,
                    "qty": intent.qty,
                    "client_order_id": intent.client_order_id,
                    **dict(res or {}),
                }
            )
        except Exception as e:
            log.error("submit_failed", symbol=intent.symbol, error=str(e))
            results.append(
                {
                    "symbol": intent.symbol,
                    "qty": intent.qty,
                    "client_order_id": intent.client_order_id,
                    "status": "error",
                    "reason": str(e),
                }
            )
    _print_frame(f"Paper submissions via {broker} approved by {approver}", pd.DataFrame(results))
    path = _run_file(settings, "fills", as_of_d)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, default=str))
    _console().print(f"saved {len(results)} submission results to {path}")
    if reconcile:
        _print_any("Reconcile", manager.reconcile())


def _paper_pending(
    settings: Settings, secrets: Secrets, as_of_d: date, broker_name: str, approver: str, path: Path
) -> None:
    """Execute the autopilot's staged plan with a human approver (kill switch: only entry cancels run)."""
    load_pending = _load("execution.autopilot.load_pending")
    run_pending = _load("execution.autopilot.run_pending")
    intents, exits = load_pending(settings, as_of_d)
    _console().print(f"staged plan {path}: {len(exits)} exits, {len(intents)} entries (--from-intents to bypass)")
    plan = [{"kind": str(getattr(a.kind, "value", a.kind)), "symbol": a.symbol, "qty": a.qty,
             "new_stop": a.new_stop, "detail": a.detail} for a in exits]
    plan += [{"kind": "entry", "symbol": i.symbol, "qty": i.qty, "new_stop": i.stop, "detail": i.client_order_id}
             for i in intents]
    if plan:
        _print_frame("Staged plan", pd.DataFrame(plan))
    report = run_pending(settings, secrets, as_of_d, _make_broker(broker_name, settings, secrets), approver)
    results = [r.model_dump(mode="json") for r in [*report.exits, *report.entries]]
    mode = str(getattr(report.mode, "value", report.mode))
    if results:
        _print_frame(f"Staged plan via {broker_name} approved by {approver} ({mode})", pd.DataFrame(results))
    out = _run_file(settings, "fills", as_of_d)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str))
    _console().print(f"saved {len(results)} results to {out}")
    if mode == "aborted":
        _fail(f"staged plan not executed: {'; '.join(report.errors)}", EXIT_FAILED)
    if mode == "killed":
        _fail("kill switch tripped: only unfilled-entry cancels ran; remove the file to resume", EXIT_REFUSED)


# ----------------------------------------------------------------------------------------------------------
# monitor
# ----------------------------------------------------------------------------------------------------------
def _monitor_run(settings: Settings, dry_run: bool, feeds: list[str] | None) -> None:
    run_monitor = _load("monitor.service.run_monitor")
    log.info("monitor_start", dry_run=dry_run, feeds=feeds or settings.monitor.feeds)
    result = run_monitor(settings, load_secrets(), dry_run=dry_run, feeds=feeds)
    if inspect.isawaitable(result):
        asyncio.run(result)


@monitor_app.callback(invoke_without_command=True)
def monitor_main(
    ctx: typer.Context,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="(no subcommand) run the monitor without delivering alerts")
    ] = False,
) -> None:
    """`swing monitor --dry-run` is shorthand for `swing monitor run --dry-run`."""
    if ctx.invoked_subcommand is None:
        _monitor_run(_state(ctx).settings, dry_run, None)


@monitor_app.command("run")
def monitor_run(
    ctx: typer.Context,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="process feeds and log, but deliver nothing")
    ] = False,
    feeds: Annotated[
        list[str] | None, typer.Option("--feeds", "-f", help="repeat or comma-separate; default settings")
    ] = None,
) -> None:
    """Run the live monitor supervisor (feeds -> dedup -> rules -> classify -> alerts)."""
    _monitor_run(_state(ctx).settings, dry_run, _split_list(feeds))


@monitor_app.command("report")
def monitor_report(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = DEFAULT_MONITOR_REPORT_DAYS,
) -> None:
    """Alerts per rule/source, duplicate rate, latency and ratings over the last N days."""
    settings = _state(ctx).settings
    report = _load("monitor.report.report")
    event_log = str(_resolve(settings.data.event_log_path))
    _print_any(f"Monitor report, last {days} days", _call_supported(report, days, path=event_log))


@monitor_app.command("replay")
def monitor_replay(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days")] = DEFAULT_MONITOR_REPORT_DAYS,
    rules: Annotated[
        list[str] | None, typer.Option("--rules", "-r", help="repeat or comma-separate; default all")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run/--deliver", help="replay never delivers alerts by default")
    ] = True,
) -> None:
    """Re-run stage-1 rules over the logged events of the last N days (for threshold tuning)."""
    settings = _state(ctx).settings
    replay = _load("monitor.replay.replay")
    event_log = str(_resolve(settings.data.event_log_path))
    _print_any(
        f"Replay, last {days} days",
        _call_supported(replay, days, _split_list(rules), dry_run=dry_run, path=event_log),
    )


@monitor_app.command("rate")
def monitor_rate(
    ctx: typer.Context,
    event_id: Annotated[str, typer.Argument(help="event id of the alert (shown in the alert and the event log)")],
    rating: Annotated[str, typer.Argument(help="useful | noise | traded")],
) -> None:
    """Rate an alert (same as the Telegram Useful / Noise / Traded buttons; monitor.rate.rate_cli)."""
    settings = _state(ctx).settings
    rate_cli = _load("monitor.rate.rate_cli")
    try:
        result = rate_cli(settings, event_id, rating)
    except ValueError as e:  # not one of useful | noise | traded
        _fail(str(e), EXIT_USAGE)
    summary = result.summary() if hasattr(result, "summary") else str(result)
    if not getattr(result, "ok", False):
        code = EXIT_NO_DATA if getattr(result, "reason", None) == RATE_REASON_UNKNOWN_EVENT else EXIT_FAILED
        _fail(escape(summary), code)
    _console().print(escape(summary))


# ----------------------------------------------------------------------------------------------------------
# journal / trials
# ----------------------------------------------------------------------------------------------------------
@app.command()
def journal(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
) -> None:
    """Write the day's journal entry from saved signals, reviews, intents and fills (agent.journal)."""
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    signals = _load_models(_run_file(settings, "signals", as_of_d), Signal)
    reviews = _load_models(_run_file(settings, "reviews", as_of_d), Review)
    intents = _load_models(_run_file(settings, "intents", as_of_d), OrderIntent)
    fills = _load_json(_run_file(settings, "fills", as_of_d), [])
    write_entry = _load("agent.journal.write_entry")
    secrets = load_secrets()
    narrative = bool(secrets.anthropic_api_key) and settings.agent.llm_enabled  # prose needs the API
    client = _anthropic_client(secrets, async_client=False) if narrative else None
    out = _call_supported(
        write_entry, as_of_d, signals, reviews, intents, fills, settings=settings, narrative=narrative, client=client
    )
    _console().print(str(out), markup=False)


@app.command("notify-test")
def notify_test(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="print the message instead of sending it")] = False,
) -> None:
    """Send a short Telegram message to TELEGRAM_CHAT_ID to confirm nightly / research reports will arrive."""
    from swing_engine.ops import notify

    title, body = notify.ping_message(datetime.now().strftime("%Y-%m-%d %H:%M"))
    if dry_run:
        _console().print(escape(f"{title}\n{body}"), highlight=False)
        return
    why = notify.deliver(title, body, secrets=load_secrets())
    if why:
        _fail(f"not delivered: {why}")
    _console().print("sent")


@app.command("weekly-report")
def weekly_report(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
) -> None:
    """Write data/journal/weekly-<ISO week>.md: paper trades, shadow ledger, drift, rule-based recommendations."""
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    path = _store_path(settings)
    if not path.exists():
        _fail(f"store {path} does not exist; run `swing ingest` first", EXIT_NO_DATA)
    store = _load("data.store.Store")(str(path), read_only=True)
    try:
        out = _load("agent.weekly.write_report")(settings, as_of_d, store)
    finally:
        store.close()
    _console().print(f"wrote {out}")


@app.command()
def trials(
    ctx: typer.Context,
    name: Annotated[str | None, typer.Option("--name", "-n", help="only this strategy")] = None,
    last: Annotated[int, typer.Option("--last", help="rows to show (most recent)")] = DEFAULT_TRIALS_SHOWN,
    path: Annotated[Path | None, typer.Option("--path", help=f"trial log (default {TRIALS_PATH})")] = None,
) -> None:
    """List logged backtest trials; the count is what deflated Sharpe must be judged against."""
    _state(ctx)
    log_path = path or ROOT / TRIALS_PATH
    rows = _read_jsonl(log_path)
    if name:
        rows = [r for r in rows if r.get("name") == name]
    if not rows:
        _console().print(f"no trials logged{f' for {name}' if name else ''} in {log_path}")
        return
    per_name: dict[str, int] = {}
    for r in rows:
        per_name[str(r.get("name"))] = per_name.get(str(r.get("name")), 0) + 1
    table = Table(
        title=f"Trials in {escape(str(log_path))} (total {len(rows)}; by name: {_compact(per_name)})"
    )
    for col in ("#", "logged", "name", "params", *TRIAL_METRIC_KEYS):
        table.add_column(col)
    start_idx = max(len(rows) - last, 0)
    for idx, r in enumerate(rows[start_idx:], start=start_idx + 1):
        metrics = r.get("metrics") or {}
        logged = r.get("ts") or r.get("timestamp") or r.get("logged_at") or "-"
        if isinstance(logged, (int, float)):
            logged = datetime.fromtimestamp(logged).isoformat(timespec="seconds")
        table.add_row(
            str(idx),
            str(logged),
            str(r.get("name")),
            _compact(r.get("params") or {}),
            *[_fmt(metrics.get(k)) for k in TRIAL_METRIC_KEYS],
        )
    _console().print(table)


# ----------------------------------------------------------------------------------------------------------
# ops: doctor / nightly / monitor outcomes
# ----------------------------------------------------------------------------------------------------------
DEFAULT_OUTCOMES_DAYS = 30
CHECK_STYLES = {"ok": "green", "warn": "yellow", "fail": "bold red", "skip": "dim"}
STEP_STYLES = {"ok": "green", "fail": "bold red", "skip": "dim"}


def _status_text(value: Any, styles: dict[str, str]) -> Text:
    key = str(getattr(value, "value", value))
    return Text(key, style=styles.get(key, ""))


@app.command()
def dashboard(
    ctx: typer.Context,
    port: Annotated[int, typer.Option("--port", min=0, max=65535, help="port on 127.0.0.1")] = 8765,
    demo: Annotated[bool, typer.Option("--demo", help="serve deterministic fake data (no keys, no files)")] = False,
    open_browser: Annotated[bool, typer.Option("--open", help="open the default browser")] = False,
) -> None:
    """Local read-only dashboard on http://127.0.0.1:<port>/ (swing_engine.dashboard; never places orders)."""
    serve = _load("dashboard.serve")
    path = _state(ctx).settings_path
    try:
        serve(settings_path=str(path) if path else None, port=port, demo=demo, open_browser=open_browser)
    except OSError as exc:
        _fail(f"could not start the dashboard on 127.0.0.1:{port}: {exc}")


@app.command()
def doctor(
    ctx: typer.Context,
    live: Annotated[
        bool, typer.Option("--live", help="also probe each vendor whose key is set (one cheap request each)")
    ] = False,
    send_test: Annotated[
        bool, typer.Option("--send-test", help="with --live: send a test message to TELEGRAM_CHAT_ID")
    ] = False,
) -> None:
    """Pre-flight checks: .env keys, settings, store, calendar, plugins, kill switch, versions (ops.doctor).

    Exit code 1 when any check fails. Secret values are never printed.
    """
    if send_test and not live:
        _fail("--send-test only makes sense together with --live", EXIT_USAGE)
    st = _state(ctx)
    run_doctor = _load("ops.doctor.run_doctor")
    checks = list(
        _call_supported(
            run_doctor, st.settings, load_secrets(), live, send_test=send_test, settings_path=st.settings_path
        )
    )
    table = Table(title=f"swing doctor ({'offline + live' if live else 'offline'})")
    table.add_column("check", style="cyan")
    table.add_column("status")
    table.add_column("detail")
    counts: dict[str, int] = {}
    for check in checks:
        status = str(getattr(check.status, "value", check.status))
        counts[status] = counts.get(status, 0) + 1
        table.add_row(escape(check.name), _status_text(status, CHECK_STYLES), escape(str(check.detail)))
    _console().print(table)
    _console().print(", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if counts.get("fail"):
        raise typer.Exit(EXIT_FAILED)


def _open_execution_broker(name: str, settings: Settings, secrets: Secrets) -> Any:
    """Build the broker the nightly / autopilot reads and trades; a live session without the override is refused."""
    try:
        return _make_broker(name, settings, secrets)
    except typer.Exit:
        raise
    except Exception as e:
        code = EXIT_REFUSED if type(e).__name__ == "LiveTradingBlocked" else EXIT_USAGE
        _fail(f"could not open broker {name!r}: {type(e).__name__}: {e}", code)


def _print_step_report(title: str, report: Any) -> list[str]:
    """Steps table plus written files; returns the names of failed steps."""
    steps = list(getattr(report, "steps", []) or [])
    table = Table(title=title)
    for col in ("step", "status", "seconds", "detail"):
        table.add_column(col)
    for step in steps:
        table.add_row(
            escape(str(step.name)),
            _status_text(step.status, STEP_STYLES),
            f"{float(step.elapsed_s):.2f}",
            escape(str(step.detail)),
        )
    _console().print(table)
    files = dict(getattr(report, "files", {}) or {})
    report_path = getattr(report, "report_path", None)
    if files or report_path:
        _print_mapping("Files written", {**files, "report": report_path})
    regime_payload = getattr(report, "regime", None)
    if isinstance(regime_payload, dict) and regime_payload:
        allowed = regime_payload.get("allowed")
        _print_mapping("Market regime", {
            "regime": regime_payload.get("regime"),
            "allowed (risk multiplier)": "unrouted" if allowed is None else
            (", ".join(f"{k} x{float(v):g}" for k, v in allowed.items()) or "none: no new entries"),
            "blocked": ", ".join(sorted(regime_payload.get("blocked") or {})) or "-",
        })  # fmt: skip
    return [str(s.name) for s in steps if str(getattr(s.status, "value", s.status)) == "fail"]


@app.command()
def nightly(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    provider: Annotated[
        str | None, typer.Option("--provider", "-p", help="bar provider (default settings.data.bar_provider)")
    ] = None,
    equity: Annotated[
        float | None,
        typer.Option("--equity", help="account equity for sizing (default: the broker's, else risk.account_equity_override)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="skip the Claude calls and never execute; data steps still run"),
    ] = False,
    broker: Annotated[
        str | None,
        typer.Option("--broker", help="alpaca | paper_sim: equity, positions and the execute step (default execution.broker)"),
    ] = None,
    execute: Annotated[
        bool | None,
        typer.Option("--execute/--no-execute", help="run positions -> execute via execution.autopilot "
                     "(default execution.nightly_execute; never with --dry-run)"),
    ] = None,
) -> None:
    """Ingest -> features -> scan -> rank -> size -> review -> shadow -> positions -> execute -> journal (ops.nightly).

    The scan runs only the strategies the playbook allows in today's market regime (runs/regime/<date>.json)
    and the size step scales each one's risk by its multiplier; `swing regime` shows the same decision.

    Writes runs/nightly/<date>.json next to the other run files. Orders leave only through the execute step
    (execution.autopilot: automatic approval on a paper broker only). Exit code 1 when a step failed.
    """
    settings = _state(ctx).settings
    secrets = load_secrets()
    as_of_d = _parse_date(as_of, date.today())
    provider_name = provider or settings.data.bar_provider
    broker_name = broker or settings.execution.broker
    execute_flag = settings.execution.nightly_execute if execute is None else execute
    run_nightly = _load("ops.nightly.run_nightly")
    b: Any | None = None
    broker_error: tuple[str, int] | None = None
    if broker_name:
        try:  # a broken broker must not stop the data steps; it fails the run afterwards instead
            b = _open_execution_broker(broker_name, settings, secrets)
        except typer.Exit as e:
            broker_error = (f"broker {broker_name!r} unavailable; positions/execute were skipped", int(e.exit_code))
    report = _call_supported(
        run_nightly, settings, secrets, as_of_d, provider_name, equity, dry_run, broker=b, execute=execute_flag
    )
    mode = " (dry run)" if dry_run else (f", execute via {broker_name}" if execute_flag and b is not None else "")
    failed = _print_step_report(f"Nightly {as_of_d} via {provider_name}{mode}", report)
    report_path = getattr(report, "report_path", None)
    if failed:
        _fail(f"nightly finished with failed steps: {', '.join(failed)} (see {report_path})", EXIT_FAILED)
    if broker_error is not None and execute_flag and not dry_run:
        _fail(broker_error[0], broker_error[1])


@app.command()
def autopilot(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
    broker: Annotated[
        str | None, typer.Option("--broker", help="alpaca | paper_sim (default execution.broker)")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="reconcile and plan only; nothing reaches the broker")
    ] = False,
) -> None:
    """Size -> positions -> execute from the latest saved signals (ops.nightly.run_cycle, execution.autopilot).

    Orders are approved automatically only on a paper broker (alpaca with ALPACA_PAPER=true, or paper_sim) as
    'autopilot:paper'. A live account stages its plan to runs/pending/<date>.json; `swing paper --approve NAME
    --as-of <date>` executes exactly that plan.
    The kill switch, risk limits, review vetoes and execution.max_new_orders_per_day always apply.
    """
    settings = _state(ctx).settings
    secrets = load_secrets()
    as_of_d = _parse_date(as_of, date.today())
    broker_name = broker or settings.execution.broker
    if not broker_name:
        _fail("no broker: pass --broker alpaca|paper_sim or set execution.broker in settings.yaml", EXIT_USAGE)
    run_cycle = _load("ops.nightly.run_cycle")
    b = _open_execution_broker(broker_name, settings, secrets)
    report = run_cycle(settings, secrets, as_of_d, b, dry_run)
    failed = _print_step_report(f"Autopilot {as_of_d} via {broker_name}{' (dry run)' if dry_run else ''}", report)
    execute_step = report.step("execute") if hasattr(report, "step") else None
    if execute_step is not None and execute_step.data:
        _print_mapping("Autopilot", dict(execute_step.data))
    if failed:
        _fail(f"autopilot finished with failed steps: {', '.join(failed)} (see {report.report_path})", EXIT_FAILED)


# ----------------------------------------------------------------------------------------------------------
# regime / replay / shadow (strategies.playbook, research.replay, research.shadow)
# ----------------------------------------------------------------------------------------------------------
def _jsonable(obj: Any) -> Any:
    """JSON-ready form of replay output: frames/series become records, models dicts, the rest via str()."""
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        frame = obj.reset_index() if not isinstance(obj.index, pd.RangeIndex) else obj
        return json.loads(frame.to_json(orient="records", date_format="iso"))
    if isinstance(obj, pd.Series):
        return _jsonable(obj.rename(obj.name or "value").to_frame())
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return json.loads(json.dumps(obj, default=str))


def _as_frame(obj: Any) -> pd.DataFrame | None:
    if obj is None:
        return None
    if isinstance(obj, pd.DataFrame):
        return obj.reset_index() if not isinstance(obj.index, pd.RangeIndex) else obj
    if isinstance(obj, dict):
        return pd.DataFrame([{"key": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in obj.items()])
    return pd.DataFrame(obj)


@app.command()
def regime(
    ctx: typer.Context,
    as_of: Annotated[str | None, typer.Option("--as-of", help="YYYY-MM-DD (default: today)")] = None,
) -> None:
    """Market state for a date (strategies.playbook.market_state) and the strategies the playbook allows.

    Breadth is computed over the screened universe in the cached panel, like the nightly scan step. Prints the
    risk multiplier the size step would apply to each allowed strategy (risk.risk_per_trade_pct x multiplier).
    """
    settings = _state(ctx).settings
    as_of_d = _parse_date(as_of, date.today())
    compute_regime = _load("ops.nightly.compute_regime")
    screened_breadth = _load("ops.nightly.screened_breadth")
    _load("strategies.playbook.market_state")  # exit with a clear message before any work when it is missing
    store = _open_store(settings)
    panel = _read_panel(store, settings, None, as_of_d)
    listing = _store_listing(store)
    universe = _universe_window(listing, settings, [as_of_d], bars=panel) if listing is not None else None
    store_splits = _try_load("ops.nightly._store_splits")
    breadth, breadth_note = screened_breadth(panel, universe, store_splits(store) if store_splits else None)
    if breadth_note:
        Console(stderr=True).print(f"[yellow]breadth: {escape(breadth_note)}; the playbook computes its own[/yellow]")
    state, payload, note = compute_regime(settings, panel, as_of_d, breadth=breadth)
    if state is None or payload is None:
        _fail(note or "market state unavailable", EXIT_MISSING_MODULE)
    fields = dict(payload.get("market_state") or {})
    notes = fields.pop("notes", []) or []
    _print_mapping(f"Market state as of {as_of_d}", {**fields, "universe": len(universe) if universe else "-"})
    for line in notes:
        _console().print(f"  - {escape(str(line))}")
    if "allowed" not in payload:
        _fail(f"strategy routing unavailable: {note}", EXIT_MISSING_MODULE)
    table = Table(title=f"Strategies in regime {escape(str(payload.get('regime')))}")
    for col in ("strategy", "status", "multiplier", "risk % per trade", "reason"):
        table.add_column(col)
    base = settings.risk.risk_per_trade_pct
    for name, mult in payload["allowed"].items():
        table.add_row(escape(name), Text("allowed", style="green"), f"{mult:g}", f"{base * mult:.2f}", "")
    for name, reason in payload["blocked"].items():
        table.add_row(escape(name), Text("blocked", style="dim"), "0", "0.00", escape(reason))
    _console().print(table)


@app.command()
def replay(
    ctx: typer.Context,
    start: Annotated[str, typer.Option("--start", help="YYYY-MM-DD first session")],
    end: Annotated[str | None, typer.Option("--end", help="YYYY-MM-DD last session (default: today)")] = None,
    strategies: Annotated[
        list[str] | None, typer.Option("--strategies", "-s", help="repeat or comma-separate (default: enabled)")
    ] = None,
    no_router: Annotated[
        bool, typer.Option("--no-router", help="run every strategy every day at full risk (no playbook routing)")
    ] = False,
    equity: Annotated[float, typer.Option("--equity", help="starting equity")] = DEFAULT_REPLAY_EQUITY,
    tag: Annotated[
        str | None, typer.Option("--tag", help="suffix for the saved file (runs/replay/<start>_<end>_<tag>.json)")
    ] = None,
    cost: Annotated[
        list[str] | None, typer.Option("--cost", help="CostModel field override k=v (repeatable)")
    ] = None,
) -> None:
    """Day-by-day portfolio replay of the live pipeline (research.replay.run_replay): market state -> allowed
    strategies -> signals -> sizing -> next-open fills -> exits, logged as one trial.

    Prints the summary, by-strategy and by-regime tables and saves runs/replay/<start>_<end>.json. Its signals
    are graded into the `shadow_signals_replay` table (`swing shadow report --replay`), never the live ledger.
    Opens the DuckDB store for writing: do not run it while the nightly or an ingest is running.
    """
    settings = _state(ctx).settings
    start_d = _parse_date(start)
    end_d = _parse_date(end, date.today())
    if start_d is None or end_d is None or start_d > end_d:
        _fail(f"--start {start_d} must be on or before --end {end_d}", EXIT_USAGE)
    run_replay = _load("research.replay.run_replay")
    costs = _load("research.backtest.CostModel")(**_parse_params(cost)) if cost else None
    names = _split_list(strategies)
    store = _open_store(settings)
    log.info("replay_start", start=str(start_d), end=str(end_d), strategies=names, router=not no_router)
    result = _call_supported(
        run_replay, settings, store, start_d, end_d, strategies=names, use_router=not no_router, equity=equity,
        costs=costs, shadow_table=REPLAY_SHADOW_TABLE,
    )
    summary = dict(getattr(result, "summary", None) or {})
    _print_mapping(
        f"Replay {start_d}..{end_d} ({'playbook router' if not no_router else 'no router'})",
        {"strategies": ", ".join(names) if names else "enabled", "equity": equity, **summary},
    )
    for title, attr in (("By strategy", "by_strategy"), ("By regime", "by_regime")):
        frame = _as_frame(getattr(result, attr, None))
        if frame is None or frame.empty:
            _console().print(f"{title}: (no trades)")
        else:
            _print_frame(title, frame)
    payload = {
        "start": start_d.isoformat(), "end": end_d.isoformat(), "strategies": names, "use_router": not no_router,
        "equity": equity, "summary": _jsonable(summary),
        **{attr: _jsonable(getattr(result, attr, None))
           for attr in ("by_strategy", "by_regime", "trades", "equity_curve", "daily")},
    }
    stem = f"{start_d.isoformat()}_{end_d.isoformat()}" + (f"_{tag}" if tag else "")
    path = _store_path(settings).parent / RUNS_DIRNAME / REPLAY_KIND / f"{stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    _console().print(f"saved replay to {path}")


@shadow_app.command("report")
def shadow_report(
    ctx: typer.Context,
    since: Annotated[str | None, typer.Option("--since", help="YYYY-MM-DD: only signals on or after")] = None,
    by: Annotated[str, typer.Option("--by", help="comma-separated group columns")] = SHADOW_GROUP_BY,
    horizon: Annotated[
        int | None, typer.Option("--horizon", help="grade at this horizon in sessions (default: the longest)")
    ] = None,
    taken: Annotated[
        bool | None, typer.Option("--taken/--untaken", help="only signals the engine took / passed on")
    ] = None,
    replay_rows: Annotated[
        bool, typer.Option("--replay", help=f"report the `swing replay` ledger ({REPLAY_SHADOW_TABLE})")
    ] = False,
    all_columns: Annotated[bool, typer.Option("--all-columns", help="print every statistic column")] = False,
) -> None:
    """Win rate, average R, expectancy and profit factor of graded shadow signals per group (the nightly's
    shadow step records every signal and grades it at 5/10/20 sessions on daily bars, stop-first)."""
    settings = _state(ctx).settings
    since_d = _parse_date(since)
    group_by = tuple(_split_list([by]) or [])
    if not group_by:
        raise typer.BadParameter("--by needs at least one column, e.g. strategy,regime")
    report_fn = _load("research.shadow.shadow_report")
    store = _open_store(settings)
    extra: dict[str, Any] = {k: v for k, v in {"horizon": horizon, "taken": taken}.items() if v is not None}
    if replay_rows:
        extra["table"] = REPLAY_SHADOW_TABLE
    frame = _call_supported(report_fn, store, since=since_d, group_by=group_by, **extra)
    if frame is None or len(frame) == 0:
        _console().print(f"no graded shadow signals{f' since {since_d}' if since_d else ''}")
        return
    table = _as_frame(frame)
    if not all_columns:
        keep = [c for c in table.columns if c in group_by or c in SHADOW_REPORT_COLUMNS]
        table = table[keep] if any(c in SHADOW_REPORT_COLUMNS for c in keep) else table
    _print_frame(f"Shadow signals by {', '.join(group_by)}{f' since {since_d}' if since_d else ''}", table)


@monitor_app.command("outcomes")
def monitor_outcomes(
    ctx: typer.Context,
    days: Annotated[int, typer.Option("--days", help="look-back window in days")] = DEFAULT_OUTCOMES_DAYS,
) -> None:
    """Forward outcomes of recent alerts (monitor.outcomes.compute_outcomes); prints whatever columns it returns."""
    settings = _state(ctx).settings
    compute_outcomes = _load("monitor.outcomes.compute_outcomes")
    frame = _call_supported(compute_outcomes, settings, days)
    if frame is None or len(frame) == 0:
        _console().print(f"no alert outcomes in the last {days} days")
        return
    _print_frame(f"Alert outcomes, last {days} days", pd.DataFrame(frame))


if __name__ == "__main__":  # pragma: no cover
    app()
