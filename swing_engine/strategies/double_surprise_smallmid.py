"""Double surprise, small/mid caps (Jegadeesh & Livnat 2006): docs/proposals/swing-methods-2026-10/batch5/
double_surprise_smallmid.md.

Reads `sue`, `rev_surprise`, `gross_prof`, `days_since_filing` and `days_since_earnings` (data.fundamentals.join_edgar,
usable from the session after the 10-Q/10-K filed date) and `mcap_pit` (join_share_issuance); silent without them.
Universe: SMALLMID (`_b5.smallmid`), close >= $5, and a gross profit on file (the card's stand-in for "not a
financial or utility"). On the session a filing becomes usable (`days_since_filing` == 0) and its `sue` differs from
the previous bar's (an amendment such as a 10-K/A repeats the old quarter and is not an event): buy at the next
open when both surprises are above the 80th percentile of the universe names whose latest filing became usable in
the prior 63 sessions (today's filers are not in their own reference group). Stop entry x 0.75; no target; no trail;
exit after 63 sessions, or at the next filing with a new `sue` when both surprises are at or below the 60th
percentile (out of the top two quintiles).

Deviations from the card: (1) as registered there, entry is keyed to the filing, not the earnings release, and the
hold is 63 sessions, not six months. (2) The engine asks `should_exit` at a close before `signals` sees that
session, so the exit's percentiles are the ones `signals` measured at the previous close (kept on the instance);
without them (the live position manager runs in another process) only the time stop and the stop apply.
`days_since_earnings` is logged per signal for the card's split by filing lag. History: one bar back (default).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import prev_trading_day

from . import _b5 as b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, TS, PanelStrategy, entry_feature, finite

log = structlog.get_logger(__name__)

NAME = "double_surprise_smallmid"
SUE, REV, GP, FILED, RELEASE = "sue", "rev_surprise", "gross_prof", "days_since_filing", "days_since_earnings"
NEEDS = (SUE, REV, GP, FILED, RELEASE, b5.MCAP)  # join_edgar / join_share_issuance columns


def _row_day(row: pd.Series) -> date | None:
    """Session date of a panel row (replay / live: a `ts` field; run_backtest: the (ts, symbol) index)."""
    ts = row.get(TS)
    if ts is None and isinstance(row.name, tuple):
        ts = row.name[0]
    return None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()


@register("strategy", NAME)
class DoubleSurpriseSmallmid(PanelStrategy):
    name = NAME
    description = "Small/mid caps: buy a filing whose earnings and revenue surprises are both top-quintile; hold 63 sessions."
    default_params: dict[str, Any] = {
        "top_fraction": 0.2,  # card: both surprises in the top quintile
        "hold_fraction": 0.4,  # card: exit when both fall out of the top two quintiles
        "reference_sessions": 63,  # card: breakpoints among filings usable in the prior 63 sessions
        "min_price": 5.0,  # card: close >= $5
        "stop_pct": 0.25,  # card: catastrophe stop entry x 0.75
        "max_hold_days": 63,  # card: exit after 63 sessions
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [b5.MED_DV]
    prior_columns: list[str] = [SUE]  # yesterday's sue tells a new quarter from an amendment
    engine_trail = False  # card: no trail

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._hold_cuts: tuple[date, float, float] | None = None  # (session, sue cut, revenue-surprise cut)

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        """A new filing (not the entry's quarter again) with both surprises out of the top two quintiles."""
        day, cuts, was = _row_day(row), self._hold_cuts, entry_feature(position, SUE)
        sue, rev, filed = row.get(SUE), row.get(REV), row.get(FILED)
        if day is None or cuts is None or was is None or not (finite(sue) and finite(rev) and finite(filed)):
            return False
        if float(filed) != 0.0 or float(sue) == was or cuts[0] != prev_trading_day(day):
            return False
        return float(sue) <= cuts[1] and float(rev) <= cuts[2]  # NaN cuts (too few names) compare False

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS):
            log.debug("strategy.skip", strategy=self.name, reason="panel has no EDGAR / market-cap columns")
            return []
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        uni = rows.loc[b5.smallmid(rows) & (rows["close"] >= float(p["min_price"])) & rows[GP].notna()]
        ref = uni.loc[(uni[FILED] >= 1) & (uni[FILED] <= float(p["reference_sessions"]))]
        top, hold = float(p["top_fraction"]), float(p["hold_fraction"])

        def cut(col: str, fraction: float) -> float:
            values = ref[col].dropna()
            return float(values.quantile(1.0 - fraction)) if len(values) * top >= 1.0 else float("nan")  # a quintile needs 5 names

        self._hold_cuts = (as_of, cut(SUE, hold), cut(REV, hold))
        sue_cut, rev_cut = cut(SUE, top), cut(REV, top)
        new = uni.loc[(uni[FILED] == 0) & (uni[SUE] > sue_cut) & (uni[REV] > rev_cut) & (uni[SUE] != uni[f"prior_{SUE}"])]
        out: list[Signal] = []
        for _, row in new.iterrows():
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                score=float(row[SUE]) + float(row[REV]),
                features={SUE: row[SUE], REV: row[REV], "sue_cut": sue_cut, "rev_cut": rev_cut, RELEASE: row[RELEASE],
                          b5.MCAP: row[b5.MCAP], "reference_names": len(ref)},
                notes=f"SUE {float(row[SUE]):.2f} > {sue_cut:.2f} and revenue surprise {float(row[REV]):.2f} > {rev_cut:.2f} "
                      f"(top {top:.0%} of {len(ref)} recent filers)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out

