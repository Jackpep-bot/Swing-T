# Pre-registered group of 2: results

Graded per docs/preregistration/2026-10-10-batch3.md (n_trials = 2). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| large_cap_gross_profitability | 2024 | 276 | +0.175 | 0.74 | 0.56 | 0.12 | 0.60 | 19.5% | 88 | 251% | +16.0% |
| large_cap_gross_profitability | 2017 | 297 | +7.161 | 3.33 | 0.90 | 0.81 | 0.97 | 35.5% | 346 | 89% | +270.7% |
| large_cap_residual_momentum | 2024 | 373 | +0.341 | 1.98 | 0.75 | 0.39 | 0.70 | 20.5% | 47 | 164% | +31.1% |
| large_cap_residual_momentum | 2017 | 957 | +0.172 | 2.01 | 0.40 | 0.22 | 0.72 | 28.4% | 55 | 245% | +42.9% |

## Against buy-and-hold SPY

Daily net return minus SPY close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for large_cap_gross_profitability, large_cap_residual_momentum: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.241 (two-sided Bonferroni, 5% over 2 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| large_cap_gross_profitability | 2024 | -8.4% | -0.71 | -0.71 | -3.1% | -0.41 | 0.69 | 87% | 0.56 | 1.03 | 207% |
| large_cap_gross_profitability | 2017 | +5.5% | 0.62 | 0.49 | +4.5% | 1.43 | 1.07 | 97% | 0.90 | 0.75 | 43% |
| large_cap_residual_momentum | 2024 | -1.1% | -0.06 | -0.06 | +4.0% | 0.31 | 0.70 | 74% | 0.75 | 1.03 | 353% |
| large_cap_residual_momentum | 2017 | -8.1% | -0.62 | -0.62 | -1.8% | -0.50 | 0.54 | 57% | 0.40 | 0.75 | 256% |

## Verdicts
- **large_cap_gross_profitability**: FAIL
- **large_cap_residual_momentum**: FAIL
