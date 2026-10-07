"""Nightly ingest: provider -> normalized bars -> DuckDB store (plus a `symbols` reference table).

Incremental by default: each symbol is fetched from its last stored session minus a small overlap (so
late corrections and the current partial day get overwritten by the upsert). `full=True` refetches
everything, which is what you want after a split adjusts history.
"""
from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

import pandas as pd
import structlog

from swing_engine.core import registry
from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import BarProvider

from ._common import as_date, normalize_symbols
from .store import Store

log = structlog.get_logger(__name__)

SYMBOLS_TABLE = "symbols"
INGEST_CHUNK_SYMBOLS = 50
INGEST_OVERLAP_DAYS = 5
DAYS_PER_YEAR = 365


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
) -> dict[str, Any]:
    """Fetch daily bars for `symbols` (default: the provider's listed names, or `universe.static_symbols`
    when set) between `start` and `end` and upsert them into `store`. Returns counts and elapsed time."""
    t0 = time.perf_counter()
    name = provider_name or settings.data.bar_provider
    prov = provider or make_provider(name, settings, secrets)
    own_store = store is None
    st = store or Store(settings.data.store_path)
    errors: list[dict[str, str]] = []
    try:
        end_d = as_date(end) if end is not None else date.today()
        start_d = as_date(start) if start is not None else end_d - timedelta(days=DAYS_PER_YEAR * settings.data.history_years)

        listing = normalize_symbols(prov.list_symbols(include_delisted=True))
        if not listing.empty:
            st.write_table(SYMBOLS_TABLE, listing, keys=["symbol"])
        if symbols is not None:
            wanted = sorted({s.upper() for s in symbols})
        elif settings.universe.static_symbols:
            wanted = sorted({s.upper() for s in settings.universe.static_symbols})
        else:
            wanted = listing["symbol"].tolist()

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
                log.error("ingest_chunk_failed", provider=name, symbols=chunk[:3], error=str(exc))
                errors.append({"symbols": ",".join(chunk), "error": str(exc)})
                continue
            if bars is None or bars.empty:
                continue
            bars_written += st.write_bars(bars)
            symbols_with_bars.update(bars["symbol"].unique().tolist())
        elapsed = time.perf_counter() - t0
        result = {
            "provider": name,
            "start": start_d.isoformat(),
            "end": end_d.isoformat(),
            "symbols_requested": len(wanted),
            "symbols_with_bars": len(symbols_with_bars),
            "bars_written": int(bars_written),
            "symbols_listed": int(len(listing)),
            "errors": errors,
            "elapsed_s": round(elapsed, 3),
            "snapshot_date": (st.snapshot_date().isoformat() if st.snapshot_date() else None),
        }
        log.info("ingest_done", **{k: v for k, v in result.items() if k != "errors"}, error_count=len(errors))
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
