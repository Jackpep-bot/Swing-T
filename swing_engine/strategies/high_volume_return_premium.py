"""High-volume return premium (Gervais, Kaniel & Mingelgrin, JF 2001): docs/strategies/high_volume_return_premium.md,
pre-registered in docs/preregistration/2026-10-10-two-picks.md.

Every session is a formation day. A stock is a high-volume stock when its dollar volume (close x volume, the paper's
measure) on `as_of` ranks in the top 10% of its own last 50 sessions (rank >= 46 of 50: the formation day against
the 49-day reference period). The registered version is the paper's "normal return" subsample: the formation-day
return must rank 16..35 of its own last 50 daily returns (middle 40%). Paper filters kept: every close of the 50
sessions >= $5, at least 252 bars of history. Long leg only (the paper is long high / short low volume). Buy the
next open, hold 20 sessions (`max_hold_days`), no target. Stop 3 x ATR(14) (engine choice, the paper has none; the
engine sizes on it). `engine_trail = False`. Not coded: NYSE-only, the size groups, the merger / SEO exclusions.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "high_volume_return_premium"
HIST = "hist_bars"  # features.extra
RANK_EPS = 1e-6  # float slack on pct x interval ranks


@register("strategy", NAME)
class HighVolumeReturnPremium(PanelStrategy):
    name = NAME
    description = "Dollar volume in the top 10% of its own 50 sessions on a normal-return day; hold 20 sessions."
    default_params: dict[str, Any] = {
        "interval_days": 50,  # paper: 49-day reference period + 1-day formation period
        "volume_rank_min": 46,  # paper eq. (2): high volume = rank >= 46 of 50 (top 10%)
        "ret_rank_min": 16,  # paper eq. (7): normal return = rank 16..35 of 50 (middle 40%)
        "ret_rank_max": 35,
        "min_price": 5.0,  # paper: no close below $5 in the reference period
        "min_history_bars": 252,  # paper: at least one year of trading history
        "stop_atr_mult": 3.0,  # engine choice (no stop in the paper), as pead_sue / earnings_seasonality
        "max_hold_days": 20,  # paper: 20-day test period
        P_MIN_MARKET_TREND: TREND_DOWN,  # paper: no market filter
        P_MIN_RR: 0.0,  # no target
    }
    features_required = ["atr_14", "avg_vol_50d"]
    extra_features = ["pctile_50_of_dollar_vol", "pctile_50_of_ret_1d", "min_50_of_close", HIST]  # default interval
    prior_columns: list[str] = []
    engine_trail = False  # hold the 20-day test period, as the paper does

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        n = int(self.params["interval_days"])
        self.dv_pct, self.ret_pct, self.min_close = f"pctile_{n}_of_dollar_vol", f"pctile_{n}_of_ret_1d", f"min_{n}_of_close"
        self.extra_features = [self.dv_pct, self.ret_pct, self.min_close, HIST]  # param-dependent names

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        n = float(p["interval_days"])
        vol_rank, ret_rank = rows[self.dv_pct] * n, rows[self.ret_pct] * n
        fire = ((vol_rank >= float(p["volume_rank_min"]) - RANK_EPS)
                & (ret_rank >= float(p["ret_rank_min"]) - RANK_EPS) & (ret_rank <= float(p["ret_rank_max"]) + RANK_EPS)
                & (rows[self.min_close] >= float(p["min_price"])) & (rows[HIST] >= float(p["min_history_bars"])))
        out: list[Signal] = []
        for idx, row in rows.loc[fire].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr):
                continue
            rvol = self.volume_ratio(row, "avg_vol_50d")
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None, score=rvol,
                features={"dollar_vol_rank": vol_rank[idx], "ret_rank": ret_rank[idx], "rvol_50": rvol},
                notes=f"dollar volume rank {vol_rank[idx]:.0f}/{n:.0f}, return rank {ret_rank[idx]:.0f}/{n:.0f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
