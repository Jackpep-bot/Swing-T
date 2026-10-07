---
slug: earnings_announcement_premium
name: Earnings announcement premium (Frazzini-Lamont)
originators: [Andrea Frazzini, Owen Lamont (NBER w13090, 2007); Barber-De George-Lehavy-Trueman (JFE 2013)]
category: strategy
decision: implement
holding_period_days: [5, 25]
timeframe: monthly calendar tilt, daily event dates
direction: long (academic version long announcers / short non-announcers)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]   # judgement: gap risk is largest in high-vol tapes
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Earnings announcement premium

## One-line summary
Stocks earn abnormally high returns in the month they are expected to report earnings; buying expected announcers
(and underweighting the rest) earned more than 60 bp/month, about 7%+ a year, largest for stocks with high past
announcement-period volume.

## Origin and lineage
- Beaver (1968) and Chari-Jagannathan-Ofer (1988) noted announcement-period returns; Frazzini & Lamont, "The
  Earnings Announcement Premium and Trading Volume" (NBER w13090, 2007) built the tradeable version.
- Barber, De George, Lehavy & Trueman (JFE 2013): the premium holds globally.
- Engine role (catalog): calendar tilt toward holding quality momentum names into scheduled reports.

## Exact rules (as published, approximated)
1. Each month, predict which firms will announce: those that announced in the same calendar month 12 months earlier
   (a quarter-earlier proxy is also used in summaries).
2. Long predicted announcers, short (or underweight) non-announcers; rebalance monthly.
3. Strengthen with past announcement-month volume: stocks whose volume historically surges at announcements earn the
   biggest premium.

## Why it should work
- Authors' explanation: announcements grab attention; individual investors buy attention-grabbing stocks (imputed
  small-investor buying rises), and arbitrage is incomplete, so prices rise around the event.
- Risk view: announcements carry non-diversifiable information risk, so a premium is compensation (Savor-Wilson and
  others; not read here).
- Other side: institutions providing liquidity to attention-driven retail demand.

## When it works and when it fails
- Premium persists for about four weeks around the announcement (NBER Digest summary); reported to be pronounced in
  large caps (same summary; not checked in the paper).
- Cost: single-name gap risk. A swing book holding through reports takes the full distribution of earnings gaps; a
  1% risk position with a 5% stop can lose several R on one gap.

## Parameters and sensitivity
| Knob | Published | Engine proxy |
|---|---|---|
| expected-announcer rule | reported in the same month a year ago | predicted date = last year's same-quarter date + 364 days |
| window | calendar month | sessions [-10, +5] around predicted date |
| volume filter | high past announcement volume | top tercile of past announcement-window `rvol_day` |
Traps: confusing predicted with actual dates (actual dates known in advance only ~2-4 weeks out; use the predicted
rule for backtests).

## Evidence
- FL (1972-2004 main sample, evidence back to 1927): buy-announcers strategy > 60 bp/month (NBER Digest, Mar 2008);
  > 7% a year; strongly related to volume surges and imputed small-investor buying.
- Barber et al. 2013: global evidence (not fetched here; catalog).
- Post-2004 status and costs: not verified in the sources read.

## Common mistakes
1. Using the actual report date (look-ahead) instead of the predicted month.
2. Treating the premium as a reason to oversize into a report.
3. Ignoring the engine's own earnings exit rule (positions are flattened 1 session before earnings today).

## Discretionary parts and how to make them mechanical
Fully mechanical; the policy question (hold through reports or not) must be a versioned setting, not a per-trade call.

## Implementation spec for swing-engine
- Data: historical announcement dates (EDGAR 8-K Item 2.02 acceptance timestamps; catalog
  `earnings_dates_point_in_time`).
- Features: `pred_earn_date` = date of the same fiscal quarter's report one year earlier + 364 days;
  `exp_announce_window = 1` if `as_of` is within sessions [-10, +5] of `pred_earn_date`;
  `past_earn_rvol` = mean `rvol_day` over days 0..+1 of the last 4 reports.
- Uses: (a) policy param `hold_through_earnings_if` (e.g. `rs_63d_rank >= 0.9 and past_earn_rvol` top tercile)
  overriding `execution.earnings_exit_days` with a reduced size (risk multiplier 0.5) - needs a per-strategy hook in
  `execution/position_manager.py`; (b) ranker feature; (c) research replay of the long-announcers month book.
- Gap-risk accounting: replay must model the announcement gap (backtester `STOP_GAP` handles gap-through stops).
- Missing: dated announcement history, predicted-date feature, position-manager override hook.
max_hold_days: about 25 (one announcement window). Min reward:risk: n/a.

## What the router should know
- This is a tilt that conflicts with the current risk policy (`earnings_exit_days: 1`); default stays flat into
  reports until replay shows the premium beats the gap cost net of slippage.
- Clustered in earnings season; correlated exposure across many names in the same week.

## Signs of decay to monitor
- In replay, announcement-window returns of predicted announcers minus non-announcers <= 0 over 8 quarters.
- Gap losses on held-through names exceeding the measured premium.

## Sources
- https://www.nber.org/papers/w13090
- https://www.nber.org/system/files/working_papers/w13090/w13090.pdf
- https://www.nber.org/digest/mar08/stocks-rise-around-earnings-announcements
- https://lbsresearch.london.edu/id/eprint/391
- https://alphaarchitect.com/introducing-the-global-earnings-announcement-premium/
- Repo: `docs/catalog/catalog.json` (E23), `config/settings.yaml` (`execution.earnings_exit_days`), `swing_engine/execution/position_manager.py`

## Empirical (replay)
_Pending: filled in from swing replay on real data._
