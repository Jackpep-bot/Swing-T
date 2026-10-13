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
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 80 | 0 | 62% | +0.03 | +0.01 | 63% | +0.02 | +0.00 | 71% | +0.08 | +0.06 | 2.43 |
| correction | 6 | 0 | 33% | -0.06 | -0.09 | 83% | +0.12 | +0.09 | 100% | +0.45 | +0.42 | inf |
| healthy_uptrend | 295 | 0 | 58% | +0.00 | -0.01 | 56% | +0.01 | -0.00 | 63% | +0.02 | +0.01 | 1.48 |
| high_vol_selloff | 59 | 0 | 68% | +0.02 | -0.01 | 71% | +0.05 | +0.01 | 66% | +0.06 | +0.03 | 1.65 |
| narrow_uptrend | 38 | 0 | 46% | -0.01 | -0.02 | 50% | -0.01 | -0.03 | 74% | +0.05 | +0.03 | 3.03 |
| **all** | 478 | 0 | 59% | +0.01 | -0.01 | 59% | +0.02 | +0.00 | 66% | +0.04 | +0.02 | 1.85 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 282 | 0 | 63% | +0.02 | +0.01 | 70% | +0.05 | +0.04 | 76% | +0.10 | +0.08 | 4.86 |
| correction | 177 | 0 | 66% | +0.02 | +0.01 | 66% | +0.03 | +0.02 | 62% | +0.02 | +0.01 | 1.29 |
| healthy_uptrend | 949 | 0 | 61% | +0.00 | -0.01 | 64% | +0.01 | +0.00 | 69% | +0.03 | +0.02 | 1.68 |
| high_vol_selloff | 301 | 0 | 53% | +0.00 | -0.02 | 58% | +0.00 | -0.01 | 61% | +0.02 | +0.01 | 1.38 |
| narrow_uptrend | 221 | 0 | 68% | +0.02 | +0.01 | 74% | +0.04 | +0.02 | 71% | +0.05 | +0.04 | 2.00 |
| **all** | 1930 | 0 | 61% | +0.01 | -0.00 | 65% | +0.02 | +0.01 | 68% | +0.04 | +0.03 | 1.85 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
