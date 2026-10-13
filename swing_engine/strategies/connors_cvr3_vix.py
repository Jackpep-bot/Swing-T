"""CVR3 VIX market timing (long SPY): docs/strategies/connors_cvr3_vix.md, catalog `connors_cvr3_vix` (ChartSchool P34).

Rule (ChartSchool, long side only): buy SPY when, on the VIX daily bar, low > SMA(10), close >= 1.10 x SMA(10) and
close < open (all three on one bar, or each at least once within `window` bars). Exit when the VIX closes below the
PRIOR day's SMA(10), or after `max_hold_days` (2-4 in the source). No stop in the source; the engine adds the card's
catastrophic `entry - 3 x atr_14`. The short side (VIX high < SMA, close <= 0.90 x SMA, close > open) is dropped.

Data: the VIX columns joined onto every panel row by data.market_series (`swing ingest-vix`); without them the
strategy returns []. VIX is final at 16:15 ET and SPY closes at 16:00, so the engine fills at the next SPY open.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, _local_day, finite

NAME = "connors_cvr3_vix"
VIX_OHLC = ["vix_open", "vix_high", "vix_low", "vix_close"]


def _sma_col(params: dict[str, Any]) -> str:
    return f"vix_sma_{int(params['sma_bars'])}"


@register("strategy", NAME)
class ConnorsCvr3Vix(PanelStrategy):
    name = NAME
    description = "SPY: VIX bar above its 10-day SMA, close >= 10% above it, close < open; exit VIX < prior SMA."
    default_params: dict[str, Any] = {
        "symbols": ["SPY"],  # card: trade SPY only
        "sma_bars": 10,  # card: VIX 10-day SMA
        "stretch": 0.10,  # card: VIX close >= 1.10 x SMA(10) (PPO(1,10) >= 10)
        "window": 1,  # card: all three on one bar; 3 = the optional 3-day window rule
        "max_hold_days": 4,  # card: 2-4 day time exit (upper bound)
        "stop_atr_mult": 3.0,  # card: catastrophic entry - 3 x atr_14 (not in the source)
        P_MIN_MARKET_TREND: TREND_DOWN,  # fires in selloffs by design (card: "What the router should know")
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    extra_features = [_sma_col(default_params), f"prev_{_sma_col(default_params)}"]
    engine_trail = False  # card: the VIX exit and the time stop are the exits

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        sma = _sma_col(self.params)
        self.extra_features = [sma, f"prev_{sma}"]

    def should_exit(self, row: pd.Series, bars_held: int, position: Any = None) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        close, prev_sma = row.get("vix_close"), row.get(f"prev_{_sma_col(self.params)}")
        return finite(close) and finite(prev_sma) and float(close) < float(prev_sma)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime) or not set(VIX_OHLC) <= set(panel.columns):
            return []
        sma = _sma_col(self.params)
        window = int(self.params["window"])
        hist = panel.loc[panel[SYMBOL].isin(list(self.params["symbols"]))]
        rows = self.rows_as_of(hist, as_of, required=[*self.features_required, *VIX_OHLC, sma])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            sub = hist.loc[hist[SYMBOL] == row[SYMBOL]]
            bars = sub.loc[_local_day(sub["ts"]) <= pd.Timestamp(as_of)].sort_values("ts").tail(window)
            if len(bars) < window or not bars[[*VIX_OHLC, sma]].notna().all(axis=None) or not finite(row["atr_14"]):
                continue
            above = (bars["vix_low"] > bars[sma]).any()
            stretched = (bars["vix_close"] >= (1.0 + float(self.params["stretch"])) * bars[sma]).any()
            black = (bars["vix_close"] < bars["vix_open"]).any()
            if not (above and stretched and black):
                continue
            close, vix, avg = float(row["close"]), float(row["vix_close"]), float(row[sma])
            ppo = vix / avg - 1.0
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(row["atr_14"]),
                target=None, score=ppo,
                features={"vix_close": vix, sma: avg, "vix_ppo": ppo, "atr_14": row["atr_14"],
                          "max_hold_days": self.params["max_hold_days"]},
                notes=f"CVR3: VIX {vix:.2f} is {ppo * 100:.1f}% above its {sma} {avg:.2f}, closed below its open",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
