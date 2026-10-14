---
slug: sp500_momentum_index_replica
name: Replica of the S&P 500 Momentum index - 100 largest-momentum names of the 500 largest, risk-adjusted 12-1 momentum, weight = market cap x score, rebalanced twice a year
originators: [S&P Dow Jones Indices, S&P Momentum Indices (live index; ETF SPMO tracks the S&P 500 version)]
category: strategy
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars; mcap_pit; semiannual rebalance
direction: long
universe: the 500 largest store stocks by mcap_pit on the reference date
regimes_good: [trend]
regimes_bad: [momentum_crash]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B-
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 9, 2026-10-14). WEIGHTS CARD (fixed target weights, not stop-sized). Chosen knowing the index's 2015-2026 live record, so a pass is a forward-test candidate only.
---

# S&P 500 Momentum index replica

## Why this one is genuinely different from the momentum cards that failed
`xs_momentum_rank`, `clenow_stocks_on_the_move_midcap`, `large_cap_residual_momentum` and the breakout family all
lost to SPY. Each was equal-weight or stop-sized, rebalanced weekly or monthly, and most cut winners with stops. This
card copies a live index that has beaten the S&P 500 after fees for ten years: it stays fully invested, keeps market
cap in the weights (so it still owns the giants when they lead), adjusts momentum for volatility, and trades only twice
a year. Batches 5-7 showed short holds lose to costs and part-invested books lose to SPY; this card is neither.

## One-line summary
Every March and September, hold the 100 of the 500 largest stocks with the best volatility-adjusted 12-month
momentum (skipping the last month), weighted by market cap times momentum score.

## Evidence
- Live ETF record (https://etfsavant.com/mtum-vs-spmo/, opened): SPMO (S&P 500 Momentum) daily returns since Oct 2015:
  alpha +4.41% a year vs the S&P 500, beta 0.97; 10-year annualised return 20.27%. MTUM (MSCI version, different
  rules): alpha +0.63%, beta 1.05. Net of fund fees.
- S&P DJI practitioner's guide (https://www.spglobal.com/spdji/en/education/article/momentum-a-practitioner-s-guide/,
  opened): semiannual rebalance after the third Friday of March and September, reference dates the last business
  day of February and August; 12 months of returns ending one month before the reference date; scores risk-adjusted.
  Outperformance concentrated in 1995-2000 and 2023-2026; momentum is hit hardest when a bubble bursts.
- Against: most of the live alpha came in 2023-2026, the strongest momentum stretch since the dot-com years
  (Natixis/Oakmark, https://www.im.natixis.com/en-us/insights/equities/2026/what-history-tells-us-about-momentum,
  opened). Grade B- for a live, net-of-fee record; the selection bias is stated above.

## Engine version (pre-register this one)
- Reference date: last session of February and August. Rebalance: fill at the open of the session after the third
  Friday of March and September (the index trades at that close; next open is the registered deviation).
- Momentum value: price return from the close 13 months before the reference date to the close 1 month before it,
  divided by the standard deviation of daily price returns over that same 12-month span.
- Z-score across the 500, winsorised at +/-3. Score = 1 + z if z > 0, else 1 / (1 - z).
- Select the 100 highest z. Buffer: a current holding stays if it ranks in the top 120; a new name enters only in the
  top 80; fill to 100 by rank.
- Weight = mcap_pit x score, normalised; each name capped at the lower of 9% and 3 x its weight in the 500-stock
  cap-weighted universe; excess redistributed pro rata. No stops (the index has none).
- Excluded: stocks with fewer than 252 sessions of history on the reference date.
- The details beyond the guide (buffer bands, the score mapping, the caps) follow my reading of the S&P momentum
  methodology and are stated here as the registered rule, not as a quote.

## Grading
Weights-card grading (as the VRP overlay): daily net returns vs SPY in both windows; alpha, alpha t, beta, return,
deepest drop, worst month, share of months up; haircut over this batch's trials. Turnover expected 80-150% a year.

## Expectation stated before the run
2017-24: alpha 0% to +3% a year, t below 1.5 (2018 and 2022 momentum reversals hurt). 2024-26: alpha +3% to +8% a
year (the momentum boom), t near 1.5-2. Deepest drop a few points worse than SPY's. Likely FAIL on alpha t in at
least one window; if it passes, it goes to forward test only.

## Common mistakes
Using today's S&P 500 list (survivorship); reading momentum through the rebalance month; dividends missing from
price-only bars (affects both the book and SPY the same way if both are price-only).
