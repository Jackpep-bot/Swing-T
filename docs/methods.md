# Swing methods work-up (synthesis)

*Written 2026-10-06 for swing-engine. This is the synthesis layer over the 14 deep dives in
[`docs/methods/`](methods/) and the six research sweeps in `docs/research-raw/methods-sweeps/` (books/blogs,
events, academic evidence, FinTwit, Reddit, YouTube; 53 merged methods in `merged_compact.json` /
`merged_methods.json`). It is written for someone who is starting swing trading and automating parts of it with
this engine. Nothing here is investment advice; it is a map of what is taught, what is tested, and what the
engine can code.*

**Tags used below.** "(primary)" = the teacher's own book, site, stream or interview. "(secondary)" = third-party
notes, summaries or replications. "(unverified)" = seen only in a search snippet or a secondary summary that could
not be checked this run. "(conflict)" = sources disagree; both readings are shown. Every number is carried from a
deep dive or a sweep file with its source; nothing was added from memory except where marked. The web-search
budget for this session was exhausted before synthesis, so only two facts were re-checked live today (Q3 2026
index returns and the 6 Oct 2026 SPY close, both marked "verified 2026-10-06").

**Evidence grades.**
| Grade | Meaning |
|---|---|
| A | Peer-reviewed, replicated out of sample over decades, survives realistic costs |
| B | Peer-reviewed support for the mechanism, or independent out-of-sample tests showing a modest positive edge |
| C | Vendor or independent mechanical replications that are gross of costs, small-sample or mixed |
| D | Self-reported or anecdotal only, or the only independent tests show no edge |
| Neg | High-quality evidence of no edge after costs or data-snooping corrections |

---

## 0. The short version (read this first)

1. **Gate first, then select, then trigger.** Every credible school puts a market-regime gate in front of the
   setup (IBD's M rule, Stockbee's Market Monitor, QQQ vs its 20 EMA, SPY vs its 200-day, breadth participation).
   The best-evidenced pieces for a retail swing trader are not setups at all: **relative-strength / 52-week-high
   momentum ranking** (grade A) and **trend / breadth / volatility regime filters** (grade B, mainly as drawdown
   control). Build those into the engine before adding entries.
2. **Start with one long-only, end-of-day setup that the engine already codes**: the pullback to a rising 20/50-day
   MA in a leader (`pullback_trend`), plus the RSI-2 index-ETF mean-reversion diversifier (`rsi2_meanrev`). Both are
   mostly or fully mechanical, have the least-bad public evidence, and fit the October 2026 tape better than
   breakouts.
3. **Breakout families (base breakouts, VCP, Qullamaggie flags, momentum bursts, episodic pivots) are
   feast-or-famine.** Their public mechanical tests range from profit factor 0.38 to 1.57 before costs. Their edge,
   where it exists, lives in selection, exits and exposure control, and appears in short windows after corrections
   (Apr 2025, Jul-Oct 2025, Apr 2026). Paper-trade them behind the gate; do not expect them to work in a narrow tape.
4. **Risk rules are the consensus that matters**: 0.25-1% of equity at risk per trade, a structural stop (day low,
   pivot, dip low) never wider than about one ADR/ATR, a notional cap because tight stops create big positions,
   partial profits after 3-5 days, and a moving-average trail on the rest.
5. **October 2026 regime**: the S&P 500 is at or near a record while only about 27% of US stocks are above their
   50-day and about 40% above their 200-day, small caps fell 7.5% in Q3, the Fed is hiking, and the 10-year is near
   5.3%. That rewards leaders-only pullbacks, index mean reversion and reduced size; it punishes broad breakout
   buying and small-cap momentum. See section 3.
6. **Nothing here has passed `docs/gates.md` in this engine.** Every strategy stays in paper until 3+ months and
   100+ closed trades with modelled costs, and a deflated-Sharpe pass with the full trial count logged.

---

## 1. Ranked method table

**How the rank was built.** Three inputs, then judgement for a beginner who is automating:
(1) **evidence quality** (grades above, from the deep dives' Evidence sections and the evidence sweep's ranked
table); (2) **practitioner consensus** ("mentions" = how many of the 6 sweeps carried the method, and the sweep
popularity label, from `merged_methods.json`); (3) **automatability** on daily bars in this engine (fully
mechanical / mostly mechanical / discretionary). Methods that are filters rather than entries rank high because
they improve every entry.

### 1a. Main table (the 14 deep-dived methods plus the two foundation layers)

| # | Method | Evidence | Consensus | Automation | Beginner | swing-engine today | Fit, Oct 2026 | Deep dive |
|---|---|---|---|---|---|---|---|---|
| 1 | **Regime gates**: breadth (% above 50/200-day, Zweig thrust, Stockbee 4% ratio), price trend filter (SPY > 200-day), IBD M rule, volatility scaling | B (trend filter and vol scaling peer-reviewed for drawdown control; breadth thrusts consistent but small-sample; no lead at 21 days or less per CXO) | 3/6 sweeps, very common; used by every school | Fully mechanical | Start here | `market_trend_state` gate exists; breadth and FTD/DD missing | Most useful piece now: says reduce size, leaders only | [06](methods/06-breadth-regime-filters.md), [07](methods/07-canslim-ibd-market-school.md) |
| 2 | **Relative strength / 52-week-high momentum ranking** (as a universe filter; Minervini Trend Template as the screen) | A (Jegadeesh-Titman; George-Hwang; 17/18 international markets) | Embedded in every leader method | Fully mechanical | Start here | `ret_*`, `mom_12_1`, `dist_52w_high` exist; cross-sectional percentile rank missing | Works, but momentum stalled in Q4 2025 (+0.77% vs value +8.34%) | [03](methods/03-vcp-minervini-trend-template.md), sweep |
| 3 | **Pullback to rising 20/50 MA in an uptrend** (Holy Grail, Landry, EMA zone) | B- (short-term reversal inside momentum; EasySwing panel 1,092 trades, PF 1.45, +0.3R, gross) | 5/6 sweeps, very common (top) | Mostly mechanical | Start here | `pullback_trend` enabled | Best fit of the long setups if RS-filtered and gated | [01](methods/01-pullback-20-50-ma-uptrend.md) |
| 4 | **RSI-2 / Connors mean reversion** | B- (independent 10-yr OOS: +0.27%/trade SPX, +0.43% NDX; thin, negative skew) | 3/6, common | Fully mechanical | Start here (index ETFs, small size, as a diversifier) | `rsi2_meanrev` enabled (exits differ from Connors) | 2026 YTD +6.5% SPX / +6.9% NDX (Backtrex) | [11](methods/11-rsi2-connors-mean-reversion.md) |
| 5 | **Classic base breakouts** (cup-with-handle, flat base, flags) | C (patterns carry information, no net-of-cost rule shown; EasySwing cup and handle 3,582 trades, PF 1.57 gross; Bulkowski failure rates doubled 1990s to 2003-07) | 4/6, very common | Mostly mechanical | After basics | `breakout_52w`, `sr_breakout` approximate it | Few valid setups; run only with the gate on | [04](methods/04-chart-pattern-base-breakouts.md) |
| 6 | **CAN SLIM / IBD with Market School** | C (M rule behaved well in 2025-26; selection lagged in real money: FFTY 10-yr 4.94%/yr vs SPY 15.53%) | 3/6, very common | Mostly mechanical (fundamentals need data) | After basics (use the M rule now) | Not coded; FTD/DD state machine proposed | Keep M as a gate, reduced exposure | [07](methods/07-canslim-ibd-market-school.md) |
| 7 | **Minervini VCP / SEPA** | Template as a filter B; VCP trigger D (EasySwing VCP 1,259 trades, PF 0.38, figures internally inconsistent; fresh template pass 18,382 trades, PF 0.99) | 4/6, very common | Mostly mechanical (VCP detection is hard) | Template: start here. VCP: advanced | `breakout_52w` with `vcp_contraction` is a crude proxy | Clean VCPs only after corrections | [03](methods/03-vcp-minervini-trend-template.md) |
| 8 | **Kell Cycle of Price Action** | D (no independent test; one contest year, +941.1% in 2020 on margin) | 3/6, common | Mostly mechanical in parts | After basics, as an overlay (QQQ vs 20 EMA, not-extended rule) | Not coded; pieces map to `pullback_trend`, `breakout_52w` | Suits V-turns; whipsaws in chop | [12](methods/12-kell-cycle-of-price-action.md) |
| 9 | **Anchored VWAP / multi-timeframe (Shannon)** | C-/D (no test of the method; the headline session-VWAP study failed independent replication) | 3/6, very common | Mostly mechanical on daily bars (anchor choice discretionary) | After basics, as an entry filter | Not coded; `features/avwap.py` proposed | Self-throttles in chop | [08](methods/08-anchored-vwap-multi-timeframe-shannon.md) |
| 10 | **Power Earnings Gap / Buyable Gap-Up** | C (historical price-reaction drift 6.3-15.3%/yr in 1971-2009 samples; Bulkowski BGU test 28-32% winners, +1.2-3.1%/trade; large-cap PEAD gone since about 2006) | 2/6, very common | Mostly mechanical (needs point-in-time earnings dates) | Advanced | Not coded; monitor has gap/RVOL alerts | Large-cap reactions muted (+0.4% Q2 2026); consolidation entries fit better | [13](methods/13-power-earnings-gap.md) |
| 11 | **Qullamaggie breakout** (momentum flag / HTF) | C- (EasySwing 16,943 trades, 27% wins, PF 1.10 gross; Stonks Capital CAGR 19%, costs undisclosed; Sharpe -3.59 in 2007-10) | 3/6, very common | Mostly mechanical (ORH entry is intraday) | Advanced | Not coded; `qullamaggie_flag` proposed | Feast-or-famine; famine since Mar 2026 (anecdotal) | [05](methods/05-qullamaggie-breakout.md) |
| 12 | **Episodic Pivot** | D (only explicit public mechanical test lost to SPY; about 66% of 2019-24 gap-ups closed below the open) | 4/6, very common | Discretionary (catalyst quality) | Advanced | Not coded; day-2 version proposed | Viable only catalyst-filtered in earnings season | [02](methods/02-episodic-pivot.md) |
| 13 | **Stockbee momentum burst** | D (raw 4% trigger: 46.8% 5-day win, +0.88% gross; filtered rules untested) | 3/6, common | Mostly mechanical (best entry is intraday) | Advanced (200-1,000 trades/yr, cost-heavy) | `momentum_burst` disabled (has a filter bug, section 7) | Poor: Bonde himself said stand aside until a thrust (Jul 2026) | [09](methods/09-stockbee-momentum-burst.md) |
| 14 | **Stine Insider Buy Superstocks** | D (one self-reported 28-month account; low-priced lottery stocks underperform on average) | 3/6, niche | Mostly mechanical with fundamentals, float and Form 4 data | Avoid as a system; borrow the sell rules | `insider_cluster` disabled; weekly features missing | Small-cap value H1 2026 fit; universe is dirty | [14](methods/14-insider-buy-superstocks-stine.md) |
| 15 | **Parabolic short / long reversal** | C- (academic base rates favour fades; one replication with undisclosed borrow/costs) | 3/6, common | Discretionary (intraday triggers, borrow) | Avoid (engine is long-only; squeeze risk) | Monitor scores first-red-day / VWAP-lost | Supply exists; execution is the problem | [10](methods/10-parabolic-short-and-long-reversal.md) |
| 16 | **Avoid bucket**: standalone MA crossovers, ICT/SMC liquidity swings, congressional-trade copying, ORB day trading, large-cap PEAD | Neg (data-snooping corrections; post-STOCK Act studies; ORB net about 0 after costs) | Very common online | Mostly mechanical | Avoid | n/a | n/a | section 5 |

### 1b. The other 37 methods in the sweep (one line each)

| Method (sweep name) | Verdict for this engine | Evidence | Key sources |
|---|---|---|---|
| Sector / theme rotation via ETF relative strength | Use as a ranking input (group RS), not a stand-alone system | C | https://www.bloomberg.com/news/articles/2026-07-06/morgan-stanley-s-wilson-sees-rotation-from-chips-to-hyperscalers ; https://www.reddit.com/r/swingtrading/comments/1v1oveh/ |
| Volatility-regime gating / vol-managed exposure | Add as an exposure scaler next to breadth (Barroso & Santa-Clara: vol scaling "virtually eliminates crashes") | B | https://www.nber.org/papers/w20439 ; https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html ; https://macroption.com/vix-all-time-high |
| Opening-range / intraday breakout (ORB, stocks in play) | Not swing; independent replication found net about 0 | Neg/C | https://www.mql5.com/en/blogs/post/776235 ; https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/ |
| Pure price-action structure swings (HH/HL, The Strat) | Vocabulary only; no tests | D | https://www.reddit.com/r/swingtrading/comments/1qxrw1n/ |
| Automated / AI-assisted swing systems | Use ML only as meta-labelling on an existing edge; regime "permission layer" | C | https://www.reddit.com/r/algotrading/comments/1w7zz3g/ |
| TraderLion leader trading (Moglen RS line; Petralia) | Same as 2 + 5 + 8 combined | D | https://tradingengineered.substack.com/p/lessons-from-a-veteran-swing-trader |
| Macro-print / FOMC positioning under a hiking Fed | Flatten high-beta longs into NFP/CPI/FOMC; feed `market_wide_suppression` | C | https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm ; https://fedratecalc.com/fomc-meeting-schedule/ |
| 0DTE-aware intraday structure | Context for intraday exits only | C | https://spotgamma.com/record-0dte-volume-reshapes-the-sp-500/ |
| 52-week-high proximity momentum | Fold into row 2 (`dist_52w_high` exists) | A | https://cxoadvisory.com/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks |
| Cross-sectional momentum 12-1 | Fold into row 2; monthly, low turnover is where it survives costs | A | https://alphaarchitect.com/momentum-factor-investing-30-years-of-out-of-sample-data/ ; https://www.nber.org/papers/w20721 |
| Discretionary retail trading base rates | The denominator: 93-97% of persistent day traders lose | Neg | https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html |
| MA crossovers as standalone signals | Avoid as entries; use long MAs only as filters | Neg | https://researchonline.lse.ac.uk/id/eprint/119144 |
| Post-PDT intraday-margin trading | Structural change (FINRA RN 26-10, effective 2026-06-04); not a method | n/a | https://www.finra.org/rules-guidance/notices/26-10 |
| Relative strength vs SPY "market first" (r/RealDayTrading) | Good habit: RS means stock vs SPY at the same moment, not RSI | D | https://www.reddit.com/r/RealDayTrading/comments/vczdo1/ |
| Trend filter / time-series momentum (10-month SMA) | Fold into row 1; reduces drawdown, lags in choppy rising markets | B | https://papers.ssrn.com/abstract=2677212 ; https://www.cxoadvisory.com/technical-trading/market-timing-with-moving-averages-over-the-very-long-run |
| ICT-style liquidity / FVG swings | Avoid; no tests, vocabulary marketing | D | https://www.reddit.com/r/Trading/comments/1w6samx/ |
| Extended-hours / 23x5 and tokenized venues | Re-validate all gap statistics after 2026-12-06 | n/a | https://www.wilmerhale.com/en/insights/client-alerts/20260929-23x5-trading-comes-to-us-exchanges-what-firms-should-know-before-launch |
| Growth / story discretionary swing (Caruso) | Discretionary | D | https://tradingengineered.substack.com/p/how-to-trade-stocks-with-matt-caruso |
| Congressional-trade following | Avoid | Neg | https://www.nber.org/papers/w35041 |
| High tight flag (O'Neil, Soreide) | Sub-case of rows 5 and 11 | C | https://sozai.app/transcript/powerful-swing-trading-setup-high-tight-flag/ |
| Insider cluster buying (Form 4) | Keep `insider_cluster` as a ranking feature; most return prints on disclosure day | B/C | https://papers.ssrn.com/abstract=1692517 ; https://arxiv.org/abs/2602.06198 |
| Policy-shock V-recovery buying | Buy the policy-reversal follow-through, not the first dip | C (2 cases) | https://www.betashares.com.au/insights/liberation-day-upended-markets/ |
| Weinstein Stage Analysis | Candidate weekly strategy (shares features with row 14) | D | https://traderlion.com/trading-strategies/stage-analysis/ ; https://www.mql5.com/en/articles/22746 |
| Breitstein playbook swing | Discretionary | D | https://theonelanceb.com/ |
| Core position plus options overlay | Out of scope (options) | D | https://www.reddit.com/r/Trading/comments/1n0hl6z/ |
| Crypto-proxy equities (DATs) | Avoid long; negative-carry beta | C | https://bitcointreasuries.net/news/the-mnav-trap-why-70percent-discounts-arent-bargains |
| Gamma-aware meme squeezes | Avoid (monitor warn/fade track only) | D | https://finance.yahoo.com/news/opendoor-kohls-resume-rally-meme-160314410.html |
| IPO after-market trading | First-base breakouts only; day-1 pops faded in 2025 | C | https://wolfstreet.com/2025/12/29/ipo-bloodletting-after-the-pop-in-2025-venture-global-coreweave-figma-klarna-bullish-circle-internet-naven-firefly-fermi/ |
| Position sizing / R-multiples / SQN (Van Tharp) | Adopt the vocabulary: report every trade in R | n/a | https://www.vantharpinstitute.com/ |
| Relative-volume-first selection | Already in the engine (`rvol_day`, `rvol_now`) | C | https://www.reddit.com/r/swingtrading/comments/1t4lh5n/ |
| Seasonality (turn of month) | Overlay at most (about 0.55% per 4-day window) | B- small | https://harbourfrontquant.substack.com/p/do-calendar-anomalies-still-work |
| Bear Bull Traders beginner framework | Reading list | D | https://www.blinkist.com/en/books/how-to-swing-trade-en |
| Trader Stewie discretionary swing | Source of the PEG label (row 10) | D | https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/ |
| Turtle Soup failed-breakout reversal | Codeable; regime-dependent, poor in persistent trends | D | https://www.luxalgo.com/library/concept/turtle-soup/ |
| DeMark TD Sequential | Codeable; untested here | D | https://nexusfi.com/a/indicators/td-sequential-demark-indicators |
| Grimes pullback / Anti / failure test | His own research says MA touches are random; the pullback edge is trend plus trigger | C | https://topstep.com/blog/going-deep-on-adam-grimes-approach |
| Weekend Trend Trader (Radge) | Weekly trend system; re-tests show long flat periods | C | https://usethinkscript.com/threads/weekend-trend-trader-by-nick-radge-strategy-for-thinkorswim.669/ |
| Master Swing Trader 7 Bells (Farley) | Book vocabulary only | D | https://www.goodreads.com/book/show/5017866 |
| Top-1 market-cap rotation | Curiosity; survivorship and tax issues | D | https://www.reddit.com/r/Daytrading/comments/1u7r3oy/ |

---

## 2. Consolidated recognition checklist

Read top to bottom. A trade needs a pass at every level; the higher levels veto the lower ones. "Engine" lines say
what exists or is needed in swing-engine.

### 2a. Market regime (veto layer)
- [ ] **Index trend.** SPY above its 200-day (Burns, https://moneyshow.com/articles/dailyguru-26029); engine
  `market_trend_state` = SPY close > SMA50 > SMA200 with SMA50 rising. Practitioner variants: QQQ 10-EMA above
  20-EMA (https://www.financialwisdomtv.com/post/the-episodic-pivot-strategy-qullamaggie-s-high-momentum-setup-explained);
  QQQ above a rising 20/50 EMA, VIX under 15, IWM confirming (Reddit momentum template); Kell's correction mode when
  QQQ is below its 20 EMA (doc 12).
- [ ] **IBD M rule.** Follow-through day on day 4-10 of a rally attempt (best 4-7), index up about 1.2-1.7%+ on
  higher volume; distribution day = index -0.2% or worse on higher volume; 5-6 in about 25 sessions = "under
  pressure" (https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker ;
  https://seekingalpha.com/instablog/195752-joshua-hayes/73173-a-quick-reminder-about-follow-through-days). About a
  quarter of FTDs whipsaw within 15 days (unverified, doc 07).
- [ ] **Breadth participation.** Hill: % of S&P 1500 above the 200-day turns bullish above 60% and stays bullish until
  below 40%; Keller: % above the 50-day below 50% is a red flag; Stockbee: 10-day ratio of 4%-up to 4%-down stocks at
  2 or more is bullish, 0.5 or less bearish; Zweig thrust: 10-day EMA of A/(A+D) from below 0.40 to above 0.615
  within 10 sessions (doc 06; https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts). Thrust
  signatures fired Apr 24 2025 (sentimentrader.com, Apr 25 2025). Engine: `features/breadth.py` missing.
- [ ] **Divergence warning.** Index at highs while few stocks are above the 200-day: Minervini says this has
  "never" escaped at least a correction in his 40 years (michaelsincere.com, mid-2025, secondary); Goldman (28 Sep
  2026, via Crypto Briefing, secondary) says fewer than half of S&P 500 members above the 200-day near index highs is
  rare outside 1998-2000. On 2026-09-28 the Nasdaq printed 50 new 52-week highs vs 461 new lows (NYSE 16 vs 422)
  (https://investrade.com/market-review-september-28-2026/); equal-weight S&P fell 4.8% in September 2026 while
  cap-weight rose (https://www.janushenderson.com/corporate/article/market-moves-themes-that-mattered-september-2026/).
  A majority of stocks falling while the index makes highs was also flagged on Reddit on Oct 29 2025.
- [ ] **Thrust-day caution.** Identical breadth snapshots can mark peaks: the May 6 2026 thrust day (60% of stocks up,
  63.1% above the 50-day) matched the Jan 14 2026 reading that preceded a six-week slide to 22% above the 50-day
  (edgerater.com, May 6 2026).
- [ ] **Momentum-crash state.** A sharp market decline, high volatility, then a fast rebound: past losers' betas
  exceed 3 and winners' fall below 0.5, so momentum longs get hit on the rebound (Daniel & Moskowitz,
  https://www.nber.org/papers/w20439). Scale momentum exposure down when realized volatility spikes (Barroso &
  Santa-Clara, https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html). After a record momentum year, the
  next year's momentum excess was negative in 7 of 11 cases (avg -5%)
  (https://indexes.morningstar.com/insights/markets-review/bltd9a242a7280e6745/morningstar-factor-monitor-q1-2025).
- [ ] **Policy-shock V.** Every big 2025-26 drawdown was policy-driven and reversed on a policy headline within 1-6
  weeks; the policy-reversal day was the entry, not the low (events sweep;
  https://www.betashares.com.au/insights/liberation-day-upended-markets/). Size to the reversal-day follow-through.
- [ ] **Volatility shocks.** After a day with true range above 2.5x ATR20, the next five sessions average 1.71x ATR20
  (ES 2010-Sep 2026): calmer but still elevated; do not chase extremes
  (https://adamhgrimes.com/volatility-shocks-and-what-follows/). VIX bands seen 2024-26: spikes above 40 resolved into
  V recoveries; 20-30 shocks produced rotational multi-week corrections (events sweep).
- [ ] **Hiking-Fed macro calendar.** Since 2026-09-16 the Fed is hiking (3.75-4.00%), so strong data is bad news
  (2026-06-05 payrolls: S&P -2.6%, Nasdaq -4.2%). Flatten high-beta longs into NFP/CPI/FOMC (next Oct 27-28 and Dec
  8-9) (https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm ;
  https://fedratecalc.com/fomc-meeting-schedule/). Engine: `monitor/rules/market_wide_suppression.py`.
- [ ] **Setup supply is itself a regime signal.** About 60% of clean Qullamaggie-style breakouts in a 12-month study
  came Jul-Oct 2025 and very few Apr-May 2026; size up only while setups are working
  (https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal ;
  https://retailtradersrepository.substack.com/p/qullamaggie-stream-46-50-review). Track expectancy by regime
  (https://www.tradezella.com/blog/swing-trading-strategies).
- [ ] **Regime base rates and flags (Reddit, secondary).** OptionStalker: trending higher about 75% of the time, bear
  about 10%, transition about 13%, tight compression about 2% (Feb 2026 was compression). RDT flags: lower high plus
  quarterly-AVWAP breach plus 50-day breach plus heavy-volume declines means expect a 100-day test; a sustained break
  below the 100-day ends a bull regime.
- [ ] **Small-sample signal tables, read with care.** Alvarez's "30% selloff" signal (S&P first close below the
  200-day after 6+ months above with many stocks 30%+ off highs; 17 cases since 1991)
  (https://alvarezquanttrading.com/blog/the-30-selloff-signal-what-history-tells-us-about-market-recoveries/);
  Kullamagi's V-recovery tell (Nasdaq riding the 10/20 SMA with 5-8% pullbacks)
  (https://qullamaggie.com/nasdaq-comparison-late-90s-vs-today/).
- [ ] **Trend-following check.** 2025 CTA gains were narrow (metals) while equity trend positions were whipsawed by
  the spring crash; 2026 has been broad (SG Trend +15.72% YTD at Oct 2 2026)
  (https://www.toptradersunplugged.com/author/naomi/ ; https://thefullfx.com/ctas-end-2025-on-a-positive-note/).

### 2b. Stock selection (universe layer)
- [ ] **Liquidity.** Price at least $5, average dollar volume at least $5M (engine `universe` defaults); stay under
  1% of the stock's average daily volume (Kullamagi, doc 05).
- [ ] **Stage 2 trend / Trend Template.** Close > 50 > 150 > 200-day, 200-day rising at least 1 month (Minervini
  says 4-5 months is "non-negotiable"), 30%+ above the 52-week low, within 25% of the 52-week high, RS rank 70+
  (https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini ;
  https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-trend-template-marketsmith). The count of stocks passing
  the template is a market-health gauge.
- [ ] **Relative strength.** Top percentile of 3/6/12-month return; RS line making new highs ahead of price
  (Moglen/Soreide); near the 52-week high beats raw past return (George & Hwang, via
  https://cxoadvisory.com/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks). RS means
  the stock vs SPY at the same moment, not RSI (r/RealDayTrading wiki). Engine: add `rank_ret_63d`.
- [ ] **Prior move.** For flags/HTF: up 30%+ (best 100%+) in 1-3 months, in the top 1-2% of performers
  (https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal);
  O'Neil's base breakouts want a prior advance of 30%+ (doc 04).
- [ ] **Range.** For momentum flags: ADR% above 5 so a low-of-day stop is small relative to the move
  (https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups ;
  https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/); Reddit's momentum template uses
  ADR 3-8%. Engine: add `adr_pct_20`.
- [ ] **Group / theme.** Leading stock in a leading group, read from price and volume ("Is it going up on big
  volume?"); 2025-26 leaders: AI/data centres, semis, biotech, precious metals, uranium, quantum
  (https://tradingresourcehub.substack.com/p/qullamaggie-stream-notes-1-june-2023). Rotation sequence traders described:
  precious metals, then semis, then AI infrastructure, then software; beware "least bad" RS in a falling tape.
- [ ] **Fundamentals where the method needs them.** CAN SLIM C/A (quarterly EPS up 18-25%+ and accelerating, 3-yr
  growth 25%+); EP growth (triple-digit EPS/sales); PEG (EPS surprise 20%+); Stine (PE run rate 10 or less). Engine:
  needs point-in-time EDGAR XBRL; not ingested.
- [ ] **Neglect (EP only).** Not rallied in the prior 3-6 months, no recent prior EP
  (https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/); MAGNA: massive acceleration, gap, neglect,
  acceleration in sales, plus short interest 5+ days and 3+ target raises
  (https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots).
- [ ] **Insider signal.** Ignore routine (same month every year) trades; opportunistic and cluster buys far below the
  52-week high are informative, but most of the abnormal return prints on the Form 4 disclosure day
  (https://arxiv.org/abs/2602.06198). Engine: `insider_cluster` (disabled).
- [ ] **Reject.** Names retail crowds pile into (Robinhood herding: -3% to -6% five-day abnormal returns,
  https://www.evidenceinvestor.com/why-most-robinhood-traders-earn-lousy-returns/); sub-$5 low-float promotions;
  pending offerings or shelves; earnings inside the planned hold unless earnings is the catalyst.

### 2c. Setup (the chart before the trigger)
- [ ] **Pullback.** Stacked rising MAs (Landry Proper Order 10-SMA > 20-EMA > 30-EMA,
  https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry);
  a 2-7 bar orderly dip on below-average volume that touches, not slices, the rising 20/50; Holy Grail adds ADX(14)
  above 30 and rising (https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329); Rayner's
  zone is respected twice and entered on the third test
  (https://www.financialwisdomtv.com/post/make-your-money-work-for-you-trend-following-by-rayner-teo). Bid check: more
  volume on the bounce than on the drop at the 50/100/200-day (r/RealDayTrading).
- [ ] **Base / VCP.** Contractions roughly halving (25% to 12% to 6% to 3%), volume drying up to about 40-60% of the
  50-day average in the last one, clear pivot
  (https://www.finermarketpoints.com/post/trade-like-stock-market-wizard-vcp-chapter ;
  https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist). Cup with handle: 12-33% deep, handle in the
  upper half, short handles (under the 22-day median) do best; 54% average rise, 5% failure, 62% throwback on perfect
  trades (https://thepatternsite.com/cup.html). Flat base: 5+ weeks, no more than 15% deep. Patterns that throw back
  do worse 97% of the time; heavy breakout volume helps 79% of up-breakouts
  (https://www.thepatternsite.com/studystudy.html).
- [ ] **Flag / HTF.** 2 weeks to 2 months of higher lows with range tightening while price surfs rising 10/20-day MAs;
  the strength of the first leg predicts follow-through (https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups).
  HTF: 90%+ rise in 2 months or less, buy only on a close above the pattern high (https://thepatternsite.com/htf.html);
  Soreide adds a rising RS line, declining ATR on the right side, flag no deeper than about 25% and above the 50-day,
  never below the 200-day.
- [ ] **Momentum burst.** Prior day narrow-range or down, 3-20 days of tight consolidation, not already up 3 days in a
  row, first or second breakout of a new uptrend
  (https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html); "2LNCH": not up 2 days in a
  row, linear trend, narrow/negative day before, orderly consolidation, close near the high
  (https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts). Inside bars and dojis dominate the
  3 days before a 4% breakout (86-93%) (https://tikamalma.substack.com/p/4-momentum-burst-detailed-research).
- [ ] **Gap setups.** EP: gap 10%+ on a real catalyst, full average daily volume in the first 15-30 minutes. PEG: 10%+
  gain, volume more than 200% of the 50-day average, EPS surprise 20%+, gap holds and forms a 2-5 day flag
  (https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/). BGU: gap at least 0.75x
  ATR(40) on 1.5x volume (doc 13). Catalyst rule: a +20% day in an S&P 500 name is a coin flip over 5 days but positive
  over 20 (Reddit, secondary); hold the month, not the week.
- [ ] **AVWAP.** Price above a rising AVWAP from a meaningful anchor (major low, earnings gap, IPO), tested no more than
  1-2 times; flat AVWAP = indecision; buying dips into a falling AVWAP is "often a losing strategy"
  (https://www.financialwisdomtv.com/post/maximum-trading-gains-using-price-time-volume ;
  https://www.trade-ideas.com/features/ti-avwap/). Pinch: AVWAPs from a major high and a major low converge; trade the
  side that breaks and holds (https://www.luxalgo.com/library/concept/vwap-pinch/). Three timeframes must agree
  (https://cmtassociation.org/?p=2451).
- [ ] **Kell phases.** Wedge Pop (first trade back up through the 10/20 EMAs after a downside extension), EMA
  Crossback, Base n' Break; Wedge Drop is the exit; extension from the 10 EMA on both daily and weekly means expect
  consolidation (https://www.tradingview.com/script/GOkJ7o5J-Wedge-Pop-Drop-QuantVue ;
  https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview).
- [ ] **Stage 2 / Stine weekly.** Breakout week volume at least 2x the 4-week average, 30-week MA rising, 50 above 150,
  RS above its zero line, new 12-month high
  (https://stageanalysis.net/blog/4372/stage-analysis-breakout-quality-checklist). Stine: weekly close above the
  30-week MA on massive volume at about 45 degrees, adds at the 10-week "magic line"
  (https://threadreaderapp.com/thread/1028428610275819520.html).
- [ ] **Mean reversion.** RSI(2) below 5-10 above the 200-day (thin edge: about 71-75% win rate 2016-2026 but
  +18-27% total vs +255% buy-and-hold, https://backtrex.com/en/backtests/connors-rsi-2-sp-500); IBS below 0.3 plus a
  close more than 2.5 average ranges below the 10-day high (Reddit, secondary).
- [ ] **Exhaustion / reversal.** Parabolic: 3-5+ up days, 50-100%+ (large cap) or 300-1000%+ (small cap)
  (https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic). Turtle Soup: new 20-day low with the prior
  20-day low at least 4 days old, then a reclaim (https://www.luxalgo.com/library/concept/turtle-soup/). TD Sequential
  9/13 counts (https://nexusfi.com/a/indicators/td-sequential-demark-indicators).

### 2d. Entry
- [ ] **Trigger, not touch.** Buy stop above the touch/prior bar high (Holy Grail, Landry); "buy strength after the
  dip" (Shannon). Every primary pullback variant uses a trigger.
- [ ] **Volume confirmation.** Breakout volume at least 40-50% above the 50-day average (140-150%+, or 1.5-2x);
  weak-volume breakouts fail; RVOL 2x by 10am picks the name (Reddit).
- [ ] **Do not chase.** Buy within 5% of the pivot (IBD, Minervini); never more than about 1 ADR/ATR extended on the
  day (https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/); never on day 3-5 of a burst;
  Kell's own losers cluster 3-4%+ above the MAs.
- [ ] **Intraday ORH** (1/5/60-minute opening-range high) for EPs, flags and gap-day entries; the engine's daily
  backtester fills at the next open, so daily versions are the delayed/day-2 trade.
- [ ] **Close-based** for RSI-2 (MOC or a limit below the signal close); Raschke's 80-20 buy bar (open in the top 20% of
  the range, close in the bottom 20%) sets up a next-morning trade below the low that reverses back above it
  (https://www.antoinebuteau.com/lessons-from-linda-bradford-raschke/).
- [ ] **Parabolic shorts** (not in this long-only engine): day 3-4, ORL break or first red 5-minute candle, failed
  VWAP reclaim.

### 2e. Risk
- [ ] **Structural stop**: low of day, pivot, dip low or last contraction low, never wider than 1-1.5x ADR/ATR ("if the
  setup needs a wider stop it is not a setup",
  https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/); O'Neil max 7-8%; Minervini max 10%,
  average 5-6%; Rayner 2x ATR. Tight stops beat wide stops in the parabolic-short backtest.
- [ ] **Risk per trade** 0.25-1% of equity (Kullamagi, Bonde, Burns; engine default 1%), Minervini 1.25-2.5%. Same risk
  every trade; 0.5-2% is the Reddit benchmark range.
- [ ] **Notional caps**: engine `max_position_pct` 10; no more than 30% of the account overnight in one name
  (Kullamagi); sector/theme cap (30%) in earnings season.
- [ ] **Gap and cost reality**: model gap-through-stop exits and 10/20 bps per side plus SEC/TAF fees (gates.md);
  turnover under about 50% a month is what keeps anomalies net-positive
  (https://www.nber.org/papers/w20721).
- [ ] **Progressive exposure**: add only as recent trades work, "trade the largest when you are doing your best"
  (https://discussion.fool.com/t/mark-minervini-market-wisdom/108510); never average down (Raschke).
- [ ] **Before sizing up**: 100-200 trades at about 2:1 and 50% winners (Bonde), or expectancy above 0 over hundreds of
  trades; RDT uses 75% WR and 2.0 PF over 3 months; Bonde says study 5,000-10,000 breakouts first.

### 2f. Exit
- [ ] **Partial plus trail** (common to most camps): take 1/3-1/2 into strength after 3-5 days or at +20% (or +2R),
  move the stop to breakeven, trail the rest on the first close below the 10- or 20-day MA
  (https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/). IBD/Morales violation: a close
  below the MA, then a lower low the next day
  (https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/). Engine: needs a scale-out
  hook.
- [ ] **Time exits**: momentum bursts die in 3-5 days (https://stockbee.blogspot.com/2016/07/profiting-from-momentum-bursts.html);
  no follow-through by day 3 means out.
- [ ] **Profit targets**: IBD 20-25%; 8-week hold if +20% within 3 weeks of a proper breakout
  (https://discussion.fool.com/t/ibd-8-week-hold-rule/112549); Holy Grail target = prior swing high; IBD SwingTrader
  about 10% target, 3% stop, 5-10 days.
- [ ] **Failure exits**: breakout back under the pivot within 1-2 days; two closes below the 20 EMA; a close below the
  50-day on heavy volume; Shannon: the 5-day MA rolls over or price loses its AVWAP.
- [ ] **Extension exits**: sell into extension above the 10 EMA on daily and weekly (Kell); climax runs (25-50% in 1-3
  weeks, largest up day); Raschke exits a winner that gives back 20% from its peak.
- [ ] **Mean-reversion exits**: close above the 5-day SMA, or RSI(2) above 65-70.
- [ ] **Weekly (Stine)**: a weekly close below the magic line; 7-10 weeks after a thrust; offerings sold "without
  hesitation".

---

## 3. The 2025-2026 regime: what it rewards and what it punishes

### 3a. Timeline (dates are decision/announcement dates)
| Date | Event | Source |
|---|---|---|
| 2025-04-02 to 04-08 | "Liberation Day" tariffs; S&P -4.84% (Apr 3) and -5.97% (Apr 4); VIX intraday 60.13 on Apr 7 | https://en.wikipedia.org/wiki/2025_stock_market_crash ; https://macroption.com/vix-all-time-high |
| 2025-04-09 | 90-day tariff pause: S&P +9.5% (Day 3 of the rally, too early for an FTD) | https://www.betashares.com.au/insights/liberation-day-upended-markets/ ; https://www.nasdaq.com/articles/april-2025-review-and-outlook |
| 2025-04-22 | IBD follow-through day (Day 11); exposure staged 0-20% to 40-60% (Apr 28) to 60-80% (May 13) | doc 07 |
| 2025-04-24/25 | NYSE Zweig Breadth Thrust plus Nasdaq 3:1 thrust | sentimentrader.com (Apr 25 2025), doc 06 |
| 2025-05-08 | Minervini's S&P buy signal; 100% long the index while % above 200-day stayed "very low" (secondary) | michaelsincere.com via YouTube sweep |
| 2025-06-27 | S&P new all-time high (6,173) | https://en.wikipedia.org/wiki/2025_stock_market_crash |
| 2025-07 to 10 | Window for clean breakouts (about 60% of a 12-month study's setups); meme revival (OPEN +400% in July) | FWTV link in 2a; https://finance.yahoo.com/news/opendoor-kohls-resume-rally-meme-160314410.html |
| 2025-10-06 / 10-10 | Bitcoin ATH $126,080; S&P -2.7% on 100% China tariff threat, $19.1B crypto liquidations | https://finance.yahoo.com/markets/crypto/articles/bitcoin-peaked-126-080-october-091605452.html ; https://www.theblock.co/post/374266/crypto-liquidations-near-10-billion-in-historic-drawdown-following-trumps-100-tariffs-on-china |
| 2025 Q4 | Momentum +0.77% vs value +8.34%; value top global factor for 2025 | https://money.tmx.com/content-hub/value-momentum-content-hub/why-value-outpaced-momentum-2025-top-factor/ |
| 2025-11 | NYSE ZBT near-miss (0.59, no 0.615 cross) | doc 06 |
| 2025-12-10 | Fed cut to 3.50-3.75% (175bp of cuts from peak) | https://www.federalreserve.gov/monetarypolicy/openmarket.htm |
| 2026-01-27/28 | S&P interim peak about 7,000 (level low confidence) | https://www.vtmarkets.com/en-mena/live-updates/following-a-2026-peak-spx-declines-methodically-almost-meeting-the-previously-forecast-6521-target/ |
| 2026-02-03 to 02-12 | Software rout on AI-automation fears; IBD Nasdaq 4th DD in 5 sessions on Feb 3 | https://www.cnbc.com/2026/02/04/stock-market-today-live-updates.html ; doc 07 |
| 2026-02-20 | Supreme Court voids IEEPA tariffs; Section 122 surcharge imposed | https://globaltradealert.org/blog/from-ieepa-to-section-122 |
| 2026-02-28 | US-Israel strikes on Iran; Brent from $72 toward $118-120 | https://www.fortune.com/2026/03/05/dow-drops-1000-markets-react-oil-spikes-iran-war-middle-east |
| 2026-03-27 | Nasdaq in correction (five-week rout, 10-yr 4.44%); classic ZBT setup failed in late March | https://markets.financialcontent.com/workboat/article/marketminute-2026-3-27-wall-streets-dark-friday-nasdaq-sinks-into-correction-as-five-week-rout-deepens ; doc 06 |
| 2026-04-08 | Iran ceasefire, S&P +2.2%; IBD FTD (Day 6) | https://fortune.com/2026/04/08/markets-sp-trump-truce-ceasefire-iran-war-rally-strait-of-hormuz ; doc 07 |
| 2026-04-14 | Nasdaq Breadth Thrust (62%) fired; SEC approved FINRA's PDT repeal (effective 2026-06-04) | doc 06 ; https://www.finra.org/rules-guidance/notices/26-10 |
| 2026-05-06 | Thrust day matching the January pre-correction breadth peak (caution) | edgerater.com via YouTube sweep |
| 2026-06-05 | Worst day of 2026 on strong payrolls: S&P -2.6%, Nasdaq -4.2%, SOX -10%+ | https://thebusinessjournal.com/stocks-slump-as-big-tech-sinks-and-a-strong-may-jobs-report-boosts-odds-for-higher-interest-rates/ |
| 2026 H1 | Equal-weight S&P +12.1% vs cap-weight +10.2%; scan the 493 | https://proactiveadvisormagazine.com/sp-500-update-market-breadth-improves-in-the-first-half-of-2026/ |
| 2026-07 | SOX -21% (worst month since Oct 2008), then +21% off the Jul 29 low; Section 301 tariffs with no expiry from Jul 24 | https://www.cnbc.com/2026/07/29/chip-selloff-sk-hynix-samsung-softbank.html ; https://www.clearygottlieb.com/news-and-insights/publication-listing/trump-administration-imposes-new-section-301-tariffs-on-60-trading-partners |
| 2026-07-20 | Bonde: range-bound market; breakouts unlikely to follow through until a breadth thrust (primary) | doc 09 |
| 2026-08-13 | S&P record close 7,798.99 | https://www.morningstar.com/news/dow-jones/202610018747/sp-500-rises-019-to-766645-data-talk |
| 2026-09-16 | FOMC hikes 25bp to 3.75-4.00% (first hike since July 2023) | https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm |
| 2026-09 | Equal-weight S&P -4.8%, Russell 2000 -5.3%, 10-yr 5.29% (highest since 2002) | https://www.janushenderson.com/corporate/article/market-moves-themes-that-mattered-september-2026/ |
| 2026 Q3 | S&P +2.03% (YTD +11.77%), Nasdaq +2.47%, Dow -2.70%, Russell 2000 -7.52% (YTD +12.69%), 10-yr +88bp (verified 2026-10-06) | https://www.firstfinancialtrust.com/2026/10/01/quarterly-market-review-july-september-2026/ |
| 2026-10-06 | SPY closed $779.09 vs a 52-week high of $781.62 (verified 2026-10-06, stockanalysis.com); 26.9% of 4,806 US stocks above the 50-day, 39.7% above the 200-day (doc 06, thetrading.tools) | https://stockanalysis.com/etf/spy/ ; doc 06 |

**Conflicts in the inputs, resolved where possible.**
- (conflict) *Index level on 6 Oct 2026.* The events sweep summary says the S&P was 1.7-3% below its Aug 13 record;
  that was written from the Oct 1 close (7,666.45, +11.99% YTD). Doc 04 cites 7,819 (+14.2% YTD) from a
  thepatternsite.com banner on Oct 6 (not re-verifiable today), and doc 07 reports Nasdaq record closes on Oct 5-6.
  SPY's Oct 6 close of $779.09 against a $781.62 52-week high supports "at or near a record" on Oct 6.
- (conflict) *S&P 500 % above 200-day.* 67.10% on Sep 4 2026 (https://historyofmarket.com/sp500/sp500-breadth/) vs
  41-46% on Oct 1 (Thackray via BNN Bloomberg, doc 06). Both can be true: breadth collapsed in September (equal-weight
  -4.8%). The events sweep's "breadth is healthy" read is the H1/August picture, not October.
- (conflict) *Q1 2026 drawdown.* About 10% from the Jan 27 high to about 6,317 by Mar 30 (chaikinanalytics.com,
  raseedinvest.com) vs -7.7% for March with a Mar 13 low near 6,632 (VT Markets, low confidence). Use "roughly 8-10%".
- (conflict) *Russell 2000.* Up about 19% YTD through Jul 31 (doc 14), a reported record of 3,045.48 in August
  (unverified snippet), then Q3 -7.52% and +12.69% YTD at Sep 30 (verified). Consistent once dated: small caps led H1
  and gave back much of it in Q3.
- (conflict) *Retail share of volume.* About 35% (broker estimates) vs 17% at end-Q1 2026 (JPMorgan). Use the trend.
- (unverified) A ~6% one-day drop in chip/AI-infrastructure stocks on Sept 14-15 2026 attributed to an AI-pacing essay
  (single secondary source: https://www.moneymagpie.com/investment-articles/whats-going-on-with-ai-stocks-in-september-2026),
  and reports that OpenAI paused training of its latest models (via Investrade, Sep 28). Do not rely on either.

### 3b. What the regime rewarded and punished

| Rewarded (with evidence) | Punished (with evidence) |
|---|---|
| **Buying the policy-reversal follow-through** (Apr 9 2025, Apr 8 2026), and the M rule's staged exposure after FTDs (Day 11 in 2025, Day 6 in 2026) | **Shorting into policy holes** ("shorts into the hole were destroyed", Apr 2025); carrying short swings through the 2025 grind (Reddit's top adjustment of 2025) |
| **Momentum breakouts in leaders, but only Jul-Oct 2025** (FWTV study; USIC 2025 winners, e.g. J Law +252.3%, https://www.bolsamania.com/nota-de-prensa/mercados/j-law-sets-two-year-record-with-1499-return-in-us-investing-championship--21854364.html) | **Breakouts and bull flags since Mar 2026** (a full-timer's first losing year on unchanged rules, Reddit, unverified); few clean flags Apr-May 2026; Bonde's stand-aside call (Jul 2026); Minervini's 2025 remark that breakouts failed in 1-2 days (secondary) |
| **Pullbacks in leaders above rising MAs** (EasySwing trend pullback PF 1.45 vs Qullamaggie-style breakout 1.10 through its mid-2025 to Apr 2026 holdout; crowd "buy dips, not breakouts", Sep 2026) | **Pullbacks to the 50-day in the average stock** while only about 27% of stocks are above their 50-day (the MA is rolling over) |
| **Index mean reversion** (RSI-2: SPX +6.4% in 2025 and +6.5% 2026 YTD; NDX +6.9% 2026 YTD, https://backtrex.com/en/backtests/connors-rsi-2-sp-500) and Alvarez's diversification of MR plus momentum plus timing (24%/yr, 23% max DD in his example, https://alvarezquanttrading.com/blog/the-power-of-strategy-diversification/) | **Small-cap momentum**: Russell 2000 -7.52% in Q3 2026; the 4% burst's home turf |
| **Equal-weight / the 493 in H1 2026** (EW +12.1% vs CW +10.2%) and small-cap value in July 2026 (Stine-style PE screens; doc 14) | **Mega-cap reliance and momentum after the record 2024 momentum year** (Q4 2025 momentum +0.77%) |
| **Theme rotation awareness**: semis to hyperscalers (Wilson, Jul 6 2026), memory rebound, metals (gold +64% in 2025), biotech (XBI), defense | **Holding high-beta AI through macro prints** under a hiking Fed (Jun 5 2026); crypto-proxy equities (Strategy at 0.83-0.86x mNAV, https://www.sec.gov/Archives/edgar/data/0001050446/000119312526363557/d431748dfwp.htm) |
| **Trend following in 2026** (SG Trend +15.72% YTD at Oct 2) | **Chasing large-cap earnings beats** (Q2 2026 beats +0.4% vs a +1.0% five-year average, FactSet via doc 13); late IPO pops ("bloodletting after the pop") |

### 3c. State of play on 2026-10-06 and what to do with it
- Index near a record, average stock in a correction: 26.9% above the 50-day, 39.7% above the 200-day (all US);
  S&P 500 members 41-46% above the 200-day; median S&P stock 16% off its high (Goldman via Crypto Briefing,
  secondary). The all-US ZBT line reads 0.47 (neutral). Hill-style read: inside the 40-60 no-man's land, bull signal
  still technically alive until below 40.
- Macro: Fed hiking (3.75-4.00%), 10-year above 5%, crude elevated, Q3 small caps -7.52%, VIX mid-teens.
- **Engine posture implied by the gates**: reduced size; leaders-only, RS-filtered pullbacks; RSI-2 on index ETFs as
  the diversifier; breakout families in paper only until a Stockbee 10-day ratio above 2 or a thrust prints; flatten
  into FOMC Oct 27-28.
- **Calendar ahead**: FOMC Oct 27-28; midterms Nov 3 (midterm years: 70% historical probability of a 10%+ correction
  per Chaikin, Mar 11 2026, secondary; https://realinvestmentadvice.com/resources/blog/market-correction-risk-why-summer-2026-looks-risky/);
  23x5 overnight trading from Dec 6 (re-validate all gap statistics); FOMC Dec 8-9; funding deadline Dec 11
  (https://ffis.org/budget-brief/house-and-senate-move-to-minimize-fy-2027-government-shutdown-risk/); possible
  Anthropic/OpenAI mega-IPOs as a liquidity drain (reported "as soon as October", no S-1 seen,
  https://ibinterviewquestions.com/guides/equity-capital-markets/the-2026-mega-ipo-pipeline-spacex-openai-anthropic-kraken).
- **Structural changes that touch the engine**: PDT rule gone from 2026-06-04 (phase-in to 2027-10-20; repeated
  intraday deficits can trigger 90-day freezes, https://www.sofi.com/learn/content/pattern-day-trading-rules/); T+1
  since 2024-05-28; broker MCP servers (Alpaca executes; IBKR stages to an "AI Instructions" queue,
  https://www.stockbrokers.com/guides/ai-agent-brokers); tokenized-stock exemption from 2026-09-17
  (https://www.skadden.com/insights/publications/2026/09/sec-innovation-exemption-establishes); 0DTE at a record 66.2%
  of SPX volume in July 2026 (https://spotgamma.com/record-0dte-volume-reshapes-the-sp-500/); retail flow is visible
  and textbook flags get faded more aggressively (a 2.1R strategy in 2023 might yield 0.8R in 2025-26,
  https://www.tradezella.com/blog/swing-trading-strategies).

---

## 4. Where credible practitioners agree and disagree

### 4a. Agreement (the common threads)
1. **Trade with the market.** Every school has a regime gate (M rule, Market Monitor, QQQ 20 EMA, SPY 200-day,
   breadth), and every school's failure mode is breakouts in corrective tapes. Academic support: momentum crashes
   (Daniel & Moskowitz), trend filters reduce drawdowns (Faber, Zakamulin).
2. **Buy strength, not cheapness.** Leaders near 52-week highs with top-percentile RS and stacked rising MAs
   (O'Neil, Minervini, Kullamagi, Kell, Burns). This is the best-evidenced part of the whole field.
3. **Quiet before loud.** Contraction with drying volume, then range and volume expansion on the trigger day (VCP,
   flags, bursts, PEG consolidations, Crabel NR7).
4. **A tight, structural stop capped by volatility** (low of day, pivot, dip low; at most about 1 ADR/ATR, 7-10%
   absolute), with fixed-fractional risk of 0.25-1% per trade.
5. **Asymmetric exits.** Cut failures in 1-3 days; take 1/3-1/2 after 3-5 days or 2R; trail the rest on the 10/20/50.
   Low win rates (25-40%) are normal for momentum methods; the right tail pays.
6. **Do not chase.** Within 5% of the pivot, not more than 1 ADR extended, never the third day up.
7. **Opportunity clusters by regime.** Setups and profits bunch in post-correction windows; size up only while
   recent trades work (progressive exposure).
8. **Earnings are either the catalyst or a no-go.** Avoid holding through a report unless the report is the reason
   for the trade.
9. **Process over prediction**: written plan, journal in R-multiples, hundreds of trades before conclusions.

### 4b. Disagreement
| Question | One side | Other side | What the evidence says |
|---|---|---|---|
| Breakouts or pullbacks in 2026? | Minervini, Kullamagi, Zanger: buy the breakout from a proper base | Crowd (Sep 2026) and Shannon: buy pullbacks / strength after the dip | EasySwing panel: pullbacks PF 1.45 vs flags 1.10; cup and handle 1.57 (all gross). Regime-dependent |
| Stops | Connors: "stops hurt", none | Kullamagi: low of day, max 1 ADR; O'Neil: 7-8%; Rayner: 2x ATR | Connors' no-stop is about average return; OOS losses run 1.7-2x wins (negative skew). Keep a catastrophic stop |
| Which pullback? | Kell: the first pullback after the wedge pop | Rayner: enter on the third test of the zone | Untested; pick one per strategy and log it |
| Profit-taking | IBD: 20-25% target plus 8-week rule | Kullamagi: no target, MA trail; Stockbee: out in 3-5 days | Bulkowski: much of the expectancy is in a few multi-month winners; a fixed 20-25% truncates them |
| Catalyst needed? | Bonde: bursts need no catalyst | Chan (2003), Savor (2012): no-news extremes reverse | Favour catalysts; filter attention-driven moves |
| Is PEAD alive? | Hirshleifer-Peng-Wang (RFS 2025), Dickerson-Julliard-Mueller | Martineau (CFR 2022), Subrahmanyam (Jan 2026): gone outside microcaps | Large-cap drift gone since about 2006; residual is in microcaps where costs eat 70-100% |
| Breadth thrusts | SentimenTrader/Leuthold: 16-20 of 16-20 signals up at 12 months | CXO (2017): no lead at 21 days or less; vendor counts disagree; all-US version missed Apr 2025 | Use as an exposure dial judged by drawdown reduction, not a timing signal |
| Concentration | Minervini 20-25% positions; Kell about 190% gross on margin; Stine Kelly-sized 1-2 names | Bonde/Kullamagi: 0.25-1% risk, many positions | Concentration produced contest results and 50-106% drawdowns. Engine caps stay |
| RSI-2 market filter | Connors: the instrument's own 200-day | Nagel (2012), a 2026 ES test: reversal pays most when VIX is high | Test a high-vol on-switch, small size, hard stop |
| Day-1 vs delayed EP | Kullamagi: day-1 ORH, "no need to be first in" | Bonde 2026: delayed-reaction EPs as gaps grew to 20-40% | Daily engine can only do the delayed version |
| Fundamentals | CAN SLIM, Minervini Code 33, Stine PE: required | Kullamagi: "stories are way more powerful than fundamentals"; Shannon: price only | Each letter of CAN SLIM maps to an anomaly; the bundle lagged in real money (FFTY) |

---

## 5. Scam and noise filter

**Hard red flags (walk away).**
- **Impersonation.** Kullamagi: "I am NOT running any paid service ... and I don't sell anything"
  (https://qullamaggie.com/); his official channels are X, YouTube, Twitch and one Discord. Stockbee offers no free
  signals (paid membership only, https://stockbee.blogspot.com/). Big handles (Qullamaggie, Minervini, Zanger,
  Kobeissi) are cloned on X/Telegram/Discord; unofficial Medium accounts and paid "Qullamaggie Trading System Pro"
  scripts are not the traders (https://medium.com/@qullamaggieus/mastering-swing-trading-strategies-a-comprehensive-guide-to-qullamaggie-methodology-2e2be5bf6a53 ;
  https://kr.tradingview.com/script/iQtlXxO8-Qullamaggie-Trading-System-Pro). Verify on qullamaggie.com,
  minervini.com, chartpattern.com, alphatrends.net, stockbee.blogspot.com.
- **Paid alert rooms on low-float names.** DOJ/SEC charged eight influencers (Atlas Trading Discord) over an about
  $100M pump scheme in which they posted targets while selling (https://www.aol.com/sec-charges-8-social-media-160856411.html ;
  https://dot.la/pump-and-dump-discord-2658970824.html). FURU definition: someone touting stocks while selling an alert
  service (https://www.valuethemarkets.com/analysis/what-is-a-furu).
- **DM recruiting.** "Legitimate investment advisors do not use WhatsApp, Telegram, Discord"; bots impersonate mods;
  check whether an account suddenly posts about one or two tickers (r/investing automod, snapshot Jan 9 2026,
  https://reddit.sentinel-team.org/posts/1q13q10/snapshots/2026-01-09T15%3A51%3A08.367904Z). "PM me for code" posts
  are scams.
- **Pirated courses** ("getwsodo" re-uploads of TraderLion's HTF masterclass) are unauthorized and frequently malware.
- **Prop-firm "results".** Payout posts on accounts with about $4.5K real risk; Apex co-founder scheme video (Jan
  2025), LivvFX $200K ban (Jan 2026), Topstep instrument and contract changes (Reddit sweep).

**Statistical noise (discount heavily).**
- **Results-post hygiene**: realized-gains-only journals, 100% win claims, image-only P&L, under-100-trade samples,
  1%-a-day compounding, 0-comment posts.
- **High win rate is not edge**: RSI-2 won 71% of trades 2016-2026 and compounded 1.7%/yr; FXCM's 43M-trade study had
  62% winners who lost money because losers were about 2x winners.
- **Backtest traps**: no fees/slippage, look-ahead, survivorship, overfitting ("I ADMIT IT. I OVERFIT."), testing only
  on instruments that went up for 15 years. After White's Reality Check no classic technical rule is significant
  (Sullivan-Timmermann-White 1999; Bajgrowicz-Scaillet 2012). Assume any social-media backtest without a
  multiple-testing correction is overfit.
- **Survivorship case studies**: "study the top-100 winners" (FWTV: 58 clean breakouts, 20:1 R:R; 36 VCPs, 11:1)
  shows what winners looked like, not expectancy.
- **Internally inconsistent third-party numbers**: the Jun 2025 burst study claims 82.31% hit +10% in 3-5 days yet
  12.8% and +0.88% average elsewhere; EasySwing's VCP row shows PF 0.38 with +0.1R; finermarketpoints' "40% higher
  success" line has no source; Bulkowski's stats are "perfect trades" and flagged outdated by the author
  (https://www.thepatternsite.com/BestPatterns.html).
- **Championship returns are not templates**: USIC accounts are small, concentrated, often levered (Kell about 190%
  gross; enhanced-growth divisions allow options/futures; +1,110% in H1 2025, https://www.webull.com/news/13249512026235904).
  Minervini publishes no audited returns; Stine's $45,721 to $6.8M is one window with no CPA attestation.
- **Reach is not relevance**: aggregators show Rayner Teo at "18.3M" subscribers (about 2.2M actual,
  https://sponsorradar.com/channels/tradingwithrayner); the biggest channels are forex/day-trading first; AI-summary
  sites strip the source and date (go back to TraderLion or minervini.com before quoting).
- **LLM engagement farming**: LLM-written strategy posts and "Dead Internet" content in r/algotrading; all LLMs lost
  in a live trading competition (Nov 2025, Reddit sweep).
- **Attention signals that lose**: Robinhood herding names (-3% to -6% over 5 days); congressional-trade copying (no
  edge post-STOCK Act, 45-day lag; NANC/KRUZ about track the S&P for 0.74%, https://www.nber.org/papers/w35041);
  "Congress beat the market" annual reports are approximations.
- **Commercial ties**: r/RealDayTrading is co-run by OneOption's founder (method free, room paid); course sellers seed
  r/swingtrading; most paid rooms monetise education rather than their own P&L.
- **Structural "free leverage" myths**: PDT repeal is not free leverage (intraday margin deficits, 90-day freezes,
  losses can exceed deposits); 0DTE retail losses are more than 60% transaction costs
  (https://www.bloomberg.com/news/articles/2023-04-21/day-traders-lose-358-000-per-day-gambling-on-zero-day-options).
- **Base rate**: 93-97% of persistent day traders lose (Brazil, Taiwan, India); technical-analysis users underperform by
  about 7%/yr (Hoffmann & Shefrin 2014); lower costs increase trading and deepen losses (Chen & Lin 2025).

**Own-process noise.** Do not rewrite a system after one bad month (Alvarez shelves changes 2-3 months,
https://alvarezquanttrading.com/blog/bad-month-for-your-strategy-should-you-change-it/); log every variant in
`research/trials.py`; "never read financial media" is Kullamagi's version of the same rule.

---

## 6. Method sections (one per deep dive)

Each section: what it is, the key rules in one block, the evidence in one line, the 2026 fit, and the engine
mapping. Full rules, chart signatures, teachers, pitfalls and all sources are in the linked file.

### 6.1 Pullback to the 20/50 MA in an uptrend — [docs/methods/01-pullback-20-50-ma-uptrend.md](methods/01-pullback-20-50-ma-uptrend.md)
- **What**: in an established uptrend (close > rising 50 > 200; leader near highs), buy a quiet 2-7 bar dip into the
  20 EMA/SMA or the 20-50 zone when price trades back above the touch/pivot bar high.
- **Rules**: universe close > SMA50 > SMA200, 50 rising (Landry Proper Order; Holy Grail ADX(14) > 30 and rising),
  RS rank 96+ or within 5-10% of the 52-week high; dip low within about 1-2% or 1 ATR of the 20 EMA. Stop under the
  touch-bar or swing low (or 1.5-2 ATR). Target the prior swing high or 2R for part; trail the rest under the 20/50
  (Rayner: exit on a close beyond the 50 EMA; TradeZella: 2 closes below the 20 EMA). Risk 1% (Burns, Rayner).
- **Evidence (B-)**: EasySwing (7 Jul 2026, gross, tuned on its data) 1,092 trades, 26% wins, +0.3R, PF 1.45, 3-day
  hold; SPY stochastic pullback 195 trades, 74% wins, PF 2.3, CAGR 3.6%; academic support is indirect (short-term
  reversal inside momentum); Grimes finds MA bounces random, so the edge is trend plus trigger, not the line.
- **2026 fit**: best of the long setups if leaders-only and gated; pullbacks to the 50 in the average stock fail now.
- **Engine**: `pullback_trend` (enabled). Missing: `ema_20/ema_50/adx_14`, RS percentile, `should_exit` trail,
  scale-out, earnings filter. Proposed variants `pullback_holy_grail`, `pullback_ema_zone`.

### 6.2 Episodic Pivot — [docs/methods/02-episodic-pivot.md](methods/02-episodic-pivot.md)
- **What**: a neglected stock (flat 3-6+ months) gets a real surprise and gaps 10%+ on 3-10x volume; buy the day-1
  opening-range high or a day-2+ delayed entry. Bonde named it (2007); Kullamagi popularised it.
- **Rules**: gap at least 10%, ADV traded in the first 15-30 minutes, triple-digit growth, no rally in prior 3-6
  months, no recent EP (Kullamagi); Bonde 2010: +8% on 300k shares at 3x+ the 100-day average. Stop low of day,
  max 1-1.5 ADR. Sell 1/3-1/2 after 3-5 days, breakeven, trail the 10/20-day. Risk 0.25-1%.
- **Evidence (D)**: Bonde's about 70% wins is unaudited; Torres (Sep 2026) says every mechanical EP version he tested
  lost to SPY (numbers paywalled); about 66% of 2019-24 gap-ups closed below the open; PEAD decayed outside microcaps.
- **2026 fit**: still taught (Bonde's Nov 2026 bootcamp: EP, EP9M, delayed EP); day-1 gaps are bigger, so delayed
  entries are more practical. Viable only with a catalyst filter and discretionary ranking.
- **Engine**: daily version = day-2 / delayed EP (`strategies/episodic_pivot.py` proposed); day-1 ORH belongs in the
  monitor path (`premarket_gap`, `peg_survivor`, `rvol_now`) with intraday bars. Catalyst quality is a Claude enum.

### 6.3 VCP breakout / Minervini Trend Template — [docs/methods/03-vcp-minervini-trend-template.md](methods/03-vcp-minervini-trend-template.md)
- **What**: only Stage-2 leaders passing the 8-point Trend Template, bought on a volume breakout through the pivot of
  a Volatility Contraction Pattern.
- **Rules**: Template (close > 150 and 200; 150 > 200; 200 rising 1+ month; 50 > 150 and 200; close > 50; 30%+ off the
  low; within 25% of the high; RS 70+). VCP: 2-6 contractions each about half the prior, volume dry-up, buy through the
  pivot on volume 40-50% above average, not more than about 5% above the pivot. Stop under the last contraction, max
  10%, average 5-6%. Risk 1.25-2.5%. Breakeven after 2-3x risk; sell into strength or on a heavy-volume 50-day break.
- **Evidence**: Template as a filter B (components academically supported); coded VCP trigger D (EasySwing PF 0.38,
  inconsistent row; template fresh-pass 18,382 trades PF 0.99); USIC results unaudited and one-year.
- **2026 fit**: Minervini called 2025 bifurcated and leaned on the index (May 8 2025 signal); clean VCPs bunched in
  Aug-Sep 2025, Jan 2026 and the Apr 2026 recovery. Use the Template as a universe filter and breadth gauge.
- **Engine**: add `sma_150`, `sma_200_slope_21`, `dist_52w_low`, `rank` features; `tt_pass_count` as breadth;
  swing-pivot VCP detector needed. `vcp_sepa.py` proposed but low priority.

### 6.4 Classic base breakouts — [docs/methods/04-chart-pattern-base-breakouts.md](methods/04-chart-pattern-base-breakouts.md)
- **What**: buy a leader (30%+ prior advance, high RS, confirmed uptrend) as it clears the pivot of a 7-65 week cup's
  handle, a 5+ week flat base no more than 15% deep, or a short flag, on 40-50%+ above-average volume.
- **Rules**: cup 12/15-33% deep, handle 1-3 weeks in the upper half, about 5-12% deep, light volume; buy at handle
  high + $0.10, buy zone up to 5% above. Stop 7-8% below the buy point or the handle low or back in the pattern. Take
  20-25%; hold 8 weeks if +20% within 3 weeks.
- **Evidence (C)**: Bulkowski cup rank 3/39 on perfect trades (913), 28% never reach +15% (2nd ed.); flags 44% failure;
  failure rates doubled from the 1990s to 2003-07; Lo-Mamaysky-Wang: information, no profitable rule; EasySwing cup and
  handle 3,582 trades, 30% wins, +0.5R, PF 1.57 gross (best of its base detectors).
- **2026 fit**: narrow tape, few valid setups; breakouts reportedly failing since March 2026. Gate on, RS-line leaders
  only; prefer flat bases and short-handle cups.
- **Engine**: nearest are `breakout_52w`, `sr_breakout`; `base_breakout.py` proposed with geometry features and an M
  gate.

### 6.5 Qullamaggie breakout — [docs/methods/05-qullamaggie-breakout.md](methods/05-qullamaggie-breakout.md)
- **What**: a top 1-2% momentum leader (+30-100% in 1-3 months, ADR above 5%) breaks out of a 2-week-to-2-month
  tightening flag riding its rising 10/20-day MAs.
- **Rules**: ORH entry (1/5/60-min), never more than one ATR/ADR up on the day; stop low of day, never wider than the
  ADR; sell 1/3-1/2 after 3-5 days, breakeven, trail to the first close below the 10- or 20-day; risk 0.25-1%,
  positions 10-20%, max 30% overnight in one name.
- **Evidence (C-)**: self-reported 25-35% wins, 268% CAGR 2013-19 (unaudited); Stonks Capital 2007-2025 CAGR 19%, max
  DD -21%, 2,382 trades (costs not disclosed); EasySwing 16,943 trades, 27% wins, PF 1.10 gross; Sharpe -3.59 in
  2007-10.
- **2026 fit**: clean flags clustered Jul-Oct 2025; thin mechanical edge; no primary 2025-26 commentary from Kullamagi
  found (re-checked 2026-10-06). Gate on, leading themes only, costs modelled.
- **Engine**: add `adr_pct_20`, `rank_ret_63d`, `higher_lows_n`; `qullamaggie_flag.py` proposed; ORH needs intraday
  bars.

### 6.6 Breadth / regime filters — [docs/methods/06-breadth-regime-filters.md](methods/06-breadth-regime-filters.md)
- **What**: a market-level gate that sets how much long exposure to carry by counting participation, not watching the
  cap-weighted index.
- **Rules**: ZBT (10-day EMA of A/(A+D) below 0.40 then above 0.615 within 10 sessions); Hill (% above 200-day on above
  60%, off below 40%; 2 of 3 indicators); Stockbee (10-day 4%-up/4%-down ratio 2+ bullish, 0.5 or less bearish;
  quarterly 25% counts); Keller (% above 50-day below 50% = red flag). Regime stops: any of those invalidations means no
  new entries and trim.
- **Evidence (B for the price-trend cousin; C for thrusts)**: about 14-20 ZBTs since 1945, all up at 6 and 12 months
  (Detrick 19/19, SentimenTrader 20/20); ZBT as a timing system had lower CAGR but much lower drawdown (secondary);
  CXO 2017 found no lead at 21 days or less; Yu, Webb and Lin (2025) mixed.
- **2026 fit**: one NYSE ZBT (Apr 2025) and two near-misses (Nov 2025, Mar 2026); Nasdaq thrust Apr 14 2026; now
  bifurcated. Read: reduced size, leaders only, wait for a ratio above 2 or a thrust.
- **Engine**: `features/breadth.py` (proposed, section 7) broadcast as `market_*`; gate params next to
  `min_market_trend_state`; calibrate thresholds on the engine's own universe.

### 6.7 CAN SLIM / IBD with Market School — [docs/methods/07-canslim-ibd-market-school.md](methods/07-canslim-ibd-market-school.md)
- **What**: top-group leaders with accelerating earnings bought on base breakouts, only in an IBD confirmed uptrend.
- **Rules**: C (quarterly EPS up 18-25%+, accelerating), A (3-yr 25%+, ROE 17%+), N (new highs), S, L (RS 80+), I
  (rising fund ownership), M (FTD Day 4+, about 1-1.25%+ on higher volume; DDs -0.2% on higher volume, expire after 25
  sessions or a 6% rally; 5-6 in 25 sessions = pressure). Buy at the pivot on 40-50%+ volume, buy zone 5%; sell at
  7-8% loss, take 20-25%, 8-week rule.
- **Evidence (C)**: rules reverse-engineered from past winners; AAII paper screen 22.1%/yr vs 10.7% (10 yrs to Jan
  2019, no costs, about 3 stocks); FFTY vs SPY to Oct 6 2026: 1-yr -4.74% vs +17.67%, 10-yr 4.94%/yr vs 15.53%/yr
  (stockanalysis.com via doc 07).
- **2026 fit**: M caught both V-recoveries (Apr 22 2025, Apr 8 2026) and the Feb-Mar 2026 DD cluster warned before the
  March correction; selection lagged. Keep M as a gate at reduced exposure; prefer SwingTrader-style 5-10 day holds.
- **Engine**: `features/market_school.py` state machine (needs real index volume; local duckdb data is synthetic);
  RS percentile; EDGAR XBRL/13F for C/A/I.

### 6.8 Anchored VWAP / multi-timeframe (Shannon) — [docs/methods/08-anchored-vwap-multi-timeframe-shannon.md](methods/08-anchored-vwap-multi-timeframe-shannon.md)
- **What**: trade with the weekly/daily trend; wait for a pullback to a rising AVWAP and rising 5-day MA; buy only after
  short-term strength returns.
- **Rules**: Stage 2 names; 2-6 day pullback on falling volume, level tested at most 1-2 times; trigger: higher low,
  clears the prior short-term high, reclaims the 5-day MA and the AVWAP from the pullback high. Stop below the dip low.
  Sell the first third near the daily R2 pivot; trail while the 5-day MA rises. Hold 3-6 days, sometimes 5-6 weeks.
- **Evidence (C-/D)**: self-reported 50-60% wins; Zarattini & Aziz session-VWAP QQQ study (Sharpe 2.1) failed a
  QuantConnect replication after realistic costs.
- **2026 fit**: Shannon active through 2026 (CMT ep. 61, Feb 2026; weekly posts to 2026-09-25); self-throttles in chop.
  Best as an entry-quality and market filter.
- **Engine**: `features/avwap.py` (pivot-low, earnings, max-volume, YTD anchors; point-in-time pivot confirmation) and
  `avwap_pullback.py` proposed.

### 6.9 Momentum burst (Stockbee) — [docs/methods/09-stockbee-momentum-burst.md](methods/09-stockbee-momentum-burst.md)
- **What**: buy the first range-expansion day (up 4%+ on volume above yesterday's, close near the high) out of a quiet
  3-20 day base in a young trend; out in 3-5 days.
- **Rules**: scan `c/c1 >= 1.04 and v > v1 and v > 100000`; filters (prior day narrow or red, not up 2-3 days, orderly
  base, no 4% breakdowns, linear prior leg) remove 95%+ of hits. Stop low of the entry day; breakeven at +4-5%; sell
  half at +8% same/next day; at least half at the day-3 close. Risk 0.25-1%. Only when the Market Monitor is green.
- **Evidence (D)**: Bonde 100k to 789k over 5 years (2014), unaudited; Alma (2025) raw trigger: 46.8% 5-day win,
  +0.88% gross; academic: 1-2 week reversal is the default, continuation only for high-volume/high-turnover stocks.
- **2026 fit**: poor by its own rules (Bonde, Jul 20 2026); Russell 2000 -7.52% in Q3 2026. Turn on only after a thrust.
- **Engine**: `momentum_burst` (disabled). Fix the prior-day filter bug (section 7); add NR7, base tightness, a
  no-4%-breakdown lookback, breadth gate, scale-out exits.

### 6.10 Parabolic short and long reversal — [docs/methods/10-parabolic-short-and-long-reversal.md](methods/10-parabolic-short-and-long-reversal.md)
- **What**: short a stock gone vertical (3-5+ green days; +50-100% large cap, +300-1000% small cap) on day 3-4 after an
  intraday failure; the mirror buys a 50-60%+ crash for a bounce.
- **Rules**: ORL break, first red 5-min candle or failed VWAP retest; stop high of day; cover into the 10-, then
  20-day MA; risk 0.5% or less, 1% max. Long: low-of-day stop, crash-driven only.
- **Evidence (C-)**: Stonks Capital 1,869 trades, CAGR 27.7%, max DD -20.9% (costs/borrow withheld); 67% of 50%+
  small-cap gappers close below the open; MAX effect over 1%/month; edge concentrated in high-borrow-fee stocks.
- **2026 fit**: plenty of candidates (2025 memes, crypto-treasury blow-offs, 2026 semis), fewer small-cap
  ramp-and-dumps; execution (borrow, halts, SSR, squeezes) is the problem.
- **Engine**: long-only `PanelStrategy`; keep as monitor alerts (`monitor/smallcap.py` first-red-day, VWAP-lost);
  `rsi2_meanrev` is the nearest long-reversal module.

### 6.11 RSI-2 / Connors mean reversion — [docs/methods/11-rsi2-connors-mean-reversion.md](methods/11-rsi2-connors-mean-reversion.md)
- **What**: above the 200-day, buy at the close after a 2-7 day pullback drives RSI(2) below 5-10 (or a 7-day closing
  low, or 2-day cumulative RSI(2) below 35); sell the first bounce.
- **Rules**: exit on a close above the 5-day SMA or RSI(2) above 65-70; no price stop in the original; hold 2-6 days;
  size by fixed equity fraction with a cap on concurrent positions.
- **Evidence (B-)**: in-sample Double 7s 80.4% winners; out of sample (Backtrex, Oct 2016-Oct 2026) SPX CAGR 1.7% vs
  13.5% buy-and-hold at low exposure, 71% winners, avg win 1.22% vs avg loss 2.10% (about +0.27%/trade; NDX +0.43%);
  Nagel 2012: reversal pays most when VIX is high.
- **2026 fit**: still positive but thin; a low-correlation diversifier to the breakout strategies.
- **Engine**: `rsi2_meanrev` (enabled) deviates: exits on `sma_10` (add `sma_5`), fills next open (use a
  limit-below-close or MOC), adds a 2x ATR stop and a 5-day time stop. Missing ADX, ConnorsRSI, 7-day low, VIX.

### 6.12 Kell Cycle of Price Action — [docs/methods/12-kell-cycle-of-price-action.md](methods/12-kell-cycle-of-price-action.md)
- **What**: trade growth leaders through a repeating cycle around the daily 10/20 EMAs: buy the Wedge Pop, the EMA
  Crossback and Base n' Break; trail the EMAs; sell extensions; exit on the Wedge Drop. The same cycle on QQQ sets
  exposure.
- **Rules**: buy "in the pocket" (never 3-4%+ extended); stop at the day's low or the EMA being bought (1-2%); pieces of
  15% (+15% on follow-through); correction mode = QQQ below its 20 EMA, 1-2 names, exposure capped at 30%.
- **Evidence (D)**: USIC 2020 +941.1% (one account, one year, margin); no independent test; a plain 20-EMA rule on SPY
  made 3.06% CAGR vs 7.87% buy-and-hold.
- **2026 fit**: V-shaped turns (Apr 2025, early 2026, May 2026) suit it; his 24 Mar 2025 index wedge-pop preceded the
  tariff crash, showing the cost of early signals.
- **Engine**: add `ema_10/ema_20`, weekly EMA, extension in % or ATR, phase state machine; QQQ > 20 EMA gate;
  not-extended rule (`ext_10 <= 3%`) usable now on `pullback_trend`.

### 6.13 Power Earnings Gap / Buyable Gap-Up — [docs/methods/13-power-earnings-gap.md](methods/13-power-earnings-gap.md)
- **What**: buy a hard earnings gap-up (10%+ or 0.75x ATR(40)+ on 2-3x+ volume, strong close) at the gap-day ORH or,
  better, after a 2-5 day tight hold above the gap-day low.
- **Rules**: stop at the gap-day low (cap 1-1.5 ADR); partials after 3-5 days or +8-20%; trail the 10/20/50-day;
  Morales violation exit; 0.5% risk and a 30% sector cap in earnings season.
- **Evidence (C)**: price-reaction drift 6.3%/yr (1987-2004) and jump drift 15.3%/yr (1971-2009), but costs eat 70-100%
  in illiquid names and large-cap PEAD is gone since about 2006; Bulkowski BGU test (557 stocks, 2001-2010): +1.2-3.1%
  average, 28-32% winners, 29-43 day holds, not recommended.
- **2026 fit**: muted large-cap reactions (FactSet Q2 2026 +0.4% vs +1.0% five-year average); range tape favours
  consolidation and pullback-to-gap entries. Scan, alert and paper-trade only.
- **Engine**: add `atr_40`, `true_gap`, prior-bar `avg_vol_50d`, point-in-time earnings dates from EDGAR 8-K Item 2.02;
  `earnings_gap.py` proposed.

### 6.14 Insider Buy Superstocks (Stine) — [docs/methods/14-insider-buy-superstocks-stine.md](methods/14-insider-buy-superstocks-stine.md)
- **What**: a sub-$15, sub-10M-float, PE-run-rate 10-or-less earnings winner bought on a huge weekly volume thrust out of
  a long base above its 30-week MA, ideally with insider buying; add at the 10-week "magic line".
- **Rules**: weekly volume up 500-5,000%, about 45-degree angle; sell 7-10 weeks after a thrust, about 9 months into
  the advance, on parabolic/largest-range weeks, offerings, or a weekly close below the magic line.
- **Evidence (D)**: $45,721 to $6,845,342 (Sep 2003-Jan 2006), documented but not CPA-attested, no results after 2006;
  components (opportunistic insider long-short 82 bp/month VW alpha, buys +90 bp/month vs all insider trades; MA timing in volatile stocks; PEAD) supported; low-priced lottery
  stocks underperform on average.
- **2026 fit**: small-cap value rotation in mid-2026 fits the PE screen, but Russell 2000 EPS estimates were cut 9% YTD
  and the sub-$15 low-float pool is full of diluters.
- **Engine**: weekly features (`wk_sma_10/30`, `wk_vol_ratio`), float (`float_data.py`), Form 4 (`edgar.py`,
  `insider_cluster`), EDGAR XBRL EPS; `superstock_weekly.py` proposed, low priority. Borrow the sell rules.

---

## 7. Next strategies to implement in swing-engine

All new modules go through `.claude/skills/add-strategy`, register `enabled: false`, get every threshold as a
versioned param, and stay disabled until `docs/gates.md` is met (walk-forward with 10/20 bps per side plus SEC/TAF,
deflated Sharpe with the full trial count in `research/trials.py`, 3+ months and 100+ closed paper trades). Variants
of one idea are logged as one family.

### 7a. P0: gates, features and fixes (they improve every strategy)
1. **`features/breadth.py` (market breadth gate).** One row per session from the point-in-time universe, broadcast as
   `market_*`: `pct_above_50`, `pct_above_200`, `ad_ratio_10d_ema`, `zbt_state`, `up4_count`/`down4_count` (from
   `burst_4pct` and its mirror), `dcr_10d` (10-day up4/down4), `q25_ratio`, `nh_pct`. Params in `strategies/_base.py`
   next to `min_market_trend_state`: breakout family (`momentum_burst`, `breakout_52w`, `sr_breakout`, new breakout
   modules) requires `dcr_10d >= 2` or `pct_above_200` above its on-threshold; pullback family uses Hill-style
   hysteresis (on above 60, off below 40, in engine-calibrated percentiles); `rsi2_meanrev` stays ungated. Judge by
   drawdown reduction, not CAGR.
2. **`features/market_school.py` (IBD M state machine).** Rally Day 1 = first up close after a low (reset on undercut);
   FTD = Day 4+ with the index up at least 1.25% on higher volume than the prior day; DD = index -0.2% or worse on
   higher volume, expiring after 25 sessions or a 6% rally; 5-6 DDs in 25 sessions = under pressure. Output a 0-100
   exposure dial. Needs real index or ETF volume (local duckdb data is synthetic).
3. **Shared features**: `ema_10`, `ema_20`, `ema_50`, `sma_5`, `sma_150`, `adx_14` (+DI/-DI; `wilder_smooth` exists),
   `adr_pct_20` (mean(H/L over 20) - 1), `rank_ret_63d`/`rank_ret_126d` cross-sectional percentiles, `atr_40`,
   `avg_vol_50d_prev` (prior-bar), `higher_lows_n`, `sma_200_slope_21`, `dist_52w_low`, `days_since_earnings` (EDGAR
   8-K Item 2.02 acceptance time).
4. **Backtester hooks**: a partial-exit / scale-out hook (every school takes 1/3-1/2 off; the engine is all-or-nothing
   today) and a limit-below-close / MOC entry mode for mean reversion.
5. **Fixes to existing strategies.**
   - `momentum_burst.py` line 63 rejects `abs(prior_ret_1d) > 2%`, so it throws out the prior red days Stockbee
     prefers ("prior day narrow-range or down"). Reject only prior up-days above the threshold, and test a
     narrow-range (NR7) alternative.
   - `rsi2_meanrev`: add `sma_5` and make `exit_ma: sma_5` the Connors-faithful variant; test `target=None` with a
     close-based exit; report with and without the 2x ATR stop and 5-day time stop.
   - `pullback_trend`: implement `should_exit` (close < `ema_50`, or 2 closes < `ema_20`), add an RS-percentile gate and
     an earnings-window exclusion; add Kell's not-extended rule (entry no more than about 3% above the 10/20 EMA).

### 7b. P1: new strategy modules (in this order)
| # | Module | Key rules (one line) | Why this order |
|---|---|---|---|
| 1 | `pullback_holy_grail` / `pullback_ema_zone` (family of `pullback_trend`) | Holy Grail: `adx_14 > 30` and rising, low touches `ema_20`, buy over the touch-bar high, stop at the touch-bar low, target the prior swing high. EMA zone: low in the `ema_20`-`ema_50` band after 2 prior respected tests, 2x ATR stop, exit on a close below `ema_50`, no target | Best 2026 fit and evidence among entries; reuses existing code |
| 2 | `base_breakout` (cup with handle / flat base) | Prior advance 30%+, cup at least 7 weeks and 12-33% deep, handle in the upper half and no more than 12% deep on light volume (or flat base 5+ weeks, 15% or less deep); close > pivot on `volume >= 1.4x avg_vol_50d_prev`; skip if more than 5% above the pivot; stop = max(handle low, entry - 7-8%); exit at +20-25% or 8-week hold if +20% within 3 weeks; M gate on | Best gross PF of the breakout detectors in the only multi-year panel (1.57) |
| 3 | `earnings_gap` (PEG/BGU, consolidation entry) | Earnings day (8-K 2.02) with gap >= 10% or >= 0.75x `atr_40`, volume >= 2x prior 50-day average, `close_pos >= 0.7`; enter on the break of a 2-30 bar tight consolidation that holds above the gap-day low; stop gap-day low capped at 1.5 ADR; partial after 3-5 bars, trail `sma_20`; 30% sector cap | Event-anchored, codeable from bars plus EDGAR dates; consolidation entry fits the 2026 range tape |
| 4 | `qullamaggie_flag` | `rank_ret_63d >= 98th pct`, prior move >= 30% within 63 bars, `adr_pct_20 >= 5%`, 10-40 bar flag with higher lows near rising `sma_10/sma_20`; close > prior N-bar high on `rvol_day >= 1.5`, no more than 1 ADR above the pivot; stop entry-bar low capped at 1 ADR; 1/3 off at bar 4, trail on a close < `sma_20` | Most-taught breakout; needs breadth gate and scale-out hook first |
| 5 | `episodic_pivot` (delayed / day-2) | `gap_pct >= 10%`, `rvol_day >= 3`, `close_pos >= 0.5`, earnings required, prior-row `ret_126d <= 30%` (neglect), no EP in the prior 252 bars; enter the day-2 open or the first close above the EP-day high after a 3-10 bar flag above the EP low; stop EP-day low, skip if more than 1.5 ADR; trail `sma_10/20` after 3 bars | Daily fills make this the delayed EP; catalyst quality stays a Claude enum |
| 6 | `avwap_pullback` (or AVWAP as a filter on #1) | Above a rising AVWAP from a confirmed pivot low / earnings gap / YTD anchor (tested 2 times or fewer); 2-6 bar pullback on volume below average; trigger close > `sma_5` and > prior high; stop pullback low, max 3%; first third at R2 or swing high; 30-bar time stop | Cheap entry-quality filter on the pullback family |

**Later, low priority**: `vcp_sepa` (the coded trigger showed no edge; test the Template as a gate first),
`superstock_weekly` and a Weinstein Stage-2 weekly module (share weekly features), a Kell QQQ cycle overlay. **Do
not build** a parabolic-short strategy (long-only engine; borrow, SSR and squeeze risk) beyond monitor alerts.

---

## 8. Gaps and open items

1. **No public, cost-inclusive walk-forward exists** for most taught setups: filtered momentum bursts, the Holy Grail
   on single stocks, the exact PEG rules, EPs (Torres' numbers are paywalled), Kell, Shannon's AVWAP pullback, Stine.
   The engine's own backtests are the first real test; until then every row in section 1 is a hypothesis.
2. **Intraday dependence.** ORH entries (EP, flags, PEG), Shannon's 65/15/5-minute triggers and Stockbee's
   first-30-minute entries are not reproducible on daily bars; the backtester fills at the next open. Intraday bars
   and an execution window (09:31-10:30 ET) are needed to test the methods as taught.
3. **Point-in-time fundamentals and events are not ingested**: earnings dates (EDGAR 8-K 2.02 is the cheapest source),
   EPS/sales growth and surprise, float, short interest (needs a FINRA feed), analyst revisions.
4. **Breadth history is short.** Massive's free tier gives 2 years; thrust tables need decades or an external NYSE A/D
   series; thresholds (0.40/0.615, 300-count bands) do not transfer to the engine's universe and must be calibrated.
5. **Backtester gaps**: no partial exits, no limit-below-close entry mode for mean reversion, no borrow model for
   shorts.
6. **Primary-source gaps**: no 2025-26 primary statements found from Kullamagi, Zanger, Stewie or Morales/Kacher;
   Minervini's 2025-26 remarks are secondary; X, Reddit and many trader sites blocked fetches; investors.com bodies are
   paywalled, so every IBD number is secondary.
7. **Unverified figures still in circulation**: JPM/Vanda 2025 dip-buying flows; the 26.5% FTD whipsaw rate; Landry's
   2-for-1 rule wording; Stine's "Canary" indicator; the August 2026 Russell 2000 record; the Sept 2026 AI-pacing
   chip drop.
8. **Structural breaks to re-test after**: 23x5 overnight trading from 2026-12-06 (gap statistics, earnings-reaction
   playbooks), PDT repeal phase-in to 2027-10-20, 0DTE share growth and Mon/Wed single-stock expiries.
9. **Disagreements the data cannot settle yet**: breakouts vs pullbacks by regime, stop styles for mean reversion,
   first vs third pullback, fixed targets vs trails. Each is a logged experiment, not a choice to make by argument.

---

## Appendix: sources

All URLs from the inputs are kept below, generated from the files on 2026-10-06. Deep-dive URLs are also listed in
each file's own Sources section.

### A. Research sweeps: things to recognize, modern context, warnings

<details><summary>books_blogs.json / things_to_recognize (30 URLs)</summary>

- https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html
- https://stockbee.blogspot.com/2016/07/profiting-from-momentum-bursts.html
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups
- https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini
- https://www.finermarketpoints.com/post/trade-like-stock-market-wizard-vcp-chapter
- https://stageanalysis.net/blog/4372/stage-analysis-breakout-quality-checklist
- https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker
- https://discussion.fool.com/t/ibd-8-week-hold-rule/112549
- https://discussion.fool.com/t/mark-minervini-market-wisdom/108510
- https://www.thepatternsite.com/studystudy.html
- https://thepatternsite.com/cup.html
- https://thepatternsite.com/htf.html
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329
- https://www.luxalgo.com/library/concept/turtle-soup/
- https://www.antoinebuteau.com/lessons-from-linda-bradford-raschke/
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://www.luxalgo.com/library/concept/vwap-pinch/
- https://www.trade-ideas.com/features/ti-avwap/
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://threadreaderapp.com/thread/1028428610275819520.html
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry
- https://usethinkscript.com/threads/weekend-trend-trader-by-nick-radge-strategy-for-thinkorswim.669/
- https://nexusfi.com/a/indicators/td-sequential-demark-indicators
- https://adamhgrimes.com/volatility-shocks-and-what-follows/
- https://alvarezquanttrading.com/blog/the-30-selloff-signal-what-history-tells-us-about-market-recoveries/
- https://qullamaggie.com/nasdaq-comparison-late-90s-vs-today/
- https://www.financialwisdomtv.com/post/the-episodic-pivot-strategy-qullamaggie-s-high-momentum-setup-explained

</details>

<details><summary>books_blogs.json / modern_context (30 URLs)</summary>

- https://www.empower.com/node/12876
- https://alvarezquanttrading.com/blog/the-30-selloff-signal-what-history-tells-us-about-market-recoveries/
- https://moneylifeshow.libsyn.com/marketlifes-grimes-technicals-do-not-look-right-for-the-rally-to-roll-on
- https://theswingtrader.substack.com/p/your-weekly-guide-to-swing-trading-b5e
- https://trendspider.com/blog/market-update-into-june-2nd-2025/
- https://tikamalma.substack.com/p/4-momentum-burst-detailed-research
- https://www.webull.com/news/13249512026235904
- https://money.tmx.com/content-hub/value-momentum-content-hub/why-value-outpaced-momentum-2025-top-factor/
- https://am.jpmorgan.com/nl/en/asset-management/institutional/insights/portfolio-insights/asset-class-views/factor/
- https://www.itiger.com/news/1193183844
- https://www.business-standard.com/amp/world-news/nasdaq-joins-exchanges-seeking-to-offer-24-hour-equities-trading-125030701173_1.html
- https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/
- https://www.bolsamania.com/nota-de-prensa/mercados/j-law-sets-two-year-record-with-1499-return-in-us-investing-championship--21854364.html
- https://www.businesswire.com/news/home/20260202090143/en/
- https://www.stageanalysis.net/blog/1373123/stage-analysis-weekend-video-15-march-2026
- https://www.sofi.com/learn/content/pattern-day-trading-rules/
- https://reddit.sentinel-team.org/posts/1sevbzc/snapshots/2026-04-09T15%3A01%3A31.80847Z
- https://alvarezquanttrading.com/blog/bad-month-for-your-strategy-should-you-change-it/
- https://alvarezquanttrading.com/blog/the-100-club-2000-tech-vs-2026-ai/
- https://tradersunion.com/news/market-voices/show/2549155-bull-market-rotation-2026/
- https://www.mql5.com/en/articles/22746
- https://continuumeconomics.com/a/0a0d0277/ai-equities-correctionconsolidation
- https://alvarezquanttrading.com/blog/the-power-of-strategy-diversification/
- https://seekingalpha.com/article/4917855-sp500-bubble-burst-is-in-progress
- https://stockbee.blogspot.com/
- https://adamhgrimes.com/
- https://alphatrends.net/
- https://www.davelandry.com/
- https://gummysearch.com/r/swingtrading
- https://qullamaggie.com/

</details>

<details><summary>books_blogs.json / warnings (19 URLs)</summary>

- https://www.valuethemarkets.com/analysis/what-is-a-furu
- https://reddit.sentinel-team.org/posts/1q13q10/snapshots/2026-01-09T15%3A51%3A08.367904Z
- https://qullamaggie.com/
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream-092
- https://stockbee.blogspot.com/2016/07/profiting-from-momentum-bursts.html
- https://tikamalma.substack.com/p/4-momentum-burst-detailed-research
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://www.luxalgo.com/library/concept/turtle-soup/
- https://alvarezquanttrading.com/blog/bad-month-for-your-strategy-should-you-change-it/
- https://www.thepatternsite.com/BestPatterns.html
- https://usethinkscript.com/threads/weekend-trend-trader-by-nick-radge-strategy-for-thinkorswim.669/
- https://www.financialwisdomtv.com/post/oliver-kell-us-investing-champion
- https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing
- https://am.jpmorgan.com/nl/en/asset-management/institutional/insights/portfolio-insights/asset-class-views/factor/
- https://www.sofi.com/learn/content/pattern-day-trading-rules/
- https://www.business-standard.com/amp/world-news/nasdaq-joins-exchanges-seeking-to-offer-24-hour-equities-trading-125030701173_1.html
- https://www.financialwisdomtv.com/post/insider-buy-superstocks-by-jesse-stine
- https://adamhgrimes.com/volatility-shocks-and-what-follows/
- https://www.antoinebuteau.com/lessons-from-linda-bradford-raschke/

</details>

<details><summary>events.json / modern_context (122 URLs)</summary>

- https://www.etftrends.com/etf-strategist-content-hub/notes-desk-signal-through-noise/
- https://macroption.com/vix-all-time-high
- https://www.federalreserve.gov/monetarypolicy/openmarket.htm
- https://cetera.com/hawkish-rate-cut-sends-markets-lower
- https://www.mufgresearch.com/rates/december-2024-cb-views-fomc-recap-18-december-2024
- https://www.bloomberg.com/news/articles/2025-01-27/asml-sinks-as-china-ai-startup-triggers-panic-in-tech-stocks
- https://www.betashares.com.au/insights/liberation-day-upended-markets/
- https://www.nasdaq.com/articles/april-2025-review-and-outlook
- https://wolfstreet.com/2025/12/29/ipo-bloodletting-after-the-pop-in-2025-venture-global-coreweave-figma-klarna-bullish-circle-internet-naven-firefly-fermi/
- https://quartr.com/insights/company-research/companies-that-had-their-ipo-in-2025-the-ipo-market-recovers
- https://finance.yahoo.com/news/opendoor-kohls-resume-rally-meme-160314410.html
- https://www.renaissancecapital.com/review/2025USReview_Press.pdf
- https://www.bbae.com/blog/2025-ipo-market-review-and-2026-expectations/
- https://en.wikipedia.org/wiki/2025_United_States_federal_government_shutdown
- https://finance.yahoo.com/markets/crypto/articles/bitcoin-peaked-126-080-october-091605452.html
- https://www.theblock.co/post/374266/crypto-liquidations-near-10-billion-in-historic-drawdown-following-trumps-100-tariffs-on-china
- https://thebusinessjournal.com/stocks-slump-as-big-tech-sinks-and-a-strong-may-jobs-report-boosts-odds-for-higher-interest-rates/
- https://smallcapinvestor.beehiiv.com/p/the-resurgence-of-meme-stock-mania-from-gamestop-to-beyond-meat-and-who-s-next
- https://markets.financialcontent.com/stocks/article/marketminute-2026-3-3-fear-returns-to-wall-street-vix-soars-to-2643-as-us-iran-conflict-ignites-geopolitical-firestorm
- https://www.federalreserve.gov/monetarypolicy/fomcminutes20251029.htm
- https://www.morningstar.com/markets/whats-next-fed-2026
- https://convextrade.com/metrics/vix/history/2025
- https://fortune.com/2026/02/23/what-is-retail-trading-dumb-money-stock-markets-5-4-trillion-activity-2025/
- https://sherwood.news/markets/retail-share-of-us-trading-volume-passes-20-in-2025-analyst-says/
- https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025
- https://spotgamma.com/record-0dte-volume-reshapes-the-sp-500/
- https://www.engineeringnews.co.za/article/gold-blasts-past-5-000-to-record-high-on-safe-haven-rush-2026-01-26
- https://www.yellowcakeanalytics.com/learn/smr-stocks
- https://www.fool.com/investing/2026/02/11/better-utility-stock-constellation-energy-v-vistra/
- https://money.usnews.com/investing/articles/best-quantum-computing-stocks-to-buy
- https://www.fastcompany.com/91465778/quantum-computing-stocks-rise-and-fall-d-wave-rigetti-ionq
- https://www.cnbc.com/2025/12/16/nasdaq-moves-to-near-24-hour-trading-some-say-thats-a-bad-idea.html
- https://gfmag.com/technology/nyse-plans-tokenized-24-7-trading/
- https://corpgov.law.harvard.edu/?p=183979
- https://www.nst.com.my/amp/business/corporate/2026/01/1366849/gold-blasts-past-us5500-record-high-safe-haven-demand
- https://www.vtmarkets.com/en-mena/live-updates/following-a-2026-peak-spx-declines-methodically-almost-meeting-the-previously-forecast-6521-target/
- https://wealthvieu.com/banking/interest-rates/federal-funds-rate/
- https://www.cnbc.com/2026/02/04/stock-market-today-live-updates.html
- https://enterpriseam.com/uae/2026/02/05/software-selloff-deepens-as-ai-worries-rattle-markets/
- https://gvwire.com/2026/02/12/wall-street-sinks-as-tech-rout-deepens-on-ai-angst/
- https://www.itiger.com/news/2592917834
- https://globaltradealert.org/blog/from-ieepa-to-section-122
- https://www.bdo.com/insights/tax/supreme-court-invalidates-ieepa-tariffs-administration-replaces-with-new-surcharge-what-importers
- https://www.cnn.com/2026/03/01/business/oil-prices-us-attack-iran-vis
- https://www.fortune.com/2026/03/05/dow-drops-1000-markets-react-oil-spikes-iran-war-middle-east
- https://www.cnbc.com/2026/04/21/oil-price-iran-war-middle-east.html
- https://www.vtmarkets.com/en-mena/live-updates/march-looks-set-for-a-7-7-sp-500-drop-souring-april-sentiment-amid-troubling-conditions/
- https://fortune.com/2026/04/08/markets-sp-trump-truce-ceasefire-iran-war-rally-strait-of-hormuz
- https://www.hl.co.uk/shares/stock-market-news/market-reports/us-open-stocks-rally-following-two-week-iran-ceasefire-announcement
- https://www.aol.com/articles/meme-stocks-mega-ipos-wallstreetbets-094001244.html
- https://www.finra.org/rules-guidance/notices/26-10
- https://www.sec.gov/files/rules/sro/finra/2026/34-104572.pdf
- https://www.acaglobal.com/industry-insights/finra-ends-the-pattern-day-trader-rule/
- https://www.cnbc.com/2026/04/27/global-military-spending-record-2025-europe-asia-ukraine-sipri.html
- https://www.janushenderson.com/en-us/investor/article/european-defense-stocks-the-magnitude-of-europes-rearmament-remains-underappreciated/
- https://kelo.com/2026/04/28/oracle-coreweave-shares-drop-after-report-flags-openai-growth-worries/
- https://www.bankingdive.com/news/anthropic-rolls-out-financial-ai-tools-target-large-clients-claude/753249/
- https://vpsranking.com/news/ai/ai-2026-05-15-openai-chatgpt-personal-finance/
- https://www.cnbc.com/2026/05/13/kevin-warsh-wins-senate-confirmation-as-the-next-federal-reserve-chair.html
- https://www.aljazeera.com/economy/2026/5/22/kevin-warsh-sworn-in-as-new-us-fed-chair
- https://www.skadden.com/insights/publications/2026/05/us-trade-court-strikes-down-section-122-tariffs
- https://www.fool.com/investing/2026/07/05/the-retail-trading-boom-is-back-charles-schwab-is/
- https://www.bloomberg.com/news/articles/2026-05-28/retail-revival-adds-fuel-to-us-stocks-jpmorgan-strategists-say
- https://letsdatascience.com/news/robinhood-launches-ai-agents-for-trading-and-spending-6615397c
- https://www.stockbrokers.com/guides/ai-agent-brokers
- https://ibinterviewquestions.com/guides/equity-capital-markets/the-2026-mega-ipo-pipeline-spacex-openai-anthropic-kraken
- https://builtin.com/articles/top-tech-ipos-2026
- https://insurancenewsnet.com/oarticle/how-major-us-stock-indexes-fared-friday-6-5-2026
- https://www.cnn.com/2026/06/05/markets/stock-market-sell-off-fed
- https://walnutinvest.com/resources/mcp-connectors-for-brokerages-compared
- https://www.iposcoop.com/?p=38639
- https://en.wikipedia.org/wiki/Initial_public_offering_of_SpaceX
- https://www.home.saxo/content/articles/options/options-brief---iran-day-two-vol-surges---11-june-2026-11062026
- https://finance.yahoo.com/healthcare/articles/biotech-etfs-put-strong-show-160000067.html
- https://www.goldmansachs.com/insights/articles/biotech-stocks-are-projected-to-extend-rally-amid-innovation
- https://finance.yahoo.com/markets/stocks/articles/semiconductor-stocks-see-rare-surge-070916646.html
- https://cnttrading.substack.com/p/daily-market-2026-06-24
- https://www.top1markets.com/news/meme-stocks-2026-gme-amc-reddit-wallstreetbets
- https://www.wilmerhale.com/en/insights/client-alerts/20260929-23x5-trading-comes-to-us-exchanges-what-firms-should-know-before-launch
- https://www.dtcc.com/dtcctransformation/24x5
- https://proactiveadvisormagazine.com/sp-500-update-market-breadth-improves-in-the-first-half-of-2026/
- https://www.spglobal.com/market-intelligence/en/news-insights/articles/2026/2/market-dispersion-widens-as-mega-caps-stumble-equal-weight-index-takes-lead-99108147
- https://www.citadelsecurities.com/news-and-insights/global-market-intelligence/1h-2026-market-structure-flows/
- https://www.bloomberg.com/news/articles/2026-07-06/morgan-stanley-s-wilson-sees-rotation-from-chips-to-hyperscalers
- https://www.pewresearch.org/short-reads/2026/09/23/prediction-markets-trading-volume-doubled-between-may-and-july-largely-driven-by-sports/
- https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/
- https://www.cnbc.com/2026/07/29/chip-selloff-sk-hynix-samsung-softbank.html
- https://www.tradingview.com/news/leverage_shares:c8d519c05094b:0-the-2026-semiconductor-selloff-creates-an-opportunity/
- https://www.fool.com/investing/2026/07/21/memory-stocks-spark-a-market-rebound/
- https://www.clearygottlieb.com/news-and-insights/publication-listing/trump-administration-imposes-new-section-301-tariffs-on-60-trading-partners
- https://uhy-us.com/insights/news/2026/july/tariff-reset-section-122-expires-as-section-301-duties-expand
- https://www.cnbc.com/2026/05/28/oil-prices-iran-war-us-trump-strait-hormuz-energy-inflation-investors.html
- https://en.wikipedia.org/wiki/2026_Iran_war_fuel_crisis
- https://www.nbcnews.com/world/asia/unitree-china-robot-maker-stock-market-ai-humanoids-tech-trump-rcna593278
- https://247wallst.com/investing/2026/07/02/the-first-major-robotics-ipo-is-here-5-robotics-stocks-that-could-run-in-the-second-half-of-2026/
- https://www.kucoin.com/blog/sec-tokenized-stock-exemption-coinbase-robinhood-circle
- https://247wallst.com/investing/2026/09/08/nuscale-power-spikes-13-oklo-climbs-7-is-the-nuclear-selloff-finally-exhausted/
- https://macroplane.com/blog/oklo-stock
- https://www.morningstar.com/news/dow-jones/202610018747/sp-500-rises-019-to-766645-data-talk
- https://www.cnbc.com/2026/08/17/stock-market-volatility-vix-wall-street.html
- https://investors.robinhood.com/static-files/15576d76-2d02-4aea-a40d-48e694c04a4b
- https://blog.firstrade.com/blog/2026/retail-investors-are-trading-at-record-levels-in-2026
- https://www.investmentnews.com/equities/round-the-clock-trading-is-coming-but-retail-investors-are-already-there/267554
- https://www.xtb.com/en/market-analysis/nvidia-shares-react-to-solid-earnings-report-and-stonger-guidance-what-s-next-for-the-ai-giant
- https://finance.yahoo.com/sectors/technology/articles/hyperscalers-hit-700-billion-2026-111243744.html
- https://www.cnbc.com/2026/08/27/stock-market-today-live-updates.html
- https://ffis.org/budget-brief/house-and-senate-move-to-minimize-fy-2027-government-shutdown-risk/
- https://historyofmarket.com/sp500/sp500-breadth/
- https://articles.stockcharts.com/article/mindfulinvestor-2026-08-weakening-market-breadth-could-signal-trouble-ahead/
- https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm
- https://www.skadden.com/insights/publications/2026/09/sec-innovation-exemption-establishes
- https://www.jonesday.com/de/insights/2026/09/the-secs-new-innovation-exemption-fiveyear-relief-for-trading-on-tokenized-securities-venues
- https://www.benzinga.com/crypto/cryptocurrency/26/09/61860709/sec-gives-tokenized-stocks-a-five-year-onchain-runway-robinhood-ceo-vlad-tenev-says-its-a-good-day-for-us-innovation
- https://financefeeds.com/the-race-to-list-tokenized-stocks-in-america/
- https://invezz.com/nz/news/2026/09/29/coreweave-and-nebius-stocks-in-a-bear-market-as-ai-bubble-risk-persists/
- https://intellectia.ai/news/stock/oracle-and-coreweave-face-ai-bubble-risks-with-15-billion-debt
- https://www.citadelsecurities.com/news-and-insights/global-market-intelligence/2h-september-getting-closer/
- https://www.sec.gov/Archives/edgar/data/0001050446/000119312526363557/d431748dfwp.htm
- https://fortune.com/article/price-of-bitcoin-10-06-2026/
- https://www.sofi.com/learn/content/bitcoin-price-history/
- https://fedratecalc.com/fomc-meeting-schedule/
- https://realinvestmentadvice.com/resources/blog/market-correction-risk-why-summer-2026-looks-risky/

</details>

<details><summary>evidence.json / things_to_recognize (22 URLs)</summary>

- https://www.nber.org/papers/w20439
- https://indexes.morningstar.com/insights/markets-review/bltd9a242a7280e6745/morningstar-factor-monitor-q1-2025
- https://www.nber.org/papers/w20721
- https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html
- https://cxoadvisory.com/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks
- https://www.cxoadvisory.com/technical-trading/market-timing-with-moving-averages-over-the-very-long-run
- https://thepatternsite.com/FailureRates.html
- https://thepatternsite.com/BestPatterns.html
- https://www.mql5.com/en/blogs/post/776235
- https://www.cxoadvisory.com/technical-trading/machine-assisted-stock-price-pattern-analysis/
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://ideas.repec.org/a/now/jnlcfr/104.00000122.html
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://arxiv.org/abs/2602.06198
- https://www.nber.org/papers/w35041
- https://harbourfrontquant.substack.com/p/do-calendar-anomalies-still-work
- https://www.etftrends.com/etf-strategist-channel/turn-month-effect/
- https://www.nerdwallet.com/article/investing/santa-claus-rally
- https://www.cxoadvisory.com/technical-trading/classic-papers-returns-from-pattern-based-technical-analysis/
- https://www.evidenceinvestor.com/why-most-robinhood-traders-earn-lousy-returns/
- https://www.toptradersunplugged.com/author/naomi/
- https://thefullfx.com/ctas-end-2025-on-a-positive-note/

</details>

<details><summary>evidence.json / modern_context (8 URLs)</summary>

- https://www.capitalspectator.com/?p=24078
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://www.nber.org/papers/w35041
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://www.mql5.com/en/blogs/post/776235
- https://arxiv.org/abs/2602.06198
- https://thepatternsite.com/id84.html
- https://thepatternsite.com/BestPatterns.html

</details>

<details><summary>fintwit.json / things_to_recognize (19 URLs)</summary>

- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist
- https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://tradingresourcehub.substack.com/p/qullamaggie-stream-notes-1-june-2023
- https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-trend-template-marketsmith
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic
- https://www.tradingview.com/script/GOkJ7o5J-Wedge-Pop-Drop-QuantVue
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://www.financialwisdomtv.com/post/maximum-trading-gains-using-price-time-volume
- https://cmtassociation.org/?p=2451
- https://seekingalpha.com/instablog/195752-joshua-hayes/73173-a-quick-reminder-about-follow-through-days
- https://investrade.com/market-review-september-28-2026/
- https://www.janushenderson.com/corporate/article/market-moves-themes-that-mattered-september-2026/
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-46-50-review
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://www.tradezella.com/blog/swing-trading-strategies

</details>

<details><summary>fintwit.json / modern_context (26 URLs)</summary>

- https://en.wikipedia.org/wiki/2025_stock_market_crash
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://threadreaderapp.com/scrolly/1979196802021658884
- https://blockchain.news/flashnews/margin%20debt
- https://fundstrat.com/?p=221302
- https://fundstratdirect.com/event/mark-newtons-2026-market-outlook
- https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist
- https://blockchain.news/flashnews/0dte-options-dominate-nasdaq-100-and-s-p-500-trading-volumes
- https://markets.financialcontent.com/workboat/article/marketminute-2026-3-27-wall-streets-dark-friday-nasdaq-sinks-into-correction-as-five-week-rout-deepens
- https://insights.dsij.in/dsijarticledetail/march-2026-when-everything-fell-a-market-defined-by-broad-based-selling-id010-56215
- https://serrarigroup.com/the-proven-signs-the-fed-just-broke-the-bull-market/
- https://www.tradezella.com/blog/swing-trading-strategies
- https://invezz.com/en-ae/news/2026/04/07/fundstrat-strategist-says-us-stocks-may-have-bottomed/
- https://tradersunion.com/news/market-voices/show/2549155-bull-market-rotation-2026/
- https://www.minervini.com/
- https://www.fortune.com/2025/12/03/is-ai-a-bubble-bofa-says-air-pocket-in-2026-data-center-debt
- https://unionspace.co.th/doing-business-living-bangkok/?p=2047
- https://blockchain.news/flashnews/0dte-options-retail-volume-share-hits-record-48
- https://www.citadelsecurities.com/news-and-insights/retail-detail/the-toolkit-expands/
- https://www.moneymagpie.com/investment-articles/whats-going-on-with-ai-stocks-in-september-2026
- https://www.janushenderson.com/corporate/article/market-moves-themes-that-mattered-september-2026/
- https://www.firstfinancialtrust.com/2026/10/01/quarterly-market-review-july-september-2026/
- https://investrade.com/market-review-september-28-2026/
- https://stockbee.blogspot.com/
- https://nexusfi.com/d/platforms/deepvue/
- https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/

</details>

<details><summary>fintwit.json / warnings (16 URLs)</summary>

- https://www.aol.com/sec-charges-8-social-media-160856411.html
- https://dot.la/pump-and-dump-discord-2658970824.html
- https://medium.com/@qullamaggieus/mastering-swing-trading-strategies-a-comprehensive-guide-to-qullamaggie-methodology-2e2be5bf6a53
- https://kr.tradingview.com/script/iQtlXxO8-Qullamaggie-Trading-System-Pro
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic
- https://masteremail.podbean.com/e/stop-buying-the-dip-start-doing-this-instead-w-brian-shannon
- https://threadreaderapp.com/scrolly/1979196802021658884
- https://www.tradezella.com/blog/swing-trading-strategies
- https://moneyshow.com/articles/dailyguru-26029
- https://tradingresourcehub.substack.com/p/qullamaggie-stream-notes-1-june-2023

</details>

### B. Merged methods (all 53 in merged_methods.json / merged_compact.json)

<details><summary>1. Pullback to 20/50 MA in an uptrend (EMA-zone, SMA bounce, Holy Grail ADX, Landry, buy-the-dip) (27 URLs)</summary>

- https://www.financialwisdomtv.com/post/make-your-money-work-for-you-trend-following-by-rayner-teo
- https://sponsorradar.com/channels/tradingwithrayner
- https://socialcounts.org/youtube-live-subscriber-count/UCFSn-h8wTnhpKJMteN76Abg
- https://quantamentaltrader.substack.com/p/adam-khoos-piranha-profits-course
- https://sponsorradar.com/channels/adamkhoo
- https://en.wikipedia.org/wiki/Adam_Khoo
- https://moneyshow.com/articles/dailyguru-26029
- https://www.tradezella.com/blog/swing-trading-strategies
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://www.newtraderu.com/
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329
- https://www.antoinebuteau.com/lessons-from-linda-bradford-raschke/
- https://lindaraschke.net/
- https://www.tradingview.com/script/hawl3ybg-Holy-Grail-Setup-with-Confidence-Opacity
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry
- https://articles.stockcharts.com/article/articles-landry-2019-11-trading-the-trend-knockout-582
- https://www.davelandry.com/
- https://in.tradingview.com/script/bgcb3IIb-Pullbacks-Completo
- https://www.traders.com/Documentation/FEEDbk_docs/1996/12/1296tradetips.html
- https://www.reddit.com/r/RealDayTrading/comments/1lp2lr8/
- https://www.reddit.com/r/RealDayTrading/comments/1owinhe/
- https://www.reddit.com/r/swingtrading/comments/1tqyhi3/
- https://www.reddit.com/r/StockMarket/comments/1plnj5s/
- https://reddit.sentinel-team.org/posts/1pf44ar/snapshots/2025-12-06T02%3A59%3A48.977586Z
- https://www.reddit.com/r/swingtrading/comments/1whb374/
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx
- https://alphaarchitect.com/when-academics-disagree-on-momentum-investing/

</details>

<details><summary>2. Episodic Pivot (catalyst gap-up in a neglected stock) (14 URLs)</summary>

- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://stockbee.blogspot.com/
- https://br.tradingview.com/chart/EBS/gr5vb5Ds-EBS-June-24-Qullamaggie-Breakout-and-Episodic-Pivot
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://stockbee.blogspot.com/search?q=episodic+pivot
- https://www.financialwisdomtv.com/post/the-episodic-pivot-strategy-qullamaggie-s-high-momentum-setup-explained
- https://tikamalma.substack.com/p/systems-setups-and-process-of-swing
- https://www.reddit.com/r/swingtrading/comments/1w7tom2/
- https://www.reddit.com/r/swingtrading/comments/1tbg5r2/
- https://www.reddit.com/r/swingtrading/comments/1q9pjy2/
- https://www.reddit.com/r/swingtrading/comments/1n2allv/
- https://www.reddit.com/r/RealDayTrading/comments/1se14q6/

</details>

<details><summary>3. VCP breakout / Minervini Trend Template (SEPA; MA-stack momentum template) (20 URLs)</summary>

- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini
- https://www.minervini.com/
- https://lilys.ai/notes/it/notebooklm-20251211/perfect-vcp-trading-setup-mark-minervini
- https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist
- https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-trend-template-marketsmith
- https://tradersunion.com/news/market-voices/show/2549155-bull-market-rotation-2026/
- https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini
- https://www.tradingview.com/scripts/trend-template/
- https://www.finermarketpoints.com/post/trade-like-stock-market-wizard-vcp-chapter
- https://www.businesswire.com/news/home/20220124005241/en/2021-United-States-Investing-Championship-Winners-%E2%80%94-Minervini-Smashes-Record
- https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing
- https://discussion.fool.com/t/mark-minervini-market-wisdom/108510
- https://www.reddit.com/r/swingtrading/comments/1uebw89/
- https://www.reddit.com/r/swingtrading/comments/1w7tom2/
- https://www.reddit.com/r/swingtrading/comments/1u1u2sx/
- https://www.reddit.com/r/swingtrading/comments/1sm1eku/
- https://www.reddit.com/r/swingtrading/comments/1wauwk8/
- https://www.reddit.com/r/swingtrading/comments/1q0p32z/
- https://www.reddit.com/r/swingtrading/comments/1tqyhi3/
- https://www.reddit.com/r/swingtrading/comments/1q9pjy2/

</details>

<details><summary>4. Classic chart-pattern / base breakouts (cup-with-handle, flat base, triangles, bull flags, trendlines; Zanger practice, Bulkowski and academic statistics) (23 URLs)</summary>

- https://www.cmcmarkets.com/en-gb/opto/world-record-breaking-trader-dan-zangers-tricks-of-the-trade
- https://www.chartpattern.com/
- https://skillsmp.com/creators/mahmoud20138/tradecraft/plugins-tradecraft-skills-dan-zanger-breakout-strategy
- https://thepatternsite.com/cup.html
- https://thepatternsite.com/htf.html
- https://thepatternsite.com/id75.html
- https://www.thepatternsite.com/BestPatterns.html
- https://www.thepatternsite.com/studystudy.html
- https://www.thepatternsite.com/rank.html
- https://www.cxoadvisory.com/technical-trading/classic-papers-returns-from-pattern-based-technical-analysis/
- https://ideas.repec.org/p/fip/fednrp/9414.html
- https://ideas.repec.org/a/oup/jfinec/v5yi2p243-265.html
- https://thepatternsite.com/FailureRates.html
- https://thepatternsite.com/BestPatterns.html
- https://thepatternsite.com/id84.html
- https://papers.ssrn.com/abstract=3756587
- https://www.cxoadvisory.com/technical-trading/machine-assisted-stock-price-pattern-analysis/
- https://www.reddit.com/r/swingtrading/comments/1fy6c45/
- https://www.reddit.com/r/swingtrading/comments/1whb374/
- https://www.reddit.com/r/Daytrading/comments/lag8zs/
- https://www.reddit.com/r/swingtrading/comments/1ukmnlh/
- https://www.reddit.com/r/swingtrading/comments/1rbg39l/
- https://www.reddit.com/r/algotrading/comments/1q25jpe/

</details>

<details><summary>5. Qullamaggie breakout (momentum flag / high tight flag off the 10/20-day MA) (11 URLs)</summary>

- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://sponsorradar.com/channels/qullamaggie
- https://tradingresourcehub.substack.com/t/qullamaggie-stream-notes
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-66-70-review
- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://tradingresourcehub.substack.com/p/qullamaggie-stream-notes-1-june-2023
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-46-50-review
- https://qullamaggie.com/
- https://qullamaggie.com/nasdaq-comparison-late-90s-vs-today/
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream-092

</details>

<details><summary>6. Breadth / regime filters (Zweig breadth thrust, % above 200-day, equal-weight vs cap-weight, Market Monitor) (13 URLs)</summary>

- https://sentimentrader.com/blog/a-cluster-of-breadth-thrusts-bodes-well-for-stocks
- https://edgerater.com/blog/2026-05-06-market-notes-thrust-day
- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini
- https://articles.stockcharts.com/article/articles-arthurhill-2023-11-the-zweig-breadth-thrust-trigg-609/
- https://investing.com/analysis/the-zweig-breadth-thrust-as-a-case-study-in-quantitative-analysis-267684
- https://quantifiedstrategies.substack.com/p/dual-momentum-investing-with-gary
- https://hedgefundalpha.com/strategies/is-gary-antonaccis-global-equity-momentum-strategy-robust/
- https://www.cxoadvisory.com/technical-trading/dual-momentum-with-multi-market-breadth-crash-protection
- https://proactiveadvisormagazine.com/sp-500-update-market-breadth-improves-in-the-first-half-of-2026/
- https://www.spglobal.com/market-intelligence/en/news-insights/articles/2026/2/market-dispersion-widens-as-mega-caps-stumble-equal-weight-index-takes-lead-99108147
- https://articles.stockcharts.com/article/mindfulinvestor-2026-08-weakening-market-breadth-could-signal-trouble-ahead/
- https://historyofmarket.com/sp500/sp500-breadth/
- https://www.fool.com/research/magnificent-seven-sp-500/

</details>

<details><summary>7. CANSLIM / IBD (incl. SwingTrader 5-10 day swings and Market School FTD / distribution-day regime filter) (14 URLs)</summary>

- https://sponsorradar.com/channels/investorsbusinessdaily
- https://discussion.fool.com/t/ibd-swing-trading/109412
- https://www.valuewalk.com/investors-business-daily-swingtrader/
- https://discussion.fool.com/t/ibd-technical-talk-with-mike-webster/104454
- https://seekingalpha.com/instablog/195752-joshua-hayes/73173-a-quick-reminder-about-follow-through-days
- https://discussion.fool.com/t/ibd-market-exposure-recommendation/108128
- https://br.tradingview.com/scripts/ibd
- https://nexusfi.com/d/platforms/deepvue/
- https://magica.com/youtube-summarizer/how-to-use-deepvue-to-apply-the-canslim-methodology-for-effective-stock-trading-2RuiIelL0MA
- https://en.wikipedia.org/wiki/CAN_SLIM
- https://discussion.fool.com/t/ibd-8-week-hold-rule/112549
- https://discussion.fool.com/t/trading-ibd-stocks/104584?page=23
- https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker
- https://www.shortform.com/summary/how-to-make-money-in-stocks-summary-william-j-oneil

</details>

<details><summary>8. Anchored VWAP pullback / multi-timeframe trend alignment (Shannon) (13 URLs)</summary>

- https://masteremail.podbean.com/e/stop-buying-the-dip-start-doing-this-instead-w-brian-shannon
- https://alphatrends.net/
- https://members.alphatrends.net/new-users/
- https://en.wikipedia.org/wiki/Brian_Shannon
- https://www.financialwisdomtv.com/post/maximum-trading-gains-using-price-time-volume
- https://il.tradingview.com/scripts/brianshannon/
- https://cmtassociation.org/?p=2451
- https://www.trade-ideas.com/features/ti-avwap/
- https://shop.dreambooksco.com/products/maximum-trading-gains-with-anchored-vwap-the-perfect-combination-of-price-time-volume
- https://www.luxalgo.com/library/concept/vwap-pinch/
- https://alphatrends.net/archives/podcast/the-avwap-trading-indicator-secrets-and-setups-brian-shannon-traderlion-041523/
- https://www.smbtraining.com/blog/brian-shannon-alphatrends-guest-lectures-at-smb-capital-on-technical-analysis-vwap
- https://trendspider.com/blog/the-trading-pit-live-edition-with-brian-shannon/

</details>

<details><summary>9. Momentum burst (Stockbee 4% breakout, 3-5 day hold) (14 URLs)</summary>

- https://stockbee.blogspot.com/search?q=momentum+burst
- https://stockbee.blogspot.com/
- https://tikamalma.substack.com/p/4-momentum-burst-detailed-research
- https://retailtradersrepository.substack.com/p/pradeep-bonde-stock-examples
- https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts
- https://fintwits-most-popular-stock-market-scans.onrender.com/canada/Stockbee/Breakout%201M%20Base_criteria.html
- https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/
- https://www.hahn-tech.com/ans/tc2000-scan-for-4-breakouts/
- https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/stockbee-momentum-burst-screener
- https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html
- https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html
- https://stockbee.blogspot.com/2016/07/profiting-from-momentum-bursts.html
- https://stockbee.blogspot.com/2021/02/one-idea-which-can-make-you-millions.html
- https://tikamalma.substack.com/p/systems-setups-and-process-of-swing

</details>

<details><summary>10. Parabolic short (and parabolic long reversal) (2 URLs)</summary>

- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic

</details>

<details><summary>11. RSI-2 / Connors-style short-term mean reversion (Double 7s, Cumulative RSI, IBS, RSI-oversold pullback) (17 URLs)</summary>

- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100
- https://backtrex.com/en/backtests/connors-rsi-2-eur-usd
- https://www.luxalgo.com/library/concept/rsi-2/
- https://www.x-trader.net/tag/larry-connors
- https://alvarezquanttrading.com/blog/mean-reversion-vs-trend-following-through-the-years/
- https://alvarezquanttrading.com/blog/bad-month-for-your-strategy-should-you-change-it/
- https://alvarezquanttrading.com/blog/the-power-of-strategy-diversification/
- https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf
- https://backtrex.com/en/backtests/connors-rsi-2-dax
- https://prorealcode.com/prorealtime-trading-strategies/rsi-2p-larry-connors/?pnum=13
- https://www.reddit.com/r/Daytrading/comments/1rktyiu/
- https://www.reddit.com/r/algotrading/comments/1qfw5pl/
- https://www.reddit.com/r/algotrading/comments/1f0689m/
- https://www.reddit.com/r/Trading/comments/1pai6jt/
- https://www.reddit.com/r/swingtrading/comments/1suu91m/
- https://reddit.sentinel-team.org/posts/1qfw5pl/snapshots/2026-01-19T19%3A11%3A34.79073Z

</details>

<details><summary>12. Kell Cycle of Price Action (Wedge Pop, EMA Crossback, Base n' Break, Wedge Drop) (6 URLs)</summary>

- https://traderlion.com/technical-analysis/chart-patterns/wedge-pop-the-money-pattern/
- https://traderlion.com/technical-analysis/chart-patterns/cycle-of-price-action-by-oliver-kell/
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://id.tradingview.com/script/SmNMRIra-Oliver-Kell-Master-System/
- https://www.tradingview.com/script/GOkJ7o5J-Wedge-Pop-Drop-QuantVue
- https://www.financialwisdomtv.com/post/oliver-kell-us-investing-champion

</details>

<details><summary>13. Insider Buy Superstocks (Stine weekly 30-week MA breakout + 10-week 'magic line') (7 URLs)</summary>

- https://www.financialwisdomtv.com/post/insider-buy-superstocks-by-jesse-stine
- https://microcapclub.com/book-review-insider-buy-superstocks-by-jesse-stine/
- https://www.jessestine.com/
- https://www.tradingview.com/chart/AOI/Wl6SZ9WZ-Is-Alliance-One-a-Jesse-C-Stine-SuperStock
- https://www.goodreads.com/book/show/18012667
- https://threadreaderapp.com/thread/1028428610275819520.html
- https://www.tradingview.com/script/u0adR7NU-Superstock-10-30-WMA-Band-script

</details>

<details><summary>14. Sector / theme / group rotation via relative strength (ETF RS, thematic baskets, intra-AI rotation) (20 URLs)</summary>

- https://www.reddit.com/r/swingtrading/comments/1v1oveh/
- https://www.reddit.com/r/RealDayTrading/comments/1v5y52r/
- https://www.reddit.com/r/swingtrading/comments/1tqyhi3/
- https://www.reddit.com/r/swingtrading/comments/1q9pjy2/
- https://www.reddit.com/r/stocks/comments/1udlb11/
- https://www.bloomberg.com/news/articles/2026-07-06/morgan-stanley-s-wilson-sees-rotation-from-chips-to-hyperscalers
- https://seekingalpha.com/article/4923482-buy-hyperscalers-sell-semiconductors-the-rotation-has-already-started
- https://thecorner.eu/financial-markets/shift-from-semiconductors-and-memory-towards-hyperscalers-and-software-continues/127099/
- https://www.tradingview.com/news/leverage_shares:c8d519c05094b:0-the-2026-semiconductor-selloff-creates-an-opportunity/
- https://finance.yahoo.com/markets/stocks/articles/semiconductor-stocks-see-rare-surge-070916646.html
- https://www.cnbc.com/2026/07/29/chip-selloff-sk-hynix-samsung-softbank.html
- https://www.yellowcakeanalytics.com/learn/smr-stocks
- https://247wallst.com/investing/2026/09/08/nuscale-power-spikes-13-oklo-climbs-7-is-the-nuclear-selloff-finally-exhausted/
- https://www.goldmansachs.com/insights/articles/biotech-stocks-are-projected-to-extend-rally-amid-innovation
- https://finance.yahoo.com/healthcare/articles/biotech-etfs-put-strong-show-160000067.html
- https://www.ig.com/en/news-and-trade-ideas/memory-chip-stocks-rally-2026-260708
- https://www.nbcnews.com/world/asia/unitree-china-robot-maker-stock-market-ai-humanoids-tech-trump-rcna593278
- https://www.cnbc.com/2026/04/27/global-military-spending-record-2025-europe-asia-ukraine-sipri.html
- https://www.fool.com/investing/2026/02/11/better-utility-stock-constellation-energy-v-vistra/
- https://www.fastcompany.com/91465778/quantum-computing-stocks-rise-and-fall-d-wave-rigetti-ionq

</details>

<details><summary>15. Volatility-regime gating / vol-managed exposure (VIX bands, realized-vol scaling, momentum-crash avoidance) (10 URLs)</summary>

- https://www.nber.org/papers/w20439
- https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html
- https://www.chicagobooth.edu/review/understanding-momentum-crashes
- https://www.etf.com/sections/index-investor-corner/swedroe-downside-momentum
- https://aqr.com/library/journal-articles/momentum-crashes
- https://macroption.com/vix-all-time-high
- https://www.cnbc.com/2026/08/17/stock-market-volatility-vix-wall-street.html
- https://www.citadelsecurities.com/news-and-insights/global-market-intelligence/2h-september-getting-closer/
- https://www.sifma.org/research/insights/market-musings-vix
- https://markets.financialcontent.com/stocks/article/marketminute-2026-3-3-fear-returns-to-wall-street-vix-soars-to-2643-as-us-iran-conflict-ignites-geopolitical-firestorm

</details>

<details><summary>16. Power Earnings Gap / Buyable Gap-Up / post-earnings drift (PEAD) (7 URLs)</summary>

- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://www.tradezella.com/blog/swing-trading-strategies
- https://investmentliteracycoach.beehiiv.com/p/overview
- https://ideas.repec.org/a/now/jnlcfr/104.00000122.html
- https://cfr.ivo-welch.info/published/papers/martineau2021rest.pdf
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://www.nber.org/papers/w13090

</details>

<details><summary>17. Opening-range / intraday breakout and VWAP day-trading setups (ORB 'stocks in play'; Humbled Trader) (9 URLs)</summary>

- https://concretumgroup.com/a-profitable-day-trading-strategy-for-the-u-s-equity-market/
- https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/
- https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy
- https://www.mql5.com/en/blogs/post/776235
- https://www.cxoadvisory.com/technical-trading/day-trading-with-an-opening-range-breakout-strategy
- https://www.quantconnect.com/forum/discussion/18444/Opening+Range+Breakout+for+Stocks+in+Play/p3/comment-50591
- https://humbledtrader.beehiiv.com/p/humbled-traders-trading-strategies-crash-course-complete-criteria-live-trading-examples
- https://humbledtrader.com/blog/
- https://vidiq.com/youtube-stats/channel/UCO4h1mou05OWuJ8JZaWOj8w

</details>

<details><summary>18. Pure price-action / structure swings (HH/HL, failed retests, The Strat, weekly candles, candlestick pullbacks) (7 URLs)</summary>

- https://sponsorradar.com/channels/thetradingchannel
- https://fortraders.com/blog/top-5-best-trading-youtubers-in-2025-curated-by-expert
- https://www.reddit.com/r/swingtrading/comments/1qxrw1n/
- https://www.reddit.com/r/swingtrading/comments/1q9pjy2/
- https://www.reddit.com/r/swingtrading/comments/1tqyhi3/
- https://www.reddit.com/r/swingtrading/comments/1rdppyz/
- https://reddit.sentinel-team.org/posts/1qot5gp/snapshots/2026-01-28T17%3A51%3A57.95647Z

</details>

<details><summary>19. Automated / AI-assisted swing systems (regime filters, meta-labeling, LLM-agent research, MCP broker execution loop) (23 URLs)</summary>

- https://www.reddit.com/r/algotrading/comments/1w7zz3g/
- https://www.reddit.com/r/algotrading/comments/1r5al3o/
- https://www.reddit.com/r/algotrading/comments/1wm02aw/
- https://www.reddit.com/r/algotrading/comments/1e490dv/
- https://www.reddit.com/r/algotrading/comments/1phv4zz/
- https://www.reddit.com/r/algotrading/comments/1lnm48w/
- https://www.reddit.com/r/algotrading/comments/1vsmrbs/
- https://www.reddit.com/r/algotrading/comments/1qklj4o/
- https://www.reddit.com/r/algotrading/comments/1q25jpe/
- https://www.reddit.com/r/algotrading/comments/1kmfpx5/
- https://www.reddit.com/r/algotrading/comments/1uczfiw/
- https://www.reddit.com/r/algotrading/comments/1p6a95y/
- https://www.reddit.com/r/RealDayTrading/comments/1whaqj0/
- https://www.reddit.com/r/Daytrading/comments/1qsnkh5/
- https://www.stockbrokers.com/guides/ai-agent-brokers
- https://docs.alpaca.markets/us/docs/alpaca-mcp-server
- https://walnutinvest.com/resources/mcp-connectors-for-brokerages-compared
- https://chartlibrary.io/blog/financial-mcp-servers-compared
- https://mcpmarket.com/server/schwab-brokerage
- https://www.liberatedstocktrader.com/ai-stock-trading/
- https://vpsranking.com/news/ai/ai-2026-05-15-openai-chatgpt-personal-finance/
- https://www.bankingdive.com/news/anthropic-rolls-out-financial-ai-tools-target-large-clients-claude/753249/
- https://dangelov.com/blog/trading-with-claude/

</details>

<details><summary>20. TraderLion-school leader trading (Moglen 'True Market Leaders' RS-line + Kell/O'Neil hybrid; Petralia VCP + earnings gap) (7 URLs)</summary>

- https://tradingengineered.substack.com/p/lessons-from-a-veteran-swing-trader
- https://kj-gets-better.notion.site/Videos-Interviews-0f25743976ad43b8a0f4e2a567617a61
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://nexusfi.com/d/platforms/deepvue/
- https://app.podwise.ai/dashboard/episodes/3678873
- https://www.mypodcastdata.com/podcast/show/the-traderlion-podcast-traderlion-ffj
- https://traderlion.com/profile/richard-moglen/oliver-kell-full-strategy-masterclass/

</details>

<details><summary>21. Macro-print / FOMC event positioning under a hiking Fed (jobs/CPI as binary catalysts; prediction-market odds as input) (9 URLs)</summary>

- https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm
- https://thebusinessjournal.com/stocks-slump-as-big-tech-sinks-and-a-strong-may-jobs-report-boosts-odds-for-higher-interest-rates/
- https://www.federalreserve.gov/monetarypolicy/openmarket.htm
- https://www.morningstar.com/markets/whats-next-fed-2026
- https://fedratecalc.com/fomc-meeting-schedule/
- https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/
- https://www.pewresearch.org/short-reads/2026/09/23/prediction-markets-trading-volume-doubled-between-may-and-july-largely-driven-by-sports/
- https://www.trade-ideas.com/2026/04/29/prediction-markets-kalshi-polymarket/
- https://www.ccn.com/education/gambling/prediction-markets-53b-kalshi-polymarket-gambling-sports/

</details>

<details><summary>22. 0DTE-aware intraday structure (pinning, late-day unwinds, Mon/Wed single-stock expiries) (5 URLs)</summary>

- https://spotgamma.com/record-0dte-volume-reshapes-the-sp-500/
- https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025
- https://www.citadelsecurities.com/news-and-insights/global-market-intelligence/1h-2026-market-structure-flows/
- https://www.interactivebrokers.com/campus/traders-insight/securities/options/spx-0dte-options-jumped-to-record/
- https://concretumgroup.substack.com/p/the-rise-of-0dte-options

</details>

<details><summary>23. 52-week-high breakout / proximity-to-high momentum (4 URLs)</summary>

- https://cxoadvisory.com/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks
- https://experts.nau.edu/en/publications/the-52-week-high-and-momentum-investing-in-international-stock-in/
- https://mro.massey.ac.nz/bitstreams/99e67c25-4ed2-4314-bd0b-062930e5742b/download
- https://academicnewsletter.sufe.edu.cn/info/361244

</details>

<details><summary>24. Cross-sectional momentum / relative strength (12-1 month, monthly rebalance) (8 URLs)</summary>

- https://ideas.repec.org/a/eee/pacfin/v82y2023ics0927538x23002731.html
- https://ideas.repec.org/a/kap/fmktpm/v37y2023i1d10.1007_s11408-022-00417-8.html
- https://alphaarchitect.com/momentum-factor-investing-30-years-of-out-of-sample-data/
- https://alphaarchitect.com/surprise-the-size-value-and-momentum-anomalies-survive-after-trading-costs/
- https://www.nber.org/papers/w20721
- https://indexes.morningstar.com/insights/markets-review/bltd9a242a7280e6745/morningstar-factor-monitor-q1-2025
- https://www.capitalspectator.com/?p=24446
- https://morganstanley.com/im/en-us/financial-advisor/insights/articles/momentum-ruled-in-2024.html

</details>

<details><summary>25. Discretionary retail day/swing trading (base-rate evidence on outcomes) (11 URLs)</summary>

- https://repositorio.fgv.br/items/e87d04fc-4b4c-4a56-ab5a-1c84c1afde1b/full
- https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf
- https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html
- https://www.evidenceinvestor.com/why-most-robinhood-traders-earn-lousy-returns/
- https://www.bloomberg.com/news/articles/2023-04-21/day-traders-lose-358-000-per-day-gambling-on-zero-day-options
- https://cxoadvisory.com/individual-investing/retail-0dte-option-trader-performance
- https://realinvestmentadvice.com/resources/blog/why-retail-traders-consistently-underperform-over-time/
- https://www.chicagobooth.edu/review/high-price-cheaper-stock-trades
- https://cris.maastrichtuniversity.nl/en/publications/technical-analysis-and-individual-investors
- https://www.cxoadvisory.com/individual-investing/technical-analysis-a-drag/
- https://ideas.repec.org/a/bla/jecsur/v21y2007i4p786-826.html

</details>

<details><summary>26. Moving-average crossover signals (golden / death cross) as standalone entries (4 URLs)</summary>

- https://researchonline.lse.ac.uk/id/eprint/119144
- https://ideas.repec.org:443/a/eee/jfinec/v106y2012i3p473-491.html
- https://ideas.repec.org:443/a/eee/ecolet/v216y2022ics0165176522001720.html
- https://www.cxoadvisory.com/technical-trading/long-run-moving-average-horse-race-for-timing-the-u-s-stock-market

</details>

<details><summary>27. Post-PDT intraday-margin day trading (no $25k gate, exposure-based buying power) (5 URLs)</summary>

- https://www.finra.org/rules-guidance/notices/26-10
- https://www.sec.gov/files/rules/sro/finra/2026/34-104572.pdf
- https://www.acaglobal.com/industry-insights/finra-ends-the-pattern-day-trader-rule/
- https://optionalpha.com/blog/pdt-rule-change-what-it-means-for-options-traders
- https://tradezero.com/en-us/blog/the-usd25-000-day-trading-minimum-is-gone-here-s-what-it-means-for-you

</details>

<details><summary>28. Relative strength/weakness 'market first' method (r/RealDayTrading wiki / OneOption) (14 URLs)</summary>

- https://www.reddit.com/r/RealDayTrading/comments/vczdo1/
- https://www.reddit.com/r/RealDayTrading/comments/svn70b/
- https://www.reddit.com/r/RealDayTrading/comments/origab/
- https://www.reddit.com/r/RealDayTrading/comments/otpd7a/
- https://www.reddit.com/r/RealDayTrading/comments/1k09xap/
- https://www.reddit.com/r/RealDayTrading/comments/1lp2lr8/
- https://www.reddit.com/r/RealDayTrading/comments/1jqj3r2/
- https://www.reddit.com/r/RealDayTrading/comments/1snf2ys/
- https://www.reddit.com/r/RealDayTrading/comments/1pyqm25/
- https://www.reddit.com/r/RealDayTrading/comments/1r3u4y7/
- https://www.reddit.com/r/RealDayTrading/comments/1si1nr9/
- https://www.reddit.com/r/RealDayTrading/comments/1w7319z/
- https://www.reddit.com/r/Trading/comments/1vpbe58/
- https://github.com/RichVarney/RealDayTrading_Wiki

</details>

<details><summary>29. Trend filter / time-series momentum (10-month SMA, 200-day MA, absolute momentum) (13 URLs)</summary>

- https://www.quantconnect.com/forum/discussion/8285/a-quantitative-approach-to-tactical-asset-allocation-gtaa-5-with-simplemovingaverage/
- https://mebfaber.libsyn.com/ep86-meb-faber
- https://papers.ssrn.com/abstract=2677212
- https://www.cxoadvisory.com/technical-trading/market-timing-with-moving-averages-over-the-very-long-run
- https://www.advisorperspectives.com/articles/2014/08/19/do-moving-average-strategies-really-work
- https://papers.ssrn.com/abstract=2089463
- https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing?aqrPDF=1
- https://www.toptradersunplugged.com/trend-following-week-in-review-december-26-2025/
- https://thefullfx.com/ctas-end-2025-on-a-positive-note/
- https://www.alternativeswatch.com/2025/06/02/trend-following-hedge-funds-endure-more-pain-societe-generale-indices/
- https://www.toptradersunplugged.com/author/naomi/
- https://quantifiedstrategies.substack.com/p/dual-momentum-investing-with-gary
- https://hedgefundalpha.com/strategies/is-gary-antonaccis-global-equity-momentum-strategy-robust/

</details>

<details><summary>30. Higher-timeframe liquidity / structure swings (ICT-style: sweep -> displacement -> FVG, ERL->IRL, MSS) (9 URLs)</summary>

- https://www.reddit.com/r/Trading/comments/1w6samx/
- https://www.reddit.com/r/Trading/comments/1u2iqyl/
- https://www.reddit.com/r/Trading/comments/1rpmj8o/
- https://www.reddit.com/r/Daytrading/comments/1ufo47i/
- https://www.reddit.com/r/Daytrading/comments/1szye3f/
- https://www.reddit.com/r/Trading/comments/1ote2d5/
- https://www.reddit.com/r/swingtrading/comments/1qz7lx5/
- https://www.reddit.com/r/swingtrading/comments/1j7kkn1/
- https://reddit.sentinel-team.org/posts/1qot5gp/snapshots/2026-01-28T17%3A51%3A57.95647Z

</details>

<details><summary>31. Extended-hours / overnight-session (23x5 from 2026-12-06) and tokenized-venue trading (11 URLs)</summary>

- https://www.wilmerhale.com/en/insights/client-alerts/20260929-23x5-trading-comes-to-us-exchanges-what-firms-should-know-before-launch
- https://www.dtcc.com/dtcctransformation/24x5
- https://www.cnbc.com/2025/12/16/nasdaq-moves-to-near-24-hour-trading-some-say-thats-a-bad-idea.html
- https://www.capco.com/intelligence/capco-intelligence/us-equities-extended-trading-hours
- https://equities.24exchange.com/posts/is-2027-the-new-24-hour-trading-target
- https://www.skadden.com/insights/publications/2026/09/sec-innovation-exemption-establishes
- https://www.dechert.com/knowledge/onpoint/2026/9/sec-issues--innovation-exemption--to-facilitate-trading-of-token.html
- https://www.jonesday.com/de/insights/2026/09/the-secs-new-innovation-exemption-fiveyear-relief-for-trading-on-tokenized-securities-venues
- https://www.cnbc.com/2026/09/17/sec-clears-path-for-tokenized-stocks-bringing-24/7-trading-closer.html
- https://www.benzinga.com/crypto/cryptocurrency/26/09/61860709/sec-gives-tokenized-stocks-a-five-year-onchain-runway-robinhood-ceo-vlad-tenev-says-its-a-good-day-for-us-innovation
- https://gfmag.com/technology/nyse-plans-tokenized-24-7-trading/

</details>

<details><summary>32. Growth / story + fundamentals + technicals discretionary swing (Caruso group rotation; Chat With Traders guests) (7 URLs)</summary>

- https://tradingengineered.substack.com/p/how-to-trade-stocks-with-matt-caruso
- https://matthewcaruso.substack.com/about
- https://trendspider.com/trading-tools-store/collection/by-caruso-insights/
- https://pod.wave.co/podcast/the-traderlion-podcast-8e50b654-7b23-4b2d-aca4-50a775c117e3
- https://chatwithtraders.com/episodes
- https://chatwithtraders.com/tag/swing-trading/
- https://chatwithtraders.com/about

</details>

<details><summary>33. Congressional-trade following (Pelosi tracker, NANC/KRUZ) (7 URLs)</summary>

- https://www.cambridge.org/core/journals/business-and-politics/article/abnormal-returns-from-the-common-stock-investments-of-members-of-the-us-house-of-representatives/BC6C6A524BBE96738BB94D37EF0FD1A5
- https://ideas.repec.org/a/eee/pubeco/v207y2022ics0047272722000044.html
- https://www.nber.org/papers/w35041
- https://forum.effectivealtruism.org/posts/ojjotdtWgY9JCwMZK/congressional-insider-trading
- https://fortune.com/2025/01/08/congress-stock-trading-pelosi-2024
- https://www.webull.com/news/13470340294333440
- https://cepr.org/voxeu/columns/political-power-and-profitable-trades-us-congress

</details>

<details><summary>34. High tight flag (O'Neil pattern; Soreide masterclass) (4 URLs)</summary>

- https://sozai.app/transcript/powerful-swing-trading-setup-high-tight-flag/
- https://www.luxalgo.com/library/concept/high-tight-flag.md
- https://pod.wave.co/podcast/the-traderlion-podcast-8e50b654-7b23-4b2d-aca4-50a775c117e3
- https://www.benzinga.com/news/earnings/22/05/27209037/exclusive-if-trading-conditions-are-unfavourable-dont-waste-time-capital-trying-to-make-something-f

</details>

<details><summary>35. Insider cluster buying / Form 4 open-market-purchase following (4 URLs)</summary>

- https://papers.ssrn.com/abstract=1692517
- https://www.nber.org/digest/apr11/decoding-inside-information
- https://www.evidenceinvestor.com/what-insider-trades-and-non-trades-tell-us-about-future-returns/
- https://arxiv.org/abs/2602.06198

</details>

<details><summary>36. Policy-shock V-recovery buying (buy the policy-reversal day, not the first dip) (4 URLs)</summary>

- https://www.betashares.com.au/insights/liberation-day-upended-markets/
- https://fortune.com/2026/04/08/markets-sp-trump-truce-ceasefire-iran-war-rally-strait-of-hormuz
- https://cdn.gam.com/it/our-thinking/multi-asset-blog/did-markets-get-liberation-day-all-wrong
- https://www.nasdaq.com/articles/april-2025-review-and-outlook

</details>

<details><summary>37. Stage analysis (Weinstein 30-week MA Stage 2 breakout) (4 URLs)</summary>

- https://traderlion.com/trading-strategies/stage-analysis/
- https://stageanalysis.net/blog/4372/stage-analysis-breakout-quality-checklist
- https://www.mql5.com/en/articles/22746
- https://www.stageanalysis.net/blog/1373123/stage-analysis-weekend-video-15-march-2026

</details>

<details><summary>38. Breitstein playbook swing (mean reversion + continuation) (3 URLs)</summary>

- https://castbox.fm/channel/TheOneLanceB-Trading-Podcast-id7145293
- https://theonelanceb.com/
- https://www.smbtraining.com/blog/the-formula-for-how-to-become-a-7-figure-trader-chat-with-traders-podcast

</details>

<details><summary>39. Core position + options overlay / trading around a core (5 URLs)</summary>

- https://www.reddit.com/r/Trading/comments/1n0hl6z/
- https://www.reddit.com/r/Daytrading/comments/1isl2el/
- https://www.reddit.com/r/Daytrading/comments/1ia39vf/
- https://www.reddit.com/r/RealDayTrading/comments/1pyqm25/
- https://www.reddit.com/r/swingtrading/comments/1qpoxhk/

</details>

<details><summary>40. Crypto-proxy equities (DATs, MSTR mNAV): short / avoid the premium-collapse leg (7 URLs)</summary>

- https://www.sec.gov/Archives/edgar/data/0001050446/000105044626000036/mstr-20260730x8kxex991.htm
- https://decrypt.co/358871/anthony-pompliano-bitcoin-treasury-procap-buys-back-stock
- https://www.dextools.io/news/bitcoin-treasury-dat-model-mnav-below-1-twenty-companies-july-2026
- https://bitcointreasuries.net/news/the-mnav-trap-why-70percent-discounts-arent-bargains
- https://www.theblock.co/post/374266/crypto-liquidations-near-10-billion-in-historic-drawdown-following-trumps-100-tariffs-on-china
- https://finance.yahoo.com/markets/crypto/articles/bitcoin-peaked-126-080-october-091605452.html
- https://fortune.com/article/price-of-bitcoin-10-06-2026/

</details>

<details><summary>41. Gamma-aware meme / short-squeeze momentum (smaller size, explicit exits) (5 URLs)</summary>

- https://finance.yahoo.com/news/opendoor-kohls-resume-rally-meme-160314410.html
- https://www.aol.com/articles/meme-stocks-mega-ipos-wallstreetbets-094001244.html
- https://smallcapinvestor.beehiiv.com/p/the-resurgence-of-meme-stock-mania-from-gamestop-to-beyond-meat-and-who-s-next
- https://cnttrading.substack.com/p/daily-market-2026-06-24
- https://www.top1markets.com/news/meme-stocks-2026-gme-amc-reddit-wallstreetbets

</details>

<details><summary>42. IPO after-market trading (day-1 pop fade and first-base breakout) (5 URLs)</summary>

- https://www.renaissancecapital.com/review/2025USReview_Press.pdf
- https://wolfstreet.com/2025/12/29/ipo-bloodletting-after-the-pop-in-2025-venture-global-coreweave-figma-klarna-bullish-circle-internet-naven-firefly-fermi/
- https://www.iposcoop.com/?p=38639
- https://en.wikipedia.org/wiki/Initial_public_offering_of_SpaceX
- https://ibinterviewquestions.com/guides/equity-capital-markets/the-2026-mega-ipo-pipeline-spacex-openai-anthropic-kraken

</details>

<details><summary>43. Position sizing / R-multiples / expectancy / SQN (Van Tharp) (3 URLs)</summary>

- https://www.vantharpinstitute.com/
- https://nexusfi.com/psychology-money-management/4884-trading-metrics-journals-record-keeping-2.html
- https://www.tradingview.com/script/vTaMXYEn-SQN

</details>

<details><summary>44. Relative-volume-first stock selection and scanner / watchlist workflow (7 URLs)</summary>

- https://www.reddit.com/r/swingtrading/comments/1t4lh5n/
- https://www.reddit.com/r/swingtrading/comments/1ukmnlh/
- https://www.reddit.com/r/swingtrading/comments/1q9pjy2/
- https://www.reddit.com/r/RealDayTrading/comments/1q480ds/
- https://www.reddit.com/r/swingtrading/comments/1rbg39l/
- https://www.reddit.com/r/RealDayTrading/comments/omw9rn/
- https://www.reddit.com/r/swingtrading/comments/1upwu2j/

</details>

<details><summary>45. Seasonality (turn-of-month, Halloween / Sell-in-May, Santa rally) (7 URLs)</summary>

- https://research.nottingham.edu.cn/en/publications/the-halloween-indicator-sell-in-may-and-go-away-everywhere-and-al/fingerprints/
- https://arc-dev.theglobeandmail.com/investing/markets/inside-the-market/article-inside-the-strange-behaviour-of-sell-in-may-and-go-away
- https://harbourfrontquant.substack.com/p/do-calendar-anomalies-still-work
- https://www.etftrends.com/etf-strategist-channel/turn-month-effect/
- https://www.cxoadvisory.com/calendar-effects/turn-of-the-month-effect-persistence-and-robustness
- https://fidelity.com/insights/markets-economy/santa-claus-rally
- https://www.nerdwallet.com/article/investing/santa-claus-rally

</details>

<details><summary>46. Bear Bull Traders 'How to Swing Trade' beginner framework (Aziz / Pezim) (4 URLs)</summary>

- https://en.wikipedia.org/wiki/Andrew_Aziz
- https://www.blinkist.com/en/books/how-to-swing-trade-en
- https://www.goodreads.com/book/show/55746728
- https://gummysearch.com/r/swingtrading

</details>

<details><summary>47. Trader Stewie 'Art of Trading' discretionary swing (wedges, breakouts, pullbacks, PEGs) (3 URLs)</summary>

- https://udcourse.com/product/the-art-of-trading-inside-the-mind-of-trader-stewie/
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://www.smbtraining.com/blog/what-basic-trading-setups-should-i-learn

</details>

<details><summary>48. Turtle Soup failed-breakout reversal (Raschke / Connors) (3 URLs)</summary>

- https://www.luxalgo.com/library/concept/turtle-soup/
- https://www.tradingview.com/script/28gN99Tw-Turtle-Soup-Indicator
- https://technical.traders.com/tradersonline/display.asp?art=2414

</details>

<details><summary>49. DeMark TD Sequential / TD Combo exhaustion counts (5 URLs)</summary>

- https://www.mql5.com/en/blogs/post/748846
- https://www.mql5.com/en/blogs/post/746570
- https://nexusfi.com/a/indicators/td-sequential-demark-indicators
- https://oxfordstrat.com/?p=9037
- https://www.perlego.com/book/1007299/demark-indicators-pdf

</details>

<details><summary>50. Grimes pullback / Anti / failure test / breakout (Art and Science of Technical Analysis) (5 URLs)</summary>

- https://topstep.com/blog/going-deep-on-adam-grimes-approach
- https://adamhgrimes.com/
- https://adamhgrimes.com/volatility-shocks-and-what-follows/
- https://moneylifeshow.libsyn.com/marketlifes-grimes-technicals-do-not-look-right-for-the-rally-to-roll-on
- https://www.goodreads.com/book/show/13838135

</details>

<details><summary>51. Weekend Trend Trader weekly 20-week-high system (Nick Radge) (3 URLs)</summary>

- https://usethinkscript.com/threads/weekend-trend-trader-by-nick-radge-strategy-for-thinkorswim.669/
- https://books.apple.com/us/book/weekend-trend-trader/id711140317
- https://www.thechartist.com.au/?p=16809

</details>

<details><summary>52. Master Swing Trader '7 Bells' (Alan Farley) (3 URLs)</summary>

- https://www.mheducation.com/highered/mhp/product/master-swing-trader-tools-techniques-profit-outstanding-short-term-trading-opportunities.html
- https://www.goodreads.com/book/show/5017866
- https://chatwithtraders.com/video/swing-trading-breakouts-and-dynamics-of-price-movement-alan-farley-interview

</details>

<details><summary>53. Top-1 market-cap rotation (hold the largest company, switch on dethroning) (1 URLs)</summary>

- https://www.reddit.com/r/Daytrading/comments/1u7r3oy/

</details>

### C. Deep dives (docs/methods/*.md)

<details><summary>01-pullback-20-50-ma-uptrend.md (55 URLs)</summary>

- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry
- https://articles.stockcharts.com/article/articles-landry-2019-11-trading-the-trend-knockout-582
- https://articles.stockcharts.com/article/articles-landry-2021-04-letting-the-ebb-flow-control-y-62
- https://articles.stockcharts.com/article/articles-landry-2020-03-understanding-trend-following-468
- https://www.davelandry.com/
- https://www.traders.com/Documentation/FEEDbk_docs/1996/12/1296tradetips.html
- https://moneyshow.com/articles/dailyguru-26029
- https://www.newtraderu.com/
- https://newtraderu.teachable.com/p/moving-averages
- https://newtraderu.teachable.com/p/moving-average-signals
- https://lindaraschke.net/
- https://www.antoinebuteau.com/lessons-from-linda-bradford-raschke/
- https://traderlion.com/technical-analysis/chart-patterns/ema-crossback/
- https://traderlion.com/technical-analysis/trading-the-ema-crossback/
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://alphatrends.net/
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329
- https://tradingsetupsreview.com/the-holy-grail-trading-setup
- https://www.ebc.com/forex/holy-grail-trading-setup
- https://www.tradingview.com/script/hawl3ybg-Holy-Grail-Setup-with-Confidence-Opacity
- https://www.financialwisdomtv.com/post/make-your-money-work-for-you-trend-following-by-rayner-teo
- https://in.tradingview.com/script/srm3ovD0-Rayner-Teo-s-EMA-Setting
- https://sponsorradar.com/channels/tradingwithrayner
- https://socialcounts.org/youtube-live-subscriber-count/UCFSn-h8wTnhpKJMteN76Abg
- https://quantamentaltrader.substack.com/p/adam-khoos-piranha-profits-course
- https://sponsorradar.com/channels/adamkhoo
- https://en.wikipedia.org/wiki/Adam_Khoo
- https://www.tradezella.com/blog/swing-trading-strategies
- https://in.tradingview.com/script/bgcb3IIb-Pullbacks-Completo
- https://easyswing.trading/performance
- https://github.com/sofus-nl/swing-trading-strategies
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/23-trend-pullback.md
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/21-proximity-pullback.md
- https://quantifiedstrategies.substack.com/p/a-simple-stochastic-pullback-strategy
- https://quantifiedstrategies.substack.com/p/rsi-pullback-strategy
- https://quantifiedstrategies.substack.com/p/low-risk-pullback-strategy
- https://elitetrader.com/et/threads/moving-averages-are-random.299801/post-4280395
- https://topstepbrokerage.com/blog/going-deep-on-adam-grimes-approach
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx
- https://alphaarchitect.com/when-academics-disagree-on-momentum-investing/
- https://ideas.repec.org/a/bla/jfinan/v47y1992i5p1731-64.html
- https://alphaarchitect.com/old-school-academics-on-moving-average-rules-remarkable/
- https://eprints.soton.ac.uk/377140/1/Urquhart_How.pdf
- https://www.crowdfundinsider.com/2026/01/257034-retail-investors-navigate-market-volatility-in-2025-for-steady-returns-research/
- https://www.aol.com/articles/people-getting-more-aggressive-buying-145213218.html
- https://finance.yahoo.com/news/buy-dip-etfs-3-trends-204853436.html
- https://thenightly.com.au/business/the-economist-buy-the-dip-investment-trend-keeps-markets-from-crashing-during-donald-trumps-wild-ride-c-18597199
- https://blog.traderspost.io/article/buy-the-dip-2026-retails-data-driven-playbook
- https://sentimentrader.com/blog/the-sp-500-completes-a-base-breakdown-pattern--16-3-2026
- https://www.reddit.com/r/swingtrading/comments/1whb374/
- https://www.reddit.com/r/swingtrading/comments/1tqyhi3/
- https://www.reddit.com/r/RealDayTrading/comments/1lp2lr8/
- https://www.reddit.com/r/RealDayTrading/comments/1owinhe/
- https://www.reddit.com/r/StockMarket/comments/1plnj5s/
- https://reddit.sentinel-team.org/posts/1pf44ar/snapshots/2025-12-06T02%3A59%3A48.977586Z

</details>

<details><summary>02-episodic-pivot.md (39 URLs)</summary>

- https://stockbee.blogspot.com/2007/02/episodic-pivots-and-idea-pickle.html
- https://stockbee.blogspot.com/2007/02/up-stocks-and-down-stocks_15.html
- https://stockbee.blogspot.com/2007/06/episodic-pivot-shorts.html
- https://stockbee.blogspot.com/2007/07/episodic-pivot-catalysts.html
- https://stockbee.blogspot.com/2007/07/episodic-pivot-bullish-4-plus-breakout.html
- https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html
- https://stockbee.blogspot.com/2026/09/november-2026-bootcamp-las-vegas.html
- https://stockbee.blogspot.com/
- https://stockbee.blogspot.com/search?q=episodic+pivot
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://www.virtueofselfishinvesting.com/faqs/answer/how-do-you-determine-if-a-stock-gapping-up-is-buyable-if-it-is-buyable-how-do-you-time-your-entry
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://sozai.app/transcript/100-million-dollar-catalyst-trade-setup/
- https://traderlion.com/podcast/discover-episodic-pivots/
- https://traderlion.com/podcast/pradeep-bonde-episodic-pivots/
- https://traderlion.com/profile/pradeep-bonde/episodic-pivots/
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- http://theimpatienttrader.blogspot.com/2019/02/what-is-power-earnings-gap-and-how-to.html
- https://www.financialwisdomtv.com/post/the-episodic-pivot-strategy-qullamaggie-s-high-momentum-setup-explained
- https://stockbsessed.substack.com/p/episodic-pivot-1
- https://br.tradingview.com/chart/EBS/gr5vb5Ds-EBS-June-24-Qullamaggie-Breakout-and-Episodic-Pivot
- https://scan.stockcharts.com/discussion/comment/2735
- https://www.tradingview.com/script/PZghP0Uq-Episodic-Pivot/
- https://cn.tradingview.com/script/wvGrk7vs-Episodic-Pivot-Aparna
- https://github.com/tradermonty/claude-trading-skills/blob/main/skills/stockbee-episodic-pivot-analyzer/references/ep_methodology.md
- https://www.tradezella.com/strategies/episode-pivot-strategy
- https://www.finermarketpoints.com/post/episodic-pivot-trading-complete-guide
- https://whatworksintrading.substack.com/p/kristjan-qullamaggie-and-stockbee
- https://whatworksintrading.substack.com/p/deep-dive-on-gap-trading-how-did
- https://www.tradingresearchub.com/p/research-article-44-kristjan-kullamagis
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://papers.ssrn.com/sol3/Delivery.cfm?abstractid=5930255
- https://academic.oup.com/rfs/article-abstract/38/3/883/7698199
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4589786
- https://ideas.repec.org/a/now/jnlcfr/104.00000122.html
- https://academicnewsletter.sufe.edu.cn/info/357702
- https://quantpedia.com/strategy-tags/earnings-announcement/

</details>

<details><summary>03-vcp-minervini-trend-template.md (39 URLs)</summary>

- https://www.minervini.com/
- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini
- https://www.businesswire.com/news/home/20220124005241/en/2021-United-States-Investing-Championship-Winners-%E2%80%94-Minervini-Smashes-Record
- https://prod-01.tunein.com/podcasts/Business--Economics-Podcasts/Investing-With-IBD-p1208776
- https://prorealcode.com/prorealtime-market-screeners/trend-template-mark-minervini
- https://actionalerts.substack.com/p/using-mark-minervinis-trend-template
- https://elitetrader.com/et/threads/mark-minervinis-trend-template-question.359356/post-5400824
- https://tikamalma.substack.com/p/understanding-basics-of-vcp-and-creating
- https://www.finermarketpoints.com/post/vcp-criteria-complete-checklist
- https://www.finermarketpoints.com/post/trade-like-stock-market-wizard-vcp-chapter
- https://www.finermarketpoints.com/post/what-is-mark-minervini-s-trading-strategy-the-complete-sepa-vcp-guide
- https://www.finermarketpoints.com/post/3-key-lessons-from-trade-like-a-stock-market-wizard
- https://www.finermarketpoints.com/post/mark-minervini-s-stock-screener-what-indicators-and-criteria-does-he-use
- https://deepvue.com/screener/how-mark-minervini-screens-for-stocks/
- https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-trend-template-marketsmith
- https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-8-keys-superperformance-vcp
- https://lilys.ai/notes/it/notebooklm-20251211/perfect-vcp-trading-setup-mark-minervini
- https://lilys.ai/de/notes/notebooklm-20251211/minervini-define-trading-style
- https://www.stockopedia.com/content/minervini-power-play-242073
- https://www.prorealcode.com/topic/power-play-screener-minervini/
- https://www.shortform.com/pdf/think-trade-like-a-champion-pdf-mark-minervini
- https://shortform.com/pdf/trade-like-a-stock-market-wizard-pdf-mark-minervini
- https://www.financialwisdomtv.com/post/mark-minervini-trade-think-like-a-champion
- https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing
- https://traderlion.com/investing-champions/mark-minervinis-risk-management/
- https://knowledge.sharescope.co.uk/2022/06/24/the-trader-what-can-we-learn-from-mark-minervini/
- https://tw.tradingview.com/chart/COIN/dRQXnzm3-Minervini-s-Specific-Exit-Criteria
- https://kr.tradingview.com/chart/FDMT/rWwozTF7-FDMT-VCP-Pattern
- https://www.screener.in/screens/602587/code-33-mark-minervini
- https://www.chartmill.com/stock/markets/usa/screener/minervini-stocks
- https://www.stage2stocks.com/learn/trend-template-and-stage-analysis
- https://daytrading.com/mark-minervini-momentum-strategies
- https://easyswing.trading/performance
- https://github.com/sofus-nl/swing-trading-strategies
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/01-vcp.md
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/16-trend-template-fresh-pass.md
- https://www.financialwisdomtv.com/post/can-one-chart-pattern-beat-the-market-i-tested-the-top-100-stocks
- https://sharpely.in/blogs/volatility-contraction-pattern-vcp-rule-based-screener-built-high-quality/
- https://www.nber.org/papers/w20439

</details>

<details><summary>04-chart-pattern-base-breakouts.md (63 URLs)</summary>

- https://www.chartpattern.com/
- https://www.chartpattern.com/chart-patterns.cfm
- https://www.chartpattern.com/cup-handle.cfm
- https://www.chartpattern.com/flat-base.cfm
- https://www.chartpattern.com/flags-pennants.cfm
- https://www.chartpattern.com/ascending-triangle.cfm
- https://www.chartpattern.com/10_golden_rules.html
- https://www.cmcmarkets.com/en-gb/opto/world-record-breaking-trader-dan-zangers-tricks-of-the-trade
- https://thepatternsite.com/cup.html
- https://thepatternsite.com/flags.html
- https://thepatternsite.com/htf.html
- https://thepatternsite.com/id75.html
- https://thepatternsite.com/FailureRates.html
- https://www.thepatternsite.com/BestPatterns.html
- https://www.thepatternsite.com/studystudy.html
- https://www.thepatternsite.com/rank.html
- https://thepatternsite.com/id84.html
- https://en.wikipedia.org/wiki/CAN_SLIM
- https://discussion.fool.com/t/ibd-8-week-hold-rule/112549
- https://discussion.fool.com/t/trading-ibd-stocks/104584?page=23
- https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker
- https://www.shortform.com/summary/how-to-make-money-in-stocks-summary-william-j-oneil
- https://www.luxalgo.com/library/concept/flat-base/
- https://www.luxalgo.com/library/concept/cup-with-handle-base/
- https://www.luxalgo.com/library/concept/oneil-base-analysis/
- https://traderlion.com/technical-analysis/the-flat-base-pattern/
- https://tradingresourcehub.substack.com/p/nuances-behind-dan-zanger
- https://www.financialwisdomtv.com/post/dan-zanger
- https://www.sahmcapital.com/news/content/from-10000-to-42-million-rejecting-complex-indicators-short-term-trading-legend-dan-zanger-creates-miracles-with-chart-patterns-2025-12-02
- https://skillsmp.com/creators/mahmoud20138/tradecraft/plugins-tradecraft-skills-dan-zanger-breakout-strategy
- https://sozai.app/transcript/powerful-swing-trading-setup-high-tight-flag/
- https://www.luxalgo.com/library/concept/high-tight-flag.md
- https://pod.wave.co/podcast/the-traderlion-podcast-8e50b654-7b23-4b2d-aca4-50a775c117e3
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://www.valuewalk.com/investors-business-daily-swingtrader/
- https://www.nber.org/papers/w7613
- https://www.cxoadvisory.com/technical-trading/classic-papers-returns-from-pattern-based-technical-analysis/
- https://ideas.repec.org/p/fip/fednrp/9414.html
- https://ideas.repec.org/a/oup/jfinec/v5yi2p243-265.html
- https://papers.ssrn.com/abstract=3756587
- https://www.cxoadvisory.com/technical-trading/machine-assisted-stock-price-pattern-analysis/
- https://datalearner.com/academic/journal-papers/0957-4174/volumes-and-issues/84/paper-detail/78518
- https://easyswing.trading/performance
- https://github.com/sofus-nl/swing-trading-strategies
- https://github.com/sofus-nl/swing-trading-strategies/blob/main/strategies/02-cup-and-handle.md
- https://www.liberatedstocktrader.com/cup-and-handle-pattern/
- https://www.nber.org/papers/w20439
- https://www.reddit.com/r/swingtrading/comments/1whb374/
- https://www.reddit.com/r/swingtrading/comments/1fy6c45/
- https://www.reddit.com/r/swingtrading/comments/1ukmnlh/
- https://www.reddit.com/r/swingtrading/comments/1rbg39l/
- https://www.reddit.com/r/Daytrading/comments/lag8zs/
- https://www.reddit.com/r/algotrading/comments/1q25jpe/
- https://traderlion.com/the-tml-talk/the-tml-report-february-20-2026-follow-through-day-next-week/
- https://traderlion.com/the-tml-talk/the-tml-report-april-2nd-2026-follow-through-day-this-week/
- https://traderlion.com/the-tml-talk/the-tml-report-april-7th-2026-market-coiling-below-key-resistance/
- https://newsletter.truemarketleader.net/p/market-outlook-6135
- https://markets.financialcontent.com/workboat/article/marketminute-2026-3-27-wall-streets-dark-friday-nasdaq-sinks-into-correction-as-five-week-rout-deepens
- https://insights.dsij.in/dsijarticledetail/march-2026-when-everything-fell-a-market-defined-by-broad-based-selling-id010-56215
- https://www.janushenderson.com/corporate/article/market-moves-themes-that-mattered-september-2026/
- https://continuumeconomics.com/a/0a0d0277/ai-equities-correctionconsolidation
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://briefedup.substack.com/p/october-2026-breakouts

</details>

<details><summary>05-qullamaggie-breakout.md (34 URLs)</summary>

- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://www.youtube.com/watch?v=xx8GvtAxilk
- https://qullamaggie.com/faq/
- https://qullamaggie.com/
- https://qullamaggie.com/some-good-tweetstorms/
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://chatwithtraders.com/212
- https://tradingresourcehub.substack.com/i/132995655/introduction
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-66-70-review
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-91-95-review
- https://tradingresourcehub.substack.com/p/momentum-vehicle-selection-and-studying-1000-hours
- https://tradingresourcehub.substack.com/t/qullamaggie-stream-notes
- https://www.financialwisdomtv.com/post/kristjan-qullamaggie-multi-millionaire-stock-trader-discloses-his-winning-strategy
- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups
- https://valuefund.substack.com/p/how-does-one-trader-turn-9100-into
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://stonkscapital.substack.com/p/modeling-kullamagi-part-2-momentum
- https://easyswing.trading/performance
- https://github.com/sofus-nl/swing-trading-strategies
- https://www.tradingview.com/script/cDCAPrd1-Qullamaggie-Breakout/
- https://www.luxalgo.com/library/indicator/5bTajWQM-qullamaggie-breakout-v2/
- https://www.tradingview.com/script/vOiC5X5k-QULLAMAGGIE-Trades-Database-2014-2022/
- https://it.tradingview.com/script/WogdhAJH-Qullamaggie-High-Tight-Flag-Table
- https://easyswing.trading/blog/qullamaggie-breakout-continuation-setup/
- https://deepvue.com/screener/qullamaggie-screens/
- https://www.ebc.com/forex/qullamaggie-strategy-3-trading-setups
- https://thepatternsite.com/htf.html
- https://thepatternsite.com/HTFStudy.html
- https://www.nber.org/papers/w20439
- https://www.cxoadvisory.com/1284/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks/
- https://www.nber.org/papers/w7613
- https://lilys.ai/es/notes/notebooklm-20251211/minervini-strategy-works-2025
- https://sponsorradar.com/channels/qullamaggie

</details>

<details><summary>06-breadth-regime-filters.md (50 URLs)</summary>

- https://articles.stockcharts.com/article/articles-arthurhill-2023-11-the-zweig-breadth-thrust-trigg-609/
- https://articles.stockcharts.com/article/articles-arthurhill-2025-03-two-ways-to-use-the-zweig-brea-495
- https://articles.stockcharts.com/article/zweig-breadth-thrust-sets-up-how-to-identify-a-stampede-in-upside-participation/
- https://trendinvestorpro.com/zweig-breadth-thrust-exit-strategy/
- https://sentimentrader.com/blog/a-cluster-of-breadth-thrusts-bodes-well-for-stocks
- https://sentimentrader.com/blog/recovery-in-200-day-average-breadth-shows-long-term-promise
- https://sentimentrader.com/blog/a-double-zweig-breadth-thrust-just-as-we-hit-the-worst-six-months
- https://sentimentrader.com/blog/a-failed-zweig-breadth-thrust-does-it-matter
- https://edgerater.com/blog/2026-05-06-market-notes-thrust-day
- https://articles.stockcharts.com/article/three-breadth-indicators-that-could-decide-the-next-market-move/
- https://articles.stockcharts.com/article/mindfulinvestor-2026-08-weakening-market-breadth-could-signal-trouble-ahead/
- https://thrasheranalytics.substack.com/p/breadth-update-852026
- https://www.thetrading.tools/market-breadth
- https://www.thetrading.tools/manuals/zweig-breadth-thrust
- https://michaelsincere.com/articles/my-marketwatch-interview-with-stock-market-wizard-mark-minervini
- https://world.hey.com/nitinranjan/weekly-index-check-cw18-2022-88b02ca6
- https://finallynitin.substack.com/p/stockbee-market-monitor
- https://www.prorealcode.com/topic/market-monitor/
- https://www.luxalgo.com/library/concept/breadth-thrusts.md
- https://x.com/StockCharts/status/1915856032959549529
- https://x.com/MebFaber/status/1920163146204930213
- https://247wallst.com/investing/2025/11/28/this-rare-perfect-market-indicator-just-flashed-a-major-bull-market-is-coming/
- https://stockbee.blogspot.com/2010/08/understanding-market-monitor-part1.html
- https://stockbee.blogspot.com/2011/08/how-to-use-market-breadth-to-avoid.html
- https://articles.stockcharts.com/article/articles-arthurhill-2018-10-systemtrader-a-rules-based-approach-for-when-to-cry-uncle/
- https://articles.stockcharts.com/article/articles-arthurhill-2025-05-moving-from-thrust-signals-to-882/
- https://articles.stockcharts.com/article/articles-arthurhill-2025-04-zweig-breadth-thrust-dominates-460/
- https://sherwood.news/markets/unusual-technical-indicator-with-perfect-track-record-sends-buy-signal-on-us
- https://www.fxstreet.com/news/sp-500-trust-the-thrust-202504301444
- https://sentimentrader.com/blog/zweig-breadth-thrust-recovery
- https://sentimentrader.com/blog/the-historical-implications-of-a-nasdaq-breadth-thrust
- https://sentimentrader.com/blog/here-come-the-breadth-thrust-buy-signals
- https://sentimentrader.com/blog/the-holy-grail-of-breadth-thrusts-has-triggered
- https://www.thetrading.tools/zweig-breadth-thrust
- https://www.mcoscillator.com/learning_center/weekly_chart/watching_for_a_zweig_breadth_thrust_signal/
- https://www.tradingview.com/script/M3p31Lpg-Zweig-Breadth-Thrust-ZBT-Complete-Validation/
- https://researchwith.montclair.edu/en/publications/the-use-of-index-specific-market-breadth-and-index-over-moving-av/
- https://www.cxoadvisory.com/?p=30213
- https://seekingalpha.com/article/4778098-bull-market-indicated-by-zweig-breadth-thrust-signal-trust-it
- https://www.investing.com/analysis/the-zweig-breadth-thrust-as-a-case-study-in-quantitative-analysis-267684
- https://articles.stockcharts.com/article/articles-tac-2015-10-tom-mcclellan-zweig-breadth-thrust-signal
- https://www.cxoadvisory.com/technical-trading/dual-momentum-with-multi-market-breadth-crash-protection
- https://quantifiedstrategies.substack.com/p/dual-momentum-investing-with-gary
- https://hedgefundalpha.com/strategies/is-gary-antonaccis-global-equity-momentum-strategy-robust/
- https://cryptobriefing.com/goldman-sachs-sp500-breadth-dotcom-low/
- https://www.bnnbloomberg.ca/investing/opinion/2026/10/01/us-and-canadian-stock-markets-have-bad-breadth-brooke-thackray/
- https://proactiveadvisormagazine.com/sp-500-update-market-breadth-improves-in-the-first-half-of-2026/
- https://247wallst.com/investing/2026/06/10/rsp-vs-spy-does-equal-weight-beat-the-cap-weighted-sp-500/
- https://www.thetrading.tools/equal-weight-vs-cap-weight
- https://www.fxcm.com/eu/insights/the-2026-market-rotation-suggests-a-quiet-shift-with-loud-implications/

</details>

<details><summary>07-canslim-ibd-market-school.md (77 URLs)</summary>

- https://www.aaii.com/files/journal/pdf/9874_william-oneil-can-slim-approach-to-selecting-growth-stocks.pdf
- https://www.aaii.com/journal/article/feature-the-can-slim-approach-revising-a-screen
- https://www.aaii.com/stockideas/article/10668-oneils-can-slim-revised-3rd-edition-approach
- https://en.wikipedia.org/wiki/CAN_SLIM
- https://finance.yahoo.com/news/day-tells-time-buy-stocks-215900253.html
- https://finance.yahoo.com/news/want-spot-market-tops-count-215400254.html
- https://finance.yahoo.com/news/time-stock-market-ibd-says-223000999.html
- https://finance.yahoo.com/news/know-invoke-8-week-hold-215800238.html
- https://finance.yahoo.com/news/identify-good-qualities-cup-handle-233000441.html
- https://finance.yahoo.com/news/using-20-sell-rule-help-200500142.html
- https://finance.yahoo.com/news/learn-profits-stock-rises-20-221100662.html
- https://finance.yahoo.com/news/profits-stock-rises-20-25-215900135.html
- https://www.nasdaq.com/articles/how-build-long-term-profits-stocks-take-many-gains-20-25-2017-10-25
- https://finance.yahoo.com/news/way-heed-sell-rules-even-213000178.html
- https://finance.yahoo.com/news/why-cutting-stock-losses-short-211000887.html
- https://finance.yahoo.com/news/investors-corner-sell-way-183200275.html
- https://finance.yahoo.com/news/own-ipo-stock-weigh-8-211500240.html
- https://finance.yahoo.com/news/dont-stray-slim-investing-rules-211300166.html
- https://finance.yahoo.com/news/watch-distribution-days-spot-peaks-220700524.html
- https://finance.yahoo.com/news/learn-wait-recognize-markets-day-230300058.html
- https://www.nasdaq.com/articles/how-do-you-spot-major-stock-market-top-heres-easy-way-2017-12-21
- https://finance.yahoo.com/news/big-picture-market-pulse-keep-202900058.html
- https://finance.yahoo.com/news/cup-handle-familiar-understand-key-203500768.html
- https://finance.yahoo.com/news/chart-pattern-star-power-simple-212700404.html
- https://finance.yahoo.com/news/shakeout-breakout-why-stocks-often-214400833.html
- https://finance.yahoo.com/news/draw-trend-line-chart-identify-213500214.html
- https://finance.yahoo.com/news/brief-pause-breakout-three-weeks-225000672.html
- https://finance.yahoo.com/news/why-saucer-handle-deliver-solid-223400739.html
- https://ca.finance.yahoo.com/news/key-step-studying-look-accumulation-205200634.html
- https://www.nasdaq.com/articles/chart-reading-basics-how-find-correct-buy-point-leading-stocks-2017-10-02
- https://www.nasdaq.com/article/principles-of-technical-analysis-the-cupandhandle-pattern-cm29628
- https://www.investors.com/category/market-trend/the-big-picture/
- https://www.investors.com/ibd-university/can-slim/
- https://www.investors.com/how-to-invest/when-to-sell-stocks/
- https://www.investors.com/how-to-invest/stock-market-timing-how-to-invest-in-stocks-tracking-bull-markets-bear-markets-stock-market-trends/
- https://www.investors.com/how-to-invest/how-to-handle-changing-stock-market-trends/
- https://it.tradingview.com/script/ZgQSYzJ3-IBD-Market-School-Professional/
- https://my.tradingview.com/script/0Bkxq34e-TTI-IBD-Market-School
- https://my.tradingview.com/chart/SPX/M5ukDElr-HOW-TO-TTI-IBD-Market-School
- https://vn.tradingview.com/script/sbzEKCNa-IBD-Market-School-tradeviZion
- https://www.tradingview.com/script/mrsKTQdQ-Distribution-Follow-Through-Day-Marker/
- https://discussion.fool.com/t/ibd-follow-through-day-definition/107779
- https://discussion.fool.com/t/ibd-market-school/112218
- https://discussion.fool.com/t/ibd-market-school/112218?page=6
- https://discussion.fool.com/t/ibd-market-school/112218?page=7
- https://discussion.fool.com/t/ibd-market-school/112218?page=8
- https://discussion.fool.com/t/ibd-market-school/112218/last
- https://discussion.fool.com/t/ibd-market-exposure-recommendation/108128
- https://discussion.fool.com/t/ibd-swing-trading/109412
- https://discussion.fool.com/t/ibd-technical-talk-with-mike-webster/104454
- https://discussion.fool.com/t/ibd-8-week-hold-rule/112549
- https://discussion.fool.com/t/trading-ibd-stocks/104584?page=23
- https://discussion.fool.com/t/trading-ibd-stocks/104584?page=17
- https://discussion.fool.com/t/does-ibd-offer-any-value-to-would-be-swing-traders/106504
- https://seekingalpha.com/instablog/195752-joshua-hayes/73173-a-quick-reminder-about-follow-through-days
- https://traderhq.com/investors-business-daily-swingtrader-review-stock-trading-technical-analysis/
- https://www.valuewalk.com/investors-business-daily-swingtrader/
- https://apps.apple.com/app/id1132694075
- https://sponsorradar.com/channels/investorsbusinessdaily
- https://nexusfi.com/d/platforms/deepvue/
- https://br.tradingview.com/scripts/ibd
- https://magica.com/youtube-summarizer/how-to-use-deepvue-to-apply-the-canslim-methodology-for-effective-stock-trading-2RuiIelL0MA
- https://www.shortform.com/summary/how-to-make-money-in-stocks-summary-william-j-oneil
- https://www.getrichslowly.org/canslim-investing/
- https://www.stockrover.com/blog/can-slim-investing-strategy/
- https://blog.marketsmithindia.com/?p=14301
- https://traderlion.com/fundamentals/return-on-equity/
- https://en.globes.co.il/en/article-1000291569
- https://stockanalysis.com/etf/ffty/
- https://stockanalysis.com/etf/compare/ffty-vs-spy/
- https://www.innovatoretfs.com/etf/?ticker=ffty
- https://easyswing.trading/performance
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://fortune.com/2026/04/08/markets-sp-trump-truce-ceasefire-iran-war-rally-strait-of-hormuz
- https://www.betashares.com.au/insights/liberation-day-upended-markets/
- https://www.nasdaq.com/articles/april-2025-review-and-outlook
- https://cdn.gam.com/it/our-thinking/multi-asset-blog/did-markets-get-liberation-day-all-wrong

</details>

<details><summary>08-anchored-vwap-multi-timeframe-shannon.md (52 URLs)</summary>

- https://alphatrends.net/
- https://alphatrends.net/anchored-vwap/
- https://alphatrends.net/dont-buy-the-dip-buy-strength-after-the-dip/
- https://alphatrends.net/only-price-pays/
- https://alphatrends.net/understanding-market-structure/
- https://alphatrends.net/swing-trading-guide/
- https://alphatrends.net/technical-analysis-multiple-timeframes/
- https://alphatrends.net/anchored-vwap-book/
- https://alphatrends.net/end-of-week-market-analysis/
- https://alphatrends.net/archives/analysis/stock-market-crypto-analysis-for-week-ending-9-25-26/
- https://alphatrends.net/archives/analysis/stock-market-video-analysis-for-week-ending-9-18-26/
- https://alphatrends.net/archives/analysis/stock-market-crypto-analysis-9-11-26/
- https://alphatrends.net/archives/podcast/brian-shannon-featured-in-discussion-on-anchored-vwap-and-market-structure/
- https://alphatrends.net/archives/podcast/brian-on-ninjatrader-05-18-25/
- https://alphatrends.net/archives/podcast/the-avwap-trading-indicator-secrets-and-setups-brian-shannon-traderlion-041523/
- https://alphatrends.net/archives/2023/03/interview-stockbsessed-03112023/
- https://alphatrends.net/archives/podcast/investing-with-the-whales-interview-brian-shannon-040323/
- https://alphatrends.net/archives/podcast/conversations-about-anchored-vwap-louis-llanes-03032023-2/
- https://members.alphatrends.net/new-users/
- https://twitter.com/alphatrends
- https://www.youtube.com/@alphatrends
- https://stocktwits.com/alphatrends
- https://www.amazon.com/Maximum-Trading-Gains-Anchored-VWAP/dp/B0BLZMMLLJ
- https://cmtassociation.org/podcast/fill-the-gap-episode-sixty-one-anchored-vwap-legend-brian-shannon-cmt/
- https://cmtassociation.buzzsprout.com/1551823/episodes/18757261-episode-61-anchored-vwap-legend-brian-shannon-cmt
- https://masteremail.podbean.com/e/stop-buying-the-dip-start-doing-this-instead-w-brian-shannon
- https://wolf.videonest.co/videos/2086744/anchored-vwap-and-moving-averages-full-breakout-st-BLF7bPpLuW
- https://investingwiththewhales.substack.com/p/brian-shannon
- https://www.financialwisdomtv.com/post/maximum-trading-gains-using-price-time-volume
- https://en.wikipedia.org/wiki/Brian_Shannon
- https://www.goodreads.com/book/show/5861135-technical-analysis-using-multiple-timeframes
- https://seekingalpha.com/article/134296-book-review-brian-shannon-s-technical-analysis-using-multiple-timeframes
- https://www.scribd.com/document/1008610992/Technical-Analysis-Using-Multiple-Timeframes-Report
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap
- https://www.luxalgo.com/library/concept/vwap-pinch/
- https://www.luxalgo.com/library/indicator/VYu6A3GB-anchored-vwap-pinch-handoff-intervals-and-signals/
- https://www.tradingview.com/scripts/brianshannon/
- https://www.tradingview.com/script/boJY0VmI-Brian-Shannon-5-Day-MA-Background/
- https://www.tradingview.com/script/L8cxNVC7-Multi-VWAP-MW/
- https://www.tradingview.com/script/mBkObMct-Multi-Day-Rolling-VWAP-Intraday/
- https://www.tradingview.com/script/EQBZI5Et-dc-Swing-Traders-Setup-v2/
- https://www.tradingview.com/script/VYu6A3GB-Anchored-VWAP-Pinch-Handoff-Intervals-and-Signals/
- https://www.tradingview.com/script/gjFSGRCo/
- https://il.tradingview.com/scripts/brianshannon/
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351
- https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/
- https://bearbulltraders.com/?p=2606339
- https://www.quantconnect.com/forum/discussion/16706
- https://efmaefm.org/0efmameetings/efma%20annual%20meetings/2012-Barcelona/papers/EFMA2012_0609_fullpaper.pdf
- https://www.traders.com/Documentation/FEEDbk_docs/2008/09/Abstracts_new/Coles/coles.html
- https://ayratmurtazin.beehiiv.com/p/i-tested-this-strategy-on-the-100-largest-us-companies-here-are-the-results
- https://alphatrade.readthedocs.io/en/latest/_vwap_2020.html

</details>

<details><summary>09-stockbee-momentum-burst.md (65 URLs)</summary>

- https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html
- https://stockbee.blogspot.com/2014/01/how-to-identify-good-momentum-burst-and.html
- https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-burst.html
- https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html
- https://stockbee.blogspot.com/2014/01/there-is-structural-phenomenon-in-market.html
- https://stockbee.blogspot.com/2014/01/buy-range-expansion-at-beginning-of.html
- https://stockbee.blogspot.com/2014/01/swing-trading-using-momentum-bursts.html
- https://stockbee.blogspot.com/2014/06/how-swing-traders-make-money.html
- https://stockbee.blogspot.com/2014/07/my-swing-trading-process-flow.html
- https://stockbee.blogspot.com/2014/08/how-i-get-market-monitor-numbers.html
- https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html
- https://stockbee.blogspot.com/2014/08/how-i-generate-my-breakout-anticipation.html
- https://stockbee.blogspot.com/2014/08/the-nature-of-swing-moves.html
- https://stockbee.blogspot.com/2014/08/trading-tools-i-use.html
- https://stockbee.blogspot.com/2014/09/right-entry-reduces-your-risk.html
- https://stockbee.blogspot.com/2015/01/stocks-will-move-in-momentum-bursts-in.html
- https://stockbee.blogspot.com/2015/01/momentum-burst-is-pattern-and.html
- https://stockbee.blogspot.com/2015/05/how-do-stock-move-on-3-to-5-day-time.html
- https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html
- https://stockbee.blogspot.com/2016/07/profiting-from-momentum-bursts.html
- https://stockbee.blogspot.com/2017/01/a-simple-scan-to-find-big-winners.html
- https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html
- https://stockbee.blogspot.com/2017/10/how-to-find-good-breakouts-daily.html
- https://stockbee.blogspot.com/2019/08/how-do-stocks-move.html
- https://stockbee.blogspot.com/2020/02/one-idea-which-can-make-you-lots-of.html
- https://stockbee.blogspot.com/2021/02/one-idea-which-can-make-you-millions.html
- https://stockbee.blogspot.com/2011/08/how-to-use-market-breadth-to-avoid.html
- https://stockbee.blogspot.com/p/mm.html
- https://stockbee.blogspot.com/2021/01/situational-awareness-and-t3a.html
- https://stockbee.blogspot.com/2024/01/for-high-win-rate-fix-situational.html
- https://stockbee.blogspot.com/2025/09/stockbee-tc2000-tabs.html
- https://stockbee.blogspot.com/2025/01/how-to-gauge-market-trend-using-guppy.html
- https://stockbee.blogspot.com/2025/04/methods-and-philosophy.html
- https://stockbee.blogspot.com/2026/05/two-market-wizards-have-come-from.html
- https://stockbee.blogspot.com/2026/06/market-wizard-factory.html
- https://stockbee.blogspot.com/2026/07/situational-awareness-for-july-20-2026.html
- https://stockbee.blogspot.com/2026/07/understand-market-breadth.html
- https://stockbee.blogspot.com/2026/07/trade-with-situational-awareness.html
- https://stockbee.blogspot.com/2026/09/november-2026-bootcamp-las-vegas.html
- https://stockbee.blogspot.com/search?q=momentum+burst
- https://stockbee.biz/bootcamp/november-2026-bootcamp/
- http://stockbee.biz/position-size-calculator/
- https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts
- https://retailtradersrepository.substack.com/p/pradeep-bonde-stock-examples
- https://tikamalma.substack.com/p/systems-setups-and-process-of-swing
- https://tikamalma.substack.com/p/4-momentum-burst-detailed-research
- https://fintwits-most-popular-stock-market-scans.onrender.com/canada/Stockbee/Breakout%201M%20Base_criteria.html
- https://trendsandbreakouts.com/stockbee
- https://www.tradingview.com/script/aUbyMkHj-Stockbee-Screener-Momentum-Burst-Episodic-Pivot-Scanner/
- https://www.luxalgo.com/library/indicator/aUbyMkHj-stockbee-screener-momentum-burst-episodic-pivot-scanner/
- https://www.luxalgo.com/library/indicator/6h74IRYK-stockbee-momentum-burst/
- https://www.tradingview.com/script/Rf67M40u-StockBee-MB-Bullish/
- https://www.tradingview.com/script/ZADkBsIl-StockBee-MB-Bullish/
- https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/stockbee-momentum-burst-screener
- https://www.investorsunderground.com/trading-takes-24/
- https://www.friendlybearpodcast.com/1782340/episodes/15777662-pradeep-stockbee-bonde-how-to-make-millions-swing-trading-momentum-burst-strategy-etc
- https://easyswing.trading/performance
- https://alphaarchitect.com/short-term-momentum/
- https://repec.cepr.org/repec/cpr/ceprdp/DP15857.pdf
- https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html
- https://breesefine7110.tulane.edu/wp-content/uploads/sites/16/2015/10/Weekly-Momentum-Kelly-and-Gutierrez.pdf
- https://ideas.repec.org/a/eee/jfinec/v106y2012i3p635-659.html
- https://academicnewsletter.sufe.edu.cn/info/357702
- https://www.firstfinancialtrust.com/2026/10/01/quarterly-market-review-july-september-2026/
- https://www.finra.org/rules-guidance/notices/26-10

</details>

<details><summary>10-parabolic-short-and-long-reversal.md (54 URLs)</summary>

- https://chatwithtraders.com/?p=3456
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-56-60-review
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-61-65-review
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-86-90-review
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream-092
- https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-Kristjan-Kullamagi-market-wizards-next-generation.pdf
- https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-Lance-Breitstein-market-wizards-next-generation.pdf
- https://completetradersedge.com/?p=233509
- https://www.harriman-house.com/authors/jack-d-schwager/market-wizards-the-next-generation/9781804093641
- https://harriman-house.com/market-wizards-pre-order-offer
- https://www.panmacmillan.com/authors/jack-d-schwager/market-wizards-the-next-generation/9781804093658
- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups
- https://wallstreettrader.substack.com/p/qullamaggies-trading-playbook-speed
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic?r=5igdr
- https://stonkscapital.substack.com/p/the-science-of-shorting-using-backtesting
- https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/parabolic-short-trade-planner
- https://skillselion.com/skills/tradermonty/claude-trading-skills/parabolic-short-trade-planner
- https://fr.tradingview.com/script/iQtlXxO8-Qullamaggie-Trading-System-Pro
- https://bearbulltraders.com/wp-content/uploads/2023/05/how-to-trade-parabolic-reversals-1.pdf
- https://www.tradezella.com/strategies/parabolic-short-strategy
- https://www.tradezella.com/strategies/small-cap-short-strategy
- https://curvedtrading.com/articles/en/trading/short-selling-penny-stocks/
- https://www.timothysykes.com/blog/first-red-day-pattern-trading/
- https://www.investorsunderground.com/short-selling-stocks/
- https://www.smallcaplab.com/research
- https://www.nber.org/system/files/working_papers/w23191/w23191.pdf
- https://shleifer.scholars.harvard.edu/publications/bubbles-fama
- https://ideas.repec.org:443/a/eee/jfinec/v131y2019i1p20-43.html
- https://www.nber.org/papers/w14804.pdf
- https://alphaarchitect.com/hot-off-the-jfe-press-maxing-out-your-returns/
- https://academicnewsletter.sufe.edu.cn/info/357702
- https://repository.upenn.edu/fnce_papers/387
- https://www.nber.org/papers/w20282
- https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/03/riggenberg.pdf
- https://nber.org/papers/w17653
- https://www.nber.org/papers/w20439
- https://www.bnnbloomberg.ca/business/2025/07/23/highly-shorted-krispy-kreme-gopro-jump-as-meme-stock-rally-continues/
- https://www.marketbeat.com/articles/investors-breathe-life-into-new-batch-of-meme-stocks-as-kohls-opendoor-technologies-surge-2025-07-22
- https://www.ig.com/sg/trading-strategies/2025/09/top-meme-stocks-to-watch
- https://www.fortune.com/2025/07/23/stock-market-records-meme-stock-krispy-kreme-gopro-beyond-meat/
- https://cointelegraph.com/news/crypto-markets-down-corporate-proxies-far-worse
- https://www.bloomberg.com/news/articles/2025-06-13/ethereum-treasury-firm-sharplink-plunges-69-on-routine-filing
- https://www.itiger.com/news/2578576504
- https://cryptobriefing.com/foreign-company-us-ipos-sec-crackdown/
- https://investing.com/news/stock-market-news/nasdaq-halts-ipos-of-small-chinese-companies-as-it-probes-stock-rallies-2918997
- https://news.bgov.com/financial-accounting/michael-burry-warns-of-stock-crash-as-tech-jump-echoes-2000-peak
- https://pro.thestreet.com/market-commentary/memory-stocks-go-parabolic-as-rotation-kicks-into-high-gear
- https://www.bloomberg.com/news/articles/2026-05-14/rally-in-top-space-stocks-sets-short-sellers-up-for-squeeze
- https://www.schaeffersresearch.com/content/analysis/2026/06/03/these-growth-stocks-are-ripe-for-a-short-squeeze
- https://www.advisorperspectives.com/articles/2026/05/11/retail-flooding-chipmaker-moves-extreme
- https://seekingalpha.com/article/4903272-chip-stocks-fomo-rally-why-this-could-signal-final-blow-off-top-for-bull-market
- https://www.itiger.com/hant/news/2512543184

</details>

<details><summary>11-rsi2-connors-mean-reversion.md (36 URLs)</summary>

- https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf
- https://alvarezquanttrading.com/blog/mean-reversion-vs-trend-following-through-the-years/
- https://alvarezquanttrading.com/blog/
- https://alvarezquanttrading.com/blog/the-power-of-strategy-diversification/
- https://alvarezquanttrading.com/blog/bad-month-for-your-strategy-should-you-change-it/
- https://alvarezquanttrading.com/blog/the-100-club-2000-tech-vs-2026-ai/
- https://bettersystemtrader.libsyn.com/037-quant-trader-cesar-alvarez-discusses-stop-losses-including-intraday-vs-eod-stops-volatility-vs-percentage-stops-trailing-stops-vs-targets-which-is-best
- https://ifta.org/2016/using-stops-the-good-the-bad-and-the-ugly
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/connorsrsi
- https://wl6.wealth-lab.com/Strategy/Details/254
- https://www.wealth-lab.com/Forum/Posts/ConnorsRSI-Pullback-System-32894
- https://www.whselfinvest.de/en-de/trading-platform/free-trading-strategies/tradingsystem/81-r3-larry-connors
- https://www.quantconnect.com/forum/discussion/18219/quot-the-alpha-formula-quot-mean-reversion-strategy-by-cabedovestment/
- https://www.luxalgo.com/library/concept/rsi-2/
- https://www.prorealcode.com/prorealtime-trading-strategies/cumulative-rsi-2-periods-strategy
- https://prorealcode.com/prorealtime-trading-strategies/rsi-2p-larry-connors/?pnum=13
- https://strategyquant.com/blog/larry-connors-double-7-strategy-tested-on-spy-and-8-other-markets/
- https://quantifiedstrategies.substack.com/p/larry-connors-r3-strategy-it-still-795
- https://quantifiedstrategies.substack.com/p/the-internal-bar-strength-ibs-indicator
- https://www.x-trader.net/tag/larry-connors
- https://cmtassociation.org/?p=76021
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100
- https://backtrex.com/en/backtests/connors-rsi-2-dax
- https://backtrex.com/en/backtests/connors-rsi-2-eur-usd
- https://www.cxoadvisory.com/technical-trading/a-few-notes-on-short-term-trading-strategies-that-work/
- https://backtest.substack.com/p/the-2-period-rsi-a-simple-system
- https://algotr.substack.com/p/this-simple-mean-reversion-strategy
- https://articles.stockcharts.com/article/articles-arthurhill-2018-10-systemtrader---update-to-rsi-mean-reversion-strategy-and-dealing-with-the-dreaded-drawdown/
- https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html
- https://ideas.repec.org/p/nbr/nberwo/17653.html
- https://openaccess.city.ac.uk/id/eprint/31278/
- https://repec.cepr.org/repec/cpr/ceprdp/DP15857.pdf
- https://alphaarchitect.com/short-term-momentum/
- https://arxiv.org/abs/2306.12434

</details>

<details><summary>12-kell-cycle-of-price-action.md (58 URLs)</summary>

- https://kelltrading.com/
- https://theswingreport.com/
- https://weeklieswatch.substack.com/
- https://weeklieswatch.substack.com/p/holding-weekly-moving-averages
- https://weeklieswatch.substack.com/p/mutombod-by-weekly-resistancewhat
- https://weeklieswatch.substack.com/p/nasdaq-daily-buy-signal-can-the-spx
- https://weeklieswatch.substack.com/p/can-we-get-some-proper-rest
- https://stockbsessed.substack.com/p/oliver-kell-interview-the-mind-and
- https://twitter.com/OliverKell_/status/1368286886268174337
- https://x.com/OliverKell_/status/1904264900354126284
- https://twitter.com/OliverKell_/status/1734317574559580306
- https://x.com/OliverKell_/status/1399356790429687812
- https://books.apple.com/us/book/victory-in-stock-trading/id1566661196
- https://play.google.com/store/books/details/Victory_in_Stock_Trading_Strategies_and_Tactics_of?id=QhctEAAAQBAJ&hl=en_US
- https://traderlion.com/technical-analysis/chart-patterns/cycle-of-price-action-by-oliver-kell/
- https://traderlion.com/technical-analysis/chart-patterns/cycle-price-action-oliver-kell/
- https://traderlion.com/technical-analysis/chart-patterns/wedge-pop-the-money-pattern/
- https://traderlion.com/technical-analysis/trading-the-ema-crossback/
- https://traderlion.com/technical-analysis/chart-patterns/ema-crossback/
- https://traderlion.com/technical-analysis/chart-patterns/base-n-break-how-to-catch-breakouts/
- https://traderlion.com/technical-analysis/chart-patterns/reversal-extension-how-stocks-bottom/
- https://traderlion.com/lesson/reversal-extension/
- https://traderlion.com/technical-analysis/chart-patterns/wedge-drop-how-to-sell-short/
- https://traderlion.com/technical-analysis/chart-patterns/downside-ema-crossback-sell-short-into-resistance/
- https://traderlion.com/technical-analysis/chart-patterns/downside-base-n-break-how-to-sell-short/
- https://traderlion.com/profile/oliver-kell/mu-wedge-pop/
- https://traderlion.com/profile/oliver-kell/amd-wedge-pop/
- https://traderlion.com/profile/oliver-kell/nvda-breakout-trade/
- https://traderlion.com/profile/oliver-kell/cava-breakout/
- https://traderlion.com/profile/oliver-kell/arm-reversal-extension/
- https://traderlion.com/profile/oliver-kell/coin-trendline-breakout/
- https://traderlion.com/courses/price-cycle-mastery-pro/lessons/oliver-kells-price-cycle-2/topic/wedge-pop/
- https://app.traderlion.com/university/price-cycle-mastery-pro
- https://university.traderlion.com/forums/discussion/tos-scanner-for-oliver-kells-wedge-pop-criteria/
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview
- https://tradingengineered.substack.com/p/the-four-trading-setups-of-a-us-investing
- https://tradingengineered.substack.com/p/market-analysis-and-10-principles
- https://www.financialwisdomtv.com/post/oliver-kell-us-investing-champion
- https://deepvue.com/screener/oliver-kell-screens/
- https://www.ebc.com/forex/oliver-kell-trading-strategy
- https://www.bowdoin.edu/news/2021/03/oliver-kell-10-wins-national-investment-contest-posting-nearly-tenfold-returns.html
- https://www.businesswire.com/news/home/20210125005140/en/U.S.-Investing-Championship-2020-Final-Standings
- https://nexusfi.com/d/education/traderlion/
- https://www.tradingview.com/script/GOkJ7o5J-Wedge-Pop-Drop-QuantVue
- https://www.tradingview.com/script/xHyBTcMq-Oliver-Kell-Cycle-of-Price-Action/
- https://id.tradingview.com/script/SmNMRIra-Oliver-Kell-Master-System/
- https://github.com/passiontrader/oliver-kell-price-action-rulebook
- https://www.scribd.com/document/969184904/Oliver-Kell-Trading-Strategy-PDF-by-Uday-Mandal
- https://www.scribd.com/document/1016453334/Oliver-Kell-941-Breakout-Strategy-Full-Tutorial-Gemini
- https://coconote.app/notes/3f9f64c0-cef5-4b18-8b04-dd8b87db923a
- https://www.quantifiedstrategies.com/20-ema-trading-strategy/
- https://ideas.repec.org/a/wly/revfec/v39y2021i2p127-145.html
- https://anderson-review.ucla.edu/wp-content/uploads/2021/03/Avramov-Kaplanski-Subra_2018_SSRN-id3111334.pdf
- https://alphaarchitect.com/moving-average-distance/
- https://www.nber.org/papers/w20439
- https://www.cxoadvisory.com/1284/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks/
- https://en.wikipedia.org/wiki/2025_stock_market_crash
- https://finance.yahoo.com/news/watch-qqq-price-levels-nasdaq-133121435.html

</details>

<details><summary>13-power-earnings-gap.md (35 URLs)</summary>

- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://www.oreilly.com/library/view/-/9781118283080/
- https://investors.wiley.com/news/news-details/2013/In-The-Trading-Cockpit-with-the-ONeil-Disciples-2013-1-2/default.aspx
- https://gale.com/ebooks/9781118283080
- https://www.thepatternsite.com/KacherMorales.html
- https://tw.tradingview.com/chart/GDOT/PpBPgj8G-GDOT-buyable-gap-up-BGU-example
- https://www.tradingview.com/script/wzFOH2TL
- https://scan.stockcharts.com/discussion/comment/2736/
- https://www.tradingview.com/script/KWTJ9jeC-Earnings-Gap-Ups/
- https://tw.tradingview.com/scripts/peg/
- https://usethinkscript.com/threads/power-earnings-gaps-peg-scanner-for-thinkorswim.82/
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://www.tradezella.com/blog/swing-trading-strategies
- https://retailtradersrepository.substack.com/p/marios-stamatoudis-the-traderlion-983
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots
- https://traderlion.com/profile/pradeep-bonde/episodic-pivots/
- https://investmentliteracycoach.beehiiv.com/p/overview
- https://tw.tradingview.com/script/DKiGBmFa-LevelUp-Power-Earnings-Gap-EPS-Acceleration-Screener
- https://tradingsim.com/blog/day-trading-earnings-gaps/
- https://papertradingjournal.com/2026/07/15/how-often-do-stocks-gap-up-vs-gap-down-after-earnings/
- https://www.anderson.ucla.edu/documents/areas/fac/finance/ear.pdf
- https://bpb-us-w2.wpmucdn.com/sites.udel.edu/dist/a/855/files/2020/07/Jump-on-the-Post%E2%80%93Earnings-Announcement-Drift.pdf
- https://ideas.repec.org/a/taf/ufajxx/v65y2009i4p18-32.html
- https://rpc.cfainstitute.org/research/financial-analysts-journal/2009/liquidity-and-the-post-earnings-announcement-drift
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf
- https://ideas.repec.org/a/now/jnlcfr/104.00000122.html
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://www.nber.org/papers/w13090
- https://quantpedia.com/strategies/post-earnings-announcement-effect
- https://www.sciencedirect.com/science/article/pii/S2214635020303750
- https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_080726.pdf
- https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_050826.pdf
- https://insight.factset.com/market-is-punishing-negative-eps-surprises-more-than-average-for-q1
- https://www.nasdaq.com/articles/breakaway-gap-why-its-top-setup-2026

</details>

<details><summary>14-insider-buy-superstocks-stine.md (39 URLs)</summary>

- https://www.jessestine.com/
- https://jessestine.com/investment-documentation/
- https://jessestine.com/25-shocking-highlights/
- https://jessestine.com/book-preview/
- http://jessestine.com/wp-content/uploads/2017/10/Final-Preview-19-pages1.pdf
- https://jessestine.com/reviews/
- https://www.goodreads.com/book/show/18012667
- https://insiderbuysuperstocks.weebly.com/
- https://insiderbuysuperstocks.weebly.com/the-elusive-superstock.html
- https://insiderbuysuperstocks.weebly.com/systems-and-simplicity.html
- https://www.financialwisdomtv.com/post/insider-buy-superstocks-by-jesse-stine
- https://tradingskeptic.com/insider-buy-superstocks-review/
- https://www.tradingreviewers.com/insider-buy-superstocks-review/
- https://threadreaderapp.com/thread/1028428610275819520.html
- https://www.tradingview.com/chart/AOI/Wl6SZ9WZ-Is-Alliance-One-a-Jesse-C-Stine-SuperStock
- https://in.tradingview.com/scripts/superstocks/
- https://www.tradingview.com/script/u0adR7NU-Superstock-10-30-WMA-Band-script/
- https://jelinbra.substack.com/p/scattered-focus-822
- https://x.com/rohaninvestor/status/1993210277295272060
- https://x.com/hb_stocks/status/2091382431043801550
- https://microcapclub.com/book-review-insider-buy-superstocks-by-jesse-stine/
- https://mopiglet.medium.com/insider-buy-superstocks-by-jesse-stine-73fe571b2593
- https://doi.org/10.1093/rfs/14.1.79
- https://academicnewsletter.sufe.edu.cn/info/355718
- https://papers.ssrn.com/abstract=1692517
- https://www.nber.org/digest/apr11/decoding-inside-information
- https://ideas.repec.org/a/cup/jfinqa/v48y2013i05p1433-1461_00.html
- https://quantpedia.com/strategy-tags/insider-trading-effect
- https://finance.yahoo.com/news/small-stock-index-recently-set-164242214.html
- https://www.vcm.com/assets/market-insights/Integrity-Monthly-Commentary-July-2026.pdf
- https://www.morningstar.com/news/marketwatch/20260630245/small-cap-stocks-just-had-their-best-start-to-a-year-since-1991-the-rest-of-2026-could-look-very-different
- https://www.regardsofwallstreet.com/news/russell-2000-record-high-small-caps-beating-nasdaq-100
- https://maandhunter.substack.com/p/the-reverse-split-escape-hatch-just
- https://www.kavout.com/market-lens/the-great-divide-why-reverse-stock-splits-dominate-the-market-in-mid-2026
- https://arkolith.com/blog/insider-buying-clusters-june-2026
- https://www.heygotrade.com/en/blog/insider-buying-april-2026-growth-stocks/
- https://traderlion.com/trading-strategies/stage-analysis/
- https://deepvue.com/indicators/stage-analysis-indicator/
- https://tradingmomentum.substack.com/p/stan-weinsteins-stage-analysis-the

</details>

### D. Checked live for this synthesis (2026-10-06)

- https://www.firstfinancialtrust.com/2026/10/01/quarterly-market-review-july-september-2026/ (Q3 2026 index returns)
- https://stockanalysis.com/etf/spy/ (SPY close 2026-10-06)
- https://thepatternsite.com/ (banner figure not visible on fetch; 7,819 / +14.2% YTD stays unverified)

## Fact-check (2026-10-06)

Adversarial check of the 12 most consequential claims in the deep dives.

- **confirmed**: FINRA eliminated the PDT designation and the $25k minimum, effective 4 Jun 2026 (doc 09).  
  Evidence: FINRA RN 26-10 (20 Apr 2026): replaced by intraday margin standards, effective 4 Jun 2026; phase-in runs to 20 Oct 2027 (doc 09 omits this). https://www.finra.org/rules-guidance/notices/26-10
- **confirmed**: 6 Oct 2026: S&P 7,819, +14.2% YTD. Q3 2026: S&P +2.03%, R2K -7.52%, 10y +88bp to 5.29%. R2K ~+19% YTD to 31 Jul (docs 04/09/14).  
  Evidence: Yahoo chart API: 7,818.93 (+14.22%); Q3 +2.03% / -7.52%; R2K +18.1% YTD to 31 Jul. Treasury par 10y: 5.29 on 9/30 vs 4.44 on 6/30, so +85bp, not +88. https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value_month=202609
- **confirmed**: 6 Oct 2026: 26.9% of 4,806 US stocks above the 50-day, 39.7% above the 200-day (docs 01/04/06).  
  Evidence: thetrading.tools shows 48.5/26.9/33.6/39.7% across 4,806 stocks. One vendor only, not independently reproduced. https://www.thetrading.tools/market-breadth
- **confirmed**: Fed raised rates on 16 Sep 2026 under Chair Warsh (doc 07).  
  Evidence: FOMC raised 25bp to 3.75-4.00%, 12-0 vote; the Board page lists Kevin Warsh as Chairman. https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm
- **refuted**: '10-year yield at records above 5% (14 and 28 Sep)' (doc 07).  
  Evidence: Treasury par 10y: 4.97% on 14 Sep (below 5%), 5.24% on 28 Sep, month high 5.29% on 30 Sep. Not a record. Treasury daily par-yield CSV (2026).
- **unverifiable**: IBD follow-through days on 22 Apr 2025 (Day 11) and 8 Apr 2026 (Day 6) (doc 07).  
  Evidence: investors.com fetch blocked. Yahoo index data fits: 22 Apr 2025 Nasdaq +2.71%, S&P +2.51% on higher volume; 8 Apr 2026 is Day 6, S&P +2.51% on higher volume, Nasdaq +2.80%. The doc's '+2.2%' matches neither.
- **confirmed**: USIC: Minervini +334.8% (2021, $1M+ division) and +155% (1997); Kell +941.1% (2020) (docs 03/12).  
  Evidence: Business Wire 403. Secondary quote of the release: https://wallstreettrader.substack.com/p/how-mark-minervini-won-us-investing . Kell's figure (2nd place +497%) is from his own newsletter: https://theswingreport.com/ . Kell's '<$1M' division is unverified.
- **confirmed**: Qullamaggie FAQ: risk 0.3-0.5% (rarely >1%), size 5-25%, 25% win rate (2019), 268% CAGR 2013-19, 50% drawdown (2014) (doc 05).  
  Evidence: All appear verbatim; self-reported and unaudited. https://qullamaggie.com/faq/
- **confirmed**: PEAD decay: Martineau (CFR) finds no large-cap PEAD since 2006; Subrahmanyam t=2.18 all stocks, 1.43 ex-microcaps (docs 02/13).  
  Evidence: Martineau's abstract says this. UCLA Anderson Review (21 Jan 2026) gives the 2001-2024 sample and t 2.18/1.43; the paper is 2025, but the docs date it 2025 and 2026 inconsistently. https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- **confirmed**: Bulkowski cup with handle: rank 3/39, 5% failure, +54%, 62% throwback, 61% hit target, 913 perfect trades (doc 04).  
  Evidence: All match. The page says examples were added 7/25/25 (doc 04 says 10/25/2025). Perfect-trade stats, no stops or costs. https://thepatternsite.com/cup.html
- **confirmed**: EasySwing panel 7 Jul 2026 (~2,000 stocks, 5-yr walk-forward, no fees): Pullback PF 1.45, VCP 0.38, Template 0.99, C&H 1.57, Qullamaggie 1.10.  
  Evidence: Win rates, R, PFs and holds match (17 detectors). Trade counts (1,092, 16,943, etc.) were not visible in the fetch and are unverified. Vendor data, gross of costs. https://easyswing.trading/performance
- **confirmed**: Zweig thrust: 38% on 10 Apr 2025 to 61.7% at the 24 Apr 2025 close; Detrick '19 for 19' higher at 6 and 12 months (doc 06).  
  Evidence: Sherwood News (25 Apr 2025) gives the rule, the readings and Detrick's record. S&P closed at 5,484.77 that day (Yahoo), matching doc 06. https://sherwood.news/markets/unusual-technical-indicator-with-perfect-track-record-sends-buy-signal-on-us

## Optimization and overfitting controls (2026-10 research)

Why this matters here: `docs/leaderboard.md` has no survivors over 750 trials. Before adding more strategies,
the tests themselves need to be right. They should be strict where it counts (selection, costs) and not
needlessly strict where trials overlap. Code references are to `swing_engine/research/metrics.py`
(`metrics`), `research/leaderboard.py` (`leaderboard`), `research/cards.py` (`cards`), `research/cv.py` and
`risk/`.

### 1. Selection-bias tests

**Deflated Sharpe ratio** (Bailey and Lopez de Prado 2014, JPM 40(5) 94-107;
https://papers.ssrn.com/abstract=2460551). This is the probabilistic Sharpe ratio measured against the
expected maximum Sharpe of N zero-skill trials. It also corrects for skew and kurtosis.
- Implemented: `metrics.deflated_sharpe`, `probabilistic_sharpe`, `expected_max_sharpe`, and
  `multiple_testing` (counts ALL logged trials, per gate 2).
- Missing: (a) `sharpe_var` defaults to `1/n_obs`, the null estimator variance. The paper's input is the
  variance of Sharpe ratios across the trials actually run. The leaderboard already holds 750 trial Sharpes,
  so pass their variance. (b) The leaderboard reports only the Harvey-Liu haircut. Add a DSR column computed
  from the block-return series that the t-stat already uses.

**Probability of backtest overfitting via CSCV** (Bailey, Borwein, Lopez de Prado and Zhu 2017, J. Comp.
Finance 20(4); https://papers.ssrn.com/abstract=2326253 ; open copy
https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf). Split the time-by-trials return matrix into S
blocks. For every half/half split, check where the in-sample winner ranks out of sample. PBO is the share of
splits where it lands below the median.
- Implemented: `metrics.probability_backtest_overfit` (default 16 partitions, logits, degradation slope).
- Missing: nothing calls it. The leaderboard can build the matrix itself: one column per (strategy,
  horizon), one row per h-session block on a shared calendar, net R block means, and 0 where a strategy did
  not trade. Report PBO for the whole board and for each family (Connors variants, breakouts). A PBO above 0.5
  means picking the best leaderboard row is worse than picking at random.

**White's Reality Check** (White 2000, Econometrica 68(5) 1097-1126; https://doi.org/10.1111/1468-0262.00152)
and **Hansen's SPA test** (Hansen 2005, JBES 23, 365-380; https://ideas.repec.org/a/bes/jnlbes/v23y2005p365-380.html).
These test whether the best of many strategies beats a benchmark, using a bootstrap of the joint return
series. SPA studentizes and removes clearly bad strategies from the null, so it is less conservative than RC.
The stepwise version (Romano and Wolf 2005, Econometrica 73(4) 1237-1282;
https://www.econometricsociety.org/publications/econometrica/browse/2005/07/01/stepwise-multiple-testing-formalized-data-snooping)
names which strategies pass, not only whether the best does.
- Missing entirely. This is the most useful addition. The board's 750 trials are highly correlated (the
  Connors/RSI-2 family, many breakout variants, 3 horizons of the same signal). Bonferroni treats them as
  750 independent looks, which over-penalizes. A stationary block bootstrap of the block-return matrix above
  captures the dependence. Use the same matrix as PBO, with a benchmark of 0 net R per block. Gate 2 stays
  as written. RC/SPA is an extra test, not a looser replacement for the haircut.

**Harvey-Liu-Zhu multiple-testing hurdle and the Harvey-Liu haircut.** HLZ (2016, RFS 29(1) 5-68;
https://papers.ssrn.com/abstract=2513152) argue a new factor needs a t-statistic above 3.0. Harvey and Liu
(2015, JPM; https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF) give three
p-value adjustments: Bonferroni (inflates every p-value by M), Holm (step-down), and BHY (false-discovery
rate, which tolerates more false discoveries as M grows). They convert the adjusted p-value back into a
haircut Sharpe.
- Implemented: `metrics.haircut_sharpe` (Bonferroni, the strictest); `leaderboard.edge_stats` applies it to
  every row with `n_trials = max(logged, strategies x horizons x windows)`.
- Missing: Holm and BHY. Both are a few lines on the sorted p-values of the whole board. Show all three. A
  strategy that passes BHY and RC/SPA but not Bonferroni is a candidate for forward paper testing, not for
  enabling.

### 2. Robust parameter selection

- **Plateaus over peaks.** Pick parameters from the middle of a flat, high region of the grid, not the
  single best cell. This is a practitioner rule (Pardo, *The Evaluation and Optimization of Trading
  Strategies*, Wiley 2008; https://www.wiley-vch.de/en/areas-interest/finance-economics-law/the-evaluation-and-optimization-of-trading-strategies-978-0-470-12801-5).
  It has no formal test, but CSCV makes it measurable: a peak shows a steep negative IS-to-OOS degradation
  slope. Engine: not implemented. For any sweep, also log the grid neighbours' net R, and require the chosen
  cell to exceed the neighbour median by less than its own standard error.
- **Walk-forward efficiency** (out-of-sample over in-sample performance). The term is a practitioner one
  associated with Pardo. Walk-forward itself is described at https://en.wikipedia.org/wiki/Walk_forward_optimization ;
  the exact ratio definition was not verified in Pardo's text. Engine: `research/cv.py` has
  `purged_walk_forward`, `purged_kfold` and CPCV splitters, and the `walk-forward` skill uses them. Missing:
  a stored IS/OOS ratio per walk-forward run in the trial log. `metrics.probability_backtest_overfit` already
  returns a `degradation_slope` that serves the same purpose.
- **Monte Carlo trade reshuffling** (practitioner). Shuffling the order of closed trades changes the path,
  not the mean. It gives a drawdown and risk-of-ruin distribution and says nothing about whether the edge is
  real. Use it only for sizing (for example, the 95th percentile drawdown sets `max_drawdown` kill criteria,
  gate 4). For the edge question, use a block bootstrap of returns (RC/SPA above). Engine: not implemented.

### 3. Sizing and portfolio construction for many weak signals

- **Volatility targeting.** Moreira and Muir (2017, JF 72(4) 1611-1644; https://www.nber.org/papers/22208)
  find that scaling factor exposure down when volatility is high raises Sharpe ratios. Barroso and Santa-Clara
  (2015, JFE 116(1) 111-120; https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html) report that
  risk-managed momentum "virtually eliminates crashes and nearly doubles the Sharpe ratio". Counter-evidence:
  Cederburg, O'Doherty, Wang and Yan (2020, JFE 138, 95-117; https://www.lehigh.edu/~xuy219/research/COWY.pdf)
  find that across 103 strategies, real-time volatility-managed versions do not systematically beat the
  unmanaged ones. Engine: per-position `vol_target_annual_pct` and book-level `book_vol_scale` (off by
  default, `risk/sizing.py`). Treat it as a drawdown control, judged on drawdown, and do not count it as
  alpha.
- **Signal combination.** Chen and Velikov (2023, JFQA 58(3) 968-1004;
  https://www.federalreserve.gov/econres/feds/zeroing-in-on-the-expected-returns-of-anomalies.htm) find that
  after spreads and post-publication decay, the average anomaly nets 4 bps/month, the strongest about 10 bps,
  and combinations of anomalies about 20 bps. Combining beats picking. Engine: each strategy is scored alone.
  The LightGBM ranker in `research/` is the place for combination. A cheaper step is a z-scored composite of
  the top-t board rows, tested as ONE new trial. That is one look instead of 125.
- **Correlation-aware caps.** Many signals fire on the same names on the same day (the RSI-2 family, for
  example). Engine: sector exposure caps (`risk/limits.sector_exposure_dollars`), Turtle unit limits, and rank
  hysteresis (`risk/selection.py`, Novy-Marx and Velikov 2016 buy/hold spread). Missing: a cap per
  correlation cluster (one symbol counted once across strategies, and a limit on summed risk across names
  whose 60-day return correlation exceeds a threshold, set in `settings.yaml`).
- **Turnover.** Novy-Marx and Velikov (2016, RFS 29(1) 104-147;
  https://ideas.repec.org/a/oup/rfinst/v29y2016i1p104-147..html) find the buy/hold spread is the most
  effective simple cost mitigation, and few high-turnover anomalies survive costs. Most board strategies hold
  5-20 sessions, which is high turnover by their standard.

### 4. Realistic retail cost modelling on Alpaca

- **Regulatory fees.** SEC Section 31 is $20.60 per $1M sold from 2026-04-04. It was $0.00 before that date in
  FY2026, and the rate holds until 60 days after the FY2027 appropriation
  (https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2). FINRA TAF is $0.000195/share, capped at
  $9.79 per trade, from 2026-01-01, per broker fee schedules (https://www.investrade.com/fees/). FINRA's own
  rulebook page still showed $0.000166 / $8.30 when fetched
  (https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees),
  so recheck it. Alpaca charges both on sells only, rounded up to the cent, plus a pass-through CAT fee per
  executed share (https://alpaca.markets/support/regulatory-fees). The 2026 CAT rate of $0.000001 per
  executed equivalent share comes from a secondary summary of exchange filings
  (https://policyrisk.com/federal-register/2026-09860). Engine: `backtest.CostModel` has SEC and TAF with the
  2026 numbers. CAT is negligible. All of these are tiny next to spread.
- **Spread and slippage dominate.** Engine: `backtest.py` uses 10 bps per side for large caps and 20 bps
  otherwise (gate 1). But `cards.cost_r`, which every leaderboard number uses, charges a flat
  `NET_SLIPPAGE_BPS_PER_SIDE = 10` to every signal regardless of price or liquidity. That understates costs for
  small and low-priced names, which is exactly where the mean-reversion rows (RSI-2, Connors, IBS) trade.
  Fix: per-signal spread estimates from our own daily OHLC, with EDGE (Ardia, Guidotti and Kroencke 2024, JFE
  161, 103916; https://ftp.fau.de/cran/web/packages/bidask/readme/README.html), Abdi-Ranaldo (2017, RFS
  30(12) 4437-4480; https://ideas.repec.org/d/g/sbfsgch.html) or Corwin-Schultz (2012, JF;
  https://projects.nber.org/confer/2009/mms09/Corwin_Schultz.pdf). Charge half the estimated spread plus an
  impact term per side, floored at the gate 1 numbers. Buckets: price (<$5, $5-20, >$20) x 20-day dollar
  volume tercile. Report net R by bucket on the board. This adds no trials and is the cheapest honesty fix
  available.
- **Payment for order flow.** Alpaca routes to wholesalers and receives revenue from liquidity providers
  based on order flow, per its Rule 606 report
  (https://files.alpaca.markets/disclosures/library/SEC+606a1+-+2026Q1.pdf; per-100-share amounts not
  extracted here). Schwarz, Barber, Huang, Jorion and Odean (2025, JF 80(5) 2507-2541;
  https://papers.ssrn.com/abstract=4189239) ran about 85,000 simultaneous market orders. Round-trip costs
  excluding commissions ranged from about 0.07% to 0.46% across brokers, and PFOF did not explain the
  difference. Implications: (a) paper fills on Alpaca are simulated and do not show the actual wholesaler
  price, so gate 1's modelled costs must stay in force for paper P&L; (b) once live, log the arrival quote
  next to every fill (`execution/`) and calibrate the bucket costs to realised slippage; (c) at-the-open
  market entries (the engine default) meet the widest spreads of the day, so marketable limit orders deserve
  a test.

**Order of work, by expected effect on the board.** (1) Per-signal spread costs in `cards.cost_r`. (2) A
block-return matrix in the leaderboard, feeding PBO, RC/SPA, DSR with real `sharpe_var`, and Holm/BHY
columns. (3) Correlation-cluster caps. (4) A single composite-signal trial. Steps 1-2 will probably confirm
"no survivors". Their value is that a survivor found after they are in place can be believed.

## Event avoid filters and the no-news flag (2026-10-09)

Data: `eightk_items` and `sched13d` (`swing ingest-edgar`, or `--8k-only`) and `news_articles` (`swing ingest-news`,
Alpaca/Benzinga headline counts), joined by `data.fundamentals.join_edgar`. Every clock is keyed on EDGAR acceptance time
or the article's first-publication time, rolled to the first session whose close can react.

- **Avoid filter (general form).** Skip a long entry when `days_since_<event> < N` for an event that signals a
  credibility or information shock: 8-K Item 4.02 non-reliance (restatement) is the shown case
  (`pullback_trend_avoid_402`, N = 63 sessions, engine choice). Evidence for 4.02 covers the announcement reaction
  (Palmrose, Richardson and Scholz 2004, about -9% over two days, abstract), not a later drift, so the filter is a
  risk control to be judged on drawdown and losers removed, not on raising the mean. Do not add it as a param to
  every long strategy: each strategy x filter pair is a trial, and the haircut grows with them. Add it to one
  strategy at a time as a named variant, and only promote it if that variant beats its base in both windows.
- **No-news filter.** Mean-reversion entries only on sessions with no news (`news_flag_1d == 0`; fallback
  `news_8k_flag_1d == 0`), after Chan (2003): no-news moves tend to reverse, news moves drift. Built as
  `<base>_no_news` for the three mean-reversion strategies with the most leaderboard signals. Unknown coverage never
  counts as "no news".
- **Event entries.** `activist_13d_drift` buys the session after an original 13D is public (Brav et al. 2008); its
  card derives the tradable post-filing part (about 2% gross over ~18 sessions in 2001-2006) and halves it.
