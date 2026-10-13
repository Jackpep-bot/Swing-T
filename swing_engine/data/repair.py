"""Repair the pre-Massive-window store (docs/proposals/delisted-history-spike-2026-10.md, plan step 5).

Two contaminations from the Alpaca extension (bars before ``MASSIVE_WINDOW_START``):
* **zero-volume filler**: flat rows Alpaca writes between ticker owners or after a halt (SBNY: 395 rows at $70).
  Apply deletes them (copied first to ``repair_dropped_bars``).
* **ticker-reuse joins**: one symbol series holding a dead company and a later one (APC: Anadarko 2019 + new APC
  2026). Every gap of more than ``ENTITY_GAP_CALENDAR_DAYS`` between traded bars that starts before the window is an
  entity boundary; each segment before such a gap moves to ``TICKER~YYYYMMDD`` (its last traded bar), gets a
  ``listings`` and a ``symbols`` row (``data.delisted``), and the live company keeps the ticker. Evidence per gap
  (gap length, close-to-close jump, CIK/FIGI mismatch against ``delisted_candidates`` when enumerated) is
  reported, not required: a halt longer than the gap threshold is treated as a delisting too. Gaps at the
  Alpaca/Massive seam (``SEAM_DAYS``) are renames, not reuses, and are skipped.

A third one comes from renames (found 2026-10-13, BK/BNY, ERJ/EMBJ):
* **duplicate series**: Alpaca files a company's history under every ticker that points at it today, so two
  symbols can hold the same bars before the window: an old and a new ticker of a rename inside the window, or a
  ``TICKER~YYYYMMDD`` delisted key whose ticker was renamed (ACXM -> RAMP) or reused (P: Pandora, then Pure
  Storage; the key holds the wrong company). ``find_duplicates`` pairs them by identical (date, close, volume);
  ``merge_duplicates`` leaves one continuous series under the surviving ticker.

Every change is a row in ``repairs`` (run_id, symbol, action, rows, date range); ``undo_repair(run_id)`` reverses
a run. Nothing here calls a network.
"""
from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import structlog

from ._common import BAR_COLUMNS, session_ts
from .delisted import (
    AV_MATCH_DAYS,
    CANDIDATES_TABLE,
    DELISTED_RULES_VERSION,
    ENTITY_GAP_CALENDAR_DAYS,
    ENTITY_SEP,
    LISTINGS_TABLE,
    MASSIVE_WINDOW_START,
    SYMBOLS_TABLE,
    entity_key,
    listing_row,
    write_entities,
)

log = structlog.get_logger(__name__)

REPAIRS_TABLE = "repairs"
DROPPED_TABLE = "repair_dropped_bars"
DROP_FILLER, SPLIT = "drop_filler", "split"
MERGE, DROP_FOREIGN = "merge_duplicate", "drop_foreign"
#: Two symbols are one security when their traded bars before the window agree (same date, close and volume) on at
#: least DUP_MIN_SESSIONS sessions and DUP_MIN_SHARE of the shorter series. Two different securities do not share a
#: close and a volume for 60 sessions by chance.
DUP_MIN_SESSIONS = 60
DUP_MIN_SHARE = 0.9
#: A rename inside the window: the new ticker's first bar comes within this many calendar days of the old one's last.
HANDOFF_DAYS = 10
DUPLICATE_COLUMNS = ["symbol", "new_symbol", "dup_rows", "date_from", "date_to", "handoff"]
#: A gap that starts within this many calendar days of the window start is the Alpaca/Massive seam, not a reuse:
#: Alpaca files a renamed company's whole history under its new ticker (NAGE, ex-CDXC) while the Massive window
#: carries the old ticker until the rename, so the new ticker's series pauses at 2024-10-04. Those are left alone
#: (counted as ``seam_gaps_skipped``).
SEAM_DAYS = 7
_COLS = ", ".join(BAR_COLUMNS)
REPAIRS_SCHEMA: dict[str, str] = {
    "run_id": "VARCHAR", "seq": "INTEGER", "symbol": "VARCHAR", "action": "VARCHAR", "new_symbol": "VARCHAR",
    "rows": "BIGINT", "date_from": "DATE", "date_to": "DATE", "gap_days": "INTEGER", "price_jump": "DOUBLE",
    "cik_mismatch": "BOOLEAN", "rules_version": "VARCHAR", "applied_at": "TIMESTAMP", "reverted": "BOOLEAN",
}


def find_filler(store: Any, cutoff: date = MASSIVE_WINDOW_START) -> pd.DataFrame:
    """Per symbol: zero-volume rows before ``cutoff`` (columns symbol, rows, date_from, date_to)."""
    return store.sql(
        "SELECT symbol, count(*) AS rows, min(ts)::DATE AS date_from, max(ts)::DATE AS date_to FROM bars "
        "WHERE ts < ? AND volume = 0 AND symbol NOT LIKE ? GROUP BY symbol ORDER BY rows DESC, symbol",
        [session_ts(cutoff).to_pydatetime(), f"%{ENTITY_SEP}%"],
    )


def _old_identity(store: Any) -> pd.DataFrame | None:
    if not store.has_table(CANDIDATES_TABLE):
        return None
    cands = store.read_table(CANDIDATES_TABLE)
    cands["delist_date"] = pd.to_datetime(cands["delist_date"]).dt.date
    return cands


def find_splits(store: Any, cutoff: date = MASSIVE_WINDOW_START, gap_days: int = ENTITY_GAP_CALENDAR_DAYS) -> pd.DataFrame:
    """Segments to move off a reused ticker: symbol, new_symbol, date_from, date_to (traded bars of the dead
    entity), rows, gap_days, price_jump (|ln| close-to-close across the gap), cik_mismatch (None = unknown)."""
    gaps = store.sql(
        "WITH t AS (SELECT symbol, ts, close, lag(ts) OVER w AS prev_ts, lag(close) OVER w AS prev_close "
        "FROM bars WHERE volume > 0 AND symbol NOT LIKE ? WINDOW w AS (PARTITION BY symbol ORDER BY ts)) "
        "SELECT symbol, prev_ts::DATE AS prev_day, ts::DATE AS next_day, prev_close, close AS next_close, "
        "date_diff('day', prev_ts::DATE, ts::DATE) AS gap_days FROM t "
        "WHERE prev_ts IS NOT NULL AND prev_ts < ? AND date_diff('day', prev_ts::DATE, ts::DATE) > ? "
        "ORDER BY symbol, prev_ts",
        [f"%{ENTITY_SEP}%", session_ts(cutoff).to_pydatetime(), gap_days],
    )
    cols = ["symbol", "new_symbol", "date_from", "date_to", "rows", "gap_days", "price_jump", "cik_mismatch"]
    seam = pd.to_datetime(gaps["prev_day"]).dt.date >= cutoff - timedelta(days=SEAM_DAYS)
    gaps = gaps.loc[~seam]
    if gaps.empty:
        out = pd.DataFrame(columns=cols)
        out.attrs["seam_gaps_skipped"] = int(seam.sum())
        return out
    syms = sorted(gaps["symbol"].unique())
    stats = store.sql(
        "SELECT symbol, ts::DATE AS day FROM bars WHERE volume > 0 AND symbol IN (SELECT unnest(?)) ORDER BY symbol, ts",
        [syms],
    )
    days_by = {s: pd.Series(g["day"].to_numpy()) for s, g in stats.groupby("symbol")}
    cands = _old_identity(store)
    live = store.read_table(SYMBOLS_TABLE).set_index("symbol") if store.has_table(SYMBOLS_TABLE) else None
    rows: list[dict[str, Any]] = []
    for sym, g in gaps.groupby("symbol", sort=True):
        days = pd.to_datetime(days_by[sym]).dt.date
        start = days.iloc[0]
        for gap in g.itertuples(index=False):
            end = gap.prev_day.date() if hasattr(gap.prev_day, "date") else gap.prev_day
            n = int(((days >= start) & (days <= end)).sum())
            jump = abs(math.log(gap.next_close / gap.prev_close)) if gap.prev_close and gap.next_close else math.nan
            rows.append({"symbol": sym, "new_symbol": entity_key(sym, end), "date_from": start, "date_to": end,
                         "rows": n, "gap_days": int(gap.gap_days), "price_jump": jump,
                         "cik_mismatch": _mismatch(cands, live, sym, end)})
            start = gap.next_day.date() if hasattr(gap.next_day, "date") else gap.next_day
    out = pd.DataFrame(rows, columns=cols)
    out.attrs["seam_gaps_skipped"] = int(seam.sum())
    return out


def _match(cands: pd.DataFrame | None, sym: str, end: date) -> dict[str, Any] | None:
    if cands is None:
        return None
    hit = cands.loc[(cands["ticker"] == sym) & cands["delist_date"].map(lambda d: abs((d - end).days) <= AV_MATCH_DAYS)]
    return None if hit.empty else hit.iloc[-1].to_dict()


def _mismatch(cands: pd.DataFrame | None, live: pd.DataFrame | None, sym: str, end: date) -> bool | None:
    old = _match(cands, sym, end)
    if old is None or live is None or sym not in live.index:
        return None
    for ident in ("composite_figi", "cik"):
        a, b = old.get(ident), live.at[sym, ident] if ident in live.columns else None
        if a and b and not pd.isna(a) and not pd.isna(b):
            return str(a) != str(b)
    return None


# ----------------------------------------------------------------------------------------------- duplicates


def _first_segment(days: list[date], gap_days: int = ENTITY_GAP_CALENDAR_DAYS) -> tuple[date, date] | None:
    """First and last day of the run of ``days`` (sorted) before its first gap longer than ``gap_days``."""
    if not days:
        return None
    end = days[0]
    for d in days[1:]:
        if (d - end).days > gap_days:
            break
        end = d
    return days[0], end


def find_duplicates(store: Any, cutoff: date = MASSIVE_WINDOW_START) -> pd.DataFrame:
    """Symbols whose bars before ``cutoff`` duplicate another symbol's (module docstring): one row per symbol to
    merge away. ``symbol`` -> ``new_symbol`` (the survivor), ``dup_rows`` identical sessions between
    ``date_from`` and ``date_to``, ``handoff`` = the old ticker's last day as this security when the rename fell
    inside the window (else None). Which one survives:

    * a ``TICKER~YYYYMMDD`` key loses to a plain ticker; between two keys, or two tickers that both stopped
      before the window, the one with the earlier last bar loses;
    * two plain tickers that both trade in the window: the old one starts at the window start and the other
      takes over within ``HANDOFF_DAYS`` of the end of its first run of bars. If both fit, the one with no bars
      afterwards is the old one. Pairs that fit no rule are left alone and listed in ``attrs["unresolved"]``.
    """
    cut = session_ts(cutoff).to_pydatetime()
    pairs = store.sql(
        "WITH pre AS (SELECT symbol, ts::DATE AS d, close, volume FROM bars WHERE ts < ? AND volume > 0), "
        "n AS (SELECT symbol, count(*) AS n FROM pre GROUP BY symbol), "
        "m AS (SELECT a.symbol AS a, b.symbol AS b, count(*) AS k, min(a.d) AS kf, max(a.d) AS kl FROM pre a "
        "JOIN pre b ON a.d = b.d AND a.close = b.close AND a.volume = b.volume AND a.symbol < b.symbol "
        "GROUP BY a.symbol, b.symbol HAVING count(*) >= ?) "
        "SELECT m.a, m.b, m.k, m.kf, m.kl FROM m JOIN n na ON na.symbol = m.a JOIN n nb ON nb.symbol = m.b "
        "WHERE m.k >= ? * least(na.n, nb.n) ORDER BY m.a, m.b",
        [cut, DUP_MIN_SESSIONS, DUP_MIN_SHARE],
    )
    out = pd.DataFrame(columns=DUPLICATE_COLUMNS)
    out.attrs["unresolved"] = []
    if pairs.empty:
        return out
    syms = sorted(set(pairs["a"]) | set(pairs["b"]))
    days = store.sql("SELECT symbol, ts::DATE AS d FROM bars WHERE volume > 0 AND symbol IN (SELECT unnest(?)) "
                     "ORDER BY symbol, ts", [syms])
    days["d"] = pd.to_datetime(days["d"]).dt.date
    by = {s: g["d"].tolist() for s, g in days.groupby("symbol")}

    def old_end(x: str, y: str) -> date | None:
        """``x``'s last day as the shared security when ``y`` takes over from it inside the window."""
        seg = _first_segment([d for d in by[x] if d >= cutoff])
        if seg is None or (seg[0] - cutoff).days > SEAM_DAYS:
            return None
        return seg[1] if any(0 < (d - seg[1]).days <= HANDOFF_DAYS for d in by[y]) else None

    best: dict[str, tuple[date, dict[str, Any]]] = {}
    for p in pairs.itertuples(index=False):
        a, b = str(p.a), str(p.b)
        in_a, in_b = by[a][-1] >= cutoff, by[b][-1] >= cutoff
        key_a, key_b = ENTITY_SEP in a, ENTITY_SEP in b
        loser, handoff = None, None
        if key_a != key_b:
            loser = a if key_a else b
        elif not (in_a and in_b) or key_a:
            if by[a][-1] != by[b][-1]:
                loser = a if by[a][-1] < by[b][-1] else b
        else:
            ends = {x: old_end(x, y) for x, y in ((a, b), (b, a))}
            fits = [x for x, d in ends.items() if d is not None]
            if len(fits) == 2:
                fits = [x for x in fits if by[x][-1] == ends[x]]
            if len(fits) == 1:
                loser, handoff = fits[0], ends[fits[0]]
        if loser is None:
            out.attrs["unresolved"].append((a, b))
            continue
        winner = b if loser == a else a
        row = {"symbol": loser, "new_symbol": winner, "dup_rows": int(p.k), "date_from": pd.Timestamp(p.kf).date(),
               "date_to": pd.Timestamp(p.kl).date(), "handoff": handoff}
        if loser not in best or by[winner][-1] > best[loser][0]:  # a chain A -> B -> C: A goes straight to C
            best[loser] = (by[winner][-1], row)
    rows = sorted((r for _, r in best.values()), key=lambda r: (by[r["symbol"]][-1], r["symbol"]))
    unresolved = out.attrs["unresolved"]
    out = pd.DataFrame(rows, columns=DUPLICATE_COLUMNS)
    out.attrs["unresolved"] = unresolved
    return out


def merge_duplicates(store: Any, cutoff: date = MASSIVE_WINDOW_START) -> dict[str, Any]:
    """Merge every ``find_duplicates`` row into its survivor in one transaction, logged in ``repairs`` and
    reversible with ``undo_repair``. Per row, in order of the loser's last bar:

    * a rename inside the window: the survivor's own bars from the window start to the handoff belong to whoever
      held that ticker before (BNY was a bond fund until 2026-05-20) and are dropped (action ``drop_foreign``);
    * the loser's bars (up to the handoff, or all of them) move under the survivor where it has no bar of its own
      (the window segment, earlier history, single missing days) and are deleted from the loser. Bars of the old
      ticker after the handoff (a later owner of the ticker) stay.

    Repeats until nothing is left: a second rename in the window (BBBY -> BYON -> NXH) only shows once the first
    is merged. ``repair_dropped_bars`` keeps every bar the touched symbols had before the run, so the undo is
    exact. ``symbols`` / ``listings`` rows of merged-away keys are left in place (no bars, nothing trades them)."""
    # ponytail: the dropped ticker-holder's bars are not re-homed (Barrick's 2024-25 bars sat under GOLD and belong
    # to B). Needs a ticker-change feed (FIGI by date) to do properly; they stay recoverable in repair_dropped_bars.
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    con = store._con
    cut = session_ts(cutoff).to_pydatetime()
    rest = _COLS.split(", ", 1)[1]
    passes: list[pd.DataFrame] = []
    unresolved: list[tuple[str, str]] = []
    log_rows: list[dict[str, Any]] = []
    totals = {"moved_rows": 0, "deleted_rows": 0, "foreign_rows": 0}

    def count(where: str, params: list[Any]) -> int:
        return int(con.execute(f"SELECT count(*) FROM bars WHERE {where}", params).fetchone()[0])

    def span(where: str, params: list[Any]) -> tuple[Any, Any]:
        return con.execute(f"SELECT min(ts)::DATE, max(ts)::DATE FROM bars WHERE {where}", params).fetchone()

    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"CREATE TABLE IF NOT EXISTS {DROPPED_TABLE} AS SELECT ''::VARCHAR AS run_id, {_COLS} FROM bars LIMIT 0")
        while True:
            dups = find_duplicates(store, cutoff)
            unresolved = dups.attrs["unresolved"]
            if dups.empty:
                break
            passes.append(dups)
            con.execute(
                f"INSERT INTO {DROPPED_TABLE} SELECT ?, {_COLS} FROM bars WHERE symbol IN (SELECT unnest(?)) "
                f"AND symbol NOT IN (SELECT DISTINCT symbol FROM {DROPPED_TABLE} WHERE run_id = ?)",
                [run_id, sorted(set(dups["symbol"]) | set(dups["new_symbol"])), run_id])
            for r in dups.itertuples(index=False):
                mine, args = "symbol = ?", [r.symbol]
                if r.handoff is not None:
                    hi = session_ts(r.handoff).to_pydatetime()
                    mine, args = "symbol = ? AND ts <= ?", [r.symbol, hi]
                    foreign, fargs = "symbol = ? AND ts >= ? AND ts <= ?", [r.new_symbol, cut, hi]
                    n_foreign = count(foreign, fargs)
                    if n_foreign:
                        lo_day, hi_day = span(foreign, fargs)
                        con.execute(f"DELETE FROM bars WHERE {foreign}", fargs)
                        log_rows.append({"symbol": r.new_symbol, "action": DROP_FOREIGN, "new_symbol": None,
                                         "rows": n_foreign, "date_from": lo_day, "date_to": hi_day})
                        totals["foreign_rows"] += n_foreign
                n_loser, before = count(mine, args), count("symbol = ?", [r.new_symbol])
                lo_day, hi_day = span(mine, args)
                con.execute(f"INSERT INTO bars ({_COLS}) SELECT ?, {rest} FROM bars WHERE {mine} "
                            "ON CONFLICT DO NOTHING", [r.new_symbol, *args])
                con.execute(f"DELETE FROM bars WHERE {mine}", args)
                log_rows.append({"symbol": r.symbol, "action": MERGE, "new_symbol": r.new_symbol, "rows": n_loser,
                                 "date_from": lo_day, "date_to": hi_day})
                totals["moved_rows"] += count("symbol = ?", [r.new_symbol]) - before
                totals["deleted_rows"] += n_loser
        _log_repairs(store, log_rows, run_id)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    merged = pd.concat(passes, ignore_index=True) if passes else pd.DataFrame(columns=DUPLICATE_COLUMNS)
    log.info("duplicates_merged", run_id=run_id, merged=len(merged), **totals)
    return {"run_id": run_id, "duplicates": merged, "merged": len(merged), "unresolved": unresolved, **totals}


def _log_repairs(store: Any, log_rows: list[dict[str, Any]], run_id: str) -> None:
    if not log_rows:
        return
    frame = pd.DataFrame(log_rows).assign(run_id=run_id, rules_version=DELISTED_RULES_VERSION,
                                          applied_at=datetime.now(UTC).replace(tzinfo=None), reverted=False)
    frame["seq"] = range(len(frame))
    store.write_table(REPAIRS_TABLE, frame.reindex(columns=list(REPAIRS_SCHEMA)), ["run_id", "seq"],
                      schema=REPAIRS_SCHEMA)


def plan(store: Any, cutoff: date = MASSIVE_WINDOW_START) -> dict[str, Any]:
    filler, splits = find_filler(store, cutoff), find_splits(store, cutoff)
    return {"filler": filler, "splits": splits, "filler_rows": int(filler["rows"].sum()) if len(filler) else 0,
            "filler_symbols": len(filler), "split_symbols": int(splits["symbol"].nunique()),
            "split_segments": len(splits), "split_rows": int(splits["rows"].sum()) if len(splits) else 0,
            "seam_gaps_skipped": splits.attrs.get("seam_gaps_skipped", 0)}


def apply(store: Any, cutoff: date = MASSIVE_WINDOW_START) -> dict[str, Any]:
    """Drop the filler and split the joined series in one transaction; returns the plan plus ``run_id``."""
    p = plan(store, cutoff)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    con = store._con
    cut = session_ts(cutoff).to_pydatetime()
    log_rows: list[dict[str, Any]] = []
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"CREATE TABLE IF NOT EXISTS {DROPPED_TABLE} AS SELECT ''::VARCHAR AS run_id, {_COLS} FROM bars LIMIT 0")
        con.execute(f"INSERT INTO {DROPPED_TABLE} SELECT ?, {_COLS} FROM bars WHERE ts < ? AND volume = 0 "
                    f"AND symbol NOT LIKE ?", [run_id, cut, f"%{ENTITY_SEP}%"])
        con.execute("DELETE FROM bars WHERE ts < ? AND volume = 0 AND symbol NOT LIKE ?", [cut, f"%{ENTITY_SEP}%"])
        for r in p["filler"].itertuples(index=False):
            log_rows.append({"symbol": r.symbol, "action": DROP_FILLER, "new_symbol": None, "rows": int(r.rows),
                             "date_from": r.date_from, "date_to": r.date_to})
        cands = _old_identity(store)
        listings, metas = [], []
        for r in p["splits"].itertuples(index=False):
            lo, hi = session_ts(r.date_from).to_pydatetime(), session_ts(r.date_to).to_pydatetime()
            con.execute(f"INSERT INTO bars ({_COLS}) SELECT ?, {_COLS.split(', ', 1)[1]} FROM bars "
                        "WHERE symbol = ? AND ts BETWEEN ? AND ? ON CONFLICT DO NOTHING", [r.new_symbol, r.symbol, lo, hi])
            con.execute("DELETE FROM bars WHERE symbol = ? AND ts BETWEEN ? AND ?", [r.symbol, lo, hi])
            seg = store.read_bars([r.new_symbol])
            meta = _match(cands, r.symbol, r.date_to) or {}
            listings.append(listing_row(r.new_symbol, seg, meta, "repair"))
            metas.append(meta)
            log_rows.append({"symbol": r.symbol, "action": SPLIT, "new_symbol": r.new_symbol, "rows": int(r.rows),
                             "date_from": r.date_from, "date_to": r.date_to, "gap_days": int(r.gap_days),
                             "price_jump": float(r.price_jump), "cik_mismatch": r.cik_mismatch})
        write_entities(store, listings, metas)
        _log_repairs(store, log_rows, run_id)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    log.info("store_repaired", run_id=run_id, filler_rows=p["filler_rows"], split_segments=p["split_segments"])
    return {**p, "run_id": run_id}


def undo_repair(store: Any, run_id: str) -> dict[str, int]:
    """Reverse one ``apply`` or ``merge_duplicates`` run: move split segments back under the ticker, take merged
    rows back out of their survivor, restore every dropped row, drop the run's listings / symbols rows, mark its
    ``repairs`` rows reverted. (A key the delisted ingest also wrote moves back with it.)"""
    log_rows = store.read_table(REPAIRS_TABLE, "run_id = ? AND NOT reverted", [run_id])
    if log_rows.empty:
        raise ValueError(f"no unreverted repair run {run_id!r}")
    con = store._con
    moved = restored = 0
    con.execute("BEGIN TRANSACTION")
    try:
        for r in log_rows.loc[log_rows["action"] == SPLIT].itertuples(index=False):
            con.execute(f"INSERT INTO bars ({_COLS}) SELECT ?, {_COLS.split(', ', 1)[1]} FROM bars WHERE symbol = ? "
                        "ON CONFLICT DO NOTHING", [r.symbol, r.new_symbol])
            moved += int(con.execute("SELECT count(*) FROM bars WHERE symbol = ?", [r.new_symbol]).fetchone()[0])
            con.execute("DELETE FROM bars WHERE symbol = ?", [r.new_symbol])
            for table, col in ((LISTINGS_TABLE, "key"), (SYMBOLS_TABLE, "symbol")):
                store.delete(table, f"{col} = ?", [r.new_symbol])
        merges = log_rows.loc[log_rows["action"].isin([MERGE, DROP_FOREIGN])]
        if len(merges):  # the run's snapshot holds every bar these symbols had; bars ingested since stay
            touched = sorted(set(merges["symbol"]) | set(merges["new_symbol"].dropna()))
            con.execute(f"DELETE FROM bars WHERE symbol IN (SELECT unnest(?)) AND ts <= (SELECT max(d.ts) FROM "
                        f"{DROPPED_TABLE} d WHERE d.run_id = ? AND d.symbol = bars.symbol)", [touched, run_id])
        if store.has_table(DROPPED_TABLE):
            restored = int(con.execute(f"SELECT count(*) FROM {DROPPED_TABLE} WHERE run_id = ?", [run_id]).fetchone()[0])
            con.execute(f"INSERT INTO bars ({_COLS}) SELECT {_COLS} FROM {DROPPED_TABLE} WHERE run_id = ? "
                        "ON CONFLICT DO NOTHING", [run_id])
            con.execute(f"DELETE FROM {DROPPED_TABLE} WHERE run_id = ?", [run_id])
        con.execute(f"UPDATE {REPAIRS_TABLE} SET reverted = TRUE WHERE run_id = ?", [run_id])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"moved_back": moved, "filler_restored": restored}


__all__ = ["apply", "find_duplicates", "find_filler", "find_splits", "merge_duplicates", "plan", "undo_repair"]
