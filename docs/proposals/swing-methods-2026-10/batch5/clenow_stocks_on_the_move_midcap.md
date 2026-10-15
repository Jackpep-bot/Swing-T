---
slug: clenow_stocks_on_the_move_midcap
name: Clenow "Stocks on the Move", regression-slope x R-squared momentum, weekly, ATR sizing, on mid caps
originators: [Andreas Clenow, "Stocks on the Move: Beating the Market with Hedge Fund Momentum Strategies" (2015)]
category: strategy
decision: implement
holding_period_days: [5, 252]
timeframe: weekly (Wednesday) rebalance; daily bars
direction: long
universe: mcap_pit ranks 501-1,500 (registered deviation: published universe is the S&P 500)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff, v_shaped_rebound]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; differs from catalog slope_performance_trend and xs_momentum_rank)
---

# Stocks on the Move, mid caps

## Why this one is different from what was tested
`slope_performance_trend` uses 12-month linear slopes of price and relative price; `xs_momentum_rank` ranks 12-1
returns. Clenow's score rewards SMOOTH trends (slope x R-squared over 90 days), excludes stocks with any 15% gap,
sizes by ATR and trades weekly. Independent replications exist with numbers, all on the S&P 500; none on smaller
stocks, which is what this card tests.

## One-line summary
Every Wednesday, rank mid caps by the steadiness-weighted 90-day trend, hold those in the top fifth that are above
their 100-day average with no big gaps, buy only when SPY is above its 200-day, and size each by its volatility.

## Origin and lineage
Rules as replicated by Teddy Koker (https://teddykoker.com/2019/05/momentum-strategy-from-stocks-on-the-move-in-python/,
opened) and the QuantConnect thread (https://www.quantconnect.com/forum/discussion/10493/, opened).

## Exact rules (as published)
Score = annualised exponential-regression slope over 90 days x R-squared. Disqualify: close below 100-day MA, or any
gap > 15% in the last 90 days. Buy only if the S&P 500 is above its 200-day MA (blocks new buys only). Trade
Wednesdays; sell if out of the top 20%, below the 100-day, a gap > 15%, or leaves the index. Shares = equity x 0.001 /
ATR(20). Re-size every second Wednesday "if the deviation is significant".

## Engine version (pre-register this one)
- Universe: `mcap_pit` rank 501-1,500 among store stocks with close >= $5 and `med_dv_63` >= $2M (F).
- Score: regress ln(close) on 0..89 over the last 90 sessions; annualised slope = exp(b x 252) - 1; score = that x R^2.
- Disqualify as published (gap = |open / prev close - 1| > 0.15 on any of the last 90 sessions).
- Weekly on Wednesday (next session if a holiday); fills next open. Top 20% of the universe by score = hold zone;
  buy in rank order while cash remains. Index filter: SPY close > SPY 200-day SMA.
- Size: shares = equity x 0.001 / `atr_20`-equivalent (ATR 20); with a $10k book this is about 10 positions. Re-size
  (F) every second Wednesday when the position's target shares differ by more than 25%.
- No stop other than the rules above (Clenow uses none); `engine_trail = False`.

## Grading
Batch standard, alpha vs SPY and vs IWM. Report turnover a year.

## Evidence
| Who | Period / universe | CAGR | Max DD |
|---|---|---|---|
| Book (via The Chartist, https://www.thechartist.com.au/?p=5829, opened) | 1999-2014, S&P 500 | 12.3% | -24% (S&P 5.2%, -55%) |
| Teddy Koker (independent) | 2012-02..2018-02, survivorship-free S&P 500 | 8.99% (SPY about 12%) | 11.7% |
| QuantConnect user (https://www.quantconnect.com/forum/discussion/16578/, opened) | 2009..2024-01, original rules | 8.79% | 24.1% |
Grade C: the published edge is mostly drawdown control in 2000-02 and 2008; after 2009 it trails SPY in every
replication found. No small/mid replication exists.

## Expectation stated before the run
Alpha vs SPY negative in both windows (as in the S&P replications); the question is whether mid caps change that.

## Common mistakes
Comparing the data feed instead of the close to the SMA (Koker's code); daily rebalancing.

## Signs of decay to monitor
Trailing 3-year alpha vs SPY <= 0.
