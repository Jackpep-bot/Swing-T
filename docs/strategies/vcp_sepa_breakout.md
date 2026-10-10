---
slug: vcp_sepa_breakout
name: Minervini VCP / SEPA pivot breakout
originators: [Mark Minervini]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [4, 60]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: 0.37   # EasySwing coded VCP, 1,259 trades, gross; row internally inconsistent (see Evidence)
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built   # crude proxy: breakout_52w (enabled) with vcp_max_contraction off by default
---

# Minervini VCP / SEPA breakout

## One-line summary
Trade only Stage 2 leaders that pass the 8-point Trend Template. Buy the volume breakout through the pivot of a
Volatility Contraction Pattern: 2-6 pullbacks, each about half the prior, with volume drying up. Stop under the
last contraction, at most 10%. Move the stop to breakeven at 2-3R and sell into strength or on a heavy-volume
50-day break.

## Origin and lineage
- Builds on Weinstein stages, O'Neil (CAN SLIM, pivots, RS) and Darvas boxes.
- Minervini named SEPA, the Trend Template and the VCP in *Trade Like a Stock Market Wizard* (2013: ch. 5 is the
  template, ch. 10 is the VCP) and *Think & Trade Like a Champion* (2017).
- He won the US Investing Championship with +155% (1997) and +334.8% (2021). These are self-entered, one-year
  contests.

## Exact rules
All numbers below are from `docs/methods/03-vcp-minervini-trend-template.md`.

**Trend Template (all 8 must pass):**
1. Close > SMA150 and close > SMA200.
2. SMA150 > SMA200.
3. SMA200 rising for at least 1 month (4-5 months preferred).
4. SMA50 > SMA150 and SMA50 > SMA200.
5. Close > SMA50.
6. Close at least 30% above the 52-week low.
7. Close within 25% of the 52-week high.
8. RS rating at least 70 (IBD's rating is proprietary, so any replication approximates it).

**Setup:**
- 2-6 contractions, typically 2-4, each about half the prior (for example 25% -> 15% -> 8%).
- Volume dries up in the final contraction. The 40-60%-of-50-day figure is secondary and unverified.
- Prior advance of 25-30% or more (replications).

**Trigger and entry:**
- Pivot = the high of the last contraction. Buy as price trades through it; replications use a buy-stop 1-2%
  above the pivot.
- Breakout volume at least 40-50% above the 50-day average.
- Do not buy more than about 5% above the pivot.

**Stop:** just under the last contraction low. Maximum 10%; average target 5-6%.

**Exits:**
- Breakeven after 2-3x risk.
- Partial sales into strength at 2-3R.
- Climax sale after a 25-50% run in 1-3 weeks.
- Exit on a heavy-volume close below the 50-day.
- Exit a failed breakout that falls back below the pivot within 1-2 days.

**Sizing:** risk 1.25-2.5% of equity per trade, 20-25% positions, 4-12 names. Keep the engine caps instead.

## What the engine code actually does
`swing_engine/strategies/breakout_52w.py` is the closest proxy. It is enabled in `config/settings.yaml` and
allowed only in `healthy_uptrend`.

The rules it applies:
- `breakout_52w` flag: close > prior `high_52w` and volume >= 1.5x `avg_vol_50d`.
- `dist_52w_high >= -0.03`.
- Explicit volume ratio >= 1.5.
- `trend_state >= 0` and `market_trend_state >= 0`.
- **Optional** `vcp_contraction <= vcp_max_contraction`. The default is `None`, so this filter is off.
- Entry at the close. Stop at close - 2.0 x `atr_14`. Target 2R.

Differences from Minervini:
- No Trend Template: there is no SMA150, no SMA200 slope, no 30%-off-the-low test and no RS rank.
- `vcp_contraction` is a fixed ratio: the 20-bar range now divided by the 20-bar range 40 bars ago. It is not a
  count of shrinking swing pullbacks.
- The pivot is the 52-week high, not the last contraction high.
- The stop is ATR-based, not the contraction low.
- A fixed 2R target replaces breakeven, partial sales and the 50-day trail.
- There is no failed-breakout exit.

## Why it should work
Contracting ranges and volume show that supply from earlier buyers is exhausted (the "line of least resistance").
A volume breakout from that state forces stops and sidelined buyers in, and leaders near their highs carry
momentum and 52-week-high drift. Base sellers and short-term mean-reversion traders take the other side.

## When it works and when it fails
- **Works:** in bursts after corrections. FWTV found clean VCPs bunched in Aug-Sep 2025, Jan 2026 and Apr 2026.
- **Fails:** in narrow or choppy tapes. Minervini said 2025 breakouts failed within 1-2 days. Setups almost
  vanish in corrections, where FWTV found only 11% of them.

## Parameters and sensitivity
| Parameter | Value or range |
|---|---|
| `vcp_min_t` | 2 (3 preferred) |
| `vcp_depth_ratio_max` | 0.5-0.75 |
| `vcp_final_depth_max` | 0.10 |
| `vcp_first_depth_max` | 0.35 |
| `vol_dryup_max` | 0.6-0.7 (no book number) |
| `breakout_vol_mult` | 1.4-1.5 |
| `max_extension` | 0.05 |
| `max_stop_pct` | 0.10 |
| `rs_rank_min` | 0.70 |

The VCP has many knobs and few true setups per year, which is a classic overfitting trap. Pick the parameters
once, log every variant, and report deflated Sharpe.

## Evidence
- **EasySwing walk-forward** (7 Jul 2026, about 2,000 US stocks, 5 years, no costs):
  - Coded VCP: 1,259 trades, 37% wins, +0.1R average, PF 0.38. The PF and average R contradict each other, so
    read this as "no demonstrated edge".
  - Trend Template fresh pass: 18,382 trades, 40% wins, PF 0.99.
  - Cup & Handle on the same panel: PF 1.57.
- **FWTV top-100 study** (Aug 2025-Apr 2026): 6% average risk, +69% average gain. It is survivorship-conditioned.
- **Academic:** there is no peer-reviewed test of the template or the VCP. Its parts are supported: the 52-week-high
  effect (George & Hwang 2004) and momentum (Jegadeesh & Titman 1993). Momentum crashes in rebounds (Daniel &
  Moskowitz 2016).
- **Decay:** the template is now a commodity screen (chartmill, TradingView, MarketSurge), so the pivots are
  crowded.

## Common mistakes
- Seeing VCPs in hindsight.
- Buying late-stage (3rd-4th) bases.
- Chasing more than 5% past the pivot, which turns a 5% stop into a 10%+ stop.
- Copying the 20-25% position sizes.
- Using O'Neil's 7-8% stop while calling it Minervini's rule.

## Discretionary parts and how to make them mechanical
- **Contraction count:** a zig-zag swing detector from the base start (the last 52-week or pivot high). Emit
  `vcp_n_t`, `vcp_max_depth`, `vcp_final_depth`, `vcp_pivot` and `vcp_final_low`.
- **Base quality and the cheat / 3C entries:** a Claude review enum (`base_quality`), never a price.
- **Fundamentals (Code 33):** EDGAR XBRL, stamped by filing date. Not ingested.

## Implementation spec for swing-engine
**New features:**
- `sma_150`
- `sma_200_slope_21 = sma_200 / sma_200.shift(21) - 1`
- `dist_52w_low = close / low_52w - 1`
- `rs_rank`: the existing `rs_63d_rank`, or a weighted 63/126/189/252-day percentile
- `trend_template_pass` (0/1)
- `vcp_*` swing features (listed above)
- `vcp_vol_dryup = mean(volume over final contraction) / avg_vol_50d_prev`

**Signal:**
- `trend_template_pass == 1`
- `vcp_n_t >= 2`
- `close > vcp_pivot` and `close / vcp_pivot - 1 <= 0.05`
- `vol_ratio_50d_prev >= 1.4`

**Orders:**
- Entry at the close, or next open. A buy-stop at the pivot needs a stop-entry order type, which does not exist
  (intents carry `entry_limit` only).
- Stop = `max(vcp_final_low * 0.995, entry * 0.90)`.
- No fixed target. Use breakeven at 2R (`execution.breakeven_after_r` is 1.0 globally, so this needs a
  per-strategy override). Exit on a close < `sma_50` on volume >= 1.5x, or a close < `vcp_pivot` within 2 bars
  of entry.
- `max_hold_days` 60. `min_reward_risk` 0 (rule exit).

**Reuse:** `breakout_52w`, `dist_52w_high`, `rs_63d_rank`, `vol_ratio_50d_prev`, `atr_14`, `sma_50`, `sma_200`.

**Missing:** the swing-pivot detector, scale-out / partial exits, and per-strategy breakeven R.

The cheaper first test is the Trend Template as a universe filter for existing strategies.

## What the router should know
- Allow it in `healthy_uptrend` only.
- It is in the breakout family with `breakout_52w`, `base_breakout` and `qullamaggie_flag`, and overlaps with all
  three. De-duplicate by symbol.
- The count of `trend_template_pass` names is itself a breadth gauge (670 -> 127 in Q4 2018 per Weissman).

## Signs of decay to monitor
- Rate of breakouts that close back below the pivot within 2 bars.
- Average MFE in R.
- Template-pass count falling while the index makes highs (bifurcation).

## Sources
- `docs/methods/03-vcp-minervini-trend-template.md` and `docs/methods.md` 1a #7, 6.3, 7b
- https://easyswing.trading/performance
- https://github.com/sofus-nl/swing-trading-strategies
- https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini
- https://tikamalma.substack.com/p/understanding-basics-of-vcp-and-creating
- https://www.financialwisdomtv.com/post/can-one-chart-pattern-beat-the-market-i-tested-the-top-100-stocks
- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini
- Minervini, *Trade Like a Stock Market Wizard* (McGraw-Hill, 2013). Not read directly.

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 12 | 1 | 64% | +0.04 | -0.03 | 36% | -0.08 | -0.16 | 55% | -0.05 | -0.12 | 0.88 |
| correction | 1 | 0 | 0% | -0.35 | -0.49 | 100% | +0.02 | -0.12 | 100% | +0.05 | -0.09 | inf |
| healthy_uptrend | 27 | 1 | 50% | +0.04 | -0.04 | 65% | +0.31 | +0.23 | 58% | +0.42 | +0.34 | 2.43 |
| high_vol_selloff | 10 | 0 | 50% | -0.21 | -0.27 | 40% | -0.10 | -0.16 | 30% | +0.08 | +0.02 | 1.16 |
| narrow_uptrend | 4 | 0 | 25% | -0.19 | -0.30 | 25% | -0.28 | -0.39 | 25% | -0.20 | -0.31 | 0.71 |
| **all** | 54 | 2 | 50% | -0.03 | -0.11 | 52% | +0.10 | +0.02 | 50% | +0.20 | +0.12 | 1.53 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 38 | 0 | 39% | -0.33 | -0.42 | 42% | -0.33 | -0.42 | 45% | -0.35 | -0.44 | 0.48 |
| correction | 12 | 0 | 75% | +0.20 | +0.12 | 67% | -0.00 | -0.08 | 58% | +0.01 | -0.08 | 1.02 |
| healthy_uptrend | 197 | 0 | 47% | -0.04 | -0.12 | 48% | -0.06 | -0.14 | 47% | -0.02 | -0.10 | 0.96 |
| high_vol_selloff | 37 | 0 | 68% | +0.14 | -0.09 | 59% | +0.08 | -0.15 | 62% | +0.23 | +0.00 | 1.87 |
| narrow_uptrend | 39 | 0 | 44% | -0.06 | -0.14 | 59% | +0.12 | +0.03 | 56% | +0.33 | +0.24 | 1.89 |
| **all** | 323 | 0 | 49% | -0.05 | -0.15 | 50% | -0.05 | -0.15 | 50% | +0.01 | -0.09 | 1.03 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
