"""Russell 2000 additions front-run (Madhavan 2003; Petajisto 2011): docs/proposals/swing-methods-2026-10/batch5/
russell_recon_addition_frontrun.md.

Membership proxy (card: no Russell membership file in the store): on a rank day, rank by `mcap_pit` (close x
point-in-time EDGAR shares, data.fundamentals.join_share_issuance; total, not float-adjusted) every row of that day
with a valid `mcap_pit` and an as-traded close >= $1. rank_R is that rank on this rank day, rank_prev the same rank
on the previous rank day; both are read from the panel rows of those two days, so each uses only the bars and
filings known on its own day. Rank day = the last NYSE session of April; reconstitution day = the 4th Friday of
June; plus the dated events in `extra_events` (card: FTSE Russell's second reconstitution, 2026-10-30 / 2026-12-11;
later semi-annual dates are not on the card and must be added there).

At the close of a rank day: buy (next open) names with rank_prev > 3,100, or no rank_prev but >= 252 bars, AND
1,300 <= rank_R <= 2,800 AND `med_dv_63` >= $500k; at most 40, largest caps first. Sold at the reconstitution-day
close (replay and live decide at that close and fill the next open, the card's stated fallback, which gives back the
recon-day closing pressure). Catastrophe stop entry x 0.75, no target, no trail, no regime gate.

Deviations and limits:
* Ranks are taken among the rows the caller passes. The replay passes its screened universe as of the signal day
  (config/prereg_b5.yaml: up to 4,000 names), so a name that has left that universe since the previous rank day is
  missing from rank_prev's population and every rank_prev is a little better (smaller) than the true one.
* History: the previous rank day is about 253 sessions back, inside the replay's 300-session signal slice
  (research.replay.SIGNAL_LOOKBACK_SESSIONS). No signals when the panel has no bars on it.
* The card fixes the rank day as the last business day of April for every year.
* Replay-only: the CLI scan and nightly do not run the share join, so `mcap_pit` is absent there and it is silent.
"""
from __future__ import annotations

from calendar import monthrange
from collections.abc import Mapping
from datetime import date, timedelta
from functools import cache
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import trading_days

from . import _catalog1 as c1
from ._b5 import MCAP, MED_DV, mcap_rank
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy

NAME = "russell_recon_addition_frontrun"
AS_TRADED = "close_as_traded"  # join_share_issuance; the adjusted close stands in when it is absent
FRIDAY = 4  # date.weekday()
#: the reconstitution calendar both Russell cards share
CALENDAR_PARAMS: dict[str, Any] = {
    "rank_month": 4,  # card: rank day is the last business day of April
    "recon_month": 6,  # card: effective after the close of the 4th Friday of June
    "recon_friday": 4,
    "extra_events": [["2026-10-30", "2026-12-11"]],  # card: second reconstitution from 2026 (rank day, recon day)
    "rank_min_close": 1.0,  # card: ranked names have close >= $1
}


@cache
def _events(year: int, rank_month: int, recon_month: int, nth_friday: int, extra: tuple) -> list[tuple[date, date]]:
    out = [(date.fromisoformat(r), date.fromisoformat(c)) for r, c in extra]
    for y in (year - 1, year):
        rank = trading_days(date(y, rank_month, 1), date(y, rank_month, monthrange(y, rank_month)[1]))[-1]
        first = date(y, recon_month, 1)
        friday = first + timedelta(days=(FRIDAY - first.weekday()) % 7 + 7 * (nth_friday - 1))
        out.append((rank, trading_days(friday - timedelta(days=6), friday)[-1]))
    return sorted(e for e in set(out) if year - 1 <= e[0].year <= year)


def recon_events(params: Mapping[str, Any], year: int) -> list[tuple[date, date]]:
    """(rank day, reconstitution day) of every event ranked in ``year - 1`` or ``year``, oldest first."""
    return _events(year, int(params["rank_month"]), int(params["recon_month"]), int(params["recon_friday"]),
                   tuple(tuple(e) for e in params["extra_events"]))


def local_day(panel: pd.DataFrame) -> pd.Series:
    """Session day of each panel row (naive, normalized)."""
    return pd.to_datetime(panel[TS]).dt.tz_localize(None).dt.normalize()


def as_traded_close(rows: pd.DataFrame) -> pd.Series:
    return rows[AS_TRADED] if AS_TRADED in rows.columns else rows["close"]


def mcap_ranks(panel: pd.DataFrame, day: pd.Series, on: date, min_close: float) -> pd.Series:
    """symbol -> `mcap_pit` rank (1 = largest) among the panel's rows dated ``on`` that have one and an as-traded
    close >= ``min_close``. Empty when the panel has no such row (history does not reach that day)."""
    rows = panel.loc[(day == pd.Timestamp(on)).to_numpy()]
    rows = rows.loc[rows[MCAP].notna() & (as_traded_close(rows) >= min_close)]
    return pd.Series(mcap_rank(rows).to_numpy(), index=rows[SYMBOL].to_numpy(), dtype="float64")


def row_day(row: pd.Series) -> date | None:
    """Session date of a panel row (live / replay: a `ts` field; run_backtest: the (ts, symbol) index)."""
    ts = row.get(TS)
    if ts is None and isinstance(row.name, tuple):
        ts = row.name[0]
    return None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()


@register("strategy", NAME)
class RussellReconAdditionFrontrun(PanelStrategy):
    name = NAME
    description = "Rank day: buy likely microcap-to-Russell-2000 additions by market-cap rank; sell on recon day."
    default_params: dict[str, Any] = {
        **CALENDAR_PARAMS,
        "prev_rank_min": 3100,  # card: rank_prev > 3,100 (clear of the banding around the Russell 3000 cut)
        "min_history_bars": 252,  # card: unranked last year qualifies with at least 252 bars of history
        "rank_min": 1300,  # card: 1,300 <= rank_R ...
        "rank_max": 2800,  # ... <= 2,800
        "min_median_dollar_volume": 500_000.0,  # card: med_dv_63 >= $500k at entry
        "max_names": 40,  # card: max 40, the largest caps first
        "stop_pct": 0.25,  # card: catastrophe stop at entry x 0.75
        "max_hold_days": 45,  # card front matter: holds 30-45 sessions; backstop only, recon day is the exit
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # card: no stop except the catastrophe stop

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """At or after the reconstitution day of the latest event ranked before this row's day."""
        day = row_day(row)
        past = [] if day is None else [recon for rank, recon in recon_events(self.params, day.year) if rank < day]
        return bool(past) and day >= past[-1]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or MCAP not in panel.columns or not self.market_ok(regime):
            return []
        p = self.params
        events = recon_events(p, as_of.year)
        k = next((i for i, (rank_day, _) in enumerate(events) if rank_day == as_of), None)
        if not k:  # not a rank day (or no earlier rank day to compare with)
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or pd.Timestamp(rows[TS].iloc[0]).date() != as_of:
            return []
        day = local_day(panel)
        now = mcap_ranks(panel, day, as_of, float(p["rank_min_close"]))
        prev = mcap_ranks(panel, day, events[k - 1][0], float(p["rank_min_close"]))
        if now.empty or prev.empty:
            return []
        bars = panel.loc[(day <= pd.Timestamp(as_of)).to_numpy(), SYMBOL].value_counts()
        rows = rows.assign(rank_r=rows[SYMBOL].map(now), rank_prev=rows[SYMBOL].map(prev), bars=rows[SYMBOL].map(bars))
        was_out = (rows["rank_prev"] > float(p["prev_rank_min"])) | (
            rows["rank_prev"].isna() & (rows["bars"] >= int(p["min_history_bars"])))
        ok = (was_out & rows["rank_r"].between(float(p["rank_min"]), float(p["rank_max"]))
              & (rows[MED_DV] >= float(p["min_median_dollar_volume"])))
        picks = rows.loc[ok].sort_values(["rank_r", SYMBOL]).head(int(p["max_names"]))
        out: list[Signal] = []
        for i, (_, row) in enumerate(picks.iterrows()):
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                score=1.0 - i / max(len(picks), 1),
                features={"rank_r": row["rank_r"], "rank_prev": row["rank_prev"], MCAP: row[MCAP]},
                notes=f"market-cap rank {row['rank_r']:.0f} (previous rank day {row['rank_prev']:.0f}); "
                      f"reconstitution {events[k][1]}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
