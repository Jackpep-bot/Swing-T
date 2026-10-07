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
_Pending: filled in from swing replay on real data._
