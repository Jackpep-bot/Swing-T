---
slug: parabolic_sar_reversal
name: Parabolic SAR stop-and-reverse entries (TradeStation, TradingView)
originators: [J. Welles Wilder Jr. (New Concepts in Technical Trading Systems, 1978), TradeStation Parabolic LE/SE, TradingView]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long (stop-and-reverse in source; engine takes long side only)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Parabolic SAR reversal

## One-line summary
Buy when price touches the falling SAR (stop entry at the SAR), then trail with a SAR that accelerates toward price as new highs
are made; exit/reverse when price touches the rising SAR.

## Origin and lineage
J. Welles Wilder Jr., New Concepts in Technical Trading Systems (1978), alongside RSI, ATR and ADX. Wilder designed it as an
always-in-the-market stop-and-reverse system. TradeStation ships Parabolic LE/SE (stop entry at SAR) and Parabolic_m Trail LX;
TradingView ships "Parabolic SAR Strategy" (start 0.02, increment 0.02, max 0.2). ChartSchool also suggests SAR as a trailing exit
for other setups (see ichimoku_cloud_pullback, rsi2 doc 11).

## Exact rules
- SAR recursion: SAR_{t+1} = SAR_t + AF * (EP - SAR_t), where EP = extreme point (highest high of the current long, lowest low of
  the current short). AF starts at 0.02, rises by 0.02 each bar a new EP is set, capped at 0.20.
- Long-side clamp: SAR may not be above the low of the current or prior bar (Wilder: the two prior lows); short mirror on highs.
- Reversal: when a bar's low touches/pierces the long SAR, the position reverses; the new short SAR starts at the prior EP and
  AF resets to 0.02. Mirror for shorts.
- TradeStation Parabolic LE: buy-stop order at the current (short-side) SAR, i.e. long when high >= SAR. Parabolic_m Trail LX:
  SAR trailing exit whose first-bar stop is low - 1.5 * ATR(3).
- TradingView: stop-and-reverse orders resting at the SAR level.
- Sizing, targets: none.

## Why it should work
Wilder's idea is time-and-price: a stop that tightens faster the longer and stronger the trend, harvesting the middle of
intermediate moves. Counterparty: generic trend-following. Wilder's own performance claims (repeated on Wikipedia, e.g. a 95%
figure) are unsourced marketing-era numbers and were not verified.

## When it works and when it fails
Works in strong, persistent trends. In ranges it reverses constantly; with AF accelerating, stops sit very close after a run, so
normal pullbacks stop out the trade.

## Parameters and sensitivity
AF start/step (0.01-0.03; Wilder, as quoted on Wikipedia, found an increment of about 0.018-0.021 best on his data), AF max (0.1-0.3). Lower step = slower stop,
fewer trades. Test defaults only plus step 0.01.

## Evidence
No performance data from TradeStation or TradingView (demonstration strategies). No academic test of SAR as a stock swing
system was found in this pass. Grade none.

## Common mistakes
Forgetting the two-bar clamp (SAR inside the prior bar's range); computing tomorrow's SAR using today's not-yet-closed bar;
treating SAR flips on a close basis while the source uses intrabar stop orders.

## Discretionary parts and how to make them mechanical
None. The only choice is fill model: the source is a stop order at SAR (intrabar), which the engine cannot place.

## Implementation spec for swing-engine
- Features `features/trend_stops.py` (shared with supertrend): `psar` (value for the next bar, computed on bar t),
  `psar_dir` (+1 long / -1 short), `psar_dir_prev`, `psar_af`.
- Strategy `strategies/parabolic_sar.py`, registered `parabolic_sar`, disabled.
- Engine approximation of the stop entry: signal on close t when psar_dir flips to +1 on bar t (low-side series detected the
  reversal intrabar); fill next open. This lags the source by up to one bar; note it in the trial log.
- Initial stop: the new long SAR for t+1 (= lowest low of the prior short leg, which is the prior EP). Optionally
  Parabolic_m style: min(that, low_t - 1.5 * ATR(3)).
- Trailing: needs a "stop follows indicator column" hook (missing; engine trailing is best_price - k*ATR); fallback is
  `should_exit` when close < psar (close-based, looser than source).
- Target: reference `target_r` 4.0. max_hold_days: 40. min_reward_risk param 1.0.
- Missing: SAR features, stop-entry order hook, column-following trailing stop.

## What the router should know
Trend follower; healthy_uptrend only. Same family as supertrend_flip (expect correlated entries).

## Signs of decay to monitor
Median hold < 3 bars; reversals per symbol per quarter rising.

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/parabolic_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/parabolic_se_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/parabolic_m_trail_lx_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://ru.tradingview.com/support/solutions/43000599890
- https://en.wikipedia.org/wiki/Parabolic_SAR
- Wilder, J. W., New Concepts in Technical Trading Systems, 1978 (not read directly)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 65938 | 61107 | 52% | +0.03 | -0.02 | 49% | +0.05 | +0.00 | 48% | +0.17 | +0.12 | 1.35 |
| correction | 7272 | 6644 | 34% | -0.30 | -0.34 | 46% | -0.11 | -0.15 | 47% | +0.22 | +0.18 | 1.45 |
| healthy_uptrend | 189777 | 172437 | 49% | +0.01 | -0.04 | 45% | -0.03 | -0.08 | 40% | -0.01 | -0.06 | 0.98 |
| high_vol_selloff | 38963 | 34578 | 56% | +0.07 | +0.03 | 57% | +0.19 | +0.16 | 48% | +0.15 | +0.12 | 1.31 |
| narrow_uptrend | 33778 | 31573 | 38% | -0.15 | -0.20 | 37% | -0.18 | -0.23 | 30% | -0.23 | -0.28 | 0.66 |
| **all** | 335728 | 306339 | 50% | +0.00 | -0.04 | 47% | +0.00 | -0.04 | 42% | +0.03 | -0.01 | 1.06 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 211782 | 193522 | 53% | +0.06 | +0.02 | 53% | +0.13 | +0.09 | 49% | +0.22 | +0.18 | 1.47 |
| correction | 134508 | 121337 | 51% | +0.02 | -0.01 | 52% | +0.10 | +0.07 | 47% | +0.16 | +0.13 | 1.33 |
| healthy_uptrend | 528100 | 477523 | 49% | -0.00 | -0.04 | 47% | +0.00 | -0.04 | 42% | +0.01 | -0.03 | 1.02 |
| high_vol_selloff | 243866 | 223181 | 51% | +0.01 | -0.02 | 52% | +0.06 | +0.03 | 48% | +0.08 | +0.05 | 1.16 |
| narrow_uptrend | 155758 | 141506 | 50% | +0.02 | -0.01 | 48% | +0.04 | -0.00 | 44% | +0.07 | +0.03 | 1.13 |
| **all** | 1274014 | 1157069 | 50% | +0.01 | -0.02 | 49% | +0.05 | +0.01 | 45% | +0.08 | +0.04 | 1.15 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
