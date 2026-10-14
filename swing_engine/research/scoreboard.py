"""Scoreboard of every pre-registered card: one table from the results files in docs/preregistration/, and what
separated the better cards from the rest. Descriptive: it grades nothing and logs no trial. Run::

    uv run python -m swing_engine.research.scoreboard        # writes docs/research_scoreboard.md

Read from two machine-written formats: the engine replays' tables (``research.prereg_eval``: per strategy and window,
then "Against buy-and-hold SPY") and the weights cards' tables (``research.b9_books`` style: per card, a "book" and a
"SPY" row per window; and ``research.vrp_overlay``). Windows: "2017-24", "2024-26" and "2017-26" (pooled).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT

RESULTS = ROOT / "docs" / "preregistration"
OUT = ROOT / "docs" / "research_scoreboard.md"
WINDOW = {"2024": "2024-26", "2017": "2017-24", "B": "2024-26", "A": "2017-24", "pooled": "2017-26", "2017-26": "2017-26"}
SHORT_HOLD_DAYS = 10  # "short hold": batches 5-7 found every card holding under two weeks lost to costs


def _num(cell: str) -> float:
    """'+12.3%' -> 0.123, '-0.45' -> -0.45, '-' -> NaN."""
    c = cell.strip().replace(",", "")
    if c in ("", "-", "n/a", "nan"):
        return float("nan")
    try:
        return float(c[:-1]) / 100.0 if c.endswith("%") else float(c)
    except ValueError:
        return float("nan")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _verdicts(text: str) -> dict[str, str]:
    return dict(re.findall(r"^- \*\*([\w]+)\*\*: (PASS|FAIL)", text, re.M))


def parse_engine(text: str, source: str) -> list[dict]:
    """Rows of a ``prereg_eval`` report: the standard table joined with the 'Against buy-and-hold' table."""
    rows: dict[tuple[str, str], dict] = {}
    table = None
    for line in text.splitlines():
        if line.startswith("| strategy | window | trades"):
            table = "main"
        elif line.startswith("| strategy | window | excess"):
            table = "vs"
        elif not line.startswith("|"):
            table = None if not line.strip() else table
        elif table and not line.startswith("|---"):
            c = _cells(line)
            key = (c[0], WINDOW.get(c[1], c[1]))
            r = rows.setdefault(key, {"source": source, "card": c[0], "window": key[1], "kind": "engine"})
            if table == "main" and len(c) >= 12:
                r.update(trades=_num(c[2]), net_r=_num(c[3]), sharpe=_num(c[5]), max_dd=_num(c[8]), hold_days=_num(c[9]),
                         window_return=_num(c[11]))
            elif table == "vs" and len(c) >= 11:
                r.update(excess_ann=_num(c[2]), alpha_ann=_num(c[5]), alpha_t=_num(c[6]), beta=_num(c[7]),
                         exposure=_num(c[8]), turnover=_num(c[11]) if len(c) > 11 else float("nan"))
    return list(rows.values())


def parse_weights(text: str, source: str) -> list[dict]:
    """Rows of a weights-card report (b9_books / b11_books / b12_books / vrp_overlay layouts)."""
    out: list[dict] = []
    card, cols, spy_ret = None, [], {}
    title = re.search(r"^# Batch \d+ results: `(\w+)`", text, re.M)
    if title:
        card = title.group(1)
    for line in text.splitlines():
        m = re.match(r"^## `(\w+)`", line)
        if m:
            card = m.group(1)
        if line.startswith("| window |"):
            cols = _cells(line)
            continue
        if not line.startswith("|") or line.startswith("|---") or not cols or card is None:
            continue
        c = dict(zip(cols, _cells(line), strict=False))
        label = c.get("book", "")
        w = WINDOW.get(c.get("window", ""), None)
        if w is None or "descriptive" in c.get("window", ""):
            continue
        if label == "SPY":
            spy_ret[(card, w)] = _num(c.get("return/yr", ""))
            continue
        if label not in ("book", "overlay"):
            continue
        out.append({"source": source, "card": card, "window": w, "kind": "weights", "cagr": _num(c.get("return/yr", "")),
                    "max_dd": -_num(c.get("deepest drop", "")), "sharpe": _num(c.get("Sharpe", "")),
                    "alpha_ann": _num(c.get("alpha/yr", "")), "alpha_t": _num(c.get("alpha t", "")),
                    "beta": _num(c.get("beta", "")), "turnover": _num(c.get("turnover/yr", "")), "exposure": 1.0})
    for r in out:
        spy = spy_ret.get((r["card"], r["window"]))
        r["excess_ann"] = r["cagr"] - spy if spy is not None else float("nan")
    return out


def collect(root: Path = RESULTS) -> pd.DataFrame:
    rows: list[dict] = []
    for path in sorted(root.glob("*-results.md")):
        text = path.read_text()
        verdicts = _verdicts(text)
        found = parse_engine(text, path.name) if "| strategy | window | trades" in text else parse_weights(text, path.name)
        for r in found:
            r["verdict"] = verdicts.get(r["card"], re.search(r"## Verdict: (PASS|FAIL)", text).group(1)
                                        if re.search(r"## Verdict: (PASS|FAIL)", text) else "")
        rows += found
    frame = pd.DataFrame(rows)
    return frame.loc[frame["window"].isin(["2017-24", "2024-26", "2017-26"])].reset_index(drop=True)


def _fmt(x: float, spec: str) -> str:
    return "-" if x is None or not np.isfinite(x) else format(x, spec)


def _group(frame: pd.DataFrame, mask: pd.Series, label: str) -> str:
    g = frame.loc[mask]
    return (f"| {label} | {g['card'].nunique()} | {_fmt(g['alpha_ann'].median(), '+.1%')} | "
            f"{_fmt(g['alpha_t'].median(), '+.2f')} | {_fmt((g['alpha_ann'] > 0).mean(), '.0%')} |")


def render(frame: pd.DataFrame) -> list[str]:
    b = frame.loc[frame["window"] == "2024-26"]
    lines = ["# Research scoreboard: every pre-registered card so far", "",
             "Generated by `swing_engine.research.scoreboard` from docs/preregistration/*-results.md. Descriptive: "
             "nothing here passes or fails a card, and nothing is a new trial. Alpha is against SPY (price-only bars).", "",
             f"{frame['card'].nunique()} cards, {len(frame)} card-windows. Passed their own registered rule: "
             + (", ".join(f"`{c}` ({src})" for c, src in frame.loc[frame["verdict"] == "PASS"].drop_duplicates("card")[
                 ["card", "source"]].itertuples(index=False)) or "none") + ".", "",
             "## Best 15 by alpha t in 2024-26 (survivorship-free window)", "",
             "| card | kind | alpha/yr | alpha t | beta | excess vs SPY/yr | turnover/yr | hold days | invested | source |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in b.sort_values("alpha_t", ascending=False).head(15).itertuples():
        lines.append(f"| {r.card} | {r.kind} | {_fmt(r.alpha_ann, '+.1%')} | {_fmt(r.alpha_t, '+.2f')} | "
                     f"{_fmt(r.beta, '.2f')} | {_fmt(r.excess_ann, '+.1%')} | {_fmt(r.turnover, '.0%')} | "
                     f"{_fmt(getattr(r, 'hold_days', float('nan')), '.0f')} | {_fmt(r.exposure, '.0%')} | {r.source} |")
    a = frame.loc[frame["window"] == "2017-24"]
    lines += ["", "## Cards with alpha t above 1 in any window", "",
              "| card | window | alpha/yr | alpha t | beta | source |", "|---|---|---|---|---|---|"]
    for r in frame.loc[frame["alpha_t"] > 1].sort_values(["card", "window"]).itertuples():
        lines.append(f"| {r.card} | {r.window} | {_fmt(r.alpha_ann, '+.1%')} | {_fmt(r.alpha_t, '+.2f')} | "
                     f"{_fmt(r.beta, '.2f')} | {r.source} |")
    hold = b.get("hold_days", pd.Series(np.nan, index=b.index))
    lines += ["", "## What separated them (2024-26 window, medians)", "",
              "| group | cards | median alpha/yr | median alpha t | share with alpha > 0 |", "|---|---|---|---|---|",
              _group(b, b["kind"] == "weights", "weights cards (fully or mostly invested, few trades)"),
              _group(b, b["kind"] == "engine", "engine cards (stop-sized trades)"),
              _group(b, hold <= SHORT_HOLD_DAYS, f"engine, average hold <= {SHORT_HOLD_DAYS} sessions"),
              _group(b, hold > SHORT_HOLD_DAYS, f"engine, average hold > {SHORT_HOLD_DAYS} sessions"),
              _group(b, b["turnover"] >= 5.0, "turnover >= 500% a year"),
              _group(b, b["turnover"] < 3.0, "turnover < 300% a year"),
              _group(b, b["exposure"] < 0.5, "under half invested on average"),
              _group(b, b["exposure"] >= 0.8, "80%+ invested"),
              "", f"Same split in 2017-24 for comparison: weights cards median alpha t "
              f"{_fmt(a.loc[a['kind'] == 'weights', 'alpha_t'].median(), '+.2f')}, engine cards "
              f"{_fmt(a.loc[a['kind'] == 'engine', 'alpha_t'].median(), '+.2f')}.", ""]
    return lines


def main() -> None:
    frame = collect()
    OUT.write_text("\n".join(render(frame)) + "\n", encoding="utf-8")
    print(f"{frame['card'].nunique()} cards -> {OUT}")


if __name__ == "__main__":
    main()
