"""Alert outcome tracking (docs/smallcap-spec.md "Outcome logging"): every alert in the event log is joined with
prices from the DuckDB store to measure what happened afterwards.

An *alert* is an event the policy did not drop (priority >= P1) or that has a row in the event log's `alerts`
audit table. For each (alert, symbol) the reference price is the first print at/after the alert time:
- intraday bars (table ``bars_intraday``, same columns as ``bars``) when present: the open of the first bar at or
  after the alert inside the alert's ET session;
- otherwise daily bars: the open of the alert's session when the alert lands before 09:30 ET, the close of the
  session when it lands during regular hours (the only daily print at/after the alert), the next session's open
  when it lands after the close.
Realized returns are measured at +5 min and +30 min after the reference print (intraday only: a pre-open alert
is measured from the open, the first price anyone could act on), at the close of the reference session and at
the close 1, 5 and 20 sessions later. Anything unavailable is NaN, never guessed. Returns are percentages.
The window is "since now - days" (the event log's `recent` semantics); it has no upper bound.

Rows are tagged with rule hits, priority, the Haiku classification enums, the small-cap classifier fields
(``meta["smallcap"]``: classifier, grade, structural_score, bagholder_score) and the user's useful/noise rating
(``meta["rating"]``) when present. Results are upserted into the store table ``alert_outcomes`` keyed on
(event_id, symbol). Pure pandas; nothing here touches the network.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.config import ROOT, Settings
from swing_engine.core.models import Event
from swing_engine.data.store import Store

from .constants import PRIORITY_RANK, REGULAR_OPEN
from .eventlog import EventLog
from .hours import ET, session_bounds, to_et

log = structlog.get_logger(__name__)

OUTCOMES_TABLE = "alert_outcomes"
INTRADAY_BARS_TABLE = "bars_intraday"
OUTCOMES_KEYS: tuple[str, ...] = ("event_id", "symbol")
HOURS_PER_DAY = 24
PCT = 100.0
MIN_ALERT_PRIORITY = "P1"  # P0 is dropped by the policy; everything above is an alert of some tier
#: horizon name -> minutes after the alert (intraday) or sessions after the reference session (daily)
INTRADAY_HORIZONS_MIN: dict[str, int] = {"5m": 5, "30m": 30}
DAILY_HORIZONS_SESSIONS: dict[str, int] = {"1d": 1, "5d": 5, "20d": 20}
CLOSE_HORIZON = "close"
HORIZONS: tuple[str, ...] = (*INTRADAY_HORIZONS_MIN, CLOSE_HORIZON, *DAILY_HORIZONS_SESSIONS)
RETURN_COLUMNS: tuple[str, ...] = tuple(f"ret_{h}_pct" for h in HORIZONS)
REF_INTRADAY = "intraday"
REF_DAILY_OPEN = "daily_open"
REF_DAILY_CLOSE = "daily_close"
REF_NONE = "none"
RULE_SEP = "|"
TITLE_MAX = 120
#: user feedback on an alert, read from ``event.meta["rating"]`` (or ``useful: bool``)
RATING_USEFUL = "useful"
RATING_NOISE = "noise"
RATING_TRADED = "traded"  # monitor.rate.AlertRating.TRADED: you acted on it; counts as useful in the precision proxy
RATING_KEY = "rating"
USEFUL_KEY = "useful"
SMALLCAP_KEY = "smallcap"
CLASSIFICATION_KEY = "classification"
ALL_RULES = "all"
#: alert audit rows are stamped at delivery time; allow them to trail the event window by this much
ALERT_AUDIT_SLACK_HOURS = 24.0

OUTCOME_COLUMNS: tuple[str, ...] = (
    "event_id", "symbol", "alert_ts", "session", "source", "kind", "priority", "rule_hits", "primary_rule",
    "title", "delivered", "channels", "cls_relevance", "cls_event_type", "cls_materiality", "cls_sentiment",
    "cls_action", "sc_classifier", "sc_grade", "sc_structural_score", "sc_bagholder_score", "rating",
    "ref_price", "ref_ts", "ref_source", *RETURN_COLUMNS,
)
OUTCOMES_SCHEMA: dict[str, str] = {
    "event_id": "VARCHAR", "symbol": "VARCHAR", "alert_ts": "TIMESTAMPTZ", "session": "DATE", "source": "VARCHAR",
    "kind": "VARCHAR", "priority": "VARCHAR", "rule_hits": "VARCHAR", "primary_rule": "VARCHAR", "title": "VARCHAR",
    "delivered": "BOOLEAN", "channels": "VARCHAR", "cls_relevance": "VARCHAR", "cls_event_type": "VARCHAR",
    "cls_materiality": "DOUBLE", "cls_sentiment": "VARCHAR", "cls_action": "VARCHAR", "sc_classifier": "VARCHAR",
    "sc_grade": "VARCHAR", "sc_structural_score": "DOUBLE", "sc_bagholder_score": "DOUBLE", "rating": "VARCHAR",
    "ref_price": "DOUBLE", "ref_ts": "TIMESTAMPTZ", "ref_source": "VARCHAR",
    **{c: "DOUBLE" for c in RETURN_COLUMNS},
}
_TEXT_COLUMNS: tuple[str, ...] = tuple(c for c, t in OUTCOMES_SCHEMA.items() if t == "VARCHAR")
_FLOAT_COLUMNS: tuple[str, ...] = tuple(c for c, t in OUTCOMES_SCHEMA.items() if t == "DOUBLE")


# ---- public API ----------------------------------------------------------------------------------------------
def compute_outcomes(
    settings: Settings,
    days: float = 1.0,
    *,
    eventlog: EventLog | None = None,
    store: Store | None = None,
    now: datetime | None = None,
    persist: bool = True,
    intraday_table: str = INTRADAY_BARS_TABLE,
) -> pd.DataFrame:
    """Join the last ``days`` of alerts with store prices and return one row per (alert, symbol).

    ``eventlog`` / ``store`` default to the paths in ``settings.data`` (relative to the repo root). The frame is
    upserted into ``alert_outcomes`` unless ``persist`` is False. Columns: :data:`OUTCOME_COLUMNS`."""
    own_log = eventlog is None
    own_store = store is None
    log_ = eventlog or EventLog(_resolve(settings.data.event_log_path))
    store_ = store or Store(_resolve(settings.data.store_path))
    try:
        alerts = _alert_rows(log_, days, now)
        frame = _outcomes_frame(alerts, store_, intraday_table)
        if persist and not frame.empty and not store_.read_only:
            store_.write_table(OUTCOMES_TABLE, frame, list(OUTCOMES_KEYS), schema=OUTCOMES_SCHEMA)
        log.info("outcomes.computed", alerts=len(alerts), rows=len(frame), days=days, persisted=persist)
        return frame
    finally:
        if own_log:
            log_.close()
        if own_store:
            store_.close()


def summarize_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """Per-rule summary of an outcomes frame: ``n``, and for every horizon the hit rate (return > 0 among the
    measured returns), mean and median return; plus ``rated``/``useful``/``traded`` counts and ``precision_proxy``
    (useful / rated, NaN when nothing is rated; a ``traded`` rating counts as useful). The first row
    (``rule == "all"``) covers every alert."""
    if df is None or df.empty:
        return pd.DataFrame(columns=_summary_columns())
    rows = [_summarize_group(ALL_RULES, df)]
    exploded = df.assign(rule=df["rule_hits"].fillna("").astype(str).str.split(RULE_SEP)).explode("rule")
    exploded = exploded[exploded["rule"].astype(str).str.len() > 0]
    for rule, group in exploded.groupby("rule", sort=True):
        rows.append(_summarize_group(str(rule), group))
    return pd.DataFrame(rows, columns=_summary_columns())


# ---- alert extraction ----------------------------------------------------------------------------------------
def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _alert_rows(eventlog: EventLog, days: float, now: datetime | None) -> list[dict[str, Any]]:
    """One dict per (event, symbol) for every alert-tier event in the window, joined with its audit row."""
    hours = days * HOURS_PER_DAY
    events = eventlog.recent(hours, now=now)
    audit: dict[str, dict[str, Any]] = {}
    for row in eventlog.recent_alerts(hours + ALERT_AUDIT_SLACK_HOURS, now=now):
        audit[str(row["event_id"])] = row  # last delivery attempt wins
    rows: list[dict[str, Any]] = []
    for event in events:
        alert = audit.get(event.event_id)
        if alert is None and PRIORITY_RANK.get(str(event.priority), 0) < PRIORITY_RANK[MIN_ALERT_PRIORITY]:
            continue
        for symbol in dict.fromkeys(s.upper().strip() for s in event.symbols if s):
            rows.append(_tag_row(event, symbol, alert))
    return rows


def _tag_row(event: Event, symbol: str, alert: dict[str, Any] | None) -> dict[str, Any]:
    meta = event.meta or {}
    cls = meta.get(CLASSIFICATION_KEY) if isinstance(meta.get(CLASSIFICATION_KEY), dict) else {}
    sc = meta.get(SMALLCAP_KEY) if isinstance(meta.get(SMALLCAP_KEY), dict) else {}
    hits = [str(h) for h in event.rule_hits]
    channels = _channels(alert)
    return {
        "event_id": event.event_id,
        "symbol": symbol,
        "alert_ts": _utc(event.ts_received),
        "source": event.source,
        "kind": event.kind,
        "priority": str(alert["priority"]) if alert else str(event.priority),
        "rule_hits": RULE_SEP.join(hits),
        "primary_rule": hits[0] if hits else "",
        "title": event.title[:TITLE_MAX],
        "delivered": bool(alert["delivered"]) if alert else False,
        "channels": RULE_SEP.join(channels),
        "cls_relevance": _text(cls.get("relevance")),
        "cls_event_type": _text(cls.get("event_type")),
        "cls_materiality": _number(cls.get("materiality")),
        "cls_sentiment": _text(cls.get("sentiment")),
        "cls_action": _text(cls.get("suggested_action")),
        "sc_classifier": _text(sc.get("classifier")),
        "sc_grade": _text(sc.get("grade", meta.get("grade"))),
        "sc_structural_score": _number(sc.get("structural_score", meta.get("structural_score"))),
        "sc_bagholder_score": _number(sc.get("bagholder_score", meta.get("bagholder_score"))),
        "rating": _rating(meta),
    }


def _channels(alert: dict[str, Any] | None) -> list[str]:
    if not alert:
        return []
    raw = alert.get("channels")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return [raw]
    return [str(c) for c in (raw or [])]


def _rating(meta: dict[str, Any]) -> str | None:
    value = meta.get(RATING_KEY)
    if value is None and USEFUL_KEY in meta:
        value = RATING_USEFUL if bool(meta[USEFUL_KEY]) else RATING_NOISE
    if value is None:
        return None
    text = str(value).strip().lower()
    return text if text in (RATING_USEFUL, RATING_NOISE, RATING_TRADED) else None


def _text(value: Any) -> str | None:
    return None if value is None else str(value)


def _number(value: Any) -> float:
    try:
        return float(value) if value is not None else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _utc(dt: datetime) -> pd.Timestamp:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return pd.Timestamp(dt).tz_convert("UTC")


# ---- price joins ---------------------------------------------------------------------------------------------
def _outcomes_frame(rows: list[dict[str, Any]], store: Store, intraday_table: str) -> pd.DataFrame:
    if not rows:
        return _empty_frame()
    symbols = sorted({r["symbol"] for r in rows})
    daily = _daily_by_symbol(store, symbols)
    intraday = _intraday_by_symbol(store, symbols, intraday_table)
    out: list[dict[str, Any]] = []
    for row in rows:
        priced = dict(row)
        priced.update(_price_row(row["alert_ts"], daily.get(row["symbol"]), intraday.get(row["symbol"])))
        out.append(priced)
    frame = pd.DataFrame(out)
    for col in OUTCOME_COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    return _coerce(frame[list(OUTCOME_COLUMNS)].reset_index(drop=True))


def _daily_by_symbol(store: Store, symbols: list[str]) -> dict[str, pd.DataFrame]:
    bars = store.read_bars(symbols)
    if bars.empty:
        return {}
    bars = bars.assign(session=bars["ts"].dt.tz_convert(ET).dt.date)
    return {str(sym): g.sort_values("ts").reset_index(drop=True) for sym, g in bars.groupby("symbol")}


def _intraday_by_symbol(store: Store, symbols: list[str], table: str) -> dict[str, pd.DataFrame]:
    if not table or not store.has_table(table):
        return {}
    frame = store.read_table(table, "symbol IN (SELECT unnest(?))", [symbols], order_by="symbol, ts")
    if frame.empty or "ts" not in frame.columns or "open" not in frame.columns:
        return {}
    ts = pd.to_datetime(frame["ts"])
    ts = ts.dt.tz_localize(ET) if ts.dt.tz is None else ts.dt.tz_convert(ET)
    frame = frame.assign(ts=ts, session=ts.dt.date, open=pd.to_numeric(frame["open"], errors="coerce"))
    return {str(sym): g.sort_values("ts").reset_index(drop=True) for sym, g in frame.groupby("symbol")}


def _price_row(alert_ts: pd.Timestamp, daily: pd.DataFrame | None, intraday: pd.DataFrame | None) -> dict[str, Any]:
    """Reference price, its session and every horizon return for one alert."""
    et = to_et(alert_ts.to_pydatetime())
    out: dict[str, Any] = {
        "session": None, "ref_price": float("nan"), "ref_ts": pd.NaT, "ref_source": REF_NONE,
        **{c: float("nan") for c in RETURN_COLUMNS},
    }
    ref_session: date | None = None
    if intraday is not None:
        first = _first_intraday_at_or_after(intraday, alert_ts, et.date())
        if first is not None:
            ref_ts = _utc(first["ts"])
            out.update(ref_price=float(first["open"]), ref_ts=ref_ts, ref_source=REF_INTRADAY)
            ref_session = et.date()
            for name, minutes in INTRADAY_HORIZONS_MIN.items():
                bar = _first_intraday_at_or_after(intraday, ref_ts + timedelta(minutes=minutes), et.date())
                if bar is not None:
                    out[f"ret_{name}_pct"] = _pct(float(bar["open"]), out["ref_price"])
    if ref_session is None and daily is not None:
        ref = _daily_reference(daily, et)
        if ref is not None:
            price, ts, source, ref_session = ref
            out.update(ref_price=price, ref_ts=ts, ref_source=source)
    if ref_session is None:
        return out
    out["session"] = ref_session
    if daily is not None:
        idx = daily.index[daily["session"] == ref_session]
        if len(idx):
            i = int(idx[0])
            out[f"ret_{CLOSE_HORIZON}_pct"] = _pct(float(daily.at[i, "close"]), out["ref_price"])
            for name, sessions in DAILY_HORIZONS_SESSIONS.items():
                j = i + sessions
                if j < len(daily):
                    out[f"ret_{name}_pct"] = _pct(float(daily.at[j, "close"]), out["ref_price"])
    return out


def _first_intraday_at_or_after(intraday: pd.DataFrame, when: pd.Timestamp, session: date) -> pd.Series | None:
    mask = (intraday["ts"] >= when.tz_convert(ET)) & (intraday["session"] == session) & intraday["open"].notna()
    hit = intraday[mask]
    return None if hit.empty else hit.iloc[0]


def _daily_reference(daily: pd.DataFrame, et: datetime) -> tuple[float, pd.Timestamp, str, date] | None:
    """First daily print at/after the alert: open of the session (pre-open alert or a later session), the close
    of the session (regular-hours alert) or the next session's open (after the close)."""
    d = et.date()
    regular_close, _ = session_bounds(d)
    after_close = et.time() >= regular_close
    candidates = daily[daily["session"] > d] if after_close else daily[daily["session"] >= d]
    if candidates.empty:
        return None
    bar = candidates.iloc[0]
    session: date = bar["session"]
    if session == d and et.time() >= REGULAR_OPEN:
        return float(bar["close"]), _utc(_session_close_ts(d)), REF_DAILY_CLOSE, session
    return float(bar["open"]), _utc(_session_open_ts(session)), REF_DAILY_OPEN, session


def _session_open_ts(d: date) -> datetime:
    return datetime.combine(d, REGULAR_OPEN, tzinfo=ET)


def _session_close_ts(d: date) -> datetime:
    return datetime.combine(d, session_bounds(d)[0], tzinfo=ET)


def _pct(price: float, ref: float) -> float:
    if pd.isna(price) or pd.isna(ref) or ref <= 0:
        return float("nan")
    return (price / ref - 1.0) * PCT


# ---- frame shaping -------------------------------------------------------------------------------------------
def _empty_frame() -> pd.DataFrame:
    return _coerce(pd.DataFrame({c: [] for c in OUTCOME_COLUMNS}))


def _coerce(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in _FLOAT_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("float64")
    for col in _TEXT_COLUMNS:
        out[col] = out[col].astype("object").where(out[col].notna(), None)
    out["delivered"] = out["delivered"].fillna(False).astype("bool")
    out["alert_ts"] = pd.to_datetime(out["alert_ts"], utc=True)
    out["ref_ts"] = pd.to_datetime(out["ref_ts"], utc=True)
    out["session"] = out["session"].astype("object").where(out["session"].notna(), None)
    return out


def _summary_columns() -> list[str]:
    cols = ["rule", "n"]
    for h in HORIZONS:
        cols.extend([f"hit_{h}", f"mean_{h}", f"median_{h}"])
    cols.extend(["rated", "useful", "traded", "precision_proxy"])
    return cols


def _summarize_group(rule: str, group: pd.DataFrame) -> dict[str, Any]:
    row: dict[str, Any] = {"rule": rule, "n": int(len(group))}
    for h in HORIZONS:
        rets = pd.to_numeric(group[f"ret_{h}_pct"], errors="coerce").dropna()
        row[f"hit_{h}"] = float((rets > 0).mean()) if len(rets) else float("nan")
        row[f"mean_{h}"] = float(rets.mean()) if len(rets) else float("nan")
        row[f"median_{h}"] = float(rets.median()) if len(rets) else float("nan")
    ratings = group["rating"].dropna().astype(str).str.lower()
    rated = int(ratings.isin([RATING_USEFUL, RATING_NOISE, RATING_TRADED]).sum())
    traded = int((ratings == RATING_TRADED).sum())
    useful = int((ratings == RATING_USEFUL).sum()) + traded
    row.update(rated=rated, useful=useful, traded=traded, precision_proxy=(useful / rated) if rated else float("nan"))
    return row
