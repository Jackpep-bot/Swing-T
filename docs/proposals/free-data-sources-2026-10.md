# Free data sources: ranked proposal (2026-10-08)

Status: PROPOSAL ONLY. Nothing here is built. Jack approves before any ingest work starts.

Context: `docs/leaderboard.md` has no survivors after round-trip slippage and a Harvey-Liu haircut over 750
trials. Every strategy on the board is built from daily OHLCV plus the EDGAR fundamentals already ingested
(8-K Item 2.02 earnings dates, XBRL companyfacts). New data helps the board in three ways only:

1. **Unblock a strategy with published evidence that currently fires zero signals** (`insider_cluster`,
   `opportunistic_insider_purchases_cmp`, `connors_cvr3_vix` skipped, `short_interest_days_to_cover`).
2. **Fix a known bias in the inputs** (survivorship before 2024-10-07; the market-only proxy in
   `residual_momentum`; flat 10 bps cost in `research/cards.cost_r`).
3. **Gate 2 checks** (the CZ comparison in `docs/gates.md`).

More price-pattern variants do not belong on this list. Each one adds trials, which makes the haircut bigger.

Rules applied to every candidate: point-in-time on publication date, never on event or period date (CLAUDE.md
rule 3); delisted entities stay in; no network in tests (fixtures only).

---

## 1. SEC EDGAR Form 4 (insider transactions)

- **Terms:** free. The SEC says "Anyone can access and download this information for free". Fair access
  is "10 requests/second" with a declared User-Agent (company name plus contact email). No explicit license
  text. https://www.sec.gov/os/accessing-edgar-data
- **Two routes:**
  - **Insider Transactions Data Sets** (recommended for history): quarterly ZIPs, "January 2006 - September
    2026", flattened from the XML part of Forms 3/4/5 "without change from the as-filed submissions".
    Filings after 5:30 PM ET on a quarter's last business day go into the next posting.
    https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets
    The readme (https://www.sec.gov/files/insider_transactions_readme.pdf) lists the fields this needs:
    `REPORTINGOWNER` keyed by `ACCESSION_NUMBER` + `RPTOWNERCIK`; `RPTOWNER_RELATIONSHIP` (OFFICER, DIRECTOR,
    TENPERCENTOWNER, OTHER); `RPTOWNER_TITLE`; `SUBMISSION.FILING_DATE` (a date, no time of day);
    `PERIOD_OF_REPORT`; `NONDERIV_TRANS.TRANS_CODE`. The SUBMISSION file gained `AFF10B5ONE` (the Rule 10b5-1
    checkbox) in July 2025 for the 2023-2025 sets.
  - **Live / current quarter:** the per-filing XML via the submissions API, or the Atom feed the monitor
    already polls (`monitor/adapters/edgar.py` reads only the feed title; no Form 4 XML parser exists yet).
- **History:** 2006 Q1 onward. The CMP routine flag needs 3 prior years per insider, so it becomes usable
  from about 2009. That covers both replay windows.
- **Point-in-time:** good. Key on `FILING_DATE`, never the transaction date. With no time of day, the safe
  rule is the same as companyfacts: visible from the next session. Amendments (4/A) arrive as separate
  accessions, so keep the original and ignore the amendment, as `edgar.py` does for 8-K/A.
- **Delisted:** yes. Filings stay keyed by issuer CIK. The gap is CIK to ticker for dead names (see
  section 9).
- **Format:** tab-delimited text in ZIPs, roughly 16.5 MB for 2006 Q1 (from the page listing).
- **Evidence:** Cohen, Malloy and Pomorski (2012, JF). A routine insider traded in the same calendar month in
  prior years. Opportunistic trades carry "all the predictive power", with value-weighted abnormal returns of
  82 bps/month. Routine trades are about zero. That is a long-short monthly alpha, not a swing edge, and the
  sample is 1986-2007. https://www.nber.org/papers/w16454 ,
  https://papers.ssrn.com/abstract=1692517
- **Value to the board: HIGH.** Two registered strategies return zero signals today:
  `insider_cluster` (needs `insider_cluster_score`) and `opportunistic_insider_purchases_cmp` (needs
  `opp_buy_value_21d` and `opp_buy_flag`). Of everything on this list, this is the most plausible way to get a
  survivor. The signal is information-based, not a price pattern, it has an academic record, and it is
  orthogonal to the 125 OHLCV strategies already tested. It adds only 2 strategies x 3 horizons x 2 windows of
  trials. Apply the McLean-Pontiff halving from `docs/gates.md` gate 2.

## 2. SEC 13F holdings

- **Terms and route:** the same EDGAR terms. Form 13F Data Sets are quarterly ZIPs, "July 2013 - August
  2026". Since March 2024, each set covers the three months ending Feb/May/Aug/Nov.
  https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
- **Point-in-time:** usable only from the filing date. Filings arrive weeks after the quarter-end holdings date
  (statutory deadline not re-checked here), so holdings are stale by the time they are visible.
- **Delisted:** holdings reference CUSIPs, so a CUSIP-to-ticker map is needed. Not free in clean form.
- **Value: LOW for a 5-20 day swing book.** It is a quarterly, lagged, slow-moving signal. Possible later use
  as a universe filter (institutional ownership breadth). Not recommended now.

## 3. XBRL frames API

- **Terms:** free, no key. `data.sec.gov/api/xbrl/frames/` returns one fact per entity per calendar period:
  "the last filed fact that most closely fits the requested calendar period". Annual is CY####, quarterly is
  CY####Q#, instantaneous is CY####Q#I. Fiscal calendars vary, so facts in one frame can have different
  dates. The data updates in real time ("under a minute" processing). `companyfacts.zip` holds everything in
  Frames and Company Facts and is rebuilt nightly around 3:00 a.m. ET.
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- **Point-in-time: POOR as a feature source.** "Last filed" means restated values replace originals.
- **Value: LOW.** `companyfacts` is already ingested and keeps the `filed` date per fact, which is the
  point-in-time-correct source. Frames could act as a fast cross-sectional sanity check (coverage per
  quarter), but not as a feature. A related source is the **Financial Statement Data Sets** (quarterly,
  "January 2009 - September 2026", "without change from the as-filed" reports).
  https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets . That page does not say
  whether an acceptance timestamp is included. Check that before using it as an as-filed backup.

## 4. FINRA equity short interest

- **Terms:** free on finra.org. The page links a Terms of Use and notes FINRA Data is generally for
  non-commercial use. The API needs a credential, and the Public credential is "$0 per month".
  https://www.finra.org/finra-data/browse-catalog/equity-short-interest , https://developer.finra.org/fees .
  API limits are 1200 synchronous requests per minute per IP and 5000 records per synchronous request.
  https://developer.finra.org/docs
- **History:** the grid and API hold "five rolling years". Archive files go back to 2014, but before June 2021
  they cover only OTC securities, not exchange-listed ones.
  https://finra.org/finra-data/browse-catalog/equity-short-interest/files . So the free listed-stock history
  starts around mid-2021. Older listed short interest would have to come from Massive (Stocks Basic lists
  short interest, `docs/research-architecture.md`). Its depth on the free tier is unverified.
- **Point-in-time:** reported twice a month (mid-month and end-of-month settlement dates). Data is due by
  6 p.m. ET on settlement +2 business days and published on the 7th business day after settlement. Key the
  feature on that publication date, never the settlement date. Corrections carry a Revision Flag and only the
  latest version is kept, so revisions are not point-in-time. Accept that and log it.
- **Delisted:** rows exist for whatever was reported at the time.
- **Evidence:** days-to-cover (short ratio / turnover) predicts low returns; the long-short spread is about
  1.2%/month in the paper's sample (Hong, Li, Ni, Scheinkman and Yan, NBER w21166).
  https://www.nber.org/papers/w21166 . Aggregate short interest predicts market returns (Rapach,
  Ringgenberg and Zhou 2016, JFE 121(1)). https://ideas.repec.org/p/cuf/wpaper/716.html . A non-peer-reviewed
  replication says the effect weakens without the GFC (student thesis, https://thesis.eur.nl/pub/73709/Thesis_Final_Draft.pdf).
- **Value: MEDIUM.** It powers `short_interest_days_to_cover` (catalog: "strongest on the short/avoid
  side"). For a long-only book that is an avoid filter on existing longs: drop the top days-to-cover decile.
  A filter like that cuts losers and adds few trials. It also powers `aggregate_short_interest_index` as a
  regime overlay. With only about 5 years of listed history, it can be tested only in the
  survivorship-free window.

## 5. FINRA daily short-sale volume (Reg SHO)

- **Terms:** free files on `cdn.finra.org`, no key. The parser already exists in `swing_engine/data/altdata.py`
  (nightly CNMS fetch).
- **History:** Consolidated NMS (`CNMSshvol`) "back to August 1, 2018".
  https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files
- **Point-in-time:** posted "no later than 6:00:00pm ET" on the trade date, so the value is usable from the
  next session. Files can be revised and are labeled "Updated". Keep the first version.
- **Caveat:** covers only off-exchange short sales reported to a TRF, the ADF or the ORF, not total short
  volume. The academic daily-shorting evidence (Boehmer, Jones and Zhang 2008, JF) used proprietary NYSE
  order data, not these files. https://www.johnhcochrane.com/s/boehmer_jones_zhang_shorts.pdf
- **Value: LOW-MEDIUM.** A backfill from 2018 is cheap (one file per day). It gives a noisy squeeze or crowding
  feature. Treat it as a research feature, not a strategy.

## 6. Cboe VIX, VIX9D, VIX3M history

- **Terms:** free CSVs. Cboe says the data "is compiled for the convenience of site visitors" and is provided
  without warranty. https://www.cboe.com/tradable_products/vix/vix_historical_data/
- **History (checked by fetching the CSVs on 2026-10-08):** `VIX_History.csv` 1990-01-02 to 2026-10-07;
  `VIX9D_History.csv` 2011-01-04 to 2026-10-08; `VIX3M_History.csv` 2009-09-18 to 2026-10-08 (VIX3M is not
  listed on the page but sits at the same CDN path). Columns are DATE, OPEN, HIGH, LOW, CLOSE.
- **Point-in-time:** a daily close is known at the close, so it is usable for a next-open entry. Index levels
  are not revised.
- **Delisted:** not applicable.
- **Evidence:** the VIX term-structure slope prices variance risk and predicts variance-asset returns
  (Johnson 2017, JFQA 52(6)). It does not directly predict stock returns.
  https://ideas.repec.org/a/cup/jfinqa/v52y2017i06p2461-2490_00.html
- **Value: MEDIUM, and the cheapest item here.** It unblocks `connors_cvr3_vix` (skipped for no VIX; the
  rule is practitioner-sourced) and gives the playbook a risk-reducing regime overlay (VIX9D/VIX > 1 =
  backwardation, stand aside or shrink). Overlays are judged on drawdown, not on adding a survivor.

## 7. FRED (rates, credit spreads, yield curve)

- **Terms:** an API key is required. The Fed may set upper limits "at any time" and gives no number. For a
  third-party copyrighted series, "for anything other than your own personal use, you must contact the data
  owner". https://fred.stlouisfed.org/docs/api/terms_of_use.html
- **Series traps:** ICE BofA high-yield OAS (`BAMLH0A0HYM2`) is "Copyrighted: Pre-Approval Required", and
  "Starting in April 2026, this series will only include 3 years of observations".
  https://fred.stlouisfed.org/series/BAMLH0A0HYM2 . That makes it useless for a 2017+ backtest. Use Moody's
  `BAA10Y` instead (daily, "Copyrighted: Citation Required"; https://fred.stlouisfed.org/series/BAA10Y) and
  Treasury spreads such as `T10Y2Y` (daily; https://fred.stlouisfed.org/series/T10Y2Y).
- **Point-in-time:** market-price series (yields, spreads) are not revised. Macro series are, and ALFRED
  vintages via `realtime_start`/`realtime_end` (a closed interval) give as-of values.
  https://fred.stlouisfed.org/docs/api/fred/realtime_period.html . A daily series is visible next session at
  the earliest (T10Y2Y updated 4:03 PM CDT on 2026-10-08, per the series page).
- **Value: LOW-MEDIUM.** Regime overlays only (curve inversion, credit-spread widening). These add risk
  controls, not signals, so they are unlikely to create a survivor. Personal research use is fine.

## 8. Open Source Asset Pricing (Chen-Zimmermann) and Kenneth French library

- **OSAP:** current release "version 2.0.0" (October 2025), 212 predictors. Monthly long-short and portfolio
  sort CSVs, with daily portfolio returns in a Google Drive folder. Firm-level signals (209) come as a 1.6 GB
  zipped CSV. Most data runs through December 2024. Price, Size and STreversal "can be downloaded from CRSP"
  (not included). No license is stated on the data page. The code repo is GPL-2.0 and needs WRDS to rebuild.
  https://www.openassetpricing.com/data/ , https://github.com/OpenSourceAP/CrossSection
  - **Point-in-time:** the portfolio returns are research outputs, not tradeable signals. Use them only as the
    gate 2 CZ benchmark. The firm-level file is keyed by CRSP permno (not confirmed on the page), and there
    is no free permno-to-ticker link, so do not use it for live signals.
  - **Value: MEDIUM (process, not signals).** Gate 2 already requires the CZ correlation check by hand for
    `xs_momentum_rank`, `breakout_52w`, `short_term_reversal_1m`, `pead_sue`, `residual_momentum`,
    `earnings_announcement_*`, and the insider strategies. A script that downloads the long-short CSV once,
    outside tests, and writes the correlation into each card turns a manual step into a repeatable one.
- **Ken French data library:** daily FF3, FF5 (2x3), Momentum, ST Reversal, and 5/10/12/17/30/38/48/49
  industry portfolios. "We reconstruct the full history of returns each month", so history can change when
  CRSP revises. US returns use the CRSP CIZ format from the January 2025 release. Missing values are
  -99.99/-999. Copyright Fama and French; no explicit license.
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
  - **Point-in-time:** factors are published with a lag (the page header shows August 2026 data in October)
    and the history is rewritten monthly. That is fine for estimating betas over t-36..t-2 months. Never use
    the current month's factor.
  - **Value: MEDIUM.** It replaces the SPY-only proxy in `residual_momentum` (its docstring says "there is no
    Fama-French factor ingest") with the Blitz-Huij-Martens FF3 residual. It also gives
    `industry_momentum_overlay` and `faber_sector_rotation` a long industry history instead of 11 sector ETFs.
    `residual_momentum` had t 0.81 on 8,796 signals in the 2017-2024 window, so a correct implementation is a
    real test rather than a new look. It still costs trials.

## 9. Delisting and ticker-change history (survivorship before 2024-10-07)

Today the 2017-2024 window holds about 4,300 names still liquid in 2024 ("biased upward",
`research/cards.WINDOWS`). This is the largest bias in the board, and it inflates mean-reversion results the
most (dead names that kept falling are missing).

- **Nasdaq Trader symbol directory:** `nasdaqlisted.txt` and `otherlisted.txt`, "updated periodically
  through-out each day". Fields include Test Issue, ETF, and Financial Status (deficient, delinquent,
  bankrupt). Current snapshot only; the page says nothing about history.
  https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs . The historical Nasdaq Daily List (symbol
  changes, deletions back to 1999-05-24) is a paid product (a 2017 SEC filing gives $1,750/month;
  https://www.sec.gov/file/34-79701 , https://sec.gov/files/rules/sro/nasdaq/2024/34-100416.pdf). Value:
  LOW, except as a nightly snapshot from now on. Financial Status is a useful avoid flag.
- **SEC `company_tickers.json`:** current map only (779.98 KB). The page says nothing about inactive
  tickers. https://www.sec.gov/file/company-tickers . It is already the cause of the `no_cik_symbols` gap.
- **Alpha Vantage `LISTING_STATUS` (NEW, best free option):** "a list of active or delisted US stocks and
  ETFs, either as of the latest trading day or at a specific time in history". `date` accepts any date after
  2010-01-01, with `state=delisted`. The output is CSV. The free key allows 25 requests/day.
  https://www.alphavantage.co/documentation/#listing-status , https://www.alphavantage.co/support/ . Quarterly
  `state=active` snapshots for 2017-2024 (about 31 calls) plus one `state=delisted` call fit in 2 days of
  free quota. That gives the delisted symbol list, but not
  their bars.
- **Alpaca corporate actions:** `name_change` (old_symbol, new_symbol, CUSIPs, process_date),
  `worthless_removal`, mergers, and spin-offs. Free with the paper key. "Currently Alpaca has no guarantees
  on the creation time of corporate actions" and history depth is unstated.
  https://docs.alpaca.markets/reference/corporateactions-1
- **Massive ticker events:** `vX/reference/tickers/{id}/events` returns `ticker_change` history (described by
  a third-party connector page, not verified against Massive's docs; https://www.withone.ai/knowledge/massive/conn_mod_def%3A%3AGLtaDmjWi4A%3A%3APDXShh9WRwWvuNZy6kwnlg).
  At 5 calls/min it is usable for a few thousand dead names over a few nights.
- **Bars for the dead names:** Alpaca historical bars go "back to 2016" on the Basic plan with 200 calls/min.
  https://docs.alpaca.markets/docs/about-market-data-api . Whether Alpaca serves bars for symbols it no
  longer lists is UNVERIFIED and must be tested on a handful first. `extend_history_alpaca.py` pulled only
  names alive in 2024.
- **Value: HIGH for honesty, NEUTRAL-TO-NEGATIVE for survivor count.** Fixing the window makes the
  2017-2024 numbers lower, not higher. It still matters most: a survivor found on a biased window is not
  real.

## 10. Forward earnings-date calendar

- **Alpha Vantage `EARNINGS_CALENDAR`** (already wired in `swing_engine/data/alphavantage.py`): the next 3, 6
  or 12 months, all symbols in one CSV call, 25 requests/day free.
  https://www.alphavantage.co/documentation/#earnings-calendar
  - **Point-in-time:** forward dates move. History exists only if a snapshot is stored each day with its
    `as_of`. Backtests keep using the realized 8-K Item 2.02 dates (already ingested). Live uses the latest
    snapshot as a blackout filter.
  - **Value: LOW for the board, MEDIUM for live risk.** It prevents holding through an unknown earnings gap.
    The Empirical sections cannot score it until about a year of snapshots exists.
- **Finnhub** earnings calendar: free-tier rate limit and history window are UNVERIFIED (secondary sources
  disagree: 60 vs 50 calls/min). Not recommended until checked on a key.
  https://metacpan.org/pod/Finance::Quote::Finnhub ,
  https://www.interactivebrokers.com/campus/ibkr-quant-news/exploring-the-finnhub-io-api/

## 11. Others found (genuinely free, relevant)

- **SEC fails-to-deliver:** twice monthly, "February 2004 - September 2026". The first half of a month posts
  at month end and the second half around the 15th of the next month. Values are cumulative balances. Fails
  "are not necessarily the result of short selling". https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data
  Value: LOW. A squeeze/avoid flag in the small-cap monitor at most.
- **Nasdaq Reg SHO threshold list and SSR list:** already parsed in `data/altdata.py`. Nothing new to add.
- **Spread estimators from our own OHLC (no new data):** EDGE (Ardia, Guidotti and Kroencke 2024, JFE 161),
  Abdi-Ranaldo (2017, RFS 30(12)), and Corwin-Schultz (2012, JF). Covered in `docs/methods.md` (Optimization
  and overfitting controls). This is the cheapest high-value "data" item: it replaces the flat 10 bps.

---

## Ranked table

| rank | source | effort (plain words) | unblocks / improves | can it plausibly create a survivor? | point-in-time quality |
|---|---|---|---|---|---|
| 1 | EDGAR insider data sets (Form 4) + routine/opportunistic flag | moderate: one quarterly-ZIP loader, a join to CIK/ticker, the CMP routine rule, two panel columns | `insider_cluster`, `opportunistic_insider_purchases_cmp` (zero signals today), monitor Form 4 rule | **yes, best odds**: information signal with academic evidence, orthogonal to OHLCV, few added trials | good (filing date, next session) |
| 2 | Delisted-universe repair (AV LISTING_STATUS + Alpaca/Massive bars + Alpaca name changes) | moderate to large: symbol lists are easy, bars for dead names are the unknown | every strategy in the 2017-2024 window | no; it removes false survivors, which a gate needs | good if bars exist |
| 3 | Cboe VIX / VIX9D / VIX3M | small: three CSVs, one table, a few panel columns | `connors_cvr3_vix`, a regime overlay for all strategies | unlikely as a signal; overlays cut drawdown | excellent |
| 4 | Ken French daily factors + industries | small: zipped CSVs, a parser for -99.99 | `residual_momentum` done properly, `industry_momentum_overlay`, `faber_sector_rotation` | possible for `residual_momentum` (already t 0.81 pre-2024) | fair (history rewritten monthly; use lagged betas) |
| 5 | FINRA short interest (2021+ listed) | small to moderate: API credential or file archive, twice-monthly join on publication date | `short_interest_days_to_cover` avoid filter, `aggregate_short_interest_index` | indirectly (a filter that removes losers) | fair (latest-revision only) |
| 6 | OSAP long-short returns | small: one download script outside tests, a correlation per card | gate 2 CZ check, automated | no (it is a check) | n/a |
| 7 | FINRA daily short volume backfill (2018+) | small: the parser exists, just loop dates | crowding feature | unlikely | fair (keep first version) |
| 8 | FRED BAA10Y, T10Y2Y | small: API key, two series | regime overlays | unlikely | good for market series |
| 9 | AV forward earnings snapshots | small: the adapter exists; store daily with as_of | live earnings blackout | no (needs a year of snapshots) | good only from first snapshot |
| 10 | 13F, XBRL frames, fails-to-deliver | - | little for a 5-20 day book | no | poor to fair |

## Recommended first three

1. **Form 4 via the SEC Insider Transactions Data Sets.** Effort: moderate. One loader for quarterly ZIPs
   (SUBMISSION, REPORTINGOWNER, NONDERIV_TRANS). Visibility is the session after `FILING_DATE`. Filter to
   code P (open-market purchase) and keep owner relationship and title. A routine flag per CMP: the insider
   traded in the same calendar month in each of the 3 prior years. Produce `insider_cluster_score`,
   `opp_buy_value_21d` and `opp_buy_flag`, then rerun cards and the leaderboard. Fixture: one tiny quarter in
   `tests/fixtures`. This is the only candidate with a credible route to a survivor.
2. **Delisted-universe repair for 2017-2024.** Effort: moderate to large, with one unknown. Start with a spike
   on 20 known-dead tickers to see whether Alpaca or Massive returns their bars. If yes, pull AV
   `LISTING_STATUS` quarterly snapshots (2 days of free quota), map renames with Alpaca `name_change`, and
   backfill bars. If no, label the 2017-2024 window "survivors only" permanently and require survivors to
   come from the 2024-2026 window alone. The fix lowers numbers, but no other item can make a survivor
   believable.
3. **Cboe VIX family plus Ken French daily factors** (one small job, two tiny loaders). VIX unblocks
   `connors_cvr3_vix` and a term-structure overlay. French FF3 makes `residual_momentum` the paper's version
   instead of a SPY proxy. Both are a few CSVs with no rate limits.

Deferred: FINRA short interest (only about 5 years of listed history; take it after 1-3). OSAP automation
(do it when a strategy first gets close to gate 2).
