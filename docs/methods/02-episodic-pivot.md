# 02 — Episodic Pivot (catalyst gap-up in a neglected stock)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Every number is tagged with where it came from:
"(primary)" = the proponent's own blog/site, "(secondary)" = third-party notes of a talk, a transcript, or a
replication, "(unverified)" = could not be checked against a primary source in this run, "(from knowledge)" =
standard literature cited without re-fetching it this run.*

**One line.** A stock that has been ignored for months gets a real surprise (usually earnings/sales acceleration or
guidance, sometimes FDA, contract, policy or a hot theme), gaps up 10%+ on several times normal volume, and the
market spends weeks or months repricing it. Buy the day-1 opening-range high (or a day-2+ "delayed" entry), stop at
the low of the day, take partial profits in the first days, trail the rest with the 10/20-day MA.

**Lineage.** Pradeep Bonde (Stockbee) named and blogged the setup from **Feb 2007** ("Episodic Pivots and Idea
Pickle", "Episodic Pivot Catalysts") and tied it explicitly to post-earnings-announcement drift (PEAD, Ball & Brown
1968) in **Feb 2010** ("What are Episodic Pivots and how to trade them"). Kristjan Kullamägi (Qullamaggie) made it one
of his "3 timeless setups" (Jan 2021) and wrote a dedicated post (Nov 2021). Close cousins: O'Neil-school
**Buyable Gap-Up** (Gil Morales & Chris Kacher) and Trader Stewie's **Power Earnings Gap (PEG)**.

---

## Rules

There are two primary rule sets that agree on the core (catalyst + gap + volume + neglect) and differ on
management. They are listed side by side; pick one and version it.

### Universe and scan

**Kullamägi (qullamaggie.com, primary)**

| Rule | Value as taught | Source |
|---|---|---|
| Gap | "Gap up 10%+" / "gap up of 10% or more" | 3 Timeless Setups (8 Jan 2021); EP post (2 Nov 2021) |
| Volume | "Big volume. If the volume is not there in premarket, it needs to come in at the open"; often trades the average daily volume in the first **15–30 minutes** (2021 setups post) / "ideally the stock should trade the average daily volume the first **15–20 minutes**" (EP post) | primary |
| Earnings quality (earnings EPs) | "big growth numbers, preferably mid/high or even triple digit EPS and revenue growth and a significant beat to analyst expectations" | 3 Timeless Setups |
| Neglect | "It's best if the stock has not rallied over the past **3–6 months**"; ideal stocks have been "sideways for 3–6 months or more" | 3 Timeless Setups; EP post |
| Prior EPs | Avoid stocks with a recent prior EP (higher failure rate, smaller moves) | EP post (paraphrase of fetch) |
| Catalysts | earnings/guidance, government regulation, biotech/FDA, macro/political, contracts/partnerships, a red-hot sector | both posts |
| When | Concentrated in earnings season: "3–4 weeks every quarter" | EP post |

**Bonde (stockbee.blogspot.com, primary; talks via notes, secondary)**

| Rule | Value as taught | Source |
|---|---|---|
| Original 2007 scans (TC2000 syntax; `V` is in hundreds of shares, which matches his prose) | (1) `%chg >= 20 AND V > 10000 AND C >= 5` = "20% in a single day on at least 1 million shares"; (2) `%chg >= 30 AND V > 3000 AND C >= 5` = 30% on 300,000 shares; (3) `(C − C1) >= 5 AND V > 10000 AND C >= 5` = "$5 in a single day" on 1M shares; (4) `%chg >= 10 AND V > 1000 AND C >= 5`; (5) `C > C1 AND V > 5 * AVGV50.1 AND V > 3000 AND C > 5` (volume spike without a big price move) | "Episodic Pivots and Idea Pickle", 26 Feb 2007 (primary) |
| 2010 scan | `((C − C1) >= 5 AND V > 10000 AND C >= 62.50 AND V > V1) OR ((100*(C − C1)/C1 >= 8 AND V > 3000 AND 100*V/AVGV100 >= 300) AND C > 1)` — i.e. a **$5+ move on 1M+ shares** for $62.50+ stocks, or **+8% on 300k+ shares at ≥3× the 100-day average volume** | "What are Episodic Pivots…", 12 Feb 2010 (primary, verbatim) |
| Volume on true earnings breakouts | "10 times or more compared to average volume" | 2010 post (primary) |
| Float | Below 25M ideal, best moves below 10M; 100M+ float tends to pull back; little enthusiasm above 500M | 2010 post (primary, paraphrase) |
| Catalysts (high probability) | "Earnings acceleration", "Sales Acceleration", "New Contracts or new orders", "New Product Launch or news", "Sector Runaway move", "Biotech/drug approvals", "Biotech/drug tie ups with large companies", "Earnings guidance raised by company", "Inside buying>1 million", IBD rating / IBD 100 addition. Low probability: Barron's/BusinessWeek mention, Cramer mention ("one day phenomenon") | "Episodic Pivot Catalysts", 11 Jul 2007 (primary) |
| 2010 catalyst list | earnings growth 100%+, earnings 40%+, beats, sales 100%+, IPO breakout, buyout/merger, product launch, drug approval, analyst up/downgrade, dividend, regulatory change | 2010 post (primary) |
| **MAGNA53 + CAP 10x10** (2024 framework) | **MA** massive acceleration in earnings/sales (double/triple-digit, beats) — required; **G** gap up; **N** neglected "for 2 months, 6 months, 1–3 years" (price neglect or analyst neglect); **A** acceleration in sales growth (prioritised over earnings); **5** short interest ≥ 5 days to cover; **3** ≥ 3 analysts raising targets; **CAP 10** market cap limit (notes read "Market Cap Below $10M" — almost certainly a transcription slip, value **unverified**); **10** IPO within the last 10 years. MA required; 53/CAP10x10 optional conviction boosters | TraderLion Conference 2024 via Retail Trader's Repository notes (19 Sep 2024, secondary) |
| Growth EP | "Sales growth above 39% on consecutive earnings releases will have a high probability of making a move higher" | same (secondary) |
| Turnaround EP | neglected stock with a surprise swing in sales/earnings; "often make bigger and longer moves than Growth EPs" | same (secondary) |
| Story EP | theme-driven (e.g. AI in Jan 2024), no fundamental metrics | same (secondary) |
| **9 Million EP (EP9M)** | previously neglected, low-volume stock that trades **≥ 9 million shares**; in the 2024 talk framed as the top ~2% of daily volume (~200–250 names of ~13,000 instruments). He expects "100–300 trades in a year" from this variant | RTR notes (secondary); talk transcript on sozai.app (secondary, machine transcript) |
| Delayed-reaction EP | enter on day 2+ after the catalyst (pullback/consolidation) when day 1 is too extended to risk-manage | RTR notes (secondary); listed as a module in the Nov 2026 bootcamp post (primary, 17 Sep 2026) |
| Scan timing | "Night Time is Right Time, Morning Time is Right Time" (scan after hours and pre-market); news from Briefing.com, The Fly | RTR notes (secondary) |

**Community simplifications (secondary, not Bonde's own words).** TradingView "Episodic Pivot" screen
("inspired by stockbee", yogy.frestarahmawan, 3 Oct 2021): `close/close[1] > 1.04`, `volume > 3 × SMA50(volume)`,
`volume >= 300,000`. tradermonty/claude-trading-skills (MIT, 2025–26) day-1 checklist: gap or same-day move ≥ 4%,
volume ≥ 3× average or ≥ 9M shares, close in upper part of range, risk to EP-day low sizeable, prior neglect/base.
Tradingsim (J. McDowell, Nov 2021, upd. Mar 2026): gap "8–10% or more", volume "2x, 3x, 4x or more" arriving
pre-market or in the first 30 minutes. Morales/Kacher **Buyable Gap-Up** as coded by StockCharts/TradingView users:
gap ≥ **0.75 × 40-day ATR** (ATR excluding the gap bar), volume ≥ **150% of 50-day average** (book-derived, secondary;
the Virtue of Selfish Investing FAQ itself says "there are no hard and fast rules that govern when to buy gap ups").

### Market filter
- **Kullamägi:** no explicit index rule for EPs; the setup clusters in earnings season. His general practice (see
  method 05) is to cut new longs in corrections. Financial Wisdom TV suggests **QQQ 10-EMA > 20-EMA** as a gate
  (secondary, not attributed to him verbatim).
- **Bonde:** quality and count depend on regime: "Average of 10–12 Classic EPs a year" with ~**70%** wins in a good
  market vs "3–4 Classic EPs a year" in a choppy one (RTR notes, secondary). Regime is read from his breadth
  "Market Monitor" (counts of 4% up/down movers, 25% in a quarter, etc.) and the "20% study" (Sep 2026 bootcamp
  outline, primary; the breadth construction is in method 06).

### Entry
- **Kullamägi (primary):** "Enter opening range highs. ORH can be the highs of the first 1-, 5-, or 60-minute
  candle." Wait for the first 1-minute candle to complete; add on 5-minute or 60-minute highs as confirmation; "no
  need to be first in" — entries later in the day are fine if the stock is acting well; size is built through the
  day as confirmation arrives.
- **Bonde:** "Enter at the Open" or wait "a few minutes to see how the market reacts to the news before entry as
  there are shakeouts" (RTR notes, secondary). 2024 talk: buy on the first day, "as early as possible", within the
  first 30–60 minutes (machine transcript, secondary). 2007: "enter the 1-2 with clear catalyst and where the move is
  just starting… some next day" (primary). Delayed-reaction EP for day 2+ entries.
- **Buyable Gap-Up (Morales/Kacher):** buy near the open or on a pullback toward the gap-day intraday low, allowing "a
  good 3-4% on the downside" (Tradingsim summary, secondary).

### Stop
- **Kullamägi (primary):** "The stop is at the lows of the day." Risk "1x, or maximum 1.5x the average daily range
  or average true range" (EP post). If the LOD is further than that, size down or skip.
- **Bonde:** 2010 (primary): "The stop is the low of last 2 days before entry." 2024 (secondary): "Normally with a
  2.5% stop loss"; will accept a "10% stop" when expecting a triple-digit move; exits fast if price hesitates
  after entry. Talk transcript: "never move stops down, always move them up".
- **Buyable Gap-Up:** a close below the gap-day intraday low (secondary).

### Exits and targets
- **Kullamägi (primary):** "Trail your stop with the 10- or 20-day moving average once they surpass your initial
  stop." His generic management (3 Timeless Setups, applied to EPs by secondary summaries such as Stockbsessed and
  What Works in Trading): sell **1/3–1/2 after 3–5 days**, move stop to break-even, trail the rest to the first
  **close** below the 10- or 20-day MA.
- **Bonde 2010 (primary):** "The exits are in 4 parts with profit target of 20% plus." EPs "start their rally on
  earnings day and continue it for months or 3-4 quarters". **2007 (primary):** holding periods "few weeks to
  months… Exits are based on trailing stops". **2024 (secondary):** set an approximate target from experience and
  catalyst strength — if a 60–70% move is expected, do not exit at 30%; talk transcript: scale out in ~20% pieces,
  keep a 20% core.
- **Morales "violation rule"** (secondary): exit on a second close below the MA that also undercuts the low of the
  first violating candle.

### Position sizing
- **Kullamägi (primary):** risk usually **0.25–1%** of equity per trade; never more than **30%** of the account
  overnight in one stock (3 Timeless Setups). His FAQ (method 05) gives 0.3–0.5% typical risk, positions 5–25%.
- **Bonde (secondary, talk transcript):** "singles" 20–25% of the account; an overnight anticipation position about
  10%; very large size only in liquid EP9M names. Tight (2.5%) stops are what make 20–25% positions survivable.

### Holding period
- Kullamägi: day 3–5 partial, remainder trailed; meant to catch "multi-month, and multi-year moves" (primary).
- Bonde: two horizons — EP9M/momentum trades "3 to 5 days" as the unit and "3 days to at best 20 days" (2024
  transcript, secondary); classic earnings EPs held weeks to 2–3 months (2007/2010 posts, primary).

---

## Chart signatures
1. **Neglect base.** 2–6+ months (Bonde: up to 1–3 years) of sideways or declining price, flat or falling MAs, low
   and falling volume, no prior EP; total rise over the prior 3–6 months small (What Works in Trading codes "< 30%
   prior appreciation, dormant 3+ months", secondary).
2. **The gap.** Day-1 open ≥ 10% above prior close (Bonde's scans go as low as 4–8% with heavy volume), ideally
   clearing every MA and the recent range high in one bar — a "pivot" from neglect to repricing.
3. **Volume shock.** ≥ 3× average (scans), 10×+ on the best earnings EPs (Bonde 2010), or the whole ADV in the first
   15–30 minutes (Kullamägi); highest volume in a year or ever. EP9M: ≥ 9M shares in a stock that usually trades a
   fraction of that.
4. **Day-1 close.** Holds the opening range and closes in the upper part of the day's range; the gap is not filled.
   A close near the low / below the open ("gap-and-crap") is the failure tell.
5. **Follow-through.** 3–5 days of continuation (Bonde's momentum-burst rhythm), then a tight flag above the EP-day
   low — which becomes a Qullamaggie flag breakout (method 05). The classic EP → flag → breakout sequence is the
   "delayed" second entry (e.g. the EBS June-24 TradingView study).
6. **Multi-quarter drift.** For true growth/turnaround EPs, the next 1–3 earnings reports produce further gaps
   (Bonde: "continue it for months or 3-4 quarters"); weekly chart turns from base to stage-2 advance.
7. **Anti-signatures.** Already-extended stocks (rallied hard in the prior 3–6 months), second or third EPs,
   gaps on offerings/dilution, gaps on no identifiable news, M&A gaps (upside capped by deal price), day-1 ranges of
   20–40% that put the LOD far beyond 1.5 ADR.

---

## Who teaches it
- **Pradeep Bonde (Stockbee)** — originator of the term. stockbee.blogspot.com (posts from Feb 2007; Feb 2010 PEAD
  post), stockbee.biz membership, TraderLion conference/podcast appearances (2024: MAGNA53 + CAP 10x10 framework),
  in-person bootcamps (Nov 2026 Las Vegas outline lists EP, EP9M "Catalyst-based, Story-based, High
  Liquidity-based", delayed-reaction and bearish EPs). YouTube @Stockbeevideos and X @PradeepBonde per the sweep (not
  re-verified this run).
- **Kristjan Kullamägi (Qullamaggie)** — qullamaggie.com "My 3 timeless setups" (8 Jan 2021) and "How to master a
  setup: Episodic Pivots" (2 Nov 2021); stream archive; X @qullamaggie. Mastery claim: "3–4 earnings seasons to get
  good…".
- **Gil Morales & Chris Kacher** — Buyable Gap-Up (*Trade Like an O'Neil Disciple*, 2010; Virtue of Selfish
  Investing FAQ, 2010/2012).
- **Trader Stewie** — Power Earnings Gap; blog post "What is power earnings gap and how to…" (Feb 2019; not fetched).
- **Educators/summarisers:** Financial Wisdom TV (EP explainer with QQQ EMA gate; PL and HYMC case studies),
  Tradingsim (J. McDowell, 2021, updated Mar 2026), A Retail Trader's Repository (F4VS) Substack (talk notes),
  Stockbsessed Substack, TraderLion ("Episodic Pivots: 5 simple steps" course page; 403 at fetch time).
- **Testers:** Ney Torres H, *What Works in Trading* Substack (gap-day study Feb 2024; EP coding series 2026);
  Pedma, *Trading Research Hub* article #44 (Aug 2024, paywalled).
- **Open-source code:** TradingView "Episodic Pivot" screen (Oct 2021) and "Episodic Pivot Aparna"; GitHub
  tradermonty/claude-trading-skills `stockbee-episodic-pivot-analyzer` (MIT; ranks/classifies, does not decide).

---

## Evidence

### Self-reported (unaudited)
- Bonde (2024 talk notes): ~70% win rate on classic EPs in good markets; 10–12 classic EPs a year (3–4 in chop);
  100–300 EP9M trades a year. No P&L series published.
- Kullamägi: no EP-specific statistics; illustrative winners NVDA (2016–17, doubled in ~6 months after an earnings
  gap), FSLR (2007), BB (2004); 2021 post shows AFRM, UPST, ASAN including stop-outs. Account-level results in
  method 05.

### Independent / mechanical tests (secondary)
| Study | What was tested | Result |
|---|---|---|
| Ney Torres H, "Kristjan Qullamaggie and Stockbee on Episodic Pivots" (What Works in Trading, 28 Sep 2026) | Coded "every rule": earnings gap with triple-digit growth/sales emphasis; dormant 3+ months with < 30% prior rise; gap clears all MAs and range highs; full-day volume in first 5–15 min; ORH entry; LOD stop ≤ 1 ADR; 1/3–1/2 out at day 3–5; 10/20-day trail; biotech excluded | Numbers paywalled. Author states every mechanical EP version in his four prior posts "lost to a plain S&P 500 index fund" — this post retests after reader objections. **Treat as: no public evidence of a mechanical edge.** |
| Ney Torres H, "Deep dive on gap trading" (20 Feb 2024) | All US gap-ups 2019-01-01 → 2024-02-09 (not filtered for catalyst/neglect) | Median gap 7.14%, mean 12.8%; **~65.9% closed red** vs the open; median intraday high +1.96% at 09:46, median low −6.61% at 11:00. Base rate: the average gapper fades. |
| Pedma, Trading Research Hub #44 (23 Aug 2024) | Gap ≥ 10%, heavy early volume, earnings, ORH entry, LOD stop, 10/20-day trail | Results paywalled (unverified). |
| swing-engine's own small-cap research (docs/smallcap-spec.md) | Low-float catalyst gappers | 67% of 50%+ gappers close below the open; 73% gap down next day — the small-cap tail of the EP universe fades by default. |

No public, audited, cost-inclusive EP backtest with win rate/PF was found in this run.

### Academic backdrop
- **PEAD.** Ball & Brown (1968); Bernard & Thomas (1989) (from knowledge). Bonde's 2010 post names PEAD as the
  mechanism.
- **PEAD has decayed.** Martineau, "Rest in Peace Post-Earnings Announcement Drift", *Critical Finance Review*
  (2022): conditioning on analyst surprises, "For large stocks, PEAD have been non-existent since 2006 but has only
  disappeared recently for microcap stocks." Subrahmanyam (SSRN 5930255, Dec 2025; UCLA Anderson Review, 21 Jan
  2026): drift t-stat 2.18 with all stocks, **1.43 excluding microcaps** (microcaps ≈ 3% of market value).
  Counter-claims: Hirshleifer, Peng & Wang, *RFS* 38(3) 2025 (t ≈ 14 for drift) and Dickerson, Julliard & Mueller
  (*JFE*, in press) find drift still priced — the dispute is mostly about microcap inclusion.
- **Price reaction, not just the EPS number.** Brandt, Kishore, Santa-Clara & Venkatachalam (2008, "Earnings
  announcements are full of surprises"): portfolios sorted on the earnings-announcement *return* (the academic
  analogue of the gap) drift, ~12.5% a year combined with SUE (secondary snippet; unverified number).
- **News vs no news.** Chan (2003, *JFE* 70(2)): drift after headline news (strongest after bad news), **reversal
  after extreme moves with no news**, concentrated in small illiquid stocks — the academic case for "no catalyst, no
  trade".
- **Neglect.** Hong, Lim & Stein (2000, *J. Finance*): momentum is stronger in small, low-analyst-coverage stocks
  (from knowledge). Jegadeesh & Livnat (2006, *JAE*): revenue surprises add to drift (from knowledge) — consistent
  with Bonde's "sales over earnings". DellaVigna & Pollet (2009): inattention slows earnings incorporation (cited in
  Martineau).

### Reading the evidence
The EP premise (surprise + neglect → slow repricing) has real academic roots, but the free lunch has shrunk to
small/illiquid names where gaps, spreads and dilution eat it. What practitioners monetise is **selection** (real,
large, sales-led surprises in stocks nobody owned), **execution** (ORH entry, LOD stop capped at 1–1.5 ADR) and
**asymmetric management** (cut day-1 failures fast, trail the rare multi-month repricing). The one public attempt to
code all of it (Torres, 2026) has so far underperformed SPY; treat any edge as unproven until the engine's own
walk-forward with costs says otherwise.

---

## Pitfalls
1. **Most gappers fade.** ~66% of 2019–24 US gap-ups closed below the open; without a real catalyst and early
   volume, an EP scan is a gap-fade universe.
2. **Day-1 stop distance.** Modern earnings gaps often run 20–40% with huge ranges; LOD can be 2–3 ADR away. Rule:
   skip or go to a delayed-reaction entry when LOD > 1.5 ADR (Kullamägi's cap).
3. **Catalyst misclassification.** Offerings, reverse splits, PR fluff, analyst mentions and "story" pumps produce
   gaps that do not drift (Bonde rates media mentions low; Chan 2003: no-news moves reverse). An offering is not a
   catalyst (repo smallcap-spec).
4. **Already-extended or repeat EPs.** Stocks that ran in the prior 3–6 months, and second/third EPs, fail more.
5. **Survivorship in examples.** NVDA 2016, PL Sep 2025 (+100%), HYMC (+180% in 21 sessions) are hand-picked;
   no public base rates accompany them.
6. **Earnings-season clustering.** Setups bunch in 3–4 week windows, often in one theme → correlated positions and
   portfolio-level gap risk; cap sector/theme exposure.
7. **Microcap dependence.** Academic drift survives mainly in microcaps; low floats bring halts, LULD pauses,
   dilution and slippage that a daily backtest will not see.
8. **Look-ahead in backtests.** Day-1 "close in upper range", day-1 volume and the LOD are not known at the open;
   point-in-time fundamentals (EPS/sales growth, analyst revisions, float) must be as-of the announcement.
9. **Rule drift across sources.** Stop (LOD vs low of last 2 days vs 2.5%), exits (MA trail vs 4-part 20%+ target)
   and holding period (3–20 days vs months) differ between Bonde and Kullamägi; version one combination.
10. **Intraday dependence.** ORH entries need 1/5/60-minute data and live execution at 09:31–10:30 ET; a daily-bar
    version is a different (later, wider-stop) trade.

---

## 2025–2026 fit
- **Still taught, now with more variants.** Bonde's 17 Sep 2026 bootcamp post lists EP, EP9M (catalyst-, story- and
  liquidity-based) and delayed-reaction EPs; the emphasis has moved toward high-liquidity and delayed entries.
- **Day-1 gaps are bigger.** 2025–26 community guides (search snippets; unattributed, secondary) say day-one moves
  have become more aggressive (20–40% gaps, very wide ranges), making the delayed-reaction EP the practical entry
  more often.
- **Recent examples (secondary, survivorship-selected).** Financial Wisdom TV: Planet Labs (PL) gapped ~20% on
  earnings in Sep 2025 and gained "over 100%" after the ORH break; HYMC +180% in 21 sessions on discovery news
  (date not given). Themes driving story EPs in 2025–26: AI infrastructure, semis, space, nuclear/power, crypto.
- **Evidence trend.** Academic PEAD debate (Jan 2026) says drift is weak outside microcaps; the most explicit public
  mechanical test (Torres, 2025–26 series) lost to SPY. Kullamägi has published no new EP material since 2021 that
  was found in this run (unverifiable).
- **Verdict.** Viable as a **catalyst-filtered, discretionary-ranked** setup in earnings season with a market gate
  on; weak as a blind scan. For swing-engine, the realistic version is a day-2 / delayed-EP daily strategy plus a
  day-1 intraday alert path, both judged only after cost-inclusive walk-forward.

---

## Automatability

### Mechanical (daily panel; most columns exist)
| Element | swing-engine mapping |
|---|---|
| Gap | `gap_pct` (open/prev_close − 1) `>= 0.10` (Kullamägi) or `>= 0.08` with heavier volume (Bonde 2010) |
| Volume shock | `rvol_day` (volume/avg_vol_20d) `>= 3` (scan) / `>= 10` (best earnings EPs); add `rvol_100d` (volume/avg_vol_100d) for Bonde's 2010 formula; absolute `volume >= 9e6` for EP9M; cross-sectional `vol_rank_xs >= 0.98` (new, `features/cross_section.py`) for "top 2% of volume" |
| Day-1 quality | `close_pos >= 0.5` (upper half), `close > open` (gap not faded), `range_pct` |
| Neglect | **prior-row** `ret_63d`/`ret_126d` `<= 0.30` (use `prior_columns`, not the gap bar), `dist_52w_high` before the gap, `base_len`; new `bars_since_gap10` / `prior_ep_count_252d` in `features/patterns.py` to reject repeat EPs |
| Clears resistance | `level_break` / `close > resistance_1` (`features/levels.py`), `close > sma_50 and close > sma_200` |
| Stop | EP-day `low` (carry as `ep_low` via `RollingSpec`), skip if `(entry − ep_low) > 1.5 * adr_pct_20 * close` — **add `adr_pct_20`** (shared need with method 05) |
| Exits | `should_exit`: first close `< sma_10` or `< sma_20` after `bars_held >= 3`, plus a time stop (`max_hold_days`) for the EP9M/3–20-day variant; `min_reward_risk: 0.0` (no fixed target) |
| Market gate | `market_trend_state` / `market_vol_regime` (`features/regime.py`, `P_MIN_MARKET_TREND`); optional QQQ EMA10 > EMA20; breadth regime from method 06 |
| Earnings tag | `data/alphavantage.py` EARNINGS_CALENDAR (`report_date`) → new `days_since_earnings` ≤ 1; historical, point-in-time dates need a second source for backtests |
| Float / size | `data/float_data.py` (EDGAR float) for Bonde's < 25M / < 10M preference and CAP limits; `dollar_vol_20d`, `universe.min_price` |
| Sizing | `risk/sizing.py` with `risk.risk_per_trade_pct` (0.25–1%), `max_position_pct`; add a sector/theme cap for earnings-season clustering |

**Fill convention matters.** `research/backtest.py` fills signals emitted at the close of t−1 at the next open. A
daily EP strategy therefore enters at the **day-2 open** — structurally Bonde's delayed-reaction EP / Kullamägi's
"no need to be first in", not the day-1 ORH. Proposed module (via `.claude/skills/add-strategy`):
`strategies/episodic_pivot.py`, params `gap_min=0.10`, `rvol_min=3.0`, `close_pos_min=0.5`, `neglect_lookback=126`,
`neglect_max_ret=0.30`, `max_stop_adr=1.5`, `trail_ma=10|20`, `exit_after_bars=3`, `max_hold_days=60`,
`require_earnings=true`, `min_market_trend_state=0`; variant B "delayed EP": first close above the EP-day high after a
3–10-bar flag that holds above `ep_low`. Register `enabled: false` until the walk-forward + trial log clear
`docs/gates.md` (with 20 bps/side slippage outside large caps). Closest existing code: `strategies/momentum_burst.py`
(Stockbee 4% burst, 3–5-day exit) and `strategies/breakout_52w.py`.

**Day-1 intraday path (monitor).** `monitor/rules/rvol_gate_triggers.py` already emits `premarket_gap` (gap ≥
`monitor.gap_pct_alert` 8.0, `rvol_gate` 2.0; P2 when `news_tagged`) and `peg_survivor` (TRIGGER_PEG) alerts;
`features/rvol.py` `rvol_now` can test "ADV traded by 09:45–10:00". ORH entry needs 1/5/60-minute bars and an order
layer at 09:31–10:30 ET. Note the small-cap track (`monitor/smallcap.py`, docs/smallcap-spec.md) is a warn/fade
posture with long alerts only until 09:45 — EPs under $20 / < 20M float fall into that track and its stricter
rules, not this method's.

### Discretionary (keep as Claude-review enums or human steps)
- **Catalyst quality**: is it a real, large, sales-led surprise or guidance raise vs PR/story/offering? Map to
  enums in `monitor/classify.py` (Haiku structured output) fed by Alpaca/Benzinga news and `eightk_items.py`
  (8-K Items 2.02/7.01/8.01 vs 1.01, 3.02 dilution).
- **Magnitude of growth** (triple-digit EPS/sales, consecutive > 39% sales growth) needs point-in-time
  fundamentals the engine does not ingest yet.
- **Neglect beyond price**: analyst coverage, short interest days-to-cover ≥ 5, analyst target raises ≥ 3 (MAGNA
  "5" and "3") — data not in the engine.
- Expected-move-based targets (Bonde), intraday add/size-up as confirmation arrives (Kullamägi), and the
  day-1 vs delayed-entry choice when the gap is huge.

---

## Sources
Primary — Bonde (Stockbee)
- https://stockbee.blogspot.com/2007/02/episodic-pivots-and-idea-pickle.html — 26 Feb 2007, five original scans, entry/holding guidance
- https://stockbee.blogspot.com/2007/02/up-stocks-and-down-stocks_15.html — 15 Feb 2007, "100% plus moves… have such episodic pivots at the beginning"
- https://stockbee.blogspot.com/2007/06/episodic-pivot-shorts.html — 26 Jun 2007, bearish EPs
- https://stockbee.blogspot.com/2007/07/episodic-pivot-catalysts.html — 11 Jul 2007, catalyst list
- https://stockbee.blogspot.com/2007/07/episodic-pivot-bullish-4-plus-breakout.html — Jul 2007, EP + 4% breakout lists
- https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html — 12 Feb 2010, PEAD link, scan formula, float, stop, 4-part exits
- https://stockbee.blogspot.com/2026/09/november-2026-bootcamp-las-vegas.html — 17 Sep 2026, current curriculum (EP, EP9M, delayed EP)
- https://stockbee.blogspot.com/ — blog index; https://stockbee.blogspot.com/search?q=episodic+pivot — post search
Primary — Kullamägi (Qullamaggie)
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/ — 8 Jan 2021, EP rules, sizing
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/ — 2 Nov 2021, EP mastery post (gap, volume, ORH, LOD, 1–1.5 ADR)
Primary — Morales/Kacher
- https://www.virtueofselfishinvesting.com/faqs/answer/how-do-you-determine-if-a-stock-gapping-up-is-buyable-if-it-is-buyable-how-do-you-time-your-entry — BGU FAQ (2010, upd. 2012)
Secondary notes / transcripts / summaries
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots — 19 Sep 2024, TraderLion 2024 talk notes (MAGNA53, CAP 10x10, EP types, 70% win rate, 2.5% stop)
- https://sozai.app/transcript/100-million-dollar-catalyst-trade-setup/ — machine transcript of a Bonde TraderLion talk (EP9M, sizing, 3–20 day holds)
- https://traderlion.com/podcast/discover-episodic-pivots/ — TraderLion podcast (403 at fetch time)
- https://traderlion.com/podcast/pradeep-bonde-episodic-pivots/ — TraderLion podcast, "5 swing trading strategies using EPs" (403)
- https://traderlion.com/profile/pradeep-bonde/episodic-pivots/ — course page (403)
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/ — EP vs PEG vs BGU (Nov 2021, upd. Mar 2026)
- http://theimpatienttrader.blogspot.com/2019/02/what-is-power-earnings-gap-and-how-to.html — Trader Stewie PEG (not fetched)
- https://www.financialwisdomtv.com/post/the-episodic-pivot-strategy-qullamaggie-s-high-momentum-setup-explained — QQQ EMA gate, PL/HYMC examples
- https://stockbsessed.substack.com/p/episodic-pivot-1 — EP summary (catalyst types, 1/3–1/2 partials)
- https://br.tradingview.com/chart/EBS/gr5vb5Ds-EBS-June-24-Qullamaggie-Breakout-and-Episodic-Pivot — EP→breakout study idea (from sweep)
- https://scan.stockcharts.com/discussion/comment/2735 — BGU scan (0.75×40-day ATR, 150% of 50-day volume)
- https://www.tradingview.com/script/PZghP0Uq-Episodic-Pivot/ — Stockbee-inspired screen (4%, 3×50-day volume, 300k)
- https://cn.tradingview.com/script/wvGrk7vs-Episodic-Pivot-Aparna — community EP script (not fetched)
- https://github.com/tradermonty/claude-trading-skills/blob/main/skills/stockbee-episodic-pivot-analyzer/references/ep_methodology.md — MIT EP analyzer (families, day-1 checklist, states)
- https://www.tradezella.com/strategies/episode-pivot-strategy — community guide (search result only)
- https://www.finermarketpoints.com/post/episodic-pivot-trading-complete-guide — community guide (search result only)
Tests / evidence
- https://whatworksintrading.substack.com/p/kristjan-qullamaggie-and-stockbee — Ney Torres H, 28 Sep 2026 (paywalled results; "lost to a plain S&P 500 index fund")
- https://whatworksintrading.substack.com/p/deep-dive-on-gap-trading-how-did — gap-day statistics 2019–2024
- https://www.tradingresearchub.com/p/research-article-44-kristjan-kullamagis — Pedma, 23 Aug 2024 (paywalled)
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf — Martineau, "Rest in Peace PEAD", CFR 2022
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/ — UCLA Anderson Review, 21 Jan 2026
- https://papers.ssrn.com/sol3/Delivery.cfm?abstractid=5930255 — Subrahmanyam (2025)
- https://academic.oup.com/rfs/article-abstract/38/3/883/7698199 — Hirshleifer, Peng & Wang, RFS 2025
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4589786 — Dickerson, Julliard & Mueller, "The co-pricing factor zoo"
- https://ideas.repec.org/a/now/jnlcfr/104.00000122.html — Martineau CFR listing (from sweep)
- https://academicnewsletter.sufe.edu.cn/info/357702 — Chan (2003), JFE 70(2) 223–260 summary
- https://quantpedia.com/strategy-tags/earnings-announcement/ — earnings-announcement strategy index (Brandt et al. 2008 cited via search)
- Hong, Lim & Stein (2000) *J. Finance* 55(1); Jegadeesh & Livnat (2006) *JAE* 41; Bernard & Thomas (1989) *JAR*; Ball & Brown (1968) *JAR* — from knowledge, not fetched
Repo context
- `docs/research-raw/methods-sweeps/merged_compact.json` (this method; also "Power Earnings Gap / BGU / PEAD")
- `docs/smallcap-spec.md`, `docs/feature-contract.md`, `docs/methods/05-qullamaggie-breakout.md`, `docs/methods/06-breadth-regime-filters.md`
