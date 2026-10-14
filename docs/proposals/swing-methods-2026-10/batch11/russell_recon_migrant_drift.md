---
slug: russell_recon_migrant_drift
name: Russell reconstitution migrants - hold stocks that fall from a large-cap rank band into the top of the small-cap band, for one year
originators: [Chang, Hong & Liskovich (2015, RFS); Madhavan (2003, FAJ); Cai & Houge (2008, "Index rebalancing and long-term portfolio performance")]
category: strategy
decision: implement
holding_period_days: [252, 252]
timeframe: daily bars; mcap_pit; annual rebalance after the last Friday of June
direction: long
universe: stocks whose mcap_pit rank moved from 1-1,000 last year to 1,001-1,300 this year
regimes_good: [small_cap_rally]
regimes_bad: [large_cap_leadership]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 11, 2026-10-14). WEIGHTS CARD. New family (index-membership price pressure); 1 trial.
---

# Russell reconstitution migrants

## Why this card exists
Each June the Russell indexes are rebuilt from market caps ranked on a rank day in late April or May. A stock that
slips from the bottom of the Russell 1000 into the top of the Russell 2000 goes from a tiny weight to one of the
biggest weights in a heavily indexed small-cap benchmark, and index funds must buy it. Chang, Hong & Liskovich (2015)
use this cutoff as a natural experiment and find these migrants beat stocks just on the other side of the line by a
few percent in the months around reconstitution, with the gap persisting after. The rule needs only market caps,
which the store already has point-in-time, and it is a different family from anything tested (it is not momentum,
value or an event filing).

## Evidence
- Chang, Hong & Liskovich (2015): sharp return gap at the 1,000 cutoff in June, regression-discontinuity design.
- Cai & Houge (2008): a buy-and-hold book of Russell 2000 deletions and additions beat the rebalanced index by about
  2.2% in the first year (1979-2004).
- CXO Advisory summary of index-rebalancing papers (https://www.cxoadvisory.com/miscellaneous/strategies-for-exploiting-index-rebalancing/, opened 2026-10-14) notes the effect has weakened in recent years. Grade C.

## Engine version (pre-register this one)
- **Rank day:** the last session of April each year (the 2024 Russell switch to semiannual review is ignored; one
  annual cohort, written here so it is not chosen later). Rank common stocks by `mcap_pit` on that session, with an
  as-traded close >= $1 (Russell's own floor).
- **Migrant:** ranked 1-1,000 on last year's rank day **and** 1,001-1,300 on this year's. (Russell uses a 5%
  banding rule around the line; the 1,300 limit is this card's simple stand-in, stated here.)
- **Entry:** target weights set on the session after the last Friday of June (reconstitution day), orders at that
  session's open. **Exit:** replaced by the next year's cohort on the same day; a holding still in the new cohort is
  kept (no trade).
- **Weights:** equal weight 1/N, each capped at 3%. **Cash treatment:** any weight the cap leaves unused, and the whole
  book before the first cohort (2017-01-01 .. June 2017), is held in SPY, never in cash or BIL.
- No stops. A delisted holding exits at its last close x the store's delisting multiplier.
- First cohort: needs the 2016 and 2017 rank days, so the first migrant book is June 2017; the store starts 2016-01.
- Costs: `weights_book.simulate` with the per-stock cost table.

## Grading (docs/gates.md, including "Full-period test")
Daily net returns vs SPY. Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 .. 2026-10-05, and the pooled window
2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the batch bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: 1 trial of a new family; batch bar `alpha_t_critical(2)` = 2.241 (2 cards).
Descriptive only: the same rules on the opposite side of the line (ranked 1,001-1,300 last year, 1-1,000 this year,
"promoted" stocks), which the paper expects to do worse; and the cohort count per year.

## Expectation stated before the run
Weak. These are mid-sized stocks that just fell in value, in a period when large caps led; the price pressure is
mostly front-run in May and June now. Alpha vs SPY likely around zero with alpha t under 1. Likely FAIL.
