---
slug: multi_asset_trend_long_flat
name: Multi-asset time-series momentum, long-or-flat, across nine ETFs with volatility-scaled weights, monthly
originators: [Moskowitz, Ooi & Pedersen (2012, JFE) "Time series momentum"; Hurst, Ooi & Pedersen (2017, JPM) "A Century of Evidence on Trend-Following Investing"; Faber (2007)]
category: strategy
decision: implement
holding_period_days: [21, 21]
timeframe: daily bars of nine ETFs; monthly rebalance
direction: long
universe: SPY, EFA, EEM, VNQ, IEF, TLT, GLD, DBC, UUP
regimes_good: [trending, crisis]
regimes_bad: [choppy_reversals]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 12, 2026-10-14). WEIGHTS CARD. New family (cross-asset trend); 1 trial. Needs the nine ETFs' daily bars from 2016-01 added to the research store (free; same feed as SVXY/IWD/IWF/BIL).
---

# Multi-asset trend, long or flat

## Why this card exists
Eleven batches of long-only US stock books have failed, almost all with beta near 1 and negative alpha against a
2017-26 SPY that was led by a few mega caps. With the bill-rate fix, alpha is now the intercept of (r - BIL) on
(SPY - BIL), so a book whose returns do not come from SPY can earn alpha even if its raw return is below SPY's. This
card is the most-studied such book that needs only free daily ETF bars: hold each of nine asset-class ETFs when its
own 12-month trend is up, sized so each contributes similar risk, otherwise hold nothing in it. It is a different
family from every card so far (not a stock selector, not an event).

## Evidence
- Moskowitz, Ooi & Pedersen (2012): 12-month time-series momentum positive in all 58 futures markets tested
  1985-2009, diversified Sharpe above 1 gross.
- Hurst, Ooi & Pedersen (2017): positive in every decade since 1880; low correlation to equities; strongest in
  crises. Live managed-futures indices had a weak 2012-2019 and a strong 2022. Grade B (long record; the long-or-flat
  ETF version here gives up the short side).

## Engine version (pre-register this one)
- Assets (fixed list): SPY, EFA, EEM, VNQ (stocks and REITs), IEF, TLT (Treasuries), GLD (gold), DBC (commodities),
  UUP (US dollar). All trade from before 2016.
- Signal day: the last session of each month. Orders at the next session's open.
- Trend: asset i is ON when its close on the signal day is above its close 252 sessions earlier (12-month price
  return > 0; bills earn about nothing in this price-only store, so "excess over bills" and "above zero" agree).
- Volatility: sigma_i = standard deviation of the last 63 daily close-to-close returns x sqrt(252).
- Weight: w_i = (0.10 / 9) / sigma_i for each ON asset, 0 for each OFF asset (a 10% a year risk budget shared
  equally across the nine). Each w_i is capped at 0.30. If the weights sum to more than 1, all are scaled down to sum
  to 1 (no leverage).
- **Cash treatment:** whatever the weights leave unused is held in BIL (price-only, so about zero return). This is
  stated on purpose: unlike the stock cards, this book's job is to be different from SPY, so it does not park spare
  weight in SPY.
- No stops. First signal day 2016-12-30 (needs 252 sessions from 2016-01).
- Costs: `weights_book.simulate` with the per-symbol cost table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover (stated before the run): about 150-250% a year one-way (monthly weight changes plus several
  trend flips a year per asset), so costs of roughly 0.2-0.3% a year at 10 bp.

## Price-only data note
The store is price-only. IEF, TLT, VNQ and EFA/EEM pay meaningful distributions (about 2-4% a year) that this
book does not get, while SPY loses about 1.5% a year on its side. The bias is against the book when it holds bonds or
REITs. The grade uses the price-only store as registered.

## Grading (docs/gates.md, including "Full-period test" and "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: 1 trial of a new family. Bar: `alpha_t_critical(2)` = 2.241 (2 cards in the batch).
Beside the verdict: return per year, deepest drop, beta, and the correlation of monthly returns with SPY.

## Expectation stated before the run
Return about 3-6% a year with beta 0.2-0.4 and a smaller deepest drop than SPY (it would have been mostly out of
stocks and bonds in 2022). Alpha about 0 to +3% a year, alpha t under 1.5 after the price-only drag on bonds.
Likely FAIL on the t bar; useful as the first low-beta diversifier with a full grade.
