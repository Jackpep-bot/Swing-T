---
slug: elder_triple_screen
name: "Elder Triple Screen"
originators: ["Alexander Elder (Futures magazine 1986; Trading for a Living 1993; Come into My Trading Room 2002)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: weekly trend + daily setup + intraday/stop-order trigger
direction: long_short   # engine long side only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Elder Triple Screen

## One-line summary
Trade only in the direction of the weekly trend (weekly MACD-histogram slope), buy daily pullbacks against it
(2-day EMA of Force Index below zero), and enter with a buy stop above the prior day's high.

## Origin and lineage
Alexander Elder introduced it in *Futures* (1986) and expanded it in *Trading for a Living* (1993) and *Come into My
Trading Room* (2002). It formalises the multiple-timeframe idea: "tide" (weekly), "wave" (daily), "ripple" (entry).
Later Elder pieces (Impulse System, SafeZone stops) are add-ons.

## Exact rules (as summarized in the catalog; books not re-read this run)
- Screen 1, tide: weekly MACD-histogram (12,26,9). Rising slope (this week's value > last week's) = only longs.
  Early versions used the slope of a weekly EMA (commonly cited as 13-week; not verified).
- Screen 2, wave: daily oscillator moving against the tide. In a weekly uptrend: 2-day EMA of Force Index < 0
  (alternatives: stochastic oversold, Williams %R < -80, Elder-ray Bear Power negative but rising).
  Force Index = (close - prev_close) x volume.
- Screen 3, entry: buy stop one tick above the previous day's high. If not filled, move it down to one tick above the
  latest day's high each day until filled or the setup is void (tide turns or wave reverses).
- Initial stop: below the lower of the entry day's low and the previous day's low (later: SafeZone stop).
- Exit: not a single fixed rule; channel/envelope targets or when the impulse turns (catalog). Treat as unspecified.
- Money management: risk at most 2% of equity per trade; stop trading for the month after a 6% equity drawdown
  (2002 book; not fetched this run, unverified).

## Why it should work
Combines intermediate-term momentum (weekly trend) with short-term reversal (buy a 1-3 day dip): both documented
effects (Jegadeesh 1990 short-term reversal; momentum). The buy stop ensures price has turned before entry. Counterparty:
short-term sellers liquidating into a dip inside a trend.

## When it works and when it fails
- Works: orderly uptrends with 2-4 day pullbacks.
- Fails: weekly MACD-histogram slope flips frequently in ranges (whipsaw on the tide); gaps through the buy stop in
  volatile markets; deep pullbacks that become trend reversals.

## Parameters and sensitivity
| Knob | Default | Range |
|---|---|---|
| weekly MACD | 12,26,9 | fixed |
| Force Index EMA | 2 | 2-3 |
| setup expiry | until tide flips | 3-5 sessions (engine choice) |
| stop | lower of two lows | + 0.1 x atr_14 buffer |
Trap: picking the "best" of the four alternative oscillators after testing all four = multiple testing; log each as a trial.

## Evidence
- No peer-reviewed or vendor test of the full system found. Forum/platform tests vary wildly: a Wealth-Lab forum thread
  reports Triple Screen losing over 1990-2013 on its dataset; an anonymous QuantConnect backtest (2017-2019) shows 58%
  wins, 2.60% avg win vs 1.64% avg loss. Neither is audited; both are search-snippet level. Grade D.
- Component evidence: short-term reversal inside momentum supports the pullback family (methods/01, B-).

## Common mistakes
- Using the weekly MACD level (above zero) instead of its slope.
- Computing the weekly slope with the current, unfinished week (look-ahead in backtests; Elder used it live).
- Using a market order on the setup day instead of the trailing buy stop.

## Discretionary parts and how to make them mechanical
- Exit: pick one: target = upper envelope (EMA22 + channel, not specified here) or trail under the prior 2-day low; log
  as variants.
- Oscillator choice: fix Force Index EMA(2) as the primary.

## Implementation spec for swing-engine
- Weekly (W-FRI, completed weeks only, forward-filled): `wk_macd_hist` from weekly closes; `tide_up = wk_macd_hist[w] > wk_macd_hist[w-1]`.
- Daily: `force_1 = (close - prev_close) * volume`; `fi_ema2 = EMA(force_1, 2)`.
- Setup on day t: `tide_up` and `fi_ema2 < 0`.
- Entry: buy stop at `high[t] + 0.01`, valid next session; if unfilled, re-arm at the new day's high while setup holds,
  max 3 re-arms (engine choice). Without a stop-entry hook, approximate with "enter next session if high > prior high,
  fill at max(open, prior_high + 0.01)" in replay only.
- Stop: `min(low[entry_day], low[entry_day-1]) - 0.1 * atr_14`.
- Target: 2R (engine default) or Landry-style half at 1R and trail; exit on `tide_up` turning false.
- max_hold_days: 20; min_reward_risk: 2.0 (engine default) for the fixed-target variant.
- Reuses: `macd*` (daily only), `atr_14`, `prev_close`. Missing: weekly resample + weekly MACD, Force Index,
  stop-entry order hook, intraday trigger.

## What the router should know
A pullback-family setup with a weekly filter: same regimes as pullback_trend (healthy and narrow uptrends). Overlaps
heavily with pullback_trend / pullback_holy_grail signals; compare overlap before allowing both.

## Signs of decay to monitor
Fill rate of buy stops falling (dips keep extending), share of stops hit within 2 days, tide flip frequency.

## Sources
- https://www.tradingview.com/scripts/triplescreen/
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/force-index
- https://wl6.wealth-lab.com/Forum/Posts/Original-Turtle-and-Triple-Screen-backtesting-results-33566 (forum, unaudited)
- https://www.quantconnect.com/terminal/cache/embedded_backtest_8cdd33d2291c33ba7acaa23fe598624b.html (anonymous, unaudited)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 27699 | 17147 | 45% | +0.01 | -0.25 | 41% | +0.03 | -0.23 | 39% | +0.05 | -0.21 | 1.08 |
| correction | 3327 | 1687 | 57% | +0.51 | -0.15 | 55% | +0.57 | -0.09 | 54% | +0.57 | -0.09 | 2.07 |
| healthy_uptrend | 88015 | 56958 | 40% | -0.08 | -0.33 | 36% | -0.08 | -0.34 | 34% | -0.08 | -0.33 | 0.90 |
| high_vol_selloff | 8292 | 5096 | 41% | -0.14 | -0.36 | 38% | -0.10 | -0.32 | 36% | -0.12 | -0.34 | 0.84 |
| narrow_uptrend | 7661 | 4898 | 36% | -0.19 | -0.44 | 33% | -0.19 | -0.44 | 30% | -0.20 | -0.46 | 0.75 |
| **all** | 134994 | 85786 | 41% | -0.05 | -0.32 | 38% | -0.04 | -0.31 | 36% | -0.04 | -0.30 | 0.95 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 74166 | 49141 | 44% | +0.01 | -0.21 | 41% | +0.04 | -0.18 | 38% | +0.05 | -0.17 | 1.07 |
| correction | 56887 | 35166 | 48% | +0.10 | -0.16 | 44% | +0.13 | -0.13 | 41% | +0.12 | -0.14 | 1.19 |
| healthy_uptrend | 264892 | 173056 | 41% | -0.06 | -0.30 | 37% | -0.06 | -0.30 | 35% | -0.05 | -0.30 | 0.93 |
| high_vol_selloff | 46874 | 31599 | 37% | -0.19 | -0.43 | 33% | -0.19 | -0.43 | 31% | -0.19 | -0.43 | 0.75 |
| narrow_uptrend | 64267 | 41402 | 44% | +0.03 | -0.21 | 41% | +0.06 | -0.18 | 38% | +0.07 | -0.17 | 1.11 |
| **all** | 507086 | 330364 | 42% | -0.03 | -0.27 | 38% | -0.02 | -0.26 | 36% | -0.01 | -0.25 | 0.98 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
