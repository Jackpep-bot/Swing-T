"""Katsanos VPN high-volume breakout (long), docs/strategies/katsanos_vpn_breakout.md (catalog B15, thinkorswim
VPNStrat).

Buy when all hold: VPN(30) crosses above +10; the 50-bar momentum of average volume is positive (avg_vol_50d above
its value 50 bars earlier); rsi_14 < 90; close > sma_50. Exit when VPN is below its 30-bar average AND the close is
below the 20-bar highest close - 3 x atr_14. The tos page gives no default lengths; the card's engine values
(30, EMA 3, 30, 14, 50, 20, 14, 3) are used untuned (`features.extra` `vpn_<n>`). Initial stop = entry - 3 x atr_14,
no target, 40-session cap.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "katsanos_vpn_breakout"


@register("strategy", NAME)
class KatsanosVpnBreakout(PanelStrategy):
    name = NAME
    description = "VPN30 crosses above 10, rising 50-bar volume average, rsi_14 < 90, close > sma_50; 3 ATR stop."
    default_params: dict[str, Any] = {
        "vpn_len": 30,  # card engine value (tos default unstated)
        "vpn_avg_len": 30,  # card engine value: VPN average length
        "critical": 10.0,  # card / tos: VPN crosses above +10
        "vol_mom_bars": 50,  # card / tos: 50-bar momentum of average volume > 0
        "rsi_max": 90.0,  # card / tos: RSI < 90
        "trend_ma": "sma_50",  # card: close above its average
        "highest_len": 20,  # card engine value: exit reference = highest close of 20 bars
        "exit_atr_mult": 3.0,  # card engine value: num_atrs 3
        "stop_atr_mult": 3.0,  # card: initial stop = entry - 3 x atr_14
        "max_hold_days": 40,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no fixed target
    }
    features_required = ["atr_14", "rsi_14", "avg_vol_50d", "sma_50"]
    extra_features = ["vpn_30", "prev_vpn_30", "sma_30_of_vpn_30", "max_20_of_close"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        n, a, h = (int(self.params[k]) for k in ("vpn_len", "vpn_avg_len", "highest_len"))
        self.extra_features = [f"vpn_{n}", f"prev_vpn_{n}", f"sma_{a}_of_vpn_{n}", f"max_{h}_of_close"]

    def required_features(self) -> list[str]:
        return list(dict.fromkeys([*super().required_features(), str(self.params["trend_ma"])]))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        vpn_col, _, avg_col, max_col = self.extra_features
        vpn, avg, top, atr = row.get(vpn_col), row.get(avg_col), row.get(max_col), row.get("atr_14")
        if not all(finite(x) for x in (vpn, avg, top, atr)):
            return False
        return float(vpn) < float(avg) and float(row["close"]) < float(top) - float(self.params["exit_atr_mult"]) * float(atr)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        vpn_col, prev_col = self.extra_features[:2]
        trend_col, k = str(p["trend_ma"]), int(p["vol_mom_bars"])
        view = as_of_view(panel, as_of, ["close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            vpn, prev, rsi, ma, atr = row[vpn_col], row[prev_col], row["rsi_14"], row[trend_col], row["atr_14"]
            if not all(finite(x) for x in (vpn, prev, rsi, ma, atr)):
                continue
            close = float(row["close"])
            if not (float(prev) <= float(p["critical"]) < float(vpn) and float(rsi) < float(p["rsi_max"]) and close > float(ma)):
                continue
            avg_vol = view.window(str(row[SYMBOL]), ("avg_vol_50d",))["avg_vol_50d"]
            if len(avg_vol) <= k or not (finite(avg_vol[-1 - k]) and avg_vol[-1] > avg_vol[-1 - k]):
                continue
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=close - float(p["stop_atr_mult"]) * float(atr),
                target=None,
                score=float(vpn),
                features={vpn_col: vpn, "rsi_14": rsi, "atr_14": atr, "vol_mom": avg_vol[-1] - avg_vol[-1 - k],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"VPN {float(prev):.1f} -> {float(vpn):.1f} through {float(p['critical']):g}, rsi {float(rsi):.0f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
