---
slug: residual_momentum
name: Residual (idiosyncratic) momentum
originators: [Blitz-Huij-Martens (J. Empirical Finance 2011)]
category: strategy
decision: implement
holding_period_days: [21, 126]
timeframe: monthly rank (daily proxy possible)
direction: long (academic factor is long-short)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Residual momentum

## One-line summary
Rank stocks on their past-year return after stripping out market, size and value exposure (Fama-French 3-factor
residuals), scaled by residual volatility; it earns about the raw-momentum return with roughly half the volatility
and avoids buying pure beta or sector bets.

## Origin and lineage
- Blitz, Huij & Martens, "Residual Momentum", Journal of Empirical Finance 18(3), 2011, pp. 506-521.
- Builds on Grundy-Martin (2001): raw momentum carries time-varying factor exposure that causes crashes.
- Engine role (catalog): prefer the residual rank over raw 12-1 after rebounds; candidate ranker feature.

## Exact rules (as published)
1. Each month-end t, for each stock regress monthly excess returns on the FF3 factors (Mkt-RF, SMB, HML) over months
   t-36..t-1; all 36 months required.
2. Residuals e = actual excess return minus fitted (intercept treatment: BHM use the regression residuals).
3. Score = sum of e over t-12..t-2 divided by the standard deviation of e over the same window (skip month t-1).
4. Sort into deciles; long top decile (short bottom); hold 1 month (HXZ also test 6- and 12-month holds and a 6-month
   formation t-7..t-2).

## Why it should work
- Raw momentum in a rebound is long low-beta / short high-beta, so it crashes when beta rallies; removing factor
  exposure leaves the firm-specific underreaction component.
- Other side: the same underreacting investors as raw momentum, without the factor-timing bet.

## When it works and when it fails
- More consistent over time; in 2000-2009 raw momentum returned -8.5% while residual returned +4.7% (CXO summary of
  BHM, annualised gross).
- Fails if factor loadings shift abruptly (the 36-month beta is stale), and it still loses in sharp junk rallies,
  though less. Weak at the 6-month-formation / 1-month-hold combination.

## Parameters and sensitivity
| Knob | Published | Range |
|---|---|---|
| regression window | 36 months, all required | 24-60 |
| factor set | FF3 | CAPM (simpler), FF5 |
| formation | t-12..t-2 | t-7..t-2 (weaker) |
| scaling | divide by residual std | raw sum (worse risk-adjusted) |
| hold | 1 month | 1-12 |
Traps: factor model choice is a hidden knob; residuals from a sector-ETF regression are a different signal.

## Evidence
- BHM (US, 1926-2009, 1-month hold, gross, per CXO Advisory summary): residual momentum 11.2%/yr return, 12.5% vol,
  Sharpe 0.90, FF3 alpha 10.8%; total-return momentum 10.3%, 22.7% vol, Sharpe 0.45, alpha 8.0%. Large-cap subset
  Sharpe 0.60 vs 0.36. 12-month hold: 3.9% vs 0.16%. Authors' abstract: risk-adjusted profits about twice raw
  momentum, less concentrated in the extremes.
- HXZ (VW, NYSE breakpoints, through 2014): 11-month residual momentum 1-month hold 0.67%/mo (t = 3.91), 6-month
  0.55% (t = 3.94), 12-month 0.36% (t = 2.96); 6-month formation with 6/12-month holds 0.49% (t = 3.86) and 0.39%
  (t = 3.92); 6-month formation 1-month hold 0.20% (insignificant). t-stats exceed raw momentum's in the same tests.
- Out-of-sample: Blitz and co-authors later report the result is robust across global universes (search summary;
  not fetched). Costs: all figures gross; monthly rebalancing turnover not reported in the sources read.

## Common mistakes
1. Using total returns instead of excess returns (subtract the risk-free rate from the French library).
2. Look-ahead in factor data (French factors are published with a lag and occasionally revised).
3. Too-short history: needs 36 + 12 months per stock; Massive Basic gives only 2 years.
4. Forgetting volatility scaling (the main source of the Sharpe gain).

## Discretionary parts and how to make them mechanical
Fully mechanical. Choice of factor model and window must be fixed and versioned.

## Implementation spec for swing-engine
- Data: monthly FF3 + RF from the Ken French Data Library (free CSV); ingest into the store with a
  `published_on` date for point-in-time use (use factors only for months ending before `as_of` minus one month to be
  safe). Stock monthly returns from month-end `adj_close`.
- Feature `resid_mom_12_1` per symbol at each month-end m:
  `beta = OLS(r_i - rf ~ 1 + mktrf + smb + hml)` over months m-36..m-1;
  `e_k = (r_ik - rf_k) - beta . x_k` for k in m-12..m-2;
  `resid_mom_12_1 = sum(e_k) / std(e_k)`; NaN if fewer than 36 valid months.
  Broadcast to every daily row until the next month-end. Rank: same-session percentile within the universe.
- Daily proxy (if FF data unavailable): regress daily returns on SPY over 756 bars, sum residuals over bars t-252..t-21,
  divide by their std. Treat as a separate, versioned variant.
- Uses: (a) ranker feature in `research/ranker.py` `RANKER_FEATURES`; (b) universe filter `min_resid_mom_rank`;
  (c) monthly top-decile replay book as for `xs_momentum_rank`.
- Missing: French-factor ingest, month-end feature builder, 48+ months of bars (`data.history_years: 5` is enough
  only with a paid/alternative history source).
max_hold_days: 21 per monthly cohort. Min reward:risk: n/a.

## What the router should know
- Preferred momentum rank in `high_vol_selloff` exits and the first months after a `correction` (when raw momentum
  crash risk peaks).
- Correlated with `xs_momentum_rank`; do not stack both as independent score terms.

## Signs of decay to monitor
- Rolling 24-month top-minus-bottom decile spread in the engine universe <= 0.
- IC vs next-21-day returns no better than raw `mom_12_1` for 12 months (the volatility advantage is the point).

## Sources
- https://repub.eur.nl/pub/22252
- https://www.cxoadvisory.com/momentum-investing/stripping-risks-from-a-stock-momentum-strategy/
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- Repo: `docs/catalog/catalog.json` (E04), `swing_engine/research/ranker.py`

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| narrow_uptrend | 108 | 0 | 0% | -0.74 | -0.81 | 0% | -0.74 | -0.81 | 0% | -0.74 | -0.81 | 0.00 |
| **all** | 108 | 0 | 0% | -0.74 | -0.81 | 0% | -0.74 | -0.81 | 0% | -0.74 | -0.81 | 0.00 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1699 | 6 | 49% | +0.00 | -0.10 | 48% | +0.02 | -0.09 | 41% | +0.02 | -0.08 | 1.04 |
| correction | 1061 | 3 | 67% | +0.28 | +0.16 | 62% | +0.38 | +0.26 | 59% | +0.50 | +0.38 | 2.30 |
| healthy_uptrend | 3787 | 17 | 51% | +0.07 | -0.04 | 48% | +0.13 | +0.03 | 41% | +0.10 | -0.01 | 1.19 |
| high_vol_selloff | 1458 | 9 | 44% | -0.12 | -0.23 | 43% | -0.15 | -0.26 | 42% | -0.02 | -0.13 | 0.96 |
| narrow_uptrend | 1055 | 3 | 54% | +0.10 | -0.00 | 59% | +0.34 | +0.23 | 43% | +0.09 | -0.01 | 1.17 |
| **all** | 9060 | 38 | 52% | +0.05 | -0.05 | 50% | +0.12 | +0.01 | 44% | +0.11 | +0.00 | 1.22 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
