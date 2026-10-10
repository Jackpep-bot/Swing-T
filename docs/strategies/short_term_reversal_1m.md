---
slug: short_term_reversal_1m
name: Short-term (1-month) reversal
originators: [Narasimhan Jegadeesh (1990), Bruce Lehmann (1990), Fama-French ST_Rev factor, de Groot-Huij-Zhou (2012)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 21]
timeframe: daily
direction: long   # academic version is long-short; engine is long-only, so only the loser leg is usable
regimes_good: [choppy, high_vol_selloff]
regimes_bad: [correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built   # rev_5d / rev_21d features exist; no strategy module, not in config/settings.yaml
---

# Short-term (1-month) reversal

## One-line summary
Last month's biggest losers tend to beat last month's biggest winners next month; the effect is real in equal-weighted,
small-cap-heavy tests but largely disappears value-weighted and after costs, so in this engine it is an entry-timing
overlay inside momentum names, not a standalone strategy.

## Origin and lineage
- Jegadeesh (Journal of Finance, 1990) and Lehmann (QJE, 1990) documented monthly / weekly reversal.
- Kenneth French's library publishes ST_Rev (prior-month return sort) as a standard factor.
- de Groot, Huij and Zhou (Journal of Banking & Finance, 2012) showed a cost-aware large-cap, weekly version survives costs.
- Medhat and Schmeling ("Short-term Momentum", Review of Financial Studies, March 2022) split it by turnover: reversal
  in low-turnover stocks, continuation in high-turnover stocks.
- Related engine docs: `docs/methods/01-pullback-20-50-ma-uptrend.md` (pullback = short-term reversal inside momentum),
  `docs/methods/09-stockbee-momentum-burst.md`, `docs/methods/10-parabolic-short-and-long-reversal.md` (Nagel 2012).

## Exact rules
Academic factor (as catalogued):
- Universe: all common stocks (Jegadeesh: equal weight, all-stock breakpoints).
- Signal: return over month t-1 (about 21 trading days).
- Portfolio: long bottom decile (losers), short top decile (winners), rebalanced monthly, held one month.
- No stops, no targets; time exit only. Equal or value weight.

Cost-aware variant (de Groot et al.): large caps only, weekly rebalance, a portfolio construction that limits turnover;
abstract reports 30-50 bp per week net of costs. Exact construction details were not re-read this run.

Engine-adapted long-only overlay (the catalog's "source_engine_use"): inside long-momentum candidates, buy after a 1-4
week pullback, only in low-turnover names, never after an earnings or news gap.

## Why it should work
Liquidity provision: the buyer of a recent loser is paid for absorbing order-flow imbalances from forced or impatient
sellers (Nagel 2012: reversal returns rise with VIX). Part of the measured effect is bid-ask bounce in small stocks,
which a trader cannot capture. Medhat-Schmeling: where turnover is high, price moves carry information and continue.

## When it works and when it fails
- Works: after liquidity shocks (high VIX), in low-turnover large caps, when the decline is not news-driven.
- Fails: news/earnings-driven moves (information, not liquidity), high-turnover names (continuation), value-weighted
  universes, and anywhere costs approach the weekly edge. Persistent bear markets: losers keep losing.

## Parameters and sensitivity
- Lookback: 5 days (`rev_5d`) or 21 days (`rev_21d`). Weekly versions are noisier but stronger gross.
- Bucket: decile vs quintile. Holding: 5 vs 21 days. Size floor (large caps only).
- Turnover split: needs shares outstanding; without it the key conditioning variable is missing.
- Trap: equal-weight tests on the whole universe report the bid-ask-bounce version; never compare to that.

## Evidence
- Jegadeesh 1990: about -1.99%/month spread (t = -12.55), EW, all-stock breakpoints (as quoted by Hou-Xue-Zhang).
- Hou-Xue-Zhang replication (NBER w23394), VW NYSE breakpoints: -0.26%/month (t = -1.31), fails replication.
- de Groot-Huij-Zhou 2012: 30-50 bp/week net of costs in large caps with a turnover-limiting construction (abstract).
- Medhat-Schmeling 2022 (1963-2018 sample): reversal only among low-turnover stocks; high-turnover winners continue,
  and that short-term momentum is said to survive costs and be strongest in the largest, most liquid stocks.
- Decay / costs: turnover near 100%/month; costs are the binding constraint. Dimensional's Q&A calls it impractical
  standalone and useful as entry timing.

## Common mistakes
- Treating the EW t-stat as tradable. Buying losers that fell on earnings or guidance. Ignoring turnover.
- Running it as a short-winners book in a long-only engine.

## Discretionary parts and how to make them mechanical
- "Not after a news gap": exclude names with `abs(gap_pct) >= 0.05` on any of the last 21 bars, plus any earnings date
  within the lookback once point-in-time earnings dates exist.
- "Low turnover": turnover_21d = avg_vol_20d / shares_outstanding, below the cross-sectional median. Proxy until shares
  data exists: `amihud_21d` above median (illiquid ~ low turnover), labelled as a proxy.

## Implementation spec for swing-engine
- Today: `rev_5d` / `rev_21d` (= minus the 5- / 21-bar return, `features/cross_section.py reversal()`) are panel
  columns and inputs to the ML ranker (`research/ranker.py`); no strategy trades them.
- Reuses: `rev_5d`, `rev_21d`, `ret_21d`, `mom_12_1`, `trend_state`, `dollar_vol_20d`, `gap_pct`, `atr_14`, `amihud_21d`.
- Missing: cross-sectional percentile rank by date (`rank_pct(col)`), `shares_outstanding` / turnover, earnings dates.
- Screen (weekly, Friday close): top 500 by `dollar_vol_20d`; `mom_12_1` in top 30% cross-sectionally; `trend_state >= 0`.
- Setup: `rank_pct(rev_21d) >= 0.9` within that screen (biggest 1-month losers among momentum names); no gap filter hit.
- Entry: next open (engine default). Stop: catastrophe stop `entry - 2.5 * atr_14` (engine choice; the factor has none).
- Target: none; exit on time. `max_hold_days`: 5 (weekly variant) or 21 (monthly variant), run both.
- `min_reward_risk: 0.0` (rule/time exit, as for `rsi2_meanrev`).
- Score: `rank_pct(rev_21d)`.

## What the router should know
Only meaningful as a comparison to `pullback_trend` / `rsi2_meanrev` (it is their academic parent). Allow in `choppy`
and `high_vol_selloff` at small size; block in `correction`. Correlated with `rsi2_meanrev` signals.

## Signs of decay to monitor
Weekly net return of the loser leg vs equal-size SPY falls below 0 over 26 weeks; average round-trip cost / gross edge
> 50%; hit rate of losers vs universe median drops toward 50%.

## Sources
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf (Hou-Xue-Zhang replication)
- https://ideas.repec.org/a/eee/jbfina/v36y2012i2p371-382.html (de Groot-Huij-Zhou 2012)
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx
- https://alphaarchitect.com/short-term-momentum/ (Medhat-Schmeling summary)
- https://repec.cepr.org/repec/cpr/ceprdp/DP15857.pdf (Medhat-Schmeling working paper)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 102 | 0 | 44% | +0.03 | -0.02 | 45% | +0.05 | +0.00 | 49% | +0.06 | +0.01 | 1.20 |
| correction | 8 | 0 | 50% | +0.02 | -0.14 | 50% | +0.10 | -0.06 | 75% | +0.51 | +0.35 | 4.47 |
| healthy_uptrend | 332 | 0 | 48% | +0.00 | -0.07 | 45% | +0.02 | -0.05 | 37% | -0.05 | -0.12 | 0.90 |
| high_vol_selloff | 37 | 0 | 43% | -0.04 | -0.10 | 59% | +0.13 | +0.07 | 51% | +0.24 | +0.18 | 1.59 |
| narrow_uptrend | 59 | 0 | 48% | +0.07 | +0.02 | 42% | +0.00 | -0.05 | 47% | +0.27 | +0.21 | 1.67 |
| **all** | 538 | 0 | 47% | +0.01 | -0.06 | 46% | +0.04 | -0.03 | 42% | +0.02 | -0.05 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 504 | 0 | 58% | +0.11 | +0.05 | 56% | +0.13 | +0.08 | 52% | +0.18 | +0.12 | 1.48 |
| correction | 408 | 1 | 60% | +0.09 | +0.02 | 59% | +0.12 | +0.05 | 56% | +0.21 | +0.14 | 1.61 |
| healthy_uptrend | 1698 | 3 | 49% | +0.00 | -0.07 | 49% | +0.01 | -0.05 | 45% | +0.03 | -0.04 | 1.06 |
| high_vol_selloff | 264 | 1 | 44% | +0.00 | -0.06 | 51% | -0.03 | -0.08 | 45% | -0.03 | -0.09 | 0.94 |
| narrow_uptrend | 318 | 0 | 59% | +0.09 | +0.03 | 56% | +0.08 | +0.02 | 48% | +0.04 | -0.02 | 1.10 |
| **all** | 3192 | 5 | 53% | +0.04 | -0.03 | 52% | +0.05 | -0.01 | 48% | +0.07 | +0.01 | 1.17 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
