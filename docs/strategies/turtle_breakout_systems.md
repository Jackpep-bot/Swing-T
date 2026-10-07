---
slug: turtle_breakout_systems
name: Turtle System 1 (20/10 with skip rule) and System 2 (55/20)
originators: [Richard Dennis, William Eckhardt, Curtis Faith]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 120]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Turtle breakout systems

## One-line summary
Donchian breakouts with volatility (N) sizing and pyramiding: System 1 buys 20-day highs and exits on 10-day lows,
skipping a signal if the previous one would have won; System 2 buys 55-day highs and exits on 20-day lows.

## Origin and lineage
Richard Dennis and William Eckhardt's 1983-84 "Turtle" experiment in futures. Rules published by Curtis Faith ("The
Original Turtle Trading Rules"; *Way of the Turtle*, 2007). Descends from Donchian channels
(`donchian_channel_breakout`). Engine runs it long-only on stocks.

## Exact rules (as published for futures; from Faith's rules as summarised in the catalog and general knowledge, original PDF not re-read this run)
- N = 20-day exponentially smoothed true range: N = (19 x prior N + today's TR) / 20.
- Unit = 1% of account equity / (N x dollars per point); for stocks dollars per point = 1, so shares = 0.01 x equity
  / N.
- System 1: enter when price exceeds the 20-day high by one tick (intraday stop order). Skip if the last S1 breakout
  (taken or not) was a winner; a breakout counts as a loser if price moved 2N against it before a profitable 10-day
  exit. If skipped, take the 55-day breakout as failsafe. Exit on a 10-day low.
- System 2: enter on the 55-day high, always taken; exit on a 20-day low.
- Initial stop: 2N below entry. Pyramid: add 1 unit every 1/2 N of favourable move, max 4 units; on each add, raise all
  stops to 2N below the newest entry.
- Portfolio limits (futures): 4 units per market, 6 closely correlated, 10 loosely correlated, 12 per direction.
- Whipsaw variant: 1/2 N stop with re-entry.

## Why it should work
Trend persistence plus asymmetric payoff: small, frequent losses at 2N, and occasional large trends ridden with a
loose channel exit and pyramided. Counterparties are mean-reversion traders and hedgers. On futures this is
documented time-series momentum; on single stocks idiosyncratic noise is larger and costs/gaps matter more.

## When it works and when it fails
Long trending periods with dispersion. Fails in sideways markets (System 1 whipsaws), sharp V reversals and gap-downs
through the 2N stop (single stocks gap on earnings).

## Parameters and sensitivity
Entry 20/55, exit 10/20, stop 2N, pyramid step 0.5N, 4 units. Trap: shortening windows to swing horizons turns it
into a whipsaw machine; keep the published values and treat the skip rule as a separate variant.

## Evidence
- Futures trend-following evidence is strong (catalog); for stocks the catalog grades it C.
- Wilcox & Crittenden (2005; read this run): long-only all-time-high-close entry (buy next open), 10 x ATR trailing
  stop, 24,000+ NYSE/AMEX/Nasdaq securities 1983-2004 including delisted, $15 minimum price and liquidity floors,
  0.5% round-trip cost. 18,000+ trades, 49.3% winners, average win / average loss 2.56, expectancy about 15.2% per
  trade, average hold 305 calendar days. Portfolio: 19.3% compounded annual return vs 12.0% for the benchmark, max
  drawdown -20.8% vs -44.7%. (Catalog's "$1,000 to ~$30,000" figure was not re-verified.)
- Zarattini, Pagani & Wilcox (2025, 1950-2024): fewer than 7% of trades produce the profit (catalog; not re-read).
- Turtle-specific tests on stocks: none located. Expect < 50% winners and a heavy right tail.

## Common mistakes
- Dropping the skip-rule's "shadow" trades (the rule needs the result of signals you did not take).
- Using simple ATR instead of the 20-day smoothed N (minor) or the current bar in the channel (look-ahead, major).
- Expecting swing-length holds: System 2 trades last weeks to months.

## Discretionary parts
None; fully mechanical once the shadow ledger exists.

## Implementation spec for swing-engine
- Features: `turtle_n` = Wilder-style EMA of `true_range` with alpha 1/20 (reuse `features.indicators.true_range` and
  `wilder_smooth(tr, 20)`); `dc_high_20`, `dc_high_55`, `dc_low_10`, `dc_low_20` from prior bars (`RollingSpec`
  with `prior=True`).
- S1 signal: high > `dc_high_20` (stop entry at `dc_high_20` + 0.01) unless the last S1 breakout in the shadow ledger
  was a winner; failsafe S2 entry. S2 signal: high > `dc_high_55`.
- Stop = entry - 2 x `turtle_n`. Exit rule: low < `dc_low_10` (S1) / `dc_low_20` (S2). No target, `min_reward_risk: 0`;
  `max_hold_days: 120` (S2) / 60 (S1).
- Sizing: the engine's `risk_per_trade_pct` 1.0 with stop distance 2N gives half a Turtle unit (Turtle risk per unit is
  1% per 1N move = 2% at the 2N stop); record this difference in replays.
- Close-based approximation (no new hooks): signal on close > channel, entry next open, no pyramiding, no skip rule.
- Missing: stop-entry hook, pyramiding (add-on units with shared stop), shadow-trade ledger for the skip rule
  (`research/shadow.py` records shadow signals and could be extended).

## What the router should know
Breakout/trend family; healthy_uptrend only. Long holds conflict with `earnings_exit_days: 1`; replays should report
how many trades were cut by earnings exits.

## Signs of decay to monitor
Share of P&L from the top 5% of trades; S1 skip-rule hit rate; whipsaw count per quarter.

## Sources
- https://www.mql5.com/en/articles/23448
- https://www.cis.upenn.edu/~mkearns/finread/trend.pdf (Wilcox & Crittenden 2005, numbers read this run)
- https://cxoadvisory.com/momentum-investing/all-time-high-trend-following

## Empirical (replay)
_Pending: filled in from swing replay on real data._
