---
slug: insider_cluster
name: Insider cluster buying (Form 4) follow-through
originators: ["Lakonishok & Lee (2001)", "Cohen, Malloy & Pomorski (2012)", "SEC EDGAR Form 4 practitioners"]
category: strategy
decision: have
holding_period_days: [1, 20]   # evidence says the return prints in 1-3 sessions; code uses the 20-bar backtest default
timeframe: daily (event-driven; filing-day execution matters)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: disabled
---

# Insider cluster buying (`insider_cluster`)

## One-line summary
When three or more distinct insiders make open-market purchases (Form 4 code P) in the same stock within 30 days,
buy on the disclosure; most of the documented abnormal return arrives on the filing day and the next 1-2 sessions,
so this is a ranking feature plus a same-day alert, not a multi-week drift trade.

## Origin and lineage
- Academic: Lakonishok & Lee (RFS 2001): insider purchases, not sales, are informative, mainly in smaller firms.
  Cohen, Malloy & Pomorski (JF 2012): a long-short portfolio of "opportunistic" (non-routine) insider buys minus
  opportunistic sells earns 82 bp/month value-weighted five-factor alpha (t=2.15; 180 bp equal-weighted, t=6.07);
  opportunistic buys add about 90 bp/month over all insider trades (t=4.64); routine trades earn about zero.
- Disclosure: Form 4 due within 2 business days of the trade since Sarbanes-Oxley (Aug 2002).
- Practitioner use: Stine's *Insider Buy Superstocks* (2013) treats multiple C-level/director open-market buys as a
  bonus signal (see docs/methods/14); cluster screeners (openinsider-style) are common.
- Repo definition (docs/research-monitor.md, `monitor/constants.py`): >= 3 distinct insiders within 30 days, reject
  clusters where >= 80% of trades share the same date and price (ESPP / directed-share pseudo-clusters).

## Exact rules
As specified in the repo (no single originator rule book exists):
- **Universe**: US common stocks in the engine universe ($5+, liquid). The evidence is strongest in microcaps, which the
  universe floors mostly exclude.
- **Setup**: Form 4 open-market purchases (transaction code P, acquired) by officers/directors/10% owners; >= 3
  distinct insiders in a rolling 30-day window; reject if >= 80% identical date+price; practitioner value floor (e.g.
  >= $100k total, sweep note).
- **Quality weights** (research sweep): officers over 10% owners; opportunistic over routine (same month every
  year); dollar size; distance below the 52-week high.
- **Trigger / entry**: act on the filing day (EDGAR intraday polling); next-day entries capture little.
- **Stop/target/time**: none specified in the literature; the engine uses an ATR stop and a 2R target.
- **Sizing**: engine default 1%.

## Why it should work
- Insiders have private information about firm prospects; purchases are voluntary and costly (sales are often for
  liquidity/diversification). Counterparty: uninformed sellers before disclosure, then the market reprices at filing.
- After disclosure the price adjusts quickly: Zhao (arXiv 2602.06198, 2026): day-1 abnormal return 0.86% for purchases
  nearest the 52-week high vs 4.13% for the quintile farthest below; drift lasts 2-3 sessions; skipping day 1 leaves
  no significant alpha. Johnsen (2026) citing Ozlen & Batumoglu (SSRN, Jan 2026): 70-80% of the apparent return occurs
  between trade and filing (from the repo sweep, not re-fetched).

## When it works and when it fails
- Works: beaten-down small caps far below the 52-week high with opportunistic, senior, sizeable buys; acted on the
  same day.
- Fails: routine/ESPP buys, token purchases, large caps (smaller effect), entries 2+ days after filing, broad
  selloffs where insider buying is common and uninformative about timing.

## Parameters and sensitivity
| Knob | Default | Range | Notes |
|---|---|---|---|
| cluster size | 3 insiders | 2-4 | `INSIDER_CLUSTER_MIN` |
| window | 30 days | 30-90 | `INSIDER_CLUSTER_WINDOW_DAYS` |
| identical reject | 80% | 70-90% | removed 75% of apparent clusters in one 20-year dataset (sweep) |
| `min_score` | 1.0 | producer-defined | |
| `stop_atr_mult` | 2.0 | 1.5-3 | |
| `target_r` | 2.0 | 1-3 | |
| hold | 20 bars (backtest default) | 1-5 | evidence points to 1-3 sessions |
Traps: weighting schemes (title, dollar size, 52w distance) fitted to a few hundred events.

## Evidence
- Cohen, Malloy & Pomorski (JF 2012, 1986-2007): opportunistic long-short 82 bp/month VW alpha (t=2.15), buys +90 bp/month vs all insider trades (t=4.64); routine ~0.
- Lakonishok & Lee (RFS 2001, 1975-1995): predictability driven by purchases in smaller firms.
- Zhao (arXiv 2602.06198; v1 5 Feb 2026, v2 24 Sep 2026): 13,534 purchases, 1,192 microcaps ($30M-$500M), 2018-2024;
  day-1 AR 0.86%-4.13% by 52-week-high distance quintile; volatility explains much of the gradient (differential
  falls to 0.94 pp); random days 0.14%; 29-day drift t = 1.70 (insignificant); skip-day-1 portfolios no significant
  alpha.
- A "2024 JFE study showing 8.7% over six months" circulating on blogs could not be verified (repo sweep) and is not used.
- Decay: post-SOX two-day reporting moved most of the return to the filing day; edge for a daily-bar follower is small.

## Common mistakes
1. Buying days after the filing.
2. Counting ESPP/directed-share purchases or option exercises as buys.
3. Treating a single routine buy as a signal.
4. Using transaction date instead of filing/acceptance time (look-ahead).
5. Holding for weeks expecting drift the evidence does not show.

## Discretionary parts and how to make them mechanical
- "Opportunistic vs routine": routine = the insider bought in the same calendar month in each of the prior 3 years
  (Cohen-Malloy-Pomorski definition, as summarised); otherwise opportunistic.
- "Meaningful size": dollar floor per insider and total (salary data needs DEF 14A; use a dollar floor).
- "Seniority": title contains CEO/CFO/COO/President/Chair/Director (parse `insider_title`).
- Catalyst context: Claude enum only (never a price).

## Implementation spec for swing-engine
What `swing_engine/strategies/insider_cluster.py` does:
- Returns [] unless the panel has `insider_cluster_score` (no producer exists yet; Form 4 ingest not wired into the panel).
- Gates: `market_trend_state >= -1` and `trend_state >= -1` (both off).
- Condition: `insider_cluster_score >= 1.0`, `atr_14 > 0`.
- Entry reference = as-of close, next-open fill. Stop = `close - 2 * atr_14`. Target = `close + 2 * (close - stop)`.
  Score = cluster score.
- No `should_exit`, no `max_hold_days` (backtest default 20 bars); execution breakeven +1R / trail from +2R.
Data path: `data/edgar.py::form4_buys` returns code-P acquired rows with `filed_at` taken from the filing date (a date,
not the acceptance timestamp), plus insider, title, shares, price, value. Point-in-time rule: the signal may use only
filings with `filed_at <= as_of`; for same-day action the acceptance time is needed.
Proposed producer: per symbol and session t, `insider_cluster_score` = number of distinct insiders with code-P buys
filed in [t-29, t] (calendar days), set to NaN if >= 80% of those trades share date and price, and only on the session
when the 3rd insider's filing arrives (event day) so the strategy does not re-fire for 30 days. Optional weights:
officer = 1.5, director = 1.0, 10% owner = 0.5 (untested numbers, research params); multiply by
`1 + max(0, -dist_52w_high)`.
- Proposed `max_hold_days`: 3 (evidence); target None; `min_reward_risk: 0` for that variant.
- Min reward:risk: 1.0 local, 2.0 portfolio.
- Reuses: `atr_14`, `trend_state`, `dist_52w_high`, monitor constants.
- Missing: the score producer, acceptance timestamps, routine/opportunistic flag, intraday entry on filing day.

## What the router should know
- Settings: `enabled: false` (needs EDGAR Form 4 ingest). Router allows it in healthy (1.0) and narrow (0.5).
- Best used as a ranking feature for other strategies' candidates and as a P2 monitor alert (filing-day), not as a
  standalone daily-bar trade (methods.md 1b).

## Signs of decay to monitor
- Filing-day to next-open gap absorbing most of the move (entry next open earns ~0).
- 1-3 day average return after costs <= 0 over 50 events.
- Share of clusters rejected as pseudo-clusters rising.

## Sources
- docs/methods.md 1b and 2b (insider signal); docs/research-monitor.md; docs/methods/14-insider-buy-superstocks-stine.md
- https://papers.ssrn.com/abstract=1692517
- https://www.nber.org/digest/apr11/decoding-inside-information
- https://arxiv.org/abs/2602.06198 (fetched 2026-10-07)
- https://doi.org/10.1093/rfs/14.1.79
- https://tommijohnsen.substack.com/p/most-of-the-insider-trading-alpha
- https://www.evidenceinvestor.com/what-insider-trades-and-non-trades-tell-us-about-future-returns/
- https://www.ropesgray.com/en/newsroom/alerts/2002/08/sec-accelerates-filing-of-section-16-reports

## Empirical (replay)
_Pending: filled in from swing replay on real data._
