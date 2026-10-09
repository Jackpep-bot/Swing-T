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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 14370 | 13072 | 39% | -0.01 | -0.25 | 31% | -0.02 | -0.25 | 26% | -0.01 | -0.25 | 0.98 |
| correction | 1407 | 1273 | 40% | -0.12 | -0.37 | 34% | +0.06 | -0.19 | 32% | +0.22 | -0.04 | 1.32 |
| healthy_uptrend | 79036 | 73449 | 43% | +0.11 | -0.13 | 34% | +0.14 | -0.10 | 27% | +0.13 | -0.11 | 1.17 |
| high_vol_selloff | 5684 | 5119 | 40% | -0.00 | -0.21 | 35% | +0.11 | -0.10 | 29% | +0.12 | -0.09 | 1.17 |
| narrow_uptrend | 6199 | 5424 | 33% | -0.20 | -0.46 | 21% | -0.33 | -0.60 | 15% | -0.35 | -0.62 | 0.59 |
| **all** | 106696 | 98337 | 41% | +0.05 | -0.19 | 33% | +0.07 | -0.17 | 26% | +0.07 | -0.17 | 1.09 |

Portfolio replay (net of costs, slots shared with its run): 4 trades, win 25%, avg -0.06R, PF 0.93, P&L $1,053 on $100k, avg hold 3.8 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 47163 | 43442 | 49% | +0.25 | +0.03 | 43% | +0.38 | +0.16 | 36% | +0.44 | +0.21 | 1.68 |
| correction | 18449 | 17158 | 48% | +0.18 | -0.04 | 38% | +0.11 | -0.11 | 30% | +0.12 | -0.11 | 1.16 |
| healthy_uptrend | 277113 | 258035 | 40% | -0.01 | -0.24 | 33% | +0.02 | -0.21 | 26% | +0.04 | -0.19 | 1.05 |
| high_vol_selloff | 33410 | 30461 | 38% | -0.08 | -0.29 | 32% | -0.03 | -0.25 | 27% | -0.01 | -0.22 | 0.99 |
| narrow_uptrend | 44109 | 41023 | 44% | +0.09 | -0.15 | 37% | +0.11 | -0.13 | 29% | +0.09 | -0.14 | 1.13 |
| **all** | 420244 | 390119 | 42% | +0.03 | -0.19 | 35% | +0.07 | -0.16 | 28% | +0.09 | -0.13 | 1.13 |

Portfolio replay (net of costs, slots shared with its run): 5 trades, win 40%, avg -0.49R, PF 0.01, P&L $-177 on $100k, avg hold 6.8 bars.
