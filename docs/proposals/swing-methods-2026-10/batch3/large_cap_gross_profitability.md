---
slug: large_cap_gross_profitability
name: Large-cap gross profitability, long the most profitable of the 500 largest non-financials (Novy-Marx 2013)
originators: [Novy-Marx, "The Other Side of Value: The Gross Profitability Premium", JFE 108(1) 2013]
category: strategy
decision: implement
holding_period_days: [63, 504]
timeframe: monthly check, annual-speed signal; daily bars + EDGAR XBRL (GrossProfit, Assets)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, correction]
regimes_bad: [junk_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 3, 2026-10-10; not in catalog as a standalone strategy)
---

# Large-cap gross profitability

## Why this one is different from what failed
The catalog's `gross_cash_profitability` was never built as a standalone strategy; gross profitability only entered
the engine as one of four ranks inside `composite_cost_aware_rank`, which traded the broad top-1,500 universe and
failed in 2024-26. This card isolates the signal, restricts it to the 500 largest non-financial stocks, and trades it
at its natural (annual) speed, so costs are near zero. Large, highly profitable companies are what the 2024-26 tape
rewarded, so the failure mode here is "no alpha beyond SPY", not "small caps lagged".

## One-line summary
Hold the third of the 500 largest non-financial US stocks with the highest gross profit to assets; replace a name only
when it falls out of the top half. Turnover is roughly a name every few years.

## Origin and lineage
- Novy-Marx 2013, JFE. Read: https://www.johnhcochrane.com/s/Novy_marx_OSoV.pdf and
  https://oldschoolvalue-files.s3.amazonaws.com/pdf/Novy-Marx_Gross-Profitability-Anomaly_JFE_2013.pdf
- Costs: Novy-Marx & Velikov 2016, https://www.nber.org/papers/w20721.pdf
- Engine: `data.fundamentals.gross_profitability_asof` already computes TTM GrossProfit / latest Assets, point in time
  by filing date (docstring cites Novy-Marx).

## Exact rules (as published)
1. GP/A = (revenue - cost of goods sold) / total assets, annual Compustat, used from the end of June of the following
   year; financials (SIC 6xxx) excluded; rebalanced each June.
2. Large-cap test (Table 7): the 500 largest non-financial stocks, sorted into GP/A tertiles.

## Engine version (pre-register this one)
- Rebalance check: last NYSE session of each month (`month_end` = 1); fills next open.
- Universe: the 500 largest names by market cap (close x `shares_outstanding_asof`) in the replay universe, excluding
  financials. The store has no SIC codes, so "financial" = no `GrossProfit` value in the last 4 quarters (banks and
  insurers do not report it). Names without GrossProfit are excluded, never filled with revenue. Log how many of the
  500 drop out this way.
- Signal: `gross_profitability_asof(fund, symbol, day)` (TTM gross profit over latest assets, filed on or before the
  signal day). NaN = excluded.
- Buy zone: top third of GP/A in the universe. Hold zone: top half. Sell only when a name leaves the hold zone or the
  universe. Equal weight, max 60 names.
- Catastrophe stop 3 x `atr_63` (the engine needs a stop to size; same as the other monthly picks). `engine_trail =
  False`, `min_reward_risk = 0`, no target, no regime gate.
- Costs: per-stock model on traded notional.

## Grading
Batch standard (prereg_eval, net of per-stock costs, own holding period) plus alpha vs SPY from daily net returns,
haircut over the batch-3 group size. Pass = the standard rule AND positive haircut alpha vs SPY in both windows (batch
2's repurchasers passed the standard rule with zero alpha, so alpha is the binding test here).

## Evidence
- Novy-Marx 2013, full sample 7/1963-12/2010, value-weighted quintiles (Table 2): long-short 0.31%/month (t=2.49), FF3
  alpha 0.52% (t=4.49).
- Big-size quintile (Table 4): high-minus-low 0.26%/month (t=1.88, not significant raw); FF3 alpha 0.50 (t=3.90).
- 500 largest non-financials (Table 7): high-GP tertile excess return 0.65%/month (t=3.03), FF3 alpha 0.25 (t=3.84),
  market beta 1.02; high-minus-low 0.27 (t=2.33). Part of the FF3 alpha is the growth tilt (negative HML loading).
  No CAPM alpha is reported; a rough reading is 0.15-0.2%/month over the market before costs (our inference).
- Costs: Novy-Marx-Velikov (Table 3A, full universe, value-weighted deciles): turnover 1.96%/month, cost 0.03%/month,
  net 0.37%/month (t=2.74), net FF4 alpha 0.51 (t=3.77). Cheapest anomaly class in their study.
- Recent: Novy-Marx & Medhat (NBER w33601, 2025) find profitability earned more in 2007-2023 (60 bp/month, t=4.84)
  than in 1963-2006 (31 bp, t=3.96), but that is their preferred measure, half small caps, no large-cap split.
- Against: Fama-French RMW was +4.0% in 2023 and 2024 but -10.2% in 2025 and -5.8% Jan-Jul 2026 (compounded from a
  YCharts mirror of the French library; re-check against the French file on the Mac). Ball et al. (JFE 2015) find
  operating profitability is the better measure.
- Grade C: peer-reviewed and cost-proof, but the documented large-cap long side is mostly beta, and the factor was
  sharply negative in the second half of the 2024-26 window.

## Expectation stated before the run
Likely small positive alpha in 2017-24, likely negative in 2024-26 (2025 junk rally). It earns its trial because it
costs almost nothing to trade, the data is already in the store, and it is the cleanest test of "quality large caps"
the engine has not run.

## Common mistakes
Filling missing COGS with zero (turns banks into the most profitable firms); using a single quarter instead of TTM;
reading a 10-K value before its filing date.

## Signs of decay to monitor
Trailing 3-year alpha vs SPY <= 0.
