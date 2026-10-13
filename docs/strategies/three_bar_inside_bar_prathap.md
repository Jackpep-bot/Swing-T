---
slug: three_bar_inside_bar_prathap
name: Three-Bar Inside Bar (Johnan Prathap)
originators: [Johnan Prathap]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: both
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: 1.0
evidence_grade: D
free_data_ok: true
status: not_built
---

# Three-Bar Inside Bar (Prathap)

## One-line summary
Up close, inside bar, up close again -> buy next open with a tight symmetric target and stop; a commodity
pattern from a 2011 magazine article, here only as a comparison baseline.

## Origin and lineage
Johnan Prathap, "Three-Bar Inside Bar Pattern", *Technical Analysis of Stocks & Commodities* V.29:3 (March 2011),
pp. 30-35. Tested on daily gold, silver and crude oil futures, May 2001 to Aug 2010 (per traders.com abstract /
search summary). Shipped as thinkorswim ThreeBarInsideBarLE/SE; WH SelfInvest republished it.

## Exact rules
Bars indexed oldest to newest as 1..4 (bar 4 = signal bar):
- Long: `C1 < C2` (bar 2 closed up), `H3 < H2 and L3 > L2` (bar 3 inside bar 2), `C4 > C3`. Buy at next open (market).
- Short: mirror (`C1 > C2`, bar 3 inside, `C4 < C3`).
- Exits: thinkorswim leaves exits to ProfitTargetLX / StopLossLX. WH SelfInvest's restatement uses target and stop
  both at 0.75% of entry (fixed %, not volatility-scaled). The original article's exit values could not be read
  (traders.com returned 403), so the 0.75% is a secondary-source figure.
- No trailing or time exit described. Sizing: not specified. Entry only opens positions, never adds.

## Why it should work
Claimed mechanism: an inside bar between two up closes is a pause, not a reversal; the next up close confirms
continuation. Counterparty: short-term faders of the first up move. No independent mechanism study exists.

## When it works and when it fails
Designed on trending commodities. In stocks a 0.75% symmetric bracket is inside daily noise for most names
(median `atr_pct_14` is typically 2-4%), so outcomes approach coin flips minus costs. Fails in choppy tapes.

## Parameters and sensitivity
| Knob | Taught | Sensible stock range | Trap |
|---|---|---|---|
| target/stop | 0.75% / 0.75% (secondary) | 0.5-1.5 x atr_14 | tuning the bracket per market = overfit |
| trend filter | none | trend_state == 1 for longs | |
| max_hold_days | none | 3-5 | |

## Evidence
- Only the author's in-sample commodity illustration (catalog grade D). No independent test found; no published
  result for equities. Performance numbers from the article could not be verified.

## Common mistakes
Porting fixed-% brackets from futures to equities; trading both sides in an uptrending market.

## Discretionary parts and how to make them mechanical
None in the pattern; exits are the only choice. Use ATR-scaled brackets and log each choice as a trial.

## Implementation spec for swing-engine
- Reuse: `inside_day` (shifted one bar), `prev_close`, `atr_14`, `trend_state`.
- Signal on as-of bar t (= bar 4): `close[t-2] > close[t-3]` and `inside_day[t-1] == 1` and `close[t] > close[t-1]`.
- Entry = next open. Two variants for replay: (a) taught: stop = entry x (1 - 0.0075), target = entry x (1 + 0.0075);
  (b) engine-native: stop = min(low[t-1], low[t]) - 0.25 x atr_14, target = entry + 1.5R, `max_hold_days = 5`.
- `min_reward_risk`: 1.0 for (a) (the floor must be lowered or it never passes the default 2:1), 1.5 for (b).
- Short side only if the backtest's `allow_short` stays true and the router permits; default long only.
- New module `strategies/three_bar_inside_bar.py`; no new feature needed.

## What the router should know
Low-information pattern with frequent signals; at most a small allocation in uptrend regimes. Disabled for comparison.

## Signs of decay to monitor
Hit rate at 1R below 50% after costs; mean R per trade <= 0 over 100+ trades.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/ThreeBarInsideBarLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/ThreeBarInsideBarSE
- https://store.traders.com/stcov293thin.html
- https://www.traders.com/Documentation/FEEDbk_docs/2011/03/Prathap.html (403 at fetch)
- https://www.whselfinvest.de/en/trading-platform/free-trading-strategies/tradingsystem/21-bib

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2914 | 78 | 48% | +0.02 | -0.22 | 44% | +0.01 | -0.23 | 42% | -0.00 | -0.24 | 1.00 |
| correction | 479 | 19 | 48% | +0.10 | -0.33 | 53% | +0.25 | -0.19 | 52% | +0.31 | -0.13 | 1.66 |
| healthy_uptrend | 11821 | 456 | 42% | -0.08 | -0.33 | 40% | -0.09 | -0.34 | 39% | -0.08 | -0.33 | 0.87 |
| high_vol_selloff | 2637 | 207 | 39% | -0.11 | -0.44 | 54% | +0.15 | -0.18 | 54% | +0.22 | -0.11 | 1.48 |
| narrow_uptrend | 1433 | 46 | 34% | -0.20 | -0.44 | 32% | -0.23 | -0.47 | 32% | -0.20 | -0.44 | 0.70 |
| **all** | 19284 | 806 | 42% | -0.07 | -0.34 | 42% | -0.04 | -0.31 | 41% | -0.03 | -0.29 | 0.95 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10609 | 534 | 49% | +0.05 | -0.17 | 47% | +0.06 | -0.16 | 46% | +0.09 | -0.13 | 1.16 |
| correction | 8011 | 386 | 50% | +0.06 | -0.19 | 49% | +0.11 | -0.14 | 47% | +0.12 | -0.13 | 1.22 |
| healthy_uptrend | 42936 | 2325 | 45% | -0.00 | -0.24 | 44% | +0.00 | -0.24 | 42% | +0.01 | -0.23 | 1.02 |
| high_vol_selloff | 10731 | 602 | 48% | +0.04 | -0.23 | 47% | +0.07 | -0.19 | 47% | +0.10 | -0.17 | 1.19 |
| narrow_uptrend | 8820 | 413 | 46% | +0.02 | -0.23 | 44% | +0.02 | -0.22 | 44% | +0.05 | -0.20 | 1.09 |
| **all** | 81107 | 4260 | 47% | +0.02 | -0.22 | 45% | +0.03 | -0.21 | 44% | +0.05 | -0.20 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 0%, avg -0.67R, PF 0.00, P&L $-121 on $100k, avg hold 3.5 bars.
