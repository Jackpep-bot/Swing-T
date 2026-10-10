---
slug: fomc_cycle_even_weeks
name: FOMC-cycle even weeks, long SPY only in weeks 0/2/4/6 (Cieslak-Morse-Vissing-Jorgensen)
originators: [Cieslak, Morse & Vissing-Jorgensen, "Stock Returns over the FOMC Cycle", Journal of Finance 74(5) 2019]
category: strategy
decision: implement
holding_period_days: [5, 5]
timeframe: daily bars (SPY) + published FOMC meeting calendar
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy, correction]
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: draft_card (research thread batch 2, 2026-10-10; not in catalog yet)
---

# FOMC-cycle even weeks

## Why this one is different from what failed
Every strategy replayed so far picks individual stocks, and all of them were positive in 2017-24 and flat or negative
in 2024-26, the narrow-market window. This one owns no single stocks: it times SPY on a published calendar. Its failure
mode is that the calendar effect has decayed, not that small and mid caps lagged mega caps.

## One-line summary
Since 1994, nearly all of the US equity premium has been earned in "even weeks" of the cycle that starts on each
scheduled FOMC meeting (weeks 0, 2, 4, 6). Hold SPY in those weeks and cash otherwise: about 26 round trips a year in
the most liquid ETF.

## Origin and lineage
- Cieslak, Morse & Vissing-Jorgensen, JF 74(5) 2019. Peer-reviewed. Drafts read:
  https://stern.nyu.edu/sites/default/files/assets/documents/cycle_paper_cieslak_morse_vissingjorgensen.pdf (1994-2013)
  and the 1994-2016 version https://acfr.aut.ac.nz/__data/assets/pdf_file/0012/222024/Keynote-2-vissingjorgensen.pdf
  (published Wiley version not opened).
- Different from `pre_fomc_drift_trade` (catalog: avoid; Lucca-Moench 24-hour drift, which Kurov-Wolfe-Gilbert, FRL
  2021, report "essentially disappeared after 2015"). Different from `macro_event_calendar_flag` (a flag, not a
  strategy).

## Exact rules (as published)
1. Day 0 = scheduled FOMC announcement day (second day of a two-day meeting). Trading days only.
2. Even weeks: week 0 = days -1..3; week 2 = days 9..13; week 4 = days 19..23; week 6 = days 29..33.
   Odd weeks: week -1 = days -6..-2; week 1 = 4..8; week 3 = 14..18; week 5 = 24..28.
3. Strategy B: long the stock market in even weeks, T-bills otherwise.

## Engine version (pre-register this one)
- Instrument: SPY only. Uninvested days earn zero (or the Fama-French RF if the grader supports it; registered: zero).
- Day index: for each session t, let `k_prev` = sessions since the most recent day 0 on or before t (day 0 itself is
  0) and `k_next` = sessions until the next day 0 (negative, day -1 = -1). If -6 <= `k_next` <= -1 use k = `k_next`,
  else k = `k_prev`. Even-week session if k in {-1,0,1,2,3, 9..13, 19..23, 29..33}.
- Position: hold SPY at 100% of book on every even-week session. Engine fills at the open, so a session is held from
  its open to the next session's open: signal at close of session t-1 if session t is even-week and t-1 is not; exit
  signal at close of the last even-week session; fill next open. (Deviation from close-to-close returns, registered.)
- Calendar: scheduled meetings as published at the start of each year (below). The cancelled 2020-03-17/18 meeting
  stays as scheduled (that is what was known in advance); unscheduled meetings and notation votes are ignored.
- Costs: per-stock model for SPY (floor 10 bp/side per gates.md gate 1; SPY's real spread is far smaller, so this is
  conservative).
- No stop, no target, no regime gate.

### Scheduled announcement days (day 0), from federalreserve.gov (read 2026-10-10)
- 2016: Jan 27, Mar 16, Apr 27, Jun 15, Jul 27, Sep 21, Nov 2, Dec 14
- 2017: Feb 1, Mar 15, May 3, Jun 14, Jul 26, Sep 20, Nov 1, Dec 13
- 2018: Jan 31, Mar 21, May 2, Jun 13, Aug 1, Sep 26, Nov 8, Dec 19
- 2019: Jan 30, Mar 20, May 1, Jun 19, Jul 31, Sep 18, Oct 30, Dec 11 (Oct 4 unscheduled call: ignore)
- 2020: Jan 29, Mar 18 (scheduled, later cancelled; keep), Apr 29, Jun 10, Jul 29, Sep 16, Nov 5, Dec 16
  (Mar 2 and Mar 15 unscheduled: ignore)
- 2021: Jan 27, Mar 17, Apr 28, Jun 16, Jul 28, Sep 22, Nov 3, Dec 15
- 2022: Jan 26, Mar 16, May 4, Jun 15, Jul 27, Sep 21, Nov 2, Dec 14
- 2023: Feb 1, Mar 22, May 3, Jun 14, Jul 26, Sep 20, Nov 1, Dec 13
- 2024: Jan 31, Mar 20, May 1, Jun 12, Jul 31, Sep 18, Nov 7, Dec 18
- 2025: Jan 29, Mar 19, May 7, Jun 18, Jul 30, Sep 17, Oct 29, Dec 10
- 2026: Jan 28, Mar 18, Apr 29, Jun 17, Jul 29, Sep 16, Oct 28, Dec 9
- 2027: Jan 27, Mar 17, Apr 28, Jun 9, Jul 28, Sep 15, Oct 27, Dec 8
Source pages: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm and
https://www.federalreserve.gov/monetarypolicy/fomchistorical2016.htm .. fomchistorical2020.htm. Re-check each date
against the page when coding (these were read through a page summariser).

## Grading (needs a small grader addition)
This is a timing strategy on one ETF, so R per trade and absolute Sharpe are the wrong yardsticks: a long-SPY strategy
will look good in any bull window. Grade on daily net returns:
1. Alpha: regress daily net strategy returns on daily SPY returns over each window; primary statistic = alpha t-stat,
   haircut over the batch-2 group size.
2. Also report net Sharpe vs SPY buy-and-hold Sharpe, time in market (expect about half), and the even-minus-odd
   SPY return per session.
Pass = positive haircut alpha in both windows. Expect low power: about 16 meetings in the 2-year window.

## Evidence
- First draft (1994-2013, ~160 meetings, p.6): average 5-day excess returns, even weeks 0.57% / 0.30% / 0.42% /
  0.61% (weeks 0/2/4/6); odd weeks about 0 / -0.17% / -0.17% / -0.12%. Even-week days earn about 10-14 bp/day more
  than odd-week days (Table 1, significant at 1%).
- 1994-2016 version: Strategy A (always long) 8.48% excess, Sharpe 0.45; Strategy B (even weeks only) Sharpe 0.92,
  about one-third lower volatility. The authors report the pattern continued in 2014-2016, after the first draft.
- CXO summary of the June 2016 draft (1994-2015, 176 meetings, gross): even-week-only 11.8% excess, 13.3% vol,
  Sharpe 0.88 vs buy-and-hold 8.3%, 19.1%, 0.43.
  https://www.cxoadvisory.com/calendar-effects/hold-stocks-only-during-fomc-even-weeks
- Robustness in paper: present in 1994-2000, 2001-07, 2008-13 subperiods and in MSCI emerging/developed indices;
  survives day-of-week, day-of-month, macro-release and earnings controls.
- Costs (practitioner blog, SPY 1994-Mar 2015, 5 bp per trade): 11.29% gross -> 8.55% net vs buy-and-hold 9.15%;
  Sharpe 0.82 gross, 0.62 net vs 0.47. http://www.returnandrisk.com/2015/03/fomc-cycle-trading-strategy-in.html
- No peer-reviewed post-2016 test found. One backtest site (paperswithbacktest.com, 1990-2026, rules and costs not
  confirmed) shows Sharpe 0.43: treat as a warning sign of decay, weak evidence.
- Grade B: peer-reviewed, internationally replicated in-paper, some post-draft evidence, decay after 2016 unknown.

## Why it might beat costs where the others failed
One instrument with the tightest spread in the market, 26 round trips a year, and a per-week edge (tens of bp) that
is several times SPY's real spread. It does not depend on breadth or stock selection.

## Common mistakes
Counting calendar days; using unscheduled meetings; using the minutes release date; measuring against cash instead of
SPY (beta in a bull market looks like skill).

## What the router should know
Standalone sleeve; not combined with stock strategies in this test.

## Signs of decay to monitor
Trailing 3-year even-minus-odd average SPY return per session <= 0.

## Empirical (replay)
Pre-registered batch 2 group (docs/preregistration/2026-10-10-batch2.md), n_trials = 3. **FAIL**. Full tables: docs/preregistration/2026-10-10-batch2-results.md.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fomc_cycle_even_weeks | 2024 | 47 | -0.020 | -1.12 | -0.68 | -0.68 | 0.03 | 19.3% | 5 | -60% | -14.7% |
| fomc_cycle_even_weeks | 2017 | 181 | -0.008 | -0.79 | -0.21 | -0.21 | 0.08 | 32.4% | 5 | -171% | -23.6% |

Against buy-and-hold SPY:

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| fomc_cycle_even_weeks | 2024 | -24.5% | -1.81 | -1.81 | -13.9% | -2.21 | 0.38 | 43% | -0.68 | 1.03 |
| fomc_cycle_even_weeks | 2017 | -16.4% | -1.13 | -1.13 | -8.5% | -2.34 | 0.43 | 44% | -0.21 | 0.75 |
