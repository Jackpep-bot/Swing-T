---
slug: dividend_increase_drift
name: Dividend increases and initiations - hold stocks for 63 sessions after an ex-date that raised the regular dividend
originators: [Michaely, Thaler & Womack (1995, JF); Grullon, Michaely & Swaminathan (2002, JB); Boehme & Sorescu (2002, JF)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; dividends table (Alpaca cash dividends, approved 2026-10-13); weekly rebalance
direction: long
universe: top 1,500 by mcap_pit, as-traded close >= $5
regimes_good: [any]
regimes_bad: [crash]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 11, 2026-10-14). WEIGHTS CARD. New family (dividend-change drift); 1 trial.
---

# Dividend increases and initiations

## Why this card exists
Firms that raise or start a regular dividend have shown positive drift for months after the announcement (the market
under-reacts to the signal), with the effect strongest for initiations. It is a different family from everything
tested so far: the dividend-month card (batch tracking) traded the *timing* of ordinary payments; this one trades a
*change* in the payment. The book is fully invested (unused weight sits in SPY), so it does not lose to SPY simply by
holding cash, and its alpha comes from many small, separate events rather than one factor bet.

## Evidence
- Michaely, Thaler & Womack (1995): initiations earned about +7.5% excess in the year after, omissions -11%
  (1964-88). Grade: published, pre-dates our window.
- Boehme & Sorescu (2002): the initiation drift weakens after risk adjustment; this is the main reason the expectation
  below is cautious.
- No live product tracks this rule; grade C.

## Engine version (pre-register this one)
- Data: `data.dividends.mapped` (split-adjusted `rate_adj`), regular dividends only: `special` false and `foreign`
  false. The signal date is the **ex-date** (always on or after the declaration, so point-in-time safe; it gives up the
  first days of the reaction).
- An **increase event** on ex-date d for a symbol: its regular `rate_adj` on d is at least 1.10 x its previous
  regular `rate_adj` (the most recent earlier ex-date within 400 sessions), and at most 3.0 x it (above that is
  treated as a data error or special payment and ignored).
- An **initiation event** on ex-date d: a regular dividend with no regular ex-date in the 400 sessions before d, and
  the symbol has at least 400 sessions of bars before d (so a newly listed stock's first dividend does not count).
- Eligible on d: in the top 1,500 by `mcap_pit` on d and as-traded close >= $5 on d.
- Holdings: every eligible event whose ex-date falls in the 63 sessions ending on the rebalance signal day.
- Rebalance: weekly; signal day = the last session of each week, orders at the next session's open.
- Weights: equal weight 1/N across the held names, each capped at 4%. **Cash treatment:** whatever weight the cap
  leaves unused (for example fewer than 25 names) is held in SPY, never in cash or BIL.
- No stops. A delisted holding exits at its last close x the store's delisting multiplier (as `weights_book`).
- Costs: `weights_book.simulate` with the per-stock cost table (DEFAULT_COST_BPS where missing).

## Grading (docs/gates.md, including "Full-period test")
Daily net returns vs SPY. Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 .. 2026-10-05, and the pooled window
2017-01-01 .. 2026-10-05 as one simulation. The dividends feed starts 2016-01, so the 400-session look-back first
covers fully in mid-2017; before that, initiations cannot be told apart from feed start and **only increase events
count until 2017-08-01** (written here so it is not a choice made later).
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the batch bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: this card counts as 1 trial of a new family; the batch bar is `alpha_t_critical(2)` = 2.241 (2 cards).
Descriptive only: the same book split into increase events and initiation events.

## Data note (added 2026-10-14 before any result, not a rule change)
The store is price-only: dividends are left out for the book and for SPY alike. This book holds dividend raisers,
which yield more than SPY on average, so price-only grading understates its return against SPY by about the yield
gap (likely under 1% a year). The grade uses the price-only store as registered.

## Expectation stated before the run
Modest. Most increases come from large, steady dividend payers, which lagged SPY in 2024-26; alpha vs SPY likely
0 to +2% a year with alpha t under 1.5. Likely FAIL.
