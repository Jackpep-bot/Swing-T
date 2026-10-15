---
slug: smallcap_momentum_index_replica
name: Replica of the S&P SmallCap 600 Momentum (live ETF XSMO) index rules on a different universe - same rules as sp500_momentum_index_replica, 120 names
originators: [S&P Dow Jones Indices, S&P Momentum Indices methodology; live ETF record]
category: strategy
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars; mcap_pit; semiannual rebalance
direction: long
universe: ranks 901-1,500 by mcap_pit, close >= $3, med_dv_63 >= $1M (an S&P 600 proxy)
regimes_good: [trend]
regimes_bad: [momentum_crash]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 10, 2026-10-14). WEIGHTS CARD. Independent-universe test of the momentum-index family; NOT a tuning of sp500_momentum_index_replica (identical rules, different stocks).
---

# S&P SmallCap 600 Momentum (live ETF XSMO) replica

## Why this card exists
`sp500_momentum_index_replica` (batch 9) beat SPY in both windows (+17.0% vs +12.4% a year in 2017-24, +27.0% vs
+16.4% in 2024-26) with drawdowns no deeper than SPY's, but its alpha t (1.30 and 0.73) missed the 2.24 bar. A
second look at the same stocks with changed settings would be tuning. This card instead applies the **same rules,
unchanged**, to a different and non-overlapping set of stocks. If momentum-index construction carries a real edge, it
should show up here too; if the batch-9 result was the 2023-26 mega-cap run, it should not. Either answer is
informative, and the stocks do not overlap with the batch-9 card, so the evidence is independent in the cross-section
(the market periods are the same).

## Evidence
Live ETF tracking the S&P SmallCap 600 Momentum (live ETF XSMO) index (https://portfolioslab.com/tools/stock-comparison/XMMO/XSMO, opened): XSMO 10-year CAGR 13.21%, 5-year 9.37%, 1-year 13.17%
(net of fees; the page does not give the benchmark's figures, so no excess return is claimed here). Grade C.

## Engine version (pre-register this one)
Every rule of `docs/proposals/swing-methods-2026-10/batch9/sp500_momentum_index_replica.md` applies unchanged
(reference dates, 12-1 volatility-adjusted momentum, z-score winsorised at +/-3, score mapping, mcap x score weights,
caps of 9% and 3 x cap weight, next-open fills, no stops, 252-session history rule), except:
- Universe: ranks 901-1,500 by mcap_pit, close >= $3, med_dv_63 >= $1M (an S&P 600 proxy), ranked on each reference date.
- Count: 120 names; buffer: a holding stays in the top 144, a new name enters in the top 96.
- The 3 x cap-weight cap is measured against the cap-weighted universe of this card.

## Grading
Weights-card grading: daily net returns vs SPY in both windows, plus descriptive vs the cap-weight of the same 600 names (built from the store,
no new data). Haircut: this card is a trial of the momentum-index family; count the family as batch 9's card plus
both batch 10 cards (3 trials).

## Expectation stated before the run
Lower return than the large-cap version in 2024-26 (smaller stocks lagged); 2017-24 near its own cap-weighted
universe plus 0 to +3% a year. Alpha vs SPY likely negative in 2024-26. Likely FAIL.
