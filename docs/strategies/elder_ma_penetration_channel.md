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
_Pending: filled in from swing replay on real data._
