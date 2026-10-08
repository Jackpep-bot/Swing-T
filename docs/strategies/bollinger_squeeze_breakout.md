---
slug: bollinger_squeeze_breakout
name: Bollinger Squeeze breakout (Bollinger Method I / Method IV)
originators: [John Bollinger]
category: volatility_breakout
decision: implement_disabled_for_comparison
holding_period_days: [5, 20]
timeframe: daily
direction: long            # Bollinger teaches both sides; swing-engine strategies are long-only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built          # bb_width_20 exists; no strategy module or settings entry
---

# Bollinger Squeeze breakout

## One-line summary
After Bollinger BandWidth falls to a six-month low (volatility contraction), go with the first close outside the band
(Method I) or two consecutive closes outside it (Method IV), expecting a volatility expansion in that direction.

## Origin and lineage
John Bollinger, *Bollinger on Bollinger Bands* (2001): Method I = "volatility breakout" after a Squeeze. Method IV
(confirmed breakout, consecutive closes plus ADX) appears in later TradeStation material on bollingerbands.com.
StockCharts ChartSchool and Webull Learn repeat it. The TTM Squeeze (`ttm_squeeze.md`) is a descendant that defines
the squeeze as BB inside KC.

## Exact rules
- Bands: mid = SMA20(close); upper/lower = mid +/- 2 x stdev20(close) (population stdev per Bollinger).
- BandWidth = (upper - lower) / mid (StockCharts multiplies by 100).
- Squeeze: BandWidth at or near the lowest of the last ~6 months (126 bars). Scan proxy used by practitioners:
  (upper - lower)/close < 0.04.
- Direction bias inside the squeeze: rising OBV / A-D / positive CMF / Intraday Intensity / MFI favours an upside break.
- Trigger, Method I: close above the upper band. Method IV: consecutive (2) closes above the upper band after a squeeze,
  and ADX used to judge whether a trend is under way (threshold not stated in the material read).
- Entry: at the close or next open (Webull variant: buy stop above the upper band).
- Stop: Parabolic SAR, or failure back inside the bands / below the mid band (practitioner).
- Target: none; exit when the trend fades (SAR hit, close back below mid band). Bollinger notes the opposite band
  often reverses at the start of a big move, a sign the move is real.
- Head fake: the first band break often reverses; Bollinger suggests waiting for the reversal and trading the second
  move, or using volume indicators to pick direction.
- Sizing: not taught.

## Why it should work
Volatility clusters and mean-reverts: very low realised vol is followed by higher vol on average (a robust stylised
fact). The open question is direction. The squeeze only says "a move is coming"; direction comes from the trend and
accumulation, i.e. who has been buying quietly during the contraction.

## When it works and when it fails
- Works: quiet bases in uptrending names where the break aligns with the trend and volume.
- Fails: choppy markets (head fakes), event-driven breaks (earnings gaps) that reverse, and low-vol regimes where
  BandWidth stays compressed for months.

## Parameters and sensitivity
- BB length 20 / 2 SD (keep fixed); squeeze lookback 100-150 bars; percentile threshold 5-10%; Method I vs IV.
- Trap: tuning the BandWidth threshold per symbol; testing many volume confirmers and keeping the best.

## Evidence
- Lento, Gradojevic & Wright (2007, *Applied Financial Economics Letters* 3(4)): Bollinger Band rules did not beat
  buy-and-hold after transaction costs; contrarian versions did better. This tested band-touch rules, not the squeeze.
- CXO Advisory (14 Jan 2010): SPY 1993-2010, BB(20,2) inside KC(20, 1.5 x avg range), 86 spaced breakout events; the
  3-day breakout direction had correlation -0.11 with the next 18-day trend (R^2 0.01). No directional edge.
- An unrefereed forum study (399 squeezes, 50 S&P 500 stocks, 2023-2026) reported 49.6% unfiltered direction
  accuracy; not verified.
- No independent test of Method I/IV with stops and costs on US stocks located.

## Common mistakes
- Treating the squeeze as directional. Buying the first break without trend context (head fake).
- Using sample stdev vs population stdev inconsistently across tools (small numeric drift).

## Discretionary parts and how to make them mechanical
- "Near six-month low": `bbw_pctile_126 <= 0.10`, evaluated on any of the prior 5 bars (squeeze then release).
- Volume bias: `obv_slope_20 > 0` or `cmf_20 > 0` (new features), one confirmer fixed in advance.
- "Trend fades": close < `sma_20` (the mid band).

## Implementation spec for swing-engine
- Features: reuse `bb_upper_20`, `bb_lower_20`, `bb_width_20` (indicators.py: population std, width = (U-L)/mid).
  Add `bbw_pctile_126` = rolling percentile rank of `bb_width_20` within the trailing 126 bars (inclusive of t).
  Optional `cmf_20` = sum(((C-L)-(H-C))/(H-L) x V, 20) / sum(V, 20).
- Setup: `min(bbw_pctile_126[t-5..t-1]) <= SQUEEZE_PCTILE (0.10)`.
- Trigger Method I: `close_t > bb_upper_20_t`; Method IV: also `close_{t-1} > bb_upper_20_{t-1}` and
  `adx_14_t >= ADX_MIN` (param, start 20; Bollinger's value unverified).
- Entry: next open (fits the current backtester). Stop: `max(sma_20_t, low_t - 0.01)` capped at 2 x `atr_14` below
  entry. Exit rule: `close < sma_20`. Target: none -> `min_reward_risk: 0.0`. `max_hold_days: 20`.
- Filters: `trend_state >= 1` (variant flag to test with and without).
- Reuses: bb_*_20, sma_20, atr_14, adx_14 (patterns2), trend_state.

## What the router should know
Comparison strategy. Only `healthy_uptrend` / `narrow_uptrend`. In low SPY vol regimes squeeze counts explode; cap
signals per day by score (lowest BandWidth percentile first).

## Signs of decay to monitor
Breakout-direction hit rate near 50%; share of trades stopped within 3 bars (head fakes) rising above ~50%.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/bollinger-band-squeeze
- https://www.bollingerbands.com/tradestation-methods
- https://ideas.repec.org/a/taf/raflxx/v3y2007i4p263-267.html
- https://www.webullapp.com/learn/courseware/l5VtDs/Swing-Trade-with-Bollinger-Bands?courseId=553Fb2
- https://www.cxoadvisory.com/volatility-effects/testing-a-complex-breakout-indicator/

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 877 | 43 | 33% | +0.18 | +0.03 | 29% | +0.27 | +0.13 | 23% | +0.37 | +0.23 | 1.45 |
| correction | 51 | 1 | 26% | -0.32 | -0.43 | 18% | -0.25 | -0.35 | 14% | -0.26 | -0.36 | 0.69 |
| healthy_uptrend | 5409 | 272 | 32% | -0.12 | -0.29 | 25% | -0.13 | -0.30 | 21% | +0.10 | -0.08 | 1.10 |
| high_vol_selloff | 246 | 12 | 36% | +0.05 | -0.09 | 33% | +0.14 | -0.00 | 15% | -0.41 | -0.55 | 0.63 |
| narrow_uptrend | 335 | 13 | 29% | -0.08 | -0.22 | 23% | -0.27 | -0.42 | 13% | -0.40 | -0.54 | 0.64 |
| **all** | 6918 | 341 | 33% | -0.07 | -0.24 | 26% | -0.08 | -0.24 | 20% | +0.09 | -0.08 | 1.09 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3051 | 127 | 38% | +0.04 | -0.11 | 33% | +0.14 | -0.01 | 27% | +0.42 | +0.27 | 1.46 |
| correction | 1257 | 61 | 32% | -0.22 | -0.35 | 26% | -0.25 | -0.37 | 20% | -0.15 | -0.28 | 0.83 |
| healthy_uptrend | 21679 | 937 | 34% | -0.05 | -0.21 | 27% | -0.07 | -0.22 | 20% | -0.09 | -0.24 | 0.91 |
| high_vol_selloff | 960 | 46 | 36% | -0.02 | -0.14 | 28% | -0.11 | -0.23 | 21% | +0.00 | -0.12 | 1.00 |
| narrow_uptrend | 3373 | 143 | 37% | +0.08 | -0.06 | 31% | +0.11 | -0.03 | 25% | +0.18 | +0.03 | 1.20 |
| **all** | 30320 | 1314 | 35% | -0.04 | -0.19 | 28% | -0.03 | -0.18 | 21% | -0.01 | -0.16 | 0.99 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
