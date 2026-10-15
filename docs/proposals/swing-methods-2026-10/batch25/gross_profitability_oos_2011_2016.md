---
slug: gross_profitability_oos_2011_2016
name: Out-of-sample confirmation of large_cap_gross_profitability (batch 3) on 2011-2016
originators: [batch 3 card large_cap_gross_profitability; Novy-Marx (2013); Chen-Zimmermann GP (VW) in the premise library]
category: confirmation_test
decision: implement
holding_period_days: [63, 504]
timeframe: daily bars 2010-01-04 onward (data/live/replay_2010.duckdb); XBRL GrossProfit and Assets
direction: long
universe: as batch 3 (the 500 largest non-financials)
evidence_grade: B
free_data_ok: true
weights_card: false
status: draft_card (research thread batch 25, 2026-10-15). CONFIRMATION TEST, pre-registered before the 2010 store exists. Same approval caveat as mom_prof_replica_oos_2011_2016.
---

# Large-cap gross profitability out of sample: 2011-2016

## Why
It is the only card besides the replica with alpha t above 1.4 in any graded window (2017-24: +4.5%, t 1.43; then
2024-26: -3.1%, t -0.41, so it failed). The signal has the longest outside record of anything we tested (Novy-Marx
1963-2010; CZ value-weighted GP since 2017 t 2.5). If it carries in 2011-2016 too, 2024-26 looks like a bad stretch;
if not, the 2017-24 number was likely luck.

## What is run (fixed now)
- The batch 3 engine card's code and settings exactly as in 2026-10-10-batch3-results.md (an engine card: stop-sized
  positions, monthly check, as registered), with `DATA_START` = 2010-01-04 and the 2010 store. Nothing else changes.
- The same 60% gross-profit coverage rule for the window start as `mom_prof_replica_oos_2011_2016`.
- Store checks, universe fallback, costs and delistings as batch 24.

## Confirmation rule (window O = 2011-01-03 .. 2016-12-30, or the later start)
- **Confirmed**: batch 3's own standard rule (haircut Sharpe > 0, net R > 0) and alpha vs SPY > 0 with alpha t >= 2.241.
- **Consistent, not confirmed**: alpha > 0, t < 2.241. **Not supported**: alpha <= 0.
Bar `alpha_t_critical(2)` = 2.241, shared with the batch's other confirmation card. Not a new trial.
Beside it, descriptive: 2011-2026 as one simulation; exposure and turnover.

## Expectation stated before the run
Quality and profitability were rewarded in 2011-2016 large caps, so this is the card most likely to show positive
alpha here; with beta near 1 and about 6 years, t about 0.5 to 1.5. Most likely "consistent, not confirmed".
