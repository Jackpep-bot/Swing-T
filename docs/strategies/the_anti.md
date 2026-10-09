---
slug: the_anti
name: The Anti (stochastic hook pullback; Raschke, Grimes)
originators: [Linda Bradford Raschke, Adam Grimes (restatement)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 4]
timeframe: daily
direction: long   # sells mirror; engine is long-only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# The Anti

## One-line summary
In a trend shown by a rising slow stochastic line, wait for the fast line to pull back for a few bars, then buy when it
hooks back up: a short pullback-continuation trade held 2-4 bars.

## Origin and lineage
Linda Raschke (*Street Smarts*; later LBR course material). Adam Grimes uses an "Anti" pullback in his teaching
(*The Art and Science of Technical Analysis*) and reports that moving-average touches alone are random; the edge he
claims is trend plus trigger (`docs/methods.md` 1b, grade C for that statement).

## Exact rules (long)
- Stochastic: %K period 7, %K smoothing 4, %D 10 (*Street Smarts*; the later manual uses %D 12).
- Setup: %D has been rising (roughly 4+ bars); %K has pulled back toward / against %D for about 3+ bars.
- Trigger: %K hooks back up in the direction of %D; buy stop above the hook bar's high.
- Stop: below the entry bar low or the last swing low. Exit: within 2-4 bars.
- Bar counts (4 and 3) come from forum restatements, not the book (catalog flag); formula status "approximation".

## Why it should work
The slow line is a trend proxy; the fast line's counter-move is a minor pullback whose failure re-engages trend
followers. It is a momentum-continuation entry with a tight, nearby stop.

## When it works and when it fails
Trending tape with orderly pullbacks. Fails in chop (the slow line flips often, many whipsaws) and in sharp sell-offs.

## Parameters and sensitivity
Stochastic (7, 4, 10/12), bar counts 3-4, hold 2-4 bars. Stochastic parameter grids are a classic overfit; fix the
book values and test %D 10 vs 12 only.

## Evidence
No independent test located. Indirect support only: QuantifiedStrategies' SPY stochastic-pullback test (29 Jul 2026;
195 trades, 74% wins, PF 2.3; parameters paywalled) cited in `docs/methods/01`; that is an index pullback, not this rule.

## Common mistakes
Buying the hook without a stop-entry trigger; ignoring the price trend (stochastic slope alone is not a trend filter).

## Discretionary parts and how to make them mechanical
"%D established an uptrend" = `slowD_t > slowD_{t-4}` and `slowD` rising on 3 of last 4 bars. "%K pulled back" =
`slowK` falling on at least 3 of the last 4 bars before t, with `slowK_{t-1} <= slowD_{t-1} + 5`. "Hook" =
`slowK_t > slowK_{t-1}`. Add a price trend gate `trend_state == 1` (engine choice).

## Implementation spec for swing-engine
- New features: `fastK7 = 100 * (close - min(low,7)) / (max(high,7) - min(low,7))`; `slowK = SMA4(fastK7)`;
  `slowD = SMA10(slowK)` (also `slowD12`). Catalog maps this to a new `stochastic_oscillator` in `features/indicators.py`.
- Reuses: `trend_state`, `atr_14`, `support_1` (last swing low proxy).
- Signal at close t (hook bar). Entry: buy stop at `high_t + 0.01` on t+1 (needs stop-entry hook); fallback proxy =
  next open if `close_{t+1} > high_t` (later entry, labelled).
- Stop: `low_t - 0.01` (or `min(low[t-3..t])`). Target: none taught; `max_hold_days: 4`; `min_reward_risk: 0.0`.

## What the router should know
Pullback family, overlaps `pullback_trend` and `pullback_holy_grail`. Trend regimes only.

## Signs of decay to monitor
Hooks that fail within 1 bar > 50%; average 4-bar return after fill <= 0 over 50+ trades.

## Sources
- https://nexusfi.com/thinkorswim/23724-anti-strategy-linda-bradford-rasche-2.html
- https://il.tradingview.com/chart/GPS/RdUkem6a-The-Anti-A-Super-Powerful-1-1-Setup
- https://topstep.com/blog/going-deep-on-adam-grimes-approach
- https://quantifiedstrategies.substack.com/p/a-simple-stochastic-pullback-strategy

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 374 | 107 | 40% | -0.07 | -0.37 | 27% | -0.33 | -0.63 | 16% | -0.55 | -0.86 | 0.44 |
| correction | 35 | 14 | 33% | +0.07 | -0.24 | 33% | +0.14 | -0.17 | 19% | +0.61 | +0.30 | 1.61 |
| healthy_uptrend | 1841 | 633 | 40% | -0.08 | -0.33 | 33% | -0.02 | -0.27 | 25% | +0.04 | -0.21 | 1.05 |
| high_vol_selloff | 171 | 60 | 51% | +0.14 | -0.27 | 25% | -0.34 | -0.75 | 17% | -0.44 | -0.85 | 0.58 |
| narrow_uptrend | 221 | 83 | 42% | +0.11 | -0.24 | 33% | +0.17 | -0.18 | 19% | -0.14 | -0.49 | 0.85 |
| **all** | 2642 | 897 | 41% | -0.05 | -0.33 | 31% | -0.07 | -0.35 | 23% | -0.08 | -0.36 | 0.91 |

Portfolio replay (net of costs, slots shared with its run): 205 trades, win 38%, avg -0.14R, PF 0.75, P&L $-5,496 on $100k, avg hold 3.2 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1216 | 391 | 42% | -0.00 | -0.24 | 39% | +0.15 | -0.09 | 32% | +0.18 | -0.06 | 1.23 |
| correction | 361 | 128 | 39% | -0.10 | -0.42 | 38% | +0.06 | -0.26 | 29% | -0.03 | -0.35 | 0.96 |
| healthy_uptrend | 7454 | 2449 | 39% | -0.06 | -0.32 | 32% | -0.05 | -0.31 | 24% | -0.05 | -0.31 | 0.95 |
| high_vol_selloff | 925 | 325 | 38% | -0.11 | -0.40 | 35% | -0.02 | -0.32 | 24% | -0.24 | -0.53 | 0.72 |
| narrow_uptrend | 1056 | 363 | 47% | +0.10 | -0.16 | 40% | +0.11 | -0.14 | 33% | +0.31 | +0.05 | 1.39 |
| **all** | 11012 | 3656 | 40% | -0.05 | -0.31 | 34% | -0.00 | -0.27 | 26% | -0.00 | -0.26 | 1.00 |

Portfolio replay (net of costs, slots shared with its run): 644 trades, win 39%, avg -0.10R, PF 0.81, P&L $-11,760 on $100k, avg hold 3.3 bars.
