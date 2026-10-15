"""Connors RSI(2) family variants (long): docs/strategies/connors_rsi2_variants.md, docs/methods/11.

A thin subclass of `rsi2_meanrev` with a `variant` param (each variant is its own trial):
- `double_7s`: close > SMA200 and the close is the lowest close of 7 bars; exit at the highest close of 7 bars.
- `cumulative_rsi`: close > SMA200 and RSI2[t] + RSI2[t-1] < 35; exit RSI2 > 65.
- `r3`: close > SMA200; RSI2 falls 3 days in a row, the first of them < 60, today < 10; exit RSI2 > 70.
- `crsi_pullback`: price > $5, 20-day avg volume >= 250k (card: 21-day), ADX(10) > 30, low at least 4% under the
  prior close, close in the bottom 25% of the range, ConnorsRSI(3,2,100) < 15; buy limit 4% under the close
  (`entry_type = limit`); exit ConnorsRSI > 50.
Connors uses no price stop ("stops hurt"); the card asks for a catastrophic `2 x atr_14` stop and a 10-session cap.
Approximation: the source buys the close (MOC); the engine fills at the next open (or the limit). Not built: the
weekly Alpha Formula (weekly RSI(2), top-500 liquidity, 10 lowest-vol slots: needs a weekly resampler and a portfolio
selection hook).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, finite
from .rsi2_meanrev import RSI2MeanRev

NAME = "connors_rsi2_variants"
VARIANTS = ("double_7s", "cumulative_rsi", "r3", "crsi_pullback")
CRSI = "connors_rsi"
LOW_7, HIGH_7 = "min_7_of_close", "max_7_of_close"  # Double 7s: 7-bar closing low / high (book ch. 10)


@register("strategy", NAME)
class ConnorsRSI2Variants(RSI2MeanRev):
    name = NAME
    description = "Connors RSI(2) variants: Double 7s, Cumulative RSI, R3, ConnorsRSI pullback (param `variant`)."
    default_params: dict[str, Any] = {
        "variant": "double_7s",  # one of VARIANTS; register each as its own trial
        "trend_ma": "sma_200",  # card: close > SMA(200) (all but crsi_pullback)
        "cum_rsi_entry": 35.0,  # Cumulative RSI: RSI2 + RSI2[t-1] < 35
        "cum_rsi_exit": 65.0,  # exit RSI2 > 65
        "r3_first_max": 60.0,  # R3: first day of the 3-day drop < 60
        "r3_entry": 10.0,  # today < 10
        "r3_exit": 70.0,  # exit RSI2 > 70
        "crsi_min_price": 5.0,  # ConnorsRSI pullback (Wealth-Lab coding): price > $5
        "crsi_min_avg_volume": 250_000.0,  # 21-day avg volume >= 250k (engine has avg_vol_20d)
        "crsi_adx_min": 30.0,  # ADX(10) > 30
        "crsi_low_drop": 0.04,  # W: low >= 4% below the prior close (coded 4)
        "crsi_close_pos_max": 0.25,  # X: close in the bottom 25% of the range (coded 25)
        "crsi_entry": 15.0,  # Y: ConnorsRSI < 15 (coded 15)
        "crsi_limit_pct": 0.04,  # Z: next-day limit 4% below the close (coded 4)
        "crsi_exit": 50.0,  # exit ConnorsRSI > 50 (coded 50)
        "max_hold_days": 10,  # card: max_hold_days 5-10 for all variants
        "stop_atr_mult": 2.0,  # card: catastrophic stop 2 x atr_14
        P_MIN_MARKET_TREND: TREND_DOWN,  # Connors gates on the instrument's own 200-day
        P_MIN_RR: 0.0,  # card: min_reward_risk 0 (rule exits)
    }
    features_required = ["rsi_2", "atr_14", "avg_vol_20d", "close_pos", "prev_close"]
    extra_features = [LOW_7, HIGH_7, CRSI, "adx_10"]

    def required_features(self) -> list[str]:
        return list(dict.fromkeys([*self.features_required, str(self.params["trend_ma"]), *self.extra_features]))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        p, v = self.params, str(self.params["variant"])
        if bars_held >= int(p["max_hold_days"]):
            return True
        if v == "double_7s":
            hi = row.get(HIGH_7)
            return finite(hi) and float(row["close"]) >= float(hi)
        if v == "crsi_pullback":
            crsi = row.get(CRSI)
            return finite(crsi) and float(crsi) > float(p["crsi_exit"])
        level = float(p["cum_rsi_exit"] if v == "cumulative_rsi" else p["r3_exit"])
        rsi = row.get("rsi_2")
        return finite(rsi) and float(rsi) > level

    def _setup(self, row: pd.Series, rsi: Any) -> bool:
        p, v, close = self.params, str(self.params["variant"]), float(row["close"])
        if v == "crsi_pullback":
            prev, crsi, cpos = row["prev_close"], row[CRSI], row["close_pos"]
            return (
                close > float(p["crsi_min_price"])
                and float(row["avg_vol_20d"]) >= float(p["crsi_min_avg_volume"])
                and float(row["adx_10"]) > float(p["crsi_adx_min"])
                and finite(prev) and float(row["low"]) <= float(prev) * (1.0 - float(p["crsi_low_drop"]))
                and finite(cpos) and float(cpos) <= float(p["crsi_close_pos_max"])
                and finite(crsi) and float(crsi) < float(p["crsi_entry"])
            )
        trend = row[str(p["trend_ma"])]
        if not (finite(trend) and close > float(trend)):
            return False
        if v == "double_7s":
            lo = row[LOW_7]
            return finite(lo) and close <= float(lo)
        if v == "cumulative_rsi":
            return finite(rsi[-1]) and finite(rsi[-2]) and rsi[-1] + rsi[-2] < float(p["cum_rsi_entry"])
        if v == "r3":
            r = rsi[-4:]
            return (len(r) == 4 and all(finite(x) for x in r) and r[0] > r[1] > r[2] > r[3]
                    and r[1] < float(p["r3_first_max"]) and r[3] < float(p["r3_entry"]))
        raise ValueError(f"{self.name}: unknown variant {v!r}; expected one of {VARIANTS}")

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p, v = self.params, str(self.params["variant"])
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            rsi = view.window(str(row[SYMBOL]), ["rsi_2"])["rsi_2"]
            atr = row["atr_14"]
            if len(rsi) < 4 or not finite(atr) or not self._setup(row, rsi):
                continue
            close = float(row["close"])
            limit = v == "crsi_pullback"
            entry = close * (1.0 - float(p["crsi_limit_pct"])) if limit else close
            sig = self.build_signal(
                row, as_of, entry=entry, stop=entry - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=-float(row[CRSI]) if limit else -float(rsi[-1]),
                features={"rsi_2": rsi[-1], CRSI: row[CRSI], "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"{v}: rsi_2 {rsi[-1]:.1f}" + (f", limit {entry:.2f}" if limit else ""),
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.LIMIT}) if limit else sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
