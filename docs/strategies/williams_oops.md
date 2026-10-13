---
slug: williams_oops
name: Oops! gap-through reversal (Larry Williams; ChartSchool full-gap-down long)
originators: [Larry Williams]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [0, 3]
timeframe: daily (same-day stop-entry)
direction: long   # sell mirror (open above prior high); engine is long-only
regimes_good: [choppy, narrow_uptrend, healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Oops!

## One-line summary
When a stock opens below yesterday's low and then trades back up to that low the same day, the gap has failed: buy at
yesterday's low with a stop at the day's low.

## Origin and lineage
Larry Williams, *Long-Term Secrets to Short-Term Trading* (1999), ch. 7, used on S&P futures with day-of-week and other
filters. StockCharts ChartSchool's gap rules include the same idea for a full gap down (long stop 2 ticks above the
prior day's low).

## Exact rules (long)
- Setup: `open_t < low_{t-1}` (full gap down through the prior low).
- Entry: buy stop at (a tick above) `low_{t-1}`, same day only.
- Stop: the day's low.
- Exit: at the close, or at the first profitable open (Williams' "bailout"; the pairing with Oops is unverified).
- ChartSchool variant: trailing stops 8% (long), tighter 5-6% for partial gaps.

## Why it should work
Overnight sellers (stops, news over-reaction) push the open below support; if the gap is reclaimed intraday, those
sellers are wrong and must cover, while the gap-fill attracts buyers.

## When it works and when it fails
Small, non-news gaps in liquid names. Large gaps (> ~1.2 x ATR) usually do not fill and behave as continuation (see the
power gap / `docs/methods/13-power-earnings-gap.md` work); earnings gaps are information, not noise.

## Parameters and sensitivity
Gap size band (min/max as multiples of `atr_14`), buffer above the prior low, exit rule (close vs next open). Williams'
day-of-week filters are classic data-mined additions; do not add them.

## Evidence
- Book examples only; the widely repeated "93% of the time" claim has no traceable test.
- Descriptive gap-fill stats (search summaries, not re-verified): SPY up-gaps of 0.1-0.25% filled the same day about
  78% of the time; 0.25-0.5% gaps about 60% same day and 82% within 5 sessions; ES gaps > 1.2 x ATR(14) filled the same
  day only about 8% (2014-2024). These are fill rates, not Oops returns, and are for index products.

## Common mistakes
Buying the gap-down open (no confirmation); trading earnings gaps; holding a failed Oops overnight.

## Discretionary parts and how to make them mechanical
Gap band: `0.25 * atr_14_{t-1} <= low_{t-1} - open_t <= 1.2 * atr_14_{t-1}`. Exclude earnings days once dates exist;
until then exclude `rvol_day >= 3` as a news proxy (labelled).

## Implementation spec for swing-engine
- Reuses: OHLC, `gap_pct`, `prev_close`, `atr_14`, `rvol_day`.
- New feature: `prev_low` (already computed inside `features/patterns.py`; expose it).
- Daily fill is exact: the open is below the level, so if `high_t >= low_{t-1}` the fill is at `low_{t-1} + 0.01`.
- Stop: `low_t - 0.01` (the day's full low is known only at the close; when the low prints after the fill, a same-day
  stop-out cannot be detected on daily bars: flag any day with `close_t < entry` as at-risk).
- Exit: close of t (`max_hold_days: 1`) or next open if profitable; compare a 3-day hold.
- `min_reward_risk: 0.0`. Missing: same-day stop-entry fill in `research/backtest.py`; intraday bars for exit honesty.

## What the router should know
Same-day mean reversion; correlated with `eighty_twenty_reversal` and `turtle_soup`. Not in sell-off regimes.

## Signs of decay to monitor
Fill-to-close average < costs; share of filled Oops closing below entry > 50%.

## Sources
- https://catalogimages.wiley.com/images/db/pdf/0471297224.pdf (book excerpt)
- https://jp.tradingview.com/script/7Gqs0Sqn-Larry-Williams-Oops-Strategy
- https://www.luxalgo.com/library/concept/classic-bar-setups.md
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/gap-trading-strategies
- https://tradethatswing.com/sp-500-spy-es-gap-fill-strategy-and-statistics/
- https://www.thetrading.tools/gap-analysis

## Empirical (replay)
_Pending: filled in from swing replay on real data._
