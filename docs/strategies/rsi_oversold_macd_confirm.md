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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 361 | 12 | 53% | +0.07 | -0.02 | -0.05 | 55% | +0.09 | -0.00 | -0.01 | 52% | +0.11 | +0.02 | -0.01 | 1.30 |
| correction | 108 | 2 | 48% | -0.03 | -0.17 | -0.02 | 73% | +0.38 | +0.24 | -0.04 | 75% | +0.91 | +0.77 | -0.02 | 5.49 |
| healthy_uptrend | 1628 | 70 | 52% | +0.01 | -0.07 | -0.10 | 47% | -0.07 | -0.15 | -0.16 | 44% | -0.11 | -0.19 | -0.20 | 0.76 |
| high_vol_selloff | 1273 | 57 | 66% | +0.17 | +0.06 | -0.12 | 67% | +0.18 | +0.07 | -0.17 | 61% | +0.11 | -0.00 | -0.23 | 1.29 |
| narrow_uptrend | 301 | 7 | 52% | +0.01 | -0.08 | +0.05 | 51% | +0.04 | -0.05 | +0.05 | 55% | +0.15 | +0.05 | +0.03 | 1.36 |
| **all** | 3671 | 148 | 57% | +0.07 | -0.02 | -0.09 | 56% | +0.05 | -0.04 | -0.13 | 53% | +0.03 | -0.06 | -0.17 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 24 trades, win 46%, avg +0.16R, PF 1.35, P&L $2,944 on $100k, avg hold 10.5 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2418 | 99 | 54% | +0.05 | -0.02 | -0.10 | 55% | +0.06 | -0.01 | -0.15 | 58% | +0.14 | +0.07 | -0.13 | 1.38 |
| correction | 846 | 31 | 59% | +0.17 | +0.10 | -0.01 | 60% | +0.22 | +0.15 | +0.00 | 59% | +0.30 | +0.23 | +0.05 | 1.86 |
| healthy_uptrend | 4473 | 180 | 50% | -0.01 | -0.09 | -0.12 | 49% | -0.04 | -0.12 | -0.14 | 50% | -0.03 | -0.11 | -0.16 | 0.94 |
| high_vol_selloff | 5557 | 252 | 50% | +0.02 | -0.06 | -0.09 | 60% | +0.13 | +0.05 | -0.06 | 59% | +0.15 | +0.08 | -0.06 | 1.49 |
| narrow_uptrend | 1928 | 71 | 49% | -0.02 | -0.10 | -0.13 | 51% | -0.00 | -0.08 | -0.13 | 52% | +0.04 | -0.04 | -0.09 | 1.11 |
| **all** | 15222 | 633 | 51% | +0.02 | -0.06 | -0.10 | 55% | +0.06 | -0.02 | -0.10 | 55% | +0.09 | +0.01 | -0.10 | 1.25 |

Portfolio replay (net of costs, slots shared with its run): 129 trades, win 46%, avg +0.19R, PF 1.49, P&L $8,484 on $100k, avg hold 10.7 bars.
