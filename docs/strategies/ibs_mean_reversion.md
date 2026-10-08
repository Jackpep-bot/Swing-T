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
_Pending: filled in from swing replay on real data._
