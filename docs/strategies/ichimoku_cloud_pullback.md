---
slug: ichimoku_cloud_pullback
name: Ichimoku cloud pullback (Kijun dip, Tenkan reclaim)
originators: [Goichi Hosoda (Ichimoku Kinko Hyo, published 1969), StockCharts ChartSchool pullback system]
category: setup
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: long (short mirror in source; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Ichimoku cloud pullback

## One-line summary
While price holds above the bottom of the Ichimoku cloud, wait for a dip below the Kijun (26-bar midpoint), then buy when price
crosses back above the Tenkan (9-bar midpoint); stop at the pre-signal low, trail with SAR or 2 ATR.

## Origin and lineage
Goichi Hosoda (pen name Ichimoku Sanjin) developed Ichimoku Kinko Hyo before WWII and published it in 1969. The full method
includes time-cycle counts (9/17/26) and wave/price targets, which are not covered here (catalog "unverified"). The pullback
system is StockCharts ChartSchool's mechanical reading of the lines.

## Exact rules
- Tenkan (conversion) = (max(H,9) + min(L,9))/2. Kijun (base) = (max(H,26) + min(L,26))/2.
- Senkou A = (Tenkan + Kijun)/2 plotted 26 bars ahead; Senkou B = (max(H,52) + min(L,52))/2 plotted 26 ahead.
  So the cloud visible over bar t uses values computed at t-26. Chikou = close plotted 26 bars back (confirmation only).
- Bias (long): close above the lower edge of the cloud at t, i.e. close_t > min(SpanA_{t-26}, SpanB_{t-26}).
- Setup: price declines below the Kijun (pullback).
- Trigger: price turns up and crosses back above the Tenkan.
- Initial stop: the low just before the buy signal.
- Trail: Parabolic SAR or 2 x ATR below price. Exit also when price breaks below the Tenkan or cloud support (ChartSchool).
- Volume: expanding volume on the advance preferred (not a hard rule).
- Classic signals (context, not this system): Tenkan/Kijun cross above a green cloud (SpanA > SpanB) is "strong"; chikou above the
  price of 26 bars ago confirms.
- Sizing and targets: none taught.

## Why it should work
It is a pullback-in-trend buy with a midpoint-based definition of trend and of the dip: the cloud filter keeps the trade on the
right side of the 26-52 bar trend, the Kijun dip finds short-term sellers, and the Tenkan reclaim shows they are done.
Counterparty: short-term profit-takers and late sellers in a still-intact intermediate trend.

## When it works and when it fails
Works in established uptrends with orderly 3-8 bar pullbacks. Fails when the "bias" is only marginal (price just above a thin
cloud), in chop (Tenkan/Kijun are flat and price crosses them constantly) and in fast declines where the Kijun dip becomes a
trend change.

## Parameters and sensitivity
9/26/52 are traditional (originally based on a 6-day trading week); some traders use 10/30/60 or crypto 20/60/120. Treat them as
fixed; tune only the dip-to-trigger window (max bars between Kijun dip and Tenkan reclaim, 3-10).

## Evidence
- Che-Ngoc, Do-Thi, Nguyen-Trang, "Profitability of Ichimoku-Based Trading Rule in Vietnam Stock Market in the Context of the
  COVID-19 Outbreak", Computational Economics 62(4), 2023: Ichimoku rules profitable in Vietnam; return per trade about 8-9%
  higher in the pandemic period vs pre-pandemic; slightly higher accumulated return than buy-and-hold with lower risk. Different
  market and rule set (not this pullback system).
- Practitioner backtests (e.g. liberatedstocktrader.com) report mixed results, including a very low win rate on DJ-30 stocks;
  methodology unclear, not relied on.
- A frequently cited academic test (Lim, Yanyali, Savidge) could not be verified in this pass.
- No independent test of the ChartSchool pullback system found. Grade D.

## Common mistakes
Look-ahead with the forward-plotted spans (using SpanA/SpanB computed at t for the cloud at t); using closes instead of highs/lows
for the midpoints; entering inside the cloud.

## Discretionary parts and how to make them mechanical
- "Declines below the Kijun": close_{t-k} < kijun_{t-k} for some k in [1, dip_window], default dip_window 8.
- "Crosses above the Tenkan": close_{t-1} <= tenkan_{t-1} and close_t > tenkan_t.
- "Low just before the signal": min(low) over the bars since the Kijun dip began.

## Implementation spec for swing-engine
- Features `features/ichimoku.py`: `tenkan_9`, `kijun_26`, `span_a_26` = shift((tenkan+kijun)/2, 26),
  `span_b_26` = shift((max52H+min52L)/2, 26), `cloud_low` = min(span_a_26, span_b_26), `cloud_high`, `bars_since_kijun_dip`,
  `dip_low` (min low since the dip started), `tenkan_prev`. Shift test must show no future data.
- Strategy `strategies/ichimoku_pullback.py`, registered `ichimoku_pullback`, disabled.
- Signal on close t: close_t > cloud_low_t; bars_since_kijun_dip in [1, 8]; close_{t-1} <= tenkan_{t-1} and close_t > tenkan_t.
- Entry next open; stop = dip_low - 0.1*atr_14. Target: reference `target_r` 3.0 (or prior 20-bar swing high when higher).
- Trail: engine `trailing.atr_mult` = 2.0 on atr_14 matches the ChartSchool 2-ATR option; SAR option needs psar features.
- `should_exit`: close < cloud_low (cloud support broken). max_hold_days: 30. min_reward_risk 1.5.
- Reuses `atr_14`, `avg_vol_20d` (volume check), engine ATR trail. Missing: ichimoku columns.

## What the router should know
Pullback family; overlaps pullback_trend and pullback_holy_grail. Allow in healthy_uptrend (1.0) and narrow_uptrend (0.5) for
the comparison run.

## Signs of decay to monitor
Stop-outs within 2 bars rising; trades triggered while price is inside the cloud (filter bug).

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/ichimoku-cloud-trading-strategies
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/ichimoku-cloud
- https://ideas.repec.org/a/kap/compec/v62y2023i4d10.1007_s10614-022-10319-6.html
- https://www.liberatedstocktrader.com/ichimoku-cloud/

## Empirical (replay)
_Pending: filled in from swing replay on real data._
