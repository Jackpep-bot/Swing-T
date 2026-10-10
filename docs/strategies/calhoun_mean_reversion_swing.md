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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 235 | 15 | 35% | +0.04 | -0.19 | 29% | -0.09 | -0.32 | 23% | -0.25 | -0.48 | 0.73 |
| correction | 44 | 1 | 26% | -0.46 | -0.83 | 42% | +0.26 | -0.10 | 42% | +1.81 | +1.45 | 3.79 |
| healthy_uptrend | 392 | 18 | 36% | -0.15 | -0.40 | 28% | -0.23 | -0.48 | 22% | -0.11 | -0.36 | 0.87 |
| high_vol_selloff | 212 | 9 | 47% | +0.48 | +0.23 | 43% | +0.69 | +0.43 | 27% | +0.16 | -0.10 | 1.19 |
| narrow_uptrend | 123 | 6 | 36% | +0.06 | -0.21 | 19% | -0.40 | -0.66 | 14% | -0.34 | -0.61 | 0.65 |
| **all** | 1006 | 49 | 38% | +0.04 | -0.21 | 31% | +0.00 | -0.25 | 23% | -0.02 | -0.27 | 0.98 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 421 | 8 | 46% | +0.20 | -0.02 | 42% | +0.45 | +0.24 | 33% | +0.56 | +0.35 | 1.81 |
| correction | 193 | 6 | 46% | +0.71 | +0.47 | 41% | +0.92 | +0.69 | 35% | +1.18 | +0.94 | 2.69 |
| healthy_uptrend | 929 | 24 | 39% | -0.04 | -0.27 | 33% | +0.00 | -0.23 | 27% | +0.05 | -0.18 | 1.06 |
| high_vol_selloff | 930 | 72 | 43% | +0.04 | -0.19 | 36% | +0.04 | -0.18 | 28% | -0.10 | -0.32 | 0.88 |
| narrow_uptrend | 406 | 8 | 53% | +0.43 | +0.21 | 49% | +0.47 | +0.26 | 38% | +0.53 | +0.32 | 1.84 |
| **all** | 2879 | 118 | 44% | +0.14 | -0.09 | 38% | +0.21 | -0.01 | 30% | +0.23 | +0.00 | 1.30 |

Portfolio replay (net of costs, slots shared with its run): 17 trades, win 18%, avg +0.17R, PF 1.30, P&L $1,464 on $100k, avg hold 5.5 bars.
