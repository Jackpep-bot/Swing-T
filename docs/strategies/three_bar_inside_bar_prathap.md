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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2905 | 77 | 48% | +0.02 | -0.22 | -0.48 | 44% | +0.01 | -0.23 | -0.51 | 42% | -0.00 | -0.24 | -0.56 | 1.00 |
| correction | 478 | 19 | 48% | +0.10 | -0.33 | -0.45 | 53% | +0.25 | -0.19 | -0.62 | 52% | +0.31 | -0.13 | -0.72 | 1.67 |
| healthy_uptrend | 11795 | 450 | 42% | -0.08 | -0.33 | -0.30 | 40% | -0.09 | -0.34 | -0.31 | 39% | -0.08 | -0.33 | -0.31 | 0.87 |
| high_vol_selloff | 2631 | 206 | 39% | -0.11 | -0.44 | -0.32 | 55% | +0.15 | -0.18 | -0.34 | 54% | +0.22 | -0.11 | -0.36 | 1.49 |
| narrow_uptrend | 1428 | 46 | 34% | -0.20 | -0.44 | -0.16 | 32% | -0.23 | -0.47 | -0.18 | 32% | -0.20 | -0.44 | -0.18 | 0.69 |
| **all** | 19237 | 798 | 42% | -0.07 | -0.34 | -0.32 | 42% | -0.04 | -0.31 | -0.34 | 41% | -0.03 | -0.29 | -0.36 | 0.95 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10366 | 526 | 48% | +0.05 | -0.17 | -0.27 | 47% | +0.06 | -0.16 | -0.28 | 46% | +0.08 | -0.14 | -0.27 | 1.15 |
| correction | 7848 | 384 | 50% | +0.06 | -0.19 | -0.27 | 49% | +0.11 | -0.14 | -0.25 | 47% | +0.12 | -0.13 | -0.23 | 1.22 |
| healthy_uptrend | 41677 | 2292 | 45% | +0.00 | -0.24 | -0.28 | 44% | +0.01 | -0.24 | -0.29 | 42% | +0.01 | -0.23 | -0.29 | 1.02 |
| high_vol_selloff | 10453 | 597 | 48% | +0.03 | -0.23 | -0.26 | 47% | +0.07 | -0.20 | -0.25 | 46% | +0.10 | -0.17 | -0.25 | 1.18 |
| narrow_uptrend | 8624 | 410 | 45% | +0.02 | -0.23 | -0.29 | 44% | +0.02 | -0.22 | -0.30 | 44% | +0.05 | -0.20 | -0.29 | 1.08 |
| **all** | 78968 | 4209 | 47% | +0.02 | -0.23 | -0.28 | 45% | +0.03 | -0.21 | -0.28 | 44% | +0.05 | -0.20 | -0.28 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 0%, avg -0.67R, PF 0.00, P&L $-121 on $100k, avg hold 3.5 bars.
