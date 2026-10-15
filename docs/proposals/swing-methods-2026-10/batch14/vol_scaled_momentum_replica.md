---
slug: vol_scaled_momentum_replica
name: Batch 9's S&P 500 momentum replica with a book-level volatility target (Barroso & Santa-Clara scaling), exposure capped at 100%, rest in BIL
originators: [Barroso & Santa-Clara (2015, JFE) "Momentum has its moments"; Daniel & Moskowitz (2016, JFE) "Momentum crashes"; Moreira & Muir (2017)]
category: strategy
decision: implement
holding_period_days: [21, 126]
timeframe: daily bars; mcap_pit; monthly exposure update on top of semiannual selection
direction: long
universe: as sp500_momentum_index_replica (batch 9)
regimes_good: [trend]
regimes_bad: [v_shaped_rebound]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 14, 2026-10-14). WEIGHTS CARD. A new rule on top of batch 9's replica (not a resubmission; the replica itself is not re-graded). Momentum family trial 6. Chosen knowing the replica's results.
---

# Volatility-scaled momentum replica

## Why this card exists, and what was known when it was chosen
The replica is the nearest miss so far (pooled +19.0% a year, alpha +4.9%, t 1.51; now in shadow tracking). Its
risk comes in bursts (momentum crashes when markets rebound sharply). Barroso & Santa-Clara found that scaling a
momentum book by its own recent volatility roughly doubles the Sharpe ratio and cuts the worst month from -79% to
-28%, for long-short momentum in 1927-2011. For a long-only book the gain is expected to be smaller and is untested
in that work. Scaling changes the book's exposure over time, which is a different rule; it is counted as a new
momentum trial and the replica's selection and weights are **not** changed.

## Engine version (pre-register this one)
- Base book: every rule of `docs/proposals/swing-methods-2026-10/batch9/sp500_momentum_index_replica.md` unchanged
  (universe, reference dates, score, weights and caps, semiannual rebalance), giving target weights w_base.
- Exposure: on the last session of each month, sigma = standard deviation of the **base book's** daily net returns
  over the last 126 sessions x sqrt(252) (the base book is simulated alongside; before 126 sessions of base-book
  history exist, exposure = 1). Exposure e = min(1.0, 0.15 / sigma). The 15% target is SPY's approximate long-run
  annual volatility, a round number fixed before the run, not fitted to the replica.
- Held weights: e x w_base in the stocks, (1 - e) in BIL. Exposure changes trade at the next session's open, and only
  when |e_new - e_held| >= 0.10 (to limit turnover); the semiannual selection still trades on its own dates.
- **Cash treatment:** the unscaled part sits in BIL (about zero return in this price-only store); this is the rule
  being tested, so it does not park in SPY. Before the base book's first rebalance the book holds SPY.
- No stops. Delisting as the replica.
- Expected turnover: the replica's own (about 60-100% a year) plus exposure moves; with the 0.10 threshold, perhaps
  4-8 exposure changes a year of 0.1-0.3 each, trading the whole stock sleeve pro rata: about 150-250% a year one-way
  in total; costs about 0.2-0.3% a year.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
As the composite card: daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL), windows A, B and pooled
2017-01-01 .. 2026-10-05 as one simulation; PASS on either route. Trials: momentum family count 6; bar
`alpha_t_critical(6)` = 2.638.
Beside the verdict, descriptive only: average exposure, the share of days below 1.0, the worst month against the
unscaled replica's worst month, and the unscaled replica's pooled numbers for reference (not re-graded).

## Expectation stated before the run
The replica's realised volatility was probably near or above 15% for much of 2020, 2022 and 2025, so exposure would
have been cut then. Lower return than the replica (perhaps 14-17% a year) with a shallower worst drop; alpha t may rise
a little if the cuts land in crash months, or fall if they miss rebounds (2020). Pooled alpha t about 1-2. Likely FAIL
on the 2.638 bar.
