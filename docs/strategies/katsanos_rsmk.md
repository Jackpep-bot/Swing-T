---
slug: katsanos_rsmk
name: RSMK relative-strength strategy (Katsanos)
originators: [Markos Katsanos (S&C Mar 2020), thinkorswim RSMK study + RSMKStrat]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [10, 60]    # fixed-bar time exit; TOS default bar count not published
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# RSMK (Katsanos)

## One-line summary
Buy when a stock's smoothed 90-day log relative strength versus the index crosses above zero (it starts outperforming),
hold a fixed number of bars.

## Origin and lineage
Markos Katsanos, "Using Relative Strength To Outperform The Market", S&C Mar 2020; thinkorswim RSMK study and RSMKStrat.

## Exact rules
- RSMK = EMA( ln(C/B) - ln(C[n]/B[n]), m ), with C the stock close, B the benchmark close, n = 90, m = 3 (Traders' Tips
  code defaults via search snippet; benchmark SPY). The 90-bar lookback is also the TOS documented default. Some ports
  multiply by 100 (scale only; zero crossing unchanged).
- Entry: RSMK crosses above 0. Next-open fill.
- Exit: after a fixed number of bars (`time exit length`; default not published on TOS; unverified).
- The article's full system may contain extra filters (e.g. market trend); not retrievable (traders.com 403). Unverified.

## Why it should work
Cross-sectional momentum / relative strength persistence (Jegadeesh-Titman): stocks starting to outperform tend to keep
doing so for weeks to months as information diffuses and institutions rotate. The other side: benchmark-hugging and value sellers.

## When it works and when it fails
Rotational bull markets with stable leadership. Fails at momentum crashes (sharp rebounds led by losers, e.g. Apr 2009,
Nov 2020, Apr 2025) and when the stock outperforms only by falling less in a down market.

## Parameters and sensitivity
n 20-126, m 3-10, hold 10-63 bars. A zero cross of a 90-day difference fires often in flat names; add a minimum slope or
trend filter only as a declared variant.

## Evidence
In-sample S&C illustration only (grade D). The underlying idea (relative strength) is well documented academically
(Jegadeesh & Titman 1993 and follow-ups), but this specific 90/3 zero-cross with a fixed hold has no independent test found.

## Common mistakes
Using price-only benchmark vs total-return stock (dividends bias); not requiring the stock itself to be in an uptrend.

## Discretionary parts and how to make them mechanical
Benchmark choice -> SPY by default; sector ETF as a variant param.

## Implementation spec for swing-engine
- Module `strategies/rsmk.py`, `@register("strategy")`; feature `rsmk_90_3` computed with the `market` frame
  (catalog maps_to: `relative_strength_line`). Align on session dates; NaN where the benchmark is missing.
- Signal: rsmk[t] > 0 and rsmk[t-1] <= 0; optional `require_trend_state: 1`. Entry next open.
- Stop: entry - 2.5 x atr_14 (engine-required). Target: None. Time exit: `max_hold_days` = 20 (engine assumption until the
  article default is confirmed).
- Reuses rs_63d_rank (related cross-sectional RS), trend_state, atr_14.
- settings.yaml: `rsmk: {enabled: false, shadow_only: true, rs_length: 90, ema_length: 3, max_hold_days: 20}`.

## What the router should know
Relative-strength trigger; overlaps with any strategy that ranks on rs_63d_rank. Most informative as a feature.

## Signs of decay to monitor
Zero-cross frequency per symbol rising (whipsaw); hit rate in down markets.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RSMKStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/RSMK
- https://www.traders.com/Documentation/FEEDbk_docs/2020/03/TradersTips.html

## Empirical (replay)
_Pending: filled in from swing replay on real data._
