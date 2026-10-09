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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4489 | 73 | 48% | -0.04 | -0.21 | 45% | -0.06 | -0.23 | 43% | +0.07 | -0.10 | 1.10 |
| correction | 290 | 0 | 55% | +0.12 | -0.10 | 51% | +0.10 | -0.12 | 53% | +0.18 | -0.04 | 1.42 |
| healthy_uptrend | 14444 | 140 | 47% | +0.04 | -0.12 | 43% | +0.05 | -0.11 | 38% | +0.06 | -0.10 | 1.10 |
| high_vol_selloff | 1550 | 17 | 51% | +0.05 | -0.13 | 43% | -0.00 | -0.18 | 35% | -0.05 | -0.23 | 0.92 |
| narrow_uptrend | 1365 | 22 | 30% | -0.27 | -0.47 | 26% | -0.40 | -0.60 | 20% | -0.44 | -0.65 | 0.49 |
| **all** | 22138 | 252 | 47% | +0.00 | -0.16 | 43% | -0.00 | -0.17 | 38% | +0.03 | -0.14 | 1.04 |

Portfolio replay (net of costs, slots shared with its run): 87 trades, win 28%, avg -0.17R, PF 0.71, P&L $-1,846 on $100k, avg hold 12.7 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11940 | 141 | 50% | +0.09 | -0.06 | 47% | +0.12 | -0.03 | 43% | +0.19 | +0.04 | 1.36 |
| correction | 8016 | 54 | 53% | +0.07 | -0.10 | 49% | +0.07 | -0.09 | 42% | +0.04 | -0.12 | 1.08 |
| healthy_uptrend | 52481 | 504 | 45% | -0.01 | -0.17 | 42% | -0.01 | -0.17 | 37% | -0.00 | -0.16 | 1.00 |
| high_vol_selloff | 7887 | 120 | 45% | -0.06 | -0.22 | 44% | -0.05 | -0.21 | 41% | -0.02 | -0.18 | 0.97 |
| narrow_uptrend | 8845 | 102 | 49% | +0.06 | -0.11 | 47% | +0.09 | -0.07 | 42% | +0.12 | -0.04 | 1.23 |
| **all** | 89169 | 921 | 47% | +0.01 | -0.14 | 44% | +0.02 | -0.14 | 39% | +0.04 | -0.12 | 1.07 |

Portfolio replay (net of costs, slots shared with its run): 347 trades, win 30%, avg +0.07R, PF 1.13, P&L $2,679 on $100k, avg hold 12.4 bars.
