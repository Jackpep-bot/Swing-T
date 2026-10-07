# 08 - Anchored VWAP pullback / multi-timeframe trend alignment (Brian Shannon, CMT)

Written 2026-10-06 from primary sources (alphatrends.net, Shannon's 2026 CMT Association podcast, his 2025-2026 interviews),
secondary summaries of his two books, and the public quant literature on VWAP. Verification status is marked inline:
**[primary]** = Shannon or his site in his own words; **[secondary]** = a third-party summary of his book/talks;
**[unverified]** = seen only in a search snippet or a summary whose underlying page could not be fetched this session.
Starting point was the sweep entry in `docs/research-raw/methods-sweeps/merged_compact.json` (methods[7]) and the three
source entries in `merged_methods.json` (key `avwap`).

One line: trade in the direction of the higher-timeframe trend, wait for a pullback toward a rising Anchored VWAP (AVWAP)
and the rising 5-day moving average, and buy only when the short-term chart proves strength has returned ("Don't buy the
dip, buy strength after the dip"); stop below the dip low, scale out in thirds, hold days to a few weeks.

---

## 1. Rules as taught

### 1.1 Universe and scan

- Liquid US stocks (and, since the 2020s, crypto). Shannon says he screens roughly **1,100 liquid stocks weekly** and narrows
  to about **150 setup candidates** for the week (CMT Fill the Gap ep. 61, recorded 2026-02-04) **[primary, from episode
  page summary]**. No published dollar-volume or price floor; the engine's `universe:` block (price >= $5, ADV >= 500k
  shares, $5M dollar volume) is a reasonable proxy.
- Scan logic is structural, not indicator-threshold based: stocks in a **Stage 2 markup** (higher highs / higher lows on the
  daily, price above a rising 50-day SMA) that have **pulled back** toward the rising 5-day MA and/or a rising AVWAP from a
  meaningful anchor **[primary + secondary]**.
- Shannon explicitly **does not** use relative-strength ranking or inter-market analysis for swing selection; he says they
  complicate decisions without improving results (Fill the Gap ep. 61) **[primary]**.
- Members' trade ideas are split into lower-volatility "official ideas" and more volatile "watch list ideas" (sweep note,
  youtube entry) **[secondary]**.

### 1.2 Market filter (the higher timeframes)

Shannon's framework from *Technical Analysis Using Multiple Timeframes* (2008): "Start with the long-term timeframe to
determine overall money flows; then move to intermediate term to plan the trade and finally consult the short-term chart to
fine-tune entries and exits." At least three timeframes should agree **[secondary: FinancialWisdomTV summary and fintwit
sweep; consistent with his 2026 podcast]**.

- **Primary trend:** weekly chart. **Intermediate / stage identification:** daily chart. **Execution:** intraday chart
  (Goodreads / Seeking Alpha reviewer descriptions) **[secondary]**.
- **Four stages** of the cycle (his 2008 book): accumulation, markup, distribution, markdown (decline). Longs are only taken in
  markup (Stage 2); shorts in decline (Stage 4) **[secondary]**.
- **Moving averages are reference points, not triggers.** In 2026 he repeats that the 5-day, 50-day and 200-day are "levels
  of interest, not a place to do business" and that "a close above the 50-day isn't automatically bullish"; "a rising vs
  falling moving average changes everything" (Fill the Gap ep. 61; WOLF Financial masterclass 2026-08-20) **[primary]**.
  A 2023 interview snippet adds that the **direction of the 20-day MA matters more than whether price is above or below
  it** **[unverified: search snippet only]**.
- **Index / sector context via long anchors:** he reads the market with AVWAPs anchored to **year-to-date, quarter-to-date,
  month-to-date** and to the most recent major high/low. Example given on 2026-02-04: semiconductors "broke below year-to-date
  VWAP anchors, indicating sellers controlled positions from January forward", and the same day touched both the 50-day MA
  and the November-low anchor - "confluence but requiring validation on shorter timeframes before entry" **[primary]**.
- The AVWAP reading rule (alphatrends.net/anchored-vwap): "When a stock is above an advancing AVWAP, buyers are in control";
  "when prices are below a declining AVWAP, sellers are in control"; "when prices oscillate above and below the AVWAP it
  indicates indecision" **[primary]**. Book phrasing: above an up-sloping AVWAP the stock is "innocent until proven guilty";
  below a down-sloping one "guilty until proven innocent" **[secondary]**.

### 1.3 Where to anchor (the one genuinely subjective input)

Alphatrends calls anchor selection "the most subjective part of our analysis" and says the anchor must be "a specific
meaningful point. That is, it is not simply the start of the trading day" **[primary]**. The book's anchor catalogue
**[secondary, FinancialWisdomTV summary; matches the fintwit sweep]**:

| Anchor class | Examples as taught | Mechanical proxy |
|---|---|---|
| High-volume event | sessions with volume **> 1.5x normal** | max-volume bar in lookback, or `rvol_day >= 1.5` |
| Fundamental event | earnings release, Fed announcement (anchor to the 2:00 PM ET bar), regulatory news | earnings date from the calendar feed; FOMC dates |
| Price event | significant swing high / swing low, prior major pivot | pivot-detected swing high/low (`features/levels.py` style) |
| Gap | breakaway, continuation, exhaustion gaps | `gap_pct` beyond a threshold |
| IPO | anchor to the **second** intraday candle, not the first, because of the opening print's volume | first session after listing |
| Calendar | year-to-date, quarter-to-date, month-to-date (used mostly for the index/sector read) | fixed calendar anchors |

Precision rule: anchor "on as short a timeframe as possible" so the starting bar is the actual event bar **[primary]**.
Randomly placed anchors are explicitly disallowed **[secondary]**.

### 1.4 Entry (long; mirror for shorts)

The entry is the "**Don't Buy the Dip, Buy Strength After the Dip**" sequence. The three objective signals that strength has
returned, in Shannon's words on alphatrends.net **[primary]**:

1. "Higher highs and higher lows" - "the basic signature of a trend regaining its footing" (on the execution timeframe).
2. Reclaimed key levels (the 5-day MA, a prior intraday high, a broken support level).
3. The AVWAP from the prior high: "The AVWAP tells me whether the average participant from a prior high is winning or losing.
   When they move back into a winning position, buyers are in control."

Putting the timeframes together (synthesis of primary + secondary sources):

- **Setup (daily):** Stage 2 stock; price has pulled back toward the rising 5-day MA and/or a rising AVWAP anchored at the
  swing low / earnings / breakout bar; ideally on declining volume. The sweep's fintwit entry summarises the preferred
  configuration as "price above rising 5-day MA + above AVWAP + above longer MAs" **[secondary]**.
- **Do not buy the first touch.** "Avoid premature entry: wait for confirmation of strength after the dip, not at first
  touch" **[secondary]**. "First one or two touches on AVWAP anchored to an important point are more likely to see strong
  moves"; "the more times AVWAP support or resistance is tested, the more likely it is to fail" **[secondary]**.
- **Trigger (65-minute / 15-minute / 5-minute):** the short-term downtrend of the pullback ends - a higher low forms, then
  price takes out the prior short-term high and reclaims the 5-day MA (and the AVWAP anchored to the pullback's high turns
  from resistance to support). Buy on that confirmation. For momentum entries he consults 1-10 minute charts after the daily
  setup is confirmed **[secondary]**, and in 2026 lists his working timeframes as weekly, daily, 65-minute, 15-minute,
  5-minute and 1-2 minute **[primary]**.
- **Breakout variant (2026 masterclass):** "most breakouts fail because traders buy a move that's already run too far"; the
  AVWAP from the prior high tells you whether you are "early to a breakout or chasing a trap" **[primary]**.
- **Pinch variant:** two AVWAPs (from a significant high and a significant low) converge with price between them; trade the
  resolution only "after the break confirms" (closes beyond the line, a retest that fails to reclaim it) - never pre-empt
  **[secondary: book summary; LuxAlgo concept page attributes the read to Shannon]**.
- **Handoff:** when the trend accelerates after an AVWAP test, drop a fresh anchor at the new pivot (the breakout bar) and
  manage against that "momentum layer"; the violated/older anchor loses relevance **[secondary]**.

### 1.5 Stop

- Structure-based, never arbitrary: long stop "at the low of the dip"; short stop "at the high of the bounce"
  **[secondary, book summary]**.
- Practical size from his 2026 podcast example: "I'm looking at a 1.8% stop based on that prior high or low. If that's
  violated, that's my stop" **[primary]**. Treat 1.8% as an example from a tight intraday-timed entry, not a fixed rule.
- A decisive close through the most recent anchor's AVWAP invalidates the thesis (the sweep's books_blogs entry calls the
  current anchor the "point of ruin") **[secondary]**.

### 1.6 Exits and targets

He describes "definitive rules of engagement, rules for when and where I trim my first third" (Fill the Gap ep. 61) **[primary]**:

- **First third** off "profitably under pretty strict circumstances" - the stated reference is the **daily R2 floor-trader
  pivot**; the episode summary cites a statistic that about **86% of daily range is contained within S2/R2** **[primary
  statement, statistic reported second-hand from the episode page]**.
- **During a momentum run:** raise the stop beneath prior **2-minute lows**.
- **Trailing the swing:** trail under **higher lows on the 15-minute chart while price stays above a rising 5-day MA**.
- **Thesis exit:** 5-day MA rolls over / price loses the AVWAP it was riding; on the pinch, the surviving AVWAP becomes the
  trailing reference **[secondary]**.
- No fixed R-multiple target is taught; targets are prior highs, pivots and "let the trend tell you".

### 1.7 Sizing

- No per-trade risk percentage is stated in any source fetched this session **[gap]**. He does say he typically holds
  **6-7 positions** and treats his own over-allocation as a contrary indicator: "When I start getting over allocated... it
  typically means we're getting a little overheated" **[primary]**.
- "Managing risk is Job One"; "clearly defined risk" before entry (alphatrends.net) **[primary]**.
- Engine default (1% of equity at risk, max 8 positions, 10% max position) is consistent with his position count.

### 1.8 Holding period

"Three to six days" typical, "occasionally extending to five or six weeks" (Fill the Gap ep. 61) **[primary]**. He discourages
day trading for most people and frames the method as swing trading timed with intraday charts **[primary]**.

### 1.9 The 5-day MA across timeframes (the arithmetic)

Shannon keeps the *same* 5-day moving average on every intraday chart by converting it to bars of regular-hours time
(390 minutes/day, 1,950 minutes per five days) **[unverified: search snippet of a NinjaTrader session page and TradingView
script descriptions; the page itself redirected endlessly]**:

| Chart | Bars per RTH day | 5-day MA length |
|---|---|---|
| Daily | 1 | 5 |
| 65-minute | 6 | 30 |
| 30-minute | 13 | 65 |
| 15-minute | 26 | 130 |
| 5-minute | 78 | 390 |

65 minutes is used because it divides the 390-minute session evenly (6 bars), unlike 60 minutes.

---

## 2. Chart signatures

1. **Stage 2 staircase:** daily higher highs / higher lows, price above a rising 50-day SMA, 50 above 200.
2. **Rising AVWAP under price:** the AVWAP anchored at the swing low (or earnings gap) slopes up and price has not closed
   below it; steeper slope = more aggressive control by buyers.
3. **Orderly pullback:** 2-6 days of lower highs on contracting volume that drifts into the rising 5-day MA / AVWAP zone
   without a high-volume breakdown.
4. **Strength after the dip:** on the 65-min / 15-min chart the pullback's own downtrend breaks - a higher low, then a close
   above the prior intraday high and above the 5-day MA; the AVWAP anchored at the pullback's high is reclaimed.
5. **Confluence:** AVWAP + 5-day MA + prior support within a tight band ("Where multiple Anchored VWAP lines converge, that
   can indicate an especially strong area of support or resistance" - StockCharts ChartSchool).
6. **Pinch:** AVWAP-from-high and AVWAP-from-low converging with price sandwiched; resolution bar closes outside and the
   retest holds.
7. **Failure signature (do not trade):** price "oscillating above and below the AVWAP" (indecision), flat AVWAP, or a level
   that has already been tested 3+ times.

---

## 3. Who teaches it

- **Brian Shannon, CMT** - founder of Alphatrends (2006); CMT 2013; ex-Lehman Brothers / Tucker Anthony / MarketWise
  Securities. Books: *Technical Analysis Using Multiple Timeframes* (LifeVest Publishing, 2008, 184 pp; Goodreads 4.20 from
  447 ratings) and *Maximum Trading Gains with Anchored VWAP* (AlphaTrends.Net Publishing, 2023). He stresses he
  **popularized** AVWAP but did not invent it: Dr. Paul Levine's MIDAS work (~1996) and VWAP as an execution benchmark
  (1988) came first **[primary]**. The 2023 book is reported to be in the CMT Level 2 and 3 curriculum **[unverified beyond
  the episode page]**.
- Channels: alphatrends.net (Premium, 5 daily videos, Discord, "$59/month" trial listed), X @alphatrends ($10/month
  subscription), YouTube @alphatrends, StockTwits, courses "Intro" and "Advanced Stock Trading". Trademarked mottos:
  "Only Price Pays" and "Don't Buy the Dip, Buy Strength After the Dip".
- Alphatrends team: Andy Moss, CMT (ex-Morgan Stanley PM) and Andrew Menaker, PhD (trading psychology).
- Secondary teachers / amplifiers: CMT Association "Fill the Gap" podcast ep. 61 (Feb 2026); MoneyShow MoneyMasters podcast
  (2025-03-27, "STOP Buying the Dip"); TraderLion podcast (2023-04-15); Investing With The Whales ep. 20 (2023-04-03);
  Tactical Edge Trading video "Anchored VWAP vs Session VWAP" (posted 2026-06-08); WOLF Financial masterclass (2026-08-20);
  Bear Bull Traders (Andrew Aziz) hosted him and co-authored the VWAP paper below; StockCharts ChartSchool features his AVWAP
  video; LuxAlgo's "VWAP pinch" library page credits him; Trade-Ideas (AVWAP feature) **[secondary]**.
- Community tooling: TradingView scripts "Brian Shannon 5-Day MA Background" (Sunlord75), "Multi VWAP [MW]" (mwrightinc),
  "Multi-Day Rolling VWAP [Intraday]" (fyntrade), "dc_Swing Traders Setup v2" (donaldecotton), "[TTI] Pinch AVWAPs",
  "Anchored VWAP Pinch Handoff Intervals and Signals".

---

## 4. Evidence

**There are no published performance statistics for Shannon's method itself.** He gives only a self-reported win rate of
"50 to 60% of the time" over full cycles **[primary, unaudited]**. The method is discretionary at the anchor and the
intraday-timing steps, so no vendor or academic study tests it as taught. What exists:

1. **Zarattini & Aziz (2023/2024), "Volume Weighted Average Price (VWAP): The Holy Grail for Day Trading Systems"** (SSRN
   4631351; Concretum / Bear Bull Traders). *Session* VWAP, not anchored: long QQQ when the 1-minute close is above the
   day's VWAP, short below, flat at the close; 2018-01-02 to 2023-09-28. Reported: $25,000 -> $192,656 (671%), max DD 9.4%,
   Sharpe 2.1, vs buy-and-hold QQQ 126% / 37% DD / Sharpe 0.7; TQQQ variant 8,242%. "Net of commissions", no slippage detail.
   **Independent replication on QuantConnect (forum 16706) did not reproduce it**: Algo_dude's version underperformed; Jared
   Broad (QuantConnect) noted it is "pretty sensitive to the minimum filter and gets eaten alive by covid"; Evgenii Lazarev's
   config-matched version: "out-of-sample and after realistic spreads it looks a lot less exciting than the headline
   numbers." Takeaway for this method: VWAP-as-trend-filter has *some* signal, but the headline numbers are an in-sample,
   cost-light artefact.
2. **VWAP vs close in classical technical rules (EFMA 2012 conference paper, Barcelona):** the search abstract reports that
   substituting VWAP for the closing price in popular technical rules on NYSE/AMEX stocks was *less* profitable
   **[unverified: PDF fetch failed on a certificate error]**.
3. **Ayrat Murtazin (2025-01-08):** a daily VWAP-crossover test on the 50 largest S&P 500 names, 2020-2023, "mixed"; it names
   a few winners (INTC, BA, DIS, META, CRM, MDT) and gives no aggregate win rate or profit factor **[secondary, weak]**.
4. **Andrew Coles, Technical Analysis of Stocks & Commodities (Sept 2008):** argues a MIDAS-style anchored VWAP is "a powerful
   predictor of support and resistance" at major daily-chart reversals **[unverified: abstract only]**.
5. **Indirect, stronger evidence for the components:** the engine's own `pullback_trend` strategy family (Raschke "Holy
   Grail" / MA-pullback-in-trend) and the trend-following literature behind `trend_state` (50/200 SMA) are the quantified
   cousins; the AVWAP adds a volume-weighted cost-basis line that is conceptually similar to the "average cost of holders"
   anchoring effect studied in behavioural finance (capital-gains overhang), but no paper tests Shannon's pullback trigger.

Net: **evidence grade C.** Plausible mechanism (trend persistence + cost-basis support + volume-confirmed entries), zero
audited track record, and the one headline VWAP study is a day-trading result that failed independent replication.

---

## 5. Pitfalls

1. **Anchor subjectivity.** Shannon himself calls it the most subjective step; LuxAlgo: "anchor choice stays discretionary;
   there is no single correct set." Two traders can draw different lines on the same chart; any automation must fix a
   deterministic anchor menu and then live with it.
2. **First-touch buying.** The whole point of "buy strength after the dip" is that the first touch of AVWAP/5-day MA is not
   an entry; most naive AVWAP backtests test exactly the first touch.
3. **Over-tested levels.** Each additional test of an AVWAP weakens it; count tests and skip 3+.
4. **Choppy / flat-AVWAP regimes.** Explicitly excluded by the book; price oscillating through the line = no trade.
5. **Daily-bar AVWAP is an approximation.** True AVWAP from an intraday event (earnings at 4:05 PM, FOMC at 2:00 PM) needs
   intraday bars; a daily typical-price x volume cumulation is close but not identical, and split/dividend adjustment must be
   applied consistently to price *and* volume or the line jumps.
6. **Look-ahead in swing-high/low anchors.** A pivot is only confirmed N bars later; anchoring at "the swing low" in a
   backtest must use the confirmation date, not the pivot date, for the signal (the pivot date is fine for the calculation).
7. **Chasing extended breakouts.** "Most breakouts fail because traders buy a move that's already run too far."
8. **Intraday timing requires intraday data and attention.** The 65/15/5-minute confirmation and 2-minute stop-raising are
   where the edge is claimed; on daily bars the method degrades to a generic MA-pullback system.
9. **Marketing surface.** Most alphatrends.net pages are promotional; rules live in the books, courses and member videos,
   so "as taught" details beyond those cited here are paywalled.
10. **Position-count creep.** Shannon treats his own over-allocation as a sell signal; an automated book will not feel that.

---

## 6. 2025-2026 fit

- **Shannon's own 2025-2026 commentary is consistent and active.** March 2025 (MoneyShow): the "stop buying the dip" message
  explicitly addressed "high-volatility conditions"; Feb 2026 (CMT podcast): semis below the YTD AVWAP = sellers in control,
  with a 50-day + November-low confluence that still needed short-timeframe validation; June 2026: AVWAP vs session VWAP
  video; Aug 2026: WOLF masterclass on failed breakouts (semis, Nebius, Bitcoin, SpaceX examples); weekly analysis posts
  continue through 2026-09-25 and a seminar was scheduled for 2026-09-30.
- **Regime-agnostic by construction.** The rule set only takes longs above a rising AVWAP and shorts below a falling one,
  so a choppy 2025 tape should have produced *fewer* signals rather than more losses - if the "flat AVWAP = no trade" filter
  is honoured. That is a feature for a paper-trading phase: it throttles itself.
- **No independent 2025-2026 performance data exists** for the method **[gap]**. The only new quant item in the window is
  Murtazin's weak 2025 crossover test. Treat the method's current fit as unknown and measure it in the engine's walk-forward
  with the deflated-Sharpe gate.
- **Where it should help in the current engine:** as an *entry-quality filter* on top of `pullback_trend` and `sr_bounce`
  (require price above a rising AVWAP from the last confirmed swing low / earnings gap, and require the "strength after the
  dip" bar), and as a *market filter* (SPY/QQQ above rising YTD and QTD AVWAPs) alongside `market_trend_state`.

---

## 7. Automatability

### Mechanical (can be coded today, daily bars)

| Rule | Engine implementation |
|---|---|
| Stage 2 trend filter | `features/regime.py` `trend_state == 1` (close > sma_50 > sma_200, sma_50 rising over 5 bars) |
| Rising 5-day MA | add `sma_5` to `features/indicators.py` and `sma_5 > sma_5.shift(k)` |
| AVWAP from deterministic anchors | new `features/avwap.py`: cumulative sum(typical price x volume) / sum(volume) from anchor index; anchors = (a) last confirmed pivot low (reuse `levels.py` pivot width 5, signal only from confirmation date), (b) last earnings date (`data/alphavantage.py` / `data/calendar.py`), (c) max-volume bar in 63 bars with `rvol_day >= 1.5`, (d) YTD/QTD/MTD for SPY/QQQ |
| AVWAP slope and side | `avwap_slope_k = avwap - avwap.shift(k) > 0`; `close > avwap` |
| Touch counting | bars where `low <= avwap * (1+touch_pct)` since anchor; skip if `>= 3` |
| Pullback into the zone | existing `pullback_trend` logic with `pullback_ma = sma_5` (or `ema_9`) and `max_pullback_volume_ratio <= 1.0`; also require `pb_low <= max(avwap, sma_5) * (1 + touch_pct)` |
| "Strength after the dip" trigger | `close > prior high` **and** `close > sma_5` **and** `close > avwap` on the as-of bar (already the `pullback_trend` entry test, add the two extra conditions) |
| Stop | `pullback_low - stop_atr_buffer * atr_14` (existing) or `min(pullback_low, avwap)`; cap at `max_stop_pct` (e.g. 3%, Shannon's example is 1.8%) |
| Targets / exits | first third at prior swing high or daily R2 (`R2 = pivot + (high - low)` from the prior bar, pivot = (H+L+C)/3); trail under higher lows while `sma_5` rising; thesis exit on close below AVWAP. Needs a partial-exit path in `execution/order_manager.py` (currently one target) |
| Market filter | `market_trend_state == 1` plus SPY/QQQ `close > avwap_ytd` and `avwap_qtd` rising |
| Sizing | `risk/sizing.py` fixed-fractional 1%, `max_open_positions` 8 -> consider 7 to match Shannon |
| Holding period | hard time stop 30 trading days (5-6 weeks); typical 3-6 days falls out of the trail |

### Discretionary (keep human / Claude-review, never numeric)

- Which of several candidate anchors is "the" meaningful one when they disagree (the engine should emit all and let the
  review flag conflicts as an enum).
- Judging "choppy market" beyond a flat-slope test; news context (the engine's monitor can supply the event, not the judgement).
- The 65/15/5-minute confirmation and 2-minute stop management: only partially codable without intraday bars in the panel.
  `features/rvol.py` and the `alpaca_stocks` adapter already consume intraday data for the monitor; a 65-minute resample
  (`6 bars/day`, 5-day MA = 30 bars) is the natural first step.
- Handoff timing (when to re-anchor on acceleration).

### Proposed engine objects

- `features/avwap.py`: `avwap_from(bars, anchor_idx)`, `add_avwap(panel, anchors=["pivot_low","earnings","max_vol_63","ytd"])`
  -> columns `avwap_pl`, `avwap_earn`, `avwap_vol`, `avwap_ytd`, `avwap_*_slope5`, `avwap_*_touches`.
- `strategies/avwap_pullback.py` (`@register("strategy", "avwap_pullback")`): params `anchor_pref`, `touch_pct 0.01`,
  `max_touches 2`, `pullback_bars 2..6`, `max_pullback_volume_ratio 1.0`, `max_stop_pct 3.0`, `first_third_at "r2"|"swing_high"`,
  `time_stop_bars 30`, `P_MIN_TREND = TREND_UP`, `P_MIN_MARKET_TREND = TREND_UP`.
- Monitor rule: `avwap_reclaim` (price crosses back above a falling-to-flat AVWAP from the prior high on `rvol >= 1.5`) as a
  P2 "strength after the dip" alert for watchlist names.
- Backtest hygiene: every anchor computed point-in-time; pivot anchors signal only from confirmation date; log the trial count
  for the anchor-menu grid in `research/trials.py` before reading any Sharpe.

---

## 8. Sources

Primary (Shannon / Alphatrends)
- https://alphatrends.net/
- https://alphatrends.net/anchored-vwap/
- https://alphatrends.net/dont-buy-the-dip-buy-strength-after-the-dip/
- https://alphatrends.net/only-price-pays/
- https://alphatrends.net/understanding-market-structure/ (landing page only)
- https://alphatrends.net/swing-trading-guide/ (landing page only)
- https://alphatrends.net/technical-analysis-multiple-timeframes/
- https://alphatrends.net/anchored-vwap-book/
- https://alphatrends.net/end-of-week-market-analysis/
- https://alphatrends.net/archives/analysis/stock-market-crypto-analysis-for-week-ending-9-25-26/ (video/charts only)
- https://alphatrends.net/archives/analysis/stock-market-video-analysis-for-week-ending-9-18-26/
- https://alphatrends.net/archives/analysis/stock-market-crypto-analysis-9-11-26/
- https://alphatrends.net/archives/podcast/brian-shannon-featured-in-discussion-on-anchored-vwap-and-market-structure/ (2026-06-08)
- https://alphatrends.net/archives/podcast/brian-on-ninjatrader-05-18-25/ (redirect loop this session; 5-day MA / 65-min arithmetic from snippet)
- https://alphatrends.net/archives/podcast/the-avwap-trading-indicator-secrets-and-setups-brian-shannon-traderlion-041523/ (redirect loop this session)
- https://alphatrends.net/archives/2023/03/interview-stockbsessed-03112023/ (404 this session)
- https://alphatrends.net/archives/podcast/investing-with-the-whales-interview-brian-shannon-040323/
- https://alphatrends.net/archives/podcast/conversations-about-anchored-vwap-louis-llanes-03032023-2/
- https://members.alphatrends.net/new-users/
- https://twitter.com/alphatrends ; https://www.youtube.com/@alphatrends ; https://stocktwits.com/alphatrends
- https://www.amazon.com/Maximum-Trading-Gains-Anchored-VWAP/dp/B0BLZMMLLJ (page did not render)

Interviews / podcasts 2025-2026
- https://cmtassociation.org/podcast/fill-the-gap-episode-sixty-one-anchored-vwap-legend-brian-shannon-cmt/ (recorded 2026-02-04)
- https://cmtassociation.buzzsprout.com/1551823/episodes/18757261-episode-61-anchored-vwap-legend-brian-shannon-cmt
- https://masteremail.podbean.com/e/stop-buying-the-dip-start-doing-this-instead-w-brian-shannon (MoneyShow, 2025-03-27)
- https://wolf.videonest.co/videos/2086744/anchored-vwap-and-moving-averages-full-breakout-st-BLF7bPpLuW (2026-08-20)
- https://investingwiththewhales.substack.com/p/brian-shannon (2023-04-03)

Book summaries / reviews (secondary)
- https://www.financialwisdomtv.com/post/maximum-trading-gains-using-price-time-volume
- https://en.wikipedia.org/wiki/Brian_Shannon
- https://www.goodreads.com/book/show/5861135-technical-analysis-using-multiple-timeframes
- https://seekingalpha.com/article/134296-book-review-brian-shannon-s-technical-analysis-using-multiple-timeframes (403 this session)
- https://www.scribd.com/document/1008610992/Technical-Analysis-Using-Multiple-Timeframes-Report

Independent descriptions and tooling
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap
- https://www.luxalgo.com/library/concept/vwap-pinch/
- https://www.luxalgo.com/library/indicator/VYu6A3GB-anchored-vwap-pinch-handoff-intervals-and-signals/
- https://www.tradingview.com/scripts/brianshannon/
- https://www.tradingview.com/script/boJY0VmI-Brian-Shannon-5-Day-MA-Background/
- https://www.tradingview.com/script/L8cxNVC7-Multi-VWAP-MW/
- https://www.tradingview.com/script/mBkObMct-Multi-Day-Rolling-VWAP-Intraday/
- https://www.tradingview.com/script/EQBZI5Et-dc-Swing-Traders-Setup-v2/
- https://www.tradingview.com/script/VYu6A3GB-Anchored-VWAP-Pinch-Handoff-Intervals-and-Signals/
- https://www.tradingview.com/script/gjFSGRCo/ (Dynamic Swing Anchored VWAP STRAT, Zeiierman; repainting swing labels noted)
- https://il.tradingview.com/scripts/brianshannon/

Evidence
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351 (403 this session)
- https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/
- https://bearbulltraders.com/?p=2606339
- https://www.quantconnect.com/forum/discussion/16706 (replication thread)
- https://efmaefm.org/0efmameetings/efma%20annual%20meetings/2012-Barcelona/papers/EFMA2012_0609_fullpaper.pdf (certificate error this session)
- https://www.traders.com/Documentation/FEEDbk_docs/2008/09/Abstracts_new/Coles/coles.html
- https://ayratmurtazin.beehiiv.com/p/i-tested-this-strategy-on-the-100-largest-us-companies-here-are-the-results (2025-01-08)
- https://alphatrade.readthedocs.io/en/latest/_vwap_2020.html (VWAP execution-tracking literature, context only)

Engine files referenced
- /Users/personal/Desktop/swing-engine/swing_engine/strategies/pullback_trend.py
- /Users/personal/Desktop/swing-engine/swing_engine/features/regime.py
- /Users/personal/Desktop/swing-engine/swing_engine/features/levels.py
- /Users/personal/Desktop/swing-engine/swing_engine/features/rvol.py
- /Users/personal/Desktop/swing-engine/swing_engine/risk/sizing.py
- /Users/personal/Desktop/swing-engine/config/settings.yaml
- /Users/personal/Desktop/swing-engine/docs/research-raw/methods-sweeps/merged_compact.json (methods[7])
