---
slug: ath_trend_following_wide_stop
name: All-time-high breakout with a 10-ATR trailing stop (Wilcox-Crittenden; Zarattini-Pagani-Wilcox update)
originators: [Cole Wilcox & Eric Crittenden (Blackstar Funds white paper, 2005), Zarattini, Pagani & Wilcox (SSRN 5084316, 2025)]
category: strategy
decision: implement
holding_period_days: [20, 500]
timeframe: daily bars, end-of-day signals, next-open fills
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff, choppy]
typical_win_rate: 0.44-0.49
typical_payoff_ratio: 2.56 (2005 paper, avg win / avg loss)
evidence_grade: C
free_data_ok: true
status: built_disabled (pre-registered 2026-10-09)
---

# All-time-high trend following with a wide trailing stop

## One-line summary
Buy any liquid US stock that closes at its highest close ever, exit only on a trailing stop ten ATRs below the high;
few trades, long holds, and a payoff that comes from a small share of very large winners rather than a thin
per-trade edge, so per-stock costs are a small fraction of each trade.

## Origin and lineage
- Wilcox & Crittenden, "Does Trend Following Work on Stocks?" (Blackstar Funds white paper, 2005). Practitioner /
  originator. PDF: https://www.cis.upenn.edu/~mkearns/finread/trend.pdf
- Zarattini, Pagani & Wilcox, "Does Trend-Following Still Work on Stocks?" (SSRN 5084316, v. 2025-01-17). Same
  originator lineage (Wilcox is an author), extended to 1950-2024 with a cost model. PDF:
  https://concretumgroup.com/wp-content/uploads/2026/02/Does-Trend-Following-Still-Work-on-Stocks.pdf
- Engine relatives: `breakout_52w` (52-week high, graded at 5/10/20 sessions), `turtle_breakout_systems`,
  `donchian_channel_breakout`. None of those hold a winner for months; this one does.

## Exact rules (as published, 2025 version; 2005 differences noted)
1. Universe each day: unadjusted close > $10 (2005: >= $15); 42-day average dollar volume > $1M, CPI-deflated
   (2005: $500K NYSE/AMEX, $1M NASDAQ). Portfolio version also requires Russell 3000 membership.
2. Entry: close >= highest close in the stock's entire available history (all-time high, not 52-week). Buy next open.
3. Stop: stop_t = ATH_t x (1 - 10 x ATR42_t / close_t); never lowered. Exit next open after a close below the stop.
   (2005: 10-ATR trailing stop, ATR length not stated; multiples 8-12 gave no material difference.)
4. No profit target, no time stop.
5. Sizing (portfolio): w_i = (30% / sigma_i) x 1 / max(200, N_holdings), sigma_i = 42-day annualised vol; gross
   exposure capped at 200% (engine: cap at 100%, long-only, cash account).
6. Turnover control (2025): skip rebalances below a threshold, spread entries over days, skip trades whose commission
   is large vs notional. Thresholds not disclosed.

## Why it should work
- Under-reaction / anchoring: investors sell into new highs, so the stock keeps drifting (George-Hwang lineage).
- Cost arithmetic: with ~300-day holds the round trip is paid once a year per position, not once a week. The 2005
  paper charged 0.5% round trip per trade and still showed a positive expectancy.
- The edge is in the right tail: the 2025 paper says fewer than 7% of trades produce all the profits. Tight-stop,
  20-day-horizon tests (how the engine graded `breakout_52w`) cut that tail off.

## When it works and when it fails
Works in broad, persistent uptrends; gives back in sharp reversals (2025 max drawdown about 32-33% even with
vol-sizing). Long flat stretches with many small stop-outs. Edge per trade has shrunk: 0.39R before 2005, 0.31R after
(2025 paper, Fig 9).

## Parameters and sensitivity
- Stop multiple 8-12 ATR: no material difference (2005 p.8). Register only 10.
- Price/liquidity floors and the ATR length (42) are the only other knobs. Do not sweep them.

## Evidence
- 2005 paper (practitioner/originator, survivorship-free: 24,057 securities incl. 12,673 delisted, 1983-2004):
  18,000+ trades, win rate 49.3%, avg win / avg loss 2.56, average hold 305 calendar days, 0.5% round-trip cost per
  trade. Portfolio 1991-2004, net of costs: 19.3% CAGR, 15.6% annual s.d., -20.8% max drawdown vs S&P 500 12.0%,
  14.4%, -44.7%.
- 2025 update (originator lineage, 1950-2024, ~66,000 trades): win rate 43.9%, average +0.50R, winners +1.90R,
  losers -0.70R, winners held ~370 days. Portfolio 1991-2024: gross 15.02% CAGR, Sharpe 0.85, max DD 31.75%.
  Net with $0.0035/share commission and I-Star slippage: $0.1M account 2.45% CAGR / Sharpe 0.06; $1M 9.01% / 0.49;
  $10M 12.53% / 0.70. With turnover control: $0.1M 12.97% / 0.75; $1M 13.40% / 0.75; $10M 13.38% / 0.74.
- Independent (practitioner blog reader comment, survivorship-biased large/mid caps 2000-2026, unverified):
  win 46.6%, win/loss 2.88, ~340-day holds; a random-entry test with the same stop gave Sharpe 0.50 vs 0.62 for the
  ATH entry, i.e. the exit does most of the work. https://harbourfrontquant.substack.com/p/does-trend-following-work-on-single
- Grade C: originator evidence over a long survivorship-free sample with costs, measured decay, one informal
  replication. No peer-reviewed test.

## Why it might beat costs where the others failed
1. The small-account net result is driven by commissions per share; Alpaca is commission-free, so the engine's cost
   is the spread only (its per-stock model), which is closer to the "turnover control" rows.
2. One entry and one exit per ~year per name; the engine's cost-in-R stays tiny because the stop distance is 10 ATR.
3. Payoff is a few very large winners, which the engine's current 5/10/20-day grading cannot see at all.

## Common mistakes
- Grading at 20 sessions (it will look like noise). Grade per trade to the stop exit, and as a portfolio.
- Using 52-week instead of all-time high (that is `breakout_52w`).
- Split-adjust the ATH series but apply the price floor on unadjusted closes.
- Dropping delisted names (the bad trades are the ones that delist).

## Implementation spec for swing-engine
Pre-registered in `docs/preregistration/2026-10-09-three-picks.md` (section 1): exact rules, parameters and deviations live there; any change is a new
trial. Module `strategies/ath_trend_following_wide_stop.py`: `ath_close` / `hist_bars` (features.extra; store bars
before the panel's warm-up via `data.market_series.join_pre_panel_high`, so the ATH reaches back to the store start
2016-01-04), close >= $10, >= 252 bars of history, next-open entry, stop ATH x (1 - 10 x ATR(42) / close) ratcheted
through `trail_stop` (a resting stop, not close-based), `engine_trail = False`, no target, `max_hold_days` 10,000 (no
time stop). Settings: `ath_trend_following_wide_stop: {enabled: false}`. Tests: tests/test_strategy_three_picks.py.
Graded per trade to the stop exit and as a portfolio (net of per-stock costs), not on the 5/10/20-day table.

## What the router should know
Always-on core; regime gate optional (test with and without; the published version has none).

## Signs of decay to monitor
Rolling 3-year average R per closed trade below +0.15R; share of trades held > 1 year falling.

## Sources
- https://www.cis.upenn.edu/~mkearns/finread/trend.pdf
- https://concretumgroup.com/wp-content/uploads/2026/02/Does-Trend-Following-Still-Work-on-Stocks.pdf
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5084316
- https://harbourfrontquant.substack.com/p/does-trend-following-work-on-single

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3260 | 0 | 56% | +0.01 | -0.02 | 53% | +0.00 | -0.03 | 53% | +0.04 | +0.01 | 1.31 |
| correction | 322 | 0 | 51% | -0.00 | -0.04 | 60% | +0.04 | +0.00 | 61% | +0.07 | +0.03 | 1.65 |
| healthy_uptrend | 19051 | 7 | 48% | -0.01 | -0.04 | 51% | +0.01 | -0.02 | 51% | +0.03 | +0.00 | 1.19 |
| high_vol_selloff | 863 | 2 | 50% | -0.04 | -0.07 | 48% | -0.04 | -0.07 | 49% | -0.00 | -0.04 | 0.97 |
| narrow_uptrend | 815 | 0 | 48% | -0.02 | -0.06 | 48% | -0.03 | -0.07 | 50% | +0.01 | -0.03 | 1.04 |
| **all** | 24311 | 9 | 49% | -0.01 | -0.04 | 51% | +0.01 | -0.02 | 51% | +0.03 | +0.00 | 1.20 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 9397 | 13 | 53% | +0.01 | -0.01 | 59% | +0.04 | +0.02 | 60% | +0.06 | +0.04 | 1.68 |
| correction | 3298 | 13 | 51% | -0.02 | -0.04 | 50% | -0.03 | -0.05 | 47% | -0.07 | -0.09 | 0.60 |
| healthy_uptrend | 72979 | 45 | 51% | -0.00 | -0.02 | 51% | -0.00 | -0.03 | 52% | +0.00 | -0.02 | 1.01 |
| high_vol_selloff | 5669 | 10 | 51% | -0.01 | -0.04 | 49% | -0.03 | -0.06 | 51% | -0.03 | -0.06 | 0.78 |
| narrow_uptrend | 8908 | 6 | 54% | +0.01 | -0.01 | 55% | +0.02 | -0.00 | 56% | +0.03 | +0.00 | 1.22 |
| **all** | 100251 | 87 | 52% | -0.00 | -0.02 | 52% | -0.00 | -0.02 | 53% | +0.01 | -0.02 | 1.04 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
