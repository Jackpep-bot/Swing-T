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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1712 | 22 | 52% | +0.02 | -0.07 | -0.14 | 49% | +0.01 | -0.08 | -0.15 | 50% | +0.10 | +0.01 | -0.23 | 1.25 |
| correction | 243 | 4 | 68% | +0.23 | +0.03 | -0.02 | 78% | +0.41 | +0.21 | -0.19 | 73% | +0.65 | +0.45 | -0.44 | 5.20 |
| healthy_uptrend | 4635 | 42 | 50% | +0.02 | -0.06 | -0.08 | 49% | +0.04 | -0.05 | -0.07 | 45% | +0.09 | +0.00 | -0.07 | 1.19 |
| high_vol_selloff | 1202 | 30 | 52% | -0.01 | -0.13 | -0.02 | 53% | +0.02 | -0.09 | -0.13 | 42% | -0.09 | -0.21 | -0.05 | 0.81 |
| narrow_uptrend | 625 | 1 | 35% | -0.15 | -0.23 | -0.22 | 36% | -0.23 | -0.32 | -0.32 | 29% | -0.32 | -0.41 | -0.48 | 0.50 |
| **all** | 8417 | 99 | 50% | +0.01 | -0.08 | -0.09 | 50% | +0.03 | -0.07 | -0.12 | 46% | +0.06 | -0.03 | -0.13 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4844 | 46 | 54% | +0.05 | -0.04 | -0.11 | 53% | +0.10 | +0.01 | -0.13 | 52% | +0.18 | +0.10 | -0.13 | 1.47 |
| correction | 3410 | 30 | 59% | +0.10 | +0.02 | -0.09 | 58% | +0.15 | +0.06 | -0.09 | 53% | +0.18 | +0.09 | -0.08 | 1.48 |
| healthy_uptrend | 17162 | 201 | 50% | +0.00 | -0.08 | -0.10 | 48% | -0.00 | -0.09 | -0.12 | 44% | -0.01 | -0.10 | -0.18 | 0.97 |
| high_vol_selloff | 5858 | 57 | 48% | -0.05 | -0.14 | -0.11 | 49% | -0.05 | -0.14 | -0.13 | 47% | +0.02 | -0.07 | -0.12 | 1.04 |
| narrow_uptrend | 4037 | 41 | 52% | +0.03 | -0.06 | -0.13 | 49% | +0.06 | -0.03 | -0.13 | 50% | +0.12 | +0.03 | -0.11 | 1.30 |
| **all** | 35311 | 375 | 51% | +0.01 | -0.07 | -0.10 | 50% | +0.02 | -0.06 | -0.12 | 47% | +0.05 | -0.03 | -0.14 | 1.12 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
