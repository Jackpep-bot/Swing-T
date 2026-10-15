---
slug: sp500_low_volatility_replica
name: S&P 500 Low Volatility index replica - the 100 least volatile of the 500 largest, inverse-volatility weights, quarterly
originators: [S&P Dow Jones Indices "S&P 500 Low Volatility Index" methodology (2011); Baker, Bradley & Wurgler (2011, FAJ); Frazzini & Pedersen (2014, JFE) "Betting against beta"; Haugen & Heins (1975)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; quarterly rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $5, >= 253 sessions of bars
regimes_good: [crash, bear, rate_cut]
regimes_bad: [speculative_rally, mega_cap_led_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 17, 2026-10-14). WEIGHTS CARD. New family (low risk); 1 trial. Bar set at alpha_t_critical(2) on purpose, see Grading.
---

# Low-volatility large caps (S&P 500 Low Volatility replica)

## Why this card exists, and what was known when it was chosen
Every stock book tested so far carried a beta near 1, so it could only beat SPY by out-picking a mega-cap-led market,
and none did with a usable t. The low-risk anomaly is the one long-only, large-cap, low-turnover effect we have not
tested: the least volatile stocks have earned about the market's return with roughly two-thirds of its risk, so their
CAPM alpha is positive. With alpha measured as the intercept of (r - BIL) on (SPY - BIL), a beta-0.65 book can earn
alpha while making less than SPY.

Known when choosing: the premise library (746f611) shows AQR's US BAB factor with CAPM alpha t 7.48 over 1930-2026 but
only 1.08 since 2017. That is weak recent evidence, and it is why the card expects a likely FAIL. It was **not** picked
from the Chen-Zimmermann since-2017 ranking (see the README for why those were set aside), so no selection from 208
predictors applies to it.

## Evidence
- Haugen & Heins (1975) and Baker, Bradley & Wurgler (2011): low-volatility US stocks matched or beat high-volatility
  ones over decades with far less risk.
- Frazzini & Pedersen (2014): betting against beta works in US stocks, 20 international markets, bonds and futures.
- Live product: SPLV (Invesco S&P 500 Low Volatility) has tracked this index since 2011. Grade B: long record, a real
  index, but low volatility lagged SPY badly in the 2020-21 and 2023-26 rallies.

## Engine version (pre-register this one)
- Reference date: the last session of January, April, July and October (the index's schedule). Orders at the open of
  the session after the third Friday of the following month.
- Universe on the reference date: the 500 largest by `mcap_pit`, as-traded close >= $5, at least 253 sessions of bars.
- Volatility: standard deviation of the last 252 daily close-to-close returns, annualised (x sqrt(252)).
- Holdings: the 100 lowest-volatility names, with a buffer to cut churn: a current holding stays while it ranks within
  the lowest 130; new names fill from the lowest volatility up until there are 100. (The published index has no buffer;
  this one change is stated here, before the run, to keep turnover down.)
- Weights: proportional to 1 / volatility, each capped at 3% (excess spread pro rata over the uncapped names), summing
  to 1. Between rebalances the weights drift with prices.
- **Cash treatment:** fully invested; no cash, no BIL. If fewer than 100 names qualify, the unused weight is held in
  SPY. Before the first rebalance (February 2017) the book holds SPY.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier.
- Costs: `weights_book.simulate` with the per-symbol cost table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover, from the rank buffer and the weighting rule: volatility ranks are sticky, but earlier rank-buffer
  books replaced about 40% of names a rebalance against estimates of 15-25%. Taking that lesson: about 20-35% of names
  replaced per quarter plus inverse-volatility re-weighting of the rest, so **80-150% a year one-way**; costs about
  0.1-0.2% a year.

## Price-only data note
The store is price-only for the book and for SPY. Low-volatility stocks (utilities, staples, REITs, insurers) yield
about 1-1.5 points a year more than SPY, so price-only grading understates the book against SPY by about that much,
and the bias is against the card. The grade uses the price-only store as registered; the total-return store's figure
is reported beside it, descriptive only.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: 1 trial of a new family. Bar: `alpha_t_critical(2)` = 2.241, one step above a single trial, because the family
was chosen after reading the AQR table in the premise library (7 factors seen).
Beside the verdict, descriptive only: beta, return per year, deepest drop, tracking error against SPY, the
total-return-store alpha, and the correlation of monthly excess-of-SPY returns with `sp500_momentum_index_replica`
(a low correlation is what would make it useful next to the shadowed replica).

## Expectation stated before the run
Return about 7-10% a year against SPY's 13.6% price-only, beta 0.55-0.75, a smaller drop than SPY in 2020 and 2022.
Alpha about -1% to +2% a year, pooled alpha t under 1. Likely FAIL. Its value if it fails is the companion premise
check and the correlation with the replica.
