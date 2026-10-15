"""Grade docs/preregistration/2026-10-10-exit-1r.md: every recorded replay signal again with its target moved to
``entry + TARGET_R x (entry - stop)``, everything else as recorded, through ``research.shadow.grade_signals``.

The source stores are opened read-only. Worker processes grade a week of signals at a time in memory (bars, splits
and listings read from the signal's own store); this process appends the results to a scratch store, one table per
(store, month), so a stopped run resumes where it was.

    uv run python -m swing_engine.research.regrade            # regrade (resumes), then write docs/leaderboard_t1r.md
    uv run python -m swing_engine.research.regrade --check data/live/replay_r2.duckdb:2025-03-10   # reproduction check
"""
from __future__ import annotations

import argparse
import math
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from swing_engine.data.store import Store
from swing_engine.research.cards import ROOT, WINDOWS, Window, executable, with_costs
from swing_engine.research.leaderboard import edge_stats, leaderboard, log_board_trials, render, survivors
from swing_engine.research.shadow import (
    DEFAULT_HORIZONS,
    KEYS,
    REPLAY_SHADOW_TABLE,
    SIGNAL_SCHEMA,
    TRADE_HITS,
    Hit,
    _typed,
    grade_signals,
    horizon_column,
    table_schema,
)
from swing_engine.research.walkforward_ensemble import EXCLUDED

log = structlog.get_logger(__name__)

TARGET_R = 1.0
SUFFIX = "@t1r"
#: read order = research.cards.read_shadow's in the earlier reports: the last store wins a duplicate key
SOURCES = ("data/live/replay_r2.duckdb", "data/live/replay_r1.duckdb", "data/live/replay_news.duckdb")
SCRATCH = "data/live/regrade_1r.duckdb"
OUT = "docs/leaderboard_t1r.md"
PREREG = "docs/preregistration/2026-10-10-exit-1r.md"
BATCH2 = ("fomc_cycle_even_weeks", "large_cap_net_repurchasers", "volatility_managed_spy")
POOLED_HORIZON = 20
POOLED_MIN_T = 2.0
#: calendar days of bars read after a chunk's last signal: 20 sessions need about 30
BARS_AFTER_DAYS = 90
COST_COLUMNS = ("cost_bps", "dollar_volume")
#: measured: a worker reaches about 1.4 GB and this process up to 1.8 GB; 3 workers peaked at 5.9 GB in total
WORKERS = 2
POOL_BATCH = 16
WORKER_DB_MEMORY = "512MB"
SCRATCH_DB_MEMORY = "512MB"


def is_base(strategy: pd.Series) -> pd.Series:
    """Base strategies only: no ``@`` variants, no ``_no_news`` twins, none of the pre-registered picks."""
    s = strategy.astype(str)
    return ~(s.str.contains("@") | s.str.endswith("_no_news") | s.isin((*EXCLUDED, *BATCH2)))


def with_target(signals: pd.DataFrame, target_r: float | None) -> pd.DataFrame:
    """The signal columns with the target at ``target_r`` x the planned risk (``None`` keeps the recorded one)."""
    out = signals[list(SIGNAL_SCHEMA)].copy()
    if target_r is not None:
        entry, stop = out["entry"].astype(float), out["stop"].astype(float)
        out["target"] = entry + target_r * (entry - stop)
        out["reward_risk"] = target_r
    return out


class _Feed:
    """What ``grade_signals`` needs from a store: the signal table lives in ``scratch``, everything else (bars,
    splits, listings) is read from the read-only ``source``."""

    def __init__(self, scratch: Store, source: Store, bars_end: date) -> None:
        self.scratch, self.source, self.bars_end = scratch, source, bars_end
        self.write_table = scratch.write_table
        self.snapshot_date = source.snapshot_date

    def _of(self, name: str) -> Store:
        return self.scratch if self.scratch.has_table(name) else self.source

    def has_table(self, name: str) -> bool:
        return self._of(name).has_table(name)

    def read_table(self, name: str, *args: Any, **kwargs: Any) -> pd.DataFrame:
        return self._of(name).read_table(name, *args, **kwargs)

    def read_bars(self, symbols: Any, start: date, end: date) -> pd.DataFrame:
        # ponytail: bars capped BARS_AFTER_DAYS after the chunk (memory); a name with < 20 bars in that span that
        # resumed later closes as delisted. Read to `end` if that ever matters.
        return self.source.read_bars(symbols, start, min(end, self.bars_end))


def chunk_table(source_path: Path, year: int, month: int, prefix: str = "t1r") -> str:
    return f"{prefix}_{source_path.stem}_{year}_{month:02d}"


def regrade_chunk(source_path: Path, year: int, month: int, week: date, target_r: float | None = TARGET_R,
                  horizons: Sequence[int] = DEFAULT_HORIZONS, ledger: str = REPLAY_SHADOW_TABLE) -> pd.DataFrame:
    """One week (within one month) of one store's base-strategy signals, regraded in memory: the signal columns
    with the new target, the outcome columns and per-signal ``cost_bps`` / ``dollar_volume``. Runs in a worker
    process; the source is opened read-only and nothing is written to disk."""
    with Store(str(source_path), read_only=True) as source, Store() as memory:
        source.sql(f"SET memory_limit = '{WORKER_DB_MEMORY}'")
        signals = source.read_table(ledger, "year(as_of) = ? AND month(as_of) = ? AND date_trunc('week', as_of) = ?",
                                    [year, month, week])
        signals = signals.loc[is_base(signals["strategy"])] if not signals.empty else signals
        if signals.empty:
            return pd.DataFrame()
        signals = with_target(signals, target_r)
        signals["regime"] = signals["regime"].astype("string")
        last = pd.to_datetime(signals["as_of"]).max().date()
        memory.write_table(ledger, signals, list(KEYS), schema=table_schema(horizons))
        del signals
        grade_signals(_Feed(memory, source, last + timedelta(days=BARS_AFTER_DAYS)), source.snapshot_date(), horizons,
                      table=ledger)
        graded = memory.read_table(ledger)
    return with_costs(graded, source_path)


def _job(args: tuple[Any, ...]) -> pd.DataFrame:
    return regrade_chunk(*args)


def _chunks(source_path: Path, ledger: str = REPLAY_SHADOW_TABLE) -> list[tuple[int, int, date]]:
    with Store(str(source_path), read_only=True) as s:
        frame = s.sql("SELECT DISTINCT year(as_of) AS y, month(as_of) AS m, date_trunc('week', as_of) AS w "  # noqa: S608
                      f"FROM {ledger} ORDER BY y, m, w")
    return [(int(y), int(m), pd.Timestamp(w).date()) for y, m, w in frame.itertuples(index=False)]


def regrade_store(source_path: Path, scratch: Store, *, workers: int = 1, target_r: float | None = TARGET_R,
                  horizons: Sequence[int] = DEFAULT_HORIZONS) -> int:
    """Regrade every chunk of ``source_path`` not yet in ``scratch`` (one table per month, appended a week at a
    time by this process only); returns the signals written. ``workers`` > 1 grades chunks in that many
    processes."""
    todo = []
    for y, m, w in _chunks(source_path):
        table = chunk_table(source_path, y, m)
        done = set(pd.to_datetime(scratch.sql(f"SELECT DISTINCT date_trunc('week', as_of) AS w FROM {table}")["w"])  # noqa: S608
                   .dt.date) if scratch.has_table(table) else set()
        if w not in done:
            todo.append((y, m, w))
    written = 0
    for start in range(0, len(todo), POOL_BATCH):  # a fresh pool per batch: workers do not give memory back
        batch = todo[start:start + POOL_BATCH]
        jobs = [(source_path, *chunk, target_r, horizons) for chunk in batch]
        with ProcessPoolExecutor(workers) if workers > 1 else nullcontext() as pool:
            for (y, m, w), frame in zip(batch, (pool.map if pool else map)(_job, jobs), strict=True):
                if not frame.empty:
                    written += scratch.write_table(
                        chunk_table(source_path, y, m), _typed(frame), list(KEYS),
                        schema={**table_schema(horizons), **dict.fromkeys(COST_COLUMNS, "DOUBLE")})
                print(f"{source_path.stem} {w}: {len(frame)} signals regraded", flush=True)
    return written


def _slim_columns(horizons: Sequence[int]) -> list[str]:
    cols = [*KEYS, "entry", "stop", "entry_price"]
    for h in horizons:
        cols += [horizon_column("hit", h), horizon_column("result_r", h)]
    return cols


def _chunk_tables(scratch: Store, source: Path, prefix: str) -> list[str]:
    return sorted(t for t in scratch.tables() if t.startswith(f"{prefix}_{source.stem}_"))


def regraded_strategies(scratch: Store, sources: Sequence[Path], prefix: str = "t1r") -> list[str]:
    names: set[str] = set()
    for p in sources:
        for t in _chunk_tables(scratch, p, prefix):
            names |= set(scratch.sql(f"SELECT DISTINCT strategy FROM {t}")["strategy"])  # noqa: S608
    return sorted(names)


def _last_wins(frames: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(list(KEYS), keep="last")


def read_regraded(scratch: Store, sources: Sequence[Path], strategy: str,
                  horizons: Sequence[int] = DEFAULT_HORIZONS, prefix: str = "t1r") -> pd.DataFrame:
    """One strategy's regraded signals from every chunk, slim columns plus costs, one row per key (the last
    source wins a duplicate, as research.cards.read_shadow)."""
    cols = ", ".join([*_slim_columns(horizons), *COST_COLUMNS])
    frames = []
    for p in sources:
        union = " UNION ALL ".join(f"SELECT {cols} FROM {t} WHERE strategy = ?"  # noqa: S608 - chunk_table names
                                   for t in _chunk_tables(scratch, p, prefix))
        if union:
            frames.append(scratch.sql(union, [strategy] * union.count("?")))
    return _last_wins(frames)


def read_original(sources: Sequence[Path], strategy: str, horizons: Sequence[int] = DEFAULT_HORIZONS,
                  ledger: str = REPLAY_SHADOW_TABLE) -> pd.DataFrame:
    """The recorded outcomes of one strategy's signals (slim columns), for the contrast."""
    cols = ", ".join(_slim_columns(horizons))
    frames = []
    for p in sources:
        with Store(str(p), read_only=True) as s:
            frames.append(s.sql(f"SELECT {cols} FROM {ledger} WHERE strategy = ?", [strategy]))  # noqa: S608
    return _last_wins(frames)


# ----------------------------------------------------------------------------------------------- report

LABELS = ("orig", "t1r")  # the strategy's own target, the 1R target
_MIX = (Hit.STOP.value, Hit.TARGET.value, Hit.TIME.value, Hit.SKIPPED.value)


def _in_window(frame: pd.DataFrame, w: Window) -> tuple[pd.DataFrame, float]:
    d = pd.to_datetime(frame["as_of"]).dt.date
    return frame.loc[(d >= w.start) & (d <= w.end)], (w.end - w.start).days / 365.25


def _f(x: float, spec: str = "+.3f") -> str:
    return "-" if x is None or not math.isfinite(x) else format(x, spec)


def build_report(names: Sequence[str], load: Callable[[str], tuple[pd.DataFrame, pd.DataFrame]],
                 windows: Sequence[Window] = WINDOWS, notes: Sequence[str] = ()) -> tuple[str, pd.DataFrame, dict[str, Any]]:
    """The markdown report, the leaderboard of the ``@t1r`` rows and a summary dict. ``load(name)`` returns one
    base strategy's (original, regraded) slim frames; strategies are read one at a time to bound memory. No
    trial is logged here."""
    hit, r = horizon_column("hit", POOLED_HORIZON), horizon_column("result_r", POOLED_HORIZON)
    pool_cols = ["as_of", "entry", "stop", "cost_bps", hit, r]
    years = [w.start.year for w in windows]
    n_trials = max(len(names) * len(DEFAULT_HORIZONS) * len(windows), 1)
    boards, rows = [], {}
    pools: dict[str, list[pd.DataFrame]] = {k: [] for k in LABELS}
    mix: dict[str, Counter[str]] = {k: Counter() for k in LABELS}
    for name in names:
        original, regraded = load(name)
        original = original.merge(regraded[[*KEYS, *COST_COLUMNS]], on=list(KEYS), how="left")
        boards.append(leaderboard(regraded.assign(strategy=name + SUFFIX), windows, logged_trials=n_trials)[0])
        row: dict[str, float] = {}
        for label, frame in zip(LABELS, (original, regraded), strict=True):
            ex = executable(frame)
            mix[label].update(ex[hit].astype(str).value_counts().to_dict())
            for w in windows:
                sub, span = _in_window(ex, w)
                row[f"{label}_{w.start.year}"] = edge_stats(sub, POOLED_HORIZON, span, 1)["net_r"]
            traded = ex.loc[ex[hit].astype(str).isin(TRADE_HITS), pool_cols]
            pools[label].append(traded.assign(**{hit: traded[hit].astype("category")}))
        rows[name] = row
    board = pd.concat(boards, ignore_index=True) if boards else pd.DataFrame()
    table = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=[f"{k}_{y}" for k in LABELS for y in years])
    pooled: dict[str, list[dict[str, float]]] = {}
    for label in LABELS:
        frame = pd.concat(pools[label], ignore_index=True)
        pools[label].clear()
        frame[hit] = frame[hit].astype(str)
        pooled[label] = [edge_stats(sub, POOLED_HORIZON, span, 1) for sub, span in (_in_window(frame, w) for w in windows)]
        del frame
    passed = all(s["net_r"] > 0 and s["t"] >= POOLED_MIN_T for s in pooled["t1r"])
    surv = survivors(board)
    delta = pd.DataFrame({y: table[f"t1r_{y}"] - table[f"orig_{y}"] for y in years})
    both = delta.dropna()
    up, down = (both > 0).all(axis=1), (both < 0).all(axis=1)
    summary = {"n_trials": n_trials, "strategies": len(names),
               "survivors": sorted({(str(s.strategy), int(s.horizon)) for s in surv.itertuples()}),
               "pooled": pooled["t1r"], "pooled_pass": passed, "in_both_windows": int(len(both)),
               "improved_both": int(up.sum()), "worsened_both": int(down.sum()),
               "mixed": int(len(both) - up.sum() - down.sum()),
               **{f"improved_{y}": int((delta[y] > 0).sum()) for y in years},
               **{f"worsened_{y}": int((delta[y] < 0).sum()) for y in years}}
    lines = [
        "# 1R-target regrade of every strategy", "",
        f"Graded per {PREREG} by `swing_engine.research.regrade`: every recorded replay signal of every base "
        f"strategy, same entry and stop, target moved to entry + {TARGET_R:g} x (entry - stop), graded by "
        "`research.shadow.grade_signals` on its own store's bars (stop first when both touch in a bar). The "
        f"haircut counts this family only ({len(names)} strategies x {len(DEFAULT_HORIZONS)} horizons x "
        f"{len(years)} windows = {n_trials} trials). Shadow grading is per signal, not a portfolio, and the ledgers "
        "predate the 2026-10-10 splits backfill.", "",
        f"## Pooled test (pre-registered, {POOLED_HORIZON}d, n_trials = 1): {'PASS' if passed else 'FAIL'}", "",
        f"PASS needs net R > 0 and block t >= {POOLED_MIN_T:g} in both windows. The own-target rows are the same "
        "signals with their recorded targets, for contrast only.", "",
        "| window | exit | trades | win | gross R | net R/signal | block t | Sharpe |", "|---|---|---|---|---|---|---|---|",
    ]
    for i, w in enumerate(windows):
        for label, text in (("t1r", f"1R target ({SUFFIX})"), ("orig", "own target")):
            s = pooled[label][i]
            lines.append(f"| {w.start} .. {w.end} | {text} | {int(s['n'])} | {_f(s['win'] * 100, '.0f')}% | "
                         f"{_f(s['gross_r'])} | {_f(s['net_r'])} | {_f(s['t'], '.2f')} | {_f(s['sharpe'], '.2f')} |")
    lines += ["", f"Exit mix at {POOLED_HORIZON}d, all signals pooled (stop / target / time: share of trades; "
              "skipped: share of signals never entered, which includes an entry fill already at or above the target):",
              "", "| exit | stop | target | time | skipped |", "|---|---|---|---|---|"]
    for label, text in (("t1r", "1R target"), ("orig", "own target")):
        c = mix[label]
        trades = sum(c[h] for h in TRADE_HITS) or math.nan
        shares = [c[h] / trades for h in _MIX[:3]] + [c[Hit.SKIPPED.value] / (sum(c.values()) or math.nan)]
        lines.append(f"| {text} | " + " | ".join(_f(x * 100, ".0f") + "%" for x in shares) + " |")
    lines += ["", render(board, n_trials, windows).replace("# Strategy leaderboard", f"## Leaderboard of the {SUFFIX} variants", 1)
              .replace("\n## ", "\n### ").rstrip("\n"), "",
              f"## Own target vs 1R target: net R per signal at {POOLED_HORIZON}d", "",
              f"{len(both)} strategies have trades in both windows under both exits: {summary['improved_both']} are "
              f"better with the 1R target in both windows, {summary['worsened_both']} are worse in both, "
              f"{summary['mixed']} are mixed. "
              + " ".join(f"In the {y} window {summary[f'improved_{y}']} improve and {summary[f'worsened_{y}']} worsen."
                         for y in years), "",
              "| strategy | " + " | ".join(f"{y} own | {y} 1R | {y} change" for y in years) + " |",
              "|---|" + "---|---|---|" * len(years)]
    for strat, row in table.iterrows():
        cells = [_f(x) for y in years for x in (row[f"orig_{y}"], row[f"t1r_{y}"], row[f"t1r_{y}"] - row[f"orig_{y}"])]
        lines.append(f"| {strat} | " + " | ".join(cells) + " |")
    if notes:
        lines += ["", "## Notes", "", *(f"- {n}" for n in notes)]
    return "\n".join(lines) + "\n", board, summary


def reproduction_check(source_path: Path, year: int, month: int, week: date,
                       horizons: Sequence[int] = DEFAULT_HORIZONS) -> dict[str, float]:
    """Regrade one chunk with its ORIGINAL targets and compare with the stored outcomes (share of rows equal)."""
    new = regrade_chunk(source_path, year, month, week, None, horizons)
    with Store(str(source_path), read_only=True) as s:
        old = s.read_table(REPLAY_SHADOW_TABLE, "year(as_of) = ? AND month(as_of) = ? AND date_trunc('week', as_of) = ?",
                           [year, month, week])
    both = old.assign(as_of=pd.to_datetime(old["as_of"]).dt.date).merge(new, on=list(KEYS), suffixes=("", "_new"))
    out = {"rows": float(len(both))}
    for h in horizons:
        hit, r = horizon_column("hit", h), horizon_column("result_r", h)
        final = both[hit].notna() & (both[hit] != Hit.PENDING.value)
        same = both.loc[final, hit].astype(str) == both.loc[final, hit + "_new"].astype(str)
        a, b = both.loc[final, r].astype(float), both.loc[final, r + "_new"].astype(float)
        close = (a - b).abs() <= 1e-6 * (1 + a.abs())
        out[f"hit_{h}d"] = float(same.mean()) if final.any() else math.nan
        out[f"r_{h}d"] = float((close | (a.isna() & b.isna())).mean()) if final.any() else math.nan
    return out


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--store", action="append", default=[], help=f"source stores in read order (default {SOURCES})")
    ap.add_argument("--scratch", default=SCRATCH)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", default=None, help="<store>:<monday>: reproduction check with the original targets")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--no-report", action="store_true", help="regrade only")
    ap.add_argument("--note", action="append", default=[], help="line for the report's Notes section (repeatable)")
    args = ap.parse_args(argv)
    sources = [ROOT / s for s in (args.store or SOURCES)]
    if args.check:
        path, monday = args.check.rsplit(":", 1)
        week = date.fromisoformat(monday)
        print(reproduction_check(ROOT / path, week.year, week.month, week))
        return
    with Store(str(ROOT / args.scratch)) as scratch:
        scratch.sql(f"SET memory_limit = '{SCRATCH_DB_MEMORY}'")
        for path in sources if not args.report_only else []:
            print(f"{path.stem}: {regrade_store(path, scratch, workers=args.workers)} signals regraded", flush=True)
        if args.no_report:
            return
        text, board, summary = build_report(
            regraded_strategies(scratch, sources),
            lambda name: (read_original(sources, name), read_regraded(scratch, sources, name)), notes=args.note)
    log_board_trials(board)
    (ROOT / args.out).write_text(text)
    print(summary)


if __name__ == "__main__":
    main()
