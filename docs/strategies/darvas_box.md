---
slug: darvas_box
name: Darvas Box breakout and pyramid
originators: [Nicolas Darvas]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 120]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Darvas Box

## One-line summary
For stocks at new highs on rising volume, define a "box" (a high that holds 3 days, then a low that holds 3 days), buy
the break above the box top, keep the stop under the latest box bottom, and add on each new higher box.

## Origin and lineage
Nicolas Darvas, *How I Made $2,000,000 in the Stock Market* (1960); "techno-fundamentalist" (new highs plus improving
earnings). thinkorswim ships a `DarvasBox` study with a 5-state band machine. Ancestor of base/VCP breakouts
(`docs/methods/03-vcp-minervini-trend-template.md` names Darvas boxes).

## Exact rules (catalog coding of the book)
- Universe: stocks making 52-week highs on rising volume, ideally with improving earnings.
- Box top: a new high not exceeded on the next 3 consecutive days.
- Box bottom: after the top is set, the lowest low that holds for 3 consecutive days.
- Buy: break above the box top (buy stop just above; many codings use a close above and buy next open), with volume
  expansion (one coding: breakout volume >= 1.3x the box-period average; this threshold is a coder's choice, not
  Darvas').
- Stop: just under the box bottom. Pyramid: add when a new higher box forms and breaks; move the shared stop to the
  latest box bottom. Exit everything on a break below the current box bottom.
- thinkorswim: bands come from a 5-state machine; buy when the upper band is breached, sell on the lower band; a new
  box starts at the breaching bar. The state conditions are in a flowchart image not readable this run (unverified).

## Why it should work
Same mechanism as 52-week-high breakouts: anchoring near highs (George-Hwang) delays buyers; a tight box shows supply
absorbed. The ratcheting box stop keeps losses small and lets winners run.

## When it works and when it fails
Bull markets with leadership (Darvas' 1957-59). Fails in choppy tape (box breaks fail) and with gaps below the box
bottom.

## Parameters and sensitivity
Confirmation days 3 (2-4); volume multiple 1.3-1.5; stop offset 0-0.25 x `atr_14` below box bottom. Trap: box
definitions that repaint; confirm only with bars before as-of.

## Evidence
Book anecdote; no independent test located (grade C via related evidence). Related: Wilcox & Crittenden (2005)
all-time-high breakouts with 10 ATR trailing stops on 24,000+ US stocks 1983-2004 had positive expectancy (49.3%
winners, win/loss 2.56); Zarattini, Pagani & Wilcox (2025) extend to 1950-2024 with <7% of trades producing the profit
(catalog).

## Common mistakes
Using intraday highs that later get exceeded within the 3-day window (box not yet confirmed); tight stops on volatile
names; pyramiding without moving the stop.

## Discretionary parts
"Improving earnings" needs point-in-time EPS (not ingested); omit and note it. Volume expansion: make it
`rvol` >= 1.3 vs `avg_vol_50d`.

## Implementation spec for swing-engine
- State machine per symbol over prior bars (causal): `box_top` = high H at bar t once bars t+1..t+3 all have high <= H;
  `box_bottom` = after top confirmation, low L at bar u once bars u+1..u+3 have low >= L and no high > `box_top`. Box
  is "complete" when both are set; reset when price breaks either side.
- Universe gate: `dist_52w_high >= -0.05` at box completion.
- Signal: box complete and close > `box_top` and volume >= 1.3 x `avg_vol_50d` (close-based; buy-stop variant needs the
  hook). Entry next open.
- Stop = `box_bottom` - 0.1 x `atr_14`; exit rule: close < current `box_bottom` (ratchets as new boxes form). No fixed
  target, `min_reward_risk: 0`; `max_hold_days: 120`.
- Reuses: `dist_52w_high`, `avg_vol_50d`, `atr_14`, `breakout_52w` (overlap check), detector style of
  `features/patterns2.py` (numpy, `end` = bar before as-of).
- Missing: box state machine, stop-entry hook, pyramiding hook, ratcheting box stop (backtester trails by lowest low of
  N days, not by box bottom), EPS data.

## What the router should know
Breakout family; healthy_uptrend only; overlaps `breakout_52w` and `base_breakout`; report signal overlap.

## Signs of decay to monitor
Box-break failure rate (stopped within 5 bars); average boxes per winning trade.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/C-D/DarvasBox
- https://www.mql5.com/en/articles/24111
- https://www.sharescope.co.uk/sharescope_tutorial33.jsp
- https://www.cis.upenn.edu/~mkearns/finread/trend.pdf

## Empirical (replay)
_Pending: filled in from swing replay on real data._
