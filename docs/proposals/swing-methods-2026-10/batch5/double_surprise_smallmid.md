---
slug: double_surprise_smallmid
name: Double surprise, earnings AND revenue both in the top fifth, small/mid caps (Jegadeesh-Livnat)
originators: [Jegadeesh & Livnat, "Revenue surprises and stock returns", Journal of Accounting and Economics 41 (2006)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars + EDGAR filings (point-in-time `sue`, `rev_surprise`)
direction: long
universe: SMALLMID, close >= $5, financials and utilities excluded where identifiable (no gross profit concept)
regimes_good: [healthy_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; variant of catalog pead_sue and revenue_surprise)
---

# Double surprise, small/mid

## Why this one is different from what was tested
`pead_sue` and `revenue_surprise` were replayed separately, each on the 1,500 most liquid names, and both lost to
SPY (batch 4 README). The running small-cap map retests each alone on the next 2,500. This card is the JOINT
condition (both top quintile) that the paper found strongest, and the paper found the revenue part works only in
small firms (coefficient 1.04 small, -0.03 large).

## One-line summary
When a small or mid cap's filing shows both an earnings and a revenue surprise in the top fifth of recent
reporters, buy and hold three months.

## Origin and lineage
- Jegadeesh & Livnat 2006 (working paper opened: https://pages.stern.nyu.edu/~jlivnat/JAE%20submission.pdf).

## Exact rules (as published)
SUE and SURGE (revenue surprise, seasonal random walk, standardised) quintiles; price >= $5; no financials or
utilities; enter at day +2 after the announcement, hold six months.

## Engine version (pre-register this one)
- Signals: `sue` and `rev_surprise` from `fundamental_events`, usable from `avail_ts` (session after the 10-Q/10-K
  filed date). Registered deviation: entry is keyed to the filing, which is often days to weeks after the earnings
  release; the store has no press-release-day surprise. Gate: sessions since the event's `avail_ts` == 0.
- Quintile breakpoints: among all SMALLMID names whose latest event became usable in the prior 63 sessions.
- Buy: both `sue` and `rev_surprise` in the top quintile. Entry next open. Equal weight, max 40 open.
- Exit: after 63 sessions (registered deviation from six months, to stay inside the swing horizon), or at the next
  usable filing if both surprises fall out of the top two quintiles.
- Catastrophe stop entry x 0.75. No trail, no target.

## Grading
Batch standard. Report results split by filing lag (days between `expected_earnings` and `avail_ts`): if the edge is
all in short-lag filings, the next step is a press-release date source, not a re-run.

## Evidence
- 1987-2003, 165,708 firm-quarters: high/high +4.52% over six months, low/low -3.89%, spread 8.41% (earnings alone
  5.6-6.6%), significant at 1%.
- Against: PEAD is gone outside microcaps after 2006 (Martineau, CFR 2022: https://cfr.ivo-welch.org/forthcoming/papers/martineau2021rest.pdf,
  opened; Subrahmanyam 2025 via https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/,
  opened: t 2.18 with microcaps, 1.43 without). Chordia et al. 2009 (FAJ abstract, opened): costs absorb 70-100% of
  drift profits in illiquid stocks. No post-2010 test of the joint condition found. Grade C.

## Expectation stated before the run
Small positive gross in 2017-24, about zero net; 2024-26 about zero.

## Common mistakes
Breakpoints from the whole year (look-ahead); counting a 10-K/A as a new event.

## Signs of decay to monitor
Trailing 100-trade mean net return <= 0.
