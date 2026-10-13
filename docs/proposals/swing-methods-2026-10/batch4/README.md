# Batch 4 candidates (research thread, 2026-10-13)

Fifteen ideas were checked against the constraints (long-only US stocks or ETFs, days to about 3 months, data already
in the store, graded on alpha vs SPY net of costs in both windows). One is kept, with a low prior and a stated power
problem. The other fourteen are rejected below. Zero would also have been a defensible answer.

| # | Card | Universe | Evidence | Expectation stated before the run |
|---|---|---|---|---|
| 1 | [month_end_rebalancing_avoidance_spy](month_end_rebalancing_avoidance_spy.md) | SPY (TLT for the signal only) | C: one 2025 working paper (Harvey-Mazzoleni-Melone), S&P 500 futures 1997-2023, Calendar x last-week coefficient -0.27 (s.e. 0.076) on the equity leg; no independent or post-2023 test | 2017-24: alpha 0 to +2% a year, t < 1.5. 2024-26: about zero, t inside +/-1. FAIL on the alpha-t rule in both |

Why only one: every stock-selection idea on the list either was already replayed here and lost to SPY, or has
published evidence that the edge is gone outside microcaps, or needs data the store does not have. The kept card is a
flow effect in the most liquid instrument, with about 7 round trips a year.

**Power warning (my arithmetic, in the card).** The kept strategy differs from SPY on about 35 sessions a year, a
residual of roughly 6% a year. The registered alpha t of 2.241 needs about 9.5% a year of alpha in the 2-year window
and 4.8% in the 2017-24 window; the paper's effect applied to the long-only half is about 4% a year net at best. It
cannot pass the rule in the 2-year window even if the paper is right. Every SPY timing card has this kind of limit.
If the rule stays as is, the run tells us sign and size only.

Data check (read-only, `data/live/replay_p3.duckdb`): SPY and TLT bars cover 2016-01-04..2026-10-08; IEF, AGG, SHY
and BIL start 2024-10-07. The card registers TLT as the bond leg for that reason. `tom_day` and `month_end` exist in
`swing_engine/features/extra.py`. No new data needed.

Engine numbers below are from `docs/leaderboard.md` as read on 2026-10-13 (the file is regenerated; values move in
the third decimal): `vs SPY` is net R minus SPY's R on the same days, with its block t-stat. The first pair is
2024-10..2026-10, the second 2017-01..2024-10.

## Looked at and rejected

- **Post-earnings drift in large caps, SUE from EDGAR.** Martineau, "Rest in Peace Post-Earnings Announcement
  Drift" (Critical Finance Review 11, 2022; https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf,
  abstract read via search, PDF not opened): drift has been absent in large stocks since 2006. A UCLA Anderson
  brief (https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/, read) reports
  Subrahmanyam's 2025 reconciliation (SSRN 5930255, not opened): the earnings factor over 2001-02..2024-12 has
  t = 2.18 with all stocks and t = 1.43 once microcaps are dropped. Engine: `pead_sue` vs SPY -0.195R (t -2.89) and
  -0.125R (t -4.54); `revenue_surprise` and `earnings_announcement_return_abr` also negative.
- **Earnings acceleration (He & Narayanamoorthy, JAE 69, 2020).** Claimed 1.8% a month (SSRN abstract 3057632 via
  search; paper not opened). No large-cap split, no post-publication test and no cost study found. The one
  "replication" located (American Century, https://res.americancentury.com/docs/revisiting-earnings-acceleration.pdf,
  read) measures acceleration with future reported EPS ("perfect foresight"), so it is not a tradable test. It is a
  second difference of the same EDGAR EPS series as SUE, which has already failed here.
- **Insider cluster buys / opportunistic insiders in large caps.** Already replayed: `insider_cluster` vs SPY
  -0.110R (t -2.39) and -0.115R (t -3.24); `opportunistic_insider_purchases_cmp` -0.082R (t -0.59) and -0.172R
  (t -2.77). Jeng, Metrick & Zeckhauser report a purchase portfolio earning more than 50 bp a month in 1975-1996
  with no significant small/large difference (abstract via search;
  https://scholar.harvard.edu/sites/scholar.harvard.edu/files/rzeckhauser/files/insider_trading.pdf not opened). I
  found no 2020+ study showing a large-cap, net-of-cost edge. A large-cap-only rerun would be a subset of a failed
  test with far fewer events.
- **13D activist drift in liquid names.** Already replayed: `activist_13d_drift` vs SPY -0.249R (t -1.92) and
  -0.154R (t -3.29). Brav, Jiang, Partnoy & Thomas put the abnormal return at about 7% around the announcement with
  no reversal (abstract via search; https://corpgov.law.harvard.edu/wp-content/uploads/2008/03/hedge_fund_activism-final.pdf
  not opened), which is earned before a filing-day buyer can act. No large-cap or post-2015 drift evidence found.
- **Industry momentum and time-series momentum on sector ETFs.** CXO, nine Select Sector SPDRs, Dec 1998-Dec 2015:
  holding the top sector by 6-month return made 4.4% a year (5.0% with a variant) against 4.6% for SPY and 6.2% for
  equal-weighted sectors, and three ranking intervals lose money after trading frictions
  (https://www.cxoadvisory.com/momentum-investing/simple-sector-etf-momentum-strategy-performance/ and
  .../simple-sector-etf-momentum-strategy-robustnesssensitivity-tests/, read through search summaries, pages not
  opened). No independent post-2015 test showing alpha was found. Engine: `faber_sector_rotation` (top 3 sectors
  with a 10-month trend filter, so it covers the time-series variant too) vs SPY -0.067R (t -0.42) and -0.052R
  (t -1.35); `industry_momentum_overlay` -0.160R (t -1.70) and -0.055R (t -1.48). Those were graded as signals at
  5-20 sessions, not as a monthly portfolio on alpha; given the external record a regrade is not worth a trial.
- **52-week-high momentum (George-Hwang) in large caps.** The catalog already grades `fifty_two_week_high_proximity`
  C: significant only at the 6-month horizon in the value-weighted replication (`docs/catalog/CATALOG.md`). Alpha
  Architect's reading of Hou-Xue-Zhang is that the signal is not robust to the holding period
  (https://alphaarchitect.com/52-week-high-q-factor-investment-model/, via search). No post-2005 US large-cap test
  found. Engine: `breakout_52w` vs SPY -0.055R (t -1.76) and -0.163R (t -5.12); the large-cap momentum portfolios
  (`xs_momentum_rank`, batch 3 residual momentum) had no alpha. The ratio-sort portfolio itself was never run; it
  is a third momentum variant on the same names.
- **Quality-minus-junk long leg.** Live index record: MSCI USA Sector Neutral Quality (the index behind QUAL)
  returned 13.94% a year over 10 years against 14.80% for MSCI USA, with 12.55% vs 17.31% in 2025 and 21.98% vs
  24.58% in 2024 (factsheet dated 2026-08-31, read through a search summary,
  https://www.msci.com/documents/10199/255599/msci-usa-sector-neutral-quality-index-usd-net.pdf, not opened). Batch 3's
  large-cap gross profitability, the main QMJ ingredient, had alpha +4.5% (t 1.43) and -3.1% (t -0.41).
- **Net payout / net issuance.** Batch 2's `large_cap_net_repurchasers` had alpha +1.5% a year (t 0.44) and 0.0%
  (t 0.00). The payout half needs dividends, which the store does not have.
- **Accruals, long leg.** Green, Hand & Soliman, "Going, Going, Gone? The Apparent Demise of the Accruals Anomaly"
  (Management Science 57(5), 2011; https://pubsonline.informs.org/doi/10.1287/mnsc.1110.1320, abstract via search):
  hedge returns are no longer reliably positive. A Columbia study argues it persists where institutions do not
  trade, which is the opposite of the liquid large-cap universe needed here.
- **Credit or volatility regime filters on SPY.** Goyal, Welch & Zafirov (RFS 37(11), 2024) re-test equity-premium
  predictors. Welch's results table (https://www.ivo-welch.org/home/card-eqpredict.html, read through a page
  summariser) lists the variance risk premium with an in-sample t of 0.12 and out-of-sample R2 of -8.88, the default
  yield spread with t 0.15 and the default return spread with t 0.90. Engine: `volatility_managed_spy` and
  `connors_cvr3_vix` failed. A VIX term-structure filter would need VIX3M or VIX futures, not in the store.
- **Seasonal sector rotation (Halloween effect in sectors; CFRA-Stovall).** Live record: the Pacer CFRA-Stovall
  Equal Weight Seasonal Rotation ETF (SZNE) returned 6.02% a year at NAV since inception on 2018-07-23 against
  13.41% for the S&P 500, 1.29% vs 12.06% over 5 years and -0.08% vs 18.32% over 3 years (fact sheet as of
  2026-03-31, https://www.paceretfs.com/media/szne.pdf, read from the PDF text). Its 6-month holds are also outside
  the holding-period limit.
- **Pre-FOMC announcement drift (Lucca-Moench).** Kurov, Wolfe & Gilbert, "The Disappearing Pre-FOMC Announcement
  Drift" (Finance Research Letters 40, 2021;
  https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf,
  abstract via search): the drift vanished after 2015. One-day holds, eight a year. The catalog already marks it
  avoid.
- **Momentum with the frog-in-the-pan filter (Da-Gurun-Warachka).** The closest live product, Alpha Architect's QMOM
  (large and mid-cap momentum with that filter), returned 10.26% a year at NAV from December 2015 to 2025-03-31
  against 10.39% for the S&P 500 (fund fact sheet via search,
  https://alphaarchitect.com/wp-content/uploads/compliance/etf/factsheets/Factsheet_QMOM.pdf, not opened). No alpha
  in ten years of live trading, and two momentum forms have failed here.
- **Threshold leg of the rebalancing paper.** Same source as the kept card, larger coefficient (-0.41, s.e. 0.11),
  but the position changes daily, and the combined strategy's largest gains came in late 2008 and March 2020 from
  leveraged long positions a long-only book cannot take. At 10 bp per side a daily SPY switch is not affordable, so
  only the month-end leg is carried forward.

Blocked by data, not researched further this session: dividend-payment price pressure (Hartzmark-Solomon 2025; the
3.2 bp per standard deviation figure is quoted in the Harvey paper, original not opened; needs dividend pay dates
and amounts), index additions (needs index membership history), 10-K text changes (needs filing text), 13F cloning
(needs 13F holdings), analyst-based surprise or revisions (needs estimates).

## Caveats
- Harvey-Mazzoleni-Melone numbers were read from text extracted from the PDF by a script (no PDF reader on this
  machine). Table values in the card should be re-checked against the PDF before they are quoted elsewhere. The
  first-business-day reversal leg of their strategy could not be read reliably and is not used.
- Not opened directly (numbers come from abstracts or search summaries, as marked): Martineau 2022, Subrahmanyam
  2025, He & Narayanamoorthy 2020, Jeng-Metrick-Zeckhauser, Brav et al., the CXO sector pages, the MSCI and QMOM
  fact sheets, Green-Hand-Soliman, Kurov-Wolfe-Gilbert, Goyal-Welch-Zafirov (table read through a summariser).
- The expected-size and power figures for the kept card are my arithmetic from the paper's coefficients, not
  published numbers.
- Nothing was replayed. Nothing outside this folder was changed.
