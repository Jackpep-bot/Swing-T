---
slug: zscore_mean_reversion_garner
name: "SimpleMeanReversion z-score (Anthony Garner)"
originators: ["Anthony Garner (S&C, May 2019)", "thinkorswim SimpleMeanReversion"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long (original also shorts; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Z-score mean reversion (Garner)

## One-line summary
Buy when price is more than 1 standard deviation below its L-bar mean while the L-bar SMA is above the 10L-bar SMA
(long-term uptrend); exit when the z-score recovers above -0.5.

## Origin and lineage
Anthony Garner, S&C May 2019 (Python backtest article per catalog; not read); coded by thinkorswim (catalog B10). A
textbook Bollinger-style mean reversion with a trend filter; cousin of Connors RSI-2 (`rsi2_meanrev`).

## Exact rules (thinkorswim)
- `z = (price - SMA(price, L)) / StDev(price, L)`.
- Fast SMA length = L x fast factor (default 1); slow SMA length = L x slow factor (default 10).
- Buy to open: z < -1.0 and fast SMA > slow SMA. Sell to close: z > -0.5.
- Short: z > +1.0 and fast SMA < slow SMA; cover z < +0.5 (not used).
- Default `length` L: **unverified** (tos text truncated); no price stop; sizing not specified.

## Why it should work
Short-horizon reversal (Jegadeesh 1990; Lehmann 1990) inside a long-term uptrend: liquidity-driven dips are bought by
trend holders. The other side is short-term momentum sellers and forced sellers.

## When it works and when it fails
Works in rising or ranging markets with no news. Fails in trend breaks: the filter (SMA L > SMA 10L) lags, so the first
weeks of a correction still produce buys; no stop means losses are open-ended.

## Parameters and sensitivity
L (10-50; 20 matches `bb_*_20`), entry z (-1 to -2.5), exit z (-0.5 to 0), slow factor (5-10). Deeper entry z = fewer
but higher-quality trades. Trap: grid-searching all four together.

## Evidence
Garner's article is an in-sample illustration; no broker statistics; no independent test of this exact rule. Grade D.
Related Connors RSI-2 rules have extensive practitioner tests; docs/methods/11 records (Alvarez, Jan 2024) that
short-term mean reversion has not decayed further since the mid-2000s but edges are smaller.

## Common mistakes
Running it without any stop; using z on very low-vol names (tiny StDev gives large z for trivial moves); ignoring
earnings gaps.

## Discretionary parts and how to make them mechanical
None in the original. Add a protective ATR stop and time stop as engine choices.

## Implementation spec for swing-engine
- With L = 20: `z = (close - sma_20) / sd_20` where `sd_20 = (bb_upper_20 - sma_20) / 2` (BB uses 2 std with
  ddof=0 per indicators.py `rolling_std`). Slow SMA = SMA(200) = existing `sma_200` (10 x 20). So the rule is
  `close < bb_mid - 1*sd` and `sma_20 > sma_200` with existing columns only.
- Entry at t: `z[t] < -1.0` (first bar crossing, `z[t-1] >= -1.0`, to avoid repeated signals), `sma_20 > sma_200`.
- Entry next open. Stop `entry - 2*atr_14` (engine choice, as `rsi2_meanrev`). Reference target = `sma_20 - 0.5*sd_20`
  (the exit level), so `reward_risk` is honest and low; `min_reward_risk` 0. `should_exit`: `z > -0.5`;
  `max_hold_days` 10.
- Reuses `sma_20`, `bb_upper_20`, `sma_200`, `atr_14`. Nothing missing for L = 20; other L need a generic rolling std.

## What the router should know
Mean-reversion family; highly correlated with `rsi2_meanrev` entries. Treat as the same bucket (shared risk cap). Allowed
where `rsi2_meanrev` is allowed.

## Signs of decay to monitor
Win rate below ~60% or average trade below costs (mean reversion is thin); stop-outs clustering in sell-offs.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SimpleMeanReversion
- docs/methods/11-rsi2-connors-mean-reversion.md (family evidence)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4973 | 247 | 66% | +0.02 | -0.03 | 68% | +0.01 | -0.04 | 70% | +0.01 | -0.03 | 1.05 |
| correction | 454 | 22 | 70% | +0.12 | +0.09 | 82% | +0.24 | +0.20 | 85% | +0.29 | +0.26 | 3.24 |
| healthy_uptrend | 12546 | 604 | 65% | +0.01 | -0.04 | 68% | +0.00 | -0.05 | 71% | -0.00 | -0.05 | 0.99 |
| high_vol_selloff | 2351 | 126 | 70% | +0.11 | +0.08 | 73% | +0.14 | +0.11 | 74% | +0.14 | +0.11 | 1.65 |
| narrow_uptrend | 2766 | 155 | 62% | +0.02 | -0.03 | 68% | +0.02 | -0.04 | 70% | +0.03 | -0.02 | 1.12 |
| **all** | 23090 | 1154 | 66% | +0.02 | -0.02 | 69% | +0.02 | -0.02 | 71% | +0.02 | -0.02 | 1.09 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 13715 | 491 | 70% | +0.07 | +0.03 | 76% | +0.11 | +0.07 | 77% | +0.12 | +0.08 | 1.55 |
| correction | 5470 | 259 | 71% | +0.08 | +0.05 | 76% | +0.10 | +0.07 | 78% | +0.12 | +0.08 | 1.59 |
| healthy_uptrend | 37723 | 1415 | 65% | -0.01 | -0.05 | 69% | -0.01 | -0.05 | 71% | -0.00 | -0.05 | 0.98 |
| high_vol_selloff | 13248 | 446 | 61% | -0.06 | -0.09 | 63% | -0.05 | -0.08 | 65% | -0.04 | -0.07 | 0.87 |
| narrow_uptrend | 12087 | 447 | 68% | +0.04 | +0.00 | 72% | +0.05 | +0.01 | 74% | +0.05 | +0.01 | 1.19 |
| **all** | 82243 | 3058 | 66% | +0.01 | -0.03 | 70% | +0.02 | -0.02 | 72% | +0.03 | -0.01 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
