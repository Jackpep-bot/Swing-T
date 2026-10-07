"""Shadow ledger: record every strategy signal (taken or not) and grade it later against the bars that followed.

The point is to measure the *signals*, independent of sizing, cash and slot limits: a signal the router or the
risk layer skipped is graded exactly like one that became an order, so the playbook's choices can be audited
(``docs/methods.md`` section 8 item 9: "each is a logged experiment, not a choice to make by argument").

Table ``shadow_signals`` (DuckDB, via ``data.store.Store.write_table``) is keyed ``(strategy, symbol, as_of)``.

Grading rules (``grade_signals``), all on daily bars dated strictly after the signal date:

* entry = the next session's open (``entry_type`` stop / limit: the fill at ``entry`` on that session, or ``not_triggered``
  when the bar never reaches it). When that open is already through the stop (or, for a long, at or above the
  target) the signal is ``entry_skipped``: the setup's geometry no longer exists (``docs/methods.md`` 2e,
  "model gap-through-stop").
* then the first touch of the stop or the target decides the outcome, bar by bar: a later open through the stop or
  the target fills at that open; inside a bar the stop wins when both the stop and the target are touched (we cannot
  know the intrabar order, so we assume the worse one; same convention as ``research.backtest``).
* untouched after ``h`` sessions (the entry session counts as 1): exit at the close of session ``h``
  (``time_exit``). A horizon that has not matured and is not resolved yet is ``pending``.
* a symbol whose bars stop (delisted, acquired, moved to OTC, long halt) ``DELIST_GRACE_SESSIONS`` sessions before
  the store's latest session resolves its open horizons as ``delisted`` at its last close (a trade, like
  ``research.backtest.ExitReason.DELISTED``), so the statistics are not survivors-only; with no bar after the
  signal at all it is ``entry_skipped`` (``delisted_before_entry``).
* a horizon that is final is never rewritten by a later pass. Stored bars are split-adjusted and
  ``data.ingest.repair_splits`` rewrites a symbol's history after a split, so before grading the recorded stop and
  target are divided by the product of the ``splits`` table ratios with ``as_of < ex_date <= grading date`` (the
  same convention as ``data.universe.as_traded``): prices and bars are then in the same space and R is unchanged.

Results are in R (risk per share at the actual entry), gross of costs, so ``result_r`` measures the setup, not the
broker. ``mfe_r`` / ``mae_r`` are the best and worst excursions while held (``mae_r`` positive = adverse), the same
sign convention as ``research.backtest`` trades. Per-horizon columns are suffixed ``_<h>d``; the unsuffixed
outcome columns mirror the longest horizon. Nothing here reads a model or an LLM.
"""
from __future__ import annotations

import math
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import EntryType, Side, Signal
from swing_engine.risk.sizing import make_client_order_id

log = structlog.get_logger(__name__)

SHADOW_TABLE = "shadow_signals"
#: ``research.replay.run_replay``'s default ledger: research replays never overwrite or mix with the live nightly's
#: rows (same key: strategy, symbol, as_of). ``swing shadow report --replay`` reads it.
REPLAY_SHADOW_TABLE = "shadow_signals_replay"
KEYS: tuple[str, ...] = ("strategy", "symbol", "as_of")
#: docs/methods.md 2f "Time exits" (momentum bursts 3-5 days) and the 5-20 day swing hold window of section 2.
DEFAULT_HORIZONS: tuple[int, ...] = (5, 10, 20)
UNKNOWN_REGIME = "unknown"
SOURCE_LIVE = "live"
TAKEN_KEY_SEP = ":"


class Hit(StrEnum):
    TARGET = "target_hit"
    STOP = "stop_hit"
    TIME = "time_exit"
    SKIPPED = "entry_skipped"
    DELISTED = "delisted"
    PENDING = "pending"


FINAL_HITS = frozenset({Hit.TARGET.value, Hit.STOP.value, Hit.TIME.value, Hit.SKIPPED.value, Hit.DELISTED.value})
TRADE_HITS = frozenset({Hit.TARGET.value, Hit.STOP.value, Hit.TIME.value, Hit.DELISTED.value})
#: sessions with no bar for the symbol, counted up to the store's latest session, before it is treated as gone
DELIST_GRACE_SESSIONS = 5
SKIP_DELISTED_BEFORE_ENTRY = "delisted_before_entry"
SPLITS_TABLE = "splits"  # data.ingest.SPLITS_TABLE: symbol, ex_date, ratio (split_to / split_from)
SKIP_OPEN_THROUGH_STOP = "open_through_stop"
SKIP_OPEN_THROUGH_TARGET = "open_through_target"
SKIP_NOT_TRIGGERED = "not_triggered"  # a stop/limit entry the next session never reached

SIGNAL_SCHEMA: dict[str, str] = {
    "strategy": "VARCHAR",
    "symbol": "VARCHAR",
    "as_of": "DATE",
    "side": "VARCHAR",
    "entry": "DOUBLE",
    "entry_type": "VARCHAR",
    "stop": "DOUBLE",
    "target": "DOUBLE",
    "reward_risk": "DOUBLE",
    "score": "DOUBLE",
    "taken": "BOOLEAN",
    "regime": "VARCHAR",
    "source": "VARCHAR",
    "recorded_at": "VARCHAR",
}
OUTCOME_SCHEMA: dict[str, str] = {
    "hit": "VARCHAR",
    "skip_reason": "VARCHAR",
    "entry_date": "DATE",
    "entry_price": "DOUBLE",
    "exit_date": "DATE",
    "exit_price": "DOUBLE",
    "result_r": "DOUBLE",
    "mfe_r": "DOUBLE",
    "mae_r": "DOUBLE",
    "bars_held": "DOUBLE",
    "graded_through": "DATE",
}
HORIZON_FIELDS: dict[str, str] = {
    "hit": "VARCHAR",
    "result_r": "DOUBLE",
    "mfe_r": "DOUBLE",
    "mae_r": "DOUBLE",
    "exit_date": "DATE",
}


def horizon_column(name: str, horizon: int) -> str:
    """``result_r`` + 10 -> ``result_r_10d``."""
    return f"{name}_{int(horizon)}d"


def table_schema(horizons: Iterable[int] = DEFAULT_HORIZONS) -> dict[str, str]:
    schema = {**SIGNAL_SCHEMA, **OUTCOME_SCHEMA}
    for h in sorted({int(x) for x in horizons}):
        schema.update({horizon_column(k, h): t for k, t in HORIZON_FIELDS.items()})
    return schema


def signal_key(signal: Signal) -> str:
    """``strategy:symbol``: one of the forms ``record_signals`` accepts in ``taken``."""
    return f"{signal.strategy}{TAKEN_KEY_SEP}{signal.symbol}"


def _is_taken(signal: Signal, taken: Collection[str]) -> bool:
    """``taken`` may hold ``strategy:symbol`` keys, ``risk.sizing.make_client_order_id`` ids or bare symbols."""
    return signal_key(signal) in taken or make_client_order_id(signal) in taken or signal.symbol in taken


def _as_date(value: Any) -> date:
    if isinstance(value, pd.Timestamp | datetime):
        return value.date()
    if isinstance(value, str):
        return pd.Timestamp(value).date()
    return value


def _opt_float(value: float | None) -> float:
    return math.nan if value is None else float(value)


# ----------------------------------------------------------------------------------------------- record


def record_signals(
    store: Any,
    signals: list[Signal],
    taken: set[str],
    as_of: date,
    regime: str | None,
    *,
    source: str = SOURCE_LIVE,
    table: str = SHADOW_TABLE,
) -> int:
    """Upsert one row per signal into ``table`` keyed ``(strategy, symbol, as_of)``; returns rows written.

    Re-recording a key refreshes the signal columns (``taken``, ``regime`` ...) and keeps any outcome already
    graded. ``source`` tags who wrote the row (``live`` nightly scan, ``replay`` research run).
    """
    if not signals:
        return 0
    day = _as_date(as_of)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for sig in signals:
        if sig.as_of != day:
            log.warning("shadow.as_of_mismatch", symbol=sig.symbol, strategy=sig.strategy, signal=str(sig.as_of),
                        recorded=str(day))
        rows.append(
            {
                "strategy": sig.strategy,
                "symbol": sig.symbol,
                "as_of": day,
                "side": sig.side.value,
                "entry": float(sig.entry),
                "entry_type": sig.entry_type.value,
                "stop": float(sig.stop),
                "target": _opt_float(sig.target),
                "reward_risk": _opt_float(sig.reward_risk),
                "score": float(sig.score),
                "taken": bool(_is_taken(sig, taken)),
                "regime": regime,
                "source": source,
                "recorded_at": stamp,
            }
        )
    frame = pd.DataFrame(rows)
    frame["regime"] = frame["regime"].astype("string")
    written = store.write_table(table, frame, list(KEYS), schema=table_schema())
    log.info("shadow.recorded", as_of=str(day), rows=written, taken=int(frame["taken"].sum()), regime=regime)
    return int(written)


# ----------------------------------------------------------------------------------------------- grade


@dataclass(frozen=True)
class Outcome:
    hit: str
    result_r: float = math.nan
    mfe_r: float = math.nan
    mae_r: float = math.nan
    exit_date: date | None = None
    exit_price: float = math.nan
    bars_held: float = math.nan


@dataclass(frozen=True)
class Grade:
    """Every horizon's outcome for one signal plus the entry facts."""

    by_horizon: dict[int, Outcome]
    entry_date: date | None
    entry_price: float
    skip_reason: str | None


def grade_one(
    side: Side | str,
    stop: float,
    target: float | None,
    bars: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    *,
    delisted: bool = False,
    entry_type: EntryType | str = EntryType.OPEN,
    entry_level: float | None = None,
) -> Grade:
    """Grade one signal on ``bars`` (columns ``day, open, high, low, close``; sessions strictly after the signal,
    oldest first, none after the grading date). ``delisted``: the symbol has stopped trading, so horizons the
    bars cannot reach close at the last close. Pure function: the rules are in the module docstring."""
    hs = sorted({int(h) for h in horizons})
    pending = {h: Outcome(Hit.PENDING.value) for h in hs}
    if bars.empty:
        if delisted:
            return Grade({h: Outcome(Hit.SKIPPED.value) for h in hs}, None, math.nan, SKIP_DELISTED_BEFORE_ENTRY)
        return Grade(pending, None, math.nan, None)
    d = 1.0 if Side(side) == Side.LONG else -1.0
    days = list(bars["day"])
    o = bars["open"].to_numpy(dtype=float)
    hi = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    entry = float(o[0])
    kind = EntryType(entry_type or EntryType.OPEN)
    if kind != EntryType.OPEN and entry_level is not None and math.isfinite(entry_level) and math.isfinite(entry):
        lvl = float(entry_level)
        is_stop = kind == EntryType.STOP
        reached = (float(hi[0]) >= lvl if d > 0 else float(lo[0]) <= lvl) if is_stop else \
            (float(lo[0]) <= lvl if d > 0 else float(hi[0]) >= lvl)
        if not reached:
            out = Outcome(Hit.SKIPPED.value, exit_date=days[0])
            return Grade({h: out for h in hs}, days[0], entry, SKIP_NOT_TRIGGERED)
        entry = (max if (d > 0) == is_stop else min)(entry, lvl)
    has_target = target is not None and math.isfinite(float(target))
    tgt = float(target) if has_target else math.nan
    skip: str | None = None
    if not math.isfinite(entry) or d * (entry - stop) <= 0:
        skip = SKIP_OPEN_THROUGH_STOP
    elif has_target and d * (entry - tgt) >= 0:
        skip = SKIP_OPEN_THROUGH_TARGET
    if skip is not None:
        out = Outcome(Hit.SKIPPED.value, exit_date=days[0])
        return Grade({h: out for h in hs}, days[0], entry, skip)

    risk = d * (entry - stop)
    fav = hi if d > 0 else lo
    adv = lo if d > 0 else hi
    mfe = 0.0
    mae = 0.0
    resolved: Outcome | None = None
    resolved_at = -1
    time_exits: dict[int, Outcome] = {}
    max_h = hs[-1]
    for k in range(min(len(days), max_h)):
        ok, fk, ak, ck = float(o[k]), float(fav[k]), float(adv[k]), float(c[k])
        exit_px: float | None = None
        hit: Hit | None = None
        if k > 0 and d * (ok - stop) <= 0:
            exit_px, hit, fk, ak = ok, Hit.STOP, ok, ok  # gapped through the stop: out at the open
        elif k > 0 and has_target and d * (ok - tgt) >= 0:
            exit_px, hit, fk, ak = ok, Hit.TARGET, ok, ok  # gapped through the target: the resting limit fills
        elif d * (ak - stop) <= 0:
            exit_px, hit, fk = stop, Hit.STOP, ok  # stop first when both touch: no credit for the bar's best
        elif has_target and d * (fk - tgt) >= 0:
            exit_px, hit, fk = tgt, Hit.TARGET, tgt
        mfe = max(mfe, d * (fk - entry) / risk)
        mae = max(mae, -d * (ak - entry) / risk)
        if hit is not None and exit_px is not None:
            resolved = Outcome(hit.value, d * (exit_px - entry) / risk, mfe, mae, days[k], exit_px, float(k + 1))
            resolved_at = k
            break
        if (k + 1) in hs:
            time_exits[k + 1] = Outcome(Hit.TIME.value, d * (ck - entry) / risk, mfe, mae, days[k], ck, float(k + 1))
    by_h: dict[int, Outcome] = {}
    n = min(len(days), max_h)
    gone = None
    if delisted and resolved is None:
        last_close = float(c[n - 1])
        gone = Outcome(Hit.DELISTED.value, d * (last_close - entry) / risk, mfe, mae, days[n - 1], last_close, float(n))
    for h in hs:
        if resolved is not None and resolved_at < h:
            by_h[h] = resolved
        else:
            by_h[h] = time_exits.get(h, gone if gone is not None and n < h else pending[h])
    return Grade(by_h, days[0], entry, None)


def _bars_by_symbol(store: Any, symbols: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
    bars = store.read_bars(symbols, start, end)
    if bars is None or bars.empty:
        return {}
    ts = pd.to_datetime(bars["ts"])
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert("America/New_York").dt.tz_localize(None)
    bars = bars.assign(day=[t.date() for t in ts]).sort_values(["symbol", "day"], kind="stable")
    return {str(s): g.reset_index(drop=True) for s, g in bars.groupby("symbol", sort=False)}


def _load_splits(store: Any) -> pd.DataFrame | None:
    """The store's ``splits`` table (symbol upper-cased, ex_date as date), or None when there is none."""
    try:
        if not store.has_table(SPLITS_TABLE):
            return None
        splits = store.read_table(SPLITS_TABLE)
    except Exception as e:  # noqa: BLE001 - optional input: without it prices are graded as recorded
        log.info("shadow.splits_unavailable", error=str(e))
        return None
    if splits is None or splits.empty or not {"symbol", "ex_date", "ratio"} <= set(splits.columns):
        return None
    return splits.assign(
        symbol=splits["symbol"].astype(str).str.upper(), ex_date=pd.to_datetime(splits["ex_date"]).dt.date
    )


def split_factor(splits: pd.DataFrame | None, symbol: str, after: date, through: date) -> float:
    """Product of ``ratio`` over ``symbol``'s splits with ``after < ex_date <= through``: a price recorded on
    ``after`` divided by this is in the price space of split-adjusted bars stored through ``through``."""
    if splits is None:
        return 1.0
    rows = splits.loc[(splits["symbol"] == str(symbol).upper()) & (splits["ex_date"] > after)
                      & (splits["ex_date"] <= through)]
    factor = 1.0
    for ratio in rows["ratio"]:
        if ratio is not None and not pd.isna(ratio) and float(ratio) > 0:
            factor *= float(ratio)
    return factor


def _sessions_between(after: date, through: date) -> int:
    """NYSE sessions in ``(after, through]`` (business days when the calendar is unavailable)."""
    if through <= after:
        return 0
    try:
        from swing_engine.data.calendar import trading_days

        return len([d for d in trading_days(after, through) if d > after])
    except Exception:  # noqa: BLE001 - calendar data missing: weekdays are close enough for a grace period
        return len(pd.bdate_range(after + timedelta(days=1), through))


def _store_last_session(store: Any, day: date) -> date:
    """The store's latest bar date capped at ``day`` (a stale store must not make every name look delisted)."""
    snapshot = getattr(store, "snapshot_date", None)
    try:
        last = snapshot() if callable(snapshot) else None
    except Exception:  # noqa: BLE001
        last = None
    return day if last is None else min(_as_date(last), day)


def _keep_final_horizons(row: dict[str, Any], rec: dict[str, Any], horizons: Sequence[int]) -> None:
    """A horizon already final in the stored record keeps its stored outcome: a later pass (re-graded because a
    longer horizon is still pending) never rewrites a result that was already counted."""
    for h in horizons:
        if rec.get(horizon_column("hit", h)) in FINAL_HITS:
            for name in HORIZON_FIELDS:
                col = horizon_column(name, h)
                row[col] = rec.get(col)


def _needs_grading(frame: pd.DataFrame, horizons: Sequence[int]) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    for h in horizons:
        col = horizon_column("hit", h)
        if col not in frame.columns:
            return pd.Series(True, index=frame.index)
        mask |= ~frame[col].isin(FINAL_HITS)
    return mask


def _outcome_row(key: dict[str, Any], grade: Grade, horizons: Sequence[int], as_of: date) -> dict[str, Any]:
    primary = grade.by_horizon[max(horizons)]
    row: dict[str, Any] = {
        **key,
        "hit": primary.hit,
        "skip_reason": grade.skip_reason,
        "entry_date": grade.entry_date,
        "entry_price": grade.entry_price,
        "exit_date": primary.exit_date,
        "exit_price": primary.exit_price,
        "result_r": primary.result_r,
        "mfe_r": primary.mfe_r,
        "mae_r": primary.mae_r,
        "bars_held": primary.bars_held,
        "graded_through": as_of,
    }
    for h in horizons:
        out = grade.by_horizon[h]
        row.update(
            {
                horizon_column("hit", h): out.hit,
                horizon_column("result_r", h): out.result_r,
                horizon_column("mfe_r", h): out.mfe_r,
                horizon_column("mae_r", h): out.mae_r,
                horizon_column("exit_date", h): out.exit_date,
            }
        )
    return row


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    """String columns as pandas ``string`` so an all-None column still maps to VARCHAR in DuckDB."""
    out = frame.copy()
    for col in out.columns:
        if col == "hit" or col.startswith("hit_") or col in ("skip_reason", "strategy", "symbol"):
            out[col] = out[col].astype("string")
    return out


def grade_signals(
    store: Any,
    as_of: date,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    *,
    table: str = SHADOW_TABLE,
) -> int:
    """Fill the outcome columns of every recorded signal dated before ``as_of`` that is not final yet.

    Reads daily bars from ``store`` strictly after each signal's date and on or before ``as_of``, with the
    recorded stop/target put into the bars' split-adjusted price space; horizons already final keep their stored
    outcome. Returns the number of signals with at least one horizon newly resolved (target/stop/time/
    entry_skipped) by this call.
    """
    hs = sorted({int(h) for h in horizons})
    if not hs or hs[0] < 1:
        raise ValueError(f"horizons must be positive integers, got {horizons}")
    day = _as_date(as_of)
    if not store.has_table(table):
        return 0
    frame = store.read_table(table)
    if frame.empty:
        return 0
    frame["as_of"] = pd.to_datetime(frame["as_of"]).dt.date
    frame = frame.loc[frame["as_of"] < day]
    frame = frame.loc[_needs_grading(frame, hs)]
    if frame.empty:
        return 0
    first = min(frame["as_of"]) + timedelta(days=1)
    bars = _bars_by_symbol(store, sorted(frame["symbol"].astype(str).unique()), first, day)
    splits = _load_splits(store)
    market_last = _store_last_session(store, day)
    rows: list[dict[str, Any]] = []
    newly = 0
    for rec in frame.to_dict("records"):
        sym_bars = bars.get(str(rec["symbol"]))
        after = sym_bars.loc[sym_bars["day"] > rec["as_of"]] if sym_bars is not None else pd.DataFrame()
        last_bar = max(after["day"]) if len(after) else rec["as_of"]
        delisted = _sessions_between(last_bar, market_last) >= DELIST_GRACE_SESSIONS
        factor = split_factor(splits, str(rec["symbol"]), rec["as_of"], day)
        target = rec.get("target")
        target = None if target is None or pd.isna(target) else float(target) / factor
        kind = rec.get("entry_type")
        kind = EntryType.OPEN if kind is None or pd.isna(kind) else kind
        grade = grade_one(str(rec["side"]), float(rec["stop"]) / factor, target, after, hs, delisted=delisted,
                          entry_type=kind, entry_level=float(rec["entry"]) / factor)
        key = {k: rec[k] for k in KEYS}
        row = _outcome_row(key, grade, hs, day)
        _keep_final_horizons(row, rec, hs)
        rows.append(row)
        before = {h: rec.get(horizon_column("hit", h)) for h in hs}
        if any(row[horizon_column("hit", h)] in FINAL_HITS and before[h] not in FINAL_HITS for h in hs):
            newly += 1
    store.write_table(table, _typed(pd.DataFrame(rows)), list(KEYS), schema=table_schema(hs))
    log.info("shadow.graded", as_of=str(day), checked=len(rows), resolved=newly, horizons=hs)
    return newly


# ----------------------------------------------------------------------------------------------- report

REPORT_COLUMNS = [
    "n_signals", "n_taken", "n_pending", "n_skipped", "n", "win_rate", "avg_r", "avg_win_r", "avg_loss_r",
    "expectancy", "profit_factor", "total_r", "avg_mfe_r", "avg_mae_r", "n_target", "n_stop", "n_time",
]


def _profit_factor(r: pd.Series) -> float:
    wins = float(r[r > 0].sum())
    losses = float(-r[r < 0].sum())
    if losses > 0:
        return wins / losses
    return math.inf if wins > 0 else math.nan


def _group_stats(g: pd.DataFrame, hit_col: str, r_col: str, mfe_col: str, mae_col: str) -> dict[str, Any]:
    hits = g[hit_col].fillna(Hit.PENDING.value).astype(str)
    trades = g.loc[hits.isin(TRADE_HITS)]
    r = trades[r_col].astype(float)
    n = len(trades)
    wins, losses = r[r > 0], r[r < 0]
    win_rate = len(wins) / n if n else math.nan
    loss_rate = len(losses) / n if n else math.nan
    avg_win = float(wins.mean()) if len(wins) else math.nan
    avg_loss = float(losses.mean()) if len(losses) else math.nan
    expectancy = (
        (win_rate * (avg_win if len(wins) else 0.0) + loss_rate * (avg_loss if len(losses) else 0.0)) if n else math.nan
    )
    return {
        "n_signals": len(g),
        "n_taken": int(g["taken"].fillna(False).astype(bool).sum()) if "taken" in g.columns else 0,
        "n_pending": int((~hits.isin(FINAL_HITS)).sum()),
        "n_skipped": int((hits == Hit.SKIPPED.value).sum()),
        "n": n,
        "win_rate": win_rate,
        "avg_r": float(r.mean()) if n else math.nan,
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss,
        "expectancy": expectancy,
        "profit_factor": _profit_factor(r) if n else math.nan,
        "total_r": float(r.sum()) if n else 0.0,
        "avg_mfe_r": float(trades[mfe_col].astype(float).mean()) if n else math.nan,
        "avg_mae_r": float(trades[mae_col].astype(float).mean()) if n else math.nan,
        "n_target": int((hits == Hit.TARGET.value).sum()),
        "n_stop": int((hits == Hit.STOP.value).sum()),
        "n_time": int((hits == Hit.TIME.value).sum()),
    }


def summarize_outcomes(
    frame: pd.DataFrame,
    group_by: Sequence[str] = ("strategy", "regime"),
    *,
    horizon: int | None = None,
) -> pd.DataFrame:
    """Per-group stats over an outcome frame (the shadow table or anything with the same columns)."""
    cols = list(group_by)
    suffix = (lambda name: horizon_column(name, horizon)) if horizon is not None else (lambda name: name)
    hit_col, r_col, mfe_col, mae_col = suffix("hit"), suffix("result_r"), suffix("mfe_r"), suffix("mae_r")
    if frame.empty or hit_col not in frame.columns:
        if cols:
            return pd.DataFrame(columns=[*cols, *REPORT_COLUMNS])
        blank = pd.DataFrame({c: pd.Series(dtype=float) for c in (hit_col, r_col, mfe_col, mae_col)})
        return pd.DataFrame([_group_stats(blank, hit_col, r_col, mfe_col, mae_col)], columns=REPORT_COLUMNS)
    data = frame.copy()
    for col in cols:
        if col not in data.columns:
            raise KeyError(f"group_by column {col!r} not in the shadow table")
        data[col] = data[col].astype(object).where(data[col].notna(), UNKNOWN_REGIME if col == "regime" else None)
    if not cols:
        return pd.DataFrame([_group_stats(data, hit_col, r_col, mfe_col, mae_col)], columns=REPORT_COLUMNS)
    rows = []
    for key, g in data.groupby(cols, sort=True, dropna=False):
        key_t = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(cols, key_t, strict=True)), **_group_stats(g, hit_col, r_col, mfe_col, mae_col)})
    return pd.DataFrame(rows, columns=[*cols, *REPORT_COLUMNS]).reset_index(drop=True)


def shadow_report(
    store: Any,
    since: date | None = None,
    group_by: Sequence[str] = ("strategy", "regime"),
    *,
    horizon: int | None = None,
    taken: bool | None = None,
    table: str = SHADOW_TABLE,
) -> pd.DataFrame:
    """n, win rate, avg R, expectancy (R per trade), profit factor ... per group of graded shadow signals.

    ``horizon`` picks the ``_<h>d`` columns (None = the unsuffixed, longest-horizon outcome); ``taken`` filters
    to signals that were (True) or were not (False) turned into orders. ``entry_skipped`` and ``pending`` rows are
    counted but excluded from the R statistics.
    """
    if not store.has_table(table):
        return summarize_outcomes(pd.DataFrame(), group_by, horizon=horizon)
    frame = store.read_table(table)
    if frame.empty:
        return summarize_outcomes(frame, group_by, horizon=horizon)
    frame["as_of"] = pd.to_datetime(frame["as_of"]).dt.date
    if since is not None:
        frame = frame.loc[frame["as_of"] >= _as_date(since)]
    if taken is not None and "taken" in frame.columns:
        frame = frame.loc[frame["taken"].fillna(False).astype(bool) == taken]
    return summarize_outcomes(frame, group_by, horizon=horizon)


__all__ = [
    "DEFAULT_HORIZONS",
    "REPLAY_SHADOW_TABLE",
    "SHADOW_TABLE",
    "Grade",
    "Hit",
    "Outcome",
    "grade_one",
    "grade_signals",
    "horizon_column",
    "record_signals",
    "shadow_report",
    "signal_key",
    "split_factor",
    "summarize_outcomes",
    "table_schema",
]

