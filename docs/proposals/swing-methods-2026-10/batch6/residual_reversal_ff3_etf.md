---
slug: residual_reversal_ff3_etf
name: One-month residual reversal (factor-neutral losers), 500 largest stocks, monthly
originators: [Blitz, Huij, Lansdorp & Verbeek, "Short-term residual reversal", Journal of Financial Markets 16(3) 2013]
category: strategy
decision: implement
holding_period_days: [21, 21]
timeframe: daily bars, monthly rebalance
direction: long
universe: the 500 largest store stocks by mcap_pit on the rebalance day, close >= $5
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 6, 2026-10-13; variant of catalog short_term_reversal_1m)
---

# One-month residual reversal

## Why this one is genuinely different
Every family replayed so far lost to SPY mainly because its apparent edge was market beta. `short_term_reversal_1m`
ranks on the raw one-month return, so its losers are mostly high-beta names in a falling month. This card ranks on the
part of the month's return that the market, size and value moves do NOT explain, scaled by how noisy that stock
normally is. The losers it buys are stocks that fell for stock-specific, non-factor reasons, which is the piece of
reversal the paper says survives costs. It is the only reversal card in the catalog that removes beta before ranking.

## One-line summary
Each month, buy the 50 large caps whose last-month factor-adjusted return was most negative relative to their own
residual volatility; hold one month.

## Evidence
- Blitz et al. (via CXO, https://www.cxoadvisory.com/technical-trading/purified-short-term-stock-reversal/, opened):
  US stocks above the NYSE median cap, 1926-2008. Residual reversal 1.34% a month gross (Sharpe 1.28) vs 0.97%
  (Sharpe 0.62) for the raw version; residual version still above 8% a year net of institutional costs, breakeven
  round trip about 0.56%; net 0.67% and 0.81% a month in the 500 and 100 largest stocks. Long-short, monthly.
- Against: Robeco 2023 says classic reversal has largely gone (batch 5 README); no post-2008 net test of the residual
  form found. Long leg only here, so half the spread at best. Grade C.

## Engine version (pre-register this one)
- Factors, point-in-time from the store's own bars (the Kenneth French files lag 1-2 months, so they cannot score
  the month just ended): MKT = SPY daily return; SMB = IWM - SPY; HML = IWD - IWF (Russell 1000 value minus growth
  ETFs). Needs daily bars for IWM, IWD, IWF from 2014 (same Alpaca bars source, no new data source).
- Betas: regress each stock's daily excess return on the three proxies over the 756 sessions ending 22 sessions
  before the rebalance day (at least 500 sessions present).
- Score: sum of the last 21 sessions' residuals (that fit's betas applied to those sessions) divided by the
  standard deviation of the fit's residuals. Rank ascending.
- Rebalance on the last session of each month at the close signal, fill at the next open. Hold the 50 lowest scores
  equal weight. Keep a holding while it ranks in the lowest 100 (buy/hold band, as `composite_cost_aware_rank`).
- Exclusions: an 8-K Item 2.02 (earnings) in the 21-session window, and `event_avoid_filters`. No stop beyond the
  engine's catastrophe stop (20% from entry): the paper has none.

## Grading
Portfolio card: monthly book graded on alpha vs SPY from daily net returns in both windows (2017-01..2024-10 and
2024-10..2026-10), haircut over this batch's trials. Also report the income view (return, deepest drop, % of
months up).

## Expectation stated before the run
Alpha vs SPY about 0 to +2% a year in 2017-24, t below 1.5; 2024-26 about zero. Beta near 1 (long only), so total
return tracks SPY; the test is whether the residual loser book adds anything.

## Common mistakes
Using French factors for the scoring month (look-ahead by the publication lag); raw instead of standardised
residuals; letting earnings-month losers in (those drift, not reverse).
