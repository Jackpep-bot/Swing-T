"""Write replay results into each strategy card's ``## Empirical (replay)`` section (docs/strategies/<slug>.md).

Sources: the replay shadow ledger (``shadow_signals_replay``: every signal, graded gross at fixed horizons on the
signal's own stop / target) and the saved ``runs/replay/*.json`` files (the replay's own trades, net of costs but
competing for 8 slots with the other strategies of the same run). Run after the research replays::

    uv run python -m swing_engine.research.cards --settings config/replay.yaml --store data/live/replay_b.duckdb ...

Numbers only, no prose verdicts: the reader (and Claude) judge them against docs/gates.md.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.research.shadow import (
    DEFAULT_HORIZONS,
    REPLAY_SHADOW_TABLE,
    horizon_column,
    summarize_outcomes,
)

ROOT = Path(__file__).resolve().parents[2]
CARDS_DIR = ROOT / "docs" / "strategies"
SECTION = "## Empirical (replay)"
#: Default tag prefix of the research replay runs read by `main` (`--tag`): v2c<n> = the 2026-10-09 runs on the
#: repaired store with delisted names. `swing research run` tags its chunks <run-id>-<window><n> and passes
#: `--tag <run-id>`.
RUN_TAG_PREFIX = "v2c"
RUNS_SUBDIR = ("runs", "replay")
PCT = 100.0
BPS = 1e4
#: Round-trip cost charged on each graded signal for the net columns: slippage per side (backtest.CostModel
#: default) on the entry and the exit, expressed in R of the signal's own stop distance. Fees (SEC, TAF) are
#: under 0.1 bp on these prices and are left out.
NET_SLIPPAGE_BPS_PER_SIDE = 10.0
#: The yardstick of the leaderboard, the cards and the reality check (owner, 2026-10-13): R beyond what the same
#: dollars would have made in this symbol over the signal's holding span. Column ``mkt_r_<h>d`` (``with_costs``).
MARKET_SYMBOL = "SPY"
MARKET_R = "mkt_r"


def executable(frame: pd.DataFrame) -> pd.DataFrame:
    """Signals whose stop sits at least strategies._base.MIN_STOP_FRACTION below the entry (the live rule since
    2026-10-08); older ledgers still hold sub-tick stops whose R is meaningless."""
    from swing_engine.strategies._base import MIN_STOP_FRACTION

    if frame.empty or not {"entry", "stop"} <= set(frame.columns):
        return frame
    entry, stop = frame["entry"].astype(float), frame["stop"].astype(float)
    out = frame.loc[(entry - stop) >= entry * MIN_STOP_FRACTION].copy()
    return planned_r(out)


#: R columns graded per unit of the FILLED risk (entry_price - stop) in research.shadow.
_R_PREFIXES = ("result_r", "mfe_r", "mae_r")


def planned_r(frame: pd.DataFrame) -> pd.DataFrame:
    """Re-express graded R per unit of the PLANNED risk (signal entry - stop). The shadow ledger divides by the
    filled risk (entry_price - stop), which goes to ~0 when the next open gaps down onto the stop and turned a
    flat trade into +7e14 R (BOIL 2026-06-12). Rows without a fill keep their (empty) R."""
    if not {"entry", "stop", "entry_price"} <= set(frame.columns):
        return frame
    planned = frame["entry"].astype(float) - frame["stop"].astype(float)
    filled = frame["entry_price"].astype(float) - frame["stop"].astype(float)
    factor = (filled / planned).where(planned > 0)
    for col in [c for c in frame.columns if c.startswith(_R_PREFIXES)]:
        frame[col] = frame[col].astype(float) * factor
    return frame


def cost_r(frame: pd.DataFrame, bps_per_side: float = NET_SLIPPAGE_BPS_PER_SIDE) -> pd.Series:
    """Round-trip cost in R per signal: 2 x bps x entry / (entry - stop), with bps per side from a ``cost_bps``
    column (research.costs: half-spread, floored at gate 1) when present; NaN when the stop distance is not
    positive."""
    entry, stop = frame["entry"].astype(float), frame["stop"].astype(float)
    risk = (entry - stop).where(entry > stop)
    bps = frame["cost_bps"].astype(float).fillna(bps_per_side) if "cost_bps" in frame.columns else bps_per_side
    return 2.0 * bps / BPS * entry / risk


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    label: str


#: The two research windows (docs/STATUS.md): Massive covers every US ticker from 2024-10-07; before that the
#: store holds Alpaca history for ~4,300 names that were still liquid in 2024 (survivorship bias).
WINDOWS: tuple[Window, ...] = (
    Window(date(2024, 10, 7), date(2026, 10, 5), "survivorship-free, every US ticker"),
    Window(date(2017, 1, 1), date(2024, 10, 4), "~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store"),
)


def _fmt(x: Any, spec: str = ".2f") -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) and x > 0 else "-"
    return format(x, spec)


def _pct(x: Any) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * PCT:.0f}%"


def shadow_table(frame: pd.DataFrame, horizons: Sequence[int] = DEFAULT_HORIZONS) -> str:
    """Markdown table: one row per regime plus ``all``; win rate, gross and net avg R at each horizon."""
    if frame.empty:
        return "_No signals in this window._"
    costs = cost_r(frame) if {"entry", "stop"} <= set(frame.columns) else pd.Series(0.0, index=frame.index)
    longest = max(horizons)
    groups = [*sorted(frame["regime"].fillna("unknown").astype(str).unique()), "all"]
    head = ["regime", "signals", "skipped"]
    for h in horizons:
        head += [f"win {h}d", f"avg R {h}d", f"net R {h}d", f"vs SPY {h}d"]
    head += [f"PF {longest}d"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for g in groups:
        sub = frame if g == "all" else frame.loc[frame["regime"].fillna("unknown").astype(str) == g]
        cells = [f"**{g}**" if g == "all" else g]
        stats = {h: summarize_outcomes(sub, (), horizon=h).iloc[0] for h in horizons}
        first = stats[horizons[0]]
        cells += [str(int(first["n_signals"])), str(int(first["n_skipped"]))]
        for h in horizons:
            net, rel = _net_avg(sub, costs, h), _net_avg(sub, costs + relative_r(frame, h), h)
            cells += [_pct(stats[h]["win_rate"]), _fmt(stats[h]["avg_r"], "+.2f"), _fmt(net, "+.2f"), _fmt(rel, "+.2f")]
        cells += [_fmt(stats[longest]["profit_factor"])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _net_avg(sub: pd.DataFrame, costs: pd.Series, horizon: int) -> float:
    """Mean of result_r - cost_r over the signals that became trades at ``horizon`` (not skipped or pending)."""
    from swing_engine.research.shadow import TRADE_HITS, horizon_column

    hit, r = horizon_column("hit", horizon), horizon_column("result_r", horizon)
    if hit not in sub.columns:
        return math.nan
    traded = sub[hit].astype(str).isin(TRADE_HITS)
    net = sub.loc[traded, r].astype(float) - costs.reindex(sub.index)[traded].fillna(0.0)
    return float(net.mean()) if len(net) else math.nan


def portfolio_line(trades: pd.DataFrame) -> str:
    """One sentence on the replay's own (net) trades for the strategy."""
    if trades.empty:
        return "Portfolio replay: no trades taken (every signal lost the slot race or was skipped)."
    r = trades["r_multiple"].astype(float)
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    pf = wins / losses if losses > 0 else math.inf
    return (
        f"Portfolio replay (net of costs, slots shared with its run): {len(trades)} trades, "
        f"win {_pct(float((r > 0).mean()))}, avg {r.mean():+.2f}R, PF {_fmt(pf)}, "
        f"P&L ${trades['pnl'].astype(float).sum():,.0f} on $100k, avg hold {trades['bars_held'].astype(float).mean():.1f} bars."
    )


def render_section(
    slug: str,
    shadow: pd.DataFrame,
    trades: pd.DataFrame,
    windows: Iterable[Window] = WINDOWS,
    generated: date | None = None,
    n_strategies: int | None = None,
) -> str:
    sh = executable(shadow.loc[shadow["strategy"] == slug]) if not shadow.empty else shadow
    tr = trades.loc[trades["strategy"] == slug] if not trades.empty else trades
    out = [
        SECTION,
        f"_Generated {(generated or date.today()).isoformat()} by `swing_engine.research.cards` from "
        "`swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, "
        "entered the next session by its entry type, exited at its own stop or target or at the horizon close. "
        "`avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread "
        "(Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp "
        "otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same "
        "days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the "
        "playbook router's labels on the signal day.",
    ]
    if n_strategies:
        out.append(
            f"About {n_strategies} strategies were replayed together, so a few will look good by chance: judge them "
            "with the deflated Sharpe and haircut in docs/gates.md, not by this table alone."
        )
    for w in windows:
        def in_window(dates: pd.Series, w: Window = w) -> pd.Series:
            d = pd.to_datetime(dates).dt.date
            return (d >= w.start) & (d <= w.end)

        s = sh.loc[in_window(sh["as_of"])] if not sh.empty else sh
        t = tr.loc[in_window(tr["signal_date"])] if not tr.empty else tr
        out += ["", f"### {w.start} .. {w.end} ({w.label})", shadow_table(s), "", portfolio_line(t)]
    return "\n".join(out) + "\n"


def replace_section(text: str, section: str) -> str:
    """``text`` with its ``## Empirical (replay)`` section (up to the next ``## `` heading) replaced."""
    start = text.find(SECTION)
    if start < 0:
        return text.rstrip("\n") + "\n\n" + section
    nxt = re.search(r"^## ", text[start + len(SECTION):], flags=re.MULTILINE)
    end = start + len(SECTION) + nxt.start() if nxt else len(text)
    tail = text[end:]
    return text[:start] + section + ("\n" + tail if tail else "")


def load_trades(runs_dir: Path, tag_prefix: str = RUN_TAG_PREFIX) -> pd.DataFrame:
    frames = []
    paths = sorted(runs_dir.glob(f"*_{tag_prefix}*.json"))  # the current --no-router research runs
    for path in paths:
        payload = json.loads(path.read_text())
        trades = pd.DataFrame(payload.get("trades") or [])
        if not trades.empty:
            frames.append(trades)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["strategy", "signal_date"])


def write_cards(
    shadow: pd.DataFrame,
    trades: pd.DataFrame,
    slugs: Iterable[str],
    cards_dir: Path = CARDS_DIR,
    generated: date | None = None,
) -> list[str]:
    slugs = list(slugs)
    written = []
    for slug in slugs:
        path = cards_dir / f"{slug}.md"
        if not path.exists():
            continue
        section = render_section(slug, shadow, trades, generated=generated, n_strategies=len(slugs))
        path.write_text(replace_section(path.read_text(), section))
        written.append(slug)
    return written


def market_r(frame: pd.DataFrame, spy: pd.DataFrame, horizon: int) -> pd.Series:
    """SPY's return over each signal's holding span in the signal's R units. ``spy``: ``open``/``close`` indexed
    by session date. The span runs from the open of ``entry_date`` (the session after ``as_of`` when missing) to
    the close of ``exit_date_<h>d``; NaN when either session has no SPY bar or the stop is not below the entry."""
    sessions = pd.DatetimeIndex(pd.to_datetime(spy.index))
    opens = pd.Series(spy["open"].to_numpy(float), index=sessions)
    closes = pd.Series(spy["close"].to_numpy(float), index=sessions)
    as_of = pd.to_datetime(frame["as_of"])
    nxt = np.searchsorted(sessions.values, as_of.values.astype("datetime64[ns]"), side="right")
    after = pd.Series(sessions.append(pd.DatetimeIndex([pd.NaT]))[np.minimum(nxt, len(sessions))], index=frame.index)
    start = pd.to_datetime(frame["entry_date"]).fillna(after) if "entry_date" in frame.columns else after
    end = pd.to_datetime(frame[horizon_column("exit_date", horizon)])
    ret = end.map(closes).to_numpy(float) / start.map(opens).to_numpy(float) - 1.0
    entry, stop = frame["entry"].astype(float), frame["stop"].astype(float)
    return pd.Series(ret, index=frame.index) * entry / (entry - stop).where(entry > stop)


def relative_r(frame: pd.DataFrame, horizon: int) -> pd.Series:
    """The market component to subtract from each signal's R at ``horizon``: ``mkt_r_<h>d`` (0 where unknown or
    not attached)."""
    col = horizon_column(MARKET_R, horizon)
    return frame[col].astype(float).fillna(0.0) if col in frame.columns else pd.Series(0.0, index=frame.index)


def drop_renamed(shadow: pd.DataFrame, dups: pd.DataFrame, cutoff: date | None = None) -> pd.DataFrame:
    """``shadow`` without the signals a replay doubled or broke on renamed tickers (``data.repair.find_duplicates``
    rows of the store it ran on): a merged-away symbol's signal when the surviving symbol has the same strategy
    and day (same bars, same signal), and every signal of the new ticker of a rename inside the Massive window
    from ``cutoff`` on (its series had a hole or another company's bars until the store was repaired)."""
    from swing_engine.data.delisted import MASSIVE_WINDOW_START

    if shadow.empty or dups.empty:
        return shadow
    to = dict(zip(dups["symbol"], dups["new_symbol"], strict=True))
    renamed = set(dups.loc[dups["handoff"].notna(), "new_symbol"])
    sym = shadow["symbol"].astype(str)
    sub = shadow.loc[sym.isin(set(to) | set(to.values())), ["strategy", "symbol", "as_of"]].astype({"symbol": str})
    sub["as_of"] = pd.to_datetime(sub["as_of"])
    broken = sub["symbol"].isin(renamed) & (sub["as_of"] >= pd.Timestamp(cutoff or MASSIVE_WINDOW_START))
    keys = pd.MultiIndex.from_frame(sub.loc[~broken].astype({"strategy": str}))
    twin = pd.MultiIndex.from_arrays([sub["strategy"].astype(str), sub["symbol"].map(to), sub["as_of"]])
    drop = broken | (sub["symbol"].isin(to) & twin.isin(keys))
    return shadow.drop(index=sub.index[drop.to_numpy()])


def with_costs(shadow: pd.DataFrame, store_path: Path) -> pd.DataFrame:
    """Prepare a replay ledger for grading from the bars in ``store_path``: drop the duplicate signals of renamed
    tickers (``drop_renamed``), attach per-signal ``cost_bps`` (research.costs) and SPY's R over each graded
    holding span (``mkt_r_<h>d``, ``market_r``)."""
    from swing_engine.data.repair import find_duplicates
    from swing_engine.data.store import Store
    from swing_engine.research.costs import attach_costs, cost_table

    if shadow.empty:
        return shadow
    store = Store(str(store_path), read_only=True)
    try:
        shadow = drop_renamed(shadow, find_duplicates(store))
        d = pd.to_datetime(shadow["as_of"]).dt.date
        bars = store.read_bars(sorted(set(shadow["symbol"].astype(str))), min(d) - pd.Timedelta(days=60), max(d))
        spy = store.read_bars([MARKET_SYMBOL])
    finally:
        store.close()
    out = attach_costs(shadow, cost_table(bars))
    spy = spy.assign(d=pd.to_datetime(spy["ts"]).dt.date).set_index("d")[["open", "close"]].sort_index()
    if len(spy) and {"entry", "stop"} <= set(out.columns):
        for h in DEFAULT_HORIZONS:
            if horizon_column("exit_date", h) in out.columns:
                out[horizon_column(MARKET_R, h)] = market_r(out, spy, h)
    return out


def read_shadow(paths: Iterable[Path]) -> pd.DataFrame:
    """The replay shadow ledgers of several stores (parallel replay lanes run on store copies), one row per
    (strategy, symbol, as_of): the last store listed wins a duplicate key."""
    from swing_engine.data.store import Store

    frames = []
    for path in paths:
        store = Store(str(path), read_only=True)
        try:
            frames.append(store.read_table(REPLAY_SHADOW_TABLE))
        finally:
            store.close()
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(["strategy", "symbol", "as_of"], keep="last")


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/replay.yaml")
    ap.add_argument("--store", action="append", default=[], help="extra replay store (repeatable)")
    ap.add_argument("--tag", default=RUN_TAG_PREFIX, help="replay run tag prefix (`swing research run`: the run id)")
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    store_path = ROOT / settings.data.store_path
    shadow = with_costs(read_shadow([store_path, *(ROOT / s for s in args.store)]), store_path)
    trades = load_trades(store_path.parent.joinpath(*RUNS_SUBDIR), args.tag)
    slugs = sorted(set(shadow["strategy"].astype(str))) if not shadow.empty else []
    written = write_cards(shadow, trades, slugs)
    print(f"wrote the Empirical section of {len(written)} cards; no card for: "
          f"{sorted(set(slugs) - set(written)) or 'none'}")


if __name__ == "__main__":
    main()


__all__ = ["WINDOWS", "drop_renamed", "market_r", "relative_r", "render_section", "replace_section", "write_cards"]
