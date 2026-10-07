---
slug: sentiment_zone_oscillator
name: Sentiment Zone Oscillator strategy (Walid Khalil)
originators: [Walid Khalil (S&C, May 2012), thinkorswim "SentimentZone" built-in strategy]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: long (shorts not used by the engine)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Sentiment Zone Oscillator strategy (Khalil)

## One-line summary
Count of up-closes minus down-closes, TEMA-smoothed and scaled to +/-100, traded against self-adjusting overbought/oversold
lines and a 60-EMA trend filter.

## Origin and lineage
Walid Khalil, "Sentiment Zone Oscillator", Technical Analysis of Stocks & Commodities, May 2012. Shipped as a thinkorswim
study (SentimentZoneOscillator) and strategy (SentimentZone). Conceptually a smoothed "up-bar ratio" oscillator, close to
Khalil's earlier Volume Zone Oscillator (Khalil and Steckler) but using bar direction instead of volume.

## Exact rules (thinkorswim strategy)
- Oscillator: R_t = +1 if close_t > close_{t-1}, -1 if lower (0 if unchanged is an assumption; the doc only defines up/down).
  SZO = 100 * TEMA(R, length) / length, as the thinkorswim description and the public ports state. Because TEMA of a +/-1
  series stays near [-1, +1] (TEMA can overshoot slightly), SZO lives in roughly +/-100/length = +/-7.1 at length 14, so the
  "+7" exit level sits right at the top of the range: it fires as SZO leaves a run of near-unanimous up closes. This is an
  inference from the formula, not checked against the article; verify the scale before trusting the +7 constant.
- Dynamic levels over `long_length` bars: hi = max(SZO), lo = min(SZO), range = hi - lo;
  OB = lo + pct * range; OS = hi - pct * range.
- Defaults (from eSignal / ProRealCode ports, not verified against the article): length 14, long_length 30, pct 95%.
- Buy (any of): (a) SMA30(SZO) crosses above 0 and close > EMA60(close); (b) SZO < OS and SMA30(SZO) rising and close > EMA60;
  (c) SZO crosses above OS and SMA30(SZO) > 0 and EMA60 rising.
- Sell to close (any of): SMA30(SZO) crosses below 0; SZO crosses below +7 while SMA30(SZO) is falling.
- Entry: next open after the signal bar (thinkorswim simulated orders fill at the next bar's open by default).
- Initial stop, targets, sizing: none taught. Pure signal-in/signal-out.

## Why it should work
It is a short-horizon trend/persistence filter plus a pullback-in-trend buy (rule b/c). The counterparty is the same as any
pullback-in-uptrend buy: short-term sellers at oversold levels inside an established uptrend. No independent mechanism beyond
generic time-series momentum.

## When it works and when it fails
Works in persistent, low-noise uptrends where up-close counts stay positive. Fails in chop (SMA30 of SZO oscillates around 0,
rule (a) fires repeatedly) and in fast selloffs (exit on a 30-bar average cross is slow; no hard stop).

## Parameters and sensitivity
length (10-21), long_length (20-60), pct (80-95%), SMA 30, EMA 60, exit level +7. Six knobs plus three OR-ed entries: a large
implicit trial count. Test the default set only, then one perturbation each; do not grid-search.

## Evidence
Only the in-sample illustration in the S&C article (not reviewed here). Broker publishes no statistics. No independent or academic
test found. Grade D.

## Common mistakes
Treating the dynamic OB/OS as fixed; changing `length` without rescaling the +7 exit (it is tied to 100/length); adding no
stop.

## Discretionary parts and how to make them mechanical
None in the rules; the only ambiguities are the formula scale (above), R on unchanged closes, and "rising" (use
value_t > value_{t-1}). Make the exit level a param `exit_level` = 0.98 * 100/length so it scales with length.

## Implementation spec for swing-engine
- New module `strategies/sentiment_zone.py`, `@register("strategy", "sentiment_zone")`, default disabled.
- Features to add (per symbol, past-only): `szo_14`, `szo_sma30`, `szo_ob`, `szo_os`, `ema_60`, plus prior-bar copies
  (`szo_14_prev`, `szo_sma30_prev`, `ema_60_prev`) so crosses and "rising" can be evaluated from one row.
  TEMA(x,n) = 3*E1 - 3*E2 + E3 with E1 = EMA(x,n), E2 = EMA(E1,n), E3 = EMA(E2,n) using the existing `ema`.
- Entry: Signal on close t, filled next open (engine default). entry = close_t (reference).
- Stop (engine requires one): low of last 10 bars - 0.1 * atr_14 (engine-chosen, not taught; param `stop_lookback`).
- Target: reference only, `target_r` = 4.0 so reward_risk is defined; the rule exit is primary. min_reward_risk param 1.0.
- Rule exit via `should_exit(row, bars_held)`: szo_sma30 crosses below 0, or szo crosses below 7 with szo_sma30 falling.
- max_hold_days: 40.
- Reuses: `ema`, `atr_14`, `trend_state` (optional extra gate, off by default to stay faithful).
- Missing: TEMA helper, rolling max/min of SZO, prev-value columns.

## What the router should know
Trend-persistence long; put it only in healthy_uptrend for the comparison run. Overlaps heavily with pullback_trend and
moving_momentum_hill; expect high signal correlation.

## Signs of decay to monitor
Rule exit firing within 3 bars on most trades (whipsaw); win rate < 35% with payoff < 1.5.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SentimentZone
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/SentimentZoneOscillator
- https://www.prorealcode.com/prorealtime-indicators/sentiment-zone-oscillator/ (default parameters, port)
- Khalil, W., "Sentiment Zone Oscillator", Technical Analysis of Stocks & Commodities, May 2012 (not read directly)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
