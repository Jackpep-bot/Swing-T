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
