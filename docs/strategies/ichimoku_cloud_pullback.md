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
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3973 | 16 | 54% | +0.10 | -0.05 | 52% | +0.15 | +0.01 | 47% | +0.25 | +0.10 | 1.51 |
| correction | 296 | 3 | 37% | -0.16 | -0.36 | 47% | +0.03 | -0.18 | 41% | +0.25 | +0.05 | 1.50 |
| healthy_uptrend | 14412 | 76 | 49% | +0.04 | -0.11 | 44% | +0.02 | -0.12 | 38% | +0.03 | -0.12 | 1.04 |
| high_vol_selloff | 2225 | 14 | 55% | +0.11 | -0.04 | 50% | +0.10 | -0.04 | 37% | -0.04 | -0.19 | 0.93 |
| narrow_uptrend | 1792 | 17 | 37% | -0.16 | -0.31 | 33% | -0.24 | -0.39 | 25% | -0.25 | -0.41 | 0.65 |
| **all** | 22698 | 126 | 49% | +0.04 | -0.11 | 46% | +0.03 | -0.11 | 39% | +0.04 | -0.10 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 9 trades, win 78%, avg +0.29R, PF 2.07, P&L $202 on $100k, avg hold 21.4 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 13639 | 51 | 54% | +0.11 | -0.01 | 53% | +0.20 | +0.07 | 49% | +0.30 | +0.18 | 1.65 |
| correction | 6728 | 12 | 54% | +0.08 | -0.04 | 50% | +0.12 | +0.01 | 44% | +0.15 | +0.03 | 1.29 |
| healthy_uptrend | 42517 | 182 | 48% | +0.00 | -0.14 | 44% | +0.03 | -0.11 | 39% | +0.05 | -0.09 | 1.09 |
| high_vol_selloff | 10652 | 46 | 48% | -0.02 | -0.14 | 48% | +0.01 | -0.11 | 42% | +0.00 | -0.12 | 1.01 |
| narrow_uptrend | 10517 | 29 | 51% | +0.05 | -0.08 | 47% | +0.06 | -0.08 | 43% | +0.12 | -0.01 | 1.23 |
| **all** | 84053 | 320 | 50% | +0.03 | -0.10 | 47% | +0.07 | -0.07 | 42% | +0.10 | -0.03 | 1.19 |

Portfolio replay (net of costs, slots shared with its run): 29 trades, win 34%, avg -0.01R, PF 0.98, P&L $931 on $100k, avg hold 15.1 bars.
