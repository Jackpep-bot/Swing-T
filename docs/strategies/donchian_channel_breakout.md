---
slug: donchian_channel_breakout
name: Donchian / price-channel breakout (20-40 bar high)
originators: [Richard Donchian, Oscar G. Cagigas, TradeStation, TradingView, StockCharts]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 40]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Donchian / price-channel breakout

## One-line summary
Buy when price exceeds the highest high of the prior N bars (20-40); exit on a break of the lowest low of a shorter
M-bar window (10-15). The plain-channel control for `breakout_52w`.

## Origin and lineage
Richard Donchian's channel / "4-week rule" (1950s-60s; the 4-week rule is described on StockCharts). Platform
versions: thinkorswim `Donchian` (Oscar Cagigas, "The Degree of Complexity", S&C Feb 2014), TradeStation Price Channel
LE/SE (20 bars), TradingView Price Channel (20) and Channel BreakOut (5). The Turtle systems
(`turtle_breakout_systems`) are the best-known descendant.

## Exact rules
- thinkorswim/Cagigas, low complexity: long when high > highest high of prior `entry length` bars (40 per catalog);
  exit long when low < lowest low of prior `exit length` bars (15). Shorts mirror.
  Medium complexity adds either a volatility filter on entries (prior bar's true range < ATR x `atr factor`) or an
  ATR stop (exit long if close < entry - ATR x `atr stop factor`); high complexity uses both. Default factor values
  and ATR length are not stated on the reference page (unverified).
- TradeStation: buy stop next bar at highest high(20) + 1 tick; no other conditions.
- Donchian 4-week rule: buy above the highs of the previous 4 full weeks; sell below the prior 4-week lows.

## Why it should work
Time-series momentum: a new N-bar high says recent buyers are all in profit and supply above is thin. Counterparties
are range traders selling resistance. On single stocks, evidence is weak at short horizons (see below).

## When it works and when it fails
Works in strong, persistent trends. Fails in ranges (repeated false breaks) and after long declines (first 20-day high
off a bottom is usually a bear-market rally).

## Parameters and sensitivity
Entry 20-55; exit 10-20; ATR stop 2-3; volatility filter on/off. Trap: picking the (entry, exit) pair with the best
in-sample Sharpe; keep 40/15 (Cagigas) and 20/10 as fixed variants.

## Evidence
- Platform strategies publish no statistics (grades none/D).
- Brock, Lakonishok & LeBaron (1992) found trading-range-break rules profitable on the DJIA 1897-1986; Sullivan,
  Timmermann & White (1999) show the best rules fail out of sample after 1986 once data snooping is accounted for
  (catalog E41; not re-read this run).
- On stocks, long-only all-time-high breakouts with wide ATR trails were positive in Wilcox & Crittenden (2005; see
  `turtle_breakout_systems`), but with ~305-day average holds, not swing horizons.

## Common mistakes
Including the current bar in the channel (look-ahead; the channel must be prior bars); stop-and-reverse versions that
are always in the market; ignoring gaps through the channel.

## Discretionary parts
None.

## Implementation spec for swing-engine
- Features (new, prior-bar windows; `_base.RollingSpec(column, fn, window, prior=True)` already produces
  `prior_max_high_N` / `prior_min_low_M`): `dc_high_40` = max(high, 40) over the 40 bars before as-of; `dc_low_15`.
- Signal (close-based variant, needs no new hook): close > `dc_high_40` and `trend_state >= 0`; entry next open.
- Stop-entry variant (true to the rule): buy stop at `dc_high_40` + 0.05 x `atr_14` placed for the next session;
  needs the stop-entry hook.
- Initial stop = max(`dc_low_15`, entry - 2 x `atr_14`); exit rule (`should_exit`) when low < `dc_low_15` (prior 15
  bars, recomputed daily). No target, `min_reward_risk: 0`; `max_hold_days: 40`.
- Reuses: `RollingSpec`, `atr_14`, `trend_state`, `high_52w` analog.
- Missing: stop-entry hook (variant B only).

## What the router should know
Breakout family; healthy_uptrend only. Its job is to be the baseline: if `breakout_52w` (volume gate, near 52w high)
does not beat plain 40/15, the extra gates are not adding value.

## Signs of decay to monitor
Rolling 12-month expectancy in R; false-break rate (exit within 5 bars at a loss).

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/Donchian
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/price_channel_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/price_channel_se_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://ru.tradingview.com/support/solutions/43000599890
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/swing-charting

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 5875 | 35 | 54% | +0.06 | +0.01 | 51% | +0.10 | +0.05 | 50% | +0.35 | +0.30 | 1.74 |
| correction | 639 | 3 | 63% | +0.19 | +0.16 | 59% | +0.17 | +0.14 | 50% | +0.17 | +0.14 | 1.37 |
| healthy_uptrend | 26903 | 155 | 46% | -0.04 | -0.10 | 43% | -0.03 | -0.08 | 37% | +0.04 | -0.01 | 1.07 |
| high_vol_selloff | 1347 | 7 | 47% | -0.09 | -0.13 | 40% | -0.16 | -0.20 | 31% | -0.26 | -0.30 | 0.61 |
| narrow_uptrend | 1095 | 9 | 39% | -0.12 | -0.16 | 38% | -0.14 | -0.18 | 31% | -0.21 | -0.25 | 0.69 |
| **all** | 35859 | 209 | 48% | -0.03 | -0.08 | 45% | -0.01 | -0.06 | 39% | +0.08 | +0.03 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 17450 | 43 | 47% | -0.08 | -0.12 | 45% | -0.07 | -0.11 | 39% | -0.06 | -0.10 | 0.90 |
| correction | 12015 | 31 | 49% | -0.03 | -0.06 | 49% | +0.01 | -0.02 | 40% | -0.09 | -0.12 | 0.84 |
| healthy_uptrend | 87426 | 354 | 49% | -0.00 | -0.05 | 46% | -0.00 | -0.05 | 39% | -0.02 | -0.07 | 0.96 |
| high_vol_selloff | 8005 | 39 | 49% | -0.02 | -0.06 | 45% | -0.10 | -0.13 | 40% | -0.09 | -0.13 | 0.85 |
| narrow_uptrend | 11251 | 34 | 51% | +0.04 | -0.01 | 50% | +0.08 | +0.03 | 44% | +0.11 | +0.07 | 1.21 |
| **all** | 136147 | 501 | 49% | -0.01 | -0.06 | 46% | -0.01 | -0.05 | 39% | -0.03 | -0.07 | 0.96 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
