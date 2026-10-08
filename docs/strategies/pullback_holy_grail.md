---
slug: pullback_holy_grail
name: Holy Grail pullback (ADX > 30, 20 EMA touch, buy over the touch-bar high)
originators: [Linda Bradford Raschke, Laurence Connors]
category: strategy
decision: have
holding_period_days: [2, 10]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null        # no published test of the exact rules
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: shadow_only
---

# Holy Grail pullback (`pullback_holy_grail`)

## One-line summary
When a strong trend (14-period ADX above 30 and rising) pulls back so a bar touches the 20-period EMA, buy over the
high of that touch bar, stop at its low (the new swing low), and target a retest of the prior swing high.

## Origin and lineage
- Raschke & Connors, *Street Smarts: High Probability Short-Term Trading Strategies* (1995). Book rules are known
  here only through restatements (tradingsetupsreview.com, investingLive 29 Mar 2021); the book itself was not read.
- Restatements disagree on the MA type: EMA in most, SMA in tradingsetupsreview. The book also covers re-entry and a
  second retracement (not coded).
- It is the ADX-qualified member of the pullback family (`pullback_trend`, docs/methods/01). methods.md 7b #1 lists it
  as the first P1 module.

## Exact rules
As taught (restatements):
- **Screen**: 14-period ADX initially above 30 and rising (+DI > -DI for longs); a strong trend leg.
- **Setup**: price retraces to touch the 20-period EMA.
- **Trigger / entry order**: buy stop at or above the high of the bar that touched the MA.
- **Initial stop**: below that bar's low / the newly formed swing low.
- **Target**: retest of the prior swing high (investingLive: slightly below the highest local high); trail if the
  trend continues.
- **Time**: 2-10 sessions to the swing high (doc 01 holding-period table).
- **Sizing**: not specified in the restatements; the engine uses 1% fixed-fractional.
- Known drawbacks (restatements): ADX > 30 can mark an overdone trend; slow, steady trends may never push ADX
  above 30, so the setup skips them.

## Why it should work
- Same mechanism as `pullback_trend`: a short liquidity-driven dip inside a strong trend; buyers enter after the
  dip has turned (buy stop) rather than catching it. ADX > 30 rising selects trends with directional persistence.
- The target (prior swing high) is a nearby, frequently revisited level, which raises the hit rate at the cost of
  payoff.

## When it works and when it fails
- Works: fast, persistent trends with a first orderly pullback; leaders near highs.
- Fails: ADX exhaustion (trend already climactic), ranges (ADX falling), news-driven dips, gaps through the touch-bar
  low. Small reward:risk when the touch bar sits close to the swing high.

## Parameters and sensitivity
| Knob | Default | Range | Notes |
|---|---|---|---|
| `pullback_ma` | `ema_20` | `ema_20`, `sma_20` | book MA type disputed |
| `adx_min` | 30 | 25-35 | |
| `adx_rising_bars` | 1 | 1-5 | ADX at the swing-high bar vs N bars earlier |
| `touch_pct` | 0.01 | 0.01-0.02 | low <= ma*(1+t) and close >= ma*(1-t) |
| `max_touch_age` | 3 | 1-5 | touch bar within last N bars before trigger |
| `swing_high_bars` | 20 | 10-40 | |
| `stop_atr_buffer` | 0.0 | 0-0.25 | |
| `max_hold_days` | 10 | 5-15 | |
| `exit_ma` | None | `sma_50` | optional close-below exit |
| `rs_rank_min` / `max_dist_52w_high_pct` | 0.96 / 10 | | leader gate passes on either |
| `min_reward_risk` | 1.0 (settings) | | swing-high target often < 2R |
Traps: ADX threshold and MA type tuned jointly; touch tolerance changes sample size heavily.

## Evidence
- No independent, cost-inclusive test of the exact rules was found (docs/methods/01; catalog C5 grade D).
- Family evidence (pullback in uptrend) is B-: EasySwing Trend Pullback 1,092 trades, PF 1.45, +0.3R, gross
  (see `pullback_trend` card).
- No post-publication decay data.

## Common mistakes
1. Buying the touch instead of the break of the touch-bar high.
2. Using ADX alone without checking +DI > -DI (direction).
3. Taking it in a range where ADX is falling from a spike.
4. Accepting a trade where the swing high is barely above entry (R:R < 1).
5. Treating the 2nd/3rd touch the same as the first.

## Discretionary parts and how to make them mechanical
- "Strong trend": ADX(14) >= 30, rising over 1 bar, +DI > -DI, measured at the prior swing-high bar (done).
- "Touch": low within 1% of the EMA and close not more than 1% below it (done).
- "New swing low": approximated by the touch-bar low (done).
- Re-entry / second retracement: not coded; would need a state of prior failed triggers.

## Implementation spec for swing-engine
What `swing_engine/strategies/pullback_holy_grail.py` does:
- Gates: `market_trend_state >= 0`; `trend_state == 1`; leader: `rs_63d_rank >= 0.96` or `dist_52w_high >= -0.10`.
- Touch bar k: the most recent of the last `max_touch_age` bars before the as-of bar t with
  `low_k <= ema_20_k * 1.01` and `close_k >= ema_20_k * 0.99`.
- Swing high s: bar with the highest high among the `swing_high_bars` bars before k. Requires `adx_14[s] >= 30`,
  `adx_14[s] > adx_14[s-1]`, `plus_di_14[s] > minus_di_14[s]`.
- Trigger: `close_t > high_k` and no close between k+1 and t-1 above `high_k` (first close over).
- Entry reference = as-of close, filled next open. Stop = `low_k - stop_atr_buffer * atr_14` (buffer 0).
  Target = `high_s`. Score = reward:risk.
- `should_exit`: `bars_held >= 10`, or close < `exit_ma` when set.
- Features from features/patterns2.py: `ema_20`, `adx_14`, `plus_di_14`, `minus_di_14`, `rs_63d_rank`.

Differences from the originators:
1. Close-based trigger filled at the next open instead of an intrabar buy stop; entry is higher and R:R lower.
2. ADX is checked at the swing-high bar (before the retracement), a reading of "initially above 30".
3. The leader gate (RS / near-high) is a methods.md 6.1 addition, not Raschke's.
4. No trail after the swing-high target; no re-entry rule.
- Min reward:risk: 1.0 local (settings override), below the portfolio 2.0 floor; the settings entry sets it to 1.0.
- Missing: buy-stop entry mode, ADX-at-touch variant, earnings exclusion.

## What the router should know
- Settings: `enabled: false, shadow_only: true`; router allows it at 1.0 healthy, 0.5 narrow. Shadow ledger only.
- Overlaps `pullback_trend` (same family; log as one trial family). Expect few signals: ADX >= 30 plus leader gate.

## Signs of decay to monitor
- Share of trades reaching the swing high before the stop falling below ~50% (the target is close, so the hit rate
  must be high to pay).
- Average realised R per trade <= 0 over 50 shadow trades.
- ADX-filtered signals underperforming the unfiltered `pullback_trend` signals on the same dates.

## Sources
- docs/methods/01-pullback-20-50-ma-uptrend.md; docs/methods.md 6.1, 7b #1
- https://tradingsetupsreview.com/the-holy-grail-trading-setup/
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329
- https://lindaraschke.net/
- Raschke & Connors, *Street Smarts* (1995) (not read directly)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 492 | 17 | 48% | +0.07 | -0.14 | 41% | +0.00 | -0.20 | 38% | -0.02 | -0.22 | 0.97 |
| correction | 56 | 1 | 33% | -0.33 | -0.56 | 33% | -0.40 | -0.63 | 27% | -0.42 | -0.64 | 0.47 |
| healthy_uptrend | 2072 | 50 | 44% | +0.03 | -0.19 | 39% | -0.03 | -0.25 | 35% | -0.08 | -0.31 | 0.88 |
| high_vol_selloff | 321 | 16 | 44% | +0.00 | -0.19 | 38% | -0.05 | -0.24 | 36% | -0.07 | -0.27 | 0.89 |
| narrow_uptrend | 328 | 7 | 27% | -0.29 | -0.55 | 28% | -0.27 | -0.53 | 30% | -0.12 | -0.39 | 0.81 |
| **all** | 3269 | 91 | 43% | -0.00 | -0.23 | 38% | -0.05 | -0.28 | 35% | -0.08 | -0.31 | 0.88 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 0%, avg -0.31R, PF 0.00, P&L $-10 on $100k, avg hold 4.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1813 | 35 | 48% | +0.10 | -0.12 | 46% | +0.16 | -0.06 | 44% | +0.18 | -0.04 | 1.31 |
| correction | 484 | 8 | 42% | -0.06 | -0.27 | 39% | -0.05 | -0.26 | 36% | -0.08 | -0.29 | 0.88 |
| healthy_uptrend | 8976 | 163 | 44% | +0.01 | -0.22 | 41% | +0.02 | -0.20 | 39% | +0.02 | -0.21 | 1.03 |
| high_vol_selloff | 821 | 11 | 50% | +0.06 | -0.18 | 48% | +0.18 | -0.05 | 44% | +0.18 | -0.06 | 1.30 |
| narrow_uptrend | 1563 | 22 | 45% | +0.02 | -0.21 | 39% | -0.02 | -0.25 | 37% | +0.00 | -0.23 | 1.00 |
| **all** | 13657 | 239 | 45% | +0.02 | -0.21 | 42% | +0.04 | -0.18 | 39% | +0.04 | -0.18 | 1.07 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
