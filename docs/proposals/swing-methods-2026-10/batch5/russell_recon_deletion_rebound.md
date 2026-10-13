---
slug: russell_recon_deletion_rebound
name: Russell 2000 reconstitution, buy stocks forced out of the Russell 2000 after recon day
originators: [Cai & Houge, Russell 2000 deletions vs additions (via Alpha Architect summary); Dimensional reconstitution studies 2014-2023]
category: strategy
decision: implement
holding_period_days: [20, 20]
timeframe: daily bars; once a year (twice from 2026)
direction: long
universe: small (predicted deletions from the Russell 2000 to microcap)
regimes_good: []
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog)
---

# Russell 2000 deletion rebound

## Why this one is new
No catalog entry uses index deletions. Deleted names are sold by index funds at the recon-day close regardless of
price; the published post-2014 data show a rebound afterwards. It is the one leg of the reconstitution trade with
positive recent evidence.

## One-line summary
Predict the stocks that fell out of the Russell 2000 on rank day; buy them at the open after reconstitution day and
hold 20 sessions.

## Origin and lineage
- Cai & Houge (via https://alphaarchitect.com/2014/02/r2k/, opened): 1979-2004, Russell 2000 deletions beat additions
  by 40.1% over 5 years; deletions-minus-additions 7.9% a year.
- Dimensional, 2014-2023 (https://www.dimensional.com/us-en/insights/even-migrating-stocks-face-index-reconstitution-costs,
  opened): migrating deletions -1.1% in the 20 days before recon, about +2% in the 20 days after.
- CXO summary (link in the additions card): deletions show abnormal returns in May and June, not July.

## Exact rules (as published)
None for long-only. Fixed by me.

## Engine version (pre-register this one)
- Membership proxy as in `russell_recon_addition_frontrun` (total `mcap_pit` rank on rank days).
- Deletion candidate: 1,200 <= rank_prev <= 2,900 (was well inside the proxy Russell 2000) AND rank_R >= 3,200 (well
  below it). Exclude names with a reverse split, an 8-K Item 1.03 (bankruptcy) or 3.01 (delisting notice) in the
  last 126 sessions (see `event_avoid_filters`).
- Liquidity at entry: `med_dv_63` >= $500k; close >= $1.
- Entry: open of the first session after reconstitution day. Equal weight, max 40, ranked by the largest fall in rank.
- Exit: close of the 20th session held. Catastrophe stop entry x 0.75. No trail, no target.

## Grading
Batch standard. Also report excess return over IWM.

## Evidence
Grade C: one long-run academic result plus one recent, independent, positive 20-day number (Dimensional), but the
Dimensional sample is Russell 1000/2000 migrations, not exits to microcap, and gives no t-stat. Gross only.

## Expectation stated before the run
+1% to +2% over IWM per event gross, about +0.5% to +1% net. Ten events give sign only.

## Common mistakes
Buying before recon day (the deletion selling is still to come); ignoring that many deletions are distressed names
(hence the bankruptcy/delisting exclusions).

## Signs of decay to monitor
Two consecutive events with basket minus IWM < 0.
