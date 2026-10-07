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
_Pending: filled in from swing replay on real data._
