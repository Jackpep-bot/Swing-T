---
slug: rsi_trend_zigzag_luo
name: "RSITrend (Kevin Luo): RSI cross only in a ZigZag-confirmed trend"
originators: [Kevin Luo ("The RSI & Price Trends", S&C Jun 2015), thinkorswim RSITrend]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]     # estimate; original has no explicit long exit beyond the opposite signal
timeframe: daily
direction: long_only_in_engine (original long and short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# RSITrend (Luo)

## One-line summary
Take the classic RSI oversold cross only when a ZigZag-percent trend reading says a strong uptrend is in place.

## Origin and lineage
Kevin Luo, S&C Jun 2015; thinkorswim RSITrend uses its ZigZagTrendPercent study as the trend filter. It is the
`rsi_30_70` variant of `oscillator_cross_family` plus a trend gate.

## Exact rules (TOS)
- Inputs: RSI length, overbought, oversold, `percentage reversal` (ZigZag threshold), MA type. Defaults not given on the
  page text in the catalog (RSI(14) 30/70 assumed; unverified).
- Long: RSI crosses above oversold while ZigZagTrendPercent indicates a strong uptrend. Short: RSI crosses below
  overbought in a strong downtrend (not used).
- Exit: the TOS page describes only entry signals; exit is presumably the opposite signal (unverified).

## Why it should work
A pullback to oversold inside a confirmed uptrend is a buy-the-dip trade; the trend filter removes oversold crosses in
downtrends, the main failure of the unfiltered rule.

## When it works and when it fails
Orderly uptrends with periodic pullbacks. Fails when the trend breaks during the pullback; ZigZag confirmation lags by the
full reversal percentage.

## Parameters and sensitivity
ZigZag reversal 3-10%, RSI 7-14, oversold 25-40. A daily RSI(14) under 30 is rare in a strong uptrend, so trade count
can be tiny; that is the main trap (results on a handful of trades).

## Evidence
In-sample S&C illustration only (grade D). No independent test found.

## Common mistakes
**ZigZag repaints**: its last leg is revised as new bars arrive. Any backtest that reads the plotted ZigZag is look-ahead.
Use only confirmed swing points (catalog note).

## Discretionary parts and how to make them mechanical
"Strong uptrend" -> last two confirmed swing highs and lows are both higher (HH + HL), with swings confirmed only after
price reverses by `pct` from the extreme.

## Implementation spec for swing-engine
- Module `strategies/rsi_trend.py`, `@register("strategy")`; new feature `zz_trend_{pct}` from a non-repainting
  swing labeller (catalog maps_to `swing_point_labeling`): a swing high is confirmed on the bar where close falls
  `pct`% below the running max since the last confirmed low (and mirror); trend = +1 if last confirmed high > previous
  confirmed high and last confirmed low > previous confirmed low.
- Reuses rsi_14, atr_14, trend_state (as a sanity check), pivot logic in features/levels.py (different: fixed width).
- Signal at close t: zz_trend = +1 and rsi_14 crosses above 30. Entry next open.
- Stop: min(last confirmed swing low, entry - 1.5 x atr_14) below entry. Target: prior confirmed swing high if above entry
  (then `min_reward_risk` 1.5), else None. `should_exit`: rsi_14 crosses below 70 or zz_trend != +1. `max_hold_days`: 30.
- settings.yaml: `rsi_trend: {enabled: false, shadow_only: true, zz_pct: 5, rsi_os: 30, rsi_ob: 70}`.

## What the router should know
Low-frequency dip-buy in uptrends; compare against `pullback_trend` and `rsi2_meanrev` which cover the same idea with
more trades.

## Signs of decay to monitor
Fewer than ~30 trades per year across the universe makes the replay uninformative.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RSITrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/V-Z/ZigZagTrendPercent

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 272 | 0 | 46% | -0.09 | -0.19 | 40% | -0.15 | -0.26 | 42% | +0.05 | -0.05 | 1.09 |
| correction | 119 | 0 | 43% | -0.02 | -0.17 | 66% | +0.46 | +0.32 | 71% | +1.12 | +0.98 | 5.97 |
| healthy_uptrend | 679 | 2 | 50% | +0.04 | -0.07 | 44% | +0.03 | -0.08 | 36% | -0.06 | -0.17 | 0.90 |
| high_vol_selloff | 355 | 0 | 69% | +0.35 | +0.23 | 64% | +0.49 | +0.37 | 38% | +0.03 | -0.09 | 1.06 |
| narrow_uptrend | 230 | 0 | 38% | -0.16 | -0.26 | 30% | -0.32 | -0.42 | 23% | -0.31 | -0.41 | 0.57 |
| **all** | 1655 | 2 | 51% | +0.06 | -0.05 | 48% | +0.10 | -0.01 | 39% | +0.05 | -0.07 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 40 trades, win 45%, avg -0.03R, PF 0.94, P&L $-1,889 on $100k, avg hold 7.4 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1459 | 9 | 53% | +0.10 | -0.01 | 54% | +0.22 | +0.11 | 49% | +0.36 | +0.25 | 1.74 |
| correction | 507 | 3 | 58% | +0.27 | +0.16 | 50% | +0.24 | +0.13 | 44% | +0.48 | +0.37 | 1.97 |
| healthy_uptrend | 2170 | 6 | 46% | -0.04 | -0.16 | 42% | -0.03 | -0.15 | 37% | -0.04 | -0.16 | 0.94 |
| high_vol_selloff | 2016 | 10 | 45% | -0.09 | -0.19 | 42% | -0.03 | -0.13 | 39% | +0.01 | -0.09 | 1.02 |
| narrow_uptrend | 834 | 2 | 49% | -0.02 | -0.14 | 44% | -0.05 | -0.16 | 38% | -0.05 | -0.16 | 0.93 |
| **all** | 6986 | 30 | 48% | +0.00 | -0.11 | 45% | +0.04 | -0.07 | 41% | +0.10 | -0.02 | 1.17 |

Portfolio replay (net of costs, slots shared with its run): 126 trades, win 50%, avg -0.11R, PF 0.79, P&L $-7,590 on $100k, avg hold 6.3 bars.
