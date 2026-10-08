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
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3609 | 246 | 38% | +0.10 | -0.02 | 32% | +0.20 | +0.08 | 25% | +0.30 | +0.18 | 1.35 |
| correction | 305 | 26 | 27% | -0.16 | -0.30 | 25% | -0.01 | -0.15 | 20% | +0.11 | -0.03 | 1.13 |
| healthy_uptrend | 8486 | 508 | 35% | +0.11 | -0.03 | 26% | +0.01 | -0.13 | 18% | +0.02 | -0.12 | 1.02 |
| high_vol_selloff | 2107 | 85 | 31% | -0.14 | -0.23 | 36% | +0.08 | -0.01 | 29% | +0.05 | -0.04 | 1.06 |
| narrow_uptrend | 1374 | 70 | 19% | -0.53 | -0.66 | 12% | -0.61 | -0.74 | 7% | -0.74 | -0.87 | 0.33 |
| **all** | 15881 | 935 | 33% | +0.02 | -0.11 | 27% | +0.02 | -0.11 | 20% | +0.04 | -0.09 | 1.04 |

Portfolio replay (net of costs, slots shared with its run): 8 trades, win 38%, avg -0.18R, PF 0.62, P&L $-265 on $100k, avg hold 1.9 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 9931 | 437 | 37% | +0.16 | +0.04 | 31% | +0.24 | +0.12 | 24% | +0.33 | +0.21 | 1.39 |
| correction | 5234 | 194 | 42% | +0.25 | +0.15 | 34% | +0.32 | +0.23 | 27% | +0.39 | +0.29 | 1.45 |
| healthy_uptrend | 27732 | 908 | 33% | -0.04 | -0.18 | 25% | -0.04 | -0.17 | 19% | -0.01 | -0.15 | 0.99 |
| high_vol_selloff | 11065 | 564 | 39% | +0.10 | +0.01 | 34% | +0.15 | +0.06 | 26% | +0.10 | +0.00 | 1.11 |
| narrow_uptrend | 7317 | 294 | 35% | +0.09 | -0.03 | 29% | +0.11 | -0.01 | 22% | +0.12 | +0.00 | 1.14 |
| **all** | 61279 | 2397 | 35% | +0.06 | -0.06 | 29% | +0.09 | -0.03 | 22% | +0.11 | -0.01 | 1.13 |

Portfolio replay (net of costs, slots shared with its run): 38 trades, win 39%, avg +0.34R, PF 1.69, P&L $-652 on $100k, avg hold 1.7 bars.
