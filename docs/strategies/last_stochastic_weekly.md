---
slug: last_stochastic_weekly
name: "The 'Last' Stochastic technique (weekly 39-period)"
originators: ["George Lane (stochastics)", "StockCharts ChartSchool (write-up)", "Colby & Meyers, Encyclopedia of Technical Market Indicators (cited study)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [15, 180]
timeframe: weekly
direction: long_short   # engine would use the long side only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# The 'Last' Stochastic technique (weekly 39-period)

## One-line summary
Weekly trend-following switch: go long when a 39-week stochastic crosses up through 50 and the week closes above the
prior week's highest close; exit when it crosses down through 50 and the week closes below the prior week's lowest close.

## Origin and lineage
- Stochastic oscillator: George Lane (1950s). The "Last" technique is presented on StockCharts ChartSchool, which says a
  study in *The Encyclopedia of Technical Market Indicators* rated the signals as very good. Who coined the name and
  the exact study numbers could not be verified (the Encyclopedia was not read).
- It uses the stochastic as a slow trend/momentum gauge (above or below mid-range of a 39-week window), not as an
  overbought/oversold oscillator.

## Exact rules (as published on ChartSchool)
- Data: weekly bars.
- Indicator: 39-period stochastic %K = (close - lowest low 39) / (highest high 39 - lowest low 39) x 100. ChartSchool
  shows a fast (unsmoothed) 39-week version and a slow 39-week version with 3-period SMA smoothing, which it prefers to
  cut whipsaws. The catalog row records "(39,1)"; treat smoothing as a parameter {1, 3}.
- Buy: %K crosses above 50 AND weekly close > the previous week's highest close (catalog wording; ChartSchool phrasing is
  "previous week's highest close" - read as close > prior week's close high, i.e. the prior weekly close).
- Sell: %K crosses below 50 AND weekly close < the previous week's lowest close.
- Confirmation (optional): On Balance Volume crossing above/below its 30-period moving average in the same direction.
- ChartSchool notes some stocks respond better to 40/60 crossings than 50; this is a per-symbol tuning invitation
  (overfitting trap, see below).
- No published stop, target, sizing or time exit. Entry order type unspecified; a weekly system implies next-week open.

## Why it should work
A 39-week stochastic above 50 means price sits in the upper half of its ~9-month range: a time-series momentum /
trend state. The other side is slow-moving holders and mean-reversion sellers; the edge, if any, is the generic
intermediate-horizon momentum premium (Moskowitz-Ooi-Pedersen 2012 for time-series momentum), not anything specific
to the stochastic formula.

## When it works and when it fails
- Works: long, persistent trends (single stocks in multi-month advances; ChartSchool examples MSFT, CSCO).
- Fails: range-bound names oscillating around mid-range (repeated 50 crossings), V-shaped crashes (weekly exit lags by
  1-3 weeks and can give back 15-25%), news gaps.

## Parameters and sensitivity
| Knob | Default | Sensible range | Note |
|---|---|---|---|
| stoch_len (weeks) | 39 | 26-52 | ~half to one year |
| smoothing | 3 (ChartSchool preference) | 1-3 | 1 = more whipsaws |
| cross level | 50 | 40-60 | per-stock levels = overfitting |
| OBV MA | 30 | 20-40 | optional filter |
Trap: choosing 40/60 per symbol after looking at its chart is in-sample fitting. Fix one level for the universe.

## Evidence
- ChartSchool: illustrative charts only; cites the Encyclopedia study qualitatively, no numbers given. Grade D.
- No independent test located. Indirect support from time-series momentum literature (Moskowitz, Ooi & Pedersen,
  JFE 2012), which is about 12-month returns on futures, not this rule.

## Common mistakes
- Using daily 39-period stochastics (a 2-month window, different system).
- Acting intra-week on an unfinished weekly bar (look-ahead in backtests).
- Ignoring the price confirmation leg and trading the oscillator cross alone.

## Discretionary parts and how to make them mechanical
- "Whipsaw avoidance": fix smoothing = 3 and the 50 level globally.
- OBV confirmation: OBV > SMA(OBV, 30) on the signal week, as a boolean filter variant.

## Implementation spec for swing-engine
- Weekly resample (W-FRI, last session of week; only completed weeks, forward-filled to daily rows from the next
  session): `wk_open, wk_high, wk_low, wk_close`.
- `stoch_k_39w = 100 * (wk_close - min(wk_low, 39)) / (max(wk_high, 39) - min(wk_low, 39))`; `stoch_ks_39w = SMA(stoch_k_39w, 3)`.
- Long entry: `stoch_ks_39w[t-1] <= 50 < stoch_ks_39w[t]` and `wk_close[t] > wk_close[t-1]` (prior week's close).
  Entry = next session open after the weekly close.
- Initial stop: not published. Engine choice: lowest weekly low of the last 2 weeks minus 0.1 x atr_14, capped at
  2.5 x atr_14 (weekly signals have wide natural stops; size via risk/sizing.py).
- Exit: weekly sell signal, or `stoch_ks_39w < 50` on a completed week (variant). No fixed target, so `min_reward_risk: 0.0`.
- max_hold_days: 180 (outside swing norm; flag for router).
- Reuses: nothing directly (no stochastic in the panel). Missing: weekly resample helper, `stoch_*_39w`, OBV
  (`obv`, `obv_sma_30`), `min_reward_risk` override.

## What the router should know
Slow trend state; at most a handful of signals per symbol per year. Better as a feature (weekly trend on/off) feeding
other strategies than as a standalone entry. Keep out of choppy and high_vol_selloff.

## Signs of decay to monitor
Rising whipsaw rate (signals reversed within 3 weeks), average holding period shrinking, give-back on exits > 50% of
peak open profit.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/the-last-stochastic-technique
- Moskowitz, Ooi & Pedersen, "Time Series Momentum", JFE 2012 (background only)

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 484 | 1 | 53% | +0.13 | +0.03 | -0.17 | 55% | +0.13 | +0.03 | -0.30 | 57% | +0.33 | +0.23 | -0.31 | 1.99 |
| correction | 135 | 0 | 73% | +0.18 | -0.06 | -0.24 | 56% | +0.17 | -0.07 | -0.36 | 67% | +0.28 | +0.03 | -0.51 | 2.36 |
| healthy_uptrend | 1411 | 7 | 49% | +0.03 | -0.06 | -0.12 | 47% | +0.01 | -0.08 | -0.17 | 41% | +0.03 | -0.06 | -0.21 | 1.07 |
| high_vol_selloff | 197 | 1 | 56% | +0.09 | -0.04 | -0.21 | 53% | +0.06 | -0.07 | -0.26 | 50% | +0.10 | -0.03 | -0.28 | 1.23 |
| narrow_uptrend | 134 | 1 | 46% | -0.00 | -0.10 | -0.07 | 45% | -0.04 | -0.13 | -0.11 | 37% | -0.19 | -0.29 | -0.47 | 0.67 |
| **all** | 2361 | 10 | 52% | +0.06 | -0.05 | -0.14 | 50% | +0.05 | -0.06 | -0.21 | 47% | +0.11 | +0.00 | -0.26 | 1.24 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 0%, avg -1.03R, PF 0.00, P&L $-325 on $100k, avg hold 8.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1549 | 10 | 43% | -0.15 | -0.24 | -0.20 | 39% | -0.19 | -0.28 | -0.25 | 37% | -0.20 | -0.29 | -0.29 | 0.64 |
| correction | 1652 | 10 | 56% | +0.07 | -0.04 | -0.11 | 57% | +0.13 | +0.02 | -0.12 | 52% | +0.16 | +0.05 | -0.08 | 1.45 |
| healthy_uptrend | 5497 | 58 | 49% | +0.02 | -0.08 | -0.10 | 49% | +0.04 | -0.06 | -0.11 | 43% | +0.02 | -0.08 | -0.18 | 1.04 |
| high_vol_selloff | 1155 | 12 | 56% | +0.06 | -0.07 | -0.17 | 52% | +0.02 | -0.11 | -0.18 | 49% | +0.06 | -0.07 | -0.23 | 1.14 |
| narrow_uptrend | 859 | 7 | 54% | +0.04 | -0.05 | -0.11 | 53% | +0.07 | -0.02 | -0.14 | 45% | +0.05 | -0.05 | -0.16 | 1.11 |
| **all** | 10712 | 97 | 51% | +0.01 | -0.09 | -0.13 | 49% | +0.02 | -0.08 | -0.14 | 45% | +0.02 | -0.09 | -0.18 | 1.03 |

Portfolio replay (net of costs, slots shared with its run): 16 trades, win 19%, avg -0.41R, PF 0.47, P&L $-2,386 on $100k, avg hold 64.4 bars.
