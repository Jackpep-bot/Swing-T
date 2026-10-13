"""Pre-earnings run-up of past winners (Aboody, Lehavy & Trueman 2010): docs/proposals/swing-methods-2026-10/batch5/
pre_earnings_runup_winners.md.

Winners: on the last NYSE session of the prior calendar quarter, the top 1% by `ret_252d` (raw 252-session return,
no skip month) among that day's rows with an as-traded close >= $5 and `med_dv_63` >= $1M. The value is read from
the panel row of that day, so the ranking never moves inside the quarter. Trigger: a winner whose
`sessions_to_expected_earnings` (join_edgar: last year's report session + 364 days, point-in-time) is 5 at a close
and that still passes the two floors; buy the next open (day -4). Catastrophe stop entry x 0.85, no target, no
trail, no regime gate; the 20-position cap comes from the book.

Exit, a deviation from the card's text: the card sells at the close of day -1 so that a report after that close or
before the next open is never held. The replay and the live engine fill rule exits at the next open, so a decision
at the day -1 close would sell at the day 0 open, through the report. The exit is therefore decided at the close
with 2 sessions to go (`exit_sessions_to_report`) and fills at the open of day -1: the report is never held, and the
day -1 session is given up. Set it to 1 only on an engine that fills rule exits at the close (run_backtest). If the
actual report arrives early (`days_since_earnings` shows one on or after the entry session) it exits at the next
open, as the card says; `max_hold_days` 5 is the backstop.

Limits: the winner population is the rows the caller passes (the replay's screened universe as of the signal day,
measured on the quarter-end day). Silent without the two earnings columns.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import trading_days

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, finite

NAME = "pre_earnings_runup_winners"
TO_EXP, SINCE = "sessions_to_expected_earnings", "days_since_earnings"  # data.fundamentals.join_edgar
RET, MED_DV = "ret_252d", "med_dv_63"  # contract column (card: raw 252-session return); features.extra
AS_TRADED = "close_as_traded"  # join_share_issuance; the adjusted close stands in when it is absent
QUARTER_MONTHS = 3
WEEK_PAD_DAYS = 10  # calendar days searched back from a quarter's first day for its previous session


@register("strategy", NAME)
class PreEarningsRunupWinners(PanelStrategy):
    name = NAME
    description = "Top 1% by 12-month return at the last quarter end: buy 4 sessions before the expected report, sell before it."
    default_params: dict[str, Any] = {
        "min_price": 5.0,  # card: close >= $5
        "min_median_dollar_volume": 1_000_000.0,  # card: med_dv_63 >= $1M
        "top_fraction": 0.01,  # card: top 1% of the eligible universe on the quarter-end day
        "entry_sessions_to_report": 5,  # card: trigger at sessions_to_expected_earnings == 5, fill next open (day -4)
        "exit_sessions_to_report": 2,  # card: out before the report; 2 with next-open fills (see the docstring)
        "stop_pct": 0.15,  # card: catastrophe stop entry x 0.85
        "max_hold_days": 5,  # card front matter: holds 3-5 sessions; backstop for a report that never comes
        P_MIN_MARKET_TREND: TREND_DOWN,  # card engine version: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = [RET]
    extra_features = [MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # card: no trail

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """The expected report is `exit_sessions_to_report` sessions away or closer, or the report already came."""
        to, since = row.get(TO_EXP), row.get(SINCE)
        if finite(since) and float(since) < bars_held:
            return True
        return finite(to) and float(to) <= float(self.params["exit_sessions_to_report"])

    def _eligible(self, rows: pd.DataFrame) -> pd.Series:
        price = rows[AS_TRADED] if AS_TRADED in rows.columns else rows["close"]
        return ((price >= float(self.params["min_price"]))
                & (rows[MED_DV] >= float(self.params["min_median_dollar_volume"]))).fillna(False)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in (TO_EXP, SINCE)) or not self.market_ok(regime):
            return []
        p = self.params
        panel = c1.with_extras(self, panel)
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        due = rows.loc[(rows[TO_EXP] == float(p["entry_sessions_to_report"])) & self._eligible(rows)]
        if due.empty:
            return []
        quarter_start = date(as_of.year, (as_of.month - 1) // QUARTER_MONTHS * QUARTER_MONTHS + 1, 1)
        quarter_end = trading_days(quarter_start - timedelta(days=WEEK_PAD_DAYS), quarter_start - timedelta(days=1))[-1]
        day = pd.to_datetime(panel[TS]).dt.tz_localize(None).dt.normalize()
        pop = panel.loc[(day == pd.Timestamp(quarter_end)).to_numpy()]
        pop = pop.loc[self._eligible(pop) & pop[RET].notna()]
        if pop.empty:
            return []
        pct = pd.Series(pop[RET].rank(pct=True).to_numpy(), index=pop[SYMBOL].to_numpy())
        ret = pd.Series(pop[RET].to_numpy(), index=pop[SYMBOL].to_numpy())
        out: list[Signal] = []
        for _, row in due.iterrows():
            rank = pct.get(row[SYMBOL])
            if not finite(rank) or float(rank) <= 1.0 - float(p["top_fraction"]):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None, score=float(rank),
                features={"quarter_end_ret_252d": ret[row[SYMBOL]], "winner_pct": rank, TO_EXP: row[TO_EXP]},
                notes=f"12-month return {float(ret[row[SYMBOL]]):+.0%} on {quarter_end} (top "
                      f"{float(p['top_fraction']):.0%}); report expected in {int(row[TO_EXP])} sessions",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
