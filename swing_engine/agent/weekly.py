"""Weekly one-page report: `data/journal/weekly-<ISO week>.md`, tables and rule-generated sentences only (no LLM).

Sections: what traded on paper this week (order ledger rows created this week, autopilot audit and `swing paper`
run files), the live shadow ledger (top / bottom strategies by net R this week and to date), drift against the
replay (research.drift) and a rules-based recommendations list. Written by `swing weekly-report` and by the
nightly on the last session of each ISO week.
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.config import ROOT, Settings
from swing_engine.data.calendar import is_trading_day, next_trading_day
from swing_engine.research.cards import executable
from swing_engine.research.drift import (
    ABOVE,
    BELOW,
    DRIFT_MIN_N,
    DRIFT_SE_BAND,
    DRIFT_WINDOW_DAYS,
    drift_table,
    net_r,
)
from swing_engine.research.shadow import DEFAULT_HORIZONS, REPLAY_SHADOW_TABLE, SHADOW_TABLE, horizon_column

from .journal import JOURNAL_DIR, _table

log = structlog.get_logger(__name__)

REPORT_HORIZON = 10  # sessions: the shadow ranking and the walk-forward rule read this horizon
TOP_N = 3
WALK_FORWARD_MIN_N = 50  # live trades before a shadow-only strategy is proposed for walk-forward
AUTOPILOT_KIND, FILLS_KIND = "autopilot", "fills"
SENT_STATUSES = frozenset({"submitted", "done"})  # execution.autopilot.Outcome values that reached the broker


def iso_week(day: date) -> str:
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def weekly_path(day: date, root: Path | None = None) -> Path:
    return (root if root is not None else ROOT) / JOURNAL_DIR / f"weekly-{iso_week(day)}.md"


def is_last_session_of_week(day: date) -> bool:
    """`day` is a session and the next session falls in a later ISO week (Friday, or Thursday before a holiday)."""
    return is_trading_day(day) and next_trading_day(day).isocalendar()[:2] != day.isocalendar()[:2]


def _f(x: Any, spec: str = "+.2f") -> str:
    return "-" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _pct(x: Any) -> str:
    return "-" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x * 100:.0f}%"


# ---- inputs ------------------------------------------------------------------------------------------------
def ledger_orders(settings: Settings, start: date, end: date) -> list[dict[str, Any]]:
    """Order ledger rows created in [start, end] (read-only; [] without a ledger)."""
    from swing_engine.risk.killswitch import resolve_state_path

    path = resolve_state_path(settings.execution.ledger_file)
    if not path.exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM orders WHERE substr(created_at, 1, 10) BETWEEN ? AND ? ORDER BY created_at",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    except sqlite3.OperationalError:  # no orders table yet
        return []
    finally:
        con.close()
    return [dict(r) for r in rows]


def paper_actions(settings: Settings, start: date, end: date) -> list[dict[str, Any]]:
    """Entries and exits the autopilot sent (non dry-run audit runs) plus `swing paper` results, per day."""
    from swing_engine.execution.autopilot import run_path

    out: list[dict[str, Any]] = []
    day = start
    while day <= end:
        audit = run_path(settings, AUTOPILOT_KIND, day)
        if audit.exists():
            for run in (json.loads(audit.read_text(encoding="utf-8") or "{}") or {}).get("runs") or []:
                if run.get("dry_run"):
                    continue
                for r in [*(run.get("exits") or []), *(run.get("entries") or [])]:
                    if r.get("status") in SENT_STATUSES:
                        out.append({"day": day.isoformat(), "source": "autopilot", **r})
        fills = run_path(settings, FILLS_KIND, day)
        if fills.exists():
            for r in json.loads(fills.read_text(encoding="utf-8") or "[]") or []:
                out.append({"day": day.isoformat(), "source": "swing paper", "kind": r.get("kind", "entry"), **r})
        day += timedelta(days=1)
    return out


# ---- sections ----------------------------------------------------------------------------------------------
def _fill_price(row: dict[str, Any]) -> str:
    try:
        b = json.loads(row.get("broker_json") or "null") or {}
    except ValueError:
        return "-"
    raw = b.get("raw", b) if isinstance(b, dict) else {}
    price = raw.get("filled_avg_price") if isinstance(raw, dict) else None
    return _f(float(price), ".2f") if price not in (None, "") else "-"


def _trading_section(orders: Sequence[dict[str, Any]], actions: Sequence[dict[str, Any]]) -> list[str]:
    filled = sum(str(o.get("status")) == "filled" for o in orders)
    lines = ["## Paper trading this week", ""]
    if not orders and not actions:
        return [*lines, "Nothing was sent to the paper broker this week.", ""]
    lines += [f"{len(orders)} orders entered the ledger ({filled} filled); {len(actions)} actions reached the broker "
              "through the autopilot or `swing paper`.", "", "### Order ledger", ""]
    lines.append(_table(["created", "symbol", "side", "qty", "strategy", "status", "fill"], [
        [str(o.get("created_at", ""))[:16], o.get("symbol"), o.get("side"), o.get("qty"), o.get("strategy"),
         o.get("status"), _fill_price(o)] for o in orders]))
    lines += ["", "### Broker actions", ""]
    lines.append(_table(["day", "source", "kind", "symbol", "strategy", "status", "reason"], [
        [a.get("day"), a.get("source"), a.get("kind"), a.get("symbol"), a.get("strategy") or "-", a.get("status"),
         a.get("reason") or ""] for a in actions]))
    return [*lines, ""]


def _by_strategy(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    net = net_r(frame, horizon)
    if net.empty:
        return pd.DataFrame(columns=["n", "win", "net_r"])
    strat = frame.loc[net.index, "strategy"].astype(str)
    g = net.groupby(strat)
    return pd.DataFrame({"n": g.size(), "win": g.apply(lambda s: float((s > 0).mean())), "net_r": g.mean()})


def _ranking(stats: pd.DataFrame, label: str) -> list[str]:
    if stats.empty:
        return [f"No live signal resolved {label}.", ""]
    ranked = stats.sort_values("net_r", ascending=False)
    top = ranked.head(TOP_N)
    bottom = ranked.drop(top.index).tail(TOP_N).iloc[::-1]
    best = ranked.index[0]
    lines = [f"{len(ranked)} strategies resolved signals {label}; best **{best}** at {_f(ranked.loc[best, 'net_r'])}R "
             f"net over {int(ranked.loc[best, 'n'])} trades.", ""]
    rows = [[k, s, int(r.n), _pct(r.win), _f(r.net_r)] for k, part in (("top", top), ("bottom", bottom))
            for s, r in part.iterrows()]
    return [*lines, _table(["", "strategy", "trades", "win", "net R"], rows), ""]


def _shadow_section(live: pd.DataFrame, start: date, end: date) -> list[str]:
    lines = ["## Shadow ledger", "", f"Net R per traded signal at {REPORT_HORIZON} sessions, after round-trip "
             "slippage (research.cards.cost_r).", ""]
    live = executable(live).reset_index(drop=True)
    exit_col = horizon_column("exit_date", REPORT_HORIZON)
    week = live
    if not live.empty and exit_col in live.columns:
        d = pd.to_datetime(live[exit_col]).dt.date
        week = live.loc[(d >= start) & (d <= end)]
    lines += ["### Resolved this week", "", *_ranking(_by_strategy(week, REPORT_HORIZON), "this week")]
    lines += ["### To date", "", *_ranking(_by_strategy(live, REPORT_HORIZON), "to date")]
    return lines


def _drift_section(drift: pd.DataFrame) -> list[str]:
    lines = ["## Drift (live vs replay)", "", f"Live: last {DRIFT_WINDOW_DAYS} days of the shadow ledger; flagged when "
             f"the live mean is outside replay +/- {DRIFT_SE_BAND:g} standard errors with at least {DRIFT_MIN_N} live "
             "trades.", ""]
    if drift.empty:
        return [*lines, "No live signals in the window.", ""]
    flagged = drift.loc[drift["flag"] != ""]
    lines += [f"{len(drift)} strategies compared; {int((drift['flag'] == BELOW).sum())} below replay, "
              f"{int((drift['flag'] == ABOVE).sum())} above.", ""]
    if flagged.empty:
        return [*lines, ""]
    rows = []
    for r in flagged.to_dict(orient="records"):
        for h in DEFAULT_HORIZONS:
            if r.get(f"flag_{h}d"):
                rows.append([r["strategy"], f"{h}d", r[f"flag_{h}d"], r[f"n_{h}d"], _f(r[f"live_r_{h}d"]),
                             _f(r[f"replay_r_{h}d"]), _f(r[f"diff_{h}d"]), _f(r[f"se_{h}d"], ".2f")])
    return [*lines, _table(["strategy", "horizon", "flag", "live n", "live R", "replay R", "diff", "SE"], rows), ""]


def recommendations(drift: pd.DataFrame, settings: Settings) -> list[str]:
    """Rules only: an enabled strategy drifting below replay -> consider disabling; a shadow-only strategy with
    WALK_FORWARD_MIN_N live trades at REPORT_HORIZON and net R above its replay -> walk-forward candidate."""
    out = []
    h = REPORT_HORIZON
    for r in drift.to_dict(orient="records") if not drift.empty else []:
        cfg = settings.strategies.get(r["strategy"])
        if cfg is None:
            continue
        enabled = bool((cfg or {}).get("enabled", True))
        if enabled and r["flag"] == BELOW:
            hb = next(x for x in DEFAULT_HORIZONS if r.get(f"flag_{x}d") == BELOW)
            out.append(f"**{r['strategy']}** (enabled): consider disabling. Live {_f(r[f'live_r_{hb}d'])}R vs replay "
                       f"{_f(r[f'replay_r_{hb}d'])}R at {hb}d over {r[f'n_{hb}d']} trades, more than "
                       f"{DRIFT_SE_BAND:g} SE below.")
        elif (not enabled and (cfg or {}).get("shadow_only") and r[f"n_{h}d"] >= WALK_FORWARD_MIN_N
              and r[f"live_r_{h}d"] > r[f"replay_r_{h}d"]):
            out.append(f"**{r['strategy']}** (shadow only): candidate for walk-forward. Live {_f(r[f'live_r_{h}d'])}R "
                       f"vs replay {_f(r[f'replay_r_{h}d'])}R at {h}d over {r[f'n_{h}d']} trades.")
    return out


def render_report(
    as_of: date,
    settings: Settings,
    live: pd.DataFrame,
    replay: pd.DataFrame,
    orders: Sequence[dict[str, Any]],
    actions: Sequence[dict[str, Any]],
) -> str:
    start = as_of - timedelta(days=as_of.weekday())
    drift = drift_table(live, replay, as_of)
    recs = recommendations(drift, settings)
    lines = [
        f"# Weekly report {iso_week(as_of)} ({start} .. {as_of})", "",
        "_Generated by `swing_engine.agent.weekly` from the order ledger, the run files and the shadow ledgers. "
        "Tables and rule-based sentences only; no LLM. Judge any change against docs/gates.md._", "",
        *_trading_section(orders, actions),
        *_shadow_section(live, start, as_of),
        *_drift_section(drift),
        "## Recommendations", "",
        *([f"- {r}" for r in recs] or ["None: no enabled strategy drifts below its replay and no shadow-only "
                                       "strategy has earned a walk-forward yet."]),
    ]
    return "\n".join(lines) + "\n"


def write_report(settings: Settings, as_of: date, store: Any, root: Path | None = None) -> Path:
    """Gather this week's inputs, render, write `<root>/data/journal/weekly-<ISO week>.md`; returns the path."""
    start = as_of - timedelta(days=as_of.weekday())
    text = render_report(
        as_of, settings, store.read_table(SHADOW_TABLE), store.read_table(REPLAY_SHADOW_TABLE),
        ledger_orders(settings, start, as_of), paper_actions(settings, start, as_of),
    )
    path = weekly_path(as_of, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log.info("agent.weekly.written", path=str(path))
    return path


__all__ = ["is_last_session_of_week", "iso_week", "recommendations", "render_report", "weekly_path", "write_report"]
