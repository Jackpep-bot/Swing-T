---
slug: pre_earnings_runup_winners
name: Pre-earnings run-up of past winners, buy the top 1% by 12-month return 4 sessions before the report, sell before it
originators: [Aboody, Lehavy & Trueman, "Limited attention and the earnings announcement returns of past stock market winners", Review of Accounting Studies 15(2) 2010]
category: strategy
decision: implement
holding_period_days: [3, 5]
timeframe: daily bars + earnings dates (point-in-time expected date)
direction: long
universe: all store stocks with close >= $5 and med_dv_63 >= $1M (published universe is all US stocks above $5)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog)
---

# Pre-earnings run-up of past winners

## Why this one is new
`earnings_announcement_premium` holds THROUGH the report (and failed; batch 3 README). This card exits before the
report and only holds extreme past winners, where retail attention buying peaks just ahead of the date and the
published result is a reversal after it.

## One-line summary
Four sessions before an expected earnings report, buy stocks in the top 1% of 12-month return; sell at the close of
the last session before the report.

## Origin and lineage
- Aboody, Lehavy & Trueman 2010 (https://ideas.repec.org/a/spr/reaccs/v15y2010i2d10.1007_s11142-009-9104-9.html;
  summaries opened: https://alphaarchitect.com/go-long-make-money-go-short-make-money-all-good/ and
  https://www.cxoadvisory.com/animal-spirits/returns-of-high-momentum-stocks-around-earnings-announcements).

## Exact rules (as published)
Price > $5. Rank all stocks on 12-month return at the end of the prior calendar quarter; take the top 1%. Buy at the
close of day -5 (so the return covers days -4..0), sell at the close of day 0.

## Engine version (pre-register this one)
- Rank: `mom_12_1`-style but registered as the raw 252-session return to the last session of the prior calendar
  quarter (published definition; no skip month). Top 1% of the eligible universe on that date.
- Trigger: `sessions_to_expected_earnings` == 5 at a close. Entry next open (day -4).
- Exit: close of the session with `sessions_to_expected_earnings` == 1 (day -1, so an after-close OR pre-open report
  is never held; registered deviation from the paper's day 0, chosen because the store cannot always tell
  before-open from after-close). If the actual report arrives earlier than expected, exit at the next open.
- Stop: catastrophe entry x 0.85. No trail, no target. Equal weight, max 20 open.

## Grading
Batch standard (own holding period, net). Also report the mean days -4..-1 return and the mean +1..+5 return of the
same names, so the reversal half is visible.

## Evidence
- 1971-2005, market-adjusted, gross: +1.58% over days -4..0 and -1.86% over +1..+5. Reports clearly outside trading
  hours: +3.09% before. With buy-at-ask / sell-at-bid: +0.94% (+1.66% for outside-hours reports).
- Against: the broader earnings announcement premium collapsed after 2004 (Heitz, Narayanamoorthy & Zekhnini,
  https://www.iimb.ac.in/ARC2020/Papers/The_Disappearing_Earnings_Announcement_Premium.pdf, opened: 43.4 bp, t 8.22,
  in 1994-2003 vs 0.3 bp, t 0.05, in 2005-2016). No direct post-2005 replication of the winners' run-up found.
- Grade C.

## Expectation stated before the run
+0.3% to +0.8% per trade gross, close to zero net. About 40-60 trades a year.

## Common mistakes
Holding through the report; ranking on the current day (look-ahead at the quarter boundary); using a revised
earnings date.

## Signs of decay to monitor
Trailing 100-trade mean net return <= 0.
