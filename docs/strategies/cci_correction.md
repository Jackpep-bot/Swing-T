---
slug: cci_correction
name: CCI Correction (weekly CCI bias, daily CCI dip and recovery)
originators: [Donald Lambert (CCI, 1980); StockCharts ChartSchool (strategy write-up)]
category: pullback
decision: implement_disabled_for_comparison
holding_period_days: [5, 30]
timeframe: weekly bias + daily signal
direction: long (bearish-bias short mirror; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# CCI Correction

## One-line summary
Once weekly CCI(26) has pushed above +100 (bullish bias), buy when daily CCI dips below -100 and then crosses back above 0.
It is a trend pullback entry timed by an oscillator.

## Origin and lineage
Donald Lambert introduced the Commodity Channel Index in *Commodities* magazine (1980). StockCharts ChartSchool
(Arthur Hill) wrote up "CCI Correction" as a two-timeframe strategy. ChartSchool notes that by construction about 70-80% of CCI values
fall between +/-100, so extremes occur 20-30% of the time.

## Exact rules
- **CCI:** TP = (H+L+C)/3. CCI_n = (TP - SMA_n(TP)) / (0.015 * mean absolute deviation of TP over n).
- **Bias:** weekly CCI(26) crosses above +100 sets the bias to bullish. It stays bullish until weekly CCI(26) crosses below -100
  (bearish). The daily alternative for the bias is CCI(100).
- **Setup (bullish bias):** daily CCI (26, or 20) closes below -100.
- **Trigger:** daily CCI then closes back above 0. Buy (next open in a daily system).
- **Stops and targets:** left to the trader. ChartSchool says disciplined stops and profit-taking are required but gives none.
- Bearish mirror: in a bearish bias, a daily CCI move above +100 and then back below 0 is a sell or short signal.

## Why it should work
It buys a correction within an established trend, so trend followers re-entering and momentum continuation are on the
buyer's side. Waiting for CCI to recover to 0 means the pullback has already turned, at the cost of a later entry.

## When it works and when it fails
It works in persistent trends with orderly pullbacks. It fails in late-trend tops: the bias is sticky (it needs -100 weekly to flip)
and keeps signalling longs into a top. ChartSchool's 2008-2010 S&P 500 examples were mixed, including a failed Feb 2008 signal.
In chop the daily CCI whipsaws through 0.

## Parameters and sensitivity
- Weekly bias length (26 weeks) or daily CCI(100), signal CCI 20 or 26, thresholds +/-100 and the 0 re-cross.
  Changing the re-cross from 0 to -100 makes the entry earlier and noisier.
- Overfitting trap: two lengths, three thresholds and an unspecified exit. Fix the exit a priori.

## Evidence
Practitioner illustration only. No published statistics (catalog grade D), and no independent or academic test of this rule was found.

## Common mistakes
Leaving the exit unspecified (it turns into a discretionary hold). Recomputing the weekly bias with the
current, incomplete week. Point-in-time rule: use only completed weeks as of `as_of`.

## Discretionary parts and how to make them mechanical
- Exit, as proposed for testing: daily CCI crosses above +100 and then back below +100 (take profit), or a close below the setup's lowest
  low (stop), or 20-day time stop.
- Stop: lowest low between the -100 dip and the trigger, minus 0.1*atr_14.

## Implementation spec for swing-engine
- New features: `cci_20` (catalog item `cci_indicator`, "implement"), `cci_26`, and a weekly `cci_26w` built from
  week-ending Friday bars (completed weeks only, forward-filled to daily rows).
- State: `cci_bias` in {+1, -1, 0} with hysteresis (+100 / -100 crosses on `cci_26w`); daily `cci_dip_seen` = min(cci_26 over the
  last 10 bars) < -100.
- Entry: `cci_bias == 1 and cci_dip_seen and cci_26[t-1] <= 0 < cci_26[t]`, filled at the next open.
- Stop: as above. Target: none (rule exit). `max_hold_days` 20. `min_reward_risk` 0 (rule exit), or 1.5 if a fixed
  2R target variant is tested.
- Reuses `atr_14`, `trend_state` (optional confirm). Missing: CCI features and weekly resampling helper.

## What the router should know
It is a pullback-in-trend setup, the same family as `pullback_trend` and `pullback_holy_grail`. Allow it only when the market trend is up.
Signals cluster after broad pullbacks, so cap them per sector.

## Signs of decay to monitor
A falling share of signals that reach a new 20-day high within 10 bars, and a rising share stopped within 3 bars.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/cci-correction

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 804 | 0 | 58% | +0.10 | +0.05 | 54% | +0.10 | +0.06 | 50% | +0.13 | +0.08 | 1.34 |
| correction | 91 | 0 | 42% | -0.15 | -0.18 | 55% | +0.07 | +0.04 | 57% | +0.25 | +0.21 | 1.66 |
| healthy_uptrend | 4454 | 9 | 47% | -0.00 | -0.04 | 45% | -0.02 | -0.06 | 43% | +0.03 | -0.01 | 1.07 |
| high_vol_selloff | 713 | 2 | 69% | +0.29 | +0.26 | 62% | +0.30 | +0.27 | 48% | +0.20 | +0.17 | 1.43 |
| narrow_uptrend | 484 | 1 | 41% | -0.14 | -0.18 | 46% | -0.06 | -0.10 | 36% | -0.13 | -0.17 | 0.76 |
| **all** | 6546 | 12 | 50% | +0.03 | -0.01 | 48% | +0.03 | -0.01 | 44% | +0.06 | +0.02 | 1.12 |

Portfolio replay (net of costs, slots shared with its run): 379 trades, win 44%, avg -0.08R, PF 0.78, P&L $-21,310 on $100k, avg hold 9.1 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3736 | 8 | 55% | +0.08 | +0.05 | 56% | +0.16 | +0.13 | 54% | +0.27 | +0.24 | 1.68 |
| correction | 1055 | 1 | 57% | +0.09 | +0.06 | 54% | +0.09 | +0.06 | 53% | +0.25 | +0.23 | 1.68 |
| healthy_uptrend | 12620 | 23 | 50% | +0.01 | -0.02 | 49% | +0.02 | -0.01 | 47% | +0.08 | +0.04 | 1.17 |
| high_vol_selloff | 2134 | 4 | 50% | +0.01 | -0.02 | 50% | +0.00 | -0.03 | 48% | +0.05 | +0.02 | 1.11 |
| narrow_uptrend | 3614 | 4 | 48% | -0.01 | -0.04 | 51% | +0.04 | +0.01 | 46% | +0.04 | +0.00 | 1.08 |
| **all** | 23159 | 40 | 51% | +0.02 | -0.01 | 51% | +0.05 | +0.02 | 48% | +0.11 | +0.07 | 1.25 |

Portfolio replay (net of costs, slots shared with its run): 1291 trades, win 51%, avg +0.04R, PF 1.12, P&L $39,228 on $100k, avg hold 9.4 bars.
