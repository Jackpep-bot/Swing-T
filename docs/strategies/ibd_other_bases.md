---
slug: ibd_other_bases
name: IBD double bottom, ascending base, saucer and consolidation bases
originators: [William J. O'Neil, Investor's Business Daily, MarketSmith/MarketSurge]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 60]
timeframe: daily and weekly
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built   # base_breakout detects only cup-with-handle and flat base
---

# IBD other bases (double bottom, ascending, saucer, consolidation)

## One-line summary
These are the O'Neil base types that `base_breakout` does not detect. Buy the breakout above each base's pivot
within 5% (the buy zone) on volume 40-50% or more above average. Cut losses 5-8% below the pivot (the
loss-cutting zone) and take profits at 20-25% above it.

## Origin and lineage
O'Neil's base taxonomy appears in *How to Make Money in Stocks* and the IBD articles. MarketSurge (formerly
MarketSmith) pattern recognition detects seven base types on daily and weekly charts:
- cup and cup-with-handle
- saucer and saucer-with-handle
- double bottom
- flat base
- ascending base
- consolidation
- IPO base

The IPO base has its own card (`ipo_first_base_breakout`). Cup and flat base are built in `base_breakout`.

## Exact rules
**Double bottom:**
- At least about 7 weeks long.
- W shape whose second low undercuts the first, even slightly. The undercut is mandatory.
- Pivot = the middle peak of the W (plus a small margin; IBD adds $0.10 on cups, and the double-bottom margin was
  not verified).
- A handle variant moves the pivot to the handle high.
- Depth limit: "comparable to other corrections". No number was verified.

**Ascending base:**
- Three pullbacks of about 10-20% each.
- Each low and each high steps above the last.
- Forms over about 9-16 weeks.
- Pivot = the high before the third pullback.

**Saucer (with handle):**
- A longer, shallower cup. IBD article titles confirm the pattern. Numeric limits were not verified in this run.

**Consolidation:**
- MarketSurge's catch-all base. Pivot = the left-side high. No numeric definition was found.

**Common rules:**
- Buy zone: pivot to pivot + 5%.
- Loss-cutting zone: 5-8% below the pivot.
- Profit-taking zone: 20-25% above the pivot.
- Only buy when M (market direction) allows it.

## Why it should work
- **Double bottom:** the undercut runs stops and shakes out weak holders below the first low, so supply above the
  pivot is thinner.
- **Ascending base:** shows relative strength, because the stock keeps setting higher lows through market
  pullbacks.

The mechanism is otherwise the same as other base breakouts: a supply/demand handoff into momentum.

## When it works and when it fails
- Works in leaders during confirmed uptrends.
- Double bottoms often form during market corrections and break out near the FTD.
- Ascending bases fail when the "higher lows" are just a choppy uptrend; LuxAlgo warns the pattern is easy to
  force.
- All base types fail en masse in corrections.

## Parameters and sensitivity
| Base | Parameters |
|---|---|
| Double bottom | `db_min_bars` 35; `db_max_depth` 0.33 (unverified); `db_undercut_min` 0.0; pivot margin 0.10 or 0.1% |
| Ascending base | `ab_pullbacks` 3; `ab_pullback_depth` [0.10, 0.20]; `ab_bars` [45, 80] |
| Saucer | Same as cup with a longer minimum and shallower `depth_max`. Pick and fix values before any test. |
| Consolidation | Leave out until a definition exists. |

Every new base type multiplies the trial count. Log them as one breakout family.

## Evidence
- Catalog grade C (P66, P67): O'Neil's historical model-book studies, which are descriptive and
  survivorship-conditioned. No peer-reviewed validation.
- No independent statistics for these base types were read in this run. Bulkowski's double-bottom data exists but
  was not fetched, so the numbers are unverified.
- The nearest tested relative, EasySwing's cup-and-handle detector, shows PF 1.57 gross.

## Common mistakes
- A "double bottom" with no undercut.
- Ascending bases with overlapping ranges.
- Buying the right side before the pivot.
- Deep, wide-and-loose bases in laggards.

## Discretionary parts and how to make them mechanical
Use zig-zag swing points (pivot width 5, the same convention as `features/levels.py`) inside the base window:
- **Double bottom:** two swing lows L1 < peak P > L2 with L2 < L1, at least 7 weeks from the left high to the
  breakout.
- **Ascending base:** three successive swing highs and three swing lows, each strictly above the prior, with each
  drawdown in [0.10, 0.20].

Base quality stays a Claude enum.

## Implementation spec for swing-engine
**Detectors:** add `double_bottom(...)` and `ascending_base(...)` to `features/patterns2.py`. Like `flat_base` and
`cup_with_handle`, each should take numpy arrays with `end` = the bar before as-of and return a `Base`-like tuple
(pivot, floor, start, top, length, depth).

**Where they plug in:** `BaseBreakout.find_base` as new variants. Add `is_double_bottom` and `is_ascending`
features.

**Rules** (same as `base_breakout`):
- Prior advance at least 30% over 126 bars (relax for double bottoms in corrections; param).
- `vol_ratio_50d_prev >= 1.4`, extension in (0, 0.05].
- `rs_63d_rank >= 0.80`, `min_market_trend_state` 1.

**Orders and exits:**
- Stop = max(floor, entry x 0.93), where floor is L2 for the double bottom and the third pullback low for the
  ascending base.
- Target +20%. Exit on a heavy-volume close below `sma_50`.
- `max_hold_days` 40. Minimum R:R 2.0.

**Missing:** a swing-point helper over arrays, the 8-week rule hook (same gap as `base_breakout`), and stop-entry
orders for the intraday pivot cross.

## What the router should know
- Same family and regime rules as `base_breakout`: `healthy_uptrend` only.
- Double bottoms appear around FTDs, when the playbook may still read `correction`. Do not override the gate.
  Shadow-log instead.

## Signs of decay to monitor
- Per-variant 10-bar failure rate (close back below the pivot).
- Count of detected bases per month vs breadth.
- MFE at 20 bars.

## Sources
- https://www.luxalgo.com/library/concept/double-bottom-base.md (fetched 2026-10-07)
- https://www.luxalgo.com/library/concept/ascending-base.md (fetched 2026-10-07)
- https://www.luxalgo.com/library/concept/cup-with-handle-base.md
- https://levelup.gitconnected.com/trading-cup-and-handles-with-marketsmith-pattern-recognition-3b869d0cfe2a
- https://www.scribd.com/document/781709581/Using-MarketSurge
- `docs/methods/04-chart-pattern-base-breakouts.md`; `docs/methods/07-canslim-ibd-market-school.md`
- O'Neil, *How to Make Money in Stocks* (not read directly)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
