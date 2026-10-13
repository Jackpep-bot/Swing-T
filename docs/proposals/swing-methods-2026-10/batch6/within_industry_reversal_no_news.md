---
slug: within_industry_reversal_no_news
name: Within-industry one-month losers with no earnings or news, 1,000 largest stocks, monthly
originators: [Da, Liu & Schaumburg, "A Closer Look at the Short-Term Return Reversal", Management Science 60(3) 2014; Savor, "Stock returns after major price shocks: the impact of information", JFE 106(3) 2012]
category: strategy
decision: implement
holding_period_days: [21, 21]
timeframe: daily bars, monthly rebalance; SIC codes; 8-K items; Alpaca news flag
direction: long
universe: the 1,000 largest store stocks by mcap_pit, close >= $5
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 6, 2026-10-13; needs SIC codes parsed from the EDGAR submissions JSON the store already fetches)
---

# Within-industry reversal, no-news losers

## Why this one is genuinely different
Raw reversal mixes two things that go opposite ways: industry moves (which continue, industry momentum) and stock
moves on real news (which drift). Da, Liu & Schaumburg show reversal is strong only once both are removed. The
catalog's reversal and pullback cards (`short_term_reversal_1m`, `connors_*`, `rsi2_meanrev`, the `_no_news`
variants) rank on the stock's own raw move. This card ranks a stock against its own industry that month and drops
any move that came with earnings or news. Industry codes were the blocker in batch 5; they are a field in the EDGAR
submissions JSON the store already downloads for 8-K items, so no new data source is needed.

## One-line summary
Each month, within each two-digit SIC industry, buy the stocks that lagged their industry most last month without an
earnings release or news story; hold one month.

## Evidence
- Da-Liu-Schaumburg via CXO (https://www.cxoadvisory.com/animal-spirits/refined-short-term-reversal-strategies,
  opened): large liquid US stocks (about 75% of market cap), 1982-2009. All-stock reversal 0.67% a month gross;
  simple within-industry 1.20%; within-industry with cash-flow news removed 1.57% (3-factor alpha 1.34%), "remains
  economically significant" after 0.80% a month of friction (roughly 0.5% a month alpha net is my arithmetic,
  long-short). Their news proxy uses analyst forecasts we do not have; this card uses earnings dates and the news flag.
- Savor 2012 (abstract, https://repository.upenn.edu/fnce_papers/387, opened): large price moves without analyst
  reports reverse; moves with reports drift. Supports the no-news filter.
- Against: no post-2009 test; long leg only. Grade C.

## Engine version (pre-register this one)
- Industry: two-digit SIC from `sic` in the submissions JSON (current value; SIC changes are rare, recorded as a known
  point-in-time gap). Industries with fewer than 5 universe members that month are skipped.
- Score: stock's 21-session return minus the equal-weight mean of its SIC2 industry over the same sessions, divided by
  the stock's 252-session daily return standard deviation x sqrt(21).
- No-news: no 8-K Item 2.02 and no Alpaca news item tagged to the symbol in the 21 sessions (the approved news flag;
  if the news flag is missing for a date, 8-K items of any type stand in, as `event_avoid_filters`).
- Rebalance last session of the month, fill next open, buy the 50 lowest scores equal weight, keep while in the
  lowest 100. Catastrophe stop 20%. `event_avoid_filters` applies.

## Grading
As `residual_reversal_ff3_etf` (portfolio card, alpha vs SPY both windows, income view).

## Expectation stated before the run
Alpha vs SPY 0 to +3% a year in 2017-24 (t near 1); about zero in 2024-26. If it beats `short_term_reversal_1m`
by a wide margin while losing to SPY, that still tells us industry-adjusting is the right direction for reversal.

## Common mistakes
Industry mean that includes the stock itself in tiny industries; counting the news flag only from 2015 on (Alpaca
news starts 2015, fine for both windows).
