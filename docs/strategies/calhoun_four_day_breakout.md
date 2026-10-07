---
slug: calhoun_four_day_breakout
name: Four-Day Breakout (Ken Calhoun)
originators: [Ken Calhoun]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 15]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Four-Day Breakout (Calhoun)

## One-line summary
In a stock above its moving average, four consecutive bullish candles followed by a buy stop a fixed offset above the
pattern's highest high.

## Origin and lineage
Ken Calhoun, "Swing Trading Four-Day Breakouts", *Technical Analysis of Stocks & Commodities*, October 2017. Shipped
as the thinkorswim built-in `FourDayBreakoutLE` (entry only; exits come from separate strategies).

## Exact rules (thinkorswim description)
- Filter: close > SMA(close, `average length`). The default length is not stated on the reference page (unverified).
- Setup: the last `pattern length` (default 4) candles are all bullish (close > open).
- Trigger: buy stop at the highest high of those candles + `breakout amount` (default $0.50).
- Stop, target, sizing: not specified in the broker description; Calhoun's article was not available this run.

## Why it should work
Four up-closes show persistent buying; a buy stop above the pattern only fills if demand continues (short-term
continuation). Who is on the other side: short-term mean-reversion sellers and late shorts. Counter-argument: four
up days in a row is also a short-term overbought condition, where the literature favours reversal (e.g. Connors'
RSI(2) work), so this is a contrarian test of the engine's mean-reversion assumption.

## When it works and when it fails
Trending, low-volatility markets with broad participation. Fails in chop (buy stop fills at the top of the range) and
when the four candles are small-bodied drift.

## Parameters and sensitivity
- `pattern_len` 3-5; `sma_len` 20/50 (replay both; the published default is unknown); `offset` as
  0.1-0.25 x `atr_14` instead of $0.50, since a fixed dollar amount means 5% on a $10 stock and 0.1% on a $500 one.
- Trap: tuning the offset to the sample's average breakout follow-through.

## Evidence
Practitioner in-sample illustration only (grade D). The broker publishes no performance data. No independent test
located.

## Common mistakes
Using the $0.50 offset across price levels; counting doji as bullish; entering at the next open instead of the stop
(changes the trade entirely).

## Discretionary parts
Exit is unspecified. Make it mechanical with the engine defaults (initial stop below the pattern low, breakeven at
+1R, trail at +2R) and a time stop.

## Implementation spec for swing-engine
- Features: `bull_k` = close > open; `bull_run_4` = rolling sum of `bull_k` over 4 bars == 4; `pattern_high_4` =
  rolling max(high, 4) on the as-of bar; `pattern_low_4` = rolling min(low, 4).
- Signal at as-of close if `bull_run_4` and close > `sma_50` (replay `sma_20` as well) and `trend_state >= 0`.
- Entry: buy stop at `pattern_high_4 + 0.15 x atr_14`, valid for 1 session. Stop = `pattern_low_4 - 0.1 x atr_14`
  (engine choice). Target = entry + 2R; `max_hold_days: 10`; `min_reward_risk: 2.0`.
- Reuses: `sma_20`, `sma_50`, `atr_14`, `trend_state`, playbook gate.
- Missing: **stop-entry order hook** in the backtester (today `_fill_entry` only fills at the next open, with an
  optional limit). Interim approximation: next-open entry only if next open <= trigger and next high >= trigger,
  filling at max(open, trigger); this needs the hook.

## What the router should know
Breakout family; healthy_uptrend only. Disabled; comparison against `breakout_52w` and `momentum_burst`.

## Signs of decay to monitor
Fill rate of the buy stop vs subsequent 5-day return; share of fills that close below the trigger the same day.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/FourDayBreakoutLE

## Empirical (replay)
_Pending: filled in from swing replay on real data._
