---
slug: industry_neutral_momentum_sp500
name: Industry-neutral 12-1 momentum in the 500 largest stocks - best 100 by return above their industry's median, quarterly, equal weight
originators: [Moskowitz & Grinblatt (1999, JF); Asness, Porter & Stevens (2000) "Predicting stock returns using industry-relative firm characteristics"; Novy-Marx (2012)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; sic2; quarterly rebalance
direction: long
universe: the 500 largest by mcap_pit on the reference date, as-traded close >= $10, >= 273 sessions of bars
regimes_good: [trend]
regimes_bad: [momentum_crash]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 12, 2026-10-14). WEIGHTS CARD. Momentum family, trial 4 (after batch 9's replica and batch 10's two). Chosen knowing batch 9-10 results; NOT a tuning of the replica (different signal construction, stated below).
---

# Industry-neutral momentum, S&P 500 universe

## Why this card exists, and what was known when it was chosen
Batch 9's momentum-index replica beat SPY in both halves but its alpha t (1.30, 0.73) missed the bar; batch 10 ran
the same rules on mid and small caps and failed. A large part of a raw momentum book's tracking error is industry
bets (in 2017-26: whole tech or energy groups), which adds noise without adding much return: industry-relative
momentum has historically had a similar spread with lower volatility, so a higher information ratio. This card
changes the signal, not the settings of the replica: it ranks each stock against its own industry and holds the
best 100 equally. It is counted honestly as the **fourth trial of the momentum family**, so its bar is higher.

## Evidence
- Asness, Porter & Stevens (2000): industry-adjusted momentum and value predict returns better than raw versions.
- Moskowitz & Grinblatt (1999): much of raw momentum is industry momentum; the within-industry part is the residual
  this card keeps.
- Grade B for the effect existing; its strength after 2016 in large caps is unknown.

## Engine version (pre-register this one)
- Reference date: the last session of February, May, August and November. Orders at the open of the session after
  the third Friday of the following month (March, June, September, December), as the batch-9 timing.
- Universe on the reference date: the 500 largest by `mcap_pit`, as-traded close >= $10, at least 273 sessions of
  bars.
- Raw momentum: close 21 sessions before the reference date over close 273 sessions before, minus 1 (12-1).
- Industry: `sic2` (current two-digit SIC; it is not point-in-time, but a company's two-digit SIC rarely changes;
  stated as a known limit). Industries with fewer than 5 universe members are pooled into one "other" group.
- Score: raw momentum minus the median raw momentum of its industry group on that date.
- Holdings: the 100 highest scores, with a buffer: a current holding stays while it ranks within the top 150; new
  names fill from the top until there are 100.
- Weights: equal, 1% each. **Cash treatment:** if fewer than 100 names qualify, the unused weight is held in SPY.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier.
- First trade: March 2017 (needs 273 sessions from 2016-01). Until then the book holds SPY.
- Expected turnover (stated before the run): about 40-50% of names replaced per quarter, so about 160-200% a year
  one-way; at about 10 bp per side for these names, costs of about 0.3-0.4% a year.

## Grading (docs/gates.md, including "Full-period test" and "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: momentum family count 4. Bar: `alpha_t_critical(4)` = 2.498.
Beside the verdict: tracking error against SPY, and the same numbers for batch 9's replica over the pooled window
(descriptive only; the replica is not re-graded).
CZ check (docs/gates.md): compare this card's monthly top-minus-universe return with the Chen-Zimmermann
industry-adjusted momentum portfolio, if the Mac can do the hand download; otherwise note that it was skipped.

## Expectation stated before the run
Equal weight across 100 of the 500 largest gives up the mega-cap tilt that helped batch 9 in 2024-26, so its return
is likely below the replica's. Tracking error maybe 6-8% a year against SPY; alpha 0 to +3% a year; alpha t under
1.5 pooled. Likely FAIL.
