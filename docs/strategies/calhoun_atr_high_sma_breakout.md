---
slug: calhoun_atr_high_sma_breakout
name: ATR High / SMA breakouts (Ken Calhoun)
originators: [Ken Calhoun]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# ATR High / SMA Breakouts (Calhoun)

## One-line summary
Volatility-expansion breakout: when ATR is at its 14-bar high and price is above its 100-day SMA, buy on a stop a
fixed offset above that bar's high.

## Origin and lineage
Ken Calhoun, "ATR Breakout Entries", *Technical Analysis of Stocks & Commodities*, May 2016 (catalog). thinkorswim
`ATRHighSMABreakoutsFilter` (Stock Hacker scan) and `ATRHighSMABreakoutsLE` (entry only). Follows his ADX Breakouts.

## Exact rules (thinkorswim description, defaults verified this run)
- Universe filter: price $15-$70, 90-day range >= $5, daily volume >= 1,000,000 (catalog).
- Trigger: ATR(`length` 14) at its highest over the lookback (14 bars per catalog) and close > SMA(close, 100).
- Entry: buy stop at the trigger bar's high + `offset` ($0.50).
- Optional filters (off by default): wide-range candle (trigger bar's range >= 1.5x the average range) and volume
  increase (volume > prior bar's volume).
- Exits: not part of the entry strategy.

## Why it should work
Range expansion in an uptrend marks new information or institutional demand; the buy stop requires follow-through.
Caveat: ATR at a 14-bar high also happens on large down bars, so the SMA filter is doing most of the directional work.

## When it works and when it fails
Works at the start of trending legs (expansion after contraction). Fails on climactic or news-driven bars that
reverse, and in high-volatility markets where ATR highs are everywhere.

## Parameters and sensitivity
ATR length 10-20; ATR-high lookback 10-20; SMA 50-200; offset 0.1-0.25 x `atr_14`; turn on both optional filters as
a second variant. Convert $15-$70 / $5 / 1M-share rules to the engine universe and a % range filter (90-day range
>= 20% of close, engine choice).

## Evidence
Practitioner in-sample (grade D); no broker statistics; no independent test located. Catalog note: worth one replay
against `breakout_52w`.

## Common mistakes
Triggering on down bars (add close > open or close_pos >= 0.5); dollar thresholds across price levels.

## Discretionary parts
Exit unspecified; use engine defaults.

## Implementation spec for swing-engine
- Features: `atr_14` exists; new `atr_high_14` = `atr_14 >= rolling max(atr_14, 14)`; new `sma_100` (only 10/20/50/200
  exist today); `range_pct`, `close_pos`, `rvol_day` exist; `wide_range` = (high - low) >= 1.5 x mean(high - low, 20)
  (averaging window not stated by tos; 20 is an engine choice).
- Signal: `atr_high_14` and close > `sma_100` and `close_pos >= 0.5`; variant B adds `wide_range` and volume >
  prior volume.
- Entry: buy stop at high + 0.15 x `atr_14`, valid 2 sessions. Stop = entry - 2 x `atr_14` (or trigger bar low,
  whichever is closer, min 1 ATR). Target 2R; `max_hold_days: 15`; `min_reward_risk: 2.0`.
- Missing: `sma_100`, `atr_high_14`, stop-entry hook.

## What the router should know
Breakout family; healthy_uptrend only; avoid when `market_vol_regime` = 2.

## Signs of decay to monitor
Same-day reversal rate of filled buy stops; mean R by `vol_regime`.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ATRHighSMABreakoutsLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/A-B/ATRHighSMABreakoutsFilter

## Empirical (replay)
_Pending: filled in from swing replay on real data._
