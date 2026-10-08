---
slug: intermarket_divergence_katsanos
name: "Intermarket divergence (BBDivergence, RegressionDivergence; Markos Katsanos)"
originators: ["Markos Katsanos (S&C Dec 2015 'Trading the Loonie'; S&C Jul 2017)", "thinkorswim BBDivergenceStrat / RegressionDivergenceStrat"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 15]
timeframe: daily
direction: long (originals also short; engine long-only)
regimes_good: [healthy_uptrend, choppy]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Intermarket divergence (Katsanos)

## One-line summary
When a stock that normally tracks a related market (its sector ETF) temporarily lags it, buy the laggard as the
divergence starts to close; exit on reconvergence, momentum exhaustion or a time stop.

## Origin and lineage
Markos Katsanos, *Intermarket Trading Strategies* (2008) and S&C articles: "Trading the Loonie" (Dec 2015, CAD vs
crude oil, BBDivergence) and a Jul 2017 article behind RegressionDivergence (catalog B47; title not verified).
Coded by thinkorswim. The original tests were on currencies/futures pairs, not stocks vs sector ETFs; the engine
adaptation (stock vs sector ETF) is ours.

## Exact rules (thinkorswim)
**BBDivergence study**: relative position inside Bollinger Bands (length default 20) is computed for primary and
secondary; divergence = their percentage difference; levels +20 / -20. The exact normalisation (which symbol is the
denominator, any offset) was **not verified** (S&C article and Traders' Tips pages inaccessible).

**BBDivergenceStrat**
- Buy: 3-day maximum divergence > 20 but divergence now falling; primary close and secondary close average both up
  over the last 2 days; correlation(primary, secondary) > -0.4.
- Sell to close (any): MACD crosses below its 9-day EMA while stochastic > 85; 3-day minimum divergence < -20 and
  ROC < -3; primary closes at a 15-day low while correlation < -0.4.
- Short side mirrors (not used). Correlation / ROC / stochastic lengths: unverified.

**RegressionDivergenceStrat**
- Buy: regression divergence (primary vs secondary) rises above 75 then reverses within 3 bars, while correlation of
  rates of change between primary and a third symbol is below 0.8.
- Exit: after a maximum number of bars (catalog: 11).

## Why it should work
Correlated assets share drivers; a temporary gap is often noise or slow information diffusion (lead-lag effects across
related firms are documented, e.g. Cohen and Frazzini 2008 on customer-supplier links). The other side is liquidity
demand in the laggard.

## When it works and when it fails
Works when the relationship is stable and the gap is non-news. Fails when the laggard lags for a reason (earnings,
downgrade): the "divergence" is a regime change. Correlations collapse in high-vol sell-offs.

## Parameters and sensitivity
BB length 20, divergence level 20, correlation floor -0.4 (very permissive), RD level 75, reversal window 3, max bars 11.
Trap: choosing the pair per stock in-sample. Fix pairing by rule (GICS sector -> SPDR sector ETF).

## Evidence
Only Katsanos's in-sample article results (not reviewed); no broker performance. Grade D. Pair-trading literature
(Gatev, Goetzmann and Rouwenhorst 2006) supports convergence of matched pairs but is a different, market-neutral setup.

## Common mistakes
Trading divergences around the laggard's own earnings; using a pair with low long-run correlation; ignoring that the
leader may converge down instead.

## Discretionary parts and how to make them mechanical
Pair choice -> fixed sector ETF map; require 120-day correlation of daily returns >= 0.5 for the pair to be eligible
(engine addition).

## Implementation spec for swing-engine
- Features (new, per symbol with its sector ETF bars aligned by session):
  `pb_p = (close - bb_lower_20) / (bb_upper_20 - bb_lower_20)` (existing BB columns), same for the ETF `pb_s`;
  `bb_div = 100 * (pb_s - pb_p)` (assumed form: positive when the stock lags the ETF; verify against the article);
  `corr_20 = corr(close_p, close_s, 20)`.
- Buy at as-of t: `max(bb_div[t-2..t]) > 20` and `bb_div[t] < bb_div[t-1]`; `close_p[t] > close_p[t-2]` and
  `sma(close_s,3)[t] > sma(close_s,3)[t-2]` (2-day up approximation); `corr_20[t] > -0.4`.
- Entry next open. Stop `entry - 2*atr_14` (engine choice; original has no price stop). Target: none;
  `min_reward_risk` 0. Rule exits via `should_exit`: `min(bb_div[t-2..t]) < -20`; close = 15-day low while
  `corr_20 < -0.4` (thinkorswim's clause; engine column `corr_market_20`); or
  MACD crosses below signal while stochastic > 85 (needs stochastic). `max_hold_days` 15.
- Reuses `bb_upper_20`, `bb_lower_20`, `macd`, `macd_signal`, `atr_14`. Missing: symbol -> sector ETF map, ETF bars
  in the panel per row, rolling cross-symbol correlation, stochastic, earnings-date blackout.

## What the router should know
Mean-reversion / relative-value flavour; low overlap with breakout families. Allowed in healthy_uptrend and choppy at
reduced size; off in correction and high_vol_selloff.

## Signs of decay to monitor
Average divergence half-life lengthening; share of signals followed by the ETF falling to the stock rising.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/BBDivergenceStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RegressionDivergenceStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/A-B/BBDivergence
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/RegressionDivergence

## Empirical (replay)
_Pending: filled in from swing replay on real data._
