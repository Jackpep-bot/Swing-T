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
_Pending: filled in from swing replay on real data._
