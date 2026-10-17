"""Clenow "Stocks on the Move" on mid caps (Clenow 2015): docs/proposals/swing-methods-2026-10/batch5/
clenow_stocks_on_the_move_midcap.md.

Universe: `mcap_pit` ranks 501-1,500 (`_b5.smallmid` over the rows it is given; data.fundamentals.join_share_issuance;
silent without it), close >= $5, `med_dv_63` >= $2M. Score, computed here from the closes dated <= as_of: OLS of
ln(close) on 0..89 over the last 90 bars, (exp(slope x 252) - 1) x R-squared. On the week's rebalance session (the
first NYSE session on or after Wednesday): buy at the next open the universe names whose score is in the top 20%
of the universe, that close at or above their 100-day average and have no gap (|open / previous close - 1|) above
15% in the last 90 sessions, in score order, and only when SPY (`market_close`) closes above its own 200-day
average. On a rebalance session a held name is sold at the next open when it closes below its 100-day average, has
a gap above 15% in the last 90 sessions, or is out of the top 20% / out of the universe.

Deviations from the card: (1) Clenow uses no stop; the engine sizes on one, so the stop is 10 x ATR(20) below the
close: at the book's 1% risk per trade that is the card's shares = equity x 0.001 / ATR(20). It is a real stop if
ever reached, and a name whose 10 ATR exceed its price is skipped. (2) No re-sizing every second Wednesday (the
engine does not resize open positions). (3) The engine asks `should_exit` at a close before `signals` sees that
session, so "out of the top 20% or the universe" uses the ranking `signals` measured at the previous close (kept on
the instance; the live position manager, another process, never sells on rank); the average and gap exits use the
rebalance close itself. History: 200 sessions of SPY and 90 bars per stock, inside the replay's 300-session slice.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import next_trading_day, prev_trading_day, trading_days

from . import _b5 as b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, _local_day, finite

NAME = "clenow_stocks_on_the_move_midcap"
MARKET, GAP = "market_close", "gap_pct"  # features.extra; panel contract (open / previous close - 1)
SCORE = "clenow_score"
SESSIONS_PER_YEAR = 252  # card: annualised slope = exp(b x 252) - 1


def _row_key(row: pd.Series) -> tuple[date | None, str | None]:
    """(session date, symbol) of a panel row (replay / live: `ts` and `symbol` fields; run_backtest: the index)."""
    ts, sym = row.get(TS), row.get(SYMBOL)
    if (ts is None or sym is None) and isinstance(row.name, tuple):
        ts, sym = row.name[0], row.name[1]
    return (None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()), (None if sym is None else str(sym))


def is_rebalance(day: date, weekday: int) -> bool:
    """True on the week's first NYSE session on or after `weekday` (0 = Monday): Wednesday, or the next session
    when the market was closed on it."""
    back = day.weekday() - weekday
    return back >= 0 and trading_days(day - timedelta(days=back), day)[:1] == [day]


def trend_scores(closes: pd.DataFrame, n: int) -> pd.Series:
    """Per symbol of `closes` (symbol, ts, close): annualised exponential-regression slope x R-squared over its
    last `n` bars; symbols with fewer bars or a non-positive close are left out."""
    tail = closes.sort_values([SYMBOL, TS], kind="mergesort").groupby(SYMBOL, sort=False).tail(n)
    tail = tail.loc[(tail.groupby(SYMBOL, sort=False)["close"].transform("size") == n).to_numpy()]
    if tail.empty:
        return pd.Series(dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log(tail["close"].to_numpy(dtype=float)).reshape(-1, n)
        x = np.arange(n) - (n - 1) / 2.0
        dev = y - y.mean(axis=1, keepdims=True)
        slope = dev @ x / (x @ x)
        r2 = (dev @ x) ** 2 / ((x @ x) * (dev**2).sum(axis=1))
        score = (np.exp(slope * SESSIONS_PER_YEAR) - 1.0) * r2
    return pd.Series(score, index=tail[SYMBOL].to_numpy()[::n]).dropna()


@register("strategy", NAME)
class ClenowStocksOnTheMoveMidcap(PanelStrategy):
    name = NAME
    description = "Weekly: mid caps in the top 20% by 90-day regression slope x R-squared, above the 100-day, no 15% gap."
    default_params: dict[str, Any] = {
        "rank_first": 501,  # card: mcap_pit rank 501 ...
        "rank_last": 1500,  # ... to 1,500
        "min_price": 5.0,  # card: close >= $5
        "min_median_dollar_volume": 2_000_000.0,  # card: med_dv_63 >= $2M
        "regression_sessions": 90,  # card: ln(close) on 0..89, and the gap look-back
        "trend_sma": 100,  # card: disqualify below the 100-day MA
        "max_gap": 0.15,  # card: no gap > 15% in the last 90 sessions
        "hold_fraction": 0.20,  # card: top 20% of the universe by score
        "market_sma": 200,  # card: buy only when SPY close > SPY 200-day SMA
        "rebalance_weekday": 2,  # card: Wednesday (next session if a holiday)
        "atr_window": 20,  # card: ATR 20
        "size_atr_mult": 10.0,  # card: shares = equity x 0.001 / ATR(20) = 1% book risk on a stop 10 ATR away
        "max_hold_days": 10_000,  # rule exits only (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # the card's index filter is the SPY 200-day test below
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = [GAP]
    extra_features = [b5.MED_DV, MARKET, "sma_100", "atr_20", "max_90_of_gap_pct", "min_90_of_gap_pct"]
    prior_columns: list[str] = []
    engine_trail = False  # card: no stop or trail beyond the rules

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        p = self.params
        n = int(p["regression_sessions"])
        self._sma, self._atr = f"sma_{int(p['trend_sma'])}", f"atr_{int(p['atr_window'])}"
        self._gap_up, self._gap_down = f"max_{n}_of_{GAP}", f"min_{n}_of_{GAP}"
        # param-dependent: replay / CLI / nightly attach these via required_extras
        self.extra_features = [b5.MED_DV, MARKET, self._sma, self._atr, self._gap_up, self._gap_down]
        self._zone: tuple[date, frozenset[str]] | None = None  # (session, symbols in the hold zone at its close)

    def _disqualified(self, close: Any, sma: Any, gap_up: Any, gap_down: Any) -> bool | None:
        """Below the trend average or a gap beyond the limit; None when the row cannot tell."""
        if not (finite(close) and finite(sma) and finite(gap_up) and finite(gap_down)):
            return None
        limit = float(self.params["max_gap"])
        return float(close) < float(sma) or float(gap_up) > limit or float(gap_down) < -limit

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        day, sym = _row_key(row)
        if day is None or not is_rebalance(day, int(self.params["rebalance_weekday"])):
            return False
        if self._disqualified(row.get("close"), row.get(self._sma), row.get(self._gap_up), row.get(self._gap_down)):
            return True
        zone = self._zone
        return zone is not None and zone[0] == prev_trading_day(day) and sym not in zone[1]

    def _market_up(self, panel: pd.DataFrame, as_of: date) -> bool:
        """SPY close above its own SMA, from the market column's sessions dated <= as_of."""
        n = int(self.params["market_sma"])
        upto = panel.loc[(_local_day(panel[TS]) <= pd.Timestamp(as_of)).to_numpy(), [TS, MARKET]].dropna()
        spy = upto.drop_duplicates(TS).sort_values(TS)[MARKET].to_numpy(dtype=float)
        return len(spy) >= n and bool(spy[-1] > spy[-n:].mean())

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or b5.MCAP not in panel.columns or not self.market_ok(regime):
            return []
        p = self.params
        weekday = int(p["rebalance_weekday"])
        rebalance = is_rebalance(as_of, weekday)
        if not (rebalance or is_rebalance(next_trading_day(as_of), weekday)):
            return []  # the ranking is needed on the rebalance close (buys) and the close before it (sells)
        panel = c1.with_extras(self, panel)
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        uni = rows.loc[b5.smallmid(rows, int(p["rank_first"]), int(p["rank_last"])) & (rows["close"] >= float(p["min_price"]))
                       & (rows[b5.MED_DV] >= float(p["min_median_dollar_volume"]))]
        if uni.empty:
            return []
        past = (_local_day(panel[TS]) <= pd.Timestamp(as_of)).to_numpy() & panel[SYMBOL].isin(uni[SYMBOL]).to_numpy()
        score = trend_scores(panel.loc[past, [SYMBOL, TS, "close"]], int(p["regression_sessions"]))
        rank = score.rank(pct=True)
        top = rank.index[rank > 1.0 - float(p["hold_fraction"])]
        self._zone = (as_of, frozenset(map(str, top)))
        if not rebalance or not self._market_up(panel, as_of):
            return []
        out: list[Signal] = []
        for _, row in uni.loc[uni[SYMBOL].isin(top)].iterrows():
            close, atr, sym = float(row["close"]), row[self._atr], row[SYMBOL]
            if not finite(atr) or self._disqualified(close, row[self._sma], row[self._gap_up], row[self._gap_down]) is not False:
                continue
            stop = close - float(p["size_atr_mult"]) * float(atr)
            if stop <= 0:
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=float(score[sym]),
                                    features={SCORE: score[sym], "score_rank": rank[sym], self._atr: atr,
                                              b5.MCAP: row[b5.MCAP]},
                                    notes=f"slope x R2 score {float(score[sym]):.2f}, rank {float(rank[sym]):.2f} of "
                                          f"{len(rank)} mid caps")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
