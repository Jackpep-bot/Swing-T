---
slug: earnings_announcement_return_abr
name: Earnings-announcement abnormal return continuation (Abr)
originators: [Chan-Jegadeesh-Lakonishok (JF 1996); Hou-Xue-Zhang replication]
category: strategy
decision: implement
holding_period_days: [21, 126]
timeframe: daily event feature, monthly sort
direction: long (academic factor is long-short)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Earnings-announcement return (Abr)

## One-line summary
Rank stocks by their market-adjusted return over the 4 days around their latest earnings report; strong reactions
keep drifting the same way for about a month (fading over 6-12 months). The price reaction is used instead of the
EPS surprise.

## Origin and lineage
- Chan, Jegadeesh & Lakonishok, "Momentum Strategies", Journal of Finance 1996: earnings-announcement returns and
  SUE both predict returns, partly explaining price momentum.
- Brandt-Kishore-Santa-Clara-Venkatachalam (2008) return-based earnings surprise (related).
- HXZ (2017/2020) replication defines Abr1/Abr6/Abr12.
- Engine context: academic analogue of the gap in `power_gap` and `episodic_pivot`.

## Exact rules (HXZ definition)
1. Day 0 = announcement date of the latest quarterly earnings (announcement after the fiscal quarter end; fiscal
   quarter end within the last 6 months).
2. `Abr = sum over d = -2..+1 of (r_i,d - r_m,d)`, r_m = value-weighted market return.
3. Each month-end sort on the most recent Abr into deciles (NYSE breakpoints, VW).
4. Long top decile (short bottom); hold 1 month (Abr6/Abr12 = 6/12-month holds).

## Why it should work
- Investors underreact to the information in earnings news; the market reaction captures surprise in revenue,
  guidance and quality that EPS surprise misses.
- Other side: anchored analysts and holders slow to update; contrarians fading the reaction.

## When it works and when it fails
- Strongest at month 1; weakens with holding horizon.
- PEAD-type drift has decayed for large stocks since about 2006 (Martineau 2022) and is concentrated in microcaps
  (Subrahmanyam 2025); Abr's post-2014 status is not verified.
- Fails when the reaction is a liquidity event (no-news extremes reverse, Chan 2003) or in market-wide panics.

## Parameters and sensitivity
| Knob | Published | Range |
|---|---|---|
| window | d = -2..+1 | -1..+1, 0..+2 |
| market | VW market | SPY as proxy |
| recency | quarter end within 6 months | latest report within 63-126 sessions |
| hold | 1 month | 1-6 |
Traps: getting day 0 wrong (after-close reports move on day +1); using restated or vendor-backfilled dates.

## Evidence
- HXZ (VW, NYSE breakpoints, through 2014): Abr1 0.74%/mo (t = 5.85), Abr6 0.30% (t = 3.24), Abr12 0.22%
  (t = 2.84); among anomalies the q-factor model leaves unexplained.
- Post-2014: not verified; Martineau's PEAD decay result argues for re-testing on 2015-2026 data before use.
- No cost-inclusive estimate in the sources read.

## Common mistakes
1. Look-ahead on dates: transaction or period-end dates instead of the public release timestamp (CLAUDE.md rule 3).
2. Including the announcement return in the holding-period return.
3. Not adjusting for the market (a raw 4-day return in a rally is not a surprise).

## Discretionary parts and how to make them mechanical
Fully mechanical given point-in-time announcement timestamps.

## Implementation spec for swing-engine
- Data: point-in-time earnings dates; cheapest source is EDGAR 8-K Item 2.02 acceptance timestamps (catalog
  `earnings_dates_point_in_time`); Alpha Vantage `EARNINGS_CALENDAR` (`data/alphavantage.py`) is forward-looking
  only, not a history.
- Day 0 = the first session in which the release could trade: acceptance before 09:30 ET -> that session; after
  16:00 ET -> next session.
- Feature `abr_4d` available from the close of day +1:
  `abr_4d = sum_{d=-2..+1} (ret_1d_i,d - ret_1d_SPY,d)`; carry forward until the next report;
  `days_since_earnings`; NaN if the last report is more than 126 sessions old.
- `abr_rank` = same-session percentile within the universe.
- Uses: (a) ranker feature; (b) filter/boost for `power_gap` / `episodic_pivot` (require `abr_rank >= 0.8`, which also
  supplies the missing "earnings required" check); (c) research replay: month-end long top decile, 21-session hold.
- Reuses `ret_1d`, market panel (SPY). Missing: 8-K 2.02 history ingest, `days_since_earnings`, `abr_4d`.
max_hold_days: 21 (Abr1). Min reward:risk: n/a.

## What the router should know
- Event-driven: signals concentrate in earnings season; sector cap applies.
- Conflicts with `execution.earnings_exit_days: 1` only at the next report (about 63 sessions later), not with the
  1-month hold.

## Signs of decay to monitor
- 2015-2026 replay Abr1 spread insignificant (t < 2) or negative.
- Abr effect only in names below the engine's liquidity floor (price >= $5, $5M ADV).

## Sources
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- Repo: `docs/catalog/catalog.json` (E22), `docs/methods/02-episodic-pivot.md` (PEAD backdrop), `swing_engine/data/alphavantage.py`

## Empirical (replay)
_Pending: filled in from swing replay on real data._
