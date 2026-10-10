---
slug: inside_outside_bar_breakout
name: Inside-bar and outside-bar breakouts (thinkorswim, TradeStation, TradingView, Williams/Crabel)
originators: [Larry Williams, Toby Crabel, thinkorswim/TradeStation/TradingView built-ins]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 10]
timeframe: daily
direction: both
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Inside-bar and outside-bar breakouts

## One-line summary
Trade the break of a one-bar range-contraction (inside bar) or range-expansion (outside bar) in the direction of
the trend; a comparison baseline, not a primary setup.

## Origin and lineage
- Classic bar patterns catalogued by Larry Williams (inside days ~7.6% of 50,692 commodity sessions per the catalog
  entry) and Toby Crabel (range contraction: NR4/NR7, ID/NR4, *Day Trading with Short Term Price Patterns*, 1990).
- Shipped as demonstration strategies: thinkorswim InsideBarLE/SE, TradeStation Inside Bar LE/SE and Outside Bar
  LE/SE, TradingView "InSide Bar" and "OutSide Bar". None publishes performance.

## Exact rules
Two families exist and must be kept apart in replay:
1. **Broker built-in (close-direction) version** (thinkorswim, TradingView):
   inside bar `H < H[1] and L > L[1]`; if `C > O` buy next bar (market), if `C < O` short next bar. No stop/target
   in the entry script; tos pairs it with ProfitTargetLX / StopLossLX.
2. **TradeStation Outside Bar LE**: `L < L[1] and H > H[1] and C > O` -> buy next bar.
3. **Classic breakout version** (Williams/Crabel lineage, practitioner standard): after an inside bar, buy stop
   1 tick above the inside-bar high (or mother-bar high), protective stop below the inside-bar low (or mother-bar
   low); trade only in the trend direction, optionally only when the inside bar is also NR4/NR7. Outside bar: a
   bullish outside bar closing near its high -> buy above its high.
- Targets/trailing as taught: none standardised. Sizing: none specified by any source.

## Why it should work
Range contraction concentrates resting orders just outside a small range; when one side is taken, stops and
breakout entries cascade (volatility clustering: small ranges tend to be followed by larger ones). The counterparty
is the range trader / short-term mean-reverter selling the top of the small range. Note that volatility expansion
is predicted, direction is not.

## When it works and when it fails
- Works: trending names with the break in trend direction; low-vol pauses inside a strong uptrend.
- Fails: choppy tapes (false breaks both ways), news-driven gaps through the stop, illiquid names where the
  inside bar is noise.

## Parameters and sensitivity
| Knob | Range | Trap |
|---|---|---|
| reference bar for trigger/stop | inside bar vs mother bar | mother bar doubles risk; pick one before replay |
| NR filter | none / NR4 / NR7 | NR7 cuts signal count ~5x; small samples |
| trend filter | trend_state >= 0 / == 1 | testing both directions and keeping the best = selection bias |
| trigger window | 1-3 bars after the inside bar | longer windows turn it into a generic breakout |
| max_hold_days | 3-10 | |

## Evidence
- No robust stand-alone test of inside/outside-bar breakouts was verified (catalog grade D). The NR7 / ID-NR4
  tests are the closest relatives (catalog: grade C); specific numbers could not be re-verified this run (the
  QuantifiedStrategies NR7 post returned 404).
- Broker and TradingView strategies are demonstrations with no published statistics.

## Common mistakes
- Treating the close-direction built-in as the same rule as the breakout rule.
- Counting an inside bar on a gap/news day; ignoring that daily bars cannot see which side broke first intraday.

## Discretionary parts and how to make them mechanical
"In the trend direction" -> `trend_state == 1` for longs. "Near its high" for outside bars -> `close_pos >= 0.75`.

## Implementation spec for swing-engine
- Reuse: `inside_day` (features/patterns.py: `high < prev_high and low > prev_low`), `trend_state`, `atr_14`,
  `close_pos`, `range_pct`.
- Missing: `outside_day = high > prev_high and low < prev_low`; `nr7 = range == min(range over last 7 bars)`
  and `nr4` (also requested by docs/methods/09).
- Long (breakout variant): setup bar `t-1` has `inside_day == 1` (optionally `nr7 == 1`) and `trend_state == 1`;
  trigger on as-of bar `t`: `close_t > high_{t-1}`; entry = next open; stop = `low_{t-1} - 0.0 * atr_14`;
  target = entry + 2R; `max_hold_days = 5`; `min_reward_risk = 2.0`.
- Built-in variant (for comparison only): `inside_day == 1 and close > open` -> buy next open, stop = inside-bar low.
- Outside-bar variant: `outside_day == 1 and close > open and close_pos >= 0.75` -> trigger close > that bar's
  high within 2 bars; stop = outside-bar low.
- Gap: the taught entry is a buy-stop; the engine has no stop-entry order hook on daily bars, so close-trigger +
  next-open fill overstates risk and lags entry.

## What the router should know
Allow only in `healthy_uptrend` at reduced risk if ever enabled; disabled for comparison now.

## Signs of decay to monitor
Win rate of trend-direction breaks falling to that of counter-trend breaks; median follow-through (MFE in R)
< 1R over 5 bars.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/InsideBarLE
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/outside_bar_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/inside_bar_le_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://catalogimages.wiley.com/images/db/pdf/0471297224.pdf
- https://www.luxalgo.com/library/concept/inside-bar/

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4246 | 1787 | 33% | -0.22 | -0.60 | 31% | -0.22 | -0.60 | 30% | -0.22 | -0.60 | 0.72 |
| correction | 383 | 161 | 37% | -0.10 | -0.64 | 37% | -0.09 | -0.63 | 36% | -0.08 | -0.62 | 0.88 |
| healthy_uptrend | 19125 | 8156 | 33% | -0.22 | -0.62 | 31% | -0.23 | -0.62 | 31% | -0.23 | -0.62 | 0.72 |
| high_vol_selloff | 1415 | 570 | 39% | -0.14 | -0.53 | 38% | -0.13 | -0.53 | 37% | -0.13 | -0.53 | 0.84 |
| narrow_uptrend | 1687 | 693 | 34% | -0.21 | -0.58 | 34% | -0.15 | -0.52 | 33% | -0.16 | -0.53 | 0.79 |
| **all** | 26856 | 11367 | 34% | -0.21 | -0.61 | 32% | -0.21 | -0.61 | 31% | -0.21 | -0.61 | 0.73 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 12383 | 5073 | 39% | -0.04 | -0.41 | 37% | -0.02 | -0.39 | 36% | -0.01 | -0.38 | 0.99 |
| correction | 4829 | 1865 | 35% | -0.16 | -0.61 | 33% | -0.15 | -0.60 | 32% | -0.17 | -0.61 | 0.78 |
| healthy_uptrend | 74274 | 30894 | 34% | -0.16 | -0.56 | 32% | -0.16 | -0.56 | 31% | -0.16 | -0.56 | 0.79 |
| high_vol_selloff | 8908 | 3795 | 37% | -0.11 | -0.56 | 35% | -0.08 | -0.54 | 34% | -0.08 | -0.53 | 0.90 |
| narrow_uptrend | 11142 | 4317 | 38% | -0.10 | -0.48 | 36% | -0.08 | -0.47 | 35% | -0.08 | -0.47 | 0.89 |
| **all** | 111536 | 45944 | 35% | -0.14 | -0.54 | 33% | -0.13 | -0.53 | 32% | -0.13 | -0.53 | 0.83 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
