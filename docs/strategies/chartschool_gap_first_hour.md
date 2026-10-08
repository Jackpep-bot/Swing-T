---
slug: chartschool_gap_first_hour
name: Gap trading first-hour range rules (Scott Andrews / ChartSchool)
originators: [Scott Andrews ("Understanding Gaps"), StockCharts ChartSchool]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [0, 5]
timeframe: intraday trigger (first hour) plus daily hold
direction: long and short (engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: false   # true rule needs first-hour intraday bars
status: not_built
---

# ChartSchool gap trading: first-hour range rules

## One-line summary
Classify the opening gap as full or partial, up or down. Let the first hour (to about 10:30 ET) set a range. Buy
on a stop two ticks above the first-hour high, or short two ticks below the first-hour low. Exit with an 8% (long)
or 4% (short) trailing stop, tighter (5-6%) for partial gaps.

## Origin and lineage
- ChartSchool's "Gap Trading Strategies" article. The catalog attributes the eight rules to Scott Andrews'
  *Understanding Gaps*; the fetched page names no originator.
- Gap-fill statistics from TradeThatSwing and thetrading.tools are the descriptive backdrop.

## Exact rules
ChartSchool, fetched 2026-10-07.

**Gap types:**
- Full Gap Up: open > prior high.
- Full Gap Down: open < prior low.
- Partial Gap Up: prior close < open <= prior high.
- Partial Gap Down: prior low <= open < prior close.

**Timing:** after about 10:30 ET, read the first hour's range on a 1-minute chart. Each of the four gap types has
a long and a short rule.

**Entry:** a buy stop two ticks above the first-hour high (long), or a sell stop two ticks below the first-hour
low (short). A "tick" means the bid/ask spread. For a full gap down, the long is a buy stop two ticks above the
prior day's low, an Oops-style reclaim (catalog P36).

**Exit:** trailing stop 8% for longs and 4% for shorts; 5-6% for partial gaps.

**Filters:** average volume at least 500k shares.

**Modified method:**
- Volume at least 2x the 5-day average.
- Full-gap entry at the average of the open and the first-hour high (a mid-rebound entry).
- Partial gaps may wait for a break of the prior high or low when volume is short.

No performance claims.

## Why it should work
The first hour absorbs overnight order imbalance and opening noise. A break of its range after 10:30 shows which
side won the open auction. The full-gap-down long bets that sellers are exhausted once price reclaims the prior
low. The other side is opening-auction liquidity and gap faders.

## When it works and when it fails
- Large gaps tend to continue: ES gaps over 1.2x ATR(14) filled the same day only about 8% of the time,
  2014-2024 (C50).
- Small index gaps tend to fill: SPY 0.1-0.25% up-gaps filled the same day about 78% of the time; 0.25-0.5% gaps
  about 60% the same day and 82% within 5 sessions.
- These fill numbers come from search summaries and are about index products, not single stocks.
- Fails on choppy opens with two-sided breaks. 8% trailing stops are wide for liquid large caps.

## Parameters and sensitivity
| Parameter | Value |
|---|---|
| `first_window_min` | 60 |
| `tick_offset` | 2 x spread (or 0.02) |
| `trail_long` | 0.08 |
| `trail_short` | 0.04 |
| `trail_partial` | 0.05-0.06 |
| `min_avg_volume` | 500k |
| `modified_vol_mult` | 2.0 (vs 5-day) |
| `min_gap_pct` | the source sets none; add 0.02 as an engine choice |

## Evidence
- Book-level practitioner method (P36, grade D). No independent statistics.
- The gap-fill statistics (C50) are descriptive only and not cost-inclusive.
- Post-23x5 trading (from 2026-12-06) changes what "the open" means. Re-validate gap statistics then.

## Common mistakes
- Using daily bars and pretending the first-hour high is known.
- Ignoring spread when setting the two-tick offset.
- Trading thin names, below the 500k filter.
- An 8% trail on a stock with a 2% ATR (wide), or on a 10% ATR small cap (tight).

## Discretionary parts and how to make them mechanical
The rules are exact. The only choices are which gap types and directions to trade. Fix the set (long only: full
gap up breakout, partial gap up breakout, full gap down Oops reclaim) and log it.

## Implementation spec for swing-engine
**True version (monitor path, intraday):**
- At 10:30 ET compute `fh_high` / `fh_low` from 1-minute bars (Alpaca stream; Massive Basic gives 2 years of
  delayed history).
- Place a buy stop at `fh_high + offset`.
- This needs a stop-entry order type, which the engine lacks: intents carry `entry_limit` only. It also needs an
  approval path fast enough for intraday use. Rule 5 requires human approval for orders.

**Daily approximation (label `approx_daily`):**
- Gap type comes from `open` vs `prior_high` / `prior_low` / `prior_close` (`gap_pct` exists).
- There are no first-hour bars, so the trigger becomes "close > open and close_pos >= 0.7" on the gap day, with
  entry at the next open. This is not the ChartSchool rule.
- Full-gap-down long: low < prior low, then close > prior low (the Oops reclaim, testable on daily bars).

**Exits:**
- Trailing stop = max(stop, highest close since entry x (1 - 0.08)). This needs a percent-trail hook; the current
  trail is the 10-bar lowest low after 2R.
- Initial stop = gap-day low.
- `max_hold_days` 5. No target. `min_reward_risk` 0.

**Reuse:** `gap_pct`, `prior_*`, `close_pos`, `avg_vol_20d`, `rvol_day`, the monitor's `rvol_now`.

**Missing:** intraday first-hour bar store, stop-entry orders, percent trailing stop.

## What the router should know
- Treat this as an intraday or monitor alert rather than a nightly scan signal. The daily approximation belongs in
  the gap family with `full_gap_continuation_bar` and `power_gap`, shadow only.
- Never let the monitor's Haiku classifier emit the trigger price. The price comes from bars.

## Signs of decay to monitor
- First-hour breakout follow-through (close beyond the trigger) by gap size.
- Same-day fill rates by gap bucket.
- Changes after 23x5 trading starts.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/gap-trading-strategies (fetched 2026-10-07)
- https://tradethatswing.com/sp-500-spy-es-gap-fill-strategy-and-statistics/ (statistics via search summaries)
- https://www.thetrading.tools/gap-analysis (statistics via search summaries)
- `docs/catalog/catalog.json` P36, C50; `docs/research-architecture.md` (data limits)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11024 | 790 | 36% | +0.01 | -0.09 | 30% | +0.04 | -0.06 | 23% | +0.17 | +0.07 | 1.20 |
| correction | 1788 | 129 | 33% | +0.16 | +0.05 | 30% | +0.26 | +0.16 | 24% | +0.28 | +0.18 | 1.30 |
| healthy_uptrend | 25352 | 1309 | 36% | +0.05 | -0.06 | 28% | +0.00 | -0.11 | 20% | -0.01 | -0.12 | 0.99 |
| high_vol_selloff | 7782 | 434 | 43% | +0.13 | +0.05 | 41% | +0.41 | +0.33 | 34% | +0.48 | +0.40 | 1.62 |
| narrow_uptrend | 4337 | 203 | 25% | -0.33 | -0.43 | 18% | -0.42 | -0.53 | 10% | -0.63 | -0.74 | 0.38 |
| **all** | 50283 | 2865 | 36% | +0.03 | -0.07 | 30% | +0.05 | -0.05 | 23% | +0.07 | -0.03 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 25327 | 1000 | 37% | +0.03 | -0.07 | 31% | +0.09 | -0.01 | 25% | +0.15 | +0.05 | 1.17 |
| correction | 20576 | 648 | 42% | +0.16 | +0.08 | 36% | +0.26 | +0.18 | 29% | +0.30 | +0.22 | 1.37 |
| healthy_uptrend | 64229 | 2341 | 35% | -0.02 | -0.13 | 28% | -0.00 | -0.12 | 21% | +0.01 | -0.10 | 1.01 |
| high_vol_selloff | 35579 | 2343 | 36% | +0.03 | -0.04 | 31% | +0.04 | -0.03 | 26% | +0.06 | -0.01 | 1.08 |
| narrow_uptrend | 17276 | 601 | 39% | +0.13 | +0.02 | 32% | +0.17 | +0.06 | 25% | +0.19 | +0.08 | 1.23 |
| **all** | 162987 | 6933 | 37% | +0.04 | -0.06 | 31% | +0.07 | -0.03 | 24% | +0.10 | +0.00 | 1.12 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
