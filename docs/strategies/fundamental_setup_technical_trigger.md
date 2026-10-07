---
slug: fundamental_setup_technical_trigger
name: "Fundamental setup + technical trigger (TradeStation Fundamntl & Chan/MACD/RSI/Stoch/Volty)"
originators: ["TradeStation built-in demonstration strategies"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [10, 40]
timeframe: daily (fundamentals quarterly)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Fundamental setup + technical trigger

## One-line summary
Only take a technical long trigger (channel breakout, MACD cross, RSI cross, stochastic cross or volatility expansion)
in stocks whose chosen fundamental field is improving (positive momentum or acceleration).

## Origin and lineage
TradeStation EasyLanguage demo strategies "Fundamntl & Chan / MACD / RSI / Stoch / Volty" LE/LX (catalog B85). They
are platform templates, not a published trader's method. The concept parallels CANSLIM's "fundamentals first,
chart for timing" (docs/methods/07). Holding period "weeks" is the catalog's estimate.

## Exact rules (per catalog summary of TradeStation help; details partly unverified)
- **Setup** (`FundSetup` function): a selected fundamental field (e.g. EPS, revenue) must show momentum (latest value
  > prior value) or, with input 1, acceleration (latest change > prior change). Exact FundSetup arithmetic was not
  verified against the EasyLanguage source.
- **Triggers (one per strategy variant)**:
  - Chan LE: buy on break of the 6-bar highest high; LX on 6-bar lowest low.
  - MACD LE: MACD(12,26,9) difference crosses above 0.
  - RSI LE: RSI(14) crosses above 30; LX when it crosses below 70.
  - Stoch LE: %K crosses above %D while oversold (< 20); LX on cross down while > 80.
  - Volty LE: upside volatility expansion using ATR(5) x 1.5 (TradeStation places a stop order above the close; the
    exact reference price is unverified).
- Stops/targets: none beyond the LX signals; sizing not specified.

## Why it should work
Post-earnings-announcement drift and earnings momentum are documented anomalies: improving fundamentals are
under-reacted to. A technical trigger times entry. The other side is investors anchored on stale estimates.

## When it works and when it fails
Works in uptrends where earnings revisions drive leadership. Fails in macro-driven sell-offs (fundamentals ignored),
and when fundamentals are used with look-ahead (fiscal period end instead of filing date) - the main backtest trap.

## Parameters and sensitivity
Field choice (EPS diluted, revenue, operating cash flow), momentum vs acceleration, trigger choice, trigger lengths.
Five triggers x many fields x two setup modes = a large search space; with grade "none" evidence this is a
multiple-testing trap. Pre-register: EPS diluted, momentum (yoy, same quarter), Chan 6-bar trigger.

## Evidence
TradeStation publishes no performance. Academic support exists for the fundamental component in general
(post-earnings drift, Bernard and Thomas 1989; earnings momentum), not for these templates. Grade none.

## Common mistakes
Using quarter-end dates instead of filing timestamps; mixing restated values; comparing sequential quarters for
seasonal businesses (use year-over-year).

## Discretionary parts and how to make them mechanical
None in the templates; the choices are the field and trigger, fixed as parameters.

## Implementation spec for swing-engine
- Fundamentals: EDGAR XBRL companyfacts. A client already exists in `swing_engine/data/float_data.py`
  (`companyfacts(cik)`, shared SEC token bucket). Missing: a point-in-time fundamentals table keyed by the `filed`
  date (CLAUDE.md rule 3), e.g. `EarningsPerShareDiluted` 10-Q/10-K values.
- Feature `fund_mom` = value of latest filed quarter - value of same quarter one year earlier, available from the
  session after `filed`; `fund_acc` = fund_mom(latest) - fund_mom(previous filing). Setup = `fund_mom > 0`
  (or `fund_acc > 0`).
- Triggers from existing features: `macd_hist` crossing above 0 (`macd_hist[t] > 0 >= macd_hist[t-1]`);
  `rsi_14` crossing above 30; Chan: `close[t] > max(high[t-6..t-1])` (approximation of the intraday break).
  Missing: stochastic %K/%D (14,3) and ATR(5).
- Entry: next open. Stop: `min(low[t-6..t-1])` (Chan LX level) or `entry - 2*atr_14`, whichever is tighter
  but at least 1*atr_14 below entry (engine choice). Target: none; `min_reward_risk` 0; exit on LX rule via
  `should_exit`, `max_hold_days` 40.

## What the router should know
Hybrid fundamental/technical; correlates with breakout families (Chan trigger) when fundamentals are good. Only in
healthy_uptrend until replay shows otherwise.

## Signs of decay to monitor
Spread between setup-on and setup-off trigger outcomes shrinking to zero (fundamental filter adds nothing).

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/fundamntl___chan_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/fundamntl___macd_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/fundamntl___rsi_le_signal_.htm
- Bernard, V. and Thomas, J. (1989), "Post-Earnings-Announcement Drift", Journal of Accounting Research (general
  context only)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
