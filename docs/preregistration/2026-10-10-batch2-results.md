# Pre-registered group of 3: results

Graded per docs/preregistration/2026-10-10-batch2.md (n_trials = 3). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fomc_cycle_even_weeks | 2024 | 47 | -0.020 | -1.12 | -0.68 | -0.68 | 0.03 | 19.3% | 5 | -60% | -14.7% |
| fomc_cycle_even_weeks | 2017 | 181 | -0.008 | -0.79 | -0.21 | -0.21 | 0.08 | 32.4% | 5 | -171% | -23.6% |
| large_cap_net_repurchasers | 2024 | 236 | +0.449 | 2.10 | 0.72 | 0.07 | 0.56 | 18.2% | 85 | 161% | +19.2% |
| large_cap_net_repurchasers | 2017 | 574 | +0.988 | 4.71 | 0.71 | 0.52 | 0.87 | 26.6% | 128 | 101% | +123.0% |
| volatility_managed_spy | 2024 | 6 | +0.192 | 2.06 | 0.87 | 0.31 | 0.64 | 14.8% | 79 | 38% | +23.3% |
| volatility_managed_spy | 2017 | 35 | +0.106 | 1.51 | 0.71 | 0.52 | 0.86 | 22.1% | 54 | 107% | +85.4% |

## Against buy-and-hold SPY

Daily net return minus SPY close-to-close return on the same sessions. Pass rule for fomc_cycle_even_weeks, volatility_managed_spy: positive haircut IR in both windows; the columns are information only for the others.

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| fomc_cycle_even_weeks | 2024 | -24.5% | -1.81 | -1.81 | -13.9% | -2.21 | 0.38 | 43% | -0.68 | 1.03 |
| fomc_cycle_even_weeks | 2017 | -16.4% | -1.13 | -1.13 | -8.5% | -2.34 | 0.43 | 44% | -0.21 | 0.75 |
| large_cap_net_repurchasers | 2024 | -7.3% | -0.61 | -0.61 | +0.0% | 0.00 | 0.57 | 83% | 0.72 | 1.03 |
| large_cap_net_repurchasers | 2017 | -2.0% | -0.19 | -0.19 | +1.5% | 0.44 | 0.74 | 78% | 0.71 | 0.75 |
| volatility_managed_spy | 2024 | -5.6% | -0.90 | -0.90 | -1.3% | -0.38 | 0.74 | 89% | 0.87 | 1.03 |
| volatility_managed_spy | 2017 | -5.0% | -0.52 | -0.52 | +0.6% | 0.30 | 0.59 | 82% | 0.71 | 0.75 |

## Verdicts
- **fomc_cycle_even_weeks**: FAIL
- **large_cap_net_repurchasers**: PASS
- **volatility_managed_spy**: FAIL
