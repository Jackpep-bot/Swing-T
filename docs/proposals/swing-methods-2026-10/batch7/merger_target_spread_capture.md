---
slug: merger_target_spread_capture
name: Merger arbitrage, long leg only - buy announced takeover targets after the definitive proxy or tender offer is filed, hold to completion
originators: [Mitchell & Pulvino, "Characteristics of risk and return in risk arbitrage", Journal of Finance 56(6) 2001]
category: strategy
decision: implement
holding_period_days: [20, 180]
timeframe: daily bars; EDGAR form types from the submissions JSON (DEFM14A, SC TO-T)
direction: long
universe: store stocks with mcap_pit >= $300M and med_dv_63 >= $5M on the signal day
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 7, 2026-10-14; first merger-arbitrage card in the catalog)
---

# Merger target spread capture

## Why this one is genuinely different
Every family replayed so far made or lost money with the stock market. A takeover target that has signed a deal
trades a few percent under the offer price and drifts up to it as the deal closes, mostly regardless of what the
market does. The return comes from bearing deal-break risk, not from market direction, so it is the first card whose
expected beta is near zero in normal markets. It needs no deal price: the store keeps delisted symbols, so the last
bar before the target stops trading is the payout.

## One-line summary
When a target files its definitive merger proxy (DEFM14A) or a third-party tender offer (SC TO-T) is filed on it, buy
the next open; hold until it stops trading, the deal breaks, or 180 sessions pass.

## Evidence
- Mitchell & Pulvino 2001 (via https://www.insidearbitrage.com/?p=102296, opened; paper at
  https://www.johnhcochrane.com/s/mitchell-pulvino-characteristics-of-risk-and-return-JF.pdf, not opened): 4,750
  mergers 1963-1998, excess return about 4% a year after transaction costs; returns correlate with the market only in
  severe down markets (like selling index puts). Spreads on deals that later failed were wider from the start.
- A merger-arb manager reports over 98% of its 5,000+ deals completed
  (https://www.westchestercapitalmanagement.com/assets/files/2/an_introduction_to_merger_arbitrage_5969.pdf, opened);
  a selected sample, not a base rate.
- Against: the sample ends in 1998; spreads are known to have narrowed since; no post-2010 cost-inclusive study
  found. Long-only means stock-for-stock deals carry the acquirer's price risk unhedged. Grade C.

## Engine version (pre-register this one)
- Signal (F): first DEFM14A filed by the symbol's CIK, or first SC TO-T with the symbol's CIK as subject, in the last
  365 days. Signal session = the session after the filing's acceptance time (as 8-K items).
- Skip if the stock is up more than 30% over the 20 sessions before the signal (a bidding war or a non-deal spike),
  or if a DEFM14A/SC TO-T signal for the same CIK fired in the prior 365 days.
- Entry next open. Exits, first to hit: (a) the symbol has no bar for 3 sessions (deal closed; exit at the last
  close, recorded as such); (b) close <= 0.85 x entry (deal break); (c) 180 sessions.
- Up to 15 open, equal dollar risk using the 15% break stop. `event_avoid_filters` does not apply (a merger 8-K is
  the event itself).

## Grading
Batch standard (net, own holding period) plus alpha and beta vs SPY from daily net returns in both windows, haircut
over this batch's trials. Report: completion share, mean gain on completed deals, mean loss on broken deals, worst
month vs SPY's.

## Expectation stated before the run
Many small wins (+1% to +4%) and a few -15% to -30% breaks (gaps through the stop). Net about +2% to +5% a year of
capital in use, beta 0.1-0.3, alpha t near 1. Fewer than 100 deals a year in this universe.

## Common mistakes
Treating a delisted symbol's missing bars as a loss; counting a target that was acquired before the replay window
starts; letting the last bar's close be read before the session it prints.
