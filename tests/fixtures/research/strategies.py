"""Test-double strategies for the research backtester."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.interfaces import Strategy
from swing_engine.core.models import Side, Signal

from .synthetic_panel import FLAG_COLUMN

PCT = 100.0


def long_signal(
    symbol: str,
    as_of: date,
    entry: float,
    stop: float,
    target: float | None = None,
    score: float = 1.0,
    strategy: str = "scripted",
    side: Side = Side.LONG,
) -> Signal:
    rr = None if target is None else abs(target - entry) / abs(entry - stop)
    return Signal(
        strategy=strategy, symbol=symbol, side=side, as_of=as_of, entry=entry, stop=stop, target=target,
        reward_risk=rr, score=score,
    )


class FlagStrategy(Strategy):
    """Goes long at the close of any bar with ``flag == 1``: stop/target are fixed percentages."""

    name = "flag_test"
    default_params: dict[str, Any] = {"stop_pct": 3.0, "target_pct": 6.0, "max_hold_days": 10}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty:
            return []
        last_ts = panel["ts"].iloc[-1]
        if last_ts.date() != as_of:
            return []
        rows = panel[(panel["ts"] == last_ts) & (panel[FLAG_COLUMN] == 1)]
        stop_f = 1.0 - self.params["stop_pct"] / PCT
        target_f = 1.0 + self.params["target_pct"] / PCT
        return [
            long_signal(str(r.symbol), as_of, float(r.close), float(r.close) * stop_f, float(r.close) * target_f,
                        score=float(r.close), strategy=self.name)
            for r in rows.itertuples(index=False)
        ]


class ScriptedStrategy(Strategy):
    """Returns pre-built signals keyed by as_of date."""

    name = "scripted"

    def __init__(self, signals_by_date: Mapping[date, Iterable[Signal]], params: dict[str, Any] | None = None):
        super().__init__(params)
        self.by_date = {d: list(sigs) for d, sigs in signals_by_date.items()}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        return list(self.by_date.get(as_of, []))


class RecordingStrategy(ScriptedStrategy):
    """ScriptedStrategy that also records what it was shown each day (as_of, last panel ts, regime)."""

    name = "recording"

    def __init__(self, signals_by_date: Mapping[date, Iterable[Signal]] | None = None, params=None):
        super().__init__(signals_by_date or {}, params)
        self.calls: list[tuple[date, pd.Timestamp | None, dict[str, Any] | None]] = []

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        last = None if panel.empty else panel["ts"].max()
        self.calls.append((as_of, last, regime))
        return super().signals(panel, as_of, regime)
