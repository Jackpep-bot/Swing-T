---
slug: breakout_52w
name: 52-week-high breakout on volume (Minervini / O'Neil lineage; TradeStation New High LE)
originators: [William O'Neil / IBD, Mark Minervini, TradeStation (New High LE built-in)]
category: strategy
decision: have
holding_period_days: [5, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: null        # no test of this exact rule; base-breakout detectors run ~30% (EasySwing, gross)
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: enabled
---

# 52-week-high breakout on volume (`breakout_52w`)

## One-line summary
Buy the first close above the prior 52-week high on at least 1.5x average volume, closing near the day's high; ATR
stop and a fixed-R target.

## Origin and lineage
- O'Neil/IBD: buy leaders as they clear a proper base into new highs on 40-50%+ above-average volume (docs/methods/04).
- Minervini: only Stage-2 names (Trend Template: price above rising 50 > 150 > 200-day MAs, >= 30% above the 52-week
  low, within 25% of the 52-week high, RS >= 70) breaking out of a VCP (docs/methods/03).
- TradeStation "New High LE": buy stop 1 tick above the highest high of the chosen period (day/week/month/year/
  chart); no performance published (catalog B80).
- Academic anchor: George & Hwang (JF 2004), nearness to the 52-week high predicts returns.
- The engine's version is a coarse "breakout from any base near highs" with no base geometry (doc 04 says so).

## Exact rules
As taught (composite):
- **Screen**: leader in an uptrend (Trend Template), RS rank >= 70-80, confirmed market uptrend.
- **Setup**: a base (cup, flat base, VCP) whose pivot is at or near the 52-week high.
- **Trigger**: price exceeds the pivot / prior 52-week high on volume >= 40-50% above average (IBD) or >= 1.5x
  (repo monitor rule).
- **Entry order**: buy stop 1 tick above the high (TradeStation New High LE); IBD buys up to 5% above the pivot.
- **Initial stop**: 7-8% (O'Neil) or under the last contraction low, max 10% (Minervini).
- **Targets**: 20-25% (O'Neil); Minervini sells into strength or on a 50-day violation.
- **Sizing**: 1.25-2.5% equity risk (Minervini); engine 1%.

## Why it should work
- Anchoring: investors under-react to good news when the price is near a salient high (George & Hwang); a new high on
  heavy volume shows institutional demand absorbing overhead supply. Counterparty: holders anchored to the old high
  selling to break even, and shorts.
- High-volume return premium (Gervais, Kaniel & Mingelgrin 2001) supports the volume condition at monthly horizons.

## When it works and when it fails
- Works: breadth thrusts and healthy uptrends (Jul-Oct 2025 cluster of clean breakouts per doc 05).
- Fails: narrow, mega-cap-led tapes (Oct 2026: 26.9% of stocks above the 50-day); breakouts "reportedly failing since
  March 2026" (r/swingtrading, unverified); late-stage bases; low-RS names making a new high after a long base.

## Parameters and sensitivity
| Knob | Default | Range | Notes |
|---|---|---|---|
| `volume_mult` | 1.5 | 1.4-2.0 | vs `avg_vol_50d` incl. today; the flag uses the prior-bar average |
| `stop_atr_mult` | 2.0 | 1.5-3.0 | |
| `target_r` | 2.0 | 2-4 | taught exits are 20-25% or trailing |
| `max_close_below_high` | 0.03 | 0.02-0.05 | on a breakout day this is close vs the day's high (the day's high is the new 52w high) |
| `vcp_max_contraction` | None | 0.5 | Minervini "each contraction about half" |
| `min_trend_state` | 0 | 0-1 | Trend Template implies 1 |
| `min_market_trend_state` | 0 | 0-1 | doc 04: 1 |
Traps: 52-week window (250 vs 252), volume benchmark (incl./excl. today), VCP window (20x3 bars) all shift samples.

## Evidence
- 52-week-high proximity (E06): George & Hwang 2004 strong in equal-weighted tests; Hou-Xue-Zhang value-weighted
  replication: 6-month hold 0.57%/month (t = 2.02, q-factor alpha -0.01), 1-month hold 0.14% (t = 0.43,
  insignificant). International: profits in 17 of 18 markets (prior sweep). Grade C for the anomaly as traded VW.
- Breakout family (M1a5): EasySwing cup-and-handle 3,582 trades, 30% wins, +0.5R, PF 1.57 gross; EasySwing VCP
  breakout PF 0.38 (internally inconsistent figures) and a fresh Trend Template pass PF 0.99 (methods.md 1a #7).
- Bulkowski: failure to gain 10% rose from 14% (1990s) to 28% (2003-07) of up-breakouts.
- TradeStation New High LE: documentation only, no statistics.
- No net-of-cost test of this exact rule.

## Common mistakes
1. Chasing more than ~5% past the prior high.
2. Ignoring market breadth.
3. Buying new highs in non-leaders after a long, loose base.
4. Fixed 2R target truncating the right tail where the edge sits (doc 04 reading of Bulkowski).
5. Holding through earnings without deciding to.

## Discretionary parts and how to make them mechanical
- "Leader": `rs_63d_rank >= 0.80` (feature exists, not used here) and `trend_state == 1`.
- "Proper base": `vcp_contraction <= 0.5` (crude) or `base_breakout` geometry.
- "Strong close": `dist_52w_high >= -0.03` (effectively close within 3% of the day's high on the breakout day).

## Implementation spec for swing-engine
What `swing_engine/strategies/breakout_52w.py` does:
- Gates: `market_trend_state >= 0`; `trend_state >= 0`; feature flag `breakout_52w == 1`
  (close > prior bar's `high_52w` and volume >= 1.5 x prior `avg_vol_50d`, features/patterns.py).
- Also requires `volume / avg_vol_50d >= 1.5` (today-inclusive average), `dist_52w_high >= -0.03`, optional
  `vcp_contraction <= vcp_max_contraction`.
- Entry reference = as-of close, next-open fill. Stop = `close - 2 * atr_14`. Target = `close + 2 * (close - stop)`
  (4 ATR). Score = volume ratio + (1 - vcp_contraction).
- No `should_exit`, no `max_hold_days` (backtest default 20 bars); execution breakeven at +1R, trail from +2R.
- Min reward:risk fixed at 2.0 by construction.
Differences from the originators: no base geometry, no RS, no Trend Template, no buy-zone cap from the pivot, ATR
stop instead of 7-8% / contraction low, 2R target instead of 20-25% or trailing, close-based trigger instead of a
buy stop at prior high + tick (TradeStation).
Missing: breadth gate, `sma_150`, RS gate, earnings blackout, breakout-day intraday volume pace (`features/rvol.py`).

## What the router should know
- Settings: allowed only in `healthy_uptrend` (1.0). Breakout family; methods.md 7a #1 asks for `dcr_10d >= 2` or the
  200-day breadth line on.
- Fires on the same days as `sr_breakout` and `base_breakout`; cap combined breakout exposure.

## Signs of decay to monitor
- Share of signals closing back below the prior 52w high within 5 bars.
- Win rate < 30% with the 2R target over 50 trades.
- New-high count collapsing while index makes highs (bifurcation; doc 06 signal 3).

## Sources
- docs/methods/03-vcp-minervini-trend-template.md; docs/methods/04-chart-pattern-base-breakouts.md; docs/methods.md 1a #2, #5, #7
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/new_high_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/pivot_reversal_le_signal_.htm
- https://cxoadvisory.com/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks
- https://easyswing.trading/performance
- https://thepatternsite.com/FailureRates.html
- George & Hwang (2004), "The 52-Week High and Momentum Investing", Journal of Finance 59(5)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 572 | 5 | 54% | +0.10 | +0.01 | 52% | +0.13 | +0.04 | 50% | +0.22 | +0.13 | 1.47 |
| correction | 57 | 1 | 62% | +0.18 | +0.05 | 62% | +0.24 | +0.11 | 48% | +0.14 | +0.00 | 1.32 |
| healthy_uptrend | 3192 | 70 | 48% | +0.04 | -0.05 | 46% | +0.08 | -0.01 | 43% | +0.07 | -0.02 | 1.12 |
| high_vol_selloff | 202 | 2 | 46% | -0.11 | -0.24 | 38% | -0.21 | -0.33 | 28% | -0.35 | -0.47 | 0.47 |
| narrow_uptrend | 160 | 1 | 46% | -0.11 | -0.20 | 38% | -0.22 | -0.32 | 31% | -0.21 | -0.31 | 0.68 |
| **all** | 4183 | 79 | 49% | +0.04 | -0.06 | 47% | +0.07 | -0.03 | 42% | +0.06 | -0.03 | 1.11 |

Portfolio replay (net of costs, slots shared with its run): 4 trades, win 75%, avg -0.33R, PF 0.11, P&L $-283 on $100k, avg hold 28.8 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1483 | 17 | 50% | -0.02 | -0.12 | 51% | +0.06 | -0.03 | 50% | +0.13 | +0.03 | 1.27 |
| correction | 495 | 8 | 53% | +0.01 | -0.09 | 49% | -0.00 | -0.11 | 47% | +0.05 | -0.06 | 1.11 |
| healthy_uptrend | 11062 | 155 | 48% | -0.00 | -0.10 | 45% | -0.02 | -0.12 | 41% | -0.01 | -0.11 | 0.98 |
| high_vol_selloff | 1002 | 14 | 50% | +0.04 | -0.06 | 46% | +0.01 | -0.09 | 44% | +0.05 | -0.05 | 1.10 |
| narrow_uptrend | 1329 | 13 | 50% | +0.02 | -0.08 | 49% | +0.05 | -0.05 | 46% | +0.08 | -0.02 | 1.17 |
| **all** | 15371 | 207 | 49% | +0.00 | -0.10 | 46% | -0.00 | -0.10 | 43% | +0.01 | -0.08 | 1.03 |

Portfolio replay (net of costs, slots shared with its run): 19 trades, win 74%, avg +0.50R, PF 3.27, P&L $1,558 on $100k, avg hold 58.8 bars.
