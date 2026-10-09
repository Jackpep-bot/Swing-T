---
slug: classic_pattern_detector_lmw
name: Objective chart-pattern detector (Lo-Mamaysky-Wang kernel regression) standing in for vendor pattern engines
originators: [Andrew Lo, Harry Mamaysky, Jiang Wang, Thomas Bulkowski (statistics), Trading Central/Recognia, thinkorswim, Finviz (vendors)]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [5, 60]
timeframe: daily
direction: both
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Objective chart-pattern detector (LMW)

## One-line summary
Replace unpublished vendor pattern engines (thinkorswim, Recognia/Trading Central, Finviz) with the published
Lo-Mamaysky-Wang kernel-regression detector for 10 classic patterns, then trade breakouts from them with fixed rules.

## Origin and lineage
- Lo, Mamaysky & Wang, "Foundations of Technical Analysis", *Journal of Finance* 55(4), 2000 (NBER w7613).
- Vendor engines whose algorithms are unpublished: thinkorswim Classic Patterns (sliders 0-5 for trend strength,
  breakout strength, volume, uniformity, clarity), Recognia/Trading Central Technical Events (classic patterns
  > 12 days; Fidelity screen requires >= 35 days of formation, close >= $3 bullish / $5 bearish, volume >= 50k),
  Finviz pattern signals.
- Bulkowski (*Encyclopedia of Chart Patterns*, thepatternsite.com): descriptive statistics used as priors only.

## Exact rules (LMW detector)
1. Window: rolling 38 bars (35 + 3-bar lag so the last extremum is confirmed).
2. Smooth closes with a Nadaraya-Watson Gaussian kernel; bandwidth = 0.3 x the cross-validated optimum.
3. Local extrema = sign changes of the smoothed series' slope; map each back to the actual max/min close nearby.
4. Patterns on the last 5 alternating extrema E1..E5 (examples as summarised in the catalog):
   - Head-and-shoulders: E1 max, E3 > E1 and E3 > E5, E1 and E5 within 1.5% of their average, E2 and E4 within 1.5%.
   - Inverse H&S: mirror.
   - Rectangle top/bottom: tops within 0.75% of their average, bottoms within 0.75%, lowest top > highest bottom.
   - Double top/bottom: two extrema within 1.5%, at least 22 bars apart.
   - Also broadening and triangle tops/bottoms (10 patterns total).
5. LMW measured conditional 1-day returns after detection; they did not specify a trading rule.
- Trading layer (ours, not LMW): breakout = close beyond the neckline / rectangle edge; target = pattern height
  projected from the breakout (vendor and Finviz convention); stop = opposite side of the last swing.

## Why it should work
Patterns are a crude proxy for supply/demand zones and for crowds of pattern traders (Osler 1998 shows their
volume footprint). Any edge comes from momentum after the breakout, not the shape itself.

## When it works and when it fails
Bullish continuation patterns in uptrends are the most plausible use. Reversal patterns (H&S) were unprofitable to
trade in Osler's study. Fails in noisy, gap-driven names.

## Parameters and sensitivity
Bandwidth multiplier (0.3 is LMW's hand-picked choice), window (38), tolerance (0.75-1.5%), min spacing (22).
Trap: many knobs x 10 patterns x both directions = huge trial count; deflate Sharpe accordingly.

## Evidence
- LMW 2000: US stocks 1962-96; conditional return distributions after several patterns differ from unconditional
  ones, more so on Nasdaq ("incremental information"); no profitable trading rule shown.
- Osler (FRBNY Staff Report 42, Feb 1998): 100 random US stocks, Jul 1962-Dec 1993; H&S appears roughly once a year
  per stock; volume peaks about 11% higher on the neckline-cross day; H&S trading unprofitable; price effects gone
  within two weeks.
- Bulkowski: 30,000+ samples; cup-with-handle rank 3 of 39, 5% failure, +54% average rise; failure rates doubled
  in 2003-07 vs the 1990s; measured to the ex-post ultimate high with no stops/costs (inflated); site says the
  statistics are outdated (Sept 2021). Grade D, priors only.

## Common mistakes
Eyeballing patterns; measuring to the ultimate high; counting a pattern before its last extremum is confirmed
(look-ahead from the kernel's two-sided smoothing - the 3-bar lag exists to prevent it).

## Discretionary parts and how to make them mechanical
The whole point: the kernel detector is the mechanical replacement. Keep breakout volume (`rvol_day >= 1.5`) as an
optional filter, logged as a trial.

## Implementation spec for swing-engine
- New `features/patterns3.py`: `kernel_smooth(close, h)` causal per window ending at t-3; `extrema(...)`;
  pattern flags `pat_hs, pat_ihs, pat_rect_top, pat_rect_bot, pat_dtop, pat_dbot, pat_btop, pat_bbot, pat_ttop,
  pat_tbot`, plus `pat_neckline`, `pat_height`. Must pass the shift test (no look-ahead).
- Reuse: `features/levels.py` pivots as a cross-check, `rvol_day`, `atr_14`, `trend_state`, existing geometry
  detectors in `features/patterns2.py` (flat base, cup-with-handle, flag) for the bullish continuation cases.
- Long trade (pattern-breakout module): bullish pattern (`pat_ihs`, `pat_dbot`, `pat_rect_bot` breakout up) detected
  within 10 bars; trigger `close > pat_neckline`; entry next open; stop = max(last swing low, entry - 2 x atr_14);
  target = neckline + pat_height; `max_hold_days = 30`; `min_reward_risk = 2.0`.
- Compute cost: kernel per symbol per window is O(38^2); vectorise or limit to liquid universe.

## What the router should know
Breakout family; `healthy_uptrend` only. Per-pattern results must be reported separately.

## Signs of decay to monitor
Breakout failure rate (move < 5% after breakout, Bulkowski's definition) rising; target hit rate falling.

## Sources
- https://www.nber.org/system/files/working_papers/w7613/w7613.pdf
- https://www.newyorkfed.org/research/staff_reports/sr42.html
- https://thepatternsite.com/BestPatterns.html
- https://thepatternsite.com/cup.html
- https://toslc.thinkorswim.com/center/howToTos/thinkManual/charts/Patterns/Using-Classic-Patterns
- https://investor.tradingcentral.com/about-us/technical-events
- https://research2.fidelity.com/fidelity/research/reports/release2/Research/Recognia.asp
- https://finviz.com/help/technical-analysis/charts-patterns.ashx

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 31 | 1 | 50% | -0.18 | -0.38 | 23% | -0.21 | -0.41 | 27% | -0.20 | -0.40 | 0.71 |
| correction | 8 | 0 | 38% | -0.15 | -0.40 | 12% | -0.40 | -0.65 | 25% | -0.29 | -0.54 | 0.59 |
| healthy_uptrend | 284 | 3 | 45% | -0.12 | -0.36 | 41% | -0.19 | -0.43 | 29% | -0.30 | -0.54 | 0.58 |
| high_vol_selloff | 21 | 0 | 57% | +0.23 | -0.06 | 24% | -0.21 | -0.50 | 24% | -0.25 | -0.54 | 0.67 |
| narrow_uptrend | 12 | 0 | 50% | -0.01 | -0.22 | 33% | -0.17 | -0.37 | 27% | -0.46 | -0.68 | 0.40 |
| **all** | 356 | 4 | 46% | -0.10 | -0.34 | 37% | -0.19 | -0.43 | 28% | -0.29 | -0.53 | 0.59 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 0%, avg -1.07R, PF 0.00, P&L $-138 on $100k, avg hold 1.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 108 | 0 | 48% | -0.00 | -0.28 | 47% | +0.03 | -0.24 | 41% | +0.03 | -0.24 | 1.05 |
| correction | 49 | 0 | 57% | +0.06 | -0.21 | 53% | +0.11 | -0.16 | 41% | +0.19 | -0.08 | 1.35 |
| healthy_uptrend | 628 | 6 | 46% | +0.02 | -0.20 | 46% | +0.08 | -0.14 | 38% | +0.07 | -0.15 | 1.11 |
| high_vol_selloff | 83 | 1 | 50% | +0.14 | -0.09 | 55% | +0.29 | +0.06 | 52% | +0.49 | +0.26 | 1.98 |
| narrow_uptrend | 85 | 1 | 56% | +0.23 | +0.00 | 52% | +0.21 | -0.02 | 43% | +0.20 | -0.02 | 1.36 |
| **all** | 953 | 8 | 48% | +0.05 | -0.18 | 48% | +0.10 | -0.12 | 40% | +0.12 | -0.11 | 1.20 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
