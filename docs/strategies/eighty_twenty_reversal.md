---
slug: eighty_twenty_reversal
name: 80-20 reversal (Raschke & Connors)
originators: [Linda Bradford Raschke, Laurence Connors]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [0, 2]
timeframe: daily setup, intraday stop-entry
direction: long   # sell setup mirrors; engine is long-only
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# 80-20 reversal

## One-line summary
A bar that opens near its high and closes near its low tends to see a little more selling next morning; when that
follow-through fails and price climbs back to the prior low, buy.

## Origin and lineage
*Street Smarts* (1995), credited to a George Taylor-style observation that such bars usually extend beyond the extreme
next morning and then often fail. Catalog note: Roboforex's "80% body candle" version is a forex adaptation, not the
book rule. `docs/methods.md` 2d quotes a secondary source with the open/close percentages reversed; the catalog rule
below (open top 20%, close bottom 20% for a buy) is the one used here.

## Exact rules (long)
- Setup bar (yesterday): opened in the top 20% of its range and closed in the bottom 20%.
- Today: price must trade at least 5-15 ticks below yesterday's low (guideline).
- Entry: buy stop at yesterday's low (re-entry into the prior range).
- Stop: near today's low; raise to lock in profit.
- Exit: taught as a day trade; may be held 1-2 days if strong.

## Why it should work
A strong-open, weak-close bar leaves late sellers and stop-runs under the low. Once the morning flush runs out of
sellers, short-covering and dip buyers push it back through the low.

## When it works and when it fails
Works in range-bound or pullback conditions with liquid names. Fails in trend-down liquidation and news days; the edge
(if any) is mostly intraday, so daily replay will understate or distort it.

## Parameters and sensitivity
Open/close thresholds (0.8 / 0.2), the undercut distance (5-15 ticks -> 0.05-0.3% or 0.1 x atr_14 for stocks), hold
(same day vs 1-2 days). Few knobs; do not tune thresholds per symbol.

## Evidence
Originator claims only; no independent test located. Rules come from a search summary of the book (catalog flag).

## Common mistakes
Buying the setup bar's close (the method expects a lower open/flush first); holding a failed day trade overnight.

## Discretionary parts and how to make them mechanical
Undercut = `low_t < low_{t-1} - 0.1 * atr_14_{t-1}`. "Held if strong" = close in top 25% of today's range and above entry.

## Implementation spec for swing-engine
- Reuses: OHLC, `close_pos` ((close-low)/(high-low)), `atr_14`.
- New feature: `open_pos = (open - low) / (high - low)` (NaN when range is 0).
- Setup at close t-1: `open_pos >= 0.8` and `close_pos <= 0.2`.
- Fill on t: if `low_t < low_{t-1} - buf` and `high_t >= low_{t-1}`: entry = `low_{t-1}`. Order is certain only if
  `open_t < low_{t-1}`; otherwise flag `ambiguous`.
- Stop: `low_t - 0.01`. Exit: close of t (day-trade variant) or next close / `max_hold_days: 2` (swing variant).
- `min_reward_risk: 0.0` (no target taught).
- Missing: stop-entry hook; intraday bars for honest same-day exits.

## What the router should know
Short-horizon mean reversion, overlaps `turtle_soup` and `williams_oops`. Small size, `choppy` / `narrow_uptrend` only.

## Signs of decay to monitor
Same-day stop-out rate > 55%; average trade < round-trip cost.

## Sources
- https://technical.traders.com/tradersonline/display.asp?art=2527
- https://roboforex.com/blog/education/trading-strategies-that-were-a-revolution-three-strategies-of-linda-raschke/
  (different, forex-adapted version)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3609 | 246 | 38% | +0.10 | -0.23 | 32% | +0.20 | -0.13 | 25% | +0.30 | -0.03 | 1.35 |
| correction | 305 | 26 | 27% | -0.16 | -0.74 | 25% | -0.01 | -0.59 | 20% | +0.11 | -0.47 | 1.13 |
| healthy_uptrend | 8486 | 508 | 35% | +0.11 | -0.26 | 26% | +0.01 | -0.36 | 18% | +0.02 | -0.35 | 1.02 |
| high_vol_selloff | 2108 | 85 | 31% | -0.14 | -0.42 | 36% | +0.08 | -0.20 | 29% | +0.05 | -0.24 | 1.06 |
| narrow_uptrend | 1374 | 70 | 19% | -0.53 | -0.87 | 12% | -0.61 | -0.95 | 7% | -0.74 | -1.08 | 0.33 |
| **all** | 15882 | 935 | 33% | +0.02 | -0.33 | 27% | +0.02 | -0.34 | 20% | +0.04 | -0.32 | 1.04 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10401 | 477 | 37% | +0.16 | -0.17 | 31% | +0.25 | -0.08 | 25% | +0.35 | +0.02 | 1.41 |
| correction | 5286 | 200 | 43% | +0.27 | -0.07 | 35% | +0.33 | +0.00 | 28% | +0.39 | +0.06 | 1.45 |
| healthy_uptrend | 30252 | 1003 | 32% | -0.06 | -0.43 | 25% | -0.06 | -0.43 | 18% | -0.04 | -0.42 | 0.95 |
| high_vol_selloff | 11670 | 571 | 39% | +0.11 | -0.20 | 34% | +0.17 | -0.14 | 27% | +0.14 | -0.17 | 1.16 |
| narrow_uptrend | 7561 | 293 | 37% | +0.12 | -0.22 | 31% | +0.15 | -0.19 | 23% | +0.16 | -0.18 | 1.19 |
| **all** | 65170 | 2544 | 35% | +0.05 | -0.29 | 29% | +0.09 | -0.26 | 22% | +0.11 | -0.24 | 1.12 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
