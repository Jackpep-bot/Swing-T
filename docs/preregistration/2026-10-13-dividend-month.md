# Pre-registration: dividend month premium (one card, total-return grading)

Committed 2026-10-13 **before** any replay of this rule exists on any data. The dividend ingest, the signal and the
total-return store were written and tested without running the strategy. Nothing below may change after the first
replay except a harness-only amendment (a bug that stops the rules as written from running), written into this
file before results are read.

Card: project file `research/strategies/dividend_month_premium.md` (Hartzmark & Solomon, "The Dividend Month
Premium", JFE 2013; Chen-Zimmermann signal `DivSeason`). It was blocked on two things, both now built with the
owner's yes of 2026-10-13: ex-dividend dates (Alpaca's free corporate-actions feed) and total-return grading.

## Expectation, stated before the run
The published long-only edge is small: predicted payers earned a four-factor alpha of 0.41% a month equal-weighted and
0.24% value-weighted, gross, 1927-2009 (CXO's summary of the paper; tables not read). This card buys large, liquid
payers, so the 0.24% is the relevant number: about 2.9% a year gross. One round trip a month at 10 bp a side costs
about 2.4% a year. **Expected net alpha: about zero. Expected verdict: FAIL.**

Power, plainly: a 50-name equal-weight book differs from SPY by roughly 6 to 8% a year. An alpha t of 1.96 over the
two-year window needs about 9 to 11% a year of alpha, several times the published gross effect. The card **cannot
pass window B even if the paper is exactly right**; the run tells sign and size only. It is run because it is the
last candidate card never tested and the owner asked for it.

## Data
- `dividends` table (`swing ingest-dividends`, `data/dividends.py`): 367,989 cash dividends, every symbol,
  2016-01-04 on, fetched 2026-10-13. Rates are as paid and are divided by later split ratios (`splits`). A row is
  keyed by the ticker on its ex-date and moved to the store's series for that security on that day (renames merged
  2026-10-13, delisted keys); 367,554 rows map, of which 74% land on a symbol with bars (the rest are funds and
  names the store does not carry).
- The feed is today's record of past dividends, not a point-in-time vintage. Ex-dates are historical facts; the
  signal reads only ex-dates up to the decision day.
- Store: `data/live/replay_tr.duckdb` (config/prereg_div.yaml), a copy of the repaired live store taken 2026-10-13
  with every bar back-adjusted for the dividends that went ex after it (`data.dividends.total_return_adjust`:
  145,353 dividends applied; 135 left out because one payment was 25% or more of the previous close). Close-to-close
  returns in this store are total returns, for the book and for SPY alike. The live store is not adjusted.

## Rule (`swing_engine/strategies/dividend_month_premium.py`)
| Item | Value | Source |
|---|---|---|
| Decision day | the last NYSE session of each month | card |
| Frequency | number of distinct ex-months of **regular** (non-special) dividends in the 12 months ending with the decision month: 1 = annual, 2 = semi-annual, 3 to 5 = quarterly, 6 or more = monthly (left out) | **reading**: Chen-Zimmermann use CRSP's declared frequency; the feed has none |
| Predicted payer | went ex 3, 6, 9 or 12 months before next month (quarterly), 6 or 12 (semi-annual), 12 (annual) | Chen-Zimmermann `DivSeason` (their "2, 5, 8, 11 months ago" counted from the decision month) |
| Universe | predicted payers with a market cap from EDGAR share counts (`mcap_pit` not missing), close >= **$5**, 63-day median dollar volume >= **$20M** | card; the EDGAR requirement is **added**: the store's symbol type calls ETFs common stock, and funds do not file share counts |
| Selection | the **50** with the largest 63-day median dollar volume | **registered deviation** from the paper's all-payers portfolio: the book has 50 slots, and the liquid end is where the value-weighted result and this engine's costs meet |
| Entry | next session's open (the month's first session) | card |
| Exit | at the open after the next month's last session, unless predicted again that day | card says month-end close; the engine sells at the next open (one extra overnight) |
| Stop | 3 x ATR(63) below the entry close, catastrophe stop only | engine convention of the monthly books (batch 2, 3) |
| Target, trail, regime gate | none (`engine_trail = False`) | card |
| Book | equal weight 2%, 50 positions, up to 50 new orders a day (config/prereg_div.yaml) | as the batch 2 and 3 books |

Readings fixed here: price and dollar-volume filters read the total-return bars, so an old price is lower than it
traded by the dividends paid since (about 13% for SPY in 2017, more for high yielders); special dividends do not
count for the signal but are in the total return; a name's first months of monthly payments can look quarterly.

## Run
```
nohup uv run python -m swing_engine.research.prereg_run --settings config/prereg_div.yaml --tag-prefix prereg-div- \
  --slugs dividend_month_premium --n-trials 1 --benchmark SPY --alpha-slugs dividend_month_premium \
  --out docs/preregistration/2026-10-13-dividend-month-results.md > data/logs/research/prereg_div.log 2>&1 &
```
Windows as every pre-registered group: 2017-01-01 .. 2024-10-04 and 2024-10-07 .. 2026-10-05. One run, one trial
group (n_trials = 1); the trial is logged with the rest.

## Pass rule
As batch 3 (`docs/preregistration/2026-10-10-batch3.md`), with one trial. PASS needs, in **both** windows:
1. the standard rule: haircut Sharpe > 0 and net R per trade > 0, net of replay costs and the spread top-up;
2. alpha vs buy-and-hold SPY > 0 with **alpha t >= 1.960** (two-sided 5%, one trial; `prereg_eval.alpha_t_critical(1)`),
   OLS of the daily net return on SPY's close-to-close return in the same total-return store.
Otherwise FAIL.

## What a pass allows
Shadow-only tracking and a walk-forward; the live scan would first need the dividend join and dividend cash in the
paper ledger. Paper trading needs `docs/gates.md`.
