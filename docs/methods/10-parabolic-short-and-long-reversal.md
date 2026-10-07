# 10: Parabolic short (and the parabolic long reversal)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Each rule below says where it came from.
"(primary)" means Kullamägi's own site. "(secondary)" means third-party notes of his streams or a companion summary of the 2026
*Market Wizards* chapter; the book itself was not read. "(inference)" is my own mirroring or derivation.
"(unverified)" means it could not be checked against a primary source in this run.*

**One line.** Short a stock that has gone vertical. That means a large cap up 50–100%+ or a small cap up 300–1000%+ in days to
weeks, after 3–5+ green days in a row. Never short it on day one. Usually take it on day 3 or 4, and only after it shows
intraday weakness: an opening-range-low break, the first red 5-minute bar breaking, or a failed VWAP retest. Stop at the high of
the day, cover into the 10- and then the 20-day moving average, and expect several stop-outs before one trade works. The mirror
trade buys a stock after a 50–60%+ collapse in a few days, looking for a 50–100% bounce.

**Lineage.** Kristjan Kullamägi ("Qullamaggie") lists it as the third of his three setups, after the breakout and the episodic pivot.
He credits his concepts to others and has said he never had an original trading insight (secondary, CTE sheet). The same idea is
older day-trader lore: the small-cap "first red day" and "backside" short (Tim Sykes, Investors Underground, Steven Dux), the
"exhaustion gap" short and "capitulation buy" of Lance Breitstein (ex-Trillium; *Market Wizards: The Next Generation*, ch. 2),
and intraday parabolic-reversal scalps (Bear Bull Traders). In academic terms it is a bet on short-horizon overreaction and on
lottery-stock overpricing, made against the strongest short-squeeze and borrow risks in the market.

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| Size of move, large caps | Up **50–100%+ in a few days or weeks** | qullamaggie.com, "3 Timeless Setups" (primary) |
| Size of move, small caps | Up **300–1000%+** over the same span | same (primary) |
| Streak | Up **3–5+ days in a row** | same (primary) |
| "A+" version in the 2026 book | Up **3 or 4 days in a row for ≥ 300% total**, typically a small-cap pump-and-dump; **never day one, rarely day two, usually day 3 or 4** | Schwager & Coyle, *Market Wizards: The Next Generation* (Harriman House, 9 Jun 2026), ch. 1, via Complete Trader's Edge companion sheet (secondary; book not read) |
| Day-one ban, stream version | "Never shorted day one"; day one is where accounts get broken (TSLA discussion, stream 60, 5 Feb 2020) | Retail Trader's Repository notes of streams 56–60 (secondary) |
| Example threshold from streams | A stock up 3 days in a row for more than 60% that reverses on day 3 and takes out its opening-range low | search-surfaced summary of stream notes; exact stream not pinned (unverified) |
| Systemized universe (one replication) | Large caps: +50–100%+ in **3 days**, 3+ green days. Small caps: +300–1000%+ in 3 days, 3+ green days. Market-cap cut-off not disclosed | Stonks Capital (Niv Goren), "Systemizing Kullamägi's Parabolic Short Setup" (secondary) |
| Third-party scanner presets | 3+ consecutive up days, RSI ≥ 75, ≥ 30% above recent lows | TradingView protected script "Qullamaggie Trading System Pro" (unverified attribution) |
| Third-party scoring model | Five factors weighted 30/25/20/15/10: MA extension, acceleration, volume climax, range expansion, liquidity; grades A–D; `safe_largecap` and `classic_qm` modes; checks borrow inventory and SSR | tradermonty/claude-trading-skills "parabolic-short-trade-planner" (secondary; thresholds not public) |

Kullamägi has published no scan formula for this setup. In practice it is a daily "biggest % gainers over 3–10 days"
list, filtered by streak length and by how far price sits above its 10/20-day MAs.

### Market filter
- Short: the book summary says the parabolic short is **the only one of his three setups that does not depend on market
  direction** (secondary, CTE sheet of ch. 1). His long-side regime rule (10-day MA above a rising 20-day) does not apply to it.
- In practice, parabolics cluster in speculative tapes: 2020–early 2021, mid-2025 meme and crypto-treasury runs, and the 2026
  AI/semis run. The short works best **after** the speculative impulse cracks. Breitstein's 2020/early-2021 P&L concentration
  makes the same point: about 63% of a decade's profit came in 14 months of panic and mania (CTE sheet, ch. 2).
- Long reversal: needs a **panic or liquidation** state. In March 2020 Kullamägi said panic and liquidation create "enormous"
  opportunities if you have cash (stream 89, 24 Mar 2020; secondary notes). Breitstein's capitulation-buy test is a panic whose
  severity exceeds its cause. His example is 5 Aug 2024: Nikkei volatility above peak Covid on a mere yen-carry unwind (CTE sheet).
  Nagel (2012) gives the academic version: short-term reversal returns rise sharply with the VIX.

### Entry
**Short (intraday trigger on daily candidates; primary unless noted):**
1. Short the **opening-range low (ORL)** break on 1- or 5-minute candles.
2. If the stock rips straight up at the open, wait for the **first red 5-minute candle** and short the break of its low. Stream 90
   (25 Mar 2020) says the same: wait for a range to build so there is a fixed stop (secondary notes).
3. **VWAP fail**: after the first crack, the stock bounces back into VWAP. If it fails there, short on the first red 1- or 5-minute
   candle into VWAP.
4. Re-entry is part of the method. On high-momentum names you usually get stopped out a couple of times and rarely nail it on the
   first try or the first day (stream notes via search summary; secondary/unverified).
- Daily-bar approximations used by replications: Stonks Capital's baseline was **short the open, cover at the close**. Other
  options are shorting the close of the first red day, or the next open under the first red day's low (inference;
  the first-red-day framing is Sykes/IU small-cap lore).

**Long reversal:**
- Premise (primary): a parabolic short that has already fallen **50–60%+ in a few days** can bounce **50–100% in a few days**.
- Kullamägi gives no trigger. The mirror of his short triggers would be an opening-range-high break, the first green 5-minute bar
  after a flush, or a VWAP reclaim (inference).
- Breitstein's capitulation buy: wait for a **V-bottom on the intraday chart**, not the falling knife (secondary, CTE sheet ch. 2).
  He **will not buy a panic that a news event triggered**, and he reads his patterns on a 2-minute chart with 3-month and 3-year
  daily context.

### Stop
- Short: the **high of the day**. For a VWAP-fail entry, the stop is **a reclaim of VWAP** (primary). On the first-red-candle
  entry it is HOD or the high of that candle (stream 90 notes). Keep stops "relatively tight and defined" (primary).
- Stonks Capital tested tight stops against the wide stops typical of mean-reversion systems and found **tight stops better**. The
  exact level was withheld (secondary).
- Long: the **low of the day**, then trail **below the prior day's low** (Breitstein, secondary). Kullamägi's general rule from the
  book applies too: if the day's extreme is farther away than **one average daily range**, skip the trade rather than widen the
  stop (secondary, CTE sheet).

### Exits and targets
- Target area: the **10- and 20-day moving averages**, "where these stocks usually bounce" (primary).
- Staged version (TSLA, stream 60, 5 Feb 2020): first target the 10-day, second the 20-day, third the 50-day (secondary notes).
- Expected payoff: **5–10x risk/reward**. That is not the 30–50x+ his breakouts and EPs can produce, but the win rate is higher if
  you wait for perfect setups (primary).
- Stonks Capital: **time-based and SMA-based profit targets gave almost identical results** (secondary).
- Contrarian covering: don't cover when everyone else covers (stream notes via search summary; unverified).
- Long reversal: the bounce target is +50–100% within days (primary). By mirroring, take profits into the falling 10/20-day MA or a
  VWAP or gap fill (inference).

### Position sizing
- Risk **≤ 0.5% of equity per trade, 1% maximum**, and 1% is a ceiling, not the norm (book via CTE; secondary). His FAQ figure
  is 0.3–0.5% (see doc 05).
- Short-specific: size smaller than for longs. Upside is unbounded, halts and squeezes can gap through the HOD stop, and borrow can
  be recalled. Breitstein's largest-ever loss was **over $2M in under an hour** shorting Avis on **2 Nov 2021** during an upside
  capitulation. The book attributes it to a sound setup taken **far larger than his method called for** while he chased an
  annual P&L target (secondary, CTE sheet ch. 2).
- Breitstein sizes in after-tax dollars. His biggest trade (Nikkei long, 5 Aug 2024) risked about $2M against a $40M account,
  roughly 5% pre-tax, which he treated as exceptional (secondary).

### Holding period
- Short: intraday to a few days. The ORL or first-red trigger is intraday; the 10-day-MA target is usually hit within days, the
  20-day within one to two weeks (inference from the targets). Stonks Capital's baseline closed by end of day.
- Long reversal: a few days (primary, "in a few days").

---

## Chart signatures
**Parabolic top (short):**
- **3–5+ consecutive green daily candles** with an **accelerating slope**: each day's range and % gain is larger than the last, and
  the stock gaps up on successive days. Price is many ADRs above a 10-day MA that itself is steepening.
- **Volume climax**: volume expands day after day. On the last day there is often a wide **gap-up on even higher volume**, and that
  is the reversal day. This is Breitstein's "exhaustion gap": days A, B and C each show a large up-move on high volume, then day D
  gaps up and reverses (secondary, CTE sheet ch. 2).
- Intraday tells: the opening-range low breaks, the first red 5-minute bar after a vertical open breaks, lower highs form under
  VWAP, and the stock fails to reclaim VWAP (the TSLA, Feb 2020 notes).
- Small-cap extras: multiple LULD **up-halts**, float rotation above 1x, a same-day **424B5/ATM offering**, and the **first red
  day** after ≥ 3 green days and a ~300% run. Rule 201 SSR then applies after a ≥ 10% drop.
- Candle tells used by day traders: shooting star or evening star at the high. "Climactic volume" means at least 2x the average of
  the last 10 bars (Bear Bull Traders, "How to Trade Parabolic Reversals").

**Capitulation low (long):**
- **−50–60%+ in a few days**, a waterfall with gap-downs and record volume, far below the 10/20-day MA.
- An intraday **V-bottom**: reclaims VWAP, breaks the opening-range high, and closes in the upper half of the range. On daily bars
  this looks like a bullish key-reversal or hammer bar.
- Not news-driven, or the selling is far out of proportion to the news (Breitstein's override; consistent with Chan 2003).

---

## Who teaches it
| Who | What they teach | Where |
|---|---|---|
| Kristjan Kullamägi (Qullamaggie) | Parabolic short rules and the parabolic-long premise | qullamaggie.com "My 3 timeless setups"; 2019–2021 Twitch/YouTube streams; *Market Wizards: The Next Generation* ch. 1 (2026). In the book he says he now does far less of it than in his early profitable years (secondary) |
| Lance Breitstein | Exhaustion-gap short, capitulation buy, "bouncy ball" short | *Market Wizards: The Next Generation* ch. 2 (2026); Chat With Traders interview (https://chatwithtraders.com/?p=3456) |
| Niv Goren (Stonks Capital) | Mechanical replication of the KK parabolic short; small-cap gap-short ("OPB") backtests | stonkscapital.substack.com |
| Tim Sykes; Investors Underground; Steven Dux | Small-cap "first red day", "backside" short, gap-up short (stock > +100%, price > $3, below the open at about 10:00) | Cited via in-repo research `docs/research-raw/smallcap-pump.json` (not re-fetched this run) |
| Bear Bull Traders ("Aiman" deck) | Intraday parabolic reversals: 3+ consecutive 5-min candles extended from the 9 EMA, climactic volume ≥ 2x the 10-bar average, ATR-stretch variant; targets 50% at the 5-min 9 EMA and 90% at VWAP | bearbulltraders.com PDF |
| tradermonty (open-source Claude skill) | Five-factor parabolic-short scorer plus ORL / first-red / VWAP-fail plans with borrow and SSR checks | tessl.io registry |

---

## Evidence

### Self-reported (unaudited)
- Kullamägi states the payoff as 5–10R with a higher win rate than his other setups (primary). The 2020 narrative in the book has
  mask makers APT and LAKE giving EPs in late February 2020, then **parabolic shorts the following week** (secondary).
  No setup-level P&L has been published.

### Mechanical replications (secondary)
| Study | Rules coded | Period / sample | Result |
|---|---|---|---|
| Stonks Capital, "Systemizing Kullamägi's Parabolic Short Setup" (Niv Goren) | Large caps +50–100% in 3 d with 3+ green days; small caps +300–1000% in 3 d; baseline short at the open, cover at the close; tight stop beat wide stop; 10/20-SMA targets about equal to time exits; final "mixed variation" combines them | End-2007 to publication, daily bars; **1,869 trades** | **CAGR 27.7%, max DD −20.9%**. Win rate, PF, costs, borrow model and survivorship handling **not disclosed**; exact rules withheld; intraday entries not tested |
| Stonks Capital, "The Science of Shorting" (24 Mar 2025) | "Opening Print Boys": pre-market gap > 50%, pre-market $vol > $200K, short the open, cover the close, wide stop, 5% of equity per trade | 3,636 instances since 2008; Polygon data | Positive equity curve shown, no stats. Assumes borrow at **$0.01/share**, slippage 1% at entry/exit and 2% on stops, and **borrow always available** (it is not) |
| In-repo small-cap base rates (`docs/research-raw/smallcap-pump.json`, cites SmallCapLab) | 50%+ small-cap gappers | ~3,200 events, Jan 2022–Mar 2026 | **67% close below the open; 72.7% gap down the next day; 46.6% of highs of day are set by 9:45 and 85%+ by 10:30** (not re-fetched this run) |

No peer-reviewed study of the exact Kullamägi rule (≥ 3 green days, ORL trigger, HOD stop, 10/20-MA target) was found.

### Academic backdrop
- **Greenwood, Shleifer & You (2019, *JFE* 131(1): 20–43, "Bubbles for Fama")**: industry run-ups of 100%+ do **not** predict low
  average returns. They do predict a much higher **crash probability**, and volatility, turnover, issuance and the **price path
  (acceleration)** help forecast both. Lesson: shorting big winners blindly has no average edge. The edge, if any, sits in the
  convex path plus a timing trigger, which is exactly what the parabolic short adds. (Industry portfolios over two years, not
  single stocks over days.)
- **Bali, Cakici & Whitelaw (2011, *JFE* 99: 427–446, "Maxing out")**: stocks with the largest daily return in the past month
  underperform. The lowest-minus-highest MAX decile spread is **> 1% per month**, consistent with lottery-stock overpricing.
- **Chan (2003, *JFE* 70(2))**: extreme moves **without public news reverse**, while bad-news moves drift, mostly in small
  illiquid stocks. Savor (2012, *JFE*, "Stock returns after major price shocks") reports the same split; abstract not
  re-fetched. This supports favouring **no-news or promotion parabolics** for shorts and **non-news panics** for capitulation
  longs, as Breitstein does.
- **Drechsler & Drechsler (2014, NBER w20282)**: high-borrow-fee stocks underperform. The cheap-minus-expensive-to-short portfolio
  earns **1.43%/month gross but 0.91% net** of fees, and anomalies concentrate in the ~20% of stocks with high fees. The
  parabolic-short edge lives where shorting is most expensive.
- **Engelberg, Reed & Ringgenberg (2018, *J. Finance*, "Short-selling risk")**: fee spikes and loan recalls are a priced risk, and
  stocks with more short-selling risk show lower returns and less efficient prices.
- **Nagel (2012, *RFS* 25(7), "Evaporating liquidity")**: short-term reversal returns, read as liquidity provision, are strongly
  time-varying and rise with the VIX. This is the case for the long reversal **in panics only**.
- **Daniel & Moskowitz (2016, *JFE*, "Momentum crashes")**: in panic states, past losers rebound violently along with the market.
  That is the same force behind capitulation-long profits and parabolic-short losses in V-shaped markets.

### Reading the evidence
The base rates favour the fade side: lottery-stock underperformance, reversal of no-news extremes, and small-cap gapper fades.
One replication shows a positive, moderate-drawdown curve (27.7% CAGR, −20.9% DD, about 1,870 trades over ~17 years), but it
does not disclose borrow, cost or survivorship assumptions. Those assumptions decide the result for small-cap shorts, where
borrow can cost 50–1,000%+ annualised. One secondary source cites Tilray at about 700% annualised, roughly 2% per day. Large-cap
parabolics are cheaper to short, but there is no evidence their run-ups reliably mean-revert on average (Greenwood et al.). Treat
it as a **low-frequency, trigger-dependent, cost-dominated** edge.

---

## Pitfalls
1. **Shorting day one or the "frontside."** Kullamägi never shorted day one, and parabolics can double again before they crack.
   Wait for day 3–4 and an intraday failure.
2. **Squeezes and unbounded loss.** Avis on 2 Nov 2021 cost Breitstein >$2M in under an hour. Halts (LULD) and overnight gaps
   jump straight through HOD stops, so a daily-bar backtest that fills stops at the stop price understates losses.
3. **Borrow.** Hard-to-borrow names may have no locate, very high fees, or recalls. Rule 201 SSR (after a ≥ 10% drop, shorts only
   above the national best bid for the rest of the day and the next) blocks the ORL/VWAP-fail entries exactly when they trigger.
4. **Several stop-outs before the winner.** The method expects re-entries, and anyone who quits after two losses gives up the edge.
   Track expectancy per *setup*, not per *attempt*.
5. **News-driven moves** (buyouts, FDA approvals, index adds, real earnings re-ratings) don't mean-revert like promotions do. The
   same goes for news-triggered panics on the long side.
6. **Over-sizing a "sure thing"** (the Avis lesson), and covering too early. Selling into the first flush cuts the average winner
   below what the higher win rate needs.
7. **Survivorship and data.** Pump-and-dump issuers delist, reverse-split and get suspended (SEC 12(k)). A backtest without
   delisted names and split-adjusted intraday data is optimistic.
8. **Large-cap "parabolics" can last for months.** The 2026 semis/memory run is the example (see below), and shorting a trend
   because it looks steep is not the setup. Without the streak, climax and intraday-failure filters it becomes fighting momentum.

---

## 2025–2026 fit
- **Plenty of candidates.** July 2025 brought a meme revival. Opendoor rose as much as ~260% in July and fell ~40% after its 21 Jul
  peak before rallying again. Kohl's gained almost 50% in a week with ~49% of shares sold short, and GoPro, Krispy Kreme and
  Beyond Meat all spiked and faded within days. These are textbook day-3/4 parabolic-short candidates, but they carry squeeze
  risk.
- **Crypto-treasury stocks (2025)** went vertical and then collapsed. SharpLink peaked near $124 in May 2025 and was down ~87%
  later. Eightco rose ~3,000% in one day. The median crypto-treasury stock was down 43% YTD while broad indices rose. Both sides
  showed up: parabolic shorts, then capitulation-bounce candidates.
- **Fewer small-cap ramp-and-dumps in 2026.** The SEC set up a Cross-Border Task Force (Sept 2025) and suspended 15 issuers
  between Sept 2025 and June 2026 (in-repo research). Nasdaq tightened listing standards. Only **13 microcap IPOs listed in H1
  2026, against ~140 in 2025** (Crypto Briefing, 16 Jul 2026). The classic +300–1000% small-cap parabolic is scarcer and more
  often ends in a halt or suspension than in a tradeable fade.
- **2026 large-cap parabolics.** The SOX rose ~70% from end-March to 11 May 2026, and Michael Burry called the move "parabolic"
  and compared it to 2000 (Bloomberg Government, 11 May 2026). Micron was up >100% YTD on HBM demand (TheStreet Pro). Squeeze
  setups appeared in space, quantum and AI-cloud names (Bloomberg, 14 May 2026; Schaeffer's, 3 Jun 2026: NBIS, QBTS, BKSY).
  This is the large-cap 50–100%+ variant. How those moves resolved after June 2026 was **not verified in this run**.
- **Crowding.** *Market Wizards: The Next Generation* (Harriman House, 9 Jun 2026) brought Kullamägi's and Breitstein's rules to a
  mass audience, so expect more competition for the same ORL triggers.
- **Net.** The setup fits the 2025–26 tape on *supply*. The obstacles are execution: borrow, halts, SSR, and squeeze risk in heavily
  shorted themes. The large/mid-cap variant with intraday triggers and small size is the most practical. The parabolic long fits
  only after crash days. It is event-driven and rare: Aug 2024 and the April 2025 tariff sell-off (the latter from knowledge, not
  re-fetched).

---

## Automatability

### Mechanical (can be coded in swing-engine today or with small feature additions)
| Element | swing-engine mapping |
|---|---|
| Run size over 3–10 days | `ret_5d`, `ret_21d` exist (`features/cross_section.py`, windows 1/5/21/63/126/252). **Add `ret_3d`**, or a rolling `run_gain_n = close / min(low, n) − 1`, to measure the "+50–100% (large) / +300%+ (small) in 3 days" rule |
| Consecutive green days | `up_days_3` counts up closes in the last 3 bars. **Add `up_streak`** (current run of consecutive up closes) to `features/cross_section.py` or `features/patterns.py`, then require `up_streak >= 3` (this also enforces "never day one") |
| Extension / acceleration | `sma_10`, `sma_20`, `atr_14`, `atr_pct_14` (`features/indicators.py`). **Add `ext_atr_10 = (close − sma_10) / atr_14`** and an acceleration term (`ret_1d` today > yesterday > day before). `rsi_14` ≥ 75 matches the third-party preset |
| Volume climax / gaps / range expansion | `rvol_day`, `gap_pct`, `range_pct`, `close_pos` exist. Climax = `rvol_day >= 2` (Bear Bull's 2x) on a gap-up day |
| Daily reversal proxy (first red day) | **Add a bearish `key_reversal_dn`** (high > prev_high, close < prev_close, volume ≥ 1.5x) and `first_red_day` (close < open after `up_streak >= 3`) to `features/patterns.py`. The current `key_reversal` is bullish only and is the daily proxy for the capitulation long |
| Large- vs small-cap split | Market cap and float are not in the daily panel. The small-cap monitor has a float map (`data.float_data.load_float_map`). Proxy with `dollar_vol_20d` and price for now |
| Short signals | `PanelStrategy.build_signal` (`strategies/_base.py`) hard-codes `Side.LONG` and requires stop < entry. **Add a short-capable builder** (stop > entry, target < entry). The backtester already supports shorts (`BacktestConfig.allow_short=True`, `_signal_error` checks), and `execution/paper_sim.py` and `alpaca_broker.py` handle `Side.SHORT` |
| Stop | Signal-day high (HOD proxy), or `max(high, high_prev)`. Skip the trade when `(stop − entry) > 1 × atr_14` (Kullamägi's one-ADR filter) |
| Targets / exits | `target = sma_10` at signal time. `should_exit`: cover when `low <= sma_10` (or `sma_20` for the runner), plus `max_hold_days` (5–10) as the time stop. Stonks found SMA and time exits about equivalent |
| Long reversal | Closest existing module: `strategies/rsi2_meanrev.py` (RSI(2) < 10, exit above `sma_10`, time stop). New filter: `ret_5d <= −0.5` and a bullish `key_reversal`/`close_pos >= 0.5`. Stop at the reversal-day low. Trail below the prior day's low, which **needs a `prev_low` trailing option** in `research/backtest.py: TrailingStop` (today it supports pct, ATR and breakeven only). Gate on `market_vol_regime == 2` (high-vol state, per Nagel) |
| Market gate | Short: do not require `P_MIN_MARKET_TREND` (setup is direction-agnostic). Long reversal: require a panic state (`market_vol_regime` high), optionally `market_trend_state <= 0` |
| Costs | `docs/gates.md` models 10/20 bps per side plus SEC/TAF fees but **no borrow fee**. Add `borrow_bps_per_day` (≥ 5–30 bps/day for hard-to-borrow names) and a locate-availability flag before any short goes live |
| Intraday small-cap overlay (alerts only) | `monitor/smallcap.py` already scores this: **first red day after ≥ 3 green and ~300% run (+3)**, gap-and-crap (+2), VWAP lost (+2), ≥ 4 up-halts (+2), SSR (+1), offering filings (+3). It fires "DO NOT HOLD / short watch" at ≥ 6. That is the alert-side implementation of the small-cap parabolic short; it never places orders |

Proposed modules (via `.claude/skills/add-strategy`, registered `enabled: false` until walk-forward and `docs/gates.md` are cleared):
- `strategies/parabolic_short.py`: `min_up_streak=3`, `run_lookback=3`, `min_run_gain=0.5` (large/liquid) or `3.0`
  (small, if a cap or float feed exists), `min_ext_atr=3.0`, `trigger="first_red_day" | "next_open_below_low"`,
  `stop="signal_high"`, `max_stop_atr=1.0`, `target_ma="sma_10"`, `runner_ma="sma_20"`, `max_hold_days=10`,
  `borrow_bps_per_day=10`, no market-trend gate.
- `strategies/parabolic_bounce.py`: `min_drop_5d=0.5`, `min_down_streak=3`, `trigger="bull_key_reversal"`,
  `stop="signal_low"`, `trail="prev_low"`, `target_ma="sma_10"`, `max_hold_days=5`, `require_market_vol_regime=2`.

### Discretionary (cannot be fully coded; keep as Claude review enums or human steps)
- The intraday trigger itself (ORL, first red 5-minute bar, VWAP fail or reclaim, V-bottom) needs 1–5-minute bars and live
  execution. The daily panel can only approximate it with next-open or first-red-day-close entries. The live monitor is the
  right home if intraday bars are added.
- "Is this an A+ parabolic?": the steepness of the curve, the crowd's mood, and whether there is real news (an acquisition, FDA,
  index inclusion) or a promotion. This can be an `agent/review.py` enum (news / no-news / promotion), never a number.
- Borrow availability, the locate fee and SSR status are broker-time facts. Alpaca's easy-to-borrow and shortable flags can gate
  them, but a hard-to-borrow fee is quoted live.
- When to re-enter after a stop-out, and when to stop trying (Kullamägi expects multiple attempts).
- Sizing down for squeeze risk and avoiding target-driven over-sizing (the Avis lesson).

---

## Sources
Primary (Kullamägi)
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/ — parabolic short rules (50–100%+ large / 300–1000%+ small, 3–5+ days up, ORL / first red 5-min / VWAP fail, HOD or VWAP-reclaim stop, 10/20-day MA targets, 5–10x R:R) and the parabolic-long premise (−50–60% → +50–100% bounce)

Secondary notes of primary material
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-56-60-review — stream 60 (5 Feb 2020): never shorted day one; TSLA targets 10/20/50-day
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-61-65-review — streams 61–65 (Feb 2020): LKNCY bounce short, TSLA bear flag under VWAP, PBYI ORL
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-86-90-review — streams 86–90 (Mar 2020): don't short out of the gate, ORL / first red 5-min trigger, HOD stop, panic = opportunity
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream-092 — streams 11–15 (Oct 2019); checked, no parabolic-short content
- https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-Kristjan-Kullamagi-market-wizards-next-generation.pdf — companion sheet to *Market Wizards: The Next Generation* ch. 1 (A+ = 3–4 days, ≥ 300%, never day one; risk ≤ 0.5%; regime rule; "does far less of it now")
- https://completetradersedge.com/wp-content/uploads/2026/09/CTE-Research-Sheet-Lance-Breitstein-market-wizards-next-generation.pdf — companion sheet to ch. 2 (exhaustion gap, capitulation buy, Avis 2 Nov 2021 loss, Nikkei 5 Aug 2024, news override, stops)
- https://completetradersedge.com/?p=233509 — CTE Kullamägi profile page (not fetched)
- https://www.harriman-house.com/authors/jack-d-schwager/market-wizards-the-next-generation/9781804093641 — book listing (Schwager & Coyle, Harriman House, published 9 Jun 2026)
- https://harriman-house.com/market-wizards-pre-order-offer — publisher page
- https://www.panmacmillan.com/authors/jack-d-schwager/market-wizards-the-next-generation/9781804093658 — e-book listing
- https://chatwithtraders.com/?p=3456 — Lance Breitstein on Chat With Traders (not fetched this run)
- https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups — checked; covers breakouts/EPs only, no parabolic-short section
- https://wallstreettrader.substack.com/p/qullamaggies-trading-playbook-speed — paywalled; not used

Replications, tools and practitioner material
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic — mechanical replication: 1,869 trades since end-2007, CAGR 27.7%, max DD −20.9%; rules withheld
- https://stonkscapital.substack.com/p/systemizing-kullamagis-parabolic?r=5igdr — same article (referral URL)
- https://stonkscapital.substack.com/p/the-science-of-shorting-using-backtesting — small-cap gap-short backtest (24 Mar 2025): 3,636 instances since 2008; cost and borrow assumptions
- https://tessl.io/registry/skills/github/tradermonty/claude-trading-skills/parabolic-short-trade-planner — five-factor parabolic-short scorer and trigger plans
- https://skillselion.com/skills/tradermonty/claude-trading-skills/parabolic-short-trade-planner — mirror listing
- https://fr.tradingview.com/script/iQtlXxO8-Qullamaggie-Trading-System-Pro — protected script; parabolic-short preset (3+ up days, RSI 75+, 30%+ extension; unverified attribution)
- https://bearbulltraders.com/wp-content/uploads/2023/05/how-to-trade-parabolic-reversals-1.pdf — intraday parabolic-reversal rules (climactic volume ≥ 2x the 10-bar average; 9-EMA/VWAP targets)
- https://www.tradezella.com/strategies/parabolic-short-strategy — vendor explainer (not fetched)
- https://www.tradezella.com/strategies/small-cap-short-strategy — vendor explainer (gap > 100%, 9:30–11:30 window; search snippet only)
- https://curvedtrading.com/articles/en/trading/short-selling-penny-stocks/ — borrow 50–1,000%+ annualised; Tilray ~700% (secondary)
- https://www.timothysykes.com/blog/first-red-day-pattern-trading/ — first-red-day pattern (via in-repo research; not re-fetched)
- https://www.investorsunderground.com/short-selling-stocks/ — frontside/backside shorting (via in-repo research; not re-fetched)
- https://www.smallcaplab.com/research — small-cap gapper base rates (via in-repo research; not re-fetched)
- /Users/personal/Desktop/swing-engine/docs/research-raw/smallcap-pump.json and /Users/personal/Desktop/swing-engine/docs/smallcap-spec.md — in-repo research (base rates, SEC task-force suspensions, bag-holder scorer)

Academic
- https://www.nber.org/system/files/working_papers/w23191/w23191.pdf — Greenwood, Shleifer & You, "Bubbles for Fama" (JFE 2019)
- https://shleifer.scholars.harvard.edu/publications/bubbles-fama — same, author page
- https://ideas.repec.org:443/a/eee/jfinec/v131y2019i1p20-43.html — same, JFE record
- https://www.nber.org/papers/w14804.pdf — Bali, Cakici & Whitelaw, "Maxing out" (JFE 2011)
- https://alphaarchitect.com/hot-off-the-jfe-press-maxing-out-your-returns/ — summary of the MAX paper
- https://academicnewsletter.sufe.edu.cn/info/357702 — Chan (2003), "Stock price reaction to news and no-news" (abstract)
- https://repository.upenn.edu/fnce_papers/387 — Savor, "Stock returns after major price shocks: the impact of information" (abstract not re-fetched)
- https://www.nber.org/papers/w20282 — Drechsler & Drechsler, "The shorting premium and asset pricing anomalies"
- https://rodneywhitecenter.wharton.upenn.edu/wp-content/uploads/2014/03/riggenberg.pdf — Engelberg, Reed & Ringgenberg, "Short-selling risk" (working paper; J. Finance 2018)
- https://nber.org/papers/w17653 — Nagel, "Evaporating liquidity" (RFS 2012)
- https://www.nber.org/papers/w20439 — Daniel & Moskowitz, "Momentum crashes" (JFE 2016)

2025–2026 context
- https://www.bnnbloomberg.ca/business/2025/07/23/highly-shorted-krispy-kreme-gopro-jump-as-meme-stock-rally-continues/ — July 2025 meme rally
- https://www.marketbeat.com/articles/investors-breathe-life-into-new-batch-of-meme-stocks-as-kohls-opendoor-technologies-surge-2025-07-22 — KSS/OPEN surge and same-week reversal
- https://www.ig.com/sg/trading-strategies/2025/09/top-meme-stocks-to-watch — OPEN +260% in July 2025, −40% after the 21 Jul peak; short interest figures (figures from search summary; attribution to this page not pinned)
- https://www.fortune.com/2025/07/23/stock-market-records-meme-stock-krispy-kreme-gopro-beyond-meat/ — meme rally coverage
- https://cointelegraph.com/news/crypto-markets-down-corporate-proxies-far-worse — crypto-treasury stocks collapse (SharpLink −87% from ~$124)
- https://www.bloomberg.com/news/articles/2025-06-13/ethereum-treasury-firm-sharplink-plunges-69-on-routine-filing — SBET −69% on a filing
- https://www.itiger.com/news/2578576504 — Barron's: crypto-treasury stocks face a reckoning (Eightco +3,000% in a day; median −43% YTD)
- https://cryptobriefing.com/foreign-company-us-ipos-sec-crackdown/ — 16 Jul 2026: 13 microcap listings in H1 2026 vs ~140 in 2025; SEC suspensions
- https://investing.com/news/stock-market-news/nasdaq-halts-ipos-of-small-chinese-companies-as-it-probes-stock-rallies-2918997 — Nasdaq halts small Chinese IPOs
- https://news.bgov.com/financial-accounting/michael-burry-warns-of-stock-crash-as-tech-jump-echoes-2000-peak — 11 May 2026: SOX ~+70% since end-March; "parabolic" warning
- https://pro.thestreet.com/market-commentary/memory-stocks-go-parabolic-as-rotation-kicks-into-high-gear — Micron >100% YTD (2026)
- https://www.bloomberg.com/news/articles/2026-05-14/rally-in-top-space-stocks-sets-short-sellers-up-for-squeeze — space-stock squeeze, 14 May 2026 (headline only)
- https://www.schaeffersresearch.com/content/analysis/2026/06/03/these-growth-stocks-are-ripe-for-a-short-squeeze — 3 Jun 2026: NBIS, QBTS, BKSY squeeze candidates; "parabolic semiconductors"
- https://www.advisorperspectives.com/articles/2026/05/11/retail-flooding-chipmaker-moves-extreme — retail flows into chip moves (HTTP 403; headline only)
- https://seekingalpha.com/article/4903272-chip-stocks-fomo-rally-why-this-could-signal-final-blow-off-top-for-bull-market — blow-off-top commentary (not fetched)
- https://www.itiger.com/hant/news/2512543184 — short sellers lost $73B in early 2025 (headline)
