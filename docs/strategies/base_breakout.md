---
slug: base_breakout
name: Classic base breakout - cup-with-handle and flat base (O'Neil / IBD / MarketSurge)
originators: [William J. O'Neil / IBD, Dan Zanger, Thomas Bulkowski (statistics)]
category: strategy
decision: have
holding_period_days: [5, 40]
timeframe: daily (patterns judged on daily/weekly)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: 0.30        # EasySwing Cup & Handle detector, gross
typical_payoff_ratio: 3.7     # computed here from EasySwing PF 1.57 and 30% wins: 1.57 * 0.70 / 0.30; gross
evidence_grade: C
free_data_ok: true
status: shadow_only
---

# Classic base breakout (`base_breakout`)

## One-line summary
Buy a leader (30%+ prior advance, high RS, confirmed market uptrend) on the close through the pivot of a 7-65 week
cup's handle or a 5+ week flat base no more than 15% deep, on volume 40%+ above average and no more than 5% past
the pivot; cut at 7-8% or back in the pattern; take 20-25%.

## Origin and lineage
- William O'Neil, *How to Make Money in Stocks* (1988) and IBD/MarketSmith (now MarketSurge): base taxonomy, 7-8%
  stop, 20-25% profit, 8-week hold rule, follow-through-day market filter.
- MarketSurge pattern recognition: 7 base types; pivot = handle high for cups with handles, left-side high for flat
  bases; buy zone 0-5% above pivot, profit zone 20-25%, loss zone 5-8% below (catalog P66).
- Dan Zanger (chartpattern.com): volume-first practice; cups 20-35% deep over 8-12 weeks, handle ~5% below the high.
- Thomas Bulkowski (*Encyclopedia of Chart Patterns*, thepatternsite.com): large-sample pattern statistics.
- Minervini (VCP), Kullamagi and Kell build on this vocabulary.

## Exact rules
As taught (IBD per secondary sources; investors.com was unreachable):
- **Screen**: prior advance >= 30% into the base; improving RS (RS rank >= 80 in coded replications; RS line at new
  highs preferred); CAN SLIM earnings (quarterly EPS +25% y/y etc.); handle above the 200-day MA.
- **Cup-with-handle**: >= 7 weeks (7-65), 12-15% to 33% deep (40-50% in bear markets), U shape; handle 1-2+ weeks in
  the upper half, 10-15% deep max (summaries 8-12%), drifting down on light volume.
- **Flat base**: >= 5 weeks, <= ~15% deep, often a second-stage base after a 20%+ advance.
- **Trigger**: breakout above the pivot (handle high or base high) + $0.10 on volume >= 40-50% above average.
- **Entry order**: buy stop at pivot + $0.10; buy zone up to 5% above the pivot.
- **Initial stop**: 7-8% below the buy point (O'Neil); handle low (Bulkowski); back in the pattern (Zanger).
- **Targets**: take 20-25%. 8-week rule: a 20%+ gain within 3 weeks of breakout -> hold at least 8 weeks through
  10-week-MA pullbacks. Bulkowski measure rule: breakout + cup height (met 61% of perfect trades).
- **Sizing**: risk-based; 7-8% stop at 1% risk gives a 12-14% position. IBD portfolios 4-8 names scaled by Market
  School exposure.

## Why it should work
- A base shakes out weak holders while supply dries up; the breakout on volume shows institutions absorbing remaining
  supply near a high (anchoring, George & Hwang 2004). Counterparty: holders selling at break-even near the old high,
  and shorts.
- Lo, Mamaysky & Wang (JF 2000): price patterns carry incremental information (cups not tested); Jiang, Kelly & Xiu (JF
  2023): chart images predict returns (gross).

## When it works and when it fails
- Works: early in a new market uptrend after a correction (Zanger); first and second bases; RS-line leaders; bull-
  market cups rose 34% on average vs 23% in bear markets (Bulkowski 2nd ed.).
- Fails: corrections ("fail en masse"); late-stage bases; lower-half or wedging handles; V cups; low-volume breakouts;
  narrow 2026 tape (breakouts reportedly failing since March 2026, unverified anecdote).

## Parameters and sensitivity
| Knob | Default | Range / source |
|---|---|---|
| `prior_advance_min` | 0.30 | O'Neil 30% |
| `advance_lookback` | 126 | 63-126 bars |
| `cup_min_bars` / `cup_max_bars` | 35 / 325 | 7-65 weeks |
| `cup_depth_min` / `cup_depth_max` | 0.12 / 0.33 | 12-33% |
| `handle_min_bars` / `handle_max_bars` | 5 / 25 | 1-5 weeks |
| `handle_depth_max` | 0.12 | 8-15% |
| `handle_upper_half` | True | |
| `handle_vol_ratio_max` | 1.0 | light volume |
| `flat_min_bars` / `flat_max_bars` | 25 / 325 | 5+ weeks |
| `flat_depth_max` | 0.15 | |
| `breakout_vol_mult` | 1.4 | 1.4-1.5 vs prior 50-day avg |
| `max_extension` | 0.05 | IBD buy zone |
| `rs_rank_min` | 0.80 | 63-day return percentile |
| `stop_pct` | 0.07 | 7-8% |
| `target_pct` | 0.20 | 20-25% |
| `max_hold_days` | 40 | time cap |
| `exit_ma` / `exit_volume_mult` | sma_50 / 1.4 | failure exit |
| `min_market_trend_state` | 1 | M gate |
| `min_reward_risk` | 2.0 | |
Traps: teacher rules disagree (cup 12-33% vs 20-35%, handle 5% vs 10-15%, volume 40/50/300%); pick one set; pivot
look-ahead (a pivot is known only after it forms).

## Evidence
- Bulkowski, site (fetched 2026-10-06 in doc 04): cup-with-handle rank 3/39, 5% break-even failure, 54% average rise,
  913 "perfect trades" (no stop, perfect exit); 300 cups 1990-Mar 2024: 47% dropped substantially within two months,
  23% rose no more than 15%.
- Bulkowski 2nd ed. (2005): 412 bull-market cups, average rise 34%; 28% failed to reach +15%, 55% failed +30%;
  throwbacks 58%.
- Bulkowski failure-rate study (13,932 patterns, 1991-2008): up-breakouts failing to gain 10% rose from 14% (1990s)
  to 28% (2003-07).
- EasySwing (7 Jul 2026, gross, ~2,000 US stocks, 5-year walk-forward): Cup & Handle 3,582 trades, 30% wins, +0.5R,
  PF 1.57, 8-day average hold; best of its base detectors.
- sofus-nl cup spec: 69% wins best regime vs 32% worst, 2.1R, 16-day hold, "55+ trades", no costs.
- Academic: no peer-reviewed net-of-cost single-stock cup or flat-base rule. Osler (1998) H&S unprofitable on average.

## Common mistakes
1. Treating Bulkowski "perfect trade" averages as tradeable.
2. Chasing beyond 5% of the pivot.
3. No market gate.
4. Tight stop just under the pivot (throwbacks).
5. Selling every winner at +20% and losing the right tail (8-week rule exists for this).
6. Holding through earnings by accident.

## Discretionary parts and how to make them mechanical
- U vs V cup, wedging handle, base stage (1st-2nd vs 4th+), overhead supply: Claude enums (`base_quality` A/B/C,
  `base_stage`), ranking only.
- CAN SLIM fundamentals: need point-in-time EDGAR XBRL (not ingested).
- Market School FTD/distribution days: proposed `features/market_school.py`.

## Implementation spec for swing-engine
What `swing_engine/strategies/base_breakout.py` does:
- Gates: `market_trend_state >= 1`; `trend_state >= 0`; `vol_ratio_50d_prev >= 1.4`; `rs_63d_rank >= 0.80`.
- Base search on the bars up to the bar before as-of (`end = t-1`), cup first then flat (features/patterns2.py):
  - Cup: right lip = highest high of the last 25 bars (handle 5-25 bars); left lip = highest high 35-325 bars before
    the right lip and above every bar in between; cup low = lowest low between lips; depth 12-33%; handle depth
    <= 12%; handle low above the cup midpoint; mean handle volume / `avg_vol_50d_prev` <= 1.0. Pivot = right-lip high.
  - Flat: longest window ending at t-1 (<= 325 bars) with (max high - min low)/max high <= 0.15, length >= 25.
    Pivot = base high.
  - Prior advance: top / min(low over 126 bars before base start) - 1 >= 0.30.
- Trigger: `0 < close / pivot - 1 <= 0.05`.
- Entry reference = close, next-open fill. Stop = max(base low or handle low, close x 0.93). Target = close x 1.20.
  Score = volume ratio + RS rank.
- `should_exit`: `bars_held >= 40`, or close < `sma_50` on volume >= 1.4 x `avg_vol_50d`.
Differences from the originators:
1. IBD 8-week rule not implemented (`should_exit` cannot see entry price or path); the +20% target sells the fast
   movers that rule would hold.
2. Close-based trigger, next-open fill, not a buy stop at pivot + $0.10.
3. RS is a 63-day return percentile, not IBD's 12-month RS or the RS line.
4. No fundamentals, no Market School; M gate = SPY trend state 1.
5. Flags, double bottoms, ascending bases, saucers, IPO bases not covered (separate catalog items).
- `max_hold_days`: 40. Min reward:risk: 2.0 (20% target vs <= 7% stop ~ 2.9R).
- Reuses: `trend_state`, `avg_vol_50d`, `vol_ratio_50d_prev`, `avg_vol_50d_prev`, `rs_63d_rank`, `sma_50`.
- Missing: partial-exit hook, entry-aware exit state (8-week rule), RS line vs SPY, earnings blackout, FTD state.

## What the router should know
- Settings: `enabled: false, shadow_only: true`; router allows it only in `healthy_uptrend` (1.0); code also requires
  SPY trend up.
- Overlaps `breakout_52w` and `sr_breakout`; expect few setups in narrow tapes.

## Signs of decay to monitor
- Share of breakouts back below the pivot within 5 bars (throwback-to-failure).
- Fraction failing to reach +10% (Bulkowski's measure) rising above ~30%.
- Shadow PF below 1.2 after costs over 50 trades.

## Sources
- docs/methods/04-chart-pattern-base-breakouts.md; docs/methods.md 1a #5, 6.4, 7b #2
- https://thepatternsite.com/cup.html
- https://thepatternsite.com/FailureRates.html
- https://www.chartpattern.com/cup-handle.cfm
- https://www.chartpattern.com/flat-base.cfm
- https://www.luxalgo.com/library/concept/cup-with-handle-base.md
- https://levelup.gitconnected.com/trading-cup-and-handles-with-marketsmith-pattern-recognition-3b869d0cfe2a
- https://easyswing.trading/performance
- https://github.com/sofus-nl/swing-trading-strategies/blob/main/strategies/02-cup-and-handle.md
- https://www.nber.org/papers/w7613
- Bulkowski, *Encyclopedia of Chart Patterns*, 2nd ed. (Wiley 2005), ch. 9; O'Neil, *How to Make Money in Stocks*

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 567 | 6 | 48% | -0.03 | -0.10 | 44% | -0.03 | -0.10 | 42% | -0.01 | -0.07 | 0.99 |
| narrow_uptrend | 45 | 2 | 40% | -0.19 | -0.26 | 39% | -0.21 | -0.28 | 51% | -0.04 | -0.12 | 0.92 |
| **all** | 612 | 8 | 48% | -0.04 | -0.11 | 44% | -0.04 | -0.11 | 43% | -0.01 | -0.07 | 0.99 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 3086 | 32 | 48% | -0.03 | -0.10 | 47% | -0.05 | -0.12 | 47% | -0.04 | -0.10 | 0.92 |
| narrow_uptrend | 486 | 0 | 49% | +0.01 | -0.07 | 53% | +0.06 | -0.01 | 48% | +0.07 | -0.01 | 1.18 |
| **all** | 3572 | 32 | 48% | -0.02 | -0.09 | 48% | -0.03 | -0.10 | 47% | -0.02 | -0.09 | 0.95 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 0%, avg -0.07R, PF 0.00, P&L $-16 on $100k, avg hold 40.0 bars.
