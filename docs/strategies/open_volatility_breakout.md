---
slug: open_volatility_breakout
name: Open +/- k x range volatility breakout (Williams volatility breakout / GSV, Crabel stretch)
originators: [Larry Williams, Toby Crabel]
category: volatility_breakout
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily (entry intraday off the open)
direction: long            # originals are OCO both sides; swing-engine strategies are long-only
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built          # needs a same-day stop-entry-off-the-open hook
---

# Open +/- k x range volatility breakout

## One-line summary
Each morning place a buy stop at today's open plus a fraction of recent range (or "noise"); if price travels that far
from the open, ride the expansion for a few days with the opposite level as the stop.

## Origin and lineage
Larry Williams, *Long-Term Secrets to Short-Term Trading* (1999), ch. 4: volatility breakout and Greatest Swing Value
(GSV). Toby Crabel (1990; S&C "Opening Range Breakout" series 1988-89): open +/- "stretch", used mainly after
contraction days (NR4, NR7, ID/NR4; see `nr7_nr4_range_contraction.md`).

## Exact rules
- Williams volatility breakout: buy stop at `open_t + k x range_{t-1}` (range = high-low or true range); sell stop at
  `open_t - k x range_{t-1}`. k is chosen by testing; broker adaptations use 0.25, a Korean retail version 0.5-0.6.
  Williams' own k values were not read.
- Williams GSV: per day, if close > open the "swing" = open - low, if close < open it = high - open; GSV = SMA_N of
  that x a multiple; stops at open +/- GSV.
- Crabel stretch: `noise_i = min(high_i - open_i, open_i - low_i)`; stretch = SMA10(noise) (x multiple); stops at
  open +/- stretch.
- OCO: the first filled is the position, the other is its protective stop.
- Exits: protective stop; N-day time exit; Williams' bailout = exit at the first profitable opening.
- Sizing: not taught in the material read.

## Why it should work
Most days the price wanders a "normal" distance from the open (noise). A move beyond that suggests directional
order flow (institutional programmes working through the day). The other side: intraday mean-reversion traders
fading the open drive.

## When it works and when it fails
Works after contraction days and in trending futures (its home market). Fails in choppy names, on gap-and-reverse
days, and wherever costs on a 1-5 day hold eat the small average gain; methods.md notes intraday ORB in stocks nets
about 0 after costs.

## Parameters and sensitivity
k 0.25-1.0; noise window 4-10; hold 1-10 days; contraction pre-filter on/off. Trap: k fitted per symbol; ignoring
both-stops-hit days.

## Evidence
- Oxford Capital Strategies benchmarked ORB / GSV variants on 42 futures, 1980-2011, with sensitivity grids (numbers
  not captured in the catalog; not re-read here).
- No stock swing test located. No peer-reviewed study.

## Common mistakes
Using the prior close instead of today's open; assuming fills at the stop on gap opens (fill is the open when it gaps
through); not modelling days when both stops trade.

## Discretionary parts and how to make them mechanical
All mechanical; only k and the exit need fixing in advance.

## Implementation spec for swing-engine
- Features (new): `crabel_noise = min(high-open, open-low)`; `stretch_10 = sma(crabel_noise,10)` as of t-1;
  `gsv_up` per Williams; `range_prev = high_{t-1} - low_{t-1}`.
- Signal at close t-1 carries `trigger_offset = k x range_prev` (or `stretch_10`), not a price; the trigger price
  `open_t + offset` is known only at the open.
- **Missing hook**: entry type "stop off the open": fill if `high_t >= open_t + offset` at `open_t + offset`
  (the open is never above it by construction); protective stop `open_t - offset`. If `low_t <= open_t - offset` as
  well, assume the worst order (stopped the same day). Live execution needs an order placed after the 9:30 print.
- Exits: bailout at the first open above entry (needs an at-open exit hook), else `max_hold_days: 5`.
- Target: none -> `min_reward_risk: 0.0`. Pre-filter variant: only after `nr7` or `id_nr4` at t-1.
- Reuses: `trend_state`, `atr_14`, `inside_day`.

## What the router should know
Comparison only; untested on stocks. `healthy_uptrend` only if ever enabled.

## Signs of decay to monitor
Net expectancy per trade below round-trip cost; same-day stop-outs above 40%.

## Sources
- https://oxfordstrat.com/trading-strategies/greatest-swing-value/
- https://whselfinvest.com/en-be/trading-platform/free-trading-strategies/tradingsystem/56-volatility-break-out-larry-williams-free
- https://catalogimages.wiley.com/images/db/pdf/0471297224.pdf
- https://oxfordstrat.com/?p=4761
- https://store.traders.com/-v06-c09-playing-pdf.html

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 35714 | 18331 | 37% | -0.12 | -0.42 | 30% | -0.12 | -0.41 | 23% | -0.05 | -0.34 | 0.95 |
| correction | 2916 | 1472 | 31% | -0.28 | -0.72 | 27% | -0.27 | -0.71 | 20% | -0.30 | -0.74 | 0.67 |
| healthy_uptrend | 162553 | 83709 | 35% | -0.10 | -0.43 | 28% | -0.12 | -0.44 | 21% | -0.06 | -0.38 | 0.94 |
| high_vol_selloff | 12512 | 6464 | 37% | -0.11 | -0.45 | 27% | -0.24 | -0.58 | 17% | -0.35 | -0.68 | 0.65 |
| narrow_uptrend | 14877 | 7957 | 31% | -0.27 | -0.57 | 24% | -0.34 | -0.65 | 18% | -0.39 | -0.69 | 0.58 |
| **all** | 228572 | 117933 | 35% | -0.12 | -0.44 | 28% | -0.14 | -0.46 | 21% | -0.09 | -0.41 | 0.90 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 105410 | 51158 | 40% | -0.03 | -0.32 | 35% | +0.05 | -0.24 | 28% | +0.12 | -0.18 | 1.15 |
| correction | 42967 | 21674 | 37% | -0.14 | -0.48 | 30% | -0.15 | -0.49 | 24% | -0.13 | -0.47 | 0.85 |
| healthy_uptrend | 594014 | 305771 | 35% | -0.12 | -0.43 | 28% | -0.12 | -0.43 | 22% | -0.12 | -0.43 | 0.86 |
| high_vol_selloff | 73056 | 37952 | 36% | -0.14 | -0.47 | 30% | -0.14 | -0.48 | 23% | -0.18 | -0.52 | 0.78 |
| narrow_uptrend | 97975 | 48491 | 39% | -0.05 | -0.36 | 32% | -0.04 | -0.35 | 25% | -0.05 | -0.36 | 0.94 |
| **all** | 913422 | 465046 | 36% | -0.10 | -0.42 | 30% | -0.09 | -0.41 | 23% | -0.09 | -0.40 | 0.90 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
