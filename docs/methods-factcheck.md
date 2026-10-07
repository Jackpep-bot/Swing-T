# Methods fact-check

Adversarial check of the deep dives in `docs/methods/`. `docs/methods.md` did not exist when this finished, so the
section is written here. Append it to `methods.md` once the synthesis exists.

## Fact-check (2026-10-06)

Method: for each claim, try to refute it from a primary source fetched today. Market data was recomputed from the
Yahoo chart API (`query1.finance.yahoo.com/v8/finance/chart/<sym>`) and the Treasury daily par-yield CSV. Limits:
the web-search quota ran out at the start, so only direct URL fetches were possible. investors.com and Business
Wire were blocked (403 or fetch-blocked).

| # | Claim (doc) | Verdict | Evidence |
|---|---|---|---|
| 1 | FINRA eliminated the PDT designation and the $25k minimum, effective 4 Jun 2026 (09) | Confirmed | FINRA Regulatory Notice 26-10 (20 Apr 2026): replaced by intraday margin standards, effective 4 Jun 2026, **phase-in to 20 Oct 2027**. Doc 09 should mention the phase-in, since brokers may lag. https://www.finra.org/rules-guidance/notices/26-10 |
| 2 | S&P 500 7,819, +14.2% YTD on 6 Oct 2026. Q3 2026: S&P +2.03%, Russell 2000 −7.52%, 10y at 5.29%. R2K ~+19% YTD to 31 Jul, ~9 pp ahead (04, 09, 14) | Confirmed | Yahoo: ^GSPC 7,818.93 (+14.22% YTD). Q3 ^GSPC +2.03%, ^RUT −7.52%. ^RUT +18.1% YTD to 31 Jul vs S&P +9.4% (8.7 pp). Treasury 10y par was 5.29 on 9/30 and 4.44 on 6/30, so Q3 was **+85 bp, not +88 bp**. https://www.firstfinancialtrust.com/2026/10/01/quarterly-market-review-july-september-2026/ ; https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value_month=202609 |
| 3 | 6 Oct 2026: 26.9% of 4,806 US stocks above the 50-day, 39.7% above the 200-day (01, 04, 06) | Confirmed (one vendor) | thetrading.tools shows 48.5 / 26.9 / 33.6 / 39.7% across 4,806 stocks. Not reproduced independently. Doc 04 places this next to a "thepatternsite banner" citation, but the breadth figures come from thetrading.tools. https://www.thetrading.tools/market-breadth |
| 4 | Fed hiked on 16 Sep 2026 under Chair Warsh (07) | Confirmed | FOMC: +25 bp to 3.75–4.00%, 12–0 vote. The Board page lists Kevin Warsh as Chairman. https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm ; https://www.federalreserve.gov/aboutthefed/bios/board/default.htm |
| 5 | "10-year yield at records above 5% (14 and 28 Sep)" (07) | **Refuted** | Treasury 10y par: **4.97% on 14 Sep** (below 5%) and 5.24% on 28 Sep. The month's high was 5.29% on 30 Sep. It was not a record: 10y yields were far higher in the 1980s. Reword as "highest in years, above 5% from late Sep". Same Treasury URL as row 2. |
| 6 | IBD follow-through days on 22 Apr 2025 (Day 11) and 8 Apr 2026 (Day 6) (07) | Unverifiable (IBD's call) | investors.com could not be fetched. The index data fits: on 22 Apr 2025 Nasdaq was +2.71% and S&P +2.51%, both on higher volume, Day 11 from 7 Apr. On 8 Apr 2026, Day 6 from 31 Mar, S&P was +2.51% on higher volume and Nasdaq +2.80% (on lower volume per Yahoo). The doc's "+2.2%" for that day matches neither index. |
| 7 | USIC results: Minervini +334.8% (2021, $1M+ division) and +155% (1997); Kell +941.1% (2020) (03, 12) | Confirmed (secondary / self-published) | Business Wire returned 403. The USIC "previous standings" page only shows 2025–26. Minervini's figures are quoted from the release by https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing . Kell's +941.1% (2nd place +497%) is from his own newsletter, https://theswingreport.com/ . Kell's "<$1M accounts" division is **unverified**. These are one-year contest results. |
| 8 | Qullamaggie FAQ: risk 0.3–0.5% (rarely >1%), positions 5–25% (mostly 10–15%), 25% win rate (2019), 268% CAGR 2013–19, 50% drawdown (2014) (05) | Confirmed as published | Every figure appears verbatim in the FAQ. All are self-reported and unaudited. https://qullamaggie.com/faq/ |
| 9 | PEAD decay: Martineau (CFR) finds no large-cap PEAD since 2006; Subrahmanyam finds t = 2.18 for all stocks and 1.43 ex-microcaps (02, 13) | Confirmed | Martineau's abstract: "For large stocks, PEAD have been non-existent since 2006." UCLA Anderson Review (21 Jan 2026): sample Feb 2001–Dec 2024, t 2.18 / 1.43. The Subrahmanyam paper is a 2025 SSRN paper; the docs label it 2025 and 2026 inconsistently. https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf ; https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/ |
| 10 | Bulkowski cup-with-handle: rank 3/39, 5% failure, +54%, 62% throwback, 61% hit target, 913 perfect trades (04) | Confirmed | All six numbers match. The page says examples were added on **7/25/25**; doc 04 says 10/25/2025. These are "perfect trade" statistics with no stops or costs. https://thepatternsite.com/cup.html |
| 11 | EasySwing panel (7 Jul 2026; ~2,000 stocks, 5-yr walk-forward, no fees) (01, 03, 04, 05, 07) | Confirmed (rates and PFs) | Trend Pullback 26% / 0.3R / PF 1.45 / 3d. VCP 37% / 0.1R / 0.38 / 4d. Template Fresh-Pass 40% / 0.1R / 0.99 / 4d. Cup & Handle 30% / 0.5R / 1.57 / 8d. Qullamaggie 27% / 0.1R / 1.10 / 7d. 17 detectors in all. The trade counts (1,092; 1,259; 18,382; 3,582; 16,943) were not visible in the fetch and are **unverified**. The figures come from a vendor, are gross of costs and may be tuned. https://easyswing.trading/performance |
| 12 | Zweig Breadth Thrust: 38% on 10 Apr 2025 to 61.7% at the 24 Apr 2025 close; Detrick: "19 for 19", with the S&P higher 6 and 12 months later (06) | Confirmed (secondary) | Sherwood News, 25 Apr 2025, quotes the rule (≤40% to ≥61.5% within 10 sessions) and Detrick's 19 signals since WWII, all higher at 6 and 12 months. The S&P closed at 5,484.77 on 24 Apr 2025 (Yahoo), matching doc 06. https://sherwood.news/markets/unusual-technical-indicator-with-perfect-track-record-sends-buy-signal-on-us |

### Also checked (not in the top 12)
- **FFTY vs SPY (07): confirmed approximately.** Yahoo total return to 6 Oct 2026, 10 years: FFTY 4.92%/yr vs SPY 15.51%/yr, which
  matches the doc. Five years: FFTY about −4%/yr, which is negative. The one-year figure depends on the as-of date: FFTY was −4.3% to 5 Oct
  and −7.1% to 6 Oct, against SPY +17.0% and +17.3%. The doc's −4.7% vs +17.7% is in range but not exact.
- **Stonks Capital Qullamaggie replication (05): confirmed.** It reports a 19% CAGR, −21% max drawdown and 2,382 trades from end-2007,
  with an SPY > 140 EMA filter (17 Feb 2025). Costs and slippage are **not stated**, so treat the results as gross.
  https://stonkscapital.substack.com/p/modeling-kullamagi-part-2-momentum

### What to fix in the docs
1. Doc 07, FIT section: replace "10-year yield at records above 5% (14 and 28 Sep)" with "10y touched 5.00-5.01% on 15-18 Sep, stayed above 5% from 23 Sep, and reached 5.29% on 30 Sep (Treasury par)".
2. Doc 07: drop the "+2.2%" for 8 Apr 2026 or replace it with S&P +2.5% / Nasdaq +2.8%. Mark both IBD FTD dates "index data consistent; IBD text not read".
3. Doc 09: change "+88 bp" to "+85 bp (Treasury par)", and add the FINRA phase-in end date (20 Oct 2027).
4. Doc 12: mark Kell's division size (<$1M) as unverified.
5. Docs 01/03/04/05/07: mark the EasySwing trade counts as unverified, or re-read them from the page source.
6. Docs 02/13: settle on one Subrahmanyam date (2025 paper; reported Jan 2026).
