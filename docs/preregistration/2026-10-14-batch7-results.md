# Pre-registered group of 2: results

Graded per docs/preregistration/2026-10-14-batch7.md (n_trials = 2). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture | 2024 | 52 | -0.181 | -0.84 | -0.33 | -0.33 | 0.16 | 12.8% | 93 | -155% | -7.8% |
| merger_target_spread_capture | 2017 | - | - | - | - | - | - | - | - | - | - |
| seo_marketed_offer_rebound | 2024 | 164 | -0.065 | -1.01 | -0.40 | -0.40 | 0.14 | 13.5% | 6 | -274% | -6.9% |
| seo_marketed_offer_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |

## Against buy-and-hold SPY

Daily net return minus SPY close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for merger_target_spread_capture, seo_marketed_offer_rebound: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.241 (two-sided Bonferroni, 5% over 2 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture | 2024 | -20.6% | -1.39 | -1.39 | -8.8% | -1.31 | 0.31 | 63% | -0.33 | 1.03 | 158% |
| merger_target_spread_capture | 2017 | - | - | - | - | - | - | - | - | - | - |
| seo_marketed_offer_rebound | 2024 | -20.3% | -1.35 | -1.35 | -6.8% | -1.29 | 0.20 | 16% | -0.40 | 1.03 | 655% |
| seo_marketed_offer_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |

## Verdicts
- **merger_target_spread_capture**: FAIL
- **seo_marketed_offer_rebound**: FAIL

## Descriptive: `merger_target_spread_capture` trades by how they ended (2024-26; promised by the pre-registration)
Return per trade on the money put in, net of the replay's costs; 52 trades.

| exit | trades | mean return |
|---|---|---|
| deal closed (the symbol stopped trading) | 1 | +3.6% |
| still held at the window's end | 14 | +3.3% |
| 180-session limit | 14 | +21.9% |
| break stop at 85% of the signal close | 17 | -15.0% |
| break stop, gapped through | 6 | -35.0% |

Read: only one position ended with a completed deal, and 23 of 52 hit the break stop, far more than takeover
targets break. The DEFM14A / SC TO-T flag catches many filings that are not a target waiting for its cash price
(acquirers' own proxies, other tender offers), so this test says little about merger arbitrage itself. Written
after the results were read; not part of the verdict.
