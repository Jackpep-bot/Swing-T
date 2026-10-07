# Swing tool catalog

*Generated 2026-10-07 from `docs/research-raw/brands/{brokers,platforms,classic,evidence}.json`, `docs/methods.md` (tables 1a/1b, sections 6-7), the deep dives in `docs/methods/`, the existing modules in `swing_engine/strategies/` and `docs/feature-contract.md`. The machine-readable version with full merged rules, evidence text, source refs and URLs is [`catalog.json`](catalog.json). Nothing here is investment advice; every item still has to pass `docs/gates.md`.*

## How the catalog was built

- **Inputs**: 367 research rows (brokers 93, platforms 82, classic 61, evidence 51, methods.md 1a 16, 1b 39, 6.x 14, 7a 5, 7b 6) plus the broker built-in appendix (95 thinkorswim strategies, 350 thinkorswim studies, 128 TradeStation strategies).
- **Deduplication**: the same tool across brands is one item that keeps every brand name and source (for example the Donchian / price-channel breakout appears in thinkorswim, TradeStation, TradingView and ChartSchool). Variants of one idea that share a setup become one item with a `variant` parameter (MA crossovers, oscillator crosses, Connors RSI(2) variants, Turtle Soup and Turtle Soup +1, NR7/NR4/ID-NR4), so the trial count in `research/trials.py` stays honest.
- **Result**: **281 distinct items**. A build-time check fails if any research row, methods.md row or appendix entry is not mapped to an item, so nothing is dropped silently. `catalog.json` `source_coverage` lists, for every source row, the item(s) it landed in; `appendix_coverage` does the same for all 573 appendix entries.
- **Evidence grades** are normalised to the methods.md scale (A, B, C, D, Neg, none; a trailing '-' marks the weak end). Each source file uses its own rubric, so per-source grades are kept in `source_grades`; conflicts are called out in the notes.

**Decisions**

| Decision | Meaning | Items |
|---|---|---|
| `have` | an existing module or feature already covers it (maps_to) | 32 |
| `implement` | build it as a normal candidate (still subject to docs/gates.md) | 65 |
| `implement_disabled_for_comparison` | build it, keep it disabled, measure it in replay (weak or negative evidence, or a negative control) | 130 |
| `approximate` | proprietary rating rebuilt from its published description | 14 |
| `blocked_paid_data` | needs data the free stack does not have (options, analyst estimates, vendor scores) | 14 |
| `avoid` | no evidence, pure discretion, not testable, or out of scope; notes say why | 26 |
| **total** | | **281** |

**Items by build batch and decision**

| Batch | have | implement | disabled-compare | approximate | blocked (paid data) | avoid | total |
|---|---|---|---|---|---|---|---|
| `indicators` | 6 | 25 | 2 | 0 | 2 | 4 | 39 |
| `ratings_screens` | 4 | 14 | 5 | 14 | 9 | 5 | 51 |
| `strategies_trend` | 2 | 2 | 36 | 0 | 0 | 4 | 44 |
| `strategies_meanrev` | 2 | 0 | 33 | 0 | 0 | 2 | 37 |
| `strategies_breakout` | 8 | 0 | 26 | 0 | 0 | 1 | 35 |
| `strategies_pattern` | 0 | 0 | 10 | 0 | 0 | 2 | 12 |
| `regime_tools` | 4 | 13 | 16 | 0 | 1 | 7 | 41 |
| `risk_tools` | 6 | 11 | 2 | 0 | 2 | 1 | 22 |

**Strategy cards**: 130 strategy or strategy-like pattern items are `have`, `implement` or `implement_disabled_for_comparison`; they are listed at the end and in `catalog.json` `strategies_to_card`.

## Cross-cutting work the catalog implies

These are not strategies, but most copied strategies cannot be replayed faithfully without them:

1. **Order types in the backtester** (`backtester_order_type_hooks`). Nearly every broker built-in enters on a *buy stop* (price + $0.50 / + 1 tick / above the signal-bar high); Connors and IBS enter at the close or on a limit below it; TPS and the Turtles scale in; every discretionary school scales out. Today the engine fills everything at the next open, which silently changes those rules.
2. **Point-in-time earnings dates** (`earnings_dates_point_in_time`, EDGAR 8-K Item 2.02). Needed by power_gap, episodic_pivot, Rich & Rich, Abr, SUE, the earnings premium and the reaction statistics.
3. **Longer free history.** Massive Basic serves 2 years of daily bars. Residual momentum (36 months), the Daniel-Moskowitz crash filter (24 months), Heston-Sadka seasonality (5-20 years), breadth-thrust calibration and every monthly/weekly system need more; Alpha Vantage / EODHD free daily-adjusted history is the free route (slow: per-symbol calls).
4. **Indicator backlog.** Stochastic, %R, CCI, Keltner, volume-flow family, Supertrend, PSAR, swing-point hierarchy, pivots, AVWAP, volume profile and the long-tail library (feature-only, ranker-tested) unblock most of the disabled comparison strategies.
5. **Negative controls.** `ma_crossover_family` and `oscillator_cross_family` are deliberately kept as disabled baselines: a candidate that cannot beat them after costs in the same replay is noise (STW 1999, Aronson 2006, Bajgrowicz-Scaillet 2012).
6. **Long-only engine.** Every short-entry (SE) built-in is cataloged under its long mirror; short-only ideas (parabolic short, pair short leg, Bon Shorty) are `avoid` for that reason.

## Strategies: breakout and momentum entries

have: 8, disabled-compare: 26, avoid: 1

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **52-week-high breakout on volume (Minervini / O'Neil lineage; TradeStation New High LE)** `breakout_52w` | TradeStation; Mark Minervini; IBD / William O'Neil (MarketSurge) | have | C | yes | swing_engine/strategies/breakout_52w.py | Enabled. Also covers TradeStation New High LE (PeriodType = year). 52w-high nearness is C in VW replication (E06). |
| **Classic base breakout: cup-with-handle and flat base (O'Neil / IBD / MarketSurge)** `base_breakout` | IBD / William O'Neil (MarketSurge) | have | C | yes | swing_engine/strategies/base_breakout.py | Round-4 module (built). Best gross PF (1.57) of the multi-year breakout panel; Bulkowski failure rates doubled after the 1990s. Double bottom / ascending base / saucer / IPO base are separate items. |
| **Episodic pivot, delayed day-2 entry** `episodic_pivot` | Interactive Brokers; Pradeep Bonde (Stockbee); Kristjan Kullamagi (Qullamaggie) | have | D | yes | swing_engine/strategies/episodic_pivot.py | Round-4 module (built). Only public mechanical test lost to SPY; catalyst quality stays a Claude enum. IBKR Campus 'float back to the gap' variant is the delayed entry. |
| **Insider cluster buying (Form 4) follow-through** `insider_cluster` | SEC EDGAR Form 4 | have | C | yes | swing_engine/strategies/insider_cluster.py | Code exists, disabled until Form 4 ingest feeds insider_cluster_score; most return prints on the disclosure day. |
| **Power earnings gap / buyable gap-up, consolidation entry** `power_gap` | Trader Stewie; Gil Morales / Chris Kacher; Kristjan Kullamagi (Qullamaggie) | have | C | yes | swing_engine/strategies/power_gap.py | Round-4 module (built). Signals are volume gaps until point-in-time earnings dates exist (see earnings_dates_point_in_time). |
| **Qullamaggie momentum flag breakout** `qullamaggie_flag` | Kristjan Kullamagi (Qullamaggie) | have | C- | yes | swing_engine/strategies/qullamaggie_flag.py | Round-4 module (built). EasySwing 16,943 trades PF 1.10 gross; feast-or-famine. ORH entry needs intraday bars. |
| **Resistance breakout with measured-move target (Schwab Learn / Joe Mazzola)** `sr_breakout` | Charles Schwab / thinkorswim | have | none | yes | swing_engine/strategies/sr_breakout.py | Enabled. Measured move = resistance + (resistance - support); gap-through-stop risk noted by Schwab. |
| **Stockbee 4% momentum burst** `momentum_burst` | Pradeep Bonde (Stockbee) | have | D | yes | swing_engine/strategies/momentum_burst.py | Code exists, disabled in settings (weak standalone evidence). Known bug (methods.md 7a #5): line 63 rejects prior red days Stockbee prefers; fix and add an NR7 variant, breadth gate and scale-out. |
| **ADX Breakouts (Ken Calhoun)** `calhoun_adx_breakout` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module; adx_14 exists | S&C in-sample only; $20-70 price and $5 range filters are 2016 dollar rules (convert to %). |
| **ATR High / SMA breakouts (Ken Calhoun)** `calhoun_atr_high_sma_breakout` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample only; volatility-expansion trigger worth one replay against breakout_52w. |
| **Bollinger Squeeze breakout (Method I / Method IV)** `bollinger_squeeze_breakout` | StockCharts / ChartSchool; John Bollinger; TradeStation (+1) | disabled-compare | C | yes | new module; bb_width_20 exists | Practitioner backtests only; Lento et al. found band-touch rules fail after costs (not the squeeze itself). Head-fakes common. |
| **Boomers (two inside days in an ADX > 30 trend; Jeff Cooper)** `boomers_cooper` | Jeff Cooper | disabled-compare | D | yes | new module; inside_day, adx_14 exist | Rules from summaries, not the book; no test. |
| **Bull flag / high-tight flag breakout (Schwab Learn, Katsanos flags, O'Neil HTF)** `bull_flag_breakout` | Charles Schwab / thinkorswim; Thomas Bulkowski; Markos Katsanos (+1) | disabled-compare | C | yes | swing_engine/features/patterns2.py flag(); qullamaggie_flag | Generic flag without the top-2% RS filter, as a comparison to qullamaggie_flag; HTF Bulkowski +22% at 1 month (descriptive). |
| **CAN SLIM selection (C-A-N-S-L-I) with base-breakout entries** `canslim` | IBD / William O'Neil (MarketSurge) | disabled-compare | C | yes | swing_engine/strategies/base_breakout.py (chart side) | Selection lagged in real money (FFTY 10-yr 4.94%/yr vs SPY 15.53%). Needs XBRL EPS/ROE (free) and 13F (free, 45-day lag). |
| **Darvas Box breakout and pyramid** `darvas_box` | Charles Schwab / thinkorswim; Nicolas Darvas | disabled-compare | C | yes | new module (box state machine); overlaps breakout_52w | Book anecdote; related ATH-breakout evidence C. thinkorswim ships a 5-state box study. |
| **Donchian / price-channel breakout (20-40 bar high; Cagigas, TradeStation, TradingView, 4-week rule)** `donchian_channel_breakout` | Charles Schwab / thinkorswim; TradeStation; TradingView (+1) | disabled-compare | D | yes | new module; high_52w analog exists | Trading-range-break rules failed out of sample after 1986 (BLL / STW, E41); stock ATH-breakout trend following is positive in Wilcox-Crittenden. Replay as the plain-channel control for breakout_52w. |
| **Expansion Pivot (Jeff Cooper)** `expansion_pivot_cooper` | Jeff Cooper | disabled-compare | D | yes | new module | Author examples only; cousin of the pocket-pivot / MA-reclaim ideas. |
| **Four-Day Breakout (Ken Calhoun)** `calhoun_four_day_breakout` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module; needs stop-entry hook | S&C in-sample illustration only. Dollar thresholds ($0.50) convert to ATR/% for stocks. |
| **Full-gap entry bar (Gap Up LE: low > prior high; thinkorswim, TradeStation)** `full_gap_continuation_bar` | Charles Schwab / thinkorswim; TradeStation | disabled-compare | none | yes | new module; gap_pct exists | Demonstration strategy. Large gaps mostly do not fill same day (E30), which is the continuation case. |
| **Gap trading first-hour range rules (Scott Andrews / ChartSchool)** `chartschool_gap_first_hour` | StockCharts / ChartSchool; Scott Andrews; TradeThatSwing | disabled-compare | D | no | monitor path (intraday) + daily approximation | True rule needs first-hour bars (free intraday is limited: Massive Basic 2 years, delayed); daily approximation is labelled. No independent stats. |
| **IBD double bottom, ascending base, saucer and consolidation bases** `ibd_other_bases` | IBD / William O'Neil (MarketSurge) | disabled-compare | C | yes | swing_engine/strategies/base_breakout.py (add variants) | Base types base_breakout does not detect yet; Bulkowski / O'Neil statistics are descriptive only. |
| **IPO first-base breakout** `ipo_first_base_breakout` | IBD / William O'Neil (MarketSurge) | disabled-compare | C | yes | swing_engine/strategies/base_breakout.py (IPO variant) | Day-1 pops faded in 2025; only first-base breakouts are worth a replay. Needs IPO dates (EDGAR S-1/424B, free). |
| **Keltner channel breakout (TradeStation, TradingView, Keltner 10-day rule)** `keltner_channel_breakout` | TradeStation; TradingView; Chester Keltner (+1) | disabled-compare | D | yes | new module + keltner_channels | Demonstration strategies; no evidence. |
| **Minervini VCP / SEPA pivot breakout** `vcp_sepa_breakout` | Mark Minervini | disabled-compare | D | yes | swing_engine/strategies/breakout_52w.py vcp_contraction (crude proxy) | Coded VCP trigger shows no edge (EasySwing PF 0.38; template pass PF 0.99). Low priority per methods.md; needs a swing-pivot detector. |
| **NR7 / NR4 / ID-NR4 range-contraction breakout (Crabel)** `nr7_nr4_range_contraction` | Toby Crabel; Raschke & Connors; StockCharts / ChartSchool | disabled-compare | C | yes | new module; inside_day exists; also the NR7 variant for momentum_burst | C: Bulkowski 7%/7% test won 57% (~+0.8%/trade net of $10 commissions); Oxford Capital: not tradeable in futures after costs. |
| **Open +/- k x range volatility breakout (Williams GSV, Crabel stretch)** `open_volatility_breakout` | Larry Williams; Toby Crabel | disabled-compare | D | yes | new module; needs same-day stop-entry fills on the open | Futures-tested only; needs OCO stop simulation (ambiguous both-hit days take the worst case). |
| **Pivot Reversal breakout (confirmed swing high buy stop)** `pivot_reversal_breakout` | TradeStation; TradingView | disabled-compare | none | yes | new module; features/levels.py pivots exist | Demonstration strategies; no evidence. |
| **Stine insider-buy superstocks (weekly volume thrust, magic line)** `stine_insider_superstock_weekly` | Jesse Stine | disabled-compare | D | yes | superstock_weekly.py (proposed) + float_data.py + edgar.py | One self-reported window; universe is full of diluters. Low priority; borrow the sell rules. |
| **Stochastic Pop (Bernstein, Steckler/Hill)** `stochastic_pop_and_drop` | StockCharts / ChartSchool; Jake Bernstein | disabled-compare | D | yes | new module + stochastic_oscillator | Practitioner only; low-ADX consolidation then stochastic surge on volume. |
| **TTM Squeeze (BB inside Keltner, momentum fire)** `ttm_squeeze` | Charles Schwab / thinkorswim; TradingView; LazyBear (+1) | disabled-compare | D | yes | new module + keltner_channels | No independent test; vol clustering is real, direction edge unproven. |
| **Turtle System 1 (20/10 with skip rule) and System 2 (55/20)** `turtle_breakout_systems` | Richard Dennis & William Eckhardt; Curtis Faith | disabled-compare | C | yes | new module; needs stop-entry + pyramiding hooks and a shadow-trade ledger | C for stocks (Wilcox-Crittenden, Zarattini-Pagani-Wilcox: <50% winners, a few large winners). Holding weeks-months. |
| **Volatility Expansion Close/Open entries (TradeStation, TradingView)** `volatility_expansion_close` | TradeStation; TradingView | disabled-compare | none | yes | new module; stop-entry hook | Demonstration strategies; no evidence. |
| **VPN high-volume breakout (Markos Katsanos)** `katsanos_vpn_breakout` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + VPN indicator | S&C 2021 in-sample; volume-confirmed breakout to compare with breakout_52w volume gate. |
| **Weinstein Stage 2 breakout (weekly 30-week MA, Mansfield RS)** `weinstein_stage2_breakout` | Stan Weinstein | disabled-compare | D | yes | new weekly module (shares weekly features with stine) | methods.md candidate weekly strategy; no independent test of the full method; the 30-week trend filter itself is B. |
| **Intraday-only day-trading strategies (ORB, first-hour breakout, intraday gap reversal, session VWAP, close-at-EOD)** `orb_intraday_day_trading` | Charles Schwab / thinkorswim; TradeStation | avoid | Neg | no | - | Not swing (flat by the close) and an independent ORB replication nets ~0 after costs; the session-VWAP study failed replication. |

## Strategies: trend following and pullbacks

have: 2, implement: 2, disabled-compare: 34, avoid: 4

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Holy Grail pullback (ADX > 30, 20 EMA touch, buy over the touch-bar high)** `pullback_holy_grail` | Raschke & Connors | have | D | yes | swing_engine/strategies/pullback_holy_grail.py | Round-4 module (built). Exact rules have no independent cost-inclusive test (D); the pullback family is B-. Known drawback: slow steady trends never push ADX above 30. |
| **Pullback to a rising 20/50 MA in an uptrend (Landry / Raschke / Qullamaggie pullback core)** `pullback_trend` | Dave Landry; Linda Raschke; Kristjan Kullamagi (Qullamaggie) (+2) | have | B- | yes | swing_engine/strategies/pullback_trend.py | Enabled; best evidence and 2026 fit among long setups. Open fixes (methods.md 7a #5): should_exit trail (close < ema_50 or 2 closes < ema_20), RS-percentile gate, earnings-window exclusion, Kell not-extended rule (<= ~3% above 10/20 EMA). |
| **Anchored-VWAP pullback (Brian Shannon multi-timeframe)** `avwap_pullback_shannon` | Brian Shannon (Alphatrends) | implement | D | yes | features/avwap.py (proposed) + strategies/avwap_pullback.py | methods.md 7b #6 (last P1 module). Evidence C-/D, but it is the planned entry-quality filter for the pullback family. |
| **EMA-zone pullback (low in the 20-50 EMA band after 2 respected tests)** `pullback_ema_zone` | Dave Landry; Linda Raschke; Rayner Teo (+1) | implement | B- | yes | swing_engine/strategies/pullback_trend.py (family) | Second variant of methods.md 7b #1 (holy_grail was built, ema_zone was not). Needs ema_50 feature. |
| **1-2-3-4 pullback (Jeff Cooper Hit and Run)** `cooper_123_pullback` | Jeff Cooper; Connors/Raschke | disabled-compare | D | yes | new module; adx_14 exists | No independent test; same family as Holy Grail and Connors 3-day pullbacks. |
| **Bollinger Method II: %b + MFI trend confirmation** `bollinger_pctb_mfi_trend` | StockCharts / ChartSchool; John Bollinger | disabled-compare | D | yes | new module + volume_flow_indicators (MFI) | No independent stats; PSAR stops. |
| **Classic oscillator cross strategies (RSI 30/70, stochastic 20/80, %R, MACD signal/zero, PMO, DMI osc, momentum rising, Spectrum Bars)** `oscillator_cross_family` | Charles Schwab / thinkorswim; TradeStation; TradingView | disabled-compare | none | yes | new module with variant param (negative control) | Built-in demonstration strategies with no published performance; Aronson's 6,402-rule test found none significant. Negative-control baselines. |
| **Ehlers DSP indicators and strategies (roofing filter, super smoother, onset trend, universal/elegant osc, reverse EMA, Swami charts)** `ehlers_dsp_family` | Charles Schwab / thinkorswim; John Ehlers | disabled-compare | D | yes | new module + DSP indicator set | S&C in-sample; one module with variants keeps the trial count honest. Filters double as long-tail features. |
| **Elder Triple Screen** `elder_triple_screen` | Alexander Elder | disabled-compare | D | yes | new module (weekly resample) + elder_force_index | No independent test; uses a trailing buy stop (stop-entry hook). |
| **Faber sector rotation (top-3 sectors by 3-month ROC, 10-month SMA filter)** `faber_sector_rotation` | StockCharts / ChartSchool; Mebane Faber | disabled-compare | C | yes | new monthly module on sector ETFs | Grade conflict: platforms B, classic C (in-sample, no costs). Monthly holding is outside swing; doubles as the sector rank. |
| **Fundamental setup + technical trigger (TradeStation Fundamntl & Chan/MACD/RSI/Stoch/Volty)** `fundamental_setup_technical_trigger` | TradeStation | disabled-compare | none | yes | new module + XBRL fundamentals | Demonstration strategies; fundamental field momentum from SEC XBRL (free). |
| **Gap Momentum System (Perry Kaufman 2024)** `kaufman_gap_momentum` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; OBV-style accumulation of opening gaps; overnight-return feature is the evidence-backed cousin (E31). |
| **Heikin-Ashi trend riding (Valcu)** `heikin_ashi_trend_ride` | Dan Valcu | disabled-compare | D | yes | new module | No independent test; fill at real prices, HA values are synthetic. |
| **Ichimoku cloud pullback (Kijun dip, Tenkan reclaim)** `ichimoku_cloud_pullback` | StockCharts / ChartSchool; Goichi Hosoda | disabled-compare | D | yes | new module + ichimoku lines | Practitioner only; use spans computed 26 bars ago (no look-ahead). |
| **Kell Cycle of Price Action (Wedge Pop, EMA Crossback, Base n' Break, Wedge Drop; QQQ 20 EMA gate)** `kell_cycle_of_price_action` | Oliver Kell | disabled-compare | D | yes | new module + ema_10 + phase state machine | One contest year; no independent test. The not-extended rule and QQQ > 20 EMA gate are usable now as filters. |
| **Landry Bow Tie, Proper Order and 90%-of-50-day-closing-high trend rules** `landry_bow_tie` | Dave Landry | disabled-compare | D | yes | swing_engine/strategies/pullback_trend.py (family) + ema_30 | Pullback family B- per methods/01; bow-tie sequencing untested. |
| **Long Haul (Donald Pendergast Jr.)** `pendergast_long_haul` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; formula partly approximated (RSI thresholds per article). |
| **MACD zero-line crosses confirmed by swing structure (ChartSchool)** `macd_zero_line_swing_points` | StockCharts / ChartSchool | disabled-compare | D | yes | new module + swing_point_labeling | Discretionary framework approximated with confirmed swing points. |
| **MeanReversionSwingLE (Ken Calhoun): 50% retracement then rise** `calhoun_mean_reversion_swing` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + swing_point_labeling | Despite the name it is a pullback-in-uptrend entry; S&C in-sample only. |
| **Moving Momentum (Arthur Hill)** `moving_momentum_hill` | StockCharts / ChartSchool; Arthur Hill | disabled-compare | D | yes | new module + stochastic_oscillator | Author examples only; trend + stochastic pullback + MACD turn. |
| **Moving-average crossover family (price/MA, 2-line, 3-line, golden cross, VWMA/SMA, MHL MA, Breen bands, Webull 5/10/20)** `ma_crossover_family` | Charles Schwab / thinkorswim; Webull; TradeStation (+6) | disabled-compare | Neg | yes | new module with variant param (negative control) | Neg: no rule survives White's Reality Check out of sample (STW 1999). Kept only as a negative-control baseline in replay; long MAs stay as filters (trend_state). Webull's 3-step sell ladder is a variant. |
| **Parabolic SAR stop-and-reverse entries (TradeStation, TradingView)** `parabolic_sar_reversal` | TradeStation; TradingView; Charles Schwab / thinkorswim | disabled-compare | none | yes | new module + parabolic_sar | Demonstration strategy; long side only. |
| **Price Zone Oscillator strategies (Khalil & Steckler)** `price_zone_oscillator` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample. |
| **Rate of Change with Bands (Vitali Apirine)** `apirine_roc_bands` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; band definition approximated. |
| **RSITrend (Kevin Luo): RSI cross only in a ZigZag-confirmed trend** `rsi_trend_zigzag_luo` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + swing_point_labeling | S&C in-sample; ZigZag last leg repaints, use confirmed swings only. |
| **RSMK relative-strength strategy (Katsanos)** `katsanos_rsmk` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + relative_strength_line | S&C in-sample; RS crossing zero with a fixed-bar hold. |
| **Sentiment Zone Oscillator strategy (Walid Khalil)** `sentiment_zone_oscillator` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample. |
| **Simple Trend Channel system (James & John Rich)** `rich_simple_trend_channel` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + earnings_dates_point_in_time | S&C in-sample; useful as an earnings-avoidance template. |
| **Slope Performance Trend (price and relative slopes)** `slope_performance_trend` | StockCharts / ChartSchool | disabled-compare | C | yes | new module + relative_strength_line | Related to time-series and relative momentum; very few signals (months). |
| **Stiffness indicator strategy (Katsanos)** `katsanos_stiffness` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + stiffness indicator | S&C in-sample; trend-quality measure worth one replay against trend_state. |
| **Supertrend / ATR-trailing-stop flip entries (TradingView, thinkorswim ATRTrailingStopLE)** `supertrend_flip_strategy` | TradingView; Charles Schwab / thinkorswim | disabled-compare | none | yes | new module + supertrend | Demonstration strategy; long-only flips. |
| **SwingThree (Donald Pendergast)** `pendergast_swingthree` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; tick offsets convert to cents/%. |
| **TAC_DMI trend-start system (BC Low)** `tac_dmi_trend_start` | Charles Schwab / thinkorswim | disabled-compare | none | yes | new module | thinkorswim built-in from S&C; no evidence. Rules from the thinkorswim appendix. |
| **The 'Last' Stochastic technique (weekly 39-period)** `last_stochastic_weekly` | StockCharts / ChartSchool; George Lane | disabled-compare | D | yes | new weekly module | Illustrative only. |
| **The Anti (stochastic hook pullback; Raschke, Grimes)** `the_anti` | Linda Bradford Raschke; Linda Raschke; Adam Grimes | disabled-compare | D | yes | new module + stochastic_oscillator | No independent test. Grimes' own research: MA touches are random; the edge is trend plus trigger. |
| **Trend-strength filter family ADXTrend / ERTrend / R2Trend / VHFTrend (Katsanos)** `katsanos_trend_strength_filters` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module; adx_14 exists + kaufman_efficiency_ratio_kama | S&C 'Which trend indicator wins?' in-sample; doubles as a regime-router experiment. |
| **Vervoort Heikin-Ashi family (HACOLT, SVEHaTypCross, SVESC, SVEZLRBPercB, VolatilityBand)** `vervoort_heikin_ashi_family` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module with variant param | S&C in-sample; formulas partly approximated. |
| **Weekend Trend Trader (Nick Radge)** `radge_weekend_trend_trader` | Nick Radge | disabled-compare | C | yes | new weekly module | Re-tests show long flat periods; weekly breakout with an index filter. |
| **Discretionary teaching frameworks (Caruso growth/story, Breitstein playbook, Bear Bull Traders, Farley 7 Bells)** `discretionary_teaching_frameworks` | Matt Caruso; Lance Breitstein; Bear Bull Traders (+1) | avoid | D | yes | - | Pure discretion or reading lists; no mechanical rule to test. |
| **Pair trading long/short on a price ratio (D'Errico)** `pair_trading_ratio` | Charles Schwab / thinkorswim | avoid | D | yes | - | Market-neutral pair needs a short leg (engine long-only); the long leg alone duplicates relative_strength_line / katsanos_rsmk. |
| **Trade Ideas Holly AI** `trade_ideas_holly_ai` | Trade Ideas | avoid | C | no | - | Intraday only (no overnight), proprietary nightly optimisation, vendor-only stats; its families map to cataloged MR/pullback items. |
| **TradingView Greedy Strategy (gap pyramiding)** `greedy_strategy_tv` | TradingView | avoid | none | yes | - | Exact rules not retrieved; cannot be copied faithfully. Gap pyramiding ideas are covered by kaufman_gap_momentum. |

## Strategies: mean reversion and reversals

have: 2, disabled-compare: 29, avoid: 2

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Connors RSI(2) mean reversion** `rsi2_meanrev` | StockCharts / ChartSchool; Larry Connors; Connors-Alvarez (+2) | have | B- | yes | swing_engine/strategies/rsi2_meanrev.py | Enabled. Grade conflict: platforms B, methods.md B-, evidence.json D (Backtrex OOS CAGR 1.7%, 71% wins, negative skew). Faithful variant needs sma_5 exit and close/MOC fills (methods.md 7a #5). |
| **Support bounce (Schwab Learn / Joe Mazzola)** `sr_bounce` | Charles Schwab / thinkorswim | have | none | yes | swing_engine/strategies/sr_bounce.py | Enabled. Schwab teaches it with illustrative examples only; pivot S/R from features/levels.py. |
| **80-20 reversal (Raschke & Connors)** `eighty_twenty_reversal` | Raschke & Connors | disabled-compare | D | yes | new module; stop-entry hook | Originator claims only; taught as a day trade. |
| **Bollinger band mean reversion (re-entry above the lower band; TradeStation, thinkorswim, TradingView, Webull)** `bollinger_band_mean_reversion` | TradeStation; Webull; TradingView (+1) | disabled-compare | D | yes | new module; bb_lower_20 exists | Lento-Gradojevic-Wright: band rules did not beat buy-and-hold after costs (contrarian versions did better). |
| **Bollinger Bands with bullish engulfing (Pawel Kosinski)** `bb_bullish_engulfing_kosinski` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; has a reward/risk-to-upper-band filter. |
| **Bollinger Method III (Intraday Intensity) and W-bottoms** `bollinger_w_bottom_ii_reversal` | John Bollinger | disabled-compare | D | yes | new module + volume_flow_indicators (II%) | No independent test. |
| **CCI Correction (weekly bias, daily CCI dip)** `cci_correction` | StockCharts / ChartSchool; Donald Lambert | disabled-compare | D | yes | new module + cci_indicator | Practitioner illustration. |
| **Connors %b strategy (ETF)** `connors_pctb` | Larry Connors | disabled-compare | D | yes | swing_engine/strategies/rsi2_meanrev.py family | In-sample; band parameters unconfirmed (test 20/2 and 5-day side by side). |
| **Connors 3-Day High/Low (ETF)** `connors_3day_high_low` | Larry Connors | disabled-compare | C | yes | swing_engine/strategies/rsi2_meanrev.py family | EdgeRater replication on 20 ETFs beat random entry (no costs). |
| **Connors HPETF RSI(4) 25/75, Multiple Days Down, RSI 10/6** `connors_hpetf_rsi_variants` | Larry Connors | disabled-compare | none | yes | swing_engine/strategies/rsi2_meanrev.py family | All thresholds unverified (from recollection); verify against the book first. |
| **Connors RSI(2) family variants (Double 7s, Cumulative RSI, R3, ConnorsRSI pullback, Alpha Formula)** `connors_rsi2_variants` | Larry Connors; Cesar Alvarez | disabled-compare | C | yes | swing_engine/strategies/rsi2_meanrev.py (variant param) | In-sample originator figures (Double 7s 80.4% winners); independent OOS for the family is thin and negative-skew. |
| **Connors TPS (time, price, scale-in 10/20/30/40)** `connors_tps_scale_in` | Larry Connors | disabled-compare | D | yes | new module; needs scale-in hook | Originator claims; averaging down concentrates risk, cap total size. |
| **CVR3 VIX market timing (Connors)** `connors_cvr3_vix` | StockCharts / ChartSchool; Larry Connors | disabled-compare | C | yes | new module + vix series (CBOE free) | Connors backtests; VIX-spike mean reversion broadly documented. |
| **DeMark TD Sequential (setup 9, countdown 13)** `td_sequential` | Tom DeMark; Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | Codeable, untested here. |
| **Elder MA-penetration channel swing (Fidelity Learning Center)** `elder_ma_penetration_channel` | Fidelity; Alexander Elder | disabled-compare | none | yes | new module; needs limit-below-close entry hook | Educational; average penetration depth sets the limit buy. |
| **Gandalf Project Research System (D'Errico & Trombetta)** `gandalf_project_research_system` | Charles Schwab / thinkorswim | disabled-compare | none | yes | new module | thinkorswim built-in; candle-structure weakness entries with time/price exits; no evidence. |
| **Intermarket divergence (BBDivergence, RegressionDivergence; Katsanos)** `intermarket_divergence_katsanos` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module (stock vs sector ETF pairs) | S&C in-sample. |
| **Internal Bar Strength mean reversion (IBS < 0.2 buy, > 0.8 sell)** `ibs_mean_reversion` | Quantified Strategies; Pagonidis; Charles Schwab / thinkorswim | disabled-compare | C | yes | swing_engine/features/cross_section.py close_pos (= IBS) + MOC entry hook | Index-ETF effect (Pagonidis 2013); weaker on single stocks; needs a close-fill entry mode. |
| **Momentum Pinball (LBR/RSI first-hour breakout)** `momentum_pinball` | Raschke & Connors | disabled-compare | D | no | new module (daily approximation labelled) / monitor path | True entry needs first-hour bars; daily approximation changes the method. |
| **Oops! gap-through reversal (Larry Williams; ChartSchool full-gap-down long)** `williams_oops` | Larry Williams; StockCharts / ChartSchool; TradeThatSwing | disabled-compare | D | yes | new module; same-day stop-entry fill | Book examples only; the '93%' claim is untraceable. |
| **P/E undervalued / overvalued vs its own average (TradeStation)** `pe_valuation_reversion` | TradeStation | disabled-compare | none | yes | new module + XBRL TTM EPS | Demonstration strategy; no evidence. |
| **Post-earnings-announcement drift (SUE)** `pead_sue` | Bernard-Thomas; Foster-Olsen-Shevlin; Martineau | disabled-compare | C | yes | new factor + earnings_dates_point_in_time | Dead in large caps since 2006 (Martineau); methods.md avoid-bucket for large caps. Replay only, small/mid split. |
| **Price Swing detector entries (Domenico D'Errico)** `derrico_price_swing` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; four swing definitions as variants; 20-bar time exit. |
| **RSI < 30 recovery confirmed by MACD cross (Webull)** `rsi_oversold_macd_confirm` | Webull | disabled-compare | none | yes | new module | Illustrative only. |
| **RSI regular / hidden divergence (TradingView)** `rsi_divergence` | TradingView | disabled-compare | D | yes | new module + swing_point_labeling | Anecdotal; 5-bar confirmation lag. |
| **Short-term (1-month) reversal** `short_term_reversal_1m` | Jegadeesh; Fama-French ST_Rev; de Groot-Huij-Zhou | disabled-compare | C | yes | swing_engine/features/cross_section.py rev_21d | Fails VW replication (HXZ -0.26%, t=-1.31); large-cap weekly version keeps 30-50 bp/week net. Use as entry timing inside momentum candidates, only in low-turnover names. |
| **SimpleMeanReversion z-score (Anthony Garner)** `zscore_mean_reversion_garner` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C Python backtest article, in-sample. |
| **Stress strategy (Perry Kaufman)** `kaufman_stress` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample; index hedge leg not modelled (long-only engine). |
| **Three Period Divergence (Perry Kaufman)** `kaufman_three_period_divergence` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module + stochastic_oscillator | S&C in-sample; note thinkorswim buys on bearish divergence as coded. |
| **Turnaround Tuesday** `turnaround_tuesday` | Quantified Strategies | disabled-compare | D | yes | new module (SPY) | Practitioner backtest, no snooping correction; 2.5% market exposure. |
| **Turtle Soup and Turtle Soup Plus One (failed 20-day breakout fade)** `turtle_soup` | Linda Bradford Raschke & Laurence Connors; Raschke & Connors; Linda Raschke (+1) | disabled-compare | D | yes | new module; needs stop-entry hook | Originator claims only; poor in persistent trends. |
| **Parabolic short / crash-bounce reversal** `parabolic_short_long_reversal` | Kristjan Kullamagi (Qullamaggie); Lance Breitstein; Stonks Capital (Niv Goren) (+2) | avoid | C- | no | swing_engine/monitor/smallcap.py (alerts only) | Engine is long-only; borrow, SSR, halts and squeezes make the short untestable with free data; triggers are intraday. Monitor alerts only, per methods.md 7b. |
| **Weekly / daily contrarian reversal (Lehmann, Lo-MacKinlay)** `weekly_daily_contrarian` | Lehmann; Lo-MacKinlay contrarian; Khandani-Lo | avoid | C | yes | swing_engine/features/cross_section.py rev_5d (feature exists) | Arbitraged away since 1995 and needs a dollar-neutral short book; rev_5d stays as a ranker feature. |

## Strategies: chart and bar patterns

disabled-compare: 16, avoid: 2

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Consecutive up/down closes and BarUpDn (thinkorswim, TradeStation, TradingView)** `consecutive_bars` | Charles Schwab / thinkorswim; TradeStation; TradingView | disabled-compare | none | yes | new module; up_days_3 exists | Demonstration strategies; consecutive-down is the Connors mean-reversion mirror. |
| **Fibonacci retracement pullback (Webull, ChartSchool, Dow/Hamilton 1/3-2/3)** `fibonacci_retracement_pullback` | Webull; StockCharts / ChartSchool | disabled-compare | D | yes | new module + swing_point_labeling | No evidence Fibonacci ratios beat arbitrary levels: replay against a 50%-only control. |
| **Golden Triangle (Charlotte Hudgin)** `hudgin_golden_triangle` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample. |
| **Harmonic patterns (Gartley only; Carney ratios)** `harmonic_gartley` | StockCharts / ChartSchool; Scott Carney / H.M. Gartley | disabled-compare | none | yes | new module + swing_point_labeling | No independent evidence. Only the Gartley ratios are captured (0.786 XA PCZ, BC 1.27-1.618, AB=CD); Bat/Butterfly/Crab/Shark/Cypher ratio tables are in Carney's books and not reproduced, so those stay out. |
| **Inside-bar and outside-bar breakouts (thinkorswim, TradeStation, TradingView, Williams/Crabel)** `inside_outside_bar_breakout` | Charles Schwab / thinkorswim; TradeStation; TradingView (+2) | disabled-compare | D | yes | swing_engine/features/patterns.py inside_day (flag exists) | No robust stand-alone test; NR7/ID-NR4 tests are the closest (C). |
| **Key reversal day (thinkorswim, TradeStation, classic)** `key_reversal_day` | Charles Schwab / thinkorswim; TradeStation | disabled-compare | D | yes | swing_engine/features/patterns.py key_reversal (flag exists) | Weak: SentimenTrader 41% positive after a month; ~600-reversal study found no lasting prediction. |
| **Lizards (new 10-day low with long lower tail; Jeff Cooper)** `lizards_cooper` | Jeff Cooper | disabled-compare | D | yes | new module | Author examples only. |
| **Objective chart-pattern detector (Lo-Mamaysky-Wang kernel regression) standing in for vendor pattern engines** `classic_pattern_detector_lmw` | Charles Schwab / thinkorswim; Fidelity; E*TRADE (Morgan Stanley) (+7) | disabled-compare | C | yes | new features/patterns3.py + pattern-breakout module | LMW: patterns carry incremental information but no profitable rule shown. thinkorswim / Recognia / Finviz algorithms are unpublished, so one objective detector replaces them; Bulkowski stats are descriptive priors only. |
| **Pivot Extension reversal (TradeStation, TradingView)** `pivot_extension_reversal` | TradeStation; TradingView | disabled-compare | none | yes | new module; features/levels.py pivots | Demonstration strategy. |
| **Point & Figure signals (double/triple top buys, catapults, price objectives)** `point_and_figure_signals` | StockCharts / ChartSchool; Nasdaq Dorsey Wright; Tom Dorsey | disabled-compare | C | yes | new module (P&F column builder) | Long practitioner history; limited academic testing. Bullish Percent Index is a breadth by-product. |
| **Semi-Cup formation detector (thinkorswim)** `semi_cup_detector` | Charles Schwab / thinkorswim | disabled-compare | none | yes | features (new) for base_breakout | Exact published detector; no trade rule, so it is a feature for base_breakout. |
| **Smash Day and Hidden Smash Day reversals (Larry Williams)** `williams_smash_day` | Larry Williams | disabled-compare | D | yes | new module; stop-entry hook | Originator examples only; use with the higher-timeframe trend. |
| **Three-Bar Inside Bar (Johnan Prathap)** `three_bar_inside_bar_prathap` | Charles Schwab / thinkorswim | disabled-compare | D | yes | new module | S&C in-sample. |
| **Trend Knockout (TKO, Dave Landry)** `tko_landry` | StockCharts / ChartSchool; Dave Landry | disabled-compare | D | yes | new module | Wide-range threshold and trigger window undefined in the source; parameters must be logged as trials. |
| **Trendline breakout (TradeStation Trendline LE, Finviz TL signals)** `trendline_break` | Finviz; TradeStation | disabled-compare | none | yes | new module + swing_point_labeling | Trendline fitting through confirmed pivots; detector unpublished. |
| **Wyckoff accumulation: spring / test / SOS / LPS entries** `wyckoff_spring_accumulation` | StockCharts / ChartSchool; Richard D. Wyckoff | disabled-compare | D | yes | new module (trading-range box approximation) | Discretionary method; the classic file gives a testable approximation (TR box, spring close back inside, low-volume test). |
| **ICT / smart-money-concepts liquidity and FVG swings** `ict_smc_liquidity` | ICT (Inner Circle Trader) / Smart Money Concepts | avoid | D | yes | - | No tests; vocabulary marketing; rules too discretionary to code faithfully. |
| **Pure price-action structure swings (HH/HL, The Strat)** `price_action_structure_strat` | The Strat | avoid | D | yes | swing_engine/swing_point_labeling | Vocabulary only, no tests; the codeable structure lives in swing_point_labeling. |

## Strategies: factor, event and calendar rules (academic and quant)

implement: 9, disabled-compare: 3, blocked (paid data): 1, avoid: 8

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Cross-sectional momentum rank (12-1 and Jegadeesh-Titman 6-1)** `xs_momentum_rank` | Jegadeesh-Titman; Fama-French UMD; Daniel-Moskowitz WML definition (+1) | implement | A | yes | swing_engine/features/cross_section.py mom_12_1 (rank missing) | Grade A (Jegadeesh-Titman, HXZ VW replication 1.19%/mo). Engine use: percentile rank as the universe filter plus a monthly top-decile replay; crash control via momentum_crash_filter_dm and volatility_scaling_book. |
| **Earnings announcement premium (Frazzini-Lamont)** `earnings_announcement_premium` | Frazzini-Lamont; Barber-De George-Lehavy-Trueman | implement | B | yes | features (new): expected-announcement-month flag | B, global. Calendar tilt toward holding quality momentum names into scheduled reports; gap risk is the cost. |
| **Earnings-announcement abnormal return continuation (Abr)** `earnings_announcement_return_abr` | Chan-Jegadeesh-Lakonishok | implement | B | yes | features (new) + earnings_dates_point_in_time | B in HXZ (0.74%/mo, t=5.85) but post-2014 unverified: re-test on 2015-2026 before relying on it. |
| **Industry / sector momentum overlay** `industry_momentum_overlay` | Moskowitz-Grinblatt | implement | B | yes | features (new): sector rank from SIC (EDGAR) or sector ETFs | B (Moskowitz-Grinblatt, survives HXZ). Use as a ranking input (prefer longs in top industries), not a standalone system. |
| **Opportunistic insider purchases (Cohen-Malloy-Pomorski routine filter)** `opportunistic_insider_purchases_cmp` | Cohen-Malloy-Pomorski | implement | B | yes | swing_engine/strategies/insider_cluster.py + monitor/rules/form4_buy_and_cluster.py | B: opportunistic buys 82 bp/mo VW, routine ~0. Adds the routine/opportunistic split to insider_cluster; edge now prints mostly on the filing day, so enter at the next open. |
| **Residual (idiosyncratic) momentum** `residual_momentum` | Blitz-Huij-Martens | implement | B | yes | research/ranker.py feature (new) | B: about twice the risk-adjusted profit of raw momentum and holds up better in VW tests. Needs Fama-French 3 factors (free, Ken French library) and 36 months of history (Alpha Vantage / EODHD free daily history; Massive Basic has 2 years). |
| **Same-calendar-month return seasonality (Heston-Sadka)** `heston_sadka_seasonality` | Heston-Sadka | implement | B | yes | research/ranker.py feature (new) | B, survives VW/NYSE breakpoints at every lag. Needs 5-20 years of monthly history (free from Alpha Vantage monthly adjusted). |
| **Short-term momentum in high-turnover stocks (Medhat-Schmeling)** `high_turnover_short_term_momentum` | Medhat-Schmeling | implement | B | yes | features (new): turnover = volume / shares outstanding | B. Gates reversal entries: a big 1-month move on high turnover is a continuation candidate, not a fade. |
| **Turn-of-the-month window** `turn_of_month` | Quantified Strategies; Ariel; Lakonishok-Smidt (+1) | implement | B | yes | strategies/playbook.py calendar tilt (new) | B, persistent but small (~0.55% per 4-day window). Use as an entry/exit timing tilt; QS index rule replayed for comparison. |
| **Pre-holiday effect** `pre_holiday_effect` | StockCharts / ChartSchool; Yale Hirsch / Stock Trader's Almanac; Ariel (+1) | disabled-compare | C | yes | calendar flag (new) + data/calendar.py | Decayed in large caps after 1990 (Ko 2021); tie-breaker only. |
| **Revenue surprise (Jegadeesh-Livnat)** `revenue_surprise` | Jegadeesh-Livnat | disabled-compare | C | yes | new factor (XBRL revenue) | Marginal (t ~2.2); minor confirmation feature. |
| **Santa Claus rally window** `santa_claus_rally` | Yale & Jeffrey Hirsch | disabled-compare | C | yes | calendar flag (new) | Almanac averages, not cost-tested. |
| **Analyst forecast revision momentum** `analyst_revision_momentum` | Chan-Jegadeesh-Lakonishok; Hawkins-Chamberlin-Daniel | blocked (paid data) | B | no | - | B (CJL; HXZ Re1 0.81%/mo) but needs I/B/E/S-type consensus history. |
| **Congressional-trade following** `congressional_trade_copying` | Congressional-trade ETFs (NANC, KRUZ) | avoid | Neg | yes | - | No edge post-STOCK Act (45-day lag); NANC/KRUZ track the S&P. |
| **Core position plus options overlay** `core_position_options_overlay` | Reddit sweep (r/Trading) | avoid | D | yes | - | Options strategy; the engine trades stock. |
| **Crypto-proxy equities (digital-asset treasuries)** `crypto_proxy_equities` | Digital-asset treasury equities | avoid | C | yes | - | Negative-carry beta; mNAV discount trap. |
| **Day-of-week / weekend effect** `day_of_week_weekend` | French; Schwert | avoid | D | yes | - | Disappeared after publication (Schwert 2003). |
| **Overnight drift in the 2-3 a.m. ET futures window** `overnight_drift_futures` | Boyarchenko-Larsen-Whelan | avoid | C | no | - | Needs intraday futures data and has averaged ~0 since 2021. |
| **Policy-shock V-recovery buying** `policy_shock_v_recovery` | Events sweep (Liberation Day 2025) | avoid | C | yes | - | Two cases, no rule; the mechanical part is the IBD follow-through day (ibd_market_school_ftd_dd). |
| **Pre-FOMC announcement drift trade** `pre_fomc_drift_trade` | Lucca-Moench; Kurov-Wolfe-Gilbert | avoid | C | yes | - | Gone after 2015 (Kurov-Wolfe-Gilbert); kept only as macro_event_calendar_flag. |
| **Top-1 market-cap rotation** `top1_market_cap_rotation` | Reddit sweep (r/Daytrading) | avoid | D | yes | - | Curiosity; survivorship and tax issues. |

## Regime tools (market gates and exposure overlays)

have: 4, implement: 12, disabled-compare: 14, blocked (paid data): 1, avoid: 2

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Market regime playbook (index trend, volatility, breadth -> allowed strategies)** `market_regime_playbook` | swing-engine playbook; IBD (M rule); Pradeep Bonde (Stockbee) | have | B | yes | swing_engine/strategies/playbook.py + features/regime.py | Exists: high_vol_selloff / correction / healthy_uptrend / narrow_uptrend / choppy states map to per-strategy risk multipliers. |
| **Participation breadth: % above 50-day / 200-day (Keller)** `pct_above_ma_breadth` | David Keller (StockCharts); EdgeRater | have | C | yes | swing_engine/features/breadth.py pct_above_50 / pct_above_200 | Exists; thresholds must be calibrated on the engine universe (methods.md 8 #4). |
| **Stockbee Market Monitor 4% counts and 10-day ratio** `stockbee_market_monitor_ratio` | Pradeep Bonde (Stockbee) | have | C | yes | swing_engine/features/breadth.py up4_count / down4_count / ratio_10d | Exists and feeds the playbook breadth state. |
| **Trend filter: 10-month SMA / 200-day (Faber; thinkorswim EightMonthAvg)** `trend_filter_10m_200d` | Faber; Charles Schwab / thinkorswim | have | B | yes | swing_engine/strategies/playbook.py (SPY below sma_200 = correction) | B as a drawdown reducer, C as a return enhancer. |
| **Advance/decline line vs its average (McEwan AdvanceDeclineCumulative)** `advance_decline_line` | Charles Schwab / thinkorswim | implement | D | yes | swing_engine/features/breadth.py (new: advances, declines, ad_line) | Computable from the universe panel; NYSE A/D history itself is not free beyond what the panel holds. |
| **Arthur Hill breadth model (AD%, % above 200-day hysteresis, HL%; SPXA50R timing)** `hill_breadth_model` | StockCharts / ChartSchool; Arthur Hill | implement | C | yes | swing_engine/features/breadth.py pct_above_200 (+ AD%, HL%) | methods.md 7a #1: the pullback family uses Hill-style hysteresis; thresholds need engine-universe calibration. |
| **Equal-weight vs cap-weight regime width (RSP vs SPY)** `equal_weight_vs_cap_weight` | Invesco RSP vs SPDR SPY (ETF ratio) | implement | none | yes | swing_engine/strategies/playbook.py input (new) | Cheap width signal from free ETF bars; measure as a playbook input. |
| **Halloween / Sell-in-May overlay (incl. Six-Month Cycle MACD)** `halloween_seasonal_overlay` | Charles Schwab / thinkorswim; Bouman & Jacobsen; StockCharts / ChartSchool (+1) | implement | B | yes | swing_engine/strategies/playbook.py exposure scaler (new) | B (Bouman-Jacobsen, 36 of 37 markets) but the weak half is usually still positive: use as an exposure scaler, not a switch. |
| **IBD Market School: distribution days and follow-through day (M rule)** `ibd_market_school_ftd_dd` | IBD / William O'Neil (MarketSurge) | implement | C | yes | features/market_school.py (proposed) | methods.md P0 #2; M caught both 2025-26 V-recoveries. Needs real index/ETF volume (local duckdb data is synthetic). |
| **Macro event calendar flag (FOMC / CPI / NFP)** `macro_event_calendar_flag` | Lucca-Moench; Kurov-Wolfe-Gilbert | implement | C | yes | swing_engine/monitor/rules/market_wide_suppression.py + calendar (new) | Flatten high-beta longs into prints; the pre-FOMC drift trade itself is gone (separate avoid item). |
| **McClellan Oscillator and Summation Index** `mcclellan_oscillator` | Charles Schwab / thinkorswim | implement | D | yes | swing_engine/features/breadth.py (new columns) | Breadth feature used by Keller's healthy-bull test and the Hindenburg Omen. |
| **Momentum crash regime filter (Daniel-Moskowitz bear state)** `momentum_crash_filter_dm` | Daniel-Moskowitz | implement | B | yes | swing_engine/strategies/playbook.py input (new) | B. Rule: 24-month market return < 0 and high 126-day vol -> cut momentum/breakout exposure. Needs 24+ months of SPY. |
| **Stockbee primary indicator (25%-in-a-quarter counts) and 50%-in-a-month excess** `stockbee_primary_q25` | Pradeep Bonde (Stockbee) | implement | C | yes | swing_engine/features/breadth.py (extend: q25_ratio) | Small extension named in methods.md 7a #1 (q25_ratio). |
| **Time-series momentum regime (12-month and 3-month excess return sign)** `time_series_momentum_regime` | Moskowitz-Ooi-Pedersen; Hurst-Ooi-Pedersen | implement | B | yes | swing_engine/strategies/playbook.py input (new) | B; live CTA record weaker than backtests. Allow longs in an asset/sector only when its 12m (and 3m) excess return > 0. |
| **VIX level regime (20 / 30 thresholds)** `vix_level_regime` | Charles Schwab / thinkorswim | implement | none | yes | swing_engine/strategies/playbook.py input (new); vol_regime uses realized vol today | Thresholds are descriptive (no backtest); VIX is free from CBOE. Nagel 2012: reversal pays most when VIX is high, so it is also the switch for mean-reversion sizing. |
| **Zweig Breadth Thrust and companion thrusts (Deemer 1.97, Nasdaq 62%, near-miss 0.60)** `zweig_breadth_thrust` | Martin Zweig; Walter Deemer; SentimenTrader | implement | C | yes | swing_engine/features/breadth.py (add ad_ratio_10d_ema, zbt_state) | About 14-20 signals since 1945, all higher at 6-12 months, but small-sample; CXO found no lead at <= 21 days. |
| **Aggregate short interest index (Rapach-Ringgenberg-Zhou)** `aggregate_short_interest_index` | Rapach-Ringgenberg-Zhou | disabled-compare | C | yes | regime replay; FINRA short interest | Slow macro overlay; detrending details unverified. |
| **Coppock Curve** `coppock_curve` | Edwin 'Sedge' Coppock | disabled-compare | D | yes | regime replay (monthly) | About five monthly signals since the late 1980s; too few to validate. |
| **DecisionPoint Trend Model (5/20/50/200 EMA states)** `decisionpoint_trend_model` | StockCharts / ChartSchool; Carl Swenlin / Erin Swenlin | disabled-compare | C | yes | regime replay vs trend_state | Mechanical MA model; mixed MA-trend evidence. |
| **Dow Theory confirmation gate (DJIA and transports)** `dow_theory_confirmation` | Charles Dow; William P. Hamilton; Robert Rhea | disabled-compare | C | yes | regime replay (DIA / IYT) | Brown-Goetzmann-Kumar 1998: Hamilton's calls had positive risk-adjusted returns; compare with the 200-day gate. |
| **Elder Impulse System (13 EMA + MACD-histogram colour)** `elder_impulse_system` | Alexander Elder | disabled-compare | D | yes | regime/exit replay | No independent test. |
| **Guppy Multiple Moving Average ribbons** `guppy_gmma` | Daryl Guppy; StockCharts / ChartSchool; Charles Schwab / thinkorswim | disabled-compare | D | yes | regime replay | No independent test. |
| **Hindenburg Omen** `hindenburg_omen` | StockCharts / ChartSchool; Jim Miekka | disabled-compare | D | yes | regime replay + mcclellan_oscillator | ~20% hit rate with many false positives; computable from the universe panel. |
| **Kaufman monthly seasonal frequency system** `kaufman_seasonal_trading` | Charles Schwab / thinkorswim | disabled-compare | D | yes | regime replay (monthly) | S&C in-sample; 4-year frequency window is noisy. |
| **Kirkpatrick indicator rule set (ADX regime, RSI range shift, MA trend proxies)** `kirkpatrick_indicator_rules` | Fidelity; Charles Kirkpatrick | disabled-compare | none | yes | regime-classifier replay | Educational thresholds; RSI bull/bear range shift worth one test. |
| **Major Bear Market Aware exit/re-entry (Katsanos)** `katsanos_bear_market_aware` | Charles Schwab / thinkorswim | disabled-compare | D | yes | regime replay (weekly) | S&C in-sample; needs weekly OHLCV and VIX (free). |
| **Trend Quantification and Asset Allocation (Hill, 25% steps)** `trend_quantification_hill` | StockCharts / ChartSchool; Arthur Hill | disabled-compare | D | yes | exposure-scaler replay | Illustrative only. |
| **VIX timing vs its moving average (Gardner)** `vix_ma_timing_gardner` | Charles Schwab / thinkorswim | disabled-compare | D | yes | regime replay | S&C in-sample. |
| **Volatility Switch trend / mean-reversion router (Ron McEwan)** `volatility_switch_mcewan` | Charles Schwab / thinkorswim | disabled-compare | D | yes | regime router experiment | S&C in-sample. |
| **Zweig Four Percent Model (weekly index 4% reversals)** `zweig_four_percent_model` | Charles Schwab / thinkorswim | disabled-compare | D | yes | regime replay (weekly) | thinkorswim study; classic market-timing model, no evidence captured. |
| **Options-flow and gamma methods (0DTE-aware intraday structure, gamma meme squeezes)** `options_flow_gamma_methods` | SpotGamma (0DTE research) | blocked (paid data) | D | no | - | Needs dealer-gamma / options-flow data (paid); monitor keeps warn-only squeeze alerts. |
| **Hybrid Seasonal System (Katsanos)** `hybrid_seasonal_katsanos` | Charles Schwab / thinkorswim | avoid | D | yes | - | Exact seasonal windows and thresholds not captured (description only); its parts are cataloged (halloween, vix, katsanos_vfi_vzo). |
| **Market-structure changes (PDT repeal, 23x5 extended hours, tokenized venues)** `market_structure_changes_2026` | FINRA RN 26-10; 23x5 exchange trading | avoid | none | yes | - | Not methods: no trade logic. They are re-validation triggers (gap statistics after 2026-12-06). |

## Ratings (vendor and practitioner scores)

disabled-compare: 1, approximate: 13, blocked (paid data): 6, avoid: 1

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Technical Stock Rating (Katsanos)** `katsanos_technical_stock_rating` | Charles Schwab / thinkorswim | disabled-compare | D | yes | features (new) + katsanos_vfi_vzo | Exact published formula (not proprietary); in-sample; 63-bar hold strategy replay. |
| **Barchart Opinion (13-indicator composite)** `barchart_opinion` | Barchart | approximate | C | yes | features (new) | Legacy indicator list rebuilt; Barchart's own backtests only. |
| **Dorsey Wright P&F relative strength and Technical Attribute** `dorsey_wright_rs_technical_attribute` | Nasdaq Dorsey Wright; Tom Dorsey | approximate | C | yes | features (new) + point_and_figure_signals | Box size and attribute definitions unconfirmed; PDP lagged S&P. |
| **IBD Accumulation/Distribution Rating** `ibd_acc_dis_rating` | IBD / William O'Neil (MarketSurge) | approximate | C | yes | features (new) | Open approximation has 0.67 rank correlation to IBD. |
| **IBD Composite Rating** `ibd_composite_rating` | IBD / William O'Neil (MarketSurge) | approximate | C | yes | features (new) | Weights unpublished; built from the other IBD approximations. |
| **IBD EPS Rating (open reconstruction)** `ibd_eps_rating` | IBD / William O'Neil (MarketSurge) | approximate | B | yes | features (new) from SEC XBRL | ~8-point mean error reconstruction; earnings momentum evidence. |
| **IBD Relative Strength Rating (40/20/20/20 reconstruction)** `ibd_rs_rating` | IBD / William O'Neil (MarketSurge) | approximate | B | yes | swing_engine/features/patterns2.py rs_63d_rank (63-day only); new rs_rating_ibd | open8585 reconstruction matches IBD within ~1 point; momentum evidence underneath. |
| **IBD SMR Rating (sales, margins, ROE)** `ibd_smr_rating` | IBD / William O'Neil (MarketSurge) | approximate | C | yes | features (new) from XBRL | Quintile grade; profitability factor evidence underneath. |
| **Recognia / Trading Central technical events catalog (Fidelity, E*TRADE, IBKR, Merrill, Webull)** `recognia_technical_events` | Fidelity; E*TRADE (Morgan Stanley); Interactive Brokers (+3) | approximate | D | yes | features (new) event generator | Vendor detectors unpublished; rebuild events from our own indicator crossovers and the LMW detector. |
| **Recognia Technical Summary Score (recency-weighted event vote)** `recognia_technical_summary_score` | Fidelity; E*TRADE (Morgan Stanley); Interactive Brokers (+3) | approximate | D | yes | features (new) on top of recognia_technical_events | Exact weighting published; only evidence is agreement with 3 technicians, not returns. |
| **Relative Rotation Graphs (JdK RS-Ratio / RS-Momentum)** `rrg_relative_rotation` | StockCharts / ChartSchool; RRG Research; Julius de Kempenaer | approximate | C | yes | features (new) on sector ETFs | Exact formula unpublished; community z-score approximation. Sector momentum underneath is B. |
| **Stock Rover ratings and scores** `stock_rover_ratings` | Stock Rover | approximate | none | yes | features (new) | Rebuildable from XBRL + FINRA short interest; vendor weights unpublished. |
| **StockCharts Technical Rank (SCTR)** `sctr` | StockCharts / ChartSchool | approximate | C | yes | features (new) percentile by cap group | Exact weights published; ~90% momentum. The 20-day ROC component contradicts short-term reversal. |
| **TradingView Technical Ratings (26-signal vote) and its strategy wrapper** `tv_technical_ratings` | TradingView | approximate | none | yes | features (new) + indicator_library_long_tail | Published rule set rebuilt; trend and contrarian votes partly cancel; StochRSI/BBP trend definition must come from the Pine source. |
| **Equity Summary Score (LSEG StarMine)** `fidelity_equity_summary_score` | Fidelity | blocked (paid data) | C | no | - | Needs third-party analyst rating histories. |
| **Schwab Equity Ratings (A-F)** `schwab_equity_ratings` | Charles Schwab / thinkorswim | blocked (paid data) | C | no | - | Needs analyst forecasts and unpublished weights. |
| **Seeking Alpha Quant Rating and factor grades** `seeking_alpha_quant` | Seeking Alpha | blocked (paid data) | C | no | - | Needs revisions data; weights unpublished. |
| **Trading Central Quantamental Rating** `tc_quantamental_rating` | Interactive Brokers; Trading Central / Recognia | blocked (paid data) | none | no | - | Proprietary vendor data; the technical-event part is rebuilt under recognia_technical_events. |
| **Zacks Rank** `zacks_rank` | Zacks | blocked (paid data) | B | no | - | Needs consensus estimate history; estimate-revision drift is B evidence (see analyst_revision_momentum). |
| **Zacks Style Scores (VGM)** `zacks_style_scores` | Zacks | blocked (paid data) | C | no | - | Paid estimates; formulas not retrieved. |
| **Deepvue proprietary ratings and preset screens** `deepvue_ratings_presets` | Deepvue | avoid | none | yes | - | Ratings formulas unpublished; its presets are cataloged separately (minervini_trend_template, qullamaggie_flag, vcp_sepa_breakout, high_volume_edge, strength_on_down_day, ibd_rs_rating). |

## Screens and quant screening factors

have: 4, implement: 6, disabled-compare: 3, approximate: 1, blocked (paid data): 2, avoid: 1

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Generic screeners (Stock Hacker, TV, Finviz filters, TC2000 PCF, Webull, Robinhood Legend, RadarScreen, Koyfin, Merrill)** `scan_engine_generic` | Charles Schwab / thinkorswim; Webull; Robinhood (+6) | have | none | yes | swing_engine/data/universe.py + features/panel.py columns | Tooling, not a signal: boolean filters over panel columns. Named presets (unusual volume, 52w highs, Minervini, etc.) are separate items. |
| **New high/low, gap, gainers and activity screens (IBKR 13/26/52-week, Finviz signals)** `new_high_low_activity_screens` | Interactive Brokers; Finviz; Market Chameleon | have | C | yes | swing_engine/features/cross_section.py high_52w / gap_pct / ret_1d | Exists; analyst-upgrade and news parts of Finviz need paid/news feeds (not built). |
| **Real-time alert scanners (Fidelity ATP, Trade Ideas alerts)** `realtime_alert_scanners` | Fidelity; Trade Ideas | have | none | no | swing_engine/monitor/ (rvol_gate_triggers, watchlist_hit, smallcap, form4, 8-K rules) | Vendor alert definitions unpublished; the engine monitor implements its own rvol/gap/halt/filing alerts. |
| **Relative / unusual volume screens (IBKR Hot by Volume, Finviz, Schwab, TC2000, rvol-first)** `relative_volume_screen` | Interactive Brokers; Finviz; TC2000 (Worden) (+1) | have | C | yes | swing_engine/features/cross_section.py rvol_day + features/rvol.py | Exists; IBKR uses a 30-day EMA of volume as the base (variant). |
| **Gross and cash-based profitability** `gross_cash_profitability` | Novy-Marx; Ball et al. cash-based OP | implement | B | yes | features (new) from SEC XBRL | Cash-based OP survives HXZ (0.63%/mo); quality screen against momentum-crash junk. |
| **IBKR Hot Contracts by Price (move / average daily change)** `hot_by_price_normalized_move` | Interactive Brokers | implement | none | yes | features (new): ret_1d / EMA(/close-open/) | Cheap feature column for the ranker. |
| **Low beta / betting-against-beta sizing penalty** `beta_low_volatility` | Frazzini-Pedersen; Baker-Bradley-Wurgler; Charles Schwab / thinkorswim | implement | B | yes | features (new): beta_252 + sizing penalty | B, but construction-sensitive (Novy-Marx-Velikov critique). Sizing insight, not a long-short book. |
| **Minervini 8-point Trend Template (Stage-2 screen)** `minervini_trend_template` | TradingView; Deepvue; Mark Minervini | implement | B | yes | features (new): sma_150, sma_200_slope_21, dist_52w_low; tt_pass_count | B as a filter (momentum + 52w-high components). Also gives tt_pass_count as a breadth gauge (methods.md 6.3). |
| **Quality minus junk (profitability, growth, safety, payout)** `quality_minus_junk` | Asness-Frazzini-Pedersen | implement | B | yes | features (new) from SEC XBRL | B, 24 countries; sub-component formulas approximated. |
| **Short interest and days-to-cover** `short_interest_days_to_cover` | Hong-Li-Ni-Scheinkman-Yan; Asquith-Pathak-Ritter | implement | B | yes | swing_engine/data/altdata.py + Massive short interest | Avoid longs in the top DTC decile unless trading a squeeze; strongest on the short/avoid side. |
| **High Volume Edge screen (highest volume in a year / ever)** `high_volume_edge` | Deepvue | disabled-compare | none | yes | features (new): vol_max_252 | Deepvue preset reconstructed from its name/description (formula unpublished); measure forward returns in replay. |
| **Hit and Run 'Hit List' filter (Jeff Cooper)** `cooper_hit_list` | Jeff Cooper | disabled-compare | D | yes | screen (new) | Author examples; $30 floor is a 1990s price rule. |
| **Relative strength on an index down day (Kell preset)** `strength_on_down_day` | Deepvue | disabled-compare | none | yes | features (new): ret_1d vs market ret_1d | Deepvue 'Oliver Kell Strength on Down Day' preset reconstructed: stock up while SPY/QQQ is down; measure in replay. |
| **IBD 50 list construction** `ibd_50_list` | IBD / William O'Neil (MarketSurge) | approximate | C | yes | screen (new) from IBD approximations | Thresholds/weights not retrieved; FFTY live record mixed. |
| **Option implied-volatility scans (IBKR, Market Chameleon)** `options_iv_scans` | Interactive Brokers; Market Chameleon | blocked (paid data) | none | no | - | Needs option chains / IV history. |
| **Sizzle Index (option volume vs 5-day average; thinkorswim)** `sizzle_index` | Charles Schwab / thinkorswim | blocked (paid data) | none | no | - | Needs per-symbol daily option volume. |
| **IBD Leaderboard** `ibd_leaderboard` | IBD / William O'Neil (MarketSurge) | avoid | none | no | - | Human-curated editorial list; not mechanical. |

## Indicators and feature columns

have: 6, implement: 25, disabled-compare: 2, blocked (paid data): 2, avoid: 4

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **52-week-high proximity (George-Hwang)** `fifty_two_week_high_proximity` | George-Hwang | have | C | yes | swing_engine/features/cross_section.py dist_52w_high | Corrected to C: significant only at 6 months in VW replication; use PTH > 0.9 as context. |
| **ADX / +DI / -DI (Wilder)** `adx_dmi` | Charles Schwab / thinkorswim | have | none | yes | swing_engine/features/patterns2.py adx_14 | Exists (round 4). |
| **Amihud illiquidity** `amihud_illiquidity` | Amihud | have | C | yes | swing_engine/features/cross_section.py amihud_21d | Exists; cost/tradability gate, not alpha (liquidity factors fail HXZ). |
| **Core indicators (SMA/EMA, RSI, MACD, Bollinger, ATR, returns, realized vol, volume averages)** `core_indicators` | Charles Schwab / thinkorswim | have | none | yes | swing_engine/features/indicators.py + features/cross_section.py | Exists per docs/feature-contract.md; covers the thinkorswim/TradeStation basic studies listed in the appendix. |
| **Pivot support/resistance levels (Schwab S/R, Trading Central key levels)** `pivot_support_resistance_levels` | Fidelity; E*TRADE (Morgan Stanley); Interactive Brokers (+1) | have | none | yes | swing_engine/features/levels.py | Exists. Trading Central's congestion algorithm is unpublished; confirmed pivots over 60 bars are the free equivalent. |
| **Relative-strength percentile rank (63-day)** `rs_percentile_rank` | swing-engine | have | A | yes | swing_engine/features/patterns2.py rs_63d_rank | Exists; 126-day and 12-1 ranks pending (xs_momentum_rank). |
| **Anchored VWAP (pivot-low, earnings, max-volume, YTD anchors) with bands** `anchored_vwap_feature` | TradingView; Charles Schwab / thinkorswim | implement | D | yes | features/avwap.py (proposed) | Execution benchmark, weak as a predictor; needed by avwap_pullback_shannon. |
| **Bollinger %b and BandWidth (22 rules)** `bollinger_pctb_bandwidth` | John Bollinger; Charles Schwab / thinkorswim | implement | none | yes | swing_engine/features/indicators.py bb_width_20 (exists); add bb_pctb_20 | BandWidth exists; %b is one line. |
| **Commodity Channel Index (Lambert)** `cci_indicator` | Charles Schwab / thinkorswim | implement | none | yes | features (new): cci_20 | Needed by CCI Correction, Barchart Opinion, TV ratings, NR7 ChartSchool filter. |
| **Elder Force Index (FI(2), FI(13))** `elder_force_index` | Alexander Elder; Charles Schwab / thinkorswim | implement | D | yes | features (new) | Needed by Elder Triple Screen. |
| **Floor pivot points (standard, Fibonacci, Woodie, DeMark, Camarilla)** `floor_pivot_points` | StockCharts / ChartSchool; TradingView; Charles Schwab / thinkorswim | implement | D | yes | features (new): monthly/weekly pivots | Shannon sells the first third near R2; no equity test. |
| **Frog-in-the-pan information discreteness filter** `frog_in_the_pan` | Da-Gurun-Warachka | implement | B | yes | features (new): id_score | B: smooth grinders keep momentum ~8 months, gap-driven winners fade after 2. |
| **Gap-fill base rates by gap size** `gap_fill_base_rates` | thetrading.tools gap analysis; StockCharts / ChartSchool; TradeThatSwing | implement | D | yes | research table (new) on the engine universe | Descriptive priors for the monitor's gap alerts; fade only small gaps. |
| **Historical earnings-reaction statistics (realized side of Market Chameleon)** `historical_earnings_reaction_stats` | Market Chameleon | implement | C | yes | features (new) + earnings_dates_point_in_time | Free part of the implied-vs-realized comparison: average absolute post-earnings move per symbol for sizing/avoidance. |
| **Kaufman Efficiency Ratio and KAMA** `kaufman_efficiency_ratio_kama` | Perry Kaufman; Charles Schwab / thinkorswim | implement | D | yes | features (new): er_10, kama | Cheap regime feature to route between trend and mean-reversion modules; validate before trusting. |
| **Keltner channels (original 1960 and Raschke EMA/ATR)** `keltner_channels` | Chester Keltner; Linda Raschke | implement | D | yes | features (new): kc_upper/lower | Needed by TTM Squeeze and Keltner breakout. |
| **Long-tail indicator library (the remaining broker studies: oscillators, bands, adaptive MAs, volume studies)** `indicator_library_long_tail` | Robinhood; Charles Schwab / thinkorswim | implement | none | yes | features/indicators_ext.py (new; feature-only) | Implemented as feature columns only; each gets an information-coefficient test in the ranker before any rule may use it. Several are inputs to TV Technical Ratings (Hull MA, Awesome Osc, StochRSI, Ultimate Osc, Bull/Bear Power) and Barchart Opinion. |
| **Overnight vs intraday return decomposition** `overnight_intraday_decomposition` | Cliff-Cooper-Gulen; Lou-Polk-Skouras | implement | C | yes | features (new): ret_overnight, ret_intraday, mom_overnight | B as a feature (momentum built overnight persists); C as a trade. |
| **Parabolic SAR (Wilder) and SAR trailing exits** `parabolic_sar` | J. Welles Wilder; TradeStation; Charles Schwab / thinkorswim | implement | D | yes | features (new) + exit hook | Bollinger pairs it with Method II as the stop. |
| **Point-in-time earnings dates (EDGAR 8-K Item 2.02)** `earnings_dates_point_in_time` | SEC EDGAR | implement | none | yes | swing_engine/data/edgar.py (8-K feed exists) -> features days_since_earnings | Cross-cutting dependency: power_gap verification, EP catalyst, Rich & Rich, Abr, SUE, earnings premium, reaction stats. |
| **Pring KST (Know Sure Thing)** `kst_pring` | Martin Pring | implement | D | yes | features (new) | Used by Recognia oscillator events. |
| **Relative-strength line vs SPY (Mansfield RS, IBD RS line new high, RS vs SPY 'market first')** `relative_strength_line` | Mansfield Charts / Stan Weinstein; IBD / William O'Neil (MarketSurge); TraderLion (Moglen) (+2) | implement | C | yes | features (new): rs_line, rs_line_new_high, mansfield_rs | RS ranking is A; this normalisation is untested on its own. RS-line new high before price is the TraderLion/IBD cue. |
| **Shared feature backlog (ema_10/50, sma_5/150, sma_200 slope, dist_52w_low, higher_lows_n, atr_22, rank_ret_126d)** `ma_and_structure_feature_backlog` | swing-engine | implement | none | yes | swing_engine/features/patterns2.py (extend) | Inputs named by methods.md 7a #3 and by the Trend Template, Kell, Landry and Chandelier items. |
| **Stochastic oscillator (fast / slow / full)** `stochastic_oscillator` | Charles Schwab / thinkorswim | implement | none | yes | features (new): stoch_k / stoch_d | Needed by the Anti, Moving Momentum, Elder, Stochastic Pop, Kaufman divergence and TV ratings. |
| **Supertrend (indicator and trailing stop)** `supertrend` | TradingView; Olivier Seban | implement | D | yes | features (new) + exit hook | Trailing-stop / trend filter; no independent evidence. |
| **Swing-point labeling (Williams short/intermediate/long-term points, ZigZag, swing charting)** `swing_point_labeling` | Larry Williams; Charles Schwab / thinkorswim; StockCharts / ChartSchool (+1) | implement | none | yes | swing_engine/features/levels.py pivots (width 5) exist; add hierarchy | Needed by Fibonacci, harmonics, divergence, RSITrend, trendlines; ZigZag last leg repaints, so only confirmed swings. |
| **Volume Flow Indicator and Volume Zone Oscillator (Katsanos)** `katsanos_vfi_vzo` | Charles Schwab / thinkorswim; Markos Katsanos | implement | none | yes | features (new) | Needed by Technical Stock Rating and Hybrid Seasonal. |
| **Volume profile from daily bars (POC, value area, HVN/LVN)** `volume_profile_daily` | TradingView; Charles Schwab / thinkorswim | implement | D | yes | features (new) | Daily-bar approximation distributes each bar's volume across its range; IBKR EP uses HVN support. |
| **Volume-flow indicators (OBV, A/D line, Chaikin MF/osc, MFI, PVT, Intraday Intensity)** `volume_flow_indicators` | Robinhood; Charles Schwab / thinkorswim | implement | D | yes | features (new) | Used for squeeze direction bias (Bollinger), %b+MFI, II% reversals; weak-moderate evidence for volume-weighted flow. |
| **Williams %R** `williams_percent_r` | Larry Williams; Charles Schwab / thinkorswim | implement | D | yes | features (new): pct_r_14 | Cheap; Elder second-screen condition; 125-day %R as a trend gauge. |
| **Williams VIX Fix (synthetic VIX)** `williams_vix_fix` | Larry Williams | implement | D | yes | features (new): wvf_22 | Stock-level fear gauge for mean-reversion filters; no independent test. |
| **Idiosyncratic volatility (IVOL) penalty** `idiosyncratic_volatility` | Ang-Hodrick-Xing-Zhang | disabled-compare | C | yes | features (new) + FF daily factors | Fails VW replication; measure only as an avoid filter. |
| **MAX / lottery-stock flag** `max_lottery` | Bali-Cakici-Whitelaw | disabled-compare | C | yes | features (new): max_ret_21d | Fails VW replication; conviction penalty for spike-driven setups. |
| **IV Rank and IV Percentile (tastytrade)** `iv_rank_percentile` | tastytrade | blocked (paid data) | none | no | - | Needs daily IV history. |
| **Option greek and option-chain studies (thinkorswim)** `options_greek_studies` | Charles Schwab / thinkorswim | blocked (paid data) | none | no | - | Delta/gamma/theta/vega/rho, open interest, probability cones, theoretical prices need option chains. |
| **Account and P&L display studies (thinkorswim)** `account_display_studies` | Charles Schwab / thinkorswim | avoid | none | yes | - | Account net liquidation / open P&L plots are not signals. |
| **Barchart Trend Seeker** `barchart_trend_seeker` | Barchart | avoid | none | yes | - | Formula unpublished ('wave theory, momentum and volatility'); nothing to rebuild. |
| **Gann levels, Ermanometry and Elliott-wave time counts (thinkorswim studies)** `gann_elliott_tools` | Charles Schwab / thinkorswim | avoid | none | yes | - | Numerology-style projections with no testable rule or evidence. |
| **Multi-currency correlation tools (thinkorswim)** `fx_multi_currency_tools` | Charles Schwab / thinkorswim | avoid | none | yes | - | FX pair tools; the engine trades US equities. |

## Risk, exits, sizing and validation standards

have: 6, implement: 11, disabled-compare: 2, blocked (paid data): 2, avoid: 1

| Item | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |
|---|---|---|---|---|---|---|
| **Basic exit library (stop loss, profit target, % / point / $ stops, breakeven, % and ATR trailing, time exits)** `basic_exit_library` | Charles Schwab / thinkorswim; TradeStation; Fidelity (+3) | have | none | yes | swing_engine/research/backtest.py TrailingStop + Signal stop/target + max_hold_days | Exists: TrailingStop(pct / atr_mult / breakeven_after_r) ratchets on closes; max_hold_days time stop. |
| **Custom strategy template (TradeStation Custom Strategy LE/LX/SE/SX)** `custom_strategy_template` | TradeStation | have | none | yes | swing_engine/strategies/_base.py PanelStrategy | Exists: every strategy is a PanelStrategy with params, geometry checks and a market gate. |
| **Fixed-fractional risk, ATR stops and portfolio caps** `fixed_fractional_risk_caps` | Charles Schwab / thinkorswim | have | none | yes | swing_engine/risk/sizing.py + risk/limits.py + risk/killswitch.py | Exists: 1% risk on stop distance (worst-case marketable fill), max position 10%, sector 30%, daily loss 3%, drawdown 15% kill switch. |
| **ML ranker / meta-labeling on an existing edge** `ml_ranker_meta_labeling` | swing-engine | have | C | yes | swing_engine/research/ranker.py | Ranker exists (ranks only, never prices); meta-labeling is an extension. |
| **R-multiple reporting and SQN (Van Tharp)** `r_multiple_sqn_reporting` | Van Tharp Institute | have | none | yes | swing_engine/research/metrics.py (r_multiple, expectancy) | Exists for R and expectancy; SQN = sqrt(N) x mean(R)/std(R) is a one-line addition. |
| **Scam, noise and base-rate filter** `scam_noise_filter` | swing-engine | have | none | yes | docs/methods.md section 5 + docs/gates.md | Documented: impersonation, paid rooms, survivorship case studies, results-post hygiene; 93-97% of persistent day traders lose. |
| **Backtester order types and hooks (stop entries, limit-below-close, MOC, OCO, scale-out, scale-in, same-day exits)** `backtester_order_type_hooks` | TradeStation | implement | none | yes | swing_engine/research/backtest.py | Cross-cutting: most broker strategies use buy stops; Connors uses closes/limits; TPS/Turtles scale in; every school scales out. |
| **Chandelier exit (highest high - 3 x ATR(22))** `chandelier_exit` | Chuck LeBeau; TradeStation; Alexander Elder | implement | C | yes | swing_engine/research/backtest.py TrailingStop (atr trail exists on best close with atr_14) | Small change: add atr_22 and a high-based extreme; ATR trails are the exit in the Wilcox-Crittenden stock tests. |
| **Cost-aware rank hysteresis (Novy-Marx-Velikov buy/hold spread)** `cost_aware_rank_hysteresis` | Novy-Marx-Velikov | implement | A | yes | swing_engine/research/ranker.py consumers (new rule) | Enter only in the top 10% of a rank, exit below the top 20-30%. |
| **Drawdown risk rules (Elder 2% / 6% monthly stop; Turtle 10% drawdown -> 20% smaller account)** `drawdown_risk_rules` | Alexander Elder; Curtis Faith | implement | none | yes | swing_engine/risk/limits.py (new monthly rule) | Engine has daily-loss and max-drawdown gates; the monthly stop and drawdown-scaled sizing are new. |
| **Extra exit rules (profitable closes, channel trailing, give-back % of open profit, ATR target & trail, VoltyExpanClose LX, entry-bar ATR stop)** `extra_exit_rules` | TradeStation; Charles Schwab / thinkorswim | implement | none | yes | swing_engine/research/backtest.py (new exit hooks) | Needed to copy broker strategies faithfully; no evidence on their own. |
| **Microcap control: value-weighted / NYSE-breakpoint backtests (Hou-Xue-Zhang)** `microcap_control_vw_nyse` | Hou-Xue-Zhang | implement | A | yes | swing_engine/research/backtest.py option (new) | 64-65% of anomalies fail; exclude stocks below the NYSE 20th size percentile. |
| **Multiple-testing validation (White's Reality Check, FDR, permutation tests)** `multiple_testing_validation` | Park-Irwin; Bajgrowicz-Scaillet; Aronson | implement | C | yes | swing_engine/research/metrics.py deflated_sharpe + research/trials.py (exist) | Deflated Sharpe and the trial log exist; Reality Check / FDR / Masters permutation are the missing standards. Grade refers to the cited surveys. |
| **Open-source factor benchmark (Chen-Zimmermann, JKP)** `open_factor_benchmark_cz` | Jensen-Kelly-Pedersen; Chen-Zimmermann | implement | A | yes | research (new) sanity check | Free monthly long-short returns to check our signal implementations. |
| **Post-publication decay haircut (McLean-Pontiff)** `post_publication_haircut` | McLean-Pontiff | implement | A | yes | docs/gates.md planning rule | Assume live edge <= ~half of the published edge. |
| **Turtle N sizing, unit limits and pyramiding** `turtle_n_sizing_unit_limits` | Curtis Faith | implement | B | yes | swing_engine/risk/sizing.py (equivalent at a 2N stop) + new unit limits | B for vol-normalised sizing; correlated-unit limits are new. |
| **Volatility scaling of the book (Barroso-Santa-Clara constant-vol; Moreira-Muir)** `volatility_scaling_book` | Moreira-Muir; Cederburg-O'Doherty-Wang-Yan; Barroso-Santa-Clara | implement | B | yes | swing_engine/risk/sizing.py (per-position vol target exists) | B for momentum books (crash control); COWY 2020 shows no general Sharpe gain, so use for risk stability, not alpha. |
| **Indicator-based exits (close < MA5 with MA5 < MA10, RSI(7) back below 70, stochastic cross above 80)** `indicator_exit_signals_webull` | Webull | disabled-compare | none | yes | exit variants in replay | Illustrative; measure against the MA trail. |
| **Wyckoff distribution exit signals (UTAD failure, SOW, LPSY)** `wyckoff_distribution_exit` | Richard D. Wyckoff | disabled-compare | D | yes | exit replay | Discretionary; approximated with trading-range box rules. |
| **Earnings implied move vs historical reaction (Market Chameleon)** `earnings_implied_vs_realized_move` | Market Chameleon | blocked (paid data) | B | no | - | Implied side needs option chains; variance risk premium evidence is B. |
| **Expected move (one standard deviation; tastytrade)** `expected_move` | tastytrade | blocked (paid data) | none | no | - | Needs IV or straddle prices; realized-move proxy lives in historical_earnings_reaction_stats. |
| **Guru Grades (pundit market-forecast accuracy)** `guru_market_calls` | CXO Advisory | avoid | D | yes | - | Evidence that pundit calls have ~47% accuracy; nothing to build, and pundit calls are excluded as inputs. |

## What cannot be done with free data

The free stack is daily OHLCV (Massive Basic: 2 years, 5 calls/min, 15-minute delayed), SEC EDGAR (filings, Form 4, XBRL), FINRA / Nasdaq short-interest and short-volume files, CBOE VIX, Ken French factors and Alpha Vantage / EODHD free tiers. Against that:

**Blocked outright (`blocked_paid_data`)**

- **Analyst forecast revision momentum** (`analyst_revision_momentum`): Monthly consensus EPS history (I/B/E/S, Zacks, FactSet), not in the free stack. B (CJL; HXZ Re1 0.81%/mo) but needs I/B/E/S-type consensus history.
- **Earnings implied move vs historical reaction (Market Chameleon)** (`earnings_implied_vs_realized_move`): Option chains (implied) + daily OHLCV (realized). Implied side needs option chains; variance risk premium evidence is B.
- **Equity Summary Score (LSEG StarMine)** (`fidelity_equity_summary_score`): Third-party analyst ratings history (not free). Needs third-party analyst rating histories.
- **Expected move (one standard deviation; tastytrade)** (`expected_move`): Option IV or straddle prices. Needs IV or straddle prices; realized-move proxy lives in historical_earnings_reaction_stats.
- **IV Rank and IV Percentile (tastytrade)** (`iv_rank_percentile`): Daily implied volatility history (paid options data). Needs daily IV history.
- **Option greek and option-chain studies (thinkorswim)** (`options_greek_studies`): Option chains, greeks, open interest (paid). Delta/gamma/theta/vega/rho, open interest, probability cones, theoretical prices need option chains.
- **Option implied-volatility scans (IBKR, Market Chameleon)** (`options_iv_scans`): Options chains / IV history (paid); Daily OHLCV + options. Needs option chains / IV history.
- **Options-flow and gamma methods (0DTE-aware intraday structure, gamma meme squeezes)** (`options_flow_gamma_methods`): Options flow and dealer gamma estimates (paid). Needs dealer-gamma / options-flow data (paid); monitor keeps warn-only squeeze alerts.
- **Schwab Equity Ratings (A-F)** (`schwab_equity_ratings`): Fundamentals (SEC), analyst estimates, short interest (FINRA), prices. Needs analyst forecasts and unpublished weights.
- **Seeking Alpha Quant Rating and factor grades** (`seeking_alpha_quant`): Fundamentals, analyst revisions, price. Needs revisions data; weights unpublished.
- **Sizzle Index (option volume vs 5-day average; thinkorswim)** (`sizzle_index`): Daily per-symbol total call and put option volume (5-day history); stock price, volume, market cap. Needs per-symbol daily option volume.
- **Trading Central Quantamental Rating** (`tc_quantamental_rating`): Proprietary vendor data. Proprietary vendor data; the technical-event part is rebuilt under recognia_technical_events.
- **Zacks Rank** (`zacks_rank`): Analyst EPS estimate history and surprises. Needs consensus estimate history; estimate-revision drift is B evidence (see analyst_revision_momentum).
- **Zacks Style Scores (VGM)** (`zacks_style_scores`): Price + estimates + fundamentals. Paid estimates; formulas not retrieved.

**Doable only in part, or only approximately**

- **Option-derived inputs** (Sizzle, IV rank/percentile, expected move, implied earnings move, IV scans, put/call, dealer gamma, 0DTE structure): no free historical option chains. The realized-move half is built instead (`historical_earnings_reaction_stats`).
- **Analyst estimates and revisions** (Zacks Rank and Style Scores, Seeking Alpha Quant, Schwab Equity Ratings, Fidelity Equity Summary Score, revision momentum, analyst SUE): need I/B/E/S-type consensus history. Time-series SUE from XBRL EPS is the free fallback (`pead_sue`).
- **Proprietary vendor scores** whose formulas are unpublished (Trading Central Quantamental, Barchart Trend Seeker, Deepvue ratings, Recognia's quant score, Finviz pattern strength, thinkorswim pattern targets, Trade Ideas Holly): cannot be copied; where a description exists the catalog rebuilds it (`approximate`), otherwise `avoid`.
- **Intraday triggers** (opening-range highs, first-hour ranges, Momentum Pinball, 5/15/65-minute AVWAP triggers, Stockbee's first-30-minute entries, session VWAP): free minute bars exist only as delayed, 2-year, rate-limited history, so these are replayed on daily approximations that are labelled as such.
- **Long history and survivorship**: 2 years of free Massive history is too short for 12-1 momentum backtests over several cycles, 24-month crash states, Heston-Sadka lags, Coppock/seasonal systems and breadth-thrust calibration; a survivorship-free universe with all delisted names is not available free (the universe builder accepts a residual gap).
- **Exchange-wide breadth series** (NYSE advances/declines, new highs/lows, up-volume since the 1940s) are not free; the engine computes breadth from its own universe, so classic thresholds (0.40/0.615 ZBT, Hindenburg 2.8%) must be re-calibrated.
- **Real index volume** for IBD distribution days and follow-through days: the local duckdb history is synthetic for indexes; ETF volume (SPY/QQQ) is the free proxy.
- **Fundamental timing**: XBRL facts and 13F holdings are free but lag (13F up to 45 days), so CAN SLIM's I and the IBD EPS/SMR approximations are point-in-time but stale relative to the vendors.
- **Borrow and short data** for the short side (parabolic shorts, pair short legs): borrow fees and locate availability are not free, and the engine is long-only anyway.

## Avoid list (with reasons)

- **Account and P&L display studies (thinkorswim)** (`account_display_studies`): Account net liquidation / open P&L plots are not signals.
- **Barchart Trend Seeker** (`barchart_trend_seeker`): Formula unpublished ('wave theory, momentum and volatility'); nothing to rebuild.
- **Congressional-trade following** (`congressional_trade_copying`): No edge post-STOCK Act (45-day lag); NANC/KRUZ track the S&P.
- **Core position plus options overlay** (`core_position_options_overlay`): Options strategy; the engine trades stock.
- **Crypto-proxy equities (digital-asset treasuries)** (`crypto_proxy_equities`): Negative-carry beta; mNAV discount trap.
- **Day-of-week / weekend effect** (`day_of_week_weekend`): Disappeared after publication (Schwert 2003).
- **Deepvue proprietary ratings and preset screens** (`deepvue_ratings_presets`): Ratings formulas unpublished; its presets are cataloged separately (minervini_trend_template, qullamaggie_flag, vcp_sepa_breakout, high_volume_edge, strength_on_down_day, ibd_rs_rating).
- **Discretionary teaching frameworks (Caruso growth/story, Breitstein playbook, Bear Bull Traders, Farley 7 Bells)** (`discretionary_teaching_frameworks`): Pure discretion or reading lists; no mechanical rule to test.
- **Gann levels, Ermanometry and Elliott-wave time counts (thinkorswim studies)** (`gann_elliott_tools`): Numerology-style projections with no testable rule or evidence.
- **Guru Grades (pundit market-forecast accuracy)** (`guru_market_calls`): Evidence that pundit calls have ~47% accuracy; nothing to build, and pundit calls are excluded as inputs.
- **Hybrid Seasonal System (Katsanos)** (`hybrid_seasonal_katsanos`): Exact seasonal windows and thresholds not captured (description only); its parts are cataloged (halloween, vix, katsanos_vfi_vzo).
- **IBD Leaderboard** (`ibd_leaderboard`): Human-curated editorial list; not mechanical.
- **ICT / smart-money-concepts liquidity and FVG swings** (`ict_smc_liquidity`): No tests; vocabulary marketing; rules too discretionary to code faithfully.
- **Intraday-only day-trading strategies (ORB, first-hour breakout, intraday gap reversal, session VWAP, close-at-EOD)** (`orb_intraday_day_trading`): Not swing (flat by the close) and an independent ORB replication nets ~0 after costs; the session-VWAP study failed replication.
- **Market-structure changes (PDT repeal, 23x5 extended hours, tokenized venues)** (`market_structure_changes_2026`): Not methods: no trade logic. They are re-validation triggers (gap statistics after 2026-12-06).
- **Multi-currency correlation tools (thinkorswim)** (`fx_multi_currency_tools`): FX pair tools; the engine trades US equities.
- **Overnight drift in the 2-3 a.m. ET futures window** (`overnight_drift_futures`): Needs intraday futures data and has averaged ~0 since 2021.
- **Pair trading long/short on a price ratio (D'Errico)** (`pair_trading_ratio`): Market-neutral pair needs a short leg (engine long-only); the long leg alone duplicates relative_strength_line / katsanos_rsmk.
- **Parabolic short / crash-bounce reversal** (`parabolic_short_long_reversal`): Engine is long-only; borrow, SSR, halts and squeezes make the short untestable with free data; triggers are intraday. Monitor alerts only, per methods.md 7b.
- **Policy-shock V-recovery buying** (`policy_shock_v_recovery`): Two cases, no rule; the mechanical part is the IBD follow-through day (ibd_market_school_ftd_dd).
- **Pre-FOMC announcement drift trade** (`pre_fomc_drift_trade`): Gone after 2015 (Kurov-Wolfe-Gilbert); kept only as macro_event_calendar_flag.
- **Pure price-action structure swings (HH/HL, The Strat)** (`price_action_structure_strat`): Vocabulary only, no tests; the codeable structure lives in swing_point_labeling.
- **Top-1 market-cap rotation** (`top1_market_cap_rotation`): Curiosity; survivorship and tax issues.
- **Trade Ideas Holly AI** (`trade_ideas_holly_ai`): Intraday only (no overnight), proprietary nightly optimisation, vendor-only stats; its families map to cataloged MR/pullback items.
- **TradingView Greedy Strategy (gap pyramiding)** (`greedy_strategy_tv`): Exact rules not retrieved; cannot be copied faithfully. Gap pyramiding ideas are covered by kaufman_gap_momentum.
- **Weekly / daily contrarian reversal (Lehmann, Lo-MacKinlay)** (`weekly_daily_contrarian`): Arbitraged away since 1995 and needs a dollar-neutral short book; rev_5d stays as a ranker feature.

## Broker built-in appendix coverage

All 573 entries of `brokers.json` `catalog_appendix` are mapped to an item (full list with URLs in `catalog.json` `appendix_coverage`). Built-ins that duplicate a curated item (for example `Price Channel LE` -> `donchian_channel_breakout`) are merged into it; short-entry (SE/SX) versions sit with their long mirror.

- **thinkorswim_strategies** (95): `ehlers_dsp_family` 7, `ma_crossover_family` 6, `oscillator_cross_family` 6, `basic_exit_library` 6, `vervoort_heikin_ashi_family` 5, `katsanos_trend_strength_filters` 4, `price_zone_oscillator` 4, `supertrend_flip_strategy` 2, `intermarket_divergence_katsanos` 2, `bollinger_band_mean_reversion` 2, `consecutive_bars` 2, `orb_intraday_day_trading` 2, `full_gap_continuation_bar` 2, `inside_outside_bar_breakout` 2, `key_reversal_day` 2, `pair_trading_ratio` 2, `three_bar_inside_bar_prathap` 2, `volume_flow_indicators` 1, `advance_decline_line` 1, `calhoun_adx_breakout` 1, `calhoun_atr_high_sma_breakout` 1, `bb_bullish_engulfing_kosinski` 1, `floor_pivot_points` 1, `donchian_channel_breakout` 1, `trend_filter_10m_200d` 1, `calhoun_four_day_breakout` 1, `gandalf_project_research_system` 1, `kaufman_gap_momentum` 1, `hudgin_golden_triangle` 1, `halloween_seasonal_overlay` 1, `hybrid_seasonal_katsanos` 1, `bull_flag_breakout` 1, `pendergast_long_haul` 1, `katsanos_bear_market_aware` 1, `calhoun_mean_reversion_swing` 1, `fx_multi_currency_tools` 1, `derrico_price_swing` 1, `apirine_roc_bands` 1, `rsi_trend_zigzag_luo` 1, `katsanos_rsmk` 1, `kaufman_seasonal_trading` 1, `sentiment_zone_oscillator` 1, `zscore_mean_reversion_garner` 1, `rich_simple_trend_channel` 1, `katsanos_stiffness` 1, `kaufman_stress` 1, `pendergast_swingthree` 1, `tac_dmi_trend_start` 1, `katsanos_technical_stock_rating` 1, `kaufman_three_period_divergence` 1, `vix_ma_timing_gardner` 1, `volatility_switch_mcewan` 1, `extra_exit_rules` 1, `katsanos_vpn_breakout` 1
- **tradestation_strategies** (128): `basic_exit_library` 29, `oscillator_cross_family` 12, `extra_exit_rules` 10, `fundamental_setup_technical_trigger` 10, `backtester_order_type_hooks` 8, `ma_crossover_family` 8, `orb_intraday_day_trading` 7, `custom_strategy_template` 4, `inside_outside_bar_breakout` 4, `key_reversal_day` 4, `pe_valuation_reversion` 4, `volatility_expansion_close` 4, `bollinger_band_mean_reversion` 2, `chandelier_exit` 2, `consecutive_bars` 2, `full_gap_continuation_bar` 2, `keltner_channel_breakout` 2, `breakout_52w` 2, `parabolic_sar_reversal` 2, `parabolic_sar` 2, `pivot_extension_reversal` 2, `pivot_reversal_breakout` 2, `donchian_channel_breakout` 2, `trendline_break` 2
- **thinkorswim_studies** (350): `indicator_library_long_tail` 131, `ehlers_dsp_family` 58, `core_indicators` 26, `volume_flow_indicators` 15, `options_greek_studies` 9, `relative_strength_line` 8, `oscillator_cross_family` 8, `floor_pivot_points` 6, `adx_dmi` 5, `beta_low_volatility` 5, `swing_point_labeling` 5, `account_display_studies` 4, `intermarket_divergence_katsanos` 4, `gann_elliott_tools` 4, `ma_crossover_family` 4, `kaufman_efficiency_ratio_kama` 3, `volume_profile_daily` 3, `stochastic_oscillator` 3, `tac_dmi_trend_start` 3, `advance_decline_line` 2, `anchored_vwap_feature` 2, `bollinger_pctb_bandwidth` 2, `cci_indicator` 2, `mcclellan_oscillator` 2, `guppy_gmma` 2, `williams_percent_r` 2, `katsanos_trend_strength_filters` 2, `katsanos_vfi_vzo` 2, `calhoun_adx_breakout` 1, `calhoun_atr_high_sma_breakout` 1, `basic_exit_library` 1, `ibs_mean_reversion` 1, `orb_intraday_day_trading` 1, `darvas_box` 1, `elder_force_index` 1, `zweig_four_percent_model` 1, `kaufman_seasonal_trading` 1, `fx_multi_currency_tools` 1, `parabolic_sar` 1, `parabolic_sar_reversal` 1, `donchian_channel_breakout` 1, `price_zone_oscillator` 1, `apirine_roc_bands` 1, `relative_volume_screen` 1, `katsanos_rsmk` 1, `semi_cup_detector` 1, `sentiment_zone_oscillator` 1, `td_sequential` 1, `rich_simple_trend_channel` 1, `katsanos_stiffness` 1, `kaufman_stress` 1, `vervoort_heikin_ashi_family` 1, `katsanos_technical_stock_rating` 1, `ttm_squeeze` 1, `volatility_switch_mcewan` 1, `katsanos_vpn_breakout` 1

The 131 thinkorswim studies without a dedicated item go to `indicator_library_long_tail` (feature columns only, information-coefficient tested in the ranker before any rule uses them): AccelerationBands, AccelerationDecelerationOsc, AccumulationSwingIndex, ADXR, APTR, AroonIndicator, AroonOscillator, AwesomeOscillator, BalanceOfMarketPower, CAM-Indicator, ChaikinVolatility, ChandeMomentumOscillator, CondensedCandles, CongAdaptiveMovingAverage, CSI, CumulativeVolumeIndex, DEMA, DemandIndex, DetrendedPriceOsc, DisparityIndex, DisplacedEMA, Displacer, DMA, DMI-ReversalAlerts, DMI-StochasticExtreme, DoubleSmoothedStochastic, DynamicMomentumIndex, EaseOfMovement, ErgodicOsc, ESDBands, ExponentialDeviationBands, ForecastOscillator, FreedomOfMovement, FW-CCI-Advanced, FW-CCI-Basic, FW-DPO-MOBO, FW-MMG, FW-MOBO-Advanced, FW-MOBO-Basic, FW-SOAP, MAD, MarkerIndicator, MarketForecast, MarketSentiment, MassIndex, MedianAverage, MktFacilitationIdx, ModifiedTrueRange, MomentumPercentDiff, MoneyFlowOscillator, MovAvgBands, MovAvgBandWidth, MovAvgEnvelope, MovAvgTriangular, MovAvgWeighted, NegativeVolumeIndex, PolarizedFractalEfficiency, PolychromMtm, PositiveVolumeIndex, PriceActionIndicator, PriceOsc, PriceTimeFilteringAccVolume, PriceTimeFilteringBarCount, PriceVolumeRank, ProjectionBands, ProjectionOscillator, QStick, RainbowAverage, RandomWalkIndex, RangeBands, RangeIndicator, Ray, RayBearPower, RayBullPower, RDOC, RelativeMomentumIndex, RelativeRangeIndex, RelativeVolatilityIndex, ReverseEngineeringMACD, ReverseEngineeringRSI, RS-VA-EMA, SchaffTrendCycle, SectorRotationModel, SlowRSI, SlowVSI, Spearman, StandardDevChannel, StandardError, StandardErrorBands, StandardErrorChannel, STARCBands, StochasticDistanceOsc, StochasticFullDiff, StochasticMACD, StochasticMomentumIndex, StochRSI, SVEStochRSI, SwingIndex, TEMA, TimeSeriesForecast, TMV, TradeVolumeIndex, TrendNoiseBalance, TrendPeriods, TrendPersistenceRate, TrendQuality, TRIX, TrueRangeAdjEMA, TrueRangeSpecifiedVolume, TrueStrengthIndex, TTM-LRC, TTM-ScalperAlert, TTM-Trend, TTM-Wave, UlcerIndex, UltimateBands, UltimateChannels, UltimateOscillator, UndersampledDoubleMovAvg, VariableMA, VelocityAndAcceleration, VolumeOsc, VolumeRateOfChange, VolumeWeightedMACD, VortexIndicator, WarningSymbols, WeaknessInAStrongTrend, WeeklyAndDailyMACD, WeeklyAndDailyPPO, WilliamsAlligator, WoodiesCCI.

**Gap in the appendix itself**: the captured thinkorswim study list jumps from `FW-SOAP` to `MACD` (no studies starting with G-L, such as Heikin-Ashi, Ichimoku, Keltner, KST or Linear Regression). Those tools are still in the catalog from other sources (Ichimoku, Keltner, KST, Heikin-Ashi items), but a re-fetch of that page range would complete the thinkorswim list.

## Strategy cards to write

130 items (category strategy or strategy-like pattern, decision have / implement / implement_disabled_for_comparison):

| Slug | Name | Decision |
|---|---|---|
| `base_breakout` | Classic base breakout: cup-with-handle and flat base (O'Neil / IBD / MarketSurge) | have |
| `breakout_52w` | 52-week-high breakout on volume (Minervini / O'Neil lineage; TradeStation New High LE) | have |
| `episodic_pivot` | Episodic pivot, delayed day-2 entry | have |
| `insider_cluster` | Insider cluster buying (Form 4) follow-through | have |
| `momentum_burst` | Stockbee 4% momentum burst | have |
| `power_gap` | Power earnings gap / buyable gap-up, consolidation entry | have |
| `pullback_holy_grail` | Holy Grail pullback (ADX > 30, 20 EMA touch, buy over the touch-bar high) | have |
| `pullback_trend` | Pullback to a rising 20/50 MA in an uptrend (Landry / Raschke / Qullamaggie pullback core) | have |
| `qullamaggie_flag` | Qullamaggie momentum flag breakout | have |
| `rsi2_meanrev` | Connors RSI(2) mean reversion | have |
| `sr_bounce` | Support bounce (Schwab Learn / Joe Mazzola) | have |
| `sr_breakout` | Resistance breakout with measured-move target (Schwab Learn / Joe Mazzola) | have |
| `avwap_pullback_shannon` | Anchored-VWAP pullback (Brian Shannon multi-timeframe) | implement |
| `earnings_announcement_premium` | Earnings announcement premium (Frazzini-Lamont) | implement |
| `earnings_announcement_return_abr` | Earnings-announcement abnormal return continuation (Abr) | implement |
| `heston_sadka_seasonality` | Same-calendar-month return seasonality (Heston-Sadka) | implement |
| `high_turnover_short_term_momentum` | Short-term momentum in high-turnover stocks (Medhat-Schmeling) | implement |
| `industry_momentum_overlay` | Industry / sector momentum overlay | implement |
| `opportunistic_insider_purchases_cmp` | Opportunistic insider purchases (Cohen-Malloy-Pomorski routine filter) | implement |
| `pullback_ema_zone` | EMA-zone pullback (low in the 20-50 EMA band after 2 respected tests) | implement |
| `residual_momentum` | Residual (idiosyncratic) momentum | implement |
| `turn_of_month` | Turn-of-the-month window | implement |
| `xs_momentum_rank` | Cross-sectional momentum rank (12-1 and Jegadeesh-Titman 6-1) | implement |
| `apirine_roc_bands` | Rate of Change with Bands (Vitali Apirine) | disabled-compare |
| `bb_bullish_engulfing_kosinski` | Bollinger Bands with bullish engulfing (Pawel Kosinski) | disabled-compare |
| `bollinger_band_mean_reversion` | Bollinger band mean reversion (re-entry above the lower band; TradeStation, thinkorswim, TradingView, Webull) | disabled-compare |
| `bollinger_pctb_mfi_trend` | Bollinger Method II: %b + MFI trend confirmation | disabled-compare |
| `bollinger_squeeze_breakout` | Bollinger Squeeze breakout (Method I / Method IV) | disabled-compare |
| `bollinger_w_bottom_ii_reversal` | Bollinger Method III (Intraday Intensity) and W-bottoms | disabled-compare |
| `boomers_cooper` | Boomers (two inside days in an ADX > 30 trend; Jeff Cooper) | disabled-compare |
| `bull_flag_breakout` | Bull flag / high-tight flag breakout (Schwab Learn, Katsanos flags, O'Neil HTF) | disabled-compare |
| `calhoun_adx_breakout` | ADX Breakouts (Ken Calhoun) | disabled-compare |
| `calhoun_atr_high_sma_breakout` | ATR High / SMA breakouts (Ken Calhoun) | disabled-compare |
| `calhoun_four_day_breakout` | Four-Day Breakout (Ken Calhoun) | disabled-compare |
| `calhoun_mean_reversion_swing` | MeanReversionSwingLE (Ken Calhoun): 50% retracement then rise | disabled-compare |
| `canslim` | CAN SLIM selection (C-A-N-S-L-I) with base-breakout entries | disabled-compare |
| `cci_correction` | CCI Correction (weekly bias, daily CCI dip) | disabled-compare |
| `chartschool_gap_first_hour` | Gap trading first-hour range rules (Scott Andrews / ChartSchool) | disabled-compare |
| `classic_pattern_detector_lmw` | Objective chart-pattern detector (Lo-Mamaysky-Wang kernel regression) standing in for vendor pattern engines | disabled-compare |
| `connors_3day_high_low` | Connors 3-Day High/Low (ETF) | disabled-compare |
| `connors_cvr3_vix` | CVR3 VIX market timing (Connors) | disabled-compare |
| `connors_hpetf_rsi_variants` | Connors HPETF RSI(4) 25/75, Multiple Days Down, RSI 10/6 | disabled-compare |
| `connors_pctb` | Connors %b strategy (ETF) | disabled-compare |
| `connors_rsi2_variants` | Connors RSI(2) family variants (Double 7s, Cumulative RSI, R3, ConnorsRSI pullback, Alpha Formula) | disabled-compare |
| `connors_tps_scale_in` | Connors TPS (time, price, scale-in 10/20/30/40) | disabled-compare |
| `consecutive_bars` | Consecutive up/down closes and BarUpDn (thinkorswim, TradeStation, TradingView) | disabled-compare |
| `cooper_123_pullback` | 1-2-3-4 pullback (Jeff Cooper Hit and Run) | disabled-compare |
| `darvas_box` | Darvas Box breakout and pyramid | disabled-compare |
| `derrico_price_swing` | Price Swing detector entries (Domenico D'Errico) | disabled-compare |
| `donchian_channel_breakout` | Donchian / price-channel breakout (20-40 bar high; Cagigas, TradeStation, TradingView, 4-week rule) | disabled-compare |
| `ehlers_dsp_family` | Ehlers DSP indicators and strategies (roofing filter, super smoother, onset trend, universal/elegant osc, reverse EMA, Swami charts) | disabled-compare |
| `eighty_twenty_reversal` | 80-20 reversal (Raschke & Connors) | disabled-compare |
| `elder_ma_penetration_channel` | Elder MA-penetration channel swing (Fidelity Learning Center) | disabled-compare |
| `elder_triple_screen` | Elder Triple Screen | disabled-compare |
| `expansion_pivot_cooper` | Expansion Pivot (Jeff Cooper) | disabled-compare |
| `faber_sector_rotation` | Faber sector rotation (top-3 sectors by 3-month ROC, 10-month SMA filter) | disabled-compare |
| `fibonacci_retracement_pullback` | Fibonacci retracement pullback (Webull, ChartSchool, Dow/Hamilton 1/3-2/3) | disabled-compare |
| `full_gap_continuation_bar` | Full-gap entry bar (Gap Up LE: low > prior high; thinkorswim, TradeStation) | disabled-compare |
| `fundamental_setup_technical_trigger` | Fundamental setup + technical trigger (TradeStation Fundamntl & Chan/MACD/RSI/Stoch/Volty) | disabled-compare |
| `gandalf_project_research_system` | Gandalf Project Research System (D'Errico & Trombetta) | disabled-compare |
| `harmonic_gartley` | Harmonic patterns (Gartley only; Carney ratios) | disabled-compare |
| `heikin_ashi_trend_ride` | Heikin-Ashi trend riding (Valcu) | disabled-compare |
| `hudgin_golden_triangle` | Golden Triangle (Charlotte Hudgin) | disabled-compare |
| `ibd_other_bases` | IBD double bottom, ascending base, saucer and consolidation bases | disabled-compare |
| `ibs_mean_reversion` | Internal Bar Strength mean reversion (IBS < 0.2 buy, > 0.8 sell) | disabled-compare |
| `ichimoku_cloud_pullback` | Ichimoku cloud pullback (Kijun dip, Tenkan reclaim) | disabled-compare |
| `inside_outside_bar_breakout` | Inside-bar and outside-bar breakouts (thinkorswim, TradeStation, TradingView, Williams/Crabel) | disabled-compare |
| `intermarket_divergence_katsanos` | Intermarket divergence (BBDivergence, RegressionDivergence; Katsanos) | disabled-compare |
| `ipo_first_base_breakout` | IPO first-base breakout | disabled-compare |
| `katsanos_rsmk` | RSMK relative-strength strategy (Katsanos) | disabled-compare |
| `katsanos_stiffness` | Stiffness indicator strategy (Katsanos) | disabled-compare |
| `katsanos_trend_strength_filters` | Trend-strength filter family ADXTrend / ERTrend / R2Trend / VHFTrend (Katsanos) | disabled-compare |
| `katsanos_vpn_breakout` | VPN high-volume breakout (Markos Katsanos) | disabled-compare |
| `kaufman_gap_momentum` | Gap Momentum System (Perry Kaufman 2024) | disabled-compare |
| `kaufman_stress` | Stress strategy (Perry Kaufman) | disabled-compare |
| `kaufman_three_period_divergence` | Three Period Divergence (Perry Kaufman) | disabled-compare |
| `kell_cycle_of_price_action` | Kell Cycle of Price Action (Wedge Pop, EMA Crossback, Base n' Break, Wedge Drop; QQQ 20 EMA gate) | disabled-compare |
| `keltner_channel_breakout` | Keltner channel breakout (TradeStation, TradingView, Keltner 10-day rule) | disabled-compare |
| `key_reversal_day` | Key reversal day (thinkorswim, TradeStation, classic) | disabled-compare |
| `landry_bow_tie` | Landry Bow Tie, Proper Order and 90%-of-50-day-closing-high trend rules | disabled-compare |
| `last_stochastic_weekly` | The 'Last' Stochastic technique (weekly 39-period) | disabled-compare |
| `lizards_cooper` | Lizards (new 10-day low with long lower tail; Jeff Cooper) | disabled-compare |
| `ma_crossover_family` | Moving-average crossover family (price/MA, 2-line, 3-line, golden cross, VWMA/SMA, MHL MA, Breen bands, Webull 5/10/20) | disabled-compare |
| `macd_zero_line_swing_points` | MACD zero-line crosses confirmed by swing structure (ChartSchool) | disabled-compare |
| `momentum_pinball` | Momentum Pinball (LBR/RSI first-hour breakout) | disabled-compare |
| `moving_momentum_hill` | Moving Momentum (Arthur Hill) | disabled-compare |
| `nr7_nr4_range_contraction` | NR7 / NR4 / ID-NR4 range-contraction breakout (Crabel) | disabled-compare |
| `open_volatility_breakout` | Open +/- k x range volatility breakout (Williams GSV, Crabel stretch) | disabled-compare |
| `oscillator_cross_family` | Classic oscillator cross strategies (RSI 30/70, stochastic 20/80, %R, MACD signal/zero, PMO, DMI osc, momentum rising, Spectrum Bars) | disabled-compare |
| `parabolic_sar_reversal` | Parabolic SAR stop-and-reverse entries (TradeStation, TradingView) | disabled-compare |
| `pe_valuation_reversion` | P/E undervalued / overvalued vs its own average (TradeStation) | disabled-compare |
| `pead_sue` | Post-earnings-announcement drift (SUE) | disabled-compare |
| `pendergast_long_haul` | Long Haul (Donald Pendergast Jr.) | disabled-compare |
| `pendergast_swingthree` | SwingThree (Donald Pendergast) | disabled-compare |
| `pivot_extension_reversal` | Pivot Extension reversal (TradeStation, TradingView) | disabled-compare |
| `pivot_reversal_breakout` | Pivot Reversal breakout (confirmed swing high buy stop) | disabled-compare |
| `point_and_figure_signals` | Point & Figure signals (double/triple top buys, catapults, price objectives) | disabled-compare |
| `pre_holiday_effect` | Pre-holiday effect | disabled-compare |
| `price_zone_oscillator` | Price Zone Oscillator strategies (Khalil & Steckler) | disabled-compare |
| `radge_weekend_trend_trader` | Weekend Trend Trader (Nick Radge) | disabled-compare |
| `revenue_surprise` | Revenue surprise (Jegadeesh-Livnat) | disabled-compare |
| `rich_simple_trend_channel` | Simple Trend Channel system (James & John Rich) | disabled-compare |
| `rsi_divergence` | RSI regular / hidden divergence (TradingView) | disabled-compare |
| `rsi_oversold_macd_confirm` | RSI < 30 recovery confirmed by MACD cross (Webull) | disabled-compare |
| `rsi_trend_zigzag_luo` | RSITrend (Kevin Luo): RSI cross only in a ZigZag-confirmed trend | disabled-compare |
| `santa_claus_rally` | Santa Claus rally window | disabled-compare |
| `sentiment_zone_oscillator` | Sentiment Zone Oscillator strategy (Walid Khalil) | disabled-compare |
| `short_term_reversal_1m` | Short-term (1-month) reversal | disabled-compare |
| `slope_performance_trend` | Slope Performance Trend (price and relative slopes) | disabled-compare |
| `stine_insider_superstock_weekly` | Stine insider-buy superstocks (weekly volume thrust, magic line) | disabled-compare |
| `stochastic_pop_and_drop` | Stochastic Pop (Bernstein, Steckler/Hill) | disabled-compare |
| `supertrend_flip_strategy` | Supertrend / ATR-trailing-stop flip entries (TradingView, thinkorswim ATRTrailingStopLE) | disabled-compare |
| `tac_dmi_trend_start` | TAC_DMI trend-start system (BC Low) | disabled-compare |
| `td_sequential` | DeMark TD Sequential (setup 9, countdown 13) | disabled-compare |
| `the_anti` | The Anti (stochastic hook pullback; Raschke, Grimes) | disabled-compare |
| `three_bar_inside_bar_prathap` | Three-Bar Inside Bar (Johnan Prathap) | disabled-compare |
| `tko_landry` | Trend Knockout (TKO, Dave Landry) | disabled-compare |
| `trendline_break` | Trendline breakout (TradeStation Trendline LE, Finviz TL signals) | disabled-compare |
| `ttm_squeeze` | TTM Squeeze (BB inside Keltner, momentum fire) | disabled-compare |
| `turnaround_tuesday` | Turnaround Tuesday | disabled-compare |
| `turtle_breakout_systems` | Turtle System 1 (20/10 with skip rule) and System 2 (55/20) | disabled-compare |
| `turtle_soup` | Turtle Soup and Turtle Soup Plus One (failed 20-day breakout fade) | disabled-compare |
| `vcp_sepa_breakout` | Minervini VCP / SEPA pivot breakout | disabled-compare |
| `vervoort_heikin_ashi_family` | Vervoort Heikin-Ashi family (HACOLT, SVEHaTypCross, SVESC, SVEZLRBPercB, VolatilityBand) | disabled-compare |
| `volatility_expansion_close` | Volatility Expansion Close/Open entries (TradeStation, TradingView) | disabled-compare |
| `weinstein_stage2_breakout` | Weinstein Stage 2 breakout (weekly 30-week MA, Mansfield RS) | disabled-compare |
| `williams_oops` | Oops! gap-through reversal (Larry Williams; ChartSchool full-gap-down long) | disabled-compare |
| `williams_smash_day` | Smash Day and Hidden Smash Day reversals (Larry Williams) | disabled-compare |
| `wyckoff_spring_accumulation` | Wyckoff accumulation: spring / test / SOS / LPS entries | disabled-compare |
| `zscore_mean_reversion_garner` | SimpleMeanReversion z-score (Anthony Garner) | disabled-compare |


## Fact-check (2026-10-07)

Stopped early at the user's request. Claims marked "refuted (fix pending)" were checked against the source, but the files have **not** been edited yet. Claims marked "not yet checked" still need verification.

| Claim | File(s) | Verdict | Evidence URL |
|---|---|---|---|
| CMP 82 bp/month is the return on opportunistic buys | catalog.json (`opportunistic_insider_purchases_cmp` notes/evidence_text, `stine_insider_superstock_weekly`), CATALOG.md row, docs/methods/14 (l.123, l.227), docs/methods.md l.718, strategies/insider_cluster.md, stine_insider_superstock_weekly.md | refuted (fix pending). 82 bp/mo is the value-weighted five-factor alpha of a long-short portfolio (opportunistic buys minus opportunistic sells), t=2.15; equal-weighted 180 bp (t=6.07). Long-side regression: opportunistic buys add +90 bp/mo over all insider trades (t=4.64). | https://dash.harvard.edu/server/api/core/bitstreams/7312037e-2b77-6bd4-e053-0100007fdf3b/content |
| 80-20 buy setup: open in the top 20% of the range, close in the bottom 20% | strategies/eighty_twenty_reversal.md, catalog.json | confirmed | https://technical.traders.com/tradersonline/display.asp?art=2527 |
| 80-20 bar "open in the bottom 20%, close in the top 80%" | docs/methods.md l.299 (section 2d) | refuted (fix pending). The buy setup is the reverse: opens in the top 20% and closes in the bottom 20%. | same as above |
| NR7 Oxford Capital test period 1980-2011 | catalog.json (NR7/NR4 evidence) | refuted (fix pending). All three Oxford NR7 pages say 1 Jan 1980 to 31 Jan 2016, 42 futures, "not currently tradeable" after costs. The card's 1980-Jan 2016 is correct. | https://oxfordstrat.com/?p=3707 , https://oxfordstrat.com/?p=16086 |
| Oxford ORB/GSV 1980-2011 (C12/C18) | catalog.json | not yet checked (probably 1980-2016 as well) | - |
| Ehlers super smoother (a=exp(-1.414π/P), b=2a·cos(1.414π/P), c1=1-c2-c3) and 2-pole high-pass alpha/recursion; roofing 48/10 | strategies/ehlers_dsp_family.md | confirmed. Matches Ehlers' EasyLanguage. The card's "from memory" caveat can be dropped. | https://www.linnsoft.com/topic/super-smoother-and-roofing-filter |
| Kaufman Gap Momentum: cumulative vs. non-cumulative ratio | strategies/kaufman_gap_momentum.md | resolved, card fix pending. The published Traders' Tips (Zorro) code uses a non-cumulative ratio, 100·UpGaps/DnGaps over Period (1 if DnGaps=0), with an SMA signal over SignalPeriod. Defaults are 40/20. The "cumulative like OBV" wording in summaries does not match the code. | https://financial-hacker.com/the-gap-momentum-system/ |
| Turtle rules: N=(19·PDN+TR)/20; S1 skip rule (2N adverse before a profitable 10-day exit); 55-day failsafe; S1 exit 10-day low, S2 exit 20-day low; ½N pyramid; limits 4/6/10/12; whipsaw ½N stop | strategies/turtle_breakout_systems.md | confirmed | https://www.tradingwithrayner.com/wp-content/uploads/2014/11/OriginalTurtleRules.pdf |
| Wilcox-Crittenden 2005: 49.3% winners, W/L 2.56, ~15.2% expectancy, 305-day hold, 19.3% vs 12.0% CAGR, DD -20.8% vs -44.7% | strategies/turtle_breakout_systems.md | confirmed | https://www.cis.upenn.edu/~mkearns/finread/trend.pdf |
| Holy Grail: ADX(14) > 30 and rising, pullback to 20-period EMA | strategies/pullback_holy_grail.md | confirmed (secondary sources; some restatements say SMA, most say EMA) | https://tradingsetupsreview.com/the-holy-grail-trading-setup |
| Connors RSI(2): close > SMA200, buy RSI(2) < 10 (< 5 better), exit above the 5-day SMA | strategies/rsi2_meanrev.md | confirmed | https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2 |
| Double 7s SPY 1993-2007: 153 trades, +0.85%, 80.4% | rsi2_meanrev.md, connors_rsi2_variants.md | confirmed (book chapter) | https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf |
| HXZ Sue1 0.47% (t=3.42); Sue6 0.19, Sue12 0.11 | strategies/pead_sue.md | confirmed | https://www.nber.org/papers/w23394 |
| HXZ R11-1 1.19 (4.06), R11-6 0.81 (3.14), R6-1 0.60 (2.04), R6-6 0.82 (3.49), R6-12 0.55 (2.90) | strategies/xs_momentum_rank.md, catalog.json | confirmed | https://www.nber.org/papers/w23394 |
| HXZ 52w6 0.57 (t=2.02), 52w1 0.14 (t=0.43) | strategies/breakout_52w.md | confirmed | https://www.nber.org/papers/w23394 |
| HXZ residual momentum ε11-1 0.67 (3.91), ε11-6 0.55 (3.94), ε11-12 0.36 (2.96), ε6-6 0.49, ε6-12 0.39, ε6-1 0.20 | strategies/residual_momentum.md | confirmed | https://www.nber.org/papers/w23394 |
| BHM residual momentum 11.2%/12.5% vol, Sharpe 0.90 vs 0.45 | strategies/residual_momentum.md | confirmed (CXO summary) | https://www.cxoadvisory.com/momentum-investing/stripping-risks-from-a-stock-momentum-strategy/ |
| Daniel-Moskowitz: WML Sharpe 0.71, winners +15.3%/yr, losers -2.5%/yr, CAPM alpha 22.3%/yr | strategies/xs_momentum_rank.md | confirmed | https://www.nber.org/papers/w20439 |
| Bernard-Thomas: SUE spread positive in 41 of 48 quarters, 1974-85 | strategies/pead_sue.md | confirmed (secondary) | https://en.wikipedia.org/wiki/Post%E2%80%93earnings-announcement_drift |
| Martineau CFR 2022: large-cap PEAD gone since 2006, microcaps only recently | pead_sue.md, power_gap.md, episodic_pivot.md | confirmed | https://ideas.repec.org/a/now/jnlcfr/104.00000122.html |
| Zhou-Zhu FAJ 2012: ~15.3%/yr abnormal, Sharpe 1.52 | strategies/power_gap.md | confirmed (3.63%/quarter not separately seen) | https://engagedscholarship.csuohio.edu/bus_facpub/202 |
| Pagonidis IBS: > 30%/yr average alpha before costs | strategies/ibs_mean_reversion.md | confirmed (abstract via search summary) | https://www.quantconnect.com/forum/discussion/5675/mean-reversion-effect-in-etf-price-series/ |
| Pandey-Joshi: 16 country ETFs 2009-2019, basket Sharpe 2.9-3.9, open-to-open near zero | strategies/ibs_mean_reversion.md | confirmed | https://arxiv.org/html/2306.12434v1 |
| Pandey-Joshi: short borrow above ~0.15%/yr erodes the long/short version | strategies/ibs_mean_reversion.md l.56 | refuted (fix pending). The paper says about 0.15% **per day** (~56% annualised). Base case assumed 0.01%/day. | https://arxiv.org/html/2306.12434v1 |
| Stockbee momentum burst: ≥ 4% up, volume > prior day, ≥ 100k | strategies/momentum_burst.md | confirmed (secondary implementations) | https://www.luxalgo.com/library/indicator/6h74IRYK-stockbee-momentum-burst/ |
| Brandt-Kishore-Santa-Clara-Venkatachalam EAR 6.3% vs SUE 5.6%/yr | strategies/power_gap.md | unverifiable (paper not reached) | - |
| Lakonishok-Lee 2001; Zhao 2026; Chordia 2009; Bulkowski NR7/BGU/cup stats; Stonks/EasySwing/Qullamaggie figures; Backtrex RSI2 OOS; JT 1993 figures; Crabel exits | various | not yet checked | - |
