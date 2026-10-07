# 09 - Momentum burst (Stockbee 4% breakout, 3-5 day hold)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Tags: "(primary)" = Pradeep Bonde's own blog post,
quoted from the page text fetched this run; "(secondary)" = third-party notes, scripts or replications;
"(unverified)" = could not be checked against a primary source in this run. The members site (stockbee.biz),
the bootcamp material and most videos are paywalled or video-only, so the blog is the citable rule book.*

**One line.** Scan all day for stocks up 4%+ on volume above yesterday's (or up $0.90+ open-to-close for stocks above
$40). Buy only the few that break out of a quiet, orderly 3-20-day base after a narrow or down day, are not already up
2-3 days in a row, sit early in a young trend and close near the high. Stop at the low of the entry day, take profits
into strength and be out within 3-5 days. Expect 5-8% per winner and run it as a high-frequency process (200-1,000
trades a year). Trade it only while Market Monitor breadth (counts of stocks up/down 4%) says breakouts are working.

**Premise as taught.** "Stocks move in momentum bursts of 3 to 5 days. During this 3 to 5 days period stock would go
up 8 to 20% (lower priced stock can even have bursts of up to 40%). Higher priced stocks above 40 tend to move in
momentum bursts of 5 to 25 dollars." Every burst "start[s] with a range expansion"; "In most cases the momentum dies
down in 3 to 5 days" (Stockbee, 31 Dec 2013, primary). Bullish sequence: range-expansion day, up day, up day, pullback,
end of momentum; occasionally a 5-day or "in rare cases" an 8-10-day burst (28 Jan 2014, primary).

**Lineage.** Bonde says he worked out the scan in 1999-2000 with a finance PhD by looking at "every 25% plus kind of
move in a month or quarter for 40 years of data using Compustat database". They found that "in majority of the
cases those 25% moves started with a 4% range expansion move", and he had used `c/c1>=1.04 and v>v1 and v>100000`
"for over 14 years" by 2014 (13 Jan 2014, primary; the study itself is unpublished). The idea is related to
Toby Crabel's range-contraction-to-expansion work (NR4/NR7) and is the short-horizon sibling of Bonde's other core
setup, the Episodic Pivot. Kullamaggie's "sell 1/3-1/2 after 3-5 days" rule (doc 05) comes from the same school.

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| 4% breakout scan | `c/c1>=1.04 and v>v1 and v>100000` on "US Common Stocks" (Telechart/TC2000), meaning close up >=4% vs prior close, volume above yesterday's and above 100k shares. Some posts write `v>=100000` | 13 Jan 2014, 23 Jan 2017, 13 Jul 2017, 21 May 2015, 18 Nov 2015 (primary) |
| Where it works best | "works best on small and mid caps and lower priced stocks" | 18 Nov 2015 (primary) |
| Dollar breakout (high-priced stocks) | 2014: "stocks up 1$ plus on 100000 volume (good at finding b/o on high priced stocks above 40)". 2017: `c-o>=.90 and v>100000`, i.e. **close minus today's open** >= $0.90 | 30 Jul 2014; 13 Jul 2017 (primary) |
| Range-expansion scan | "stocks whose range today is bigger than the range in last 3 days and that was not up more than 2% as of a day before" | 30 Jul 2014 (primary) |
| Range expansion, defined | "a day which is up bigger than last 5 to 10 days bars" (2013); "a day that is bigger than previous 3 to 5 days move" (2015) | 31 Dec 2013; 21 May 2015 (primary) |
| Ranking | Scans run "throughout the day" and are sorted with "Trend Intensity to narrow down focus to few good candidates" | 30 Jul 2014 (primary) |
| Anticipation watchlist scans | **Double Trouble:** `c/minl252>=1.8 and minv3.1>=100000` with today's change between -1% and +1%. **TI65:** `avgc7/avgc65>1.05 and minv3.1>100000` with today's change between -1% and +1%. The two lists are merged and cut to 3-5 names with pre-computed entry prices | 14 Aug 2014 (primary) |
| 5-day movers scans | `c/c5>=1.08 and c>=3 and minv3.1>=100000` and `c-c5>=5 and c>=3 and minv3.1>=100000` | Tikam Singh Alma notes, 26 Aug 2024 (secondary) |
| "Breakout 1M Base" scan | `close(1)/min(21)<=1.1 AND close/max(21)>=0.9 AND close/close(1)>=1.04 AND volume>200000 AND volume/volume(1) AND sma(50,volume)*close>2000000`, sorted by `close/min(63)`. Credited to @PradeepBonde; the `volume/volume(1)` term appears truncated, probably `>1`. **It has no close-near-high clause**, although the methods sweep said it did | fintwits scan index, dated 2023-03-07, Canada list (secondary) |
| Float / price | "Low float below 25 million is good. Below 10 million float leads to explosive moves"; sub-$5 stocks "tend to make very explosive moves of 40% kind in 3 to 5 days"; high short interest also makes bigger moves | 4 Jan 2014; 21 May 2015 (primary) |
| 2024 universe guidance | Stocks above $100 for "smoother moves"; small caps under $1B in biotech, technology and consumer discretionary; new traders should use market caps under $10B with news catalysts. Daily scan: up or down 20%+ in 5 days; weekend scan: up 50%+ in 2 months | TraderLion Conference 2024 via Retail Trader's Repository, 25 Sep 2024 (secondary) |
| Selectivity | The quality guidelines eliminate "95% or more of 4% b/o" | 21 May 2015 (primary) |
| Frequency | 500-1,000 setups a year long and short (2014); 1,000-5,000 (Jan 2014); 5,000-10,000 3-5-day setups a year counting both sides (2013); he expects to take 200-1,000+ trades a year | 4 Jan 2014; 13 Jan 2014; 31 Dec 2013 (primary) |

**Setup-quality checklist (the real filter).** Each item appears in several primary posts dated 4 Jan 2014,
14 Jan 2014, 17 Jan 2014, 30 Jul 2014, 18 Nov 2015, 21 May 2015 and 23 Jan 2017:
1. **Prior day narrow-range or negative.** "The day prior to range expansion day will be narrow range day or
   negative day." Narrower is better, and a series of narrow-range days is better still.
2. **Not already running.** "Buy range expansion if stock is not up 3 days in a row" (2014-2017; "small range days up
   3 days is ok"). The 2024 version is stricter: "Stock should not be up 2 days in a row" (the "2" in 2LYNCH). Also
   skip names that were up 8-40% in the 2-3 days before the trigger (2015).
3. **Quiet base.** 3-20 days of consolidation (2014 identify post). "5 to 10 day consolidation" (17 Jan 2014). 3-10
   days for anticipation (Aug 2014). At least 3 days with no prior momentum burst (14 Jan 2014). The 2024 version
   prefers bases under 10 days; for bases over a month it adds a **catalyst** plus a **volume surge of 1.5-2x the
   50-day average volume** ("2LYNCH + CV", secondary).
4. **No 4% breakdowns** during the consolidation, or "No 4% b/d in last 3 to 5 days" (30 Jul 2014).
5. **Linear, orderly prior leg.** Avoid "drunken man walk" volatility. The consolidation should be orderly and on
   low volume.
6. **Close at or near the high** on the breakout day ("preferred"). Community scripts code this as a close in the top
   30% of the bar (secondary).
7. **Volume above the prior day.** In the ABTL example, volume was "significantly higher than volume in preceding 8 to
   10 days" (13 Jan 2014).
8. **Young trend.** "The breakout should be first to third setup since start of the move"; first and second
   pullbacks are preferable; "extended rallies are vulnerable to correction and b/o failure" (2017). Buying a stock
   that is 6 months into a run and near its all-time high "will likely hasten your death as a trader" (17 Jan 2014).
9. **No fundamentals and no catalyst required.** Traders "do not get involved with other aspects of the company like
   profit, valuation, insider buying" (13 Jan 2014). Tracking news does help get in early.

*2LYNCH (2024 TraderLion talk via F4VS notes, secondary):* 2 = not up 2 days in a row; L = trades linearly;
N = the day before is negative or narrow; C = consolidation is orderly, low-volume and contracting; H = closes near
the high. **The "Y" is not defined in those notes** (readers asked about it in the comments). "Young trend", item 8
above, is the likely meaning **(unverified)**.

### Market filter
- **What it is for.** The setup fails "near market turns where in short period lot of breakouts fail. The bullish
  breakout trade needs to be avoided during fast selling phases in market" (28 Jan 2014, primary). A stock's own
  trend is *not* a filter: bursts happen "over 50 ma / under 50 ma / over 200 ma / under 200 ma" (2 Jan 2015;
  26 Feb 2021, primary). The filter is breadth. He also gauges market trend with a Guppy multiple moving average
  (post title "How to gauge market trend using Guppy MMA", Jan 2025; video, not transcribed). "Stocks move momentum bursts in bear market but the magnitude... is
  small" (16 Jan 2014).
- **Stockbee Market Monitor (MM).** Defined in the 8 Aug 2011 post; scans repeated 1 Aug 2014 (primary):
  - Universe: US common stocks with a liquidity floor. Daily **4% up** = `(100*(C-C1)/C1)>=4 AND V>=100000 AND V>V1`
    (TC 12.4 version; the older TC7 version uses `V>=1000`, apparently in 100-share units). **4% down** is the
    mirror image.
  - **25% up/down in a quarter**, measured from the 65-day min or max close, with `AVGC20*AVGV20>=250000`. Also
    **25% and 50% up/down in a month** (20 days, `C20>=5`) and **13% up/down in 34 days**.
  - **10-day ratio** = sum of daily 4%-up counts over 10 days / sum of 4%-down counts over 10 days.
  - Readings: daily 4%-up counts "up to 300 normal", "300 to 500 high", "500 to 1000 very high (normally seen at
    beginning of a bullish turn)", "1000 plus extreme". "At beginning of a bull move you will see a cluster of 3 to 5
    big buying days of 300 plus."
  - **10-day ratio: "2 plus readings are good for swing trading on long side"; ".5 or less readings are good for
    swing trading on short side"**. The first reading of 2+ during a bearish phase signals the start of a bull move,
    and a reading below 0.5 after a bull run signals the start of a bearish move.
  - Primary trend: bullish while 25%-up-in-a-quarter > 25%-down-in-a-quarter. Readings below 200 are extremes.
- **2024 shorthand:** "When the majority of the columns are green, it is a good time to buy breakouts. When any of
  the first few columns are red, you will most likely get choppy market conditions" (TraderLion 2024 via F4VS,
  secondary).
- **2025-2026 additions (primary):** a "20% 5 Day Study" TC2000 tab (4 Sep 2025). Its exact definition is
  members-only **(unverified)**; on 20 Jul 2026 Bonde read it as "20% of the study on the bullish side is at 15". The
  daily "Situational Awareness" question is whether breakouts are likely to work; if not, whether breakdowns are; if
  not, which setups are ("SIPS, reversals, and select EP9") (24 Jul 2026). Breakouts work during breadth thrusts:
  "back-to-back 300-plus days" of fund buying (23 Jul 2026).
- Size by regime too: "I take smaller risk positions if market direction is uncertain. Similarly I risk less when
  market is in extreme zone" (8 Aug 2014, primary).

### Entry
- **Reaction (breakout) entry.** "Buy on first day of breakout as soon as it starts breaking out" (2 Jan 2015).
  Scans run "from 9:30 onward"; "Best breakout candidate typically show up in first 30 minutes" (13 Jul 2017). Enter
  as soon as a qualifying setup appears "to capture rest of the days move". **End-of-day scanning with next-day
  entry is explicitly allowed** (18 Nov 2015). All primary.
- **Anticipation entry.** "Find a point from where stock is likely to start explosive momentum burst and buy 1 minute
  and 1 cent before the breakout" (2 Jan 2015). In practice he pre-calculates trigger prices for 3-5 watchlist names
  and places orders or alerts at those levels (14 Aug 2014).
- **Never late.** "If you are buying a stock on 3rd or 5th day of swing you are starting with low probability entry"
  (4 Sep 2014). He recommends identifying at least 500 swing-start days before trading the setup.
- Realistic slippage he concedes: "By the time you enter on breakout day the stock might be up 4 to 10%, so you will
  not be able to capture that part" (28 Jan 2014).

### Stop
- **Low of the entry day.** "If I enter a breakout I put my stop at low of the entry day" (30 Jul 2014). "That
  logically makes our stop the low of entry day" (18 Nov 2015). Restated in Jan and Jul 2017 (primary). Example:
  entry 83, low of day 81.50 (RH, 8 Aug 2014).
- **Breakeven fast.** "As soon as stock goes 4 to 5% above entry you should move stop to break even. This should be
  done intraday itself" (18 Nov 2015).
- **Fade rule.** "If stock starts to fade gain after entry exit same day" (13 Jul 2017).
- Bonde concedes gap risk: the stop math "assumes... stock will not gap down significantly below your stop"
  (8 Aug 2014).
- Note-taker version: exit "if loss > 8%" (Tikam Alma, 26 Aug 2024, secondary).

### Exits and targets
The 13 Jul 2017 rules (primary), which he labels "exit guidelines for swing trade not absolute rules":
| Condition | Action |
|---|---|
| Same day or next day up **8%+** | Sell **50%** and move the stop to **$0.25 below the day's high** |
| Day 3 | "Exit at least 50% of position on third day at close"; from day 3 trail the stop $0.25 below the high |
| Gap up **20%+** on the next day or day 3 | Exit pre-market or at the open |
| No follow-through within 3 days | Exit or move the stop to breakeven |
| Open profit > 8% | Protect it "aggressively" |
| Any day | Stop at the entry-day low until it is moved |

Older versions (primary): "Exit after 3 to 5 days"; "Exit if position gives abnormal profit in one day of 10%
plus (at least part exit and move stop to protect rest)" (30 Jul 2014). "Once stock is up 3 to 10 days in a row
exit in to strength... intraday as many big gains can fade by end of the day" (18 Nov 2015).

**Expected payoff (as stated).** Average 5-8% per trade (28 Jan 2014; 8 Aug 2019) or 5-10% (31 Dec 2013), from
8-20% bursts. Target 8-20% on 4% breakouts and "5 to 20 dollars move in 3 to 10 days" on dollar breakouts
(13 Jul 2017). "Even if 50% of your trades work you can still make decent money" (16 Jan 2015). A follow-through
should show "4 to 5% plus magnitude on second or third day" (31 Dec 2013).

### Position sizing
- **Percent-risk model.** "I risk anywhere from .25 to 4% on a trade... But most trades are around .25% to 1% risk"
  (8 Aug 2014). The process post gives ".25% to 2% per trade" (30 Jul 2014). Shares = capital x risk% / (entry - low
  of day). His TC2000 formula is `100000/100/(c-l)` for 1% risk with a low-of-day stop. Because the stop is tight, a
  1% risk can mean "55% of account... invested", and he can be "fully invested in 3 or 4 positions".
- **Scaling up.** Only after "100 to 200 trades with 2:1 profit and 50% kind success rate" should risk rise to 1-2%
  per trade (28 Jun 2014). Bonde stated a 2014 record of "60% of trades... positive" with a worst loss of 0.59% of
  equity (8 Aug 2014). Both are self-reported.
- Note-taker version: "Extremely conservative .25% risk per trade", "absolutely zero leverage" (Tikam Alma, 2024,
  secondary).

### Holding period
3-5 trading days is the design. Up to 8-10 days in rare bursts. 3-10 days for dollar breakouts and for stocks in a
"momentum phase" (2016: "series of momentum bursts moves lasting 3 to 20 days"). "If you keep holding after the 3 to
5 days period, you would often see the stock ends up giving up all the burst gains" (31 Dec 2013, primary).

---

## Chart signatures
- **Base before the trigger.** 3-20 bars (ideally 5-10) of tight sideways action or a shallow, orderly pullback. A
  run of narrow-range bars, often inside days or dojis (Alma's 2025 study: inside bars in 86-93% of days -3 to -1,
  secondary). Volume dries up and there are no -4% bars inside the base.
- **Day before the trigger.** Narrow-range or red.
- **Trigger bar.** A wide-range bar up 4% or more (or $0.90+ open-to-close on stocks above $40). Its range is larger
  than any of the prior 3-10 bars, volume is above yesterday's (better: well above the 8-10-day norm, or 1.5-2x the
  50-day average after long bases), and it closes in the top ~30% of the bar.
- **Context.** A linear prior leg (smooth staircase); 1st-3rd breakout of a young uptrend; not 6 months into a run
  pinned at all-time highs. Anticipation names show TI65 (7-day avg close / 65-day avg close) > 1.05, or a close at
  least 80% above the 252-day low ("Double Trouble"), plus a +/-1% day inside a tight range.
- **Healthy follow-through.** Day 2 and day 3 are up, one of them by 4-5% or more. Then a pullback or sideways drift.
  Variants: day 2 is an inside day or a red day, then the burst resumes.
- **Failure.** No follow-through by day 3, an intraday fade of the trigger-day gain, or a close back inside the base
  or under the trigger-day low. Many failures at once is the breadth warning.
- **Tape.** MM 4%-up counts above 300 on several days; 10-day ratio at or above 2; quarterly 25%-up count above
  25%-down.
- **Bearish mirror.** A 4%-down range expansion after a weak bounce, traded only in an established downtrend lasting
  10+ days.

---

## Who teaches it
- **Pradeep Bonde ("Stockbee").**
  - Free blog: stockbee.blogspot.com, with rule posts from 2013-2021 and situational-awareness posts through July
    2026. Members site: stockbee.biz, with a daily morning Situational Awareness Zoom (5 Jan 2024; 5 Jan 2021) and
    published TC2000 tabs (4 Sep 2025).
  - X: @PradeepBonde (credited on the fintwits scan index). The YouTube channel is referenced on the blog (13 Jul
    2017); the @Stockbeevideos handle comes from the methods sweep **(not re-verified this run)**.
  - Bootcamps: 13-15 Nov 2026 in Las Vegas, billed as the "last-ever Bootcamp happening on the West Coast", $1,000
    rising to $1,200 from 9 Oct 2026. The syllabus includes "Start of Swing based on momentum burst", "Various kinds
    of SOS" and "Situational awareness for Swing trading using MM and 20% study" (blog post, 17 Sep 2026).
  - Talks: 2024 TraderLion Conference; The Friendly Bear podcast (19 Sep 2024); Investors Underground "Trading Takes"
    (3 Jul 2024).
  - He claims "two Market Wizards have come from Stockbee school", citing a forthcoming Market Wizards book
    (5 May 2026; 11 Jun 2026). The names are not given in the post text.
- **@mhp (Stockbee.biz member).** Bonde says this member traded the method "completely mechanically", with "custom
  developed software", and posted a 10-year equity line (up to 6 bursts a day, 1,000 shares each, 3-day hold)
  (28 Jan 2014). The backtest is not public **(unverified)**.
- **Note-takers and explainers:**
  - F4VS, *A Retail Trader's Repository*: momentum-burst rules from the TraderLion 2024 talk (25 Sep 2024), plus a
    stock-examples post.
  - Tikam Singh Alma (Substack): process notes (26 Aug 2024) and a 1,227-event study (18 Jun 2025).
  - Paulius Juozaitis, *Trends and Breakouts*: Stockbee page, last modified 22 Jul 2026. It explicitly says audited
    records are not public.
- **Code reproductions:**
  - TradingView: "Stockbee Screener - Momentum Burst & Episodic Pivot Scanner" (mericourt; includes TI65 >= 1.05,
    close >= 70% of range, prior day <= 2%), "StockBee MB Bullish" (lukebrod; princemraj), and the LuxAlgo library
    mirrors.
  - tradermonty `claude-trading-skills` `stockbee-momentum-burst-screener`: grades setups A / A- / B / Watch-only /
    Rejected with failure filters. The authors say it is "not a signal service" and publish no validation.
- **Downstream.** Kristjan Kullamaggie's breakout partial-sell at day 3-5 and his opening-range entries descend from
  this school (see doc 05). His Episodic Pivot is Bonde's term.

---

## Evidence

### Self-reported (primary, unaudited)
- "100k has compounded to 789k using this kind of method if you take every trade I take in last 5 years"
  (30 Jul 2014).
- "14 years of full time trading profitably... never a negative year"; in 2014, "60% of trades are positive" with a
  worst loss of 0.59% of equity (8 Aug 2014).
- Origin claim: the 1999-2000 Compustat study of 25%+ moves (13 Jan 2014). **Caveat:** this conditions on the
  outcome. A high P(4% day | big move) says nothing about P(big move | 4% day). Most 4% days are noise, which is why
  his own filters remove "95% or more" of them.
- The @mhp mechanical equity line exists only as a description in a 2014 post.

### Independent tests (secondary)
| Study | Design | Result |
|---|---|---|
| Tikam Singh Alma, "4% Momentum Burst - Detailed Research" (18 Jun 2025) | 1,227 events from S&P 500 + NIFTY750, 2020 to Jun 2025. Trigger: close >= 1.04 x prior close, close > open, volume > prior day. 3-5-day forward window. **No stops, no costs, none of the quality filters** | **5-day win rate 46.8%, average 5-day gain +0.88%, 12.8% reached +10% within 5 days.** The same piece also reports "82.31% success (>=10% gain in 3-5 days)", which contradicts the 12.8% figure; treat that number as an error. Trigger-day volume averaged ~1.93x normal, and pre-trigger days were dominated by inside bars and dojis. A separate Indian-market run of 336,869 signals over 1-10% thresholds favoured 3.5-4.5% triggers |
| EasySwing.trading performance panel (updated 7 Jul 2026) | 17 mechanical detectors on ~2,000 US stocks, 5-year walk-forward, no fees | **No momentum-burst / 4%-breakout detector is included.** The nearest relative, "ROC Breakout", shows PF 1.26, 32% win rate, 8-day average hold over 120,823 trades. Context only |
| tradermonty skill; TradingView scripts | Screeners | No performance published |
| Trends and Breakouts (Jul 2026) | Review | "independent audited performance records in the public domain are limited" |

**Bottom line on testing.** No public, cost-inclusive, walk-forward backtest of the *filtered* rule set was found.
The only raw-trigger study suggests the unfiltered 4% day is roughly a coin flip with a small positive drift (+0.88%
over 5 days, gross). That is too thin to survive 20 bps per side plus slippage on small caps. Any edge has to come from
the filters (quiet base, close near high, young trend, no recent breakdown), the exits and the breadth gate. Those are
exactly the parts nobody has published tests for.

### Academic backdrop (not tests of this setup)
- **Short-term reversal is the default.** Stocks with the highest returns over the prior week or month underperform
  next week/month (Jegadeesh 1990, *JF*; Lehmann 1990, *QJE*). Gutierrez & Kelley, "The Long-Lasting Momentum in
  Weekly Returns" (working-paper PDF fetched; published in *JF* 2008), confirm that the long-minus-short extreme-week
  portfolio **loses in the first two weeks** and then turns to continuation over the following year. A raw 3-5-day
  hold after a big up move sits squarely in the reversal window.
- **Volume and turnover flip the sign.** Medhat & Schmeling, "Short-term Momentum" (*RFS*, Mar 2022; US common
  stocks 1963-2018): among **high-turnover** stocks, last month's winners keep winning; among low-turnover stocks they
  reverse. Gervais, Kaniel & Mingelgrin, "The High-Volume Return Premium" (*JF* 2001): stocks with unusually high
  daily or weekly volume outperform over the following month. Both support the volume half of the trigger. They are
  monthly-horizon results, not 3-5-day ones. Conrad, Hameed & Niden (1994, *JF*) found the opposite at weekly horizons
  for high-transaction stocks **(citation from the standard literature, not re-fetched)**.
- **News vs no-news.** Chan (2003, *JFE*) and Savor (2012, *JFE*): large price moves *with* information drift, and
  those *without* it reverse, mostly in smaller, illiquid stocks. Bonde says no catalyst is needed. The evidence
  favours bursts that have one, which matches his own 2024 "C + V" requirement for long bases.
- **Attention and herding.** Barber, Huang, Odean & Schwarz (*JF* 2022): stocks that retail crowds pile into (e.g.
  Robinhood top movers) underperform afterwards (cited via the evidence sweep). A naive top-gainers scan is an
  attention screen.

### Reading the evidence
This is a plausible, well-specified microstructure idea with strong anecdotal support and many followers. There is
no public statistical proof, and the raw trigger has a documented headwind. It should be treated as a
**candidate-generation step** that needs filters, plus a **process** that needs a breadth gate. It should not be
treated as a standalone edge. That matches swing-engine's current `enabled: false` setting.

---

## Pitfalls
1. **Trading the raw scan.** The 4% scan "throws a wide net"; his filters remove 95%+ of hits. The unfiltered trigger
   is roughly a coin flip before costs (Alma 2025).
2. **Late entry.** Entering at the trigger-day close, or the next open, gives away 4-10% of a move that averages
   8-20%. Against a low-of-day stop that is often 5-8% wide, reward-to-risk on a 5-8% average gain falls toward 1:1.
   Intraday entry in the first 30 minutes is part of the method, not a detail.
3. **Chasing day 3.** Buying a stock already up 2-3 days in a row is the "bag holder" entry (17 Jan 2014).
4. **Holding past the burst.** Gains are usually given back after day 3-5. A stock that has not followed through by
   day 3 is out.
5. **Regime blindness.** Failures cluster near market turns, in fast selling phases and in range-bound tapes. "A good
   breakout will look as good as it did under better market conditions, but then fail to follow through"
   (20 Jul 2026). Losses are correlated, so many stops hit in the same week.
6. **Costs and turnover.** 200-1,000 trades a year in small and mid caps means spreads, slippage and fees decide the
   result. The engine's gates.md assumes 20 bps per side for non-large caps, before SEC/TAF fees.
7. **Low-float, sub-$5 names.** These are where the 40% bursts happen, and also where offerings, halts, pump schemes
   and meme squeezes happen. 4% days driven by social attention tend not to follow through (Barber et al.). Gaps
   through the low-of-day stop are common.
8. **Rule drift.** "Not up 3 days" (2014-2017) became "not up 2 days" (2024). The base is "3-20 days" in one post,
   "5-10" in another and "<10" in 2024. 100k volume vs 200k. Lock one versioned rule set before testing, or the trial
   count balloons.
9. **Outcome-conditioned evidence.** The Compustat origin story and "every big winner started with a 4% day" are
   hindsight statistics.
10. **Discretion is part of the edge.** "Traders like me trade the method using discretion. I do not take every
    setup" (28 Jan 2014). Words like "linear", "orderly" and "A-quality" are judgement calls. Bonde says it takes
    studying "5,000, 6,000, 10,000 breakouts" before trading it.
11. **Sizing illusions.** Tight low-of-day stops let 1% risk mean a 50%+ position. A gap down through the stop on a
    concentrated position is the tail risk he acknowledges.
12. **Marketing context.** Performance claims sit next to bootcamp and membership sales and are unaudited.

---

## 2025-2026 fit
- **Bonde's own read (primary, July 2026).** "We remain in a range-bound market." "Breakouts are unlikely to have
  follow-through here till a breadth thrust happens." His focus was "EP EP9 (very selectively) DEP" and SIPS for day
  trades (20 Jul 2026). Breakouts work when funds produce "back-to-back 300-plus days" (23 Jul 2026). Under the
  method's own regime rule, summer 2026 was a stand-aside period for momentum-burst longs. Whether a thrust happened
  in Aug-Sep 2026 could not be confirmed: no blog posts after the 17 Sep bootcamp notice, and MM data is
  members-only **(unverified)**.
- **Small caps lagged.** Q3 2026: S&P 500 +2.03%, Nasdaq +2.47%, Dow -2.70%, **Russell 2000 -7.52%**, 10-year yield
  +88 bp to 5.29%. The gains were "narrowly driven" by AI mega-caps while "market breadth deteriorated" (First
  Financial Trust, 1 Oct 2026). The 4% scan "works best on small and mid caps", so its home turf was the weakest
  segment of the market.
- **Windows that did fit.** The 24-25 Apr 2025 post-tariff-crash breadth thrust (Zweig thrust plus a Nasdaq 3:1
  thrust; see doc 06) is exactly the "cluster of 3 to 5 big buying days of 300 plus" pattern. Clean breakouts
  clustered in Jul-Oct 2025 in AI, biotech and semis (Financial Wisdom TV survey via doc 05). The momentum factor then
  stalled in Q4 2025 (+0.77% vs value +8.34%; TMX via the sweep). Feast-or-famine by regime is the expected
  signature.
- **Market-structure changes.**
  - FINRA RN 26-10 removed the pattern-day-trader designation and the $25k minimum, effective **4 Jun 2026**
    (phase-in to 20 Oct 2027). Small margin accounts can now take the method's same-day exits (sell half into an
    8%+ day, exit fades the same day) without day-trade counting.
  - Retail flow is heavy (broker estimates ~35% of 2026 equity volume), 0DTE options dominate, and meme bursts recur
    (e.g. a +25% day on a WallStreetBets campaign in Jun 2026, per the events sweep). The likely result is more 4%
    days without follow-through, especially in low-float names. This is an inference from the sweep, not a test.
- **Still taught.** The Nov 2026 bootcamp syllabus keeps "Start of Swing based on momentum burst" as a module, and
  2026 TradingView and AI-skill reproductions keep appearing. The method is alive and practised. No 2025-2026
  performance numbers for it were found.
- **Verdict.** Valid only behind a breadth gate. In a narrow, mega-cap-led tape with small caps falling, the method
  says to sit out or trade very selectively. Turn it on after a breadth thrust: a cluster of 300+ 4%-advancer days
  and a 10-day ratio of 2 or more.

---

## Automatability

### Mechanical (code it; every number a versioned param)
| Element | swing-engine mapping |
|---|---|
| 4% trigger | **Exists**: `burst_4pct` in `features/patterns.py` (`BURST_CLOSE_RATIO=1.04`, `v>prev_v`, `BURST_MIN_VOLUME=100_000`), an exact match to the 2014-2017 scan |
| Dollar breakout | **Add** `dollar_bo` = `close - open >= 0.90 and volume > 100_000` (versioned constants) for stocks above $40 |
| Range-expansion variant | **Add** `range_exp_3` = today's `high-low` > max of the prior 3 bars' ranges and `prior ret_1d <= 0.02` |
| Close near high | **Exists**: `close_pos` (`features/cross_section.py`). Add param `min_close_pos` (0.7) |
| Prior day narrow or negative | `prior_ret_1d <= 0` OR an NR flag. **Add** `nr7` / `prior_range_rank` (prior bar's range is the smallest of N). `inside_day` exists |
| Not up 2-3 days | **Exists**: `up_days_3` (current `max_up_days=2` matches 2LYNCH's "2") |
| Quiet base 3-20 bars | **Add** `bars_since_burst` (via `bars_since(burst_4pct)` in `patterns.py`, needs >= 3) and a base-tightness measure such as `max(high,N)/min(low,N)-1` over 5-20 bars. `vcp_contraction`, `bb_width_20` and `range_pct` exist |
| No 4% breakdown | **Add** `breakdown_4pct` (mirror flag) and a rolling count over 3-5 bars that must be 0 |
| Volume | `volume > prev_volume` (in the flag); `rvol_day` (vs prior 20-day average) >= 1.5 for bases over a month, per the 2024 "CV" rule |
| Young trend / momentum universe | **Add** `ti65 = sma_7/sma_65` (>= 1.05) and `dt_252 = close/min(low,252)` (>= 1.8). Count of bursts since the 63-day low <= 3 |
| Market Monitor gate | **Add a cross-sectional breadth feature** (e.g. `features/breadth.py`): daily counts of 4%-up and 4%-down (same 100k-volume and v>v1 rules) across the full universe, `mm_ratio_10d`, and 25%-quarter up/down counts. Pass them in the `regime` dict next to `market_trend_state`. Gate longs on `mm_ratio_10d >= 2`. Doc 06 proposes the same data. Needs full-universe daily bars (the Massive grouped-daily ingest in STATUS round 3) |
| Stop | **Exists**: `stop = low - stop_atr_buffer*atr_14` with buffer 0 = entry-day low |
| Exits | **Exists**: time stop via `max_hold_days` (5; read by `research/backtest.py` `STRATEGY_HOLD_PARAM`). **Missing**: 50% at the day-3 close; +8% same/next day -> sell half and trail $0.25 under the high; breakeven at +4-5%; exit at the open on a 20%+ gap. These need a scale-out hook (`should_exit` is all-or-nothing) and a stop ratchet in the round-3 position manager |
| Sizing | `risk/sizing.py` with `risk_per_trade_pct` of 0.25-1.0 (he mostly uses 0.25-1). Note that `max_position_pct: 10` will usually bind. A 1% risk with a ~5% low-of-day stop wants a 20% position, so the effective risk becomes ~0.5% |
| Costs | `docs/gates.md` cost model (20 bps per side for non-large caps plus SEC/TAF); mandatory given the turnover |

**Gaps in the current `strategies/momentum_burst.py`** (it is close to the raw scan, which explains the "weak
standalone evidence" note in settings.yaml):
1. `abs(prior_ret_1d) <= max_prev_move` rejects a prior **down** day of more than 2%, but a negative prior day is
   Bonde's *preferred* precondition. The primary range-expansion rule is one-sided ("not up more than 2%"). Use
   `prior_ret_1d <= max_prev_move`.
2. It has no close-near-high, no base, no no-breakdown and no young-trend filters, which are the filters that remove
   95% of hits.
3. The market gate is SPY `trend_state >= 0`, not breadth. Bonde's stock rules use no MA trend, and his breakout
   gate is MM breadth. He has also posted on gauging the *market* trend with a Guppy MMA (Jan 2025 post; "Guppy"
   TC2000 tab), so keep the SPY trend as a secondary check.
4. Exits are a pure 5-day time stop plus a 2R reference target. The day-3 partial, the 8% strength sale and the
   breakeven ratchet are missing.
5. Entry is at the trigger close. The method enters intraday, and EOD-to-next-day entry is allowed but changes
   whether the stop is the trigger-day low or the entry-day low. Make it a param (`stop_ref: trigger_low|entry_low`).
6. The universe floors in `settings.yaml` (price >= $5, avg volume >= 500k) exclude the sub-$5 / low-float bursts.
   That is a sensible, deliberate deviation, consistent with the small-cap track's warn/fade posture.

Suggested params for a v2 (all new, versioned): `prior_ret_max=0.02` (one-sided), `min_close_pos=0.7`,
`base_min_bars=3`, `base_max_bars=20`, `no_breakdown_lookback=5`, `max_up_days=2`, `min_ti65=1.05` (optional),
`mm_ratio_min=2.0`, `partial_day=3`, `partial_frac=0.5`, `strength_exit_pct=0.08`, `gap_exit_pct=0.20`,
`breakeven_trigger_pct=0.045`, `max_hold_days=5`, `risk_per_trade_pct=0.5`. Keep `enabled: false` until a
walk-forward run on a real full-universe history clears the deflated-Sharpe gate with every variant logged in
`research/trials.py`. **Note:** the local `data/swing.duckdb` currently holds 60 synthetic sample symbols
(2021-10 to 2026-09), so no meaningful test is possible yet.

### Discretionary (Claude review enums or human steps, never prices)
- "Linear", "orderly", "drunken man walk", "A-quality vs marginal" -> a `setup_quality` enum (A/B/C) plus a short
  reason in `agent/review.py`, used to rank candidates. It never sets entry, stop or size.
- Intraday first-30-minute entries and anticipation buy-stops need live 1-minute data. The monitor's `rvol_now`
  (`features/rvol.py`) plus an intraday 4%/volume check can raise alerts, but order placement stays human-approved
  (CLAUDE.md rule 5).
- Situational awareness beyond the mechanical ratio (the "20% study", "fast selling phase", "range-bound"),
  catalyst judgement for long bases, and whether the theme is in play.

---

## Sources

Primary - Pradeep Bonde, stockbee.blogspot.com (page text fetched 2026-10-06)
- https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html - premise, 8-40%, 3-5 days, 5-10% per trade, 200-1,000 trades (31 Dec 2013)
- https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html - identification checklist: NR/negative prior day, 3-20-day base, float < 25M / < 10M, sub-$5 (4 Jan 2014)
- https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-burst.html - `c/c1>=1.04 and v>v1 and v>100000`; 1999-2000 Compustat origin; anticipation vs reaction (13 Jan 2014)
- https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html - A-quality checklist, no 4% breakdowns, 3+ days with no burst (14 Jan 2014)
- https://stockbee.blogspot.com/2014/01/there-is-structural-phenomenon-in-market.html - burst facts, bull vs bear magnitude (16 Jan 2014)
- https://stockbee.blogspot.com/2014/01/buy-range-expansion-at-beginning-of.html - 5-10-day base, not up 3 days, young trend (17 Jan 2014)
- https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html - burst sequence, 5-8% per trade, failure near turns, @mhp mechanical version (28 Jan 2014)
- https://stockbee.blogspot.com/2014/06/how-swing-traders-make-money.html - return math, 2:1 and 50% before raising risk to 1-2% (28 Jun 2014)
- https://stockbee.blogspot.com/2014/07/my-swing-trading-process-flow.html - scans (4%, $1, range expansion), stop = entry-day low, 0.25-2% risk, 3-5-day exit, 10% day partial (30 Jul 2014)
- https://stockbee.blogspot.com/2014/08/how-i-get-market-monitor-numbers.html - Market Monitor scan formulas (1 Aug 2014)
- https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html - % risk model 0.25-4%, share formula, 60% winners, worst loss 0.59% (8 Aug 2014)
- https://stockbee.blogspot.com/2014/08/how-i-generate-my-breakout-anticipation.html - Double Trouble and TI65 scans, anticipation checklist (14 Aug 2014)
- https://stockbee.blogspot.com/2014/08/the-nature-of-swing-moves.html - 3-10-day variants, 5-20% per trade (13 Aug 2014)
- https://stockbee.blogspot.com/2014/08/trading-tools-i-use.html - Telechart/TC2000, brokers (5 Aug 2014)
- https://stockbee.blogspot.com/2014/09/right-entry-reduces-your-risk.html - do not buy day 3-5 (4 Sep 2014)
- https://stockbee.blogspot.com/2015/01/stocks-will-move-in-momentum-bursts-in.html - "1 minute and 1 cent before the breakout"; over/under 50/200 MA (2 Jan 2015)
- https://stockbee.blogspot.com/2015/01/momentum-burst-is-pattern-and.html - time stop, breakeven, 50% win rate OK, 400-1,000 trades (16 Jan 2015)
- https://stockbee.blogspot.com/2015/05/how-do-stock-move-on-3-to-5-day-time.html - guidelines eliminate 95%+ of 4% breakouts (21 May 2015)
- https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html - small/mid caps, EOD-next-day OK, breakeven at +4-5% (18 Nov 2015)
- https://stockbee.blogspot.com/2016/07/profiting-from-momentum-bursts.html - momentum phase, 3-20-day bursts (6 Jul 2016)
- https://stockbee.blogspot.com/2017/01/a-simple-scan-to-find-big-winners.html - young-trend rules, 1st-3rd setup (23 Jan 2017)
- https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html - `c-o>=.90` $ breakout; full exit table (13 Jul 2017)
- https://stockbee.blogspot.com/2017/10/how-to-find-good-breakouts-daily.html - restatement of the 2017 loop (19 Oct 2017)
- https://stockbee.blogspot.com/2019/08/how-do-stocks-move.html - restatement (8 Aug 2019)
- https://stockbee.blogspot.com/2020/02/one-idea-which-can-make-you-lots-of.html - burst facts (12 Feb 2020)
- https://stockbee.blogspot.com/2021/02/one-idea-which-can-make-you-millions.html - burst facts (26 Feb 2021)
- https://stockbee.blogspot.com/2011/08/how-to-use-market-breadth-to-avoid.html - Market Monitor definitions and thresholds (300/500/1000, 10-day ratio 2 / 0.5, 25% quarter) (8 Aug 2011)
- https://stockbee.blogspot.com/p/mm.html - Market Monitor page (links only; data members-only)
- https://stockbee.blogspot.com/2021/01/situational-awareness-and-t3a.html - SA / T3A (5 Jan 2021)
- https://stockbee.blogspot.com/2024/01/for-high-win-rate-fix-situational.html - daily SA meeting (5 Jan 2024)
- https://stockbee.blogspot.com/2025/09/stockbee-tc2000-tabs.html - TC2000 tabs incl. MM, "20% 5 Day Study" (4 Sep 2025)
- https://stockbee.blogspot.com/2025/01/how-to-gauge-market-trend-using-guppy.html - Guppy MMA market-trend post (Jan 2025; video only)
- https://stockbee.blogspot.com/2025/04/methods-and-philosophy.html - index of method posts (5 Apr 2025)
- https://stockbee.blogspot.com/2026/05/two-market-wizards-have-come-from.html - Market Wizards claim (5 May 2026)
- https://stockbee.blogspot.com/2026/06/market-wizard-factory.html - (11 Jun 2026)
- https://stockbee.blogspot.com/2026/07/situational-awareness-for-july-20-2026.html - range-bound; breakouts unlikely to follow through (20 Jul 2026)
- https://stockbee.blogspot.com/2026/07/understand-market-breadth.html - breadth thrusts = back-to-back 300+ days (23 Jul 2026)
- https://stockbee.blogspot.com/2026/07/trade-with-situational-awareness.html - SA decision question (24 Jul 2026; the key question is in an image)
- https://stockbee.blogspot.com/2026/09/november-2026-bootcamp-las-vegas.html - Nov 13-15 2026 bootcamp syllabus and price (17 Sep 2026)
- https://stockbee.blogspot.com/search?q=momentum+burst - post index
- https://stockbee.biz/bootcamp/november-2026-bootcamp/ - signup (not fetched)
- http://stockbee.biz/position-size-calculator/ - calculator referenced in the 2014 risk post (not fetched)

Secondary - notes, reproductions, interviews
- https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts - 2LYNCH, CV rule, universe, MM columns (F4VS, 25 Sep 2024, TraderLion 2024 talk)
- https://retailtradersrepository.substack.com/p/pradeep-bonde-stock-examples - examples post (not fetched this run)
- https://tikamalma.substack.com/p/systems-setups-and-process-of-swing - 8%/$5 scans, 0.25% risk, exit 3-5 days or -8% (26 Aug 2024)
- https://tikamalma.substack.com/p/4-momentum-burst-detailed-research - 1,227-event study (18 Jun 2025)
- https://fintwits-most-popular-stock-market-scans.onrender.com/canada/Stockbee/Breakout%201M%20Base_criteria.html - Breakout 1M Base scan (2023-03-07)
- https://trendsandbreakouts.com/stockbee - explainer, no audited records (P. Juozaitis, modified 22 Jul 2026)
- https://www.tradingview.com/script/aUbyMkHj-Stockbee-Screener-Momentum-Burst-Episodic-Pivot-Scanner/ - mericourt script (TI65, close >= 70% of range, prior day <= 2%)
- https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/ - LuxAlgo mirror (Jan 2026 per sweep)
- https://www.luxalgo.com/library/indicator/6h74IRYK-stockbee-momentum-burst/ - LuxAlgo "Stockbee Momentum Burst" page (qualitative)
- https://www.tradingview.com/script/Rf67M40u-StockBee-MB-Bullish/ - lukebrod script (close within 30% of high; not opened)
- https://www.tradingview.com/script/ZADkBsIl-StockBee-MB-Bullish/ - princemraj script (not opened)
- https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/stockbee-momentum-burst-screener - AI skill, grades, no validation
- https://www.investorsunderground.com/trading-takes-24/ - IU interview (3 Jul 2024; page has no transcript)
- https://www.friendlybearpodcast.com/1782340/episodes/15777662-pradeep-stockbee-bonde-how-to-make-millions-swing-trading-momentum-burst-strategy-etc - podcast (19 Sep 2024; not transcribed)
- https://easyswing.trading/performance - 17-detector panel, no MB detector (7 Jul 2026)

Academic / market context
- https://alphaarchitect.com/short-term-momentum/ and https://repec.cepr.org/repec/cpr/ceprdp/DP15857.pdf - Medhat & Schmeling, "Short-term Momentum", RFS 2022
- https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html - Gervais, Kaniel & Mingelgrin, "The High-Volume Return Premium", JF 2001
- https://breesefine7110.tulane.edu/wp-content/uploads/sites/16/2015/10/Weekly-Momentum-Kelly-and-Gutierrez.pdf - Gutierrez & Kelley, "The Long-Lasting Momentum in Weekly Returns" (working paper; JF 2008)
- https://ideas.repec.org/a/eee/jfinec/v106y2012i3p635-659.html - Savor, "Stock returns after major price shocks: The impact of information", JFE 2012
- https://academicnewsletter.sufe.edu.cn/info/357702 - Chan, "Stock price reaction to news and no-news", JFE 2003 (abstract mirror)
- Jegadeesh (1990) JF 45(3); Lehmann (1990) QJE 105(1); Conrad, Hameed & Niden (1994) JF 49(4); Barber, Huang, Odean & Schwarz (2022) JF - standard citations, not re-fetched
- https://www.firstfinancialtrust.com/2026/10/01/quarterly-market-review-july-september-2026/ - Q3 2026 index returns, Russell 2000 -7.52%
- https://www.finra.org/rules-guidance/notices/26-10 - PDT designation and $25k minimum eliminated, effective 4 Jun 2026
- Internal: docs/methods/05-qullamaggie-breakout.md, docs/methods/06-breadth-regime-filters.md, docs/research-raw/methods-sweeps/*.json (Q4-2025 momentum reversal, retail share, meme context)
