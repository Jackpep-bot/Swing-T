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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 65874 | 61050 | 52% | +0.02 | -0.09 | 49% | +0.05 | -0.07 | 48% | +0.17 | +0.05 | 1.35 |
| correction | 7265 | 6637 | 34% | -0.30 | -0.49 | 46% | -0.11 | -0.30 | 47% | +0.22 | +0.04 | 1.45 |
| healthy_uptrend | 189594 | 172271 | 49% | +0.01 | -0.11 | 45% | -0.03 | -0.15 | 40% | -0.01 | -0.13 | 0.98 |
| high_vol_selloff | 38875 | 34498 | 56% | +0.07 | -0.07 | 57% | +0.19 | +0.06 | 49% | +0.15 | +0.02 | 1.31 |
| narrow_uptrend | 33749 | 31545 | 38% | -0.15 | -0.27 | 37% | -0.19 | -0.31 | 30% | -0.23 | -0.36 | 0.66 |
| **all** | 335357 | 306001 | 50% | +0.00 | -0.12 | 47% | +0.00 | -0.12 | 42% | +0.03 | -0.09 | 1.06 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 221679 | 202529 | 53% | +0.06 | -0.04 | 53% | +0.13 | +0.03 | 49% | +0.22 | +0.12 | 1.47 |
| correction | 135374 | 122032 | 51% | +0.02 | -0.09 | 52% | +0.10 | -0.01 | 47% | +0.15 | +0.05 | 1.31 |
| healthy_uptrend | 584261 | 529132 | 49% | -0.01 | -0.12 | 46% | -0.00 | -0.12 | 41% | -0.00 | -0.12 | 0.99 |
| high_vol_selloff | 255619 | 234060 | 52% | +0.01 | -0.10 | 53% | +0.06 | -0.05 | 48% | +0.08 | -0.03 | 1.17 |
| narrow_uptrend | 154360 | 140036 | 50% | +0.03 | -0.09 | 49% | +0.06 | -0.06 | 47% | +0.11 | +0.00 | 1.23 |
| **all** | 1351293 | 1227789 | 50% | +0.01 | -0.10 | 49% | +0.05 | -0.06 | 45% | +0.08 | -0.03 | 1.15 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
