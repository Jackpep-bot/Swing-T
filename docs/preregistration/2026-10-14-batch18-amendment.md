# Batch 18, amendment 1: step 2 rerun once on the VWforce series

Committed 2026-10-14 **before** the VWforce file was opened and before any statistic on it was computed.

- **Step 2 was rerun once after the first pass came back empty.** The first pass (committed 0c4a0f2, kept unchanged
  in `docs/preregistration/2026-10-14-batch18-selection.md`) applied the rule to value-weighted original CZ series only,
  because the card's preferred VWforce file was not on the Mac; it selected nothing.
- The card names the VWforce portfolios as its first choice. They come from the same CZ v2.0.0 release the owner
  approved (2026-10-14 19:20 UTC); the coordinator relayed the go-ahead to fetch them (19:39 UTC). File:
  `PredictorAltPorts_LiqScreen_VWforce.zip` from the release's Google Drive folder Portfolios / Full Sets Alt, saved in
  data/research/chen_zimmermann/.
- **Nothing else changes**: the step-1 list stays at 66 buildable (`2026-10-14-batch18-list.md`, commit 8db344a); the
  same exclusions (momentum family, GP); the same threshold (post-publication through 2016-12, at least 60 months,
  t >= 2.0, positive in-sample mean); at most 10 by t; returns after 2016-12 are dropped before anything is computed.
  The in-sample mean is read from the same VWforce series. Every buildable predictor (EW or VW in CZ's original build)
  is judged on its VWforce long-short series.
- Still 1 trial, bar `alpha_t_critical(3)` = 2.394. If the rerun selects nothing, batch 18 ends with no card.
- Results of the rerun: `docs/preregistration/2026-10-14-batch18-selection-vwforce.md`.
