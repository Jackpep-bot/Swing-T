# 06 - Breadth / regime filters (Zweig Breadth Thrust, % above 200-day, equal-weight vs cap-weight, Stockbee Market Monitor)

Written 2026-10-06 from the methods sweep entry `Breadth / regime filters` in
`docs/research-raw/methods-sweeps/merged_compact.json` plus primary-source checks. Items marked **[unverified]**
were seen only in search snippets or secondary summaries; the source page could not be fetched (403/404/bot wall).
Resume pass (same day): Stockbee Market Monitor rules verified on the 2010/2011 primary posts, Hill's 3x3 breadth
model added, Nov 2025 and Mar 2026 ZBT outcomes resolved (both near-misses), a 2025 peer-reviewed paper and
late-Sep/Oct 2026 breadth readings added, swing-engine strategy mapping refreshed against the current code.

**One line.** Not an entry system: a market-level gate that says *how much* long exposure a swing book should carry and
*when* to switch from defense to offense, by counting how many stocks participate (advances vs declines, % above a
moving average, 4%-day counts) rather than watching the cap-weighted index alone.

---

## Rules

### Universe / scan
Breadth is computed on a *population of stocks*, not on a price series. Which population matters:

| Variant | Population | Who |
|---|---|---|
| Original Zweig Breadth Thrust (ZBT) | NYSE advancing / declining issues (official exchange counts) | Zweig (1986 book), StockCharts `$NYAD`-style data |
| ZBT on S&P 500 / S&P 1500 ("ZBT1500") | index constituents, both exchanges | Arthur Hill / TrendInvestorPro |
| Nasdaq A/D-ratio thrust | Nasdaq issues | SentimenTrader |
| % of stocks above 50/200-day MA | S&P 500 members (Keller, Minervini commentary) or all US common stocks (~4,800 names at thetrading.tools) | StockCharts Mindful Investor, EdgeRater, thetrading.tools |
| Stockbee Market Monitor | broad all-stock universe; counts of names up/down 4% in a day, 25% in a quarter, 13% in 34 days | Pradeep Bonde (Stockbee), reproduced by Nitin Ranjan / ProRealCode |
| Equal-weight vs cap-weight | S&P 500 EW (RSP) vs cap-weight (SPY) | Proactive Advisor Magazine, 24/7 Wall St, thetrading.tools |

Scan output is a single daily regime vector, not a stock list. The stock list comes from whatever setup method the
trader runs (VCP, 52-week breakout, momentum burst, pullback, etc.); breadth decides whether and how hard to run it.

### Market filter (the method itself)

**A. Zweig Breadth Thrust (trend-start trigger).** Verified on StockCharts (Hill, Nov 2023; Mar 2025; Apr 3 2026),
SentimenTrader (Apr 25 2025), LuxAlgo and thetrading.tools:

- Indicator = 10-day EMA of `advances / (advances + declines)` (NYSE issues in the original).
- **Setup**: indicator closes below **0.40** (washed-out).
- **Signal**: indicator then closes above **0.615** within **10 trading sessions** of the setup. Slower recoveries do not
  count: Hill shows March 2023 (11 days) and May 2023 (12 days) as near-misses that were disqualified.
- Hill's second use (Mar 2025): a dip below 0.40 by itself is a short-term oversold reading that "can lead to a bounce",
  i.e. a tactical mean-reversion setup rather than a regime call.
- TrendInvestorPro added an exit condition "based on backtesting" (Apr 3 2026 article; the exit itself is paywalled -
  **[unverified]**). The free Apr 2025 article only names two families: exit on a break of prior reaction-low support
  (Oct 2023 / Jan 2025 / Apr 2025 lows) or "a trend-following indicator" (subscriber detail).
- Zweig's own record, as reported by LuxAlgo and thetrading.tools (book text not fetched): 14 signals 1945-1986 in
  *Winning on Wall Street* (1986), average gain 24.6% within 11 months.
- Canonical modern print (NYSE): 10-day EMA at 38% on Apr 10 2025, 61.7% at the Apr 24 2025 close (Sherwood News,
  Apr 25 2025; Ryan Detrick, Carson: "19 for 19" higher 6 and 12 months later since WWII). SPX close that day 5,485
  (Ter Schure via FXStreet, Apr 30 2025: 20th occurrence since 1940, +14.3% / +24.8% average at 6 / 12 months).
- *Near-miss variant* (Jay Kaeppel, SentimenTrader Apr 20 2026): treat a cross above **0.60** (not 0.615) after a
  sub-0.40 reading as a weaker but still positive signal: S&P 500 median 1-year return 15.07%, 92% win rate; the
  Nasdaq 100 had higher medians but one -35.08% loss (Mar 6 2002). SentimenTrader's Dec 2 2025 "recovery" study
  (< 0.40 to > 0.59 in 10 days, 16 cases in 60 years): 93% win rate at 1 year, average max drawdown -1.6%, with 1974
  and 2008 cited as bull traps.

**B. Companion thrusts** (used to confirm or substitute):
- *Nasdaq A/D-ratio thrust* (SentimenTrader, Apr 25 2025): Nasdaq advance/decline ratio above **3:1** on **3 of the
  last 10 sessions**.
- *Deemer "Breakaway Momentum"* (LuxAlgo library, TradingView reproductions): 10-day sum of NYSE advances >= **1.97 x**
  10-day sum of declines, using raw totals rather than a smoothed ratio, so it can fire on different days than ZBT.
- *Whaley breadth thrust*: thrusts in A/D and up-volume ratios over roughly week-long windows (LuxAlgo gives no exact
  numbers - **[unverified]**).
- *EdgeRater "thrust day"* (Chris White, May 6 2026): a multi-metric 90th-percentile day - 60% of stocks advanced with
  median +1%, 5.6% "Big Kahuna" ups and 15.8% "Little Kahuna" ups (Bollinger-based), 69.5% of stocks with up/down
  volume ratio > 1, 21-day median price change +6%. Confirmation checklist afterwards: A/D accumulation share back
  above **45%** (was 40.6%), 5-day SPX-outperformance share above **45%** (was 39.3%), and leadership (semis, hardware,
  electrical components) holding.
- *Nasdaq Breadth Thrust, Kaeppel version* (SentimenTrader Apr 16 2026): 10-day sum of Nasdaq advances divided by
  10-day sum of advances + declines closes at **>= 62%** (first in 12 months); fired **Apr 14 2026**; the Nasdaq 100
  historically led afterwards.
- *1.97 thrust on the S&P 1500* (Dean Christians, SentimenTrader Jul 29 2022): 10-day sum of S&P 1500 advancing issues
  >= 1.97 x 10-day sum of decliners; fired Jul 28 2022; 35 prior signals in 52 years, S&P 500 higher 12 months later
  97% of the time, max drawdown -5.6%; 8 bear-market cases, 100% higher at 6 and 12 months.
- *Thrasher Analytics "Breadth Thrust Composite"*: a count of several price+volume thrust indicators across indices;
  read **0** on Aug 5 2026 (no thrust active).

**C. Participation level (state, not trigger).**
- % of S&P 500 above the 200-day: **> 50% = constructive**, below 50% = bearish (David Keller, StockCharts, Jul 30 and
  Aug 28 2026). Keller's three-part "healthy bull" test: MA-breadth above 50%, McClellan Oscillator above zero, and an
  expanding count of new 52-week highs (10-12% of members in a healthy bull vs 3-4% late Aug 2026).
- % above the 50-day is the fast line: EdgeRater's warning case was the slide from **63% to 22%** in six weeks after
  the mid-January 2026 peak reading.
- **Arthur Hill's breadth model** (StockCharts SystemTrader, Oct 2018; same thresholds in his later work), run on each
  of the S&P 500, S&P MidCap 400 and S&P SmallCap 600 (about 1,500 operating companies, ~925 NYSE / ~575 Nasdaq):
  AD Percent 10-day EMA bullish above **+30%**, bearish below **-30%**; % above 200-day EMA bullish above **60%**,
  stays bullish until below **40%** (hysteresis "to reduce whipsaws"; 50% is only a mean-reversion watch level);
  High-Low Percent bullish above **+10%**, bearish below **-10%**. Each index group turns net bullish/bearish when
  **2 of 3** indicators agree; the nine signals together are the "weight of the evidence". Hill (May 23 2025): a
  thrust alone is not a bull market - % of S&P 1500 above 200-day "at the very least" needs to clear **50%** (it had
  been above 50% Dec 2023-Feb 2025 and broke below 40% on Mar 10 2025).
- Minervini (MarketWatch interview via michaelsincere.com): a low % of stocks above their 200-day while the S&P makes
  new highs is a "bifurcated market"; he answered it by going 100% long the *index* (his May 8 S&P signal) while
  staying cautious on individual small/mid caps.
- Folk thresholds (search-snippet only, **[unverified]**): >= 70% above 200-day associated with ~+10.4% average 12-month
  forward return and ~86% positive; 85-90% readings cluster near tops; < 10% is a contrarian bottom zone.

**D. Stockbee Market Monitor** (Pradeep Bonde; verified on "Understanding Market Monitor Part1", Aug 1 2010, and
"How to use market breadth to avoid market crashes", Aug 8 2011). Bonde calls it "a breadth based market timing
system" and says breadth cross-overs "signal safe periods for breakout trading".
- Scans (TC2000 syntax, volume in hundreds): 4% up = `100*(C-C1)/C1 >= 4 AND V >= 1000 AND V > V1` (i.e. >= 100k
  shares and more than yesterday); 4% down = the mirror with `<= -4`. Quarter / month scans: up or down >= 25% in a
  quarter, >= 25% in a month, >= 50% in a month, "34/13" = 13% in 34 days (a faster, noisier version of the quarter
  column), MMA+/MMA- moving-average alignment; minimum average dollar-volume filter on the longer scans.
- Daily 4% counts: up to 300 = normal; 300-500 high; **500-1,000 = very high buying pressure, "normally seen at
  beginning of a bullish turn"**; 1,000+ extreme. On the down side 1,000+ = extreme selling, after which bear-market
  rallies typically start. A cluster of 3-5 days with 300+ up-4% names is a bullish-momentum tell.
- **10-day ratio** = sum of 4%-up counts over 10 days / sum of 4%-down counts: **>= 2.0** = long-side swing trading
  favoured; "when market is in bearish phase first time ratio is 2 plus signals start of a bull move";
  **<= 0.50** = "start of a bearish move after a bull move" (go defensive / short side).
- **Primary indicator** = count up 25%+ in a quarter vs count down 25%+ in a quarter: bullish when up > down, bearish
  when down > up. Extremes: up-25% count **below 200** = extreme bearishness, "extremely bullish" for long-term buys
  (rallies from there are "extremely powerful"); below 500 = watch for reversal. Secondary: 50%-in-a-month count
  **above 20** = speculative excess, correction risk; below 3 = bullish.
- Followers (Nitin Ranjan 2022) also run a 10-day ratio on stocks crossing the 50-day MA with the same > 2 rule.

**E. Equal-weight vs cap-weight** (regime width): when RSP leads SPY the opportunity set is the "493"; when EW rolls
over while cap-weight holds, narrow and tighten (events sweep, Feb 2026 example). H1 2026: EW +12.1% vs CW +10.2%,
46.3% of members beat the index vs 26.9-30.5% in each of the prior three years (Proactive Advisor, Jul 22 2026).

**F. Price-based regime filters** (10-month SMA, 12-month absolute momentum) belong to method 28 (trend filter); the
multi-market breadth version is Keller's PAA: safe-asset share = number of the 13 ETFs below their 12-month SMA
divided by 12 / 9 / 6 (low / medium / high protection) - see Evidence.

### Entry
Breadth does not pick the stock. Practitioner sequence after a thrust: (1) treat the thrust day as the first day of a
new regime; (2) buy the setups the primary method already produces, favouring the groups that led into the thrust
(SentimenTrader found the S&P 500 tech sector the best performer in five of seven horizons after Nasdaq thrusts;
EdgeRater says trade "confirmed leaders ... with elite earnings quality"); (3) Hill: "entry is only half of the
equation" - plan the exit before adding size. Stockbee-style: start breakouts when 10-DCR crosses above 2, not before.

### Stop
Per-trade stops come from the setup method, not from breadth. The *regime* stop is the thing breadth owns:
- ZBT line falling back below **0.40** (Hill's oversold threshold) or the % above 50-day dropping under **50%** (Keller)
  = cut new entries and trim.
- Stockbee: 10-day 4% ratio at or below **0.50** = bear move starting; stop initiating breakouts (verified, 2011 post).
  Between 0.5 and 2 is a neutral zone where Bonde trades smaller and more selectively.
- Hill: % above 200-day back under **40%** (after a > 60% bull reading), or 2 of 3 indicators bearish per index.
- EdgeRater: when the "fingerprint" matches a prior narrowing top (Jan 2026), hold only names with institutional
  support and let the confirmation checklist decide.

### Exits / targets
Thrust statistics are measured at 3-, 6- and 12-month horizons (SentimenTrader: 6-month S&P gains in 20 of 20 since
1938; Nasdaq thrust 3-month 100% positive, 4- and 12-month one loss). For a swing book that translates into: keep the
risk-on dial up until a breadth invalidation (above), not until a price target. 24/7 Wall St (Nov 28 2025) notes
20-30% pullbacks *within* the first year after a signal have occurred, so the thrust is not a drawdown guarantee.

### Position sizing
Exposure, not per-trade risk, is what breadth scales. No teacher publishes a single ladder; the verified data points
are: Minervini 100% index on his May 8 signal with reduced single-stock risk; the summarized ZBT backtest held the
S&P ~67% of the time; Stockbee treats 10-day ratio >= 2 as "swing longs allowed" and <= 0.5 as defensive; Hill's
nine-signal tally is a natural 0-9 exposure score. Reasonable mechanical mapping: 0% new
longs when % above 200-day < 50% and no thrust; 50% when > 50% without thrust; 100% for N months after a thrust while
the fast line holds. Treat any such ladder as a parameter to backtest, not a published rule.

### Holding period
Regime-level: weeks to months (a thrust's statistical window is 6-12 months). Trade-level: inherited from the setup
method (3-5 days for momentum bursts, weeks for breakouts). The Apr 24-25 2025 thrust is the clean modern example: S&P
higher 6 and 12 months later, in line with the historical table (Meb Faber citing Leuthold: 16 signals since 1950, all
16 up at 6 and 12 months, average +23% a year later).

---

## Chart signatures
1. **The V with a wide base of participation**: index falls > 10%, NYSE 10-day EMA A/(A+D) sinks under 0.40, then the
   line goes near-vertical to 0.615+ inside two weeks while the index itself has only recovered part of the drop
   (Apr 2025; Mar/Apr 2009; the 2023 Nov signal).
2. **Three-day stampede**: > 70% of NYSE issues advancing three sessions in a row (Apr 2025, youtube sweep - secondary)
   or Nasdaq A/D > 3:1 on three of ten days.
3. **Bifurcation**: cap-weighted index at or near highs while % above 200-day is under 50% and new 52-week highs are
   3-4% of members (Keller Aug 28 2026; Minervini's "bifurcated market").
4. **Narrowing-top fingerprint**: % above 50-day peaks (63% mid-Jan 2026), A/D accumulation share and 5-day
   outperformance share both below 45%, then a six-week slide to ~22% (EdgeRater).
5. **Fast-vs-slow breadth gap**: ratio of (% above 50-day)/(% above 200-day) well under 1 (0.68 on Oct 6 2026 across
   4,806 US stocks: 26.9% vs 39.7%) = short-term trend broken beneath a still-standing long-term trend.
6. **Near-miss ZBT**: line reaches 0.59-0.61 inside or just outside the window (Mar/May 2023 per Hill; Nov 20-Dec 2025:
   0.393 low, peak above 0.59, no trigger; Mar 20-Apr 2026: no 0.615 cross) - a discretionary call the classic rule
   rejects; Kaeppel's 0.60 variant accepts it with weaker statistics.
8. **Stockbee stampede**: 500-1,000+ stocks up 4% on rising volume, 3-5 days in a row with 300+, and the 10-day ratio
   crossing 2 for the first time after a bearish phase.
7. **EW/CW crossover**: RSP:SPY ratio turning up from a multi-year low (RSP trailed SPY by 16.3% over three years as
   of Sep 25 2026, a reading lower than all but 1.7% of months since 1929 - search snippet, **[unverified]**).

---

## Who teaches it
- **Martin Zweig** - originator; the 0.40 -> 0.615-in-10-days rule as popularised in *Winning on Wall Street* (1986).
  Book text not fetched; rule verified through StockCharts, SentimenTrader, LuxAlgo and thetrading.tools.
- **Arthur Hill** (StockCharts "Art's Charts", TrendInvestorPro) - ZBT on NYSE, S&P 500 and S&P 1500; "two ways to
  use" (thrust vs oversold); exit-condition work (paywalled).
- **SentimenTrader** (Jason Goepfert, Dean Christians) - signal tables for ZBT, Nasdaq A/D thrust, 200-day breadth
  recoveries, "failed ZBT" studies.
- **Tom McClellan** (McClellan Financial) - critic of ZBT reliability post-2008 (via Cam Hui's summary); McClellan
  Oscillator as the companion breadth-momentum gauge.
- **Cam Hui** (Humble Student of the Markets) - "ZBT as a case study in quantitative analysis" (Investing.com, Oct 2015).
- **Walter Deemer** - Breakaway Momentum (1.97x 10-day advances/declines).
- **David Keller, CMT** (Sierra Alpha Research; StockCharts Mindful Investor) - % above 50/200-day with the 50% line,
  McClellan Oscillator, new-high counts, Nasdaq-100 Bullish Percent.
- **Chris White** (EdgeRater) - thrust-day percentiles and the Jan 2026 / May 2026 fingerprint comparison.
- **Andrew Thrasher** (Thrasher Analytics) - Breadth Thrust Composite.
- **Pradeep Bonde** (Stockbee) - Market Monitor (4% days, 10-DCR, 25%-in-a-quarter ratio); reproduced by Nitin Ranjan
  and ProRealCode users.
- **Mark Minervini** - % above 200-day as the correction / bifurcation warning layered on his Trend Template.
- **Meb Faber / Gary Antonacci / Wouter Keller** - price-based and multi-market breadth regime filters (10-month SMA,
  absolute momentum, PAA "breadth" crash protection).
- **Ryan Detrick (Carson), Leuthold Group** - Apr 2025 breadth-thrust notes (Detrick's "19 for 19" verified via
  Sherwood News; Leuthold cited through Faber's post).
- **Jay Kaeppel, Jason Goepfert, Dean Christians** (SentimenTrader) - Nasdaq Breadth Thrust (62%), the 0.60 near-miss
  study, 1.97 S&P 1500 thrust, issues+volume "holy grail" thrust (Mar 31 2023).
- **Brooke Thackray** (BNN Bloomberg columnist) - % above 200-day and 20%-off-highs counts, Oct 2026.

---

## Evidence

**Practitioner signal tables (strong on consistency, weak on sample size).**
- SentimenTrader Apr 25 2025: ZBT -> S&P 500 up at 6 months in 20 of 20 cases since 1938; 12-month "outstanding
  returns and consistency". Nasdaq A/D 3:1-in-3-of-10 thrust -> 3-month 100% positive, one loss at 4 and 12 months.
- Leuthold via Meb Faber (May 2025): 16 ZBT signals since 1950, all up at 6 and 12 months, average +23% at 12 months.
- 24/7 Wall St (Nov 28 2025): ~20 thrusts since 1950; average S&P return +1.3% (1 week) to +23.3% (1 year); 100%
  positive at 6 and 12 months; caveat that the pending Nov 2025 signal would be the first ever within 5% of an
  all-time high.
- Search-snippet (page 403, **[unverified]**): "previous 17 signals, S&P up 100% of the time over 12 months, median
  +22.9%"; "all 6 graded thrusts 2010-2019 higher 12 months on, average +14.9%".
- Note the counts disagree (16 / 17 / ~20 / "fewer than 30") because data vendor, EMA seeding, and NYSE issue
  definitions differ - itself evidence of parameter fragility (Hui 2015).

**Backtest as a timing system (secondary summary, low-medium confidence).** A ZBT long-only test on the S&P
summarised in search results (TrendInvestorPro page returned 403): exposure 67%, 53% of signals winners, average gain
more than 3x average loss, compound annual return *below* buy-and-hold, higher risk-adjusted return and much lower
maximum drawdown. Reading: ZBT is a drawdown-control overlay, not an alpha source.

**Critique.** Cam Hui (Investing.com, Oct 11 2015) compiled: Tom McClellan's post-2008 grading of 11 "great", 4 "meh",
12 "horrible" signals; Rob Hanna (Quantifiable Edges) bullish since 1970; Hui's own post-war count 9 / 3 / 1. Causes of
disagreement: StockCharts vs NYSE-published breadth, EMA weighting choices, 2011 and 2013 signals flagged without a
clean threshold cross, tiny sample, obsolete 1930s data. Hill (Nov 2023): NYSE-only breadth "is missing" Nasdaq
stocks, hence ZBT1500. SentimenTrader has a dedicated "a failed Zweig Breadth Thrust - does it matter" study (not
fetched).

**Level-of-participation evidence.**
- SentimenTrader May 20 2020 (200-day breadth recovery, S&P 500 since 1990, 40-day correlation analogs > 0.90):
  1-2 months "mostly positive but not exceptional", 3-12 months higher probability of gains, 12-month 100% win rate but
  average return "about in line with random" - a modest upside bias, "not a slam-dunk".
- Keller Jul 30 / Aug 28 2026 and EdgeRater May 2026 are commentary, not tests.

**Peer-reviewed / out-of-sample.** No peer-reviewed study of the Zweig Breadth Thrust itself was found. Closest
academic work: Yu, Webb and Lin (2025), "The Use of Index-Specific Market Breadth and Index-Over-Moving-Average
Indicators in Stock Trading Strategies", *Journal of Investing* 34(2):83-101 - tests market-breadth and TRIN ratios and
% of members above 20/50/200-day averages as momentum vs reversal signals in monthly timing schemes, and whether
breadth from a broader index predicts better than breadth from the index itself; abstract concludes only that "some
technical strategies may be effective" (full results paywalled - **[unverified]** which ones). CXO Advisory ("Can the
Stock Market Have Bad Breadth?", Sep 11 2017; RSP-SPY, NYSE A/D, up/down volume, 52-week highs-lows, 2003-2017):
"little or no indication that breadth metrics lead SPY return at any horizon up to 21 trading days"; monthly leads of
1-12 months are mildly positive but depend on 2008-09 and weaken sharply when the five worst crash months are removed;
NYSE up/down volume was "most promising". Implication for swing trading: breadth is a slow regime variable, not a
next-week predictor. The academically supported neighbours are price-based regime filters (Faber 2007/2018;
Zakamulin; Antonacci's GEM with 1974-2011 in-sample and 1950-73 / 2012-18 out-of-sample - see method 28) and
multi-market breadth in Keller's PAA as reviewed by CXO Advisory: 13-ETF universe, 12-month SMA, 1971-1992 in-sample,
1993-2015 out-of-sample; PAA2 CAGR 10.4%, max drawdown -8.8%, Sharpe 1.00 vs 60/40 CAGR 8.2%, Sharpe 0.33, with
underperformance in the 1990s and post-2008. Volatility-based regime scaling (Daniel-Moskowitz 2016; Barroso and
Santa-Clara 2015) is the other peer-reviewed cousin (method 14).

**Data-definition disagreement, documented.** Mar 31 2023: Goepfert (SentimenTrader) reported a NYSE ZBT plus a
volume thrust ("holy grail", third ever with 1982 and 2019); Hill counted Mar 2023 as an 11-day near-miss. Apr 2025:
NYSE fired (61.7%), Hill's S&P 1500 version fired, but an FXStreet-cited source had the S&P 500 version only at 0.58
and one NYSE series at 61.42 on day 10 **[unverified]**; thetrading.tools' ~4,750-stock all-US universe records its
last completed thrust on Jan 8 2019 - i.e. the broad-universe version did not fire in Apr 2025 at all, and reads 0.47
(neutral) on Oct 6 2026. The same day can be a signal or not depending on the issue list.

**Verdict.** Breadth thrusts have a consistent but small-sample record as *bull-start* markers; participation levels
are a reasonable risk dial; neither is a validated standalone edge. Use as an exposure governor on top of a tested
setup method, and judge it by drawdown reduction, not by return.

---

## Pitfalls
1. **Sample size**: fewer than ~20 clean ZBTs in 75 years; one or two failures change the statistics completely.
2. **Data-definition drift**: NYSE issue counts include funds and preferreds; vendors' A/D series and EMA seeding
   differ; 11- vs 10-day near-misses flip the signal (2023 twice, Nov 2025). Decide the data source and lock it.
3. **Universe mismatch**: NYSE-only misses Nasdaq growth leaders (Hill); a self-built breadth from your own ingested
   universe is a different indicator with no historical table - backtest it fresh.
4. **Survivorship**: computing historical % above 200-day on today's constituents inflates past breadth; use
   point-in-time membership and delisted names (Massive `active=false`, EODHD constituents add-on).
5. **Lag**: by the time a thrust prints the index is often 8-12% off the low; the edge is in the next 3-12 months,
   not the next 3 days. Swing traders who buy the thrust day with tight stops get chopped (Apr-May 2025 tariff
   headlines; SentimenTrader warned of near-term volatility on the day it fired).
6. **Thrust at the highs**: the Nov 2025 setup was within 5% of an all-time high, outside the historical sample
   (it ended as a 0.59 near-miss, so the sample is still untested at the highs).
7. **Narrowing can persist**: 2023-2025 ran three years with only 27-31% of S&P members beating the index while the
   cap-weighted index compounded; a breadth-gated book under-owned that tape.
8. **Discretionary creep**: "near-miss" reasoning, hand-picked analogs (SentimenTrader's critique of the 2009 analog),
   and divergence narratives are the usual ways breadth becomes a story instead of a rule.
9. **Thresholds do not transfer across universes**: 0.40 / 0.615 were set on NYSE issues (a list that also includes
   closed-end funds, preferreds and ADRs, so its composition differs from an operating-company universe). A 4,750-stock all-US universe missed the Apr 2025 thrust entirely
   (thetrading.tools). A self-built universe needs its own calibrated thresholds or percentiles.

---

## 2025-2026 fit
- **Apr 24-25 2025**: textbook ZBT (NYSE) plus a Nasdaq 3:1 thrust after the tariff crash; StockCharts, SentimenTrader,
  Leuthold/Faber all logged it; S&P was higher at 6 and 12 months, consistent with the table.
- **Late Nov 2025**: setup at 0.393 on Nov 20; 10-day EMA ~0.595 by Nov 28 (24/7 Wall St). **Resolved: no signal** -
  SentimenTrader (Dec 2 2025) logged a rise "to above 0.59" inside 10 days but no 0.615 cross; it would have been the
  first thrust within 5% of an all-time high.
- **Jan-Feb 2026**: % above 50-day peaked at 63% mid-January then fell to 22% within six weeks (EdgeRater); EW rolled
  over while cap-weight held (events sweep).
- **Mar 20-Apr 6 2026**: NYSE ZBT setup (below 0.40 on Mar 20); Hill's Apr 3 note had nine days elapsed and one left.
  **Resolved: classic ZBT failed** (Kaeppel, SentimenTrader Apr 20 2026: no 0.615 cross in 10 days), but the
  **Nasdaq Breadth Thrust (62%) fired Apr 14 2026** (Kaeppel, Apr 16 2026). Two near-misses in five months.
- **May 6 2026**: EdgeRater thrust day inside a "Stagflation Lite" tape with narrowing leadership; confirmation checklist
  not met at publication.
- **H1 2026**: EW +12.1% vs CW +10.2%; 46.3% of members beat the index; Mag 7 weight 33.4% but contribution -1.96%
  (Proactive Advisor, Jul 22 2026) - breadth-led regime, opportunity set is the 493.
- **Jul 30 2026**: 64% above 50-day, 69% above 200-day, McClellan Oscillator < 0, NDX Bullish Percent 30% (Keller).
- **Aug 5 2026**: Breadth Thrust Composite 0 while S&P broke out of consolidation (Thrasher).
- **Aug 28 2026**: 70% above 200-day but 54% above 50-day (from 70%), new highs 3-4% then 1%; Keller: "bull fatigue",
  red flag if the 50-day line loses 50%.
- **Sep 18 2026**: 43.2% of all US common stocks above 200-day; 31% above 50-day (thetrading.tools).
- **Sep 28 2026**: Goldman Sachs (via Crypto Briefing, secondary): median S&P 500 stock 16% below its 52-week high with
  the index +14% YTD; fewer than half of members above the 200-day while the index is near highs - "rare since 1990",
  clustered almost entirely in 1998-2000. Sentiment indicator -0.9.
- **Oct 1 2026**: Thackray (BNN Bloomberg): 46% of S&P 500 above 200-day; 43% of S&P 500 members (38% of TSX) 20%+
  below their 52-week highs; more 52-week lows than highs near index highs - bifurcation signature #3.
- **Oct 6 2026 (today)**: 48.5% above 10-day (+21 pts in 5 days), 26.9% above 50-day, 33.6% above 100-day, 39.7% above
  200-day across 4,806 stocks; fast/slow ratio 0.68. By the Keller 50% test the all-stock universe is in a bearish
  participation state while the S&P 500 subset was still > 50% in late August. A sharp 10-day breadth bounce from
  depressed 50-day breadth is exactly the pre-condition for a thrust setup; it is not a signal until the 10-day EMA
  rule prints (all-US ZBT line 0.47, neutral). Hill-style read: S&P 500 % above 200-day ~41-46% is inside the 40-60
  no-man's land after falling from ~70-73% in August - the bull signal from > 60% is still technically alive until
  < 40%, which is the line to watch.
- Fit summary: since Apr 2025 the classic NYSE ZBT has produced one signal and two near-misses (Nov 2025, Mar-Apr
  2026); the Nasdaq thrust filled the Apr 2026 gap. H1 2026 rewarded breadth-aware universe selection (EW over CW,
  scanning the 493); since August the participation dial has been the most useful piece, flagging the late-1990s-style
  bifurcation (index near highs, < 50% above 200-day, median stock -16%). For a long-only swing book in Oct 2026 the
  gates say: reduced size, leaders only, wait for a Stockbee 10-day ratio > 2 or a thrust before pressing.

---

## Automatability

**Fully mechanical (deterministic from EOD data):** A/(A+D) 10-day EMA with the 0.40 / 0.615 / 10-session rule;
Deemer 1.97x; Nasdaq 3:1-in-3-of-10; % above 10/50/100/200-day; new-high/new-low counts; Stockbee 4%-day counts,
10-DCR, 25%-in-a-quarter ratio; RSP:SPY ratio and its moving-average state; the Keller 50% line; PAA breadth fraction.
All are cross-sectional aggregates of per-symbol features the engine already computes.

**Discretionary today:** choosing the population (NYSE vs S&P 500 vs all-stock), near-miss handling, divergence
narratives, EdgeRater's leadership judgment, sector tilt after a thrust, the exposure ladder.

**swing-engine mapping (as of docs/STATUS.md 2026-10-06):**
- Existing gate: `features/regime.py` produces `trend_state` (close > SMA50 > SMA200 with rising SMA50 = 1, mirror = -1)
  and `vol_regime`, and when SPY is passed, broadcasts `market_trend_state` / `market_vol_regime` to every row.
  `strategies/_base.py::market_ok` applies `min_market_trend_state` (default `TREND_FLAT` in `pullback_trend`,
  `momentum_burst`, `breakout_52w`, `sr_breakout`, `sr_bounce`: trade unless SPY is in a defined downtrend;
  `TREND_DOWN`, i.e. no market gate, in `rsi2_meanrev` and `insider_cluster`). `research/backtest.py::_RegimeLookup`
  and `ops/nightly.py::_regime` feed that dict per day; `research/ranker.py` includes `trend_state` / `vol_regime` as
  features. This is a price-based (method 28) filter, not breadth.
- Missing: a cross-sectional breadth aggregator. Proposed `features/breadth.py` producing one row per session from the
  long panel and broadcast as `market_*` columns (same pattern as `add_market_regime`):
  `pct_above_200 = mean(close > sma_200)`, `pct_above_50`, `ad_ratio_10d_ema = ewm(mean(ret_1d > 0) over 10d)`
  (universe A/D, not NYSE official), `zbt_state` (0 / setup / signal with the 10-session counter), `deemer_10d`
  (sum(ret_1d>0)/sum(ret_1d<0) over 10d), `up4_count` = sum of existing `burst_4pct`, `down4_count` (add the mirror of
  `burst_4pct`), `dcr_10d = rolling 10d sum(up4)/sum(down4)`, `q25_ratio = count(ret_63d >= 0.25)/count(ret_63d <= -0.25)`,
  `nh_pct = mean(close >= high_52w)`. Feature-contract rules apply: pure pandas, no look-ahead (aggregate only rows with
  ts <= session), NaN during warm-up, deterministic. Then add `min_pct_above_200`, `require_dcr_gt` style params to
  `_base.py` next to `min_market_trend_state`, and surface the vector in `swing scan`/nightly reports.
- Stockbee mapping is exact: `features/patterns.py::burst_4pct` already encodes Bonde's 4%-up scan (c/c1 >= 1.04,
  v > v1, v >= 100,000 = TC2000 `V >= 1000` in hundreds). The 10-day ratio thresholds (>= 2 long, <= 0.5 defensive),
  the 300 / 500 / 1,000 daily-count bands and the 25%-quarter primary ratio are absolute counts tuned to a full US
  universe of several thousand names; on a smaller ingested universe use ratios (unaffected) but rescale the count
  bands to percentages of the universe.
- Gate wiring by strategy: `momentum_burst`, `breakout_52w`, `sr_breakout` (breakout family) - the natural consumers
  of a `dcr_10d >= 2` / `pct_above_200` gate (Bonde: breadth cross-overs mark "safe periods for breakout trading");
  `pullback_trend`, `sr_bounce` - Hill-style hysteresis on `pct_above_200` (on > 60, off < 40); `rsi2_meanrev` - leave
  ungated or use Hill's oversold use of ZBT < 0.40 as an *entry booster*; `insider_cluster` - leave ungated.
  `research/ranker.py` can take the breadth vector as features so the model learns the interaction instead of a
  hard gate.
- Calibrate thresholds on the engine's own universe (percentiles of its own history) rather than copying 0.40 / 0.615,
  because the broad-universe ZBT did not fire in Apr 2025 (see Evidence).
- Universe for breadth must be the point-in-time ingested universe (`data.universe.build_universe` keeps names active
  at `as_of`), otherwise survivorship inflates every historical reading.
- Data limits: Massive free tier gives 2 years of history, so thrust backtests (events decades apart) are impossible
  in-house; the Starter / Developer / Advanced tiers (5 / 10 / 20+ years) or an external NYSE A/D series are needed to
  reproduce the published tables. The participation dial (% above 200-day, 10-DCR) can be validated on 2 years.
- Monitor: `monitor/rules/market_wide_suppression.py` already suppresses single-name alerts on circuit-breaker / FOMC /
  CPI days; a breadth state is the natural daily input for an "exposure dial" line in the morning report, not a P2 alert.
- Evaluation per `docs/gates.md`: judge any breadth gate by drawdown reduction and deflated Sharpe of the gated
  strategy versus ungated, with the full trial count logged in `research/trials.py`; do not expect it to raise CAGR.

---

## Sources
Primary / practitioner
- https://articles.stockcharts.com/article/articles-arthurhill-2023-11-the-zweig-breadth-thrust-trigg-609/ (Hill, Nov 2023: rule, 2023 near-misses, ZBT1500)
- https://articles.stockcharts.com/article/articles-arthurhill-2025-03-two-ways-to-use-the-zweig-brea-495 (Hill, Mar 2025: thrust vs oversold uses)
- https://articles.stockcharts.com/article/zweig-breadth-thrust-sets-up-how-to-identify-a-stampede-in-upside-participation/ (Hill, Apr 3 2026: Mar 20 2026 setup)
- https://trendinvestorpro.com/zweig-breadth-thrust-exit-strategy/ (exit-strategy backtest; 403 - stats seen in snippet only)
- https://sentimentrader.com/blog/a-cluster-of-breadth-thrusts-bodes-well-for-stocks (Apr 25 2025: ZBT + Nasdaq 3:1 thrust tables)
- https://sentimentrader.com/blog/recovery-in-200-day-average-breadth-shows-long-term-promise (May 20 2020: 200-day breadth recovery analogs)
- https://sentimentrader.com/blog/a-double-zweig-breadth-thrust-just-as-we-hit-the-worst-six-months (Apr 30 2020: double thrust, seasonality)
- https://sentimentrader.com/blog/a-failed-zweig-breadth-thrust-does-it-matter (not fetched)
- https://edgerater.com/blog/2026-05-06-market-notes-thrust-day (White, May 6 2026: thrust-day metrics, Jan 2026 fingerprint)
- https://articles.stockcharts.com/article/three-breadth-indicators-that-could-decide-the-next-market-move/ (Keller, Jul 30 2026)
- https://articles.stockcharts.com/article/mindfulinvestor-2026-08-weakening-market-breadth-could-signal-trouble-ahead/ (Keller, Aug 28 2026)
- https://thrasheranalytics.substack.com/p/breadth-update-852026 (Thrasher, Aug 5 2026)
- https://www.thetrading.tools/market-breadth (all-US-stock breadth, Oct 6 2026 readings) and https://www.thetrading.tools/manuals/zweig-breadth-thrust
- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini (Minervini on bifurcation)
- https://world.hey.com/nitinranjan/weekly-index-check-cw18-2022-88b02ca6 and https://finallynitin.substack.com/p/stockbee-market-monitor (Stockbee Market Monitor reproductions)
- https://www.prorealcode.com/topic/market-monitor/ (4%-day code reproduction)
- https://www.luxalgo.com/library/concept/breadth-thrusts.md (Zweig / Deemer / Whaley definitions)
- https://x.com/StockCharts/status/1915856032959549529 (ZBT fired Apr 25 2025) and https://x.com/MebFaber/status/1920163146204930213 (Leuthold table)
- https://247wallst.com/investing/2025/11/28/this-rare-perfect-market-indicator-just-flashed-a-major-bull-market-is-coming/ (Nov 2025 setup, at-the-highs caveat)
- https://stockbee.blogspot.com/2010/08/understanding-market-monitor-part1.html (Bonde, Aug 1 2010: scans, "breadth based market timing system")
- https://stockbee.blogspot.com/2011/08/how-to-use-market-breadth-to-avoid.html (Bonde, Aug 8 2011: 4% count bands, 10-day ratio 2.0 / 0.5, 25%-quarter primary)
- https://world.hey.com/nitinranjan/weekly-index-check-cw18-2022-88b02ca6 (follower use of 10-day ratio on 50-MA crosses)
- https://articles.stockcharts.com/article/articles-arthurhill-2018-10-systemtrader-a-rules-based-approach-for-when-to-cry-uncle/ (Hill 3x3 breadth model: +/-30%, 60/40, +/-10%, 2 of 3)
- https://articles.stockcharts.com/article/articles-arthurhill-2025-05-moving-from-thrust-signals-to-882/ (Hill, May 2025: S&P 1500 % above 200-day must clear 50%)
- https://articles.stockcharts.com/article/articles-arthurhill-2025-04-zweig-breadth-thrust-dominates-460/ (Hill, Apr 2025: exit via support or trend indicator)
- https://sherwood.news/markets/unusual-technical-indicator-with-perfect-track-record-sends-buy-signal-on-us (Apr 25 2025: 38% -> 61.7%, Detrick 19 for 19)
- https://www.fxstreet.com/news/sp-500-trust-the-thrust-202504301444 (Ter Schure, Apr 30 2025: 20th since 1940, +14.3% / +24.8%)
- https://sentimentrader.com/blog/zweig-breadth-thrust-recovery (Dec 2 2025: Nov 2025 near-miss, 0.59 recovery study)
- https://sentimentrader.com/blog/a-failed-zweig-breadth-thrust-does-it-matter (Kaeppel, Apr 20 2026: Mar 2026 failure, 0.60 variant stats)
- https://sentimentrader.com/blog/the-historical-implications-of-a-nasdaq-breadth-thrust (Kaeppel, Apr 16 2026: NBT 62%, fired Apr 14 2026)
- https://sentimentrader.com/blog/here-come-the-breadth-thrust-buy-signals (Christians, Jul 29 2022: 1.97 S&P 1500 thrust, 35 signals / 52 years)
- https://sentimentrader.com/blog/the-holy-grail-of-breadth-thrusts-has-triggered (Goepfert, Apr 3 2023: Mar 31 2023 issues+volume thrust)
- https://www.thetrading.tools/zweig-breadth-thrust (all-US universe ZBT: 0.47 neutral Oct 6 2026; last thrust Jan 8 2019)
- https://www.mcoscillator.com/learning_center/weekly_chart/watching_for_a_zweig_breadth_thrust_signal/ (McClellan, Nov 2025 setup; 403 at fetch)
- https://www.tradingview.com/script/M3p31Lpg-Zweig-Breadth-Thrust-ZBT-Complete-Validation/ (open-source ZBT with setup / near-miss / expired states)
Critique / evidence
- https://researchwith.montclair.edu/en/publications/the-use-of-index-specific-market-breadth-and-index-over-moving-av/ (Yu, Webb, Lin 2025, Journal of Investing 34(2):83-101)
- https://www.cxoadvisory.com/?p=30213 (CXO, Sep 11 2017: "Can the Stock Market Have Bad Breadth?")
- https://seekingalpha.com/article/4778098-bull-market-indicated-by-zweig-breadth-thrust-signal-trust-it (Apr 2025 data disagreement; 403 at fetch)
- https://www.investing.com/analysis/the-zweig-breadth-thrust-as-a-case-study-in-quantitative-analysis-267684 (Hui, Oct 2015)
- https://articles.stockcharts.com/article/articles-tac-2015-10-tom-mcclellan-zweig-breadth-thrust-signal (McClellan, 404 at fetch time)
- https://www.cxoadvisory.com/technical-trading/dual-momentum-with-multi-market-breadth-crash-protection (PAA breadth crash protection)
- https://quantifiedstrategies.substack.com/p/dual-momentum-investing-with-gary (404 at fetch time; see method 28)
- https://hedgefundalpha.com/strategies/is-gary-antonaccis-global-equity-momentum-strategy-robust/ (from sweep; not fetched)
Regime context 2026
- https://cryptobriefing.com/goldman-sachs-sp500-breadth-dotcom-low/ (Sep 28 2026: Goldman median stock -16% from high; secondary)
- https://www.bnnbloomberg.ca/investing/opinion/2026/10/01/us-and-canadian-stock-markets-have-bad-breadth-brooke-thackray/ (Thackray, Oct 1 2026: 46% above 200-day)
- https://proactiveadvisormagazine.com/sp-500-update-market-breadth-improves-in-the-first-half-of-2026/ (Jul 22 2026)
- https://247wallst.com/investing/2026/06/10/rsp-vs-spy-does-equal-weight-beat-the-cap-weighted-sp-500/ and https://www.thetrading.tools/equal-weight-vs-cap-weight (RSP vs SPY; snippets)
- https://www.fxcm.com/eu/insights/the-2026-market-rotation-suggests-a-quiet-shift-with-loud-implications/ (early-2026 RSP vs SPY; snippet)
