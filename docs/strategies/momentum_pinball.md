---
slug: momentum_pinball
name: Momentum Pinball (LBR/RSI first-hour breakout)
originators: [Linda Bradford Raschke, Laurence Connors]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [0, 2]
timeframe: daily signal, 60-minute entry
direction: long   # short mirror on LBR/RSI > 70; engine is long-only
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: false   # true entry needs first-hour intraday high/low
status: not_built
---

# Momentum Pinball

## One-line summary
A 3-period RSI of daily price change flags an oversold day; next day, buy a break above the first trading hour's high
and be out within two sessions.

## Origin and lineage
*Street Smarts* (1995). The "LBR/RSI" is Raschke's oscillator: RSI(3) applied to the 1-day rate of change rather than to
price. The authors pitched it for 1-2 day flips; no independent test exists.

## Exact rules (long)
- Indicator: ROC1_t = close_t - close_{t-1}; LBR/RSI = RSI(3) of ROC1.
- Signal: LBR/RSI closes below 30 -> look to buy tomorrow (above 70 -> short).
- Entry: next day, the first trading hour sets a range; buy stop above the first-hour high.
- Stop: the first-hour low.
- Exit: if losing at the close, exit; if profitable or flat, carry overnight and exit next day. Never hold a second night.
- Re-entry allowed if stopped and the range breaks again. Prefer instruments with a good average daily range.

## Why it should work
Short-term exhaustion of daily momentum: after an extreme run of down closes the first-hour range break shows buyers
taking over, and the strict 1-night limit keeps exposure to the bounce only.

## When it works and when it fails
Needs range and liquidity. Fails in trending sell-offs where oversold stays oversold, and on news days with gap-and-go.

## Parameters and sensitivity
RSI length 3, thresholds 30/70, first-hour window (60 min). The ROC-of-RSI double transform makes thresholds touchy;
keep book values.

## Evidence
Authors' claim only; no independent test located (catalog C3).

## Common mistakes
Approximating the first-hour high with the prior-day high and calling it Momentum Pinball (a different method);
holding a second night.

## Discretionary parts and how to make them mechanical
Already mechanical. "Good average daily range" -> `atr_pct_14 >= 0.02`.

## Implementation spec for swing-engine
- Reuses: `close`, `prev_close`, `atr_pct_14`; `features/indicators.py rsi()` applied to `close.diff()`.
- New feature: `lbr_rsi = rsi(close.diff(), 3)` (note: `rsi()` diffs its input, so pass ROC1 as the series).
- Signal at close t: `lbr_rsi < 30`.
- True entry needs 60-minute bars for day t+1: buy stop at first-hour high, stop first-hour low, exit at close t+1 if
  losing else at close t+2 (`max_hold_days: 2`).
- Daily approximation (must be labelled `approx_daily`): buy stop at `high_t`; fill on t+1 if `high_{t+1} >= high_t`
  at `max(open_{t+1}, high_t)`; stop `low_t`. This changes the method.
- `min_reward_risk: 0.0`. Missing: intraday bar store for first-hour range; stop-entry hook.
- Natural home is the monitor path (live first-hour range) rather than the nightly daily scan.

## What the router should know
Two-day trade; comparable to `rsi2_meanrev` (also close-based oversold). Do not run both on the same symbol/day.

## Signs of decay to monitor
Win rate on 2-day holds < 50% with payoff < 1.2; first-hour breaks that reverse the same day > 50%.

## Sources
- https://www.whselfinvest.de/en/trading-platform/free-trading-strategies/tradingsystem/48-momentum-pinball-trading-indicator-raschke-linda-connors-larry
- https://strategyquant.com/forum/topic/2846-linda-bradford-raschkes-momentum-pinball/

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11970 | 9209 | 35% | -0.21 | -0.41 | 29% | -0.17 | -0.37 | 24% | -0.17 | -0.37 | 0.80 |
| correction | 1730 | 1103 | 39% | +0.18 | -0.50 | 38% | +0.15 | -0.53 | 33% | +0.24 | -0.44 | 1.31 |
| healthy_uptrend | 31818 | 24642 | 36% | -0.12 | -0.32 | 29% | -0.11 | -0.31 | 23% | -0.06 | -0.27 | 0.92 |
| high_vol_selloff | 6760 | 5200 | 39% | -0.17 | -0.49 | 34% | +0.04 | -0.28 | 25% | -0.08 | -0.39 | 0.91 |
| narrow_uptrend | 4438 | 3482 | 39% | +0.02 | -0.20 | 31% | -0.06 | -0.27 | 21% | -0.20 | -0.42 | 0.76 |
| **all** | 56716 | 43636 | 36% | -0.12 | -0.36 | 30% | -0.09 | -0.33 | 24% | -0.08 | -0.32 | 0.90 |

Portfolio replay (net of costs, slots shared with its run): 43 trades, win 33%, avg -0.19R, PF 0.46, P&L $-2,323 on $100k, avg hold 1.4 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 35474 | 27713 | 39% | -0.06 | -0.26 | 34% | -0.06 | -0.26 | 27% | -0.07 | -0.27 | 0.91 |
| correction | 26533 | 19733 | 43% | +0.03 | -0.20 | 36% | +0.11 | -0.13 | 29% | +0.07 | -0.17 | 1.09 |
| healthy_uptrend | 100775 | 78746 | 36% | -0.13 | -0.34 | 30% | -0.13 | -0.34 | 24% | -0.14 | -0.36 | 0.81 |
| high_vol_selloff | 47404 | 37437 | 37% | -0.10 | -0.33 | 34% | -0.06 | -0.28 | 30% | -0.04 | -0.26 | 0.95 |
| narrow_uptrend | 27150 | 20833 | 38% | -0.12 | -0.33 | 33% | -0.09 | -0.30 | 27% | -0.04 | -0.25 | 0.95 |
| **all** | 237336 | 184462 | 38% | -0.09 | -0.31 | 33% | -0.07 | -0.28 | 27% | -0.07 | -0.29 | 0.90 |

Portfolio replay (net of costs, slots shared with its run): 138 trades, win 31%, avg -0.21R, PF 0.41, P&L $-16,948 on $100k, avg hold 1.4 bars.
