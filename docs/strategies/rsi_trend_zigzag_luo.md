---
slug: rsi_trend_zigzag_luo
name: "RSITrend (Kevin Luo): RSI cross only in a ZigZag-confirmed trend"
originators: [Kevin Luo ("The RSI & Price Trends", S&C Jun 2015), thinkorswim RSITrend]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]     # estimate; original has no explicit long exit beyond the opposite signal
timeframe: daily
direction: long_only_in_engine (original long and short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# RSITrend (Luo)

## One-line summary
Take the classic RSI oversold cross only when a ZigZag-percent trend reading says a strong uptrend is in place.

## Origin and lineage
Kevin Luo, S&C Jun 2015; thinkorswim RSITrend uses its ZigZagTrendPercent study as the trend filter. It is the
`rsi_30_70` variant of `oscillator_cross_family` plus a trend gate.

## Exact rules (TOS)
- Inputs: RSI length, overbought, oversold, `percentage reversal` (ZigZag threshold), MA type. Defaults not given on the
  page text in the catalog (RSI(14) 30/70 assumed; unverified).
- Long: RSI crosses above oversold while ZigZagTrendPercent indicates a strong uptrend. Short: RSI crosses below
  overbought in a strong downtrend (not used).
- Exit: the TOS page describes only entry signals; exit is presumably the opposite signal (unverified).

## Why it should work
A pullback to oversold inside a confirmed uptrend is a buy-the-dip trade; the trend filter removes oversold crosses in
downtrends, the main failure of the unfiltered rule.

## When it works and when it fails
Orderly uptrends with periodic pullbacks. Fails when the trend breaks during the pullback; ZigZag confirmation lags by the
full reversal percentage.

## Parameters and sensitivity
ZigZag reversal 3-10%, RSI 7-14, oversold 25-40. A daily RSI(14) under 30 is rare in a strong uptrend, so trade count
can be tiny; that is the main trap (results on a handful of trades).

## Evidence
In-sample S&C illustration only (grade D). No independent test found.

## Common mistakes
**ZigZag repaints**: its last leg is revised as new bars arrive. Any backtest that reads the plotted ZigZag is look-ahead.
Use only confirmed swing points (catalog note).

## Discretionary parts and how to make them mechanical
"Strong uptrend" -> last two confirmed swing highs and lows are both higher (HH + HL), with swings confirmed only after
price reverses by `pct` from the extreme.

## Implementation spec for swing-engine
- Module `strategies/rsi_trend.py`, `@register("strategy")`; new feature `zz_trend_{pct}` from a non-repainting
  swing labeller (catalog maps_to `swing_point_labeling`): a swing high is confirmed on the bar where close falls
  `pct`% below the running max since the last confirmed low (and mirror); trend = +1 if last confirmed high > previous
  confirmed high and last confirmed low > previous confirmed low.
- Reuses rsi_14, atr_14, trend_state (as a sanity check), pivot logic in features/levels.py (different: fixed width).
- Signal at close t: zz_trend = +1 and rsi_14 crosses above 30. Entry next open.
- Stop: min(last confirmed swing low, entry - 1.5 x atr_14) below entry. Target: prior confirmed swing high if above entry
  (then `min_reward_risk` 1.5), else None. `should_exit`: rsi_14 crosses below 70 or zz_trend != +1. `max_hold_days`: 30.
- settings.yaml: `rsi_trend: {enabled: false, shadow_only: true, zz_pct: 5, rsi_os: 30, rsi_ob: 70}`.

## What the router should know
Low-frequency dip-buy in uptrends; compare against `pullback_trend` and `rsi2_meanrev` which cover the same idea with
more trades.

## Signs of decay to monitor
Fewer than ~30 trades per year across the universe makes the replay uninformative.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RSITrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/V-Z/ZigZagTrendPercent

## Empirical (replay)
_Pending: filled in from swing replay on real data._
