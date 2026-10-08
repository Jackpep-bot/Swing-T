---
slug: gandalf_project_research_system
name: "Gandalf Project Research System (D'Errico & Trombetta)"
originators: ["Domenico D'Errico and Giovanni Trombetta, 'System Development Using Artificial Intelligence', Technical Analysis of Stocks & Commodities (Aug 2017)", "thinkorswim built-in strategy"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 10]   # exit lengths not published; assumption
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]   # assumption: dip-buy pattern
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Gandalf Project Research System

## One-line summary
A machine-generated candle-pattern dip-buy: enter long after specific orderings of ohlc4, median price and mid-body
price that indicate short-term weakness; exit after a fixed number of bars or on a weakness pattern while losing.

## Origin and lineage
From D'Errico & Trombetta's S&C article (Aug 2017) on building systems with genetic algorithms and out-of-sample
testing; the pattern was found by search, not designed from a market thesis. thinkorswim ships it as
GandalfProjectResearchSystem. The article and its original instrument/timeframe were not read (traders.com 403).

## Exact rules (thinkorswim documentation)
Definitions: ohlc4 = (O+H+L+C)/4; median = (H+L)/2; mid-body = (O+C)/2 (thinkorswim MidBodyVal; standard definition,
assumed). Index [k] = k bars ago.
- Buy (either set, all conditions within the set):
  - A: ohlc4[1] < median[1]; median[2] <= ohlc4[1]; median[2] <= ohlc4[3].
  - B: ohlc4[1] < median[3]; midbody[0] < median[2]; midbody[1] < midbody[2].
- Sell to close (any):
  - `exit length` bars elapsed since entry;
  - `exit gain length` bars elapsed and close > entry price;
  - close < entry price and either weakness set holds:
    - C: ohlc4[1] < midbody[1]; median[2] == midbody[3]; midbody[1] <= midbody[4];
    - D: ohlc4[2] < midbody[0]; median[4] < ohlc4[3]; midbody[1] < ohlc4[1].
- Input defaults for `exit length` and `exit gain length` are not listed on the doc page. No stop, no sizing.
- Note: condition C requires an exact equality of two prices, which almost never happens on equities (likely an
  artifact of tick-sized futures data).

## Why it should work
No stated mechanism. At best it captures short-term reversal after a weak close in the bar range (Jegadeesh 1990).
Data-mined patterns found by genetic search usually fail out of sample unless the authors' OOS test was strict.

## When it works and when it fails
Unknown. Expect behaviour like other 1-3 day dip-buys: better in uptrends, poor in crashes.

## Parameters and sensitivity
Only the two exit lengths. Use fixed values (engine v1: exit_length = 5, exit_gain_length = 2; arbitrary, logged as
such) and do not tune.

## Evidence
None. Article claims (OOS methodology) not verified; no independent test found.

## Common mistakes
Treating a GA-found pattern as a discovered edge; running it on instruments other than those it was mined on without
noting it.

## Discretionary parts and how to make them mechanical
Fully mechanical. Replace the exact equality in C with |median[2] - midbody[3]| <= 0.001 x close as a variant.

## Implementation spec for swing-engine
- Features: `ohlc4`, `median_price`, `mid_body` per bar plus shifts 1-4 (cheap, no warm-up).
- Long on bar t close if set A or B is true; filter `trend_state >= 0` and universe liquidity as usual. Entry next open.
- Stop: engine needs one for sizing: entry - 1.5 x atr_14 (engine choice, logged).
- Exits: per rules above; also the stop. No target -> `min_reward_risk: 0.0`. max_hold_days: 5 (= exit_length).
- Reuses: `atr_14`, `trend_state`, `prev_close`. Missing: the three price transforms and a bars-since-entry exit hook
  with entry-price awareness (`should_exit(row, bars_held)` lacks entry price today).

## What the router should know
Short dip-buy with zero evidence and likely very high signal frequency (simple candle orderings); cap signals per day and
treat as shadow-only noise benchmark.

## Signs of decay to monitor
Win rate near 50% with average win <= average loss would mean no edge; signal count per day.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GandalfProjectResearchSystem
- https://www.traders.com/Documentation/FEEDbk_docs/2017/08/TradersTips.html (Traders' Tips for the article; 403 this run)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 42849 | 271 | 49% | +0.02 | -0.03 | 45% | +0.03 | -0.02 | 39% | +0.12 | +0.07 | 1.20 |
| correction | 4890 | 21 | 47% | -0.03 | -0.08 | 56% | +0.23 | +0.17 | 55% | +0.56 | +0.51 | 2.29 |
| healthy_uptrend | 127748 | 686 | 48% | +0.04 | -0.02 | 42% | +0.03 | -0.03 | 34% | +0.04 | -0.02 | 1.06 |
| high_vol_selloff | 20156 | 148 | 54% | +0.13 | +0.09 | 51% | +0.24 | +0.20 | 37% | +0.17 | +0.13 | 1.28 |
| narrow_uptrend | 18688 | 122 | 38% | -0.16 | -0.22 | 29% | -0.33 | -0.38 | 23% | -0.34 | -0.39 | 0.57 |
| **all** | 214331 | 1248 | 48% | +0.03 | -0.03 | 43% | +0.03 | -0.03 | 35% | +0.05 | -0.00 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 50%, avg -0.36R, PF 0.31, P&L $84 on $100k, avg hold 1.5 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 125501 | 494 | 53% | +0.11 | +0.06 | 49% | +0.18 | +0.13 | 42% | +0.27 | +0.22 | 1.48 |
| correction | 73334 | 268 | 55% | +0.14 | +0.10 | 48% | +0.15 | +0.10 | 40% | +0.15 | +0.11 | 1.26 |
| healthy_uptrend | 397944 | 1872 | 47% | -0.00 | -0.06 | 42% | +0.01 | -0.05 | 35% | +0.04 | -0.02 | 1.05 |
| high_vol_selloff | 116882 | 1630 | 46% | -0.05 | -0.09 | 42% | -0.03 | -0.07 | 35% | -0.04 | -0.09 | 0.93 |
| narrow_uptrend | 101197 | 355 | 52% | +0.10 | +0.05 | 47% | +0.12 | +0.07 | 39% | +0.13 | +0.08 | 1.21 |
| **all** | 814858 | 4619 | 49% | +0.04 | -0.02 | 44% | +0.06 | +0.01 | 37% | +0.08 | +0.03 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
