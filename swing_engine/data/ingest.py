"""Nightly ingest: provider -> normalized bars -> DuckDB store (plus a `symbols` reference table).

Modes (`run_ingest(..., mode=)`):

* ``symbols``: per-symbol fetches. Incremental by default: each symbol is fetched from its last stored session
  minus a small overlap (late corrections and the current partial day get overwritten by the upsert);
  `full=True` refetches everything. With explicit symbols the provider's full reference list is never paged:
  metadata comes from `provider.symbol_details` only for names the `symbols` table does not know yet
  (providers without that method fall back to their `list_symbols`, which is cheap for them).
* ``grouped``: one call per NYSE session for the whole US market (`provider.grouped_daily`). Sessions in
  [start, end] are walked newest first; sessions already ingested are skipped (resumable), each session is
  written as soon as it arrives (an interrupted backfill keeps its progress), progress is logged every
  `GROUPED_PROGRESS_EVERY_DAYS` sessions, and the walk stops at the plan's history limit (HTTP 403 on a
  session older than one that worked). Afterwards split-adjusted history is repaired for names that split
  since the last check, and the `symbols` table is refreshed from `provider.universe_reference` (cached on
  disk for a week). An incremental nightly run costs one call per missing session plus one splits call.
* ``auto`` (default): ``grouped`` when the provider has `grouped_daily` and neither `symbols` nor
  `universe.static_symbols` is given; ``symbols`` otherwise.
"""
from __future__ import annotations

import inspect
import time
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import Any

import pandas as pd
import structlog

from swing_engine.core import registry
from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import BarProvider

from ._common import TZ, as_date, normalize_symbols, session_ts
from ._http import redact_secrets
from .calendar import trading_days
from .store import BARS_TABLE, Store
from .universe import SPLITS_TABLE

log = structlog.get_logger(__name__)

SYMBOLS_TABLE = "symbols"
SYMBOLS_KEYS = ["symbol"]
#: explicit column types: DuckDB would type an all-NULL column (e.g. `delisted_at` of active names) INTEGER
SYMBOLS_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR",
    "name": "VARCHAR",
    "exchange": "VARCHAR",
    "type": "VARCHAR",
    "active": "BOOLEAN",
    "listed_at": "DATE",
    "delisted_at": "DATE",
}
#: ledger of sessions ingested in grouped mode (what makes a grouped backfill resumable)
GROUPED_DAYS_TABLE = "ingest_grouped_days"
GROUPED_DAYS_KEYS = ["session"]
GROUPED_DAYS_SCHEMA: dict[str, str] = {"session": "DATE", "symbols": "BIGINT", "provider": "VARCHAR", "fetched_on": "DATE"}
INGEST_META_TABLE = "ingest_meta"
INGEST_META_KEYS = ["key"]
INGEST_META_SCHEMA: dict[str, str] = {"key": "VARCHAR", "value": "VARCHAR"}
SPLIT_CHECK_META = "{provider}:split_check"  # date of the last split repair
PLAN_FLOOR_META = "{provider}:plan_floor"  # newest session the plan refused (history limit); older ones are skipped

INGEST_CHUNK_SYMBOLS = 50
INGEST_OVERLAP_DAYS = 5
DAYS_PER_YEAR = 365
MODE_AUTO, MODE_SYMBOLS, MODE_GROUPED = "auto", "symbols", "grouped"
MODES = (MODE_AUTO, MODE_SYMBOLS, MODE_GROUPED)
GROUPED_PROGRESS_EVERY_DAYS = 10
#: a session with at least this many stored symbols counts as ingested even without a ledger row
#: (e.g. bars imported from Parquet); a few hand-picked symbols never do
GROUPED_PRESENT_MIN_SYMBOLS = 2000
LARGE_BACKFILL_DAYS = 20  # at or above this many sessions the time estimate is a warning (visible by default)
GROUPED_MAX_CONSECUTIVE_ERRORS = 3  # e.g. a bad key: stop instead of burning hours of quota
HTTP_FORBIDDEN = 403
SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0

Progress = Callable[[str], None]


def _now_et() -> pd.Timestamp:
    return pd.Timestamp.now(tz=TZ)


def _today() -> date:
    """Today's date in America/New_York (a Pacific-time Mac must not think the session is over at 21:00 ET)."""
    return _now_et().date()


SESSION_FINAL_ET = (20, 15)  # after-hours ends 20:00 ET; daily aggregates are treated as final 15 minutes later


def session_is_final(d: date) -> bool:
    """True when session ``d`` is over and its daily bar will not change. Today's session counts as final only
    after SESSION_FINAL_ET on today's ET clock; a partial bar is written but never ledgered, so the next run
    re-fetches it (finding: a mid-session ingest froze a truncated close and volume forever)."""
    today = _today()
    if d < today:
        return True
    if d > today:
        return False
    now = _now_et()
    return now.date() == today and (now.hour, now.minute) >= SESSION_FINAL_ET


def _provider_class(provider_name: str) -> type[BarProvider]:
    """Registry lookup. If a foreign plugin package fails to import during discovery, fall back to the
    providers that live in this package so ingest keeps working."""
    try:
        return registry.get("bar_provider", provider_name)
    except KeyError:
        raise
    except Exception as exc:  # pragma: no cover - depends on sibling packages
        log.warning("registry_discover_failed", error=str(exc))
        from . import alpaca, eodhd, massive, sample

        local = {
            sample.SampleProvider.name: sample.SampleProvider,
            massive.MassiveProvider.name: massive.MassiveProvider,
            eodhd.EodhdProvider.name: eodhd.EodhdProvider,
            alpaca.AlpacaProvider.name: alpaca.AlpacaProvider,
        }
        if provider_name not in local:
            raise KeyError(f"No bar_provider named {provider_name!r}") from exc
        return local[provider_name]


def make_provider(provider_name: str, settings: Settings, secrets: Secrets) -> BarProvider:
    cls = _provider_class(provider_name)
    factory = getattr(cls, "from_settings", None)
    if factory is None:
        return cls()  # type: ignore[call-arg]
    return factory(settings, secrets)


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ---------------------------------------------------------------------------------------------- helpers
def resolve_mode(mode: str, provider: BarProvider, symbols: Iterable[str] | None, settings: Settings) -> str:
    """The concrete mode (`symbols` or `grouped`) for a requested `mode`."""
    if mode not in MODES:
        raise ValueError(f"ingest mode must be one of {MODES}, got {mode!r}")
    can_group = callable(getattr(provider, "grouped_daily", None))
    named = symbols is not None or bool(settings.universe.static_symbols)
    if mode == MODE_GROUPED:
        if not can_group:
            raise ValueError(f"provider {getattr(provider, 'name', provider)!r} has no grouped-daily endpoint")
        if symbols is not None:
            raise ValueError("mode='grouped' ingests every US ticker per session; drop the symbol list")
        return MODE_GROUPED
    if mode == MODE_AUTO and can_group and not named:
        return MODE_GROUPED
    return MODE_SYMBOLS


def estimate_backfill_seconds(calls: int, calls_per_min: float | None) -> float | None:
    """Rough wall time for `calls` rate-limited requests (free tier: 12 s each); None when the rate is unknown."""
    if not calls_per_min or calls_per_min <= 0:
        return None
    return calls * SECONDS_PER_MINUTE / float(calls_per_min)


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    hours, rest = divmod(int(round(seconds)), int(SECONDS_PER_HOUR))
    minutes, secs = divmod(rest, int(SECONDS_PER_MINUTE))
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {secs:02d}s"


def _say(progress: Progress | None, level: str, event: str, message: str, **fields: Any) -> None:
    getattr(log, level)(event, **fields)
    if progress is not None:
        progress(message)


def _status_code(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _accepts(fn: Callable[..., Any], kwarg: str) -> bool:
    try:
        return kwarg in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def write_symbols(st: Store, frame: pd.DataFrame) -> int:
    """Upsert reference rows into the `symbols` table with explicit column types."""
    frame = normalize_symbols(frame)
    if frame.empty:
        return 0
    schema = dict(SYMBOLS_SCHEMA)
    for col in frame.columns:
        if col in schema:
            continue
        series = frame[col]
        if pd.api.types.is_bool_dtype(series):
            schema[col] = "BOOLEAN"
        elif pd.api.types.is_integer_dtype(series):
            schema[col] = "BIGINT"
        elif pd.api.types.is_float_dtype(series):
            schema[col] = "DOUBLE"
        else:
            schema[col] = "VARCHAR"
            frame[col] = series.map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    return st.write_table(SYMBOLS_TABLE, frame, SYMBOLS_KEYS, schema=schema)


def _known_symbols(st: Store) -> set[str]:
    if not st.has_table(SYMBOLS_TABLE):
        return set()
    rows = st.sql(f"SELECT symbol FROM {SYMBOLS_TABLE}")
    return set(rows["symbol"].astype(str)) if not rows.empty else set()


def _meta_get(st: Store, key: str) -> str | None:
    if not st.has_table(INGEST_META_TABLE):
        return None
    rows = st.read_table(INGEST_META_TABLE, "key = ?", [key])
    return None if rows.empty else str(rows["value"].iloc[0])


def _meta_set(st: Store, key: str, value: str) -> None:
    st.write_table(INGEST_META_TABLE, pd.DataFrame({"key": [key], "value": [value]}), INGEST_META_KEYS, schema=INGEST_META_SCHEMA)


def grouped_days_present(st: Store, start: date, end: date) -> set[date]:
    """Sessions in [start, end] already ingested: in the grouped ledger, or holding at least
    `GROUPED_PRESENT_MIN_SYMBOLS` stored symbols (a handful of `--symbols` names never counts)."""
    present: set[date] = set()
    if st.has_table(GROUPED_DAYS_TABLE):
        rows = st.read_table(GROUPED_DAYS_TABLE, "session >= ? AND session <= ?", [start, end])
        present.update(as_date(v) for v in rows.get("session", []))
    if st.has_table(BARS_TABLE):
        dense = st.sql(
            f"SELECT ts FROM {BARS_TABLE} WHERE ts >= ? AND ts < ? GROUP BY ts HAVING count(*) >= ?",
            [session_ts(start).to_pydatetime(), (session_ts(end) + timedelta(days=1)).to_pydatetime(),
             GROUPED_PRESENT_MIN_SYMBOLS],
        )
        if not dense.empty:
            present.update(pd.to_datetime(dense["ts"], utc=True).dt.tz_convert(TZ).dt.date)
    return {d for d in present if session_is_final(d)}  # an unfinished session is never "present"


def _ledger_first_fetch(st: Store, provider: str) -> date | None:
    if not st.has_table(GROUPED_DAYS_TABLE):
        return None
    rows = st.sql(f"SELECT min(fetched_on) AS first FROM {GROUPED_DAYS_TABLE} WHERE provider = ?", [provider])
    value = None if rows.empty else rows["first"].iloc[0]
    return None if value is None or pd.isna(value) else as_date(value)


def _record_session(st: Store, session: date, n_symbols: int, provider: str, fetched_on: date) -> None:
    row = pd.DataFrame(
        {"session": [session], "symbols": [int(n_symbols)], "provider": [provider], "fetched_on": [fetched_on]}
    )
    st.write_table(GROUPED_DAYS_TABLE, row, GROUPED_DAYS_KEYS, schema=GROUPED_DAYS_SCHEMA)


# ---------------------------------------------------------------------------------------------- symbols mode
def _reference_for(prov: BarProvider, st: Store, wanted: list[str]) -> pd.DataFrame:
    """Reference rows for explicitly requested names without paging the provider's whole list."""
    details = getattr(prov, "symbol_details", None)
    if not callable(details):
        return normalize_symbols(prov.list_symbols(include_delisted=True))
    unknown = sorted(set(wanted) - _known_symbols(st))
    if not unknown:
        return normalize_symbols(pd.DataFrame())
    try:
        return normalize_symbols(details(unknown))
    except Exception as exc:  # metadata is optional: bars still ingest
        log.warning("ingest_symbol_details_failed", symbols=unknown[:3], error=redact_secrets(str(exc)))
        return normalize_symbols(pd.DataFrame())


def _ingest_symbols(
    prov: BarProvider, st: Store, settings: Settings, name: str, symbols: Iterable[str] | None,
    start_d: date, end_d: date, *, full: bool,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    if symbols is not None or settings.universe.static_symbols:
        source = symbols if symbols is not None else settings.universe.static_symbols
        wanted = sorted({s.upper() for s in source})
        listing = _reference_for(prov, st, wanted)
    else:
        listing = normalize_symbols(prov.list_symbols(include_delisted=True))
        wanted = listing["symbol"].tolist()
    if not listing.empty:
        try:
            write_symbols(st, listing)
        except Exception as exc:  # e.g. a symbols table created with other column types; bars still ingest
            log.warning("ingest_symbols_write_failed", provider=name, error=str(exc))

    last_dates = {} if full else st.last_bar_dates()
    bars_written = 0
    symbols_with_bars: set[str] = set()
    for chunk in _chunks(wanted, INGEST_CHUNK_SYMBOLS):
        # the chunk starts at the earliest per-symbol resume point; the upsert makes overlap harmless
        resume = [max(start_d, last_dates[s] - timedelta(days=INGEST_OVERLAP_DAYS)) for s in chunk if s in last_dates]
        chunk_start = min(resume) if len(resume) == len(chunk) else start_d
        if chunk_start > end_d:
            continue
        try:
            bars = prov.daily_bars(chunk, chunk_start, end_d)
        except Exception as exc:
            error = redact_secrets(str(exc))  # vendor errors echo the request URL, API key included
            log.error("ingest_chunk_failed", provider=name, symbols=chunk[:3], error=error)
            errors.append({"symbols": ",".join(chunk), "error": error})
            continue
        if bars is None or bars.empty:
            continue
        bars_written += st.write_bars(bars)
        symbols_with_bars.update(bars["symbol"].unique().tolist())
    return {
        "provider": name,
        "mode": MODE_SYMBOLS,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "symbols_requested": len(wanted),
        "symbols_with_bars": len(symbols_with_bars),
        "bars_written": int(bars_written),
        "symbols_listed": int(len(listing)),
        "errors": errors,
    }


# ---------------------------------------------------------------------------------------------- grouped mode
def _refetch_bars(prov: BarProvider, symbol: str, start: date, end: date) -> pd.DataFrame:
    fetch = prov.daily_bars
    if _accepts(fetch, "use_cache"):
        return fetch([symbol], start, end, use_cache=False)  # type: ignore[call-arg]
    return fetch([symbol], start, end)


def repair_splits(prov: BarProvider, st: Store, since: date, through: date) -> list[str]:
    """Refetch the full stored history of every stored symbol with a split executed in [since, through]
    whose stored bars start before the split (those bars were fetched unadjusted). Returns the symbols."""
    splits_fn = getattr(prov, "splits", None)
    if not callable(splits_fn) or not st.has_table(BARS_TABLE):
        return []
    splits = splits_fn(since=since)
    if splits is None or len(splits) == 0:
        return []
    persist = splits.assign(ex_date=pd.to_datetime(splits["ex_date"]).dt.date)
    st.write_table(SPLITS_TABLE, persist, ["symbol", "ex_date"])  # the universe screen un-adjusts with it
    ex = pd.to_datetime(splits["ex_date"]).dt.date
    window = splits.loc[(ex >= since) & (ex <= through)].assign(ex_date=ex)
    if window.empty:
        return []
    first_split = window.groupby("symbol")["ex_date"].min()
    spans = st.sql(
        f"SELECT symbol, min(ts) AS first_ts, max(ts) AS last_ts FROM {BARS_TABLE} "
        "WHERE symbol IN (SELECT unnest(?)) GROUP BY symbol",
        [sorted(first_split.index.astype(str))],
    )
    repaired: list[str] = []
    for row in spans.itertuples(index=False):
        first_d, last_d = as_date(pd.Timestamp(row.first_ts)), as_date(pd.Timestamp(row.last_ts))
        if first_d >= first_split[row.symbol]:
            continue  # nothing stored from before the split
        bars = _refetch_bars(prov, row.symbol, first_d, last_d)
        if bars is not None and not bars.empty:
            st.write_bars(bars)
        repaired.append(str(row.symbol))
    if repaired:
        log.info("ingest_splits_repaired", symbols=repaired[:10], count=len(repaired))
    return sorted(repaired)


def _ingest_grouped(
    prov: BarProvider, st: Store, settings: Settings, name: str, start_d: date, end_d: date, *,
    full: bool, splits: bool, reference: bool, progress: Progress | None,
) -> dict[str, Any]:
    today = _today()
    last = min(end_d, today)
    sessions = trading_days(start_d, last) if start_d <= last else []
    present = set() if full else grouped_days_present(st, start_d, last)
    floor_raw = None if full else _meta_get(st, PLAN_FLOOR_META.format(provider=name))
    floor = date.fromisoformat(floor_raw) if floor_raw else None
    beyond_plan = {d for d in sessions if floor is not None and d <= floor and d not in present}
    todo = sorted((d for d in sessions if d not in present and d not in beyond_plan), reverse=True)
    newest_present = max(present) if present else None
    rate = getattr(prov, "calls_per_min", None)
    estimate = estimate_backfill_seconds(len(todo), rate)
    split_anchor_raw = _meta_get(st, SPLIT_CHECK_META.format(provider=name))
    split_anchor = date.fromisoformat(split_anchor_raw) if split_anchor_raw else _ledger_first_fetch(st, name)

    _say(
        progress, "warning" if len(todo) >= LARGE_BACKFILL_DAYS else "info", "ingest_grouped_estimate",
        f"grouped ingest via {name}: {len(todo)} of {len(sessions)} sessions to fetch "
        f"(~{_fmt_duration(estimate)} at {rate or '?'} calls/min); resumable, re-run to continue",
        sessions=len(sessions), to_fetch=len(todo), present=len(present), calls_per_min=rate,
        estimate_s=None if estimate is None else round(estimate, 1),
    )

    errors: list[dict[str, str]] = []
    fetched = empty = pending = consecutive = 0
    bars_written = 0
    tickers: set[str] = set()
    plan_limit_at: date | None = None
    aborted = False
    remaining = 0
    for i, d in enumerate(todo, start=1):
        try:
            bars = prov.grouped_daily(d)  # type: ignore[attr-defined]
        except Exception as exc:
            status = _status_code(exc)
            error = redact_secrets(str(exc))
            if d >= today:
                pending += 1  # today's bar is not published yet on EOD plans; the next run picks it up
                log.info("ingest_grouped_pending", session=d.isoformat(), status=status)
                continue
            worked_newer = fetched > 0 or empty > 0 or (newest_present is not None and newest_present > d)
            if status == HTTP_FORBIDDEN and worked_newer:
                plan_limit_at = d
                remaining = len(todo) - i + 1  # this session and every older one
                _meta_set(st, PLAN_FLOOR_META.format(provider=name), d.isoformat())
                _say(progress, "warning", "ingest_grouped_plan_limit",
                     f"plan history limit reached at {d}; {remaining} sessions on or before it skipped",
                     session=d.isoformat(), skipped=remaining)
                break
            errors.append({"session": d.isoformat(), "error": error})
            log.error("ingest_grouped_day_failed", provider=name, session=d.isoformat(), status=status, error=error)
            consecutive += 1
            if consecutive >= GROUPED_MAX_CONSECUTIVE_ERRORS:
                remaining = len(todo) - i
                aborted = True
                _say(progress, "error", "ingest_grouped_aborted",
                     f"grouped ingest stopped after {consecutive} consecutive failures; {remaining} sessions left",
                     remaining=remaining)
                break
            continue
        consecutive = 0
        if bars is None or bars.empty:
            empty += 1
            log.info("ingest_grouped_empty", session=d.isoformat())
        else:
            bars_written += st.write_bars(bars)
            day_symbols = set(bars["symbol"].unique().tolist())
            tickers.update(day_symbols)
            if session_is_final(d):
                _record_session(st, d, len(day_symbols), name, today)
            else:
                log.info("ingest_grouped_partial_session", session=d.isoformat(), note="written, not ledgered")
            fetched += 1
        if i % GROUPED_PROGRESS_EVERY_DAYS == 0 and i < len(todo):
            left = len(todo) - i
            eta = estimate_backfill_seconds(left, rate)
            _say(progress, "info", "ingest_grouped_progress",
                 f"{i}/{len(todo)} sessions (at {d}); {bars_written:,} bars; ~{_fmt_duration(eta)} left",
                 done=i, total=len(todo), session=d.isoformat(), bars_written=bars_written,
                 eta_s=None if eta is None else round(eta, 1))

    repaired: list[str] = []
    if splits and st.has_table(BARS_TABLE):
        try:
            if split_anchor is not None and split_anchor < today:
                repaired = repair_splits(prov, st, split_anchor, today)
            _meta_set(st, SPLIT_CHECK_META.format(provider=name), today.isoformat())
        except Exception as exc:
            errors.append({"stage": "splits", "error": redact_secrets(str(exc))})
            log.error("ingest_split_repair_failed", provider=name, error=redact_secrets(str(exc)))

    symbols_listed = 0
    reference_error: str | None = None
    ref_fn = getattr(prov, "universe_reference", None)
    if reference and callable(ref_fn):
        try:
            ref = ref_fn(include_etfs=settings.universe.include_etfs, delisted_since=start_d)
            symbols_listed = write_symbols(st, ref)
        except Exception as exc:  # the next run retries; bars are what matter here
            reference_error = redact_secrets(str(exc))
            log.warning("ingest_reference_failed", provider=name, error=reference_error)

    return {
        "provider": name,
        "mode": MODE_GROUPED,
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "sessions": len(sessions),
        "sessions_present": len(present & set(sessions)),
        "sessions_fetched": fetched,
        "sessions_empty": empty,
        "sessions_pending": pending,
        "sessions_beyond_plan": len(beyond_plan) + (remaining if plan_limit_at is not None else 0),
        "sessions_remaining": remaining if aborted else 0,
        "plan_limit_at": plan_limit_at.isoformat() if plan_limit_at else (floor.isoformat() if floor else None),
        "symbols_requested": len(tickers),
        "symbols_with_bars": len(tickers),
        "bars_written": int(bars_written),
        "symbols_listed": int(symbols_listed),
        "splits_repaired": repaired,
        "reference_error": reference_error,
        "estimate_s": None if estimate is None else round(estimate, 1),
        "errors": errors,
    }


# ---------------------------------------------------------------------------------------------- entry point
def run_ingest(
    settings: Settings,
    secrets: Secrets,
    provider_name: str | None = None,
    symbols: Iterable[str] | None = None,
    start: date | str | None = None,
    end: date | str | None = None,
    store: Store | None = None,
    *,
    full: bool = False,
    provider: BarProvider | None = None,
    mode: str = MODE_AUTO,
    splits: bool = True,
    reference: bool = True,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Fetch daily bars between `start` and `end` into `store` and return counts and elapsed time.

    `symbols` (default: `universe.static_symbols`, else the provider's listing) drive the per-symbol mode;
    with neither, a provider that has `grouped_daily` (massive) ingests the whole market session by session
    (see the module docstring). `progress` receives human-readable estimate/progress lines (e.g. a CLI
    console print); `splits` / `reference` toggle the grouped-mode split repair and reference refresh."""
    t0 = time.perf_counter()
    name = provider_name or settings.data.bar_provider
    prov = provider or make_provider(name, settings, secrets)
    own_store = store is None
    st = store or Store(settings.data.store_path)
    try:
        end_d = as_date(end) if end is not None else _today()
        start_d = as_date(start) if start is not None else end_d - timedelta(days=DAYS_PER_YEAR * settings.data.history_years)
        chosen = resolve_mode(mode, prov, symbols, settings)
        if chosen == MODE_GROUPED:
            result = _ingest_grouped(
                prov, st, settings, name, start_d, end_d, full=full, splits=splits, reference=reference, progress=progress
            )
        else:
            result = _ingest_symbols(prov, st, settings, name, symbols, start_d, end_d, full=full)
        snapshot = st.snapshot_date()
        result["elapsed_s"] = round(time.perf_counter() - t0, 3)
        result["snapshot_date"] = snapshot.isoformat() if snapshot else None
        log.info(
            "ingest_done",
            **{k: v for k, v in result.items() if k not in ("errors", "splits_repaired")},
            error_count=len(result["errors"]),
        )
        return result
    finally:
        if own_store:
            st.close()


def bars_from_store_or_provider(
    st: Store, prov: BarProvider, symbols: list[str], start: date, end: date
) -> pd.DataFrame:
    """Read from the store, falling back to the provider for symbols with nothing stored."""
    bars = st.read_bars(symbols, start, end)
    missing = sorted(set(symbols) - set(bars["symbol"].unique()))
    if missing:
        extra = prov.daily_bars(missing, start, end)
        if not extra.empty:
            st.write_bars(extra)
            bars = pd.concat([bars, extra], ignore_index=True).sort_values(["symbol", "ts"]).reset_index(drop=True)
    return bars
