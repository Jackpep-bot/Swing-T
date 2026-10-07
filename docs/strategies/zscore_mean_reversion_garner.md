---
slug: zscore_mean_reversion_garner
name: "SimpleMeanReversion z-score (Anthony Garner)"
originators: ["Anthony Garner (S&C, May 2019)", "thinkorswim SimpleMeanReversion"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long (original also shorts; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Z-score mean reversion (Garner)

## One-line summary
Buy when price is more than 1 standard deviation below its L-bar mean while the L-bar SMA is above the 10L-bar SMA
(long-term uptrend); exit when the z-score recovers above -0.5.

## Origin and lineage
Anthony Garner, S&C May 2019 (Python backtest article per catalog; not read); coded by thinkorswim (catalog B10). A
textbook Bollinger-style mean reversion with a trend filter; cousin of Connors RSI-2 (`rsi2_meanrev`).

## Exact rules (thinkorswim)
- `z = (price - SMA(price, L)) / StDev(price, L)`.
- Fast SMA length = L x fast factor (default 1); slow SMA length = L x slow factor (default 10).
- Buy to open: z < -1.0 and fast SMA > slow SMA. Sell to close: z > -0.5.
- Short: z > +1.0 and fast SMA < slow SMA; cover z < +0.5 (not used).
- Default `length` L: **unverified** (tos text truncated); no price stop; sizing not specified.

## Why it should work
Short-horizon reversal (Jegadeesh 1990; Lehmann 1990) inside a long-term uptrend: liquidity-driven dips are bought by
trend holders. The other side is short-term momentum sellers and forced sellers.

## When it works and when it fails
Works in rising or ranging markets with no news. Fails in trend breaks: the filter (SMA L > SMA 10L) lags, so the first
weeks of a correction still produce buys; no stop means losses are open-ended.

## Parameters and sensitivity
L (10-50; 20 matches `bb_*_20`), entry z (-1 to -2.5), exit z (-0.5 to 0), slow factor (5-10). Deeper entry z = fewer
but higher-quality trades. Trap: grid-searching all four together.

## Evidence
Garner's article is an in-sample illustration; no broker statistics; no independent test of this exact rule. Grade D.
Related Connors RSI-2 rules have extensive practitioner tests; docs/methods/11 records (Alvarez, Jan 2024) that
short-term mean reversion has not decayed further since the mid-2000s but edges are smaller.

## Common mistakes
Running it without any stop; using z on very low-vol names (tiny StDev gives large z for trivial moves); ignoring
earnings gaps.

## Discretionary parts and how to make them mechanical
None in the original. Add a protective ATR stop and time stop as engine choices.

## Implementation spec for swing-engine
- With L = 20: `z = (close - sma_20) / sd_20` where `sd_20 = (bb_upper_20 - sma_20) / 2` (BB uses 2 std with
  ddof=0 per indicators.py `rolling_std`). Slow SMA = SMA(200) = existing `sma_200` (10 x 20). So the rule is
  `close < bb_mid - 1*sd` and `sma_20 > sma_200` with existing columns only.
- Entry at t: `z[t] < -1.0` (first bar crossing, `z[t-1] >= -1.0`, to avoid repeated signals), `sma_20 > sma_200`.
- Entry next open. Stop `entry - 2*atr_14` (engine choice, as `rsi2_meanrev`). Reference target = `sma_20 - 0.5*sd_20`
  (the exit level), so `reward_risk` is honest and low; `min_reward_risk` 0. `should_exit`: `z > -0.5`;
  `max_hold_days` 10.
- Reuses `sma_20`, `bb_upper_20`, `sma_200`, `atr_14`. Nothing missing for L = 20; other L need a generic rolling std.

## What the router should know
Mean-reversion family; highly correlated with `rsi2_meanrev` entries. Treat as the same bucket (shared risk cap). Allowed
where `rsi2_meanrev` is allowed.

## Signs of decay to monitor
Win rate below ~60% or average trade below costs (mean reversion is thin); stop-outs clustering in sell-offs.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SimpleMeanReversion
- docs/methods/11-rsi2-connors-mean-reversion.md (family evidence)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
