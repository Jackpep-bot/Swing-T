# Pre-registered group of 1: results

Graded per docs/preregistration/2026-10-13-dividend-month.md (n_trials = 1). Net of replay costs plus the per-stock spread top-up.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dividend_month_premium | 2024 | 646 | +0.077 | 1.49 | 0.51 | 0.51 | 0.76 | 9.3% | 19 | 283% | +7.8% |
| dividend_month_premium | 2017 | 2398 | +0.138 | 5.58 | 0.67 | 0.67 | 0.97 | 14.6% | 20 | 162% | +60.1% |

## Against buy-and-hold SPY

Daily net return minus SPY close-to-close return on the same sessions. Pass rule for no strategy: positive haircut IR in both windows. Pass rule for dividend_month_premium: the standard rule (haircut Sharpe > 0 and net R > 0) and alpha > 0 with alpha t >= 1.960 (two-sided Bonferroni, 5% over 1 trials) in both windows. The columns are information only for the others; turnover is one-way (half of bought + sold notional over mean equity).

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dividend_month_premium | 2024 | -14.0% | -1.08 | -1.08 | -1.5% | -0.34 | 0.31 | 45% | 0.51 | 1.09 | 622% |
| dividend_month_premium | 2017 | -8.8% | -0.71 | -0.71 | +0.3% | 0.11 | 0.41 | 48% | 0.67 | 0.84 | 639% |

## Verdicts
- **dividend_month_premium**: FAIL

## Notes (written after the run; nothing was re-run)

- **FAIL, as expected.** Against total-return SPY the book's alpha is +0.3% a year (t 0.11) in 2017-24 and -1.5% a
  year (t -0.34) in 2024-26. The published premium does not show up net of costs in the 50 most liquid payers.
- The book made money in absolute terms (net +0.14R and +0.08R a trade, +60% and +8%) because it was long stocks in
  a rising market; its beta to SPY was 0.41 and 0.31.
- The book ran about half invested (exposure 48% and 45%), not the 50 positions the card describes. The replay's
  skip counts for 2017-24: `no_free_slot` 1,615 (the outgoing month's names still hold their slots when the new
  month's are sized, and both trade at the same open), `open_through_limit` 328 (the open was above the entry limit),
  `symbol_busy` 308. A third of the exits were the 3 x ATR(63) stop, which is not a rare event for a low-volatility
  large cap inside a month. Both are how the engine runs every monthly book, and both were in place before the run.
  A fully invested book would scale alpha and tracking error together, so the t-statistics, the test itself, would
  be about the same. Fixing the slot handling would be an engine change and a new trial, not a re-run of this one.
- Turnover was about 6 times equity a year one-way; the replay's cost drag was 1.2% a year.
