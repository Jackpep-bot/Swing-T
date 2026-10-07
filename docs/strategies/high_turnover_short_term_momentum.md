---
slug: high_turnover_short_term_momentum
name: Short-term momentum in high-turnover stocks (Medhat-Schmeling)
originators: [Mamdouh Medhat, Maik Schmeling (Review of Financial Studies 2022)]
category: strategy
decision: implement
holding_period_days: [15, 25]
timeframe: monthly sort (1-month return x 1-month turnover)
direction: long (academic factor is long-short); main engine use is a gate on reversal entries
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]   # judgement: high turnover in a panic is selling pressure; not tested in the sources read
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Short-term momentum in high-turnover stocks

## One-line summary
Last month's winners keep winning next month when they traded on very high share turnover; low-turnover stocks show
the classic one-month reversal. For the engine: a big 1-month move on high turnover is a continuation candidate,
not a fade.

## Origin and lineage
- Medhat & Schmeling, "Short-term Momentum", Review of Financial Studies, March 2022 (CEPR DP15857 earlier).
- Reconciles Jegadeesh (1990) short-term reversal with volume-return literature (Lee-Swaminathan 2000).
- Medhat also co-authored the Dimensional Q&A that treats reversal as a timing overlay (used in the pullback cards).

## Exact rules (as published, partially verified)
1. Universe: NYSE/AMEX/Nasdaq common non-financial stocks, July 1963-December 2018.
2. Each month, double sort on prior-month return (t-1) and prior-month share turnover (volume / shares outstanding)
   into deciles (whether conditional or independent sorts, and the breakpoints used, were not verified here).
3. Short-term momentum (STMOM): within the highest-turnover decile, long prior-month winners, short losers;
   value-weighted, rebalance monthly, hold 1 month.
4. Short-term reversal lives in the low-turnover deciles.

## Why it should work
- Authors' reading: high turnover marks months when prices absorbed real information that traders underweight;
  results are hard to reconcile with strict rationality. Low-turnover moves are liquidity-driven and revert.
- Other side: contrarian liquidity providers fading big movers, who are right in thin stocks and wrong in heavily
  traded ones.

## When it works and when it fails
- Strongest among the largest, most liquid, most covered stocks (abstract) - the opposite of most anomalies.
- Profitability and persistence comparable to conventional momentum; survives transaction costs (abstract).
- Extends to 23 developed markets (as cited by a 2022 LINC/LYNX student report; not checked against the paper).
- Failure modes not documented in the sources read; judgement: panic months where turnover is high because of
  forced selling may behave differently (unverified).

## Parameters and sensitivity
| Knob | Published | Engine proxy |
|---|---|---|
| return window | prior calendar month | `ret_21d` |
| turnover | volume / shares outstanding over the month | `turnover_21d` |
| buckets | deciles x deciles | top turnover decile / top return decile |
| hold | 1 month | 21 sessions |
Traps: daily-rolling versions of a monthly sort, and relative turnover (vs own history) vs absolute turnover are
different signals; version them separately.

## Evidence
- Abstract (City Research Online): double sort reveals significant reversal in low-turnover stocks and short-term
  momentum in high-turnover stocks; as profitable and persistent as conventional momentum; survives transaction
  costs; strongest among the largest, most liquid and most covered stocks.
- Exact decile spreads, t-stats and cost-adjusted figures were not retrieved (Alpha Architect and CEPR pages returned
  403); do not quote numbers until the paper is read.
- Post-publication: one 2022 paper; little out-of-sample evidence yet.

## Common mistakes
1. Fading every 1-month big winner with RSI-type reversal rules without checking turnover.
2. Using float instead of shares outstanding (the paper uses shares outstanding).
3. Stale share counts (use the point-in-time EDGAR value).

## Discretionary parts and how to make them mechanical
Fully mechanical once shares outstanding are point-in-time.

## Implementation spec for swing-engine
- Data: shares outstanding point-in-time from `data/float_data.py` (EDGAR dei / Massive reference; store keeps
  `as_of`). Use the latest value with `as_of <= session`.
- Features: `turnover_21d = sum(volume over 21 bars) / shares_outstanding`;
  `turnover_21d_rank`, `ret_21d_rank` = same-session percentiles within the universe (or month-end only, per paper).
- Flag `stmom_long = turnover_21d_rank >= 0.90 and ret_21d_rank >= 0.90`;
  `stmom_avoid_fade = turnover_21d_rank >= 0.90 and ret_21d_rank <= 0.10` (high-turnover loser: continuation down).
- Engine uses:
  1. Gate on `rsi2_meanrev` and other dip-buys: skip when `stmom_avoid_fade` (do not buy a high-turnover 1-month
     loser).
  2. Ranking boost for breakout/momentum candidates with `stmom_long`.
  3. Research replay: month-end long book of high-turnover winners, 21-session hold.
- Reuses `ret_21d`, `avg_vol_20d`; missing `turnover_21d` and a reliable share-count history.
max_hold_days: 21. Min reward:risk: n/a.

## What the router should know
- Most useful as a veto on mean-reversion entries in any regime where `rsi2_meanrev` runs (choppy,
  high_vol_selloff).
- Correlated with `momentum_burst` and `episodic_pivot` signals (high-volume movers).

## Signs of decay to monitor
- In the engine universe, next-21-day return of high-turnover winners minus high-turnover losers <= 0 over 12
  months.
- RSI-2 trades vetoed by the gate outperforming the ones kept.

## Sources
- https://openaccess.city.ac.uk/id/eprint/31278/
- https://alphaarchitect.com/short-term-momentum/
- https://ideas.repec.org/p/cpr/ceprdp/15857.html
- https://linclund.com/momentum-turnover
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx
- Repo: `docs/catalog/catalog.json` (E09), `swing_engine/data/float_data.py`, `swing_engine/strategies/rsi2_meanrev.py`

## Empirical (replay)
_Pending: filled in from swing replay on real data._
