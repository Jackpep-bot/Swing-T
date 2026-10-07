---
slug: momentum_pinball
name: Momentum Pinball (LBR/RSI first-hour breakout)
originators: [Linda Bradford Raschke, Laurence Connors]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [0, 2]
timeframe: daily signal, 60-minute entry
direction: long   # short mirror on LBR/RSI > 70; engine is long-only
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: false   # true entry needs first-hour intraday high/low
status: not_built
---

# Momentum Pinball

## One-line summary
A 3-period RSI of daily price change flags an oversold day; next day, buy a break above the first trading hour's high
and be out within two sessions.

## Origin and lineage
*Street Smarts* (1995). The "LBR/RSI" is Raschke's oscillator: RSI(3) applied to the 1-day rate of change rather than to
price. The authors pitched it for 1-2 day flips; no independent test exists.

## Exact rules (long)
- Indicator: ROC1_t = close_t - close_{t-1}; LBR/RSI = RSI(3) of ROC1.
- Signal: LBR/RSI closes below 30 -> look to buy tomorrow (above 70 -> short).
- Entry: next day, the first trading hour sets a range; buy stop above the first-hour high.
- Stop: the first-hour low.
- Exit: if losing at the close, exit; if profitable or flat, carry overnight and exit next day. Never hold a second night.
- Re-entry allowed if stopped and the range breaks again. Prefer instruments with a good average daily range.

## Why it should work
Short-term exhaustion of daily momentum: after an extreme run of down closes the first-hour range break shows buyers
taking over, and the strict 1-night limit keeps exposure to the bounce only.

## When it works and when it fails
Needs range and liquidity. Fails in trending sell-offs where oversold stays oversold, and on news days with gap-and-go.

## Parameters and sensitivity
RSI length 3, thresholds 30/70, first-hour window (60 min). The ROC-of-RSI double transform makes thresholds touchy;
keep book values.

## Evidence
Authors' claim only; no independent test located (catalog C3).

## Common mistakes
Approximating the first-hour high with the prior-day high and calling it Momentum Pinball (a different method);
holding a second night.

## Discretionary parts and how to make them mechanical
Already mechanical. "Good average daily range" -> `atr_pct_14 >= 0.02`.

## Implementation spec for swing-engine
- Reuses: `close`, `prev_close`, `atr_pct_14`; `features/indicators.py rsi()` applied to `close.diff()`.
- New feature: `lbr_rsi = rsi(close.diff(), 3)` (note: `rsi()` diffs its input, so pass ROC1 as the series).
- Signal at close t: `lbr_rsi < 30`.
- True entry needs 60-minute bars for day t+1: buy stop at first-hour high, stop first-hour low, exit at close t+1 if
  losing else at close t+2 (`max_hold_days: 2`).
- Daily approximation (must be labelled `approx_daily`): buy stop at `high_t`; fill on t+1 if `high_{t+1} >= high_t`
  at `max(open_{t+1}, high_t)`; stop `low_t`. This changes the method.
- `min_reward_risk: 0.0`. Missing: intraday bar store for first-hour range; stop-entry hook.
- Natural home is the monitor path (live first-hour range) rather than the nightly daily scan.

## What the router should know
Two-day trade; comparable to `rsi2_meanrev` (also close-based oversold). Do not run both on the same symbol/day.

## Signs of decay to monitor
Win rate on 2-day holds < 50% with payoff < 1.2; first-hour breaks that reverse the same day > 50%.

## Sources
- https://www.whselfinvest.de/en/trading-platform/free-trading-strategies/tradingsystem/48-momentum-pinball-trading-indicator-raschke-linda-connors-larry
- https://strategyquant.com/forum/topic/2846-linda-bradford-raschkes-momentum-pinball/

## Empirical (replay)
_Pending: filled in from swing replay on real data._
