# Pre-registered group of 15: results

Graded per docs/preregistration/2026-10-13-batch5.md (n_trials = 15). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| russell_recon_deletion_rebound | 2024 | 0 | - | - | - | - | - | - | - | - | - |
| russell_recon_deletion_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |
| russell_recon_addition_frontrun | 2024 | 56 | -0.114 | -0.81 | -0.23 | -0.23 | 0.02 | 14.3% | 32 | -153% | -4.2% |
| russell_recon_addition_frontrun | 2017 | - | - | - | - | - | - | - | - | - | - |
| tax_loss_loser_rebound | 2024 | 36 | -0.085 | -0.96 | -0.22 | -0.22 | 0.02 | 7.8% | 19 | -110% | -3.1% |
| tax_loss_loser_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |
| ceo_cfo_buy_5day | 2024 | 511 | -0.058 | -2.94 | -1.10 | -1.10 | 0.00 | 34.1% | 5 | -107% | -27.9% |
| ceo_cfo_buy_5day | 2017 | - | - | - | - | - | - | - | - | - | - |
| pre_earnings_runup_winners | 2024 | 132 | +0.013 | 0.13 | -0.14 | -0.14 | 0.03 | 8.8% | 3 | -560% | -2.6% |
| pre_earnings_runup_winners | 2017 | - | - | - | - | - | - | - | - | - | - |
| double_surprise_smallmid | 2024 | 277 | +0.054 | 0.70 | 0.28 | 0.00 | 0.08 | 19.8% | 54 | 437% | +8.0% |
| double_surprise_smallmid | 2017 | - | - | - | - | - | - | - | - | - | - |
| shareholder_yield_smallmid | 2024 | 313 | -0.392 | -3.26 | -0.60 | -0.60 | 0.00 | 24.8% | 64 | -112% | -19.5% |
| shareholder_yield_smallmid | 2017 | - | - | - | - | - | - | - | - | - | - |
| clenow_stocks_on_the_move_midcap | 2024 | 363 | +0.045 | 1.16 | 0.38 | 0.00 | 0.11 | 23.4% | 37 | 446% | +11.8% |
| clenow_stocks_on_the_move_midcap | 2017 | - | - | - | - | - | - | - | - | - | - |
| piotroski_fscore8_small_value | 2024 | 72 | +0.251 | 0.91 | 0.45 | 0.00 | 0.13 | 15.5% | 88 | 174% | +12.2% |
| piotroski_fscore8_small_value | 2017 | - | - | - | - | - | - | - | - | - | - |
| code33_trend_template | 2024 | 167 | -0.064 | -0.40 | -0.34 | -0.34 | 0.01 | 10.3% | 11 | -479% | -4.6% |
| code33_trend_template | 2017 | - | - | - | - | - | - | - | - | - | - |
| pocket_pivot_morales_kacher | 2024 | 385 | -0.191 | -2.41 | -0.67 | -0.67 | 0.00 | 32.7% | 25 | -160% | -23.9% |
| pocket_pivot_morales_kacher | 2017 | - | - | - | - | - | - | - | - | - | - |
| green_line_breakout_wish | 2024 | 222 | -0.000 | -0.00 | 0.17 | 0.00 | 0.06 | 24.1% | 35 | 2157% | +2.2% |
| green_line_breakout_wish | 2017 | - | - | - | - | - | - | - | - | - | - |
| bensdorp_mr_selloff | 2024 | 819 | -0.059 | -4.72 | -2.55 | -2.55 | 0.00 | 49.5% | 3 | -69% | -49.0% |
| bensdorp_mr_selloff | 2017 | - | - | - | - | - | - | - | - | - | - |
| bensdorp_adx_reversal | 2024 | 633 | -0.066 | -3.15 | -1.68 | -1.68 | 0.00 | 44.0% | 6 | -100% | -40.6% |
| bensdorp_adx_reversal | 2017 | - | - | - | - | - | - | - | - | - | - |
| sykes_first_green_day | 2024 | 8 | -0.228 | -1.19 | -0.76 | -0.76 | 0.00 | 1.8% | 1 | -52% | -1.3% |
| sykes_first_green_day | 2017 | - | - | - | - | - | - | - | - | - | - |

## Against buy-and-hold SPY

Daily net return minus SPY close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for russell_recon_deletion_rebound, russell_recon_addition_frontrun, tax_loss_loser_rebound, ceo_cfo_buy_5day, pre_earnings_runup_winners, double_surprise_smallmid, shareholder_yield_smallmid, clenow_stocks_on_the_move_midcap, piotroski_fscore8_small_value, code33_trend_template, pocket_pivot_morales_kacher, green_line_breakout_wish, bensdorp_mr_selloff, bensdorp_adx_reversal, sykes_first_green_day: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 2.935 (two-sided Bonferroni, 5% over 15 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| russell_recon_deletion_rebound | 2024 | - | - | - | - | - | - | - | - | - | - |
| russell_recon_deletion_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |
| russell_recon_addition_frontrun | 2024 | -18.9% | -1.11 | -1.11 | -3.3% | -0.58 | 0.08 | 9% | -0.23 | 1.03 | 71% |
| russell_recon_addition_frontrun | 2017 | - | - | - | - | - | - | - | - | - | - |
| tax_loss_loser_rebound | 2024 | -18.5% | -1.10 | -1.10 | -2.4% | -0.53 | 0.06 | 4% | -0.22 | 1.03 | 61% |
| tax_loss_loser_rebound | 2017 | - | - | - | - | - | - | - | - | - | - |
| ceo_cfo_buy_5day | 2024 | -32.6% | -2.03 | -2.03 | -22.2% | -2.49 | 0.39 | 33% | -1.10 | 1.03 | 2010% |
| ceo_cfo_buy_5day | 2017 | - | - | - | - | - | - | - | - | - | - |
| pre_earnings_runup_winners | 2024 | -18.1% | -1.06 | -1.06 | -2.2% | -0.42 | 0.07 | 4% | -0.14 | 1.03 | 340% |
| pre_earnings_runup_winners | 2017 | - | - | - | - | - | - | - | - | - | - |
| double_surprise_smallmid | 2024 | -8.9% | -0.33 | -0.33 | -5.1% | -0.27 | 0.78 | 74% | 0.28 | 1.03 | 351% |
| double_surprise_smallmid | 2017 | - | - | - | - | - | - | - | - | - | - |
| shareholder_yield_smallmid | 2024 | -26.7% | -1.85 | -1.85 | -19.8% | -2.18 | 0.60 | 84% | -0.60 | 1.03 | 296% |
| shareholder_yield_smallmid | 2017 | - | - | - | - | - | - | - | - | - | - |
| clenow_stocks_on_the_move_midcap | 2024 | -9.4% | -0.56 | -0.56 | -4.6% | -0.39 | 0.72 | 67% | 0.38 | 1.03 | 417% |
| clenow_stocks_on_the_move_midcap | 2017 | - | - | - | - | - | - | - | - | - | - |
| piotroski_fscore8_small_value | 2024 | +16.3% | 0.21 | 0.00 | +30.2% | 0.57 | 0.18 | 32% | 0.45 | 1.03 | 92% |
| piotroski_fscore8_small_value | 2017 | - | - | - | - | - | - | - | - | - | - |
| code33_trend_template | 2024 | -19.2% | -1.19 | -1.19 | -3.8% | -0.87 | 0.09 | 20% | -0.34 | 1.03 | 428% |
| code33_trend_template | 2017 | - | - | - | - | - | - | - | - | - | - |
| pocket_pivot_morales_kacher | 2024 | -29.2% | -1.71 | -1.71 | -21.8% | -1.98 | 0.57 | 94% | -0.67 | 1.03 | 944% |
| pocket_pivot_morales_kacher | 2017 | - | - | - | - | - | - | - | - | - | - |
| green_line_breakout_wish | 2024 | -12.6% | -0.52 | -0.52 | -7.3% | -0.44 | 0.69 | 78% | 0.17 | 1.03 | 508% |
| green_line_breakout_wish | 2017 | - | - | - | - | - | - | - | - | - | - |
| bensdorp_mr_selloff | 2024 | -50.2% | -2.86 | -2.86 | -37.4% | -4.26 | 0.25 | 10% | -2.55 | 1.03 | 1184% |
| bensdorp_mr_selloff | 2017 | - | - | - | - | - | - | - | - | - | - |
| bensdorp_adx_reversal | 2024 | -42.2% | -2.42 | -2.42 | -31.2% | -3.18 | 0.36 | 25% | -1.68 | 1.03 | 1308% |
| bensdorp_adx_reversal | 2017 | - | - | - | - | - | - | - | - | - | - |
| sykes_first_green_day | 2024 | -17.7% | -1.07 | -1.07 | -0.7% | -1.11 | 0.00 | 0% | -0.76 | 1.03 | 22% |
| sykes_first_green_day | 2017 | - | - | - | - | - | - | - | - | - | - |

## Verdicts
- **russell_recon_deletion_rebound**: FAIL
- **russell_recon_addition_frontrun**: FAIL
- **tax_loss_loser_rebound**: FAIL
- **ceo_cfo_buy_5day**: FAIL
- **pre_earnings_runup_winners**: FAIL
- **double_surprise_smallmid**: FAIL
- **shareholder_yield_smallmid**: FAIL
- **clenow_stocks_on_the_move_midcap**: FAIL
- **piotroski_fscore8_small_value**: FAIL
- **code33_trend_template**: FAIL
- **pocket_pivot_morales_kacher**: FAIL
- **green_line_breakout_wish**: FAIL
- **bensdorp_mr_selloff**: FAIL
- **bensdorp_adx_reversal**: FAIL
- **sykes_first_green_day**: FAIL
