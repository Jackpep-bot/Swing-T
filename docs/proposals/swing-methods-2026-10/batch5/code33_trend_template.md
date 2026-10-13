---
slug: code33_trend_template
name: Minervini "Code 33" (three quarters of accelerating EPS, sales and margin) with the trend template as trigger
originators: [Minervini, "Trade Like a Stock Market Wizard" (2013), Code 33 and Trend Template; He & Narayanamoorthy, JAE 69 (2020) for the academic cousin]
category: strategy
decision: implement
holding_period_days: [10, 63]
timeframe: daily bars + EDGAR quarterly values (point-in-time)
direction: long
universe: SMALLMID
regimes_good: [healthy_uptrend]
regimes_bad: [high_vol_selloff, v_shaped_rebound]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog as a rule)
---

# Code 33 plus trend template

## Why this one is different from what was tested
`vcp_sepa_breakout` and `canslim` use price patterns with loose earnings filters. Batch 4 rejected large-cap
earnings acceleration (EPS only). Code 33 is Minervini's stricter fundamental gate, three-way acceleration (EPS,
revenue AND margin) for three straight quarters, and he applies it to small growth names.

## One-line summary
Buy a small or mid cap in a Minervini stage-2 uptrend when its last three quarters show accelerating year-over-year
growth in earnings, sales and profit margin; exit on a close below the 50-day.

## Origin and lineage
- Minervini (book not opened). Secondary descriptions opened (screener.in, a TradingView script): three consecutive
  quarters of acceleration in EPS, sales and profit margins, year-over-year by quarter, no thresholds published.
- He & Narayanamoorthy 2020 (via https://www.cxoadvisory.com/?p=30457, opened): 1972-2015, change in y/y quarterly
  EPS growth, top-minus-bottom decile +1.8% the month after the report, +3.4% over the quarter, gross; weaker
  value-weighted and outside stocks under $5 / under $0.5B.

## Exact rules (as published)
Code 33: EPS growth, sales growth and margin each up for three consecutive quarters. No numbers. Trend template:
close > 150 and 200-day; 150 > 200; 200-day rising >= 1 month; 50 > 150 and 200; close > 50; close >= 30% above the
52-week low; within 25% of the 52-week high; RS rating >= 70.

## Engine version (pre-register this one)
Fixed by me:
- Quarterly values from `quarterly_values` (point-in-time). g_EPS(q) = y/y change in quarterly EPS / |EPS a year
  ago| (skip if |EPS a year ago| < $0.05); g_REV(q) = y/y revenue growth; margin(q) = EPS(q) x shares / revenue(q)
  (net margin proxy).
- Code 33 true when, for the three latest quarters q-2, q-1, q: g_EPS rises each quarter, g_REV rises each quarter,
  margin rises each quarter, and g_EPS(q) > 0, g_REV(q) > 0.
- Trend template true on the bar (the published list, `rs_rating_ibd` >= 70, 200-day slope over 21 sessions > 0).
- Trigger: first session on which both are true (either may become true first), and the close is no more than 5%
  above `sma_10` (not extended). Entry next open. Max 20 open, equal risk.
- Stop: max(entry x 0.92, entry - 2.5 x `atr_14`) (Minervini's 7-8% max loss).
- Exit: first close below `sma_50` (next open), or after 63 sessions, or when the next filing breaks Code 33 AND
  close < `sma_20`.

## Grading
Batch standard.

## Evidence
Grade D: the rule itself has no independent test; the academic cousin is gross and pre-2016; the AAII CAN SLIM
paper screen (19.2% a year since 1998 vs 5.7% for the S&P 500 price index, no costs, often 0-6 names) is a
seller-adjacent screen record, not a test.

## Expectation stated before the run
Few signals (tens a year). Small positive gross in 2017-24 trend years; about zero net.

## Common mistakes
Using annual instead of quarter-on-year-ago growth; letting a restated quarter in (look-ahead).

## Signs of decay to monitor
Trailing 50-trade mean net R <= 0.
