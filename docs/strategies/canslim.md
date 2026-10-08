---
slug: canslim
name: CAN SLIM selection (C-A-N-S-L-I) with base-breakout entries
originators: [William J. O'Neil, Investor's Business Daily]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 60]
timeframe: daily (fundamentals quarterly)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built   # chart side partly covered by base_breakout (shadow_only); C/A/I fundamentals not ingested
---

# CAN SLIM

## One-line summary
Buy the top 2-3 stocks of a leading group when they break out of a proper base, within 5% of the pivot, on volume
40-50% or more above average. Qualifying stocks show:
- quarterly EPS up 18-25% or more and accelerating
- 3-year EPS growth of 25% or more
- ROE of 17% or more
- RS rating of 80 or more
- rising fund ownership

Buy only in an IBD "confirmed uptrend" (the M rule). Cut losses at 7-8%, take most gains at 20-25%, and hold at
least 8 weeks any stock that rises 20% within 3 weeks.

## Origin and lineage
- William O'Neil, *How to Make Money in Stocks* (4 editions, through 2009/2011).
- The rules were reverse-engineered from the pre-run features of past big winners: 500, then 600, then 1,000
  stocks (AAII 2016 summary).
- IBD publishes the M rule as Market Pulse. Market School is IBD's signal counter for it.
- Descendants: Minervini, Morales/Kacher, Kell and Qullamaggie.
- The M rule has its own card. This card covers selection plus the entry.

## Exact rules
Detail is in `docs/methods/07-canslim-ibd-market-school.md`.

**Selection:**
- **C:** quarterly EPS vs the same quarter a year earlier, at least 18-20% (book, 4th edition) or 25% (IBD today).
  Both of the last 2 quarters should qualify and be accelerating. Quarterly sales growth at least 25%, or
  accelerating for 3 quarters.
- **A:** EPS up in each of the last 3 years, compound growth at least 25%, ROE at least 17%.
- **N:** new product, management or industry conditions, plus new price highs. AAII's proxy is within 10% of the
  52-week high.
- **S:** volume expands on up-moves.
- **L:** RS at least 80 (avoid below 70). Buy the top 2-3 in the group.
- **I:** about 20 institutional owners or more (AAII's screen uses 10 or more), with the number rising.
- **M:** confirmed uptrend. A follow-through day (FTD) is Day 4 or later of a rally attempt, a gain of at least
  1-1.25% on higher volume. A distribution day (DD) is a drop of at least 0.2% on higher volume; DDs expire after
  25 sessions or a 6% rally.

**Entry and exits:**
- **Entry:** pivot = handle high + $0.10 for a cup-with-handle; other bases use their own pivots (see
  `ibd_other_bases`). Breakout volume at least 40-50% above the 50-day average. Buy zone is pivot to pivot + 5%.
- **Stop:** 7-8% below the purchase price, no exceptions. Don't let a double-digit gain turn into a loss.
- **Exits:** take 20-25%. If the stock gains 20% or more within 3 weeks of breakout, hold at least 8 weeks from
  the breakout week. Sell on a climax run, a heavy-volume break of the 50-day, or two quarters of EPS slowdown.
- **SwingTrader variant:** 5-10 day holds, about 10% target, about 3% stop (secondary, unverified).

## What the engine code actually does
The chart side maps to `swing_engine/strategies/base_breakout.py`. It is `enabled: false, shadow_only: true`.

The rules it applies:
- **Patterns:** cup-with-handle (cup 35-325 bars, 12-33% deep; handle 5-25 bars, at most 12% deep, in the upper
  half, on handle volume no higher than the prior 50-day average) or flat base (25-325 bars, at most 15% deep).
- **Prior advance:** at least 30% over 126 bars.
- **Breakout:** close above the pivot with `vol_ratio_50d_prev >= 1.4`, no more than 5% above the pivot.
- **Filters:** `rs_63d_rank >= 0.80`. `min_market_trend_state = 1` (SPY uptrend) stands in for M.
- **Orders:** stop = max(base floor, entry x 0.93). Target +20%.
- **Exits:** a 40-bar time cap, and a close below `sma_50` on volume >= 1.4x `avg_vol_50d`.

Differences from O'Neil:
- No C/A/I fundamentals.
- RS is a 63-day percentile, not IBD's roughly 12-month weighted rating.
- The pivot has no +$0.10.
- No FTD/DD state machine.
- The 8-week hold rule is not implemented, because `should_exit` cannot see the entry price or the path. The fixed
  +20% target therefore sells exactly the fast movers that rule would hold.

## Why it should work
Each letter maps to a documented anomaly:
- C: post-earnings-announcement drift and earnings momentum.
- L and N: price momentum and the 52-week-high effect.
- A: profitability (Novy-Marx 2013).
- I: changes in the breadth of institutional ownership (Chen, Hong & Stein 2002).

M avoids momentum crashes, since about 3 of 4 stocks follow the market. The other side is the seller anchored to
old prices and institutions still building positions.

## When it works and when it fails
- **Works:** early in new uptrends after an FTD. The best breakouts come in the first weeks after it.
- **Fails:** narrow, rotating leadership (2025-26) and bifurcated breadth. Late-stage bases, and V-bottoms where
  the FTD comes late (Day 11 in Apr 2025).

## Parameters and sensitivity
| Parameter | Value |
|---|---|
| `eps_q_min` | 0.18-0.25 |
| `sales_q_min` | 0.25 |
| `eps_3y_min` | 0.25 |
| `roe_min` | 0.17 |
| `rs_min` | 0.80 |
| `vol_mult` | 1.4-1.5 |
| `max_ext` | 0.05 |
| `stop_pct` | 0.07-0.08 |
| `target_pct` | 0.20-0.25 |
| `fast_gain` / `fast_bars` / `hold_bars` | 0.20 / 15 / 40 |

The FTD threshold has drifted from about 1% to 2%, then 1.7%, then 1.25%. Fix one version; do not refit it by era.

## Evidence
- **Hypothetical screen:** AAII's CAN SLIM screen made 22.1%/yr over 10 years vs 10.7% for the S&P 500 (4 Feb
  2019). Costs were not included, and only about 3 stocks passed at a time.
- **Real money:**
  - FFTY (IBD 50 ETF) vs SPY to 6 Oct 2026: 1 year -4.74% vs +17.67%; 10 years 4.94%/yr vs 15.53%/yr.
  - O'Neil's own mutual funds had "lackluster" results.
- **Chart side:** EasySwing Cup & Handle, gross: 3,582 trades, 30% wins, +0.5R, PF 1.57.
- **FTD stats (unverified "Stock Guide 2024Q1"):** 33% of FTDs led to profitable rallies and 26.5% whipsawed
  within 15 days.
- No peer-reviewed out-of-sample test of the full system was found.
- Post-publication: the FFTY record suggests the mechanical selection has decayed or never had a net edge.

## Common mistakes
- Buying at the top of the 5% zone, which leaves the stop only 2-3% under the pivot.
- Holding through earnings.
- Using non-point-in-time EPS.
- Ignoring M.
- Buying laggards in the group.

## Discretionary parts and how to make them mechanical
- **N** (what is new) and group leadership: a Claude enum.
- **Proper base:** a `base_quality` review enum.
- **EPS quality** (one-time items): a review flag.
- **IBD group ranks:** proprietary. Substitute a sector RS rank.

## Implementation spec for swing-engine
**Data:** EDGAR XBRL companyfacts, stamped at filing acceptance. Derive:
- `eps_q_yoy`, `eps_accel` (current yoy minus prior yoy), `sales_q_yoy`, `eps_3y_cagr`, `roe`
- `inst_holders_chg` from 13F, which lags by 45 days

**Signal:**
- `base_breakout` geometry passes
- `eps_q_yoy >= 0.25`, `eps_3y_cagr >= 0.25`, `roe >= 0.17`
- an IBD-style RS percentile >= 0.80
- `ms_state == confirmed` (the new `features/market_school.py`)

**Orders:**
- Entry at the close, or a limit at pivot x 1.05 max.
- Stop = entry x 0.93.
- Target = entry x 1.20, unless the 8-week rule fired. That needs an exit hook that receives entry price and bars
  held, plus a `max_gain_since_entry` input.
- `max_hold_days` 40 (55 with the 8-week rule). Minimum R:R about 2.5 (20/8).

**Reuse:** `base_breakout` detectors, `rs_63d_rank`, `vol_ratio_50d_prev`, `dist_52w_high`, `sma_50`.

**Missing:**
- fundamentals ingest
- the Market School state machine, which needs real index volume
- path-aware exits
- earnings-date handling (do not enter inside `earnings_exit_days`)

## What the router should know
- `healthy_uptrend` only. Halve exposure while breadth is weak.
- Use Market School exposure, not the SPY SMA alone, when it exists.
- Treat it as the same family as `base_breakout`, and only add risk when the fundamentals filter adds names
  `base_breakout` would not take.

## Signs of decay to monitor
- FFTY vs SPY rolling 1 year.
- Breakouts hitting the 7% stop within 10 bars.
- Share of +20%-in-3-weeks winners.
- FTD failure rate in the engine's own state machine.

## Sources
- `docs/methods/07-canslim-ibd-market-school.md`; `docs/methods.md` 1a #6, 6.7
- https://www.aaii.com/files/journal/pdf/9874_william-oneil-can-slim-approach-to-selecting-growth-stocks.pdf
- https://www.aaii.com/stockideas/article/10668-oneils-can-slim-revised-3rd-edition-approach
- https://stockanalysis.com/etf/compare/ffty-vs-spy/
- https://finance.yahoo.com/news/know-invoke-8-week-hold-215800238.html
- https://finance.yahoo.com/news/identify-good-qualities-cup-handle-233000441.html
- https://easyswing.trading/performance
- https://quizlet.com/83588114/the-ibd-smartselect-corporate-ratings-flash-cards/ (catalog source; not read)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 238 | 2 | 49% | -0.01 | -0.04 | 42% | -0.05 | -0.08 | 39% | -0.08 | -0.11 | 0.84 |
| narrow_uptrend | 29 | 0 | 46% | -0.02 | -0.05 | 46% | +0.06 | +0.04 | 57% | +0.19 | +0.17 | 1.64 |
| **all** | 267 | 2 | 49% | -0.01 | -0.04 | 42% | -0.04 | -0.06 | 41% | -0.06 | -0.08 | 0.88 |

Portfolio replay (net of costs, slots shared with its run): 12 trades, win 58%, avg +0.58R, PF 2.70, P&L $6,286 on $100k, avg hold 25.9 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 1125 | 5 | 48% | -0.04 | -0.06 | 47% | -0.06 | -0.08 | 50% | -0.04 | -0.06 | 0.90 |
| narrow_uptrend | 203 | 1 | 49% | +0.03 | +0.01 | 51% | +0.08 | +0.05 | 48% | +0.09 | +0.06 | 1.24 |
| **all** | 1328 | 6 | 48% | -0.03 | -0.05 | 48% | -0.04 | -0.06 | 50% | -0.02 | -0.04 | 0.95 |

Portfolio replay (net of costs, slots shared with its run): 51 trades, win 33%, avg -0.02R, PF 0.96, P&L $-1,255 on $100k, avg hold 23.5 bars.
