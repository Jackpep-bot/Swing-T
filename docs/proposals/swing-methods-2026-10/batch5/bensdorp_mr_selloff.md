---
slug: bensdorp_mr_selloff
name: Bensdorp "Long Mean Reversion Selloff", 12.5% three-day drop in a volatile stock above its 150-day, limit buy 7% lower, 3-day exit
originators: [Laurens Bensdorp, "Automated Stock Trading Systems" (2020), system 3; DrKoch WealthLab published code ID 52]
category: strategy
decision: implement
holding_period_days: [1, 3]
timeframe: daily bars, limit entry
direction: long
universe: store stocks, close >= $1 (published), 50-day average volume >= 1M shares, ATR%(10) >= 5
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; differs from catalog connors_* and rsi2_meanrev)
---

# Bensdorp mean-reversion selloff

## Why this one is different from what was tested
The Connors family buys oversold readings at the close or next open. Bensdorp's version (1) selects by a fixed
3-day percentage drop, (2) requires high volatility (ATR% >= 5, which pushes it into small and mid caps), and (3)
buys only with a limit order 7% BELOW the signal close, so it fills only on a further flush. The engine has never
replayed a deep-limit entry.

## One-line summary
When a volatile stock that is still above its 150-day average falls 12.5% in three days, place a limit buy 7% under
the close; take 4% profit or leave after three days.

## Origin and lineage
- DrKoch's WealthLab code (https://wealth-lab.com/Strategy/PublishedStrategies, ID 52, read); book values are in the
  code comments, live defaults (1.9 / 1.6 / 1.4) look optimised, so the book values are used.
- Discussion: https://wealth-lab.com/Discussion/Laurens-Bensdorp-s-Automated-Stock-Trading-Systems-9377 (opened).

## Exact rules (as published)
Filters: 50-day average volume >= 1M, close >= $1, ATR%(10) >= 5. Setup: close >= SMA(150); 3-day drop >= 12.5%;
rank by drop. Entry: limit 7% below the close, next session. Exits: stop entry - 2.5 x ATR(10); profit target +4%;
time exit after 3 days.

## Engine version (pre-register this one)
- ATR% = `atr_10` / close x 100. 3-day drop = 1 - close / close 3 sessions ago.
- Entry: limit at 0.93 x signal close, valid for the next session only; filled at min(open, limit) if low <= limit,
  else no trade (gap-down opens fill at the open, the realistic case).
- Profit target: limit at entry x 1.04, from the fill session's close onward (F: not the fill session itself, since
  bar order inside the day is unknown).
- Stop: entry - 2.5 x `atr_10`. Time exit: close of the 3rd session after the fill.
- Max 10 open (book sizing: 2% risk, 10% of equity cap); rank by largest 3-day drop.
- Exclusions (F): `event_avoid_filters`; skip if the drop session carried an 8-K Item 1.03 or 3.01.

## Grading
Batch standard. Report fill rate (signals filled / signals).

## Evidence
No per-system book numbers could be read. DrKoch's equal-weight blend of all seven book systems: 16.7% APR, 8.2% max
drawdown, Sharpe 2.12 (https://backtest.substack.com/p/building-a-better-system-from-a-bunch), which forum users
could not reproduce (8-9% APR, -10% DD on a survivorship-biased 738-symbol list). Seller-adjacent; grade D.

## Expectation stated before the run
High win rate (>60%), small average gain; net about zero after small-cap spreads.

## Common mistakes
Filling the limit on the signal day; letting the target and stop both hit on the fill bar.

## Signs of decay to monitor
Trailing 100-trade mean net R <= 0.
