---
slug: cooper_123_pullback
name: "1-2-3-4 pullback (Jeff Cooper, Hit and Run)"
originators: ["Jeff Cooper (Hit and Run Trading, 1996)", "taught alongside Connors/Raschke pullback family"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long (originator also trades the short mirror; engine is long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# 1-2-3-4 pullback (Cooper)

## One-line summary
In a stock with a strong directional trend (ADX(14) > 30, +DI > -DI), wait for three lower lows in a row (inside days
skipped), then buy a break above the third pullback bar's high on day 4 with the stop under that bar's low.

## Origin and lineage
Jeff Cooper, *Hit and Run Trading* (1996), "1-2-3-4" pullbacks. Same family as the Raschke/Connors Holy Grail
(ADX > 30 + pullback to the 20 EMA, `pullback_holy_grail`), Connors' 3-day pullback sets and Landry's "two or more
lower lows" pullback (docs/methods/01). The book was not read for this card; rules come from the catalog entry (C20)
and secondary restatements (see Sources). Exact exit wording in the book is **unverified**.

## Exact rules (as taught, per catalog)
- **Universe / screen**: Cooper's "hit list": ADX(14) > 30 and +DI > -DI (longs). Any extra hit-list criteria in the
  book (e.g. new highs, price/volume floors) are unverified.
- **Setup**: three consecutive bars, each with a low below the previous counted bar's low. Inside days (high below
  prior high and low above prior low) are ignored, not counted and not breaking the sequence.
- **Trigger**: on day 4, a buy stop one tick above the day-3 high.
- **Initial stop**: below the day-3 low (the pullback low).
- **Targets / exits**: exit into strength over the following 1-5 days; Cooper scales out and trails. No fixed R target.
- **Short mirror**: ADX > 30 with -DI > +DI, three higher highs, sell stop under day-3 low. Not used here.
- **Sizing**: not specified in the sources used.

## Why it should work
Short pullbacks inside strong trends are bought by trend followers and institutions working orders; the day-3 high
break shows the pullback sellers are exhausted. The other side is short-term mean-reversion sellers and late
shorts covering on the break. Documented academic support is for the family (short-horizon reversal within
intermediate momentum), not this exact pattern.

## When it works and when it fails
- Works: steady leadership trends, sector rotation into the name, low index volatility.
- Fails: trend exhaustion (ADX > 30 is often late-trend), gap-down news on day 4, index sell-offs where three lower
  lows are the start of a correction. Breaks above day-3 high frequently fail in choppy tape (one-day pops).

## Parameters and sensitivity
| Knob | Default | Sensible range | Note |
|---|---|---|---|
| `adx_min` | 30 | 20-35 | Higher = fewer, later-trend signals |
| `n_lower_lows` | 3 | 2-4 | 2 = Landry; 4 is rare |
| `skip_inside_days` | true | - | Core to the definition |
| `stop_tick` | 0.01 | 0.01-0.1*ATR | Stop under day-3 low |
| `max_hold_days` | 5 | 3-7 | Cooper "1-5 days" |
Overfitting traps: tuning ADX threshold per regime; adding MA filters until backtest looks good.

## Evidence
No independent test located (catalog grade D). EasySwing's 2026 panel for a related EMA20 pullback detector reports
win 26%, avg +0.3R, PF 1.45 on raw exits (docs/methods/01); that is a different rule set and is not evidence for this
one. No post-publication decay study.

## Common mistakes
Counting inside days; entering on day-3 close instead of above the day-3 high; holding a failed break beyond day 5;
using it when SPY is below its 50-day.

## Discretionary parts and how to make them mechanical
"Exit into strength" -> time stop at `max_hold_days` plus a trail to the prior bar's low once close >= entry + 1R
(engine choice, not Cooper's documented rule). Hit-list membership -> ADX/DI test on the day-3 bar.

## Implementation spec for swing-engine
- Features (exist): `adx_14`, `plus_di_14`, `minus_di_14` (features/patterns2.py, Wilder 14); `inside_day`
  (features/patterns.py: high < prev_high and low > prev_low); `atr_14`, `high`, `low`.
- Counted-bar sequence (per symbol, as-of bar t = day 3): walk back from t skipping `inside_day == 1`; require counted
  bars c3 = t, c2, c1, c0 with `low[c3] < low[c2] < low[c1] < low[c0]`; and `adx_14[t] >= adx_min`,
  `plus_di_14[t] > minus_di_14[t]`; c0 within 10 bars of t.
- Entry (as the engine works today): no stop-entry order hook exists; backtest fills signals at the next open
  (research/backtest.py). Two options:
  1. Preferred once a stop-entry hook exists: emit on day-3 close with `entry = high[t] + 0.01`, order type buy-stop,
     valid one session, cancel if not triggered.
  2. Now: emit on day-4 close if `close[t+1] > high[t]` (first such close) and fill at the next open, exactly as
     `pullback_holy_grail` approximates its trigger. This is later and worse than Cooper's entry; record it.
- Stop: `low[day3] - 0.01` (option 1) or the same level carried to option 2.
- Target: none taught. For `build_signal` geometry use prior swing high = max(high) over the 20 bars before c0
  (same convention as `pullback_holy_grail`), `min_reward_risk` 1.0.
- Exits: `max_hold_days` = 5 (read by backtest STRATEGY_HOLD_PARAM); `TrailingStop(breakeven_after_r=1.0)`.
- Missing: stop-entry order support in backtest/execution; short side (engine signals are long-only).

## What the router should know
Pullback family; overlaps `pullback_holy_grail` heavily (both ADX > 30). Treat as the same risk bucket; allow in
healthy_uptrend (1.0) and narrow_uptrend (0.5) only, never in correction / high_vol_selloff.

## Signs of decay to monitor
Day-4 break failure rate (close back below day-3 low within 2 bars) rising above ~50%; average MFE within 5 days
shrinking below 1R; overlap with Holy Grail signals making it redundant.

## Sources
- https://elibook.vn/2020/02/03/hit-run-trading-cach-chon-co-phieu-de-trading-cua-thanh-giao-dich-ngan-han-jeff-cooper/
- https://stock3.com/news/die-1-2-3-4-chartformation-5810362
- docs/methods/01-pullback-20-50-ma-uptrend.md (family context)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1104 | 551 | 35% | -0.17 | -0.49 | 33% | -0.13 | -0.45 | 32% | -0.10 | -0.43 | 0.87 |
| correction | 36 | 21 | 47% | +0.13 | -0.06 | 33% | -0.00 | -0.19 | 33% | +0.11 | -0.08 | 1.16 |
| healthy_uptrend | 3753 | 2023 | 39% | +0.01 | -0.27 | 35% | +0.03 | -0.25 | 33% | +0.02 | -0.26 | 1.02 |
| high_vol_selloff | 290 | 156 | 39% | -0.04 | -0.29 | 36% | -0.06 | -0.31 | 30% | -0.17 | -0.42 | 0.78 |
| narrow_uptrend | 409 | 219 | 36% | -0.23 | -0.52 | 26% | -0.26 | -0.55 | 22% | -0.30 | -0.59 | 0.64 |
| **all** | 5592 | 2970 | 38% | -0.05 | -0.33 | 34% | -0.03 | -0.32 | 32% | -0.04 | -0.33 | 0.95 |

Portfolio replay (net of costs, slots shared with its run): 437 trades, win 32%, avg -0.16R, PF 0.74, P&L $-40,975 on $100k, avg hold 3.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2864 | 1590 | 39% | -0.12 | -0.45 | 36% | -0.09 | -0.42 | 34% | -0.06 | -0.39 | 0.92 |
| correction | 1799 | 960 | 40% | -0.03 | -0.37 | 35% | -0.08 | -0.42 | 33% | -0.04 | -0.38 | 0.95 |
| healthy_uptrend | 12624 | 6891 | 36% | -0.15 | -0.44 | 32% | -0.16 | -0.45 | 29% | -0.15 | -0.44 | 0.80 |
| high_vol_selloff | 1412 | 797 | 34% | -0.24 | -0.55 | 33% | -0.17 | -0.49 | 32% | -0.11 | -0.42 | 0.86 |
| narrow_uptrend | 2045 | 1032 | 38% | -0.09 | -0.40 | 35% | -0.03 | -0.34 | 33% | -0.01 | -0.32 | 0.99 |
| **all** | 20744 | 11270 | 37% | -0.14 | -0.44 | 33% | -0.13 | -0.43 | 31% | -0.11 | -0.42 | 0.85 |

Portfolio replay (net of costs, slots shared with its run): 1376 trades, win 30%, avg -0.31R, PF 0.55, P&L $-70,241 on $100k, avg hold 3.1 bars.
