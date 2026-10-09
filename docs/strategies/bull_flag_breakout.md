---
slug: bull_flag_breakout
name: Bull flag / high-tight flag breakout (Schwab Learn, Katsanos flags, O'Neil HTF)
originators: [Markos Katsanos (S&C, Dec 2014), Charles Schwab (Schwab Learn), William O'Neil (high tight flag), Thomas Bulkowski (statistics)]
category: pattern_breakout
decision: implement_disabled_for_comparison
holding_period_days: [3, 40]
timeframe: daily        # Katsanos rules were written for intraday bars
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null   # Bulkowski bull flags: 44% break-even failure, measured without stops
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built        # the RS-gated sibling qullamaggie_flag exists (shadow_only)
---

# Bull flag / high-tight flag breakout

## One-line summary
Buy the break above a short, shallow, declining-volume consolidation (flag) that follows a steep advance (pole);
target a fraction of the pole. This card is the generic flag, run as a comparison against the RS-filtered
`qullamaggie_flag`.

## Origin and lineage
Flags and pennants are classic Edwards & Magee continuation patterns. O'Neil's high tight flag (pole 90-120%+ in
<= 8 weeks, 10-25% flag) is the extreme case (docs/methods/04, 05). Katsanos formalised flag geometry in ATR units
("Detecting Flags in Intraday Charts", S&C Dec 2014), shipped by thinkorswim as IntradayFlagFormationStrat. Schwab
Learn teaches a discretionary swing version.

## Exact rules
- Katsanos / thinkorswim (defaults): pole height >= 5.5 x ATR formed in <= 23 bars; flag width <= 2.5 x ATR and
  <= 15 bars; prior uptrend persisting >= 70 bars; previous flag >= 50 bars ago; ATR changed by >= 5% during the
  formation; enter when flat on a breakout of the flag. Exits: target 1.2 x pole height; stop or trailing stop;
  inactivity exit (favourable advance < 4 x ATR within 70 bars); max 100 bars.
- Schwab Learn: pole = strong rally on high volume (example +23% in ~3 weeks); flag = drifting/declining channel on
  falling volume retracing about half the pole; buy the break above the flag channel on rising volume; stop just below
  flag support; target B = breakout + 1/2 pole (take partial), target A = breakout + full pole.
- High tight flag (docs/methods/04): pole ~90-120%+ in <= 8 weeks, then a 10-25% flag of 1-3 (max ~5) weeks above the
  50-day MA.
- Zanger (docs/methods/04): flag = lower highs and lower lows in parallel lines slanting against the trend, <= 3 weeks.

## Why it should work
Momentum continuation: a pole is a burst of demand (often news-driven); a tight, low-volume flag shows little supply
from early holders. The break releases pent-up demand. The other side: profit-takers from the pole and shorts who
read the pole as overextended.

## When it works and when it fails
Works in leaders in a healthy uptrend with broad participation. Fails when breakouts fail broadly (doc 04: failure
rates 2-4x higher in 2003-07 than the 1990s; practitioner reports of breakouts failing since Mar 2026), and in flags
that are deep or loose, or form below the 50-day.

## Parameters and sensitivity
Pole size (ATR multiple or %), pole bars, flag max bars (10-40 daily), flag depth (<= 25% or <= 2.5 ATR), volume
dry-up, breakout rvol. Trap: many geometric knobs; fix them from sources before replay, do not tune.

## Evidence
- Bulkowski bull flags (flags.html, stats updated 27 Aug 2020): break-even failure 44%, average rise 9%, measure rule
  met 46%, measured breakout-to-ultimate-high with no stops (descriptive only).
- Bulkowski high tight flags: rank 30/39, failure 15%, average rise 39%, n=1,028; about +22% after 1 month and +21%
  after 2 months (catalog). Perfect-trade measurement inflates results; the site says the 2020 tables are outdated.
- Katsanos 2014: in-sample illustration in a practitioner magazine; thinkorswim publishes no performance.
- Schwab: illustrative example only.

## Common mistakes
Buying loose, deep or V-shaped flags; buying extended (> 1 ADR above the flag high); flags below the 50-day; no
market filter.

## Discretionary parts and how to make them mechanical
"Pole on high volume": mean `rvol_day` over the pole bars >= 1.3. "Falling volume in the flag": mean volume in the
flag < mean volume in the pole. "Channel break": close > flag high (pivot), as `patterns2.flag()` defines it.

## Implementation spec for swing-engine
- Reuse `features/patterns2.py::flag(high, low, end, max_bars)`: consolidation since the highest high of the last
  `max_bars` bars; `pivot` = that high, `depth` = (pivot - flag low)/pivot, `higher_lows` flag. Reuse
  `prior_advance` for pole gain, `atr_14`, `rvol_day`, `sma_50`, `trend_state`.
- What `qullamaggie_flag` actually does (for the comparison): RS rank >= 0.98, pole >= 30% within 42 bars, ADR >= 5%,
  flag 10-40 bars, depth <= 25%, higher lows, rising sma_10/sma_20, close > sma_20, close-above-pivot on rvol >= 1.5
  and <= 1 ADR extended; entry at next open; stop = entry-day low capped at 1 ADR; exit on close < sma_20; 10R
  reference target; max hold 60; requires market trend up.
- Generic bull flag (this card), daily translation of Katsanos: pole height (pivot - pole low) >= 5.5 x atr_14 within
  <= 23 bars; flag length 3-15 bars; flag height (pivot - flag low) <= 2.5 x atr_14; `trend_state >= 1` (stand-in for
  the 70-bar uptrend); no RS/ADR filter; close > pivot and close - pivot <= 1 x atr_14; rvol_day >= 1.2.
  Skip the "ATR changed >= 5%" rule (direction of change ambiguous in the description).
- Entry: next open (fits the backtester; Schwab/Katsanos imply a stop entry at the flag high, which needs the
  stop-entry hook to model exactly). Stop: flag low - 0.01, or entry-day low if tighter is wanted (param).
- Target: entry + 1.0 x pole height (Schwab A; Katsanos 1.2 x as variant). Partial at 0.5 x pole is not modelable
  (no scale-out hook). `max_hold_days: 40`; inactivity exit not modelled. `min_reward_risk: 2.0` (default) applies.

## What the router should know
Breakout family: `healthy_uptrend` only, same as `qullamaggie_flag`. The comparison question is whether the RS/ADR
gate adds value over the generic flag on identical dates.

## Signs of decay to monitor
Rolling 50-trade failure rate (stop before +1R) above 55%; average MFE in the first 5 bars shrinking.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/IntradayFlagFormationStrat
- https://www.schwab.com/learn/story/swing-trading-strategies
- https://sozai.app/transcript/powerful-swing-trading-setup-high-tight-flag/
- https://thepatternsite.com/BestPatterns.html
- https://thepatternsite.com/cup.html
- docs/methods/04-chart-pattern-base-breakouts.md, docs/methods/05-qullamaggie-breakout.md

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 138 | 2 | 49% | +0.03 | -0.10 | 51% | +0.03 | -0.10 | 47% | +0.30 | +0.17 | 1.66 |
| correction | 7 | 0 | 57% | +0.39 | +0.11 | 57% | +0.61 | +0.34 | 43% | +0.41 | +0.14 | 1.65 |
| healthy_uptrend | 591 | 5 | 51% | +0.05 | -0.05 | 48% | +0.11 | +0.01 | 45% | +0.28 | +0.18 | 1.53 |
| high_vol_selloff | 17 | 0 | 41% | -0.20 | -0.30 | 24% | -0.52 | -0.61 | 18% | -0.32 | -0.42 | 0.60 |
| narrow_uptrend | 35 | 0 | 30% | -0.27 | -0.34 | 31% | -0.16 | -0.23 | 31% | -0.10 | -0.17 | 0.84 |
| **all** | 788 | 7 | 49% | +0.03 | -0.08 | 48% | +0.08 | -0.03 | 44% | +0.26 | +0.15 | 1.49 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 305 | 1 | 51% | +0.04 | -0.07 | 53% | +0.06 | -0.06 | 44% | -0.06 | -0.17 | 0.90 |
| correction | 157 | 1 | 53% | -0.01 | -0.13 | 51% | +0.04 | -0.08 | 42% | +0.03 | -0.09 | 1.06 |
| healthy_uptrend | 2152 | 13 | 46% | -0.02 | -0.13 | 44% | -0.05 | -0.15 | 38% | -0.07 | -0.18 | 0.88 |
| high_vol_selloff | 118 | 1 | 44% | -0.12 | -0.25 | 44% | -0.13 | -0.26 | 33% | -0.20 | -0.32 | 0.68 |
| narrow_uptrend | 244 | 1 | 49% | +0.01 | -0.09 | 45% | +0.06 | -0.05 | 44% | +0.14 | +0.04 | 1.29 |
| **all** | 2976 | 17 | 47% | -0.02 | -0.13 | 45% | -0.03 | -0.13 | 39% | -0.05 | -0.16 | 0.91 |

Portfolio replay (net of costs, slots shared with its run): 3 trades, win 67%, avg +0.06R, PF 1.43, P&L $13 on $100k, avg hold 21.7 bars.
