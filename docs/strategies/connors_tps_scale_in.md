---
slug: connors_tps_scale_in
name: Connors TPS (Time, Price, Scale-in 10/20/30/40)
originators: [Larry Connors, Connors Research (High Probability ETF Trading, 2009)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 10]
timeframe: daily
direction: long (short mirror exists; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Connors TPS (scale-in)

## One-line summary
For an ETF above its 200-day SMA, after RSI(2) has closed below 25 for two days, buy 10% of the planned position. Add 20%, 30%
and 40% on each later close below the previous entry price, and exit everything when RSI(2) closes above 70.

## Origin and lineage
*High Probability ETF Trading* (2009). The name stands for Time, Price, Scale-in: time in the trade and scaling in replace
the stop. Wealth-Lab's forum coding (Rev. B, after community correction) confirms that add-ons need only a lower close
than the previous entry, not a repeated RSI condition.

## Exact rules
- **Filter:** close > SMA(200). Connors normally uses the SMA; one restatement says EMA (**unverified**).
- **Initial entry:** RSI(2) < 25 on two consecutive closes. Buy 10% of the full position at the close.
- **Scale-ins:** each later close below the previous entry price adds 20%, then 30%, then 40% (total 100%). The source does not
  state whether scaling stops if the 200-day is lost. The catalog says it does; treat that as **unverified**.
- **Exit:** whole position at the close when RSI(2) > 70.
- **Stop:** none. Wealth-Lab coded entries at next-bar market because close orders cannot raise alerts in Wealth-Lab.

## Why it should work
The same reversal mechanism as RSI(2). Scaling in buys more at better prices, so the average cost falls fast: the final 40% is
bought at the deepest point, and a small bounce clears the whole position. That raises the win rate further.

## When it works and when it fails
It works when pullbacks in uptrending ETFs are short. It fails badly in trend breaks: averaging down puts 100% of the
position into the worst trade, so the loss distribution is strongly negatively skewed. The tail risk is concentrated in the full-size
positions.

## Parameters and sensitivity
RSI(2) entry 25 and 2 days, tranche schedule 10/20/30/40, exit 70. The tranche schedule determines the skew. A capped
schedule (for example 25/25/25/25 with a hard 10% catastrophic stop) is a different strategy and should be logged separately.

## Evidence
Originator claims only. No independent test was found, and the Wealth-Lab thread published no metrics. The book's figures were not read
this run. Expect the family profile from methods/11: a high win rate, with average loss 1.7-2x the average win, out of sample for plain RSI(2).

## Common mistakes
Counting the 10% first tranche as the risk unit (true exposure is the full 100%). No total size cap. Running it on
single stocks (earnings gaps) instead of diversified ETFs.

## Discretionary parts and how to make them mechanical
None. The open question is engine-level: whether a catastrophic stop exists. Here it is required (CLAUDE.md rule 5 safety).

## Implementation spec for swing-engine
- Features: `rsi_2` and `sma_200` exist. Add `rsi2_below_25_2d = rsi_2 < 25 and rsi_2[t-1] < 25`.
- **Needs a scale-in hook** (missing). `Signal` is one entry. The backtester (`OpenPosition`) holds a single fill. It needs
  `PositionPlan` with tranche weights and add conditions evaluated on each close, and risk sizing against the *full* planned
  position (`risk.sizing` must see 100% notional at the first tranche).
- Entry: MOC needed (close-fill mode missing); interim next open for each tranche.
- Exit: `rsi_2 > 70` for all tranches. Catastrophic stop: full-position average cost - 10%, or `-3*atr_14` from the first entry.
  `max_hold_days` 10. `min_reward_risk` 0. Cap: planned full position <= `max_position_pct`.
- Universe: index and sector ETFs.

## What the router should know
Treat it as the same bucket as `rsi2_meanrev`, at the full planned size. Block new first tranches when the market regime is
`correction` or `high_vol_selloff`, because averaging down there is the failure mode.

## Signs of decay to monitor
Share of trades reaching tranche 4 (the full position) rising above about 15%. Largest loss above 5x the median win.

## Sources
- https://wl6.wealth-lab.com/Forum/Posts/Connors-TPS-Strategy-40197
- https://tradingstrategyguides.com/tps-trading-strategy/ (not re-read this run)
- docs/methods/11-rsi2-connors-mean-reversion.md

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10821 | 2 | 51% | +0.02 | -0.04 | 49% | -0.03 | -0.09 | 52% | +0.06 | -0.00 | 1.17 |
| correction | 834 | 1 | 50% | +0.01 | -0.06 | 75% | +0.29 | +0.21 | 76% | +0.56 | +0.49 | 5.84 |
| healthy_uptrend | 26991 | 28 | 53% | +0.06 | -0.01 | 51% | +0.07 | +0.00 | 48% | +0.08 | +0.01 | 1.20 |
| high_vol_selloff | 3873 | 3 | 57% | +0.05 | -0.01 | 62% | +0.18 | +0.11 | 52% | +0.14 | +0.07 | 1.35 |
| narrow_uptrend | 4622 | 5 | 44% | -0.05 | -0.12 | 40% | -0.12 | -0.18 | 45% | -0.06 | -0.13 | 0.87 |
| **all** | 47141 | 39 | 52% | +0.04 | -0.03 | 51% | +0.04 | -0.02 | 49% | +0.08 | +0.01 | 1.21 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 26841 | 21 | 59% | +0.10 | +0.04 | 60% | +0.19 | +0.12 | 58% | +0.26 | +0.20 | 1.89 |
| correction | 11057 | 12 | 58% | +0.06 | -0.00 | 55% | +0.08 | +0.01 | 51% | +0.07 | +0.00 | 1.19 |
| healthy_uptrend | 90570 | 128 | 50% | -0.00 | -0.07 | 50% | +0.01 | -0.06 | 48% | +0.04 | -0.03 | 1.10 |
| high_vol_selloff | 21520 | 42 | 49% | -0.06 | -0.12 | 47% | -0.09 | -0.15 | 45% | -0.08 | -0.14 | 0.82 |
| narrow_uptrend | 23436 | 23 | 58% | +0.08 | +0.02 | 57% | +0.10 | +0.04 | 53% | +0.14 | +0.07 | 1.41 |
| **all** | 173424 | 226 | 53% | +0.02 | -0.04 | 52% | +0.04 | -0.03 | 50% | +0.07 | +0.01 | 1.20 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
