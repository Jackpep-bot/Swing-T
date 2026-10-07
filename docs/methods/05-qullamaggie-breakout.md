# 05 — Qullamaggie breakout (momentum flag / high tight flag off the 10/20-day MA)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Every number below is tagged with where it came
from; "(primary)" = Kullamägi's own site/interview/stream, "(secondary)" = third-party notes or replications,
"(unverified)" = could not be checked against a primary source in this run.*

**One line.** Buy a leading momentum stock (top 1–2% performer over 1/3/6 months, ADR well above 5%) on the day
it breaks out of a 2-week-to-2-month tightening flag that has been "surfing" its rising 10/20-day MAs; stop at the
entry-day low (never wider than one ADR), sell a third to a half after 3–5 days, trail the rest on the first close
below the 10- or 20-day MA. Low win rate (25–35%), pay-off from occasional 10–20R+ winners, works only in
uptrending markets.

**Lineage.** O'Neil's high tight flag (Bulkowski formalised it: ≥90% rise in ≤2 months, then a shallow pause),
Minervini/Zanger continuation breakouts, Stockbee's momentum-burst scans. Kristjan Kullamägi ("Qullamaggie",
Sweden) turned it into a streamed, three-setup method (Breakout, Episodic Pivot, Parabolic Short) and reports the
flag breakout as the setup "most of his money comes from" (streams 1–5, Oct 2019, via Retail Trader's Repository).

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| Momentum rank | Scan "1 or 2% of stocks that are up the most" over **1-month, 3-month, 6-month** lookbacks | qullamaggie.com, 3 Timeless Setups (primary) |
| Same, interview version | "Top 2%" across **1, 3, 6, 12, 18-month** timeframes, with liquidity and ADR filters | Chat With Traders ep. 212 (Feb 2021) via Trading Resource Hub notes (secondary) |
| Prior move | "A big move higher sometime in the past 1–3 months. This move can be anywhere from **30–100%+**" | qullamaggie.com (primary) |
| ADR % (20-day average daily range) | Formula: `100*((H0/L0 + H1/L1 + ... + H19/L19)/20 - 1)`. Avoid < 2% ("you'll never get rich trading stocks like this"); 2.8% called "slow". Community scans use **ADR > 5%** | FAQ (primary, formula); stream 30 Jun 2020 via Trading Resource Hub (secondary); Tikam Alma, TradingView HTF-table script (secondary, the 5% number) |
| Dollar volume | "$Volume (close * volume) greater than **3,000,000**" (Tikam Alma); "> $10 million" and "≈50x account size" (TradingView HTF-table script). Own rule: "should not be trading over **1% of daily volume** on a stock" | secondary for the thresholds (unverified against primary); streams 1–5 for the 1%-of-ADV rule (secondary notes of primary) |
| Vendor scan (Deepvue, 25 Jul 2025) | "Continuation base": up **≥25% in the past month**, current-week volume **≥50% below** prior week, price **within ~2% of the 10-day SMA**; plus "top monthly gainers" by absolute strength and ADR. Deepvue says it "partnered with" Kullamägi, but the numbers are its own implementation, not quoted rules | deepvue.com (secondary, vendor) |
| Intraday watch scan | "above yesterday's highs, up 1% on the day" | streams 1–5 (secondary notes) |
| Vehicle character | "clean, linear price action", respects the 10/20-day, "momentum leaders"; prefers liquid, higher-priced names; avoids pump stocks; triple-leveraged ETFs (SOXL) acceptable over slow underlyings | streams 1–5, 30 Jun 2020 stream, CWT 212 (secondary) |
| Event hygiene | Check earnings dates and avoid holding through them; biotech: check for pending FDA/data | CWT 212 notes (secondary) |

### Market filter
Qualitative, not a rule set:
- "In a bullish market it is very common to get moves that are 10–20x+ your initial risk." (primary)
- "Generally in corrective markets you don't get many b/os that work, most of them just fail" (stream 91, 26 Mar 2020); "a very hostile market for breakouts" (stream 94). Exposure is rebuilt "over many weeks", "dipping my toes in … very carefully" (stream 95). (secondary notes of primary)
- Prefers "uptrending/sideways markets", especially right after a pullback/correction (CWT 212 notes). Watches breadth/sentiment ($NAMO, $NASI, $CPCE) (streams 1–5).
- Independent replication (Stonks Capital, Feb 2025) used **SPY > 140-day EMA** as the long-only gate.

### Entry
- Daily setup = flag breakout; execution = **opening-range high (ORH)**: "the highs of the first 1-minute candle, the 5-minute candle or the 60-minute candle" (primary). Interview version: 1-min ORH at 09:31, 5-min at 09:35, hourly at 10:00 ET; "buys his full positions in one go" (secondary notes).
- Breakouts are bought "as they break out, it doesn't matter if it's morning, afternoon or midday" (streams 1–5) — but **"when a stock is up more than its ATR you do not buy it"** (streams 1–5, 95). Adds are allowed when a stock "takes out 5-min ORHs" (stream 67).
- First flag after the big move is the best; a second flag soon after is lower quality (streams 1–5).

### Stop
- "Stop is always lows of the day and stop should not be wider than the ATR or ADR of the stock" (primary). Example given by Financial Wisdom TV: ADR 5% ⇒ max stop 5%.
- Market stops only: "Always use market stops, never limit stops" (FAQ, primary). Both mental and hard stops are used; stops are rarely overridden.
- For breakouts from large/long bases he has used the **10/20-week** MAs as the stop reference (stream 67, DXCM) — an exception, not the default.

### Exits and targets
- No price target. "Sell **1/3 to 1/2** of the position after **3–5 days**, and then move the stop to break even" (primary). Interview version: 20–25% after the first 3–5 days (secondary notes) — the fraction is discretionary.
- "Rest of the position should be trailed with the **10- or the 20-day** moving average … You wait for the first **CLOSE** below the 10-day" (primary). 10-day for fast movers, 20-day for slower names (choice is discretionary).
- Layered version from early streams: sell 1/4–1/3 on the first close below the 10-day, another 1/4–1/3 on the first close below the 20-day, the rest at the 50-day; plus a hard "sell no matter what" level, usually the prior wick lows (streams 1–5, secondary notes).
- Expectation: "5 to 10x or more R/R but your win rate will be very low (~30%)" (streams 1–5); "10–20x+ your initial risk" in bull markets (primary).

### Position sizing
- Position size: "Most of my positions are **10–20% of account size**" (3 Timeless Setups); FAQ: "Generally 5%–25% with most being around 10–15%".
- Risk per trade: "usually **0.25–1%**" (3 Timeless Setups); FAQ: "0.3–0.5%. Rarely more than 1%"; Financial Wisdom TV reports 0.5–1.5% for accounts below "a few million" (secondary).
- "Never have more than **30% of your account overnight in any stock**" (primary).
- Portfolio: 15–20 positions preferred, 30+ "triggers concern" (CWT 212 notes, secondary). No more than 1% of a stock's daily volume.
- Drawdown tolerance: largest drawdown 50% (2014); tries to contain drawdowns at 15–20% (FAQ, primary).

### Holding period
- Partial at day 3–5; remainder held "for as long as possible, to catch the big big moves" — i.e. until the first daily close below the chosen MA. Typical holds run from a few days (failed/sluggish) to many weeks (winners). Mechanical replications report an **average hold of ~7 trading days** (EasySwing panel, Jul 2026) because most trades stop out or lose the MA quickly.

---

## Chart signatures
1. **Flagpole**: +30% to +100%+ (often more) within the prior 1–3 months, ideally a leader in a live theme; weekly chart shows the stock near/at highs.
2. **Orderly flag**: 2 weeks to 2 months of sideways/pullback with **higher lows** (or a rounded bottom) and a **tightening range**; daily ranges and volume contract into the right side. Also acceptable: flat channels, symmetrical and descending triangles (FWTV summary).
3. **MA surfing**: price rides the rising 10- and 20-day MAs ("sometimes the 50-day"); the 50-day is rising and not far below. Closes cluster near the 10/20-day; no deep undercut.
4. **Shallow retrace**: Bulkowski's HTF study found 10–34% flag retracements and 10–29-day flags performed best; Kullamägi's NIO example: "365% run, pulled back 37%, going sideways, higher lows, getting really tight".
5. **Breakout day**: gap or early range expansion through the flag high on a volume surge; entry at ORH; close near the high; price not more than ~1 ADR above the pivot.
6. **Follow-through**: 3–5 up days (partial sale), then a glide along the 10/20-day. Failure signature: immediate reversal back into the flag (stopped at LOD) or close below the 20-day within days.

---

## Who teaches it
- **Kristjan Kullamägi (Qullamaggie)** — qullamaggie.com ("My 3 timeless setups", FAQ, Episodic Pivots post), 420+ archived Twitch/YouTube streams, the "Swing Trading School" YouTube playlist and breakout video (youtube.com/watch?v=xx8GvtAxilk — linked from the site; not transcribed this run), X @qullamaggie. States he sells nothing.
- **Chat With Traders ep. 212** (Aaron Fifield, 26 Feb 2021) — the long-form interview on the breakout strategy.
- **A Retail Trader's Repository** (Substack) — stream-by-stream notes, streams 1–95+ (2019–2020).
- **The Trading Resource Hub** (Substack) — stream notes (2020–2024 posts) and CWT interview notes.
- **Financial Wisdom TV** — strategy summary (2021, updated Dec 2025) and the Aug 2026 "top 100 winners" case study.
- **Tikam Singh Alma** (Substack, Apr 2024) — scan-oriented summary.
- **Deepvue** (charting/screening vendor) — "Qullamaggie screens" page (Jul 2025) claiming a partnership with Kullamägi; numeric filters are Deepvue's.
- **Leif Soreide / TraderLion** — high tight flag masterclass (adjacent, O'Neil framing; see method 33 in the sweep).
- **Thomas Bulkowski** (thepatternsite.com) — the statistical reference for the high and tight flag pattern.
- Open-source replications: TradingView "Qullamaggie Breakout" (millerrh, May 2021), "Qullamaggie Breakout V2" (LuxAlgo library mirror, 404 at fetch time), "Qullamaggie High Tight Flag Table" (protected), "QULLAMAGGIE Trades Database 2014–2022" (trend-wolf, Jul 2025: 1,700+ trade entries, no statistics); GitHub sofus-nl/swing-trading-strategies (MIT) / EasySwing.trading; Stonks Capital "Modeling Kullamägi" series.

---

## Evidence

### Self-reported (primary, unaudited)
- Win rate "25% in 2019" (FAQ) and "about 35%" in 2020 (CWT 212 notes). CAGR 2013–2019: 268% (FAQ). Largest drawdown 50% (2014).
- Account path reported by third parties: $9,100 (2013) → $1.4M (2018) → $4M (Jul 2019) → ~$82M (Mar 2021) (ValueFund Substack; secondary, unaudited).

### Independent / mechanical replications (secondary)
| Study | Rules coded | Period / sample | Result |
|---|---|---|---|
| Stonks Capital, "Modeling Kullamägi part 2" (Niv Goren, 17 Feb 2025) | Top 1–2% ROC over 1/3/6/12 m and ≥+30% over the lookback; 2 w–2 m tightening range near 10/20/50-day with higher lows; break of recent highs or gap; SPY > 140 EMA; stop > 1 ATR (1 ATR "didn't work"); trail 10/20-day close | Daily bars, end-2007 → 2025; 2,382 trades | CAGR 19%, max DD −21%; win rate / PF not disclosed |
| EasySwing.trading performance panel (updated 7 Jul 2026) + sofus-nl GitHub | Prior leg ≥30%, base 5–15 bars with narrow-range bars, high RS rank, breakout above base high on volume surge | ~2,000 US stocks, 5-year walk-forward, raw exits, no fees/slippage; 16,943 trades | **Win rate 27%, avg +0.1R, profit factor 1.10, avg hold 7 days**. Same panel: Cup & Handle PF 1.57, Trend Pullback 1.45, 52w-high-proximity pullback 1.33 |
| EasySwing blog detector write-up (May 2026) | RS rank ≥ 80; close > SMA200; 60-day return ≥ +25%; 6-month return ≥ +20%; 20-bar range ≤ 20% of close; close within 10% of EMA20; close > 20-day high; volume ≥ 1.4x 50-day avg; stop 1.5 ATR; exit first close < EMA20 or 60-bar time stop | 24-year walk-forward (rules differ from the panel row above; vendor has iterated) | Only figure disclosed: **Sharpe −3.59 in 2007–2010 (GFC)** — the regime-failure mode in numbers; no win rate/PF given |
| Financial Wisdom TV case study (Aug 2026) | Hand-classified clean setups among the **top 100 performers of the prior 12 months** (prior advance ≥30%, 2 w–2 m consolidation, 10/20/50 EMA support, higher lows, ADR > 5%, $vol > $10M) | 100 winners → 58 clean setups | Avg initial risk ≈3%, avg return 62%, avg R:R > 20:1; ~60% of setups in Jul–Oct 2025 (AI, biotech, semis). **Survivorship-conditioned: not an expectancy estimate** |

### Pattern statistics (Bulkowski, thepatternsite.com)
- High and tight flag, bull market, 1,028 trades (stats as of 26 Aug 2020): performance rank 30/39, break-even failure 15%, average rise 39%, throwback 67%, 82% reach the half-height target. The Encyclopedia-era 69% average rise and "none of 307 failed to rise 5%" was later revised down (rank 43/56 in that revision).
- HTF study (1,018 stocks, 1995–2009, 2,588 patterns): flagpole averaged +111% in ~36 calendar days; post-breakout average +27%; 14% never broke out upward; 19% of upward breakouts gained < 5%. Best: shallow preceding uptrend (34–36%), retrace 10–34%, flag 10–29 days; worst: steep downtrend into the pattern (22%).

### Academic backdrop
- Cross-sectional momentum (Jegadeesh & Titman 1993) and the 52-week-high anchor (George & Hwang 2004, *J. Finance*: nearness to the 52-week high dominates past-return momentum and does not reverse long-run) support the "buy leaders near highs" premise.
- Daniel & Moskowitz (2016, *JFE*, "Momentum crashes", NBER w20439): momentum suffers rare, persistent crashes in panic states after market declines and when volatility is high — the academic version of "breakouts fail in corrective markets", and the reason a market filter is non-optional.
- Lo, Mamaysky & Wang (2000, *J. Finance*, "Foundations of Technical Analysis", NBER w7613) find chart patterns carry some information but modest economic value (from knowledge; not re-fetched this run).

### Reading the evidence
The raw pattern has a thin, positive edge (PF ≈ 1.1, 27% wins) when coded naively on a broad universe. The practitioner's edge is in **selection** (true leaders, clean charts, live themes), **timing** (ORH entry, never extended), **asymmetric exits** (tiny stops vs. MA-trailed winners) and **regime discipline** (exposure ramps). Those are mostly discretionary, which is why self-reported results and mechanical replications differ by an order of magnitude.

---

## Pitfalls
1. **Low hit rate by design** (25–35%). Strings of 8–10 losers are normal; the P&L is carried by a few 10–20R trades. Needs many shots, consistent 0.25–1% risk, and no revenge sizing.
2. **Regime dependence.** Most breakouts fail in corrections; momentum crashes cluster after declines in high-vol states (Daniel–Moskowitz). Kullamägi stops/limits new longs and rebuilds exposure over weeks.
3. **Survivorship in the teaching material.** "Study the top 100 winners" shows what winners looked like, not how many look-alikes failed. Do not read 20:1 case-study R:R as expectancy.
4. **Extension.** Buying more than ~1 ADR above the pivot or late in the day after a big gap converts a tight-stop trade into a wide-stop one.
5. **Universe hazards.** ADR > 5% names are small/mid-caps with gaps, halts, dilution and thin books; obey the ≤1%-of-ADV rule and model slippage (swing-engine gates: 20 bps/side outside large caps).
6. **Event risk.** Earnings and FDA/data dates inside the hold window; the method says check and avoid.
7. **Second flags and late-cycle setups** are weaker than the first flag after the initial move; crowded, obvious flags in late-cycle themes fail more.
8. **Rule drift.** Partial-sell fraction (1/3–1/2 vs 20–25%) and 10- vs 20-day choice differ across his own statements; pick one, version it, and do not tune it per trade.
9. **Whipsaw near the MAs.** Entries taken right at the 10/20-day get chopped (noted by the TradingView script author); require a real pivot break and range expansion.
10. **Overfitting risk when mechanising.** Many knobs (lookbacks, tightness, ADR, volume) and a small number of true winners per year — walk-forward and trial logging (research/trials.py) are mandatory.

---

## 2025–2026 fit
- **What the data says.** Financial Wisdom TV's 12-month survey (published Aug 2026) found the clean flag breakouts concentrated in **Jul–Oct 2025** in AI, biotech and semiconductor leaders — a classic "post-correction, theme-driven" window that the method is built for. EasySwing's live-detector panel (walk-forward through its mid-2025 → Apr 2026 holdout, updated 7 Jul 2026) shows the mechanical version still positive but thin (PF 1.10), ranking below cup-and-handle and trend-pullback detectors on the same universe.
- **Practitioner mood.** Minervini is quoted (NotebookLM-style summaries of 2025 IBD Live/podcast appearances; unverified against primary) as saying more breakouts failed than in 2020 and that he responded with shorter holds, smaller reward targets and tighter stops rather than a new strategy — consistent with the thin mechanical edge above.
- **Regime sensitivity, quantified.** EasySwing's May 2026 detector write-up reports a Sharpe of −3.59 for its Qullamaggie-breakout detector during 2007–2010 over a 24-year walk-forward: in a bear/crash regime the mechanical version is strongly negative, so the market gate is not optional in any year that turns corrective.
- **No fresh primary commentary from Kullamägi for 2026 was found** in this run (re-checked 2026-10-06 with fresh searches: results were still the 2019–2020 stream notes, the 2021 CWT interview and vendor/blog explainers) (search returned only 2019–2024 stream notes and the 2021 interview); his streaming cadence has dropped and the method is now mostly taught second-hand. Mark as unverifiable.
- **Verdict.** Still a valid bull-phase continuation setup; expect it to be feast-or-famine. In 2026 it should be run with the market gate on, only in leading themes, and with the engine's cost model (fees, slippage, halts) applied before any claim of edge.

---

## Automatability

### Mechanical (can be coded in swing-engine today or with small feature additions)
| Element | swing-engine mapping |
|---|---|
| Universe floors | `universe.min_price` (5.0), `min_avg_dollar_volume` (5e6), `min_avg_volume` (5e5) in `config/settings.yaml`; `dollar_vol_20d`, `avg_vol_20d/50d` in `features/cross_section.py` |
| ADR % | **Add `adr_pct_20`** to `features/indicators.py` using the FAQ formula (`mean(H/L over 20 bars) − 1`); `atr_pct_14` exists but is not the same statistic |
| Momentum rank (top 1–2% over 1/3/6 m) | `ret_21d`, `ret_63d`, `ret_126d`, `ret_252d`, `mom_12_1`; **add a cross-sectional percentile rank** per `ts` (`rank_ret_63d` etc.) in `features/cross_section.py` |
| Prior move ≥ 30% in 1–3 m | `max(ret_21d, ret_63d) >= prior_move_min` (param) |
| Consolidation length 10–40 bars | bars since the flagpole high: `base_len` (currently "bars since 52w high within 5%") or a new `bars_since_high_63d`; `RollingSpec` in `strategies/_base.py` for prior swing high |
| Tightness / higher lows | `vcp_contraction`, `bb_width_20`, `range_pct`; **add `higher_lows_n`** (rolling count of rising 5-bar lows) to `features/patterns.py` |
| MA surfing | `sma_10`, `sma_20`, `sma_50`; conditions `close >= sma_20`, `sma_10 >= sma_20`, `sma_20` rising, `abs(close/sma_10 − 1) <= x%` |
| Breakout trigger | `close > prior max(high, N)` (RollingSpec prior=True) or `level_break`/`resistance_1` from `features/levels.py`; volume `rvol_day >= v` |
| Not extended | `(close − pivot) <= k * atr_14` (k ≈ 1 ADR) |
| Stop | entry-bar `low`, capped at `close * (1 − adr_pct_20)` |
| Market gate | `market_trend_state >= 0/1`, `market_vol_regime < 2` via `features/regime.py` (`P_MIN_MARKET_TREND`); optional SPY > EMA(140) as in Stonks Capital |
| Trailing exit | `should_exit`: `close < sma_10` (fast) or `close < sma_20` (slow) — same pattern as `rsi2_meanrev`'s rule exit; `min_reward_risk: 0.0` since there is no fixed target |
| Sizing | `risk.risk_per_trade_pct` (1.0 → consider 0.5), `max_position_pct` (10 vs his 10–20), `max_open_positions` (8 vs his 15–20); all flow through `risk/sizing.py` |
| Cost model | gates.md: 10/20 bps per side + SEC/TAF fees; required because the universe is high-ADR |

Closest existing modules: `strategies/momentum_burst.py` (Stockbee 4% burst; same "momentum leader" universe but a 3–5-day time exit instead of an MA trail), `strategies/breakout_52w.py` (52w-high break on ≥1.5x volume, optional `vcp_max_contraction`), `strategies/pullback_trend.py` (already cites Qullamaggie's 10/20-day surfing), `strategies/sr_breakout.py` (pivot-level break). Proposed new module via `.claude/skills/add-strategy`: `strategies/qullamaggie_flag.py` with params `prior_move_min=0.30`, `prior_move_lookback=63`, `flag_min_bars=10`, `flag_max_bars=40`, `adr_min=0.05`, `rank_pct_min=0.98`, `max_extension_adr=1.0`, `trail_ma=20`, `partial_fraction=0.33`, `partial_after_bars=4`, `min_market_trend_state=1`; register `enabled: false` until the walk-forward backtest and trial log clear `docs/gates.md`.

### Discretionary (cannot be fully coded; keep as Claude review enums or human steps)
- "Clean chart", "leader of the theme", "has a reason to go up" — candidate ranking / `agent` review layer, not a rule.
- Intraday ORH entry needs 1-/5-minute bars and an order at 09:31–10:00 ET; the daily panel can only approximate with "buy the close of the breakout bar" or "next open if not > 1 ADR extended". The live monitor (`rvol_now`, intraday feeds) is the place to reproduce ORH if intraday data is added.
- 10- vs 20-day trail and the partial-sell fraction (needs a scale-out hook; `should_exit` is currently all-or-nothing).
- Exposure ramp after corrections, earnings/FDA avoidance (needs an earnings calendar feed), and the weekly-MA stop exception for big bases.

---

## Sources
Primary (Kullamägi)
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/ — the canonical rule set (numbers quoted above); links the breakout video https://www.youtube.com/watch?v=xx8GvtAxilk
- https://qullamaggie.com/faq/ — risk 0.3–0.5%, size 5–25%, win rate 25% (2019), CAGR 268% (2013–19), DD 50% (2014), ADR formula, market stops, tools
- https://qullamaggie.com/ — site index (About, Blog, FAQ, Swing Trading School playlist, scan clips)
- https://qullamaggie.com/some-good-tweetstorms/ — risk/psychology tweetstorms (no numeric rules)
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/ — the sister setup (not fetched this run)
- https://chatwithtraders.com/212 — Chat With Traders ep. 212, 26 Feb 2021 (audio; show page has no notes)
Secondary notes of primary material
- https://tradingresourcehub.substack.com/i/132995655/introduction — CWT 212 interview notes, 4 Jul 2023 (win rate 35%/25%, 15–20 positions, ORH times, 20–25% partial, scans 1/3/6/12/18 m)
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream — streams 1–5 (Oct 2019) notes
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-66-70-review — streams 66–70 (Feb 2020)
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-91-95-review — streams 91–95 (Mar/Apr 2020), bear-market behaviour
- https://tradingresourcehub.substack.com/p/momentum-vehicle-selection-and-studying-1000-hours — stream 30 Jun 2020 notes (ADR thresholds, vehicle selection)
- https://tradingresourcehub.substack.com/t/qullamaggie-stream-notes — index of stream-note posts (2020–2024)
- https://www.financialwisdomtv.com/post/kristjan-qullamaggie-multi-millionaire-stock-trader-discloses-his-winning-strategy — strategy summary (Oct 2021, updated Dec 2025)
- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups — scan thresholds ADR > 5%, $vol > 3M (Apr 2024)
- https://valuefund.substack.com/p/how-does-one-trader-turn-9100-into — account history as reported (unaudited)
Evidence / replications
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal — top-100-winners case study (Aug 2026; survivorship-conditioned)
- https://stonkscapital.substack.com/p/modeling-kullamagi-part-2-momentum — mechanical replication, 2007–2025, CAGR 19%, DD −21%, 2,382 trades (17 Feb 2025)
- https://easyswing.trading/performance — detector panel (7 Jul 2026): win 27%, 0.1R, PF 1.10, 16,943 trades
- https://github.com/sofus-nl/swing-trading-strategies — MIT repo with the coded hard gates behind the EasySwing panel
- https://www.tradingview.com/script/cDCAPrd1-Qullamaggie-Breakout/ — open-source indicator (millerrh, May 2021)
- https://www.luxalgo.com/library/indicator/5bTajWQM-qullamaggie-breakout-v2/ — V2 mirror (HTTP 404 at fetch time)
- https://www.tradingview.com/script/vOiC5X5k-QULLAMAGGIE-Trades-Database-2014-2022/ — 1,700+ trade entries, no statistics (trend-wolf, 29 Jul 2025)
- https://it.tradingview.com/script/WogdhAJH-Qullamaggie-High-Tight-Flag-Table — protected script; description carries ADR > 5%, $vol > $10M, "50x account size" (unverified attribution)
- https://easyswing.trading/blog/qullamaggie-breakout-continuation-setup/ — detector rules (RS ≥ 80, 60-d ≥ +25%, range ≤ 20%, vol ≥ 1.4x, 1.5 ATR stop, EMA20/60-bar exit) and GFC Sharpe −3.59 (May 2026)
- https://deepvue.com/screener/qullamaggie-screens/ — vendor screens (25 Jul 2025): +25%/1 m, volume dry-up, within 2% of 10-day SMA
- https://www.ebc.com/forex/qullamaggie-strategy-3-trading-setups — "do the setups still work?" explainer (HTTP 403 at fetch time; not used)
- https://thepatternsite.com/htf.html — Bulkowski high and tight flag statistics
- https://thepatternsite.com/HTFStudy.html — Bulkowski HTF study (1995–2009, 2,588 patterns)
- https://www.nber.org/papers/w20439 — Daniel & Moskowitz, "Momentum Crashes"
- https://www.cxoadvisory.com/1284/technical-trading/the-52-week-high-as-a-momentum-indicator-for-individual-stocks/ — summary of George & Hwang (2004), *J. Finance* 59(5)
- https://www.nber.org/papers/w7613 — Lo, Mamaysky & Wang (2000), from knowledge, not re-fetched
Context (unverified / secondary)
- https://lilys.ai/es/notes/notebooklm-20251211/minervini-strategy-works-2025 — AI-generated notes of Minervini 2025 appearances (breakout failure commentary); treat as hearsay
- https://sponsorradar.com/channels/qullamaggie — channel size (from the sweep; not re-fetched)
- Sweep entries: `docs/research-raw/methods-sweeps/merged_compact.json` methods[4] (this method) and methods[33] (High tight flag, Soreide/TraderLion)
