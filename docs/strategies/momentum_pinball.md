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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11952 | 9273 | 33% | -0.23 | -0.44 | 27% | -0.18 | -0.38 | 21% | -0.19 | -0.39 | 0.80 |
| correction | 1730 | 1126 | 38% | +0.21 | -0.46 | 36% | +0.19 | -0.48 | 30% | +0.29 | -0.38 | 1.35 |
| healthy_uptrend | 31711 | 24791 | 35% | -0.13 | -0.34 | 28% | -0.12 | -0.32 | 21% | -0.08 | -0.28 | 0.92 |
| high_vol_selloff | 6759 | 5298 | 38% | -0.19 | -0.51 | 32% | +0.05 | -0.27 | 24% | -0.08 | -0.40 | 0.92 |
| narrow_uptrend | 4422 | 3513 | 36% | +0.01 | -0.21 | 28% | -0.09 | -0.30 | 18% | -0.24 | -0.46 | 0.74 |
| **all** | 56574 | 44001 | 35% | -0.13 | -0.37 | 28% | -0.09 | -0.34 | 22% | -0.09 | -0.33 | 0.90 |

Portfolio replay (net of costs, slots shared with its run): 6 trades, win 50%, avg -0.12R, PF 0.68, P&L $-558 on $100k, avg hold 1.5 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 35406 | 28336 | 37% | -0.07 | -0.27 | 31% | -0.06 | -0.27 | 23% | -0.05 | -0.26 | 0.94 |
| correction | 26495 | 20146 | 41% | +0.04 | -0.20 | 34% | +0.12 | -0.11 | 27% | +0.08 | -0.16 | 1.10 |
| healthy_uptrend | 101793 | 81345 | 34% | -0.14 | -0.36 | 28% | -0.14 | -0.36 | 21% | -0.16 | -0.38 | 0.81 |
| high_vol_selloff | 47397 | 38527 | 35% | -0.12 | -0.36 | 31% | -0.07 | -0.30 | 25% | -0.03 | -0.26 | 0.96 |
| narrow_uptrend | 25716 | 19965 | 37% | -0.12 | -0.34 | 31% | -0.08 | -0.29 | 25% | -0.01 | -0.22 | 0.99 |
| **all** | 236807 | 188319 | 36% | -0.10 | -0.32 | 30% | -0.07 | -0.29 | 23% | -0.07 | -0.29 | 0.92 |

Portfolio replay (net of costs, slots shared with its run): 104 trades, win 31%, avg -0.20R, PF 0.46, P&L $-5,288 on $100k, avg hold 1.3 bars.
