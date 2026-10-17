---
slug: large_cap_opportunistic_insider_buys
name: Large-cap opportunistic insider purchases (Cohen-Malloy-Pomorski routine filter) as a 2%-slot satellite with SPY core, monthly
originators: [Cohen, Malloy & Pomorski (2012, JF) "Decoding Inside Information"; Lakonishok & Lee (2001, RFS); Seyhun (1986)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; SEC Form 4 (approved round 1, dated by filing acceptance); monthly rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $5
regimes_good: [choppy, recovery]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 22, 2026-10-14). WEIGHTS CARD. Insider family, trial 5 (after insider_cluster, ceo_cfo_buy_5day, opportunistic_insider_purchases_cmp, stine_insider_superstock_weekly; all engine cards). Bar alpha_t_critical(5).
---

# Large-cap opportunistic insider buys, satellite on SPY

## Why this card exists
Every earlier insider card was a stop-sized engine card with short holds in small and mid caps, the profile the
scoreboard shows always loses after costs. This one keeps the information (non-routine open-market purchases by
officers and directors) and moves it to the profile that does best here: large caps, 63-session holds, fully invested
with SPY as the core. Cohen-Malloy-Pomorski's value-weighted long-short alpha was 82 bp a month (t 2.15, 1986-2007);
the long side alone and large caps alone are weaker, which is why the expectation is modest.

## Engine version (pre-register this one)
- Data: Form 4 non-derivative transactions, code **P** (open-market purchase) only, dated by the filing's acceptance
  timestamp (point-in-time), never the transaction date. Reporting person is an officer or director (Form 4
  relationship flags); 10% owners that are neither are excluded.
- Routine vs opportunistic (CMP, as published): at the start of each calendar year, an insider is **classifiable** if
  they made at least one Form 4 trade (purchase or sale, codes P or S) in each of the three preceding calendar years;
  **routine** if they traded in the same calendar month in each of three consecutive prior years; otherwise
  **opportunistic**. Unclassifiable insiders are ignored. The label holds for the whole year.
- First usable year: the first January with three full prior calendar years of Form 4 in the store. Until then the
  book holds SPY (if the store starts 2016-01, the first classification is 2019-01; stated so the late start is not a
  surprise).
- Event: an opportunistic purchase with value (shares x price) of at least $50,000, filed while the company is in the
  500 largest by `mcap_pit` and its as-traded close is >= $5.
- Reference date: the last session of each month; orders at the next session's open.
- Holdings: every company with at least one event filed in the 63 sessions ending on the reference date.
- Weights: 2% per company, at most 50 companies (if more, keep those with the largest total event value divided by
  `mcap_pit`). **Cash treatment:** whatever weight the slots leave unused is held in SPY, never cash or BIL.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier. Costs: `weights_book.simulate`
  with the per-symbol table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover, from the weighting rule: each name sits in the book about three months, so the satellite turns
  over about four times a year; with the satellite at about 20-60% of the book and SPY trades to refill it,
  **100-250% a year one-way**; costs about 0.1-0.25% a year.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation (SPY-only months before the first usable
year are included as registered).
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: insider family count 5. Bar: `alpha_t_critical(5)` = 2.576.
Beside the verdict, descriptive only: average number of names and satellite weight, the satellite's own return against
SPY, the same book with routine purchases instead (CMP's placebo), and total-return-store figures.

## Expectation stated before the run
Large-cap insider buying is sparse (often 10-40 names at a time) and the purchases cluster in sell-offs (2018-Q4,
2020-Q1, 2022), so the satellite will be small and partly a buy-the-dip bet. Tracking error about 2-4%, alpha about 0
to +1.5% a year, pooled alpha t under 1. Likely FAIL; the routine-buy placebo shows whether the CMP split matters here.
