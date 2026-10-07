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
_Pending: filled in from swing replay on real data._
