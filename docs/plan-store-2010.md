# Plan: a stock-level research store back to 2010

Owner approved 2026-10-14 19:20 UTC (card "Approve longer free history", option "All three"): AQR, Chen-Zimmermann,
and a free Tiingo account he creates himself. This is the plan for the stock-level part; nothing below touches
data/live/market.duckdb (research copies only), and nothing is graded on the new years until the owner says so.

## Why
Every weights card so far is graded on 2017-2026 (under 10 years). A real 3%-a-year edge with 6% tracking error has an
expected alpha t of about 3 / 6 x sqrt(years): 1.6 over 9.8 years, 2.0 over 16.8 years (2010-2026). The bars at 2.4-2.7
stay out of reach for most honest edges unless the window grows; the window is the binding constraint the scoreboard
names.

## What exists
- Bars: Alpaca SIP from 2016-01-04 (about 4,300 names) plus Massive from 2024-10-07; no stock bars before 2016.
- EDGAR XBRL facts (`fundamentals`, `fundamental_events`): filed from 2009-04-15; 915 filers with an event in 2010,
  2,215 in 2011, 2,767 in 2016. Point-in-time by `avail_ts` (acceptance time). Keyed by the CURRENT ticker map
  (company_tickers.json), so filers that stopped before about 2016 are missing.
- Splits from 2015, dividends from 2016 (Alpaca corporate actions).

## Steps
1. **Candidate list without prices.** EDGAR quarterly full-index (form.idx, every filer including dead ones, CIK +
   company name) for 2009-2016 10-K / 10-Q filers; companyfacts `dei:EntityPublicFloat` (dated, on every 10-K) ranks
   them by size with no price needed. Candidates: every CIK that is in the top 700 by public float in any year
   2009-2015. Expected about 900-1,000 CIKs, of which roughly 150-250 stopped filing before 2016 (acquired, failed,
   went private). Free, inside EDGAR's fair-access rate (the client already enforces it).
2. **Tickers for dead CIKs.** Tiingo's supported-tickers file (public) lists delisted tickers with first / last price
   dates but no CIK. Match by company name (normalised: suffixes, punctuation) plus date overlap (the ticker's last
   price within 120 days of the CIK's last filing); unmatched or ambiguous large names are listed for a hand check,
   never guessed. A ticker reused by a later company is only used for dates before its reuse.
3. **Bars 2010-01-04 .. 2015-12-31 from Tiingo** (`data/tiingo.py`): one request per symbol per span. Free tier: 500
   distinct symbols a month and about 1,000 requests a day, enforced in code. About 1,000 symbols -> **two calendar
   months** of quota (first month: the names that are top 500 in 2010-2012 and SPY, BIL, the sector ETFs; second:
   the rest). Each response is cached under data/raw/tiingo, so a rerun costs nothing.
4. **Splits and dividends 2010-2015** from the same responses (`splitFactor`, `divCash` per day): rows for the
   `splits` and `dividends` tables in the research copy, so the total-return path (`data.dividends`) works too.
5. **Fundamentals for dead CIKs**: companyfacts for the CIKs from step 1 that the store lacks, through the existing
   `parse_companyfacts` with the matched ticker as the symbol (delisted names keyed `TICKER~last date`, as now).
6. **Checks before any use**: (a) Tiingo vs Alpaca closes on 2016-01-04 .. 2016-06-30 for 50 names already in the
   store (requests only, no new symbols): median absolute difference after split adjustment under 0.1%; (b) the
   seam at 2016-01-04 continuous for every name in both; (c) each year 2010-2015 the store holds at least 480 of the
   500 largest by public float; (d) count of names that vanish before 2016 vs a published S&P 500 change count
   (descriptive).
7. **Store**: `data/live/replay_2010.duckdb` = a copy of replay_b9 plus the above (scripts/extend_research_store.py
   pattern); settings `config/prereg_2010.yaml`. `DATA_START` for research modules becomes a parameter.

## What needs the owner
- His free Tiingo account and `TIINGO_API_KEY=` in .env (asked in the thread 2026-10-14).
- Whether new cards are graded on 2010-2026 (a change to docs/gates.md, like the full-period test). Until he says
  so, the early years are descriptive only and past verdicts stay as they are.

## Known limits
- Coverage of small caps before 2016 stays thin (the quota fits large and mid caps only). Fine for the weights cards,
  which are all large-cap; not enough for a small-cap map.
- Tiingo is a single vendor for 2010-2015; step 6(a) is the only cross-check.
- EDGAR XBRL starts 2009 (large accelerated filers) and 2011 (everyone): signals that need a year-ago filing start
  in 2010 for large caps, 2012 for small.
