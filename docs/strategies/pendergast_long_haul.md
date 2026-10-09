---
slug: pendergast_long_haul
name: Long Haul (Donald Pendergast Jr.)
originators: [Donald Pendergast Jr. (S&C 2014 Bonus Issue), thinkorswim built-in strategy + Long Haul Filter]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 40]     # estimate ("weeks" per catalog)
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Long Haul (Pendergast)

## One-line summary
Long-only "dip then breakout": after RSI has been oversold without reaching overbought, buy the bar that closes above
several prior highs and above the slow MA; exit on a close below the fast MA or a 3-bar-low trailing stop.

## Origin and lineage
Donald Pendergast Jr., S&C 2014 Bonus Issue. thinkorswim ships the strategy and a Long Haul Filter (Stock Hacker scan)
implementing his stock-selection criteria. The filter's criteria are not documented on the TOS page (unverified).

## Exact rules (TOS documentation; defaults not published)
- Setup: RSI(len) fell below the oversold level and has not since risen above the overbought level.
- Entry: the bar closes above the highest high of the prior `high length` bars and above the slow MA. Next-open fill.
- Exit 1: close below the fast MA. Exit 2 (trailing): price drops below the lowest low of the last 3 bars.
- Inputs: fast length, slow length (slow >> fast), MA type, RSI length, oversold, overbought, RSI average type, high length.
  **No default values are published** (checked TOS page 2026-10-07). Catalog formula status: approximation.

## Why it should work
Buying the resumption of an uptrend after a washout: weak holders have sold at the oversold low, and the breakout above
recent highs shows demand has returned. The other side: sellers who bought the prior high and exit at breakeven.

## When it works and when it fails
Pullbacks within long-term uptrends. Fails when the oversold reading marks the start of a downtrend (slow MA filter only
partly guards against this) and in chop where the 3-bar-low stop is hit within days.

## Parameters and sensitivity
Engine assumptions (not from the source): RSI(14) oversold 30 / overbought 70, high length 5, fast MA SMA(10), slow MA
SMA(50). Each is a guess; replay a small grid (RSI os 25-35, high length 3-10) and report all of it, not the best cell.

## Evidence
In-sample S&C illustration only (grade D). No independent test found.

## Common mistakes
Requiring RSI to still be oversold at entry (it is the history since the last oversold that matters); letting the
setup age indefinitely.

## Discretionary parts and how to make them mechanical
Stock selection -> trend_state = 1 and the universe filter. Setup age -> cap at 30 bars since the oversold reading.

## Implementation spec for swing-engine
- Module `strategies/long_haul.py`, `@register("strategy")`.
- Reuses rsi_14, sma_10, sma_50, atr_14, trend_state. Compute in-module: bars_since_oversold, max RSI since then,
  prior_max_high_n (RollingSpec(high, max, n, prior=True)), lowest_low_3.
- Signal at close t: bars_since(rsi_14 < 30) <= 30, max(rsi_14 since then) < 70, close > prior_max_high_5, close > sma_50.
- Stop: lowest low of last 3 bars (must be < entry; else entry - 1.5 x atr_14). Target: None.
  Trailing: ratchet stop to lowest_low_3 each close. `should_exit`: close < sma_10.
- `max_hold_days`: 40. `min_reward_risk`: not applied.
- settings.yaml: `long_haul: {enabled: false, shadow_only: true}` with the assumed params listed explicitly.

## What the router should know
Close cousin of `pullback_trend` and `rsi2_meanrev` (dip in uptrend) but enters on strength; compare overlap in replay.

## Signs of decay to monitor
Median holding under 5 days (stop too tight for current volatility); win rate below 35%.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/LongHaul

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 191 | 1 | 54% | +0.05 | -0.09 | 48% | -0.06 | -0.19 | 45% | +0.13 | -0.01 | 1.25 |
| correction | 38 | 0 | 61% | +0.30 | -0.11 | 66% | +0.51 | +0.10 | 68% | +0.86 | +0.45 | 4.49 |
| healthy_uptrend | 378 | 2 | 46% | -0.06 | -0.21 | 43% | -0.12 | -0.27 | 35% | -0.07 | -0.22 | 0.88 |
| high_vol_selloff | 109 | 2 | 47% | -0.07 | -0.25 | 43% | -0.16 | -0.34 | 36% | -0.02 | -0.19 | 0.97 |
| narrow_uptrend | 33 | 0 | 61% | +0.08 | -0.03 | 55% | +0.05 | -0.06 | 55% | +0.30 | +0.19 | 1.80 |
| **all** | 749 | 5 | 49% | -0.01 | -0.17 | 46% | -0.07 | -0.23 | 40% | +0.05 | -0.11 | 1.09 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 263 | 4 | 59% | +0.14 | +0.01 | 60% | +0.28 | +0.15 | 56% | +0.48 | +0.35 | 2.23 |
| correction | 315 | 0 | 55% | +0.13 | -0.09 | 58% | +0.35 | +0.13 | 58% | +0.67 | +0.45 | 2.65 |
| healthy_uptrend | 1751 | 10 | 45% | -0.03 | -0.17 | 42% | -0.04 | -0.18 | 33% | -0.11 | -0.25 | 0.83 |
| high_vol_selloff | 769 | 3 | 49% | -0.03 | -0.17 | 49% | +0.06 | -0.09 | 45% | +0.12 | -0.02 | 1.25 |
| narrow_uptrend | 389 | 2 | 45% | -0.07 | -0.19 | 44% | -0.05 | -0.17 | 34% | -0.11 | -0.24 | 0.82 |
| **all** | 3487 | 19 | 48% | -0.01 | -0.15 | 47% | +0.04 | -0.10 | 40% | +0.05 | -0.09 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
