---
slug: rsi_oversold_macd_confirm
name: RSI < 30 recovery confirmed by MACD cross (Webull Learn)
originators: [Webull Learn (broker education; generic RSI/MACD folklore, no single originator)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# RSI < 30 recovery confirmed by MACD cross

## One-line summary
After RSI(14) dips below 30 and climbs back above it, buy when the MACD line crosses above its signal line; skip
the trade if RSI is already above 70 when MACD crosses.

## Origin and lineage
Broker course material (Webull Learn, "Swing Trade With MACD And RSI"). RSI is Wilder (1978); MACD is Appel
(late 1970s). The combination is generic retail teaching with no originator, no published test, and no stated
exit or stop. Catalog grade: none, "illustrative only".

## Exact rules (as taught)
- Universe: not specified (any liquid stock after a downtrend).
- Setup: RSI(14) closes below 30, then closes back above 30.
- Trigger: MACD(12,26,9) line crosses above the signal line, confirming the RSI turn.
- Filter: skip when MACD crosses up while RSI(14) > 70.
- Entry / stop / target / time exit / sizing: **not specified by the source** (WebFetch 2026-10-07 confirms the page
  gives no exit, stop or statistics).

## Why it should work
Claimed mechanism: short-term selling exhaustion (RSI) followed by momentum turn (MACD). Counterparty would be
late sellers capitulating. Both indicators are lagging transforms of the same closes, so the "confirmation" is
largely redundant; the MACD cross typically arrives several bars after the RSI recovery, after part of the bounce.

## When it works and when it fails
- Works: range-bound or pullback-within-uptrend names where oversold readings mean-revert (the same environment
  where RSI-2 works, `docs/methods/11-rsi2-connors-mean-reversion.md`).
- Fails: persistent downtrends (RSI can sit near 30 for weeks; MACD whipsaws around zero), high-vol selloffs.

## Parameters and sensitivity
RSI length (14), oversold level (30), lookback window allowing the RSI recovery and MACD cross to be "together"
(source silent; engine default 5 bars), MACD (12,26,9). Trap: tuning the pairing window and the exit on the same
sample creates a different strategy per parameter set; fix them before replay.

## Evidence
None located. No broker statistics. The closest tested relative is Connors RSI-2 (thin edge, see doc 11).
Standalone indicator crossovers sit in the methods.md 1a #16 "avoid bucket" (data-snooping corrections).

## Common mistakes
Treating RSI < 30 as a buy in a downtrend; no stop; entering on the MACD cross days after the low (poor R:R);
ignoring the trend filter that RSI-2 needs to work.

## Discretionary parts and how to make them mechanical
"After a downtrend" -> `trend_state <= 0` or `ret_63d < 0` at setup (engine choice). "Together" -> RSI recovery
within the last `pair_window` bars of the MACD cross. Exit/stop are engine choices (below), not the source's.

## Implementation spec for swing-engine
- Features reused: `rsi_14`, `macd`, `macd_signal`, `atr_14`, `sma_200`, `low` (all in `docs/feature-contract.md`).
- New helper features (causal): `rsi14_min_10 = rolling min(rsi_14, 10)`;
  `rsi_up30_bars = bars since rsi_14 crossed from < 30 to >= 30`; `macd_xup = macd > macd_signal and prior macd <= prior macd_signal`.
- Signal on close t: `macd_xup` and `rsi_up30_bars <= pair_window (5)` and `rsi14_min_10 < 30` and `rsi_14 <= 70`.
- Entry: next open (backtest default). Stop: `min(low over 10 bars) - 0.5 * atr_14` (engine choice).
- Target: none fixed; reference target = `sma_50` if above entry, else exit by rule. Exits: `macd < macd_signal`
  (cross down) or `rsi_14 > 70`, time stop `max_hold_days = 15`.
- `min_reward_risk = 0.0` (rule exit, like `rsi2_meanrev`); comparison variant with `close > sma_200` gate.
- Missing: nothing structural; a "bars since cross" helper.

## What the router should know
Mean-reversion family: allow at most in `choppy` / `narrow_uptrend` with the RSI-2 multipliers; never in `correction`.
Expect heavy overlap with `rsi2_meanrev` signals; log overlap rather than double-sizing.

## Signs of decay to monitor
Win rate < 50% with payoff < 1.2 over 50+ replay trades; median entry already > 1 ATR off the 10-day low (late entry).

## Sources
- https://www.webullapp.com/learn/courseware/1k79fn/Swing-Trade-With-MACD-And-RSI?courseId=553Fb2
- docs/methods/11-rsi2-connors-mean-reversion.md; docs/methods.md 1a #16

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 365 | 3 | 52% | +0.06 | +0.03 | 54% | +0.08 | +0.05 | 51% | +0.09 | +0.06 | 1.24 |
| correction | 108 | 0 | 49% | -0.03 | -0.06 | 73% | +0.39 | +0.36 | 75% | +0.90 | +0.87 | 5.57 |
| healthy_uptrend | 1646 | 17 | 52% | -0.00 | -0.04 | 47% | -0.09 | -0.12 | 44% | -0.13 | -0.16 | 0.73 |
| high_vol_selloff | 1276 | 10 | 65% | +0.16 | +0.12 | 67% | +0.17 | +0.14 | 61% | +0.10 | +0.07 | 1.28 |
| narrow_uptrend | 298 | 2 | 51% | +0.00 | -0.04 | 52% | +0.05 | +0.00 | 55% | +0.14 | +0.10 | 1.35 |
| **all** | 3693 | 32 | 56% | +0.06 | +0.03 | 56% | +0.04 | +0.01 | 52% | +0.02 | -0.01 | 1.06 |

Portfolio replay (net of costs, slots shared with its run): 4 trades, win 50%, avg -0.31R, PF 0.40, P&L $-725 on $100k, avg hold 9.8 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2421 | 26 | 54% | +0.05 | +0.02 | 56% | +0.06 | +0.03 | 58% | +0.14 | +0.11 | 1.37 |
| correction | 870 | 8 | 59% | +0.18 | +0.15 | 60% | +0.24 | +0.22 | 58% | +0.31 | +0.29 | 1.89 |
| healthy_uptrend | 4048 | 37 | 50% | -0.01 | -0.04 | 49% | -0.03 | -0.06 | 51% | -0.01 | -0.04 | 0.98 |
| high_vol_selloff | 5553 | 36 | 50% | +0.02 | -0.00 | 60% | +0.13 | +0.12 | 59% | +0.16 | +0.14 | 1.54 |
| narrow_uptrend | 1881 | 15 | 49% | -0.02 | -0.05 | 50% | -0.00 | -0.03 | 52% | +0.03 | +0.01 | 1.09 |
| **all** | 14773 | 122 | 51% | +0.02 | -0.01 | 55% | +0.07 | +0.04 | 56% | +0.10 | +0.08 | 1.29 |

Portfolio replay (net of costs, slots shared with its run): 28 trades, win 61%, avg +0.38R, PF 2.40, P&L $6,850 on $100k, avg hold 11.3 bars.
