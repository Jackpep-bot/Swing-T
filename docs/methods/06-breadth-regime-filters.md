# 06 - Breadth / regime filters (Zweig Breadth Thrust, % above 200-day, equal-weight vs cap-weight, Stockbee Market Monitor)

Written 2026-10-06 from the methods sweep entry `Breadth / regime filters` in
`docs/research-raw/methods-sweeps/merged_compact.json` plus primary-source checks. Items marked **[unverified]**
were seen only in search snippets or secondary summaries; the source page could not be fetched (403/404/bot wall).

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
  **[unverified]**).

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
- *Thrasher Analytics "Breadth Thrust Composite"*: a count of several price+volume thrust indicators across indices;
  read **0** on Aug 5 2026 (no thrust active).

**C. Participation level (state, not trigger).**
- % of S&P 500 above the 200-day: **> 50% = constructive**, below 50% = bearish (David Keller, StockCharts, Jul 30 and
  Aug 28 2026). Keller's three-part "healthy bull" test: MA-breadth above 50%, McClellan Oscillator above zero, and an
  expanding count of new 52-week highs (10-12% of members in a healthy bull vs 3-4% late Aug 2026).
- % above the 50-day is the fast line: EdgeRater's warning case was the slide from **63% to 22%** in six weeks after
  the mid-January 2026 peak reading.
- Minervini (MarketWatch interview via michaelsincere.com): a low % of stocks above their 200-day while the S&P makes
  new highs is a "bifurcated market"; he answered it by going 100% long the *index* (his May 8 S&P signal) while
  staying cautious on individual small/mid caps.
- Folk thresholds (search-snippet only, **[unverified]**): >= 70% above 200-day associated with ~+10.4% average 12-month
  forward return and ~86% positive; 85-90% readings cluster near tops; < 10% is a contrarian bottom zone.

**D. Stockbee Market Monitor** (secondary reproductions; the 2011 "How to use market breadth" post was not fetched -
treat exact column list as **[unverified]**):
- Daily counts: stocks up >= 4% on higher volume (ProRealCode reproduction: `(C-C1)/C1 >= 4%`, `V > V1`, plus a
  minimum volume) and stocks down >= 4%.
- **10-day cumulative ratio (10-DCR)** of 4%-up to 4%-down counts: **> 2 = favorable for swing longs**; in a bearish
  phase "a fresh bull move starts when 10-DCR first time crosses above 2"; well below 1 means breakouts fail and a
  technical bounce is more probable than a breakout campaign.
- **Primary breadth ratio** = count up >= 25% in a quarter / count down >= 25% in a quarter (a 1.2 reading was read as
  "bullish structure"); a 50-MA cumulative ratio > 2 is also used; shorter columns include 13% in 34 days.

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
- Stockbee: 10-DCR falling back under 1 (secondary; threshold **[unverified]**) = stop initiating breakouts.
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
S&P ~67% of the time; Stockbee treats 10-DCR > 2 as "swing longs allowed". Reasonable mechanical mapping: 0% new
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
6. **Near-miss ZBT**: line reaches 0.60-0.61 in 11-12 days (Mar/May 2023; the Nov 2025 "poised" episode) - a
   discretionary judgment call that the mechanical rule explicitly rejects.
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
- **Ryan Detrick (Carson), Leuthold Group** - Apr 2025 breadth-thrust notes (cited through Faber's post; not fetched).

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

**Peer-reviewed / out-of-sample.** No peer-reviewed study of the Zweig Breadth Thrust or of %-above-200-day timing was
found (two targeted searches). The academically supported neighbours are price-based regime filters (Faber 2007/2018;
Zakamulin; Antonacci's GEM with 1974-2011 in-sample and 1950-73 / 2012-18 out-of-sample - see method 28) and
multi-market breadth in Keller's PAA as reviewed by CXO Advisory: 13-ETF universe, 12-month SMA, 1971-1992 in-sample,
1993-2015 out-of-sample; PAA2 CAGR 10.4%, max drawdown -8.8%, Sharpe 1.00 vs 60/40 CAGR 8.2%, Sharpe 0.33, with
underperformance in the 1990s and post-2008. Volatility-based regime scaling (Daniel-Moskowitz 2016; Barroso and
Santa-Clara 2015) is the other peer-reviewed cousin (method 14).

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
6. **Thrust at the highs**: the Nov 2025 setup was within 5% of an all-time high, outside the historical sample.
7. **Narrowing can persist**: 2023-2025 ran three years with only 27-31% of S&P members beating the index while the
   cap-weighted index compounded; a breadth-gated book under-owned that tape.
8. **Discretionary creep**: "near-miss" reasoning, hand-picked analogs (SentimenTrader's critique of the 2009 analog),
   and divergence narratives are the usual ways breadth becomes a story instead of a rule.

---

## 2025-2026 fit
- **Apr 24-25 2025**: textbook ZBT (NYSE) plus a Nasdaq 3:1 thrust after the tariff crash; StockCharts, SentimenTrader,
  Leuthold/Faber all logged it; S&P was higher at 6 and 12 months, consistent with the table.
- **Late Nov 2025**: 10-day EMA "just below 60%" with the signal described as imminent (24/7 Wall St, Nov 28 2025;
  StockSavvyShay post) - whether the 0.615 cross printed inside the window is **[unverified]**; would have been the
  first thrust within 5% of an all-time high.
- **Jan-Feb 2026**: % above 50-day peaked at 63% mid-January then fell to 22% within six weeks (EdgeRater); EW rolled
  over while cap-weight held (events sweep).
- **Mar 20-Apr 6 2026**: NYSE ZBT setup (below 0.40 on Mar 20); Hill's Apr 3 note had nine days elapsed and one left -
  outcome **[unverified]**.
- **May 6 2026**: EdgeRater thrust day inside a "Stagflation Lite" tape with narrowing leadership; confirmation checklist
  not met at publication.
- **H1 2026**: EW +12.1% vs CW +10.2%; 46.3% of members beat the index; Mag 7 weight 33.4% but contribution -1.96%
  (Proactive Advisor, Jul 22 2026) - breadth-led regime, opportunity set is the 493.
- **Jul 30 2026**: 64% above 50-day, 69% above 200-day, McClellan Oscillator < 0, NDX Bullish Percent 30% (Keller).
- **Aug 5 2026**: Breadth Thrust Composite 0 while S&P broke out of consolidation (Thrasher).
- **Aug 28 2026**: 70% above 200-day but 54% above 50-day (from 70%), new highs 3-4% then 1%; Keller: "bull fatigue",
  red flag if the 50-day line loses 50%.
- **Sep 18 2026**: 43.2% of all US common stocks above 200-day; 31% above 50-day (thetrading.tools).
- **Oct 6 2026 (today)**: 48.5% above 10-day (+21 pts in 5 days), 26.9% above 50-day, 33.6% above 100-day, 39.7% above
  200-day across 4,806 stocks; fast/slow ratio 0.68. By the Keller 50% test the all-stock universe is in a bearish
  participation state while the S&P 500 subset was still > 50% in late August. A sharp 10-day breadth bounce from
  depressed 50-day breadth is exactly the pre-condition for a thrust setup; it is not a signal until the 10-day EMA
  rule prints.
- Fit summary: 2026 rewarded breadth-aware universe selection (EW over CW, scanning the 493) more than the thrust
  trigger itself, which fired at most twice and once at the highs. The participation dial has been the useful part.

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
  `momentum_burst`, `breakout_52w`: trade unless SPY is in a defined downtrend). `research/backtest.py::_RegimeLookup`
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
Critique / evidence
- https://www.investing.com/analysis/the-zweig-breadth-thrust-as-a-case-study-in-quantitative-analysis-267684 (Hui, Oct 2015)
- https://articles.stockcharts.com/article/articles-tac-2015-10-tom-mcclellan-zweig-breadth-thrust-signal (McClellan, 404 at fetch time)
- https://www.cxoadvisory.com/technical-trading/dual-momentum-with-multi-market-breadth-crash-protection (PAA breadth crash protection)
- https://quantifiedstrategies.substack.com/p/dual-momentum-investing-with-gary (404 at fetch time; see method 28)
- https://hedgefundalpha.com/strategies/is-gary-antonaccis-global-equity-momentum-strategy-robust/ (from sweep; not fetched)
Regime context 2026
- https://proactiveadvisormagazine.com/sp-500-update-market-breadth-improves-in-the-first-half-of-2026/ (Jul 22 2026)
- https://247wallst.com/investing/2026/06/10/rsp-vs-spy-does-equal-weight-beat-the-cap-weighted-sp-500/ and https://www.thetrading.tools/equal-weight-vs-cap-weight (RSP vs SPY; snippets)
- https://www.fxcm.com/eu/insights/the-2026-market-rotation-suggests-a-quiet-shift-with-loud-implications/ (early-2026 RSP vs SPY; snippet)
