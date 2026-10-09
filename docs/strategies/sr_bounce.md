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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 6107 | 57 | 49% | +0.03 | -0.13 | 44% | -0.02 | -0.18 | 41% | -0.02 | -0.18 | 0.97 |
| correction | 742 | 6 | 47% | -0.01 | -0.25 | 57% | +0.29 | +0.04 | 56% | +0.44 | +0.19 | 2.06 |
| healthy_uptrend | 18663 | 191 | 47% | +0.02 | -0.15 | 43% | +0.01 | -0.16 | 40% | +0.01 | -0.16 | 1.02 |
| high_vol_selloff | 3227 | 46 | 55% | +0.18 | +0.02 | 53% | +0.32 | +0.16 | 46% | +0.25 | +0.10 | 1.49 |
| narrow_uptrend | 3699 | 41 | 38% | -0.13 | -0.30 | 31% | -0.24 | -0.41 | 32% | -0.19 | -0.36 | 0.72 |
| **all** | 32438 | 341 | 47% | +0.02 | -0.15 | 43% | +0.02 | -0.15 | 40% | +0.02 | -0.15 | 1.04 |

Portfolio replay (net of costs, slots shared with its run): 6 trades, win 17%, avg -0.55R, PF 0.25, P&L $-1,271 on $100k, avg hold 37.8 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 21354 | 171 | 53% | +0.10 | -0.05 | 51% | +0.17 | +0.02 | 48% | +0.21 | +0.06 | 1.41 |
| correction | 8793 | 50 | 56% | +0.17 | +0.01 | 53% | +0.22 | +0.06 | 50% | +0.25 | +0.10 | 1.50 |
| healthy_uptrend | 64689 | 567 | 47% | -0.01 | -0.18 | 44% | -0.00 | -0.17 | 41% | +0.01 | -0.16 | 1.01 |
| high_vol_selloff | 13649 | 212 | 48% | +0.01 | -0.15 | 46% | +0.06 | -0.10 | 43% | +0.06 | -0.11 | 1.10 |
| narrow_uptrend | 17831 | 124 | 50% | +0.07 | -0.09 | 48% | +0.09 | -0.06 | 46% | +0.13 | -0.02 | 1.25 |
| **all** | 126316 | 1124 | 49% | +0.03 | -0.13 | 46% | +0.06 | -0.10 | 44% | +0.08 | -0.08 | 1.15 |

Portfolio replay (net of costs, slots shared with its run): 11 trades, win 27%, avg +0.11R, PF 1.19, P&L $2,654 on $100k, avg hold 10.8 bars.
