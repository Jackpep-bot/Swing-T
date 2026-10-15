"""Swing-pivot helpers for the base detectors (vcp_sepa_breakout, ibd_other_bases). Not a strategy module.

Pivots read only bars <= ``end`` and are confirmed ``width`` bars after the pivot bar, so callers that pass
``end`` = the bar before the as-of bar stay point-in-time.
"""
from __future__ import annotations

import numpy as np

Pivot = tuple[str, int, float]  # ("H" | "L", bar index, price)


def swing_pivots(high: np.ndarray, low: np.ndarray, start: int, end: int, width: int) -> list[Pivot]:
    """Alternating confirmed pivots with index in [start, end - width]: ("H", i, high[i]) when high[i] is the highest
    of high[i-width .. i+width], ("L", i, low[i]) the mirror. A run of one kind keeps its most extreme pivot."""
    raw: list[Pivot] = []
    for i in range(max(start, width), end - width + 1):
        hs, ls = high[i - width : i + width + 1], low[i - width : i + width + 1]
        if not (np.isfinite(hs).all() and np.isfinite(ls).all()):
            continue
        if high[i] >= hs.max():
            raw.append(("H", i, float(high[i])))
        if low[i] <= ls.min():
            raw.append(("L", i, float(low[i])))
    return alternate(raw)


def alternate(pivots: list[Pivot]) -> list[Pivot]:
    """Collapse runs of same-kind pivots to the most extreme one (the later one on ties)."""
    out: list[Pivot] = []
    for p in pivots:
        if out and out[-1][0] == p[0]:
            if (p[2] >= out[-1][2]) if p[0] == "H" else (p[2] <= out[-1][2]):
                out[-1] = p
        else:
            out.append(p)
    return out


def trim_to_last_low(seq: list[Pivot]) -> list[Pivot]:
    """Drop trailing pivots after the last swing low."""
    while seq and seq[-1][0] != "L":
        seq = seq[:-1]
    return seq
