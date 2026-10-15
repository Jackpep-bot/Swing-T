---
slug: sykes_first_green_day
name: First green day (Tim Sykes) after a small-cap runner has sold off three-plus sessions, hold overnight to the next close
originators: [Timothy Sykes, "First Green Day" pattern (blog and courses)]
category: strategy
decision: implement
holding_period_days: [1, 2]
timeframe: daily bars
direction: long
universe: store stocks, close $1-$20, med_dv_63 >= $1M, mcap_pit <= $2B
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog; parabolic_short_long_reversal was marked avoid as an intraday method)
---

# First green day

## Why this one is new
The catalog avoided the intraday parabolic-reversal family. This is its daily-bar long side as taught to
small-cap traders: a stock that ran hard, then bled for several days, prints its first strong green candle; buyers
hold it overnight for a gap up. It targets exactly the small, volatile names Jack said are fine, and it is the
kind of method the most-followed small-cap educators sell.

## One-line summary
After a stock doubles within a month and then falls at least 30% over three or more red days, buy the first day it
closes green near its high on above-average volume; sell at the next close.

## Origin and lineage
- https://www.timothysykes.com/blog/first-green-day-pattern/ (opened): a big green daily candle after a stock was
  "beaten down or stuck in consolidation", closing near the high on above-average volume, ideally with news; he buys
  before the close, holds overnight only on a strong close, sells into the next morning's spike, exits at once on a
  gap down. No numbers given.

## Exact rules (as published)
None numeric. Every threshold below is mine.

## Engine version (pre-register this one)
- Runner (F): max close over t-25..t-3 >= 2.0 x min close over the 20 sessions before that peak (a double).
- Selloff (F): at least 3 consecutive down closes ending at t-1, and close(t-1) <= 0.70 x that peak close.
- First green day (F): close(t) > open(t), close(t) > close(t-1), `close_pos` >= 0.75, volume(t) >= 1.5 x 20-session
  average volume.
- Entry (registered deviation): the engine fills at the next open, which loses the overnight gap Sykes holds for. If
  the engine supports market-on-close fills, use the signal-day close and record it; otherwise next open, and the card
  becomes a test of day-2 follow-through.
- Exit: close of the session after entry (fallback next open). Stop: signal-day low.
- Exclusions: `event_avoid_filters` (reverse splits are common in this group). Max 5 open, equal risk.

## Grading
Batch standard.

## Evidence
No statistics anywhere; a neutral explainer says the pattern "does not have documented statistical edge"
(https://curvedtrading.com/articles/en/trading/first-green-day-small-cap-continuation-pattern/, opened). The large-move
literature points the other way for continuation (an Aalto thesis on US stocks 2010-2024 finds significant negative
abnormal returns 1-21 days after +20% days: https://aaltodoc3.org.aalto.fi/items/323aea28-873b-40ef-ac56-e26143d10c32/full,
opened), but this card buys after the selloff, where short-term reversal works in its favour. Grade D.

## Expectation stated before the run
Few signals (tens a year), fat-tailed, likely negative net because of spreads in $1-$5 names.

## Common mistakes
Split-adjusted prices hiding a reverse split (gives a fake "runner"); trading names under $1M daily dollar volume.

## Signs of decay to monitor
Trailing 50-trade mean net R <= 0.
