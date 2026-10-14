---
slug: merger_target_spread_capture_v2
name: Merger arbitrage, long leg only, RE-TEST with a cleaned target flag (subject-only tender offers, proxy plus agreement 8-K, premium and pinned price)
originators: [Mitchell & Pulvino, JF 56(6) 2001; Alpha Architect, "A quantitative strategy for enhancing merger arbitrage" (2018)]
category: strategy
decision: implement
retest_of: merger_target_spread_capture (batch 7, FAIL in 2024-26)
holding_period_days: [10, 180]
timeframe: daily bars incl. delisted; form_events (DEFM14A, SC TO-T with filer/subject CIKs); 8-K items
direction: long
universe: store stocks with mcap_pit >= $300M and med_dv_63 >= $5M on the signal day
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: false
status: draft_card (research thread batch 8, 2026-10-14). RE-TEST: counts as a second trial of the merger-arbitrage family (batch 7 + this = 2 trials); grade with the haircut over both.
---

# Merger target spread capture, re-test

## Why a re-test, and what changed
Batch 7's version failed, but its own trade list says the flag was wrong, not the idea: of 52 trades in 2024-26 only 1
ended in a completed deal and 23 hit the break stop, while real takeover targets rarely break. DEFM14A is also filed
by acquirers, and SC TO-T includes non-deal tender offers. The changes below were chosen from that diagnosis (which
the Mac wrote after reading results), so this is honestly a second look at the same family and is counted as such.
The rule is fixed here before any run.

## What is still genuinely different
Same as batch 7: the payoff is a deal spread closing, not market direction; the expected beta is low.

## Engine version (pre-register this one)
A symbol is a **target** on signal session t if one of these is true:
- (a) an SC TO-T in `form_events` whose **subject** CIK is the symbol's CIK and whose **filer** CIK is different
  (a third party bidding for it); or
- (b) a DEFM14A **filed by** the symbol's CIK, and an 8-K with Item 1.01 (material agreement) filed by the same CIK in
  the 120 sessions before it.
And both of these price checks hold (point-in-time, from bars up to t):
- **Premium**: let a = the session of the earliest qualifying filing or 8-K 1.01 above. Close(t) >= 1.10 x
  close(a - 25). (Targets jump on announcement; acquirers usually do not.)
- **Pinned**: stdev of daily returns over sessions t-9..t <= 1.0%. (A target waiting for a fixed cash price barely
  moves.)
Signal session t = the session after the qualifying filing's acceptance time; if the pinned check fails then, it is
re-checked each session for up to 20 sessions and the first pass is the signal. One signal per CIK per 365 days.

Entry next open. Exits, first to hit: (a) the symbol has no bar for 3 sessions (deal closed; exit at the last close,
recorded as such); (b) close <= 0.85 x entry (break); (c) 180 sessions. Up to 15 open, equal dollar risk on the 15%
break stop.

## Grading
Batch standard plus alpha and beta vs SPY in both windows, haircut over **2 trials** (batch 7's and this). Report the
same exit table as batch 7 (completed / still held / time limit / break / break gapped). Pass also needs the
completed-deal share above 50% of closed trades, so a win from mislabelled non-targets does not count.

## Expectation stated before the run
Fewer signals than batch 7 (perhaps 15-30 a year). Mostly +1% to +4% completions; a few -15% to -30% breaks. Net
about +2% to +5% a year on capital in use, beta 0.1-0.3. Likely FAIL on alpha vs SPY in 2024-26 because the book is
under half invested and SPY made about 16% a year; the descriptive exit table is the main thing to read.

## Evidence
- Mitchell & Pulvino 2001 (see batch 7 card): about 4% a year excess after costs, 1963-1998, market-linked only in
  crashes.
- Alpha Architect 2018 (https://alphaarchitect.com/a-quantitative-strategy-for-enhancing-merger-arbitrage/, opened):
  1996-2012, 3,836 deals; picking deals by target option implied volatility raised Sharpe from 0.33 to 0.54 with a
  2.8% maximum drawdown, and "seems to have eliminated almost all of the failed deals". The pinned-price check here is
  a stock-only stand-in for that option signal (no options data). Grade C.
