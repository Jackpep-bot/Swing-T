# Spike: free daily bars for US stocks delisted 2017-2024 (2026-10-08)

This is the first step of "delisted-stock history for 2017-24" (proposal `free-data-sources-2026-10.md` section 9).
All tests used the repo's own clients (`AlpacaProvider` with feed=sip and split adjustment, the `MassiveProvider`
http/limiter, and plain Alpha Vantage CSV calls) and the keys in `.env`. Raw outputs went to the session
scratchpad. Nothing was written to any store.

Calls spent: Alpha Vantage 3 of 25/day. Massive 18 (5 aggregates, 12 reference, 1 ticker events). Alpaca about 15
(3 multi-symbol bars requests, 1 asset list, about 11 corporate-action pages).

## Verdict

**Feasible on free tiers. Alpaca is the only bar source, and it serves almost all of them.** Alpaca SIP daily bars
cover delisted names back to 2016-01-04: 27 of 28 test names and 97 of 100 random delisted common stocks. Massive
free returns 403 on any aggregate range before its 2-year window. Alpha Vantage gives no bars and its delisted list
is incomplete, but it is a useful cross-check. The hard parts are identity and the price at exit, not access:
- Alpaca keys history by symbol and stitches unrelated companies that reuse a ticker. It pads gaps with
  zero-volume rows at a stale price.
- Alpaca has no OTC tail after an exchange delisting, so bankruptcy losses are cut off at the last exchange close.
- The current store already contains this contamination: 228 stitched symbols and 192,598 zero-volume filler rows
  before 2024-10-07.

## 1. Test names x source

Delisting dates come from the source named in brackets. M = Massive `/v3/reference/tickers?active=false`
(`delisted_utc`). AV = Alpha Vantage `LISTING_STATUS`. Alp = Alpaca's last bar with volume. Alpaca bars were
requested for 2016-01-04..2024-10-06, SIP, split-adjusted. "0-vol" means zero-volume filler rows. Massive aggregates
were tried for TWTR, SIVB, CELG and BBBY (all 403) and for TUP 2024 (OK but 0 rows; TUP delisted before the window
opened). "Store" means `data/live/replay.duckdb`, opened read-only.

| Name (cause) | Delisted | Alpaca SIP daily bars | AV delisted list | Store |
|---|---|---|---|---|
| TWTR (taken private) | 2022-10-31 [M], 10-28 [AV] | 1,718 bars, 2016-01-04..2022-10-27, no gaps | yes | none |
| BBBY (bankrupt) | last trade 2023-05-02 [Alp]. M shows only the 2025 ticker reuse (2026-08-17, other CIK) | 1,845 bars to 2023-05-02 ($0.075). BBBYQ gives the same series | **absent** | **stitched**: old BBBY 2016..2023-05-02 + new BBBY 2025-08-29.. under one symbol |
| SIVB (bank failure) | 2023-03-28 [M] | 1,808 bars to 2023-03-09, last close $106.04 (holders got ~0) | **absent** | none |
| FRC (bank failure) | 2023-05-03 [M] | 1,843 bars to 2023-04-28 ($3.51). FRCB gives the same series | **absent** | none |
| SBNY (bank failure) | last trade 2023-03-10 [Alp] | 1,809 bars to 2023-03-10, then **395 0-vol rows at $70.00** through 2024-10-04 | **absent** | symbols row (OTC, "active"), no bars |
| SHLD (Sears, bankrupt) | last trade 2018-10-23 [Alp] | Sears: 708 bars, then **513 0-vol rows at $0.37**, then a sparse unrelated issue 2020-21, 484 0-vol rows, then the Global X ETF from 2023-09 | wrong entity (2020-11-06..2021-10-12) | SHLD = ETF, after the window only |
| JCP (bankrupt) | 2020-05-20 [M] | 1,101 bars to 2020-05-18 ($0.18) | **absent** | none |
| GNC (bankrupt) | 2020-06-30 [AV] | 1,130 bars to 2020-06-29 | yes | none |
| HTZ (bankrupt 2020, same CIK relisted 2021) | M events: HTZZ 2021-09-23, HTZ 2021-11-09 | **only 2021-11-09 onward**. Old Hertz 2016-2020 is unreachable (HTZ, HTZGQ and HTZZ return nothing for it) | absent | new HTZ from 2021-11-09 |
| CHK (bankrupt 2020, relisted 2021) | AV says 2024-10-04 (that is the EXE rename, not the 2020 event) | **stitched across bankruptcy**: trades to 2020-06-26, 156 0-vol rows, new equity from 2021-02-10. The 1:200 reverse split is adjusted, so 2016 prints near $1,000 | wrong date | none |
| YELL / YRCW (bankrupt) | 2023-08-16 [M] | YELL: 634 bars, only from 2021-02-08 (rename). **YELLQ: 1,917 bars from 2016** (full history) | absent | none |
| WE (bankrupt) | last trade 2023-11-07 [Alp] | 767 bars from 2020-10-21. The pre-merger SPAC (BowX) history sits under WE. WEWKQ returns nothing | absent | none |
| RAD (bankrupt) | last trade 2023-10-16 [Alp] | 1,131 bars, **only from 2019-04-22** (earlier history missing) | absent | none |
| TUP (bankrupt) | 2024-09-19 [M] | 2,191 bars to 2024-09-17 | absent | none (delisted 3 weeks before the store's Massive window) |
| CELG (acquired) | 2019-11-21 [M], 11-22 [AV] | 979 bars to 2019-11-20 | yes (latest and 2019 lists) | symbols row only |
| MON (acquired) | 2018-06-08 [AV 2019-12-31 list] | Monsanto: 611 bars to 2018-06-06, then **697 0-vol rows at $127.95**, then a SPAC 2021-22 | latest list: the SPAC. **Only the dated 2019 list shows Monsanto** | none |
| TWX (acquired) | 2018-06-15 [AV] | 617 bars to 2018-06-14 | yes | none |
| RHT (acquired) | 2019-07-08 [AV] | 883 bars to 2019-07-08 | yes | symbols row only |
| XLNX (acquired) | 2022-02-14 [AV] | 1,540 bars to 2022-02-11 | yes | symbols row only |
| WORK (acquired) | 2021-07-21 [AV] | 525 bars, 2019-06-20 (IPO)..2021-07-20 | yes | symbols row only |
| CERN (acquired) | last bar 2022-06-07 [Alp] | 1,619 bars | date wrong (2022-09-08) | symbols row only |
| CTXS (taken private) | last bar 2022-09-29 [Alp] | 1,698 bars | date wrong (2022-11-02) | none |
| ATVI (acquired) | 2023-10-13 [AV] | 1,959 bars to 2023-10-13 | yes | none |
| HZNP (acquired) | 2023-10-06 [AV] | 1,954 bars to 2023-10-06 | yes | none |
| VMW (acquired) | 2023-11-24 [M] | 1,986 bars to 2023-11-21 | **absent** | none |
| SGEN (acquired) | last bar 2023-12-13 [Alp] | 2,001 bars | date wrong (2026-10-07) | none |
| SPLK (acquired) | last bar 2024-03-15 [Alp] | 2,064 bars | date wrong (2026-10-07) | none |
| PXD (acquired) | 2024-05-03 [AV] | 2,097 bars to 2024-05-02 | yes | none |
| FB -> META (rename) | n/a | FB: 2016..2022-06-08. **META also returns full history from 2016** (two copies of the same company) | n/a | META full; FB = an unrelated ETF after the window |
| DISCA -> WBD (merger) | n/a | DISCA to 2022-04-08; WBD from 2022-04-11 | wrong row (blank name) | none |

**Store check (task step 3):** the Massive grouped-daily ingestion (2024-10-07 onward) holds **none** of these
entities. The only matching tickers (BBBY, HTZ, SHLD, FB) belong to different or reorganized companies. Delisted
rows in the store's `symbols` table have `delisted_at` >= 2024-10-07 only. About 2,700 non-OTC inactive rows with a
NULL `delisted_at` came from Alpaca's asset list (CELG, CERN, RHT, XLNX, WORK); they have no bars.

**Random sample (Alpaca coverage):** 100 random plain common stocks from AV's delisted list, delisted between
2017-01-01 and 2024-10-06:
- 97 have Alpaca bars.
- In 69, the last traded bar falls within 7 days of AV's delisting date; in 12 more, within 30 days.
- In 9, the last bar comes more than 30 days earlier (thin trading or a wrong AV date).
- In 7, bars run past the delisting date: the ticker was reused (AMTD, FUN, OXLCO ...).
- The 3 misses were CHKAQ, a preferred, and Point.360.

## 2. Enumerating the delisted universe 2017-2024 for free

| Source | What it gives | Limits found |
|---|---|---|
| **Massive `/v3/reference/tickers?market=stocks&active=false`** (free) | ticker, name, primary_exchange, type, **cik, composite_figi, delisted_utc**. History back to 2003. | **One row per ticker, the latest entity only.** BBBY shows the 2025 reuse; old Hertz has no inactive row. The `delisted_utc.gte` filter is ignored, so you page the whole inactive list alphabetically (1,000 rows per call; the first page covered only A-B, so expect roughly 15-25 calls, one night at 5/min). `vX/.../events` gives ticker changes (HTZZ -> HTZ). |
| **Alpha Vantage `LISTING_STATUS&state=delisted`** (1 call) | 9,547 rows (7,536 stocks, 2,011 ETFs). 5,327 stocks delisted 2017-2024, one row per symbol. | **Misses most bank failures and bankruptcies** (SIVB, FRC, SBNY, BBBY, JCP, HTZ, YELL, WE, RAD, TUP) and some deals (VMW). Several dates are wrong: SGEN and SPLK show 2026-10-07, CERN and CTXS are months off, CHK uses the 2024 rename. |
| AV `...&state=delisted&date=YYYY-MM-DD` | The list as of that date. **This recovers earlier owners of reused tickers** (2019-12-31 list: MON = Monsanto; 74 of 3,745 shared symbols had a different name than in the latest list). | 1 call per date. |
| AV `...&state=active&date=2017-01-03` | Returned `{}` on the free key. **There is no free point-in-time "active on date" list.** | |
| Alpaca `/v2/assets` (1 call) | 33,306 assets, 18,914 inactive. No dates. Useful to resolve the symbol Alpaca keys a name under. | |
| Alpaca `/v1/corporate-actions` | name_change, cash/stock_merger, worthless_removal | **Effectively starts 2019-2020**: 2017 has 4 events, 2018 has 2, 2020 has 1,131, 2024 has 1,598. Usable for cause (merger vs worthless) only from 2020. |

**Recommended enumeration:**
1. Use the full Massive inactive CS/ADRC list (about 20 calls) as the primary list. Filter
   `delisted_utc` in [2017-01-01, 2024-10-07).
2. Add the union of AV dated delisted lists at each year-end, 2017 through 2024 (8 calls, within 1 day of quota).
   This catches earlier owners of reused tickers.
3. Key every entity on (cik or composite_figi, ticker, delisting date), not on the ticker alone.

## 3. Ticker-reuse and identity pitfalls (all seen in the test)

1. **Stitching across companies.** One Alpaca symbol series can hold two unrelated companies: Monsanto then a
   SPAC; Sears then an ETF; old BBBY then a renamed Beyond Inc. **The store already has 228 symbols whose bar
   series has a gap of more than 30 days starting before 2024-10-07.** Examples: APC (Anadarko 2019 -> new APC
   2026), POM, ITG, Q, HAWK, BBBY. These are dead companies glued to new ones by the Alpaca extension, which chose
   symbols by their liquidity in 2024-26. They need splitting at the gap now; this is independent of the ingest.
2. **Zero-volume filler.** Alpaca writes flat zero-volume bars between owners or after a halt (SBNY: 395 rows at
   $70; MON: 697 rows). **The store has 192,598 zero-volume rows across 840 symbols before 2024-10-07.** A backtest
   can hold or exit a position at a stale price. Drop runs of volume == 0 (or flag them as no-trade).
3. **Renames put full history under the newest symbol, too.** META and YELLQ return the whole history, while FB and
   YELL return only their own period. Fetch each entity once, under its last symbol (find it via Massive events or
   the Alpaca asset list), and do not also fetch the old symbol. Otherwise you get double counts (FB + META).
4. **Bankrupt-then-relisted under the same ticker or CIK.** CHK is stitched across a 100% equity wipe-out. Old
   HTZ 2016-2020 is simply missing. Treat any 0-vol run longer than 20 sessions as an entity boundary.
5. **No OTC tail.** Alpaca SIP stops at the exchange delisting (SIVB's last close is $106, FRC's $3.51), and Massive
   free cannot reach the OTC period. Exit prices for performance delistings must be imputed.
6. **Partial histories.** RAD starts only 2019-04-22 and WE carries SPAC history. Accept these, but listed_at must
   come from the first real bar.

## 4. Ingest plan (proposal; needs approval before any write)

1. **Enumerate** (one night): Massive inactive tickers (about 20 calls) plus AV dated delisted lists (8 calls). Write
   a new table `delistings(entity_id, symbol, alpaca_symbol, name, cik, figi, delisted_at, cause, source)`, with
   `entity_id = f"{symbol}~{delisted_at:%Y%m%d}"`. Keep CS/ADRC only, and drop units, warrants, rights, preferreds
   and SPACs before their merger. Expect about 3,000-5,000 common stocks.
2. **Bars** (minutes): Alpaca SIP, split-adjusted, 2016-01-04..delisted_at, through the existing
   `AlpacaProvider.daily_bars` (100 symbols per request, so roughly 50 requests). Then:
   - truncate at delisted_at + 3 sessions;
   - drop zero-volume rows;
   - cut at any zero-volume run longer than 20 sessions (an entity boundary);
   - store the rows under `entity_id` as the bars symbol, so a reused ticker never collides with the live name.
   The rule thresholds (3, 20, 30 days) go in `settings.yaml` as versioned params, per CLAUDE.md rule 4.
3. **Point-in-time membership:** `symbols.listed_at` = first traded bar and `delisted_at` = last traded bar (the
   date the name drops out of the tradable universe). The universe at `as_of` is `listed_at <= as_of < delisted_at`
   plus the existing liquidity filter. No AV active-as-of list is needed.
4. **Delisting return:** the sample provider already models `delistings()` (symbol, reason, delisted_at); real data
   should use the same contract.
   - Cause: Alpaca corporate actions from 2020 (cash/stock merger vs worthless_removal). Before 2020, a heuristic
     (last close < $1, or a falling 60-day trend, means performance-related; otherwise merger).
   - Exit rule: a performance delisting is filled at last close x (1 + `delist_return_performance`), as a versioned
     constant. Shumway (1997) uses -30%; -100% is the conservative choice for bank failures and Ch.11 equity.
     Merger delistings exit at the last close.
5. **Repair existing contamination first** (no API calls): split the 228 stitched symbols at their pre-window gap
   into `symbol~lastdate` entities, and drop the 192,598 zero-volume rows. Re-run the leaderboard both before and
   after, so the effect of each fix is measured separately.
6. Record `ingest_meta['delisted_extension']` with the counts, and keep the "biased upward" label on the
   2017-2024 window until steps 1-5 are done.

## 5. What could make it infeasible (none fatal)

- **Exit prices.** Bankruptcy and failure exits are imputed, not observed (no free OTC bars). Results for
  mean-reversion and dip-buying setups will depend on `delist_return_performance`, so report a sensitivity check at
  -30% and -100%.
- **Missing entities.** Some histories are lost: old HTZ 2016-2020, CHKAQ, and early RAD. The sample suggests a few
  percent; this bias is small but nonzero.
- **Unverifiable entity matching before 2020.** Before 2020 there are no Alpaca corporate actions, so causes and
  some reused tickers depend on heuristics plus AV's error-prone dates.
- **Alpaca terms.** "Back to 2016" is the documented depth, so 2016 is the floor; there is no pre-2016 history.
  Rate limits were never hit at 200/min.
