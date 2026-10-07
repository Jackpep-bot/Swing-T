# 04 - Classic chart-pattern / base breakouts (cup-with-handle, flat base, flags)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Each number is tagged with where it came from.
"(primary)" means the teacher's own site, book or interview. "(secondary)" means third-party notes, summaries or
replications. "(sweep)" means it was carried over from `docs/research-raw/methods-sweeps/*.json` and not re-fetched in
this run. "(unverified)" means it could not be checked against a primary source. investors.com (IBD) blocks this
agent's fetcher, so every IBD number below is secondary. Treat those numbers as the commonly quoted IBD rules, not
as quotations.*

**One line.** Buy a leading stock (big prior advance, strong relative strength, in a confirmed market uptrend) on the
day it clears the pivot of a proper consolidation: the handle high of a 7-to-65-week cup, the top of a 5-week-plus
flat base no more than 15% deep, or the high of a short flag after a steep pole. Breakout volume should be at least
40-50% above average. Do not chase more than ~5% past the pivot. Cut the loss at 7-8% or when price falls back into
the pattern, and take most gains at 20-25% unless the stock is a fast mover that qualifies for a longer hold.

**Lineage.** William J. O'Neil formalised the base taxonomy (cup-with-handle, flat base, double bottom, high tight
flag) in *How to Make Money in Stocks* (McGraw-Hill, 1988) and in IBD/MarketSmith (now MarketSurge). Dan Zanger
turned it into a high-turnover, volume-first breakout practice. Thomas Bulkowski supplied the large-sample pattern
statistics. Minervini (VCP), Kullamägi (doc 05) and Kell all build on this base vocabulary.

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| Prior advance into the base | "Rise before cup is at least 30%" is an O'Neil criterion, and Bulkowski adopted it as his own selection rule | Bulkowski, *Encyclopedia of Chart Patterns* 2nd ed. (Wiley 2005), ch. 9, Table 9.1 (primary for Bulkowski, secondary for O'Neil) |
| Relative strength | O'Neil requires "improving relative strength". IBD's "L" = leader in a leading industry, measured by 12-month RS vs the market. Coded replications use an RS rank of at least 80. Moglen/TraderLion want the RS line at new highs ahead of price | Table 9.1 (secondary); Wikipedia CAN SLIM summary (sweep); sofus-nl repo gate (secondary); Trading Engineered (sweep) |
| Fundamentals (CAN SLIM C/A) | Current quarterly EPS up at least 25% y/y; annual EPS growth at least 25% over 3 years; ROE at least 17%. Zanger wants "powerful earnings growth (50%+)", a young global leader, a high-priced stock in a strong group | Wikipedia CAN SLIM (sweep); Trading Resource Hub "Nuances behind Dan Zanger" (16 May 2026, secondary) |
| Trend template | Handle forms above the 200-day MA (O'Neil per Bulkowski). Coded versions require SMA50 > SMA200. Soreide: "never buy below the 200-day" for high tight flags | Table 9.1; sofus-nl; Soreide TraderLion masterclass transcript (sweep) |
| Near highs | Bulkowski: 93% of bull-market cup breakouts occur in the top third of the 12-month range | Encyclopedia 2nd ed., Table 9.4 (primary) |
| Vehicle | Zanger trades "leading high-beta stocks coming out of well-defined patterns" and scrolls 1,400-1,500 charts a day by hand instead of using scanners | Trading Resource Hub (secondary, compiling 2000-2020 interviews) |

### Pattern geometry (the core of the method)

**Cup-with-handle**
| Element | O'Neil / IBD | Zanger (chartpattern.com) | Bulkowski |
|---|---|---|---|
| Cup length | At least 7 weeks; 7-65 weeks (Table 9.1) | Correction lasts 8-12 weeks "depending on the overall market" (primary) | 7-65 weeks, i.e. 49-455 days (primary) |
| Cup depth | 12% or 15% to 33%; 40-50% possible in bear markets (Table 9.1) | 20-35% off the old high (primary) | No limit; prefers tall cups. Lips should sit at about the same price (primary) |
| Shape | U-shaped. Cups without handles are allowed | Avoid lopsided cups, "halfway on one side and all the way up on the other" (CMC Opto interview, sweep) | U-shaped. Higher left lip did slightly better in the 2nd ed. sample |
| Handle position | Upper half of the cup, above the 200-day MA | About 5% below the old high. A lower handle is "generally a defective stock" (primary) | Upper half of the cup (primary) |
| Handle length | Usually at least 1-2 weeks | 4 days to 3 weeks, drifting sideways with a downside bias (primary) | At least 1 week, no maximum. Handles shorter than the 22-day median do better (primary) |
| Handle depth | 10-15% from its high unless the cup is very large (Table 9.1); summaries say 8-12% | Implied ~5% (primary) | Not constrained |
| Handle volume | Drifts down on light volume | Not stated on the page | Not used as a filter |
| Buy point | Handle high plus $0.10 (IBD, secondary) | "as it emerges into new highs at the top of the handle", not at the old high of the left lip (primary) | Close above the handle high |
| Breakout volume | At least 50% above normal (Table 9.1); IBD summaries say at least 40% above average | 300%+ on breakout per Trading Resource Hub (secondary) | Heavy breakout volume helps 79% of the time (sweep: "study of studies") |

**Flat base**
- IBD: at least 5 weeks (vs 7 for a cup), depth no more than ~15%, a tight range throughout. It usually forms after a stock
  has broken out of a deeper base and advanced 20% or more, so it is often a second-stage base. The pivot is the
  base high plus $0.10, with breakout volume at least 40% above average. (secondary: LuxAlgo flat-base page, IBD
  summaries in search results; investors.com unreachable)
- Zanger: a base that "goes horizontal for any length of time". Volume should dry up while price holds level. Draw
  a trendline across the top and buy as price breaks it on rising volume. (primary, chartpattern.com/flat-base.cfm)

**Flags, pennants, high tight flag**
- Zanger: a bull flag has lower highs and lower lows inside parallel lines that slant against the trend. A pennant
  looks like a small symmetrical triangle. Both are brief pauses "right after a big, quick move". Volume contracts in
  the pause and rises on the breakout. (primary, chartpattern.com/flags-pennants.cfm)
- Bulkowski: the flagpole should be "unusually steep" and last several days. Flags are under 3 weeks long; anything
  longer is a rectangle or channel. The best ones tilt down after an upward pole. Volume trends down in 74% of
  up-breakout cases, and tight flags beat loose ones. (primary, thepatternsite.com/flags.html)
- High tight flag (O'Neil/Soreide): the pole rises ~90% minimum (100-120%+ ideal) in 4-8 weeks. The flag is a
  shallow 10-25% pullback over 1-3 weeks (max ~5), holding above the 50-day with volume drying up. Buy above the flag
  high (+$0.10) on volume 50%+ above average. Bulkowski requires a 90% rise in 2 months or less and buys only on a
  close above the pattern's highest peak. (sweep: Soreide TraderLion 2025 transcript; Bulkowski htf.html; see doc 05)
- Ascending triangle (Zanger): flat top with rising lows, most reliable in an uptrend, breakout on "a marked increase
  in volume". (primary)

### Market filter
- O'Neil "M": about 3 of 4 stocks follow the general market. Buy only in a "confirmed uptrend". (Wikipedia CAN SLIM,
  sweep)
- IBD Market School: a follow-through day on day 4-7 of a rally attempt (some versions say 4-10) with an index gain
  of roughly 1.2-1.75%+ on higher volume than the prior day. A distribution day is an index decline on higher volume,
  and 5-6 of them within ~25 sessions flags "uptrend under pressure". (sweep: TradingView FTD marker, Fool boards,
  TraderLion TML reports)
- Zanger: the cup-with-handle works best at the start of a market move after a good correction, and not during or at
  the end of a major advance (primary, cup-handle page). He avoids bear markets, saying "not to trade bear markets"
  and you will not lose money. He reports trading only the 3-4 favourable months of a year and sitting in cash
  otherwise. Bear-like tape: breakouts "fail en masse", or stocks make new highs off abbreviated bases and quickly
  fail. (secondary, Trading Resource Hub)
- Bulkowski 2nd ed.: bull-market cups rose 34% on average vs 23% in bear markets. During those bull-market cups the
  S&P rose 16%. (primary)

### Entry
- Buy on the breakout through the pivot: the handle high, flat-base high or flag high, typically + $0.10, on the day
  volume runs 40-50%+ above average. IBD's "buy zone" is up to 5% above the pivot. Zanger avoids buying more than ~5%
  above the breakout (sweep, low-confidence "10 Golden Rules" summary).
- Zanger's execution (secondary): he "probes" with a partial position first. A hard fill means supply is tight, so he
  adds. An easy fill means supply is present, so he passes. He abandons stocks that do not "rocket out of their bases
  on the first day".
- Bulkowski: wait for a close above the pattern high. Throwbacks to the breakout happen 58-62% of the time but should
  not be relied on for a second entry. Cups that threw back rose 30% vs 40% for those that did not. (primary)
- IBD SwingTrader variant (5-10 day swings): buy at the pivot of a proper base or on a pullback to the 21-day line.
  (sweep)

### Stop
- O'Neil/IBD: "cut your losses at 7% to 8%" below the buy point, no exceptions (IBD article quoted on Motley Fool board
  22 Jan 2025, sweep). IBD SwingTrader uses ~3% max loss. (sweep)
- Bulkowski: stop at the handle low (point C). (primary, cup.html)
- Zanger: exit immediately if price falls back into the pattern (sweep). In practice he exits on trendline breaks,
  bearish reversal bars, or stalled volume, and will sell within ~20 minutes if the stock underperforms. (secondary)
- Soreide (HTF): hard stop placed immediately, typically ~5% below entry or under the flag low. (sweep)

### Exits and targets
- O'Neil/IBD: "take your profits at 20% to 25%". **8-week hold rule:** if a stock gains 20% or more within 3 weeks of a
  proper breakout, hold it at least 8 weeks through pullbacks to the 10-week MA unless a clear sell signal appears.
  (sweep: Fool board quoting IBD, Jan 2025)
- IBD SwingTrader: profit target ~10%. (sweep)
- Zanger: partial profits of 20-30% of the position at +15-20% (sweep, low confidence). He adds to and concentrates in
  the "one or two fastest stocks" and moves "in and out until they begin to fizzle". (secondary)
- Bulkowski measure rule: target = breakout + cup height. 61% of perfect trades reach it (primary). In the 2nd ed. data,
  28% of bull-market cups failed to rise 15% and 55% failed to reach +30%. When the uptrend ends, prices drop over 30%,
  so do not buy-and-hold a cup. (primary)
- Soreide (HTF): take partials at 2R+ into strength and do not hold through earnings. (sweep)

### Position sizing
- Risk-based sizing is implied, not prescribed. A 7-8% stop at ~1% account risk gives a ~12-14% position. IBD-style
  portfolios run 4-8 concentrated names, scaled by Market School exposure levels (0-100% in steps). (sweep;
  arithmetic is ours)
- Zanger used 2:1 margin and extreme concentration during the 1998-2000 run. After a single-day 32% loss on Nortel in
  2000 he diversified across stocks and groups. He warns against margin until you have mastered the market. (secondary)
- Soreide grades high tight flag setups to choose size. (sweep)

### Holding period
- Zanger: 3-5 days to 2 weeks for high-level breakouts. For long-base breakouts (6-10 weeks) after a market
  correction, 10-15 weeks. (secondary)
- IBD: days to weeks. The 8-week rule extends fast movers. IBD SwingTrader holds 2-6 days, sometimes up to 2 weeks.
  (sweep)
- Bulkowski 2nd ed.: bull-market cups took 167 days on average to reach the ultimate high, and 57% took more than 70
  days. The pattern's full move is a multi-month position trade, while the swing version harvests only the first
  leg. (primary)
- Coded replications: an average hold of 8 days (EasySwing panel) to 16 days (sofus-nl). (secondary)

---

## Chart signatures
- **Cup-with-handle:** a prior uptrend of 30% or more, then a rounded U-shaped decline of 12-33% (Zanger 20-35%) over
  7+ weeks. The right side climbs back near the left lip. A short (1-3 week), shallow (≤10-12%) handle drifts down in
  the upper half on light volume. The pivot is the handle high. Volume dries up at the cup bottom and in the handle,
  then surges on breakout day.
- **Flat base:** a sideways range no more than 15% deep for 5+ weeks, usually after a prior breakout and a 20%+
  advance. Weekly closes cluster tightly and volume contracts. Price breaks the horizontal top on expanding volume.
- **Bull flag / pennant:** a steep multi-day pole, then a ≤3-week channel tilting down (flag) or converging (pennant).
  Volume declines in the pause. Price breaks the upper line on a volume pick-up.
- **High tight flag:** a pole of ~90-120%+ in ≤8 weeks, then a 10-25% flag of 1-3 (max ~5) weeks above the 50-day MA.
- **Ascending triangle:** a flat top with rising lows. Breakout through the flat top on marked volume.
- **Quality tells:** the RS line at or near new highs before price breaks out. Bulkowski found tall patterns and
  breakout-day gaps help, and throwbacks hurt (97% of the time per the "study of studies", sweep). Short handles are
  better. A first or second base beats a late-stage base. The market is in a confirmed uptrend.
- **Faulty tells:** a handle in the lower half or wedging up. A V-shaped cup with no time to shake out holders.
  Breakout volume below average. A late-stage (3rd-4th+) base. A buy >5% past the pivot. A breakout in a market under
  pressure.

---

## Who teaches it
| Who | Where | Notes |
|---|---|---|
| William J. O'Neil (1933-2023) / Investor's Business Daily | *How to Make Money in Stocks*; investors.com; MarketSurge (formerly MarketSmith); IBD Live; X @IBDinvestors / @MarketSmith (sweep) | Source of the base taxonomy, 7-8% stop, 20-25% profit, 8-week rule, FTD/distribution-day market filter. IBD SwingTrader (Mike Webster) is the 5-10-day variant. IBD's YouTube channel had ~184K subs at the 29 Sep 2026 sweep. |
| Dan Zanger | chartpattern.com (The Zanger Report nightly newsletter + chatroom); X @DanZanger (sweep) | Volume-first breakout trader. Pattern pages on chartpattern.com are the primary rules quoted above. The site claims an audited $10,775 -> $42M in 23 months (1998-2000) (unverified independently). |
| Thomas Bulkowski | thepatternsite.com; *Encyclopedia of Chart Patterns* (Wiley, 2nd ed. 2005, 3rd ed. 2021) | Statistics, not a trading service. Cup page last had examples added 10/25/2025 per the page; rank tables dated 8/24/2020. |
| TraderLion (Richard Moglen, Leif Soreide, Oliver Kell guests) | traderlion.com, TraderLion Podcast, YouTube; X @RichardMoglen, @TraderLion_ (sweep) | RS-line leadership + O'Neil bases; Soreide HTF masterclass (2025, podcast 31 May 2026). Publishes the "TML Report" market notes (Feb-Apr 2026 FTD calls by title). |
| Deepvue | deepvue.com | CANSLIM-style screener built by TraderLion alumni (RS rating, group rank, RS line). |
| Coded/open replications | EasySwing.trading + github.com/sofus-nl/swing-trading-strategies; TradingView cup-handle scripts | Mechanical detectors with published gates and (backtested) stats. |

---

## Evidence

### Pattern statistics (Bulkowski, primary)
- **Cup-with-handle, current site (thepatternsite.com/cup.html, fetched 2026-10-06):** performance rank 3 of 39,
  break-even failure rate 5%, average rise 54%, throwback 62%, measure-rule target met 61%, based on 913 "perfect
  trades" (breakout to ultimate high, i.e. no stop and perfect exit). A review of 300 cups from 1990 to March 2024
  found 47% "dropped substantially within two months" after breakout, and 23% rose no more than 15%. Short handles
  (under the 22-day median) do better.
- **Cup-with-handle, Encyclopedia 2nd ed. (2005), ch. 9:** 412 bull-market up-breakouts with an average rise of 34%
  (bear market 23%, n=59). The cup ranked 13 of 23 then, an average performer. Break-even (5%) failure was 5%; 17%
  failed to reach +10%, 28% failed to reach +15%, 38% failed to reach +20%, 55% failed to reach +30%. The median handle
  ran 34 days from the right lip to breakout. Throwback rate 58%; cups with throwbacks rose 30% vs 40% without.
  Breakout-gap cups rose 39% vs 33% without. Average 167 days to the ultimate high. The rank moved from 13/23 (2005)
  to 3/39 (site) because the methodology changed to perfect trades and the pattern set grew, which shows how
  methodology-dependent these "rankings" are.
- **Bull flags (thepatternsite.com/flags.html, stats updated 8/27/2020):** not ranked. Break-even failure 44%,
  average rise 9%, measure rule met 46%. That is a short-swing pattern with near coin-flip follow-through when
  measured on its own.
- **High tight flag (htf.html; see doc 05):** rank 30/39, failure 15%, average rise 39%, n=1,028. The HTF study
  (1995-2009) found a +27% average post-breakout move, and 14% never broke out upward.
- **Failures rising over time (FailureRates.html):** 13,932 patterns, 1991-2008. The share of up-breakouts failing to
  gain 10% rose from 14% in the 1990s to 28% in 2003-2007, and the 2007 peak was 44%. Bulkowski concludes patterns
  "fail between two and four times more often now". The site itself notes the rank tables (Aug 2020) are outdated.
- **Study of studies (sweep, 9/17/2020):** patterns with throwbacks underperform 97% of the time; breakout-day gaps
  help 68%; tall patterns outperform 89%; heavy breakout volume helps 79%; 55% of upward breakouts move 20%+.

**Caveat.** Bulkowski's averages are "perfect trade" numbers measured from breakout to the ultimate high, with no
stop and no slippage. They describe the pattern, not a tradable rule. Sites quoting a "95% success rate, +54%"
(e.g. Liberated Stock Trader) are restating these figures and are not independent tests.

### Academic
- **Lo, Mamaysky & Wang (2000), "Foundations of Technical Analysis", *J. Finance* 55(4):1705-1765 (NBER w7613).**
  Kernel-regression pattern detection on US stocks 1962-1996. Several patterns "provide incremental information",
  meaning conditional return distributions differ for 7 of 10 patterns on NYSE/AMEX and 10 of 10 on Nasdaq. No
  profitable rule was demonstrated, and cups and flags were not among the patterns tested (head-and-shoulders,
  broadening, triangles, rectangles, double tops/bottoms).
- **Osler (1998, NY Fed Staff Report):** head-and-shoulders in 100 random stocks, 1962-1993, ~10-day holds, mean
  -0.24% per round trip before costs. "On average unprofitable." (CXO review, 24 Oct 2006)
- **Savin, Weller & Zvingelis (2007, *J. Financial Econometrics*):** H&S has predictive power (5-7%/yr risk-adjusted)
  but little or no support as a stand-alone strategy. (sweep)
- **Leigh, Modani, Purvis & Roberts (2002), "Stock market trading rule discovery using technical charting heuristics",
  *Expert Systems with Applications* 23(2):155-159:** a template recognizer for two bull-flag variants, applied to the
  NYSE Composite **index** (not single stocks). It reports effective out-of-sample rules. This is weak evidence for
  single-stock swing use. (abstract only, secondary)
- **Jiang, Kelly & Xiu (2023), "(Re-)Imag(in)ing Price Trends", *J. Finance*:** CNNs trained on OHLC-volume chart
  images. Decile long-short reaches gross Sharpe ~2.5 equal-weighted but ~0.6 value-weighted, before costs, and the
  learned patterns transfer across horizons and countries. (sweep; SSRN 3756587 returned 403 on fetch.) This supports
  "price images carry information" more than any named pattern.
- **Backdrop (see doc 05):** George & Hwang (2004) find nearness to the 52-week high predicts returns. Momentum crashes
  after market declines (Daniel & Moskowitz 2016). Both support "leaders near highs, in uptrends only".

### Independent / mechanical replications (secondary)
| Study | Rules coded | Sample | Result |
|---|---|---|---|
| EasySwing.trading performance panel (updated 7 Jul 2026) | Cup & Handle detector (gates in sofus-nl repo) | ~2,000 US stocks, 5-year walk-forward, raw exits, **no fees or slippage** | **Cup & Handle: win 30%, avg +0.5R, PF 1.57, 3,582 trades, avg hold 8 days.** Same panel: VCP Breakout 37% win, 0.1R, PF 0.38 on 1,259 trades (internally inconsistent as published, treat as unreliable); Qullamaggie-style breakout PF 1.10 (doc 05) |
| sofus-nl/swing-trading-strategies `02-cup-and-handle.md` | Prior uptrend ≥30%; cup 3-6+ weeks, 12-35% deep; handle <12% of cup height, ≥5 days, volume < 50-day avg; breakout vol ≥1.4x 50-day avg; RS rank ≥80; SMA50 > SMA200; bull market only. Stop 1.5 ATR; T1 2.5 ATR (sell 40%), T2 5 ATR (60%), then trail swing low | "55+ trades", attributed to O'Neil / Quantified Strategies | 69% win in best regime vs 32% in worst; avg 2.1R; 16-day hold. **Small sample, no costs, no walk-forward**. Bull flag listed only as "honorable mention", hard to gate without manual chart reading |
| Reddit r/swingtrading (sweep; reddit not fetchable here) | Discretionary breakouts / bull flags | One trader | +$90K in 2025 at ~65% win and 3-6:1 R:R, then "every single trade fails" since March 2026 with no change in method (unverified anecdote) |

### Reading the evidence
1. Patterns carry **some** information (Lo-Mamaysky-Wang, Jiang-Kelly-Xiu). No peer-reviewed study shows a
   net-of-cost, single-stock cup or flat-base swing rule beating the market.
2. The best mechanical evidence (EasySwing, gross of costs) puts cup-with-handle at PF ~1.6 and +0.5R/trade with a
   30% hit rate. That is the best of the base patterns on that panel but thin once 10-20 bps/side and fees are applied.
3. Bulkowski's numbers say the **distribution** is the edge: few break-even failures but frequent shallow moves (28%
   never reach +15%). A large part of the expected value sits in a small number of multi-month winners that a 20-25%
   profit-take truncates. The 8-week rule exists for this reason.
4. Failure rates roughly doubled from the 1990s to 2003-07 (Bulkowski). Zanger's own record was set in the 1998-2000
   bubble. Expect the pattern to be regime-dependent, and do not anchor on 1990s statistics.

---

## Pitfalls
1. **Perfect-trade statistics are not trade statistics.** Bulkowski measures breakout to ultimate high, with no stop.
   With a 7-8% stop, many of his "successes" are stop-outs first (throwbacks 58-62%).
2. **Throwbacks vs stops.** A 58-62% throwback rate means a tight stop just under the pivot is hit often. Choose the
   stop at the handle low, at 7-8%, or "back in the pattern", version it, and test it. Do not mix them per trade.
3. **Chasing.** Buying more than 5% past the pivot, or on a gap far above it, turns a ~7% risk into a much larger one.
   Both IBD and Zanger cap the buy zone at ~5%.
4. **Bad geometry.** Handles in the lower half, wedging-up handles, V-shaped cups, low-volume breakouts and late-stage
   bases fail more often. Most of these are judgement calls that coded detectors approximate poorly.
5. **Regime.** Breakouts "fail en masse" in corrections (Zanger). Bear-market cups average 23% vs 34% (Bulkowski).
   Without an M/regime gate the method is a different, weaker strategy.
6. **Survivorship in teaching charts.** Textbook examples are winners chosen after the fact. Pattern recognition
   with hindsight (and pivot look-ahead in code) inflates backtests.
7. **Profit-taking truncation.** A strict 20-25% exit removes the right tail that carries the expectancy. A
   never-sell approach gives back 30%+ when the trend ends (Bulkowski). The 8-week rule and a partial-plus-trail
   compromise both need explicit, tested parameters.
8. **Event risk.** Earnings inside the hold. CAN SLIM selects for earnings momentum, but holding through the report
   is a separate bet. Soreide says do not hold HTFs through earnings.
9. **Concentration and margin.** Zanger's record came with 2:1 margin and one or two names. The 2000 Nortel day
   (-32%) is the cautionary tale. Do not copy his sizing.
10. **Rule drift across teachers.** Cup depth (12-33% vs 20-35%), handle depth (~5% vs 10-15%), breakout volume (40%,
    50%, 300%) and flag pole size are all inconsistent across sources. Pick one set, version it, and keep it out of
    per-trade tuning.

---

## 2025-2026 fit
- **Index vs average stock.** On 2026-10-06 the S&P 500 printed 7,819 (+14.2% YTD) and the Nasdaq +18.8% YTD
  (thepatternsite.com market banner). Underneath, only 26.9% of 4,806 US stocks were above their 50-day and 39.7%
  above their 200-day (doc 06, thetrading.tools). In September 2026 the equal-weight S&P fell 4.8% and the Russell
  2000 5.3% while the 10-year yield hit 5.29% (Janus Henderson, 1 Oct 2026). This tape favours a handful of leaders.
  Most bases in the broad universe are breaking down, not out.
- **Timeline.** The Apr 2025 tariff crash was followed by a breadth thrust and a strong Jul-Oct 2025 window for clean
  breakouts (FinancialWisdomTV study, Aug 2026, via doc 05). The S&P peaked ~7,000 on 27 Jan 2026, then fell ~10%
  into March, and the Nasdaq entered correction by 27 Mar 2026 (oil >$100-110, Iran strikes, 10-yr 4.44%).
  TraderLion's TML Report flagged a follow-through day around 20 Feb 2026 and again in early April 2026 (titles only;
  pages returned 403). Semiconductors had a "major correction" after a strong first five months (Continuum, 5 Aug
  2026). That is a stop-start year: base breakouts worked in short windows after FTDs and failed in between.
- **Practitioner reports.** A widely shared r/swingtrading post says breakout and bull-flag trades that worked all of
  2025 have failed since March 2026 (unverified). Kullamägi-style breakouts clustered in Jul-Oct 2025 with few in
  Apr-May 2026 (doc 05). No 2026 primary commentary from Zanger was found. chartpattern.com still sells the nightly
  report, and the CMC Opto interview URL now returns 404.
- **Mechanical read.** The EasySwing walk-forward through mid-2026 still shows cup-with-handle positive gross (PF 1.57)
  and the best of its base detectors. After costs, and in a market where under a third of stocks are above their
  50-day, expect much of that edge to depend on the market gate.
- **Verdict.** The method is intact but should run only when the market filter is on (FTD-confirmed uptrend /
  `market_trend_state >= 1`) and only in names with RS-line leadership. In October 2026's narrow, high-yield tape,
  expect few valid setups. Prefer flat bases and short-handle cups in leaders over flags in laggard small caps.

---

## Automatability

### Mechanical (codeable in swing-engine)
| Element | swing-engine mapping |
|---|---|
| Universe floors | `universe.min_price` 5.0, `min_avg_dollar_volume` 5e6, `min_avg_volume` 5e5 (`config/settings.yaml`); `dollar_vol_20d`, `avg_vol_50d` in `features/cross_section.py` |
| Near highs / trend template | `dist_52w_high`, `high_52w` (cross_section); `sma_50`, `sma_200` (indicators); `trend_state >= 1` (regime: close > sma_50 > sma_200, sma_50 rising) |
| Relative strength | **Add** `rs_rank` (cross-sectional percentile per `ts` of a weighted 3/6/9/12-month return built from `ret_63d`, `ret_126d`, `ret_252d`) and `rs_line_high` (close/SPY ratio at a 52-week high) to `features/cross_section.py` / `regime.py` (SPY is already loaded as the market frame) |
| Prior advance ≥30% | **Add** `prior_advance_pct`: max(high)/min(low) - 1 over the 63-126 bars *before* the base starts (point-in-time, uses only confirmed pivots) |
| Base geometry | **Add to `features/patterns.py`:** `base_depth_pct` = (left-lip high - base low)/left-lip high; `base_len` in bars since the left-lip pivot (the existing `base_len` = bars since within 5% of 52w high is a rough proxy); `handle_len`, `handle_depth_pct`, `handle_upper_half` (handle low > (lip + cup low)/2), `handle_vol_ratio` (mean volume in handle / `avg_vol_50d`), `pivot_high` (max high since the right lip). Reuse confirmed pivots from `features/levels.py` (`PIVOT_WIDTH` = 5, confirmation lag respected) |
| Flat base | rolling window ≥25 bars with (max high - min low)/max high ≤ 0.15 and `prior_advance_pct` ≥ 0.20; pivot = window max high (`RollingSpec("max","high",N,prior=True)` in `strategies/_base.py`) |
| Flag / HTF | pole = `ret` over ≤10-40 bars ≥ threshold (HTF 0.90); flag = ≤15 bars, depth ≤ 0.25 (HTF 0.10-0.25), lower highs, `vcp_contraction`/`bb_width_20` falling, close > `sma_50` |
| Breakout trigger | `close > pivot_high` and `volume >= 1.4-1.5 x prior avg_vol_50d` (the same benchmark `breakout_52w` uses); `close_pos` near the high (not a reversal bar) |
| Buy-zone cap | `(close - pivot_high)/pivot_high <= 0.05` (IBD/Zanger) |
| Stop | variants: `entry * (1 - 0.07)` (O'Neil), handle low (Bulkowski), `pivot - k*atr_14` (current `sr_breakout` level mode) |
| Exits | `target_pct` 0.20-0.25 (O'Neil) or measure-rule target (`sr_breakout` already does a measured move); 8-week rule: if `ret since entry >= 0.20` within 15 bars, switch to `close < sma_50` (10-week) trail and hold ≥40 bars; time stop for stalls (Zanger: no follow-through on day 1-3) |
| Market gate | `market_trend_state >= 1`, `market_vol_regime < 2` (`P_MIN_MARKET_TREND`). **Add** IBD-style `dist_days_25` (index down ≥0.2% on higher volume, count over 25 sessions) and `ftd_active` (day 4-10 of a rally attempt, index +≥1.2% on higher volume) to `features/regime.py`. Breadth gates from doc 06 (`pct_above_50d` ≥ 50%) are a natural complement |
| Sizing | `risk/sizing.py` with `risk_per_trade_pct` (1.0) and a 7-8% stop gives a ~12-14% position, so `max_position_pct` 10 will bind. Keep the cap and accept ~0.7% realised risk, or lower the stop distance |
| Costs | `docs/gates.md` 10/20 bps per side + SEC/TAF fees; required before quoting any PF |

**Closest existing modules.** `strategies/breakout_52w.py` (52-week-high close on ≥1.5x volume, close within 3% of the
high, optional `vcp_max_contraction`, 2-ATR stop, 2R target) is a coarse "breakout from any base near highs" with
no geometry. `strategies/sr_breakout.py` (close > pivot resistance on ≥1.5x volume, measured-move target, level or ATR
stop) is the closest structural match for flat bases and ascending triangles, since `resistance_1` is the pivot
high. `features/patterns.py` already provides `vcp_contraction`, `base_len` and `breakout_52w`.

**Proposed module** (via `.claude/skills/add-strategy`): `strategies/base_breakout.py`, registered `enabled: false`,
with `variant ∈ {cup_handle, flat_base, flag}` and versioned params. Cup-handle defaults:
`prior_advance_min=0.30`, `cup_min_bars=35`, `cup_max_bars=325`, `cup_depth_min=0.12`, `cup_depth_max=0.33`,
`handle_min_bars=5`, `handle_max_bars=25`, `handle_depth_max=0.12`, `handle_upper_half=True`,
`handle_vol_ratio_max=1.0`, `breakout_vol_mult=1.4`, `max_extension=0.05`, `rs_rank_min=0.80`, `stop_mode="pct"`,
`stop_pct=0.07`, `target_pct=0.20`, `eight_week_rule=True`, `min_market_trend_state=1`. Flat base: `min_bars=25`,
`depth_max=0.15`, `prior_advance_min=0.20`. Flag: `pole_min` and `flag_max_bars=15` are **untaught numbers** except
for the HTF (0.90 / ≤40 bars). Treat them as research parameters and log every variant in `research/trials.py`
(deflated Sharpe in `research/metrics.py`) before enabling. **Point-in-time trap:** a pivot at bar i is only known at
i + width. Pattern geometry must be computed from confirmed pivots and the prior bar, or the backtest will "see" the
handle low before it exists.

### Discretionary (Claude review enums or human steps)
- Base **quality** (U vs V, handle wedging up or not, "spirit of the pattern"), **base count/stage** (1st-2nd vs 4th+),
  overhead supply and leadership/theme. These map to `agent` review enums (e.g. `base_quality ∈ {A,B,C}`,
  `base_stage ∈ {1,2,3,4+}`); the LLM never sets price levels.
- **CAN SLIM fundamentals** (EPS/sales acceleration, institutional sponsorship) need a point-in-time fundamentals feed
  keyed on filing date (CLAUDE.md rule 3). They are not in the current panel.
- **Zanger's intraday tape work** (probe fills, half-hour volume pace, sell within 20 minutes on a stall) needs
  intraday bars. `features/rvol.py` (`rvol_now`, intraday profile) is where a breakout-day volume-pace check belongs.
- The **partial-sell** (20-30% at +15-20%, or 40%/60% ATR targets) needs a scale-out hook. `should_exit` in
  `strategies/_base.py` is all-or-nothing today.
- Market exposure ramp after an FTD (Market School levels) is a portfolio-level rule for `risk/limits`, not a
  per-signal one.

---

## Sources
Primary - teachers and statistics
- https://www.chartpattern.com/ - Zanger Report home (newsletter/chatroom; audited-record claim)
- https://www.chartpattern.com/chart-patterns.cfm - Zanger pattern index
- https://www.chartpattern.com/cup-handle.cfm - Zanger cup-and-handle: 20-35% depth, 8-12 weeks, handle ~5% below high, 4 days-3 weeks, buy at handle top
- https://www.chartpattern.com/flat-base.cfm - Zanger flat base: horizontal, volume dry-up, trendline break on volume
- https://www.chartpattern.com/flags-pennants.cfm - Zanger flags and pennants
- https://www.chartpattern.com/ascending-triangle.cfm - Zanger ascending triangle
- https://www.chartpattern.com/10_golden_rules.html - "10 Golden Rules" (HTTP 404 at fetch; rule list known only from third-party summaries)
- https://www.cmcmarkets.com/en-gb/opto/world-record-breaking-trader-dan-zangers-tricks-of-the-trade - CMC Opto profile (HTTP 404 at fetch; content via sweep)
- https://thepatternsite.com/cup.html - Bulkowski cup with handle (rank 3/39, 5% failure, 54% rise, 913 trades, 1990-Mar 2024 review)
- https://thepatternsite.com/flags.html - Bulkowski flags (44% failure, 9% rise, stats 8/27/2020)
- https://thepatternsite.com/htf.html - Bulkowski high and tight flag
- https://thepatternsite.com/id75.html - Bulkowski chart pattern rank tables (8/24/2020)
- https://thepatternsite.com/FailureRates.html - Bulkowski failure-rate study (13,932 patterns, 1991-2008)
- https://www.thepatternsite.com/BestPatterns.html - Bulkowski best patterns (sweep)
- https://www.thepatternsite.com/studystudy.html - Bulkowski "study of studies" (sweep)
- https://www.thepatternsite.com/rank.html - Bulkowski ranking (sweep)
- https://thepatternsite.com/id84.html - Bulkowski page cited by evidence sweep (not re-fetched)
- Bulkowski, T., *Encyclopedia of Chart Patterns*, 2nd ed., Wiley 2005 (ISBN 0471668265), ch. 9 "Cup with Handle", Tables 9.1-9.5. Read from a third-party PDF upload of the chapter; link deliberately omitted (unauthorised copy). Cite the book.
- O'Neil, W. J., *How to Make Money in Stocks*, McGraw-Hill (1988 and later eds.). Not read directly; criteria via Bulkowski Table 9.1 and summaries below.

Secondary - O'Neil/IBD rules and practitioner notes
- https://en.wikipedia.org/wiki/CAN_SLIM - CAN SLIM criteria summary (sweep)
- https://discussion.fool.com/t/ibd-8-week-hold-rule/112549 - IBD 7-8% / 20-25% / 8-week rule quoted (sweep)
- https://discussion.fool.com/t/trading-ibd-stocks/104584?page=23 - IBD stocks board (sweep)
- https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker - FTD/distribution-day encoding (sweep)
- https://www.shortform.com/summary/how-to-make-money-in-stocks-summary-william-j-oneil - book summary (sweep)
- https://www.luxalgo.com/library/concept/flat-base/ - flat base (≥5 weeks, ≤15%) summary
- https://www.luxalgo.com/library/concept/cup-with-handle-base/ - cup-with-handle base summary
- https://www.luxalgo.com/library/concept/oneil-base-analysis/ - O'Neil base taxonomy summary
- https://traderlion.com/technical-analysis/the-flat-base-pattern/ - TraderLion flat base (HTTP 403 at fetch)
- https://tradingresourcehub.substack.com/p/nuances-behind-dan-zanger - Zanger rules compiled from 2000-2020 interviews (16 May 2026)
- https://www.financialwisdomtv.com/post/dan-zanger - Zanger profile (search result, not fetched)
- https://www.sahmcapital.com/news/content/from-10000-to-42-million-rejecting-complex-indicators-short-term-trading-legend-dan-zanger-creates-miracles-with-chart-patterns-2025-12-02 - Zanger profile, Dec 2025 (search result, not fetched)
- https://skillsmp.com/creators/mahmoud20138/tradecraft/plugins-tradecraft-skills-dan-zanger-breakout-strategy - third-party Zanger rule summary (sweep; low confidence)
- https://sozai.app/transcript/powerful-swing-trading-setup-high-tight-flag/ - Soreide HTF masterclass transcript (sweep)
- https://www.luxalgo.com/library/concept/high-tight-flag.md - HTF reference (sweep)
- https://pod.wave.co/podcast/the-traderlion-podcast-8e50b654-7b23-4b2d-aca4-50a775c117e3 - TraderLion Podcast (sweep)
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview - Moglen RS-line leadership (sweep)
- https://www.valuewalk.com/investors-business-daily-swingtrader/ - IBD SwingTrader review (sweep)

Evidence - academic and replications
- https://www.nber.org/papers/w7613 - Lo, Mamaysky & Wang, "Foundations of Technical Analysis" (JF 2000)
- https://www.cxoadvisory.com/technical-trading/classic-papers-returns-from-pattern-based-technical-analysis/ - CXO review of Osler 1998 and LMW 2000 (24 Oct 2006)
- https://ideas.repec.org/p/fip/fednrp/9414.html - Osler, NY Fed staff report (sweep)
- https://ideas.repec.org/a/oup/jfinec/v5yi2p243-265.html - Savin, Weller & Zvingelis, JFEc 2007 (sweep)
- https://papers.ssrn.com/abstract=3756587 - Jiang, Kelly & Xiu, "(Re-)Imag(in)ing Price Trends" (HTTP 403 at fetch; sweep)
- https://www.cxoadvisory.com/technical-trading/machine-assisted-stock-price-pattern-analysis/ - CXO on machine pattern analysis (sweep)
- https://datalearner.com/academic/journal-papers/0957-4174/volumes-and-issues/84/paper-detail/78518 - Leigh et al. 2002 bull-flag paper record (ESWA 23(2):155-159)
- https://easyswing.trading/performance - detector panel (7 Jul 2026): Cup & Handle 30% win, 0.5R, PF 1.57, 3,582 trades
- https://github.com/sofus-nl/swing-trading-strategies - open detector gates
- https://github.com/sofus-nl/swing-trading-strategies/blob/main/strategies/02-cup-and-handle.md - cup-and-handle gates and small-sample stats
- https://www.liberatedstocktrader.com/cup-and-handle-pattern/ - restates Bulkowski ("95% success"); not independent
- https://www.nber.org/papers/w20439 - Daniel & Moskowitz, "Momentum Crashes" (via doc 05)

2025-2026 context
- https://www.reddit.com/r/swingtrading/comments/1whb374/ - breakouts failing since March 2026 (sweep; reddit not fetchable)
- https://www.reddit.com/r/swingtrading/comments/1fy6c45/ - breakout thread (sweep)
- https://www.reddit.com/r/swingtrading/comments/1ukmnlh/ - breakout thread (sweep)
- https://www.reddit.com/r/swingtrading/comments/1rbg39l/ - breakout thread (sweep)
- https://www.reddit.com/r/Daytrading/comments/lag8zs/ - ATH breakout post, 2021 (sweep)
- https://www.reddit.com/r/algotrading/comments/1q25jpe/ - algo breakout thread (sweep)
- https://traderlion.com/the-tml-talk/the-tml-report-february-20-2026-follow-through-day-next-week/ - FTD call (title only)
- https://traderlion.com/the-tml-talk/the-tml-report-april-2nd-2026-follow-through-day-this-week/ - FTD call (title only)
- https://traderlion.com/the-tml-talk/the-tml-report-april-7th-2026-market-coiling-below-key-resistance/ - (HTTP 403 at fetch)
- https://newsletter.truemarketleader.net/p/market-outlook-6135 - TML newsletter, 19 Jan 2026 (market in wedge)
- https://markets.financialcontent.com/workboat/article/marketminute-2026-3-27-wall-streets-dark-friday-nasdaq-sinks-into-correction-as-five-week-rout-deepens - Nasdaq correction, 27 Mar 2026 (sweep)
- https://insights.dsij.in/dsijarticledetail/march-2026-when-everything-fell-a-market-defined-by-broad-based-selling-id010-56215 - March 2026 broad selling (sweep)
- https://www.janushenderson.com/corporate/article/market-moves-themes-that-mattered-september-2026/ - Sept 2026 breadth/yields (sweep)
- https://continuumeconomics.com/a/0a0d0277/ai-equities-correctionconsolidation - semis correction, 5 Aug 2026 (sweep)
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal - Jul-Oct 2025 breakout cluster (via doc 05)
- https://briefedup.substack.com/p/october-2026-breakouts - UK 12-month-range breakouts, 6 Oct 2026 (no pattern stats)
- docs/methods/05-qullamaggie-breakout.md, docs/methods/06-breadth-regime-filters.md - in-repo context (HTF stats, Oct 2026 breadth)
