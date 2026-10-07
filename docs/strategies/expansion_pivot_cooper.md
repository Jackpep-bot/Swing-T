---
slug: expansion_pivot_cooper
name: Expansion Pivot (Jeff Cooper)
originators: [Jeff Cooper (Hit and Run Trading, 1996, ch. 8)]
category: range_expansion_ma_reclaim
decision: implement_disabled_for_comparison
holding_period_days: [2, 7]
timeframe: daily
direction: long            # Cooper teaches the short mirror; swing-engine strategies are long-only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Expansion Pivot (Cooper)

## One-line summary
A stock that has been sitting on or under its 50-day MA prints its widest range in 10 days while bursting up through
the 50-day; buy a few cents above that day's high the next day, stop under its low.

## Origin and lineage
Jeff Cooper, *Hit and Run Trading* (1996), ch. 8. Cooper's thesis: stocks often drift around the 50-day, then
"explode" when institutions step in; the 50-day matters because institutions watch it. Cousin of the pocket pivot and
of MA-reclaim setups.

## Exact rules
- Buy setup (day t): `range_t > range` of each of the previous 9 sessions; yesterday or today the stock was at or
  below its 50-day MA, and today it pushes up through / closes above the 50-day.
- Entry (day t+1): buy stop 1/8 point above `high_t` (today: a few cents).
- Stop: just below `low_t`.
- Short mirror: widest range in 10 days breaking down through the 50-day.
- Exit: not specified precisely in the summaries read; "a few days, then trail".
- Book example: IBM, 18 Jan 1995, buy above 96 1/4, stop under 95 1/4.
- Sizing: not taught in the summaries read.

## Why it should work
A range expansion through a widely watched average signals urgent demand (institutional accumulation). The other
side: holders who bought higher and sell at break-even near the MA, and MA faders.

## When it works and when it fails
Works when the broader trend is up and the stock is basing on its 50-day. Fails in downtrends (the 50-day is
resistance), and on news days where the expansion is a one-off gap that fills.

## Parameters and sensitivity
Range lookback 9 (fixed by Cooper); MA length 50; "at or below" tolerance; exit horizon. Trap: adding filters until
the few examples look good.

## Evidence
Author's examples only. No independent test located.

## Common mistakes
Using true range instead of high-low (Cooper's "range" is high-low; unconfirmed whether gaps count); taking setups in
names far below a falling 50-day.

## Discretionary parts and how to make them mechanical
"At or below the 50-day yesterday or today": `min(low_{t-1}, low_t) <= sma_50_t` (an approximation; Cooper may mean
the close). "Bursts above": `close_t > sma_50_t`.

## Implementation spec for swing-engine
- Features (new): `range_hl = high - low`; `range_exp_10 = range_hl_t > max(range_hl[t-9..t-1])` (versioned constant
  `EXPANSION_LOOKBACK = 9`). methods.md also proposes `range_exp_3` for momentum_burst; share the helper.
- Setup at close t: `range_exp_10`, `min(low_{t-1}, low_t) <= sma_50_t`, `close_t > sma_50_t`; optional
  `sma_200` filter variant (`close > sma_200`).
- Entry: buy stop `high_t + 0.01` valid one session. **Missing hook**: stop-entry fill at `max(open_{t+1}, trigger)`.
  Without it, approximate with next-open entry only when `open_{t+1} <= high_t` and flag the bias.
- Stop: `low_t - 0.01`. Target: reference 2R (`min_reward_risk: 2.0` passes by construction). Exits: `max_hold_days: 7`,
  breakeven at +1R and trail per `execution.trail_*` settings.
- Reuses: `sma_50`, `sma_200`, `atr_14`, `range_pct`.

## What the router should know
Comparison only. Allowed regimes if enabled: `healthy_uptrend` 1.0, `narrow_uptrend` 0.5 (it is an MA-reclaim, closer
to a pullback than a base breakout).

## Signs of decay to monitor
Trigger-to-fill rate (how often price clears the expansion high) falling below ~50%; median MFE before stop < 1R.

## Sources
- https://elibook.vn/2020/02/03/expansion-pivot-mot-phuong-phap-danh-cua-jeff-cooper-gan-voi-pk-technique-cua-trend-trader/ (Vietnamese summary of the chapter)
- https://content.e-bookshelf.de/media/reading/L-753078-ed07b026bb.pdf (book excerpt)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
