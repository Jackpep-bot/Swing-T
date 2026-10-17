---
slug: pendergast_swingthree
name: SwingThree (Donald Pendergast)
originators: [Donald Pendergast (S&C Dec 2013), thinkorswim built-in implementation]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]     # estimate: exit on first close-range low below SMA(low); not published
timeframe: daily
direction: long_only_in_engine (original is long and short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# SwingThree (Pendergast)

## One-line summary
Trend-aligned channel breakout: in an uptrend (prior close above EMA50), buy when price clears the SMA-of-highs band by a
small offset; exit when the low no longer holds above the SMA-of-lows band.

## Origin and lineage
Donald Pendergast, Technical Analysis of Stocks & Commodities, Dec 2013; carried as a thinkorswim built-in strategy.
Intended for volatile, high-volume stocks and ETFs with smooth, regular swings.

## Exact rules (thinkorswim documentation)
- Trend filter: EMA(close, 50) (input `ema length`, default 50). Long only when the **previous** bar closed above it.
- Signal lines: SMA(high, n) and SMA(low, n); `sma length` n default **not published in the TOS docs** (unverified).
- Long entry: price exceeds SMA(high, n) + k ticks, k = 5 by default (emulates a stop order above the band).
- Long exit: when the low fails to stay above SMA(low, n).
- Short (not used in engine): price < SMA(low, n) - k ticks with prior close below EMA50; cover when high > SMA(high, n).
- No initial stop, target or sizing rule in the TOS version.

## Why it should work
Short-term continuation inside an established trend: a push above the recent average high in an uptrend tends to attract
breakout buyers; the SMA(low) exit is a volatility-scaled trailing stop. The other side is short-term mean-reversion sellers.

## When it works and when it fails
Smooth trending names (low noise relative to the band width). Fails in ranges, where the band breakout reverses within a
bar or two and the exit triggers immediately (many small losses).

## Parameters and sensitivity
n (unknown default; try 3-10 with 5 as the engine default, flagged as an assumption), EMA 30-100, offset 0-0.5% of price.
Short n plus a 5-tick offset makes trade count very sensitive to price level; convert ticks to % of price.

## Evidence
Only the in-sample S&C illustration (grade D). No independent test found. Broker publishes no statistics.

## Common mistakes
Applying 5 cents equally to a $10 and a $500 stock; ignoring the prior-bar EMA condition; using intraday high touches for
entry while the backtester only fills at the open.

## Discretionary parts and how to make them mechanical
Candidate selection ("volatile, liquid, smooth swings") -> universe filter (settings) plus adr_pct_20 >= 2% and
trend_state = 1.

## Implementation spec for swing-engine
- Module `strategies/swingthree.py`, `@register("strategy")`.
- Features: compute `sma_high_n`, `sma_low_n`, `ema_50` in-module (only sma/ema of close exist in the panel; ema_50 missing).
  Reuses adr_pct_20, atr_14, trend_state.
- Signal at close t: `close[t-1] > ema_50[t-1]` and `close[t] > sma_high_n[t] * (1 + offset_pct)`, offset_pct default 0.1%
  (stands in for 5 ticks). The original fires intrabar; the engine fires on the close and enters next open.
  A **stop-entry order hook** would allow the faithful version (buy stop at sma_high_n + offset).
- Stop: max(sma_low_n[t], entry - 2 x atr_14) below entry. Target: None.
  `should_exit`: `low[t] <= sma_low_n[t]` (exit on the close; original exits intrabar).
- `max_hold_days`: 20. `min_reward_risk`: not applied (no target).
- settings.yaml: `swingthree: {enabled: false, shadow_only: true, sma_length: 5, ema_length: 50, offset_pct: 0.1}`.

## What the router should know
Comparison-only S&C system. Overlaps with `pullback_trend` and `sr_breakout` (trend + short breakout); use replay to see
whether it adds anything over them.

## Signs of decay to monitor
Average holding period shrinking toward 1-2 days and win rate below 35% in replay mean the band is inside noise.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SwingThree

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 7994 | 99 | 49% | +0.06 | -0.08 | -0.25 | 43% | +0.09 | -0.06 | -0.27 | 36% | +0.21 | +0.06 | -0.32 | 1.34 |
| correction | 997 | 18 | 40% | -0.08 | -0.33 | -0.51 | 37% | -0.09 | -0.34 | -0.81 | 28% | -0.11 | -0.35 | -1.11 | 0.84 |
| healthy_uptrend | 39412 | 454 | 43% | -0.04 | -0.19 | -0.18 | 38% | -0.01 | -0.16 | -0.16 | 31% | +0.04 | -0.11 | -0.14 | 1.06 |
| high_vol_selloff | 3340 | 72 | 49% | +0.02 | -0.16 | -0.27 | 40% | -0.03 | -0.21 | -0.40 | 27% | -0.15 | -0.32 | -0.51 | 0.80 |
| narrow_uptrend | 3030 | 37 | 38% | -0.18 | -0.34 | -0.25 | 30% | -0.25 | -0.41 | -0.30 | 22% | -0.31 | -0.48 | -0.45 | 0.59 |
| **all** | 54773 | 680 | 44% | -0.03 | -0.18 | -0.20 | 39% | -0.01 | -0.17 | -0.21 | 31% | +0.04 | -0.12 | -0.22 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 24210 | 241 | 49% | +0.04 | -0.11 | -0.17 | 46% | +0.13 | -0.02 | -0.16 | 40% | +0.23 | +0.08 | -0.14 | 1.39 |
| correction | 10601 | 79 | 46% | -0.03 | -0.21 | -0.24 | 41% | -0.05 | -0.22 | -0.32 | 34% | +0.01 | -0.16 | -0.30 | 1.02 |
| healthy_uptrend | 122498 | 1507 | 45% | -0.02 | -0.17 | -0.19 | 39% | -0.03 | -0.19 | -0.21 | 32% | -0.03 | -0.18 | -0.24 | 0.95 |
| high_vol_selloff | 16812 | 184 | 48% | +0.01 | -0.16 | -0.14 | 43% | -0.01 | -0.18 | -0.14 | 35% | -0.03 | -0.20 | -0.16 | 0.95 |
| narrow_uptrend | 21190 | 184 | 48% | +0.03 | -0.13 | -0.22 | 42% | +0.02 | -0.14 | -0.25 | 35% | +0.01 | -0.15 | -0.32 | 1.01 |
| **all** | 195311 | 2195 | 46% | -0.01 | -0.16 | -0.19 | 41% | -0.01 | -0.16 | -0.21 | 34% | +0.01 | -0.15 | -0.23 | 1.01 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
