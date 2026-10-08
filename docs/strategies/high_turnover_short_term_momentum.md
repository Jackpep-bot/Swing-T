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
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 134 | 0 | 55% | +0.20 | +0.18 | 54% | +0.33 | +0.31 | 53% | +0.49 | +0.48 | 2.39 |
| healthy_uptrend | 384 | 4 | 53% | +0.13 | +0.11 | 47% | +0.30 | +0.29 | 41% | +0.28 | +0.27 | 1.58 |
| high_vol_selloff | 77 | 0 | 39% | -0.26 | -0.28 | 39% | -0.09 | -0.11 | 35% | -0.12 | -0.13 | 0.79 |
| narrow_uptrend | 27 | 0 | 70% | +0.57 | +0.56 | 67% | +0.88 | +0.87 | 67% | +1.87 | +1.86 | 9.31 |
| **all** | 622 | 4 | 52% | +0.11 | +0.09 | 48% | +0.28 | +0.27 | 44% | +0.34 | +0.33 | 1.74 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 394 | 0 | 52% | +0.13 | +0.11 | 47% | +0.17 | +0.15 | 38% | -0.01 | -0.03 | 0.98 |
| correction | 200 | 1 | 49% | +0.06 | +0.04 | 56% | +0.20 | +0.18 | 51% | +0.30 | +0.28 | 1.76 |
| healthy_uptrend | 893 | 3 | 44% | -0.03 | -0.05 | 43% | -0.02 | -0.04 | 38% | +0.04 | +0.02 | 1.07 |
| high_vol_selloff | 234 | 0 | 56% | +0.13 | +0.11 | 48% | +0.08 | +0.06 | 47% | +0.11 | +0.09 | 1.22 |
| narrow_uptrend | 252 | 0 | 52% | +0.04 | +0.02 | 50% | +0.22 | +0.20 | 40% | +0.10 | +0.08 | 1.18 |
| **all** | 1973 | 4 | 49% | +0.04 | +0.02 | 47% | +0.08 | +0.06 | 41% | +0.07 | +0.05 | 1.14 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
