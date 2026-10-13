---
slug: williams_smash_day
name: Smash Day and Hidden Smash Day reversals (Larry Williams)
originators: [Larry Williams]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long   # sells mirror; engine is long-only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Smash Day / Hidden Smash Day

## One-line summary
A day that closes weak (below the prior low, or up but in the bottom quarter of its range) and is then taken out to the
upside within a few days marks a failed sell-off: buy the break of the smash day's high.

## Origin and lineage
Larry Williams, *Long-Term Secrets to Short-Term Trading* (1999), ch. 7. Best used as the end of a pullback in the
direction of the higher-timeframe trend.

## Exact rules (long)
- Naked smash: down day closing below the prior day's low (often taking out several recent lows).
- Hidden smash: up close (`close > prev_close`) that closes in the lowest 25% of its own range.
- Entry: buy stop 1 tick above the smash-day high; usually left working 1-3 days (author does not fix the duration).
- Stop: under the smash-day low. Exit: trail / short swing; Williams also used time exits.

## Why it should work
The smash day draws in sellers at the lows; a break above its high shows that supply failed and forces them to cover.

## When it works and when it fails
Pullbacks inside uptrends. In downtrends, naked smash days are just trend days.

## Parameters and sensitivity
Close-below-low depth, the 25% range cut-off, order life (1-3 days), trend filter. Keep 25% and 3 days fixed.

## Evidence
Originator examples only (catalog C11). Oxford Capital Strategies tested Smash Day variants on 42 futures from 1980;
numbers were not retrieved this run.

## Common mistakes
Taking it against the trend; leaving the buy stop open for a week (stale level).

## Discretionary parts and how to make them mechanical
Trend gate `trend_state == 1` and `close > sma_50`. "Several recent lows" -> optional `low_t == min(low[t-4..t])`.

## Implementation spec for swing-engine
- Reuses: OHLC, `prev_close`, `close_pos`, `trend_state`, `sma_50`, `atr_14`.
- Setup at close t: naked = `close_t < low_{t-1}`; hidden = `close_t > close_{t-1}` and `close_pos_t <= 0.25`.
- Entry: buy stop `high_t + 0.01`, live days t+1..t+3; fill at `max(open, level)` on the first day `high >= level`
  (needs stop-entry hook). Proxy without the hook: next open after a close above `high_t` (labelled).
- Stop: `low_t - 0.01`. Target: none taught; `min_reward_risk: 0.0`; `max_hold_days: 5`; engine trail after +2R.

## What the router should know
Pullback family; overlaps `pullback_holy_grail` (also a buy stop over a weak bar). Trend regimes only.

## Signs of decay to monitor
Triggered-then-stopped within 2 bars > 50%; average 5-day R <= 0.

## Sources
- https://prorealcode.com/prorealtime-indicators/larry-williams-smash-days
- https://roboforex.com/blog/education/catch-your-smash-day-with-larry-williams/
- https://catalogimages.wiley.com/images/db/pdf/0471297224.pdf
- https://oxfordstrat.com/?p=5935 (futures tests; numbers not retrieved)

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10854 | 7029 | 36% | -0.12 | -0.38 | -0.65 | 31% | -0.13 | -0.39 | -0.73 | 23% | -0.10 | -0.36 | -0.75 | 0.88 |
| correction | 742 | 520 | 33% | -0.31 | -0.75 | -0.89 | 30% | -0.33 | -0.77 | -1.28 | 23% | -0.27 | -0.71 | -1.76 | 0.70 |
| healthy_uptrend | 46922 | 31478 | 39% | -0.05 | -0.35 | -0.43 | 31% | -0.03 | -0.33 | -0.43 | 25% | +0.01 | -0.28 | -0.45 | 1.01 |
| high_vol_selloff | 3339 | 2224 | 37% | -0.15 | -0.43 | -0.63 | 27% | -0.29 | -0.58 | -0.73 | 19% | -0.38 | -0.66 | -0.71 | 0.61 |
| narrow_uptrend | 4941 | 3436 | 30% | -0.30 | -0.57 | -0.60 | 22% | -0.46 | -0.72 | -0.65 | 17% | -0.47 | -0.74 | -0.77 | 0.50 |
| **all** | 66798 | 44687 | 37% | -0.09 | -0.38 | -0.49 | 30% | -0.09 | -0.38 | -0.52 | 24% | -0.06 | -0.35 | -0.55 | 0.93 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 29224 | 19220 | 43% | -0.01 | -0.26 | -0.47 | 39% | +0.09 | -0.16 | -0.53 | 32% | +0.12 | -0.13 | -0.62 | 1.18 |
| correction | 12202 | 8286 | 39% | -0.09 | -0.38 | -0.67 | 32% | -0.09 | -0.38 | -0.77 | 26% | -0.13 | -0.43 | -0.85 | 0.83 |
| healthy_uptrend | 149875 | 102972 | 38% | -0.11 | -0.37 | -0.45 | 32% | -0.10 | -0.36 | -0.47 | 26% | -0.08 | -0.35 | -0.52 | 0.89 |
| high_vol_selloff | 21243 | 14723 | 36% | -0.18 | -0.45 | -0.50 | 32% | -0.19 | -0.46 | -0.55 | 26% | -0.23 | -0.50 | -0.51 | 0.69 |
| narrow_uptrend | 27273 | 18191 | 40% | -0.05 | -0.31 | -0.46 | 35% | -0.02 | -0.28 | -0.52 | 28% | -0.01 | -0.27 | -0.54 | 0.99 |
| **all** | 239817 | 163392 | 39% | -0.09 | -0.36 | -0.47 | 33% | -0.07 | -0.34 | -0.50 | 27% | -0.06 | -0.33 | -0.55 | 0.92 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 100%, avg +0.93R, PF inf, P&L $586 on $100k, avg hold 5.0 bars.
