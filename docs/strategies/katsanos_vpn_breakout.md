---
slug: katsanos_vpn_breakout
name: VPN high-volume breakout (Markos Katsanos)
originators: [Markos Katsanos]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# VPN high-volume breakout (Katsanos)

## One-line summary
Buy when Katsanos' Volume Positive Negative (VPN) indicator crosses above +10 with rising average volume, RSI not
overbought and price above its average; exit when VPN falls below its average and price drops an ATR multiple off its
recent high close.

## Origin and lineage
Markos Katsanos, VPN indicator and strategy, *Technical Analysis of Stocks & Commodities*, April 2021 (catalog).
thinkorswim ships `VPNIndicator` and `VPNStrat`. Katsanos also authored the Volume Flow Indicator; VPN is a variant.

## Exact rules (thinkorswim description, read this run)
VPN:
1. Typical price TP = (high + low + close)/3. A bar's volume is positive if TP - TP[1] >= factor x ATR (factor 0.1),
   negative if TP - TP[1] <= -factor x ATR, ignored otherwise.
2. Sum positive volume VP and negative volume VN over `length` bars.
3. VPN = (VP - VN) / (total volume over `length`) x 100, then smoothed by EMA(`ema length`).
4. VPN Average = moving average of VPN over `average length`.
Buy (all true): VPN crosses above the critical value (+10); 50-bar momentum of average volume > 0; RSI(`rsi length`) <
90; close > its average. Sell (both true): VPN crosses below VPN Average; close < highest close(`highest length`) -
`num atrs` x ATR(`atr length`).
Defaults for length, ema length, average length, rsi length, volume average length, highest length, atr length and num
atrs are **not stated** on the reference pages; Katsanos' published values were not verified this run (commonly cited
length 30 and EMA 3 are unverified).

## Why it should work
Volume that arrives on bars with a meaningful typical-price gain is accumulation; a VPN above +10 means accumulation
volume exceeds distribution volume by 10% of total volume. Sellers are supply that has already been absorbed. The ATR
exit gives trades room while VPN stays positive.

## When it works and when it fails
Volume-led breakouts out of bases in a healthy market. Fails in low-volume drift rallies (VPN never crosses) and in
news gaps where volume is one-day.

## Parameters and sensitivity
Critical value 5-15; length 20-50; ATR exit multiple 2-4. Trap: many free inputs with unknown defaults; fix them once
from the article if obtained, otherwise choose (30, 3, 30, 14, 50, 20, 14, 3) as engine values and do not tune.

## Evidence
Practitioner in-sample (grade D); no broker statistics; no independent test.

## Common mistakes
Using close instead of typical price; omitting the 0.1 ATR dead band (turns VPN into OBV-like noise).

## Discretionary parts
None beyond the unknown defaults.

## Implementation spec for swing-engine
- New features: `tp` = (h+l+c)/3; `vpn_30` = EMA3(100 x (sum vol where dTP >= 0.1 x atr_14 - sum vol where
  dTP <= -0.1 x atr_14) / sum vol, 30 bars); `vpn_avg_30` = SMA30(vpn_30); `vol_mom_50` = `avg_vol_50d` - its value 50
  bars earlier (> 0 required). (ATR length for the dead band is unspecified; using `atr_14` is an engine choice.)
- Signal: `vpn_30` crosses above 10 and `vol_mom_50 > 0` and `rsi_14 < 90` and close > `sma_50`.
- Entry: next open. Initial stop = entry - 3 x `atr_14`. Exit rule (`should_exit`): `vpn_30 < vpn_avg_30` and
  close < max(close, 20) - 3 x `atr_14`. No fixed target, so `min_reward_risk: 0`; `max_hold_days: 40`.
- Reuses: `atr_14`, `rsi_14`, `avg_vol_50d`, `sma_50`, `should_exit` hook in `_base.py`.
- Missing: VPN indicator, `vol_mom_50`.

## What the router should know
Breakout family; healthy_uptrend only. Compare its volume gate with `breakout_52w`'s 1.5x volume gate.

## Signs of decay to monitor
Mean R of VPN crosses vs plain 52-week breakouts on the same dates.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/VPNStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/V-Z/VPNIndicator

## Empirical (replay)
_Pending: filled in from swing replay on real data._
