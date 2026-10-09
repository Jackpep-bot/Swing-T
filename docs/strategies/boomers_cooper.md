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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 106 | 57 | 37% | +0.00 | -0.37 | 37% | +0.11 | -0.27 | 37% | +0.12 | -0.26 | 1.18 |
| correction | 6 | 3 | 0% | -1.09 | -1.83 | 0% | -1.09 | -1.83 | 0% | -1.09 | -1.83 | 0.00 |
| healthy_uptrend | 457 | 215 | 29% | -0.30 | -0.72 | 26% | -0.31 | -0.73 | 26% | -0.29 | -0.72 | 0.63 |
| high_vol_selloff | 33 | 17 | 25% | -0.53 | -0.82 | 19% | -0.59 | -0.88 | 19% | -0.65 | -0.94 | 0.33 |
| narrow_uptrend | 33 | 16 | 21% | -0.45 | -0.84 | 21% | -0.45 | -0.84 | 21% | -0.45 | -0.84 | 0.44 |
| **all** | 635 | 308 | 30% | -0.28 | -0.69 | 27% | -0.27 | -0.69 | 27% | -0.26 | -0.67 | 0.67 |

Portfolio replay (net of costs, slots shared with its run): 3 trades, win 0%, avg -1.03R, PF 0.00, P&L $-960 on $100k, avg hold 1.7 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 373 | 173 | 34% | -0.18 | -0.54 | 34% | -0.12 | -0.48 | 32% | -0.11 | -0.47 | 0.84 |
| correction | 232 | 125 | 29% | -0.33 | -0.81 | 24% | -0.38 | -0.86 | 23% | -0.39 | -0.87 | 0.54 |
| healthy_uptrend | 2419 | 1181 | 34% | -0.17 | -0.62 | 32% | -0.17 | -0.61 | 31% | -0.16 | -0.61 | 0.79 |
| high_vol_selloff | 176 | 82 | 34% | -0.17 | -0.66 | 29% | -0.21 | -0.70 | 30% | -0.19 | -0.69 | 0.74 |
| narrow_uptrend | 312 | 145 | 43% | +0.01 | -0.38 | 41% | +0.11 | -0.29 | 40% | +0.10 | -0.30 | 1.15 |
| **all** | 3512 | 1706 | 34% | -0.16 | -0.60 | 32% | -0.15 | -0.59 | 31% | -0.15 | -0.59 | 0.81 |

Portfolio replay (net of costs, slots shared with its run): 50 trades, win 28%, avg -0.27R, PF 0.63, P&L $-2,812 on $100k, avg hold 2.5 bars.
