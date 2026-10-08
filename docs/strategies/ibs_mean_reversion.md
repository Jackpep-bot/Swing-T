---
slug: ibs_mean_reversion
name: Internal Bar Strength mean reversion (IBS < 0.2 buy, > 0.8 sell)
originators: [Alexander Pagonidis ("The IBS Effect", 2013); Quantified Strategies (popularised); Pandey & Joshi (2023 test)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long (short > 0.8 in the sources; engine long-only)
regimes_good: [choppy, narrow_uptrend, high_vol_selloff]
regimes_bad: [correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# IBS mean reversion

## One-line summary
Buy an equity index ETF at the close when it closes in the bottom 20% of its daily range (IBS < 0.2). Sell at a
close with IBS > 0.8, usually 1-3 days later.

## Origin and lineage
Pagonidis (2013) documented the "IBS effect" in equity-index ETFs from each fund's inception to May 2013. The catalog attributes this to NAAIM, which
was not confirmed. Quantified Strategies popularised the trading rule on SPY. Pandey & Joshi (arXiv 2306.12434, 2023) retested
it on 16 country ETFs. It is a cousin of the Connors family, but not a Connors indicator. thinkorswim ships the same quantity as
"CloseLocationValue" (on a -1..+1 scale).

## Exact rules
- IBS = (close - low)/(high - low), in [0, 1]. Undefined when high == low.
- **Long:** IBS < 0.2 at the close, so buy at the close. **Exit:** sell at a close with IBS > 0.8 (QS rule). Pandey & Joshi exit at the next
  close (1-day hold).
- **Cross-sectional variant (Pandey & Joshi):** each day, long the ETF with the lowest IBS and short the highest, closing at the next close.
- No stop, no target. Sizing is not taught (full equity in QS-style tests).

## Why it should work
A close at the low of the day reflects late-session selling pressure (often mechanical flows into the close) that is partly
reversed overnight and the next day. Pagonidis found the effect stronger in high volatility, in bear markets, after high-range and high-volume days, and
early in the week. That is consistent with liquidity provision (Nagel 2012).

## When it works and when it fails
It works best on diversified index ETFs in volatile tapes. It is weaker on single stocks (catalog note). It fails if the fill is not at
the close. Pandey & Joshi report Sharpe of about 3.7 close-to-close but -0.25 to +0.36 open-to-open, so the edge is mostly in the
overnight bounce.

## Parameters and sensitivity
Entry threshold 0.1-0.3, exit 0.8 vs next close, and an optional trend filter (close > sma_200). methods.md 2c also lists a
Reddit variant: IBS < 0.3 plus a close more than 2.5 average ranges below the 10-day high (secondary, untested here).

## Evidence
- Pagonidis 2013 (ETF inception to 12 May 2013): significant next-day reversal in most equity index ETFs. A simple strategy
  reportedly earned more than 30% a year average alpha **before costs** (via the search summary; the original paper was not read).
- Pandey & Joshi 2023 (16 country ETFs incl. IVV, EWJ, FXI, EWZ; Jan 2009 - Dec 2019): min/max IBS basket Sharpe 2.9-3.9.
  Single-ETF threshold rules gave Sharpe 0.2-2.2 at 1-day holds. With open-to-open fills it was about zero. Short borrow above about 0.15%/day (~56%/yr; base case 0.01%/day) eroded the long/short
  version.
- No cost- and data-snooping-adjusted evidence was verified. QS SPY statistics are paywalled.

## Common mistakes
Next-open entry, which loses most of the edge. Applying it to illiquid single stocks where the closing print is noisy. Ignoring
days with high == low.

## Discretionary parts and how to make them mechanical
None. The `source_engine_use` idea, using IBS as an entry-timing filter for other pullback strategies, is also mechanical
(`close_pos < 0.25`).

## Implementation spec for swing-engine
- Feature exists: `close_pos` in `features/cross_section.py` = (close - low)/(high - low) = IBS.
- Entry: `close_pos < 0.2` (optional `close > sma_200`). It **requires an MOC / close-fill entry mode** (missing: the backtester fills
  at the next open). Without it, the test measures the open-to-open variant, which the evidence says is about zero. Live: evaluate at
  about 15:50 ET from the live feed and send MOC (needs a near-close scan hook in `monitor`/`execution`).
- Exit (`should_exit`): `close_pos > 0.8`, or `bars_held >= 3`. Catastrophic stop `entry - 2*atr_14`.
  `max_hold_days` 3. `min_reward_risk` 0.
- Universe: index and sector ETFs (SPY, QQQ, IWM, DIA, sector SPDRs).
- Also worth adding as an optional confirm param on `rsi2_meanrev` (`close_pos < 0.25`, per methods/11).

## What the router should know
The evidence says the effect is stronger in high vol and bear markets, so unlike the 200-day-filtered Connors rules it can be shadowed
in `high_vol_selloff` at small size. Overnight holds only, and it shares the mean-reversion exposure cap.

## Signs of decay to monitor
Rolling 60-trade mean close-to-close return after IBS < 0.2 at or below the unconditional mean. Shrinking gap between low-IBS and high-IBS
next-day returns.

## Sources
- https://arxiv.org/abs/2306.12434 ; https://arxiv.org/html/2306.12434v1
- https://quantifiedstrategies.substack.com/p/the-internal-bar-strength-ibs-indicator (paywalled, not read)
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/C-D/CloseLocationValue
- https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html
- docs/methods/11-rsi2-connors-mean-reversion.md

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 327 | 0 | 63% | +0.15 | +0.08 | 54% | +0.11 | +0.04 | 52% | +0.22 | +0.16 | 1.50 |
| correction | 41 | 0 | 63% | +0.13 | +0.08 | 76% | +0.57 | +0.52 | 80% | +1.05 | +0.99 | 8.03 |
| healthy_uptrend | 882 | 1 | 48% | -0.02 | -0.10 | 46% | -0.02 | -0.10 | 38% | -0.07 | -0.15 | 0.88 |
| high_vol_selloff | 143 | 0 | 57% | +0.10 | +0.05 | 57% | +0.33 | +0.27 | 50% | +0.48 | +0.43 | 2.12 |
| narrow_uptrend | 135 | 0 | 40% | -0.07 | -0.15 | 38% | -0.07 | -0.14 | 36% | -0.06 | -0.14 | 0.90 |
| **all** | 1528 | 1 | 52% | +0.03 | -0.05 | 49% | +0.05 | -0.02 | 43% | +0.08 | +0.00 | 1.14 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 967 | 0 | 57% | +0.11 | +0.04 | 59% | +0.29 | +0.22 | 54% | +0.45 | +0.38 | 2.11 |
| correction | 632 | 0 | 63% | +0.20 | +0.16 | 60% | +0.34 | +0.29 | 56% | +0.51 | +0.46 | 2.24 |
| healthy_uptrend | 2226 | 5 | 53% | +0.05 | -0.03 | 48% | +0.03 | -0.05 | 44% | +0.13 | +0.04 | 1.23 |
| high_vol_selloff | 1146 | 0 | 50% | -0.02 | -0.07 | 47% | -0.02 | -0.07 | 45% | +0.04 | -0.01 | 1.08 |
| narrow_uptrend | 618 | 0 | 56% | +0.10 | +0.02 | 54% | +0.17 | +0.09 | 47% | +0.10 | +0.02 | 1.19 |
| **all** | 5589 | 5 | 54% | +0.07 | -0.00 | 52% | +0.12 | +0.05 | 47% | +0.21 | +0.14 | 1.41 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
