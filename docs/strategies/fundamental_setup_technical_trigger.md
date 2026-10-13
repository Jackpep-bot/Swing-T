---
slug: fundamental_setup_technical_trigger
name: "Fundamental setup + technical trigger (TradeStation Fundamntl & Chan/MACD/RSI/Stoch/Volty)"
originators: ["TradeStation built-in demonstration strategies"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [10, 40]
timeframe: daily (fundamentals quarterly)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Fundamental setup + technical trigger

## One-line summary
Only take a technical long trigger (channel breakout, MACD cross, RSI cross, stochastic cross or volatility expansion)
in stocks whose chosen fundamental field is improving (positive momentum or acceleration).

## Origin and lineage
TradeStation EasyLanguage demo strategies "Fundamntl & Chan / MACD / RSI / Stoch / Volty" LE/LX (catalog B85). They
are platform templates, not a published trader's method. The concept parallels CANSLIM's "fundamentals first,
chart for timing" (docs/methods/07). Holding period "weeks" is the catalog's estimate.

## Exact rules (per catalog summary of TradeStation help; details partly unverified)
- **Setup** (`FundSetup` function): a selected fundamental field (e.g. EPS, revenue) must show momentum (latest value
  > prior value) or, with input 1, acceleration (latest change > prior change). Exact FundSetup arithmetic was not
  verified against the EasyLanguage source.
- **Triggers (one per strategy variant)**:
  - Chan LE: buy on break of the 6-bar highest high; LX on 6-bar lowest low.
  - MACD LE: MACD(12,26,9) difference crosses above 0.
  - RSI LE: RSI(14) crosses above 30; LX when it crosses below 70.
  - Stoch LE: %K crosses above %D while oversold (< 20); LX on cross down while > 80.
  - Volty LE: upside volatility expansion using ATR(5) x 1.5 (TradeStation places a stop order above the close; the
    exact reference price is unverified).
- Stops/targets: none beyond the LX signals; sizing not specified.

## Why it should work
Post-earnings-announcement drift and earnings momentum are documented anomalies: improving fundamentals are
under-reacted to. A technical trigger times entry. The other side is investors anchored on stale estimates.

## When it works and when it fails
Works in uptrends where earnings revisions drive leadership. Fails in macro-driven sell-offs (fundamentals ignored),
and when fundamentals are used with look-ahead (fiscal period end instead of filing date) - the main backtest trap.

## Parameters and sensitivity
Field choice (EPS diluted, revenue, operating cash flow), momentum vs acceleration, trigger choice, trigger lengths.
Five triggers x many fields x two setup modes = a large search space; with grade "none" evidence this is a
multiple-testing trap. Pre-register: EPS diluted, momentum (yoy, same quarter), Chan 6-bar trigger.

## Evidence
TradeStation publishes no performance. Academic support exists for the fundamental component in general
(post-earnings drift, Bernard and Thomas 1989; earnings momentum), not for these templates. Grade none.

## Common mistakes
Using quarter-end dates instead of filing timestamps; mixing restated values; comparing sequential quarters for
seasonal businesses (use year-over-year).

## Discretionary parts and how to make them mechanical
None in the templates; the choices are the field and trigger, fixed as parameters.

## Implementation spec for swing-engine
- Fundamentals: EDGAR XBRL companyfacts. A client already exists in `swing_engine/data/float_data.py`
  (`companyfacts(cik)`, shared SEC token bucket). Missing: a point-in-time fundamentals table keyed by the `filed`
  date (CLAUDE.md rule 3), e.g. `EarningsPerShareDiluted` 10-Q/10-K values.
- Feature `fund_mom` = value of latest filed quarter - value of same quarter one year earlier, available from the
  session after `filed`; `fund_acc` = fund_mom(latest) - fund_mom(previous filing). Setup = `fund_mom > 0`
  (or `fund_acc > 0`).
- Triggers from existing features: `macd_hist` crossing above 0 (`macd_hist[t] > 0 >= macd_hist[t-1]`);
  `rsi_14` crossing above 30; Chan: `close[t] > max(high[t-6..t-1])` (approximation of the intraday break).
  Missing: stochastic %K/%D (14,3) and ATR(5).
- Entry: next open. Stop: `min(low[t-6..t-1])` (Chan LX level) or `entry - 2*atr_14`, whichever is tighter
  but at least 1*atr_14 below entry (engine choice). Target: none; `min_reward_risk` 0; exit on LX rule via
  `should_exit`, `max_hold_days` 40.

## What the router should know
Hybrid fundamental/technical; correlates with breakout families (Chan trigger) when fundamentals are good. Only in
healthy_uptrend until replay shows otherwise.

## Signs of decay to monitor
Spread between setup-on and setup-off trigger outcomes shrinking to zero (fundamental filter adds nothing).

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/fundamntl___chan_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/fundamntl___macd_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/fundamntl___rsi_le_signal_.htm
- Bernard, V. and Thomas, J. (1989), "Post-Earnings-Announcement Drift", Journal of Accounting Research (general
  context only)

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 5612 | 19 | 51% | +0.03 | -0.07 | -0.22 | 49% | +0.06 | -0.04 | -0.23 | 47% | +0.19 | +0.09 | -0.26 | 1.39 |
| correction | 878 | 1 | 65% | +0.21 | -0.06 | -0.25 | 69% | +0.44 | +0.18 | -0.28 | 63% | +0.54 | +0.27 | -0.39 | 2.67 |
| healthy_uptrend | 22238 | 107 | 46% | -0.04 | -0.14 | -0.15 | 43% | -0.04 | -0.15 | -0.16 | 37% | -0.01 | -0.11 | -0.16 | 0.99 |
| high_vol_selloff | 3138 | 17 | 54% | +0.02 | -0.12 | -0.16 | 48% | +0.02 | -0.12 | -0.18 | 40% | -0.02 | -0.16 | -0.24 | 0.97 |
| narrow_uptrend | 1791 | 10 | 44% | -0.09 | -0.20 | -0.12 | 42% | -0.08 | -0.19 | -0.12 | 33% | -0.17 | -0.29 | -0.34 | 0.73 |
| **all** | 33657 | 154 | 48% | -0.02 | -0.12 | -0.16 | 45% | -0.01 | -0.12 | -0.17 | 39% | +0.03 | -0.08 | -0.20 | 1.06 |

Portfolio replay (net of costs, slots shared with its run): 10 trades, win 30%, avg +0.36R, PF 1.67, P&L $399 on $100k, avg hold 13.3 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 16019 | 119 | 50% | -0.03 | -0.13 | -0.17 | 49% | +0.01 | -0.09 | -0.18 | 45% | +0.10 | +0.00 | -0.18 | 1.20 |
| correction | 13264 | 114 | 50% | -0.02 | -0.13 | -0.14 | 51% | +0.07 | -0.04 | -0.16 | 45% | +0.11 | -0.01 | -0.16 | 1.22 |
| healthy_uptrend | 71617 | 726 | 50% | +0.00 | -0.11 | -0.13 | 47% | +0.01 | -0.10 | -0.14 | 41% | +0.00 | -0.11 | -0.18 | 1.01 |
| high_vol_selloff | 16363 | 131 | 52% | +0.01 | -0.11 | -0.11 | 50% | +0.02 | -0.10 | -0.12 | 47% | +0.10 | -0.02 | -0.13 | 1.21 |
| narrow_uptrend | 12870 | 59 | 52% | +0.04 | -0.07 | -0.14 | 52% | +0.09 | -0.02 | -0.14 | 45% | +0.11 | -0.00 | -0.14 | 1.22 |
| **all** | 130133 | 1149 | 50% | +0.00 | -0.11 | -0.13 | 49% | +0.03 | -0.08 | -0.14 | 43% | +0.05 | -0.06 | -0.17 | 1.09 |

Portfolio replay (net of costs, slots shared with its run): 72 trades, win 43%, avg +0.24R, PF 1.62, P&L $9,831 on $100k, avg hold 14.8 bars.
