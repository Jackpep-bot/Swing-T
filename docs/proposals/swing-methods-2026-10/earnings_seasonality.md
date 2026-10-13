---
slug: earnings_seasonality
name: Earnings seasonality, buy the seasonally strong quarter before it reports (Chang-Hartzmark-Solomon-Soltes)
originators: [Chang, Hartzmark, Solomon & Soltes, "Being Surprised by the Unsurprising", RFS 30(1) 2017]
category: strategy
decision: implement
holding_period_days: [5, 25]
timeframe: daily bars + EDGAR quarterly EPS and earnings dates
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: draft_card (research thread 2026-10-09, not in catalog yet)
---

# Earnings seasonality

## One-line summary
Firms whose upcoming fiscal quarter has historically been their best quarter earn abnormal returns in the month they
announce it, because investors anchor on the most recent (seasonally weaker) quarters and are surprised by a
predictable seasonal jump. One position per firm per year, held around a known date.

## Origin and lineage
- Chang, Hartzmark, Solomon & Soltes, RFS 30(1) 2017. Peer-reviewed. Drafts read: NBER 2014
  https://www2.nber.org/conferences/2014/BEf14/Chang_Hartzmark_Solomon_Soltes.pdf and April 2015
  https://cba.lmu.edu/media/lmucollegeofbusinessadministration/responsivesite/2015_CCFC_chang_etal.pdf
  (published RFS tables not checked; numbers below are from the drafts).
- Same authors' family: `dividend_month_premium` (Hartzmark-Solomon). Engine relatives: `earnings_announcement_premium`
  (Frazzini-Lamont, every announcer), `heston_sadka_seasonality` (return seasonality, not earnings).
- No Chen-Zimmermann signal matches (checked SignalDoc.csv); gate-2 CZ check not possible.

## Exact rules (as published)
1. For the quarter t about to be announced, take quarterly EPS excluding extraordinary items, split-adjusted, for the
   20 quarters t-23 .. t-4; all 20 required.
2. Rank those 20 quarters from largest to smallest EPS.
3. EarnRank = average rank of quarters t-4, t-8, t-12, t-16, t-20 (the same fiscal quarter in each of the prior five
   years). A low average rank number = the coming quarter is historically strong (check sign when coding: the paper
   sorts so that the "high seasonality" quintile is the one whose same-quarter EPS ranked highest).
4. Expected announcement month = month of the announcement 12 months earlier. Sort expected announcers into quintiles
   of seasonality each month; buy the top quintile; hold through the announcement month.
5. Filters: common stock, price >= $5, market cap known at prior month-end.

## Engine version (pre-register this one)
- Entry: next open 5 sessions before the expected announcement date (EDGAR 8-K 2.02 date one year earlier, +/- 7
  days); exit at the close 2 sessions after the actual announcement, or 25 sessions after entry if none.
- Universe: price >= $5, 63-day median dollar volume >= $20M.
- Long the top seasonality quintile only (the effect is "driven by the long side").

## Why it should work
Investors weight the latest quarters, which for a seasonal firm are its weak ones, so the strong quarter surprises
even though it is the same as every year. The paper shows analysts make the same error.

## Evidence
- 2014 draft, Table II (1972-2013, monthly four-factor alphas in the announcement month, gross): high quintile
  0.653% EW (t=6.98) / 0.909% VW (t=6.03); low quintile 0.306% / 0.358%; high-minus-low 0.347% EW (t=3.13) / 0.551%
  VW (t=3.14). Raw announcement-month returns: high 1.75% EW / 1.76% VW vs low 1.46% / 1.37%.
- 2015 draft: announcement day about 10 bp (t=3.37); days t-2..t+1 top-minus-bottom quintile about 26 bp, deciles
  about 39 bp; little of it before the announcement. The next quarter's announcement (seasonally weak) has negative
  returns (t=-4.00): a quarterly cycle.
- No independent replication or post-2013 test found. No cost analysis in the paper.
- Grade B (peer-reviewed, gross, not replicated).

## Why it might beat costs where the others failed
One round trip per firm per year, timed to a known date, and the VW alpha (large firms) is larger than the EW one:
the edge sits in the liquid names where the engine's per-stock cost is lowest. The long leg alone carries it.
Risk: most of the window return is a few days around the announcement, so the per-trade edge is tens of bp; it
only clears costs in liquid names.

## Common mistakes
Using restated EPS or fiscal-period-end dates (look-ahead); trading the weak-season short leg (long-only engine,
and the paper says the long side drives it); using the actual announcement date to time entry (unknown in advance).

## Implementation spec for swing-engine
- Data in hand: `data.fundamentals.quarterly_values(fund, symbol, "EPS_DILUTED", day)` (EDGAR XBRL, by filing date);
  `earnings_dates_asof` for past 8-K 2.02 dates. XBRL starts about 2009-2011, so 20 quarters exist from about
  2014-2016: the 2017-24 window is mostly covered, early years thin. Log coverage.
- Q4 = FY minus 9-month YTD (as in `pead_sue`). Use diluted EPS; the paper uses basic ex-extraordinary.
- Grade per trade in % and R to the exit above; costs per stock; report the share of return from t-2..t+1.

## What the router should know
Event sleeve, small size; not regime-sensitive in the paper.

## Signs of decay to monitor
Trailing 8-quarter average excess return (vs SPY) of the top quintile in the window <= 0.

## Sources
- https://www2.nber.org/conferences/2014/BEf14/Chang_Hartzmark_Solomon_Soltes.pdf
- https://cba.lmu.edu/media/lmucollegeofbusinessadministration/responsivesite/2015_CCFC_chang_etal.pdf
- https://rpc.cfainstitute.org/research/cfa-digest/2017/06/being-surprised-by-the-unsurprising-earnings-seasonality-and-stock-returns-digest-summary
