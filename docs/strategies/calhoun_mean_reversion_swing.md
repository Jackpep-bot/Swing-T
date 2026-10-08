---
slug: calhoun_mean_reversion_swing
name: "MeanReversionSwingLE (Ken Calhoun): uptrend, 50% retracement, then rise"
originators: ["Ken Calhoun (S&C, Dec 2016)", "thinkorswim built-in MeanReversionSwingLE"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Calhoun mean-reversion swing

## One-line summary
Despite the name, a pullback-in-uptrend entry: after an up-leg of at least 20 bars and $5, price retraces about 50%
of it, then a $0.50 bounce off the pullback low triggers a long.

## Origin and lineage
Ken Calhoun, "Mean-Reversion Swing Trading", *Technical Analysis of Stocks & Commodities*, December 2016; coded by
Schwab/thinkorswim as `MeanReversionSwingLE` (catalog B3). Related to Fibonacci 50% retracement buying and the
pullback family (docs/methods/01). The original article was not read; rules follow the thinkorswim reference.

## Exact rules (thinkorswim defaults)
- **Segment 1 (uptrend)**: lasts >= 20 bars (`min length`) with high-low range >= $5 (`min range for uptrend`).
- **Segment 2 (retracement)**: retraces 50% of segment 1, within `tolerance` 1%.
- **Segment 3 (trigger)**: price rises >= $0.50 (`min up move`) off the pullback low -> simulated buy.
- Whole sequence <= 400 bars (`max length`).
- **Exit / stop / target**: none built in; thinkorswim pairs it with generic TrailingStopLX / StopLossLX.
- Sizing: not specified.
Ambiguity: whether "1% tolerance" means retracement ratio 0.49-0.51 or price within 1% of the 50% level is not stated
in the reference text; this card assumes the ratio.

## Why it should work
A 50% retracement of a strong leg is a widely watched level; trend followers and value-sensitive buyers add there,
while the sellers are profit-takers from the leg. The $0.50 bounce is a crude confirmation that selling paused.

## When it works and when it fails
Works in persistent uptrends with orderly pullbacks. Fails when the 50% retracement is the first leg of a trend
change (correction regimes), and the fixed dollar thresholds make it meaningless across price levels: $5 / $0.50 is a
huge move for a $15 stock and noise for a $500 stock.

## Parameters and sensitivity
| Knob | Default | Range | Note |
|---|---|---|---|
| min_len | 20 bars | 15-40 | |
| min_range | $5 | prefer 5*ATR(14) or 10% | dollar version is price-biased |
| retrace | 0.50 | 0.38-0.62 | |
| tolerance | 0.01 | 0.01-0.05 | very tight; few hits at 0.01 |
| min_up_move | $0.50 | prefer 0.5*ATR(14) | |
| max_len | 400 | 100-400 | 400 daily bars is >1.5 years |
Trap: the tight tolerance yields few trades; widening it until results look good is curve fitting.

## Evidence
Only the S&C article's in-sample illustration (not reviewed); thinkorswim publishes no performance. No independent test
found. Grade D.

## Common mistakes
Using dollar thresholds across a mixed-price universe; treating any 50% retracement as valid without a real up-leg;
no stop (the tos strategy has none).

## Discretionary parts and how to make them mechanical
Segment boundaries need swing-point labeling: define the leg start as the lowest low before the peak and the peak as the
highest high between leg start and pullback low (spec below).

## Implementation spec for swing-engine
- Per symbol, as-of bar t, look back `max_len` bars:
  - pullback low j = argmin(low) over bars after the peak p, with p = argmax(high) over [t-max_len, t-1], j > p.
  - leg start s = argmin(low) over [t-max_len, p).
  - Conditions: `p - s >= min_len`; `high[p] - low[s] >= min_range`;
    `r = (high[p] - low[j]) / (high[p] - low[s])` with `|r - 0.5| <= tolerance`;
    `close[t] - low[j] >= min_up_move` and that was not true on any bar in (j, t) (first trigger only).
- Entry: next open (engine default). Stop: `low[j] - 0.1*atr_14` (engine choice). Target: `high[p]` (retest of
  the leg high; engine choice). `min_reward_risk` 1.5. `max_hold_days` 20.
- ATR-normalised variant parameters: `min_range_atr` 5, `min_up_move_atr` 0.5 using `atr_14`.
- Reuses: `atr_14`, `trend_state` (optional filter >= 0). Missing: a shared swing-point labeling helper.

## What the router should know
Pullback family; overlaps `pullback_trend` / `pullback_holy_grail`. Long-only, uptrend regimes only.

## Signs of decay to monitor
Hit rate of target before stop under 35% with R:R near 1.5; signals concentrating in low-priced names (dollar bias).

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/MeanReversionSwingLE
- Calhoun, K. "Mean-Reversion Swing Trading", S&C Dec 2016 (cited by thinkorswim; not read)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 237 | 15 | 35% | +0.03 | -0.21 | 29% | -0.11 | -0.34 | 22% | -0.26 | -0.49 | 0.72 |
| correction | 44 | 1 | 26% | -0.46 | -0.83 | 42% | +0.26 | -0.10 | 42% | +1.81 | +1.45 | 3.79 |
| healthy_uptrend | 391 | 18 | 36% | -0.14 | -0.39 | 28% | -0.23 | -0.48 | 22% | -0.10 | -0.36 | 0.88 |
| high_vol_selloff | 212 | 9 | 47% | +0.48 | +0.23 | 43% | +0.69 | +0.43 | 27% | +0.16 | -0.10 | 1.19 |
| narrow_uptrend | 123 | 6 | 36% | +0.06 | -0.21 | 19% | -0.40 | -0.66 | 14% | -0.34 | -0.61 | 0.65 |
| **all** | 1007 | 49 | 38% | +0.04 | -0.22 | 31% | +0.00 | -0.25 | 23% | -0.02 | -0.27 | 0.98 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 0%, avg -0.65R, PF 0.00, P&L $-359 on $100k, avg hold 9.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 393 | 8 | 45% | +0.18 | -0.04 | 42% | +0.41 | +0.19 | 33% | +0.49 | +0.27 | 1.70 |
| correction | 187 | 5 | 46% | +0.50 | +0.27 | 40% | +0.68 | +0.45 | 34% | +0.97 | +0.74 | 2.35 |
| healthy_uptrend | 832 | 24 | 41% | +0.02 | -0.21 | 35% | +0.06 | -0.17 | 28% | +0.12 | -0.11 | 1.15 |
| high_vol_selloff | 868 | 65 | 43% | +0.03 | -0.19 | 36% | +0.04 | -0.17 | 28% | -0.09 | -0.30 | 0.90 |
| narrow_uptrend | 376 | 8 | 50% | +0.31 | +0.11 | 45% | +0.35 | +0.14 | 35% | +0.43 | +0.22 | 1.66 |
| **all** | 2656 | 110 | 44% | +0.12 | -0.10 | 38% | +0.19 | -0.03 | 30% | +0.21 | -0.01 | 1.28 |

Portfolio replay (net of costs, slots shared with its run): 5 trades, win 20%, avg -0.36R, PF 0.43, P&L $-509 on $100k, avg hold 4.8 bars.
