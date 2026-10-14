# Pre-registered group of 2: results

Graded per docs/preregistration/2026-10-14-batch7-results-iwm.md (n_trials = 2). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture | 2024 | 52 | -0.181 | -0.84 | -0.33 | -0.33 | 0.16 | 12.8% | 93 | -155% | -7.8% |
| merger_target_spread_capture | 2017 | - | - | - | - | - | - | - | - | - | - |
| seo_marketed_offer_rebound | 2024 | 164 | -0.065 | -1.01 | -0.40 | -0.40 | 0.14 | 13.5% | 6 | -274% | -6.9% |
| seo_marketed_offer_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |

## Against buy-and-hold IWM

Daily net return minus IWM close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for merger_target_spread_capture, seo_marketed_offer_rebound: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.241 (two-sided Bonferroni, 5% over 2 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | IWM Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture | 2024 | -19.1% | -1.12 | -1.12 | -8.2% | -1.33 | 0.30 | 63% | -0.33 | 0.74 | 158% |
| merger_target_spread_capture | 2017 | - | - | - | - | - | - | - | - | - | - |
| seo_marketed_offer_rebound | 2024 | -18.8% | -1.00 | -1.00 | -5.9% | -1.16 | 0.17 | 16% | -0.40 | 0.74 | 655% |
| seo_marketed_offer_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |

## Verdicts
- **merger_target_spread_capture**: FAIL
- **seo_marketed_offer_rebound**: FAIL
