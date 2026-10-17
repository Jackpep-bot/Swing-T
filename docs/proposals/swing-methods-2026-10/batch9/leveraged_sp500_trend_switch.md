---
slug: leveraged_sp500_trend_switch
name: Leverage rotation - hold 2x S&P 500 (SSO) while SPY is above its 200-day average, T-bills (BIL) below it
originators: [Gayed & Bilello, "Leverage for the long run" (2016, CMT Charles H. Dow Award)]
category: strategy
decision: implement
holding_period_days: [5, 400]
timeframe: daily bars SPY, SSO, BIL
direction: long
universe: SSO / BIL (SPY for the signal only)
regimes_good: [trend]
regimes_bad: [whipsaw]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 9, 2026-10-14). WEIGHTS CARD (100% in one ETF at a time).
---

# Leveraged S&P 500 trend switch

## Why this one is genuinely different
Every card so far tried to pick better stocks than the index and lost. This one does not pick stocks: it owns the
index at double exposure only while the market is trending up and steps aside into T-bills when it is not, which is
when leveraged funds do most of their damage. It is fully invested whenever it is in, trades a handful of times a
year, and its edge (if any) is avoiding the volatility drag that ruins buy-and-hold leverage, not out-guessing anyone.
Jack's stated goal is money made and drawdown first; this card is judged that way as well as on alpha.

## One-line summary
At each close, if SPY is above its 200-day simple average, hold SSO; otherwise hold BIL; switch at the next open.

## Evidence
- CXO summary of Gayed & Bilello (https://www.cxoadvisory.com/volatility-effects/leveraging-the-u-s-stock-market-based-on-sma-rules/,
  opened): S&P 500 total return, Oct 1928-Oct 2015, 1% a year leverage cost, no switching costs. Sharpe: buy and hold
  1x 0.30, buy and hold 2x 0.27; 200-day timing 1x 0.60, 2x 0.51. Max drawdown: 1x hold -86%, 2x hold -99%, 1x timing
  -50%, 2x timing -78%. The index averaged +14.1% a year above its 200-day and -2.3% below.
- Against: no post-2015 test in the source; 200-day rules whipsaw in choppy years (2015-16, 2022). Grade C.

## Engine version (pre-register this one)
- Signal at the close: SPY close vs its 200-session simple average of closes. Above: target SSO 100%. At or below:
  target BIL 100%.
- Band against whipsaw: switch to SSO only when SPY closes >= 1.01 x the average; switch to BIL only when SPY closes
  <= 0.99 x the average.
- Fill at the next open. Costs: engine ETF cost model on traded notional; SSO's expense ratio is inside its price.
- Before BIL history exists in the store, BIL's return is zero (recorded).

## Grading
Weights-card grading: daily net returns vs SPY in both windows; alpha, alpha t, beta, return, deepest drop, worst
month, share of months up, number of switches; haircut over this batch's trials. Beta will be near 2 while invested,
so report return and drawdown beside SPY's first, as Jack asked.

## Expectation stated before the run
2017-24: return above SPY's (about +15% to +20% a year vs +12%), deepest drop -30% to -40% (2020 and 2022), alpha
near zero or negative after beta. 2024-26: return well above SPY's, with the April 2025 drop partly avoided depending
on the timing of the 200-day cross. Likely FAIL on alpha t; the money-made view is the point of this card.

## Common mistakes
Using SPY's own adjusted closes for the signal and unadjusted for the trade; ignoring the overnight gap on switch days.
