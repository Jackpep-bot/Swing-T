# Batch 7 candidates: event cards whose return does not come from the market (research thread, 2026-10-14)

First run of the daily research routine. No batch 5 or 6 results exist yet (both queued on the Mac), so nothing
here reacts to new replays.

8 ideas checked against the catalog, batches 1-6 and the intraday rounds. **2 kept, 6 rejected.** Both kept cards
are events whose payoff has a mechanical cause (a signed takeover, a placed share offering) and use EDGAR form
types already in the submissions JSON the store downloads: no new data source.

| # | Card | Different because | Source | Grade | Expectation stated before the run |
|---|---|---|---|---|---|
| 1 | [merger_target_spread_capture](merger_target_spread_capture.md) | pays for bearing deal-break risk; beta near zero outside crashes | Mitchell-Pulvino 2001 | C | +2 to +5%/yr on capital in use, beta 0.1-0.3, alpha t ~1 |
| 2 | [seo_marketed_offer_rebound](seo_marketed_offer_rebound.md) | buys only drops with a known temporary cause, after it ends | Price pressure and overnight SEOs (2000-2014) | C | +1 to +2% gross per trade, ~0 to +1% net |

Notes for the Mac, from its batch-6 feedback: neither card is a weights card (both size by their stated stop).
Card 1 needs `DEFM14A` and `SC TO-T` form types, card 2 needs `424B4`/`424B5`, both from the submissions JSON parsed
for 8-K items; the store starting in 2016 does not limit either card.

Suggested replay order: 1, then 2.

## Rejected (with source)
- **Treasury auction cycle (Lou-Yan-Zhang).** 1980-2008 only (https://ifr.hkust.edu.hk/uploads/upload/files/20250212/f5cba4b7e2aa3ada8477ad2fc38fab02.pdf,
  opened): 9-24 bp around 2- to 10-year note auctions, and the trade is in individual notes with repo, not an ETF.
  Would also need a new data source (TreasuryDirect auction calendar) for a few basis points per event.
- **Factor-neutral versions of 52-week-high and 12-1 momentum.** CXO's robustness review of pure momentum
  (https://www.cxoadvisory.com/momentum-investing/robustness-of-pure-stock-momentum-and-reversal/, opened): in
  2009-2015 US momentum was unattractive in both raw and residual form. `large_cap_residual_momentum` already lost.
- **Spin-offs.** The live spin-off ETF record is poor ("CSD: U.S. Spin-Off ETF Not Meeting Expectations",
  https://seekingalpha.com/article/4784447-csd-us-spin-off-etf-not-meeting-expectations, search result only);
  McConnell et al.'s 2015 update (https://business.purdue.edu/faculty/mcconnell/publications/The%20Stock%20Price...2013%20jpm.2015.42.1.143.pdf,
  not opened) is the only recent academic test found. Revisit if card 1 shows the EDGAR form-type path works.
- **Insider buys outside 10b5-1 plans.** The Form 4 plan checkbox exists only since April 2023; too few events for a
  test, and the insider family already lost to SPY.
- **Commodity carry via ETFs.** Needs futures curve history, which is not free; ETFs alone cannot measure carry.
- **Odd-lot tender offers.** A real retail-only edge (holders of under 100 shares avoid proration in buyback tenders),
  but it pays through a broker tender, not a trade the engine can replay or paper-trade, and needs the offer terms
  read from the filing text.

## Where the next batches look
More EDGAR form-type events (S-1 lockup ends are already filters; SC 14D9 recommendations; NT 10-K late filings as
an avoid filter), and results-driven follow-ups once batches 5 and 6 report.
