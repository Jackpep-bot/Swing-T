---
slug: connors_tps_scale_in_no_news
name: connors_tps_scale_in on no-news sessions only
originators: [Larry Connors (base rules), Wesley S. Chan (no-news filter, JFE 2003)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: same as connors_tps_scale_in
timeframe: daily
direction: long
regimes_good: same as connors_tps_scale_in
regimes_bad: same as connors_tps_scale_in
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B (direction of the filter only; base rules D)
free_data_ok: true
status: built_disabled
---

# connors_tps_scale_in + no-news filter

## One-line summary
Take `connors_tps_scale_in` signals (docs/strategies/connors_tps_scale_in.md) only when the stock had no news on the signal session: a drop without
news is more likely to be noise that reverses than information that keeps drifting.

## Origin and lineage
Base rules: Connors (see the base card). Filter: Chan (2003). One of three variants chosen as the mean-reversion
strategies with the most signals on docs/leaderboard.md (2024-26 window, 2026-10-09):
connors_rsi2_variants, connors_tps_scale_in, connors_hpetf_rsi_variants.

## Exact rules
- Every rule, stop, exit and param of `connors_tps_scale_in` unchanged (subclass, `strategies/news_filters.py`).
- Extra condition on the signal session (the close the signal is taken on):
  - `news_source: benzinga`: `news_flag_1d == 0`, i.e. no Benzinga article tagged with the symbol and published (created_at)
    in the 24 hours before that session's close (`data.news`, Alpaca historical news, free plan).
  - `news_source: 8k`: `news_8k_flag_1d == 0`, i.e. no original 8-K whose reaction session is this session (`data.filings`).
  - `news_source: auto` (default): Benzinga where the month is ingested, else the 8-K flag.
- Unknown (NaN, or column absent) never passes: no signal.

## Why it should work
Chan's split: news-driven moves under-react (drift), no-news moves over-react (reverse). Mean-reversion entries on
no-news drops keep the over-reaction cases and skip the information cases.

## When it works and when it fails
Benzinga tags are a proxy for "public news"; coverage of small caps is thinner, so some news days read as quiet (the
filter is weakest exactly where Chan finds the effect). The 8-K fallback catches only filings, not press or analyst news.

## Parameters and sensitivity
`news_source` (3 values; each a separate trial if run). Window fixed at 24h before the close (engine choice, matches
`news_count_1d`; Chan works at a monthly horizon, so the daily window is an approximation, **unverified**).

## Evidence
- Chan, Wesley S. (2003), "Stock price reaction to news and no-news: drift and reversal after headlines", *Journal of
  Financial Economics* 70(2), 223-260. **Peer-reviewed.** Read this session: the abstract only,
  https://academicnewsletter.sufe.edu.cn/info/357702 . It finds that stocks with public news, especially
  bad news, keep drifting, while stocks with similar-sized moves but no identifiable news partly reverse, and that the
  effects sit mostly in smaller, less liquid stocks. Monthly returns, headline database. **Effect
  sizes, sample period and costs: not checked** (full text not opened). Grade B for the direction, none for the size.
- Base strategy on this engine (docs/leaderboard.md, internal replay, net of per-stock spread costs; not evidence for
  the filter): 2024-26: 46,100 signals, net -0.023 R at 10d, t 0.07; 2017-24: 171,606 signals, net +0.010 R at 20d, t 0.86. No survivor.
- Planning edge: at most half of any published effect (docs/gates.md gate 2). No published daily-horizon number was read,
  so the planning edge is "unknown, assume zero until the replay".

## Common mistakes
Using `updated_at` instead of `created_at` (leaks later edits); counting news published after the close; treating an
un-ingested month as "no news".

## Implementation spec for swing-engine
`strategies/news_filters.py` (`_NoNewsFilter` mixin). Data: `swing ingest-news` and `swing ingest-edgar` (or
`--8k-only`); columns joined by `data.fundamentals.join_edgar`. Settings: `connors_tps_scale_in_no_news: {enabled: false, news_source: auto}`.
Tests: tests/test_strategy_event_filters.py.

## Sources
- https://academicnewsletter.sufe.edu.cn/info/357702 (Chan 2003 abstract)
- docs/strategies/connors_tps_scale_in.md, docs/leaderboard.md

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 8282 | 2 | 51% | +0.02 | -0.05 | 49% | -0.04 | -0.10 | 53% | +0.06 | -0.01 | 1.18 |
| correction | 648 | 1 | 49% | +0.01 | -0.06 | 75% | +0.28 | +0.21 | 76% | +0.58 | +0.51 | 6.34 |
| healthy_uptrend | 20294 | 19 | 53% | +0.07 | -0.00 | 51% | +0.08 | +0.01 | 48% | +0.09 | +0.02 | 1.24 |
| high_vol_selloff | 2950 | 2 | 56% | +0.05 | -0.01 | 61% | +0.18 | +0.12 | 53% | +0.15 | +0.08 | 1.38 |
| narrow_uptrend | 3498 | 2 | 44% | -0.06 | -0.13 | 39% | -0.13 | -0.20 | 45% | -0.07 | -0.14 | 0.85 |
| **all** | 35672 | 26 | 52% | +0.04 | -0.03 | 51% | +0.05 | -0.02 | 50% | +0.09 | +0.02 | 1.23 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 22545 | 14 | 59% | +0.10 | +0.04 | 61% | +0.19 | +0.12 | 58% | +0.26 | +0.20 | 1.88 |
| correction | 9228 | 8 | 58% | +0.06 | -0.00 | 55% | +0.07 | +0.01 | 51% | +0.06 | -0.00 | 1.17 |
| healthy_uptrend | 76613 | 87 | 50% | -0.00 | -0.07 | 50% | +0.01 | -0.06 | 48% | +0.04 | -0.03 | 1.10 |
| high_vol_selloff | 18106 | 28 | 49% | -0.06 | -0.12 | 47% | -0.09 | -0.16 | 45% | -0.08 | -0.15 | 0.81 |
| narrow_uptrend | 19507 | 14 | 58% | +0.08 | +0.01 | 57% | +0.10 | +0.04 | 53% | +0.13 | +0.07 | 1.39 |
| **all** | 145999 | 151 | 53% | +0.02 | -0.04 | 52% | +0.04 | -0.03 | 50% | +0.07 | +0.01 | 1.19 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
