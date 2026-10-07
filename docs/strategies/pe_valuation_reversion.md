---
slug: pe_valuation_reversion
name: P/E undervalued / overvalued vs its own average (TradeStation)
originators: [TradeStation built-in strategies (P/E UndVal LE / OverVal SE)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 60]
timeframe: daily
direction: both
regimes_good: [choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# P/E vs its own moving average

## One-line summary
Buy when a stock's P/E (close / trailing-12-month EPS) falls 10% below its 12-bar average; exit when it crosses back
above. Mirror for shorts.

## Origin and lineage
TradeStation demonstration strategies. Help pages (fetched 2026-10-07): inputs `EarningsField` (default "SDBF"),
`AvgLength` 12 (bars), `PctBelow` 10; P/E uses current close and TTM EPS. Exit and short rules are on the LX/SE/SX pages.

## Exact rules
- P/E_t = close_t / TTM EPS (latest four quarters).
- Long entry: P/E_t < (1 - 0.10) * SMA(P/E, 12 bars).
- Long exit: P/E crosses back above its average, or EPS <= 0.
- Short entry: P/E > 1.10 * average; cover on a cross below. No stop, no target, sizing unspecified.

## Why it should work
Between earnings reports EPS is constant, so on daily bars P/E is just price scaled by a constant: the rule is a
**12-day price mean-reversion rule** (price 10% below its 12-day mean), with a jump whenever EPS updates. Any edge is
short-term reversal, not valuation.

## When it works and when it fails
Behaves like a deep-oversold reversion trigger: fine in ranges, catches falling knives in downtrends. EPS updates
create artificial signals (a big EPS jump drops P/E sharply with no price change).

## Parameters and sensitivity
AvgLength (bars), PctBelow, bar size (on weekly/monthly bars it becomes closer to a valuation signal).

## Evidence
None published by the broker (catalog B86). Academic valuation reversion (value factor, e.g. E/P) works at multi-month
horizons cross-sectionally, not via a 12-day own-history average; no test of this exact rule located.

## Common mistakes
Thinking it is a valuation strategy; using EPS before its filing date; ignoring negative EPS.

## Implementation spec for swing-engine
- Data: TTM EPS from EDGAR companyfacts (`EarningsPerShareDiluted`, quarterly with Q4 = FY - 9M), point-in-time on `filed`.
- Features: `ttm_eps`, `pe = close / ttm_eps` (NaN when ttm_eps <= 0), `pe_sma_12`, `pe_dev = pe / pe_sma_12 - 1`,
  `eps_changed_12` (1 if ttm_eps changed in the last 12 bars; replay both with and without excluding these).
- Signal: `pe_dev < -0.10`, `ttm_eps > 0`. Entry next open. Stop `entry - 2.5 * atr_14` (engine choice).
  Exit: `pe_dev >= 0` or `ttm_eps <= 0`; `max_hold_days = 30`. `min_reward_risk = 0.0` (rule exit).
- Short side: not supported (`PanelStrategy.build_signal` is long-only); replay long side only.
- Missing: XBRL EPS ingest. Compare against a pure price rule (`close < 0.90 * sma_12`) to show the equivalence.

## What the router should know
Treat as mean reversion (choppy only, small). Not a value signal.

## Signs of decay to monitor
Not applicable beyond the generic: net expectancy <= 0 over 50 replay trades.

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_undval_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_undval_lx_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_overval_se_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/p_e_overval_sx_signal_.htm

## Empirical (replay)
_Pending: filled in from swing replay on real data._
