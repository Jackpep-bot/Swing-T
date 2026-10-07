---
slug: key_reversal_day
name: Key reversal day (thinkorswim, TradeStation, classic)
originators: [classic futures-pit pattern; Schwab thinkorswim and TradeStation built-in strategies]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 4]
timeframe: daily
direction: long   # bearish mirror (new high, close below prior close) used as an exit signal (KeyRevLX)
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built   # the key_reversal feature flag exists; no strategy module, not in config/settings.yaml
---

# Key reversal day

## One-line summary
A day that undercuts the prior low(s) but closes above the prior close; widely coded, weakly predictive, useful at best
as a trigger inside another setup.

## Origin and lineage
Futures-pit lore; codified as broker built-ins: thinkorswim KeyRevLE / KeyRevLX and TradeStation Key Reversal LE/LX/SE/SX.

## Exact rules (variants)
- thinkorswim KeyRevLE: low below the lows of `length` prior bars and close above the prior close -> long entry on the
  next bar. KeyRevLX: high above `length` prior highs and close below prior close -> exit next bar.
- TradeStation Key Reversal LE: same, default N = 1, buy next open.
- Classic bullish: new low below prior low, close above prior close; strict form needs close above the prior HIGH.
  Wider range and heavier volume said to strengthen it. Entry: next-day break of the reversal bar's high; stop below
  the reversal bar's low.
- No targets or sizing published by the brokers.

## Why it should work
Intraday capitulation then recovery shows sellers exhausted. The weak evidence suggests the bar mostly reflects noise
unless context (support, trend, volume) is added.

## When it works and when it fails
Possibly after extended declines into support; fails as a standalone signal (see evidence).

## Parameters and sensitivity
N prior bars (1 vs 3-5), strict vs loose close rule, volume multiple, entry (next open vs break of high).

## Evidence
- SentimenTrader: Nasdaq positive only 41% of the time one month after a key reversal.
- A study of about 600 downward key reversals across about 1,470 stocks found no lasting trend prediction (Scribd
  "KeyReversalMyth" document).
- StoneX (18 Aug 2026): bullish key reversals in ASX 200 futures anticipated the move 2-4 sessions out (index futures,
  not US single stocks).
- Brokers publish no statistics.

## Common mistakes
Treating every bar that matches the loose rule as a signal; ignoring that N = 1 fires very often.

## Discretionary parts and how to make them mechanical
Context gate: `level_touch_pct <= 1.0` (near `support_1`) or `rsi_14 < 35`; trend gate `close > sma_200`.

## Implementation spec for swing-engine
- Existing feature `key_reversal` (`features/patterns.py`): `low < prev_low and close > prev_close and
  volume >= 1.5 * avg_vol_50d` (prior bar's average). Differences vs sources: adds a volume rule (TradeStation/tos have
  none), uses N = 1, and uses the loose close rule. Volume multiple is `KEY_REVERSAL_VOL_MULT = 1.5`.
- New optional features: `key_reversal_strict` (close > prev_high), `key_reversal_n` with N = 5 (`low < min(low[t-5..t-1])`).
- Variant A (broker built-in): signal close t, buy next open (works with the current backtester), stop `low_t - 0.01`.
- Variant B (classic): buy stop `high_t + 0.01` on t+1 (needs stop-entry hook), stop `low_t - 0.01`.
- Exit: `max_hold_days: 4`; `min_reward_risk: 0.0`; optional KeyRevLX exit (new 1-bar high and close < prev close).
- Run with/without the volume rule to measure what the engine's flag adds.

## What the router should know
Low-confidence; better as a confirmation feature for `sr_bounce` or `rsi2_meanrev` than its own strategy.

## Signs of decay to monitor
Forward 4-day return after the flag not distinguishable from the unconditional mean of the same names.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/KeyRevLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/InsideBarLE
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/key_reversal_le_signal_.htm
- https://sentimentrader.com/blog/a-chart-looks-nice-but
- https://www.stonex.com/en-gb/news-and-analysis/asx-200-futures-reversal-patterns-put-to-the-test-2026-08-18/
- https://es.scribd.com/document/341277321/KeyReversalMyth-2

## Empirical (replay)
_Pending: filled in from swing replay on real data._
