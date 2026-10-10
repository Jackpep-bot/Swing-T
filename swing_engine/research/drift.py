"""Live-vs-replay drift: does each strategy's live shadow ledger still look like its replay?

Inputs are the two shadow ledgers (same schema): ``shadow_signals`` (the nightly, live) over the last
``DRIFT_WINDOW_DAYS`` and ``shadow_signals_replay`` (``swing replay``) in full. Both keep only executable signals
(``research.cards.executable``) and are scored the way ``research.leaderboard.edge_stats`` scores replays: per
horizon ``h``, net R = ``result_r_<h>d`` - round-trip slippage (``research.cards.cost_r``) over the signals that
became trades.

Flag: with at least ``DRIFT_MIN_N`` live trades at ``h``, ``below`` / ``above`` when the live mean sits outside
replay mean +/- ``DRIFT_SE_BAND`` standard errors of the difference (live and replay sampling error combined).
Numbers only; no model, no LLM.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, timedelta

import pandas as pd

from swing_engine.research.cards import WINDOWS, cost_r, executable
from swing_engine.research.shadow import DEFAULT_HORIZONS, TRADE_HITS, horizon_column

DRIFT_WINDOW_DAYS = 90  # calendar days of live ledger compared with the replay
DRIFT_MIN_N = 20  # live trades at a horizon before a flag is raised
DRIFT_SE_BAND = 2.0
BELOW, ABOVE = "below", "above"


def net_r(frame: pd.DataFrame, horizon: int) -> pd.Series:
    """Net R of the signals that became trades at ``horizon`` (index kept)."""
    hit, r = horizon_column("hit", horizon), horizon_column("result_r", horizon)
    if frame.empty or hit not in frame.columns:
        return pd.Series(dtype=float)
    traded = frame.loc[frame[hit].astype(str).isin(TRADE_HITS)]
    return traded[r].astype(float) - cost_r(traded).fillna(0.0)


def _flag(live: pd.Series, replay: pd.Series, min_n: int, band: float) -> tuple[float, str]:
    """(standard error of live mean - replay mean, flag)."""
    if len(live) < 2 or len(replay) < 2:
        return math.nan, ""
    se = math.sqrt(live.var(ddof=1) / len(live) + replay.var(ddof=1) / len(replay))
    diff = live.mean() - replay.mean()
    if len(live) < min_n or not se > 0 or abs(diff) <= band * se:
        return se, ""
    return se, BELOW if diff < 0 else ABOVE


def drift_table(
    live: pd.DataFrame,
    replay: pd.DataFrame,
    as_of: date,
    *,
    window_days: int = DRIFT_WINDOW_DAYS,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    min_n: int = DRIFT_MIN_N,
    band: float = DRIFT_SE_BAND,
) -> pd.DataFrame:
    """One row per strategy in the live window. Columns per horizon ``h``: ``n_<h>d`` (live trades),
    ``win_<h>d``, ``live_r_<h>d``, ``replay_n_<h>d``, ``replay_r_<h>d``, ``diff_<h>d``, ``se_<h>d``,
    ``flag_<h>d``; ``flag`` is ``below`` if any horizon is below, else ``above`` if any is above, else ''."""
    if not live.empty:
        d = pd.to_datetime(live["as_of"]).dt.date
        live = executable(live.loc[(d > as_of - timedelta(days=window_days)) & (d <= as_of)])
    if not replay.empty:  # compare with the survivorship-free window only (research.cards.WINDOWS[0])
        rd = pd.to_datetime(replay["as_of"]).dt.date
        replay = replay.loc[rd >= WINDOWS[0].start]
    live, replay = live.reset_index(drop=True), executable(replay).reset_index(drop=True)
    rows = []
    for strat in sorted(set(live["strategy"].astype(str))) if not live.empty else []:
        lv = live.loc[live["strategy"].astype(str) == strat]
        rp = replay.loc[replay["strategy"].astype(str) == strat] if not replay.empty else replay
        row: dict[str, object] = {"strategy": strat, "signals": len(lv)}
        flags = []
        for h in horizons:
            ln, rn = net_r(lv, h), net_r(rp, h)
            se, flag = _flag(ln, rn, min_n, band)
            live_mean = float(ln.mean()) if len(ln) else math.nan
            replay_mean = float(rn.mean()) if len(rn) else math.nan
            row.update({
                f"n_{h}d": len(ln), f"win_{h}d": float((ln > 0).mean()) if len(ln) else math.nan,
                f"live_r_{h}d": live_mean, f"replay_n_{h}d": len(rn), f"replay_r_{h}d": replay_mean,
                f"diff_{h}d": live_mean - replay_mean, f"se_{h}d": se, f"flag_{h}d": flag,
            })
            flags.append(flag)
        row["flag"] = BELOW if BELOW in flags else ABOVE if ABOVE in flags else ""
        rows.append(row)
    return pd.DataFrame(rows)


__all__ = ["ABOVE", "BELOW", "DRIFT_MIN_N", "DRIFT_SE_BAND", "DRIFT_WINDOW_DAYS", "drift_table", "net_r"]
