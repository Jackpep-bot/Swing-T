# 07 — CAN SLIM / IBD, with the Market School follow-through-day / distribution-day regime filter

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Tags: "(primary)" = O'Neil's book as summarised by
AAII from the 4th edition, or an Investor's Business Daily (IBD) article (many are syndicated on Yahoo Finance /
Nasdaq.com, which is how they were read here: investors.com itself is metered and returned truncated bodies);
"(secondary)" = third-party reconstruction, forum notes or vendor data; "(unverified)" = not checked against a primary
source in this run. The web-search budget for this session ran out mid-run, so several items below are marked
unverifiable rather than chased further.*

**One line.** Buy the top 2–3 stocks of a leading industry group (quarterly EPS up ≥ 18–25 % and accelerating,
3-year EPS growth ≥ 25 %, ROE ≥ 17 %, RS Rating ≥ 80, rising fund ownership) as they break out of a proper base
(cup-with-handle ≥ 7 weeks, etc.) on volume ≥ 40–50 % above average, but **only when IBD's market read is a
"confirmed uptrend"** (a follow-through day after a correction, with fewer than ~5–6 distribution days in the last
25 sessions); cut every loss at 7–8 %, take most gains at 20–25 %, and hold ≥ 8 weeks if a stock runs ≥ 20 % within
3 weeks of breaking out.

**Lineage.** William J. O'Neil built the rules by studying the biggest winners before their run-ups: 500 stocks
1953–1993 (2nd ed., 1994), 600 stocks 1953–2001 (3rd ed., 2002) and 1,000 stocks 1880–2009 (4th ed., "How to Make
Money in Stocks", 2009/2011) (AAII Journal, 2016, primary summary of the book). IBD (founded by O'Neil) publishes
the M-rule daily as "Market Pulse" (Confirmed Uptrend / Uptrend Under Pressure / Market in Correction) and its staff
later turned it into **Market School** (Mike Webster, Justin Nielsen, Charles Harris), a rule-based buy/sell
signal counter that sets an exposure %. **SwingTrader** is IBD's paid service applying the same stock selection to
~5–10-day swings. Minervini (SEPA/VCP), Morales & Kacher (pocket pivots, buyable gap-ups), Oliver Kell and
Qullamaggie all cite O'Neil as their root (see methods 05, and the sweep).

---

## Rules

### Universe and scan (the C-A-N-S-L-I of CAN SLIM)
| Letter | Rule as taught | Source |
|---|---|---|
| **C** Current quarterly EPS | EPS vs the **same quarter a year earlier** up a "major" amount: book: **18–20 % minimum** (4th ed.); IBD's current summary and Wikipedia: **≥ 25 %**. Prefer **both of the last two quarters** strong, **accelerating** growth, EPS from continuing operations (omit one-time gains), ignore growth off a penny or two of EPS | AAII 2016 (primary summary of 4th ed.); Wikipedia CAN SLIM; sweep `books_blogs` |
| C (sales / quality) | **Quarterly sales growth ≥ 25 %**, or sales growth accelerating over the last **3 quarters**; after-tax margins at or near a new high; rising estimates and positive surprises; at least **one other stock in the same industry** also showing strong EPS | AAII 2016 (primary summary) |
| **A** Annual EPS | EPS up in **each of the last 3 years**; compounded annual EPS growth **≥ 25 %** (25–50 %); next year's consensus above the current year; **ROE ≥ 17 %**; positive cash flow (better if > EPS); stable year-to-year growth | AAII 2016 (primary summary); AAII screen rules 2003/2019 |
| **N** New | New product/service, new management or improved industry conditions, **and** the price is reaching new highs out of a proper base on increased volume. AAII's mechanical proxy: within **10 % of the 52-week high** | AAII 2016; AAII screen 2019 |
| **S** Supply/demand | Any size of company works, but demand must exceed supply: volume should expand on up-moves; buybacks with growing net income and high management ownership are pluses; low-cap, no-institution stocks are illiquid and risky | AAII 2016 |
| **L** Leader | Avoid **RS rank < 70**; buy **RS ≥ 80**; the best winners averaged **RS 87** before their big move (1950–2008); buy only the **top 2–3 stocks in the group**, no laggards or sympathy plays | AAII 2016 |
| **I** Institutional sponsorship | A few good-performing institutional owners; book suggests **~20 institutional owners** as a reasonable minimum (AAII's screen relaxes to ≥ 10); number of owners **rising in recent quarters**; avoid "over-owned" names | AAII 2016; AAII screen 2019 |
| **M** Market direction | See next section. O'Neil's reason: roughly **3 of 4 stocks follow the general market** | sweep `books_blogs` (Wikipedia summary) |
| IBD ratings (tools) | IBD/MarketSurge pre-compute Composite, EPS Rating, RS Rating (1–99 percentile of ~12-month price performance), SMR and Accumulation/Distribution ratings; RS line at a new high is a featured MarketSurge signal. Exact formulas are proprietary; the common "RS = 40 % last quarter + 20 % each of the prior three" reproduction is **unverified** | sweep `fintwit`; (unverified) |

Discretionary layer O'Neil insists on: the company must be the innovator/leader of its group (highest ROE, widest
margins, strongest sales growth and price action), not merely the largest (AAII 2016).

### Market filter (the M rule = Market Pulse / Market School)
**States.** Confirmed Uptrend / Uptrend Under Pressure / Market in Correction (sweep `fintwit`; IBD Big Picture
headlines use the same words). New buys only in a confirmed uptrend; under pressure = slow down and tighten; in
correction = no new buys, raise cash.

**Rally attempt (Day 1).** After a decline, Day 1 is the first **higher close** (volume may be higher or lower);
community practice also accepts a "pink" day that closes down but in the upper half of its range. If the index
**undercuts the rally-attempt low** on Day 2 or 3 (or later), the count restarts (IBD, 13 May 2015; Fool board,
Mar 2025).

**Follow-through day (FTD, Market School buy signal B1).**
- Timing: **Day 4 or later** of the rally attempt; the best are **Days 4–7**, but late ones have worked (IBD cites
  a Day 15 and a Day 17 FTD) (IBD 2012, 2015).
- Size: a "significant" gain in the **Nasdaq composite or S&P 500** (not the Dow). The threshold has drifted:
  ~1 % in O'Neil's early research → ~2 % for the Nasdaq in the 1990s → **≥ 1.7 %** (IBD as quoted May 2010) →
  **1.3–1.4 %+** (IBD Dec 2012) → **"at least 1 % to 1.25 %"** (IBD May 2015) → **≥ 1.25 %** (Fool board restatement,
  2024–25) / ≥ 1.2 % (TradingView marker, Jan 2025) / ~1 % "volatility-adjusted" in Market School practice (Fool,
  May 2025).
- Volume: **higher than the prior session**; it need not be above average (IBD 2015).
- On an FTD the distribution count for all key indexes **resets to zero** (IBD via Yahoo summary).
- Exposure after an FTD is staged, not all-in: IBD's April 2025 guidance went **0–20 % at the FTD** (few actionable
  setups) → **40–60 %** (28 Apr 2025) → **60–80 %** (13 May 2025) (Fool Market School thread, restating IBD).

**Distribution day (DD).** A major index (Nasdaq, S&P 500, NYSE composite) **falls ≥ 0.2 % (no rounding up) on
volume higher than the prior session**. A DD **expires after 25 sessions**, or earlier if the index rises **6 %**
(intraday) above that day's close (IBD, 2 Mar 2012; some reconstructions use 5 %). How many is too many is
judgement: IBD wrote in 2012 the market "could probably withstand six or seven"; practitioners treat **5–6 within
~25 sessions** as the "under pressure" cluster (sweep `fintwit`), and the Market School reconstruction uses
**4 = warning (S3), 5+ = full distribution (S4)**. **Stalling days** (tiny gain near highs on higher volume) count
like DDs in IBD practice; reconstruction: index at a 13-week high, change < 0.4 %, close in the lower half, higher
volume (S13).

**Market School (reconstructed; IBD's own rule book is proprietary).** A counter adds +1 per buy signal and −1 per
sell signal; the count maps to exposure. Reconstruction by "vishnuv" (TradingView, 24 Jan 2025, secondary):

| Buy signals | Sell signals |
|---|---|
| B1 FTD · B2 additional FTD within 25 days of rally day 1 (must hold above the first FTD low) · B3 first day low ≥ 21-day EMA (up/flat close) · B4 5th straight day with low ≥ 21-day EMA · B5 10th/15th/20th day low ≥ 21-day EMA · B6 first low ≥ rising 50-day MA on an up close · B7 accumulation day (FTD-like gain after day 25, close in top 25 % of range, above 21-day EMA) · B8 higher high (close above 9-bar pivot high) · B9 downside-reversal buyback (close above the S11 bar's high within 2 days) · B10 DD count falls from ≥ 5 to ≤ 3 | S1 close below FTD low · S2 undercut of rally-day low · S3 DD warning (4) · S4 full distribution (5+) · S5 close < 21-day EMA with ≥ 0.2 % loss · S6 "overdue break" (S5 after 30+ days without one) · S7 5th day high < 21-day EMA · S8 10th/15th/20th day high < 21-day EMA · S9 close < 50-day after B6 · S10 bad break (down ≥ 2.25 %, close in bottom 25 %, below 50-day or high < 21-day EMA) · S11 downside reversal at a 13-week high (spread ≥ 1.75 %, close bottom 25 %) · S12 trend reversal (13-week high, down ≥ 1 % on higher volume; counts as a DD) · S13 stall at highs · S14 close below the B8 pivot · S15 lower low (close below 9-bar pivot low) |

- Exposure map: **count 0 = 0 %, 1 = 30 %, 2 = 55 %, 3 = 75 %, 4 = 90 %, 5+ = 100 %**; **restraint rule** caps
  exposure at **55 %** until the rally proves itself; **power trend** lets the count run to 7 with a floor of 2;
  **buy switch** is the master on/off for new purchases; **circuit breaker** (variants): index ≥ 10 % off its rally
  high and/or a close below the 50-day (or the 200-day from above) resets the count to 0 and turns the buy switch off
  (vishnuv 2025; Fool board, 4 Mar 2025, gives "10 % off high AND ≥ 5 % below the 50-day intraday, or close below
  the 50-day in the lower half of the range or > 1 % below").
- Community pyramid for filling exposure: **30 % / 25 % / 20 % / 15 % / 10 %** across five successive buy signals
  (Fool board, Lakedog, 13 Jan 2025, secondary).

### Entry
- **Pivot / buy point** = the highest price in the handle **+ $0.10** for a cup-with-handle (IBD, 6 Feb 2014); for
  other bases, the prior resistance high (double bottom: the middle peak; flat base: the base high) (unverified
  details).
- **Breakout volume** at least **40–50 % above the 50-day average** (IBD 2014).
- **Buy zone**: up to **5 % above the pivot**; beyond that the stock is "extended" and should not be chased (IBD
  convention, widely restated; not re-read from a primary page in this run — unverified wording).
- **Base requirements (cup-with-handle):** at least **7 weeks** long; cup decline **no more than ~30–35 %** (deeper
  allowed in bear-market bases); handle decline **usually ≤ 8–12 %** (up to ~15 %), on **light volume**, calm price
  action, with up-weeks on above-average volume inside the base as accumulation evidence (IBD 2014; nasdaq/yahoo
  syndications). Handle should sit in the upper half of the base (secondary). Flat base ≥ 5 weeks and ≤ ~15 % deep,
  three-weeks-tight, saucer-with-handle, ascending base and IPO base are the other IBD patterns (IBD article titles
  confirm the patterns; numeric limits for them are unverified in this run).
- Earlier entries IBD also teaches: trend-line breaks inside the handle, pullbacks to the 10-week (≈ 50-day) or
  21-day line, and (Morales/Kacher) pocket pivots and buyable gap-ups.
- **Only when M allows it**; the best breakouts tend to come in the first weeks after an FTD.
- Pyramiding (book): add smaller lots only as the stock moves up a few % from the first buy, never average down
  (unverified exact percentages).

### Stop
- **Sell any stock that falls 7–8 % below your purchase price, no exceptions** — "the cardinal rule of selling" (IBD;
  AAII 2016). Experienced users cut at 3–5 % and the 7–8 % is a ceiling, not a target (sweep; unverified as IBD
  wording).
- **Round-trip rule:** don't let a double-digit gain turn into a loss (IBD sell-rule article).
- SwingTrader version: max loss **~3 %** (sweep `youtube`; traderhq review snippet — secondary).

### Exits and targets
- **Take most profits at 20–25 %** above the buy point. O'Neil formed this rule in the early 1960s after noticing
  most breakouts ran 20–25 % and then corrected (IBD).
- **8-week hold rule:** if a stock gains **≥ 20 % within 3 weeks of breaking out** (measured from the breakout/pivot
  price), hold it for **at least 8 weeks counted from the breakout week**, unless a market correction or a sharp
  break forces protection of the gain (IBD, 6 Mar 2013; Ceradyne 2003 example: +27 % in 3 weeks, +645 % by end-2004).
- Other book sell rules (not re-verified this run): climax run (largest daily/weekly gain, exhaustion gap after a
  long advance), heavy-volume break of the 50-day/10-week line, late-stage (3rd–4th) base failures, and
  **two quarters of material slowdown in EPS growth** (the last is in AAII 2016).
- Market-level exits: an S1 (close below the FTD low), a full distribution cluster or a circuit-breaker trip means
  cut exposure, regardless of individual charts.

### Position sizing
- O'Neil is a concentrator: a handful of the best stocks, sell the worst performers first and let the best run
  (AAII 2016). Exact account-size → number-of-stocks table from the book is **unverified** in this run.
- Total exposure is the dial: IBD publishes recommended exposure bands (0–20 / 20–40 / 40–60 / 60–80 / 80–100 %);
  Market School maps the signal count to 0/30/55/75/90/100 % (reconstruction above).
- Implied payoff: a 7–8 % maximum loss against 20–25 % targets ≈ **3:1** reward-to-risk per trade.

### Holding period
- CAN SLIM position trades: **weeks to a few months** (20–25 % target; 8-week minimum for the fastest movers).
- **SwingTrader:** targets **5–10 trading days** (typical 2–6, sometimes up to 2 weeks), profit target **~10 %**
  (sweep `youtube`; traderhq review snippet).
- Market School signals operate on a **daily** index chart; an FTD-to-correction cycle has lasted from a few weeks to
  a year+.

---

## Chart signatures
1. **Prior uptrend → base**: a stock that has already advanced (IBD looks for a prior uptrend) builds a 7–65-week
   consolidation; cup depth ≤ 30–35 %, smooth U-shaped bottom, handle in the upper part of the base drifting lower on
   dry volume.
2. **Breakout bar**: close above the pivot (handle high + $0.10) on volume ≥ 40–50 % above the 50-day average,
   closing near the day's high; ideally within 5 % of the pivot at the buy.
3. **RS line** (stock / S&P 500) at a new high **before or with** price — leadership signature; RS Rating ≥ 80.
4. **Accumulation inside the base**: more up-weeks on above-average volume than down-weeks (IBD 2014).
5. **Fast follow-through**: +20 % within 3 weeks triggers the 8-week hold; failed breakouts fall back into the base and
   hit the 7–8 % stop quickly.
6. **Market tape**: a correction, a Day-1 low, a **Day 4–7 index gain ≥ ~1–1.25 % on rising volume** (FTD), then a
   clean run above the 21-day EMA and 50-day; tops show **clusters of 5–6 distribution/stalling days within 25
   sessions**, downside reversals from 13-week highs and leaders breaking their 50-day lines.
7. **Late-stage failure signatures**: wide-and-loose 3rd/4th-stage bases, climax runs with exhaustion gaps, heavy
   volume breaks of the 10-week line.

---

## Who teaches it
- **William J. O'Neil** (founder of IBD and William O'Neil + Co.; "How to Make Money in Stocks", 4 editions).
  O'Neil died in 2023 (Wikipedia, citing Hagerty, WSJ, 30 May 2023).
- **Investor's Business Daily / IBD Live** (investors.com; @IBDinvestors on X per the sweep): Mike Webster (heads
  SwingTrader, weekly status video; Market School co-author), Justin Nielsen and Charles Harris (Market School),
  Matthew Galgani (author of IBD's "How To Invest In Stocks" guide, updated 24 Jul 2025). IBD's YouTube channel had
  ~184K subscribers in Sep 2026 per the sweep (sponsorradar).
- **MarketSurge** (formerly MarketSmith; @MarketSmith per the sweep): the charting/screening tool (ratings, RS line,
  Blue Dot, pattern recognition).
- **Deepvue** (Richard Moglen, Ross Haber, Ameet Rai, Nicholas Schmidt; founded 2022) and **TraderLion**:
  CAN SLIM-style screens and education (sweep).
- **AAII** (John Bajkowski): published mechanical CAN SLIM screens since the late 1990s.
- **Community reconstructions**: Motley Fool "IBD Market School", "Trading IBD Stocks", "IBD Swing Trading" boards
  (PuddinHead42, Lakedog, buynholdisdead); TradingView scripts "IBD Market School [Professional]" (vishnuv),
  "[TTI] IBD Market School", "Distribution/Follow-Through Day Marker" (anotherfire).
- **Descendants** that keep the O'Neil core: Minervini (SEPA, VCP, Trend Template), Gil Morales & Chris Kacher
  (pocket pivots, buyable gap-ups), Oliver Kell, Qullamaggie (method 05).

---

## Evidence

### Self-reported by O'Neil / IBD (descriptive, unaudited)
- The rules were reverse-engineered from the **pre-run characteristics of past winners** (500 → 600 → 1,000 stocks).
  That is a description of winners, not a forward test of the rules: it has look-ahead and survivorship built in (no
  count of how many stocks met the same criteria and then failed).
- IBD's market-timing claim is qualitative: every major market bottom back to 1900 had a follow-through day, but not
  every FTD works (IBD, 6 Dec 2012). No IBD backtest of Market Pulse vs buy-and-hold was found.
- FTD reliability figures quoted on the Fool board from "Stock Guide 2024Q1" (primary study not located;
  unverified): **33 %** of FTDs led to profitable rallies (> 3 % gain lasting > 15 days), **41.3 %** to small gains or
  losses ("SLOGs"), **26.5 %** were whipsaws within 15 days; **6.3 %** were "life changers" (> 15 %).

### Hypothetical screens (no costs, monthly rebalance, tiny lists)
- AAII named CAN SLIM its **top-performing screen for 1998–2009** (Wikipedia, citing the Globe and Mail, Feb 2010).
- AAII, 4 Feb 2019: its O'Neil CAN SLIM screen averaged **22.1 %/yr over 10 years vs 10.7 % for the S&P 500**,
  31.0 %/yr over 5 years and 33.6 %/yr over 3 years — but only **three stocks** passed on 31 Jan 2019, so the record
  is a concentrated, cost-free paper portfolio.

### Real-money proxies
- **O'Neil's own mutual funds** were short-lived with "lackluster" results despite strong hypothetical numbers
  (Wikipedia, citing Hagerty WSJ 2023 and Jason Zweig WSJ 27 Feb 2026; WSJ itself not read — paywalled).
- **FFTY (IBD 50 ETF, launched 9 Apr 2015)**, a mechanical basket of IBD's CAN SLIM-style top-50 ranking (no
  discretionary chart reading; index methodology not re-checked this run), vs SPY, total return, as of 6 Oct 2026
  (stockanalysis.com): **YTD 2.46 % vs 15.14 %; 1 yr −4.74 % vs +17.67 %; 5 yr −4.06 %/yr vs +13.98 %/yr; 10 yr
  +4.94 %/yr vs +15.53 %/yr**. The fund moved from Innovator to the CapForce platform after an April 2026 shareholder
  vote. This is the cleanest public evidence that **the ranking alone, without discretionary timing and the 7–8 %
  stop, has not beaten the index for a decade**.
- **SwingTrader**: a review snippet reports 2020 averaged **+1.2 % per trade with > 40 % losers**, and **+11.7 %** in
  H1 2021 (search-result snippet from traderhq/valuewalk; the pages were not readable — unverified).

### Independent mechanical tests of the chart side
- EasySwing.trading live-detector panel (updated 7 Jul 2026; ~2,000 US stocks, 5-year walk-forward, **no fees or
  slippage**): **Cup & Handle detector 3,582 trades, win rate 30 %, +0.5 R average, profit factor 1.57, average hold 8
  days** — the best of the momentum-family detectors on that panel (Qullamaggie flag PF 1.10; trend pullback 1.45;
  see method 05). No fundamentals (C/A/I) are applied, and the exits differ from O'Neil's.

### Academic
- **No peer-reviewed out-of-sample test of the full CAN SLIM + M system was located in this run** (search budget ran
  out; mark as unverifiable rather than absent).
- Each letter maps onto a documented anomaly (citations from memory, not fetched this run): post-earnings-announcement
  drift and earnings momentum (C; Bernard & Thomas 1989; Chan, Jegadeesh & Lakonishok 1996), price momentum and the
  52-week-high effect (L, N; Jegadeesh & Titman 1993; George & Hwang 2004), profitability (A/ROE; Novy-Marx 2013),
  and changes in breadth of institutional ownership (I; Chen, Hong & Stein 2002). Momentum also crashes in rebounds
  out of bear markets (Daniel & Moskowitz 2016), which is exactly when an FTD fires and leadership rotates.
- PEAD's strength itself is debated again in 2025–26 (repo sweep: UCLA Anderson Review, Jan 2026, "Is post-earnings
  announcement drift a thing again?" — not re-read here).

### Reading the evidence
The pieces (earnings growth, momentum, 52-week highs, market-trend filters) each have support; the bundle has
strong hypothetical screen results, weak real-money results (O'Neil's funds, FFTY), and a market filter whose
value lies in avoiding deep bear markets rather than in precise timing (roughly a quarter of FTDs whipsaw within 15
days). The edge practitioners report comes mostly from **loss-cutting at 7–8 % plus concentration in the few big
winners** — which a backtest with realistic gaps and costs has to show before it is trusted.

---

## Pitfalls
- **Moving thresholds.** The FTD gain has drifted from ~1 % to 2 % to 1.7 % to 1.25 % to ~1 %; DD expiry is 5 % or
  6 %; the "too many DDs" line is 4, 5, 6 or 7 depending on the source. Backtesting with today's numbers on old data
  is hindsight fitting; pick one rule set, version it, and keep it.
- **Volume source.** IBD counts exchange (Nasdaq / NYSE) volume; SPY/QQQ ETF volume or consolidated volume gives a
  different DD count (the Fool board shows members arguing over exactly this, May 2025).
- **The FTD lags V-bottoms.** In April 2025 the +9.5 % tariff-pause day (9 Apr) was only Day 3 and could not count;
  the FTD came on Day 11 (22 Apr). Policy-driven reversals (2025–26) make Day-4+ rules late by design.
- **Whipsaws.** ~1 in 4 FTDs fail within 15 days (unverified stat above); the restraint rule and staged exposure exist
  for this reason.
- **7–8 % stop vs 5 % buy zone.** Buying at the top of the buy zone leaves the stop only ~2–3 % below the pivot, so a
  normal retest of the breakout stops you out; in high-volatility names 7–8 % sits inside daily noise.
- **Fundamental data hygiene.** EPS must be from continuing operations and point-in-time (filing date, not period end;
  restatements); IBD's ratings and group ranks are proprietary and cannot be reproduced exactly.
- **Survivorship in the source studies**: the "model book" of winners is not a sample of all stocks that looked the
  same.
- **Crowding.** IBD 50 / breakout lists are widely followed; FFTY's 10-year record shows the naive basket lags.
- **Chasing and late-stage bases**: extended entries (> 5 %) and 3rd/4th-stage bases have lower success (IBD
  teaching; unverified quantification).
- **Reconstructions are not the product.** Market School's official rule book is not public; the B/S tables above are
  community reverse-engineering and differ on details (e.g., B1 window 4–25 days, 1 % vs 1.25 %).

---

## 2025–2026 fit
Timeline from IBD "The Big Picture" index pages (headlines and summaries only; bodies paywalled), the Fool Market
School thread and the repo's events sweep:
- **13 Mar 2025** S&P 500 enters correction on tariff threats. **7 Apr** = rally Day 1; **9 Apr** tariff pause
  (+9.5 %, Day 3, not eligible); **15 Apr** "seventh day of rally attempt"; **22 Apr 2025 FTD** (Nasdaq and S&P 500
  confirm; actionable stocks scarce). IBD exposure 0–20 % → 40–60 % (28 Apr) → 60–80 % (13 May); power trend by
  mid-May. **21 May** first Nasdaq DD since the FTD. The uptrend held through 2025 (Nasdaq record 9 Jul "uptrend that
  began in April"; DDs on 5 Aug, 19 Aug, 2 Sep, 14 Oct absorbed; third Fed cut 10 Dec; record highs 11 Dec).
- **2026:** Nasdaq's **4th DD in 5 sessions on 3 Feb** (software/chip sell-off) and another on 3 Mar ("sell signals
  scarce") preceded the **March correction** (Dow and Nasdaq in correction territory 27 Mar, Iran war). **31 Mar** =
  Day 1; **8 Apr 2026 FTD** (Day 6; the same day as the Iran-ceasefire rally, +2.2 % per the events sweep), followed
  by a strong advance to new highs (6 May). Distribution resumed in June (9 Jun); **7 Jul** "uptrend wobbles" as
  leaders broke 50-day lines; **1 Sep** IBD questioned the health of the uptrend; **15 Sep** urged extra caution on
  new buys; **16 Sep** Fed rate hike (Chair Warsh); 10-year yield at records above 5 % (14 and 28 Sep); S&P 500
  resistance near 7,750–7,800 (29 Sep); Nasdaq record closes on 5–6 Oct 2026.
- **What worked:** the M filter caught both V-recoveries within ~2–3 weeks of the low (Day 11 in 2025, Day 6 in
  2026), and the Feb–Mar 2026 distribution cluster warned before the March correction. Staged exposure after the
  FTDs avoided going all-in on Day 1.
- **What did not:** the CAN SLIM basket as a mechanical product lagged badly (FFTY 1-yr −4.7 % vs SPY +17.7 %; 5-yr
  negative). Leadership was narrow and rotated quickly (AI/semis, then metals/shipping/biotech in FFTY's current top
  10), and breadth bifurcated: by late Sep–Oct 2026 fewer than half of stocks were above their 200-day while indexes
  made records (method 06). That environment produces few "proper bases" in true leaders and many failed breakouts.
- **Verdict for Oct 2026:** keep the **M rule as a regime gate** (cheap, mechanical, behaved well in 2025–26), but do
  not expect the stock-selection side to beat the index without strong execution; run CAN SLIM breakouts at reduced
  exposure while IBD's own tone is cautious and the 06 breadth gates are weak, and favour the SwingTrader-style short
  holds (5–10 days, ~3 % stop) over 8-week holds until breadth recovers.

---

## Automatability

### Mechanical (can be coded in swing-engine today or with small feature additions)
| Element | swing-engine mapping |
|---|---|
| **Market School state machine (M)** | New `features/market_school.py` (or extend `features/regime.py`): per index session, `ms_rally_day` (1..n, reset on undercut of the rally low), `ms_ftd` (day ≥ `ftd_min_day`=4, gain ≥ `ftd_min_gain`=0.0125, volume > prior), `ms_dd_count_25` (loss ≥ `dd_min_loss`=0.002 on higher volume, expire after `dd_window`=25 or +`dd_expiry_rally`=0.06), `ms_state` (correction / under pressure / confirmed), `ms_count` and `ms_exposure` via the 0/30/55/75/90/100 map. Thresholds go in a `market_school:` block in `config/settings.yaml` (rule 4). Broadcast to every row like `market_trend_state`. |
| Index data | Needs Nasdaq composite and S&P 500 (or NYSE composite) **with exchange volume** from `data/massive.py` or `data/eodhd.py`; QQQ/SPY volume only as a labelled proxy. Note: `data/swing.duckdb` currently holds **synthetic `sample` bars** (fictional tickers; SPY at ~409 on 2025-04-08 vs ~496 real), so a prototype FTD/DD run on it in this session produced meaningless dates — any validation must use real index bars. |
| Market gate in strategies | `PanelStrategy.market_ok` in `strategies/_base.py` reads `market_trend_state`; add `min_ms_state` / `min_ms_exposure` params. The live monitor's `monitor/rules/market_wide_suppression.py` can mark suppression when `ms_state == correction`. |
| Exposure dial | `risk/limits.py` / `risk/sizing.py`: scale `max_open_positions` or gross exposure by `ms_exposure`; restraint rule = cap 0.55 until B-count ≥ 3. |
| L (RS Rating) | Cross-sectional percentile per `ts` of a weighted 12-month return from `ret_63d`, `ret_126d`, `ret_252d` (or `mom_12_1`) in `features/cross_section.py` → `rs_rating` (1–99); `rs_line_new_high` = (close / SPY close) at a 52-week high. |
| N (near highs) | `dist_52w_high >= -0.10` (AAII proxy) and `breakout_52w` flag from `features/patterns.py`. |
| Base + pivot | `base_len`, `vcp_contraction` exist; add a cup-with-handle detector in `features/patterns.py` (`cup_depth`, `handle_depth`, `handle_len`, `pivot_price` = handle high + 0.10, base length ≥ 35 bars). |
| Breakout trigger | `close > pivot_price`, `rvol_day` / `volume / avg_vol_50d >= 1.4–1.5`, `close / pivot - 1 <= 0.05`, `close_pos` high. Closest module: `strategies/breakout_52w.py` (already 1.5x `avg_vol_50d`, close near high). |
| Stop / exits | Fixed-% stop param (`stop_pct`=0.07–0.08) instead of the ATR stop; target 0.20–0.25; 8-week rule needs a "if +20 % within 15 bars, min hold 40 bars" hook in the exit logic (currently `should_exit` is all-or-nothing); round-trip rule ≈ existing `breakeven_after_r` once a +10 % gain is reached. |
| C / A / I fundamentals | Not available today (`data/alphavantage.py` = earnings **calendar** only; `data/edgar.py` = Atom feed, Form 4, tickers). Add SEC XBRL company-facts ingestion stamped at **filing acceptance time** (rule 3) for `eps_q_yoy`, `sales_q_yoy`, `eps_accel`, `eps_3y_cagr`, `roe`; 13F holdings (45-day lag) for `inst_holders_chg`. |
| SwingTrader variant | `strategies/pullback_trend.py` (21-day EMA pullbacks) with ~10 % target, ~3 % stop, max hold 10 bars, gated by `ms_state`. |
| Proposed module | via `.claude/skills/add-strategy`: `strategies/canslim_breakout.py`, params `eps_q_min=0.25`, `sales_q_min=0.25`, `eps_3y_min=0.25`, `roe_min=0.17`, `rs_min=80`, `vol_mult=1.4`, `max_ext=0.05`, `stop_pct=0.07`, `target_pct=0.20`, `fast_gain=0.20`, `fast_bars=15`, `hold_bars=40`, `min_ms_state=confirmed`; register `enabled: false` until walk-forward + trial log clear `docs/gates.md`. |

### Discretionary (keep as Claude review enums or human steps)
- "Proper base" quality (shape, handle position, wedging, late-stage count) — chart judgement; return a
  `base_quality` enum from the `agent` review, never a price.
- "N": what is genuinely new (product, management, industry change) and whether the stock is the group's true leader;
  IBD's 197 industry groups and group ranks are proprietary.
- Marginal market calls: "mild" DDs, stalling days, late FTDs, whether a rally attempt survived an intraday undercut,
  and IBD's published exposure ranges, which are editorial.
- Earnings-quality judgement (one-time items, acquisitions, share count changes) and avoiding buys right before
  earnings (needs the earnings calendar already in `data/alphavantage.py`).

---

## Sources
Primary — O'Neil's book (via AAII) and AAII screens
- https://www.aaii.com/files/journal/pdf/9874_william-oneil-can-slim-approach-to-selecting-growth-stocks.pdf — AAII Journal (John Bajkowski, ©2016) summary of the 4th edition: C/A/N/S/L/I/M numbers, 7–8 % stop, 20 % profit, RS 70/80/87, ~20 institutional owners, editions and study sizes
- https://www.aaii.com/journal/article/feature-the-can-slim-approach-revising-a-screen — AAII, Mar 2003: screen implementation, 3rd-edition numbers
- https://www.aaii.com/stockideas/article/10668-oneils-can-slim-revised-3rd-edition-approach — AAII, 4 Feb 2019: screen returns (10-yr 22.1 % vs 10.7 %)
- https://en.wikipedia.org/wiki/CAN_SLIM — letter summary, AAII 1998–2009 claim, O'Neil funds (citing WSJ Hagerty 2023, Zweig 27 Feb 2026)

Primary — IBD articles (syndicated copies read; investors.com bodies were truncated)
- https://finance.yahoo.com/news/day-tells-time-buy-stocks-215900253.html — IBD, 13 May 2015: rally Day 1, undercut reset, Day 4+, best Days 4–7, 1–1.25 %, volume > prior day, Nasdaq/S&P not Dow
- https://finance.yahoo.com/news/want-spot-market-tops-count-215400254.html — IBD, 2 Mar 2012: DD ≥ 0.2 % on higher volume, 25-session / 6 % expiry, "six or seven", reset on FTD
- https://finance.yahoo.com/news/time-stock-market-ibd-says-223000999.html — IBD, 6 Dec 2012: every major bottom since 1900 had an FTD; 1.3–1.4 %; Day 17 example
- https://finance.yahoo.com/news/know-invoke-8-week-hold-215800238.html — IBD, 6 Mar 2013: 8-week hold rule, Ceradyne example
- https://finance.yahoo.com/news/identify-good-qualities-cup-handle-233000441.html — IBD, 6 Feb 2014: ≥ 7 weeks, cup ≤ 30–35 %, handle 8–12 %, pivot + $0.10, volume ≥ 40–50 %
- Search-result summaries only (not opened): https://finance.yahoo.com/news/using-20-sell-rule-help-200500142.html , https://finance.yahoo.com/news/learn-profits-stock-rises-20-221100662.html , https://finance.yahoo.com/news/profits-stock-rises-20-25-215900135.html , https://www.nasdaq.com/articles/how-build-long-term-profits-stocks-take-many-gains-20-25-2017-10-25 , https://finance.yahoo.com/news/way-heed-sell-rules-even-213000178.html , https://finance.yahoo.com/news/why-cutting-stock-losses-short-211000887.html , https://finance.yahoo.com/news/investors-corner-sell-way-183200275.html , https://finance.yahoo.com/news/own-ipo-stock-weigh-8-211500240.html , https://finance.yahoo.com/news/dont-stray-slim-investing-rules-211300166.html , https://finance.yahoo.com/news/watch-distribution-days-spot-peaks-220700524.html , https://finance.yahoo.com/news/learn-wait-recognize-markets-day-230300058.html , https://www.nasdaq.com/articles/how-do-you-spot-major-stock-market-top-heres-easy-way-2017-12-21 , https://finance.yahoo.com/news/big-picture-market-pulse-keep-202900058.html , https://finance.yahoo.com/news/cup-handle-familiar-understand-key-203500768.html , https://finance.yahoo.com/news/chart-pattern-star-power-simple-212700404.html , https://finance.yahoo.com/news/shakeout-breakout-why-stocks-often-214400833.html , https://finance.yahoo.com/news/draw-trend-line-chart-identify-213500214.html , https://finance.yahoo.com/news/brief-pause-breakout-three-weeks-225000672.html , https://finance.yahoo.com/news/why-saucer-handle-deliver-solid-223400739.html , https://ca.finance.yahoo.com/news/key-step-studying-look-accumulation-205200634.html , https://www.nasdaq.com/articles/chart-reading-basics-how-find-correct-buy-point-leading-stocks-2017-10-02 , https://www.nasdaq.com/article/principles-of-technical-analysis-the-cupandhandle-pattern-cm29628
- https://www.investors.com/category/market-trend/the-big-picture/ and /page/2/ … /page/12/ — IBD Big Picture headline index (May 2024 → 6 Oct 2026) used for the 2025–26 timeline
- https://www.investors.com/ibd-university/can-slim/ — resolves to "How To Invest In Stocks" (Matthew Galgani, updated 24 Jul 2025); body truncated (metered)
- https://www.investors.com/how-to-invest/when-to-sell-stocks/ , https://www.investors.com/how-to-invest/stock-market-timing-how-to-invest-in-stocks-tracking-bull-markets-bear-markets-stock-market-trends/ , https://www.investors.com/how-to-invest/how-to-handle-changing-stock-market-trends/ — bodies truncated (metered)

Secondary — reconstructions, community, reviews
- https://it.tradingview.com/script/ZgQSYzJ3-IBD-Market-School-Professional/ — vishnuv, 24 Jan 2025: B1–B10, S1–S15, exposure map, restraint, power trend, circuit breaker
- https://my.tradingview.com/script/0Bkxq34e-TTI-IBD-Market-School — "[TTI] IBD Market School" (404 at fetch)
- https://my.tradingview.com/chart/SPX/M5ukDElr-HOW-TO-TTI-IBD-Market-School — (search result only)
- https://vn.tradingview.com/script/sbzEKCNa-IBD-Market-School-tradeviZion — invite-only (search result only)
- https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker/ — anotherfire, 4 Jan 2025: DD −0.2 %, FTD +1.2 %, volume > prior day
- https://discussion.fool.com/t/ibd-follow-through-day-definition/107779 — FTD ≥ 1.25 %, Day 4+, "Stock Guide 2024Q1" FTD stats, pink rally day
- https://discussion.fool.com/t/ibd-market-school/112218 , https://discussion.fool.com/t/ibd-market-school/112218?page=6 , https://discussion.fool.com/t/ibd-market-school/112218?page=7 , https://discussion.fool.com/t/ibd-market-school/112218?page=8 , https://discussion.fool.com/t/ibd-market-school/112218/last — Market School signals, pyramid, circuit breaker, Apr–May 2025 FTD/exposure, power trend
- https://discussion.fool.com/t/ibd-market-exposure-recommendation/108128 (sweep; not opened)
- https://discussion.fool.com/t/ibd-swing-trading/109412 — SwingTrader community notes (Mike Webster; stop placements)
- https://discussion.fool.com/t/ibd-technical-talk-with-mike-webster/104454 , https://discussion.fool.com/t/ibd-8-week-hold-rule/112549 , https://discussion.fool.com/t/trading-ibd-stocks/104584?page=23 , https://discussion.fool.com/t/trading-ibd-stocks/104584?page=17 , https://discussion.fool.com/t/does-ibd-offer-any-value-to-would-be-swing-traders/106504 (sweep / search; not opened)
- https://seekingalpha.com/instablog/195752-joshua-hayes/73173-a-quick-reminder-about-follow-through-days — 25 May 2010: 1.7 % era, threshold history (1 %, 2 % Nasdaq 1990s, 1.25 % Dow)
- https://traderhq.com/investors-business-daily-swingtrader-review-stock-trading-technical-analysis/ — SwingTrader 5–10 days, ~10 % target, ~3 % stop, $699/yr (search snippet only)
- https://www.valuewalk.com/investors-business-daily-swingtrader/ — (403 at fetch; sweep source)
- https://apps.apple.com/app/id1132694075 — SwingTrader app listing (search result)
- https://sponsorradar.com/channels/investorsbusinessdaily — IBD YouTube stats (sweep)
- https://nexusfi.com/d/platforms/deepvue/ , https://br.tradingview.com/scripts/ibd , https://magica.com/youtube-summarizer/how-to-use-deepvue-to-apply-the-canslim-methodology-for-effective-stock-trading-2RuiIelL0MA , https://www.shortform.com/summary/how-to-make-money-in-stocks-summary-william-j-oneil (sweep; not opened)
- https://www.getrichslowly.org/canslim-investing/ , https://www.stockrover.com/blog/can-slim-investing-strategy/ , https://blog.marketsmithindia.com/?p=14301 , https://traderlion.com/fundamentals/return-on-equity/ , https://en.globes.co.il/en/article-1000291569 (search results only)

Evidence
- https://stockanalysis.com/etf/ffty/ — FFTY inception 9 Apr 2015, 1-yr −4.74 %, CapForce transition headlines (6 Oct 2026)
- https://stockanalysis.com/etf/compare/ffty-vs-spy/ — FFTY vs SPY YTD / 1 / 5 / 10-yr returns (6 Oct 2026)
- https://www.innovatoretfs.com/etf/?ticker=ffty — former issuer page (fetched; no performance table extracted)
- https://easyswing.trading/performance — Cup & Handle detector: 3,582 trades, 30 %, 0.5 R, PF 1.57, 8 days (7 Jul 2026)
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/ — PEAD debate (repo sweep; not opened)
- Academic, from memory, not fetched: Bernard & Thomas (1989, J. Accounting Research), Chan, Jegadeesh & Lakonishok (1996, J. Finance), Jegadeesh & Titman (1993, J. Finance), George & Hwang (2004, J. Finance), Novy-Marx (2013, J. Financial Economics), Chen, Hong & Stein (2002, J. Financial Economics), Daniel & Moskowitz (2016, J. Financial Economics)

2025–26 context (repo events sweep)
- https://fortune.com/2026/04/08/markets-sp-trump-truce-ceasefire-iran-war-rally-strait-of-hormuz , https://www.betashares.com.au/insights/liberation-day-upended-markets/ , https://www.nasdaq.com/articles/april-2025-review-and-outlook , https://cdn.gam.com/it/our-thinking/multi-asset-blog/did-markets-get-liberation-day-all-wrong
- Sibling write-ups: `docs/methods/05-qullamaggie-breakout.md` (EasySwing panel, Minervini 2025 comments), `docs/methods/06-breadth-regime-filters.md` (2025–26 breadth timeline)
