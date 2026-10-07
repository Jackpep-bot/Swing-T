# 01 — Pullback to the 20/50 MA in an uptrend (EMA zone, SMA bounce, Holy Grail ADX, Landry, buy-the-dip)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Tags: "(primary)" = the teacher's own book, site,
interview or course page; "(secondary)" = a third-party restatement, review or replication; "(unverified)" = could
not be checked against a primary source in this run (the claim is kept because it is widely repeated, but do not
code it as "the rule" without checking).*

**One line.** In a stock that is already trending up (price above a rising 50-day MA, short MA above long MA, often
a leader near its highs), wait for a 2–7 bar dip on lighter volume into the 20-day EMA/SMA (or the 20–50 "zone"),
then buy when price turns back up through the high of the touch/pivot bar; stop just under the pullback low
(or ~1.5–2 ATR); take part at the prior swing high or ~2R and trail the rest under the 20- or 50-day MA.

**Lineage.** The oldest, most widely taught swing setup. Codified as Raschke & Connors' "Holy Grail" (ADX + 20 EMA,
*Street Smarts*, 1995), Dave Landry's pullbacks/trend qualifiers (*Dave Landry on Swing Trading*, 2000; *10 Best
Swing Trading Patterns & Strategies*, 2003), and repeated in modern retail form by Rayner Teo (20/50 EMA zone),
Steve Burns (10-day EMA pullbacks near 52-week highs), Oliver Kell (EMA Crossback, 10/20 EMA), Brian Shannon
(5-day MA / AVWAP, see method 08) and Qullamaggie (uses the same 10/20-day MAs for exits, see method 05).
Academic cousin: medium-term momentum + short-term (1-month) reversal (Jegadeesh 1990; Novy-Marx 2012;
Dimensional 2023).

**Important caveat up front.** Every teacher uses a *different* MA (5/10/20/21/50; EMA vs SMA), trigger and
exit. There is no single canonical rule set; "pullback to the 20/50" is a family. The variants agree on the
structure (trend filter → shallow, quiet dip to a rising average → reversal trigger → stop under the dip) and
disagree on every number. The composite below states where each number comes from.

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| Trend qualifier (MA structure) | 10-SMA > 20-EMA > 30-EMA = "Proper Order" uptrend; yellow = neither | Landry, StockCharts ACP "Trading Simplified" plug-in docs (primary-adjacent: vendor docs of his indicators) |
| Trend qualifier (bar vs MA) | "low for a price bar is above the specified moving average" = uptrend; default **50-period SMA**, reference line 40 | Landry Light, same docs |
| Trend qualifier (ADX) | 14-period ADX "initially above 30 and rising" | Raschke/Connors *Street Smarts* via tradingsetupsreview.com and investingLive (secondary restatements of the book) |
| Trend qualifier (ADX, Landry) | "ADX reading of 30 or higher with +ADX > -ADX denotes a strong uptrend" | attributed to *Dave Landry on Swing Trading* in a web-search summary (unverified) |
| Recent high | Stock "makes a new two-month high" before pulling back | Landry-style rule quoted on a StockCharts scan forum (unverified; page unreachable this run) |
| Long-term filter | "above 200 EMA on daily" | TradeZella blog, 31 Mar 2026 (secondary/educational) |
| MA zone | "Use the 20 and 50 EMA on trending charts"; "Price must respect the EMA zone at least twice" | Rayner Teo, via Financial Wisdom TV course review, 7 Dec 2024 (secondary) |
| Near highs | Buys "stocks that are close to the 52-week highs" on pullbacks to the 10-day EMA | Steve Burns, MoneyShow interview 4 Jan 2012 (primary interview) |
| Relative strength | RS rank ≥ 96 (top 4% of universe); price > SMA50; EMA20 > SMA50, both rising | EasySwing / sofus-nl "Trend Pullback (EMA20/SMA50)" spec (secondary, vendor) |
| 52-week-high proximity variant | Within 5% of 52-week high before the dip; dip 3–10% over 3–10 bars on declining volume; holds above rising EMA21/SMA50 | sofus-nl "Proximity Pullback" spec, citing George & Hwang (2004) (secondary) |
| Liquidity | Not specified by most teachers; Burns: "high liquidity and volume" | MoneyShow 2012 (primary) |

**Practical scan (composite, for swing-engine):** price ≥ $5, 20-day $-volume ≥ $5M; `close > sma_50 > sma_200`
and `sma_50` rising (= `trend_state == 1`); 63-day return in the top 10–20% of the universe (optionally top 4% per
EasySwing); within ~10% of the 52-week high; low of the last 1–5 bars within ~1% (or ≤ 1 ATR) of the 20-day
EMA/SMA, or inside the 20–50 band.

### Market filter
- Burns: the **200-day MA on SPY** as the overall-market gate (MoneyShow 2012, primary).
- EasySwing: "Bull market or constructive range" (vendor spec, secondary); proximity variant "Bull market required".
- TradeZella: win rate below 50% "suggests" chop or stocks lacking a clear weekly uptrend (secondary).
- Raschke/Connors and Landry treat the filter at the instrument level (ADX/Proper Order) rather than an index gate.
- swing-engine equivalent: `market_trend_state` (SPY close > SMA50 > SMA200 with SMA50 rising) and
  `market_vol_regime`; plus breadth (method 06) — e.g. require % of universe above the 50-day ≥ 40–50%.

### Entry
| Variant | Trigger | Source |
|---|---|---|
| Holy Grail | After ADX > 30 and price retraces to touch the 20 EMA: "Place a buying order above the high of the candlestick" that touched it (buy stop) | investingLive (Gurkovskiy, 29 Mar 2021); tradingsetupsreview says 20 **SMA** — the book's MA type differs across restatements (secondary) |
| Landry pullback | Correction of **≥ 2 bars making lower lows**, then buy when price trades above the prior bar's high; scan-forum version: 2–7 day dip with lower highs, buy 10 cents above the pivot bar high | TradingView "Pullbacks Completo" (secondary reproduction); StockCharts forum (unverified) |
| Rayner Teo zone | "Enter on the third pullback into the EMA zone" (20–50 EMA) | FWTV review 2024 (secondary) |
| TradeZella 2026 | Price "within 2% of 20 EMA", RSI(14) "between 40-55", pullback volume "below 20-day average", reversal candle at the 20 EMA; enter at the reversal candle close "or break of candle's high next day" | TradeZella, 31 Mar 2026 (secondary) |
| EasySwing | Price within **1 ATR** of EMA20 (preferred) or SMA50; bounce candle closes in upper half of its range on volume > 20-day average | sofus-nl spec (secondary) |
| Kell EMA Crossback | First pullback to the **10- or 20-day EMA** after a strong rally off the lows (after the "wedge pop"); buy as price stabilises at the EMAs | TraderLion articles (pages returned 403; content from search snippets — unverified detail) |
| Burns | Pullback to "at least" the **10-day EMA** in a stock near 52-week highs | MoneyShow 2012 (primary) |
| Shannon | Pullback toward a rising 5-day MA / AVWAP, trigger on intraday higher-low + reclaim | see method 08 |

### Stop
- Holy Grail: stop "below its low" (the touch bar) — investingLive; most restatements: below the newly formed swing low.
- Landry (forum version): 35 cents under the pivot bar low (unverified, dollar-based, dated).
- Rayner Teo: "Set stop-loss at 2× ATR at entry" (≈ 5.4% on his worked example); a TradingView script modelled on
  his settings draws **1.5 × ATR(20)** (secondary).
- TradeZella: "below the low of the reversal candle, or below 20 EMA by 1.5%. Whichever is smaller."
- EasySwing: "1.5x ATR below entry OR below EMA20, whichever is tighter."
- swing-engine `pullback_trend` today: pullback low − 0.1 × ATR(14).

### Exits and targets
| Variant | Exit | Source |
|---|---|---|
| Holy Grail | Target = retest of the prior swing high (investingLive: "slightly below the highest local high" after the pullback); optionally trail the stop | secondary restatements |
| Landry "2-for-1" | Take half off when open profit = initial risk, stop to breakeven, trail the rest | book rule per sweep notes (unverified online this run) |
| Rayner Teo | No fixed target; "Exit when price closes beyond the 50 EMA"; "Don't rush stops to breakeven" | FWTV 2024 (secondary) |
| TradeZella | First target = most recent swing high, then stop to breakeven; exit on "price closes below 20 EMA for two consecutive days" | TradeZella 2026 |
| EasySwing | Scale 50% at +2.0 ATR; trail the rest under swing lows or 1.5 ATR from highs; hard exit on two consecutive closes below SMA50 | sofus-nl spec |
| Burns | Trailing stop on a rising MA; exit on a break of the 5- or 10-day EMA | MoneyShow 2012 (primary) |
| Raschke (general) | Exit winners that give back ~20% from peak; never average losses | Antoine Buteau's notes on Raschke (secondary; from the sweep, not re-fetched) |

### Position sizing
- Rayner Teo: risk "no more than 1% of capital per trade" (secondary). Burns: "never risk more than 1% of your
  total capital on any one trade" (primary). Raschke/Landry: fixed-fractional risk; no specific percentage found.
- Shares = (equity × risk%) / (entry − stop); because stops are tight (often 2–6%), cap position size by notional
  (swing-engine `max_position_pct: 10.0`) or a 1%-risk trade can become a 25–50% position.

### Holding period
- Swing variants (Holy Grail to swing high, TradeZella, EasySwing first target): **2–10 sessions**. EasySwing's
  mechanical panel reports an **average hold of 3 days** (Jul 2026).
- Trend-riding variants (Rayner Teo 50-EMA trail, Burns MA trail, Landry runner): weeks to months.
- swing-engine default time stop: `DEFAULT_MAX_HOLD_BARS = 20` (override per strategy with `max_hold_days`).

---

## Chart signatures
1. **Stacked, rising averages**: 10 > 20 > 50 (> 200), all sloping up; Landry "Proper Order" green.
2. **Orderly dip**: 2–7 bars of lower highs/lower lows, narrowing ranges, volume below the 20-day average
   ("drying up"); no single wide-range, high-volume down bar (that is distribution, not a pullback).
3. **Touch, not slice**: lows tag the 20-day (or enter the 20–50 band) but closes hold near or above it; the 20 has
   "held" on one or two earlier pullbacks (Rayner Teo's "respected at least twice").
4. **Reversal bar**: hammer/bullish engulfing/close in the upper half of the range, then a bar that trades above
   the prior bar's high; ideally on rising volume (EasySwing: volume > 20-day average).
5. **ADX still elevated** (> 25–30) during the dip — trend strength intact (Holy Grail).
6. **Relative strength line near highs** while price dips (leader digesting, not a laggard bouncing).
7. **Failure signature**: two closes below the 20-day, or a close below the 50-day on expanding volume; a third or
   fourth test of the same MA late in a long advance; the "Trend Knockout" one-bar flush that undercuts the MA
   and reverses (Landry TKO — a buyable shakeout, not a failure, if price quickly reclaims the bar high).

---

## Who teaches it
| Teacher | Version | Where | Status |
|---|---|---|---|
| Linda Bradford Raschke & Laurence Connors | Holy Grail (14-ADX > 30, 20 EMA touch, buy stop over touch bar) | *Street Smarts* (1995); lindaraschke.net; *Trading Sardines* | Book rules via restatements; Raschke still publishes |
| Dave Landry | Trend qualifiers, Proper Order 10/20/30, Bow Tie, pullback ≥ 2 lower lows, TKO, 2-for-1 | Books (2000, 2003); davelandry.com; StockCharts TV "Trading Simplified"; ACP plug-in | Active (sweep: "Market in a Minute" dated 10/06/26) |
| Rayner Teo (TradingwithRayner) | 20/50 EMA zone, 3rd pullback, 2 ATR stop, exit on close beyond 50 EMA | YouTube @tradingwithrayner (~2.2M subs per SponsorRadar Jun 2026, from sweep); course reviewed by FWTV | Active |
| Steve Burns (New Trader U, @SJosephBurns) | 10-day EMA pullbacks near 52-week highs; SPY 200-day filter; MA trailing | MoneyShow 2012; newtraderu.com; "Moving Average Signals" book | Active |
| Oliver Kell (@OliverKell_) | EMA Crossback (10/20 EMA) inside his Cycle of Price Action | TraderLion courses/articles | Active |
| Brian Shannon (@alphatrends) | 5-day MA / AVWAP pullbacks | alphatrends.net (method 08) | Active |
| Adam Khoo (Piranha Profits) | "Trend Retracement" buy-the-dip | Paid course; parameters not public | Unverified rules |
| TradeZella blog | 20 EMA pullback with RSI 40–55 and 2-close exit | tradezella.com (31 Mar 2026) | Educational |
| EasySwing / sofus-nl | Trend Pullback (EMA20/SMA50, RS ≥ 96) and 52w-High Proximity Pullback detectors | easyswing.trading; github.com/sofus-nl/swing-trading-strategies (MIT) | Vendor, publishes a live panel |
| Reddit (r/swingtrading, r/RealDayTrading) | SMA 50/100/200 bounces, rising 20/50 EMA + RVOL, "test the bid" volume confirmation | threads in Sources | Crowd practice |

---

## Evidence

### Mechanical replications (secondary)
| Study | Rules | Universe / period | Result |
|---|---|---|---|
| EasySwing.trading performance panel (updated **7 Jul 2026**) | Trend Pullback detector (EMA20/SMA50 structure, RS gate, bounce candle) | ~2,000 US stocks, 5-year walk-forward, **raw exits, no fees/slippage**, 1,092 trades | **Win 26%, avg +0.3R, profit factor 1.45, avg hold 3 days**. Same panel: 52w-High Proximity Pullback PF 1.33; Cup & Handle 1.57; Qullamaggie breakout 1.10 |
| sofus-nl Trend Pullback spec | as above | — | Labelled "Tuned … passed all four autoresearch gates" — i.e. parameters were selected on the data; treat PF as optimistic |
| QuantifiedStrategies "A simple stochastic pullback strategy" (**29 Jul 2026**) | Rising MA trend filter + low Stochastic (exact parameters paywalled) | SPY | 195 trades, 74% win, +0.6%/trade, PF 2.3, CAGR 3.6%, max DD 14%, 7% time in market — an *index* pullback-in-uptrend edge; short holds |
| QuantifiedStrategies RSI / "low risk" pullback variants | Rising-trend + oversold oscillator on SPY | SPY | Search-snippet figures (184 trades, 78% win, +0.7%/trade; 403 trades, 76% win) — not fetched (unverified) |

No independent, cost-inclusive backtest of the exact Holy Grail or Rayner Teo rules on US single stocks was found
this run. TradeZella's "55–65% win rate in trending markets" is an unsupported claim (no test shown).

### Academic backdrop
- **Short-term reversal inside medium-term momentum.** Recent 1-month losers outperform recent winners over the next
  month (Jegadeesh 1990); Novy-Marx (JFE 2012) shows the 12-2 / 12-7 momentum signal works while the most recent
  month behaves like noise/reversal. Dimensional (Medhat & Novy-Marx Q&A, **28 Feb 2023**): reversals are
  strongest over "a few weeks to one month", stronger in small/volatile names, and standalone reversal strategies
  are impractical because of turnover and costs; the practical use is as a **timing overlay** ("delay trades that
  demand costly liquidity"), and returns must be cleaned of post-earnings drift and industry momentum — otherwise
  you "buy the dip" into real news. That is the best academic description of *why* a pullback inside a
  momentum leader can be a better entry than a breakout.
- **52-week-high proximity** predicts returns better than raw past return (George & Hwang, JF 2004) — supports
  restricting pullbacks to names near highs (Burns, EasySwing proximity variant).
- **Moving-average rules on indices.** Brock, Lakonishok & LeBaron (JF 1992) found MA and range-break rules beat
  bootstrap nulls on the DJIA 1897–1986; Sullivan, Timmermann & White (JF 1999) showed much of that weakens after
  correcting for data snooping. MA *trend filters* remain useful mainly as risk filters (see method 06).
- **"MAs are not magic."** Adam Grimes' quantitative work (blog posts "200-day Moving Average Work" and on VWAP,
  summarised on Elite Trader) finds no special MA length and that price action after touching an MA is
  statistically random; the bounce is not a property of the line (secondary summary; posts not fetched).
  Implication: the edge, if any, comes from the *trend + short pullback + reversal trigger*, not from the specific
  20 or 50.

### Reading the evidence
1. Pullback-in-uptrend has a real but **modest** mechanical edge on stocks (PF ~1.3–1.5 before costs in the only
   live, multi-year stock panel found) and a stronger, low-exposure edge on the index (SPY oscillator pullbacks).
2. Win rate depends almost entirely on the exit: tight 2R/swing-high targets give 50–75%; MA-trail exits give
   25–40% with fatter winners. Quoted win rates without the exit rule are meaningless.
3. After 10–20 bps/side costs and gap-through-stop slippage a PF 1.45 / +0.3R raw edge with a 3-day hold shrinks
   materially — this has to be re-measured in swing-engine's cost model before any claim.

---

## Pitfalls
1. **Catching a trend change, not a pullback.** The dip that "touches the 50" is also the first leg of every
   top. Require the long-term structure (50 > 200, both rising) and reject dips on heavy volume or wide-range
   down bars.
2. **Buying the touch instead of the turn.** Limit orders at the MA fill on the way down, including the 20% that
   keep falling. Every primary variant uses a *trigger* (buy stop above the prior/touch bar high).
3. **Buying the dip into news.** Earnings misses, guidance cuts and downgrades produce "pullbacks" that are
   repricings (Dimensional's PEAD point). Exclude dips that started with an earnings gap down; avoid holding
   through the next report unless sized for it.
4. **Late-cycle tests.** First and second pullbacks to the 20/50 after a base breakout are the good ones; the
   fourth test of the 50-day in a mature advance fails more (Kell's "first pullback" emphasis; Rayner Teo's
   "third pullback" rule is the opposite convention — pick one and test it).
5. **Chop.** In sideways tape the MAs flatten and price crosses them constantly; ADX < 20–25 or a flat 50-day
   = no trade. TradeZella's own diagnostic: sub-50% win rate means chop.
6. **Stop just under an obvious MA.** Everyone's stop sits there; shakeouts (Landry's TKO) run them first.
   Use the pullback low − a small ATR buffer, and accept a re-entry above the knockout bar rather than widening.
7. **Gap risk vs tight stops.** 2–5% stops on stocks that gap 5–10% overnight produce losses of 2–3R; model
   `STOP_GAP` exits explicitly (the backtester does).
8. **Parameter shopping.** 5/10/20/21/30/50, EMA vs SMA, 1% vs 2% vs 1 ATR "touch", RSI 40–55 — the method has
   dozens of knobs and no theory for any specific value (Grimes). Fix one specification per the primary source,
   log every variant in `research/trials.py`, and use the deflated Sharpe gate.
9. **Survivorship in teaching charts.** Example charts are winners; the rules must be judged on the full scan
   output, including delisted names.

---

## 2025–2026 fit
- **2025 was a dip-buyer's year at the index level.** Media and bank flow research summarised in Jan 2026 say
  JPMorgan named dip-buying a defining retail theme of 2025, with three dip episodes accounting for ~75% of the
  group's stock positioning, and VandaTrack logging a record ~$3B net retail inflow on 3 Apr 2025 during the
  tariff crash (search-result summaries of Crowdfund Insider / AOL / Yahoo pieces; the primary JPM/Vanda notes
  were not fetched — unverified figures). The V-shaped April 2025 recovery and the Apr 24–25 2025 breadth thrust
  (method 06) rewarded buying pullbacks in uptrending leaders.
- **2026 is a narrower, choppier tape.** From method 06: % of stocks above the 50-day fell from 63% (mid-Jan) to
  22% within six weeks; an S&P "base breakdown" was flagged on 16 Mar 2026 (SentimenTrader); by **6 Oct 2026**
  only ~27% of US stocks are above their 50-day and ~40% above their 200-day while the cap-weighted index held up.
  That is the environment where single-stock pullbacks to the 50-day keep failing (the MA is rolling over) and
  only leaders near highs offer clean 20-day pullbacks.
- **Crowd view (Sep 2026, r/swingtrading):** "buying dips is better now, buying breakouts not so good" (sweep) —
  consistent with EasySwing's panel ranking Trend Pullback (PF 1.45) above breakout detectors (PF 1.10) through
  its mid-2025 → Apr 2026 holdout.
- **Verdict.** Still the most portable swing setup, and relatively better than breakouts in 2026, but only with
  (a) a market gate that respects the weak all-stock breadth, (b) a leadership/RS filter, (c) an earnings-date
  filter, and (d) costs modelled. Expect index-level pullback systems (SPY/QQQ) to be steadier than single names.

---

## Automatability

### Mechanical (exists or small additions)
| Element | swing-engine mapping |
|---|---|
| Trend qualifier | `trend_state == 1` (`features/regime.py`: close > SMA50 > SMA200, SMA50 rising over 5 bars) — already the default `min_trend_state` in `strategies/pullback_trend.py` |
| MAs | `sma_10`, `sma_20`, `sma_50`, `sma_200`, `ema_9`, `ema_21` exist. **Add `ema_20`, `ema_50`** (and optionally `ema_30` for Landry Proper Order) to `EMA_SPANS` in `features/indicators.py` to match Raschke/Rayner exactly |
| ADX filter (Holy Grail) | **Add `adx_14` (+DI/−DI)** to `features/indicators.py` (Wilder smoothing helper `wilder_smooth` already exists); param `adx_min = 30`, `adx_rising = True` |
| Touch / zone | `pullback_low <= ma * (1 + touch_pct)` (exists, default 1%); add `touch_mode = "atr"` (≤ 1 ATR, EasySwing) and `zone = (ema_20, ema_50)` (Rayner) |
| Quiet pullback | `max_pullback_volume_ratio` vs `avg_vol_20d` (exists, default 1.0) |
| Pullback shape | `pullback_bars` (exists, 4); add `min_lower_lows = 2` (Landry) via `RollingSpec` |
| Trigger | `close > prior_high` (exists). Taught trigger is a **buy stop at prior high + tick**; the panel approximates with a close-based entry (entry price ≥ trigger, larger risk). Option: enter next open if `open <= prior_high * (1 + x)` |
| Leadership | `ret_63d`, `mom_12_1`, `dist_52w_high` exist; **add a cross-sectional percentile rank** (`rank_ret_63d`) in `features/cross_section.py` for the RS ≥ 90/96 gate; `dist_52w_high >= -0.10` for the proximity variant |
| Stop | `pb_low − stop_atr_buffer × atr_14` (exists); add `stop_mode = "atr"` (2 × ATR Rayner, 1.5 × ATR EasySwing) and "tighter-of" logic |
| Targets | `target_mode = r_multiple / swing_high` (exists, 2R / 20-bar high) — covers Holy Grail and TradeZella first target |
| Trailing exit | **Implement `should_exit`** on `pullback_trend` (currently not overridden): `close < ema_50` (Rayner), two consecutive closes `< ema_20` (TradeZella) or `< sma_50` (EasySwing); set `min_reward_risk: 0.0` for the trail-only variant, as `rsi2_meanrev` does |
| Breakeven / 2-for-1 | `TrailingStop.breakeven_after_r = 1.0` in `research/backtest.py` (exists). True half-off scale-out needs a partial-exit hook (backtester is all-or-nothing today) |
| Holding period | `max_hold_days` param (backtester reads it; default 20 bars) |
| Market gate | `min_market_trend_state` (exists, default flat); add breadth (% above 50-day, method 06) and SPY > SMA200 (Burns) |
| Sizing | `risk.risk_per_trade_pct: 1.0` matches Burns/Rayner; `max_position_pct: 10.0` caps tight-stop notional |
| Costs | gates.md cost model (10/20 bps/side + SEC/TAF) |

Suggested variants to register (via `.claude/skills/add-strategy`, `enabled: false` until walk-forward + trial log
clear `docs/gates.md`): `pullback_holy_grail` (ema_20, adx ≥ 30 rising, buy over touch-bar high, stop touch-bar
low, target swing high); `pullback_ema_zone` (ema_20/ema_50 zone, 2 ATR stop, exit close < ema_50, no target);
and the existing `pullback_trend` with an RS-rank gate and the two-close `ema_20` exit. Test them as one family
(one trial log), not as independent discoveries.

### Discretionary (keep as Claude review enums or human steps)
- "Clean", orderly pullback vs distribution; quality of the reversal candle; whether the dip is news-driven
  (needs an earnings/news calendar; the monitor's news feeds can tag it).
- First vs third pullback judgment, theme leadership, and Kell-style cycle context (wedge pop → crossback).
- Intraday trigger refinement (Shannon's 65/15/5-minute higher low) needs intraday bars.

---

## Sources
Primary / primary-adjacent
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry — Landry Light (50 SMA), Proper Order 10SMA>20EMA>30EMA, Bow Tie
- https://articles.stockcharts.com/article/articles-landry-2019-11-trading-the-trend-knockout-582 — TKO episode page (6 Nov 2019; rules only in video)
- https://articles.stockcharts.com/article/articles-landry-2021-04-letting-the-ebb-flow-control-y-62 — Trading Simplified episode (7 Apr 2021; no rules in text)
- https://articles.stockcharts.com/article/articles-landry-2020-03-understanding-trend-following-468 — episode page (25 Mar 2020)
- https://www.davelandry.com/
- https://www.traders.com/Documentation/FEEDbk_docs/1996/12/1296tradetips.html — Landry 2/20 EMA (S&C Dec 1996; from sweep, not re-fetched)
- https://moneyshow.com/articles/dailyguru-26029 — Steve Burns interview (4 Jan 2012): 5/10-day EMA, SPY 200-day, 1% risk
- https://www.newtraderu.com/ ; https://newtraderu.teachable.com/p/moving-averages ; https://newtraderu.teachable.com/p/moving-average-signals
- https://lindaraschke.net/ ; https://www.antoinebuteau.com/lessons-from-linda-bradford-raschke/ (from sweep)
- https://traderlion.com/technical-analysis/chart-patterns/ema-crossback/ ; https://traderlion.com/technical-analysis/trading-the-ema-crossback/ — Kell EMA Crossback (403 at fetch; snippet only)
- https://tradingengineered.substack.com/p/5-key-concepts-from-my-interview (from sweep)
- https://alphatrends.net/ (see method 08)

Secondary restatements / vendors
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329 — Holy Grail rules (Gurkovskiy, 29 Mar 2021)
- https://tradingsetupsreview.com/the-holy-grail-trading-setup — Holy Grail per Street Smarts (20 SMA wording; no backtest)
- https://www.ebc.com/forex/holy-grail-trading-setup
- https://www.tradingview.com/script/hawl3ybg-Holy-Grail-Setup-with-Confidence-Opacity
- https://www.financialwisdomtv.com/post/make-your-money-work-for-you-trend-following-by-rayner-teo — Rayner Teo rules (7 Dec 2024)
- https://in.tradingview.com/script/srm3ovD0-Rayner-Teo-s-EMA-Setting — 20/50/200 EMA, 1.5×ATR(20) stop lines
- https://sponsorradar.com/channels/tradingwithrayner ; https://socialcounts.org/youtube-live-subscriber-count/UCFSn-h8wTnhpKJMteN76Abg
- https://quantamentaltrader.substack.com/p/adam-khoos-piranha-profits-course ; https://sponsorradar.com/channels/adamkhoo ; https://en.wikipedia.org/wiki/Adam_Khoo
- https://www.tradezella.com/blog/swing-trading-strategies — 20 EMA pullback rules (31 Mar 2026)
- https://in.tradingview.com/script/bgcb3IIb-Pullbacks-Completo — Landry pullback reproduction (≥ 2 lower lows, 21 EMA/MACD filter)
- https://easyswing.trading/performance — panel (7 Jul 2026): Trend Pullback win 26%, 0.3R, PF 1.45, 3-day hold, 1,092 trades
- https://github.com/sofus-nl/swing-trading-strategies — detector list
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/23-trend-pullback.md — Trend Pullback spec
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/21-proximity-pullback.md — 52w-High Proximity Pullback spec
- https://quantifiedstrategies.substack.com/p/a-simple-stochastic-pullback-strategy — SPY pullback stats (29 Jul 2026)
- https://quantifiedstrategies.substack.com/p/rsi-pullback-strategy ; https://quantifiedstrategies.substack.com/p/low-risk-pullback-strategy (snippets only)
- https://elitetrader.com/et/threads/moving-averages-are-random.299801/post-4280395 — summary of Adam Grimes' MA research
- https://topstepbrokerage.com/blog/going-deep-on-adam-grimes-approach

Academic
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx — reversals as timing overlay (28 Feb 2023)
- https://alphaarchitect.com/when-academics-disagree-on-momentum-investing/ (from sweep)
- https://ideas.repec.org/a/bla/jfinan/v47y1992i5p1731-64.html — Brock, Lakonishok & LeBaron (JF 1992)
- https://alphaarchitect.com/old-school-academics-on-moving-average-rules-remarkable/
- https://eprints.soton.ac.uk/377140/1/Urquhart_How.pdf
- George & Hwang (2004), "The 52-Week High and Momentum Investing", Journal of Finance 59(5) (cited via sofus-nl; not fetched)
- Jegadeesh (1990), Journal of Finance; Novy-Marx (2012), Journal of Financial Economics (cited via sweep/Dimensional; not fetched)

2025–2026 context
- https://www.crowdfundinsider.com/2026/01/257034-retail-investors-navigate-market-volatility-in-2025-for-steady-returns-research/ (403 at fetch; snippet only)
- https://www.aol.com/articles/people-getting-more-aggressive-buying-145213218.html ; https://finance.yahoo.com/news/buy-dip-etfs-3-trends-204853436.html ; https://thenightly.com.au/business/the-economist-buy-the-dip-investment-trend-keeps-markets-from-crashing-during-donald-trumps-wild-ride-c-18597199
- https://blog.traderspost.io/article/buy-the-dip-2026-retails-data-driven-playbook
- https://sentimentrader.com/blog/the-sp-500-completes-a-base-breakdown-pattern--16-3-2026
- https://www.reddit.com/r/swingtrading/comments/1whb374/ ; https://www.reddit.com/r/swingtrading/comments/1tqyhi3/ ; https://www.reddit.com/r/RealDayTrading/comments/1lp2lr8/ ; https://www.reddit.com/r/RealDayTrading/comments/1owinhe/ ; https://www.reddit.com/r/StockMarket/comments/1plnj5s/ ; https://reddit.sentinel-team.org/posts/1pf44ar/snapshots/2025-12-06T02%3A59%3A48.977586Z (from sweep)
- docs/methods/06-breadth-regime-filters.md (breadth readings 2025–Oct 2026); docs/methods/08-anchored-vwap-multi-timeframe-shannon.md; docs/methods/05-qullamaggie-breakout.md
