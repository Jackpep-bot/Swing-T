---
slug: apirine_roc_bands
name: Rate of Change with Bands strategy (Vitali Apirine)
originators: [Vitali Apirine (S&C, March 2021), thinkorswim "RateOfChangeWithBandsStrat"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 25]
timeframe: daily
direction: long (short side mirrored in the source; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Rate of Change with Bands (Apirine)

## One-line summary
In an uptrend (close above an EMA), buy when smoothed ROC climbs back above its lower RMS band; exit when it falls back below
the upper band or price loses the EMA.

## Origin and lineage
Vitali Apirine, "Rate Of Change With Bands", Technical Analysis of Stocks & Commodities, March 2021 (Traders' Tips same issue).
Implemented in thinkorswim as study RateOfChangeWithBands and strategy RateOfChangeWithBandsStrat. Same family as Bollinger-on-
momentum ideas: volatility bands drawn around a momentum oscillator instead of around price.

## Exact rules (thinkorswim strategy description)
- Trend: uptrend if close > EMA(close, ema_length); downtrend otherwise.
- ROC_t = 100 * (close_t / close_{t-roc_length} - 1); avgROC = EMA(ROC, average_length).
- Bands: thinkorswim describes them as `num_rmss` root-mean-squares of the average ROC. Assumed form (approximation, catalog
  formula_status = approximation): RMS_t = sqrt(mean(avgROC^2 over rms_length)); upper = +num_rmss * RMS, lower = -num_rmss * RMS
  (bands centred on zero, which is what RMS rather than standard deviation implies). Not verified against the article; the
  Traders' Tips page returned 403.
- Buy to open: uptrend and avgROC crosses above the lower band.
- Sell to close: avgROC crosses below the upper band while in uptrend, or close crosses below the EMA.
- Short side mirrors (ignored here).
- Default lengths: not stated on the thinkorswim pages; unverified.
- No stop, target or sizing in the source.

## Why it should work
A dip-in-trend buy: avgROC below the lower band means momentum is unusually weak relative to its own recent scale while price is
still above trend; the cross back up is the "oversold, turning" trigger. Counterparty: short-term sellers exhausting into a
trend. Same mechanism as RSI-2 / pullback setups, with an adaptive threshold.

## When it works and when it fails
Works in steady uptrends with periodic shallow dips. Fails when the EMA filter is breached repeatedly (choppy) and in regime
breaks where the "oversold" momentum keeps falling; the EMA-cross exit then fires after a gap.

## Parameters and sensitivity
roc_length (9-20), average_length (3-10), rms_length (10-30), ema_length (20-50), num_rmss (1-2). Band width is the main knob:
wider bands = fewer, deeper-dip entries. Five knobs; test the article/platform defaults once they are verified.

## Evidence
Only the author's in-sample chart examples (S&C). No broker statistics, no independent test found. Grade D.

## Common mistakes
Using standard deviation around avgROC instead of RMS around zero (changes signal timing); forgetting the EMA exit.

## Discretionary parts and how to make them mechanical
None in the rules. The open item is the exact band formula and default lengths: verify against the S&C article or the
thinkScript source before coding; until then treat as an approximation and log it in the trial log.

## Implementation spec for swing-engine
- New module `strategies/roc_bands.py`, registered `roc_bands`, disabled.
- Features: `roc_n`, `roc_avg`, `roc_rms`, `ema_trend` (EMA of close), with `_prev` copies for crosses.
- Signal on close t when close > ema_trend and roc_avg_prev <= -k*roc_rms_prev and roc_avg > -k*roc_rms. Entry next open.
- Stop (engine-chosen): min(low over the last 5 bars) - 0.1*atr_14, floor at ema_trend - 1*atr_14 if lower stop is tighter.
- Target: reference `target_r` = 3.0; exits primarily by rule.
- `should_exit`: roc_avg crosses below +k*roc_rms, or close < ema_trend.
- max_hold_days: 30. min_reward_risk param 1.0 (rule-exit system).
- Reuses `ema`, `atr_14`; missing: ROC/RMS helpers and prev-value columns.

## What the router should know
Pullback-in-uptrend family; highly correlated with pullback_trend and rsi2_meanrev entry days. Allow in healthy and narrow
uptrends only for the comparison run.

## Signs of decay to monitor
Most exits by EMA break rather than upper-band cross (trend filter too loose); average hold < 4 bars.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RateOfChangeWithBandsStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/RateOfChangeWithBands
- https://traders.com/Documentation/FEEDbk_docs/2021/03/TradersTips.html (Traders' Tips, March 2021; not readable, 403)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 777 | 3 | 60% | +0.18 | +0.05 | 52% | +0.18 | +0.05 | 50% | +0.28 | +0.15 | 1.67 |
| correction | 56 | 0 | 39% | -0.06 | -0.22 | 50% | +0.12 | -0.03 | 50% | +0.24 | +0.09 | 1.64 |
| healthy_uptrend | 3543 | 16 | 46% | -0.01 | -0.13 | 43% | -0.02 | -0.14 | 39% | -0.02 | -0.13 | 0.97 |
| high_vol_selloff | 968 | 0 | 60% | +0.08 | -0.06 | 58% | +0.13 | -0.01 | 49% | +0.17 | +0.03 | 1.38 |
| narrow_uptrend | 429 | 0 | 29% | -0.31 | -0.43 | 31% | -0.30 | -0.42 | 31% | -0.18 | -0.30 | 0.71 |
| **all** | 5773 | 19 | 49% | +0.01 | -0.12 | 46% | +0.01 | -0.11 | 42% | +0.05 | -0.08 | 1.09 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3748 | 9 | 53% | +0.07 | -0.02 | 56% | +0.18 | +0.09 | 55% | +0.33 | +0.23 | 1.82 |
| correction | 2129 | 5 | 54% | +0.05 | -0.04 | 51% | +0.09 | -0.01 | 46% | +0.17 | +0.08 | 1.36 |
| healthy_uptrend | 11036 | 41 | 47% | -0.01 | -0.13 | 45% | -0.01 | -0.13 | 41% | +0.02 | -0.10 | 1.04 |
| high_vol_selloff | 4427 | 14 | 45% | -0.05 | -0.16 | 50% | +0.00 | -0.10 | 47% | +0.05 | -0.06 | 1.11 |
| narrow_uptrend | 2743 | 3 | 49% | +0.00 | -0.11 | 49% | +0.04 | -0.07 | 50% | +0.14 | +0.03 | 1.33 |
| **all** | 24083 | 72 | 48% | +0.00 | -0.11 | 48% | +0.04 | -0.07 | 46% | +0.10 | -0.01 | 1.21 |

Portfolio replay (net of costs, slots shared with its run): 15 trades, win 60%, avg +0.39R, PF 6.52, P&L $4,114 on $100k, avg hold 8.0 bars.
