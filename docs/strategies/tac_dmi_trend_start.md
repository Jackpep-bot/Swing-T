---
slug: tac_dmi_trend_start
name: "TAC_DMI trend-start system (BC Low)"
originators: ["BC Low, CMT, 'Identify The Start Of A Trend With DMI', Technical Analysis of Stocks & Commodities V.30:11 (Nov 2012)", "thinkorswim built-in strategy"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]   # not published; engine assumption
timeframe: daily
direction: long_short   # engine long side only
regimes_good: [correction, narrow_uptrend]   # long signal is a bottom-picking signal; untested
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# TAC_DMI trend-start system (BC Low)

## One-line summary
Uses clusters of three short-length ADX, +DI and -DI lines: a long fires when the three +DI lines bunch below 10 (the
lowest at or below 5) while the ADX cluster turns down from about 70, i.e. an exhausted down-move is ending.

## Origin and lineage
Wilder's DMI (1978) re-worked by BC Low in S&C (Nov 2012), using three ADX and three DI lines of different short lengths
("clusters") instead of one of each. thinkorswim ships it as TAC_DMI with studies TAC_ADX, TAC_DIPlus, TAC_DIMinus.
The article itself (paywalled, traders.com returned 403) was not read.

## Exact rules (thinkorswim documentation)
- Long entry: TAC_DIPlus lines cluster below 10 and the lowest reaches 5, while the TAC_ADX cluster turns down from 70.
- Short entry: mirror with TAC_DIMinus.
- Chart-only (no orders): possible trend start when the ADX cluster turns up from below 30 (stronger below 20); trend
  termination when it turns up from below 70 (stronger: 90).
- Inputs: adx length1-3, di length1-3, tolerance (how close lines must be to count as a cluster; 0 = single point),
  average type. Default values are not given on the doc page. A search snippet says the article's ADX lines use 3, 4
  and 5 periods (unverified).
- Exits, stops, sizing: none documented. thinkorswim's strategy closes on the opposite signal (assumed; not verified).

## Why it should work
Very low +DI on short lengths with a very high, turning ADX means a strong, short-term down-move is exhausting: a
short-term reversal / capitulation signal. Counterparty: forced or panic sellers late in a decline. Despite the name, the
long signal is a bottom-pick, not a breakout trend start.

## When it works and when it fails
- Plausible: sharp pullbacks inside longer uptrends; index washouts.
- Fails: persistent downtrends (repeated exhaustion readings while price keeps falling), news-driven collapses.

## Parameters and sensitivity
Six lengths plus tolerance and MA type: a large search space for a no-evidence system. Fix lengths (3/4/5 for both ADX
and DI as the v1 guess), tolerance = 0 and Wilder smoothing; do not tune.

## Evidence
None found: no independent test, no stats in the thinkorswim docs. The S&C article may contain examples (not read).

## Common mistakes
Reading it as a trend-following entry; using default 14-period DMI (the cluster logic depends on very short lengths).

## Discretionary parts and how to make them mechanical
- "Cluster": max(line) - min(line) <= tolerance_pts (engine choice 5 points) plus level conditions.
- "Turns down from 70": max of the 3 ADX lines >= 70 on t-1 and all three ADX lines lower on t than t-1.

## Implementation spec for swing-engine
- Features: for n in (3, 4, 5): `adx_n`, `plus_di_n`, `minus_di_n` via the existing Wilder helpers
  (`features/patterns2.py` `directional_movement`, `_di`, `_dx`, `wilder_smooth`; only period 14 is in the panel).
- Long signal at close t: `max(plus_di_3..5) < 10`, `min(plus_di_3..5) <= 5`, `max(adx_3..5)[t-1] >= 70`, all
  `adx_n[t] < adx_n[t-1]`. Optional filter: `trend_state >= 0` or close > sma_200 (engine choice).
- Entry: next open. Stop: lowest low of the last 5 bars - 0.1 x atr_14. Target: 2R; exit also on the short signal.
- max_hold_days: 10 (exhaustion trades should work fast); min_reward_risk: 2.0.
- Reuses: Wilder DMI helpers, `atr_14`, `trend_state`. Missing: multi-length DMI columns.

## What the router should know
Behaves like a mean-reversion bounce, so it belongs with rsi2_meanrev-type allocations, not trend-following ones.
Zero evidence: shadow comparison only.

## Signs of decay to monitor
Signal count per year (very rare = untestable), share of signals followed by new lows within 5 sessions.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/TAC-DMI
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TAC-ADX
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TAC-DIPlus
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TAC-DIMinus
- https://store.traders.com/stcov301idst.html (article listing, V.30:11 pp.12-20)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
