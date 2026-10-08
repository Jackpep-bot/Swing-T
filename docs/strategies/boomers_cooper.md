---
slug: boomers_cooper
name: Boomers (two inside days in an ADX > 30 trend; Jeff Cooper)
originators: [Jeff Cooper (Hit and Run Trading ch. 11; Hit and Run Trading II)]
category: trend_pause_breakout
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long            # Cooper teaches the short mirror; swing-engine strategies are long-only
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built          # inside_day and adx_14 / plus_di_14 / minus_di_14 exist; no module
---

# Boomers (Cooper)

## One-line summary
In a strong trend (ADX > 30, +DI > -DI), two consecutive inside days mark a pause; buy a stop just above the second
inside day's high with the stop just under its low, expecting the trend to resume.

## Origin and lineage
Jeff Cooper, *Hit and Run Trading* (1996) ch. 11, and *Hit and Run Trading II* (extended-level Boomers). Shares the
ADX > 30 trend gate with Raschke's Holy Grail (`pullback_holy_grail`) and the inside-day contraction idea with Crabel
(`nr7_nr4_range_contraction.md`).

## Exact rules
- Basic Boomer buy: ADX(14) > 30 with +DI > -DI; the stock makes two consecutive inside days; next day buy stop 10
  cents above the second inside day's high; initial stop 10 cents below the second inside day's low.
- Extended-level Boomer: day 1 is a new 60-day high; the next two or more days are inside day 1's range; buy stop 1
  tick above the day-1 high; cancel if price trades below the day-1 low; once filled, trail a stop.
- Trend gate alternative (search summary): if ADX is not used, RS above 95.
- Exit: "a few days; trail" in the summaries; no fixed target.
- Shorts mirror. Sizing: not taught in the summaries read.

## Why it should work
A strong trend that pauses without giving ground (inside days) shows holders are not selling; the break of the pause
re-engages momentum buyers. Stops placed beyond the tight range give very small risk per share.

## When it works and when it fails
Works in persistent trends (high ADX) in a healthy tape. Fails at trend exhaustion (ADX very high and rolling over) and
in choppy markets, where inside-day breaks reverse.

## Parameters and sensitivity
ADX threshold 25-35; inside-day count (2 vs 3); "inside" vs day-1 (extended) or vs each prior day (basic); buffer
($0.10 vs 1 tick or % of ATR). Trap: the $0.10 buffer is large for $10 stocks and tiny for $500 stocks; scale it.

## Evidence
None beyond author examples. Rules come from scan-forum and screener summaries, not the book.

## Common mistakes
Fixed-cent buffers across price levels; ignoring that tiny stops get hit by noise (size limited by
`max_position_pct`, not by risk).

## Discretionary parts and how to make them mechanical
"Two consecutive inside days" (basic): `inside_day_t and inside_day_{t-1}` (each inside its prior bar). Extended:
`high[t-k..t] < high_{t-k-1}` and `low[t-k..t] > low_{t-k-1}` for k >= 1 with bar t-k-1 at a 60-day high.

## Implementation spec for swing-engine
- Reuse: `inside_day` (patterns.py: `high < prev_high and low > prev_low`), `adx_14`, `plus_di_14`, `minus_di_14`
  (patterns2.py, Wilder 14), `atr_14`, `rs_63d_rank` (RS variant: >= 0.95).
- New feature: `inside_streak` = count of consecutive inside days ending at t; `high_60` (rolling max of high,
  60 bars, inclusive) for the extended variant.
- Setup at close t (basic): `inside_streak_t >= 2`, `adx_14_t > 30`, `plus_di_14_t > minus_di_14_t`.
- Entry: buy stop `high_t + BUFFER`, BUFFER = max(0.01, 0.05 x atr_14) as a versioned param (Cooper: $0.10).
  **Missing hook**: stop-entry fill at `max(open_{t+1}, trigger)` if `high_{t+1} >= trigger`; extended variant also
  needs a resting order cancelled on a trade below the day-1 low.
- Stop: `low_t - BUFFER`. Target: reference 2R. Exits: `max_hold_days: 5`, breakeven at +1R and the default trail.
- Same-bar fill and stop: assume stopped (worst case).

## What the router should know
Trend-continuation; `healthy_uptrend` only if enabled. Signals are rare (two inside days plus ADX > 30), so it adds
little capacity.

## Signs of decay to monitor
Fill rate and 1R hit rate; if fewer than 40% of fills reach +1R before the stop over 50 trades, drop it.

## Sources
- https://scan.stockcharts.com/discussion/comment/6225/ (unreachable at fetch time, 2026-10-07)
- https://swingtradebot.com/stock-screens/definitions
- https://technical.traders.com/tradersonline/display.asp?art=2697

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 104 | 55 | 37% | +0.00 | -0.37 | 37% | +0.11 | -0.27 | 37% | +0.12 | -0.26 | 1.18 |
| correction | 6 | 3 | 0% | -1.09 | -1.83 | 0% | -1.09 | -1.83 | 0% | -1.09 | -1.83 | 0.00 |
| healthy_uptrend | 456 | 214 | 29% | -0.30 | -0.72 | 26% | -0.31 | -0.73 | 26% | -0.29 | -0.72 | 0.63 |
| high_vol_selloff | 33 | 17 | 25% | -0.53 | -0.82 | 19% | -0.59 | -0.88 | 19% | -0.65 | -0.94 | 0.33 |
| narrow_uptrend | 33 | 16 | 21% | -0.45 | -0.84 | 21% | -0.45 | -0.84 | 21% | -0.45 | -0.84 | 0.44 |
| **all** | 632 | 305 | 30% | -0.28 | -0.69 | 27% | -0.27 | -0.69 | 27% | -0.26 | -0.67 | 0.67 |

Portfolio replay (net of costs, slots shared with its run): 110 trades, win 26%, avg -0.51R, PF 0.39, P&L $-2,558 on $100k, avg hold 2.5 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 318 | 142 | 36% | -0.11 | -0.44 | 34% | -0.09 | -0.42 | 33% | -0.08 | -0.41 | 0.90 |
| correction | 185 | 97 | 32% | -0.28 | -0.69 | 24% | -0.37 | -0.78 | 23% | -0.40 | -0.81 | 0.53 |
| healthy_uptrend | 1998 | 949 | 34% | -0.16 | -0.55 | 33% | -0.15 | -0.54 | 32% | -0.15 | -0.54 | 0.81 |
| high_vol_selloff | 134 | 63 | 32% | -0.18 | -0.58 | 30% | -0.16 | -0.55 | 30% | -0.14 | -0.54 | 0.80 |
| narrow_uptrend | 303 | 138 | 45% | +0.03 | -0.34 | 42% | +0.13 | -0.24 | 41% | +0.12 | -0.25 | 1.19 |
| **all** | 2938 | 1389 | 36% | -0.14 | -0.52 | 33% | -0.13 | -0.51 | 32% | -0.13 | -0.51 | 0.83 |

Portfolio replay (net of costs, slots shared with its run): 520 trades, win 29%, avg -0.31R, PF 0.57, P&L $-16,492 on $100k, avg hold 2.7 bars.
