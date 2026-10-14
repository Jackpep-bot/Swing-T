---
slug: global_equities_dual_momentum
name: Antonacci's Global Equities Momentum (dual momentum) - SPY or EFA when US stocks beat bills over 12 months, else Treasuries (IEF), monthly
originators: [Gary Antonacci (2014) "Dual Momentum Investing"; Antonacci (2012) "Risk Premia Harvesting Through Dual Momentum"; Moskowitz, Ooi & Pedersen (2012)]
category: strategy
decision: implement
holding_period_days: [21, 21]
timeframe: daily bars of SPY, EFA, IEF; monthly signal
direction: long
universe: SPY, EFA, IEF (fixed list)
regimes_good: [trending, long_bear]
regimes_bad: [v_shaped_crash, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 20, 2026-10-14). WEIGHTS CARD. Cross-asset trend family, trial 2 (after batch 12's multi_asset_trend_long_flat). Bar alpha_t_critical(2).
---

# Global Equities Momentum (dual momentum)

## Why this card exists
It is one of the most followed rule-based methods among retail and online traders (Antonacci's book, many blogs and
newsletters run it live), and Jack asked for the methods traders actually use to be tested. It is also cheap to test
and the opposite of everything that failed: three ETFs, one holding at a time, one to three switches a year. Absolute
momentum (stocks vs bills) is meant to step aside in long bear markets; relative momentum (US vs international) picks
the stronger market.

## Evidence
- Antonacci (2014): 1974-2013 backtest about 17% a year vs about 12% for the S&P 500 with half the deepest drop.
  Grade C: the author's own backtest of a rule he designed, and live followers report a weak 2018-2023 (whipsaws in
  late 2018, March 2020 and 2022-23).
- Moskowitz, Ooi & Pedersen (2012): the absolute-momentum part is time-series momentum, grade B on its own.

## Engine version (pre-register this one)
- Signal day: the last session of each month. Orders at the next session's open.
- 12-month returns: close on the signal day over close 252 sessions earlier, minus 1, for SPY, EFA and BIL.
- Rule: if SPY's 12-month return is above BIL's, hold 100% of whichever of SPY and EFA has the higher 12-month return;
  otherwise hold 100% IEF.
- Substitution stated before the run: Antonacci uses AGG (US aggregate bonds); the store has IEF (7-10 year Treasuries),
  not AGG. IEF is longer and riskier than AGG (it fell more in 2022).
- **Cash treatment:** always fully invested in one ETF; never cash or BIL as a holding (BIL is only the hurdle).
- No stops. First signal day 2016-12-30 (needs 252 sessions from 2016-01).
- Costs: `weights_book.simulate` with the per-symbol cost table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover, from the rule: each switch sells 100% and buys 100% (100% one-way). Live records show one to three
  switches a year, so **100-300% a year one-way**; costs under 0.1% a year at ETF spreads, up to 0.3% at the 10 bp
  default.

## Price-only data note
The store is price-only: IEF pays about 2-3% a year and EFA yields about 1.5 points more than SPY, none of which this
book gets, while SPY loses about 1.5%. The bias is against the book whenever it holds IEF or EFA. The grade uses the
price-only store as registered; the total-return figure is reported beside it, descriptive only.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: cross-asset trend family count 2. Bar: `alpha_t_critical(2)` = 2.241.
Beside the verdict, descriptive only: return per year, deepest drop, number of switches, share of months in each ETF,
and the correlation of monthly excess-of-SPY returns with `sp500_momentum_index_replica`.

## Expectation stated before the run
2017-26 was led by US stocks with sharp V-shaped drops, the worst case for this rule: it likely sat in SPY most of
the time and switched late around 2018, 2020 and 2022. Return about 8-11% a year against SPY's 13.6%, beta about 0.7,
alpha about -3% to +1% a year. Likely FAIL; it records how a popular trader method did in this decade.
