---
slug: bollinger_w_bottom_ii_reversal
name: Bollinger Method III (Intraday Intensity reversals) and W-bottoms
originators: [John Bollinger]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [3, 15]
timeframe: daily
direction: long (sell alerts mirror; engine long-only)
regimes_good: [choppy, narrow_uptrend, healthy_uptrend]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Bollinger Method III and W-bottoms

## One-line summary
A lower-band tag while volume-weighted close location (Intraday Intensity) is positive is a buy **alert**. A W-bottom is
a first low at or below the lower band and a retest that holds inside the band. Buy the confirmation (a strong
up bar, or a break above the middle peak of the W), stop under the retest low, and exit at the mid or upper band.

## Origin and lineage
John Bollinger, *Bollinger on Bollinger Bands* (2001), "Method III" (reversals confirmed by a volume indicator), plus
his W-bottom pattern work, which builds on Arthur Merrill's M and W shapes. The rule summary in the catalog comes from Bollinger's
own PDF and bollingerbands.com. His published rules say tags are not signals and closes outside
the bands are initially continuation signals. That is why Method III requires a non-confirming indicator.

## Exact rules
- **Bands:** BB(20, 2) on close.
- **Intraday Intensity:** II_t = (2C - H - L)/(H - L) * V. II% = 21-day sum of II / 21-day sum of V * 100. The
  normalisation is **unverified**: the catalog says "21-day normalised II%", and the exact form was not in the excerpt read.
- **Buy alert:** the low tags or pierces the lower band while II% > 0 (accumulation despite the low price).
- **Confirmation (trigger):** a strong up bar after the alert (close > prior high is one coding; the source wording
  is qualitative).
- **W-bottom variant:** low #1 closes at or outside the lower band (%b <= 0). There is a reaction rally to an intervening
  peak. Low #2 makes a similar or lower price but holds inside the band (%b > 0, i.e. higher %b). Buy on the break above
  the intervening peak.
- **Initial stop:** below the retest (second) low.
- **Exit:** the mid band (conservative) or the upper band. Bollinger's sell side mirrors this: an upper-band tag with II% < 0.
- **Sizing:** not specified.

## Why it should work
A volume-confirmed non-confirmation: price makes a new low, but closes land in the upper half of the daily range
on volume, which suggests buyers are absorbing supply. The W's higher %b on the retest shows weaker downside
momentum. Sellers who chase the band break are the other side.

## When it works and when it fails
It works at the end of pullbacks in stocks above a rising 200-day, and in ranges. It fails in liquidation trends where every
bounce is sold (II stays positive on short-covering days). A W in a stock that is breaking a long-term base is a bear flag.

## Parameters and sensitivity
- BB length and width (20/2), II% window (21), and the confirmation definition. Bollinger suggests 10-period bands for
  short-term work and 50 for long-term, with 1.9 / 2.1 SD widths (book recollection, **unverified** this run).
- W geometry: maximum bars between lows (10-30), tolerance for "similar" low (+/-1 ATR). This is the main overfitting surface.

## Evidence
No independent test of Method III or the W-bottom rule was found (catalog grade D). Lento et al. (2007) tested
plain band rules only (they did not beat buy-and-hold after costs; contrarian versions did better). There are no post-publication data.

## Common mistakes
- Buying the tag itself (Bollinger: "tags are not signals").
- Drawing W-bottoms after the fact. The second low must be confirmed by the peak break, not by hindsight.
- Ignoring that a close below the band is a continuation signal at first.

## Discretionary parts and how to make them mechanical
- "Strong up bar": close > prior high and close_pos > 0.7.
- W detection: use pivot lows (`features/levels.py` pivot width 5) and require pivot1 %b <= 0, pivot2 %b > 0,
  pivot2 low within 1*atr_14 of pivot1 low (or lower), and 5-30 bars apart. The trigger is close > max(high) between the pivots.

## Implementation spec for swing-engine
- Reuses `bb_upper_20`, `bb_lower_20`, `sma_20`, `close_pos`, `atr_14`, `sma_200`, and the pivot machinery in `features/levels.py`.
- New features: `pct_b_20 = (close - bb_lower_20)/(bb_upper_20 - bb_lower_20)`; `ii = (2*close - high - low)/(high - low)*volume`
  (0 when high == low); `ii_pct_21 = sum21(ii)/sum21(volume)*100`. These fit the catalog's `volume_flow_indicators` item.
- Entry: Method III enters at the next open after a confirmation close (the backtester supports this today). The W-break wants a buy-stop at
  the intervening peak; the **stop-entry hook is missing**, so use the next open after a close above the peak.
- Stop: retest low - 0.1*atr_14. Target: `bb_upper_20` at signal time (fixed), with a `close > sma_20` partial as a variant.
- `max_hold_days` 15; `min_reward_risk` 1.5 (the stop is structural, so R:R is meaningful).
- Missing: `pct_b_20`, `ii_pct_21`, W-pattern detector, stop-entry hook.

## What the router should know
It is a low-frequency reversal setup with a real structural stop, unlike the Connors family. It is allowed in uptrends and
choppy tapes. Treat it as the same "mean reversion" bucket for exposure caps.

## Signs of decay to monitor
Rising share of W triggers that fail back below the retest low within 5 bars. II% filter no longer separating winners from losers (compare
win rate with II% > 0 vs <= 0 in replay).

## Sources
- https://www.bollingerbands.com/_files/ugd/58be43_377f4254baa04a19aaadb1735b45b6f0.pdf
- https://www.bollingerbands.com/bollinger-band-rules
- https://ideas.repec.org/a/taf/raflxx/v3y2007i4p263-267.html

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 803 | 8 | 40% | -0.12 | -0.19 | 39% | -0.09 | -0.16 | 35% | -0.05 | -0.12 | 0.92 |
| correction | 63 | 1 | 48% | +0.03 | -0.01 | 56% | +0.34 | +0.30 | 53% | +0.50 | +0.46 | 2.13 |
| healthy_uptrend | 1357 | 12 | 46% | +0.02 | -0.05 | 42% | +0.05 | -0.02 | 36% | +0.04 | -0.03 | 1.06 |
| high_vol_selloff | 640 | 23 | 45% | -0.02 | -0.06 | 56% | +0.17 | +0.14 | 45% | +0.16 | +0.13 | 1.33 |
| narrow_uptrend | 211 | 3 | 34% | -0.18 | -0.26 | 34% | -0.19 | -0.28 | 27% | -0.21 | -0.30 | 0.69 |
| **all** | 3074 | 47 | 44% | -0.04 | -0.10 | 44% | +0.03 | -0.03 | 38% | +0.04 | -0.03 | 1.06 |

Portfolio replay (net of costs, slots shared with its run): 3 trades, win 33%, avg +0.24R, PF 1.36, P&L $246 on $100k, avg hold 6.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2026 | 20 | 49% | +0.06 | +0.00 | 48% | +0.18 | +0.12 | 45% | +0.31 | +0.25 | 1.57 |
| correction | 1516 | 8 | 49% | +0.02 | -0.03 | 40% | -0.06 | -0.11 | 35% | +0.02 | -0.03 | 1.03 |
| healthy_uptrend | 4493 | 42 | 45% | -0.01 | -0.07 | 38% | -0.03 | -0.10 | 34% | -0.03 | -0.09 | 0.95 |
| high_vol_selloff | 2977 | 120 | 41% | -0.08 | -0.12 | 43% | -0.02 | -0.06 | 41% | +0.08 | +0.04 | 1.15 |
| narrow_uptrend | 1516 | 10 | 45% | +0.02 | -0.04 | 42% | +0.05 | -0.01 | 39% | +0.11 | +0.06 | 1.18 |
| **all** | 12528 | 200 | 45% | -0.01 | -0.06 | 42% | +0.01 | -0.04 | 38% | +0.07 | +0.02 | 1.12 |

Portfolio replay (net of costs, slots shared with its run): 71 trades, win 32%, avg -0.01R, PF 0.97, P&L $-1,505 on $100k, avg hold 7.3 bars.
