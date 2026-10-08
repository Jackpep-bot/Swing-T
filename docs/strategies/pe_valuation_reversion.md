---
slug: pe_valuation_reversion
name: P/E undervalued / overvalued vs its own average (TradeStation)
originators: [TradeStation built-in strategies (P/E UndVal LE / OverVal SE)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 60]
timeframe: daily
direction: both
regimes_good: [choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# P/E vs its own moving average

## One-line summary
Buy when a stock's P/E (close / trailing-12-month EPS) falls 10% below its 12-bar average; exit when it crosses back
above. Mirror for shorts.

## Origin and lineage
TradeStation demonstration strategies. Help pages (fetched 2026-10-07): inputs `EarningsField` (default "SDBF"),
`AvgLength` 12 (bars), `PctBelow` 10; P/E uses current close and TTM EPS. Exit and short rules are on the LX/SE/SX pages.

## Exact rules
- P/E_t = close_t / TTM EPS (latest four quarters).
- Long entry: P/E_t < (1 - 0.10) * SMA(P/E, 12 bars).
- Long exit: P/E crosses back above its average, or EPS <= 0.
- Short entry: P/E > 1.10 * average; cover on a cross below. No stop, no target, sizing unspecified.

## Why it should work
Between earnings reports EPS is constant, so on daily bars P/E is just price scaled by a constant: the rule is a
**12-day price mean-reversion rule** (price 10% below its 12-day mean), with a jump whenever EPS updates. Any edge is
short-term reversal, not valuation.

## When it works and when it fails
Behaves like a deep-oversold reversion trigger: fine in ranges, catches falling knives in downtrends. EPS updates
create artificial signals (a big EPS jump drops P/E sharply with no price change).

## Parameters and sensitivity
AvgLength (bars), PctBelow, bar size (on weekly/monthly bars it becomes closer to a valuation signal).

## Evidence
None published by the broker (catalog B86). Academic valuation reversion (value factor, e.g. E/P) works at multi-month
horizons cross-sectionally, not via a 12-day own-history average; no test of this exact rule located.

## Common mistakes
Thinking it is a valuation strategy; using EPS before its filing date; ignoring negative EPS.

## Implementation spec for swing-engine
- Data: TTM EPS from EDGAR companyfacts (`EarningsPerShareDiluted`, quarterly with Q4 = FY - 9M), point-in-time on `filed`.
- Features: `ttm_eps`, `pe = close / ttm_eps` (NaN when ttm_eps <= 0), `pe_sma_12`, `pe_dev = pe / pe_sma_12 - 1`,
  `eps_changed_12` (1 if ttm_eps changed in the last 12 bars; replay both with and without excluding these).
- Signal: `pe_dev < -0.10`, `ttm_eps > 0`. Entry next open. Stop `entry - 2.5 * atr_14` (engine choice).
  Exit: `pe_dev >= 0` or `ttm_eps <= 0`; `max_hold_days = 30`. `min_reward_risk = 0.0` (rule exit).
- Short side: not supported (`PanelStrategy.build_signal` is long-only); replay long side only.
- Missing: XBRL EPS ingest. Compare against a pure price rule (`close < 0.90 * sma_12`) to show the equivalence.

## What the router should know
Treat as mean reversion (choppy only, small). Not a value signal.

## Signs of decay to monitor
Not applicable beyond the generic: net expectancy <= 0 over 50 replay trades.

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_undval_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_undval_lx_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_overval_se_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_overval_sx_signal_.htm

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 6057 | 5 | 50% | +0.02 | -0.02 | 55% | +0.06 | +0.02 | 53% | +0.09 | +0.04 | 1.35 |
| correction | 551 | 1 | 50% | +0.03 | -0.06 | 62% | +0.20 | +0.12 | 72% | +0.50 | +0.42 | 4.44 |
| healthy_uptrend | 12928 | 11 | 46% | -0.01 | -0.06 | 42% | -0.06 | -0.11 | 40% | -0.09 | -0.14 | 0.77 |
| high_vol_selloff | 5648 | 5 | 66% | +0.20 | +0.13 | 70% | +0.30 | +0.24 | 60% | +0.38 | +0.32 | 2.44 |
| narrow_uptrend | 2219 | 2 | 43% | -0.04 | -0.09 | 38% | -0.13 | -0.18 | 42% | -0.08 | -0.13 | 0.78 |
| **all** | 27403 | 24 | 51% | +0.04 | -0.02 | 50% | +0.04 | -0.01 | 48% | +0.06 | +0.01 | 1.19 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11303 | 3 | 49% | +0.02 | -0.03 | 50% | +0.06 | +0.01 | 52% | +0.18 | +0.13 | 1.63 |
| correction | 10759 | 19 | 59% | +0.12 | +0.08 | 57% | +0.16 | +0.12 | 54% | +0.19 | +0.15 | 1.64 |
| healthy_uptrend | 20744 | 16 | 47% | -0.02 | -0.07 | 46% | -0.02 | -0.08 | 44% | -0.01 | -0.06 | 0.98 |
| high_vol_selloff | 37401 | 163 | 51% | -0.03 | -0.09 | 50% | -0.05 | -0.11 | 51% | +0.05 | -0.02 | 1.12 |
| narrow_uptrend | 8974 | 8 | 52% | +0.04 | -0.01 | 51% | +0.05 | -0.00 | 48% | +0.04 | -0.01 | 1.12 |
| **all** | 89181 | 209 | 51% | +0.01 | -0.05 | 50% | +0.01 | -0.05 | 50% | +0.07 | +0.01 | 1.20 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
