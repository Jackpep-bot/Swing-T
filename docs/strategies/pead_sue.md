---
slug: pead_sue
name: Post-earnings-announcement drift (SUE)
originators: [Ball and Brown (1968), Foster-Olsen-Shevlin (1984), Bernard and Thomas (1989, 1990)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [20, 60]
timeframe: daily bars, quarterly signal
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Post-earnings-announcement drift (SUE)

## One-line summary
Stocks with the largest standardized earnings surprise keep drifting in the surprise direction for ~60 trading days;
since about 2006 this no longer holds outside microcaps.

## Origin and lineage
Ball-Brown (1968) first noted drift; Foster-Olsen-Shevlin (1984) defined time-series SUE; Bernard-Thomas (1989/1990)
attributed it to investors underweighting the seasonal autocorrelation of earnings. Martineau (CFR 2022) shows it has
disappeared for all but microcaps. Related engine work: `docs/methods/13-power-earnings-gap.md` (price-reaction version).

## Exact rules (catalog E21)
- Time-series SUE = (EPS_q - EPS_{q-4}) / std of that seasonal change over the prior 8 quarters (minimum 6).
- Analyst SUE (Martineau) = (actual EPS - median of analysts' latest forecasts in the 90 days before) / price 5 days before.
- Each month, rank on the latest SUE whose fiscal quarter ended within the last 6 months; long the top decile
  (academic long-short also shorts the bottom decile). Bernard-Thomas measured a 60-trading-day drift window.
- No stop; equal or value weight; monthly rebalance.

## Why it should work
Under-reaction: investors anchor on seasonal random-walk expectations; limited attention; arbitrage costs in small
names. Counterparty: slow-updating holders. Now largely arbitraged: prices react fully on day 0 in liquid names.

## When it works and when it fails
Residual only in microcaps, where spreads/impact eat most of it (methods.md 4b: costs 70-100% of the residual).
Fails in large and mid caps since about 2006.

## Parameters and sensitivity
SUE definition (time-series vs analyst), decile cut, holding window (1, 6, 12 months), size filter. HXZ show the
1-month holding is the only significant one.

## Evidence
- Bernard-Thomas: top-minus-bottom SUE spread positive in 41 of 48 quarters, 1974-85.
- Hou-Xue-Zhang (NBER w23394, "Replicating Anomalies"): Sue1 0.47%/month (t = 3.42); Sue6 0.19% and Sue12 0.11%
  insignificant; q-factor alpha 0.05.
- Martineau (CFR 2022): since 2006 analyst SUE does not predict 60-day returns for all-but-microcap stocks, nor for
  microcaps since 2016.
- Subrahmanyam (UCLA Anderson Review, Jan 2026): t falls from 2.18 to 1.43 ex-microcaps. Counter-view: Hirshleifer-Peng-Wang (RFS 2025).
- methods.md 1a #16 places large-cap PEAD in the avoid bucket.

## Common mistakes
Holding liquid large caps for drift after a beat; using restated EPS or the fiscal-quarter-end date (look-ahead);
ignoring delisted names.

## Implementation spec for swing-engine
- Data: EDGAR XBRL companyfacts (fetcher exists in `data/float_data.py`; extend to us-gaap `EarningsPerShareDiluted`
  with `USD/shares`). Quarterly values: 10-Q facts with ~3-month duration; Q4 = FY value minus 9-month YTD. Point-in-time
  date = XBRL `filed` (10-Q/10-K filing date, often weeks after the 8-K Item 2.02 release; conservative). XBRL history
  starts ~2009-2011, so time-series SUE (12 quarters needed) is usable from ~2012.
- Feature `sue_ts` (above formula, min 6 of 8 quarters), `days_since_report`.
- Signal (monthly, first session): `sue_ts` in the top decile of the universe, `days_since_report <= 30`, price >= $5,
  and a **size split** (microcap / small / mid+) logged per trade.
- Entry next open; stop `entry - 3 * atr_14` (engine choice, source has none); exit at `max_hold_days = 60` or stop;
  `min_reward_risk = 0.0`.
- Missing: `earnings_dates_point_in_time` (Alpha Vantage `EARNINGS_CALENDAR` is forward-looking only), XBRL EPS
  ingest, monthly rebalance cadence. Analyst SUE needs paid consensus data.

## What the router should know
Context only: never a reason to hold a liquid name for drift. Replay only, with the small/mid split.

## Signs of decay to monitor
Top-decile 60-day excess return vs SPY <= 0 in the small-cap bucket over trailing 8 quarters.

## Sources
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://www.nber.org/papers/w13090

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 250 | 0 | 44% | -0.13 | -0.15 | 38% | -0.19 | -0.22 | 30% | -0.26 | -0.28 | 0.45 |
| correction | 20 | 0 | 55% | -0.04 | -0.06 | 75% | +0.18 | +0.16 | 75% | +0.36 | +0.34 | 3.77 |
| healthy_uptrend | 545 | 0 | 48% | +0.03 | +0.01 | 48% | -0.00 | -0.03 | 45% | +0.03 | +0.00 | 1.07 |
| high_vol_selloff | 79 | 0 | 49% | -0.08 | -0.09 | 53% | +0.12 | +0.10 | 51% | +0.13 | +0.11 | 1.28 |
| narrow_uptrend | 148 | 0 | 55% | +0.03 | +0.01 | 38% | -0.14 | -0.16 | 48% | -0.03 | -0.05 | 0.93 |
| **all** | 1042 | 0 | 48% | -0.02 | -0.04 | 45% | -0.05 | -0.08 | 43% | -0.04 | -0.06 | 0.91 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 679 | 0 | 51% | +0.03 | +0.00 | 43% | -0.09 | -0.12 | 40% | -0.15 | -0.17 | 0.65 |
| correction | 305 | 0 | 74% | +0.23 | +0.21 | 66% | +0.22 | +0.19 | 59% | +0.22 | +0.20 | 1.70 |
| healthy_uptrend | 1751 | 0 | 52% | +0.00 | -0.03 | 54% | +0.06 | +0.04 | 51% | +0.09 | +0.06 | 1.28 |
| high_vol_selloff | 638 | 0 | 52% | -0.05 | -0.07 | 48% | -0.11 | -0.13 | 50% | -0.06 | -0.08 | 0.84 |
| narrow_uptrend | 363 | 1 | 57% | +0.08 | +0.06 | 60% | +0.14 | +0.11 | 47% | -0.01 | -0.04 | 0.97 |
| **all** | 3736 | 1 | 54% | +0.02 | -0.00 | 53% | +0.02 | -0.00 | 49% | +0.02 | -0.00 | 1.06 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
