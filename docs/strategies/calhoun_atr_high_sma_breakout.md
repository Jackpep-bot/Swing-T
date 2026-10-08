---
slug: calhoun_atr_high_sma_breakout
name: ATR High / SMA breakouts (Ken Calhoun)
originators: [Ken Calhoun]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
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

# ATR High / SMA Breakouts (Calhoun)

## One-line summary
Volatility-expansion breakout: when ATR is at its 14-bar high and price is above its 100-day SMA, buy on a stop a
fixed offset above that bar's high.

## Origin and lineage
Ken Calhoun, "ATR Breakout Entries", *Technical Analysis of Stocks & Commodities*, May 2016 (catalog). thinkorswim
`ATRHighSMABreakoutsFilter` (Stock Hacker scan) and `ATRHighSMABreakoutsLE` (entry only). Follows his ADX Breakouts.

## Exact rules (thinkorswim description, defaults verified this run)
- Universe filter: price $15-$70, 90-day range >= $5, daily volume >= 1,000,000 (catalog).
- Trigger: ATR(`length` 14) at its highest over the lookback (14 bars per catalog) and close > SMA(close, 100).
- Entry: buy stop at the trigger bar's high + `offset` ($0.50).
- Optional filters (off by default): wide-range candle (trigger bar's range >= 1.5x the average range) and volume
  increase (volume > prior bar's volume).
- Exits: not part of the entry strategy.

## Why it should work
Range expansion in an uptrend marks new information or institutional demand; the buy stop requires follow-through.
Caveat: ATR at a 14-bar high also happens on large down bars, so the SMA filter is doing most of the directional work.

## When it works and when it fails
Works at the start of trending legs (expansion after contraction). Fails on climactic or news-driven bars that
reverse, and in high-volatility markets where ATR highs are everywhere.

## Parameters and sensitivity
ATR length 10-20; ATR-high lookback 10-20; SMA 50-200; offset 0.1-0.25 x `atr_14`; turn on both optional filters as
a second variant. Convert $15-$70 / $5 / 1M-share rules to the engine universe and a % range filter (90-day range
>= 20% of close, engine choice).

## Evidence
Practitioner in-sample (grade D); no broker statistics; no independent test located. Catalog note: worth one replay
against `breakout_52w`.

## Common mistakes
Triggering on down bars (add close > open or close_pos >= 0.5); dollar thresholds across price levels.

## Discretionary parts
Exit unspecified; use engine defaults.

## Implementation spec for swing-engine
- Features: `atr_14` exists; new `atr_high_14` = `atr_14 >= rolling max(atr_14, 14)`; new `sma_100` (only 10/20/50/200
  exist today); `range_pct`, `close_pos`, `rvol_day` exist; `wide_range` = (high - low) >= 1.5 x mean(high - low, 20)
  (averaging window not stated by tos; 20 is an engine choice).
- Signal: `atr_high_14` and close > `sma_100` and `close_pos >= 0.5`; variant B adds `wide_range` and volume >
  prior volume.
- Entry: buy stop at high + 0.15 x `atr_14`, valid 2 sessions. Stop = entry - 2 x `atr_14` (or trigger bar low,
  whichever is closer, min 1 ATR). Target 2R; `max_hold_days: 15`; `min_reward_risk: 2.0`.
- Missing: `sma_100`, `atr_high_14`, stop-entry hook.

## What the router should know
Breakout family; healthy_uptrend only; avoid when `market_vol_regime` = 2.

## Signs of decay to monitor
Same-day reversal rate of filled buy stops; mean R by `vol_regime`.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ATRHighSMABreakoutsLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/A-B/ATRHighSMABreakoutsFilter

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1569 | 701 | 46% | -0.04 | -0.08 | 45% | +0.06 | +0.02 | 42% | +0.12 | +0.09 | 1.20 |
| correction | 153 | 63 | 47% | +0.06 | +0.02 | 38% | -0.13 | -0.17 | 32% | -0.28 | -0.31 | 0.61 |
| healthy_uptrend | 6856 | 3115 | 48% | +0.04 | +0.00 | 44% | +0.05 | +0.01 | 40% | +0.05 | +0.01 | 1.07 |
| high_vol_selloff | 631 | 330 | 48% | -0.02 | -0.06 | 44% | -0.03 | -0.07 | 35% | -0.11 | -0.16 | 0.84 |
| narrow_uptrend | 576 | 291 | 38% | -0.21 | -0.25 | 34% | -0.23 | -0.27 | 32% | -0.20 | -0.24 | 0.74 |
| **all** | 9785 | 4500 | 47% | +0.01 | -0.03 | 44% | +0.03 | -0.01 | 40% | +0.03 | -0.01 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4600 | 2047 | 49% | +0.06 | +0.01 | 47% | +0.08 | +0.04 | 43% | +0.13 | +0.08 | 1.20 |
| correction | 2134 | 892 | 47% | -0.01 | -0.05 | 46% | +0.04 | +0.01 | 39% | -0.01 | -0.04 | 0.99 |
| healthy_uptrend | 18823 | 9013 | 46% | -0.04 | -0.08 | 40% | -0.07 | -0.12 | 36% | -0.09 | -0.13 | 0.87 |
| high_vol_selloff | 4873 | 2250 | 43% | -0.11 | -0.15 | 41% | -0.08 | -0.12 | 37% | -0.07 | -0.11 | 0.90 |
| narrow_uptrend | 3219 | 1426 | 45% | -0.07 | -0.11 | 42% | -0.04 | -0.09 | 39% | -0.01 | -0.06 | 0.98 |
| **all** | 33649 | 15628 | 46% | -0.04 | -0.08 | 42% | -0.04 | -0.08 | 38% | -0.04 | -0.08 | 0.94 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 0%, avg -1.01R, PF 0.00, P&L $-1,441 on $100k, avg hold 2.0 bars.
