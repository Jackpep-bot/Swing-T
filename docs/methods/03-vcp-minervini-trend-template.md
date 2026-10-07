# 03 — VCP breakout / Minervini Trend Template (SEPA)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Tags: "(primary)" = Minervini's own books,
interviews or site; "(book, from knowledge)" = a rule as printed in his books that this run could not re-fetch
online (no free full text), stated from the book and flagged so it can be checked against a physical copy;
"(secondary)" = third-party summaries or replications; "(unverified)" = could not be checked against a primary
source in this run. No number below was invented; where sources disagree both are shown.*

**One line.** Only buy stocks already in a confirmed Stage 2 uptrend (the 8-point Trend Template: price above a
rising 50 > 150 > 200-day MA stack, ≥30% above the 52-week low, within 25% of the 52-week high, RS rank ≥70),
preferably with accelerating earnings, and only on a breakout through the pivot of a Volatility Contraction
Pattern (2–6 progressively smaller pullbacks, each roughly half the prior, with volume drying up); stop just
under the last contraction low, never more than 10% (aim for 5–6% on average), risk 1.25–2.5% of equity per
trade, move to breakeven once the trade is a multiple of the risk, sell into strength or on a 50-day violation.

**Lineage.** Stan Weinstein's stage analysis (1988, Stage 1 base → Stage 2 advance → Stage 3 top → Stage 4
decline) + William O'Neil/IBD (CAN SLIM, cup-with-handle pivots, RS rating, the 7–8% loss rule) + Nicolas
Darvas boxes. Mark Minervini named the pieces: **SEPA®** (Specific Entry Point Analysis — trend, fundamentals,
catalyst, entry point, exit point — five-element breakdown from knowledge), the **Trend Template**, and the **VCP**. Canonical texts:
*Trade Like a Stock Market Wizard* (McGraw-Hill, 2013; ch. 5 trend/stage analysis and the Trend Template,
ch. 10 "Mastering the Volatility Contraction Pattern"), *Think & Trade Like a Champion* (2017; risk, position
sizing, selling), *Mindset Secrets for Winning* (2019). Schwager profiled him in *Stock Market Wizards* (2001).

---

## Rules

### Universe and scan
**Trend Template — all 8 must be true** (Trade Like a Stock Market Wizard, ch. 5; criteria 1–7 quoted verbatim in
the ProRealCode reproduction of the book list, criterion 8 as reproduced by actionalerts/elitetrader):

| # | Criterion as taught | Typical code (daily bars) |
|---|---|---|
| 1 | "The current stock price is above both the 150-day (30-week) and the 200-day (40-week) moving average price lines." | `close > sma150 and close > sma200` |
| 2 | "The 150-day moving average is above the 200-day moving average." | `sma150 > sma200` |
| 3 | "The 200-day moving average line is trending up for at least 1 month (preferably 4–5 months minimum in most cases)." | ProRealCode: `summation[20](ma200 > ma200[1]) = 20` (up every day for 20 bars); looser: `sma200 > sma200.shift(21)`; Bob Weissman's MarketSmith versions use a "one-month" and a "five-month" template |
| 4 | "The 50-day (10-week) moving average is above both the 150-day and 200-day moving averages." | `sma50 > sma150 > sma200` |
| 5 | "The current stock price is trading above the 50-day moving average." | `close > sma50` |
| 6 | "The current stock price is at least 30 percent above its 52-week low." (book adds: many of the best are 100%, 300% or more above the low before the big advance) | `close / min(low, 250) >= 1.30` |
| 7 | "The current stock price is within at least 25 percent of its 52-week high (the closer to a new high the better)." | `close / max(high, 250) >= 0.75` |
| 8 | Relative-strength ranking (IBD RS Rating) "no less than 70, and preferably in the 80s or 90s". | IBD's RS is proprietary; open replications use a cross-sectional percentile of a weighted 3/6/9/12-month return (approximation, not IBD's formula) |

Note: ProRealCode's screener (Nicolas, 13 Apr 2017) codes only criteria 1–7 (RS omitted) and uses 250 bars for
the 52-week window; several "7-criteria" web versions use 25% instead of 30% above the low — the book says 30%.

**Fundamental layer (SEPA "E" — earnings).** Minervini's superperformers show rising EPS, sales and net margins;
**"Code 33"** = three consecutive quarters of acceleration in EPS, sales **and** profit margins (secondary,
consistent across screener.in "Code 33" screens and summaries). Numeric growth floors seen in secondary write-ups
vary: quarterly EPS ≥ 20% (preferred 25%+ or 40–50%+), sales growth 15–20%+ (Finer Market Points 2026; Deepvue
Jul 2024) — **not** confirmed as fixed thresholds in the primary text; treat as house-style screens. Deepvue
adds "industry group in the top quartile".

**Power Play (the one exception to the earnings requirement)** (book, p. ~253 per Stockopedia; secondary):
an explosive move of **≥100% within ≤8 weeks** on huge volume, then a tight sideways range that corrects **no
more than 20%** (some lower-priced stocks up to **25%**) over **3–6 weeks**, with volume contracting before the
breakout; "little regard to fundamentals". Functionally Minervini's high-tight-flag.

**Stage rule.** Buy only in Stage 2; never Stage 1 (neglect), Stage 3 (topping, volatile) or Stage 4 (declining).
Late-stage bases (third/fourth base in a Stage 2 run) are riskier than first/second bases (book, from knowledge).

### Market filter
Minervini does **not** publish a mechanical index rule; the market read is bottom-up and feedback-driven:
- **Leadership breadth**: how many stocks pass the Trend Template. Bob Weissman's MarketSmith walkthrough
  (7 Jan 2019) showed the 5-month template list shrinking from ~670 stocks (fall 2018) to 127, and the
  1-month list from ~90 to 21, during the Q4-2018 decline — "a really nice gauge on the market" (secondary).
- **% of stocks above the 200-day MA**: in his mid-2025 MarketWatch interview he flagged that "the percentage of
  stocks that are above their 200-day moving average is still very low" (bifurcated, top-heavy market) (primary,
  via Michael Sincere's expanded transcript).
- **His own results as the signal** ("progressive exposure"): start with small pilot buys after a correction;
  add size only as trades work; cut back when stops are being hit (Think & Trade, from knowledge; described by
  many secondary summaries).
- **Index timing model** for his service: Minervini Private Access advertises a "SPY timing model"; in the 2025
  interview he said an **8 May (2025) buy signal** put him "100% into the S&P 500" (primary, rule set not public).
- Mechanical proxies used by replications: **major index above its 200-day SMA** (sofus-nl VCP spec;
  Finer Market Points), or SPY trend state. A widely repeated "90.77% of successful breakouts occur when indices
  trade above monthly 10-EMA" (Finer Market Points, Apr 2026) has no traceable source — **unverified**.
- The Trend Template is itself a regime filter: in corrections few stocks qualify, so the setup count collapses
  (FWTV's 2025–26 VCP study found only 11% of setups in correction months).

### Entry
- **Setup = VCP** (book ch. 10; numbers corroborated by Tikam Alma's book quotes, Feb 2025):
  - "a sequence of anywhere from **two to six** price contractions", typically **two to four**.
  - "each successive contraction is generally contained to about **half** (plus or minus a reasonable amount)
    of the previous pullback or contraction". Book example: off **25%** from the high, rally, then **15%**,
    then **8%** (other examples in summaries: 20/10/5, 18/12/6, 15/8/4).
  - Volume contracts with price; in the final contraction volume "dries up" to among the lowest levels since the
    advance began. Secondary numeric versions: pullback volume ≈ **40–60% of the 50-day average** (Finer Market
    Points) — **unverified as a book number**.
  - **Footprint notation** (Minervini's shorthand on charts): `VCP 6W 29/7 3T` = base length **6 weeks**,
    deepest correction **29%**, final contraction **7%**, **3 contractions** ("T"s) (secondary; examples on
    TradingView charts in his notation).
  - Base length: summaries give 4–12 weeks as typical (Finer Market Points) and warn against bases shorter than
    ~3 weeks; the book's examples range from a few weeks to over a year — exact book range **unverified** this run.
  - Prior uptrend: the stock must already be in Stage 2 (Template) — replications require a ≥25–30% advance
    before the base (sofus-nl: ≥25%; Tikam Alma scanner: ≥30%).
- **Pivot** = the high of the last, tightest contraction (the "line of least resistance"). Buy as price trades
  through the pivot; replications use a buy-stop 1–2% above the pivot (secondary).
- **Breakout volume**: should expand; the most common coded threshold is **≥40–50% above the 50-day average
  volume** (sofus-nl spec, Finer Market Points); the swing-engine's `breakout_52w` flag uses 1.5×.
- **Do not chase**: buy close to the pivot; summaries put the limit at **≤5% above the pivot** (O'Neil's rule,
  repeated for VCPs by Finer Market Points) — in practice Minervini's tight stops make chasing self-limiting.
- **Alternative (earlier, lower-risk) entries** within the same base (book/Think & Trade, from knowledge):
  the **"cheat" / 3C (cup completion cheat)** — buying a small pause/handle in the lower or middle third of a
  cup as it turns up, before the classic pivot; the **"low cheat"** in the lower third. These trade lower
  confirmation for a tighter stop.

### Stop
- Stop just under the low of the final contraction (the logical "you are wrong" level). Replications: sofus-nl
  uses 1.5× ATR(14), "typically just below the final contraction low".
- **Absolute maximum loss: 10%** (Trade Like a Stock Market Wizard — "capping losses at a maximum of 10%",
  Shortform summary). Average loss target **≈5–6%** (Think & Trade summaries); "get out at single digits"
  (2025 MarketWatch interview, primary). Several secondary write-ups quote 7–8% — that is O'Neil's number.
- Stops are pre-defined before entry and executed without exception ("sell for a small loss before it becomes a
  large loss", 2025 interview).
- Rule of thumb relating stop to gains: the stop should be no bigger than a fraction of the average gain
  (he frames edge as a reward/risk relationship such as 3:1) (secondary; exact formula **unverified**).

### Exits and targets
No fixed price target; the exit plan has three layers (Think & Trade, from knowledge; corroborated in part by
secondary summaries):
1. **Protect**: once the stock has risen a multiple of the initial risk (commonly cited **2–3×**), raise the stop
   to **breakeven** or better; "never let a good-sized gain turn into a loss". Shortform's summary: once the
   initial target is reached, trail the stop with the **50-day MA** so the trade is at worst breakeven.
2. **Sell into strength**: take partial profits on the way up, e.g. selling a portion at **2–3× risk**
   (≈12–20% gain on a 5–8% risk) (secondary). Climax signs to sell into: after a **25–50% run in 1–3 weeks**,
   the **largest up day since the move began**, followed by churning/reversal over the next 1–4 days
   (secondary summary of the book's climax rules; the remaining climax checklist — exhaustion gaps, unusually
   many up days in a row — is **unverified** this run).
3. **Sell into weakness**: violation of the trailing stop; a close below the **50-day MA on heavy volume**;
   breakouts that fail back into the base (in 2025 he describes taking breakouts that fail after "one or two
   days" off quickly).
- Mechanical replications: sofus-nl VCP = 50% at **+2.0 ATR**, rest at **+4.0 ATR**, trail below the latest swing
  low after the first target; FWTV 2025–26 case study = trail **10-day EMA** for ADR > 10% names, **20-day EMA**
  otherwise.

### Position sizing
- Risk per trade **1.25%–2.5% of total equity**; never more than 2.5% (Think & Trade, per Shortform summary).
- Position size: aim for **20–25%** positions in top picks, **never more than 50%** in one stock, and **no
  more than 10–12 stocks** (Think & Trade, per Shortform summary); a typical concentrated book is 4–6 names.
  Smaller "pilot" buys when conditions are uncertain (progressive exposure).
- Formula used by every replication: `shares = (equity × risk%) / (entry − stop)`; with a 5% stop and 1.25% risk
  that is a 25% position.
- Pyramiding: add only to winners, only on new low-risk entry points; never average down (from knowledge).

### Holding period
- Swing to intermediate-term: he holds "as long as the potential reward is larger than the risk" (2025 interview).
  Typical trades last days to a few weeks; the occasional true leader is held for months on the 50-day trail.
- 2025 adjustment: shorter holds and quicker profit-taking because breakouts failed fast (Investing with IBD
  podcast, 29 Oct 2025, via secondary summaries — **unverified** transcript).
- Mechanical replications cluster at 4–15 days (EasySwing: 4-day average for both VCP and Template detectors;
  sofus-nl spec: 8–15 days).

---

## Chart signatures
1. **Stage 2 MA stack**: price > 50-day > 150-day > 200-day, all rising; the 200-day has been rising for ≥1 month
   (ideally 4–5 months). Weekly chart: price above a rising 30-week MA.
2. **Near highs, far from lows**: within 25% of the 52-week high (best within ~5–15%) and ≥30% (often 100%+)
   above the 52-week low; RS line near or at new highs before price.
3. **Contraction sequence left to right**: e.g. −25% → −15% → −8% → −3%; each swing low higher or at least not
   lower, ranges narrowing; footprint like `VCP 12W 25/4 4T`.
4. **Volume signature**: heavy volume on the left side, declining through each contraction, near-zero
   ("dry-up") days in the final, tightest area (tight closes, inside days, narrow-range days).
5. **Pivot**: a clearly defined, flat-ish high of the final contraction; breakout day closes near its high on
   volume ≥40–50% above the 50-day average.
6. **Variants**: cup-with-handle (VCP inside a cup), flat base, **3C/cheat** turn in the lower/middle third of a
   cup, **Power Play** (≥100% in ≤8 weeks, ≤20–25% sideways for 3–6 weeks).
7. **Failure signature**: breakout reverses back below the pivot within 1–2 days on volume; or the base has
   wide, loose, sloppy swings (contractions not shrinking), or the stock is a late-stage (3rd–4th) base.

---

## Who teaches it
- **Mark Minervini** — books (2013, 2017, 2019); **minervini.com / Minervini Markets 360**; **Minervini Private
  Access (MPA)** with real-time picks, weekly Q&A, a "SPY timing model", screener and "Minervini AI"; **Master
  Trader Program (MTP) workshops 2025 and 2026** (listed on minervini.com); X **@markminervini**; frequent
  guest on IBD Live / Investing with IBD and TraderLion. Two-time U.S. Investing Championship winner (1997, 2021).
- **IBD / MarketSurge** (formerly MarketSmith) — RS Rating and Trend Template screens; Bob Weissman's MarketSmith
  template video (2019).
- **TraderLion / Deepvue** (Richard Moglen et al.) — Minervini interviews, "How Mark Minervini screens" (Jul 2024).
- **Finer Market Points** (Christopher Hall) — VCP checklist and chapter recaps (Jan–Apr 2026); useful but
  carries several unsourced statistics (see Evidence).
- **Laurentiu Chisca** (wallstreettrader.substack.com) — reconstruction of Minervini's 2021 championship trades
  (Jan 2022; explicitly estimated entries/exits).
- **Tikam Singh Alma** (Substack, Feb 2025) — VCP basics with book quotes and an open scanner spec.
- **Michael Sincere** (MarketWatch, mid-2025) — expanded interview transcript.
- Screener / code authors: ProRealCode (2017), TradingView (many Trend Template and VCP scripts; most closed
  source), chartmill ("Passes Minervini Trend Template" daily notes, 2026), sharpely.in (India), screener.in
  "Code 33" screens, **sofus-nl/swing-trading-strategies + EasySwing.trading** (the only open replication with
  published out-of-sample statistics found this run).

---

## Evidence

### Self-reported (primary, unaudited)
- **U.S. Investing Championship**: **+155% in 1997**; **+334.8% in 2021** in the $1,000,000+ stock division, beating
  the prior division record of +119.1% (George Tkaczuk, 2020) (Business Wire press release, 24 Jan 2022, via search
  snippet; the page itself returned 403 to the fetcher). Contest results are broker-statement verified by the
  organiser but are one-year, self-entered contests.
- **"220% per year return over five years"** (1994–1999 era, repeated in the 2025 MarketWatch interview and on
  his marketing; a YouTube interview title says "33,554% return in 5 years"). One losing quarter in that period is
  widely repeated — **unverified** this run. Claim that "88% of trading months were positive" (search snippet) —
  **unverified**.
- No published trade-level statistics (win rate, average gain/loss) for 2021; Chisca's reconstruction warns that
  "there is no additional info regarding the exact entry, exits, or position sizes".

### Independent / mechanical replications (secondary)
| Study | Rules coded | Period / sample | Result |
|---|---|---|---|
| **EasySwing.trading performance panel** (updated 7 Jul 2026) with rules in GitHub `sofus-nl/swing-trading-strategies` (`strategies/01-vcp.md`) | Template stack (50 > 150 > 200), RS > 70, within 25% of high, prior rise ≥25%, ≥3 shrinking contractions, final-contraction volume < 50-day avg, breakout above the pivot on ≥40% volume surge; stop 1.5 ATR; 50% out at +2 ATR, rest at +4 ATR, swing-low trail; index > 200-day | ~2,000 US stocks, 5-year walk-forward, raw exits, **no fees/slippage**; **1,259 trades** | **"VCP Breakout": win 37%, avg +0.1R, profit factor 0.38, avg hold 4 days.** (The PF and avg R as displayed are mutually inconsistent — a positive avg R implies PF > 1 — so treat the row as "no demonstrated edge", not a precise number.) |
| Same panel, `strategies/16-trend-template-fresh-pass.md` | All 8 template criteria true today after failing ≥2 in the prior 20 days; stop 1.5 ATR or below SMA50 (tighter); 33% at +2 ATR; trail swing low/SMA50; exit on close < SMA50 or any template criterion failing | **18,382 trades** | **win 40%, avg +0.1R, PF 0.99, avg hold 4 days** — template entry by itself is break-even before costs |
| Same panel, related detectors | Cup & Handle (prior rise ≥30%, cup 12–35%, handle in upper 15%, RS > 80, volume +40%) / 52-week-high proximity pullback / MA Stack Confluence | 3,582 / 15,415 / 102,531 trades | PF **1.57** / **1.33** / **1.19** — the O'Neil-style base and buying pullbacks near highs inside the stack did better than the coded VCP |
| sofus-nl `01-vcp.md` cites "72% win rate in trending markets with an average 1.8R … across 48+ trades (Quantified Strategies backtest)", 45% in poor regimes | — | 48 trades | **Unverified**: the Quantified Strategies source could not be located; sample far too small anyway |
| **Financial Wisdom TV**, "Can one chart pattern beat the market? I tested the top 100 stocks" (2026) | Hand-identified VCPs (≥3 contractions) among the **top-100 performers of the prior 12 months** (mcap > £100M, price > £1, ADV > £10M); entry within ~5% of breakout; stop under final contraction (< 2× ADR, generally < 10%); trail 10-day EMA (ADR > 10%) or 20-day EMA | Aug 2025 – Apr 2026; 36 clean VCPs out of 100 winners | Avg initial risk **6%**, avg gain **69%**, avg R:R **>11:1**; 33% of setups in Aug–Sep 2025, 22% Jan 2026, 17% Apr 2026, 11% in correction months. **Survivorship-conditioned (author says so): shows what winners looked like, not expectancy** |
| sharpely.in VCP screener portfolio (India) | Vendor's rule-based VCP screen | From 3 Feb 2023 | +177.1% vs benchmark +45.5% (vendor marketing, unaudited, method not disclosed) |
| Finer Market Points checklist (Jan–Mar 2026) | — | — | Claims "80% of successful VCPs show ≥3 contractions", "40% improvement" with all criteria, "3× success rate" for Stage 2 — **no source given; treat as unverified** |

### Academic backdrop (from knowledge; papers not re-fetched this run)
- **No peer-reviewed test of the Trend Template or the VCP was found** in this run.
- What the template is made of has support: **52-week-high proximity** predicts returns and dominates plain
  momentum (George & Hwang 2004, *J. Finance*); **cross-sectional momentum** (Jegadeesh & Titman 1993, *J. Finance*)
  ≈ the RS ≥ 70 filter; **moving-average signals across horizons** carry return information (Han, Zhou & Zhu 2016,
  "A trend factor", *J. Financial Economics*; Brock, Lakonishok & LeBaron 1992, *J. Finance*, on MA rules for the
  DJIA, with the usual data-snooping caveats).
- **Momentum crashes** (Daniel & Moskowitz 2016, *JFE*; NBER w20439): momentum fails in rebounds after market
  declines and in high-volatility states — the academic case for the market/breadth gate.
- **Chart patterns** (Lo, Mamaysky & Wang 2000, *J. Finance*): some patterns carry incremental information but
  modest economic value. Volatility contraction before breakouts has no direct academic test found.

### Reading the evidence
The stack-and-near-highs **filter** is a reasonable momentum/52-week-high screen with academic backing, but
**entering simply because a stock passes it is break-even** before costs (EasySwing PF 0.99 on 18k trades). The
crude **coded VCP breakout fails** in the one open walk-forward panel. The champion results and the 11:1 case
studies come from (a) concentration (20–25% positions) in a handful of true leaders, (b) fast loss-cutting and
selling into strength, (c) regime discipline, and (d) discretionary base reading and fundamentals — the parts
that do not survive a naive scan. Expect the edge, if any, to live in **selection + exits + exposure control**,
not in the pattern trigger.

---

## Pitfalls
1. **Pattern-matching on hindsight.** VCPs are easy to see after the breakout worked; "top-100 winner" studies
   are survivorship-conditioned. The only out-of-sample panel found shows the coded VCP losing.
2. **Breakout failure regimes.** In choppy/narrow markets (2025 per Minervini) breakouts fail in 1–2 days; a
   template-only or breakout-only system without a breadth/exposure gate bleeds small losses.
3. **Concentration risk.** 20–25% positions with 5–8% stops are fine until a gap through the stop (earnings,
   guidance, halts). Gap risk is not bounded by the stop; check earnings dates.
4. **Rule creep from secondary sources.** Many web "rules" (7–8% stops, 90.77%, 80%-of-VCPs, 40–60% volume
   dry-up) are O'Neil's or unsourced. Version the parameter set and cite where each came from.
5. **RS rating is proprietary.** Any homemade RS percentile (weighted 3/6/9/12-month return) is an approximation
   of IBD's; thresholds of 70/80/90 will not mean the same thing.
6. **Late-stage bases and extended entries.** Third/fourth bases, wide-and-loose bases, and buying > ~5% above
   the pivot turn a 5% stop into a 10%+ one.
7. **The template lags at turns.** It needs the 200-day to have risen for a month+; in V-shaped recoveries the
   first leaders pass late, and in tops the template keeps passing names that are already in Stage 3.
8. **Crowding.** The Trend Template is now a commodity screen (chartmill daily notes, TradingView, MarketSurge);
   obvious pivots attract buy-stops and stop-runs.
9. **Overfitting when mechanising.** The VCP has many knobs (count, depth ratio tolerance, base length, volume
   dry-up, pivot buffer, volume surge). Few true setups per year → walk-forward and `research/trials.py` logging
   are mandatory; deflated Sharpe in `research/metrics.py`.
10. **Costs and liquidity.** Replication stats above exclude fees and slippage; breakouts fill at the worst
    prices of the day.

---

## 2025–2026 fit
- **Minervini, mid-2025 (MarketWatch, via Sincere)**: market "bifurcated", top-10 S&P names ≈ 40% of cap,
  % of stocks above the 200-day "still very low"; he went 100% long the S&P on an **8 May 2025** buy signal
  rather than relying on individual breakouts — i.e. he leaned on the index when leadership breadth was thin.
- **Investing with IBD podcast, 29 Oct 2025** (secondary summaries, transcript not verified): many breakouts
  failed after one or two days, unlike 2020; he responded by taking profits faster and tightening stops — a
  tactical, not strategic, change. Same message reported elsewhere: when breakouts stop working people abandon
  them, then they work again.
- **Setup supply tracked the tape**: FWTV's study found clean VCPs bunched in **Aug–Sep 2025**, **Jan 2026** and the
  **Apr 2026 recovery**, with very few in the Nov–Dec 2025 and Feb–Mar 2026 corrections.
- **Mechanical evidence, mid-2026**: EasySwing's walk-forward panel (7 Jul 2026) shows the coded VCP breakout
  with no edge and the fresh template pass at PF 0.99, while cup-and-handle (1.57) and 52-week-high pullbacks
  (1.33) on the same universe held up better.
- **Still actively taught and sold**: minervini.com lists MTP workshops for **2025 and 2026** and an MPA service
  with an AI chart tool and a SPY timing model; chartmill publishes daily "passes the Minervini Trend Template"
  notes through 2026. No 2026 primary statement from Minervini on the setup's hit-rate was found (X posts not
  fetchable) — **unverified**.
- **Verdict.** The Trend Template remains a sound *universe filter and breadth gauge*; the VCP breakout is a
  regime-dependent, low-to-moderate win-rate trigger whose edge in 2025–26 came in short bursts after
  corrections. Run it with a breadth gate (template-pass count / % above 200-day), quick failure exits
  (breakout back under the pivot within 1–2 days), and costs modelled.

---

## Automatability

### Mechanical (can be coded in swing-engine today or with small feature additions)
| Element | swing-engine mapping |
|---|---|
| Universe floors | `config/settings.yaml` `universe.min_price` 5.0, `min_avg_dollar_volume` 5e6, `min_avg_volume` 5e5; `dollar_vol_20d`, `avg_vol_50d` in `features/cross_section.py` |
| Template 1, 2, 4, 5 (MA stack) | `sma_50`, `sma_200` exist in `features/indicators.py`; **add `sma_150`** (one constant in the SMA window tuple) |
| Template 3 (200-day rising ≥1 month) | **add `sma_200_slope_21`** (`sma_200 / sma_200.shift(21) − 1`) or a 20-of-20 up-days count; `features/regime.py` `trend_state` only checks `sma_50` slope over 5 bars and is a weaker subset (close > sma_50 > sma_200) |
| Template 6 (≥30% above 52w low) | `low_52w` exists → **add `dist_52w_low`** (`close / low_52w − 1`) |
| Template 7 (within 25% of 52w high) | `dist_52w_high >= −0.25` (exists) |
| Template 8 (RS ≥ 70) | `ret_63d`, `ret_126d`, `ret_252d` exist; **add `ret_189d`** and a per-`ts` cross-sectional percentile `rs_rank` (e.g. 0.4·r63 + 0.2·r126 + 0.2·r189 + 0.2·r252 — an IBD-style approximation) in `features/cross_section.py` |
| `trend_template_pass` | new 0/1 feature (all 8), plus `tt_fail_count` to support a "fresh pass" variant |
| Breadth gate | **add a market-level `tt_pass_count` / `pct_above_sma200`** computed across the universe per session and broadcast like `market_trend_state` (see 06-breadth-regime-filters.md); plus existing `market_trend_state >= 1`, `market_vol_regime < 2` via `P_MIN_MARKET_TREND` in `strategies/_base.py` |
| VCP contractions | current `vcp_contraction` (`features/patterns.py`) is a fixed 3 × 20-bar range ratio — only a tightness proxy. **Add a swing-based detector**: zig-zag pivots inside the base (base start = last 52w/pivot high), measure successive pullback depths, require `n_contractions >= 2` (param, 3 preferred), each `depth_i <= k · depth_{i−1}` with k ≈ 0.5–0.75 tolerance, `final_depth <= 0.10`, `first_depth <= 0.35` (Power Play ≤ 0.25); emit `vcp_n_t`, `vcp_max_depth`, `vcp_final_depth`, `vcp_base_weeks`, `vcp_pivot`, `vcp_final_low` |
| Volume dry-up | mean volume over the final contraction / `avg_vol_50d` ≤ param (start 0.6–0.7; book gives no fixed number) — new feature `vcp_vol_dryup` |
| Breakout trigger | `close > vcp_pivot` with `rvol_day` or `volume / avg_vol_50d.shift(1) >= 1.4–1.5` (same convention as `breakout_52w`), `close_pos` high; not extended: `close / vcp_pivot − 1 <= 0.05` |
| Stop | `vcp_final_low` minus buffer, capped so `(entry − stop)/entry <= 0.10` (max) and flagged if > 0.08; ATR alternative `entry − 1.5·atr_14` as in the sofus-nl replication |
| Breakeven / partials | needs a stop-adjust hook and scale-out support (`should_exit` in `strategies/_base.py` is all-or-nothing today): move stop to entry at +2R (param), sell 1/3–1/2 at +2–3R |
| Trailing / failure exits | `should_exit`: close < `sma_50` (with `rvol_day >= 1.5` for the "heavy volume" version), or close back below `vcp_pivot` within N=2 bars of entry (failed breakout), or `trend_template_pass == 0` |
| Climax sell | `ret_5d`/`ret_21d` ≥ 0.25–0.50 within 1–3 weeks and today = largest up day since the base breakout → sell-into-strength flag (new feature) |
| Sizing | `risk/sizing.py` with `risk.risk_per_trade_pct` (1.0 now; Minervini 1.25–2.5 — keep ≤1.0 on paper), `max_position_pct` 10 (his 20–25), `max_open_positions` 8 (his ≤10–12) — keep engine limits; concentration is a discretionary edge, not something to copy blindly |
| Cost model | `docs/gates.md` per-side bps + SEC/TAF fees — required, since the published replication stats are gross |

Closest existing modules: **`strategies/breakout_52w.py`** (52w-high break on ≥1.5× volume, close near high, ATR stop,
2R target, optional `vcp_max_contraction`) — the nearest thing to a VCP breakout today; **`strategies/pullback_trend.py`**
(trend_state == 1 pullbacks; maps to the "52-week-high proximity pullback" variant that tested better);
**`strategies/sr_breakout.py`** (pivot-level break via `features/levels.py` `resistance_1`/`level_break`).
Proposed: `strategies/vcp_sepa.py` (via `.claude/skills/add-strategy`) with params `tt_ma_windows=(50,150,200)`,
`tt_sma200_rising_bars=21`, `tt_min_above_low=0.30`, `tt_max_below_high=0.25`, `rs_rank_min=70`,
`vcp_min_t=2`, `vcp_depth_ratio_max=0.75`, `vcp_final_depth_max=0.10`, `vcp_first_depth_max=0.35`,
`vol_dryup_max=0.7`, `breakout_vol_mult=1.4`, `max_extension=0.05`, `max_stop_pct=0.10`, `breakeven_at_r=2.0`,
`partial_at_r=3.0`, `trail_ma=50`, `fail_exit_bars=2`, `min_market_trend_state=1`, `min_tt_breadth` (param);
register `enabled: false` until the walk-forward backtest and trial log clear `docs/gates.md`. Also worth testing
the Trend Template purely as a **universe filter / ranker feature** for the existing strategies (cheap, and the
evidence favours it over the trigger).

### Discretionary (cannot be fully coded; keep as Claude review enums or human steps)
- **Fundamentals / Code 33** (accelerating EPS, sales, margins), catalyst, "leader of a leading group": needs a
  point-in-time fundamentals feed stamped on filing date (EDGAR XBRL — `data/edgar.py` currently handles the
  current-filings feed and Form 4 only); otherwise an `agent` review enum.
- **Base quality**: "constructive" vs "wide and loose", shakeouts/undercuts of prior lows, symmetry, late-stage
  base count — candidate review layer.
- **Cheat / low-cheat / 3C entries** and pivot choice inside an imperfect base; intraday buy-stop execution
  through the pivot (needs intraday bars or a stop order at the open; the daily panel can only use close-confirmation
  or next-open).
- **Progressive exposure** (pilot buys, scale up only when trades work) — could later be approximated by an
  equity-curve/recent-hit-rate throttle in `risk/limits.py`.
- **Selling into strength** judgement beyond the simple climax flag; holding true leaders through normal
  pullbacks.

---

## Sources
Primary (Minervini)
- Mark Minervini, *Trade Like a Stock Market Wizard: How to Achieve Super Performance in Stocks in Any Market*, McGraw-Hill, 2013 — ch. 5 Trend Template/stage analysis; ch. 10 VCP; Power Play (≈p. 253). Not fetched (no free text); rules cross-checked against the reproductions below.
- Mark Minervini, *Think & Trade Like a Champion*, Access Publishing, 2017 — risk per trade, position sizing, selling. Not fetched.
- https://www.minervini.com/ — Minervini Markets 360: MPA, 2025 and 2026 MTP workshops, SPY timing model, screener, Minervini AI
- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini — expanded MarketWatch interview (mid-2025): 155% (1997), 334.8% (2021), "220% per year … five years", May 8 buy signal, % above 200-day "still very low", "get out at single digits"
- https://www.businesswire.com/news/home/20220124005241/en/2021-United-States-Investing-Championship-Winners-%E2%80%94-Minervini-Smashes-Record — USIC 2021 press release (24 Jan 2022; 403 to fetcher, figures via search snippet)
- Investing with IBD podcast, Mark Minervini episode, 29 Oct 2025 — https://prod-01.tunein.com/podcasts/Business--Economics-Podcasts/Investing-With-IBD-p1208776 (show page; episode content via secondary summaries only)
- X: @markminervini (not fetched)

Rule reproductions and summaries (secondary)
- https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini — criteria 1–7 verbatim + screener code (Nicolas, 13 Apr 2017)
- https://actionalerts.substack.com/p/using-mark-minervinis-trend-template — criterion 8 (RS ≥ 70, preferably 80s–90s)
- https://elitetrader.com/et/threads/mark-minervinis-trend-template-question.359356/post-5400824 — template discussion incl. RS criterion
- https://tikamalma.substack.com/p/understanding-basics-of-vcp-and-creating — VCP book quotes (2–6 contractions, "about half", 25/15/8 example) and scanner spec (2 Feb 2025)
- https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist — VCP checklist (Christopher Hall, Jan 2026, upd. 10 Mar 2026; several unsourced statistics)
- https://www.finermarketpoints.com/post/trade-like-stock-market-wizard-vcp-chapter — chapter 10 recap (26 Jan 2026)
- https://www.finermarketpoints.com/post/what-is-mark-minervini-s-trading-strategy-the-complete-sepa-vcp-guide — SEPA guide (Apr 2026; "90.77%" claim unsourced)
- https://www.finermarketpoints.com/post/3-key-lessons-from-trade-like-a-stock-market-wizard
- https://www.finermarketpoints.com/post/mark-minervini-s-stock-screener-what-indicators-and-criteria-does-he-use
- https://deepvue.com/screener/how-mark-minervini-screens-for-stocks/ — Deepvue screen parameters (21 Jul 2024)
- https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-trend-template-marketsmith — Bob Weissman, "Mark Minervini's Trend Template in MarketSmith" (7 Jan 2019): template-count as market gauge (670 → 127)
- https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-8-keys-superperformance-vcp — video summary (sell-rule snippets)
- https://lilys.ai/notes/it/notebooklm-20251211/perfect-vcp-trading-setup-mark-minervini — video summary (JS-rendered; not readable by fetcher)
- https://lilys.ai/de/notes/notebooklm-20251211/minervini-define-trading-style — IBD Live summary (2025 breakout-failure comments; not readable by fetcher)
- https://www.stockopedia.com/content/minervini-power-play-242073 — Power Play rules (100% in 8 weeks; ≤20/25% over 3–6 weeks)
- https://www.prorealcode.com/topic/power-play-screener-minervini/
- https://www.shortform.com/pdf/think-trade-like-a-champion-pdf-mark-minervini — risk 1.25–2.5%, 20–25% positions, ≤50%, 10–12 stocks, 50-day breakeven trail
- https://shortform.com/pdf/trade-like-a-stock-market-wizard-pdf-mark-minervini — 10% max loss
- https://www.financialwisdomtv.com/post/mark-minervini-trade-think-like-a-champion — FWTV book review (Jun 2020, upd. Dec 2025)
- https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing — Laurentiu Chisca, 2021 USIC trade reconstruction (28 Jan 2022)
- https://traderlion.com/investing-champions/mark-minervinis-risk-management/ — TraderLion on the 2021 win (403 to fetcher)
- https://knowledge.sharescope.co.uk/2022/06/24/the-trader-what-can-we-learn-from-mark-minervini/ — principles only (Michael Taylor, 24 Jun 2022)
- https://tw.tradingview.com/chart/COIN/dRQXnzm3-Minervini-s-Specific-Exit-Criteria — exit tutorial (JS_TechTrading, 26 Nov 2023; generic 7–8% numbers)
- https://kr.tradingview.com/chart/FDMT/rWwozTF7-FDMT-VCP-Pattern — example of footprint notation "VCP: 6W 29/7 3T"
- https://www.screener.in/screens/602587/code-33-mark-minervini — Code 33 screen
- https://www.chartmill.com/stock/markets/usa/screener/minervini-stocks — 2026 template screen (403 to fetcher)
- https://www.stage2stocks.com/learn/trend-template-and-stage-analysis — template vs Weinstein stages (not fetched)
- https://daytrading.com/mark-minervini-momentum-strategies (not fetched)

Evidence / replications
- https://easyswing.trading/performance — walk-forward detector panel (7 Jul 2026): VCP Breakout 1,259 trades, 37% win, PF 0.38; Trend Template Fresh-Pass 18,382 trades, 40%, PF 0.99; Cup & Handle PF 1.57
- https://github.com/sofus-nl/swing-trading-strategies — rules behind the panel
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/01-vcp.md — VCP rules (and the unverified "72% / 48 trades" citation)
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/16-trend-template-fresh-pass.md — fresh-pass rules
- https://www.financialwisdomtv.com/post/can-one-chart-pattern-beat-the-market-i-tested-the-top-100-stocks — top-100 VCP study, Aug 2025–Apr 2026 (survivorship-conditioned)
- https://sharpely.in/blogs/volatility-contraction-pattern-vcp-rule-based-screener-built-high-quality/ — vendor VCP screen portfolio (India, from Feb 2023)
- https://www.nber.org/papers/w20439 — Daniel & Moskowitz, "Momentum Crashes"
- Academic (from knowledge, not fetched): George & Hwang (2004) "The 52-Week High and Momentum Investing", *J. Finance* 59(5); Jegadeesh & Titman (1993) *J. Finance* 48(1); Han, Zhou & Zhu (2016) "A Trend Factor", *J. Financial Economics* 122(2); Brock, Lakonishok & LeBaron (1992) *J. Finance* 47(5); Lo, Mamaysky & Wang (2000) *J. Finance* 55(4); Stan Weinstein (1988) *Secrets for Profiting in Bull and Bear Markets*.
