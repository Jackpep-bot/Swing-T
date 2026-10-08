---
slug: santa_claus_rally
name: Santa Claus rally window
originators: [Yale Hirsch (Stock Trader's Almanac, 1972), Jeffrey Hirsch]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [7, 7]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Santa Claus rally window

## One-line summary
Long the index over the last 5 trading days of December plus the first 2 of January (7 sessions).

## Origin and lineage
Defined by Yale Hirsch in the Stock Trader's Almanac (first edition 1972). Almanac lore: "if Santa fails to call,
bears may come to Broad and Wall" (failed window as a bearish omen for the new year).

## Exact rules
- Instrument: S&P 500 index (SPY).
- Entry: close of the 6th-to-last December session (so the window covers the last 5 December sessions).
- Exit: close of the 2nd January session. No stop, no target, sizing unspecified.

## Why it should work
Proposed: holiday optimism, light institutional participation, year-end bonus/pension inflows, end of tax-loss
selling. No verified mechanism; it overlaps the turn-of-year and turn-of-month effects.

## When it works and when it fails
Weak when the market enters December in a correction or high-vol regime. The "omen" use is anecdotal.

## Parameters and sensitivity
Window boundaries are fixed by definition; changing them is data mining. One event per year: ~75 events since 1950,
so the standard error of the mean is large relative to a 1.3% average.

## Evidence
- Almanac figure (via multiple secondary sources, search 2026-10-07): S&P 500 averaged about **+1.3%** over the window
  since 1950. Not cost-tested. Frequency of positive windows is often quoted near 75-80%; **not verified** this session.
- No peer-reviewed test of this exact 7-day window located. Related turn-of-month/turn-of-year effects: about 0.55% per
  4-day window (methods.md, seasonality row, grade B- small).

## Common mistakes
Over-sizing on a single annual event; treating a failed window as a sell signal.

## Implementation spec for swing-engine
- Feature `santa_window` = 1 for sessions in [6th-to-last December session close, 2nd January session close]
  computed from `data/calendar.py: trading_days`.
- Use: calendar flag/tie-breaker. Replay variant: SPY long, entry at the close before the window (needs MOC hook; with
  next-open fills, enter at the open of the first window session), exit at the 2nd January close,
  `max_hold_days = 7`, catastrophic stop `3 * atr_14`.
- Missing: `calendar_flags` feature module.

## What the router should know
Tie-breaker only; do not override `correction` (no new longs).

## Signs of decay to monitor
10-year rolling mean window return below the unconditional 7-day SPY mean.

## Sources
- https://www.bankrate.com/investing/santa-claus-rally-in-stocks
- https://id.tradingview.com/chart/SPY/TsFA1ueC-Santa-Claus-Rally-Defined-for-2020
- https://en.wikipedia.org/wiki/Santa_Claus_rally
- https://harbourfrontquant.substack.com/p/do-calendar-anomalies-still-work

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 1 | 0 | 0% | -0.29 | -0.37 | 100% | +0.07 | -0.01 | 100% | +0.06 | -0.02 | inf |
| narrow_uptrend | 1 | 0 | 0% | -0.52 | -0.68 | 0% | -0.34 | -0.50 | 0% | -1.07 | -1.22 | 0.00 |
| **all** | 2 | 0 | 0% | -0.41 | -0.52 | 50% | -0.14 | -0.25 | 50% | -0.51 | -0.62 | 0.06 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| correction | 1 | 0 | 100% | +0.13 | +0.09 | 100% | +0.37 | +0.34 | 100% | +0.93 | +0.90 | inf |
| healthy_uptrend | 4 | 0 | 75% | +0.12 | +0.02 | 100% | +0.70 | +0.61 | 100% | +1.76 | +1.66 | inf |
| narrow_uptrend | 1 | 0 | 100% | +0.15 | +0.01 | 0% | -0.31 | -0.45 | 0% | -1.07 | -1.22 | 0.00 |
| **all** | 6 | 0 | 83% | +0.12 | +0.03 | 83% | +0.48 | +0.39 | 83% | +1.15 | +1.06 | 7.41 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
