---
slug: large_cap_residual_momentum
name: Large-cap residual momentum, monthly portfolio with a buy/hold band (Blitz-Huij-Martens 2011)
originators: [Blitz, Huij & Martens, "Residual Momentum", Journal of Empirical Finance 18(3) 2011]
category: strategy
decision: implement
holding_period_days: [21, 252]
timeframe: monthly rebalance; daily bars + Fama-French daily factors (store table ff_factors)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [v_shaped_rebound, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 3, 2026-10-10; portfolio variant of catalog residual_momentum)
---

# Large-cap residual momentum

## Why this one is different from what was tested
The engine's `residual_momentum` was replayed only as leaderboard signals: top decile of the broad top-1,500
universe, 2 x ATR stop, graded at 5/10/20 sessions. Its 2024-26 row is suspicious: 108 signals, all in one regime,
0% win and exactly -0.74R gross at every horizon, which looks like one batch stopped out together or a scoring fault,
not a test of the idea. Worth a look on the Mac before reading anything into it. This card is the published design:
a monthly portfolio of the 500 largest stocks, held while still ranked high, with no tight stop, graded on alpha vs SPY.

## One-line summary
Each month, among the 500 largest stocks, buy the tenth with the strongest past-year return after removing market,
size and value exposure (scaled by residual volatility); hold while in the top fifth.

## Origin and lineage
- Blitz, Huij & Martens 2011 (working paper https://repub.eur.nl/pub/22252). Blitz, Hanauer & Vidojevic, IREF 69
  (2020) "The idiosyncratic momentum anomaly". Gutierrez & Pirinsky, JFM 2007.
- Cost banding: Novy-Marx & Velikov 2016, https://www.nber.org/papers/w20721.pdf
- Engine: reuse `features.extra` `ff3_resid_mom_756_231` (FF3 on daily excess returns over 756 bars, residuals over
  t-252..t-21, factor publication lag handled) and its same-session rank.

## Exact rules (as published)
1. Regress each stock's last 36 monthly excess returns on Mkt-RF, SMB, HML (all 36 required).
2. Score = sum of residuals over t-12..t-2 / their standard deviation over the same window.
3. Deciles, equal weight, monthly rebalance; long top minus bottom (engine: long side only).

## Engine version (pre-register this one)
- Rebalance: last NYSE session of each month (`month_end` = 1); fills next open.
- Universe: 500 largest by market cap (close x `shares_outstanding_asof`), price >= $10, at least 756 bars.
- Score: `ff3_resid_mom_756_231` (daily-factor proxy of BHM; registered deviation from monthly regressions). If the
  French table is missing for a session, skip that rebalance (do not fall back to the CAPM proxy mid-test).
- Buy zone: top 10% of score in the universe. Hold zone: top 20%. Sell when a name leaves the hold zone or the universe.
  Equal weight, max 50 names.
- Catastrophe stop 3 x `atr_63`; `engine_trail = False`, `min_reward_risk = 0`, no target, no regime gate.
- Costs: per-stock model on traded notional.

## Grading
Batch standard (prereg_eval, net, own holding period) plus alpha vs SPY from daily net returns, haircut over the
batch-3 group size. Pass = standard rule AND positive haircut alpha in both windows. Also report turnover per year.

## Evidence
- BHM, US 1926-2009, long-short, gross, 1-month hold: residual 11.2%/yr, vol 12.5%, Sharpe 0.90, FF3 alpha 10.8%,
  vs total momentum 10.3%, 22.7%, 0.45, 8.0%. 2000-09: residual +4.7%/yr vs total -8.5%. (Via CXO summary
  https://www.cxoadvisory.com/momentum-investing/stripping-risks-from-a-stock-momentum-strategy/)
- Largest market-cap decile: Sharpe 0.60 residual vs 0.36 total (BHM robustness, also Quantpedia screener 136).
- BHV 2020 (US through 2015): idiosyncratic 1.39%/month, Sharpe 0.48 vs conventional 1.54%, 0.25; not explained by
  conventional momentum or newer factors; size split not seen (paper paywalled).
- Costs (Novy-Marx-Velikov, momentum, 1963-2012): basic 34.5% turnover/month, net 0.68%/month; with a 10%/20%
  buy/hold band 18.8% turnover, net 0.85%/month, but net FF4 alpha falls to 0.13% (t about 1.5).
- Against: out of sample 2009-2015 both residual and conventional momentum were "unattractive in the US" (CXO,
  https://www.cxoadvisory.com/momentum-investing/robustness-of-pure-stock-momentum-and-reversal/). Long-only
  large-cap momentum (MSCI USA Momentum, net of fees not costs) beat MSCI USA by about 1 point a year over 10 years and
  0.1 over 5 years, with swings of -17.5 (2023) to +16.1 (2017) points.
- Grade C: strong long-short history including large caps, but long-only, net and post-2009 evidence is weak.

## Expectation stated before the run
Near-zero alpha vs SPY in both windows is the most likely result. It earns its trial because it is the only momentum
form with large-cap evidence that removes the market exposure, and the leaderboard never tested it this way.

## Common mistakes
Ranking on raw return; letting the beta-regression window overlap the factor publication lag; monthly full rebalance
with no band (doubles turnover).

## Signs of decay to monitor
Trailing 3-year alpha vs SPY <= 0.
