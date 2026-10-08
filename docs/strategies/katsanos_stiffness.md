---
slug: katsanos_stiffness
name: Stiffness indicator strategy (Katsanos)
originators: [Markos Katsanos (S&C Nov 2018), thinkorswim StiffnessStrat]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [10, 84]    # 84-bar time exit is the documented cap
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

# Stiffness (Katsanos)

## One-line summary
Trend-quality entry: buy when the share of the last 60 closes that sat above a volatility-adjusted 100-day SMA rises
through 90% while the market index trend is up; exit when it falls below 50% or after 84 bars.

## Origin and lineage
Markos Katsanos, "stiffness" article, S&C Nov 2018 (Traders' Tips same issue); thinkorswim Stiffness study and
StiffnessStrat. Katsanos backtested it on a basket of S&P 500 stocks (results not retrieved: traders.com returned 403).

## Exact rules
- Stiffness = 100 x (number of bars in the last `length` where close > threshold) / `length`, threshold built from
  SMA(close, 100) and `num dev` x StDev(close, 100) with num dev = 0.2. Defaults from the Traders' Tips TradeStation code
  (via search snippet): MA length 100, stiffness length 60, 0.2 SD; TradingView port adds a 3-bar smoothing of the result.
- **Sign of the 0.2 SD offset is ambiguous**: TOS says close must exceed the MA *by* the threshold (MA + 0.2 SD); other
  descriptions read as a tolerance below the MA. Unverified; default to TOS (MA + 0.2 SD) and flag.
- Market filter: an EMA of the market index rose over the last 2 bars (EMA length not published on TOS; unverified).
- Entry: Stiffness crosses above 90 (entry level). Next-open fill.
- Exit: Stiffness < 50, or 84 bars after entry. No initial stop, target or sizing in the TOS version.

## Why it should work
A stock that rarely closes below its long average has persistent buying (institutional accumulation, momentum). Entering when
the count first reaches 90% buys an established, low-noise trend; the other side is value sellers and short-term faders.

## When it works and when it fails
Smooth bull markets with leadership persistence (2017, 2019-2021, 2023-2024). Fails at trend exhaustion: by definition the
signal arrives late, and the 50% exit gives back a large part of the move after a reversal.

## Parameters and sensitivity
Stiffness length 40-100, MA 50-200, SD 0-0.5, entry 80-95, exit 40-60, max hold 40-120. The 90/50 levels are coarse
(steps of 1/60 = 1.67 points); smoothing changes trade timing by days.

## Evidence
In-sample S&C illustration only (grade D). Conceptually related to the documented time-series and cross-sectional
momentum literature and to 52-week-high proximity, but no independent test of the indicator was found.

## Common mistakes
Survivorship-biased S&P 500 basket (current members); using an index EMA of the same day's close for a same-day fill.

## Discretionary parts and how to make them mechanical
None beyond the ambiguous offset sign and the market EMA length (engine assumption: SPY EMA(100)).

## Implementation spec for swing-engine
- Module `strategies/stiffness.py`, `@register("strategy")`; new feature `stiffness_60` (add to features with a shift test).
- Formula: thr = sma(close,100) + 0.2 x rolling_std(close,100); above = close > thr; stiffness_60 = 100 x rolling_mean(above, 60);
  optional smoothing EMA(3) as param `smooth`.
- Market: `market_ema_100` rising over 2 bars (compute from the SPY frame; only market_trend_state exists today).
- Signal: stiffness crosses above 90 at close t; entry next open.
- Stop: entry - 3 x atr_14 (engine-required; long holds need room). Target: None. `should_exit`: stiffness < 50.
  `max_hold_days`: 84. `min_reward_risk`: not applied.
- Reuses sma_200 for comparison, atr_14, trend_state, high_52w. Compare against trend_state=1 entries in replay.
- settings.yaml: `stiffness: {enabled: false, shadow_only: true, length: 60, ma: 100, num_dev: 0.2, entry: 90, exit: 50}`.

## What the router should know
A trend-quality score; even if the strategy is weak, `stiffness_60` may be useful as a ranking feature for trend setups.

## Signs of decay to monitor
Win rate of 84-bar exits falling; entries clustering at market tops (signal late).

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/StiffnessStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/Stiffness
- https://www.traders.com/Documentation/FEEDbk_docs/2018/11/TradersTips.html
- https://www.tradingview.com/script/WhX4cCcF-Stiffness-Index

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 243 | 1 | 47% | -0.01 | -0.08 | 51% | -0.03 | -0.10 | 35% | -0.20 | -0.27 | 0.63 |
| healthy_uptrend | 1827 | 8 | 49% | -0.00 | -0.08 | 49% | +0.03 | -0.04 | 45% | +0.02 | -0.06 | 1.04 |
| high_vol_selloff | 46 | 0 | 61% | +0.08 | -0.02 | 50% | -0.02 | -0.12 | 52% | +0.04 | -0.05 | 1.15 |
| narrow_uptrend | 137 | 0 | 41% | -0.08 | -0.16 | 42% | -0.12 | -0.19 | 44% | +0.09 | +0.01 | 1.17 |
| **all** | 2253 | 9 | 49% | -0.01 | -0.09 | 49% | +0.02 | -0.06 | 44% | -0.00 | -0.08 | 1.00 |

Portfolio replay (net of costs, slots shared with its run): 76 trades, win 30%, avg -0.06R, PF 0.91, P&L $-1,578 on $100k, avg hold 41.3 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1036 | 0 | 60% | +0.10 | +0.02 | 61% | +0.16 | +0.09 | 53% | +0.15 | +0.07 | 1.43 |
| correction | 113 | 0 | 40% | -0.07 | -0.14 | 50% | -0.01 | -0.07 | 49% | +0.03 | -0.03 | 1.09 |
| healthy_uptrend | 5599 | 8 | 51% | +0.01 | -0.07 | 53% | +0.05 | -0.03 | 50% | +0.09 | +0.01 | 1.22 |
| high_vol_selloff | 178 | 0 | 51% | +0.06 | -0.01 | 57% | +0.02 | -0.04 | 46% | +0.04 | -0.02 | 1.11 |
| narrow_uptrend | 1061 | 0 | 51% | -0.00 | -0.08 | 48% | -0.02 | -0.09 | 47% | +0.00 | -0.07 | 1.00 |
| **all** | 7987 | 8 | 52% | +0.02 | -0.06 | 53% | +0.05 | -0.02 | 50% | +0.08 | +0.01 | 1.21 |

Portfolio replay (net of costs, slots shared with its run): 238 trades, win 36%, avg +0.24R, PF 1.39, P&L $40,787 on $100k, avg hold 47.5 bars.
