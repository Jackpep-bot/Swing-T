---
slug: radge_weekend_trend_trader
name: "Weekend Trend Trader (Nick Radge)"
originators: ["Nick Radge (The Chartist; book 'Weekend Trend Trader', 2013)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [20, 365]
timeframe: weekly
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null   # one forum test: 70.5% (78 trades); not representative
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Weekend Trend Trader (Nick Radge)

## One-line summary
Each weekend, buy stocks making a new 20-week high with strong 20-week rate of change while the index is above its
10-week MA; trail a wide 40% stop that tightens to 10% when the index falls below its 10-week MA.

## Origin and lineage
Nick Radge (Australian, The Chartist) published *Weekend Trend Trader* (Sep 2013). Turtle/Darvas-style breakout trend
following, moved to weekly bars and gated by an index regime filter. Rules below are from the useThinkScript port
thread (sweep summary in docs/research-raw/methods-sweeps/books_blogs.json); the book was not read and Radge's site
returned 403.

## Exact rules (per the forum port; book not verified)
- Universe: index constituents (forum tests used S&P 100 and Russell 1000).
- Review after Friday close; act at Monday open.
- Entry (all): weekly close at a new 20-week high; ROC(20 weeks) >= 30% (forum testers used 10-20% for more signals);
  market index (SPX/NDX/RUT) weekly close above its 10-week MA.
- Order: market at Monday open.
- Initial/trailing stop: 40% below the highest weekly close while the index is above its 10-week MA; tightened to 10%
  below the highest weekly close when the index closes below its 10-week MA. Stop only moves up. Checked weekly on the
  close (not a resting order); exit at next open.
- Sizing: 5% of equity per position (about 20 positions). No target, no time exit.

## Why it should work
Time-series and 52-week-high/breakout momentum (George-Hwang 2004) plus an index trend filter that cuts exposure in
bear markets (Faber 2007 style). Very wide stops let winners run; counterparty: under-reacting holders and short-term
mean-reversion sellers.

## When it works and when it fails
- Works: broad, long bull markets with persistent leaders.
- Fails: range-bound years (forum: long flat stretch 2001-2007); sharp crashes while the index is still above its
  10-week MA (40% stop is huge); a 40% stop makes per-trade risk large unless sized down.

## Parameters and sensitivity
| Knob | Forum default | Range |
|---|---|---|
| breakout lookback | 20 weeks | 10-52 |
| ROC(20w) threshold | 30% | 10-30% |
| index MA | 10 weeks | 10-40 weeks |
| trail (index up / down) | 40% / 10% | 20-40% / 5-15%, or ATR-based |
Forum testers reported the 40%/10% stops lost money in one test but a 20-week ATR(3x) trail did not: high sensitivity to
the exit, an overfitting warning.

## Evidence (forum-level, unaudited)
- S&P 100 from 1992, 5% per trade: 16.61% annualized ($25,000 -> $1,789,306), dividends excluded.
- 'zachc': 35 years, 20 random S&P 100 stocks, ROC 10: 78 trades, 70.5% wins, extended drawdown 2001-2007.
- Russell 1000 "top 10 by profit factor" variant quoted at 25.3% CAGR / 14.3% max DD (low confidence).
- docs/methods.md 1b: grade C, "re-tests show long flat periods". Survivorship (current index members) likely
  inflates all of these.

## Common mistakes
- Testing on today's index members (survivorship). Leaving the 40% stop as a resting order (rules are weekly-close).
- Treating weekly holds as swing trades in a 1%-risk sizing model (40% stop -> 2.5% position).

## Discretionary parts and how to make them mechanical
None; fully mechanical. Book thresholds are uncertain: record the forum values as v1 constants.

## Implementation spec for swing-engine
- Weekly resample (W-FRI, completed weeks). `wk_high_close_20 = max(wk_close over prior 20 weeks)`;
  `new_20w_high = wk_close > wk_high_close_20`; `roc_20w = wk_close / wk_close[20] - 1`;
  `mkt_above_10w = spy_wk_close > SMA(spy_wk_close, 10)`.
- Entry: all three true on Friday; enter Monday open.
- Stop: `trail = max_close_since_entry * (1 - 0.40)` if `mkt_above_10w` else `* (1 - 0.10)`; never lowered; exit next
  open after a weekly close below it.
- No target -> `min_reward_risk: 0.0`. max_hold_days: 365.
- Sizing: engine risk sizing with stop distance up to 40% yields tiny positions; better to run as fixed 5% weight in
  replay and report separately from 1R-sized strategies.
- Reuses: `high_52w`/`breakout_52w` (daily analogs), market regime. Missing: weekly resample, weekly ROC, a
  percentage trailing-stop exit with regime-dependent width, Monday-open scheduling.

## What the router should know
Position-trading horizon, not swing. Only healthy_uptrend; the index filter already switches it off in corrections.
Useful as a long-horizon comparison baseline for breakout_52w.

## Signs of decay to monitor
Multi-year flat equity, rising share of trades stopped by the 10% tight stop, falling average winner size.

## Sources
- https://usethinkscript.com/threads/weekend-trend-trader-by-nick-radge-strategy-for-thinkorswim.669/
- https://books.apple.com/us/book/weekend-trend-trader/id711140317
- https://www.thechartist.com.au/?p=16809 (blocked, 403)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
