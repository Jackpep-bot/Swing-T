"""Write replay results into each strategy card's ``## Empirical (replay)`` section (docs/strategies/<slug>.md).

Sources: the replay shadow ledger (``shadow_signals_replay``: every signal, graded gross at fixed horizons on the
signal's own stop / target) and the saved ``runs/replay/*.json`` files (the replay's own trades, net of costs but
competing for 8 slots with the other strategies of the same run). Run after the research replays::

    uv run python -m swing_engine.research.cards --settings config/replay.yaml

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

import pandas as pd

from swing_engine.research.shadow import DEFAULT_HORIZONS, REPLAY_SHADOW_TABLE, summarize_outcomes

ROOT = Path(__file__).resolve().parents[2]
CARDS_DIR = ROOT / "docs" / "strategies"
SECTION = "## Empirical (replay)"
RUNS_SUBDIR = ("runs", "replay")
PCT = 100.0


@dataclass(frozen=True)
class Window:
    start: date
    end: date
    label: str


#: The two research windows (docs/STATUS.md): Massive covers every US ticker from 2024-10-07; before that the
#: store holds Alpaca history for ~4,300 names that were still liquid in 2024 (survivorship bias).
WINDOWS: tuple[Window, ...] = (
    Window(date(2024, 10, 7), date(2026, 10, 5), "survivorship-free, every US ticker"),
    Window(date(2017, 1, 1), date(2024, 10, 4), "survivors only: ~4,300 names liquid in 2024, biased upward"),
)


def _fmt(x: Any, spec: str = ".2f") -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "inf" if isinstance(x, float) and math.isinf(x) and x > 0 else "-"
    return format(x, spec)


def _pct(x: Any) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x * PCT:.0f}%"


def shadow_table(frame: pd.DataFrame, horizons: Sequence[int] = DEFAULT_HORIZONS) -> str:
    """Markdown table: one row per regime plus ``all``; gross avg R and win rate at each horizon."""
    if frame.empty:
        return "_No signals in this window._"
    longest = max(horizons)
    groups = [*sorted(frame["regime"].fillna("unknown").astype(str).unique()), "all"]
    head = ["regime", "signals", "skipped"]
    for h in horizons:
        head += [f"win {h}d", f"avg R {h}d"]
    head += [f"PF {longest}d"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for g in groups:
        sub = frame if g == "all" else frame.loc[frame["regime"].fillna("unknown").astype(str) == g]
        cells = [f"**{g}**" if g == "all" else g]
        stats = {h: summarize_outcomes(sub, (), horizon=h).iloc[0] for h in horizons}
        first = stats[horizons[0]]
        cells += [str(int(first["n_signals"])), str(int(first["n_skipped"]))]
        for h in horizons:
            cells += [_pct(stats[h]["win_rate"]), _fmt(stats[h]["avg_r"], "+.2f")]
        cells += [_fmt(stats[longest]["profit_factor"])]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


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
    sh = shadow.loc[shadow["strategy"] == slug] if not shadow.empty else shadow
    tr = trades.loc[trades["strategy"] == slug] if not trades.empty else trades
    out = [
        SECTION,
        f"_Generated {(generated or date.today()).isoformat()} by `swing_engine.research.cards` from "
        "`swing replay --no-router` on real data._ Gross R per signal from the replay shadow ledger: every signal, "
        "entered the next session by its entry type, exited at its own stop or target or at the horizon close, "
        "no costs (round-trip costs run roughly 0.05-0.3R for these setups). Regimes are the playbook router's "
        "labels on the signal day.",
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


def load_trades(runs_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(runs_dir.glob("*_nr*.json")):  # the chunked --no-router research runs
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


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings
    from swing_engine.data.store import Store

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/replay.yaml")
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    store_path = ROOT / settings.data.store_path
    store = Store(str(store_path), read_only=True)
    shadow = store.read_table(REPLAY_SHADOW_TABLE)
    trades = load_trades(store_path.parent.joinpath(*RUNS_SUBDIR))
    slugs = sorted(set(shadow["strategy"].astype(str))) if not shadow.empty else []
    written = write_cards(shadow, trades, slugs)
    print(f"wrote the Empirical section of {len(written)} cards; no card for: "
          f"{sorted(set(slugs) - set(written)) or 'none'}")


if __name__ == "__main__":
    main()


__all__ = ["WINDOWS", "render_section", "replace_section", "write_cards"]
