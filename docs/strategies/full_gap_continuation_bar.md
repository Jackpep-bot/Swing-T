---
slug: full_gap_continuation_bar
name: Full-gap entry bar (Gap Up LE, low > prior high; thinkorswim, TradeStation)
originators: [Charles Schwab / thinkorswim built-in, TradeStation built-in]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 10]
timeframe: daily
direction: long (GapDownSE is the short mirror; the engine is long-only)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Full-gap continuation bar (GapUpLE)

## One-line summary
When a whole daily bar sits above the prior bar (today's low > yesterday's high, so the gap never filled), buy the
next bar. This is a platform demonstration entry with no exit and no published statistics.

## Origin and lineage
- Built-in entry strategies on thinkorswim (GapUpLE / GapDownSE) and TradeStation (Gap Up LE / Gap Down SE).
- They belong to the same simple bar-pattern library as InsideBar, KeyRev and ConsBarsUp.
- These are entry-only building blocks: the platforms pair them with separate exit strategies.
- The idea relates to the "unfilled gap = continuation" view (see `chartschool_gap_first_hour` and PEG/BGU in
  `docs/methods/13-power-earnings-gap.md`).

## Exact rules
**thinkorswim:**
- Gap Up occurs when the current bar's low is higher than the previous bar's high.
- A long-entry signal is generated for the next bar.
- GapDownSE is the mirror: high < prior low means short the next bar.

**TradeStation:** the same definition per the catalog. The TradeStation help pages were not re-read this run.

**Not specified by either source:**
- order type (a strategy order "next bar" typically fills at the next open)
- stop
- target
- exit
- sizing
- universe

## Why it should work
A bar that never trades back into the prior range means overnight demand was strong enough that no seller could
fill the gap all session. That is a sign of new information (earnings, news) or institutional urgency. Large
gaps mostly do not fill the same day (catalog C50: ES gaps over 1.2x ATR(14) filled the same day only about 8% of
the time, 2014-2024; from search summaries). The other side is fade traders shorting the gap.

## When it works and when it fails
- **Works:** on catalyst gaps in uptrending, liquid names, which is the PEG / episodic-pivot territory.
- **Fails:**
  - Small, news-free gaps in choppy tapes.
  - Exhaustion gaps after long runs.
  - Next-open entries that buy into an overnight continuation and then revert.
- It fires often on low-priced, volatile names unless filtered.

## Parameters and sensitivity
The source defines no parameters. The engine needs these (engine choices, not originator rules):

| Parameter | Value |
|---|---|
| `min_gap_pct` (open / prev close - 1) | 0.0 (raw rule), also 0.03 and 0.05 |
| `min_rvol` | 0 (raw), also 1.5 |
| `stop_mode` | `prior_high` (the gap-fill level) or `bar_low` |
| `hold_days` | 5 |
| `target_r` | none |

Adding filters turns this into a different strategy (PEG/BGU). Keep the raw version as the comparison baseline.

## Evidence
- None. The brokers publish only documentation (catalog B40).
- The gap-fill statistics in C50 are descriptive and mostly about index futures and ETFs, not single stocks.
- There is no cost-inclusive test.

## Common mistakes
- Treating an entry-only built-in as a system.
- Testing on adjusted data where splits create fake gaps (check `adj_close` vs raw).
- Ignoring that the next open may itself gap away.

## Discretionary parts and how to make them mechanical
None. The rule is exact. Everything else (exits, filters) is an engine choice and must be labelled as such.

## Implementation spec for swing-engine
- **Signal on day t:** `low_t > prior_high`, using the `prior_high` that `PanelStrategy.rows_as_of` already
  provides (`prior_columns`).
- **Optional filters:** `gap_pct >= min_gap_pct`, `rvol_day >= min_rvol`, `trend_state >= 0`.
- **Entry:** next session's open. The engine's daily intents use a limit at the signal close, so a "next open"
  fill needs a market-on-open or a limit = close x (1 + slippage) param. Label the fill model.
- **Stop:** `prior_high` (the gap is filled = thesis wrong), or `low_t`.
- **Exit:** `should_exit` when `bars_held >= hold_days`. No target. `min_reward_risk` 0.
- **`max_hold_days`:** 5-10.
- **Reuse:** `gap_pct`, `rvol_day`, `prior_*` columns, `atr_14`, `trend_state`. No new features are needed.
- **Missing:** a next-open fill model in the backtest, and a split-safe check, because a reverse split creates a
  fake full gap down and a split creates one up on unadjusted bars.

## What the router should know
- This is a baseline for the gap family (`power_gap`, `episodic_pivot`).
- Allow it in `healthy_uptrend` only, in shadow.
- Its value is as a control: if `power_gap` cannot beat raw GapUpLE after costs, the extra rules add nothing.

## Signs of decay to monitor
- Same-day and 5-day fill rate of full gaps in the universe.
- Next-open slippage vs the signal close.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GapUpLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GapDownSE
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/gap_up_le_signal_.htm (not re-read)
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/gap_down_se_signal_.htm (not re-read)
- https://tradethatswing.com/sp-500-spy-es-gap-fill-strategy-and-statistics/ (C50 statistics, via search summaries)
- `docs/catalog/catalog.json` items B40, C50

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 5072 | 257 | 44% | +0.14 | -0.14 | 37% | +0.24 | -0.03 | 31% | +0.57 | +0.30 | 1.71 |
| correction | 782 | 161 | 43% | +0.52 | -0.45 | 38% | +0.68 | -0.29 | 34% | +0.89 | -0.08 | 2.27 |
| healthy_uptrend | 18880 | 1177 | 35% | -0.07 | -0.40 | 27% | -0.10 | -0.42 | 22% | +0.01 | -0.31 | 1.01 |
| high_vol_selloff | 2541 | 350 | 45% | +0.39 | -0.06 | 36% | +0.37 | -0.07 | 27% | +0.44 | -0.01 | 1.46 |
| narrow_uptrend | 2051 | 172 | 23% | -0.32 | -0.63 | 20% | -0.37 | -0.68 | 10% | -0.56 | -0.89 | 0.46 |
| **all** | 29326 | 2117 | 37% | -0.00 | -0.34 | 30% | -0.00 | -0.34 | 24% | +0.13 | -0.21 | 1.14 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 15551 | 758 | 36% | -0.00 | -0.30 | 31% | +0.05 | -0.25 | 27% | +0.23 | -0.07 | 1.25 |
| correction | 11923 | 736 | 39% | +0.01 | -0.30 | 35% | +0.14 | -0.18 | 27% | +0.08 | -0.23 | 1.09 |
| healthy_uptrend | 49315 | 2374 | 37% | -0.01 | -0.32 | 30% | -0.01 | -0.33 | 22% | -0.10 | -0.41 | 0.90 |
| high_vol_selloff | 10351 | 684 | 38% | +0.09 | -0.27 | 32% | +0.08 | -0.28 | 26% | +0.05 | -0.31 | 1.06 |
| narrow_uptrend | 11068 | 433 | 38% | -0.00 | -0.33 | 33% | +0.13 | -0.19 | 26% | +0.19 | -0.13 | 1.22 |
| **all** | 98208 | 4985 | 37% | +0.01 | -0.31 | 32% | +0.04 | -0.28 | 24% | +0.02 | -0.29 | 1.03 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
