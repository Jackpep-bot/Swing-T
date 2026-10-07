---
slug: xs_momentum_rank
name: Cross-sectional momentum rank (12-1 and Jegadeesh-Titman 6-1)
originators: [Jegadeesh-Titman (JF 1993), Fama-French UMD, Daniel-Moskowitz (JFE 2016) WML definition]
category: strategy
decision: implement
holding_period_days: [21, 252]
timeframe: monthly rank on daily data (universe/ranking filter for swing setups)
direction: long (academic factor is long-short)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff, correction]   # crash risk is in the rebound after a decline
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: A
free_data_ok: true
status: not_built
---

# Cross-sectional momentum rank

## One-line summary
Rank every stock each month on its return from 12 months ago to 1 month ago (skip the latest month); winners keep
outperforming losers for 3-12 months. For swing trading this is a universe/ranking filter, not a trade trigger.

## Origin and lineage
- Jegadeesh & Titman (JF 1993): J-month formation / K-month holding portfolios, 1965-89, about 1%/month.
- Carhart (1997) / Fama-French UMD and Daniel-Moskowitz WML formalise the 12-1 (t-12..t-2) definition.
- Practitioner echo: IBD RS rating, Minervini RS, Qullamaggie top-2% scans all rank on past return.
- `docs/methods.md` 1a #2 (relative strength as universe filter, grade A) and 1b (fold 12-1 into it).

## Exact rules (as published)
| Item | 12-1 (E01) | JT 6-1 (E02) |
|---|---|---|
| Universe | Common stocks with a valid price and >= 8 of the past 11 monthly returns (DM filter) | JT: all stocks, equal weight |
| Signal | Cumulative return t-12..t-2 (skip t-1) | 6-month return (HXZ t-7..t-2; JT skipped 1 week) |
| Sort | Deciles on NYSE-only breakpoints | Deciles, all-stock breakpoints (JT) |
| Portfolio | Long top decile (short bottom), value-weighted | Long top, short bottom; 6 overlapping cohorts, 1/6 each |
| Hold / rebalance | 1 month, monthly | K = 6 months |
| Daily proxy | `adj_close[t-21] / adj_close[t-252] - 1` | `adj_close[t-21] / adj_close[t-147] - 1` |
Costs: buy/hold spread (enter top 10%, exit only below top 20-30%) cuts turnover (Novy-Marx-Velikov).

## Why it should work
- Behavioural: underreaction to firm news then delayed overreaction (Barberis-Shleifer-Vishny, Hong-Stein); the
  52-week-high anchor (George-Hwang 2004) explains much of it.
- Other side: disposition-effect sellers who take gains too early in winners, and investors anchored to old prices.
- Skip month: the most recent month shows short-term reversal (liquidity/microstructure), so it is excluded.

## When it works and when it fails
- Works: trending, risk-on markets; strongest month-1 holding horizon.
- Fails: momentum crashes in rebounds after bear markets and high volatility (Jul-Aug 1932 losers +232% vs winners
  +32%; Mar-May 2009 losers +163% vs winners +8%). In bear markets WML's up-market beta (-1.51) is about twice its
  down-market beta (-0.70) (DM 2016). Stalled in Q4 2025 (momentum +0.77% vs value +8.34%).

## Parameters and sensitivity
| Knob | Default | Range | Note |
|---|---|---|---|
| formation window | 252 bars, skip 21 | 126-252 / 5-21 | 6-1 weaker in VW tests |
| rank breakpoints | universe percentile | NYSE-only if market cap available | microcaps fill extremes otherwise |
| entry rank | >= 0.90 | 0.80-0.95 | |
| exit rank (hysteresis) | < 0.70 | 0.70-0.80 | buy/hold spread |
| min history | 168 valid of 231 bars | | DM's 8-of-11 months |
Traps: lookback/skip shopping; mixing 63-day RS (already used by breakout modules) with 12-1 and calling both
"momentum" double-counts.

## Evidence
- JT 1993 (1965-89): about 1%/month for 12-1 style winners-minus-losers; 6/6 about 0.95%/month (secondary summary).
- Hou-Xue-Zhang replication (VW, NYSE breakpoints, through 2014): R11 1-month hold 1.19%/mo (t = 4.06), 6-month
  0.81% (t = 3.14); R6 1-month 0.60% (t = 2.04), 6-month 0.82% (t = 3.49), 12-month 0.55% (t = 2.90). About 25-50%
  smaller than JT's original numbers.
- Daniel-Moskowitz 2016 (1927-2013): WML Sharpe 0.71; winners +15.3%/yr excess, losers -2.5%/yr; CAPM alpha
  22.3%/yr; crash episodes above.
- Frazzini-Israel-Moskowitz live trading costs: implementable after costs at institutional size.
- Jensen-Kelly-Pedersen 2023: momentum replicates globally. 17/18 international markets (methods.md).
- Decay: McLean-Pontiff average anomaly -58% after publication; momentum survives but weaker and crash-prone.
  Alpha Architect "30 years of out-of-sample data" summarises post-1993 performance (not re-fetched here).

## Common mistakes
1. Including the latest month (reversal contamination).
2. Survivorship: dropping delisted losers inflates the long-short (CLAUDE.md: delisted symbols stay in).
3. Using unadjusted closes across splits/dividends.
4. Rebalancing daily: turnover kills it.
5. Running it unhedged into a post-crash rebound.

## Discretionary parts and how to make them mechanical
Fully mechanical. Only judgement: whether to apply the crash filter (see catalog `momentum_crash_filter_dm`,
`volatility_scaling_book`) - make that a versioned param.

## Implementation spec for swing-engine
- Existing: `mom_12_1 = close.shift(21) / close.shift(252) - 1` per symbol (`features/cross_section.py`); `ret_126d`,
  `ret_252d`; `rs_63d_rank` (same-session percentile of 63-bar return, `features/patterns2.py`, re-ranked inside the
  universe by `research/replay.py`).
- Note: the panel computes on `close`, not `adj_close`; verify the provider's close is split-adjusted, and note that
  dividends are excluded (price momentum, not total return).
- New features: `mom_12_1_rank` = same-session percentile of `mom_12_1` among universe members (same code path as
  `_rerank_rs`); `mom_6_1 = close.shift(21)/close.shift(147) - 1` and its rank; `mom_valid_bars_231` count for the
  DM filter.
- Use 1 (filter): param on breakout/pullback strategies `min_mom_rank` (e.g. 0.80); compare vs `rs_63d_rank`.
- Use 2 (replay): monthly top-decile long book, month-end rebalance, hold 21 sessions, hysteresis exit < 0.70, equal
  weight within the engine's 8-position cap or as a research-only portfolio in `research/`.
- Ranker: `mom_12_1` is already in `RANKER_FEATURES`; add the rank versions and `mom_6_1`.
- Missing: market cap for NYSE breakpoints / VW (shares outstanding exists in `data/float_data.py`), month-end
  rebalance driver, crash filter.
max_hold_days: 21 per cohort (rolled monthly). Min reward:risk: n/a.

## What the router should know
- Lowest-turnover, best-evidenced signal in the catalog; use it to rank candidates in every long regime.
- In `high_vol_selloff` and the first months after a `correction` ends, cut weight on raw momentum (crash risk);
  prefer `residual_momentum` there.

## Signs of decay to monitor
- Rolling 12-month spread between top and bottom decile of `mom_12_1_rank` in the engine universe turning negative.
- Information coefficient (rank of `mom_12_1` vs next-21-day return) below 0 for 6+ months.
- Factor crowding: winners' realised vol rising sharply relative to the market.

## Sources
- https://www.nber.org/system/files/working_papers/w20439/w20439.pdf
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://www.nber.org/system/files/working_papers/w7159/w7159.pdf
- https://www.nber.org/papers/w28432
- https://www.nber.org/papers/w20721
- https://alphaarchitect.com/momentum-factor-investing-30-years-of-out-of-sample-data/
- https://money.tmx.com/content-hub/value-momentum-content-hub/why-value-outpaced-momentum-2025-top-factor/
- Repo: `docs/methods.md` 1a #2, 1b; `swing_engine/features/cross_section.py`; `swing_engine/features/patterns2.py`

## Empirical (replay)
_Pending: filled in from swing replay on real data._
