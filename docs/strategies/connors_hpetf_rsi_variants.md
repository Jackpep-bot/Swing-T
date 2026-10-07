---
slug: connors_hpetf_rsi_variants
name: Connors HPETF RSI(4) 25/75, Multiple Days Down, RSI 10/6
originators: [Larry Connors, Connors Research (High Probability ETF Trading, 2009)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 6]
timeframe: daily
direction: long (shorts mirror; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Connors HPETF RSI variants (RSI 25/75, Multiple Days Down, RSI 10/6)

> **Every threshold on this card comes from the catalog's recollection of the book and is unverified.** Verify against
> *High Probability ETF Trading* before any trial is logged.

## One-line summary
These are three more ETF pullback rules from the same book, all filtered by the 200-day SMA, bought at the close and exited on a bounce: RSI(4) < 25,
4 down closes out of 5 below the 5-day SMA, or RSI(2) < 10 (adding if < 6).

## Origin and lineage
*High Probability ETF Trading* (Connors Research, 2009), which also contains 3-Day High/Low, %b, R3 and TPS (separate
cards). EdgeRater Academy lists the book's strategies. The rules below were not confirmed there this run.

## Exact rules (unverified)
| Variant | Setup / trigger (close > SMA(200) in all) | Aggressive add | Exit |
|---|---|---|---|
| RSI 25/75 | RSI(4) closes < 25 | add if RSI(4) < 20 | RSI(4) > 55 |
| Multiple Days Down | close < SMA(5); down closes on 4 of the last 5 days | add on a lower close | close > SMA(5) |
| RSI 10/6 | RSI(2) < 10 | add if RSI(2) < 6 | close > SMA(5) |
Entry is at the close in all three. No stop, no target. Shorts mirror: below the 200-day, RSI(4) > 75, 4 of 5 up, RSI(2) > 90 / 94.

## Why it should work
The same as RSI(2) (methods/11): short-horizon liquidity provision in uptrending diversified ETFs.

## When it works and when it fails
The same profile as the family: a high hit rate and small gains, with losses concentrated in trend breaks the 200-day filter is
slow to catch.

## Parameters and sensitivity
RSI length (2 vs 4) and thresholds. RSI 10/6 is nearly identical to the existing `rsi2_meanrev` entry (< 10); only the
exit (sma_5 vs sma_10/RSI>70) and the add-on differ. Testing all three alongside RSI(2) and Double 7s multiplies trials.
Count them in the deflated Sharpe.

## Evidence
None verified (catalog grade "none"). By analogy, the methods/11 out-of-sample RSI(2) results (+0.27%/trade SPX, +0.43% NDX, 2016-2026,
Backtrex) are the realistic ceiling.

## Common mistakes
Coding from recollection without checking the book. Treating RSI 10/6 as a new strategy when it is a near-duplicate of
`rsi2_meanrev`.

## Discretionary parts and how to make them mechanical
None. They are fully mechanical once the thresholds are verified.

## Implementation spec for swing-engine
- Implement as `rsi2_meanrev` parameter variants plus one new feature each:
  - `rsi_4`: add 4 to `RSI_PERIODS` in `features/indicators.py`.
  - `sma_5`: add 5 to `SMA_WINDOWS`.
  - `down_days_5 = count(close < prev_close over last 5 bars)` (the panel has `up_days_3` only).
- Variant params: `rsi_col`, `rsi_entry`, `exit_rule` in {`rsi_4>55`, `close>sma_5`}. The add-on needs the scale-in hook
  (missing; see `connors_tps_scale_in`). Test without add-ons first.
- Entry: MOC needed (missing); interim next open. Stop: catastrophic `entry - 2*atr_14`. `max_hold_days` 6.
  `min_reward_risk` 0. Universe: index and sector ETFs.

## What the router should know
They duplicate `rsi2_meanrev` exposure. Use them for comparison only and never run them alongside it at full size.

## Signs of decay to monitor
The same as `rsi2_meanrev`: rolling 30-trade expectancy <= 0, and average loss more than 2.5x the average win.

## Sources
- https://academy.edgerater.com/?p=68
- docs/methods/11-rsi2-connors-mean-reversion.md

## Empirical (replay)
_Pending: filled in from swing replay on real data._
