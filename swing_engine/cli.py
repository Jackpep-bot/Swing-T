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

DAYS_PER_YEAR = 365
PANEL_WARMUP_CALENDAR_DAYS = 400  # covers sma_200 / mom_12_1 (252 trading days) before `start`
DEFAULT_RANK_HORIZON = 10
DEFAULT_TOP_N = 25
DEFAULT_MONITOR_REPORT_DAYS = 7
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
app.add_typer(rank_app, name="rank")
app.add_typer(monitor_app, name="monitor")


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


def _read_panel(store: Any, settings: Settings, start: date | None, end: date | None) -> pd.DataFrame:
    """Cached `panel` table when present, else build it from bars on the fly."""
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
    names = [n for n, cfg in settings.strategies.items() if (cfg or {}).get("enabled", True)]
    if names:
        return names
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
) -> None:
    """Fetch daily bars through a provider into the DuckDB store (data.ingest.run_ingest)."""
    settings = _state(ctx).settings
    secrets = load_secrets()
    provider_name = provider or settings.data.bar_provider
    end_d = _parse_date(end, date.today())
    start_d = _parse_date(start, _default_start(settings, end_d))
    run_ingest = _load("data.ingest.run_ingest")
    store = _open_store(settings, must_exist=False)
    log.info("ingest_start", provider=provider_name, start=str(start_d), end=str(end_d))
    result = _call_supported(
        run_ingest, settings, secrets, provider_name, _split_list(symbols), start_d, end_d, store, full=full
    )
    _print_mapping(f"Ingest via {provider_name}", dict(result or {}))


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
    panel = _read_panel(store, settings, None, as_of_d)
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


def _panel_from_provider(
    name: str, settings: Settings, secrets: Secrets, symbols: list[str] | None, start: date, end: date
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
    return build_panel(bars, market), market


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

    if provider:
        panel, market = _panel_from_provider(
            provider, settings, secrets, _split_list(symbols), start_d, end_d
        )
    else:
        store = _open_store(settings)
        panel = _read_panel(store, settings, start_d - timedelta(days=PANEL_WARMUP_CALENDAR_DAYS), end_d)
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
        market=market, sizer=sizer, universe_at=universe_at,
    )
    metrics = dict(summarize(result))
    if not no_log:
        log_trial(strategy, dict(strat.params), metrics)
    n_trials = int(trial_count(strategy) or 0)
    n_obs, skew, kurt = _returns_moments(result, metrics)
    sharpe = float(metrics.get("sharpe") or 0.0)
    deflated = deflated_sharpe(sharpe, max(n_trials, 1), n_obs, skew, kurt) if n_obs else None

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
            "trials logged in total": int(trial_count(None) or 0),
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
    panel = _read_panel(store, settings, None, as_of)
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
    if not load_secrets().anthropic_api_key:
        _fail("ANTHROPIC_API_KEY is not set; use --dry-run to see the prompt", EXIT_USAGE)
    review_candidates = _load("agent.review.review_candidates")
    reviews: list[Review] = list(review_candidates(signals, context, settings))
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
) -> None:
    """Submit saved OrderIntents through execution.OrderManager. Refuses without --approve NAME."""
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
    narrative = bool(load_secrets().anthropic_api_key)  # tables only when no key; prose needs the API
    out = _call_supported(
        write_entry, as_of_d, signals, reviews, intents, fills, settings=settings, narrative=narrative
    )
    _console().print(str(out), markup=False)


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


if __name__ == "__main__":  # pragma: no cover
    app()
