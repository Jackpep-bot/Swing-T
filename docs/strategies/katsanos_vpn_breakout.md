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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1479 | 5 | 51% | +0.02 | -0.06 | 50% | +0.01 | -0.06 | 56% | +0.14 | +0.06 | 1.50 |
| correction | 243 | 0 | 67% | +0.15 | -0.01 | 67% | +0.19 | +0.03 | 68% | +0.35 | +0.19 | 2.79 |
| healthy_uptrend | 3780 | 7 | 50% | +0.01 | -0.07 | 49% | +0.01 | -0.06 | 45% | +0.04 | -0.03 | 1.10 |
| high_vol_selloff | 573 | 1 | 53% | -0.04 | -0.13 | 51% | -0.07 | -0.17 | 44% | -0.12 | -0.22 | 0.75 |
| narrow_uptrend | 258 | 0 | 48% | -0.03 | -0.11 | 43% | -0.07 | -0.15 | 46% | -0.02 | -0.11 | 0.96 |
| **all** | 6333 | 13 | 51% | +0.01 | -0.07 | 50% | +0.01 | -0.07 | 48% | +0.06 | -0.02 | 1.16 |

Portfolio replay (net of costs, slots shared with its run): 46 trades, win 30%, avg -0.21R, PF 0.55, P&L $-4,384 on $100k, avg hold 19.2 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2728 | 5 | 51% | -0.00 | -0.07 | 52% | +0.02 | -0.04 | 49% | +0.07 | +0.00 | 1.18 |
| correction | 3241 | 7 | 55% | +0.03 | -0.04 | 57% | +0.10 | +0.02 | 57% | +0.12 | +0.04 | 1.39 |
| healthy_uptrend | 12630 | 20 | 51% | +0.01 | -0.06 | 52% | +0.03 | -0.04 | 49% | +0.04 | -0.03 | 1.10 |
| high_vol_selloff | 2921 | 4 | 53% | -0.01 | -0.09 | 53% | -0.00 | -0.08 | 52% | +0.06 | -0.02 | 1.17 |
| narrow_uptrend | 1846 | 6 | 50% | -0.00 | -0.08 | 51% | +0.03 | -0.05 | 50% | +0.06 | -0.02 | 1.16 |
| **all** | 23366 | 42 | 52% | +0.01 | -0.06 | 53% | +0.04 | -0.04 | 50% | +0.06 | -0.02 | 1.15 |

Portfolio replay (net of costs, slots shared with its run): 148 trades, win 47%, avg +0.21R, PF 1.59, P&L $24,985 on $100k, avg hold 24.9 bars.
