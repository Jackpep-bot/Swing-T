---
slug: episodic_pivot
name: Episodic pivot, delayed day-2 entry
originators: [Pradeep Bonde (Stockbee), Kristjan Kullamagi (Qullamaggie)]
category: strategy
decision: have
holding_period_days: [3, 60]
timeframe: daily (taught day-1 entry is intraday opening-range high)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null        # Bonde's ~0.70 (good markets) is unaudited; no public mechanical win rate
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: shadow_only
---

# Episodic pivot (delayed / day-2)

## One-line summary
A neglected stock (flat 3-6+ months) gets a real surprise, gaps up 10%+ on 3-10x volume and closes strong; the
engine buys the day after, when price closes above the gap-day high, stops at the gap-day low (skip if more than
1.5 ADR away) and trails the 10-day MA.

## Origin and lineage
- Pradeep Bonde (Stockbee) named it in Feb 2007 and tied it to post-earnings-announcement drift (PEAD) in Feb 2010.
- Kullamagi made it one of his "3 timeless setups" (Jan 2021) and wrote "How to master a setup: Episodic Pivots"
  (Nov 2021).
- Cousins: Morales/Kacher Buyable Gap-Up, Trader Stewie Power Earnings Gap (engine: `power_gap`).
- IBKR Campus "Chart Advisor" variant: gap on extreme volume, low-volume drift back toward the gap, buy near the gap
  area using high-volume price nodes as support (thresholds not published). This is a delayed-entry variant.
- Bonde's Nov 2026 bootcamp still lists EP, EP9M and delayed-reaction EP.
- Full write-up: `docs/methods/02-episodic-pivot.md`; `docs/methods.md` 6.2, 7b #5.

## Exact rules (as taught)
| Step | Kullamagi (primary) | Bonde (primary 2007/2010; secondary 2024) |
|---|---|---|
| Gap | >= 10% | 2010 scan: +8% on >= 300k shares and >= 3x the 100-day average volume, or a $5+ move on 1M+ shares for $62.50+ stocks |
| Volume | Trades the average daily volume in the first 15-30 minutes | 10x+ on true earnings breakouts; EP9M >= 9M shares |
| Catalyst | Earnings with big growth and a beat; also FDA, contracts, policy, hot sector | Earnings/sales acceleration, guidance raise, contracts, drug approvals; low quality: media mentions |
| Neglect | Not rallied in the past 3-6 months; no recent EP | Neglected 2 months to 1-3 years; MAGNA53 boosters (short interest, analyst raises) |
| Entry | Opening-range high (1/5/60-minute), "no need to be first in" | At the open or after a few minutes; delayed-reaction EP day 2+ |
| Stop | Low of day; risk max 1-1.5 ADR, else size down or skip | 2010: low of the last 2 days; 2024: ~2.5% |
| Exit | Sell 1/3-1/2 after 3-5 days, breakeven, trail 10/20-day | 2010: four parts, 20%+ target; holds weeks to months; EP9M 3-20 days |
| Sizing | Risk 0.25-1%; max 30% of account in one stock overnight | Singles 20-25% of account with tight stops |

## Why it should work
- Mechanism: underreaction to large, surprising news in stocks nobody owns (PEAD; Hong-Lim-Stein 2000 neglect;
  Chan 2003: drift after headline news). Institutions need weeks to build positions in a newly relevant name.
- Other side: holders who sold the base, short sellers covering over days, analysts slow to revise.
- Without a catalyst it inverts: Chan (2003) finds reversal after extreme no-news moves; ~66% of 2019-24 US
  gap-ups closed below the open (Torres, Feb 2024).

## When it works and when it fails
- Works: earnings season in a healthy market (Bonde: 10-12 classic EPs/year in good markets vs 3-4 in chop),
  sales-led surprises, low float, first EP after a long base.
- Fails: offering/dilution gaps, no-news gaps, M&A gaps (capped), already-extended or repeat EPs, 20-40% day-1
  ranges that put the stop 2-3 ADR away, corrections. Small-cap tail: 67% of 50%+ gappers close below the open
  (`docs/smallcap-spec.md`).

## Parameters and sensitivity
| Knob | Code default | Range | Note |
|---|---|---|---|
| `min_gap_pct` | 0.10 | 0.08-0.15 | Bonde's 8% needs heavier volume |
| `min_rvol` | 3.0 | 2-10 | Code divides by prior 20-day average; Bonde uses 100-day |
| `min_close_pos` | 0.5 | 0.5-0.75 | |
| `neglect_max_ret` | 0.30 | 0.15-0.40 on `ret_126d` | |
| `repeat_lookback` | 252 | 126-504 | |
| `max_stop_adr` | 1.5 | 1.0-2.0 | |
| `trail_ma` / `trail_after_bars` | sma_10 / 3 | sma_10-sma_20 / 2-5 | |
| `max_hold_days` | 60 | 20-90 | |
Traps: few events per year per regime, so every knob is fitted on a small sample; earnings-season clustering
makes trades correlated (effective N is lower than trade count).

## Evidence
- Self-reported: Bonde ~70% wins on classic EPs in good markets (2024 talk notes, unaudited); no P&L series.
- Ney Torres H (What Works in Trading, 28 Sep 2026): every mechanical EP version he coded lost to the S&P 500
  (numbers paywalled). Treat as no public evidence of a mechanical edge.
- Torres gap study (2019-01 to 2024-02, all US gap-ups): median gap 7.14%; ~65.9% closed below the open.
- PEAD decay: Martineau (CFR 2022) finds large-cap PEAD non-existent since about 2006; Subrahmanyam (Dec 2025)
  drift t-stat 2.18 all stocks, 1.43 excluding microcaps. Counter: Hirshleifer-Peng-Wang (RFS 2025).
- No audited, cost-inclusive EP backtest with win rate or PF was found (`docs/methods/02-episodic-pivot.md`).

## Common mistakes
1. Scanning gaps without a catalyst filter (that is a gap-fade universe).
2. Buying day 1 when the low of day is 2-3 ADR away.
3. Treating offerings, reverse splits or PR fluff as catalysts.
4. Look-ahead: using day-1 close/volume as if known at the open.
5. Concentration: five EPs in one theme in the same earnings week.

## Discretionary parts and how to make them mechanical
| Discretionary | Mechanical / enum route |
|---|---|
| Catalyst quality | Claude `Classification` enum from news + 8-K items (2.02 earnings vs 3.02 dilution); `catalyst_verified` feature |
| Growth magnitude | Needs point-in-time fundamentals (not ingested) |
| Neglect | prior-row `ret_126d <= 0.30`, no EP in 252 bars (coded); analyst/short-interest neglect not available |
| Day-1 vs delayed | Daily engine can only do delayed; day-1 ORH belongs to the monitor (`premarket_gap`, `peg_survivor`, `rvol_now`) |

## Implementation spec for swing-engine
Module: `swing_engine/strategies/episodic_pivot.py` (built; `enabled: false, shadow_only: true`).
What the code does:
- Day 1 (bar e = t-1): `gap_pct >= 0.10` and `rvol_day >= 3.0` (volume / prior 20-day average) and
  `close_pos >= 0.5`.
- Day 2 (bar t): `close_t > high_e`.
- Neglect: `ret_126d` at bar e-1 (before the gap) <= 0.30. No other bar with gap >= 10% and rvol >= 3 in the
  252 bars before e.
- Stop = `low_e`; skip if `close_t - low_e > 1.5 * adr_pct_20 * close_t`.
- Entry = `close_t` as signal; backtest/replay fill at the open of t+1 (so effectively a day-3 open fill).
- Target = entry + 10R (reference). Score = `rvol_e * (1 + gap_e)`. `features.catalyst_verified = 0`.
- Exit: after 3 bars, first close < `sma_10`; time stop 60 bars. Engine-wide breakeven at +1R and 10-day-low trail
  from +2R also apply in replay/autopilot.
- Gates: `min_trend_state = -1` (any), `min_market_trend_state = 0`; router allows it only in `healthy_uptrend`.
Differences from the originators / methods 7b #5:
1. No earnings or catalyst requirement (no point-in-time earnings dates in the panel); 7b says earnings required.
2. Fill is the day-3 open, later than Bonde's day-2 entry and far later than the day-1 ORH.
3. The 3-10 bar flag variant ("first close above the EP-day high after a flag above the EP low") is not coded;
   only the immediate day-2 close trigger.
4. No check that the gap-day close held above its open (only `close_pos`).
5. No partial sale; no float filter; volume baseline is 20-day, not Bonde's 100-day.
6. Live `earnings_exit_days: 1` will exit before the next report, cutting the multi-quarter drift Bonde describes.
Missing: point-in-time earnings dates (`days_since_earnings` from EDGAR 8-K 2.02 acceptance time), catalyst enum
wired into signals, flag variant, scale-out hook, intraday bars for day-1 ORH.
max_hold_days: 60. Minimum reward:risk: n/a (trail exit); stop distance capped at 1.5 ADR.

## What the router should know
- Only `healthy_uptrend` today; with a verified catalyst it may be reasonable in `narrow_uptrend` at reduced size
  (untested).
- Signals bunch in earnings season; apply the 30% sector cap.
- Without `catalyst_verified = 1` treat signals as shadow-only regardless of regime.

## Signs of decay to monitor
- Share of day-2 triggers that close back below the gap-day low within 5 bars > 50%.
- Average R of catalyst-verified vs unverified signals converging (catalyst filter adding nothing).
- Day-1 gaps growing (median gap/ADR rising) so most setups exceed 1.5 ADR and are skipped.

## Sources
- https://stockbee.blogspot.com/2007/02/episodic-pivots-and-idea-pickle.html
- https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html
- https://stockbee.blogspot.com/2026/09/november-2026-bootcamp-las-vegas.html
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://www.interactivebrokers.com/campus/traders-insight/securities/macro/chart-advisor-a-swing-traders-paradise/
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://whatworksintrading.substack.com/p/kristjan-qullamaggie-and-stockbee
- https://whatworksintrading.substack.com/p/deep-dive-on-gap-trading-how-did
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- Repo: `docs/methods/02-episodic-pivot.md`, `docs/methods.md` 6.2 / 7b #5, `swing_engine/strategies/episodic_pivot.py`, `docs/smallcap-spec.md`

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| high_vol_selloff | 2 | 1 | 100% | +0.12 | -0.03 | 100% | +0.60 | +0.44 | 100% | +0.88 | +0.73 | inf |
| **all** | 2 | 1 | 100% | +0.12 | -0.03 | 100% | +0.60 | +0.44 | 100% | +0.88 | +0.73 | inf |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1 | 0 | 0% | -0.71 | -0.74 | 0% | -0.03 | -0.06 | 100% | +0.04 | +0.01 | inf |
| correction | 1 | 0 | 100% | +0.54 | +0.54 | 0% | -0.07 | -0.07 | 0% | -0.56 | -0.57 | 0.00 |
| healthy_uptrend | 2 | 0 | 50% | +1.17 | +1.01 | 50% | +0.11 | -0.06 | 0% | -0.58 | -0.74 | 0.00 |
| high_vol_selloff | 2 | 0 | 50% | +1.04 | +1.01 | 100% | +2.00 | +1.97 | 50% | +0.74 | +0.70 | 2.35 |
| narrow_uptrend | 2 | 0 | 0% | -0.49 | -0.51 | 50% | -0.13 | -0.16 | 50% | -0.41 | -0.44 | 0.06 |
| **all** | 8 | 0 | 38% | +0.41 | +0.35 | 50% | +0.48 | +0.42 | 38% | -0.13 | -0.19 | 0.72 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 100%, avg +5.68R, PF inf, P&L $868 on $100k, avg hold 16.0 bars.
