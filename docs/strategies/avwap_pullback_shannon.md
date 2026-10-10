---
slug: avwap_pullback_shannon
name: Anchored-VWAP pullback (Brian Shannon multi-timeframe)
originators: [Brian Shannon (Alphatrends); AVWAP lineage Paul Levine (MIDAS)]
category: strategy
decision: implement
holding_period_days: [3, 30]
timeframe: daily setup (taught trigger on 65/15/5-minute bars)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: 0.55        # self-reported "50 to 60%", unaudited
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Anchored-VWAP pullback (Shannon)

## One-line summary
In a Stage 2 stock above a rising anchored VWAP, wait for a 2-6 day pullback on falling volume toward the rising
5-day MA / AVWAP, then buy only when strength returns (higher low, close above the prior high and the 5-day MA);
stop under the dip low, first third at the R2 pivot or swing high, trail while the 5-day MA rises.

## Origin and lineage
- Brian Shannon, CMT: *Technical Analysis Using Multiple Timeframes* (2008), *Maximum Trading Gains with Anchored
  VWAP* (2023). Motto "Don't buy the dip, buy strength after the dip". He says he popularised AVWAP but did not
  invent it (Levine's MIDAS, ~1996).
- Active through 2026 (CMT Fill the Gap ep. 61, recorded 2026-02-04; weekly posts to 2026-09-25).
- Engine use per methods 7b #6: either its own module or an entry-quality filter on the pullback family.
- Full write-up: `docs/methods/08-anchored-vwap-multi-timeframe-shannon.md`.

## Exact rules (as taught)
| Step | Rule | Tag |
|---|---|---|
| Universe | ~1,100 liquid stocks weekly narrowed to ~150 candidates; no RS ranking | primary (podcast summary) |
| Trend | Stage 2 markup: higher highs/lows, above a rising 50-day; weekly agrees | secondary (book) |
| Anchor | A meaningful event bar: high-volume session (> 1.5x normal), earnings, swing low/high, gap, IPO second candle; YTD/QTD/MTD for indices | primary + secondary |
| Setup | Price above a rising AVWAP; pullback 2-6 days on declining volume toward the rising 5-day MA / AVWAP; level tested 1-2 times at most | secondary |
| Trigger | Higher low on the execution timeframe, takes out the prior short-term high, reclaims the 5-day MA and the AVWAP anchored at the pullback's high | primary (alphatrends) |
| Entry | On that confirmation, intraday; not on first touch | primary/secondary |
| Initial stop | Low of the dip (example 1.8%) | primary example |
| Targets | First third "under strict circumstances", reference = daily R2 floor pivot | primary |
| Trail | Under 15-minute higher lows while the 5-day MA rises; 2-minute lows during momentum runs | primary |
| Thesis exit | 5-day MA rolls over or price loses the AVWAP it rode | secondary |
| Hold | 3-6 days typical, sometimes 5-6 weeks | primary |
| Sizing | No per-trade % stated; 6-7 positions typical | primary |

## Why it should work
- AVWAP from an event is the average cost of everyone who bought since; above a rising AVWAP the average holder is
  in profit and less likely to sell (cost-basis / capital-gains-overhang idea).
- Waiting for strength after the dip filters dips that keep falling (the first-touch losers).
- Other side: short-term sellers exhausting into the pullback; buyers defending their cost basis.

## When it works and when it fails
- Works: trending stocks with orderly dips; self-throttles in chop because a flat AVWAP gives no setups.
- Fails: anchors tested 3+ times; price oscillating around a flat AVWAP; news-driven dips; extended breakouts.
- Daily-bar version degrades to a generic MA-pullback (the claimed edge is in the intraday trigger).

## Parameters and sensitivity
| Knob | Proposed | Range |
|---|---|---|
| anchor menu | pivot low (width 5), max-volume bar in 63 bars with rvol >= 1.5, earnings day, YTD | fixed menu, no tuning per name |
| `avwap_slope_bars` | 5 | 3-10 |
| `max_touches` | 2 | 1-3 |
| `pullback_bars` | 2-6 | |
| `max_pullback_volume_ratio` | 1.0 | 0.8-1.0 |
| `max_stop_pct` | 0.03 | 0.02-0.05 |
| `time_stop_bars` | 30 | 20-40 |
Traps: the anchor menu is a hidden parameter grid; log every anchor x knob combination as a trial.

## Evidence
- No published test of Shannon's method; self-reported 50-60% wins (unaudited).
- Zarattini & Aziz (2023/24) session-VWAP QQQ day-trading study: Sharpe 2.1, 671% 2018-2023 (net of commissions,
  no slippage detail); a QuantConnect replication thread did not reproduce it after realistic spreads.
- EFMA 2012 paper (abstract only): VWAP in place of close in classic rules was less profitable (unverified).
- Murtazin (Jan 2025) daily VWAP crossover on 50 large S&P names 2020-2023: "mixed", no aggregates.
- Grade D (catalog; methods.md gives C-/D).

## Common mistakes
1. Buying the first touch of AVWAP (most naive backtests test exactly this).
2. Look-ahead pivot anchors: a swing low is only known N bars later.
3. Using unadjusted price with adjusted volume (the line jumps at splits).
4. Trading flat-AVWAP chop.
5. Chasing breakouts far above the AVWAP from the prior high.

## Discretionary parts and how to make them mechanical
| Discretionary | Mechanical proxy |
|---|---|
| Which anchor | deterministic menu; emit all AVWAPs; Claude review flags conflicts as an enum |
| Intraday higher low / reclaim | daily: `close > high[t-1]` and `close > sma_5` and `close > avwap`; later 65-minute resample (6 bars/day, 5-day MA = 30 bars) |
| R2 first-third target | `P = (H+L+C)/3` of the entry bar, `R2 = P + (H - L)`; needs a scale-out hook; until then use swing high as target or trail only |
| "Choppy" | AVWAP slope <= 0 or price crossed AVWAP >= 3 times in 10 bars => no trade |

## Implementation spec for swing-engine
Proposed `swing_engine/features/avwap.py` + `swing_engine/strategies/avwap_pullback.py` (not built; register
`enabled: false, shadow_only: true`, family `pullback`).
- AVWAP from anchor index a, on daily bars: `avwap[t] = sum_{k=a..t}(px_k * volume_k) / sum_{k=a..t} volume_k`
  with `px_k` = the panel's daily `vwap` column when present, else typical price `(H+L+C)/3`. Price and volume
  must use the same split adjustment.
- Anchors (point-in-time): `avwap_pl` = last confirmed pivot low (pivot width 5 as in `features/levels.py`;
  usable only from pivot+5 bars); `avwap_vol` = highest-volume bar in the last 63 with `rvol_day >= 1.5`;
  `avwap_earn` = last earnings session (needs point-in-time dates; missing); `avwap_ytd` for SPY/QQQ.
- Derived: `avwap_*_slope5 = avwap[t] - avwap[t-5]`; `avwap_*_touches` = count of bars since anchor with
  `low <= avwap * 1.01` and `close >= avwap`.
- New feature `sma_5`.
- Setup at t: `trend_state == 1`; chosen avwap rising (`slope5 > 0`), `touches <= 2`; pullback of 2-6 bars with
  lower highs; pullback low <= max(avwap, sma_5) * 1.01; mean pullback volume / `avg_vol_20d` <= 1.0.
- Trigger: `close[t] > high[t-1]`, `close[t] > sma_5[t]`, `close[t] > avwap[t]`.
- Entry: signal at close, next-open fill. Stop = pullback low - 0.1 * `atr_14`; skip if `(entry - stop)/entry > 0.03`.
- Target: prior 20-bar swing high (reuse `pullback_trend` `target_mode = swing_high`); `min_reward_risk` 1.0.
- Exit: `should_exit` when `close < avwap` (thesis) or `sma_5[t] < sma_5[t-1]` and close < sma_5, or 30 bars.
- Alternative use: add `close > avwap_pl and avwap_pl_slope5 > 0 and touches <= 2` as a filter param on
  `pullback_trend` / `pullback_holy_grail` and measure the lift.
- Missing: `features/avwap.py`, `sma_5`, earnings dates, scale-out hook, intraday bars.
max_hold_days: 30. Min reward:risk 1.0 (swing-high target), else trail.

## What the router should know
- Pullback family placement: 1.0 in `healthy_uptrend`, 0.5 in `narrow_uptrend`; off elsewhere.
- Market-level use: SPY above a rising YTD AVWAP as an extra confirmation for `narrow_uptrend` pullbacks
  (untested).

## Signs of decay to monitor
- Filter lift: pullback-family signals passing the AVWAP filter no better than those failing it over 100+ signals.
- Rising share of trades closing back below AVWAP within 3 bars.

## Sources
- https://alphatrends.net/anchored-vwap/
- https://alphatrends.net/dont-buy-the-dip-buy-strength-after-the-dip/
- https://cmtassociation.org/podcast/fill-the-gap-episode-sixty-one-anchored-vwap-legend-brian-shannon-cmt/
- https://www.financialwisdomtv.com/post/maximum-trading-gains-using-price-time-volume
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap
- https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/
- https://www.quantconnect.com/forum/discussion/16706
- https://ayratmurtazin.beehiiv.com/p/i-tested-this-strategy-on-the-100-largest-us-companies-here-are-the-results
- Repo: `docs/methods/08-anchored-vwap-multi-timeframe-shannon.md`, `docs/methods.md` 6.8 / 7b #6, `swing_engine/strategies/pullback_trend.py`, `swing_engine/features/levels.py`

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11 | 1 | 70% | +0.23 | +0.12 | 50% | +0.52 | +0.42 | 50% | +0.48 | +0.38 | 1.77 |
| correction | 1 | 0 | 0% | -0.97 | -1.08 | 0% | -0.97 | -1.08 | 0% | -0.97 | -1.08 | 0.00 |
| healthy_uptrend | 21 | 0 | 38% | -0.28 | -0.43 | 38% | -0.13 | -0.28 | 38% | -0.14 | -0.29 | 0.81 |
| high_vol_selloff | 2 | 0 | 50% | +0.28 | +0.07 | 50% | +0.28 | +0.07 | 50% | +0.28 | +0.07 | 1.87 |
| narrow_uptrend | 1 | 0 | 0% | -1.04 | -1.11 | 0% | -1.04 | -1.11 | 0% | -1.04 | -1.11 | 0.00 |
| **all** | 36 | 1 | 46% | -0.15 | -0.28 | 40% | +0.03 | -0.11 | 40% | +0.01 | -0.13 | 1.02 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 12 | 0 | 42% | -0.15 | -0.59 | 33% | -0.37 | -0.81 | 25% | -0.65 | -1.08 | 0.20 |
| correction | 8 | 0 | 50% | +0.16 | -0.75 | 50% | +0.17 | -0.73 | 50% | +0.17 | -0.73 | 1.37 |
| healthy_uptrend | 143 | 3 | 50% | +0.02 | -0.28 | 45% | -0.02 | -0.32 | 41% | -0.09 | -0.39 | 0.85 |
| high_vol_selloff | 8 | 0 | 62% | +0.20 | -0.22 | 38% | -0.16 | -0.59 | 25% | -0.35 | -0.78 | 0.51 |
| narrow_uptrend | 17 | 1 | 44% | -0.06 | -0.26 | 44% | -0.07 | -0.27 | 50% | +0.29 | +0.09 | 1.61 |
| **all** | 188 | 4 | 49% | +0.01 | -0.31 | 44% | -0.05 | -0.38 | 40% | -0.09 | -0.42 | 0.85 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
