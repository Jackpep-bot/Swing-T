# Batch 2 candidates (research thread, 2026-10-10)

What failed so far: all five pre-registered picks (ATH trend, composite rank, earnings seasonality, high-volume
premium, early-stage momentum), 13D drift and the no-news mean-reversion filter. Every stock-picking one was
positive or flat in 2017-24 and lost in the survivorship-free 2024-26 window, when the average stock lagged the
largest names. So this batch avoids broad-universe stock picking: two candidates time SPY, the third trades only the
500 largest stocks on a slow corporate-action signal.

| # | Card | Instrument | Failure mode it is exposed to | Evidence | Data |
|---|---|---|---|---|---|
| 1 | [fomc_cycle_even_weeks](fomc_cycle_even_weeks.md) | SPY | calendar effect decayed after 2016 | B: JF 2019, in-paper international and post-draft evidence; no post-2016 peer-reviewed test | SPY bars + FOMC dates (listed in the card) |
| 2 | [large_cap_net_repurchasers](large_cap_net_repurchasers.md) | top-500 stocks | buyback effect weaker since 2004 | B: FF 2008 big-stock repurchasers +0.26%/month (t=3.44); survives costs (Novy-Marx-Velikov net 0.37%/month) | bars, XBRL share counts, splits table |
| 3 | [volatility_managed_spy](volatility_managed_spy.md) | SPY | mistimed de-risking; real-time tests say no edge | C: in-sample alpha 2.12%/yr capped at 1x; Cederburg et al. find no real-time gain | SPY bars |

Grading note: #1 and #3 are timing strategies on one ETF. R per trade and absolute Sharpe will flatter anything long
SPY in a bull window, so each card registers alpha vs SPY from daily net returns as the primary statistic. That needs a
small addition to the grader before the replay.

Expectations, stated before any run: #1 has the best chance; #3 is close to a control (published real-time evidence is
negative); #2 is the only stock-selection idea left that the literature finds in big stocks on the long side.

## Looked at and rejected
- **Overnight SPY (buy close, sell open)**: State Street's cost test on SPY 1993-2020 turns +717% gross into -32%
  after daily spreads and $0.01/share (https://alphaarchitect.com/trading-costs-wipe-out-the-overnight-return-anomaly/);
  the NY Fed reports the futures overnight drift averaged close to zero in 2021-25
  (https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/); 23x5 trading starts Dec 2026.
- **Reversal scaled by VIX (Nagel 2012)**: all returns gross, about half is bid-ask bounce (0.30%/day on trade prices vs
  0.18% on midpoints), daily turnover, and Collin-Dufresne & Daniel find no VIX link in large caps once
  cross-sectional volatility is controlled. Mean reversion has already failed here.
- **Asset growth (Cooper-Gulen-Schill)**: absent in big stocks (FF 2008), not significant net of costs (Novy-Marx-Velikov
  net 0.26%/month, t=1.75), and the CMA factor averaged 0.22% a year in 2010-2019.
- **SPY 10-month SMA timing (Faber 2007)**: mainly cuts drawdowns, and most of that came in 2000-02 and 2008. CXO
  (2019, independent) finds every timing variant "substantially underperforms" buy-and-hold since January 2009, and
  the month-end result is fragile to the check day (6 of 21 shifted variants beat buy-and-hold, 1990-2019).
  https://www.cxoadvisory.com/calendar-effects/optimal-cycle-for-monthly-sma-signals/
- **Dual momentum / GEM (Antonacci)**: an independent EDHEC replication (Petit, SSRN 7427878, 2026) finds GEM trailed the
  index by 4.8 points a year since 2010, with its deepest drawdown in 55 years in 2021-23. Graded on alpha vs SPY, both
  of these would almost certainly fail, so they are not worth the trials.
