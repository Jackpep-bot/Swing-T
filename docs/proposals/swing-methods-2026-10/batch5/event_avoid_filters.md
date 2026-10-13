---
slug: event_avoid_filters
name: Event avoid filters for small/mid-cap longs, reverse splits, distress 8-Ks, IPO lockup window
originators: [Kim, Klein & Rosenfeld, Financial Management 37(2) 2008 (reverse splits); Lerman & Livnat, RAST 15(4) 2010 (8-K items); Field & Hanka, JF 56(2) 2001 (lockups)]
category: filter
decision: implement
holding_period_days: null
timeframe: daily; applies to any long strategy
direction: long (exclusion only)
universe: any
regimes_good: []
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B-
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog; extends the existing days_since_402 avoid flag)
---

# Event avoid filters

## Why this one is new
The engine has one event exclusion (`days_since_402`, restatements; `pullback_trend_avoid_402`). Moving into small
caps raises the odds of buying names that are about to keep falling for known, filed reasons. These exclusions have
the most robust negative-drift evidence of anything found in this batch, and they cost no trial slots on their own:
they are graded as a change to strategies that already exist.

## One-line summary
Do not open a long in a stock with a reverse split in the last year, a bankruptcy, delisting-notice or
officer-departure 8-K in the last 63-126 sessions, or that is within five sessions of its likely IPO lockup expiry.

## Origin and lineage
- Reverse splits: Kim, Klein & Rosenfeld 2008 (working paper opened:
  https://www.efmaefm.org/0efmameetings/EFMA%20ANNUAL%20MEETINGS/2006-Madrid/papers/568563_full.pdf): 1,612 reverse
  splits 1962-2001, matched-firm BHAR -12.7% at 1 year (t -4.37), -22.7% at 3 years (t -5.59); short-sale limits keep it.
- 8-K items: Lerman & Livnat (https://archive.nyu.edu/bitstream/2451/27579/2/SSRN-id1126816.pdf, opened), 2005-06,
  size/BM-adjusted drift after filing: Item 5.02 -0.28% / -0.36% / -0.45% at 30/60/90 days (n 15,056); Item 8.01
  -0.13% / -0.35% / -0.45% (n 28,467); Item 1.03 bankruptcy -19.0% at 90 days (n 18); Item 3.01 delisting notice
  -2.90% over 3 filing days, no further drift. Frequent 8-K filers earn less (Management Science, about -4.4% a year
  four-factor; https://pubsonline.informs.org/doi/fpi/10.1287/mnsc.2015.2408, opened).
- Lockups: Field & Hanka 2001 (https://ideas.repec.org/a/bla/jfinan/v56y2001i2p471-500.html, opened): about -1.5%
  three-day abnormal return at expiry, volume up about 40%, larger for VC-backed firms; a 2024 thesis (2,428 US
  issuers 2003-2022, abstract) still finds significant negative returns at expiry.

## Rules (pre-register this one)
A long entry on day t is refused (logged as a refusal with the reason) when any of:
1. A split with ratio < 1 (reverse split) in the `splits` table with ex_date in t-252..t.
2. An original 8-K with Item 1.03 or 3.01 whose reaction session is in t-126..t.
3. An original 8-K with Item 5.02 whose reaction session is in t-63..t, and no earnings reaction session in that
   window (5.02 filed with earnings is usually routine board news).
4. Likely lockup window: the symbol's first bar in the store is after 2016-03-01, and t is within 175..190 calendar
   days of that first bar (lockups are typically 180 days; the store has no S-1 data, so the IPO date is the first
   bar, which mislabels uplistings and de-SPACs; registered limit).
Not used: Item 8.01 (too common, small effect), Item 7.01 (positive drift, not an avoid).

## Grading
Not a strategy. For each strategy in the small-cap map with t >= 1 in either window, re-run with the filter on and
report: signals removed, net R of the removed signals, change in alpha vs SPY. Adopt for small/mid runs if the
removed signals' mean net R is below the kept signals' in both windows. Counts as one trial per strategy it is
applied to, as with the earlier no-news filters.

## Evidence
Grade B- for the reverse-split leg (large, long-run, significant, persists because shorting is hard); C for 8-K
items (2005-06 only, no post-2015 replication found); C for lockups.

## Expectation stated before the run
Removes 2-5% of small-cap signals; the removed group underperforms the kept by 0.1-0.3R net.

## Common mistakes
Treating split-adjusted history as unadjusted (a reverse split looks like a crash in raw prices); counting 8-K/A
amendments as new events.
