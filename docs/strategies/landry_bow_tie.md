---
slug: landry_bow_tie
name: "Landry Bow Tie, Proper Order and 90%-of-50-day-closing-high trend rules"
originators: ["Dave Landry (Dave Landry on Swing Trading, 2000; 10 Best Swing Trading Patterns & Strategies, 2003; StockCharts ACP 'Trading Simplified' plug-in)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: long_short   # engine long side only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built   # family relative pullback_trend is enabled, but none of the Landry rules are coded
---

# Landry Bow Tie, Proper Order and Percent-of-Close trend rules

## One-line summary
Wait for the 10 SMA, 20 EMA and 30 EMA to converge and then fan out into "Proper Order" (10 > 20 > 30), then buy the
first pullback of at least 2 lower lows when price trades above the prior bar's high; stop under the pullback low.

## Origin and lineage
Dave Landry's trend qualifiers from his books and the StockCharts ACP "Trading Simplified" plug-in: Proper Order, Bow
Tie, Landry Light (bar low above MA), and a long-term "10% rule" (price above 90% of the 50-bar highest close). Same
lineage as Raschke-Connors Holy Grail (1995). Landry is active (davelandry.com, Oct 2026 per sweep).

## Exact rules
- Proper Order up: sma_10 > ema_20 > ema_30; down = reverse; else "yellow" (chop).
- Bow Tie: the three averages converge/cross and then spread into Proper Order, marking a new trend (10 SMA crossing
  through the 20 and 30 EMA). Go long when the 10 SMA is on top and the 30 EMA at the bottom.
- Setup: first pullback after the bow tie: >= 2 bars making lower lows.
- Trigger: buy when price trades above the prior bar's high (stop-entry; forum version: 10 cents above).
- Stop: below the pullback low (forum version: 35 cents under; dollar-based, dated, unverified).
- Money management "2-for-1": take half off when open profit = initial risk, move stop to breakeven, trail the rest
  (book rule; not verified online).
- Landry Light: uptrend while each bar's low is above the MA (default 50 SMA; reference 40 bars of trend age).
- 10% rule (long-term): long while close > 0.9 x highest close of the last 50 bars.

## Why it should work
Short-term reversal inside an established or newly starting trend; the bow tie selects the early part of a trend when
momentum is fresh. Counterparty: short-term profit-takers on the dip. The buy stop demands the dip has turned.

## When it works and when it fails
- Works: fresh trends after a base; orderly 2-5 bar pullbacks.
- Fails: bow ties inside ranges (averages cross back and forth; "yellow"), V-reversals that skip the pullback, gap
  downs through stops.

## Parameters and sensitivity
| Knob | Landry | Range |
|---|---|---|
| MAs | 10 SMA / 20 EMA / 30 EMA | fixed |
| convergence | not quantified | spread (max-min)/close <= 1% within 10 bars (engine choice) |
| bow-tie age | "first pullback" | pullback within 15 bars of Proper Order start |
| pullback | >= 2 lower lows | 2-7 bars |
| 10% rule | 0.90 x 50-bar max close | 0.85-0.92 |
Trap: tuning the convergence threshold; fix it and log.

## Evidence
- No independent test of the bow tie sequencing. Pullback family rated B- in methods/01 (EasySwing panel 1,092 trades,
  PF 1.45, +0.3R, gross, vendor). Grade D for this exact rule set.

## Common mistakes
- Counting any Proper Order day as a bow tie (needs the convergence-then-fan sequence).
- Buying the pullback on the close instead of the trigger above the prior high.
- Taking the 4th or 5th pullback (later pullbacks are weaker by Landry's own framing).

## Discretionary parts and how to make them mechanical
- Convergence: `spread = (max(sma_10, ema_20, ema_30) - min(...)) / close`; bow tie at t if `min(spread over t-10..t-1) <= 0.01`
  and Proper Order is true at t and was false at t-1.
- "First pullback": the first run of >= 2 consecutive lower lows after the bow tie, before any new bow tie or loss of
  Proper Order.

## Implementation spec for swing-engine
- Features: `sma_10` (exists), `ema_20` (exists in patterns2), `ema_30` (missing), `proper_order_up`, `ma_spread`,
  `bow_tie_up`, `bars_since_bow_tie`, `lower_lows_run` (count of consecutive lows below prior low), `pct_close_50 =
  close / max(close, 50)`.
- Setup at close t: `bars_since_bow_tie <= 15`, `proper_order_up`, `lower_lows_run[t] >= 2`, first such run.
- Entry: buy stop at `high[t] + 0.01` next session (needs stop-entry hook). Daily proxy: enter if next session
  `high > high[t]`, fill `max(open, high[t] + 0.01)`. The existing pullback_trend instead enters at the close when close >
  prior high (signal-bar confirmation); this is a difference to flag in comparisons.
- Stop: pullback low - 0.1 x atr_14 (matches pullback_trend's buffer convention).
- Exit: half at 1R then stop to breakeven, trail the rest under the prior 2-bar low (or ema_20 close), exit if Proper Order
  turns down. Needs a scale-out hook; single-exit variant: target 2R. min_reward_risk: 1.0 for the 2-for-1 variant.
- max_hold_days: 30.
- Reuses: `sma_10`, `ema_20`, `atr_14`, `trend_state`, pullback_trend's rolling helpers. Missing: `ema_30`, bow-tie
  state, stop-entry hook, partial exits.
- Cheaper alternative: add `proper_order_up` and the 10% rule as optional filters to pullback_trend params.

## What the router should know
Pullback family: same allocation as pullback_trend (1.0 healthy, 0.5 narrow). High overlap with pullback_trend and
pullback_holy_grail; dedupe by symbol/day.

## Signs of decay to monitor
Fill rate of the stop-entry, share of trades reaching 1R, ratio of bow ties that revert to "yellow" within 10 bars.

## Sources
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry
- https://capital.com/it-it/learn/technical-analysis/il-bow-tie-di-dave-landry
- https://articles.stockcharts.com/article/articles-landry-2019-11-trading-the-trend-knockout-582
- https://www.davelandry.com/
- docs/methods/01-pullback-20-50-ma-uptrend.md

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3897 | 2101 | 40% | -0.13 | -0.37 | -0.56 | 39% | -0.08 | -0.32 | -0.55 | 37% | -0.04 | -0.28 | -0.55 | 0.94 |
| correction | 445 | 223 | 61% | +0.53 | -0.26 | -1.74 | 59% | +0.58 | -0.20 | -1.86 | 59% | +0.61 | -0.17 | -1.86 | 2.38 |
| healthy_uptrend | 12352 | 7184 | 43% | -0.01 | -0.26 | -0.28 | 37% | -0.04 | -0.29 | -0.30 | 35% | -0.04 | -0.29 | -0.31 | 0.94 |
| high_vol_selloff | 1291 | 734 | 39% | -0.20 | -0.44 | -0.33 | 37% | -0.18 | -0.42 | -0.43 | 35% | -0.19 | -0.42 | -0.33 | 0.76 |
| narrow_uptrend | 1309 | 720 | 41% | -0.06 | -0.29 | -0.40 | 41% | -0.02 | -0.26 | -0.43 | 33% | -0.12 | -0.36 | -0.37 | 0.84 |
| **all** | 19294 | 10962 | 42% | -0.04 | -0.30 | -0.39 | 39% | -0.04 | -0.30 | -0.42 | 36% | -0.04 | -0.30 | -0.41 | 0.95 |

Portfolio replay (net of costs, slots shared with its run): 7 trades, win 0%, avg -0.95R, PF 0.00, P&L $-4,634 on $100k, avg hold 2.4 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 9636 | 5686 | 44% | +0.03 | -0.19 | -0.30 | 41% | +0.06 | -0.16 | -0.32 | 39% | +0.05 | -0.17 | -0.34 | 1.08 |
| correction | 8387 | 4286 | 54% | +0.23 | -0.00 | -0.40 | 50% | +0.29 | +0.05 | -0.40 | 48% | +0.29 | +0.05 | -0.39 | 1.48 |
| healthy_uptrend | 40992 | 23428 | 42% | -0.03 | -0.26 | -0.30 | 38% | -0.02 | -0.26 | -0.31 | 36% | -0.01 | -0.25 | -0.31 | 0.98 |
| high_vol_selloff | 9965 | 6139 | 43% | -0.04 | -0.27 | -0.40 | 40% | -0.02 | -0.25 | -0.39 | 36% | -0.05 | -0.27 | -0.38 | 0.93 |
| narrow_uptrend | 8302 | 4695 | 48% | +0.10 | -0.13 | -0.25 | 43% | +0.12 | -0.12 | -0.26 | 41% | +0.13 | -0.11 | -0.28 | 1.19 |
| **all** | 77282 | 44234 | 45% | +0.03 | -0.21 | -0.32 | 41% | +0.04 | -0.19 | -0.32 | 38% | +0.04 | -0.19 | -0.33 | 1.06 |

Portfolio replay (net of costs, slots shared with its run): 18 trades, win 28%, avg +0.09R, PF 1.13, P&L $474 on $100k, avg hold 4.7 bars.
