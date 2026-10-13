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
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 36168 | 26290 | 53% | +0.02 | -0.09 | 51% | +0.03 | -0.09 | 45% | +0.10 | -0.02 | 1.20 |
| correction | 2949 | 2113 | 47% | -0.09 | -0.26 | 50% | -0.08 | -0.25 | 45% | +0.01 | -0.16 | 1.01 |
| healthy_uptrend | 165835 | 120946 | 50% | +0.02 | -0.11 | 48% | +0.03 | -0.10 | 42% | +0.07 | -0.06 | 1.12 |
| high_vol_selloff | 12672 | 9424 | 49% | -0.06 | -0.19 | 43% | -0.14 | -0.27 | 34% | -0.22 | -0.35 | 0.66 |
| narrow_uptrend | 15054 | 10865 | 42% | -0.10 | -0.22 | 38% | -0.15 | -0.27 | 36% | -0.17 | -0.29 | 0.71 |
| **all** | 232678 | 169638 | 50% | +0.01 | -0.12 | 48% | +0.01 | -0.12 | 42% | +0.04 | -0.08 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 106337 | 74904 | 55% | +0.04 | -0.08 | 56% | +0.11 | -0.01 | 51% | +0.14 | +0.03 | 1.34 |
| correction | 43757 | 31508 | 51% | -0.03 | -0.18 | 50% | -0.02 | -0.16 | 44% | -0.02 | -0.16 | 0.97 |
| healthy_uptrend | 598013 | 433842 | 50% | -0.00 | -0.12 | 48% | +0.00 | -0.12 | 43% | +0.01 | -0.11 | 1.02 |
| high_vol_selloff | 73929 | 54759 | 50% | -0.04 | -0.16 | 48% | -0.08 | -0.21 | 43% | -0.11 | -0.23 | 0.80 |
| narrow_uptrend | 98736 | 70183 | 52% | +0.02 | -0.10 | 51% | +0.06 | -0.06 | 47% | +0.06 | -0.06 | 1.13 |
| **all** | 920772 | 665196 | 50% | +0.00 | -0.12 | 49% | +0.01 | -0.11 | 45% | +0.02 | -0.10 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
