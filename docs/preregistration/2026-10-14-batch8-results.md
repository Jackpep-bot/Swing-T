# Pre-registered group of 1: results

Graded per docs/preregistration/2026-10-14-batch8.md (n_trials = 2). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture_v2 | 2024 | 24 | -0.117 | -0.67 | -0.36 | -0.36 | 0.14 | 4.2% | 101 | -94% | -2.6% |
| merger_target_spread_capture_v2 | 2017 | - | - | - | - | - | - | - | - | - | - |

## Against buy-and-hold SPY

Daily net return minus SPY close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for merger_target_spread_capture_v2: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.241 (two-sided Bonferroni, 5% over 2 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| merger_target_spread_capture_v2 | 2024 | -18.4% | -1.11 | -1.11 | -1.7% | -0.67 | 0.02 | 30% | -0.36 | 1.03 | 75% |
| merger_target_spread_capture_v2 | 2017 | - | - | - | - | - | - | - | - | - | - |

## Verdicts
- **merger_target_spread_capture_v2**: FAIL

## Exit table and the completed-deal condition (pre-registered pass condition 3)
2024-26, 24 trades; return per trade on the money put in, net of the replay's costs.

| exit | trades | mean return |
|---|---|---|
| deal closed (the symbol stopped trading) | 2 | +2.3% |
| still held at the window's end (not closed) | 13 | +1.9% |
| 180-session limit | 4 | +8.8% |
| break stop at 85% of the signal close | 4 | -15.0% |
| break stop, gapped through | 1 | -42.9% |

Completed deals: 2 of 11 closed trades (18%), under the 50% the pre-registration requires. FAIL on condition 3 as
well as on conditions 1 and 2. The batch-7 version had 1 completed deal in 52 trades; the cleaned flag halved the
break rate (5 of 24 vs 23 of 52) but most positions were still open or timed out when the window ended.
