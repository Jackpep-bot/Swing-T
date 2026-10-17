"""Ken Calhoun ATR High / SMA Breakouts (long), docs/strategies/calhoun_atr_high_sma_breakout.md (catalog B8).

Trigger at the close: atr_14 at its 14-bar high (`atr_high_14`), close > sma_100 and close_pos >= 0.5; universe filter
price $15-$70, 20-day average volume >= 1M, 90-day range >= 20% of the close (the card's conversion of its $5 range
rule). Variant B (`require_wide_range`, `require_volume_up`): wide-range candle and volume above the prior bar's.
Entry: buy stop at the trigger high + 0.15 x atr_14 (card's ATR form of tos's +$0.50), valid one session (the card
asks for two; the engine expires stop orders after one). Stop = the trigger-bar low or entry - 2 x atr_14, whichever
is closer, but at least 1 ATR below entry. Target 2R, 15-session time stop (card).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "calhoun_atr_high_sma_breakout"
ATR_HIGH, SMA, HIGH90, LOW90, WIDE = "atr_high_14", "sma_100", "high_90", "low_90", "wide_range_bar"


@register("strategy", NAME)
class CalhounAtrHighSmaBreakout(PanelStrategy):
    name = NAME
    description = "ATR(14) at its 14-bar high and close > SMA(100); buy stop over the high, 2 ATR stop, 2R target."
    default_params: dict[str, Any] = {
        "min_close_pos": 0.5,  # card signal: close_pos >= 0.5
        "min_price": 15.0,  # catalog universe filter: price $15-$70 (None = off)
        "max_price": 70.0,
        "min_avg_volume": 1_000_000.0,  # catalog: daily volume >= 1,000,000 (avg_vol_20d)
        "min_range_90_pct": 0.20,  # card: 90-day range >= 20% of close (engine conversion of the $5 rule)
        "require_wide_range": False,  # card variant B (tos optional filters, off by default)
        "require_volume_up": False,
        "entry_offset_atr": 0.15,  # card: buy stop at high + 0.15 x atr_14
        "stop_atr_mult": 2.0,  # card: stop = entry - 2 x atr_14 or the trigger low, whichever is closer ...
        "min_stop_atr": 1.0,  # ... min 1 ATR
        "target_r": 2.0,  # card: target 2R
        "max_hold_days": 15,  # card: max_hold_days 15
        P_MIN_TREND: TREND_DOWN,  # the SMA(100) test is the trend filter
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card: min_reward_risk 2.0
    }
    features_required = ["atr_14", "close_pos", "avg_vol_20d", "trend_state"]
    extra_features = [ATR_HIGH, SMA, HIGH90, LOW90, WIDE]

    def _universe_ok(self, row) -> bool:
        p, close = self.params, float(row["close"])
        if p["min_price"] is not None and close < float(p["min_price"]):
            return False
        if p["max_price"] is not None and close > float(p["max_price"]):
            return False
        if p["min_avg_volume"] is not None and not row["avg_vol_20d"] >= float(p["min_avg_volume"]):
            return False
        rng = (row[HIGH90] - row[LOW90]) / close
        return p["min_range_90_pct"] is None or rng >= float(p["min_range_90_pct"])

    def signals(self, panel, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        p = self.params
        keep = ((rows[ATR_HIGH] == 1) & (rows["close"] > rows[SMA]) & (rows["close_pos"] >= float(p["min_close_pos"])))
        if p["require_wide_range"]:
            keep &= rows[WIDE] == 1
        if p["require_volume_up"]:
            keep &= rows["volume"] > rows["prior_volume"]
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            atr = float(row["atr_14"])
            if not finite(atr) or not self.trend_ok(row) or not self._universe_ok(row):
                continue
            entry = float(row["high"]) + float(p["entry_offset_atr"]) * atr
            stop = min(max(float(row["low"]), entry - float(p["stop_atr_mult"]) * atr), entry - float(p["min_stop_atr"]) * atr)
            sig = self.build_signal(row, as_of, entry=entry, stop=stop, target=entry + float(p["target_r"]) * (entry - stop),
                                    score=float(row["close_pos"]),
                                    features={"atr_14": atr, SMA: row[SMA], "max_hold_days": p["max_hold_days"]},
                                    notes=f"ATR at its 14-bar high, close {row['close']:.2f} > SMA100 {row[SMA]:.2f}; "
                                    f"buy stop {entry:.2f}")
            sig = c1.stop_entry(sig)
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
