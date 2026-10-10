---
slug: high_volume_return_premium
name: High-volume return premium, buy unusual one-day volume on an ordinary-return day (Gervais-Kaniel-Mingelgrin)
originators: [Gervais, Kaniel & Mingelgrin, "The High-Volume Return Premium", Journal of Finance 56(3) 2001]
category: strategy
decision: implement
holding_period_days: [20, 20]
timeframe: daily bars (1-day formation against a 49-day reference period)
direction: long (the paper is long high-volume / short low-volume)
regimes_good: []   # not studied in the paper
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: built_disabled (pre-registered 2026-10-10)
---

# High-volume return premium

## One-line summary
A stock whose dollar volume today is among the five highest of its own last 50 sessions tends to outperform over the
next 20 sessions, and more so when today's return was ordinary; the authors read it as a visibility shock (more
investors notice the stock), not as risk or news.

## Origin and lineage
- Gervais, Kaniel & Mingelgrin, JF 56(3), 2001, pp. 877-919 (peer-reviewed; published tables NOT read). Read in full
  this session: the authors' working paper, Rodney L. White Center WP 001-99, version of 17 December 1998,
  https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/9901.pdf . Every number below is from that
  working paper and may differ from the published tables.
- Kaniel, Ozoguz & Starks, JFE 103(2) 2012 (41-country evidence): not opened this session (no free copy found); no
  number from it is used here.
- Different from `high_turnover_short_term_momentum` (1-month turnover level x 1-month return) and from
  `momentum_volume_early_stage` (6-month turnover level): this is a one-day volume SHOCK relative to the stock's
  own recent volume. The paper stresses that high average volume predicts lower returns while a volume shock
  predicts higher returns.
- Chen-Zimmermann signal for the gate-2 CZ check: not identified this session (SignalDoc.csv not opened); check
  manually. Planning assumes at most half the published edge.

## Exact rules (as published, working paper)
1. Sample: NYSE stocks, CRSP daily, 15 August 1963 to 31 December 1996, split into 161 non-overlapping 50-day
   trading intervals with one day skipped between intervals (second half of 1968 dropped).
2. Reference period = first 49 days of the interval; formation period = day 50.
3. Volume = daily dollar volume (shares x closing price). Rank the formation-day volume among the interval's 50 daily
   volumes: rank >= 46 is HIGH volume (top 10%), rank <= 5 is LOW, otherwise normal (eq. 2).
4. Filters: no missing data in the interval; no merger, delisting, partial liquidation or seasoned offering during or
   within a year before the interval; at least one year of NYSE history; no price below $5 in the reference period.
5. Size groups by market-cap decile at the prior year end: large (deciles 9-10), medium (6-8), small (2-5); decile 1
   dropped.
6. Portfolios formed at the formation-day close and held, without rebalancing, for 1, 10 or 20 trading days: a
   zero-investment portfolio ($1 long high-volume, $1 short low-volume, equal weights) and reference-return
   portfolios (each high or low volume stock against its equal-weighted size group).
7. Normal-return subsample (section 4.3): drop stocks whose formation-day return ranks in the top or bottom 30% of
   the interval's 50 daily returns, i.e. keep return ranks 16..35 (eq. 7).

## Engine version (pre-register this one)
- Every session is a formation day (the paper's TAQ section does the same). High volume: dollar volume rank >= 46 of
  the stock's own last 50 sessions. Normal return: 1-day return rank 16..35 of its own last 50 daily returns.
- Filters: every close of the 50 sessions >= $5; at least 252 bars of history; the engine's liquid universe.
- Long only; entry next open; exit after 20 sessions; no target. Stop 3 x ATR(14) (engine choice so the engine can
  size; the paper has no stop).
- Not coded: NYSE-only, size groups, merger / SEO exclusions, the low-volume short leg.

## Why it should work
The authors' preferred story is Merton's (1987) investor-recognition idea: a volume shock makes a stock visible to
more investors and its price rises; they also cite Diamond-Verrecchia (1987) short-sale constraints (quiet periods
signal withheld bad news). They show it is not market risk (betas of the long-short book are zero or negative),
not earnings or dividend announcements, and not return autocorrelation.

## Evidence
All from the working paper (peer-reviewed article's draft), NYSE 1963-1996, gross of costs unless stated.
- Table 2, daily sample, zero-investment (long high / short low) net return over 20 days: small 0.94% (t=2.98),
  medium 1.07% (t=5.77), large 0.50% (t=3.11); over 10 days 0.77% / 0.74% / 0.46%; over 1 day 0.35% / 0.24% / 0.12%.
- Table 2, the LONG leg alone against its size group (reference-return portfolio, high-volume stocks), 20 days:
  small 0.45% (t=2.65), medium 0.41% (t=4.36), large 0.29% (t=3.80). This is the figure closest to a long-only book.
- Table 4, normal-return subsample, zero-investment 20-day net return: small 1.15% (t=2.25), medium 1.25% (t=4.53),
  large 0.60% (t=2.24). The long leg alone is not tabulated for this subsample.
- Announcements (section 6, Table 7): removing stocks with a dividend or earnings announcement within a day of the
  formation day leaves the 20-day returns at 0.99% / 1.10% / 0.47% (small / medium / large).
- Persistence: text says cumulative returns for small and medium firms are still about 1% after 100 days.
- Sub-periods (footnote 51): consistent before and after 21 April 1980.
- Costs (section 7, Table 12, TAQ sample, 20-day zero-investment): with limit orders at the quote, converted to
  market-on-close when unfilled, 0.33% (t=1.56) small, 0.26% (t=2.13) medium, -0.22% (t=-1.82) large; normal-return
  subsample 0.89% (t=2.53) small, 0.73% (t=3.99) medium, -0.06% large. With market orders at the bid/ask the same
  strategy loses: -3.08% small, -1.35% medium, -0.87% large (normal-return: -2.83% / -1.02% / -0.78%); at quote
  midpoints 1.39% / 0.88% / 0.32%.
- No post-1996 US test read this session.
- Grade B (peer-reviewed; gross; one cross-country study exists but was not read).

## Why it might beat costs, and why it might not
For: native 20-session horizon; one entry and one exit; the normal-return filter avoids gap days. Against: the
authors' own bid/ask test is negative for every size group with market orders, and the limit-order version is
negative for large firms. The engine fills at the next open with 10 bp slippage plus the per-stock spread top-up,
on a universe of the 1,500 most liquid names (closest to the paper's large and medium groups), where the gross long-leg edge
read above is 0.29-0.41% per 20 days against the size group. Expect a small edge at best.

## Common mistakes
Using share-volume level or turnover level (the opposite sign in the literature); ranking volume across stocks
instead of against the stock's own 50 days; trading earnings-gap days (the edge is larger on ordinary-return days);
judging it against zero rather than the market, since the long leg's raw return includes the market's.

## Implementation spec for swing-engine
Pre-registered in `docs/preregistration/2026-10-10-two-picks.md` (section 1). Module
`strategies/high_volume_return_premium.py`; extras `pctile_50_of_dollar_vol` (new exact extra `dollar_vol` = close x
volume, ranked within the symbol's own last 50 bars), `pctile_50_of_ret_1d`, `min_50_of_close`, `hist_bars`; panel
columns `atr_14`, `avg_vol_50d`. Fire: dollar-volume rank >= 46/50, return rank 16..35/50, min close >= $5,
`hist_bars` >= 252. Entry next open, stop 3 x ATR(14), no target, `max_hold_days` 20, `engine_trail = False`, score =
volume / `avg_vol_50d`. Settings: `high_volume_return_premium: {enabled: false, min_reward_risk: 0.0}`. Tests:
tests/test_strategy_two_picks.py.

## What the router should know
No regime evidence in the paper; treat as regime-neutral until the replay says otherwise.

## Signs of decay to monitor
Trailing 250-signal average 20-session return in excess of SPY <= 0.

## Sources
- https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/04/9901.pdf (working paper, read in full)
- https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html (published citation; article not read)
- https://ideas.repec.org/a/eee/jfinec/v103y2012i2p255-279.html (Kaniel-Ozoguz-Starks 2012; citation only, not read)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
