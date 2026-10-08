---
slug: heikin_ashi_trend_ride
name: Heikin-Ashi trend riding (Valcu)
originators: [Japanese charting tradition, Dan Valcu ("Using the Heikin-Ashi Technique", S&C Feb 2004)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Heikin-Ashi trend riding

## One-line summary
Enter on the first strong up Heikin-Ashi candle (no lower shadow) after a down sequence; stay long while HA candles stay up;
exit on the first down HA candle or a break of an indecision candle's low.

## Origin and lineage
Heikin-Ashi ("average bar") is a Japanese smoothing of candlesticks. Dan Valcu introduced it to Western traders in Technical
Analysis of Stocks & Commodities, February 2004, adding haDiff = haClose - haOpen (and its moving average) as a trend-strength
line. StockCharts ChartSchool documents the same reading rules. The Vervoort systems (vervoort_heikin_ashi_family) build on it.

## Exact rules
- HA bars: haClose = (O+H+L+C)/4; haOpen = (haOpen_{t-1} + haClose_{t-1})/2; haHigh = max(H, haOpen, haClose);
  haLow = min(L, haOpen, haClose).
- Up candle: haClose > haOpen. Strong up candle: up and haLow == haOpen (no lower shadow).
- Indecision: small body with shadows on both sides (doji / spinning top).
- Entry (practitioner form, catalog C46): first strong up HA candle after at least N down HA candles; buy next open.
- Initial stop: below the low of the most recent HA indecision candle (practitioner); if none, below the down-sequence low.
- Ride: hold while candles are up; tighten when bodies shrink or shadows appear on both sides.
- Exit: first down HA candle (haClose < haOpen) or a confirmed close below the indecision candle's low.
- No targets or sizing taught.

## Why it should work
HA averaging removes alternating-colour noise so runs of same-colour candles map to trend persistence. It is a smoothed
momentum filter; the counterparty is the generic one for trend following (late sellers, under-reaction). HA adds lag, not edge.

## When it works and when it fails
Good in smooth, steady trends with small daily ranges. Fails in chop (colour flips every few bars) and on gap reversals: HA
values are synthetic, so the real fill and real stop can be far from what the HA chart suggests.

## Parameters and sensitivity
Minimum prior down candles N (1-3), "small body" threshold (body < 25-35% of HA range), "no shadow" tolerance (exact equality
vs. within 0.1% of price). Exact equality haLow == haOpen is fragile with float math; use a tolerance.

## Evidence
No independent or academic test found (catalog: "None independent"). Valcu's article is illustrative. Grade D.

## Common mistakes
Filling or placing stops at HA prices; reading HA as real price levels; no initial stop (the "ride" rule alone can give back a
large gap).

## Discretionary parts and how to make them mechanical
- Indecision candle: body |haClose - haOpen| <= 0.3 * (haHigh - haLow) and both shadows >= 0.25 * (haHigh - haLow).
- No lower shadow: haOpen - haLow <= 0.001 * close.
- "Confirmed" break: a daily close below the stop level (not intrabar).

## Implementation spec for swing-engine
- Module `strategies/heikin_ashi_ride.py`, registered `heikin_ashi_ride`, disabled.
- Features (shared with vervoort_ha): `ha_open`, `ha_close`, `ha_high`, `ha_low`, `ha_up` (bool), `ha_strong_up`,
  `ha_down_run` (count of consecutive down candles ending at t-1), `ha_indecision_low` (low of most recent indecision candle in
  last 10 bars).
- Signal on close t: ha_strong_up_t and ha_down_run_{t-1} >= N (default 2). Optional gate trend_state >= 0 (off by default).
- Entry: next open (real price). Stop: min(real low over the down run) - 0.1*atr_14, or ha_indecision_low if higher and below entry.
- Target: reference `target_r` 3.0; primary exit `should_exit` on first down HA candle (row needs ha_close, ha_open).
- max_hold_days: 30; min_reward_risk param 1.0.
- Reuses `atr_14`, `trend_state`. Missing: HA feature columns.

## What the router should know
Trend follower; healthy_uptrend only. Exits are fast (first down candle), so payoff depends on long runs.

## Signs of decay to monitor
Average run length of up HA candles falling; median hold < 4 bars.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/heikin-ashi-candlesticks
- https://store.traders.com/v221usheteby.html (Valcu, S&C Feb 2004, not read directly)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4398 | 129 | 44% | +0.01 | -0.23 | 39% | +0.02 | -0.22 | 35% | +0.05 | -0.19 | 1.07 |
| correction | 703 | 43 | 44% | +0.22 | -0.27 | 45% | +0.35 | -0.14 | 44% | +0.48 | -0.01 | 2.07 |
| healthy_uptrend | 13841 | 441 | 42% | -0.03 | -0.26 | 36% | -0.08 | -0.31 | 31% | -0.08 | -0.31 | 0.88 |
| high_vol_selloff | 2391 | 115 | 59% | +0.33 | +0.02 | 55% | +0.40 | +0.09 | 44% | +0.36 | +0.05 | 1.60 |
| narrow_uptrend | 1979 | 81 | 30% | -0.24 | -0.48 | 26% | -0.30 | -0.54 | 21% | -0.30 | -0.56 | 0.60 |
| **all** | 23312 | 809 | 43% | +0.00 | -0.24 | 38% | -0.02 | -0.26 | 33% | -0.01 | -0.26 | 0.98 |

Portfolio replay (net of costs, slots shared with its run): 4 trades, win 50%, avg +0.23R, PF 1.67, P&L $736 on $100k, avg hold 5.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 14661 | 332 | 47% | +0.14 | -0.06 | 45% | +0.20 | -0.00 | 41% | +0.26 | +0.06 | 1.44 |
| correction | 9654 | 332 | 49% | +0.12 | -0.11 | 44% | +0.16 | -0.06 | 39% | +0.22 | -0.01 | 1.36 |
| healthy_uptrend | 39857 | 924 | 42% | -0.02 | -0.25 | 38% | -0.02 | -0.25 | 33% | -0.01 | -0.24 | 0.98 |
| high_vol_selloff | 15641 | 513 | 50% | +0.11 | -0.11 | 45% | +0.11 | -0.11 | 39% | +0.11 | -0.11 | 1.19 |
| narrow_uptrend | 10385 | 251 | 46% | +0.06 | -0.16 | 41% | +0.07 | -0.15 | 36% | +0.10 | -0.12 | 1.15 |
| **all** | 90198 | 2352 | 46% | +0.05 | -0.17 | 41% | +0.07 | -0.15 | 36% | +0.09 | -0.13 | 1.14 |

Portfolio replay (net of costs, slots shared with its run): 49 trades, win 57%, avg +0.42R, PF 2.85, P&L $10,091 on $100k, avg hold 4.6 bars.
