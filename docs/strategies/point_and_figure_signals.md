---
slug: point_and_figure_signals
name: "Point & Figure signals (double/triple top buys, catapults, price objectives)"
originators: ["Charles Dow era tape charting", "A.W. Cohen / ChartCraft", "Tom Dorsey (Dorsey Wright)", "StockCharts.com"]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [10, 90]
timeframe: daily (close or high/low)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Point & Figure signals

## One-line summary
Filter price into X (up) and O (down) columns with a fixed box and 3-box reversal; buy when an X column exceeds the
prior X column high (double top) or two equal prior highs (triple top), with vertical/horizontal counts as objectives.

## Origin and lineage
P&F dates to late-19th-century tape reading; formalised by ChartCraft (A.W. Cohen) and popularised by Tom Dorsey
(*Point and Figure Charting*, Dorsey Wright). StockCharts implements the traditional box table (catalog P30). The
Bullish Percent Index (% of stocks on a P&F buy signal) is the breadth by-product.

## Exact rules
- **Box size** (traditional table, partial): $5.01-$20 -> $0.50; $20.01-$100 -> $1.00; higher bands larger. Alternatives:
  percentage boxes or ATR-based boxes. Full table bands outside these are not reproduced here.
- **Reversal**: a new column starts only after price reverses by 3 boxes.
- **Construction**: close-only, or high/low method (extend current column with high (X) or low (O) first; reverse only
  if not extended).
- **Buy signals**: Double Top Buy = current X column rises one box above the previous X column's top. Triple Top Buy =
  breaks two prior equal X tops. Also spread triple tops, bullish catapult (triple top buy followed by a double top
  buy), bearish signal reversal.
- **Sell**: Double Bottom Sell = O column falls one box below the prior O low (exit for longs).
- **Price objectives**: vertical count = boxes in the breakout X column x box size x reversal (3) added to the column's
  low; horizontal count = width (columns) of the congestion x box x reversal added to the base low.
- Stop: commonly the double-bottom sell point or the low of the signal column (practitioner convention).

## Why it should work
Box filtering removes noise; a double-top break is a breakout above recent resistance (time-series momentum,
breakout family). The other side: holders selling at the prior high.

## When it works and when it fails
Works in trending names; whipsaws in sideways markets where columns alternate around the same level.

## Parameters and sensitivity
Box size (table vs 1-3% vs ATR), reversal (1/2/3 box), close vs high/low. Results are sensitive to box size; fix the
traditional table and a 3-box reversal before looking at results.

## Evidence
Anderson and Faff (2008, International Review of Financial Analysis 17(1):198-217) tested eight objective P&F rules on
S&P 500 futures 1990-1998 with bootstrapping: mixed significance, some rules significant, many not. No large
cross-sectional stock study found. Grade C reflects long practitioner use, not proof.

## Common mistakes
Changing box size after seeing the chart; treating price objectives as reliable targets; ignoring that a double-top
buy is a very common, weak signal on its own.

## Discretionary parts and how to make them mechanical
Pattern naming (catapult, spread triple top) is rule-based once columns exist; implement double and triple top only
at first.

## Implementation spec for swing-engine
- New module: per-symbol P&F column builder over daily high/low (causal: updates bar by bar, box from the traditional
  table using the price at column start). Outputs per bar: `pf_col_dir` (+1 X / -1 O), `pf_col_top`, `pf_col_bot`,
  `pf_prev_x_top`, `pf_prev_x_top2`, `pf_prev_o_bot`, `pf_box`.
- Signal at t: current column X and `pf_col_top[t] > pf_prev_x_top[t]` first time in this column (double top);
  variant triple: also `pf_prev_x_top == pf_prev_x_top2`.
- Entry next open. Stop = `pf_prev_o_bot - pf_box` (double-bottom sell level). Target = vertical count
  `pf_col_bot + n_boxes * pf_box * 3`. `min_reward_risk` 1.5; `max_hold_days` 60; rule exit on double-bottom sell.
- Reuses `atr_14` (ATR box variant), `trend_state` (optional gate). Missing: column builder; Bullish Percent Index could
  be added to features/breadth.py as a by-product.

## What the router should know
Breakout family with a noise filter; overlaps `sr_breakout` / `breakout_52w`. Only with confirmed participation.

## Signs of decay to monitor
Double-top buys followed by double-bottom sells within 10 bars above ~50%.

## Sources
- https://www.aaii.com/journal/article/online-point-and-figure-charting
- https://researchers.westernsydney.edu.au/en/publications/point-and-figure-charting-a-computational-methodology-and-trading/
- https://en.wikipedia.org/wiki/Point_and_figure_chart

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3647 | 18 | 51% | +0.07 | -0.02 | 49% | +0.09 | -0.00 | 49% | +0.16 | +0.06 | 1.38 |
| correction | 682 | 3 | 58% | +0.16 | -0.11 | 61% | +0.36 | +0.09 | 58% | +0.43 | +0.16 | 2.22 |
| healthy_uptrend | 13423 | 90 | 45% | -0.04 | -0.13 | 43% | -0.04 | -0.13 | 41% | -0.04 | -0.13 | 0.92 |
| high_vol_selloff | 2246 | 10 | 58% | +0.11 | -0.05 | 57% | +0.17 | +0.01 | 50% | +0.24 | +0.08 | 1.56 |
| narrow_uptrend | 1236 | 12 | 39% | -0.14 | -0.26 | 38% | -0.17 | -0.29 | 33% | -0.22 | -0.34 | 0.66 |
| **all** | 21234 | 133 | 48% | -0.00 | -0.11 | 46% | +0.01 | -0.10 | 43% | +0.03 | -0.07 | 1.07 |

Portfolio replay (net of costs, slots shared with its run): 5 trades, win 40%, avg +0.91R, PF 3.23, P&L $1,338 on $100k, avg hold 8.4 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 8394 | 20 | 50% | +0.00 | -0.07 | 51% | +0.03 | -0.04 | 48% | +0.06 | -0.01 | 1.16 |
| correction | 7710 | 18 | 50% | -0.01 | -0.09 | 53% | +0.07 | -0.02 | 50% | +0.09 | +0.01 | 1.25 |
| healthy_uptrend | 28983 | 69 | 49% | -0.00 | -0.07 | 48% | -0.00 | -0.07 | 46% | -0.00 | -0.07 | 1.00 |
| high_vol_selloff | 11258 | 46 | 49% | -0.01 | -0.14 | 48% | -0.01 | -0.14 | 48% | +0.06 | -0.08 | 1.13 |
| narrow_uptrend | 6133 | 23 | 49% | +0.00 | -0.07 | 49% | -0.00 | -0.08 | 48% | +0.03 | -0.05 | 1.07 |
| **all** | 62478 | 176 | 49% | -0.00 | -0.09 | 49% | +0.01 | -0.07 | 47% | +0.03 | -0.05 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 10 trades, win 30%, avg -0.32R, PF 0.38, P&L $-3,330 on $100k, avg hold 8.5 bars.
