# Batch 6 candidates: factor-neutral reversal, a non-stock premium, and cross-stock signals (research thread, 2026-10-13)

Ask (Jack, 2026-10-13): keep a research stream running that finds new swing strategies online and compares them with
what the project has already tested. This is the first batch of that stream; a daily routine continues it.

15 ideas checked against the catalog (283 items, 146 built), batches 1-5 and the intraday rounds. **5 kept, 10
rejected** (9 entries; one covers two). The bar for keeping was "genuinely different from the families that already failed", because trader
and educator material is now mostly duplicates of the catalog (batch 5 rejected 10 ideas as exact repeats).

## What the failures so far have in common, and how each kept card differs
Replays so far: none of 4,103 trials beat SPY in both windows; most apparent edge was market beta; the small-cap map
lost in every liquidity band; intraday rounds 1 and 2 failed net. So this batch looks for (a) selection that removes
beta before ranking, (b) a return source that is not owning stocks, and (c) signals that come from other stocks.

| # | Card | Different because | Source | Grade | Expectation stated before the run |
|---|---|---|---|---|---|
| 1 | [residual_reversal_ff3_etf](residual_reversal_ff3_etf.md) | ranks on factor-neutral residual losers, not raw losers | Blitz-Huij-Lansdorp-Verbeek 2013 | C | alpha 0 to +2%/yr 2017-24, ~0 2024-26 |
| 2 | [within_industry_reversal_no_news](within_industry_reversal_no_news.md) | ranks against the stock's own industry, drops news moves | Da-Liu-Schaumburg 2014; Savor 2012 | C | alpha 0 to +3%/yr 2017-24, ~0 2024-26 |
| 3 | [vrp_svxy_dual_signal](vrp_svxy_dual_signal.md) | earns the volatility insurance premium, not stock returns | QuantConnect 2026 note; Simon-Campasano 2014 | C | alpha +1 to +3%/yr, t < 1.5; worse worst-day than SPY |
| 4 | [large_shock_no_news_reversal](large_shock_no_news_reversal.md) | rare 3-sigma no-news crashes, not mild pullbacks | Savor 2012; Chan 2003 | C | +0.3 to +1% gross per trade, ~0 net |
| 5 | [industry_leader_lag_smallmid](industry_leader_lag_smallmid.md) | trades small caps off their industry's large caps | Hou 2007 | D | +0.2 to +0.5%/wk gross over IWM, ~0 net |

Suggested replay order: 3 (cheapest: two ETFs), 1, 4, then 2 and 5 together once SIC codes are parsed.

Data: nothing new to approve. Cards 2 and 5 need the `sic` field parsed from the EDGAR submissions JSON that
`data/edgar.py` already downloads. Cards 1 and 3 need daily bars for IWM, IWD, IWF and SVXY (same Alpaca bars source).
VIX and VIX3M are already in the store (`vix` table).

Grading: as batch 5 (net, own holding period; alpha vs SPY from daily net returns in both windows, haircut over this
batch's 5 trials). Portfolio cards (1, 2) also report the income view Jack asked for: return, deepest drop, share of
months up, SPY beside it.

## Rejected (with source)

**Already replayed here**
- **Zarattini-Aziz-Barbon SPY "noise area" intraday momentum (Quantpedia Awards 2025, 4th) and Gao-Han-Li-Zhou first
  half-hour momentum.** Intraday round 2 (`docs/preregistration/2026-10-13-intraday-round2-results.md`): both FAIL,
  noise area -1.09 bp a day net in 2024-26.
- **Stocks-in-play 5-minute opening-range breakout (Zarattini-Barbon-Aziz 2024).** Catalog `orb_intraday_day_trading`
  is avoid; an independent replication reports "gross reproduced, net zero"
  (https://www.mql5.com/en/blogs/post/776235, search result only).

**Evidence gone or against**
- **Ernie Chan buy-on-gap.** Replication on small-cap value 2005-2020 at 0.1% round trip: after costs only the
  2014-2017 window is positive (https://financialnoob.substack.com/p/buy-on-gap-strategy-and-its-performance,
  opened); QuantRocket finds the large-gap version negative in liquid stocks
  (https://www.quantrocket.com/blog/buy-or-sell-down-gaps/, opened). Also needs an entry conditioned on the opening
  print.
- **Zarattini-Antonacci "A century of profitable industry trends".** The independent robustness paper
  (https://arxiv.org/html/2412.14361v1, opened) says walk-forward performance "fell short of market benchmarks" and
  a variant deteriorated in live trading. Batch 4 already rejected sector-ETF trend.
- **Option-expiration-week effect.** Evidence ends 2008 (Stivers-Sun via CXO,
  https://cxoadvisory.com/calendar-effects/option-expiration-week-stock-return-drill-down, opened); and an SPY timing
  card has the batch 4 power problem.
- **Cross-sectional overnight mean reversion on ETFs (QuantReturns, 2025).** Enters at the open on an overnight
  return only known at the open; Sharpe 4-7 is the signature of open-print bounce
  (https://quantreturns.substack.com/p/overnight-mean-reversion, opened).

**Needs data or tools the project does not have**
- **End-of-day reversal (Baltussen-Da-Soebhag 2025, Quantpedia Awards 2nd).** 3:30-4:00 pm hold on intraday losers,
  1993-2019, gross only (https://alphaarchitect.com/end-of-trading/, opened). Needs minute bars for ~1,500 stocks.
  Revisit if the intraday store is widened to the top 500.
- **Quantifiable Edges Capitulative Breadth Indicator.** Exact definition is proprietary; breadth timing is covered by
  `hill_breadth_model` and `zweig_breadth_thrust`.
- **Leveraged-ETF / gamma rebalancing end-of-day flows (Barbon et al., SFI 22-40).** Intraday, effect sizes not in
  the abstract, LETF part has decayed (https://www.sfi.ch/en/publications/n-22-40-liquidity-provision-to-leveraged-etfs-and-equity-options-rebalancing-flows-evidence-from-end-of-day-stock-prices, opened).

## Where the next batches look
Ordered by how different they are from the failed families: more factor-neutral versions of signals that were
replayed raw (the residual idea of card 1 applied to 52-week-high and gross profitability); event signals from EDGAR
form types not yet parsed (spin-offs Form 10-12B, SEO 424B, Form 144, 10b5-1 flags); non-stock premia available as
ETFs (bond auction cycle, commodity carry). Each batch drops anything already in the catalog or a README's rejected
list.
