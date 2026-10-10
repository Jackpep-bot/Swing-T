---
slug: hudgin_golden_triangle
name: Golden Triangle (Charlotte Hudgin)
originators: [Charlotte Hudgin]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [5, 30]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Golden Triangle (Hudgin)

## One-line summary
Buy-the-dip variant: a stock accelerating above its 50-day SMA pivots, falls below the SMA, then reclaims a short
confirmation SMA on the highest volume of recent days.

## Origin and lineage
Charlotte Hudgin, "Finding The Golden Triangle", *Technical Analysis of Stocks & Commodities* V.32:9 (Sept 2014),
pp. 24-27, 36. Implemented as thinkorswim GoldenTriangleLE and in that month's Traders' Tips (eSignal, TradingView
ports). Overlaps the pullback family (`pullback_trend`, `pullback_holy_grail`), with a volume-confirmed reclaim.

## Exact rules (thinkorswim GoldenTriangleLE)
Inputs: `average length` (long SMA for price and volume, default 50), `confirmation length` (short price SMA,
default not stated on the page), `volume length` (look-back for highest-volume test, default not stated).
1. Initial uptrend: price rising faster than its 50 SMA (price above and pulling away from it).
2. Pivot: a high where price turns into a short-term downtrend.
3. Price drop: after the pivot, price falls below the 50 SMA and stays below for the whole drop (setup complete).
4. Price confirmation: a close above the confirmation SMA.
5. Volume confirmation: volume is the highest of the last `volume length` bars and above its 50-bar SMA, on the
   price-confirmation day or a later day that closes above the prior close.
6. Buy (next bar). No stop, target or exit in the tos script. A search summary of the Traders' Tips code mentions a
   "20 days of white space" parameter and a "days to compare volume" parameter of 0; not verified.

## Why it should work
Momentum names that shake out below the 50-day trap late sellers; a high-volume reclaim signals institutional
demand returning. Counterparty: holders who sell the break of the 50-day and short-term trend followers.

## When it works and when it fails
Works when the market is still uptrending and the dip is stock-specific or a brief market shake. Fails when the
drop below the 50 SMA is the start of a market correction (no rebound to the prior acceleration).

## Parameters and sensitivity
| Knob | Default | Range | Trap |
|---|---|---|---|
| long SMA | 50 | 40-60 | |
| confirmation SMA | unverified | 5-20 | biggest driver of signal timing |
| volume look-back | unverified | 5-10 | |
| min "acceleration" | undefined | close/sma_50 - 1 >= 5-15% at the pivot | must be fixed before replay |
| max drop below SMA | undefined | 0-15% | deep drops are broken trends |

## Evidence
Only the author's in-sample illustrations in the magazine (catalog grade D); broker publishes no statistics.
No independent test found.

## Common mistakes
Buying the first close above the confirmation SMA without the volume test; buying names whose 50 SMA has rolled over.

## Discretionary parts and how to make them mechanical
- "Rising faster than its SMA": `close / sma_50 - 1 >= accel_min` (0.10) at the pivot and `sma_50` slope > 0.
- Pivot: highest high of the 20 bars before the first close below `sma_50` (or a confirmed `pivot_highs` from
  features/levels.py, width 5).
- "Stays below throughout the drop": every close from the first close below `sma_50` to the drop low is below `sma_50`.

## Implementation spec for swing-engine
- Reuse: `sma_10`, `sma_20`, `sma_50`, `avg_vol_50d`, `pivot_highs` (levels.py), `atr_14`, `trend_state`.
- Missing: `sma_slope_50` (sma_50 vs 10 bars earlier); a stateful lookback helper (pivot -> drop -> reclaim within
  `max_setup_bars = 30`).
- Trigger on bar t: setup complete, `close_t > sma_{conf}` (conf = 10 default), and `volume_t == max(volume over 5
  bars)` and `volume_t > avg_vol_50d`. Entry = next open.
- Stop = drop low (lowest low since the pivot) - 0.25 x atr_14. Target = pivot high (prior swing high, as
  `pullback_holy_grail` does). `max_hold_days = 20`; rule exit on close < drop low. `min_reward_risk = 1.5`.
- New module `strategies/golden_triangle.py`.

## What the router should know
Pullback family; same regime treatment as `pullback_holy_grail` if ever enabled. Disabled for comparison.

## Signs of decay to monitor
Fraction of trades that reach the pivot high before the stop; drop depth of winners vs losers drifting.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GoldenTriangleLE
- https://store.traders.com/stcov32236fi.html
- https://www.traders.com/Documentation/FEEDbk_docs/2014/09/TradersTips.html

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 83 | 1 | 47% | +0.07 | -0.04 | 42% | +0.01 | -0.10 | 39% | -0.06 | -0.17 | 0.90 |
| correction | 11 | 0 | 36% | -0.18 | -0.35 | 45% | +0.06 | -0.11 | 55% | +0.38 | +0.21 | 1.91 |
| healthy_uptrend | 260 | 4 | 48% | -0.01 | -0.12 | 37% | -0.13 | -0.24 | 33% | -0.14 | -0.25 | 0.78 |
| high_vol_selloff | 127 | 0 | 59% | +0.15 | +0.03 | 57% | +0.27 | +0.15 | 46% | +0.17 | +0.05 | 1.33 |
| narrow_uptrend | 62 | 0 | 39% | -0.18 | -0.29 | 36% | -0.16 | -0.26 | 37% | +0.01 | -0.10 | 1.02 |
| **all** | 543 | 5 | 49% | +0.02 | -0.10 | 42% | -0.01 | -0.13 | 38% | -0.03 | -0.14 | 0.96 |

Portfolio replay (net of costs, slots shared with its run): 5 trades, win 0%, avg -0.77R, PF 0.00, P&L $-2,368 on $100k, avg hold 7.8 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 374 | 6 | 55% | +0.13 | +0.04 | 55% | +0.20 | +0.11 | 51% | +0.25 | +0.16 | 1.58 |
| correction | 193 | 0 | 62% | +0.32 | +0.23 | 52% | +0.14 | +0.05 | 54% | +0.47 | +0.38 | 2.06 |
| healthy_uptrend | 1016 | 18 | 43% | -0.05 | -0.16 | 44% | -0.03 | -0.14 | 40% | -0.01 | -0.13 | 0.98 |
| high_vol_selloff | 263 | 5 | 44% | -0.09 | -0.19 | 41% | -0.11 | -0.21 | 37% | -0.05 | -0.15 | 0.91 |
| narrow_uptrend | 358 | 4 | 48% | -0.02 | -0.13 | 49% | +0.03 | -0.08 | 50% | +0.17 | +0.05 | 1.38 |
| **all** | 2204 | 33 | 48% | +0.01 | -0.09 | 47% | +0.03 | -0.08 | 44% | +0.10 | -0.01 | 1.20 |

Portfolio replay (net of costs, slots shared with its run): 45 trades, win 16%, avg -0.58R, PF 0.27, P&L $-15,878 on $100k, avg hold 9.5 bars.
