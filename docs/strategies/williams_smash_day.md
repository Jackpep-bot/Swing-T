---
slug: williams_smash_day
name: Smash Day and Hidden Smash Day reversals (Larry Williams)
originators: [Larry Williams]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long   # sells mirror; engine is long-only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Smash Day / Hidden Smash Day

## One-line summary
A day that closes weak (below the prior low, or up but in the bottom quarter of its range) and is then taken out to the
upside within a few days marks a failed sell-off: buy the break of the smash day's high.

## Origin and lineage
Larry Williams, *Long-Term Secrets to Short-Term Trading* (1999), ch. 7. Best used as the end of a pullback in the
direction of the higher-timeframe trend.

## Exact rules (long)
- Naked smash: down day closing below the prior day's low (often taking out several recent lows).
- Hidden smash: up close (`close > prev_close`) that closes in the lowest 25% of its own range.
- Entry: buy stop 1 tick above the smash-day high; usually left working 1-3 days (author does not fix the duration).
- Stop: under the smash-day low. Exit: trail / short swing; Williams also used time exits.

## Why it should work
The smash day draws in sellers at the lows; a break above its high shows that supply failed and forces them to cover.

## When it works and when it fails
Pullbacks inside uptrends. In downtrends, naked smash days are just trend days.

## Parameters and sensitivity
Close-below-low depth, the 25% range cut-off, order life (1-3 days), trend filter. Keep 25% and 3 days fixed.

## Evidence
Originator examples only (catalog C11). Oxford Capital Strategies tested Smash Day variants on 42 futures from 1980;
numbers were not retrieved this run.

## Common mistakes
Taking it against the trend; leaving the buy stop open for a week (stale level).

## Discretionary parts and how to make them mechanical
Trend gate `trend_state == 1` and `close > sma_50`. "Several recent lows" -> optional `low_t == min(low[t-4..t])`.

## Implementation spec for swing-engine
- Reuses: OHLC, `prev_close`, `close_pos`, `trend_state`, `sma_50`, `atr_14`.
- Setup at close t: naked = `close_t < low_{t-1}`; hidden = `close_t > close_{t-1}` and `close_pos_t <= 0.25`.
- Entry: buy stop `high_t + 0.01`, live days t+1..t+3; fill at `max(open, level)` on the first day `high >= level`
  (needs stop-entry hook). Proxy without the hook: next open after a close above `high_t` (labelled).
- Stop: `low_t - 0.01`. Target: none taught; `min_reward_risk: 0.0`; `max_hold_days: 5`; engine trail after +2R.

## What the router should know
Pullback family; overlaps `pullback_holy_grail` (also a buy stop over a weak bar). Trend regimes only.

## Signs of decay to monitor
Triggered-then-stopped within 2 bars > 50%; average 5-day R <= 0.

## Sources
- https://prorealcode.com/prorealtime-indicators/larry-williams-smash-days
- https://roboforex.com/blog/education/catch-your-smash-day-with-larry-williams/
- https://catalogimages.wiley.com/images/db/pdf/0471297224.pdf
- https://oxfordstrat.com/?p=5935 (futures tests; numbers not retrieved)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
