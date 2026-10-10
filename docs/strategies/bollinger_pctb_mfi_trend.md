---
slug: bollinger_pctb_mfi_trend
name: "Bollinger Method II: %b + MFI trend confirmation"
originators: ["John Bollinger, Bollinger on Bollinger Bands (2001)", "StockCharts ChartSchool ('Percent B Money Flow' write-up and tweaks)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 30]
timeframe: daily
direction: long_short   # engine long side only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Bollinger Method II: %b + MFI

## One-line summary
Buy when price pushes into the top 20% of its 20-day Bollinger range (%b > 0.8) and volume-weighted momentum
confirms (MFI > 80); stop and trail with Parabolic SAR.

## Origin and lineage
John Bollinger's second of three methods in *Bollinger on Bollinger Bands* (2001): trend following with a volume
indicator confirming band strength (Method I = squeeze, Method III = reversals with Intraday Intensity). ChartSchool adds
two filters: a low ADX (< 15) before the signal and a MACD signal-line cross on the first pullback.

## Exact rules
- Bands: BB(20, 2) on close. `%b = (close - lower) / (upper - lower)`.
- MFI: typical price TP = (H+L+C)/3; raw flow = TP x volume; positive/negative flow by TP up/down vs prior TP; MFI =
  100 - 100 / (1 + pos_sum/neg_sum) over n. Bollinger often used n = 10; ChartSchool default 14.
- Buy: %b > 0.80 AND MFI > 80. Sell/short: %b < 0.20 AND MFI < 20.
- Stop: Parabolic SAR (standard 0.02 step, 0.20 max assumed; parameters not given in the sources read).
- Exit: SAR hit or opposite signal.
- ChartSchool tweaks: (a) ADX(14) < 15 shortly before the signal (new trend emerging from a quiet period); (b) wait for
  the first pullback after the signal and enter when MACD crosses above its signal line.
- No targets or sizing published.

## Why it should work
Price strength confirmed by volume-weighted buying is a short-horizon momentum/breakout signal; the low-ADX tweak
targets volatility expansion out of a quiet base. Counterparty: sellers anchored to the old range. It is buying
"overbought", the opposite of the band-touch mean-reversion use, so it depends on trend persistence.

## When it works and when it fails
- Works: breakouts from quiet bases into sustained trends.
- Fails: ranges (the classic upper-band fade wins there); news spikes that fully mean-revert; SAR stops whipsaw in
  noisy trends (ChartSchool: countertrend bounces after sharp moves trigger stops).

## Parameters and sensitivity
| Knob | Default | Range |
|---|---|---|
| BB | 20, 2.0 | 20, 2.0 fixed |
| %b / MFI thresholds | 0.8 / 80 | 0.8-1.0 / 70-80 |
| MFI length | 10 (Bollinger) | 10-14 |
| ADX pre-filter | < 15 within 10 bars | 15-20 |
| SAR | 0.02 / 0.20 | fixed |
Trap: testing every combination of the two tweaks; log each as a separate trial.

## Evidence
- None specific. ChartSchool and the book give examples only. Catalog cites Lento et al. (2007) for Bollinger-band
  rules generally (method-specific result not found). Grade D.

## Common mistakes
- Using MFI with unadjusted volume around splits; using intraday %b readings.
- Fading the upper band and following it in the same book without a regime switch.

## Discretionary parts and how to make them mechanical
- "Low ADX before the signal": `min(adx_14 over last 10 bars) < 15`.
- "First pullback + MACD cross": after the signal, wait up to 10 bars for `macd` to cross above `macd_signal` after
  having been below; enter next open.

## Implementation spec for swing-engine
- Features: `pctb_20 = (close - bb_lower_20) / (bb_upper_20 - bb_lower_20)` (bands exist); `mfi_10` (missing);
  `adx_14` (exists in patterns2); `psar` (missing); `macd`, `macd_signal` (exist).
- Base variant: long on close t if `pctb_20 > 0.8` and `mfi_10 > 80`, `trend_state >= 0`; entry next open.
- Stop: `psar` value for the next bar (initialised at the signal bar's 10-bar low if SAR flips long that bar), floored at
  entry - 2 x atr_14 for sizing sanity.
- Exit: close < SAR (trail updated daily), or `pctb_20 < 0.2 and mfi_10 < 20`. No fixed target -> `min_reward_risk: 0.0`.
- max_hold_days: 30.
- Variants: +ADX pre-filter; +MACD pullback entry.
- Missing: MFI, Parabolic SAR state (path-dependent, needs a per-symbol loop or a trailing-stop hook).

## What the router should know
Momentum/breakout family: healthy_uptrend only with confirmed participation, like breakout_52w. Correlates with
breakout_52w and momentum_burst; check overlap.

## Signs of decay to monitor
Share of signals stopped by SAR within 3 bars; average MFE after signal shrinking.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/percent-b-money-flow
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/b-indicator
- Bollinger, *Bollinger on Bollinger Bands* (McGraw-Hill, 2001) (not re-read)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 5593 | 34 | 51% | +0.05 | -0.06 | 46% | +0.04 | -0.07 | 42% | +0.19 | +0.08 | 1.35 |
| correction | 1178 | 8 | 72% | +0.37 | +0.09 | 70% | +0.50 | +0.22 | 65% | +0.61 | +0.33 | 2.93 |
| healthy_uptrend | 23379 | 210 | 45% | -0.04 | -0.16 | 43% | -0.00 | -0.12 | 36% | +0.05 | -0.07 | 1.08 |
| high_vol_selloff | 1795 | 16 | 48% | -0.05 | -0.20 | 40% | -0.14 | -0.29 | 32% | -0.24 | -0.39 | 0.64 |
| narrow_uptrend | 1225 | 12 | 45% | -0.03 | -0.16 | 38% | -0.16 | -0.29 | 27% | -0.38 | -0.51 | 0.50 |
| **all** | 33170 | 280 | 47% | -0.01 | -0.14 | 44% | +0.01 | -0.12 | 38% | +0.07 | -0.06 | 1.11 |

Portfolio replay (net of costs, slots shared with its run): 308 trades, win 28%, avg -0.22R, PF 0.55, P&L $-24,163 on $100k, avg hold 7.5 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 18702 | 109 | 48% | -0.04 | -0.16 | 45% | -0.04 | -0.16 | 39% | -0.02 | -0.14 | 0.96 |
| correction | 14964 | 94 | 53% | +0.06 | -0.08 | 53% | +0.20 | +0.06 | 46% | +0.18 | +0.04 | 1.36 |
| healthy_uptrend | 106614 | 615 | 47% | -0.00 | -0.13 | 43% | -0.01 | -0.14 | 37% | -0.03 | -0.15 | 0.96 |
| high_vol_selloff | 12508 | 67 | 49% | -0.03 | -0.17 | 46% | -0.04 | -0.18 | 43% | -0.07 | -0.21 | 0.90 |
| narrow_uptrend | 13223 | 70 | 50% | +0.03 | -0.10 | 48% | +0.08 | -0.05 | 43% | +0.11 | -0.02 | 1.19 |
| **all** | 166011 | 955 | 48% | -0.00 | -0.13 | 45% | +0.01 | -0.12 | 39% | -0.00 | -0.13 | 1.00 |

Portfolio replay (net of costs, slots shared with its run): 1120 trades, win 36%, avg +0.03R, PF 1.08, P&L $26,025 on $100k, avg hold 8.5 bars.
