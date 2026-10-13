---
slug: large_shock_no_news_reversal
name: Buy a liquid stock after a one-day crash that came with no news, no earnings and no 8-K; hold 10 sessions
originators: [Savor, "Stock returns after major price shocks: the impact of information", JFE 106(3) 2012; Chan, "Stock price reaction to news and no-news: drift and reversal after headlines", JFE 70(2) 2003]
category: strategy
decision: implement
holding_period_days: [10, 10]
timeframe: daily bars; Alpaca news flag; 8-K items; earnings dates
direction: long
universe: the 1,500 most liquid store stocks (med_dv_63), close >= $5
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 6, 2026-10-13)
---

# Large no-news shock reversal

## Why this one is genuinely different
The catalog's mean-reversion cards (`connors_*`, `rsi2_meanrev`, `ibs_mean_reversion`, their `_no_news` variants) buy
mild multi-day pullbacks inside uptrends, a crowded setup that mostly delivered market beta. This card waits for a
rare event, a stock-specific crash several times its normal daily move, and takes it only when nothing public
explains it. It is event-driven like `episodic_pivot`, but on the opposite side: overreaction rather than news drift.

## One-line summary
When a liquid stock falls at least 3 times its normal daily move relative to SPY in one session with no news, no
earnings and no 8-K, buy the next open and sell 10 sessions later.

## Evidence
- Savor 2012 (abstract, https://repository.upenn.edu/fnce_papers/387, opened): price shocks without analyst reports
  reverse; with reports they drift. Chan 2003 finds the same split using news headlines. Both samples end before
  2010; no net-of-cost test found. Grade C.

## Engine version (pre-register this one)
- Shock: (stock return - SPY return) on day t <= -3.0 x stdev of that excess return over the prior 60 sessions, and
  stock return <= -5%.
- No news: no Alpaca news item tagged to the symbol on t-1 or t (16:00 ET t-1 to 16:00 ET t), no 8-K of any item
  filed t-1..t, not within 3 sessions of an expected or actual earnings date (`sessions_to_expected_earnings`).
- Entry next open; exit at the close of the 10th session after entry; catastrophe stop at 2 x the shock day's range
  below entry. One position per symbol; max 8 open, equal risk.
- `event_avoid_filters` applies.

## Grading
Batch standard (net, own holding period) plus alpha vs SPY in both windows, haircut over this batch's trials.

## Expectation stated before the run
A few hundred signals a year; +0.3% to +1% gross over 10 sessions, near zero to slightly positive net; the news
filter should separate it clearly from the same rule with news (reported as a descriptive split, not a trial).

## Common mistakes
News timestamps after the close counted on the wrong day (news is keyed on created_at, ET); after-hours 8-Ks.
