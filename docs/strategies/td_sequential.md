---
slug: td_sequential
name: DeMark TD Sequential (setup 9, countdown 13)
originators: [Tom DeMark (The New Science of Technical Analysis, 1994; DeMark Indicators, 2008 with J. Perl)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# DeMark TD Sequential

## One-line summary
Count exhaustion: 9 consecutive closes below the close 4 bars earlier (setup), then 13 non-consecutive closes at or
below the low 2 bars earlier (countdown); buy on countdown completion.

## Origin and lineage
Tom DeMark (1980s, published 1994). thinkorswim ships it as `SequenceCounter`; TD Combo is a sibling. Rules below are
the standard public definition (nexusfi page in methods.md returned 403 this session; setup/countdown definitions
confirmed via oxfordstrat.com; perfection, TDST and risk-level details are from DeMark's published definitions as
commonly reproduced and were **not re-verified against the book**).

## Exact rules (buy side; sell is the mirror)
- Price flip: prior bar close > close 4 bars before it, current close < close 4 bars before.
- Buy setup: 9 consecutive closes < close 4 bars earlier (bar 1 = flip bar). Interrupted -> restart.
- Perfection: low of bar 8 or 9 <= lows of bars 6 and 7 (otherwise "imperfect"; wait).
- TDST: highest high of the buy setup = resistance; a close above it cancels the countdown.
- Countdown: from setup bar 9 onward, count bars with close <= low 2 bars earlier; need 13 (not consecutive).
  Qualifier: low of countdown bar 13 <= close of countdown bar 8, else defer ("13+").
- Cancellation/recycle: an opposite (sell) setup cancels; a new buy setup may restart the countdown (recycle rules vary).
- Entry: on countdown 13 (aggressive) or setup 9 (short-term); oxfordstrat's test enters on the close when close > close 4 bars earlier.
- Stop (TD risk level): lowest low of the countdown minus that bar's true range.
- Target / time exit: not fixed; DeMark expects a 1-4 bar reaction after setup 9 and a larger reversal after 13.

## Why it should work
Exhaustion: after a long sequence of lower closes, the marginal seller is used up. Counterparty: trend-followers
and capitulating holders. Equally, a counting rule fires inside strong trends (persistent sell pressure), so it fights trend.

## When it works and when it fails
Works in ranges and late in mature pullbacks within uptrends. Fails in persistent bear trends (multiple 13s in a row)
and crash regimes.

## Parameters and sensitivity
Setup length 9, lookback 4, countdown 13, countdown lookback 2. oxfordstrat varied countdown length 6-25 and exit
time 1-40 days. Trap: every variant (perfection, deferral, recycle) is a degree of freedom.

## Evidence
- oxfordstrat.com: 42 US futures markets, 1980-2013, 1% fixed-fractional with 6-ATR stops, fixed time exits; results
  shown only as sensitivity charts, no headline numbers in text. No equity test with statistics located.
- No peer-reviewed study located. Grade D.

## Common mistakes
Buying setup 9 in a downtrend expecting a major low; ignoring the bar-13 qualifier; no stop.

## Implementation spec for swing-engine
- New features (per symbol, causal loop over closes): `td_buy_setup_count` (0-9), `td_buy_perfected` (0/1),
  `td_tdst` (highest high of the last completed buy setup), `td_buy_countdown` (0-13, with qualifier and cancellation
  on close > td_tdst or a sell setup 9), `td_risk_level`.
- Signal: `td_buy_countdown == 13` on bar t; variant B: `td_buy_setup_count == 9 and td_buy_perfected` with `trend_state >= 0`.
- Entry next open. Stop `td_risk_level` (cap at `entry - 3 * atr_14`). Target `td_tdst` if above entry.
  Exit: target, stop, close < stop, or `max_hold_days = 10` (setup 9) / 20 (countdown 13). `min_reward_risk = 1.0`.
- Missing: the counter feature (loop; vectorize with numba or a per-symbol numpy pass). Short side not supported by
  `PanelStrategy.build_signal` (long only).

## What the router should know
Counter-trend: treat like mean reversion (choppy/narrow_uptrend only, reduced size).

## Signs of decay to monitor
Countdown-13 trades with win rate < 45% and payoff < 1.3.

## Sources
- https://nexusfi.com/a/indicators/td-sequential-demark-indicators
- https://oxfordstrat.com/?p=9037
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/SequenceCounter
- https://www.mql5.com/en/blogs/post/748846

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 251 | 4 | 53% | +0.05 | -0.05 | 54% | +0.11 | +0.01 | 50% | +0.21 | +0.11 | 1.48 |
| correction | 33 | 1 | 53% | -0.14 | -0.26 | 44% | -0.12 | -0.24 | 53% | +0.18 | +0.05 | 1.39 |
| healthy_uptrend | 951 | 29 | 45% | +0.01 | -0.12 | 42% | -0.02 | -0.15 | 36% | -0.06 | -0.19 | 0.90 |
| high_vol_selloff | 289 | 9 | 60% | +0.18 | +0.08 | 60% | +0.34 | +0.23 | 55% | +0.47 | +0.36 | 2.27 |
| narrow_uptrend | 185 | 7 | 40% | -0.18 | -0.31 | 28% | -0.35 | -0.48 | 28% | -0.27 | -0.41 | 0.63 |
| **all** | 1709 | 50 | 49% | +0.02 | -0.10 | 46% | +0.03 | -0.09 | 41% | +0.06 | -0.06 | 1.11 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1140 | 27 | 45% | -0.05 | -0.16 | 45% | +0.02 | -0.09 | 39% | +0.05 | -0.06 | 1.09 |
| correction | 944 | 20 | 63% | +0.26 | +0.17 | 61% | +0.36 | +0.27 | 59% | +0.49 | +0.41 | 2.33 |
| healthy_uptrend | 2198 | 84 | 48% | -0.01 | -0.13 | 43% | -0.04 | -0.15 | 36% | -0.09 | -0.21 | 0.84 |
| high_vol_selloff | 2411 | 104 | 50% | +0.04 | -0.07 | 50% | +0.08 | -0.03 | 43% | +0.07 | -0.04 | 1.14 |
| narrow_uptrend | 944 | 32 | 57% | +0.16 | +0.06 | 52% | +0.19 | +0.09 | 46% | +0.18 | +0.07 | 1.37 |
| **all** | 7637 | 267 | 51% | +0.05 | -0.05 | 49% | +0.09 | -0.02 | 43% | +0.09 | -0.02 | 1.17 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
