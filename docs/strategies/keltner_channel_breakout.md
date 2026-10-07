---
slug: keltner_channel_breakout
name: Keltner channel breakout (Keltner 10-day rule; TradeStation / TradingView built-ins)
originators: [Chester Keltner (1960), Linda Raschke (ATR version, 1980s), TradeStation, TradingView]
category: volatility_breakout
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long            # built-ins also have a short mirror (SE); swing-engine strategies are long-only
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null     # one unrefereed vendor test: ~30% on daily Dow 30 bars (see Evidence)
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built          # no module in swing_engine/strategies/, no entry in config/settings.yaml
---

# Keltner channel breakout

## One-line summary
Buy when price closes above an ATR (or average-range) envelope around a 10-20 day average, betting that a
volatility-scaled break starts a trend; a demonstration strategy with no credible evidence of edge in stocks.

## Origin and lineage
- Chester Keltner, *How to Make Money in Commodities* (1960): the "ten-day moving average rule". Centre = 10-day SMA of
  typical price (H+L+C)/3; bands = centre +/- 10-day SMA of (high - low). Buy a close above the upper line, sell a close
  below the lower line.
- Linda Raschke (1980s) popularised the modern form: 20-day EMA +/- 2 x ATR(10).
- TradeStation "Keltner Channel LE/SE" and TradingView "Keltner Channels Strategy" ship as built-in demos.
- The Keltner channel is also the outer envelope in the TTM Squeeze (see `ttm_squeeze.md`).

## Exact rules
| Element | Keltner 1960 | TradeStation LE | TradingView built-in |
|---|---|---|---|
| Centre | SMA10 of (H+L+C)/3 | SMA20(close) | EMA20(close) (defaults recalled, not confirmed) |
| Width | +/- SMA10(H-L) | +/- 1.5 x ATR(20) | +/- 2 x ATR/true range (recalled) |
| Setup | - | close crosses above upper band | close crosses above upper band |
| Entry | buy the close | buy stop at breakout bar high + 1 tick | buy stop at breakout bar high |
| Exit/stop | close below lower line (stop and reverse) | short mirror reverses; no separate stop | opposite signal reverses |

- Universe: any liquid instrument; no trend, RS or volume filter in any source.
- Targets / trailing / time exits: none in the sources; the built-ins are always-in-market stop-and-reverse systems.
- Sizing: not taught.
- Interpretive rule (StockCharts): a channel turning up plus a break above the upper line = new uptrend; in a flat
  channel the lines act as overbought/oversold. Multiplier 1 halves the width, 3 widens it by 50% vs 2.

## Why it should work
Volatility-scaled breakouts are a time-series-momentum entry: a close more than ~1.5-2 ATR above the mean is an
unusual move that may reflect new information or institutional demand. The other side is mean-reversion sellers
and short-term profit takers. In single stocks short-horizon reversal (1 week to 1 month) is the academic default,
so the edge, if any, depends on filtering for trending names.

## When it works and when it fails
- Works: persistent trends (commodities in the 1970s; leaders in a healthy uptrend).
- Fails: ranges and choppy tapes, where upper-band closes are near-term highs and reverse (whipsaw). Stop-and-reverse
  versions bleed in sideways markets.

## Parameters and sensitivity
- Length 10-20, multiplier 1.0-2.5, basis SMA vs EMA, width ATR vs average (H-L). Small changes swing results a lot
  (vendor test below: 5 settings, best and worst far apart). Trap: picking the best (length, mult) per symbol.

## Evidence
- No broker or platform performance data (documentation only).
- LiberatedStockTrader (vendor, unrefereed): 30 Dow stocks, 5 settings, 1-min to daily bars; average win rate 28%,
  daily ~30%; most stocks underperformed buy-and-hold. Methodology thinly documented.
- QuantConnect community reports: one 15.2% CAGR / Sharpe 0.9 run selected the top-10 Russell 1000 names by an
  in-sample profit-factor filter (selection bias); another similar run Sharpe -0.1. Not evidence.
- No academic study of the Keltner rule on US equities located.

## Common mistakes
- Treating an upper-band touch as a buy in a flat channel (Keltner himself saw it as overbought there).
- Running stop-and-reverse in stocks (shorts carry borrow, squeeze risk; the engine is long-only).

## Discretionary parts and how to make them mechanical
- "Channel turning up": `kc_mid_t > kc_mid_{t-5}`.
- Trend context: require `trend_state >= 1`.

## Implementation spec for swing-engine
- Features (new, `features/indicators.py` or a `features/channels.py`):
  - `kc_mid_20 = sma_20` (TradeStation) ; `atr_20` = simple mean of true range over 20 bars (TradeStation's
    AvgTrueRange); `kc_upper_20 = kc_mid_20 + KC_MULT * atr_20`, `kc_lower_20 = kc_mid_20 - KC_MULT * atr_20`,
    `KC_MULT = 1.5` versioned constant. Keltner-1960 variant: `kc1960_mid = sma(typical,10)`, width `sma(high-low,10)`.
- Setup at close t: `close_t > kc_upper_t and close_{t-1} <= kc_upper_{t-1}`.
- Entry: buy stop at `high_t + 0.01` valid for 1 session. **Missing hook**: the backtester fills all entries at the next
  open (`research/backtest.py` step 1). Needs a stop-entry mode: fill if `high_{t+1} >= trigger` at
  `max(open_{t+1}, trigger)`; else cancel.
- Stop: `kc_mid_t` (centre line) or `low_t - 0.01`, whichever is higher; exit rule `close < kc_mid` (long-only stand-in
  for the reversal).
- Target: none (rule exit); set `min_reward_risk: 0.0` like `rsi2_meanrev`. `max_hold_days: 20`.
- Reuses: `sma_20`, `trend_state`, `atr_14` (not identical to ATR(20) simple; do not substitute silently).

## What the router should know
Comparison baseline only. Only in `healthy_uptrend` if ever enabled; never in `choppy` (whipsaw regime).

## Signs of decay to monitor
Win rate below ~30% with average win/loss below 2.5; time-in-trade shrinking to 1-3 bars (immediate failures).

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/keltner_channel_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/keltner_channel_se_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://ru.tradingview.com/support/solutions/43000599890
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/keltner-channels
- https://www.liberatedstocktrader.com/keltner-channels-indicator/ (vendor test)
- https://quantconnect.com/reports/807982778d5b44c72b464dc6dd0c0b4d (community report)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
