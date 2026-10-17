---
slug: vrp_svxy_dual_signal
name: Volatility risk premium overlay - hold a small short-vol ETF (SVXY) beside SPY when VIX is in contango and above realised vol
originators: [QuantConnect research note "Harvesting the volatility risk premium with a dual VIX signal" (2026); Simon & Campasano, "The VIX futures basis: evidence and trading strategies", J. Derivatives 2014]
category: strategy
decision: implement
holding_period_days: [1, 30]
timeframe: daily bars; VIX, VIX3M (store table `vix`)
direction: long
universe: SPY + SVXY (cash = BIL or zero return before BIL history)
regimes_good: [calm_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 6, 2026-10-13; first volatility-premium card in the catalog)
---

# Volatility risk premium overlay

## Why this one is genuinely different
Every replayed card earns money the same way: owning stocks. This one earns the insurance premium that option
buyers pay (implied vol above realised vol), a different return source that the catalog has never tested. It is long
only (buying an ETF that is short VIX futures), uses only data already in the store (VIX, VIX3M) plus one more ETF's
daily bars, and is graded on what it adds to SPY.

## One-line summary
Hold SPY; when VIX is below VIX3M (contango) and above 10-day realised vol, also hold SVXY at VIX/100 of the account;
half that when VIX is in contango but below realised vol; no SVXY when VIX is above VIX3M.

## Evidence
- QuantConnect note (https://www.quantconnect.com/research/21143/harvesting-the-volatility-risk-premium-with-a-dual-vix-signal/,
  opened): Jan 2016-Jul 2026, short VIXY sized VIX/100 with SPY on the rest, Sharpe 0.729 vs SPY 0.582; all 25
  neighbouring settings (realised window 6-14 days, rebalance threshold 1-5%) between 0.713 and 0.773. A commenter
  notes the SPY leg drives much of the return. No drawdown or CAGR given. Signals at 15:45 with market-on-close.
- Short-vol ETPs lose most of their value in single days (Feb 2018; SVXY was cut from -1x to -0.5x on 2018-02-28).
  Grade C: one source, short live history, crash risk is the whole story.

## Engine version (pre-register this one)
- eVRP = VIX close - 100 x sqrt(252) x stdev(last 10 SPY daily close-to-close returns).
- Contango = VIX close < VIX3M close.
- Target SVXY weight: VIX/100 if contango and eVRP > 0; VIX/200 if contango and eVRP <= 0; 0 otherwise. SPY weight =
  1 - SVXY weight. Signals at the close, fills at the next open (registered deviation from the note's 15:45 MOC; the
  open gap after a VIX spike is the main risk and should be in the test). Trade only when the target SVXY weight moves
  by more than 2 points of the account or crosses zero.
- Window A starts 2018-03-01 (SVXY's current -0.5x form). 2016-01..2018-02 is reported separately, descriptive only.
- Costs: engine ETF cost model on traded notional.

## Grading
Alpha vs SPY from daily net returns in both windows (A 2018-03..2024-10, B 2024-10..2026-10), haircut over this
batch's trials; report worst day, worst month and deepest drop next to SPY's. Same SPY-timing power warning as batch
4: the overlay is 10-30% of the account, so alpha t is small even if the premium is real.

## Expectation stated before the run
Alpha +1% to +3% a year, t under 1.5 in both windows; worst day several points worse than SPY's (Aug 2024 and
Apr 2025 VIX spikes fall in window B).

## Common mistakes
Splicing pre-2018 -1x SVXY history into window A; using VIX3M from the same day's close for a fill earlier that day.
