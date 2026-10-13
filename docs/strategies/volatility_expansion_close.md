---
slug: volatility_expansion_close
name: Volatility Expansion Close / Open entries (TradeStation "Volty Expan", TradingView)
originators: [TradeStation, TradingView]
category: volatility_breakout
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long            # built-ins have SE mirrors; swing-engine strategies are long-only
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built          # needs the stop-entry hook
---

# Volatility Expansion Close / Open

## One-line summary
Buy on a stop placed a fixed multiple of short ATR above yesterday's close (or today's open); a platform demo of
volatility breakout with no published evidence.

## Origin and lineage
TradeStation built-in strategies "Volty Expan Close LE/SE/LX/SX" and "Volty Expan Open LE/SE"; TradingView ships
"Volty Expan Close Strategy". Same family as Williams' volatility breakout (`open_volatility_breakout.md`).

## Exact rules
- Volty Expan Close LE: buy stop for the next bar at `close_t + 0.75 x ATR(5)`. SE mirror: `close_t - 0.75 x ATR(5)`.
- Volty Expan Close LX: sell stop at `close_t - 1.5 x ATR(5)`, recomputed each bar (so it trails with the close).
- Volty Expan Open LE: buy stop at `open_{t+1} + 1.2 x average range(4)`.
- TradingView: bands `close +/- ATR(length) x mult` from the previous bar (defaults length 5, mult 0.75 recalled; the
  TV doc does not state them); long if price exceeds the prior upper band.
- No targets, filters or sizing; always-in-market when SE is paired with LE.

## Why it should work
A move of 0.75 ATR(5) beyond the close in one session is unusual; the hypothesis is that unusual moves persist. The
other side is mean-reversion traders. No universe or trend filter, so in stocks it mostly trades noise.

## When it works and when it fails
Works in trending futures with persistent vol expansion. Fails in ranges; in stocks overnight gaps through the stop
fill at the open, often at the day's extreme.

## Parameters and sensitivity
ATR length 3-10, entry mult 0.5-1.5, exit mult 1-2.5. Trap: entry/exit mults fitted jointly.

## Evidence
None. Broker documentation only; demo strategies.

## Common mistakes
Running both LE and SE in stocks (shorts); assuming fills exactly at the stop on gap days.

## Discretionary parts and how to make them mechanical
Fully mechanical. Add `trend_state >= 1` as the only filter for the comparison run.

## Implementation spec for swing-engine
- Features (new): `atr_5` = simple 5-bar mean of true range (TradeStation AvgTrueRange); `avg_range_4` = SMA4(high-low).
- Signal at close t: trigger `close_t + 0.75 x atr_5_t`, valid one session.
- **Missing hook**: stop-entry fill at `max(open_{t+1}, trigger)` if `high_{t+1} >= trigger`.
- Stop/exit: trailing stop `close_t - 1.5 x atr_5_t`, ratcheted each close (never loosened); the backtester's
  trailing logic ratchets on the close, so this maps to a strategy-level trail param.
- Target: none -> `min_reward_risk: 0.0`; `max_hold_days: 20`.
- Open variant needs the stop-off-the-open hook described in `open_volatility_breakout.md`.

## What the router should know
Baseline/control only; never enable for execution.

## Signs of decay to monitor
Not applicable beyond the replay; treat as a null-hypothesis benchmark for the other breakout cards.

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/volty_expan_close_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/volty_expan_close_lx_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/volty_expan_open_le_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://ru.tradingview.com/support/solutions/43000599890

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 36100 | 26241 | 53% | +0.02 | -0.09 | -0.27 | 51% | +0.03 | -0.09 | -0.31 | 45% | +0.10 | -0.02 | -0.36 | 1.20 |
| correction | 2934 | 2103 | 47% | -0.08 | -0.25 | -0.31 | 50% | -0.08 | -0.25 | -0.61 | 45% | +0.01 | -0.16 | -0.97 | 1.01 |
| healthy_uptrend | 165555 | 120731 | 50% | +0.02 | -0.10 | -0.15 | 48% | +0.03 | -0.10 | -0.16 | 42% | +0.07 | -0.06 | -0.18 | 1.12 |
| high_vol_selloff | 12633 | 9394 | 49% | -0.05 | -0.19 | -0.19 | 43% | -0.13 | -0.27 | -0.23 | 34% | -0.22 | -0.35 | -0.25 | 0.66 |
| narrow_uptrend | 15005 | 10832 | 42% | -0.10 | -0.22 | -0.21 | 38% | -0.16 | -0.27 | -0.24 | 36% | -0.17 | -0.29 | -0.39 | 0.71 |
| **all** | 232227 | 169301 | 50% | +0.01 | -0.12 | -0.17 | 48% | +0.01 | -0.12 | -0.20 | 42% | +0.04 | -0.08 | -0.23 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 103721 | 73014 | 55% | +0.04 | -0.08 | -0.19 | 56% | +0.10 | -0.01 | -0.23 | 51% | +0.14 | +0.03 | -0.29 | 1.34 |
| correction | 43007 | 30950 | 51% | -0.03 | -0.17 | -0.31 | 50% | -0.01 | -0.16 | -0.37 | 44% | -0.01 | -0.15 | -0.37 | 0.98 |
| healthy_uptrend | 580781 | 420789 | 50% | -0.00 | -0.12 | -0.16 | 48% | +0.00 | -0.12 | -0.18 | 43% | +0.01 | -0.11 | -0.22 | 1.02 |
| high_vol_selloff | 71747 | 53086 | 49% | -0.04 | -0.16 | -0.18 | 48% | -0.07 | -0.20 | -0.21 | 43% | -0.09 | -0.22 | -0.25 | 0.82 |
| narrow_uptrend | 96463 | 68462 | 52% | +0.02 | -0.09 | -0.20 | 52% | +0.06 | -0.06 | -0.22 | 47% | +0.06 | -0.05 | -0.24 | 1.14 |
| **all** | 895719 | 646301 | 50% | +0.00 | -0.12 | -0.18 | 49% | +0.01 | -0.11 | -0.20 | 45% | +0.02 | -0.10 | -0.24 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
