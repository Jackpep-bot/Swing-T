---
slug: shareholder_yield_smallmid
name: Shareholder yield (dividends plus net buybacks), small/mid caps, monthly with a buy/hold band (Faber; Boudoukh et al.)
originators: [Boudoukh, Michaely, Richardson & Roberts, "On the importance of measuring payout yield", JF 62(2) 2007; Faber, "Shareholder Yield" (2013); Cambria SYLD]
category: strategy
decision: implement
holding_period_days: [21, 252]
timeframe: monthly rebalance; daily bars + dividends table + EDGAR shares
direction: long
universe: SMALLMID
regimes_good: [v_shaped_rebound]
regimes_bad: [narrow_uptrend]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; variant of batch 2 large_cap_net_repurchasers)
---

# Shareholder yield, small/mid

## Why this one is different from what was tested
Batch 2's `large_cap_net_repurchasers` used buybacks only, top-500 names; it passed the standard rule with zero alpha.
This card (1) adds cash dividends (the store has them since 2026-10-13), (2) uses small and mid caps, where the only
live product (Cambria SYLD, about 100 equal-weighted mid/small caps) runs, (3) requires positive operating cash
flow so the yield is paid from earnings, not debt.

## One-line summary
Each month, among small and mid caps with positive cash flow, buy the tenth paying the most to shareholders through
dividends plus net share reduction; hold while in the top fifth.

## Origin and lineage
- Boudoukh et al. 2007 (via https://www.cxoadvisory.com/?p=1146, opened): high/medium/low net payout 1.57/1.36/1.24%
  a month. Quantpedia's quote (https://quantpedia.com/strategies/net-payout-yield-effect, opened), 1984-2003: top 30%
  three-factor alpha 0.80% a month (t 10.9), max drawdown -52.5%.
- Gray & Vogel (Alpha Architect, 1972-2011, PDF opened): shareholder yield incl. debt paydown, top quintile alpha 25 bp
  a month; all yield measures have "lost considerable power in the last twenty years".

## Exact rules (as published)
Net payout = (dividends + repurchases - issuance) / market cap; sort at end of June, hold a year. Faber adds debt
paydown (not available here).

## Engine version (pre-register this one)
- Dividend yield: sum of regular (`special` false, `foreign` false) split-adjusted dividend rates with ex-date in the
  last 252 sessions / close.
- Net buyback yield: -ln(adjusted shares now / adjusted shares 252 sessions ago), same split handling as
  `net_share_issuance` (`data/fundamentals.py` share_issuance_features; reuse its guard against >+100%/<-50% jumps).
- Shareholder yield = dividend yield + net buyback yield. Eligible: TTM operating cash flow > 0, both inputs
  present, yield <= 25% (data-error guard).
- Rebalance: last session of each month; fills next open. Buy zone top 10% of SMALLMID by yield, hold zone top 20%.
  Equal weight, max 50 names. `execution.reuse_exiting_slots` on (the fix for half-invested monthly books).
- Catastrophe stop 3 x `atr_63`; no trail, no target, no regime gate. Total-return copy of the store
  (`config/prereg_div.yaml`) so dividends count.

## Grading
Batch standard, alpha against total-return SPY and IWM. Report turnover a year.

## Evidence
Grade C: strong long-run evidence that weakened over the last two decades; the live small/mid product SYLD
(Yahoo data as of about Feb 2026, opened): 10-year 12.93% a year vs 10.84% for its mid-cap value category, but
5-year 9.73% vs 11.27% and 3-year 6.44% vs 10.32%, and below SPY over 10 years.

## Expectation stated before the run
2017-24: about zero alpha vs SPY, positive vs IWM. 2024-26: negative vs SPY.

## Common mistakes
Counting special dividends; reading cover-page share counts without split adjustment (every split looks like an
issuance).

## Signs of decay to monitor
Trailing 3-year alpha vs IWM <= 0.
