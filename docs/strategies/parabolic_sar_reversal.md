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
_Pending: filled in from swing replay on real data._
