# 11 — RSI-2 / Connors-style short-term mean reversion (RSI(2), Double 7s, Cumulative RSI, R3, ConnorsRSI, IBS)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Tags: "(primary)" = Connors/Alvarez's own book
excerpt, Connors Research material or Alvarez's own blog; "(secondary)" = third-party summary or replication of the
published rules; "(independent)" = an outside backtest or academic paper; "(unverified)" = could not be checked
against a primary source in this run (budget ~40 web calls). No number below was invented; where only a range
or a recollection exists it is labelled.*

**One line.** In a stock or index ETF that is above its 200-day SMA, buy at (or just before) the close after a
sharp 2–7 day pullback has pushed the 2-period RSI under 5–10 (or the close to a 7-day low, or two-day cumulative
RSI(2) under 35), hold a few days without a price stop, and sell into the first bounce: a close above the 5-day
SMA or RSI(2) back above 65–70. High hit rate (70–80%), small average gain, losers larger than winners, low time
in market.

**Lineage.** Short-term return reversal is one of the oldest documented anomalies (Jegadeesh 1990, Lehmann 1990
— standard references, not re-fetched here). Larry Connors popularised the trader version in *How Markets Really
Work* (2004) and, with Cesar Alvarez, in *Short Term Trading Strategies That Work* (TradingMarkets, 2008), whose
contents page frames it as six rules — buy pullbacks not breakouts; buy after the market has dropped, not risen;
buy above the 200-day, not below; use the VIX ("buy the fear, sell the greed"); stops hurt; hold overnight —
followed by chapters on intraday drops, "The 2-Period RSI — the trader's holy grail of indicators?", the Double
7's strategy, an end-of-month strategy, five market-timing strategies and exits (primary, book excerpt PDF).
Later Connors Research products extended the family: *High Probability ETF Trading* (2009: RSI 25/75, 3-Day
High/Low, R3, %b, Multiple Days Up/Down, RSI 10/6 & 90/94, TPS), ConnorsRSI (≈2012), the ConnorsRSI Pullback
stock system (Active Trader, Mar 2013) and the weekly-RSI-2 stock rotation in *The Alpha Formula* (Connors & Chris
Cain, 2019). IBS (internal bar strength) is a sibling one-bar oversold measure from the same quant-blog culture
(Pagonidis 2013), not a Connors indicator.

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| Original vehicles | US index and index ETFs (SPY, QQQ, plus country ETFs FXI, EWZ for Double 7s); "a universe of many thousands of stocks" for the stock-level studies, 1995–2007 | Book excerpt ch. 10 (primary); CXO Advisory review, Jan 2009 (secondary) |
| Stock filter, ConnorsRSI Pullback | price **> $5**; 21-day average volume **≥ 250,000** shares; **10-day ADX > 30** | Active Trader Mar 2013 rules as coded by Wealth-Lab (secondary of primary) |
| Stock filter, *The Alpha Formula* | the **500 most liquid US stocks**, re-ranked monthly by **200-day average dollar volume** | QuantConnect replication of Connors & Cain 2019 (secondary) |
| Ranking when many signal | *Alpha Formula*: take the **10 lowest 100-day historical volatility** names. ConnorsRSI Pullback: ADX > 30 (trend strength) and deepest oversold first. Classic RSI-2: unspecified | secondary as above |
| Daily scan (classic) | close > SMA(200) AND RSI(2) < 10 (aggressive < 5); Double 7s: close > SMA(200) AND close = lowest close of last 7 bars; Cumulative RSI: RSI(2) today + yesterday < 35 | StockCharts ChartSchool (secondary); book excerpt (primary) for Double 7s; ProRealCode/LuxAlgo (secondary) for Cumulative RSI |

### Market filter
- **Instrument's own 200-day SMA** is the only filter in the classic rules: "buy stocks above their 200-day moving
  average, not below" (book contents, primary). Shorts mirror it (below the 200-day, RSI(2) > 90–95).
- **VIX**: Rule 4 "use the VIX to your advantage … buy the fear" (primary, chapter title). The specific "VIX
  stretch" thresholds (VIX some % above its 10-day MA for N days) are **unverified** in this run.
- *The Alpha Formula* uses a market gate: **SPY 126-day total return > 0** (secondary).
- Independent enhancement: a VIX/volatility-regime filter on the E-mini RSI(2) system raised profit factor
  2.15 → 2.99 and cut max drawdown ~48% (Alpha Algo Trading Research, 4 Mar 2026; in-sample, independent).
- Academic support for a volatility *on*-switch rather than off-switch: reversal returns are "highly predictable
  with the VIX" and spike in turmoil (Nagel, RFS 2012). This is the opposite of most breakout filters.

### Entry
| Variant | Setup (all long; shorts are the mirror) | Execution | Source |
|---|---|---|---|
| **RSI(2) classic** | close > SMA(200); RSI(2) < 10, aggressive < 5 (some summaries 5–10) | "just before the close or on the subsequent open"; Connors prefers before the close | ChartSchool (secondary, quoting Connors) |
| **Double 7s** | SPY > SMA(200); SPY closes at a **7-day low** → buy | at the close | book ch. 10 (primary); "Double 5s … 10s" all "hold up well" (primary) |
| **Cumulative RSI** | close > SMA(200); RSI(2) summed over **2** days < **35** | at the close | ProRealCode / LuxAlgo (secondary; book attribution, chapter 12 per those sources) |
| **R3** | close > SMA(200); RSI(2) down **3 days in a row**, first day already < 60, today < 10 | at the close | WH SelfInvest (secondary of *High Probability ETF Trading*) |
| **ConnorsRSI Pullback (stocks)** | filters above; today's low ≥ **W%** below prior close (W = 2/4/6/8, coded 4); close in **bottom X%** of day's range (X = 10/25, coded 25); **ConnorsRSI(3,2,100) < Y** (Y = 5…15, coded 15) | **next day, limit Z% below today's close** (Z = 4/6/8/10, coded 4) | Wealth-Lab coding of Active Trader 2013 + parameter grid (secondary) |
| **Alpha Formula (weekly)** | SPY 126-d return > 0; top-500 liquidity; **weekly RSI(2) < 20**; pick 10 lowest-vol | end of week, equal weight | QuantConnect thread (secondary) |
| **IBS** | IBS = (C − L)/(H − L); long when IBS < ~0.2 (short > ~0.8) in equity ETFs | at the close | Pandey & Joshi, arXiv 2306.12434 (independent; thresholds via search summary, PDF body not read) |

ConnorsRSI = (RSI(3) of close + RSI(2) of the up/down streak length + PercentRank over 100 bars of the 1-day
return) / 3; Connors' suggested levels 10 oversold / 90 overbought, 5/95 for volatile names (StockCharts
ChartSchool, secondary).

### Stop
- **None, by design.** Connors "does not advocate using stops"; his testing found stops "hurt" performance on
  stocks and stock indices (ChartSchool, secondary; book chapter "Rule 5 — Stops Hurt", primary title). Alvarez
  repeated the finding that mean-reversion systems tested best without stops (Better System Trader ep. 037 and
  IFTA 2016 "Using Stops: The Good, the Bad and the Ugly", secondary listings).
- The *trend* exit is the de-facto stop in some codings: Backtrex also exits if the close crosses back below the
  200-day (independent).
- *The Alpha Formula* adds a **10% below entry** catastrophic stop, checked daily (secondary).
- ChartSchool warns the no-stop approach risks "outsized losses and large drawdowns" (secondary).

### Exits and targets
- Classic: **close above the 5-day SMA** (ChartSchool, secondary; Backtrex coding, independent). Alternatives
  taught: RSI(2) > 65–70, trailing stop or Parabolic SAR (ChartSchool).
- Double 7s: **close at a 7-day high** (primary).
- Cumulative RSI: **RSI(2) > 65** (secondary). R3: **RSI(2) > 70** (secondary).
- ConnorsRSI Pullback: exit at the close when **ConnorsRSI > N** (N = 50/60/70/80; coded 50) (secondary).
- Alpha Formula: **weekly RSI(2) > 80** (secondary).
- No fixed price target in any variant; the target is "mean reached", which is why reward:risk on a
  stop-distance basis is meaningless for this family.
- Book chapter 13 is devoted to exit strategies (primary title; contents not read).

### Position sizing
- The 2008 book reports per-trade averages and % correct, not a sizing model (consistent with the excerpt and
  CXO's note that the analyses focus on average returns, not variability/drawdowns).
- *High Probability ETF Trading*'s TPS ("time, price, scale-in") system scales into a losing position in
  increasing tranches — commonly quoted as 10/20/30/40% — **unverified** this run.
- *The Alpha Formula*: **10 equal-weight positions** (secondary).
- Independent tests use either 100% equity per index trade (Backtrex) or a 4-slot portfolio (Trading Time
  Machine) or 1 futures contract (Alpha Algo).
- Practical implication: with no price stop, risk-per-trade sizing ("1% of equity / stop distance") does not
  apply; size by a fixed equity fraction and cap the number of concurrent positions and their correlation.

### Holding period
- Days. Double 7s on SPY was in the market "less than 25% of the time" over 1993–2007 (primary). Backtrex's SPX
  run made 73 trades in 10 years (≈7/yr), the NDX run 65. Typical holds 2–6 bars (Trading Time Machine examples:
  2- and 4-bar winners). *Alpha Formula* is the weekly-bar outlier (weeks).

---

## Chart signatures
1. **Uptrend intact**: price above a rising 200-day SMA; ideally 50 > 200 (the swing-engine `trend_state` ≥ 0).
2. **Sharp, short pullback**: 2–4 consecutive lower closes (R3 needs three falling RSI(2) readings; Rule 2 "buy
   after it has dropped"), close at a 5–7 day closing low, often down to or through the 10/20-day MA.
3. **RSI(2) pinned in single digits** (< 5–10) while RSI(14) is only ~35–45 — RSI(2) is extreme, the trend
   oscillator is not.
4. **Close near the low of the day** (IBS / `close_pos` < 0.2–0.25; ConnorsRSI Pullback requires bottom 25% of
   range and an intraday low ≥ 4% under the prior close in single stocks).
5. **Fear spike** at the market level: VIX above its short average / market vol regime high (Nagel 2012).
6. **No fresh fundamental shock**: the drop is not an earnings miss / guidance cut gap (a gap-down on news is the
   classic falling knife; see Pitfalls).
7. **Exit picture**: one or two up closes that lift price back over the 5-day SMA, RSI(2) jumping to 65–90.

---

## Who teaches it
| Who | What | Where |
|---|---|---|
| Larry Connors (Connors Research; formerly TradingMarkets) | Originator of the trader version; books 2004–2019; ConnorsRSI | *How Markets Really Work*; *Short Term Trading Strategies That Work* (2008, w/ Alvarez); *High Probability ETF Trading* (2009); *The Alpha Formula* (2019, w/ Chris Cain) |
| Cesar Alvarez | Co-author/researcher at Connors Research; now independent quant blogging on mean reversion | alvarezquanttrading.com (blog, posts through Aug 2026); Better System Trader ep. 037 |
| Chris Cain, CMT (Connors Research) | *Alpha Formula* weekly RSI-2 stock rotation; CMT Association talk Apr 2019 | cmtassociation.org (search result, not read) |
| Arthur Hill (StockCharts) | ChartSchool RSI(2) article; SystemTrader RSI mean-reversion tests on SPY/QQQ/MDY/IJR | chartschool.stockcharts.com; articles.stockcharts.com |
| Backtrex | Independent 10-year out-of-sample index tests (SPX, NDX, DAX, EUR/USD), published 2 Oct 2026 | backtrex.com |
| LuxAlgo, ProRealCode, StrategyQuant, Quantified Strategies, Wealth-Lab, StockSharp | Code libraries / replications ("RSI 2P", Cumulative RSI, Double 7, R3, ConnorsRSI Pullback) | links in Sources |
| Trading Time Machine (Dave Johnson), Alpha Algo Trading Research | 2026 Substack replications on Nasdaq-100 constituents and E-mini S&P | backtest.substack.com; algotr.substack.com |
| u/Rogue-seeker (Reddit) | Named in the methods sweep as a proponent; the thread was **not located** in this run (unverified) | — |

---

## Evidence

### What the originators showed (in-sample)
- Double 7s, SPY 29 Jan 1993 – end 2007: **153 trades, avg +0.85%, 80.4% correct**; QQQQ (Mar 1999 →): 68 trades,
  +0.93%, 79.4%; FXI (Oct 2004 →): 26 trades, +1.41%, 76.9%; EWZ (Jul 2000 →): 63 trades, +1.82%, 81.0% (book
  excerpt ch. 10, primary). These are the authors' own tests on the period in which the rules were developed.
- CXO Advisory's review (26 Jan 2009) of the same book: test window 1995–2007; no correction for data-mining
  bias or out-of-sample test; little analysis of return variability/drawdowns or subperiod decay; no cost
  sensitivity; unclear whether "8 million trades" of overlapping signals were independently exploitable.

### Independent out-of-sample backtests
| Test | Rules | Period | Result |
|---|---|---|---|
| Backtrex, S&P 500 index (published 2 Oct 2026) | long RSI(2) < 5 above SMA200, short RSI(2) > 95 below; exit 5-day SMA or 200-day cross; 100% equity; 0.02%/side | 3 Oct 2016 – 1 Oct 2026 | **+18.1% total, CAGR 1.7%** vs B&H +255.4% / 13.5%; 73 trades; **71.23% win**; PF 1.43; avg win **1.22%** vs avg loss **2.10%**; max DD −21.5% vs −35.0%; years: 2017 +2.5, 2018 −9.8, 2019 −3.0, 2020 −1.3, 2021 +8.6, 2022 +0.9, 2023 −1.1, 2024 +8.6, **2025 +6.4**, **2026 YTD +6.5** |
| Backtrex, Nasdaq-100 index (2 Oct 2026) | same | same | **+26.9%, CAGR 2.4%** vs B&H +528.3% / 20.2%; 65 trades; **75.38% win**; PF 1.55; avg win 1.58% vs avg loss **3.11%**; max DD −25.0%; 2020 −12.2% on 2 trades; **2025 −0.6%**, **2026 YTD +6.9%** |
| Backtrex, DAX | same | same | +14.4% vs +136.7% B&H (from the repo's evidence sweep; page not re-fetched) |
| Trading Time Machine / Dave Johnson (4 Mar 2026) | Nasdaq-100 constituents; close > 200 MA, below 5 MA, RSI(2) < 10; exit close > 5 MA; 4 slots | Dec 2006 – 2025 | CAGR **17.84%**, win 64.33%, PF 1.45, Sharpe 1.10, max DD 29.15%; costs not stated; constituent-history (survivorship) handling not stated |
| Alpha Algo Trading Research (4 Mar 2026) | E-mini S&P (ES), long > SMA200 & RSI(2) < 10, short < SMA200 & RSI(2) > 90, exit 5-bar SMA, 1 contract, no stop | 1997 – 2026 | PF 2.15, avg trade $512, max DD $19,362; with VIX filter PF 2.99, max DD $10,100 |
| *Alpha Formula* replication (QuantConnect forum) | weekly RSI(2) stock rotation as above | 1998 – present | CAGR **12.5%**, max DD **22.8%**, win 63% (avg win 0.64%) |
| Alvarez, "Mean reversion vs trend following through the years" (24 Jan 2024) | S&P 500 index, RSI(2) < 20 / > 80 and RSI(4), 1- and 5-day forward returns | 1957 – 2023 | Mean reversion has out-performed since ~1983 on 5-day holds; "little change from the mid-2000s"; edges "harder to find and smaller"; his long and short MR strategies did well in 2023 |
| Arthur Hill, StockCharts (29 Oct 2018) | RSI(5) cross-up variant on SPY/QQQ/MDY/IJR, 5-SMA > 200-SMA filter | 2002 – Oct 2018 | CAGR 8.76%, max DD −9.33%, 71% win, 43% exposure; adding a regime exit cut CAGR to 7.29% and DD to −8.27% |

**Reading the index results correctly.** Backtrex compares a strategy that is invested a small fraction of the
time (≈7 trades a year of a few days each) with 100%-invested buy-and-hold, so the CAGR gap mostly measures
exposure, not edge. The per-trade expectancy is the cleaner statistic: SPX 0.7123 × 1.22% − 0.2877 × 2.10% ≈
**+0.27% per trade**; NDX 0.7538 × 1.58% − 0.2462 × 3.11% ≈ **+0.43% per trade** (computed here from the published
figures). That is positive after 0.02%/side costs but thin, negatively skewed (average loss 1.7–2× average win),
and the 10-year sample is only 65–73 trades — too few to separate skill from noise with confidence. On single
stocks the per-trade gross is larger (higher volatility), which is why stock-portfolio versions (17.8% CAGR,
12.5% CAGR) look better — but those are also where survivorship, costs and earnings gaps bite hardest.

### Academic evidence (mechanism, not the exact rule)
- **Short-term reversal is liquidity provision.** Nagel ("Evaporating Liquidity", RFS 25(7):2005–2039, 2012):
  reversal-strategy returns proxy the return to supplying liquidity, are "highly predictable with the VIX", and
  their expected return and conditional Sharpe spike in turmoil. Implication: RSI-2 should be most profitable
  when volatility is high — exactly when the 200-day filter often switches longs off.
- **Turnover splits reversal from continuation.** Medhat & Schmeling ("Short-term Momentum", RFS Mar 2022; US
  1963–2018 + 23 developed markets): at the one-month horizon, low-turnover stocks reverse while high-turnover
  stocks show short-term *momentum*, strongest in the largest, most liquid, most covered names. Implication: a
  pullback on very heavy volume (news) is less likely to mean-revert. (Horizon is monthly; RSI-2 is days.)
- **Standalone reversal is hard to monetise.** Novy-Marx, Rizova, Dai & Medhat (2023, via the repo's evidence
  sweep): reversals are stronger in volatile stocks but a standalone reversal strategy is impractical because of
  turnover/costs; best used as an entry-timing overlay and adjusted for earnings and industry moves.
- **IBS.** Pandey & Joshi (arXiv 2306.12434, Jun 2023, NYU Stern authors): over ~10 years IBS is a useful
  predictor of next-day moves in a basket of country ETFs, building on Pagonidis (2013) (abstract-level only).
- **Data-snooping caution.** No peer-reviewed paper testing Connors' exact RSI(2)/200-day rule with
  White-Reality-Check-style corrections was found. The repo's evidence ranking puts RSI-2 at rank 8 ("Medium:
  independent 10-yr OOS tests"; high win rate, tiny compounding).

---

## Pitfalls
1. **In-sample origin.** The rules were fitted on 1995–2007 data (CXO). Threshold menus (RSI < 2/5/10, Double
   5s…10s, W/X/Y/Z grids) are an open invitation to overfit; pick one set a priori and walk forward.
2. **Negative skew without stops.** Average loss ≈ 1.7–2× average win in OOS tests; a single trend-break
   (NDX 2020: −12.2% on two trades) erases a year. "Stops hurt" is a statement about average return, not about
   tail risk or position-level ruin; ChartSchool explicitly warns of outsized losses.
3. **Entry timing.** The edge is measured buying *at the close* of the oversold day (Connors' Rule 6: it pays to
   hold overnight; the first bounce is often the next open). Buying the next open, as swing-engine's backtester
   does, gives part of the reversal away; the ConnorsRSI limit-below-close entry is the honest next-day
   alternative.
4. **Filter whipsaw / filter-off at the best moment.** The 200-day gate switches longs off in corrections, which
   is when reversal returns are highest (Nagel). The Backtrex index tests include the mirrored short side
   (RSI(2) > 95 below the 200-day) and do not split long vs short P&L, so whether shorts helped or hurt in
   2016–2026 is unverified; shorting against US equities' upward drift deserves its own test.
5. **News gaps in single stocks.** An RSI(2) of 2 after an earnings miss or guidance cut is information, not
   noise (Medhat-Schmeling; Novy-Marx et al. advise earnings adjustment). Exclude earnings-window signals and
   gap-downs on news, or treat them separately.
6. **Survivorship and constituent bias.** Index-member backtests that use *today's* Nasdaq-100/S&P 500 list
   overstate results (stocks that fell out after failed rebounds disappear). Use point-in-time membership —
   swing-engine already keeps delisted symbols.
7. **Indicator implementation drift.** RSI(2) depends on Wilder smoothing seed/warm-up; tiny differences move a
   reading across 5 or 10. Cumulative RSI, ConnorsRSI and RSI(2) are not interchangeable.
8. **Wrong benchmark, wrong conclusion.** Comparing a ~10–25%-exposure system to 100%-invested buy-and-hold
   (Backtrex) understates it; comparing equity-curve CAGR of a 4-slot stock portfolio with no cost/survivorship
   detail (Trading Time Machine) can overstate it. Judge on per-trade expectancy, exposure-adjusted return and
   correlation to the rest of the book.

---

## 2025–2026 fit
- **Still positive, still thin.** Backtrex (published 2 Oct 2026): SPX version +6.4% in 2025 and +6.5% in 2026
  YTD; NDX version −0.6% in 2025 and +6.9% in 2026 YTD. Over the decade it has had multi-year flat/losing
  stretches (SPX 2018–2020, 2023).
- **Mean reversion has not decayed further since the mid-2000s** (Alvarez, Jan 2024), but edges are smaller.
  Alvarez's 2026 posts stress running a mean-reversion strategy *alongside* momentum and a market-timing system
  because of their low correlation (combined 24% annual return / 23% drawdown in his example, Aug 2026), and warn
  against re-tuning a strategy after one bad month (May 2026).
- **Regime read for late 2026.** Alvarez's May 2026 "100% Club: 2000 Tech vs 2026 AI" frames the market as a
  concentrated, momentum-led AI run. In such tapes, pullbacks in leaders above their 200-day have tended to be
  bought quickly (favourable for long RSI-2), while short-side RSI-2 fights the trend. When a high-volatility
  shakeout breaks the 200-day (spring 2025 tariff selloff — index fell below its 200-day; dates **not re-verified**
  here), the classic long rule sits out the sharpest rebounds; a VIX/vol-regime overlay (Alpha Algo 2026; Nagel)
  or a "deep oversold even below the 200-day with a small size and hard stop" sub-rule is the usual fix, and must
  be tested, not assumed.
- **Role in swing-engine:** a diversifier, not a core return engine. It trades when the breakout strategies
  (05-qullamaggie, breakout_52w, momentum_burst) are idle (pullbacks), holds days not weeks, and its losses come
  from trend breaks rather than failed breakouts.

---

## Automatability

**Mechanical (100% codable from end-of-day bars):** 200-day filter, RSI(2), n-day closing low/high, cumulative
RSI, ConnorsRSI, IBS, intraday-drop %, ADX, historical-volatility ranking, exit on close vs MA / RSI threshold,
time stop, position count caps. Nothing in the classic method is discretionary.

**Discretionary residue:** (a) choosing thresholds/variant before testing (do it once, log it in the trial log);
(b) news triage — whether a drop is a liquidity event or a fundamental re-rating (the agent layer can classify
the catalyst, but per CLAUDE.md the LLM returns only an enum such as `NEWS_DRIVEN` / `NO_NEWS`, never a price);
(c) whether to override the 200-day gate in panics.

### Mapping to swing-engine (as of this run)
| Method element | swing-engine today | Gap / action |
|---|---|---|
| Strategy | `swing_engine/strategies/rsi2_meanrev.py` (`close > sma_200 and rsi_2 < 10`; exit `close > sma_10` or `rsi_2 > 70` or 5-day time stop; 2×ATR(14) protective stop); enabled in `config/settings.yaml` with `min_reward_risk: 0.0` | Mostly faithful to the classic rule, with the deviations below |
| RSI(2) | `rsi_2` (Wilder) in `features/indicators.py` | OK |
| 200-day filter | `sma_200` | OK |
| **Exit MA** | **`sma_10`** (only 10/20/50/200 SMAs exist) | Connors uses the **5-day SMA**. Add 5 to `SMA_WINDOWS` and default `exit_ma: sma_5`; keep `sma_10` as a tested alternative. A 10-day exit holds losers longer and changes the win-rate/skew profile |
| **Entry timing** | backtester fills at the **next open** (`research/backtest.py`, step 1) | Book edge is at the close. Either (i) evaluate the signal ~15:50 ET on live/near-close data and fill MOC, or (ii) adopt the ConnorsRSI rule-7 style **limit Z% below the signal close** for the next day (fits the existing next-day fill model; `entry_limit` already exists in the backtester) |
| Target | `target = sma_10` as a resting limit (fills intraday in the backtester) | Taught exit is a *close* above the MA; a resting limit is a different (earlier, intraday) exit. Prefer `target=None` and rely on `should_exit` at the close, or test both |
| Stop | 2×ATR(14) below entry + 5-day time stop | Not taught (Connors: no stop). Keep a *catastrophic* stop for paper/live safety but test 2×ATR vs 10% (Alpha Formula) vs none; time stop is not in the classic rule either (Alvarez: time stops change psychology more than results) |
| Market gate | `P_MIN_MARKET_TREND = TREND_DOWN` → effectively off; instrument's own 200-day used | Faithful to classic. Variants to test: `market_trend_state >= 0`; SPY 126-day return > 0 (`ret_126d` on SPY); vol-regime *on*-switch (`market_vol_regime == 2`) per Nagel |
| IBS | `close_pos` in `features/cross_section.py` = (C−L)/(H−L) | Available now: add `close_pos < 0.25` as an optional confirm (ConnorsRSI rule 5) |
| Intraday drop | `low`, `prev_close` | Derivable: `low / prev_close - 1 <= -W%` |
| Liquidity filters | `universe` config (price ≥ $5, ADV ≥ 500k shares, ≥ $5M) ; `avg_vol_20d`, `dollar_vol_20d` | Stricter than Connors' $5 / 250k — fine |
| Ranking | `score = rsi_entry - rsi_2` | Alternatives to test: lowest `vol_63d` (≈ Alpha Formula's 100-day HV), ADX > 30 (needs ADX feature), deepest `rev_5d` |
| Double 7s | — | Needs rolling 7-bar min/max of close (one `rolling_min`/`rolling_max` call; reuse `features/cross_section.py` helpers) |
| Cumulative RSI / R3 | — | Derivable from `rsi_2` with a 2-bar sum / 3-bar monotone check |
| ConnorsRSI | — | Needs streak length, RSI(2) of streak, 100-bar percent rank of `ret_1d` |
| ADX(10) | — | Missing feature |
| VIX filter | — | No VIX series; `market_vol_regime` (SPY realised vol percentile) is a proxy |
| Earnings exclusion | events data exists in research sweeps; EDGAR ingest | Add an "earnings within ±1 day" exclusion when a calendar feed is wired |
| Sizing | `risk.risk_per_trade_pct` 1% ÷ stop distance; `max_position_pct` 10%; 8 positions | With a wide/no stop, risk-per-stop sizing is degenerate; for this strategy size by fixed equity fraction (e.g. 10% cap already acts as this) and cap concurrent RSI-2 positions and sector overlap |
| Holding / time stop | `max_hold_days: 5` (read by the backtester via `STRATEGY_HOLD_PARAM`) | Reasonable bound; report results with and without it |

**Suggested experiments (walk-forward, costs on, point-in-time universe):** (1) `exit_ma` sma_5 vs sma_10;
(2) next-open vs limit-below-close entry; (3) stop: none / 10% / 2×ATR; (4) entry RSI(2) < 5 vs < 10 fixed a
priori, plus Cumulative RSI < 35 and Double 7s as separate registered strategies rather than parameter sweeps;
(5) `close_pos` < 0.25 confirm; (6) market gate off / trend ≥ 0 / high-vol on-switch; (7) earnings exclusion.
Report per-trade expectancy, exposure, skew, and correlation of daily P&L with the breakout strategies, and log
every variant in the trial log so the deflated Sharpe accounts for the search.

---

## Sources
Primary (originators)
- Connors & Alvarez, *Short Term Trading Strategies That Work* (2008) — contents + ch. 10 "Double 7's Strategy"
  excerpt PDF (publisher promo, hosted on an MQL5 forum): https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf
- Cesar Alvarez, "Mean Reversion vs Trend Following Through the Years" (24 Jan 2024):
  https://alvarezquanttrading.com/blog/mean-reversion-vs-trend-following-through-the-years/
- Alvarez blog index: https://alvarezquanttrading.com/blog/
- Alvarez, "The Power of Strategy Diversification" (19 Aug 2026):
  https://alvarezquanttrading.com/blog/the-power-of-strategy-diversification/
- Alvarez, "Bad Month for Your Strategy? Should You Change It?" (6 May 2026):
  https://alvarezquanttrading.com/blog/bad-month-for-your-strategy-should-you-change-it/
- Alvarez, "The 100% Club. 2000 Tech vs 2026 AI" (12 May 2026; title only):
  https://alvarezquanttrading.com/blog/the-100-club-2000-tech-vs-2026-ai/
- Alvarez on stops, Better System Trader ep. 037 (listing):
  https://bettersystemtrader.libsyn.com/037-quant-trader-cesar-alvarez-discusses-stop-losses-including-intraday-vs-eod-stops-volatility-vs-percentage-stops-trailing-stops-vs-targets-which-is-best
- Alvarez, IFTA 2016 "Using Stops: The Good, the Bad and the Ugly" (listing): https://ifta.org/2016/using-stops-the-good-the-bad-and-the-ugly

Secondary (rules as reproduced)
- StockCharts ChartSchool, RSI(2): https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- StockCharts ChartSchool, ConnorsRSI: https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/connorsrsi
- Wealth-Lab, ConnorsRSI Pullback (Active Trader 2013-03): https://wl6.wealth-lab.com/Strategy/Details/254 ;
  forum: https://www.wealth-lab.com/Forum/Posts/ConnorsRSI-Pullback-System-32894
- WH SelfInvest, R3 strategy: https://www.whselfinvest.de/en-de/trading-platform/free-trading-strategies/tradingsystem/81-r3-larry-connors
- QuantConnect, *The Alpha Formula* mean reversion replication: https://www.quantconnect.com/forum/discussion/18219/quot-the-alpha-formula-quot-mean-reversion-strategy-by-cabedovestment/
- LuxAlgo RSI-2 concept: https://www.luxalgo.com/library/concept/rsi-2/
- ProRealCode Cumulative RSI: https://www.prorealcode.com/prorealtime-trading-strategies/cumulative-rsi-2-periods-strategy
- ProRealCode RSI 2P (Connors): https://prorealcode.com/prorealtime-trading-strategies/rsi-2p-larry-connors/?pnum=13
- StrategyQuant, Double 7 on SPY and 8 markets (search result, not read): https://strategyquant.com/blog/larry-connors-double-7-strategy-tested-on-spy-and-8-other-markets/
- Quantified Strategies R3 (search result, not read): https://quantifiedstrategies.substack.com/p/larry-connors-r3-strategy-it-still-795
- Quantified Strategies IBS (search result, not read): https://quantifiedstrategies.substack.com/p/the-internal-bar-strength-ibs-indicator
- x-trader.net Connors tag (from sweep; not read): https://www.x-trader.net/tag/larry-connors
- CMT Association (Connors & Cain talk, search result, not read): https://cmtassociation.org/?p=76021

Independent tests / reviews
- Backtrex RSI(2) S&P 500 (2 Oct 2026): https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- Backtrex RSI(2) Nasdaq-100 (2 Oct 2026): https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100
- Backtrex RSI(2) DAX: https://backtrex.com/en/backtests/connors-rsi-2-dax
- Backtrex RSI(2) EUR/USD (from sweep; not read): https://backtrex.com/en/backtests/connors-rsi-2-eur-usd
- CXO Advisory review of the book (26 Jan 2009): https://www.cxoadvisory.com/technical-trading/a-few-notes-on-short-term-trading-strategies-that-work/
- Trading Time Machine (Dave Johnson), "The 2-Period RSI: A Simple System That Still Earns Its Keep" (4 Mar 2026): https://backtest.substack.com/p/the-2-period-rsi-a-simple-system
- Alpha Algo Trading Research, RSI(2) on E-mini S&P with VIX filter (4 Mar 2026): https://algotr.substack.com/p/this-simple-mean-reversion-strategy
- Arthur Hill, SystemTrader RSI mean-reversion update (29 Oct 2018): https://articles.stockcharts.com/article/articles-arthurhill-2018-10-systemtrader---update-to-rsi-mean-reversion-strategy-and-dealing-with-the-dreaded-drawdown/

Academic
- Nagel, "Evaporating Liquidity", RFS 25(7) 2012: https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html ; NBER w17653: https://ideas.repec.org/p/nbr/nberwo/17653.html
- Medhat & Schmeling, "Short-term Momentum", RFS 2022: https://openaccess.city.ac.uk/id/eprint/31278/ ; CEPR DP15857: https://repec.cepr.org/repec/cpr/ceprdp/DP15857.pdf ; Alpha Architect summary: https://alphaarchitect.com/short-term-momentum/
- Pandey & Joshi, "Using Internal Bar Strength as a Key Indicator for Trading Country ETFs" (arXiv 2306.12434, 2023): https://arxiv.org/abs/2306.12434
- Novy-Marx, Rizova, Dai & Medhat (2023) reversal/liquidity provision — via repo sweep `docs/research-raw/methods-sweeps/evidence.json` (not re-fetched)

Repo
- Sweep entry: `docs/research-raw/methods-sweeps/merged_compact.json`, `evidence.json`
- Strategy: `swing_engine/strategies/rsi2_meanrev.py`; features: `swing_engine/features/indicators.py`,
  `cross_section.py`, `regime.py`; backtester: `swing_engine/research/backtest.py`; config: `config/settings.yaml`
