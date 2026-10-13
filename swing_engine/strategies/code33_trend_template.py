"""Minervini "Code 33" with the trend template as trigger: docs/proposals/swing-methods-2026-10/batch5/
code33_trend_template.md.

`b5_code33` (data.b5_fundamentals.join_b5_fundamentals; silent without it or without `mcap_pit`) is 1 when the
latest usable filing shows year-over-year EPS growth, revenue growth and margin each rising over its three latest
quarters, with the latest EPS and revenue growth positive (quarters from 10-Q/10-K values point-in-time; growth
skipped when |EPS a year ago| < $0.05). Trend template on the bar: close > sma_150 and sma_200; sma_150 > sma_200;
the 21-session regression slope of sma_200 > 0; sma_50 > sma_150 and sma_200; close > sma_50; close >= 30% above the
52-week low and within 25% of the 52-week high (`low_52w` / `high_52w`: extreme low / high of 252 bars);
`rs_rating_ibd` >= 70. Buy at the next open on the first session both are true (they were not both true on the
symbol's previous bar; either may turn true first) when the name is in SMALLMID (`_b5.smallmid`) and the close is no
more than 5% above sma_10; an extended first session is passed, not retried. Stop: the higher of entry x 0.92 and
entry - 2.5 x atr_14. Exit at the next open after a close below sma_50, after 63 sessions, or when a later filing
breaks Code 33 (`b5_code33` == 0) and the close is below sma_20.

Card silent on trailing: only the exits it lists run (`engine_trail = False`). `rs_rating_ibd` is a percentile over
the panel the extras are computed on. Replay-only: the CLI scan and nightly do not run the b5 join. History: the
template needs 252 bars (52-week range, RS rating) before a row, inside the replay's 400-day warm-up; the module
itself reads two bars.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _b5 as b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, _local_day, finite

NAME = "code33_trend_template"
CODE33 = "b5_code33"  # data.b5_fundamentals.join_b5_fundamentals
SMA10, SMA20, SMA50, SMA200, ATR, HIGH, LOW = "sma_10", "sma_20", "sma_50", "sma_200", "atr_14", "high_52w", "low_52w"
SMA150, SLOPE, RS = "sma_150", "linreg_slope_21_of_sma_200", "rs_rating_ibd"  # features.extra


@register("strategy", NAME)
class Code33TrendTemplate(PanelStrategy):
    name = NAME
    description = "Small/mid caps: three quarters of accelerating EPS, sales and margin plus Minervini's trend template."
    default_params: dict[str, Any] = {
        "min_above_low": 0.30,  # card: close >= 30% above the 52-week low
        "max_below_high": 0.25,  # card: within 25% of the 52-week high
        "min_rs_rating": 70.0,  # card: rs_rating_ibd >= 70
        "max_extension": 0.05,  # card: close no more than 5% above sma_10
        "stop_pct": 0.08,  # card: stop = max(entry x 0.92, ...
        "stop_atr_mult": 2.5,  # ... entry - 2.5 x atr_14)
        "max_hold_days": 63,  # card: exit after 63 sessions
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = [SMA10, SMA20, SMA50, SMA200, ATR, HIGH, LOW]
    extra_features = [b5.MED_DV, SMA150, SLOPE, RS]
    prior_columns: list[str] = []
    engine_trail = False  # the card lists its exits; the engine overlay is not one of them

    def _setup(self, r: pd.DataFrame) -> pd.Series:
        """Code 33 and the trend template both true, per row of `r` (NaN inputs are False)."""
        p, c = self.params, r["close"]
        return ((r[CODE33] == 1.0) & (c > r[SMA150]) & (c > r[SMA200]) & (r[SMA150] > r[SMA200]) & (r[SLOPE] > 0)
                & (r[SMA50] > r[SMA150]) & (r[SMA50] > r[SMA200]) & (c > r[SMA50])
                & (c >= (1.0 + float(p["min_above_low"])) * r[LOW]) & (c >= (1.0 - float(p["max_below_high"])) * r[HIGH])
                & (r[RS] >= float(p["min_rs_rating"])))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        close, sma50, sma20, code = row.get("close"), row.get(SMA50), row.get(SMA20), row.get(CODE33)
        if not finite(close):
            return False
        if finite(sma50) and float(close) < float(sma50):
            return True
        return finite(code) and float(code) == 0.0 and finite(sma20) and float(close) < float(sma20)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or CODE33 not in panel.columns or b5.MCAP not in panel.columns or not self.market_ok(regime):
            return []
        p = self.params
        panel = c1.with_extras(self, panel)
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        now = rows.loc[b5.smallmid(rows) & self._setup(rows)]
        if now.empty:
            return []
        before = panel.loc[(_local_day(panel[TS]) < _local_day(now[TS]).max()).to_numpy()
                           & panel[SYMBOL].isin(now[SYMBOL]).to_numpy()]
        prev = before.sort_values(TS, kind="mergesort").groupby(SYMBOL, sort=False).tail(1)  # each candidate's previous bar
        already = set(prev.loc[self._setup(prev), SYMBOL])
        out: list[Signal] = []
        for _, row in now.loc[~now[SYMBOL].isin(already)].iterrows():
            close, atr, sma10 = float(row["close"]), row[ATR], row[SMA10]
            if not (finite(atr) and finite(sma10)) or close > (1.0 + float(p["max_extension"])) * float(sma10):
                continue
            stop = max(close * (1.0 - float(p["stop_pct"])), close - float(p["stop_atr_mult"]) * float(atr))
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=float(row[RS]),
                                    features={CODE33: row[CODE33], RS: row[RS], "extension": close / float(sma10) - 1.0,
                                              "above_low": close / float(row[LOW]) - 1.0, b5.MCAP: row[b5.MCAP]},
                                    notes=f"Code 33 and trend template first true together; RS {float(row[RS]):.0f}, "
                                          f"{close / float(sma10) - 1.0:+.1%} vs the 10-day")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
