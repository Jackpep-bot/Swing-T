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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 373 | 108 | 41% | -0.06 | -0.37 | -0.44 | 28% | -0.32 | -0.62 | -0.69 | 16% | -0.54 | -0.84 | -0.88 | 0.45 |
| correction | 34 | 14 | 35% | -0.07 | -0.39 | -0.58 | 35% | +0.09 | -0.23 | -0.74 | 20% | +0.27 | -0.05 | -1.06 | 1.27 |
| healthy_uptrend | 1834 | 615 | 41% | -0.06 | -0.31 | -0.27 | 34% | -0.02 | -0.27 | -0.31 | 27% | +0.05 | -0.20 | -0.25 | 1.06 |
| high_vol_selloff | 171 | 60 | 52% | +0.13 | -0.28 | -0.40 | 26% | -0.35 | -0.75 | -0.52 | 18% | -0.43 | -0.84 | -0.44 | 0.58 |
| narrow_uptrend | 220 | 82 | 42% | +0.12 | -0.23 | -0.23 | 33% | +0.20 | -0.16 | -0.73 | 21% | -0.11 | -0.46 | -1.41 | 0.88 |
| **all** | 2632 | 879 | 41% | -0.04 | -0.32 | -0.30 | 32% | -0.07 | -0.35 | -0.42 | 24% | -0.08 | -0.35 | -0.43 | 0.91 |

Portfolio replay (net of costs, slots shared with its run): 52 trades, win 38%, avg -0.22R, PF 0.70, P&L $-1,053 on $100k, avg hold 3.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1165 | 373 | 43% | -0.02 | -0.26 | -0.33 | 41% | +0.10 | -0.14 | -0.34 | 33% | +0.07 | -0.17 | -0.42 | 1.09 |
| correction | 356 | 128 | 40% | -0.07 | -0.39 | -0.68 | 39% | +0.05 | -0.26 | -0.63 | 30% | -0.09 | -0.41 | -0.88 | 0.89 |
| healthy_uptrend | 7128 | 2271 | 40% | -0.06 | -0.32 | -0.32 | 34% | -0.05 | -0.31 | -0.36 | 26% | -0.05 | -0.31 | -0.42 | 0.94 |
| high_vol_selloff | 892 | 309 | 39% | -0.11 | -0.41 | -0.26 | 37% | -0.03 | -0.33 | -0.31 | 26% | -0.22 | -0.52 | -0.50 | 0.72 |
| narrow_uptrend | 1045 | 350 | 46% | +0.04 | -0.21 | -0.43 | 39% | +0.02 | -0.23 | -0.46 | 34% | +0.13 | -0.12 | -0.43 | 1.18 |
| **all** | 10586 | 3431 | 41% | -0.05 | -0.31 | -0.34 | 35% | -0.02 | -0.28 | -0.37 | 28% | -0.04 | -0.30 | -0.44 | 0.96 |

Portfolio replay (net of costs, slots shared with its run): 183 trades, win 42%, avg -0.02R, PF 0.97, P&L $-2,094 on $100k, avg hold 3.5 bars.
