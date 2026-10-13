---
slug: green_line_breakout_wish
name: Green line breakout (Dr. Eric Wish), first close at a new all-time high after at least three months without one
originators: [Eric Wish, Wishing Wealth blog, GLB explained (2018, 2021) and glossary]
category: strategy
decision: implement
holding_period_days: [5, 126]
timeframe: daily bars (rule defined on monthly bars)
direction: long
universe: SMALLMID
regimes_good: [healthy_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; not in catalog)
---

# Green line breakout

## Why this one is different from what was tested
`breakout_52w` buys 52-week highs; `ath_trend_following_wide_stop` buys any all-time high with a 10-ATR stop. The
GLB requires the all-time high to have stood untouched for at least three months (a dormant ceiling), and exits on a
close back below that line, a tight, structural stop.

## One-line summary
Draw the "green line" at an all-time high that has not been beaten for three months; buy the first close above it,
sell if it ever closes back below.

## Origin and lineage
- https://wishingwealthblog.com/2018/05/green-line-breakout-glb-explained-gmi-remains-green/ (opened)
- https://wishingwealthblog.com/2021/05/blog-post-glb-green-line-break-out-explained-some-stocks-having-a-glb-last-week-mec-omp-tgls-flng-cubi/ (opened)
- https://www.wishingwealthblog.com/glossary/ (opened)

## Exact rules (as published)
Green line = on a monthly chart, the highest price reached in any month that has not been surpassed for at least
three months, and it must be an all-time high. Buy when price trades above it ("break out to close at a new ATH").
Above-average weekly volume helps but is not required. "I sell it immediately if it closes back below its green
line." Pyramided winners are held until a close below the rising 30-week average. He trades only when his GMI market
indicator is positive (rules not read).

## Engine version (pre-register this one)
- History: the store starts 2016-01, so "all-time" means since the first bar; require >= 504 sessions of history
  (registered deviation; for stocks that peaked before 2016 the line is lower than Wish's).
- Monthly highs from daily bars (calendar months). Green line on day t = the highest monthly high H over all completed
  months, valid only if the month that set H is at least 3 completed months before the current month (F: three
  complete monthly bars, not counting the current month).
- Signal: close(t) > green line and close(t-1) <= green line. Entry next open. Volume: no filter (as published).
- Market gate (F, stand-in for the GMI): SPY close > SPY `sma_50`.
- Stop: close below the green line x 0.99 -> exit next open (F: 1% slack against noise; Wish uses the close with no
  slack). Catastrophe stop entry x 0.85.
- Trail (F, for winners): after +20% from entry, exit on a close below the 150-day SMA (30-week average).
- Max hold 126 sessions. Max 20 open, equal risk.

## Grading
Batch standard.

## Evidence
Only Wish's "Successful GLB Tracker": cherry-picked winners, no failures, no dates. No independent statistics found
(TraderLion explainer anecdotal only: https://traderlion.com/technical-analysis/green-line-breakout/). Grade D. The
nearest tested idea (`ath_trend_following_wide_stop`, batch 1) shows that the all-time-high effect is real gross in
some studies; this card tests whether the tight green-line stop keeps it after costs.

## Expectation stated before the run
Low win rate (<40%), many small stop-outs; positive gross in trend years; alpha vs SPY about zero net.

## Common mistakes
Using a 52-week high as the line; drawing the line from a still-open month; ignoring that the store's ATH is only
since 2016.

## Signs of decay to monitor
Trailing 100-trade mean net R <= 0.
