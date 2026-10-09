---
slug: turnaround_tuesday
name: Turnaround Tuesday
originators: [Market folklore; tested by Quantified Strategies (practitioner)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 1]
timeframe: daily (close-to-close)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: 0.56
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Turnaround Tuesday

## One-line summary
If SPY closes Monday at least 1% below Friday's close, buy at Monday's close and sell at Tuesday's close.

## Origin and lineage
Old trader saying that weak Mondays reverse on Tuesday (weekend/Monday effect literature, e.g. French 1980, is the
academic backdrop). Current rules and numbers come from Quantified Strategies' SPY backtest; their full rule
details for variants are paywalled (WebFetch 2026-10-07).

## Exact rules
- Instrument: SPY only (index ETF).
- Setup: Monday close <= 0.99 * prior Friday close (if Monday is a holiday, the source is silent; engine: first session of the week).
- Entry: market-on-close Monday. Exit: Tuesday close. No stop, no target.
- Sizing: not specified (full equity in the test).

## Why it should work
Short-horizon index mean reversion: liquidity-driven Monday selling (weekend news digestion, de-risking) is partly
reversed when liquidity providers are paid. Same family as RSI-2 / IBS index reversion.

## When it works and when it fails
Works when the broader trend is up (dip-buying regime). Fails in crashes (2008, Mar 2020) where -1% Mondays cluster
and follow-through continues.

## Parameters and sensitivity
Threshold (-1%), holding period (1 day vs until close > prior high), extra IBS filter. Variants improve stats but are
selected in-sample.

## Evidence
Quantified Strategies (SPY, period on paywalled page, no data-snooping correction):
- Base: 212 trades, +0.3%/trade, 56% winners, CAGR 1.8%, 2.5% time in market.
- With IBS filter: +0.33%/trade, 57%, CAGR 2.7%. Longer hold: +0.45%, 60%, CAGR 6.5%. Filters + flexible exit:
  +0.46%, 69%, CAGR 7%.
No academic replication located. Drawdown not reported in the free text.

## Common mistakes
Applying it to single stocks (untested); ignoring that the engine fills at next open (Tuesday open differs from Monday close).

## Implementation spec for swing-engine
- Features: `ret_monday = close_monday / close_prev_friday - 1` (per SPY; use the prior session close and the
  weekday of `ts`). Reuses `ret_1d` (equals it when Monday follows Friday).
- Signal: SPY, weekday == first session of the week, `ret_1d <= -0.01`.
- Entry: **MOC on Monday** (needs a market-on-close entry hook; current backtest fills at next open, which would test a
  different trade: Tuesday open to Tuesday close). Stop: catastrophic `entry - 3 * atr_14` (engine choice). Exit: Tuesday close, `max_hold_days = 1`.
- `min_reward_risk = 0.0`. Overlay sizing: at most the rsi2_meanrev index allocation.
- Missing: MOC entry/exit hook, SPY-as-tradable in the strategy universe.

## What the router should know
Low-exposure overlay at most. Disable in `high_vol_selloff` and `correction` (consistent with the engine's no-new-longs rule).

## Signs of decay to monitor
Rolling 40-trade average return <= 0; win rate < 50%.

## Sources
- https://quantifiedstrategies.substack.com/p/turnaround-tuesday-strategy-backtest

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3 | 0 | 67% | +0.07 | -0.04 | 33% | -0.15 | -0.25 | 33% | -0.50 | -0.60 | 0.19 |
| healthy_uptrend | 1 | 0 | 0% | -0.13 | -0.19 | 100% | +0.20 | +0.14 | 0% | -0.30 | -0.35 | 0.00 |
| high_vol_selloff | 3 | 0 | 67% | +0.26 | +0.08 | 100% | +0.48 | +0.30 | 67% | +0.32 | +0.14 | 1.81 |
| **all** | 7 | 0 | 57% | +0.12 | -0.01 | 71% | +0.17 | +0.04 | 43% | -0.12 | -0.25 | 0.75 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11 | 0 | 82% | +0.18 | +0.09 | 82% | +0.48 | +0.39 | 91% | +0.78 | +0.68 | 32.70 |
| correction | 4 | 0 | 25% | -0.10 | -0.23 | 50% | -0.31 | -0.44 | 25% | -0.51 | -0.64 | 0.33 |
| healthy_uptrend | 6 | 0 | 33% | +0.06 | -0.03 | 50% | +0.16 | +0.08 | 33% | -0.12 | -0.20 | 0.71 |
| high_vol_selloff | 21 | 0 | 38% | -0.20 | -0.29 | 52% | -0.07 | -0.16 | 52% | -0.03 | -0.12 | 0.93 |
| narrow_uptrend | 1 | 0 | 100% | +1.29 | +1.22 | 100% | +1.00 | +0.93 | 100% | +1.79 | +1.72 | inf |
| **all** | 43 | 0 | 49% | -0.02 | -0.11 | 60% | +0.10 | +0.01 | 58% | +0.16 | +0.07 | 1.44 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
