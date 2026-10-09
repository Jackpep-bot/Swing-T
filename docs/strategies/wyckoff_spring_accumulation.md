---
slug: wyckoff_spring_accumulation
name: "Wyckoff accumulation: spring / test / SOS / LPS entries"
originators: [Richard D. Wyckoff (1910s-1930s), as taught by Wyckoff Analytics / StockCharts ChartSchool]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [10, 90]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Wyckoff accumulation: spring / test / SOS / LPS

## One-line summary
After a decline stops and a trading range forms, buy a successful spring (false break below the range low that closes
back inside) on its low-volume retest, or buy the last point of support after a sign-of-strength breakout.

## Origin and lineage
Richard Wyckoff's method (composite operator, cause and effect, supply and demand), formalised into schematics by later
teachers (Pruden; Wyckoff Analytics: Evans/Hutson/Weis lineage). StockCharts ChartSchool tutorial is the catalog source.

## Exact rules (as taught, catalog C26)
- Events: PS (preliminary support), SC (selling climax: wide spread, heavy volume, close off the low), AR (automatic
  rally; its high = top of trading range, TR), ST (secondary test near SC on lower volume/spread), spring (break below TR
  low, close back inside), test (retest of spring low on low volume), SOS (advance on widening spread and higher
  volume), LPS (pullback on low spread/volume holding former resistance), BU (back-up).
- Phases A (stop) -> B (cause) -> C (spring/test) -> D (SOS/LPS) -> E (markup).
- Entries: successful spring test (Phase C) or LPS/BU after an SOS (Phase D).
- Stop: below the spring low, or below the LPS. Target: point-and-figure count; exit on distribution signs.
- Nine buying tests include upside potential at least 3x initial risk, higher highs/lows, stock stronger than the market.

## Why it should work
Stop-run below an obvious range low triggers sell stops; if larger buyers absorb that supply (close back inside, low
volume on the retest) the remaining float is in stronger hands. Counterparty: stopped-out longs and breakout shorts.

## When it works and when it fails
Works after a completed decline with market support. Fails when the "spring" is the start of a markdown (no close
back inside next bars), in index downtrends, and when the TR is mis-identified (most schematic fits are hindsight).

## Parameters and sensitivity
TR window (40-120 bars), spring depth limit (e.g. <= 1 ATR below TR low), test volume ratio (< 1.0 x 20d average),
SOS volume (> 1.5x). Trap: the schematic has many labels; letting the code search over all of them is a garden of forking paths.

## Evidence
No independent quantitative test located (catalog C26, grade D). Related: failed-breakdown reversals (Turtle Soup,
methods.md, grade D, regime-dependent).

## Common mistakes
Labelling phases after the fact; buying the spring bar itself before the test; ignoring the index; no P&F or measured target.

## Discretionary parts and how to make them mechanical (catalog approximation)
- TR box: `tr_low = min(low, N)`, `tr_high = max(high, N)` over the prior N = 60 bars (shifted one bar), require
  `(tr_high - tr_low)/close <= 0.35` and a prior decline `ret_126d < -0.15` measured at TR start.
- Spring: `low < tr_low` and `close > tr_low` (within the last 10 bars).
- Test: a later bar with `low >= spring_low` and `volume < avg_vol_20d`, close in upper half (`close_pos >= 0.5`).
- SOS: `close > tr_high` with `rvol_day >= 1.5`. LPS: pullback after SOS with `low >= tr_high * 0.98` on volume < average.

## Implementation spec for swing-engine
- Reuses: `avg_vol_20d`, `rvol_day`, `close_pos`, `atr_14`, `ret_126d`, `support_1`/`resistance_1` (as a cross-check
  of the box), `market_trend_state`.
- Two signal types (log separately): `spring_test` (entry next open; stop `spring_low - 0.25 * atr_14`;
  target `tr_high + (tr_high - tr_low)` as a measured-move proxy for the P&F count) and `lps` (stop `min(low of the
  pullback) - 0.25 * atr_14`; target `tr_high + 2 * (tr_high - tr_low)`).
- Exit: target, stop, or close < `sma_50` after markup; `max_hold_days = 60`. `min_reward_risk = 3.0` (the nine tests' 3x).
- Missing: P&F count module; the TR detector itself (new feature in `features/patterns2.py`).

## What the router should know
Base-pattern family: spring entries allowed in choppy; LPS entries act like a breakout (healthy_uptrend only).

## Signs of decay to monitor
Spring-test stop-out rate > 60%; median MFE < 1R.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 115 | 2 | 38% | -0.11 | -0.32 | 37% | +0.04 | -0.16 | 27% | +0.06 | -0.14 | 1.07 |
| correction | 7 | 0 | 43% | +0.04 | -0.20 | 29% | +0.02 | -0.22 | 29% | +0.01 | -0.23 | 1.02 |
| healthy_uptrend | 632 | 12 | 38% | -0.03 | -0.28 | 33% | -0.09 | -0.34 | 26% | -0.07 | -0.32 | 0.92 |
| high_vol_selloff | 74 | 2 | 33% | -0.28 | -0.51 | 33% | -0.19 | -0.42 | 18% | -0.51 | -0.73 | 0.37 |
| narrow_uptrend | 70 | 0 | 50% | +0.01 | -0.20 | 42% | +0.16 | -0.06 | 45% | +0.66 | +0.44 | 2.16 |
| **all** | 898 | 16 | 39% | -0.06 | -0.29 | 34% | -0.06 | -0.30 | 27% | -0.03 | -0.27 | 0.96 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 780 | 14 | 47% | +0.08 | -0.13 | 43% | +0.26 | +0.06 | 38% | +0.42 | +0.21 | 1.65 |
| correction | 478 | 17 | 51% | +0.23 | +0.01 | 43% | +0.30 | +0.08 | 38% | +0.44 | +0.22 | 1.65 |
| healthy_uptrend | 1837 | 40 | 36% | +0.00 | -0.28 | 30% | -0.02 | -0.31 | 22% | -0.13 | -0.42 | 0.84 |
| high_vol_selloff | 682 | 10 | 43% | -0.02 | -0.20 | 43% | +0.03 | -0.15 | 34% | -0.04 | -0.22 | 0.95 |
| narrow_uptrend | 333 | 1 | 44% | +0.08 | -0.15 | 35% | +0.02 | -0.22 | 30% | +0.12 | -0.11 | 1.18 |
| **all** | 4110 | 82 | 42% | +0.04 | -0.20 | 37% | +0.08 | -0.16 | 30% | +0.07 | -0.17 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
