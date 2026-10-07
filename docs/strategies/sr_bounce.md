---
slug: sr_bounce
name: Support bounce (Schwab Learn / Joe Mazzola)
originators: [Charles Schwab education (Joe Mazzola); generic support/resistance practice]
category: strategy
decision: have
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff, narrow_uptrend]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: enabled
---

# Support bounce (`sr_bounce`)

## One-line summary
Trade with the larger trend: when price comes back to a prior support level and turns up, buy, put the stop just
below support and target the prior resistance level.

## Origin and lineage
- Broker education content: Schwab Learn, "The ins and outs of a swing trade" (Joe Mazzola), as recorded in the
  catalog (B28) and docs/sources-schwab-massive.md. The page returned an authorization error when re-fetched on
  2026-10-07, so the rules below are from the catalog/repo notes, not re-read.
- Repo example (docs/sources-schwab-massive.md): HON at a ~$170 low, target the ~$200 prior high.
- No named originator; it is the generic S/R swing trade found in most introductory texts.

## Exact rules
As taught (B28):
- **Screen**: trade with the larger trend (higher highs and higher lows).
- **Setup**: price returns to a prior support level.
- **Trigger**: price rebounds off support (no bar definition given).
- **Entry order**: not specified; Schwab suggests alerts or stop orders.
- **Initial stop**: just below support.
- **Target**: the prior resistance level.
- **Trailing/time exits**: none given.
- **Sizing**: risk-based; repo settings cite Schwab's example ($50k account, 1% = $500 risk, $2 trade risk ->
  250 shares; `config/settings.yaml` comment).
- Warning given: gaps can jump through stops.

## Why it should work
- Mechanism (hypothesis, not tested): resting buy interest and anchoring at a prior low; sellers who missed the prior
  bounce are absorbed. Counterparty: late sellers into the low. Short-term reversal literature (Jegadeesh 1990,
  Lehmann 1990) supports buying short-term weakness on average, not levels specifically.
- Grimes' finding that price behaviour at MAs is random (see `pullback_trend`) warns that "levels" may carry no
  information by themselves.

## When it works and when it fails
- Works: ranges and uptrends where the level has held before; normal volatility.
- Fails: downtrends (support breaks), news-driven drops, high-vol selloffs where levels are run, narrow tapes in
  non-leaders. Code accepts `trend_state == 0` (sideways), which is why the router excludes it in `narrow_uptrend`.

## Parameters and sensitivity
| Knob | Default | Range | Notes |
|---|---|---|---|
| `touch_pct` | 0.01 | 0.005-0.02 | abs(low - support_1)/close |
| `stop_atr_mult` | 1.0 | 0.5-1.5 | stop = support_1 - k*ATR |
| `min_trend_state` | 0 | 0-1 | 1 = Schwab's "with the larger trend" more strictly |
| `min_market_trend_state` | 0 | 0-1 | |
| `min_reward_risk` | 1.0 local; 2.0 portfolio | | |
| levels lookback / pivot width | 60 / 5 (features/levels.py) | 40-120 / 3-7 | changes which level is "support" |
Traps: the pivot definition (width, lookback) is the main hidden knob; tuning it to past bounces is easy overfitting.

## Evidence
- None. Schwab teaches it with illustrative examples only (catalog B28: grade "none").
- No independent test found. The engine's replay will be the first measurement.

## Common mistakes
1. Buying a support level in a downtrend.
2. Stop exactly at the obvious level (gets run).
3. Taking a bounce whose resistance target is less than 2x the stop distance.
4. Ignoring the reason price came back (earnings, downgrade).

## Discretionary parts and how to make them mechanical
- "Support": nearest confirmed pivot low below the prior close (`support_1`, pivot width 5, 60-bar lookback,
  confirmation lag respected).
- "Rebounds": low within 1% of support (or pierced it) and close back above support.
- "Larger trend": `trend_state >= 0` (code); taught rule implies `trend_state == 1`.

## Implementation spec for swing-engine
What `swing_engine/strategies/sr_bounce.py` does:
- Gates: `market_trend_state >= 0`; `trend_state >= 0`.
- Touch: `abs((low - support_1) / close) <= 0.01`; `close > support_1`; `close < resistance_1`.
- Entry reference = as-of close, next-open fill. Stop = `support_1 - 1.0 * atr_14`. Target = `resistance_1`.
- Score = reward:risk + (close - low)/atr_14.
- No `should_exit`, no `max_hold_days`: backtester default 20-bar time stop; execution breakeven at +1R and trail from
  +2R.
- Min reward:risk: local 1.0; the portfolio floor (`risk.min_reward_risk: 2.0`) rejects most bounces where
  resistance is near.
- Reuses: `support_1`, `resistance_1`, `atr_14`, `trend_state` (features/levels.py, regime.py).
Differences from the source: entry is next open after a close-based confirmation, stop has a 1 ATR buffer below the
level (Schwab: "just below"), and sideways trend is allowed.
Missing: stop-entry hook, RS/leader filter, earnings exclusion, count of prior holds of the level.

## What the router should know
- Settings: allowed only in `healthy_uptrend` (1.0). Deliberately excluded from `narrow_uptrend` (no leader filter,
  accepts sideways names; methods.md 3b, 3c).
- Overlaps `pullback_trend` on uptrending names; on sideways names it is a mean-reversion trade like `rsi2_meanrev`.

## Signs of decay to monitor
- Fraction of trades stopped within 3 bars rising (levels failing).
- Realised R per trade <= 0 over 50 trades.
- Many signals on the same day across a sector (a market-wide flush, not individual support).

## Sources
- https://www.schwab.com/learn/story/ins-and-outs-swing-trade (authorization error when fetched 2026-10-07)
- docs/sources-schwab-massive.md; docs/catalog/catalog.json (B28)
- swing_engine/features/levels.py

## Empirical (replay)
_Pending: filled in from swing replay on real data._
