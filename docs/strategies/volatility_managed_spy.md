---
slug: volatility_managed_spy
name: Volatility-managed SPY, scale exposure by inverse realized variance, capped at 100% (Moreira-Muir)
originators: [Moreira & Muir, "Volatility-Managed Portfolios", Journal of Finance 72(4) 2017]
category: strategy
decision: implement
holding_period_days: [21, 21]
timeframe: daily bars (SPY), monthly rebalance
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [v_shaped_rebound]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 2, 2026-10-10; not in catalog yet)
---

# Volatility-managed SPY

## Why this one is different from what failed
No stock selection at all: it holds SPY and only varies how much. Its failure mode is mistimed de-risking (cutting
exposure before a fast rebound), not breadth or single-stock costs. It is also the one candidate whose published
evidence is honestly weak out of sample, so it doubles as a control for the batch.

## One-line summary
Each month, hold SPY at a weight inversely proportional to last month's realized variance, capped at 100% (cash
account): less exposure after turbulent months, full exposure in calm ones. Volatility clusters but returns do not
rise with it, so risk-adjusted returns improve in-sample.

## Origin and lineage
- Moreira & Muir, JF 72(4) 2017. Peer-reviewed. Read: NBER w22208
  https://www.nber.org/system/files/working_papers/w22208/w22208.pdf (published tables not opened).
- Critiques: Cederburg, O'Doherty, Wang & Yan, JFE 2020 (https://www.lehigh.edu/~xuy219/research/COWY.pdf); Liu,
  Tang & Zhou, JPM 2019; Barroso & Detzel, JFE 2021.
- Engine relatives: catalog `volatility_scaling_book` (Barroso-Santa-Clara, scales the strategy book, not a
  standalone SPY strategy); `vix_level_regime`, `trend_filter_10m_200d` (regime flags).

## Exact rules (as published, market factor)
1. RV_t = realized variance of daily market returns over the prior month (22 trading days).
2. Managed exposure next month = c / RV_t; c set so the managed series has the buy-and-hold volatility (full-sample:
   look-ahead, but it does not change the Sharpe ratio). Monthly rebalance.
3. Variants: scale by 1/RV (volatility); cap leverage at 1.0 or 1.5.

## Engine version (pre-register this one)
- Instrument: SPY. Rebalance at the last NYSE session of each month (`month_end` = 1), fills next open.
- RV = sum of squared daily SPY close-to-close log returns over the last 22 sessions (one month).
- Target weight w = min(1.0, c / RV), with c fixed in advance as the monthly variance of a 16% annualised volatility:
  c = 0.16^2 / 12 = 0.002133. (No fitting: 16% is chosen before seeing any engine result; it sits below SPY's long-run
  volatility so the cap binds in calm months.)
- Trade only if |w_new - w_held| >= 0.10 (no-trade band, cost control). Remainder in cash (zero return).
- No stop, no target, no regime gate.
- Costs: per-stock model for SPY on traded notional (floor 10 bp/side).

## Grading (same grader addition as `fomc_cycle_even_weeks`)
Daily net returns. Primary: alpha t-stat from regressing on daily SPY returns, haircut over the batch-2 group size;
also net Sharpe vs SPY buy-and-hold, average weight, turnover. Pass = positive haircut alpha in both windows.

## Evidence
- Moreira-Muir (1926-2015, gross, uncapped): market alpha 4.86% a year (s.e. 1.56), beta 0.61 (Table 1); Sharpe 0.52
  managed vs 0.42 buy-and-hold. Weights are levered: 75th percentile 1.59, 99th 6.39 (Table 5A).
- Capped at 1.0 (the engine's case): alpha 2.12% a year (s.e. 0.71), Sharpe 0.52; 1.93% at 10 bp costs, 1.85% at
  14 bp; break-even cost 110 bp (Tables 4, 5A).
- Out of sample, against: Cederburg et al. (through 2016) find the real-time market version has Sharpe 0.42 vs 0.46
  unmanaged (difference not significant, p=0.64), and real-time versions lose to the unmanaged factor in 72 of 103
  strategies; leverage caps do not systematically help (Tables 5-7). Liu-Tang-Zhou (abstract): after removing
  look-ahead, drawdowns of 68-93% and outperformance only in the financial crisis.
- Partly for: Barroso-Detzel (abstract) find the managed market's abnormal returns survive costs (other factors do
  not), concentrated in high-sentiment periods.
- Grade C: strong in-sample, cost-robust, but the main real-time tests say it does not beat holding the market.

## Why it might beat costs where the others failed
Monthly, one ETF, a 10-point no-trade band: costs are a few bp a year. Whether there is any edge to keep is the open
question; the test is cheap and its failure mode is uncorrelated with the stock strategies.

## Common mistakes
Fitting c on the full sample; letting weights exceed 1 in a cash account; judging it on absolute Sharpe in a bull
window.

## Signs of decay to monitor
Trailing 3-year alpha vs SPY <= 0.

## Empirical (replay)
Pre-registered batch 2 group (docs/preregistration/2026-10-10-batch2.md), n_trials = 3. **FAIL**. Full tables: docs/preregistration/2026-10-10-batch2-results.md.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| volatility_managed_spy | 2024 | 6 | +0.192 | 2.06 | 0.87 | 0.31 | 0.64 | 14.8% | 79 | 38% | +23.3% |
| volatility_managed_spy | 2017 | 35 | +0.106 | 1.51 | 0.71 | 0.52 | 0.86 | 22.1% | 54 | 107% | +85.4% |

Against buy-and-hold SPY:

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| volatility_managed_spy | 2024 | -5.6% | -0.90 | -0.90 | -1.3% | -0.38 | 0.74 | 89% | 0.87 | 1.03 |
| volatility_managed_spy | 2017 | -5.0% | -0.52 | -0.52 | +0.6% | 0.30 | 0.59 | 82% | 0.71 | 0.75 |
