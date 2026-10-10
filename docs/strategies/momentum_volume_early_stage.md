---
slug: momentum_volume_early_stage
name: Early-stage momentum, low-turnover winners (Lee-Swaminathan)
originators: [Lee & Swaminathan, "Price Momentum and Trading Volume", Journal of Finance 55(5) 2000]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [126, 126]
timeframe: monthly sort (6-month return x 6-month share turnover)
direction: long (the paper's early-stage strategy is long low-volume winners / short high-volume losers)
regimes_good: []   # not studied in the paper
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: built_disabled (pre-registered 2026-10-10)
---

# Early-stage momentum (low-turnover winners)

## One-line summary
Among six-month winners, the ones that got there on LOW share turnover keep their gains for years, while
high-turnover winners give them back; low-turnover winners are "early stage" momentum.

## Origin and lineage
- Lee & Swaminathan, JF 55(5), October 2000, pp. 2017-2069. Peer-reviewed. Read this session: the published
  article, copy at https://www.johnhcochrane.com/s/lee_swaminathan_returns_volume_JF.pdf .
- Builds on Jegadeesh-Titman momentum (`xs_momentum_rank`) and Datar-Naik-Radcliffe turnover. Relatives in the
  engine: `high_turnover_short_term_momentum` (1-month horizon, opposite turnover side), `high_volume_return_premium`
  (one-day volume shock).
- Chen-Zimmermann signal for the gate-2 CZ check: not identified this session (SignalDoc.csv not opened); look for
  the Lee-Swaminathan momentum-volume entry and check which leg it codes. Planning assumes at most half the edge.

## Exact rules (as published)
1. Sample: NYSE and AMEX firms, January 1965 to December 1995, at least two years of data before formation; no
   Nasdaq (dealer double-counting inflates its volume); no ADRs, REITs, closed-end funds, foreign firms, primes;
   price at formation >= $1.
2. Volume = average daily turnover over the formation period, turnover = shares traded / shares outstanding.
3. At the start of each month, two INDEPENDENT sorts over the same J months: return deciles R1 (losers) .. R10
   (winners), turnover terciles V1 (low) .. V3 (high). J = 3, 6, 9, 12; holding K = 3, 6, 9, 12 months,
   equal-weighted, overlapping cohorts; one week skipped between formation and holding (one month gives similar
   results, footnote 10).
4. Early-stage strategy = long R10V1 (low-volume winners), short R1V3 (high-volume losers). Late-stage = long
   R10V3, short R1V1.

## Engine version (pre-register this one)
- Last NYSE session of each month. Formation: 126 sessions ending 5 sessions before the signal day. Return =
  close[t-5] / close[t-131] - 1; turnover = mean of daily volume / point-in-time EDGAR shares outstanding over the
  same 126 sessions (all 126 required).
- Independent sorts over the session's scanned universe: top return decile AND bottom turnover tercile.
- At least 504 bars of history. Long only; entry next open; exit after 126 sessions (K = 6); no target. Stop
  3 x ATR(63) (engine choice so the engine can size; the paper has no stop).
- Not coded: the NYSE/AMEX-only sample, the short leg, equal-weighted overlapping cohorts.

## Why it should work
The authors' "momentum life cycle": low turnover marks neglected stocks early in a re-rating (value-like, low
analyst coverage, positive later earnings surprises), high turnover marks glamour stocks late in it. They argue
turnover is not a liquidity proxy here.

## Evidence
Published article, NYSE/AMEX 1965-1995, equal-weighted, gross of costs (no cost analysis in the paper).
- Table II, J = 6, average monthly return of low-volume winners (R10V1): 1.63% (K=3), 1.67% (K=6), 1.72% (K=9),
  1.66% (K=12); high-volume winners (R10V3): 1.57%, 1.55%, 1.56%, 1.42%. The difference V3-V1 among winners is
  -0.06% (t=-0.31), -0.12% (t=-0.67), -0.16% (t=-0.89), -0.23% (t=-1.34) a month: NOT significant in the first year
  (the text says so too). Middle-return, low-volume stocks (R5V1) earn 1.37% (K=3) and 1.36% (K=6).
- Table II, J = 6, K = 6: momentum spread R10-R1 is 0.54% a month (t=2.07) in low-volume stocks and 1.46% (t=5.93)
  in high-volume stocks; the volume effect in the first year comes mostly from losers (R1V1 1.12% vs R1V3 0.09%).
- Table VI Panel A, J = 6, raw annual returns: R10V1 20.64% in year 1 and 19.58% in year 2; R10V3 19.20% and
  13.14%; V3-V1 among winners -1.44% (t=-0.65) in year 1 and -6.44% (t=-3.15) in year 2. Industry-adjusted R10V1:
  3.00% (t=2.39) year 1, 3.10% (t=2.10) year 2; size-adjusted 3.45% (t=2.57), 2.74% (t=1.64).
- Table VII Panel A (long-short): early-stage 16.70% in year 1 (t=5.85), 6.19% year 2, 5.85% year 3; simple
  momentum 12.49% (t=5.04) then about zero or negative; late-stage 6.84% then -5.35%. Largest 50% of firms (Panel G,
  5x5 sort): early 11.16% in year 1 (t=3.87) vs simple 7.71%; the early-minus-simple difference there is 3.45%
  (t=1.34).
- Sample ends 1995; no later or post-publication test read this session.
- Grade B (peer-reviewed, gross, old sample). For a LONG-ONLY six-month hold the paper's own numbers show a small,
  statistically insignificant edge of low- over high-volume winners; the edge is in years 2+ and in the short leg.

## Why it might beat costs, and why it probably adds little on its own
For: about two round trips a year per slot; winners are larger and higher-priced than losers (Table I: median
size decile 5.05 and price $19.41 for R10 vs 3.56 and $9.00 for R1, J = 6). Against: the long leg's
advantage over plain winners is insignificant inside the first year, which is the whole holding period here, so
this is mostly a momentum book with a value-like tilt. Kept as a pre-registered comparison; the research note
suggests it is more useful as a fifth input to `composite_cost_aware_rank` than as its own book.

## Common mistakes
Ranking raw share volume (a size proxy) instead of turnover; using stale or look-ahead share counts (use the
point-in-time EDGAR value); conditional instead of independent sorts; mixing listing venues with different volume
conventions; expecting the first-year long-only return to differ much from plain momentum.

## Implementation spec for swing-engine
Pre-registered in `docs/preregistration/2026-10-10-two-picks.md` (section 2). Module
`strategies/momentum_volume_early_stage.py`: reads the panel column `turnover` (`data.fundamentals.join_edgar`,
volume / shares outstanding as filed) and extras `month_end`, `hist_bars`, `atr_63`; silent when the panel has no
`turnover` column (no relative-volume proxy). On `month_end`: formation return and mean turnover over 126 sessions
ending 5 sessions earlier, independent percentile ranks over the scanned rows with both values and `hist_bars` >=
504; fire on return rank > 0.90 and turnover rank <= 1/3. Entry next open, stop 3 x ATR(63), no target,
`max_hold_days` 126, `engine_trail = False`, score = return rank - turnover rank. Settings:
`momentum_volume_early_stage: {enabled: false, min_reward_risk: 0.0}`. Tests: tests/test_strategy_two_picks.py.

## What the router should know
A momentum book: expect momentum-crash behaviour in sharp rebounds (not studied in this paper).

## Signs of decay to monitor
Trailing 24-month average 126-session return of the picks minus that of all top-decile winners <= 0.

## Sources
- https://www.johnhcochrane.com/s/lee_swaminathan_returns_volume_JF.pdf (published article, read)
- https://ideas.repec.org/a/bla/jfinan/v55y2000i5p2017-2069.html (citation)

## Empirical (replay)
Pre-registered group test (docs/preregistration/2026-10-10-two-picks.md), graded as a portfolio net of per-stock costs, n_trials = 2. **FAIL**. Full table: docs/preregistration/2026-10-10-two-picks-results.md.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| momentum_volume_early_stage | 2024 | 81 | -0.228 | -1.05 | -0.26 | -0.26 | 0.19 | 12.2% | 43 | -215% | -5.1% |
| momentum_volume_early_stage | 2017 | 430 | +0.130 | 1.09 | 0.18 | 0.00 | 0.50 | 30.5% | 57 | 555% | +12.7% |
