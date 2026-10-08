---
slug: katsanos_rsmk
name: RSMK relative-strength strategy (Katsanos)
originators: [Markos Katsanos (S&C Mar 2020), thinkorswim RSMK study + RSMKStrat]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [10, 60]    # fixed-bar time exit; TOS default bar count not published
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# RSMK (Katsanos)

## One-line summary
Buy when a stock's smoothed 90-day log relative strength versus the index crosses above zero (it starts outperforming),
hold a fixed number of bars.

## Origin and lineage
Markos Katsanos, "Using Relative Strength To Outperform The Market", S&C Mar 2020; thinkorswim RSMK study and RSMKStrat.

## Exact rules
- RSMK = EMA( ln(C/B) - ln(C[n]/B[n]), m ), with C the stock close, B the benchmark close, n = 90, m = 3 (Traders' Tips
  code defaults via search snippet; benchmark SPY). The 90-bar lookback is also the TOS documented default. Some ports
  multiply by 100 (scale only; zero crossing unchanged).
- Entry: RSMK crosses above 0. Next-open fill.
- Exit: after a fixed number of bars (`time exit length`; default not published on TOS; unverified).
- The article's full system may contain extra filters (e.g. market trend); not retrievable (traders.com 403). Unverified.

## Why it should work
Cross-sectional momentum / relative strength persistence (Jegadeesh-Titman): stocks starting to outperform tend to keep
doing so for weeks to months as information diffuses and institutions rotate. The other side: benchmark-hugging and value sellers.

## When it works and when it fails
Rotational bull markets with stable leadership. Fails at momentum crashes (sharp rebounds led by losers, e.g. Apr 2009,
Nov 2020, Apr 2025) and when the stock outperforms only by falling less in a down market.

## Parameters and sensitivity
n 20-126, m 3-10, hold 10-63 bars. A zero cross of a 90-day difference fires often in flat names; add a minimum slope or
trend filter only as a declared variant.

## Evidence
In-sample S&C illustration only (grade D). The underlying idea (relative strength) is well documented academically
(Jegadeesh & Titman 1993 and follow-ups), but this specific 90/3 zero-cross with a fixed hold has no independent test found.

## Common mistakes
Using price-only benchmark vs total-return stock (dividends bias); not requiring the stock itself to be in an uptrend.

## Discretionary parts and how to make them mechanical
Benchmark choice -> SPY by default; sector ETF as a variant param.

## Implementation spec for swing-engine
- Module `strategies/rsmk.py`, `@register("strategy")`; feature `rsmk_90_3` computed with the `market` frame
  (catalog maps_to: `relative_strength_line`). Align on session dates; NaN where the benchmark is missing.
- Signal: rsmk[t] > 0 and rsmk[t-1] <= 0; optional `require_trend_state: 1`. Entry next open.
- Stop: entry - 2.5 x atr_14 (engine-required). Target: None. Time exit: `max_hold_days` = 20 (engine assumption until the
  article default is confirmed).
- Reuses rs_63d_rank (related cross-sectional RS), trend_state, atr_14.
- settings.yaml: `rsmk: {enabled: false, shadow_only: true, rs_length: 90, ema_length: 3, max_hold_days: 20}`.

## What the router should know
Relative-strength trigger; overlaps with any strategy that ranks on rs_63d_rank. Most informative as a feature.

## Signs of decay to monitor
Zero-cross frequency per symbol rising (whipsaw); hit rate in down markets.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RSMKStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/RSMK
- https://www.traders.com/Documentation/FEEDbk_docs/2020/03/TradersTips.html

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1709 | 2 | 52% | +0.02 | -0.07 | 49% | +0.01 | -0.08 | 50% | +0.12 | +0.02 | 1.28 |
| correction | 241 | 0 | 67% | +0.21 | +0.02 | 77% | +0.40 | +0.20 | 72% | +0.64 | +0.44 | 4.82 |
| healthy_uptrend | 4628 | 9 | 50% | +0.02 | -0.06 | 49% | +0.04 | -0.05 | 45% | +0.08 | -0.00 | 1.18 |
| high_vol_selloff | 1210 | 2 | 52% | -0.01 | -0.13 | 52% | +0.03 | -0.09 | 42% | -0.09 | -0.21 | 0.82 |
| narrow_uptrend | 630 | 0 | 35% | -0.15 | -0.24 | 35% | -0.24 | -0.33 | 29% | -0.33 | -0.42 | 0.49 |
| **all** | 8418 | 13 | 50% | +0.01 | -0.08 | 50% | +0.03 | -0.07 | 46% | +0.06 | -0.03 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4679 | 3 | 53% | +0.04 | -0.04 | 53% | +0.09 | +0.01 | 51% | +0.19 | +0.11 | 1.46 |
| correction | 3409 | 2 | 59% | +0.10 | +0.02 | 58% | +0.15 | +0.07 | 53% | +0.19 | +0.11 | 1.51 |
| healthy_uptrend | 16551 | 31 | 50% | +0.01 | -0.08 | 48% | +0.01 | -0.08 | 44% | +0.01 | -0.08 | 1.02 |
| high_vol_selloff | 5735 | 9 | 48% | -0.05 | -0.14 | 48% | -0.05 | -0.14 | 47% | +0.01 | -0.08 | 1.03 |
| narrow_uptrend | 4006 | 6 | 51% | +0.02 | -0.07 | 49% | +0.05 | -0.04 | 48% | +0.10 | +0.01 | 1.22 |
| **all** | 34380 | 51 | 51% | +0.02 | -0.07 | 50% | +0.03 | -0.06 | 47% | +0.06 | -0.02 | 1.14 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
