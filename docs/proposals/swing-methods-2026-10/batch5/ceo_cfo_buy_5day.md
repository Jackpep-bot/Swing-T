---
slug: ceo_cfo_buy_5day
name: CEO or CFO open-market purchase, small/mid caps, short hold from the first session after the Form 4
originators: [Wang, Shin & Francis, "Are CFOs' trades more informative than CEOs' trades?", JFQA 47(4) 2012; Knewtson & Nofsinger 2014; Hossain 2010]
category: strategy
decision: implement
holding_period_days: [5, 5]
timeframe: daily bars + Form 4 (`insider_trades`)
direction: long
universe: SMALLMID
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; variant of catalog insider_cluster / opportunistic_insider_purchases_cmp)
---

# CEO/CFO buy, 5-session hold

## Why this one is different from what was tested
- `insider_cluster` needs at least two insiders; `opportunistic_insider_purchases_cmp` takes any insider; both hold
  weeks and both lost to SPY on the 1,500 most liquid names (batch 4 README).
- This card: (1) only the CEO or CFO, the two roles with the best published record; (2) small/mid caps; (3) a
  five-session hold, because post-2002 evidence says the edge moved into the first days after the filing.

## One-line summary
When a small or mid cap's CEO or CFO buys at least $25k of stock in the open market, buy the next morning and hold
five sessions.

## Origin and lineage
- Wang, Shin & Francis 2012 (via https://www.cxoadvisory.com/investing-expertise/cfos-vs-ceos-as-inside-traders/,
  opened): 1992-2002, CFO purchases +6.19% over 12 months, CEO +1.57%, most of the gap in months 1-9.
- Knewtson & Nofsinger (https://cxoadvisory.com/investing-expertise/cfos-still-the-best-inside-traders, opened):
  1992-2009 gross 4-factor alpha 15.4% (CEO) and 19.8% (CFO) a year, falling sharply after Sarbanes-Oxley.
- Hossain 2010 (via CXO, opened): the 2-day abnormal return after a purchase filing rose to 1.13% after SOX from
  0.32% before. That is why this card holds days, not months.

## Exact rules (as published)
Buy on day +2 after the Form 4 filing date, 12-month horizon, size/BM-adjusted. No size floor.

## Engine version (pre-register this one)
- Trade rows: `insider_trades` code P, original Form 4 only (already filtered at ingest), `is_officer` true and
  `officer_title` matching (case-insensitive) `chief executive|\bceo\b|chief financial|\bcfo\b`.
- Size: sum of `value` per (symbol, filing date) for qualifying rows >= $25,000. Routine buyers (Cohen-Malloy-Pomorski
  routine label from `cmp_labels`) excluded.
- Visibility: the session after the filing date (module rule). Entry: next open after that session's close becomes
  the signal session (i.e. first fill two sessions after filing, matching the paper's day +2).
- Skip if an earnings reaction session falls inside the next 5 sessions (`sessions_to_expected_earnings` <= 5).
- Exit: close of the 5th session held (fallback next open). Catastrophe stop entry x 0.85. Equal weight, max 15 open.

## Grading
Batch standard. Report CEO and CFO separately (two sub-rows, not two trials: the role split is descriptive only).

## Evidence
Grade C: strong pre-2009 record for the role filter; recent evidence only says the edge is front-loaded. Baptista
2024 (thesis, S&P 500, 2014-2022; https://run.unl.pt/bitstream/10362/173619/1/FALL24_42997_Rodrigo_Baptista.pdf,
opened, low quality) found only 1-5 day holds beat the market. Rozeff & Zaman 1988: with 2% costs outsider profits
are about zero.

## Expectation stated before the run
+0.5% to +1% per trade gross, near zero net in the smaller names; about 150-300 trades a year.

## Common mistakes
Counting option exercises or grants (code M/A) as buys; using the transaction date instead of the filing date.

## Signs of decay to monitor
Trailing 100-trade mean net return <= 0.
