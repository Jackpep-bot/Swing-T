---
slug: turn_of_month
name: Turn-of-the-month window
originators: [Robert Ariel, Josef Lakonishok, Seymour Smidt, John McConnell, Wei Xu, Quantified Strategies]
category: strategy
decision: implement
holding_period_days: [4, 8]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Turn-of-the-month (TOM)

## One-line summary
US equity returns cluster in the window from the last trading day of a month through the third trading day of the
next; use it as a calendar tilt on entry and exit timing, and replay the simple index rule as a comparison.

## Origin and lineage
- Ariel (1987, JFE): returns concentrated in the first half of the month starting with the last day of the prior month.
- Lakonishok & Smidt (1988, RFS): 90 years of Dow data; defined the -1..+3 trading-day window.
- McConnell & Xu (FAJ 64(2), 2008): 1926-2005, the TOM window accounts for the whole US excess market return on
  average; present in 31 of 35 countries.
- Quantified Strategies popularised an S&P 500 index rule; Harbourfront Quant summarises a 1986-2021 study.

## Exact rules
- Academic window: day -1 (last trading day of month) through day +3 (third trading day of the next month).
- QS index rule (catalog): buy SPY at the close of the 5th-to-last trading day of the month; sell at the close of the
  3rd trading day of the next month. No stop, no target.
- Engine use (catalog): a timing tilt for single-stock swing trades: favour entries in the days before month-end,
  avoid discretionary exits during days -1..+3.

## Why it should work
Month-end and early-month cash flows: payroll and pension contributions, automatic 401(k) and fund inflows, and
institutional rebalancing and window dressing concentrate buying at the turn. Liquidity providers on the other side
earn the premium for absorbing it. Ogden (1990) tied it to payment timing (named from the literature; not fetched).

## When it works and when it fails
- Shows across sizes and not only at year-ends (McConnell-Xu), so it is not just the January effect.
- Small in absolute terms; a single bad macro print or a selloff month swamps it.
- Turn-of-quarter variant has faded (catalog / Harbourfront).

## Parameters and sensitivity
| Knob | Published | Range to replay | Note |
|---|---|---|---|
| Window start | day -1 (academic), day -5 (QS) | -5..-1 | Earlier start adds exposure, little return. |
| Window end | day +3 | +2..+4 | |
| Instrument | index / all stocks | SPY; strategy candidates | |
Overfitting trap: tuning start and end days on the same 10 years; keep the academic -1..+3 as the default.

## Evidence
- McConnell-Xu (1926-2005): on average all excess market return at TOM. Since 1987: 0.14%/day value-weighted at TOM vs
  -0.01% on other days (catalog).
- Harbourfront Quant summary (1986-2021): about 0.55% per four-day TOM window holding all stocks only in the window;
  TOM and turn-of-year "resurfaced in recent decades", turn-of-quarter diminished (fetched this run).
- QS (S&P since 1960): CAGR 7% vs 7.5% buy-and-hold with about 33% time in market, max drawdown 27% vs 56% (catalog,
  not re-verified).
- Grade B- for size: persistent but small.

## Common mistakes
- Using calendar days instead of trading days (holidays shift the window).
- Treating it as a standalone stock-picking signal; it is a market-level effect.
- Forgetting costs: a 4-day window per month is ~24 round trips a year.

## Discretionary parts and how to make them mechanical
None; needs only an exchange calendar (`data.calendar` / `settings.yaml data.calendar: NYSE`).

## Implementation spec for swing-engine
- Feature `tom_day` (new, market-level, broadcast to every row): signed trading-day offset relative to month end using
  the NYSE calendar: last session = -1, earlier sessions -2, -3..., first session of next month = +1, +2, +3; NaN
  outside |offset| <= 5. Must be computed from the calendar, not from future bars, so it is causal.
- `tom_window` = 1 if -1 <= tom_day <= +3 else 0; `tom_pre` = 1 if -5 <= tom_day <= -2.
- Playbook tilt (new in `strategies/playbook.py`): multiply strategy risk by `tom_entry_boost` (e.g. 1.0 default,
  replay 1.0 vs 1.25) when `tom_pre` or `tom_day == -1`; suppress rule-based exits (`should_exit`) during
  `tom_window`, never the stop.
- Comparison strategy `tom_index` (replay only): SPY, entry = close of 5th-to-last session (backtester fills next open,
  so emit the signal on the 6th-to-last session to approximate, or accept a one-day shift), exit by time at day +3
  close, stop 3 x `atr_14` as a disaster stop only, `max_hold_days: 8`, `min_reward_risk: 0` (no target).
- Reuses: NYSE calendar, `atr_14`, playbook regime multipliers, backtester time exit.
- Missing: `tom_day` feature, the playbook tilt hook, market-on-close entry (backtester only fills at next open).

## What the router should know
It is an overlay, not a regime. Apply it only inside regimes that already allow a strategy; do not use it to open
trades in correction. Report trades entered in `tom_pre` separately in replays.

## Signs of decay to monitor
- Rolling 36-month mean SPY return in `tom_window` minus non-window days falling to zero.
- Tilted vs untilted replay of the same strategies showing no difference over 2+ years.

## Sources
- https://www.cxoadvisory.com/calendar-effects/the-turn-of-the-month-effect/
- https://ideas.repec.org/a/taf/ufajxx/v64y2008i2p49-64.html
- https://quantifiedstrategies.substack.com/p/turn-of-the-month-strategy
- https://harbourfrontquant.substack.com/p/do-calendar-anomalies-still-work

## Empirical (replay)
_Pending: filled in from swing replay on real data._
