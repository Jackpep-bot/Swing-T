"""Shareholder yield, small/mid caps (Boudoukh et al. 2007; Faber 2013): docs/proposals/swing-methods-2026-10/batch5/
shareholder_yield_smallmid.md.

Shareholder yield = `b5_div_yield` (regular cash dividends with an ex-date in the last 252 sessions / close) +
`b5_buyback_yield` (-ln of split-adjusted shares now over 252 sessions ago, with the net-issuance jump guard), both
from data.b5_fundamentals.join_b5_fundamentals; silent without them. Eligible: SMALLMID (`_b5.smallmid`), TTM
operating cash flow (`b5_ocf_ttm`) > 0, both inputs present, yield <= 25%. On the last NYSE session of a month: buy
the top 10% of the eligible names by yield at the next open; a held name is sold at the next open when it is not in
the top 20% (or no longer eligible). Catastrophe stop 3 x ATR(63); no target, no trail, no regime gate. Equal
weight and the 50-name cap come from the book.

Deviations from the card: (1) the engine asks `should_exit` at a close before `signals` sees that session, so the
hold zone is the one `signals` measured at the previous close (kept on the instance): buys rank on the month's last
close, sells on the close before it. Without that zone (the live position manager runs in another process) nothing
is sold on rank. (2) The card grades on a total-return store; the batch pre-registration runs price-only bars, so
dividends are in the signal but not in the P&L. Replay-only: the CLI scan and nightly do not run the b5 join.
History: the join needs 252 bars before a row (inside the replay's 400-day warm-up); the module itself needs none.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import prev_trading_day

from . import _b5 as b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, finite

NAME = "shareholder_yield_smallmid"
DIV, BUYBACK, OCF = "b5_div_yield", "b5_buyback_yield", "b5_ocf_ttm"  # data.b5_fundamentals.join_b5_fundamentals
YIELD = "shareholder_yield"
MONTH_END, ATR = "month_end", "atr_63"  # features.extra
NEEDS = (DIV, BUYBACK, OCF, b5.MCAP)


def _row_key(row: pd.Series) -> tuple[date | None, str | None]:
    """(session date, symbol) of a panel row (replay / live: `ts` and `symbol` fields; run_backtest: the index)."""
    ts, sym = row.get(TS), row.get(SYMBOL)
    if (ts is None or sym is None) and isinstance(row.name, tuple):
        ts, sym = row.name[0], row.name[1]
    return (None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()), (None if sym is None else str(sym))


@register("strategy", NAME)
class ShareholderYieldSmallmid(PanelStrategy):
    name = NAME
    description = "Month end: buy the top 10% of small/mid caps by dividend plus net buyback yield; hold the top 20%."
    default_params: dict[str, Any] = {
        "buy_fraction": 0.10,  # card: buy zone top 10% by yield
        "hold_fraction": 0.20,  # card: hold zone top 20%
        "max_yield": 0.25,  # card: yield <= 25% (data-error guard)
        "stop_atr_mult": 3.0,  # card: catastrophe stop 3 x atr_63
        "max_hold_days": 10_000,  # the rank is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MONTH_END, b5.MED_DV, ATR]
    prior_columns: list[str] = []
    engine_trail = False  # rank exit only

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._zone: tuple[date, frozenset[str]] | None = None  # (session, symbols in the hold zone at its close)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """On a month's last session: sell a name that was outside the hold zone at the previous close."""
        flag, zone = row.get(MONTH_END), self._zone
        if not finite(flag) or float(flag) != 1.0 or zone is None:
            return False
        day, sym = _row_key(row)
        return day is not None and zone[0] == prev_trading_day(day) and sym not in zone[1]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS) or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        total = rows[DIV] + rows[BUYBACK]  # NaN when either input is missing
        ok = b5.smallmid(rows) & (rows[OCF] > 0) & (total <= float(p["max_yield"]))
        rank = total.where(ok).rank(pct=True)
        self._zone = (as_of, frozenset(rows.loc[rank > 1.0 - float(p["hold_fraction"]), SYMBOL].astype(str)))
        if not (rows[MONTH_END] == 1.0).any():
            return []
        mult = float(p["stop_atr_mult"])
        out: list[Signal] = []
        for idx, row in rows.loc[rank > 1.0 - float(p["buy_fraction"])].iterrows():
            atr, close = row[ATR], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(rank[idx]),
                                    features={YIELD: total[idx], DIV: row[DIV], BUYBACK: row[BUYBACK],
                                              "yield_rank": rank[idx], b5.MCAP: row[b5.MCAP]},
                                    notes=f"shareholder yield {float(total[idx]):.1%} (dividends {float(row[DIV]):.1%}, "
                                          f"net buybacks {float(row[BUYBACK]):+.1%}), rank {float(rank[idx]):.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
