"""Daily book of target weights, for "weights cards" (fixed target weights, not stop-sized): the engine's replay sizes
by stop distance and cannot hold them (strategies/volatility_managed_spy.py), so they are simulated here.

``simulate(opens, closes, costs, orders, delist_mult)``: wide frames indexed by session (columns symbols).
``orders[d]`` is a Series of target weights (summing to at most 1; the rest is cash at zero return) traded at the
OPEN of session d. A trade costs |dollars traded| x the symbol's ``costs`` (bp per side) of the session before d
(the signal day, as research.costs), or DEFAULT_COST_BPS without one. Between orders the share counts are held and
the weights drift. A symbol with no bar is carried at its last close; after its last bar in ``closes`` it is sold at
that close x ``delist_mult.get(symbol, 1)`` (data.delisted: a performance delisting's haircut; mergers 1). Returns
one row per session from the first order on: ret (close to close, net), cost and turnover (fractions of the equity
at the open), n_held.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

BPS = 1e4
DEFAULT_COST_BPS = 10.0  # research.backtest LARGE_CAP_SLIPPAGE_BPS: the floor for a liquid name


def simulate(opens: pd.DataFrame, closes: pd.DataFrame, costs: pd.DataFrame | None,
             orders: Mapping[Any, pd.Series], delist_mult: Mapping[str, float] | None = None) -> pd.DataFrame:
    days = list(closes.index)
    syms = list(closes.columns)
    col = {s: j for j, s in enumerate(syms)}
    o, c = opens.reindex(index=days, columns=syms).to_numpy(float), closes.to_numpy(float)
    cst = (costs.reindex(index=days, columns=syms).to_numpy(float) if costs is not None
           else np.full(c.shape, np.nan))
    seen = np.isfinite(c)
    last_bar = np.where(seen.any(axis=0), len(days) - 1 - np.argmax(seen[::-1], axis=0), -1)
    mult = np.array([float((delist_mult or {}).get(s, 1.0)) for s in syms])
    last = np.full(len(syms), np.nan)  # last close seen per symbol
    shares, cash, equity = np.zeros(len(syms)), 1.0, None
    rows: list[dict[str, Any]] = []
    for i, day in enumerate(days):
        gone = (shares != 0) & (last_bar < i)
        if gone.any():  # past its last bar: sold at that close (with the delisting haircut)
            cash += float((shares[gone] * last[gone] * mult[gone]).sum())
            shares[gone] = 0.0
        px_open = np.where(np.isfinite(o[i]), o[i], last)
        cost = turnover = 0.0
        if day in orders:
            held = np.where(shares != 0, shares * px_open, 0.0)
            at_open = cash + float(np.nansum(held))
            want = np.zeros(len(syms))
            for s, w in orders[day].items():
                if s in col and math.isfinite(float(w)) and np.isfinite(px_open[col[s]]):
                    want[col[s]] = float(w) * at_open
            delta = np.abs(want - np.nan_to_num(held))
            prev_cost = cst[i - 1] if i > 0 else np.full(len(syms), np.nan)
            cost = float((delta * np.where(np.isfinite(prev_cost), prev_cost, DEFAULT_COST_BPS)).sum() / BPS)
            turnover = float(delta.sum() / at_open) if at_open > 0 else 0.0
            shares = np.where(want != 0, want / np.where(px_open > 0, px_open, np.nan), 0.0)
            shares = np.nan_to_num(shares)
            cash = at_open - float(want.sum()) - cost
            if equity is None:
                equity = 1.0
            cost /= at_open
        last = np.where(np.isfinite(c[i]), c[i], last)
        if equity is None:
            continue
        value = cash + float(np.nansum(np.where(shares != 0, shares * last, 0.0)))
        rows.append({"day": day, "ret": value / equity - 1.0, "cost": cost, "turnover": turnover,
                     "n_held": int((shares != 0).sum())})
        equity = value
    return pd.DataFrame(rows).set_index("day") if rows else pd.DataFrame(columns=["ret", "cost", "turnover", "n_held"])


__all__ = ["simulate", "DEFAULT_COST_BPS"]
