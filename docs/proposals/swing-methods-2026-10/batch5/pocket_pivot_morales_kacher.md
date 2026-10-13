---
slug: pocket_pivot_morales_kacher
name: Pocket pivot (Morales & Kacher), up-day volume above every down-day volume of the prior 10 sessions, off the 10-day line
originators: [Gil Morales & Chris Kacher, "Trade Like an O'Neil Disciple" (2010) and "In the Trading Cockpit with the O'Neil Disciples" (2012)]
category: strategy
decision: implement
holding_period_days: [5, 63]
timeframe: daily bars
direction: long
universe: SMALLMID
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; named in docs/methods/07 but never built)
---

# Pocket pivot

## Why this one is new
`docs/methods/07-canslim-ibd-market-school.md` names pocket pivots but no strategy implements them;
`expansion_pivot_cooper` is a cousin with a range-expansion trigger, not the down-volume rule. Pocket pivots are one
of the most copied setups among IBD-style traders (TraderLion, Deepvue, MarketSurge scans) and are bought inside
the base, before a classic breakout.

## One-line summary
In a stock above its 50-day, buy an up day whose volume beats the largest down-day volume of the past ten sessions,
when price is lifting off the 10-day line rather than extended above it; sell on the "seven-week rule" violation of
the 10-day.

## Origin and lineage
- Book not online. Rule summaries opened: https://www.luxalgo.com/library/concept/pocket-pivot.md,
  https://mohitsidana.substack.com/p/pocket-pivot-buyable-gap-ups-use,
  https://traderlion.com/trading-strategies/spot-winning-trades-early-pocket-pivots/,
  https://edgerater.com/blog/morales-and-kacher-signals-template.

## Exact rules (as published)
Close up on the day; volume > highest down-day volume of the prior 10 sessions; at or near the 10-day SMA or rising
up through the 10- or 50-day; not extended; inside or just out of a constructive base; skip names below the 50- or
200-day, after a 5-month+ downtrend, after a V-shaped snap-back or a wedging drift-up. TraderLion adds: close in the
upper half of the range. Sell: if the stock has respected the 10-day for 7+ weeks, sell on the first violation (a
close below the 10-day, then a session trading below that close day's low); otherwise use the 50-day the same way
with about 2-2.5% slack. Initial stop under the pivot-day low.

## Engine version (pre-register this one)
Vague items fixed by me (marked F):
- Volume rule: close > prev close and volume > max(volume of sessions in t-10..t-1 with close < prior close). If no
  down day in the window, no signal.
- Close location: `close_pos` >= 0.5.
- Near the 10-day (F): low <= 1.01 x `sma_10` and close <= 1.05 x `sma_10`.
- Trend (F): close > `sma_50` > `sma_200`; `dist_52w_high` >= -0.25 (within 25% of the high, "constructive base").
- No V / no wedge (F): skip if the 10-session return before t exceeds +15% or if 7+ of the last 10 sessions closed up.
- No downtrend (F): skip if close 105 sessions ago > close today (5 months).
- Skip if `sessions_to_expected_earnings` <= 3.
- Entry: next open. Initial stop: min(signal-day low, entry x 0.92).
- Exit (F, mechanical form of the book rule): track whether the stock has closed above `sma_10` on each of the last 35
  sessions (7 weeks). If yes: after any close below `sma_10`, sell at the stop = that session's low on any later
  session. If no: the same rule on `sma_50` with the trigger low x 0.975. Max hold 63 sessions.
- Max 20 open, equal risk.

## Grading
Batch standard.

## Evidence
No independent backtest with numbers found (searched TraderLion, LuxAlgo, TradingView, ProRealCode). Only the
authors' self-reported account returns, which are not about this rule. Grade D.

## Expectation stated before the run
Similar to the replayed breakout family: positive gross in 2017-21, negative net vs SPY in 2024-26.

## Common mistakes
Comparing to average volume instead of down-day volume; buying extended names; using weekly bars for the rule.

## Signs of decay to monitor
Trailing 100-trade mean net R <= 0.
