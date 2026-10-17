---
slug: cz_blind_presample_composite
name: Large-cap composite of the Chen-Zimmermann predictors picked by a rule blind to 2017+ (post-publication t >= 2 through 2016-12), cap-weighted top 100, semiannual
originators: [Chen & Zimmermann (2022, Critical Finance Review) "Open Source Cross-Sectional Asset Pricing", data v2.0.0; McLean & Pontiff (2016, JF) "Does academic research destroy stock return predictability?"; Harvey, Liu & Zhu (2016)]
category: strategy
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars; mcap_pit; XBRL fundamentals (avail_ts); dividends; semiannual rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $5
regimes_good: [any]
regimes_bad: [mega_cap_led_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 18, 2026-10-14). WEIGHTS CARD. New family (CZ blind composite); 1 trial, bar raised to alpha_t_critical(3) for overlap with tested families. Selection is done by the Mac with the rule below; the rule was fixed before any selection output existed.
---

# Blind Chen-Zimmermann composite

## Why this card exists, and what was known when it was written
The premise library (746f611) ranks Chen-Zimmermann predictors by their 2017-2024 returns, which overlap our grading
window, so picking the best of that list and grading 2017-26 would count the same years twice. This card picks
predictors with a rule that **cannot see 2017 or later**: post-publication evidence through 2016-12 only (McLean &
Pontiff showed post-publication returns are the honest guide, about 58% lower than in-sample). The book is then
graded on 2017-26, which is out of sample for the selection.

Known when writing: the writer had seen the since-2017 top-25 and value-weighted tables in the premise library. The
threshold (t >= 2) and every filter below are the standard ones, not tuned to include or exclude any name seen there;
the Mac applies the rule mechanically and the writer does not choose among its output.

## Step 1: buildability list (committed before any statistic is computed)
From CZ's signal documentation, list every predictor in categories Accounting, Price or Trading whose definition can be
built point-in-time from what the store has: daily bars and volume, `mcap_pit`, `net_share_issuance`, `sic2`,
dividends, and the XBRL concepts already loaded (diluted EPS, revenue, gross profit, operating cash flow, total assets,
stockholders' equity, shares outstanding). A predictor needing any other item (current assets or liabilities, debt,
capex, R&D, inventory, analyst data, 13F, options, short interest) is out. A predictor needing more than 60 months of
history is out (store bars start 2016-01). Commit this list, with one line per predictor saying why it is in or out,
**before** step 2.

## Step 2: selection rule (fixed now)
For each predictor on the list:
- Return series: CZ's value-weighted long-short monthly returns from the v2.0.0 release (the "VWforce" alternative
  portfolios). If that file is not among the approved CZ files already on the Mac, use the predictor's original
  long-short series and keep only predictors whose original weighting is value-weighted; say which applied.
- Post-publication window: from January of the year after CZ's publication year through **2016-12**. At least 60
  months, otherwise the predictor is out.
- Selected if: the mean monthly long-short return has t >= 2.0 in that window **and** the in-sample mean (CZ's sample
  start/end years) is positive.
- Excluded by family, stated now: price-momentum predictors (any whose definition is a past-return sort, e.g. Mom6m,
  Mom12m, MomVol, IntMom, Mom12mOffSeason, FirmAgeMom) because the momentum family is already at 7 trials; and GP,
  already tested as batch 3's card.
- If more than 10 pass, keep the 10 with the highest window t. If none pass, there is no card and the result says so.
- The selection table (all listed predictors with window months, mean, t, selected yes/no) is committed before step 3.
  No one looks at any selected predictor's 2017+ CZ returns before the book is graded.

## Step 3: the book (pre-register this one)
- Reference date: the last session of May and November. Orders at the open of the session after the third Friday of
  the following month (June and December). Values use only filings with `avail_ts` on or before the reference date.
- Universe: the 500 largest by `mcap_pit`, as-traded close >= $5.
- For each selected predictor, compute our point-in-time version of CZ's signal on the reference date, and its
  percentile (0-1) within the universe, oriented so 1 = CZ's long side.
- Score: the average of the available percentiles; a name needs at least half of the selected predictors.
- Holdings: the 100 highest scores, with a buffer: a holding stays while it ranks within the top 150; new names fill
  from the top until there are 100.
- Weights: `mcap_pit`, each capped at 5% (excess spread pro rata), summing to 1; weights drift between rebalances.
- **Cash treatment:** fully invested. If fewer than 100 names qualify, the unused weight is held in SPY. Before the
  first rebalance (June 2017) the book holds SPY.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier. Costs: `weights_book.simulate`
  with the per-symbol table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover, from the rank buffer: earlier rank-buffer books replaced about 40% of names a rebalance; at two
  rebalances a year with cap weights, **80-160% a year one-way**; costs about 0.1-0.2% a year.

## Price-only data note
The store is price-only for the book and SPY. If the selected predictors tilt toward dividend payers (payout or
issuance signals), the book's yield gap goes unpaid and the grade is biased against it; the total-return store's
figure is reported beside the grade, descriptive only.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: **1** for the whole composite, however many predictors it holds: the selection is blind to the grading window,
so it is one pre-registered rule, not a search over 208. The bar is still raised one step, to `alpha_t_critical(3)` =
2.394, because selected predictors will likely overlap families already tested (profitability, issuance, accruals).
Beside the verdict, descriptive only and not graded: each selected predictor's own top-100 book under the same rules,
tracking error against SPY, and the correlation of monthly excess-of-SPY returns with `sp500_momentum_index_replica`.

## Expectation stated before the run
Unknown which predictors pass; most post-publication t values fall below 2 when cut at 2016, so expect 2-6 selected,
mostly accounting signals (issuance, accruals, profitability, payout). Large-cap value-weighted spreads are about half
the equal-weighted ones, and the long-only top 100 captures only part of a long-short spread. Alpha about 0 to +2% a
year, pooled alpha t under 1. Likely FAIL; the selection table is useful on its own as an honest shortlist.
