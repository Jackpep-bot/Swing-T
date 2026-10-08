---
slug: supertrend_flip_strategy
name: Supertrend / ATR-trailing-stop flip entries (TradingView, thinkorswim ATRTrailingStopLE)
originators: [Olivier Seban (attributed), TradingView built-in "Supertrend Strategy", thinkorswim ATRTrailingStopLE/SE]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 40]
timeframe: daily
direction: long (stop-and-reverse in source; engine takes long flips only)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Supertrend flip

## One-line summary
Go long when price closes above an ATR trailing line (Supertrend direction flips up); exit when it closes back below the line,
which ratchets up and never down while long.

## Origin and lineage
Supertrend is commonly attributed to French trader Olivier Seban (2000s; exact date varies by source, unverified). It is a
variant of Wilder-style volatility stops and the Chandelier exit. TradingView ships it as a demonstration "Supertrend Strategy"
(ATR 10, factor 3, stop-and-reverse); thinkorswim ships the closely related ATRTrailingStopLE/SE (long entry when close rises
above the ATR trailing stop).

## Exact rules (TradingView default)
- ATR(10) (Wilder smoothing in TradingView's `ta.supertrend`), mid = (H+L)/2.
- Basic bands: upper_b = mid + 3*ATR; lower_b = mid - 3*ATR.
- Final lower band: lower_t = lower_b_t if lower_b_t > lower_{t-1} or close_{t-1} < lower_{t-1}, else lower_{t-1}.
  Final upper band: upper_t = upper_b_t if upper_b_t < upper_{t-1} or close_{t-1} > upper_{t-1}, else upper_{t-1}.
- Direction: flips to up when close > prior final upper band; flips to down when close < prior final lower band.
  Supertrend line = lower band in an uptrend, upper band in a downtrend.
- Entry: long on the flip-up bar (TradingView fills at the next bar open by default). Short on flip-down (ignored here).
- Stop/exit: the Supertrend line itself (stop-and-reverse). No separate target. Sizing not taught.
- thinkorswim ATRTrailingStopLE: same idea with selectable ATR average type (simple, exponential, weighted, Wilder's, Hull) and a
  "modified" true-range option; defaults not verified.

## Why it should work
Pure trend following with a volatility-scaled trailing stop: small losses when the flip fails, open-ended gains when a trend
persists. The other side is the under-reacting or mean-reverting trader. Edge, if any, is time-series momentum (Moskowitz, Ooi
and Pedersen 2012 documented it at 1-12 month horizons in futures; it is weaker in single stocks at daily-swing horizons).

## When it works and when it fails
Works in long one-directional moves. Fails badly in ranges: every 3-ATR swing produces a flip, and with stop-and-reverse the
system is always in the market. Gap-downs fill below the line.

## Parameters and sensitivity
ATR length (7-14), factor (2-4). Lower factor = more trades, more whipsaw. Surface is smooth in most published sweeps; still
test only (10, 3) plus one neighbour each side.

## Evidence
None published by TradingView or thinkorswim (demonstration strategies). No academic test of Supertrend specifically found.
Grade none.

## Common mistakes
Using the current bar's band instead of the prior bar's for the flip test (look-ahead); acting intrabar on a close-based rule;
treating "always in" as acceptable for a long-only stock book.

## Discretionary parts and how to make them mechanical
None.

## Implementation spec for swing-engine
- Features `features/trend_stops.py`: `st_line_10_3`, `st_dir_10_3` (+1/-1), `st_dir_prev`. ATR via Wilder smoothing of true
  range (the panel's `atr_14` uses period 14; add `atr_10`).
- Strategy `strategies/supertrend_flip.py`, registered `supertrend_flip`, disabled.
- Signal on close t: st_dir_t == +1 and st_dir_prev == -1. Optional gate `min_trend_state` default -1 (no gate, faithful).
- Entry: next open. Initial stop: st_line_t (the final lower band). Risk = entry - stop; typically 3-6 ATR, so position sizes are
  small at 1% risk.
- Exit: `should_exit` when st_dir flips to -1 on a close. The engine's intrabar stop sits at the initial line; the line's ratchet
  is not applied by the engine's generic trailing (which uses best_price - k*ATR), so either add a "stop follows column"
  ratchet hook (missing) or rely on the close-based rule exit.
- Target: reference `target_r` 5.0 (rule exit primary). max_hold_days: 60. min_reward_risk param 1.0.
- Reuses `atr` logic; missing: supertrend columns, per-strategy stop-follows-indicator hook.

## What the router should know
Trend follower, healthy_uptrend only. Very wide initial stops: few shares, long holds, low win rate expected.

## Signs of decay to monitor
Flips per symbol per year rising; average loser approaching average winner.

## Sources
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://ru.tradingview.com/support/solutions/43000599890
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ATRTrailingStopLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ATRTrailingStopSE
- https://help.ctrader.com/indicators/built-in/trend/supertrend/ (band formula)
- Moskowitz, Ooi, Pedersen, "Time Series Momentum", Journal of Financial Economics, 2012 (background only)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1624 | 1 | 55% | +0.07 | +0.05 | 50% | +0.05 | +0.03 | 52% | +0.17 | +0.14 | 1.54 |
| correction | 297 | 0 | 70% | +0.14 | +0.12 | 72% | +0.33 | +0.31 | 70% | +0.33 | +0.31 | 2.82 |
| healthy_uptrend | 5896 | 15 | 46% | -0.04 | -0.07 | 45% | -0.05 | -0.08 | 45% | -0.03 | -0.06 | 0.93 |
| high_vol_selloff | 1004 | 0 | 60% | +0.07 | +0.05 | 63% | +0.11 | +0.09 | 55% | +0.09 | +0.07 | 1.26 |
| narrow_uptrend | 457 | 0 | 47% | -0.02 | -0.05 | 47% | -0.02 | -0.05 | 45% | -0.03 | -0.05 | 0.93 |
| **all** | 9278 | 16 | 50% | -0.00 | -0.03 | 49% | +0.00 | -0.03 | 48% | +0.03 | -0.00 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4947 | 2 | 49% | -0.01 | -0.04 | 53% | +0.04 | +0.02 | 54% | +0.15 | +0.13 | 1.47 |
| correction | 3862 | 4 | 52% | +0.01 | -0.01 | 60% | +0.13 | +0.11 | 59% | +0.19 | +0.17 | 1.71 |
| healthy_uptrend | 18558 | 26 | 51% | +0.02 | -0.01 | 51% | +0.03 | +0.00 | 49% | +0.04 | +0.01 | 1.09 |
| high_vol_selloff | 6697 | 7 | 49% | -0.03 | -0.05 | 50% | -0.03 | -0.05 | 54% | +0.06 | +0.04 | 1.19 |
| narrow_uptrend | 4505 | 1 | 49% | -0.00 | -0.03 | 52% | +0.03 | +0.00 | 49% | +0.03 | +0.01 | 1.09 |
| **all** | 38569 | 40 | 50% | +0.00 | -0.02 | 52% | +0.03 | +0.01 | 51% | +0.07 | +0.05 | 1.20 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
