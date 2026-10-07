---
slug: opportunistic_insider_purchases_cmp
name: Opportunistic insider purchases (Cohen-Malloy-Pomorski routine filter)
originators: [Lauren Cohen, Christopher Malloy, Lukasz Pomorski]
category: strategy
decision: implement
holding_period_days: [1, 21]
timeframe: daily bars + SEC Form 4 filings (event-driven)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Opportunistic insider purchases (CMP routine filter)

## One-line summary
Buy stocks where an insider who is *not* a calendar-routine trader made an open-market purchase (Form 4 code P),
entering at the next open after the filing, and hold up to about one month.

## Origin and lineage
- Cohen, Malloy & Pomorski, "Decoding Inside Information", *Journal of Finance* 67(3), 2012 (NBER w16454, 2010;
  SSRN 1692517). Sample: Thomson Reuters insider data, January 1986 to December 2007.
- Builds on the insider-purchase literature: Seyhun (1986), Lakonishok & Lee (RFS 2001: purchases, not sales, carry
  the information, concentrated in small firms), Jeng, Metrick & Zeckhauser (REStat 2003).
- Repo context: `docs/methods.md` 2b ("Insider signal": ignore routine trades) and the Stine doc
  (`docs/methods/14-insider-buy-superstocks-stine.md`), which cites the same 82 bp figure.

## Exact rules (as published)
Verified against the NBER working-paper text (w16454) this run:
1. **History requirement.** An insider can be classified only if they made at least one trade (buy or sell) in each of
   the three preceding calendar years. Insiders without that history are left unclassified (excluded).
2. **Routine trader.** An insider who traded in the same calendar month in at least three consecutive prior years.
3. **Opportunistic trader.** Every classifiable insider who is not routine.
4. **Classification timing.** Re-done at the start of each calendar year using only past trades; all of that insider's
   trades during the year inherit the label.
5. **Portfolios.** Each month, form opportunistic-buy, opportunistic-sell, routine-buy and routine-sell portfolios from
   that month's trades; hold over the following month; rebalance at month end. Equal- and value-weighted versions.
6. **Headline long-short.** Long opportunistic buys, short opportunistic sells.

What the paper does *not* specify as a trading system: a stop, a target, position sizing, or a price/liquidity floor
for a retail trader. Those below are engine choices.

## Why it should work
Routine trades (same month every year, often after bonus payouts or under standing plans) are liquidity or
diversification trades and carry no information. Stripping them out concentrates the sample on trades where the
insider chose the timing, which the paper shows predict firm news, analyst revisions and earnings surprises. The other
side is the uninformed seller who has not yet seen the disclosure, plus slow-reacting investors in small firms where
analyst coverage is thin.

## When it works and when it fails
- Works best in small, thinly covered firms (Lakonishok & Lee; CMP's equal-weight result is about twice the
  value-weight one), which is also where trading costs are highest.
- Purchases into weakness are common, so trend filters can cut the best trades; the existing `insider_cluster`
  module deliberately has no trend gate.
- Fails or is noisy in market-wide selloffs (insiders buy dips that keep falling) and after the disclosure-day jump has
  already priced the news. Post-SOX (2-business-day filing, since Aug 2002) much of the reaction happens on the
  filing day.

## Parameters and sensitivity
| Knob | Paper value | Sensible range | Notes |
|---|---|---|---|
| History years required | 3 | 3 (fixed) | Changing it changes what "routine" means; keep as published. |
| Routine consecutive same-month years | 3 | 3 | Paper reports robustness to "slight changes" in the classification. |
| Holding period | 1 month | 5-21 sessions | Edge front-loaded; longer holds dilute it. |
| Min purchase value | none | $10k-$100k | Engine choice to drop token buys; not in the paper. |
| Insider role filter | none | officers/directors only vs all | Test both; not in the paper. |
Overfitting traps: tuning the role/size filters and the hold length on the same sample; mixing in code A (grants).

## Evidence
- CMP 2012 (1986-2007), from the paper text: long-short opportunistic buys minus opportunistic sells earns
  **82 bp/month value-weighted** (9.8%/yr, t=2.15) and **180 bp/month equal-weighted** (21.6%/yr, t=6.07)
  five-factor alpha. Routine long-short: -20 bp VW and 43 bp EW (t=1.73). In pooled regressions, opportunistic buys
  add 90 bp (t=4.64) in the following month versus all insider trades; routine buys add 14 bp (t=0.81).
- **Correction to the catalog:** `docs/catalog/catalog.json` and `docs/methods/14` describe 82 bp/month as the return of
  "opportunistic buys". In the paper it is the **long-short** (buys minus sells) value-weighted alpha. A long-only
  opportunistic-buy portfolio's alpha is not quoted here; the 90 bp regression coefficient is the closest long-side
  number.
- Timing robustness (paper footnote): measuring returns from the 11th of month t+1 to the 10th of t+2 gives almost the
  same results, so the effect was tradable after the old 10th-of-month reporting deadline. Median reporting lag in
  their sample: 3 days.
- Post-SOX 3-day CAR on purchase filings 1.89% vs 0.59% pre-SOX (catalog, Harvard corpgov summary; not re-verified).
- Zhao (2026, arXiv 2602.06198, microcaps; cited in `docs/methods.md`): most of the abnormal return prints on the
  disclosure day. Practical consequence: the next-open entry after a filing captures less than the paper's monthly
  number.

## Common mistakes
- Treating Form 4 code **A** (grant/award) as a purchase. Only code P is an open-market buy. Note the monitor constant
  `FORM4_BUY_CODES = {"P", "A"}` in `swing_engine/monitor/constants.py` does this; the CMP feature must use P only.
- Using transaction date instead of filing date for point-in-time (CLAUDE.md rule 3).
- Classifying from buys only. The routine test uses *all* trades (buys and sells). `data/edgar.py::form4_buys`
  extracts code P only, so it cannot classify insiders as written.
- Counting 10b5-1 plan trades as opportunistic (plans are by construction scheduled; Form 4 has a 10b5-1 checkbox
  since 2023).

## Discretionary parts and how to make them mechanical
The paper is fully mechanical. The only judgement is which insider buys are "meaningful"; make it a versioned
`min_value_usd` param and a role list, and replay both with and without them.

## Implementation spec for swing-engine
Data: EDGAR Form 4 XML, all non-derivative transactions (codes P and S at minimum), per reporting owner CIK, with
`filed_at` (acceptance timestamp) and `transaction_date`. Needs a 3-year warm-up of filings before the first signal.

Features (new, computed per insider then aggregated per symbol, point-in-time on `filed_at`):
- `insider_years_active(owner, Y)` = set of calendar years < Y with >= 1 P/S trade; classifiable iff {Y-3, Y-2, Y-1}
  is a subset.
- `routine(owner, Y)` = exists month m such that owner traded in month m in each of three consecutive years before Y.
- `opp_buy_value_21d(symbol, as_of)` = sum of `shares*price` of code-P buys by opportunistic owners filed in the last
  21 sessions; `opp_buyers_21d` = distinct such owners; `opp_buy_flag` = 1 if a filing landed on `as_of`.
- Optional output into `insider_cluster_score` so `strategies/insider_cluster.py` can consume it unchanged.

Entry/exit as code would apply them (existing `insider_cluster.py` behaviour, which the CMP feature would feed):
- Signal on the session the filing becomes public (after-close filings belong to the next session); entry = next open
  (backtester fills queued signals at the next open).
- Current code: entry reference = close, stop = close - 2.0 x `atr_14`, target = entry + 2.0 x risk, `min_reward_risk`
  1.0, no trend or market gate (`min_trend_state` = `min_market_trend_state` = -1). This is an engine choice; the paper
  uses a calendar-month hold with no stop.
- Proposed CMP params: `max_hold_days: 21`, keep the 2 ATR stop for risk control, target 2R (or none plus time exit to
  mimic the paper), `min_value_usd: 25000` (to replay, not a paper value).
- Reuses: `atr_14`, `trend_state`, `dollar_vol_20d` (liquidity floor), backtester time stop via `max_hold_days`.
- Missing: full Form 4 ingest (buys and sells, owner CIK, 10b5-1 flag) into the store; per-owner history table; the
  routine classifier; fixing the code-A inclusion for this feature.
- Status: `insider_cluster` is registered but `enabled: false` in `config/settings.yaml`; the routine filter is not
  built, hence `status: not_built`.

## What the router should know
The playbook already gives `insider_cluster` 1.0 in healthy_uptrend and 0.5 in narrow_uptrend and nothing in choppy,
correction or high_vol_selloff. The event is regime-light (insiders buy weakness), so a small allocation in choppy is
defensible once replayed. Best used as an upgrade to a technical setup rather than standalone (catalog engine use).

## Signs of decay to monitor
- Next-open-to-day-21 mean return of opportunistic buys vs routine buys converging to zero.
- Share of the 3-day move occurring before the next open rising (more of the edge on the filing day).
- Rising share of 10b5-1-flagged purchases in the opportunistic bucket.

## Sources
- https://papers.ssrn.com/abstract=1692517
- https://www.nber.org/papers/w16454.pdf (definitions and Table IV numbers read from this text)
- https://www.nber.org/digest/apr11/decoding-inside-information
- https://corpgov.law.harvard.edu/2012/02/03/decoding-inside-information/
- https://corpgov.law.harvard.edu/2009/10/30/sox-and-insider-trades/
- https://arxiv.org/abs/2602.06198

## Empirical (replay)
_Pending: filled in from swing replay on real data._
