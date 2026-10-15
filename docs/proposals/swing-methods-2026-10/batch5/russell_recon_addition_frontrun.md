---
slug: russell_recon_addition_frontrun
name: Russell 2000 reconstitution, buy likely microcap-to-Russell-2000 additions on rank day, sell on recon day
originators: [Madhavan, "The Russell Reconstitution Effect", FAJ 59(4) 2003; Petajisto 2011; FTSE Russell reconstitution calendar]
category: strategy
decision: implement
holding_period_days: [30, 45]
timeframe: daily bars; once a year (twice from 2026)
direction: long
universe: small (predicted Russell 2000 additions from below)
regimes_good: []
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog)
---

# Russell 2000 additions front-run

## Why this one is new
Nothing in the catalog trades index membership. This is a pure flow event in small caps: index funds must buy
newly added names at the close of reconstitution day, and the add list is predictable from market caps on rank day.

## One-line summary
On Russell rank day, predict which stocks just crossed into the Russell 2000 from the microcap zone; buy them the next
session and hold them until the close of reconstitution day.

## Origin and lineage
- Madhavan 2003 (https://ideas.repec.org/a/taf/ufajxx/v59y2003i4p51-64.html, abstract read): additions-minus-deletions
  of the Russell 3000 earned 14.94% on average in June 1996-2002, long-short and gross; costs and price risk limit it.
- Petajisto 2011 (cited by Cho et al. 2017, https://articlegateway.com/index.php/JAF/article/download/943/889, opened):
  Russell 2000 addition premium about +4.7%, declining from a 2000 peak to 2007.
- Calendar: rank day is the last business day of April; effective after the close of the 4th Friday of June
  (2026: April 30 and June 26). FTSE Russell adds a second reconstitution from 2026: rank day 2026-10-30, effective
  after the close 2026-12-11.

## Exact rules (as published)
None. Madhavan's portfolio is long additions / short deletions held through June; no paper publishes a long-only
rank-day-to-recon-day rule for microcap additions. Every threshold below is fixed by me.

## Engine version (pre-register this one)
- Membership proxy (registered deviation: no Russell membership file in the store). On each rank day R, rank every
  US common stock in the store with a valid `mcap_pit` (close x EDGAR shares) and close >= $1 by `mcap_pit`
  (total, not float-adjusted). rank_R = this year's rank; rank_prev = the same rank computed on the previous rank day.
- Addition candidate: rank_prev > 3,100 (or no rank last year because the stock was not listed or had no shares
  filing, but at least 252 bars of history) AND 1,300 <= rank_R <= 2,800. The margins keep clear of Russell's 2.5%
  cumulative-cap banding, which my proxy cannot reproduce.
- Liquidity floor at entry: `med_dv_63` >= $500k (looser than the shared $1M floor because new additions are
  microcaps by construction; stated deviation).
- Entry: next open after rank day. Equal weight, max 40 names; if more qualify, take the 40 with the highest rank_R
  (largest caps).
- Exit: close of reconstitution day (engine fallback if close fills are not supported: open of the next session,
  which gives back the recon-day closing pressure; record which was used).
- Stop: none except a catastrophe stop at entry x 0.75. `engine_trail = False`, no target.
- Events: one per rank day: June 2017-2024 (8) in the long window, June 2025 and June 2026 in the short window,
  plus December 2026 when it happens.

## Grading
Batch standard (README, Shared definitions). Also report the gross return of the same basket over the same days
measured with IWM as the benchmark, because IWM moves with these names.

## Evidence
- Strongest in the 1990s; Petajisto and CXO's "Revisited" summary
  (https://www.cxoadvisory.com/miscellaneous/strategies-for-exploiting-index-rebalancing/, opened) say the
  reversal-type effects became "much smaller to nonexistent".
- Dimensional, 2014-2023, Russell 1000/2000 migrations (not microcap entries):
  https://www.dimensional.com/us-en/insights/even-migrating-stocks-face-index-reconstitution-costs (opened): migrating
  additions +1.2% in the 20 days before recon and -0.95% in the 20 days after. That is the shape this card bets on,
  at about a third of the old size.
- Greenwood & Sammon (via https://alphaarchitect.com/disappearing-index-effect/, opened): the S&P 500 addition
  effect fell from 7.4% in the 1990s to below 1% in the 2010s, with "similar" declines for Russell (no numbers).
- No post-2015 test of the microcap-to-R2000 addition trade found. Grade D.

## Expectation stated before the run
+0% to +2% per event over IWM, gross; near zero net. Ten events cannot show significance; the run gives sign and size.

## Common mistakes
Using today's membership list (look-ahead); counting float-adjusted caps (Russell ranks on total cap); selling the
morning after recon day instead of at the close.

## Signs of decay to monitor
Basket return from rank day to recon day minus IWM <= 0 for two years running.
