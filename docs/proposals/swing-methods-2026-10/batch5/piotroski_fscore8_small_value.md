---
slug: piotroski_fscore8_small_value
name: Piotroski F-score (8 of 9 signals buildable from the store) among cheap small/mid caps, quarterly
originators: [Piotroski, "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers", JAR 38 (2000)]
category: strategy
decision: implement
holding_period_days: [63, 126]
timeframe: monthly check, positions held 63-126 sessions; EDGAR 10-Q/10-K values point-in-time
direction: long
universe: SMALLMID, top 30% by book-to-market
regimes_good: []
regimes_bad: [narrow_uptrend]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog)
---

# Piotroski F-score, small/mid value

## Why this one is new
The catalog has profitability (`gross_cash_profitability`) and quality-minus-junk, but no accounting-signal score
inside cheap stocks. It is the most widely copied value screen online (AAII, Stockopedia, Finviz-style screeners)
and is aimed at exactly the small, thinly followed firms Jack is willing to trade.

## One-line summary
Among the cheapest 30% of small and mid caps by book-to-market, buy firms scoring at least 7 of 8 on Piotroski's
accounting checks; hold two quarters.

## Origin and lineage
- Piotroski 2000 (summary opened: https://www.chicagobooth.edu/review/separating-winners-losers): 1976-96, 14,043
  high-B/M firms; high scores +13.4% market-adjusted vs -9.6% for low; long side beats all value stocks by >= 7.5% a
  year; strongest in small, thin, no-analyst firms.

## Exact rules (as published)
Top B/M quintile. Nine binary signals: ROA > 0; CFO > 0; change in ROA > 0; CFO > net income; change in long-term
debt / assets < 0; change in current ratio > 0; no equity issued; change in gross margin > 0; change in asset
turnover > 0. Buy 8-9, formed annually about five months after fiscal year end, hold one year.

## Engine version (pre-register this one)
Store concepts: EPS diluted, revenue, gross profit, operating cash flow, total assets, total equity, shares
outstanding (`data/fundamentals.py` CONCEPT_TAGS). Each value is the latest one filed on or before the day (TTM sums
of the last four quarters; year-ago = TTM ending four quarters earlier).
- NI_ttm = sum of the last four quarterly EPS diluted x the latest shares outstanding (registered proxy for net income).
- Signals (1 point each): (1) NI_ttm / assets > 0; (2) CFO_ttm > 0; (3) NI_ttm/assets up vs year ago; (4) CFO_ttm >
  NI_ttm; (5) equity / assets up vs year ago (registered proxy for falling leverage; no debt concept in the store);
  (6) dropped: current ratio (no current assets/liabilities in the store); (7) `net_share_issuance` <= 0;
  (8) gross margin (GP_ttm / revenue_ttm) up vs year ago; (9) revenue_ttm / assets up vs year ago. Score 0-8.
  Firms without gross profit (banks, many REITs) are excluded rather than scored.
- B/M = latest total equity / `mcap_pit`; equity <= 0 excluded. Top 30% within SMALLMID on the check day.
- Check day: last session of each month (`month_end`). Buy: score >= 7 and in the top-30% B/M group. Equal weight, max
  40 names, highest score then highest B/M first.
- Sell: at the first month-end check where the score has fallen below 6, or after 126 sessions held, whichever first.
  A name sold on time may be re-bought at the same check if it still qualifies (no trade).
- Catastrophe stop entry x 0.70. No trail, no target, no regime gate.

## Grading
Batch standard; report turnover per year and the number of names held on average (Krauss et al. found about 3 in
the AAII version, which makes it "largely impractical").

## Evidence
- Decay is documented: Woodley, Jones & Reburn 2011 (abstract) find the result reversed in the 12 years after 1996;
  Kim & Lee 2014 (https://www.cxoadvisory.com/?p=26297, opened) get 8.9% a year gross over 1976-2007 and 6.0% with
  realistic formation dates; Hou-Xue-Zhang find the US value-weighted spread insignificant against q-factors.
- Krauss et al. 2015 on the AAII F 8-9 screen, 2005-2015 (https://www.cxoadvisory.com/?p=28363, opened): gross 30.9%
  a year equal-weighted, 1.08% a month once names under $1M daily volume are excluded, about 0.64% a month after
  0.7% round-trip cost.
- Outside the US it still works but mostly on the short side (Walkshausl 2020). Grade D for a long-only US version.

## Expectation stated before the run
Alpha vs SPY about zero to slightly negative in 2024-26 (a mega-cap-led market); 2017-24 small positive at best.

## Common mistakes
Using restated values (look-ahead); scoring firms with missing concepts as zero (biases toward data-poor firms);
annual-only formation (fewer, staler trades).

## Signs of decay to monitor
Trailing 3-year alpha vs IWM <= 0.
