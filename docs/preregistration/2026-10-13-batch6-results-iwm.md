# Pre-registered group of 4: results

Graded per docs/preregistration/2026-10-13-batch6-results-iwm.md (n_trials = 5). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| residual_reversal_ff3_etf | 2024 | 0 | - | - | - | - | - | - | - | - | - |
| residual_reversal_ff3_etf | 2017 | - | - | - | - | - | - | - | - | - | - |
| within_industry_reversal_no_news | 2024 | 801 | -0.032 | -1.66 | -0.34 | -0.34 | 0.05 | 21.7% | 23 | -218% | -10.3% |
| within_industry_reversal_no_news | 2017 | - | - | - | - | - | - | - | - | - | - |
| large_shock_no_news_reversal | 2024 | 293 | -0.038 | -1.05 | -0.51 | -0.51 | 0.03 | 19.0% | 9 | -221% | -10.2% |
| large_shock_no_news_reversal | 2017 | - | - | - | - | - | - | - | - | - | - |
| industry_leader_lag_smallmid | 2024 | 1665 | -0.063 | -4.43 | -1.51 | -1.51 | 0.00 | 56.2% | 5 | -124% | -51.9% |
| industry_leader_lag_smallmid | 2017 | - | - | - | - | - | - | - | - | - | - |

## Against buy-and-hold IWM

Daily net return minus IWM close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for residual_reversal_ff3_etf, within_industry_reversal_no_news, large_shock_no_news_reversal, industry_leader_lag_smallmid: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.576 (two-sided Bonferroni, 5% over 5 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | IWM Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| residual_reversal_ff3_etf | 2024 | - | - | - | - | - | - | - | - | - | - |
| residual_reversal_ff3_etf | 2017 | - | - | - | - | - | - | - | - | - | - |
| within_industry_reversal_no_news | 2024 | -20.2% | -1.56 | -1.56 | -12.5% | -2.26 | 0.51 | 70% | -0.34 | 0.74 | 796% |
| within_industry_reversal_no_news | 2017 | - | - | - | - | - | - | - | - | - | - |
| large_shock_no_news_reversal | 2024 | -20.5% | -1.20 | -1.20 | -9.3% | -1.65 | 0.28 | 34% | -0.51 | 0.74 | 988% |
| large_shock_no_news_reversal | 2017 | - | - | - | - | - | - | - | - | - | - |
| industry_leader_lag_smallmid | 2024 | -50.0% | -2.20 | -2.20 | -42.2% | -2.94 | 0.50 | 52% | -1.51 | 0.74 | 3450% |
| industry_leader_lag_smallmid | 2017 | - | - | - | - | - | - | - | - | - | - |

## Verdicts
- **residual_reversal_ff3_etf**: FAIL
- **within_industry_reversal_no_news**: FAIL
- **large_shock_no_news_reversal**: FAIL
- **industry_leader_lag_smallmid**: FAIL
