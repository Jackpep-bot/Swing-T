---
slug: bensdorp_adx_reversal
name: Bensdorp "Long Mean Reversion High ADX Reversal", strong-trend dip (ADX7 > 45, RSI3 <= 50), limit buy 4% lower, 6-day exit
originators: [Laurens Bensdorp, "Automated Stock Trading Systems" (2020); DrKoch WealthLab published code ID 51]
category: strategy
decision: implement
holding_period_days: [1, 6]
timeframe: daily bars, limit entry
direction: long
universe: store stocks with 50-day average volume >= 500k, dollar volume >= $2.5M, ATR%(10) >= 4
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 5, 2026-10-13; differs from catalog pullback_holy_grail)
---

# Bensdorp high-ADX reversal

## Why this one is different from what was tested
`pullback_holy_grail` buys over a touch-bar high after an ADX(14) > 30 pullback to the 20 EMA. This system uses a
fast ADX(7) at an extreme, requires price at least one ATR above the 100-day, and buys a limit 4% under the close
with an ATR-based target and 6-day time exit. Volatility floor again tilts it to small/mid caps.

## One-line summary
In a volatile stock trending hard above its 100-day, when the 3-day RSI dips to 50 or lower, place a limit buy 4%
below the close; take 1.2 ATR of profit or leave after six days.

## Origin and lineage
DrKoch's WealthLab code ID 51 (https://wealth-lab.com/Strategy/PublishedStrategies, read). The code's ADX limit
default is 20.5; the book value is reported as ADX(7) > 45 (from memory of forum posts, unverified). This card
registers 45 because 20.5 is not "high ADX" and looks like an optimiser output.

## Exact rules (as published)
Filters: 50-day average volume >= 500k, dollar volume >= $2.5M, ATR%(10) >= 4. Setup: ADX(7) above the limit;
close >= SMA(100) + ATR(10); RSI(3) <= 50; rank by ADX. Entry: limit 4% below the close. Exits: stop entry - 3 x
ATR(10); target entry + 1.2 x ATR(10); time exit 6 days.

## Engine version (pre-register this one)
- ADX(7) computed like `adx` but period 7 (new column `adx_7`). RSI(3) new column `rsi_3` (Wilder).
- Entry: limit 0.96 x signal close for the next session only; fill at min(open, limit).
- Target (from the fill session's close onward): entry + 1.2 x `atr_10`. Stop: entry - 3 x `atr_10`. Time exit:
  close of the 6th session after the fill. Max 10 open, rank by ADX(7).
- Exclusions: `event_avoid_filters`; skip if `sessions_to_expected_earnings` <= 6.

## Grading
Batch standard; report fill rate.

## Evidence
As for `bensdorp_mr_selloff`: book numbers not read; the forum's attempt at "ADX Reversal V2" alone reported about
12-22% APR on survivorship-biased data. Grade D.

## Expectation stated before the run
Win rate about 60%, small edge gross, near zero net.

## Common mistakes
Using ADX(14); filling on the signal bar.

## Signs of decay to monitor
Trailing 100-trade mean net R <= 0.
