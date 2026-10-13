---
slug: katsanos_trend_strength_filters
name: Trend-strength filter family ADXTrend / ERTrend / R2Trend / VHFTrend (Katsanos)
originators: ["Markos Katsanos (Which Trend Indicator Wins?, S&C Oct 2016)", "thinkorswim built-ins", "indicator authors: Wilder (ADX), Kaufman (ER), Adam White (VHF)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 40]     # estimate; exit on close back through the MA
timeframe: daily
direction: long_only_in_engine (original long and short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Trend-strength filter family (Katsanos)

## One-line summary
One template, four trend meters (ADX, Efficiency Ratio, R-squared + regression slope, VHF): if the meter says a trend is
developing or strong, buy a close crossing above its MA and exit on the cross back.

## Origin and lineage
Katsanos, S&C Oct 2016, compared the four indicators as trend filters; thinkorswim ships ADXTrend, ERTrend, R2Trend,
VHFTrend. Which indicator "won" in the article could not be retrieved (traders.com 403).

## Exact rules (TOS)
- Indicator X in {ADX(len), ER(len) smoothed by an `er average length`, VHF(len)}:
  - developing: X > crit_level and X > mult x min(X over `lag` bars);
  - strong: trend_level < X < max_level.
- R2Trend: R² of close vs a linear trendline over len > trend_level (default 0.42) and rising vs prior bar, and the
  regression slope > +critical (uptrend).
- Entry long: (developing or strong) and close crosses above its MA(average length). Next open.
- Exit long: close crosses below the MA. Shorts mirror.
- Defaults for length, lag, mult, crit/trend/max levels and MA length are **not published on the TOS pages** (only R² 0.42).

## Why it should work
MA-cross whipsaw happens in ranges; gating it with a trend meter should skip range trades. Who is on the other side: range
traders who fade the cross. The filter itself is the experiment: does it raise expectancy versus the unfiltered
`ma_crossover_family` price/MA variant?

## When it works and when it fails
Trending phases after a base. Fails at turning points (all four meters lag) and in high-volatility selloffs, where ADX and VHF
read "trend" on the way down.

## Parameters and sensitivity
Many knobs per meter (length, lag, mult, three levels, MA length): high overfitting risk. Engine assumptions: ADX(14) crit 20
trend 25 max 50; ER(10) crit 0.3 trend 0.5; VHF(28) crit 0.35 trend 0.4; lag 10, mult 1.1, MA SMA(20). All flagged as
engine choices, not Katsanos defaults.

## Evidence
In-sample S&C comparison only (grade D). Independent academic tests of ADX-style filters are mixed and not specific to these
rules. The catalog notes the family doubles as a regime-router experiment.

## Common mistakes
Reading ADX direction-agnostically (it rises in downtrends too); using R² without the slope sign.

## Discretionary parts and how to make them mechanical
Fully mechanical once defaults are fixed in params.

## Implementation spec for swing-engine
- Module `strategies/trend_strength.py`, `@register("strategy")`, param `meter` in {adx, er, r2, vhf}.
- Reuses adx_14, plus_di_14, minus_di_14 (require +DI > -DI for longs as a declared deviation), sma_20, atr_14.
- New features: `er_10` = |C - C[10]| / sum(|C - C[1]|, 10); `vhf_28` = (max(C,28) - min(C,28)) / sum(|C - C[1]|, 28);
  `r2_20` and `linreg_slope_20` of close (catalog also maps to `kaufman_efficiency_ratio_kama`).
- Signal at close t: meter gate true and close crosses above sma_20. Entry next open.
- Stop: entry - 2 x atr_14. Target: None. `should_exit`: close < sma_20. `max_hold_days`: 40. `min_reward_risk`: not applied.
- settings.yaml: `trend_strength: {enabled: false, shadow_only: true, meter: adx}`; replay all four meters and report all.

## What the router should know
Primarily a regime-gating experiment: the most useful output is which meter best separates winning from losing trades of
other strategies, not this strategy's own P&L.

## Signs of decay to monitor
Gate pass rate above 70% of days (meter no longer discriminates); filtered vs unfiltered expectancy gap closing.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ADXTrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/ERTrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/R2Trend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/VHFTrend

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 897 | 21 | 54% | +0.11 | -0.00 | -0.13 | 54% | +0.16 | +0.05 | -0.10 | 51% | +0.26 | +0.15 | -0.13 | 1.64 |
| correction | 67 | 1 | 47% | -0.08 | -0.21 | -0.15 | 55% | +0.01 | -0.12 | -0.46 | 42% | +0.15 | +0.01 | -0.83 | 1.29 |
| healthy_uptrend | 3494 | 48 | 49% | +0.03 | -0.09 | -0.11 | 45% | -0.00 | -0.12 | -0.15 | 39% | -0.02 | -0.14 | -0.21 | 0.97 |
| high_vol_selloff | 606 | 45 | 55% | +0.11 | -0.03 | +0.04 | 56% | +0.11 | -0.02 | +0.19 | 41% | -0.10 | -0.23 | +0.00 | 0.82 |
| narrow_uptrend | 427 | 8 | 34% | -0.12 | -0.24 | -0.16 | 34% | -0.18 | -0.31 | -0.19 | 31% | -0.17 | -0.30 | -0.26 | 0.74 |
| **all** | 5491 | 123 | 49% | +0.04 | -0.08 | -0.10 | 47% | +0.03 | -0.09 | -0.11 | 40% | +0.01 | -0.11 | -0.18 | 1.02 |

Portfolio replay (net of costs, slots shared with its run): 289 trades, win 31%, avg -0.03R, PF 0.89, P&L $-6,495 on $100k, avg hold 7.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3091 | 27 | 54% | +0.08 | -0.02 | -0.15 | 53% | +0.16 | +0.05 | -0.16 | 54% | +0.33 | +0.22 | -0.16 | 1.83 |
| correction | 1362 | 11 | 48% | -0.04 | -0.15 | -0.15 | 45% | -0.04 | -0.16 | -0.15 | 38% | -0.07 | -0.18 | -0.18 | 0.88 |
| healthy_uptrend | 12238 | 187 | 48% | +0.00 | -0.12 | -0.15 | 46% | +0.01 | -0.11 | -0.17 | 41% | +0.02 | -0.10 | -0.20 | 1.04 |
| high_vol_selloff | 2436 | 38 | 47% | -0.03 | -0.15 | -0.13 | 48% | -0.03 | -0.15 | -0.18 | 46% | +0.01 | -0.11 | -0.14 | 1.03 |
| narrow_uptrend | 2323 | 24 | 49% | -0.01 | -0.13 | -0.20 | 47% | +0.00 | -0.12 | -0.23 | 42% | +0.00 | -0.12 | -0.26 | 1.00 |
| **all** | 21450 | 287 | 49% | +0.01 | -0.11 | -0.15 | 48% | +0.02 | -0.09 | -0.17 | 43% | +0.06 | -0.06 | -0.19 | 1.11 |

Portfolio replay (net of costs, slots shared with its run): 1126 trades, win 28%, avg -0.01R, PF 0.98, P&L $6,267 on $100k, avg hold 7.5 bars.
