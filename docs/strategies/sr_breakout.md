---
slug: sr_breakout
name: Resistance breakout with measured-move target (Schwab Learn / Joe Mazzola)
originators: [Charles Schwab education (Joe Mazzola); classic measured-move charting]
category: strategy
decision: have
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: enabled
---

# Resistance breakout, measured move (`sr_breakout`)

## One-line summary
When price closes above a prior resistance level on expanding volume, buy; target the level plus the height of the
prior range (measured move); stop just back inside the broken level.

## Origin and lineage
- Schwab Learn, "The ins and outs of a swing trade" (Joe Mazzola), catalog B28; repo notes in
  docs/sources-schwab-massive.md. The page returned an authorization error when re-fetched on 2026-10-07; rules
  below come from the catalog record.
- Worked example (B28): range $38-$44; close above $44 -> target $50 = 44 + (44 - 38); stop $43.
- The measured-move target is classic chart-pattern practice (rectangle height projected from the breakout); the
  closest researched relative is the base-breakout family (docs/methods/04).

## Exact rules
As taught:
- **Screen**: with the larger trend (higher highs/lows).
- **Setup**: a defined range between support and resistance.
- **Trigger**: a close beyond resistance.
- **Entry order**: at/after the close, or a stop order/alert at the level.
- **Initial stop**: just back inside the broken level (example: $1 below a $44 level).
- **Target**: resistance + (resistance - support).
- **Trailing/time**: none given. Gap risk through stops noted.
- **Sizing**: risk-based (1% example in settings).

## Why it should work
- Mechanism (hypothesis): stops of shorts and new-high buy interest above a visible level; a range resolved upward on
  volume signals demand absorbing supply. Counterparty: sellers at the range top and shorts covering.
- Supporting evidence is indirect: George & Hwang (2004) nearness to highs predicts returns; Gervais-Kaniel-Mingelgrin
  (2001) high-volume return premium. Bulkowski: breakout failure rates roughly doubled from the 1990s to 2003-07.

## When it works and when it fails
- Works: broad participation (breadth thrusts), leaders, tight ranges with volume dry-up.
- Fails: narrow tapes ("breakouts fail en masse" in corrections, Zanger via doc 04); low-volume breakouts; ranges
  that are really downtrend pauses; frequent throwbacks (58-62% for cups per Bulkowski) hit a stop just under the level.

## Parameters and sensitivity
| Knob | Default | Range | Notes |
|---|---|---|---|
| `volume_mult` | 1.5 | 1.4-2.0 | vs `avg_vol_50d` (includes today's bar) |
| `stop_mode` | level | level / atr | |
| `level_stop_atr_mult` | 0.5 | 0.25-1.0 | stop = level - k*ATR |
| `atr_stop_mult` | 2.0 | 1.5-3.0 | atr mode |
| `min_trend_state` | 0 | 0-1 | |
| `min_market_trend_state` | 0 | 0-1 | |
| levels lookback / pivot width | 60 / 5 | | defines the "range" |
Traps: `range_width` is resistance_1 - support_1 measured at the prior close, which may be a narrow sub-range, so
the target depends heavily on pivot settings.

## Evidence
- None for the exact rule (catalog B28: illustrative examples only).
- Family evidence (base breakouts) is grade C: EasySwing cup-and-handle PF 1.57 gross; Bulkowski failure rates
  doubled after the 1990s (see `base_breakout`).

## Common mistakes
1. Buying a breakout far above the level (risk balloons).
2. Breakouts on below-average volume.
3. Ignoring market breadth (most fail in narrow tapes).
4. Stop too tight under the level; throwbacks are common.

## Discretionary parts and how to make them mechanical
- "Resistance": nearest confirmed pivot high above the prior close (`resistance_1`).
- "Range": `range_width = resistance_1 - support_1`.
- "Close beyond resistance": `close > resistance_1` and `prior_close <= resistance_1` (first close through).

## Implementation spec for swing-engine
What `swing_engine/strategies/sr_breakout.py` does:
- Gates: `market_trend_state >= 0`; `trend_state >= 0`.
- Trigger: `close > resistance_1`, `prior_close <= resistance_1`, `volume / avg_vol_50d >= 1.5`, `range_width > 0`.
- Entry reference = as-of close, next-open fill. Stop (level mode) = `resistance_1 - 0.5 * atr_14`; ATR mode =
  `close - 2 * atr_14`. Target = `resistance_1 + range_width`. Score = volume ratio + reward:risk.
- No `should_exit`, no `max_hold_days` (backtester default 20 bars); execution breakeven +1R, trail from +2R.
- Min reward:risk: local 1.0; portfolio 2.0 floor. Because entry is above the level, R:R falls as the breakout
  bar gets larger, so the floor removes strong breakout days.
Differences from the source: volume filter added; stop has a 0.5 ATR buffer; sideways trend allowed; no explicit
"with the larger trend" check beyond `trend_state >= 0`.
Missing: buy-zone cap (skip if > 5% above level), close-near-high filter, breadth gate (methods.md 7a #1), prior-bar
`avg_vol_50d_prev` (exists in patterns2, not used here).

## What the router should know
- Settings: allowed only in `healthy_uptrend` (1.0). Breakout family; methods.md 7a #1 wants it gated on the Stockbee
  10-day ratio >= 2 or the 200-day breadth line.
- Overlaps `breakout_52w` and `base_breakout` when the resistance is a 52-week high.

## Signs of decay to monitor
- Fraction of breakouts closing back below the level within 3 bars.
- Target-hit rate < stop-hit rate over 50 trades.
- Signals concentrated in low-RS names.

## Sources
- https://www.schwab.com/learn/story/ins-and-outs-swing-trade (authorization error when fetched 2026-10-07)
- docs/sources-schwab-massive.md; docs/catalog/catalog.json (B28); docs/methods/04-chart-pattern-base-breakouts.md
- https://thepatternsite.com/FailureRates.html

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 877 | 42 | 40% | +0.04 | -0.21 | 38% | +0.04 | -0.21 | 34% | -0.29 | -0.54 | 0.71 |
| correction | 78 | 8 | 57% | +0.45 | -0.06 | 56% | +0.41 | -0.10 | 56% | +0.66 | +0.15 | 2.39 |
| healthy_uptrend | 3163 | 204 | 41% | +0.01 | -0.23 | 36% | -0.01 | -0.24 | 34% | +0.00 | -0.24 | 1.00 |
| high_vol_selloff | 310 | 21 | 35% | -0.05 | -0.30 | 30% | -0.08 | -0.33 | 28% | -0.09 | -0.33 | 0.87 |
| narrow_uptrend | 309 | 24 | 32% | -0.24 | -0.50 | 26% | -0.30 | -0.56 | 26% | -0.26 | -0.52 | 0.67 |
| **all** | 4737 | 299 | 40% | -0.00 | -0.25 | 36% | -0.01 | -0.26 | 34% | -0.06 | -0.31 | 0.92 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 0%, avg -0.64R, PF 0.00, P&L $-43 on $100k, avg hold 4.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2728 | 129 | 38% | -0.06 | -0.28 | 36% | -0.03 | -0.25 | 34% | -0.01 | -0.23 | 0.98 |
| correction | 1464 | 69 | 40% | +0.01 | -0.23 | 39% | +0.04 | -0.20 | 35% | +0.04 | -0.20 | 1.07 |
| healthy_uptrend | 11889 | 537 | 40% | -0.00 | -0.25 | 36% | -0.01 | -0.26 | 33% | -0.01 | -0.26 | 0.99 |
| high_vol_selloff | 1582 | 96 | 39% | -0.00 | -0.25 | 36% | +0.00 | -0.25 | 34% | +0.02 | -0.23 | 1.04 |
| narrow_uptrend | 1832 | 69 | 42% | +0.06 | -0.19 | 38% | +0.09 | -0.16 | 36% | +0.09 | -0.16 | 1.13 |
| **all** | 19495 | 900 | 40% | -0.00 | -0.25 | 36% | -0.00 | -0.25 | 34% | +0.01 | -0.24 | 1.01 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 0%, avg -1.02R, PF 0.00, P&L $-744 on $100k, avg hold 1.0 bars.
