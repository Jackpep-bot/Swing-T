---
slug: pullback_trend_avoid_402
name: pullback_trend minus recent 8-K Item 4.02 (restatement) names
originators: [engine filter; restatement evidence Palmrose, Richardson and Scholz (JAE 2004)]
category: filter
decision: implement_disabled_for_comparison
holding_period_days: same as pullback_trend
timeframe: daily
direction: long
regimes_good: same as pullback_trend
regimes_bad: same as pullback_trend
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B (announcement reaction only; no evidence read for a post-announcement drift)
free_data_ok: true
status: built_disabled
---

# pullback_trend, avoiding recent restatements

## One-line summary
`pullback_trend` (docs/strategies/pullback_trend.md), but skip any symbol whose 8-K Item 4.02 (non-reliance on previously
issued financial statements) became public in the last 63 sessions. A demonstration of the general avoid filter in
docs/methods.md ("Event avoid filters").

## Exact rules
- All `pullback_trend` rules, stop and target unchanged (subclass in `strategies/news_filters.py`).
- Drop the signal when `days_since_402 < avoid_402_sessions` (default 63, about one quarter) on the signal session.
  `days_since_402` counts sessions from the reaction session of the latest ORIGINAL 8-K listing Item 4.02 (acceptance
  time, after-close filings roll to the next session; 8-K/A ignored). NaN (no 4.02 on record) passes.
- No `days_since_402` column (no `eightk_items` table): no signals, so the variant is never scored on missing data.

## Why it should work
A restatement is a credibility shock: the announcement reaction is large and negative, and trend pullbacks right after
it are buying into a re-rating rather than a pause.

## Parameters and sensitivity
`avoid_402_sessions` 63: engine choice, **not from a source**. Each other value is a separate trial.

## Evidence
- Palmrose, Richardson and Scholz (2004), "Determinants of market reactions to restatement announcements", *Journal of
  Accounting and Economics* 37(1), 59-89. **Peer-reviewed.** Read this session: the abstract summary only (via
  https://ideas.repec.org/a/eee/jaecon/v37y2004i1p59-89.html and https://academicnewsletter.sufe.edu.cn/info/412647):
  403 restatements announced 1995-1999, average two-day abnormal return about -9%, more negative for fraud, more accounts
  affected, and income-reducing restatements. That is the announcement window, which this filter cannot trade; **no
  number for a post-announcement drift was read**, so the filter's value is unproven. Gross returns.
- Coverage caveat: only issuers with a
  CIK in company_tickers.json are fetched.

## Implementation spec for swing-engine
`strategies/news_filters.py: PullbackTrendAvoid402`; data `swing ingest-edgar` (or `--8k-only`), table `eightk_items`,
join `data.filings.join_filings` via `join_edgar`. Settings: `pullback_trend_avoid_402: {enabled: false,
avoid_402_sessions: 63}`. Tests: tests/test_strategy_event_filters.py.

## Sources
- https://ideas.repec.org/a/eee/jaecon/v37y2004i1p59-89.html
- https://academicnewsletter.sufe.edu.cn/info/412647

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4681 | 149 | 51% | +0.02 | -0.11 | 46% | +0.00 | -0.12 | 43% | +0.05 | -0.08 | 1.10 |
| correction | 362 | 9 | 39% | -0.21 | -0.37 | 43% | -0.11 | -0.28 | 42% | -0.04 | -0.21 | 0.93 |
| healthy_uptrend | 25012 | 777 | 46% | -0.03 | -0.16 | 43% | -0.05 | -0.18 | 40% | -0.03 | -0.17 | 0.94 |
| high_vol_selloff | 1797 | 58 | 49% | -0.03 | -0.15 | 46% | -0.03 | -0.15 | 34% | -0.17 | -0.29 | 0.73 |
| narrow_uptrend | 1655 | 37 | 36% | -0.18 | -0.31 | 36% | -0.19 | -0.33 | 30% | -0.22 | -0.37 | 0.66 |
| **all** | 33507 | 1030 | 46% | -0.03 | -0.16 | 43% | -0.05 | -0.18 | 40% | -0.04 | -0.17 | 0.94 |

Portfolio replay (net of costs, slots shared with its run): 3 trades, win 33%, avg -0.51R, PF 0.24, P&L $-1,050 on $100k, avg hold 18.3 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 15135 | 824 | 54% | +0.08 | -0.05 | 53% | +0.14 | +0.02 | 49% | +0.19 | +0.06 | 1.40 |
| correction | 5940 | 235 | 51% | +0.01 | -0.12 | 46% | -0.01 | -0.15 | 42% | +0.01 | -0.13 | 1.01 |
| healthy_uptrend | 88497 | 4980 | 49% | +0.00 | -0.13 | 46% | +0.01 | -0.12 | 42% | +0.02 | -0.11 | 1.04 |
| high_vol_selloff | 7266 | 397 | 51% | +0.01 | -0.12 | 49% | +0.03 | -0.11 | 43% | +0.00 | -0.13 | 1.01 |
| narrow_uptrend | 14768 | 769 | 51% | +0.04 | -0.08 | 50% | +0.06 | -0.06 | 45% | +0.07 | -0.05 | 1.14 |
| **all** | 131606 | 7205 | 50% | +0.02 | -0.11 | 48% | +0.03 | -0.10 | 43% | +0.04 | -0.09 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 13 trades, win 46%, avg +0.54R, PF 2.13, P&L $6,580 on $100k, avg hold 19.8 bars.
