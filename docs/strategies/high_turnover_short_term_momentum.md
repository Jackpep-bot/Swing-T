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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 132 | 1 | 54% | +0.19 | +0.08 | +0.03 | 52% | +0.33 | +0.22 | +0.19 | 51% | +0.48 | +0.37 | +0.25 | 2.32 |
| healthy_uptrend | 387 | 4 | 53% | +0.12 | +0.02 | +0.00 | 48% | +0.31 | +0.21 | +0.17 | 42% | +0.30 | +0.21 | +0.15 | 1.62 |
| high_vol_selloff | 79 | 2 | 40% | -0.29 | -0.43 | -0.26 | 39% | -0.09 | -0.24 | -0.21 | 35% | -0.13 | -0.28 | -0.30 | 0.77 |
| narrow_uptrend | 26 | 0 | 69% | +0.54 | +0.44 | +0.16 | 65% | +0.85 | +0.75 | +0.50 | 65% | +1.85 | +1.75 | +1.41 | 8.91 |
| **all** | 624 | 7 | 52% | +0.10 | -0.01 | -0.02 | 48% | +0.28 | +0.18 | +0.14 | 44% | +0.34 | +0.24 | +0.16 | 1.75 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 338 | 1 | 53% | +0.10 | +0.01 | -0.08 | 46% | +0.09 | +0.00 | -0.10 | 36% | -0.11 | -0.20 | -0.25 | 0.79 |
| correction | 187 | 1 | 47% | +0.02 | -0.08 | -0.15 | 53% | +0.12 | +0.02 | -0.12 | 49% | +0.15 | +0.05 | -0.12 | 1.38 |
| healthy_uptrend | 850 | 2 | 43% | -0.07 | -0.16 | -0.12 | 42% | -0.07 | -0.16 | -0.15 | 37% | -0.03 | -0.13 | -0.15 | 0.94 |
| high_vol_selloff | 214 | 2 | 56% | +0.13 | +0.04 | -0.09 | 48% | +0.03 | -0.05 | -0.10 | 46% | +0.08 | -0.00 | -0.08 | 1.18 |
| narrow_uptrend | 222 | 4 | 55% | +0.09 | -0.01 | -0.09 | 53% | +0.27 | +0.17 | +0.03 | 44% | +0.19 | +0.09 | +0.04 | 1.40 |
| **all** | 1811 | 10 | 48% | +0.02 | -0.08 | -0.11 | 46% | +0.04 | -0.06 | -0.11 | 40% | +0.01 | -0.08 | -0.14 | 1.03 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 100%, avg +0.54R, PF inf, P&L $1,112 on $100k, avg hold 21.0 bars.
