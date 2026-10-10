"""Rank hysteresis (Novy-Marx & Velikov 2016 buy/hold spread): enter only near the top of a rank, keep holding
until the name falls out of a wider band. Cuts turnover (and costs) of rank-based books.

Catalog card ``cost_aware_rank_hysteresis``: enter in the top 10%, exit below the top 20-30%.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def _band(size: float, n: int) -> int:
    """``size`` >= 1 is a count; 0 < ``size`` < 1 is a fraction of ``n`` (rounded up)."""
    if size <= 0:
        raise ValueError(f"band size must be positive, got {size}")
    return int(size) if size >= 1 else math.ceil(size * n)


def rank_hysteresis(ranked: Sequence[str], held: Iterable[str], enter_top: float, hold_top: float) -> list[str]:
    """Names to hold after this rebalance, in rank order.

    ``ranked`` is best first. A name is held if it is in the top ``enter_top``, or it is already ``held`` and
    still in the top ``hold_top`` (``hold_top >= enter_top``). Held names missing from ``ranked`` are dropped.
    """
    n = len(ranked)
    k, m = _band(enter_top, n), _band(hold_top, n)
    if m < k:
        raise ValueError(f"hold band ({m}) must be at least the entry band ({k})")
    keep = set(held)
    return [s for i, s in enumerate(ranked) if i < k or (i < m and s in keep)]
