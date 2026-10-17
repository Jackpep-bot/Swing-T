"""Piotroski F-score (8 of 9 signals) among cheap small/mid caps (Piotroski 2000): docs/proposals/
swing-methods-2026-10/batch5/piotroski_fscore8_small_value.md.

`b5_fscore` (0-8; NaN when any input is missing, so a firm without a gross profit is never scored) and
`b5_book_to_market` (latest total equity / `mcap_pit`, equity > 0) come from data.b5_fundamentals
.join_b5_fundamentals, every value from filings usable on the day; silent without them. The signal definitions and
their registered proxies (net income = TTM diluted EPS x shares, equity / assets for leverage, no current ratio) are
in that module. On the last NYSE session of a month: among SMALLMID names (`_b5.smallmid`) in the top 30% by
book-to-market, buy those scoring >= 7 at the next open, highest score then highest book-to-market first (the
signal score). Catastrophe stop entry x 0.70; no target, no trail, no regime gate. Equal weight and the 40-name
cap come from the book.

Exits, at month-end checks only: the score has fallen below 6; or the position reaches the check nearest 126
sessions held (every sixth check: bars_held / 21 rounds to a multiple of 6) and would not be bought again there.
The card's "a name sold on time may be re-bought at the same check (no trade)" is that second rule: a name that
still scores >= 7 and is still in the cheap group is kept instead of sold and re-bought, and is looked at again six
checks later.

Deviation from the card: the engine asks `should_exit` at a close before `signals` sees that session, so "still
in the cheap group" uses the top-30% group `signals` measured at the previous close (kept on the instance); without
it (the live position manager runs in another process) the position is sold on time. The score tests use the
check day's own row. Replay-only: the CLI scan and nightly do not run the b5 join. History: none beyond the join's.
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

NAME = "piotroski_fscore8_small_value"
FSCORE, BM = "b5_fscore", "b5_book_to_market"  # data.b5_fundamentals.join_b5_fundamentals
MONTH_END = "month_end"  # features.extra
NEEDS = (FSCORE, BM, b5.MCAP)


def _row_key(row: pd.Series) -> tuple[date | None, str | None]:
    """(session date, symbol) of a panel row (replay / live: `ts` and `symbol` fields; run_backtest: the index)."""
    ts, sym = row.get(TS), row.get(SYMBOL)
    if (ts is None or sym is None) and isinstance(row.name, tuple):
        ts, sym = row.name[0], row.name[1]
    return (None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()), (None if sym is None else str(sym))


@register("strategy", NAME)
class PiotroskiFscore8SmallValue(PanelStrategy):
    name = NAME
    description = "Month end: cheapest 30% of small/mid caps by book-to-market with an F-score of 7 or 8; hold two quarters."
    default_params: dict[str, Any] = {
        "min_score": 7,  # card: buy score >= 7 (of 8)
        "exit_score": 6,  # card: sell when the score has fallen below 6
        "value_fraction": 0.30,  # card: top 30% by book-to-market within SMALLMID
        "hold_sessions": 126,  # card: sell after 126 sessions held ...
        "sessions_per_check": 21,  # ... judged at the monthly check nearest to it (a month is 21 sessions)
        "stop_pct": 0.30,  # card: catastrophe stop entry x 0.70
        "max_hold_days": 10_000,  # the 126-session rule is in should_exit (it can keep a name that still qualifies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MONTH_END, b5.MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # card: no trail

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._cheap: tuple[date, frozenset[str]] | None = None  # (session, top book-to-market group at its close)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        flag = row.get(MONTH_END)
        if not finite(flag) or float(flag) != 1.0:
            return False
        p = self.params
        score = row.get(FSCORE)
        if finite(score) and float(score) < float(p["exit_score"]):
            return True
        checks = round(bars_held / float(p["sessions_per_check"]))
        every = round(float(p["hold_sessions"]) / float(p["sessions_per_check"]))
        if checks < every or checks % every:
            return False
        day, sym = _row_key(row)  # the hold is up: sell unless it would be bought again at this check
        cheap = self._cheap
        again = (finite(score) and float(score) >= float(p["min_score"]) and day is not None and cheap is not None
                 and cheap[0] == prev_trading_day(day) and sym in cheap[1])
        return not again

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS) or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        rank = rows[BM].where(b5.smallmid(rows)).rank(pct=True)
        cheap = rank > 1.0 - float(p["value_fraction"])
        self._cheap = (as_of, frozenset(rows.loc[cheap, SYMBOL].astype(str)))
        if not (rows[MONTH_END] == 1.0).any():
            return []
        out: list[Signal] = []
        for idx, row in rows.loc[cheap & (rows[FSCORE] >= float(p["min_score"]))].iterrows():
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                                    score=float(row[FSCORE]) + float(rank[idx]),  # score first, then book-to-market
                                    features={FSCORE: row[FSCORE], BM: row[BM], "bm_rank": rank[idx], b5.MCAP: row[b5.MCAP]},
                                    notes=f"F-score {int(row[FSCORE])}/8, book-to-market {float(row[BM]):.2f} "
                                          f"(rank {float(rank[idx]):.2f})")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
