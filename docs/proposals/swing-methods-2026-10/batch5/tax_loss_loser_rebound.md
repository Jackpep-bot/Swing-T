---
slug: tax_loss_loser_rebound
name: Tax-loss selling rebound, buy the year's worst small/mid-cap losers late in December, sell mid-January
originators: [Ritter, JF 43(3) 1988; Grinblatt & Moskowitz, JFE 71(3) 2004; Lynch, Puckett & Yan 2014; Kozlowski & Lytle, Applied Finance Letters 2023]
category: strategy
decision: implement
holding_period_days: [15, 15]
timeframe: daily bars; once a year
direction: long
universe: small/mid (shared SMALLMID universe)
regimes_good: []
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog)
---

# Tax-loss loser rebound

## Why this one is new
`santa_claus_rally` and `halloween_seasonal_overlay` time the index. This card picks stocks: the year's biggest
losers, whose December price is held down by tax-motivated selling from individual holders.

## One-line summary
Ten sessions before year end, buy the 30 worst year-to-date performers among small and mid caps; sell after the
first ten sessions of January.

## Origin and lineage
- Ritter 1988 (https://site.warrington.ufl.edu/ritter/files/2016/01/The-Buying-and-Selling-Behavior-of-Individual-Investors-at-the-Turn-of-the-Year-1988-07.pdf,
  opened): 1971-85, smallest-minus-largest NYSE decile 0.876% a day over the first 9 January sessions (about 8.2%);
  individuals' buy/sell ratio 0.747 in late December vs 0.957 in early January.
- Lynch, Puckett & Yan 2014 (https://www.lehigh.edu/~xuy219/research/ToY.pdf, opened): 1999-2005, extreme losers'
  January-minus-December return 14.0% (winners 0.5%), 16.6% in the smallest quintile, 26.4% after down-market years.
  Windows: last 10 sessions of December and first 10 of January.
- Kozlowski & Lytle 2023 (https://ojs.aut.ac.nz/applied-finance-letters/article/download/615/164, opened): 1981-2020,
  the January alpha of the short-term reversal factor is -2.18% (t -2.10), i.e. losers rebound; strongest after
  recessions and down years. Note: the same paper finds small caps as a whole UNDERperform in January (SMB January
  alpha -5.9%), so the edge is in losers, not in size.

## Exact rules (as published)
No canonical trading rule; papers measure returns over fixed windows. I fixed the windows to Lynch et al.'s.

## Engine version (pre-register this one)
- Signal day: the 10th-to-last NYSE session of December (inclusive count: signal day + 9 sessions = last session).
- Universe: SMALLMID on the signal day.
- Score: year-to-date return = close on signal day / last close of the prior year - 1.
- Eligible: YTD <= -40% and close >= $3 (shared floor) and not inside `event_avoid_filters`.
- Pick: the 30 most negative YTD among eligible names (fewer if fewer qualify). Equal weight.
- Entry: next open after the signal day. Exit: close of the 10th NYSE session of January (fallback: next open).
- Stop: catastrophe at entry x 0.70. No trail, no target, no regime gate.
- Events: Dec 2016 .. Dec 2023 entries in the long window (8), Dec 2024 and Dec 2025 in the short window.

## Grading
Batch standard, plus excess over IWM over the same days.

## Evidence
Grade C: decades of gross evidence, still visible in 1981-2020 factor data, but no net-of-cost loser-basket test
after 2015 was found. Costs are the threat: these are wide-spread losers. Hulbert's 2026 column (anecdotal, perfect
hindsight timing; https://www.itiger.com/news/2669472193) is not evidence.

## Expectation stated before the run
+3% to +6% over IWM per event gross in down years, about zero in up years; net positive only if spreads are under
1% round trip. Ten events: sign and size only.

## Common mistakes
Entering on the last day of December (rebound has started); using names under $3 (spread eats it); holding to the
end of January (the effect is in the first two weeks).

## Signs of decay to monitor
Basket minus IWM over the 15-session window negative in three of the last four years.
