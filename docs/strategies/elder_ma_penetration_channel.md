---
slug: elder_ma_penetration_channel
name: Elder MA-penetration channel swing (Fidelity Learning Center)
originators: [Alexander Elder (Come Into My Trading Room, 2002), Fidelity Learning Center adaptation]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 10]
timeframe: weekly trend + daily entry
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Elder MA-penetration channel swing

## One-line summary
In a weekly uptrend, place a resting limit buy below the daily moving average at roughly the average depth of
recent penetrations, and sell near the upper channel line.

## Origin and lineage
Alexander Elder's channel trading (Come Into My Trading Room; Triple Screen lineage: weekly trend tide, daily wave).
Fidelity's Learning Center page "swing trading setups" adapts it with a worked example. The Fidelity page does
**not** state the MA type/length, channel coefficient, or stop distance (WebFetch 2026-10-07). Elder's books
commonly use a 13- or 22-day EMA with an envelope sized to hold about 95% of recent prices; that detail comes from
the books and was **not verified this session**.

## Exact rules (as taught by Fidelity)
- Universe/screen: stocks or ETFs with a weekly uptrend and "short, sharp" daily bottoms; broad, well-defined channels.
- Setup: measure recent dips below the daily MA. Fidelity example: 3 returns to the MA, average penetration 1.5% of price.
- Entry: limit buy about 1% of price below the MA (a little shallower than the average past penetration).
- Initial stop: "reasonably close" to entry (unquantified).
- Target: near the upper channel line; take profits sooner in a weak market; in a strong market hold until a day
  fails to make a new high.
- Grading: profit as % of channel width (bottom-to-top = 100%; Elder suggests 30%+ as an A trade in the books, unverified).
- Sizing: not specified.

## Why it should work
Trend-pullback logic: in an uptrend, value buyers and institutions accumulate around the moving average; short-term
sellers overshoot it by a repeatable amount. Buying at the overshoot depth gets a better price than a stop-entry
above the bar. Counterparty: short-term sellers and stops below the MA.

## When it works and when it fails
- Works: steady, orderly uptrends with stable volatility (penetration depth is stationary).
- Fails: trend breaks (the limit fills and price keeps falling: adverse selection of resting limit buys), volatility
  expansion (past penetration depth understates the next one), gap-downs through the limit.

## Parameters and sensitivity
MA length (13-26 EMA), number of past penetrations averaged (3-6), fraction of average depth used (Fidelity ~0.67:
1% vs 1.5%), channel coefficient (fit to contain ~90-95% of the last 100 bars), stop distance. Trap: fitting depth
fraction and channel width jointly per symbol is high-dimensional; fix globally.

## Evidence
None. Educational material, no statistics (catalog B57). Related evidence: pullback-in-uptrend work in
`docs/methods/01-pullback-20-50-ma-uptrend.md` (Grimes: MA touches themselves look random; edge comes from trend plus trigger).

## Common mistakes
Ignoring the weekly trend; averaging penetrations from a different volatility regime; no hard stop on a limit fill;
holding to the upper channel when the market turns weak.

## Discretionary parts and how to make them mechanical
- Weekly uptrend: weekly close > 26-week EMA and EMA rising (or daily `trend_state == 1`).
- "Penetration": a bar whose low is below `ema_21` after at least 3 bars closing above it; depth = `(ema_21 - low)/close`.
- Average of the last 3 such depths within 60 bars; limit = `ema_21 * (1 - 0.67 * avg_depth)`.
- Channel: `ema_21 * (1 ± k)`, `k` = smallest value containing 95% of closes in the last 100 bars.

## Implementation spec for swing-engine
- Reuses: `ema_21`, `atr_14`, `trend_state`, `high`, `low`, `close`.
- New features: `pen_depth_avg_3` (above), `channel_k_100`, `upper_channel = ema_21 * (1 + channel_k_100)`.
- Signal on close t (for day t+1): trend gate passes, close > ema_21, `pen_depth_avg_3` defined.
- Entry: **limit buy** at `ema_21_t * (1 - 0.67 * pen_depth_avg_3)`, valid one day; fills only if low_{t+1} <= limit
  (fill at min(open, limit)).
- Stop: `limit - 1.0 * atr_14`. Target: `upper_channel`. Exit early when the market regime is not `healthy_uptrend`
  and price reaches the channel mid, or on the first day without a new high after the target zone is entered;
  `max_hold_days = 10`. `min_reward_risk = 1.5`.
- Missing: **limit-below-close entry hook** in `research/backtest.py` (it fills queued signals at the next open) and
  a weekly-bar resampler.

## What the router should know
Pullback family: same allowance as `pullback_trend` (full in healthy_uptrend, half in narrow_uptrend, none in correction).

## Signs of decay to monitor
Limit fills followed by stop-outs > 45%; average channel-width capture < 20%.

## Sources
- https://www.fidelity.com/learning-center/trading-investing/trading/swing-trading-setups
- Elder, A. (2002) Come Into My Trading Room (Wiley) - not re-read this session.

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 14372 | 13073 | 39% | -0.01 | -0.25 | 31% | -0.02 | -0.26 | 26% | -0.01 | -0.25 | 0.98 |
| correction | 1407 | 1273 | 40% | -0.12 | -0.37 | 34% | +0.06 | -0.19 | 32% | +0.22 | -0.04 | 1.32 |
| healthy_uptrend | 79108 | 73514 | 43% | +0.11 | -0.13 | 34% | +0.14 | -0.10 | 27% | +0.13 | -0.11 | 1.17 |
| high_vol_selloff | 5683 | 5118 | 40% | -0.00 | -0.21 | 35% | +0.11 | -0.10 | 29% | +0.12 | -0.09 | 1.17 |
| narrow_uptrend | 6201 | 5425 | 33% | -0.19 | -0.45 | 21% | -0.32 | -0.59 | 15% | -0.34 | -0.61 | 0.60 |
| **all** | 106771 | 98403 | 41% | +0.05 | -0.19 | 33% | +0.07 | -0.17 | 26% | +0.07 | -0.17 | 1.09 |

Portfolio replay (net of costs, slots shared with its run): 134 trades, win 28%, avg +0.08R, PF 1.14, P&L $7,662 on $100k, avg hold 5.8 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 43499 | 40004 | 49% | +0.24 | +0.02 | 43% | +0.39 | +0.17 | 36% | +0.46 | +0.24 | 1.72 |
| correction | 17317 | 16068 | 48% | +0.18 | -0.04 | 37% | +0.09 | -0.12 | 30% | +0.10 | -0.12 | 1.14 |
| healthy_uptrend | 255690 | 238051 | 41% | -0.00 | -0.23 | 33% | +0.04 | -0.19 | 27% | +0.07 | -0.16 | 1.10 |
| high_vol_selloff | 30569 | 27822 | 38% | -0.07 | -0.27 | 33% | -0.01 | -0.22 | 28% | +0.03 | -0.18 | 1.04 |
| narrow_uptrend | 44432 | 41344 | 44% | +0.08 | -0.15 | 36% | +0.08 | -0.15 | 28% | +0.06 | -0.18 | 1.07 |
| **all** | 391507 | 363289 | 42% | +0.04 | -0.18 | 35% | +0.08 | -0.14 | 29% | +0.11 | -0.11 | 1.16 |

Portfolio replay (net of costs, slots shared with its run): 642 trades, win 29%, avg +0.08R, PF 1.13, P&L $31,418 on $100k, avg hold 5.5 bars.
