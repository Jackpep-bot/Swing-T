---
slug: kaufman_gap_momentum
name: Gap Momentum System (Perry Kaufman, S&C January 2024)
originators: [Perry J. Kaufman]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 30]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Kaufman Gap Momentum

## One-line summary
Measure only the overnight part of returns: the sum of up opening gaps against the sum of down gaps over N days,
smoothed into a signal line. Be long while the signal line rises and exit when it turns down.

## Origin and lineage
- Perry J. Kaufman, "Taking A Page From The On-Balance Volume: Gap Momentum", *Technical Analysis of Stocks &
  Commodities* V.42:01 (January 2024), pp. 14-17.
- The same month's Traders' Tips carried platform code.
- thinkorswim ships GapMomentum (study) and GapMomentumSystem (strategy). A TradingView open-source port exists
  ("TASC 2024.01 Gap Momentum System").
- The idea borrows from OBV: accumulate a one-sided quantity instead of price.

## Exact rules
- **Gap:** `gap_t = open_t - close_{t-1}`.
- **Sums over `length` days:** `up = sum(max(gap, 0))`, `dn = sum(max(-gap, 0))`.
- **Ratio:** `ratio = up / dn`.
- **Gap Momentum and signal line:** the sources disagree on how the ratio becomes the momentum series.
  - thinkorswim study page: Gap Momentum *is* the ratio. The signal line is a moving average of the ratio over
    `signal length`.
  - TradingView port and the S&C description: the series is built "the same way as OBV", that is,
    cumulatively. The signal line is an SMA of it.
- **Entry:** buy-to-open when signal_t > signal_{t-1}.
- **Exit:** sell-to-close when signal_t < signal_{t-1}. Long-only in the thinkorswim strategy.
- **thinkorswim inputs:** `length`, `signal length`, and `full range` (whether initialisation starts at the first
  bar of the lookup period). Defaults were not shown on the pages fetched.
- **Not specified:** stops, targets and sizing.

**Unresolved formula problem.** If the positive ratio itself were summed cumulatively, the series would rise every
day and the system could never exit. Kaufman's actual accumulation must therefore differ: for example accumulating
signed gaps OBV-style before taking the ratio, or treating the ratio as non-cumulative as thinkorswim says. The
article code was not readable this run (traders.com returned 403). **Verify against the S&C code before
implementing.** Until then, implement the thinkorswim (non-cumulative ratio) reading and label it.

## Why it should work
In US equities, most of the long-run return accrues overnight. Overnight and intraday returns behave differently,
and overnight returns are persistent cross-sectionally (catalog E31, the "evidence-backed cousin"; e.g. Lou,
Polk & Skouras 2019, JFE, cited from memory and not fetched this run). A rising share
of up-gaps may reflect persistent overnight demand: retail orders at the open, or news flow. The other side is
intraday liquidity providers who fade opens.

## When it works and when it fails
- Untested here. It should behave like any short-term momentum filter: fine in steady trends, whipsawed in chop.
- The "rising signal line" rule flips often unless `signal length` is long.
- Overnight-return regimes may shift with 23x5 trading. `docs/methods.md` says to re-validate all gap statistics
  after 2026-12-06.

## Parameters and sensitivity
| Parameter | Value |
|---|---|
| `length` | 20-60 (default unknown) |
| `signal_length` | 10-30 (default unknown) |
| `dn_zero_policy` | NaN, or cap the ratio at `ratio_cap` = 10 |
| `min_hold_days` | 0 |

The slope rule is very sensitive to `signal_length`. Pick one grid in advance and log every trial.

## Evidence
- The S&C article is a practitioner's in-sample illustration. Its results were not read (paywalled / 403).
- The broker publishes no performance data.
- Grade D. No independent test was found.

## Common mistakes
- Using adjusted opens across splits and dividends, which produces fake gaps. Compute gaps on split-adjusted prices
  with dividends handled consistently.
- Dividing by `dn = 0` in strong trends.
- Treating the cumulative and ratio versions as interchangeable.

## Discretionary parts and how to make them mechanical
None in the rule itself. The exit-only-on-slope rule has no stop, so the engine must add one (an engine choice):
`entry - 2 x atr_14`.

## Implementation spec for swing-engine
**Features (new, `features/patterns2.py` or a new `features/overnight.py`):**
- `gap_abs = open - prev_close`
- `gapm_up_L = rolling_sum(max(gap_abs, 0), L)`, `gapm_dn_L = rolling_sum(max(-gap_abs, 0), L)`
- `gapm_ratio_L = gapm_up_L / gapm_dn_L`
- `gapm_signal = sma(gapm_ratio_L, S)`
- `gapm_slope = sign(gapm_signal - gapm_signal.shift(1))`

All are per symbol and causal: today's open is known before today's close.

**Signal:** `gapm_slope` turns from <= 0 to > 0 (a fresh rise, to avoid re-entering every day). Optional
`trend_state >= 0`.

**Orders:**
- Entry at the close, or next open.
- Stop = entry - 2 x `atr_14` (engine choice).
- `should_exit` when `gapm_slope < 0`. No target.
- `min_reward_risk` 0. `max_hold_days` 30.

**Reuse:** `gap_pct`, `prev_close`, `atr_14`.

**Missing:** the gapm features themselves. `should_exit` must read `gapm_slope`, so the column has to be in
`required_features`.

## What the router should know
- High turnover: daily flips mean costs dominate (10-20 bps/side plus SEC/TAF per `docs/gates.md`).
- Use as a comparison and ranking feature for the overnight-return idea rather than a primary entry.

## Signs of decay to monitor
- Hit rate of the signal-slope direction against the next 5-day return.
- Turnover per month.
- Change in behaviour after extended-hours (23x5) trading starts.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GapMomentumSystem
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/G-L/GapMomentum (fetched 2026-10-07)
- https://kr.tradingview.com/script/52wKLj6P-TASC-2024-01-Gap-Momentum-System (fetched 2026-10-07)
- https://store.traders.com/stcov421gapm.html (article listing)
- https://traders.com/Documentation/FEEDbk_docs/2024/01/TradersTips.html (403; not read)
- `docs/catalog/catalog.json` B43; `docs/methods.md` (23x5 re-validation note)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
