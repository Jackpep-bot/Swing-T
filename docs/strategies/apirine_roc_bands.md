---
slug: apirine_roc_bands
name: Rate of Change with Bands strategy (Vitali Apirine)
originators: [Vitali Apirine (S&C, March 2021), thinkorswim "RateOfChangeWithBandsStrat"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 25]
timeframe: daily
direction: long (short side mirrored in the source; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Rate of Change with Bands (Apirine)

## One-line summary
In an uptrend (close above an EMA), buy when smoothed ROC climbs back above its lower RMS band; exit when it falls back below
the upper band or price loses the EMA.

## Origin and lineage
Vitali Apirine, "Rate Of Change With Bands", Technical Analysis of Stocks & Commodities, March 2021 (Traders' Tips same issue).
Implemented in thinkorswim as study RateOfChangeWithBands and strategy RateOfChangeWithBandsStrat. Same family as Bollinger-on-
momentum ideas: volatility bands drawn around a momentum oscillator instead of around price.

## Exact rules (thinkorswim strategy description)
- Trend: uptrend if close > EMA(close, ema_length); downtrend otherwise.
- ROC_t = 100 * (close_t / close_{t-roc_length} - 1); avgROC = EMA(ROC, average_length).
- Bands: thinkorswim describes them as `num_rmss` root-mean-squares of the average ROC. Assumed form (approximation, catalog
  formula_status = approximation): RMS_t = sqrt(mean(avgROC^2 over rms_length)); upper = +num_rmss * RMS, lower = -num_rmss * RMS
  (bands centred on zero, which is what RMS rather than standard deviation implies). Not verified against the article; the
  Traders' Tips page returned 403.
- Buy to open: uptrend and avgROC crosses above the lower band.
- Sell to close: avgROC crosses below the upper band while in uptrend, or close crosses below the EMA.
- Short side mirrors (ignored here).
- Default lengths: not stated on the thinkorswim pages; unverified.
- No stop, target or sizing in the source.

## Why it should work
A dip-in-trend buy: avgROC below the lower band means momentum is unusually weak relative to its own recent scale while price is
still above trend; the cross back up is the "oversold, turning" trigger. Counterparty: short-term sellers exhausting into a
trend. Same mechanism as RSI-2 / pullback setups, with an adaptive threshold.

## When it works and when it fails
Works in steady uptrends with periodic shallow dips. Fails when the EMA filter is breached repeatedly (choppy) and in regime
breaks where the "oversold" momentum keeps falling; the EMA-cross exit then fires after a gap.

## Parameters and sensitivity
roc_length (9-20), average_length (3-10), rms_length (10-30), ema_length (20-50), num_rmss (1-2). Band width is the main knob:
wider bands = fewer, deeper-dip entries. Five knobs; test the article/platform defaults once they are verified.

## Evidence
Only the author's in-sample chart examples (S&C). No broker statistics, no independent test found. Grade D.

## Common mistakes
Using standard deviation around avgROC instead of RMS around zero (changes signal timing); forgetting the EMA exit.

## Discretionary parts and how to make them mechanical
None in the rules. The open item is the exact band formula and default lengths: verify against the S&C article or the
thinkScript source before coding; until then treat as an approximation and log it in the trial log.

## Implementation spec for swing-engine
- New module `strategies/roc_bands.py`, registered `roc_bands`, disabled.
- Features: `roc_n`, `roc_avg`, `roc_rms`, `ema_trend` (EMA of close), with `_prev` copies for crosses.
- Signal on close t when close > ema_trend and roc_avg_prev <= -k*roc_rms_prev and roc_avg > -k*roc_rms. Entry next open.
- Stop (engine-chosen): min(low over the last 5 bars) - 0.1*atr_14, floor at ema_trend - 1*atr_14 if lower stop is tighter.
- Target: reference `target_r` = 3.0; exits primarily by rule.
- `should_exit`: roc_avg crosses below +k*roc_rms, or close < ema_trend.
- max_hold_days: 30. min_reward_risk param 1.0 (rule-exit system).
- Reuses `ema`, `atr_14`; missing: ROC/RMS helpers and prev-value columns.

## What the router should know
Pullback-in-uptrend family; highly correlated with pullback_trend and rsi2_meanrev entry days. Allow in healthy and narrow
uptrends only for the comparison run.

## Signs of decay to monitor
Most exits by EMA break rather than upper-band cross (trend filter too loose); average hold < 4 bars.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RateOfChangeWithBandsStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/RateOfChangeWithBands
- https://traders.com/Documentation/FEEDbk_docs/2021/03/TradersTips.html (Traders' Tips, March 2021; not readable, 403)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
