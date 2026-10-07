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
_Pending: filled in from swing replay on real data._
