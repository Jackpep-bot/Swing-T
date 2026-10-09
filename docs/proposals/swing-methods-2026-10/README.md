# Published swing methods the engine has not tested (research, 2026-10-09)

Scope: published methods for US stocks not already in `docs/catalog/catalog.json` (281 items) or the 794-trial
leaderboard, favouring low turnover, large per-trade moves or cost-aware design with out-of-sample or replicated
evidence. Every number below was read in the linked source this session; where only a working paper or a summary
could be opened it says so. Draft cards (repo card format) are in `research/strategies/`.

## What to replay first

| # | Card | Why it may beat costs | Evidence | Data | Replay horizon |
|---|---|---|---|---|---|
| 1 | [ath_trend_following_wide_stop](ath_trend_following_wide_stop.md) | ~1 round trip per name per year; profits come from a few huge winners | C: originator tests, survivorship-free, costs, decay measured (0.39R pre-2005, 0.31R after) | daily bars (have) | to stop exit (months) |
| 2 | [composite_cost_aware_rank](composite_cost_aware_rank.md) | one book from 4 slow signals already built; buy/hold band cuts costs ~42% | B: peer-reviewed, cost-inclusive (Novy-Marx-Velikov; DeMiguel et al.) | have | monthly rebalance |
| 3 | [earnings_seasonality](earnings_seasonality.md) | 1 trade per firm per year; VW alpha > EW alpha, so it lives in liquid names | B: peer-reviewed, gross, not replicated | EDGAR EPS + 8-K dates (have, from ~2014) | ~5-25 sessions |
| 4 | [high_volume_return_premium](high_volume_return_premium.md) | native 20-day horizon; authors' own limit-order cost test positive for the ordinary-return subsample | B: peer-reviewed, 41-country replication; no post-2001 US test | daily bars (have) | 20 sessions |
| 5 | [momentum_volume_early_stage](momentum_volume_early_stage.md) | months-long holds; better as a 5th input to #2 than its own book | B: peer-reviewed, old sample (to 1995) | bars + shares outstanding (have) | 3-12 months |
| 6 | [dividend_month_premium](dividend_month_premium.md) | quarterly, liquid payers; replicated in 44 markets and post-publication in Germany | B | **blocked**: no ex-dividend history; bars exclude dividends | 1 month |

Headline numbers (all checked against the source):
- **ATH + 10-ATR stop** (Wilcox & Crittenden 2005, https://www.cis.upenn.edu/~mkearns/finread/trend.pdf): 18,000+
  trades 1983-2004 incl. 12,673 delisted names, win 49.3%, avg win/loss 2.56, 305-day average hold, 0.5% round trip
  charged; portfolio 1991-2004 net 19.3% CAGR, -20.8% max DD vs S&P 12.0%, -44.7%. 2025 update (Zarattini, Pagani &
  Wilcox, https://concretumgroup.com/wp-content/uploads/2026/02/Does-Trend-Following-Still-Work-on-Stocks.pdf):
  66,000 trades 1950-2024, +0.50R per trade; 1991-2024 gross Sharpe 0.85; net Sharpe 0.06 for a $0.1M account
  without turnover control (commission-driven, $0.0035/share) and 0.75 with it.
- **Buy/hold band** (Novy-Marx & Velikov 2016, https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf p.26,
  Tables 3, 6): turnover -41% and costs -42% across 23 anomalies; momentum net 0.68% -> 0.85%/month.
- **Earnings seasonality** (2014 NBER draft, Table II): top quintile announcement-month alpha 0.909%/month VW (t=6.03);
  high-minus-low 0.551% VW (t=3.14), 1972-2013, gross.
- **HVRP** (GKM 1998 WP Table 2): 20-day high-minus-low volume 0.50% for large NYSE stocks, 0.94-1.07% small/medium;
  Kaniel-Ozoguz-Starks 2012: US 1.12% per 20 days (t=33.31), still 0.57% (t=4.70) in 1997-2001.

## Before replaying anything: the test cannot pass a realistic strategy as configured

This matters more than which method goes next. Read from `swing_engine/research/leaderboard.py` and
`research/metrics.py` (branch `claude/project-thread-jdz24e`, commit eb9f61f):

1. **Horizons stop at 20 sessions** (`shadow.DEFAULT_HORIZONS = (5, 10, 20)`). Strategies whose cards say 60-day or
   monthly holds (`pead_sue` 60 days, `residual_momentum` 21-126, `xs_momentum_rank`) were graded at 20 sessions;
   residual momentum shows 108 signals, 0% win, -0.74R in 2024-26, which is a stop/horizon artefact, not the factor.
   Candidates 1, 2 and 5 above cannot be judged on that table at all.
2. **Cost is charged in R of the signal's stop distance** (`cards.cost_r`). Tight stops make the same 10 bp look
   large; methods with wide or no stops need % return grading.
3. **The survivor bar is out of reach for any published strategy in the 2-year window.** Bonferroni over 794 trials
   needs t > 3.22, i.e. an annual Sharpe above 2.28 in 2024-26 and above 1.16 in 2017-24 (my arithmetic from
   `haircut_sharpe`). The best published net figures above are Sharpe 0.7-0.85, and Chen & Velikov (JFQA 2023,
   https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf) put the average anomaly at 8 bps/month net
   post-publication post-2005. Every new trial raises the bar further.

Suggested for the replay thread (Jack's call, not changed here): grade the six candidates as one pre-registered
confirmatory family (one version each, no sweeps), on their own holding period, in % return net of per-stock costs,
as portfolios; judge them on the full 2017-26 span with a family-size haircut and report the 794-trial haircut
alongside.

## Looked at and rejected

- **Trend factor** (Han-Zhou-Zhu, JFE 2016; CZ `TrendFactor` 1.63%/month, t=15.0): the edge depends on trading at
  the same close the signal uses. A replication (Zhong 2018, Aalto thesis,
  https://aaltodoc.aalto.fi/items/d7b72224-fcc3-4917-abe3-655d8b4badc0/full) finds 1.69%/month falls by more than
  0.50% with a 1-day skip and below plain momentum with a 5-day skip; 0.82% of it is last-5-day reversal. The engine
  fills next open. CXO also reports 65.6% monthly turnover.
- **Overnight-return momentum** (Lou-Polk-Skouras, JFE 2019): their momentum sort is ordinary 12-1 returns; the
  1-month past-overnight sort predicts +3.47% overnight but -3.24% intraday, so the close-to-close edge mostly
  cancels; needs an opening-half-hour VWAP and daily close-to-open trading. Authors say costs make it "much less
  attractive".
- **Dividend initiation/omission drift** (Michaely-Thaler-Womack 1995): drift insignificant value-weighted (Boehme &
  Sorescu 2002) and explained by earnings drift (Liu, Szewczyk & Zantout 2008).
- **Plain high-volume momentum** (Lee-Swaminathan late stage): high-turnover winners reverse in years 2-5; only the
  early-stage leg is carried forward (#5).

## Caveats

- Several primary PDFs were blocked (ScienceDirect, SSRN, Wiley): Hartzmark-Solomon numbers come from CZ
  documentation and CXO / Alpha Architect summaries; earnings-seasonality and HVRP numbers are from working-paper
  drafts; DeMiguel et al. net results from working-paper summaries. Each card says which.
- Chen-Zimmermann portfolio returns (for the gate-2 CZ check) could not be downloaded from this environment (Google
  Drive is blocked); that check stays a manual step on the Mac.
- Long-only engine: every long-short figure above overstates what a long book gets; plan on at most half.
