"""Tier-2 halt log (docs/smallcap-spec.md "Outcome logging"): every single-name halt is recorded with its code,
direction, halt price and resume price, then joined with daily bars to build the halted-runner statistic no
source publishes: how often a name that halted k times closes below its open and below the halt price.

``record_halt(event, store)`` is called with pipeline halt events (kind ``halt``). A ``halted``/``paused`` event
opens a row in ``halt_log`` keyed on (symbol, halt_ts); a ``resumed`` event fills the latest open row of that
symbol with the resume time and price. Market-wide codes (MWC*) are ignored, as is a resume without a logged
halt. Prices and direction are taken from event meta only (``halt_price``/``price``/``pause_threshold_price``,
``resume_price``/``price``, ``direction``) and stay NaN/unknown otherwise: nothing here guesses a number.

``halt_dataset(store)`` enriches the log with the session open/close, previous and next close, the number of
halts the symbol had that session and the below-open / below-halt flags; ``halt_statistics(store)`` aggregates
it by halt count. Pure pandas, no network.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import Event
from swing_engine.data.store import Store

from .constants import HALT_STATUSES, MARKET_WIDE_HALT_CODES
from .hours import ET

log = structlog.get_logger(__name__)

HALT_LOG_TABLE = "halt_log"
HALT_OUTCOMES_TABLE = "halt_outcomes"
HALT_LOG_KEYS: tuple[str, ...] = ("symbol", "halt_ts")
HALT_KIND = "halt"
STATUS_RESUMED = "resumed"
STATUS_HALTED = "halted"
HALT_PRICE_KEYS: tuple[str, ...] = ("halt_price", "price", "last_price", "pause_threshold_price")
RESUME_PRICE_KEYS: tuple[str, ...] = ("resume_price", "price", "last_price")
DIRECTION_KEY = "direction"
DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
DIRECTION_UNKNOWN = "unknown"
DIRECTION_META = "meta"
DIRECTION_INFERRED = "inferred"
#: a resume is matched to the symbol's latest open halt inside this window
RESUME_MATCH_MAX_HOURS = 24.0
#: statistics buckets: 1, 2, 3 and "4+" halts per session (the spec's exhaustion threshold is four up-halts)
HALT_COUNT_CAP = 4
BUCKET_CAPPED = f"{HALT_COUNT_CAP}+"
BUCKET_ALL = "all"
PCT = 100.0

HALT_LOG_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR", "halt_ts": "TIMESTAMPTZ", "halt_event_id": "VARCHAR", "resume_event_id": "VARCHAR",
    "source": "VARCHAR", "code": "VARCHAR", "status": "VARCHAR", "direction": "VARCHAR", "halt_price": "DOUBLE",
    "resume_ts": "TIMESTAMPTZ", "resume_price": "DOUBLE", "market": "VARCHAR",
}
HALT_LOG_COLUMNS: tuple[str, ...] = tuple(HALT_LOG_SCHEMA)
HALT_DATASET_COLUMNS: tuple[str, ...] = (
    *HALT_LOG_COLUMNS, "session", "direction_source", "halt_seq", "halts_that_day", "prev_close", "open", "close",
    "next_close", "resume_vs_halt_pct", "close_vs_halt_pct", "close_vs_open_pct", "next_close_vs_close_pct",
    "close_below_open", "close_below_halt", "next_close_below_close",
)
HALT_STATS_COLUMNS: tuple[str, ...] = (
    "bucket", "n_halts", "n_symbol_days", "n_up", "n_down", "share_close_below_open", "share_close_below_halt",
    "share_next_close_below_close", "mean_close_vs_halt_pct", "median_close_vs_halt_pct", "mean_close_vs_open_pct",
)


# ---- public API ----------------------------------------------------------------------------------------------
def record_halt(event: Event, store: Store) -> list[dict[str, Any]]:
    """Upsert one ``halt_log`` row per symbol of a halt event; returns the rows written (empty when ignored)."""
    if event.kind != HALT_KIND:
        return []
    meta = event.meta or {}
    code = _halt_code(meta)
    if code in MARKET_WIDE_HALT_CODES:
        return []
    status = str(meta.get("status", STATUS_HALTED)).lower().strip()
    if status not in HALT_STATUSES:
        log.debug("halt_log.status_ignored", event_id=event.event_id, status=status, code=code)
        return []  # only halted/paused open a row and only resumed closes one
    ts = _utc(event.ts_source)
    rows: list[dict[str, Any]] = []
    for symbol in dict.fromkeys(s.upper().strip() for s in event.symbols if s):
        if status == STATUS_RESUMED:
            row = _open_halt(store, symbol, ts)
            if row is None:
                log.warning("halt_log.resume_without_halt", symbol=symbol, event_id=event.event_id, code=code)
                continue
            row.update(
                resume_event_id=event.event_id, resume_ts=ts, resume_price=_price(meta, RESUME_PRICE_KEYS),
                status=STATUS_RESUMED,
            )
        else:
            row = {
                "symbol": symbol, "halt_ts": ts, "halt_event_id": event.event_id, "resume_event_id": None,
                "source": event.source, "code": code, "status": status or STATUS_HALTED,
                "direction": _direction(meta), "halt_price": _price(meta, HALT_PRICE_KEYS), "resume_ts": pd.NaT,
                "resume_price": float("nan"), "market": _text(meta.get("market")),
            }
        rows.append(row)
    if rows:
        store.write_table(HALT_LOG_TABLE, _log_frame(rows), list(HALT_LOG_KEYS), schema=HALT_LOG_SCHEMA)
        log.debug("halt_log.recorded", event_id=event.event_id, rows=len(rows), status=status, code=code)
    return rows


def halt_dataset(store: Store, bars: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-halt rows (:data:`HALT_DATASET_COLUMNS`): the log joined with the session's open/close, the previous
    and next close, the halt count for that symbol-session and the below-open / below-halt flags. ``bars``
    overrides the store's daily bars (long contract frame)."""
    raw = store.read_table(HALT_LOG_TABLE)
    if raw.empty:
        return _empty(HALT_DATASET_COLUMNS)
    halts = _log_frame(raw.to_dict("records")).sort_values(["symbol", "halt_ts"], kind="mergesort")
    halts = halts.reset_index(drop=True)
    halts["session"] = halts["halt_ts"].dt.tz_convert(ET).dt.date
    daily = store.read_bars(sorted(halts["symbol"].unique())) if bars is None else bars
    halts = halts.merge(_session_prices(daily), on=["symbol", "session"], how="left")
    group = halts.groupby(["symbol", "session"], sort=False)
    halts["halt_seq"] = group.cumcount() + 1
    halts["halts_that_day"] = group["halt_ts"].transform("size").astype("int64")
    halts["direction_source"] = halts["direction"].map(
        lambda d: DIRECTION_META if d in (DIRECTION_UP, DIRECTION_DOWN) else DIRECTION_UNKNOWN
    )
    inferred = _infer_direction(halts)
    missing = halts["direction_source"] == DIRECTION_UNKNOWN
    halts.loc[missing & inferred.notna(), "direction"] = inferred[missing & inferred.notna()]
    halts.loc[missing & inferred.notna(), "direction_source"] = DIRECTION_INFERRED
    halts["resume_vs_halt_pct"] = _pct(halts["resume_price"], halts["halt_price"])
    halts["close_vs_halt_pct"] = _pct(halts["close"], halts["halt_price"])
    halts["close_vs_open_pct"] = _pct(halts["close"], halts["open"])
    halts["next_close_vs_close_pct"] = _pct(halts["next_close"], halts["close"])
    halts["close_below_open"] = _below(halts["close"], halts["open"])
    halts["close_below_halt"] = _below(halts["close"], halts["halt_price"])
    halts["next_close_below_close"] = _below(halts["next_close"], halts["close"])
    return halts[list(HALT_DATASET_COLUMNS)].reset_index(drop=True)


def halt_statistics(store: Store, *, bars: pd.DataFrame | None = None, persist: bool = True) -> pd.DataFrame:
    """The halted-runner statistic by halts-per-session bucket (``1``, ``2``, ``3``, ``4+`` and ``all``):
    halts and symbol-days in the bucket, up/down counts, the share of symbol-days closing below the open, the
    share of halts whose session closed below the halt price, the share of next sessions closing lower, and the
    mean/median close-vs-halt move. The per-halt dataset is upserted into ``halt_outcomes`` unless ``persist``
    is False."""
    data = halt_dataset(store, bars)
    if data.empty:
        return _empty(HALT_STATS_COLUMNS)
    if persist and not store.read_only:
        store.write_table(HALT_OUTCOMES_TABLE, data, list(HALT_LOG_KEYS))
    buckets = data["halts_that_day"].map(lambda k: BUCKET_CAPPED if k >= HALT_COUNT_CAP else str(int(k)))
    rows = [_stats_row(BUCKET_ALL, data)]
    for bucket in sorted(buckets.unique(), key=lambda b: (b == BUCKET_CAPPED, b)):
        rows.append(_stats_row(str(bucket), data[buckets == bucket]))
    return pd.DataFrame(rows, columns=list(HALT_STATS_COLUMNS))


# ---- helpers -------------------------------------------------------------------------------------------------
def _halt_code(meta: dict[str, Any]) -> str:
    return str(meta.get("reason_code") or meta.get("code") or "").upper().strip()


def _direction(meta: dict[str, Any]) -> str:
    value = str(meta.get(DIRECTION_KEY) or "").lower().strip()
    return value if value in (DIRECTION_UP, DIRECTION_DOWN) else DIRECTION_UNKNOWN


def _price(meta: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        value = meta.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return float("nan")


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _utc(dt: datetime | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(dt)
    return ts.tz_localize(UTC) if ts.tzinfo is None else ts.tz_convert("UTC")


def _open_halt(store: Store, symbol: str, resume_ts: pd.Timestamp) -> dict[str, Any] | None:
    if not store.has_table(HALT_LOG_TABLE):
        return None
    since = (resume_ts - timedelta(hours=RESUME_MATCH_MAX_HOURS)).to_pydatetime()
    rows = store.read_table(
        HALT_LOG_TABLE,
        "symbol = ? AND resume_ts IS NULL AND halt_ts <= ? AND halt_ts >= ?",
        [symbol, resume_ts.to_pydatetime(), since],
        order_by="halt_ts DESC",
    )
    if rows.empty:
        return None
    row = rows.iloc[0].to_dict()
    row["halt_ts"] = _utc(row["halt_ts"])
    return row


def _log_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for col in HALT_LOG_COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[list(HALT_LOG_COLUMNS)].copy()
    for col in ("halt_ts", "resume_ts"):
        frame[col] = pd.to_datetime(frame[col], utc=True)
    for col in ("halt_price", "resume_price"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce").astype("float64")
    for col, kind in HALT_LOG_SCHEMA.items():
        if kind == "VARCHAR":
            frame[col] = frame[col].astype("object").where(frame[col].notna(), None)
    return frame


def _session_prices(daily: pd.DataFrame) -> pd.DataFrame:
    """Per (symbol, session): prev_close, open, close, next_close from a long daily bars frame."""
    cols = ["symbol", "session", "prev_close", "open", "close", "next_close"]
    if daily is None or daily.empty:
        return pd.DataFrame({c: pd.Series(dtype="object" if c in ("symbol", "session") else "float64") for c in cols})
    bars = daily.sort_values(["symbol", "ts"], kind="mergesort").copy()
    ts = pd.to_datetime(bars["ts"])
    ts = ts.dt.tz_localize(ET) if ts.dt.tz is None else ts.dt.tz_convert(ET)
    bars["session"] = ts.dt.date
    bars["prev_close"] = bars.groupby("symbol")["close"].shift(1)
    bars["next_close"] = bars.groupby("symbol")["close"].shift(-1)
    return bars[cols].reset_index(drop=True)


def _infer_direction(halts: pd.DataFrame) -> pd.Series:
    """Up/down from the halt price against the previous close (else the session open); NA when unknown."""
    anchor = halts["prev_close"].where(halts["prev_close"].notna(), halts["open"])
    known = halts["halt_price"].notna() & anchor.notna()
    out = pd.Series([None] * len(halts), index=halts.index, dtype="object")
    out[known] = (halts["halt_price"][known] > anchor[known]).map({True: DIRECTION_UP, False: DIRECTION_DOWN})
    return out


def _pct(price: pd.Series, ref: pd.Series) -> pd.Series:
    ref_ok = ref.where(ref > 0)
    return (price / ref_ok - 1.0) * PCT


def _below(price: pd.Series, ref: pd.Series) -> pd.Series:
    out = pd.Series([pd.NA] * len(price), index=price.index, dtype="boolean")
    known = price.notna() & ref.notna()
    out[known] = (price[known] < ref[known]).to_numpy()
    return out


def _share(flags: pd.Series) -> float:
    known = flags.dropna()
    return float(known.astype("bool").mean()) if len(known) else float("nan")


def _stats_row(bucket: str, data: pd.DataFrame) -> dict[str, Any]:
    days = data.drop_duplicates(subset=["symbol", "session"])
    close_vs_halt = pd.to_numeric(data["close_vs_halt_pct"], errors="coerce").dropna()
    close_vs_open = pd.to_numeric(days["close_vs_open_pct"], errors="coerce").dropna()
    return {
        "bucket": bucket,
        "n_halts": int(len(data)),
        "n_symbol_days": int(len(days)),
        "n_up": int((data["direction"] == DIRECTION_UP).sum()),
        "n_down": int((data["direction"] == DIRECTION_DOWN).sum()),
        "share_close_below_open": _share(days["close_below_open"]),
        "share_close_below_halt": _share(data["close_below_halt"]),
        "share_next_close_below_close": _share(days["next_close_below_close"]),
        "mean_close_vs_halt_pct": float(close_vs_halt.mean()) if len(close_vs_halt) else float("nan"),
        "median_close_vs_halt_pct": float(close_vs_halt.median()) if len(close_vs_halt) else float("nan"),
        "mean_close_vs_open_pct": float(close_vs_open.mean()) if len(close_vs_open) else float("nan"),
    }


def _empty(columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame({c: [] for c in columns})
