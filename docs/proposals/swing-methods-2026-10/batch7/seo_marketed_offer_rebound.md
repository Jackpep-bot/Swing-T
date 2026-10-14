---
slug: seo_marketed_offer_rebound
name: Buy after a marketed follow-on stock offering that pushed the price down beforehand; hold 7 sessions
originators: [Price pressure and overnight seasoned equity offerings (Penn State; JFQA), sample 2000-2014; Corwin, "The determinants of underpricing for seasoned equity offers", JF 2003]
category: strategy
decision: implement
holding_period_days: [7, 7]
timeframe: daily bars; EDGAR form types from the submissions JSON (424B4, 424B5)
direction: long
universe: store stocks, close >= $5, med_dv_63 >= $2M
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 7, 2026-10-14)
---

# Marketed follow-on offering rebound

## Why this one is genuinely different
This is a supply-shock event: a company sells new shares, sellers push the price down in the days before pricing, and
the pressure lifts once the deal is placed. The catalog's reversal cards buy any pullback; this one buys only drops
with a known, temporary, mechanical cause, and only after the cause is gone. Batch 5 rejected it for lack of
offering dates; the 424B prospectus form types are in the EDGAR submissions JSON the store already downloads.

## One-line summary
When a company files its final offering prospectus after its stock fell at least 4% over the prior week, buy the
next open and sell 7 sessions later.

## Evidence
- "Price pressure and overnight seasoned equity offerings" (abstract,
  https://pure.psu.edu/en/publications/price-pressure-and-overnight-seasoned-equity-offerings/, opened): stocks of
  issuers that market their offering fall about 2.5% before the issue and the drop reverses within 7 days, more so
  for larger offers and larger pre-issue drops. Overnight offerings (announced and priced the same night), 75% of
  deals in 2009-2014, show a smaller rebound. Sample to 2014, gross.
- Against: no net-of-cost test; overnight deals now dominate, so few marketed deals qualify. Grade C.

## Engine version (pre-register this one)
- Signal (F): a 424B4 or 424B5 filed by the symbol's CIK, with no 424B of any kind from that CIK in the prior 90 days
  (drops at-the-market programs' repeat supplements). Signal session = the session after the filing's acceptance time.
- Pressure (F): close on the session before the signal <= 0.96 x close 6 sessions earlier, and the stock's
  return minus SPY's over those 5 sessions <= -3%.
- Entry next open; exit at the close of the 7th session after entry; catastrophe stop 12% below entry.
- Max 8 open, equal risk. `event_avoid_filters` applies except its offering-related rule, if any.
- Descriptive split, not a trial: the same rule without the pressure filter.

## Grading
Batch standard plus alpha vs SPY in both windows, haircut over this batch's trials.

## Expectation stated before the run
Tens of signals a year; +1% to +2% gross over 7 sessions, near zero to +1% net.

## Common mistakes
Counting the 424B5 that opens an at-the-market program as a marketed deal; using the prospectus date (often the
evening before) as the trade day.
