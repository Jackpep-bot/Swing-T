---
slug: composite_cost_aware_rank
name: Cost-aware composite rank with a buy/hold band (DeMiguel et al.; Novy-Marx-Velikov; Chen-Velikov)
originators: [DeMiguel, Martin-Utrera, Nogales & Uppal (RFS 2020), Novy-Marx & Velikov (RFS 2016), Chen & Velikov (JFQA 2023), Jensen, Kelly, Malamud & Pedersen (SSRN 4187217)]
category: strategy
decision: implement
holding_period_days: [21, 126]
timeframe: monthly rebalance (daily bars for features)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: built_disabled (pre-registered 2026-10-09)
---

# Cost-aware composite rank

## One-line summary
Stop trading each signal as its own strategy: combine a few slow, published, already-built signals into one rank,
hold the top names in one book, and only sell a name when it falls well out of the buy zone. Combining lets opposing
trades cancel and the band roughly halves turnover; this is the one design the cost literature finds survives.

## Origin and lineage
- Novy-Marx & Velikov, "A Taxonomy of Anomalies and Their Trading Costs", RFS 29(1) 2016. Peer-reviewed.
  https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf
- DeMiguel, Martin-Utrera, Nogales & Uppal, "A Transaction-Cost Perspective on the Multitude of Firm
  Characteristics", RFS 33(5) 2020. Peer-reviewed. https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2180-2222..html
- Chen & Velikov, "Zeroing in on the Expected Returns of Anomalies", JFQA 2023 (FEDS 2020-039). Peer-reviewed.
  https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf
- Jensen, Kelly, Malamud & Pedersen, "Machine Learning and the Implementable Efficient Frontier" (working paper).
- Engine relatives: catalog `cost_aware_rank_hysteresis` (grade A, decision implement, not yet built as a strategy),
  `xs_momentum_rank`, `residual_momentum`, `gross_cash_profitability`, `quality_minus_junk`, `beta_low_volatility`.

## Exact rules (engine design built from the published results; pre-register before running)
1. Universe at each month-end: price >= $5, 63-day median dollar volume >= $20M, not in the bottom NYSE-size
   quintile proxy (bottom 20% of the store's market cap). Excludes microcaps where published alpha concentrates and
   costs kill it (Avramov-Cheng-Metzker 2023).
2. Inputs (each a cross-sectional percentile, 0-1, computed point-in-time; all already in the engine or catalog):
   a. 12-1 month momentum (`xs_momentum_rank`), or residual momentum if built;
   b. gross or cash profitability (`gross_cash_profitability`, EDGAR XBRL by filing date);
   c. 52-week-high proximity (`fifty_two_week_high_proximity`);
   d. low 252-day volatility (`beta_low_volatility`).
   Fixed equal weights (no fitting). Score = mean of the four percentiles.
3. Buy zone: top 10% of score. Hold zone: top 20%. A held name is sold only when it leaves the hold zone
   (Novy-Marx-Velikov 10%/20% buy/hold band). Rebalance monthly, first session, next-open fills.
4. Equal weight or inverse-volatility weight, max 30-50 names, sector cap 30%.
5. Exit is the rank (rule 3); optional catastrophe stop at 3 x ATR(63) for the paper book only.

## Why it should work
- Trading diversification: a buy driven by one signal often offsets a sell driven by another, so the combined book
  trades far less than the sum of single-signal books (DeMiguel et al.).
- Band hysteresis removes the round trips caused by names hovering at the rank cutoff (Novy-Marx-Velikov).
- Slow signals only: turnover stays in the "low/mid" class that survives costs.

## When it works and when it fails
Momentum legs crash in sharp rebounds (2009-type); profitability and low-vol legs offset part of that. Expect long
flat stretches; net Sharpe in the literature is modest after publication.

## Parameters and sensitivity
Register exactly one version: four inputs, equal weights, 10%/20% band, monthly. Every extra variant is a trial.

## Evidence
- Novy-Marx & Velikov (1963-2012, value-weighted decile L/S, effective-spread costs): nothing in the high-turnover
  class (> ~5x a year per side) is significant net. Mid-turnover survivors include momentum (net 0.68%/mo, t=2.45)
  and ValMomProf (0.99%/mo, t=5.18). The buy/hold band cuts turnover 41% and costs 42% on average across 23
  anomalies (p.26). Momentum with a 10%/20% band: turnover 34.5% -> 18.8% per month per side, costs 0.65% -> 0.35%,
  net 0.68% -> 0.85% per month (Tables 3 and 6).
- DeMiguel et al. (abstract): with transaction costs the number of jointly significant characteristics rises from
  6 to 15, because combining reduces trading. Working-paper summaries (CXO Advisory; EDHEC; 51 characteristics,
  1980-2014) report about 65% less trading per characteristic from netting. Published-version numbers not checked.
- Chen & Velikov (120 anomalies): average anomaly 66 bps/month gross in-sample, 38 net in-sample, 13 net
  post-publication, 8 bps net post-publication and post-2005; strongest anomalies 10-20 bps after data-mining
  correction. Cost optimisation (bands + weighting) cut turnover 35% in-sample.
- Jensen-Kelly-Malamud-Pedersen (AEA 2024 programme summary, 1981-2020, $10B investor): learned cost-aware portfolio
  net Sharpe 1.38 at 32% monthly turnover vs -11.87 for a naive portfolio sort at 260% turnover. Long-short, large
  investor; magnitude will not transfer, the direction does.
- Grade B: peer-reviewed, cost-inclusive, with post-publication evidence that single anomalies are near zero.

## Why it might beat costs where the others failed
Every engine strategy so far trades one signal on its own, fires daily and is graded within 20 sessions: that is the
high-turnover class where nothing survives in any of these papers. This design is the opposite on all three counts,
and it is one pre-registered trial, not dozens.

## Common mistakes
Fitting the weights (overfits; Chen-Velikov warn further optimisation overfits); adding the 1-month reversal or
other fast signals as stand-alone legs; letting microcaps in; equal-weight long-short results quoted for a
long-only book.

## Implementation spec for swing-engine
Pre-registered in `docs/preregistration/2026-10-09-three-picks.md` (section 2). Module `strategies/composite_cost_aware_rank.py`; score `ccr_score`
(features.extra): equal-weight mean of same-session percentiles of `mom_12_1`, `gross_prof`, `dist_52w_high` and
minus 252-day realised vol, among names with close >= $5, 63-day median dollar volume >= $20M and market cap above the
session's 20th percentile; `ccr_score_rank` re-ranked by the replay among its universe. Month-end signals (fill the
first session), buy rank > 0.90, sell when rank <= 0.80 or missing (= `risk.selection.rank_hysteresis` 10%/20%),
catastrophe stop 3 x ATR(63), `max_hold_days` 10,000. Built as a per-signal strategy, not a target-weight book: the
replay's sizing and slot caps apply. Replay-only (CLI / nightly attach extras before `join_edgar`). Settings:
`composite_cost_aware_rank: {enabled: false}`. Tests: tests/test_strategy_three_picks.py.

## What the router should know
Core sleeve. Optional crash filter: `momentum_crash_filter_dm` scales the momentum weight to 0 in its bear state.

## Signs of decay to monitor
Trailing 24-month net excess return vs equal-weight universe <= 0; turnover above 40% per month.

## Sources
- https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf
- https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2180-2222..html
- https://www.cxoadvisory.com/equity-premium/integrated-approach-to-factor-investing
- https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf
- https://aeaweb.org/conference/2024/program/paper/SYTF3aaz
- https://papers.ssrn.com/abstract=3450322

## Empirical (replay)
Pre-registered group test (docs/preregistration/2026-10-09-three-picks.md, amendment 1), graded as a portfolio net of per-stock costs, n_trials = 3. **FAIL**: no positive haircut Sharpe in the 2024-26 window. Full table: docs/preregistration/2026-10-09-three-picks-results.md.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| composite_cost_aware_rank | 2024 | 127 | -0.195 | -0.90 | -0.42 | -0.42 | 0.07 | 14.1% | 68 | -140% | -10.1% |
| composite_cost_aware_rank | 2017 | 381 | +0.629 | 3.01 | 0.52 | 0.28 | 0.72 | 30.9% | 105 | 168% | +69.2% |
