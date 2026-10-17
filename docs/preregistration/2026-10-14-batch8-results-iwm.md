# Pre-registered group of 1: results

Graded per docs/preregistration/2026-10-14-batch8-results-iwm.md (n_trials = 2). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture_v2 | 2024 | 24 | -0.117 | -0.67 | -0.36 | -0.36 | 0.14 | 4.2% | 101 | -94% | -2.6% |
| merger_target_spread_capture_v2 | 2017 | - | - | - | - | - | - | - | - | - | - |

## Against buy-and-hold IWM

Daily net return minus IWM close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for merger_target_spread_capture_v2: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.241 (two-sided Bonferroni, 5% over 2 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | IWM Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture_v2 | 2024 | -16.9% | -0.81 | -0.81 | -1.7% | -0.67 | 0.03 | 30% | -0.36 | 0.74 | 75% |
| merger_target_spread_capture_v2 | 2017 | - | - | - | - | - | - | - | - | - | - |

## Verdicts
- **merger_target_spread_capture_v2**: FAIL
