---
slug: katsanos_trend_strength_filters
name: Trend-strength filter family ADXTrend / ERTrend / R2Trend / VHFTrend (Katsanos)
originators: ["Markos Katsanos (Which Trend Indicator Wins?, S&C Oct 2016)", "thinkorswim built-ins", "indicator authors: Wilder (ADX), Kaufman (ER), Adam White (VHF)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 40]     # estimate; exit on close back through the MA
timeframe: daily
direction: long_only_in_engine (original long and short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Trend-strength filter family (Katsanos)

## One-line summary
One template, four trend meters (ADX, Efficiency Ratio, R-squared + regression slope, VHF): if the meter says a trend is
developing or strong, buy a close crossing above its MA and exit on the cross back.

## Origin and lineage
Katsanos, S&C Oct 2016, compared the four indicators as trend filters; thinkorswim ships ADXTrend, ERTrend, R2Trend,
VHFTrend. Which indicator "won" in the article could not be retrieved (traders.com 403).

## Exact rules (TOS)
- Indicator X in {ADX(len), ER(len) smoothed by an `er average length`, VHF(len)}:
  - developing: X > crit_level and X > mult x min(X over `lag` bars);
  - strong: trend_level < X < max_level.
- R2Trend: R² of close vs a linear trendline over len > trend_level (default 0.42) and rising vs prior bar, and the
  regression slope > +critical (uptrend).
- Entry long: (developing or strong) and close crosses above its MA(average length). Next open.
- Exit long: close crosses below the MA. Shorts mirror.
- Defaults for length, lag, mult, crit/trend/max levels and MA length are **not published on the TOS pages** (only R² 0.42).

## Why it should work
MA-cross whipsaw happens in ranges; gating it with a trend meter should skip range trades. Who is on the other side: range
traders who fade the cross. The filter itself is the experiment: does it raise expectancy versus the unfiltered
`ma_crossover_family` price/MA variant?

## When it works and when it fails
Trending phases after a base. Fails at turning points (all four meters lag) and in high-volatility selloffs, where ADX and VHF
read "trend" on the way down.

## Parameters and sensitivity
Many knobs per meter (length, lag, mult, three levels, MA length): high overfitting risk. Engine assumptions: ADX(14) crit 20
trend 25 max 50; ER(10) crit 0.3 trend 0.5; VHF(28) crit 0.35 trend 0.4; lag 10, mult 1.1, MA SMA(20). All flagged as
engine choices, not Katsanos defaults.

## Evidence
In-sample S&C comparison only (grade D). Independent academic tests of ADX-style filters are mixed and not specific to these
rules. The catalog notes the family doubles as a regime-router experiment.

## Common mistakes
Reading ADX direction-agnostically (it rises in downtrends too); using R² without the slope sign.

## Discretionary parts and how to make them mechanical
Fully mechanical once defaults are fixed in params.

## Implementation spec for swing-engine
- Module `strategies/trend_strength.py`, `@register("strategy")`, param `meter` in {adx, er, r2, vhf}.
- Reuses adx_14, plus_di_14, minus_di_14 (require +DI > -DI for longs as a declared deviation), sma_20, atr_14.
- New features: `er_10` = |C - C[10]| / sum(|C - C[1]|, 10); `vhf_28` = (max(C,28) - min(C,28)) / sum(|C - C[1]|, 28);
  `r2_20` and `linreg_slope_20` of close (catalog also maps to `kaufman_efficiency_ratio_kama`).
- Signal at close t: meter gate true and close crosses above sma_20. Entry next open.
- Stop: entry - 2 x atr_14. Target: None. `should_exit`: close < sma_20. `max_hold_days`: 40. `min_reward_risk`: not applied.
- settings.yaml: `trend_strength: {enabled: false, shadow_only: true, meter: adx}`; replay all four meters and report all.

## What the router should know
Primarily a regime-gating experiment: the most useful output is which meter best separates winning from losing trades of
other strategies, not this strategy's own P&L.

## Signs of decay to monitor
Gate pass rate above 70% of days (meter no longer discriminates); filtered vs unfiltered expectancy gap closing.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ADXTrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/ERTrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/R2Trend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/VHFTrend

## Empirical (replay)
_Pending: filled in from swing replay on real data._
