---
slug: large_cap_net_repurchasers
name: Large-cap net repurchasers, buy big stocks whose split-adjusted share count shrank most (Pontiff-Woodgate; Fama-French 2008)
originators: [Pontiff & Woodgate, "Share Issuance and Cross-sectional Returns", JF 63(2) 2008, Fama & French, "Dissecting Anomalies", JF 63(4) 2008]
category: strategy
decision: implement
holding_period_days: [21, 252]
timeframe: monthly rebalance; daily bars + EDGAR XBRL share counts + splits table
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: draft_card (research thread batch 2, 2026-10-10; not in catalog yet)
---

# Large-cap net repurchasers

## Why this one is different from what failed
Every stock strategy so far traded the replay's broad universe (top 1,500 by dollar volume) and lost in 2024-26, when
small and mid caps lagged the largest names. This one is restricted to the 500 largest stocks and selects on a slow
corporate action (buybacks), not price patterns, momentum or earnings news. Fama-French (2008) is the one major study
that finds the effect in big stocks and on the long (repurchase) side alone.

## One-line summary
Each month, among the 500 largest US stocks, buy the tenth whose split-adjusted share count fell most over the year
ending six months ago; hold until they leave the bottom fifth. Low turnover, liquid names, no shorting.

## Origin and lineage
- Pontiff & Woodgate, JF 63(2) 2008 (abstract: strong predictor after 1970). Peer-reviewed. Paper tables not opened.
- Fama & French, "Dissecting Anomalies", JF 63(4) 2008. Peer-reviewed. Read:
  https://www.johnhcochrane.com/s/fama_french_dissecting_anomalies_JF.pdf
- Chen-Zimmermann `ShareIss1Y` (CZ code: (S[t-6] - S[t-18]) / S[t-18], split-adjusted shares). Gate-2 CZ check
  signal: `ShareIss1Y`.
- Engine relatives: `quality_minus_junk` (payout is one of its parts, not a standalone strategy); the failed
  `composite_cost_aware_rank` did not use issuance.

## Exact rules (as published)
1. CZ / PW: share issuance = growth in split-adjusted shares outstanding from month t-18 to month t-6.
2. FF 2008: NS = ln(split-adjusted shares at fiscal year-end t-1 / at t-2), portfolios formed each June.
3. Long the strongest repurchasers (lowest NS), short the biggest issuers; the engine trades only the long side.

## Engine version (pre-register this one)
- Rebalance: last NYSE session of each month (`month_end` = 1); fills next open.
- Universe: the 500 largest names by market cap (close x latest XBRL share count filed on or before the bar) among
  the replay universe; price >= $10; at least 504 bars of history.
- Shares S(d) = latest EDGAR XBRL share count (`data.fundamentals.shares_outstanding_asof`) filed on or before date d,
  multiplied by the cumulative split factor from the store's splits table between that filing's date and d (XBRL
  counts are not split-adjusted; this must be done or every split looks like a 2x issuance).
- Signal: NS = ln(S(t - 126 sessions) / S(t - 378 sessions)). Require both share counts and no single-period change
  above +100% or below -50% (data-error guard; log how many names it drops).
- Buy zone: bottom 10% of NS in the universe (largest net reduction). Hold zone: bottom 20%. Sell a held name only
  when it leaves the hold zone or the universe. Equal weight, max 50 names.
- No stop for the rule; catastrophe stop 3 x `atr_63` (engine needs a stop to size; same as the earlier monthly picks).
  `engine_trail = False`, `min_reward_risk = 0`, no target, no regime gate.
- Costs: per-stock model on traded notional.

## Grading
The batch's standard portfolio grading (prereg_eval, net of per-stock costs, own holding period) plus, because this is
a long-only large-cap book, alpha vs SPY from daily returns. Pass on the standard rule; report the SPY alpha beside it
so beta in a bull window is not read as skill.

## Evidence
- FF 2008 (July 1963-Dec 2005, value-weighted, Table II): among big stocks, the biggest repurchasers earn +0.26% a
  month abnormal (t=3.44); highest issuers -0.27% (t=-3.36); hedge 0.54%. Fama-MacBeth NS slope among big stocks
  -1.71 (t=-5.28, Table IV). Repurchase returns are pervasive across size groups.
- Novy-Marx & Velikov 2016 (value-weighted, 1973-2012, monthly rebalance, Table 3B): net issuance gross 0.57%/month,
  turnover 14.36%/month, costs 0.20%, net 0.37%/month (t=2.43). Survives costs.
- Daniel-Titman composite issuance (2014 follow-up): slope -0.527 (t=-4.8) over 1968-2014, but -0.300 (t=-2.2) or
  -0.139 (t=-0.8) in 2004-2014 depending on specification: weaker recently.
- Practitioner index (Nasdaq US BuyBack Achievers, >= 5% share reduction in 12 months): 11.2% a year vs 10.7% for the
  S&P 500 total return, Dec 2006-Sep 2025 (Nasdaq research note, originator of the index): a small edge.
- International (McLean-Pontiff-Watanabe 2009, 41 countries): issuance predicts in small and large firms, but there
  the issuers' underperformance drives it, not repurchasers.
- Grade B: peer-reviewed, cost-robust, large-cap long side documented; recent-decade evidence weak.

## Why it might beat costs where the others failed
Mid-turnover class that survives costs in Novy-Marx-Velikov, applied only to the most liquid 500 stocks with a buy/hold
band, so the per-stock cost is at the engine's floor. And it is long the kind of company (large, cash-generating,
shrinking share count) that the 2024-26 tape rewarded, not punished.

## Common mistakes
Using unadjusted XBRL share counts across a split; using `WeightedAverageNumberOfSharesOutstanding` (lags by a
quarter and blends periods) instead of the cover-page count; a 0-month lag (CZ skip six months); letting
microcaps in.

## Signs of decay to monitor
Trailing 3-year alpha vs SPY <= 0.

## Sources
- https://www.johnhcochrane.com/s/fama_french_dissecting_anomalies_JF.pdf
- https://www.nber.org/papers/w20721.pdf
- https://business.columbia.edu/sites/default/files-efs/pubfiles/11569/dt7.6.pdf
- https://indexes.nasdaqomx.com/docs/DRB%20Research%20-%202025.pdf
- https://ideas.repec.org/a/eee/jfinec/v94y2009i1p1-17.html
- https://raw.githubusercontent.com/OpenSourceAP/CrossSection/master/SignalDoc.csv

## Empirical (replay)
Pre-registered batch 2 group (docs/preregistration/2026-10-10-batch2.md), n_trials = 3. **PASS on its absolute rule, but alpha against SPY is zero (t 0.00 in 2024-26, 0.44 in 2017-24): the return is market exposure, not a stock-picking edge**. Full tables: docs/preregistration/2026-10-10-batch2-results.md.

| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| large_cap_net_repurchasers | 2024 | 236 | +0.449 | 2.10 | 0.72 | 0.07 | 0.56 | 18.2% | 85 | 161% | +19.2% |
| large_cap_net_repurchasers | 2017 | 574 | +0.988 | 4.71 | 0.71 | 0.52 | 0.87 | 26.6% | 128 | 101% | +123.0% |

Against buy-and-hold SPY:

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| large_cap_net_repurchasers | 2024 | -7.3% | -0.61 | -0.61 | +0.0% | 0.00 | 0.57 | 83% | 0.72 | 1.03 |
| large_cap_net_repurchasers | 2017 | -2.0% | -0.19 | -0.19 | +1.5% | 0.44 | 0.74 | 78% | 0.71 | 0.75 |
