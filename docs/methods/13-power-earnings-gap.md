# 13 — Power Earnings Gap / Buyable Gap-Up / post-earnings drift (earnings-gap continuation)

*Practitioner write-up. Researched 2026-10-06 for swing-engine. Every number below is tagged with where it came
from: "(primary)" = the proponent's own site/book/article, "(secondary)" = third-party notes, scripts or
replications of the proponent's rules, "(academic)" = peer-reviewed or working paper, "(unverified)" = could not
be checked against a primary source in this run. Web budget for this run was exhausted at ~40 calls; items not
re-fetched are marked.*

**One line.** Buy a stock the day it gaps up hard on an earnings report (≥10% gap or ≥0.75× its 40-day ATR, on
2–3×+ normal volume, ideally with a large EPS/sales beat and a strong close), either at the gap-day opening-range
high or — more commonly for swing traders — after a 2–5-day (up to a few weeks) tight consolidation that holds
above the gap-day low; stop at the gap-day low (or the consolidation low / gap midpoint); take partial profits
after 3–5 days or +8–20%, and trail the rest on the 10/20/50-day MA. The academic backbone is post-earnings
announcement drift (PEAD), which is strongest when the signal is the *price reaction* (EAR / "jump") rather than
the EPS surprise — but drift in large, liquid stocks has largely disappeared since ~2006.

**Three names, one family.**
| Label | Who | What is distinctive |
|---|---|---|
| **Power Earnings Gap (PEG)** | Popularised by **@traderstewie** (Art of Trading); numeric definition circulated via John Pocorobba & Jason Thompson's research | Hard thresholds: gain ≥10%, volume ">200% above" 50-day average, EPS surprise ≥20%; Stewie's trade is the *consolidation after* the gap, not the gap itself |
| **Buyable Gap-Up (BGU)** | **Gil Morales & Chris Kacher** (O'Neil lineage; Active Trader Dec 2010; *In The Trading Cockpit with the O'Neil Disciples*, Wiley 2012) | Volatility-normalised: gap ≥0.75× 40-day ATR, volume ≥1.5× 50-day; gap-day intraday low is the sell guide; MA "violation" exits |
| **Earnings Episodic Pivot (EP)** | Pradeep Bonde (Stockbee) named it; Kristjan Kullamägi (Qullamaggie) codified the earnings version | ≥10% gap, ADV traded in the first 15–20 min, triple-digit growth, neglected stock (3–6 months sideways); 1-min ORH entry, LOD stop. Full treatment in the Episodic Pivot write-up (sibling method) |

---

## Rules

### Universe and scan
| Rule | Value as taught | Source |
|---|---|---|
| Catalyst | Quarterly earnings report (gap day = first regular session after an after-close or pre-open release) | all sources |
| PEG gap/gain | "Price gain of 10% or more" | Amphibiantrading "Earnings Gap Ups" TradingView script (15 Dec 2024), crediting research by John Pocorobba & Jason Thompson (secondary); usethinkscript PEG thread (BenTen, 17 Mar 2019) attributes the PEG strategy to @traderstewie / Art of Trading (secondary) |
| PEG volume | "greater than 200% above the 50-day average" — **ambiguous**: literally ≥3× the average, but commonly read as ≥2× ("200% of"). Version both. | same (secondary) |
| PEG fundamentals | EPS surprise ≥ **20%** | same (secondary) |
| "Monster Gap" | gain ≥ **20%**, volume ">300% above" 50-day average, **no** EPS requirement | same (secondary) |
| "Monster PEG" | gain ≥20%, volume ">300% above" 50-day, EPS surprise ≥20% | same (secondary) |
| Extra PEG filters seen in scripts | price above the **200-day MA**; strong close location within the day's range | TradingView "PEG" script listing (tw.tradingview.com/scripts/peg, search snippet; author not identified) (unverified) |
| BGU gap size | Gap ≥ **0.75 × 40-day ATR**, ATR computed through the *prior* bar (gap bar excluded); open defines the top of the gap | Kacher & Morales, "Trading gaps with the most potential", *Active Trader*, Dec 2010, as restated by Bulkowski (thepatternsite.com/KacherMorales.html) (secondary of primary); towT TradingView script (29 Jan 2021) for the ATR/open conventions (secondary) |
| BGU volume | ≥ **1.5×** the 50-day average volume | Bulkowski restatement; dpool135 GDOT idea (6–7 Oct 2017, quoting *In the Trading Cockpit*) (secondary of primary) |
| BGU stock quality | "constructive, fundamentally sound, leading stock" or "a compelling thematic basis" | Bulkowski restatement; GDOT idea quoting the book (secondary of primary) |
| BGU trend context | "within an uptrend or constructive consolidation, not while a stock is in a downtrend"; breaking out of a consolidation "several days or weeks long" | same (secondary of primary) |
| EP gap / volume (earnings variant) | "a gap up of **10%** or more"; "ideally the stock should trade the average daily volume the first **15-20 minutes**"; huge volume preferably already in after-hours/pre-market | qullamaggie.com, "How to master a setup: Episodic Pivots", 2 Nov 2021 (primary) |
| EP fundamentals | "triple digit year over year (YoY) earnings and sales growth but mid/high double digits works really well too"; big analyst beat and big guidance raise preferred; high sales growth without earnings also works | same (primary) |
| EP neglect | prefers stocks that have "gone sideways for **3-6 months** or more"; stocks that already made a big move from a previous EP have a "higher failure rate" | same (primary) |
| Generic practitioner version | gap "8-10% or more"; volume "2x, 3x, 4x or more" average, coming in early (pre-market / first 30 min); stock consolidating pre-gap, not extended; lower float and short interest can amplify | TradingSim, J. McDowell, 18 Nov 2021, updated 31 Mar 2026 (secondary) |
| Looser 2026 blog version ("Earnings Gap Hold") | gap up **5%+** on earnings | TradeZella blog, 31 Mar 2026 (secondary) |
| Consolidation scan (Stewie PEG, TOS implementation) | earnings gap within the last **30 bars**; price between the **10- and 30-period EMAs**; 5-bar average volume < 50-bar average volume (volume dry-up) | usethinkscript thread (scanner by Drew Griffith, after theimpatienttrader.blogspot.com) (secondary; default gap threshold in the code is a 0.5% placeholder, not a rule) |

### Market filter
- **No hard index rule is published for PEG.** Morales & Kacher pair all their setups with a separate market-direction timing model described in *In The Trading Cockpit* (Wiley product description; model details not accessed this run — unverified).
- The BGU filter is at the *stock* level (uptrend or constructive base, leading stock).
- TradeZella (Mar 2026) claims the earnings-gap hold works "in all market conditions" because earnings arrive regardless of tape — treat as an unsupported claim; academic momentum and gap studies show continuation is weakest in panicky, high-volatility regimes (see 05-qullamaggie-breakout, Daniel–Moskowitz).
- Practical default for swing-engine: require `market_trend_state >= 1` (or SPY above its 50/200-day) for new entries, and cap the number of same-sector earnings entries per week (earnings season clusters correlated bets).

### Entry
Three entry styles are taught; they are different trades and should be backtested separately.
1. **Gap-day opening-range breakout (EP / aggressive PEG).** Buy the break of the **1-minute** opening-range high; add on 5-minute or 60-minute highs; if the first entry is missed, use the 5-/60-minute highs (Kullamägi, primary). TradingSim: "breakout above the opening range high with risk defined at the day's low" (secondary). Do not chase a stock already up more than ~1 ATR from the trigger (Kullamägi rule from the breakout setup, primary — see 05).
2. **Consolidation breakout (Stewie PEG, TradeZella "Earnings Gap Hold").** Wait for a flag, wedge, pennant or VCP after the gap (TradingSim, crediting TraderStewie). TradeZella's concrete version: gap holds, **2–5 days** in a tight range, volume declining during the consolidation, then buy the "break above the consolidation high with volume confirmation". The TOS PEG scan allows up to 30 bars after the gap. A long green gap-day candle with no upper wick ("no-wick top") is the preferred precursor (sweep summary of TradeZella; candle-shape detail not re-found on the page this run — unverified).
3. **Pullback to the gap (BGU).** Buy near the gap-day intraday low as long as it holds; TradingSim paraphrases Morales/Kacher as allowing "3-4% on the downside" below the gap low as cushion (secondary). BGU can also be bought on the gap day itself once it meets the size/volume rules (Bulkowski's test enters on the gap).

### Stop
| Variant | Stop | Source |
|---|---|---|
| EP / ORH entry | "Stop is always at the lows of the day"; stop must not exceed "1x, or maximum 1.5x" the ADR/ATR | qullamaggie.com EP post (primary) |
| BGU | "A buyable gap-up should hold above the intraday low of the gap-up day … use the intraday low of the gap-up day as a selling guide"; "stops can be placed **2-3%** below the low of the BGU candle" | GDOT idea quoting *In the Trading Cockpit* (secondary of primary); Bulkowski coded it as **a close below the gap-day low** (secondary) |
| BGU pullback buy | gap-day low minus ~3–4% cushion | TradingSim paraphrase (secondary) |
| Consolidation breakout | below the consolidation (pattern) low | TradingSim (secondary) |
| Earnings Gap Hold | "Below the **midpoint** of the gap day's range"; also exit if "the gap fills" | TradeZella, Mar 2026 (secondary) |

### Exits and targets
- **Partial profits:** "1/3 to 1/2 at 20% or 3-5 days into the uptrend" (TradingSim summarising O'Neil/Qullamaggie, secondary); Kullamägi's general rule: sell 1/3–1/2 after 3–5 days, move stop to break-even (primary, 3 Timeless Setups — see 05). TradeZella: first target **8–12%** above entry (secondary).
- **Trailing:** 10-day MA (short-term), 20-day MA (intermediate), 10-week MA (longer swings) (TradingSim, secondary); Kullamägi: first close below the 10- or 20-day (primary).
- **Morales/Kacher MA "violation" rule:** a violation is a close below the moving average followed by a move on the next day below the intraday low of that first day (Wiley/search summary of *In The Trading Cockpit*; Bulkowski: "closes below SMA, then next day makes lower low") (secondary of primary). Use the **10-day** SMA as the guide if the stock has held it for ≥**7 weeks** in the trade, otherwise the **50-day**; semiconductors, retail, commodity stocks and companies above **$5B** market cap use the 50-day (Bulkowski's restatement, secondary).
- **Failure exit:** close below the gap-day low (BGU) or a gap fill (TradeZella).
- **Key levels to manage against** (Pocorobba/Thompson via the Amphibiantrading script): the high-volume close (**HVC**), **HVC − 5%** as support, gap-day high and gap-day low (secondary).

### Position sizing
- No PEG-specific primary sizing rule was found. TradeZella: keep size at **50–75% of normal** on this setup (secondary) — sensible because gap-day ranges are wide, so an LOD stop is far from the entry.
- Kullamägi's general sizing: risk 0.25–1% per trade, positions 10–20% of account, ≤30% of the account in one stock overnight (primary, see 05). EP stop capped at 1–1.5 ADR keeps share count rational.
- swing-engine defaults (`config/settings.yaml`): `risk_per_trade_pct: 1.0`, `max_position_pct: 10.0`, `max_open_positions: 8`, `max_sector_pct: 30.0`. For this setup start at 0.5% risk and enforce the sector cap — earnings seasons cluster entries by industry.

### Holding period
| Horizon | Source |
|---|---|
| First partial at day 3–5; rest trailed for weeks to months | Kullamägi / TradingSim (primary/secondary) |
| Consolidation entry 2–5 days after the gap; first target 8–12% (days to ~2 weeks) | TradeZella (secondary) |
| Bulkowski's mechanical BGU test: **29–43 days** average hold | thepatternsite.com (secondary) |
| Academic drift windows: day **t+2 to t+61** (60 trading days) for jump-based PEAD; EAR drift paid mostly around the **next four earnings announcements** | Zhou & Zhu (FAJ 2012); Brandt et al. (2007) (academic) |

Note the conflict: practitioners (and swing-engine's `event_risk` review field) avoid holding through the *next* report, but Brandt et al. find EAR-sorted stocks earn much of their drift precisely around the next announcements (3-day abnormal return ≈3.3%). Decide explicitly whether a position may be held through the next earnings date.

---

## Chart signatures
1. **Before the gap — neglect or constructive base.** Sideways 3–6+ months with no big prior run (EP), or an orderly uptrend/consolidation of days to weeks (BGU). Avoid stocks already extended or coming off a previous big gap.
2. **The gap bar.** Opens ≥10% (PEG) or ≥0.75× ATR(40) (BGU) above the prior close, ideally a *true* gap (low stays above the prior day's high); volume ≥2–3× the 50-day average, with the average daily volume often traded in the first 15–20 minutes; closes in the upper part of its range — a long green candle with little or no upper wick. The **high-volume close (HVC)** becomes the reference level.
3. **Monster gap.** ≥20% gap on ≥3–4× volume: larger, more volatile, wider LOD stop.
4. **Post-gap hold.** Price stays above the gap-day low (and above HVC − 5%); the gap does not fill; 2–5 days (up to a few weeks) of tight, low-volume sideways action near the top of the gap-day range — a flag/pennant sitting between the rising 10- and 30-day EMAs.
5. **Continuation.** Break of the flag high on rising volume, then a ride along the 10/20-day MA; often a second leg into the next earnings report.
6. **Failure signatures.** Same-day reversal from a large gap to a close near the low ("gap and crap"); close below the gap-day low; gap fill within a few days; immediate loss of the 10-day after the breakout.

---

## Who teaches it
- **@traderstewie (Trader Stewie, Art of Trading)** — credited with popularising the PEG term and the "buy the consolidation after the gap" plan (usethinkscript 2019; TradingSim 2021/2026). His teaching material is behind a paid membership; **no primary text from Stewie was accessed this run (unverified)**.
- **Gil Morales & Dr. Chris Kacher** — the Buyable Gap-Up: *Active Trader* article "Trading gaps with the most potential" (Dec 2010); *In The Trading Cockpit with the O'Neil Disciples: Strategies that Made Us 18,000% in the Stock Market* (Wiley, 2012/2013). (Their earlier *Trade Like an O'Neil Disciple*, Wiley 2010, is often cited for BGU too — from knowledge, not verified this run.)
- **John Pocorobba & Jason Thompson** — credited for the quantitative PEG / Monster Gap / Monster PEG definitions, the HVC levels and the "alpha window" concept (via the Amphibiantrading TradingView script). Their original research was not located; **the length of the "alpha window" is not stated anywhere found (unverified)**.
- **Kristjan Kullamägi (Qullamaggie)** and **Pradeep Bonde (Stockbee)** — the earnings Episodic Pivot (qullamaggie.com EP post, 2021; Bonde's TraderLion course and 2024 conference "MAGNA53" framework per the sweep).
- **Marios Stamatoudis** (TraderLion podcast; notes by Retail Trader's Repository, 27 Mar 2024) — trades earnings/EP gaps with 1-minute ORH entries, low-of-day stops, partials "after a few days", and second-day entries for biotech catalysts (secondary).
- **TradingSim (John McDowell)** and **TradeZella** — the most-cited free explainers (2021, updated 2026; 2026).
- **IBD / MarketSurge** — "buyable gap-up" is part of the IBD/O'Neil vocabulary (from the sweep; not re-verified this run).
- **Academics** — Ball & Brown (1968) and Bernard & Thomas (1989) for PEAD; Chan, Jegadeesh & Lakonishok (1996) and Brandt, Kishore, Santa-Clara & Venkatachalam (2007/08) for the price-reaction (EAR) version; Zhou & Zhu (2012) for jump-based drift; Chordia, Goyal, Sadka, Sadka & Shivakumar (2009) on liquidity/costs; Martineau (2022) and Subrahmanyam (2026) on its disappearance; Frazzini & Lamont (2007) on the earnings-announcement premium.

---

## Evidence

### Academic: the drift behind the gap
| Study | Signal / design | Sample | Result |
|---|---|---|---|
| Brandt, Kishore, Santa-Clara & Venkatachalam, "Earnings Announcements are Full of Surprises" (Duke/UCLA WP, June 2007 version) | Sort on **EAR** (abnormal return in the 3-day window around the announcement) vs SUE | CRSP/Compustat, 1987–2004 | EAR long-short **6.3%/yr** abnormal vs 5.6% for SUE; the two are largely independent; combined ≈**11–11.5%/yr**. EAR returns are concentrated around the **next four announcements** (≈3.3% 3-day abnormal return, >5× SUE's). EAR edge rose from 1987–95 to 1996–2004. In a **large-cap universe** profitability is "considerably reduced, yet far from eliminated" (one-quarter-ahead spreads 0.89–1.4% vs ≥2.5%). |
| Zhou & Zhu, "Jump on the Post–Earnings Announcement Drift", *Financial Analysts Journal* 68(3), 2012 | Long positive-**jump** stocks, short negative-jump stocks (jumps detected around the announcement), hold **t+2 to t+61** | 1971–2009 | **3.63% per quarter ≈ 15.3%/yr** Fama–French alpha, Sharpe **1.52**; not explained by standard factors, illiquidity or value/growth. Closest academic analogue to "buy the power gap after the gap day". |
| Chordia, Goyal, Sadka, Sadka & Shivakumar, "Liquidity and the Post-Earnings-Announcement Drift", *FAJ* 65(4), 2009 | SUE long-short by liquidity | — | **0.04%/month** in the most liquid stocks vs **2.43%/month** in the most illiquid; transaction costs eat **70–100%** of paper profits. |
| Martineau, "Rest in Peace Post-Earnings Announcement Drift", *Critical Finance Review* 11(3–4), 2022 | Drift after analyst-based surprises, 60-day windows; microcap vs all-but-microcap (NYSE 20th pct) | long US sample (years not re-checked this run) | "In modern financial markets, stock prices fully reflect earnings surprises on the announcement date"; for large stocks PEAD "non-existent since **2006**", only recently gone for microcaps; announcement-day responsiveness to surprises is ~6× (all-but-microcap) and ~3× (microcap) higher in the later part of the sample. |
| Subrahmanyam (WP 2025), reported by UCLA Anderson Review, 21 Jan 2026 | Replicates the newer pro-drift papers | Feb 2001–Dec 2024 | Drift strategy t-stat **2.18** with all stocks, **1.43** excluding microcaps (bottom 20% of NYSE cap ≈3% of market value): microcaps were "the reason PEAD appeared". Counter-papers: Dickerson, Julliard & Mueller (*JFE*, in press) and Hirshleifer, Peng & Wang (*RFS* 2025, t ≈ 14) find drift persists, but include microcaps. |
| Frazzini & Lamont, "The Earnings Announcement Premium and Trading Volume", NBER w13090, May 2007 | Returns around scheduled announcements | — | Prices rise around announcement dates; the premium is largest for stocks with high **past announcement-period volume** and coincides with small-investor buying. Supports holding *into* reports in attention-grabbing names — the opposite of the usual practitioner blackout. |

**Reading the academic evidence.** The literature that most resembles PEG/BGU (EAR and jump signals, entered after the reaction) found large historical alphas, but (a) those samples end in 2004–2009, (b) the effect is concentrated in small, illiquid names where costs eat most of it, and (c) the best post-2006 tests (Martineau; Subrahmanyam) find no significant drift outside microcaps when the signal is the EPS surprise. **No post-2010, net-of-cost, liquid-universe test of the price-reaction (EAR/jump) version was found in this run** — that is the gap swing-engine's own backtest must fill.

### Practitioner backtests
| Study | Rules coded | Sample | Result |
|---|---|---|---|
| Bulkowski, thepatternsite.com "Kacher-Morales setup" (page dated 2026) | Gap ≥0.75× ATR(40), volume ≥1.5× 50-day, uptrend/consolidation breakout; exit on close below gap-day low or 10/50-day SMA violation with the 7-week rule; **no fundamental filter** | 557 stocks, 12 Mar 2001 – 1 Oct 2010; 16 variants; up to 1,504 trades | **Average gain 1.2–3.1%, win rate 28–32%, average drawdown 5.5–8.9%, hold 29–43 days.** One outlier (Insteel, $0.73 → $6.45 in 2004) lifts the best variant from 2.6% to 3.1%. Bulkowski: does not recommend it ("losing two out of every three trades"). |
| Paper Trading Journal (15 Jul 2026) | 61 post-earnings setups in a personal database | — | 65.6% gapped up, 34.4% down; claims ≥3× RVOL with a clear catalyst continues more often and 3–7% gaps give the best risk-adjusted results (search snippet only; tiny sample; not fetched — low value) |
| Qullamaggie / Stockbee self-reports | — | — | EP expectations (e.g. Bonde's ~70% win rate claim per the sweep) are self-reported and unaudited |

No independent, verified mechanical backtest of the exact PEG definition (10% / 2–3× volume / 20% EPS surprise) was found.

---

## Pitfalls
1. **Definition drift.** "200% above the 50-day average" can mean 2× or 3×; "gap" can be open vs prior close or a true gap above the prior high; "price gain of 10%" can be open gap or close-to-close. Each choice changes the sample. Version them as parameters.
2. **Microcap mirage.** The academic drift that survives is in the bottom 20% of market cap, where Chordia et al. find costs eat 70–100% of profits. A liquidity floor ($5M+ ADV, $5+ price) is non-negotiable.
3. **Point-in-time earnings data.** Earnings dates, timing (BMO vs AMC) and consensus estimates must be as-known-then. Vendor "EPS surprise" fields are often restated/adjusted (GAAP vs non-GAAP), creating look-ahead bias.
4. **Low hit rate, fat tails.** Bulkowski's BGU test: 28–32% winners; the average is driven by a few big winners (one outlier moved the mean by half a point). Many small losses are the normal case.
5. **Wide stops on gap days.** A 15% gap day can have a 10% range; an LOD stop then forces a tiny position or a large loss. Cap stop width (≤1–1.5 ADR) or use the consolidation entry.
6. **Gap-and-fade / "priced-in" beats.** In Q2 2026 S&P 500 beats earned only +0.4% (−2 to +2 days) vs a +1.0% five-year average (FactSet): beats alone are not a signal; only the extreme price/volume reactions are.
7. **Earnings-season clustering.** Dozens of signals arrive in the same 3–4 weeks, often in the same industry; without a sector cap the book becomes one correlated bet.
8. **Holding through the next report.** The academic edge partly sits at the next announcement; the practitioner rule avoids it. Pick one and backtest it.
9. **Repeat gappers.** Stocks that already ran on a previous EP have a "higher failure rate" (Kullamägi).
10. **Intraday entry not reproducible on daily bars.** ORH entries need 1-/5-minute data; a daily backtest that "buys the gap-day close" is a different (later, more extended) entry.
11. **Overfitting.** Few true monster winners per season, many knobs (gap %, volume ×, surprise %, consolidation length, MA choice). Use walk-forward and log every trial (`research/trials.py`).

---

## 2025–2026 fit
- **Large-cap earnings reactions are muted.** FactSet Earnings Insight (7 Aug 2026): for Q2 2026, 86% of S&P 500 companies beat EPS and 76% beat revenue, but positive surprises got an average **+0.4%** price change (2 days before to 2 days after) vs the 5-year average of **+1.0%**; negative surprises **−2.3%** vs −3.0%. Q1 2026 was **+1.1%** vs 1.0% (FactSet 8 May 2026 report, seen as a search snippet only). Implication: the PEG filter must select the tail (10%+ gaps on heavy volume), not "beats".
- **Academic mood is sceptical.** The January 2026 UCLA Anderson Review piece (Subrahmanyam) says drift outside microcaps is not statistically significant through 2024; a 2026 study of S&P 500 announcements 2022–2024 reportedly finds PEAD small and closer to mild mean reversion (from the sweep; **authorship not verified**).
- **Regime.** The sweep's Reddit/FinTwit reading: 2025 was a V-bottom (April tariffs) into a light-volume grind where breakouts and gap continuations worked; since Feb–Mar 2026 the market has been a compression/range in which breakout swing traders report their first losing year and the crowd advice is "buy dips, not breakouts" (secondary, community sentiment). In that tape the **consolidation-after-gap (Stewie) and pullback-to-gap (BGU)** entries fit better than chasing gap-day ORHs, and the gap-day-low stop stays mandatory.
- **Still taught in 2026.** TradingSim updated its PEG/BGU/EP explainer on 31 Mar 2026; TradeZella published its "Earnings Gap Hold" version on 31 Mar 2026; a "Breakaway Gap: Why it's the Top Setup of 2026" article on Nasdaq.com exists but timed out (unverified content). No 2026 primary commentary from Stewie or Morales/Kacher was found.
- **Verdict.** A legitimate, event-anchored continuation setup with a real (if decayed) academic pedigree in its price-reaction form. In 2026 expect a thin edge in liquid names, a 30%-ish win rate, and dependence on a few monster gaps per season. It must clear swing-engine's cost model and walk-forward gate before any capital; until then run it as a scan + alert + paper trade.

---

## Automatability

### Mechanical (codeable in swing-engine today or with small additions)
| Element | swing-engine mapping |
|---|---|
| Gap size (PEG %) | `gap_pct` already in `features/cross_section.py` (`open / prev_close − 1`). **Add `true_gap`** (`low > prev_high`) and **`gap_atr40`** = `(open − prev_close) / atr_40.shift(1)` (needs `atr_40`; `atr_14` exists in `features/indicators.py`) for the BGU rule. |
| Volume surge | `rvol_day` (vs prior 20-day avg) exists; `PanelStrategy.volume_ratio(row, "avg_vol_50d")` (used by `breakout_52w`). Caveat: `avg_vol_50d` **includes the current bar**, which understates a 3× day as ≈2.9×; add a prior-bar `avg_vol_50d_prev` for exact PEG/BGU ratios. |
| Strong close / no-wick top | `close_pos` (close location in range) and `range_pct` exist; e.g. `close_pos >= 0.7`. HVC level = gap-day close; HVC − 5% support. |
| Earnings-day flag (point-in-time) | Not in the panel yet. Cheapest PIT source already wired: **EDGAR 8-K Item 2.02** ("Results of Operations", known to `monitor/constants.py`) with acceptance timestamp → gap day = same session if pre-open, next session if after close. `data/alphavantage.py` `EARNINGS_CALENDAR` is forward-looking only (blackout use). Historical EPS-surprise % needs a vendor field (EODHD/Massive/Alpha Vantage per-symbol earnings — check `docs/research-architecture.md` before adding; not verified this run). Without surprise data, the **Monster Gap** and **BGU** variants are fully codeable from bars + 8-K dates. |
| Neglect / prior base | `ret_63d`, `ret_126d` small in magnitude, `dist_52w_high`, `base_len`, `bb_width_20`; "no prior EP" = no earlier qualifying gap in N bars. |
| Trend context | `trend_state`, `sma_50`, `sma_200` (PEG scripts: price > 200-day). |
| Market gate | `market_trend_state` via `features/regime.py` and `P_MIN_MARKET_TREND` in `strategies/_base.py`. |
| Consolidation entry | bars since gap 2–30; all closes inside the gap-day range and above gap-day low; 5-bar avg volume < 50-bar avg; price between `ema_9/ema_21` (closest to the 10/30 EMAs in the TOS scan); trigger `close > max(high, consolidation)` with `rvol_day >= 1.5` (`RollingSpec` prior=True). |
| Pullback-to-gap entry | limit at gap-day low × (1 + x%); stop gap-day low × (1 − 2–4%). |
| Stops | gap-day low (BGU/EP), consolidation low, or gap-day midpoint (TradeZella); cap at 1–1.5 × ADR/ATR. |
| Exits | `should_exit` hook: close < gap-day low (fail), close < `sma_10`/`sma_20` (trail), Morales violation (close < SMA and next low < that bar's low; needs prior-bar state), 7-week rule (10-day if `bars_held >= 35` and never violated, else 50-day), time stop (`max_hold_days` pattern from `momentum_burst`). Partial scale-out at day 3–5 needs a partial-exit hook (currently all-or-nothing). |
| Sizing | `risk/sizing.py` with `risk_per_trade_pct` 0.5 for this setup; `max_sector_pct` 30% to stop earnings-season clustering. |
| Live alerts | `monitor` already has `gap_pct_alert: 8.0` and `rvol_gate: 2.0` (close to PEG thresholds), `classify.py` event_type `earnings`, and the review enum `EARNINGS` / `event_risk` in `agent/review.py`. Note the `monitor/smallcap.py` module is the **opposite posture** (warn/fade low-float sub-$20 gappers) and should not be reused for PEG longs. |

Closest existing modules: `strategies/breakout_52w.py` (volume-ratio breakout, ATR stop), `strategies/momentum_burst.py` (Stockbee burst with a time exit), `strategies/rsi2_meanrev.py` (rule-based exit with `min_reward_risk: 0.0`). Proposed module (via `.claude/skills/add-strategy`): `strategies/earnings_gap.py` with params `entry_mode ∈ {gap_day_close, consolidation_break, gap_low_pullback}`, `min_gap_pct=0.10`, `min_gap_atr40=0.75`, `min_vol_ratio_50d=2.0`, `min_close_pos=0.7`, `require_true_gap=false`, `min_eps_surprise=None`, `consol_min_bars=2`, `consol_max_bars=30`, `stop_mode ∈ {gap_low, gap_mid, consol_low}`, `stop_cushion_pct=0.0`, `max_stop_adr=1.5`, `trail_ma=20`, `max_hold_days=60`, `hold_through_next_earnings=false`, `min_market_trend_state=1`; register `enabled: false` until the walk-forward backtest (with gates.md costs) passes.

### Discretionary (keep as Claude review enums or human steps)
- Quality of the report: guidance raise, revenue/EPS acceleration, "massive" vs merely good beat, one-off items — Claude `agent/review.py` can tag from news/8-K text, but must not emit prices.
- "Neglect" and narrative/theme strength; whether the gap is "priced in" by prior run-up.
- Reading the open: premarket volume, whether ADV trades in the first 15–20 minutes, ORH timing (needs intraday bars; daily backtests can only approximate).
- Choice of MA for trailing and partial-sale fraction per stock character; the decision to hold through the next report.

---

## Sources
Primary / proponent material
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/ — Kullamägi EP rules incl. earnings variant (2 Nov 2021): 10% gap, ADV in 15–20 min, triple-digit growth, 3–6 months sideways, 1-min ORH, LOD stop ≤1–1.5 ADR
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/ — partial-sale and MA-trail rules (cited via 05-qullamaggie-breakout)
- https://www.oreilly.com/library/view/-/9781118283080/ — Morales & Kacher, *In The Trading Cockpit with the O'Neil Disciples* (Wiley) listing
- https://investors.wiley.com/news/news-details/2013/In-The-Trading-Cockpit-with-the-ONeil-Disciples-2013-1-2/default.aspx — Wiley news page for the book
- https://gale.com/ebooks/9781118283080 — e-book listing (search result)
- Kacher & Morales, "Trading gaps with the most potential", *Active Trader*, Dec 2010 — not accessed; known via Bulkowski
Secondary notes, scripts and explainers
- https://www.thepatternsite.com/KacherMorales.html — Bulkowski's restatement and test of the BGU (557 stocks, 2001–2010)
- https://tw.tradingview.com/chart/GDOT/PpBPgj8G-GDOT-buyable-gap-up-BGU-example — dpool135 (Oct 2017) quoting BGU rules from *In the Trading Cockpit* (0.75× ATR40, 1.5× volume, intraday-low sell guide, 2–3% stop cushion)
- https://www.tradingview.com/script/wzFOH2TL — towT "Buyable Gap Up" script (29 Jan 2021): ATR excludes the gap bar; open defines gap top
- https://scan.stockcharts.com/discussion/comment/2736/ — StockCharts scan thread on BGU (DNS failure at fetch time; seen only as a search result)
- https://www.tradingview.com/script/KWTJ9jeC-Earnings-Gap-Ups/ — Amphibiantrading (15 Dec 2024): PEG / Monster Gap / Monster PEG thresholds, HVC levels, "alpha window", credited to John Pocorobba & Jason Thompson
- https://tw.tradingview.com/scripts/peg/ — PEG script listing (200-day MA and close-location filters; search snippet only)
- https://usethinkscript.com/threads/power-earnings-gaps-peg-scanner-for-thinkorswim.82/ — PEG attributed to @traderstewie / Art of Trading; TOS consolidation scan (17 Mar 2019)
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/ — J. McDowell, 18 Nov 2021, updated 31 Mar 2026: three entry styles, Morales violation rule, partials
- https://www.tradezella.com/blog/swing-trading-strategies — "Earnings Gap Hold" (31 Mar 2026): 5% gap, 2–5 day consolidation, midpoint stop, 8–12% target, 50–75% size
- https://retailtradersrepository.substack.com/p/marios-stamatoudis-the-traderlion-983 — Stamatoudis earnings/EP trade notes (27 Mar 2024)
- https://retailtradersrepository.substack.com/p/pradeep-bonde-episodic-pivots — Bonde EP notes (from the sweep; not re-fetched)
- https://traderlion.com/profile/pradeep-bonde/episodic-pivots/ — Bonde EP article (search result; not fetched)
- https://investmentliteracycoach.beehiiv.com/p/overview — sweep source (not fetched)
- https://tw.tradingview.com/script/DKiGBmFa-LevelUp-Power-Earnings-Gap-EPS-Acceleration-Screener — invite-only PEG screener (existence only)
- https://tradingsim.com/blog/day-trading-earnings-gaps/ — day-trading earnings gaps, updated Apr 2026 (search result; not fetched)
- https://papertradingjournal.com/2026/07/15/how-often-do-stocks-gap-up-vs-gap-down-after-earnings/ — 61-setup personal database (search snippet only)
Academic
- https://www.anderson.ucla.edu/documents/areas/fac/finance/ear.pdf — Brandt, Kishore, Santa-Clara & Venkatachalam, "Earnings Announcements are Full of Surprises" (June 2007 version)
- https://bpb-us-w2.wpmucdn.com/sites.udel.edu/dist/a/855/files/2020/07/Jump-on-the-Post%E2%80%93Earnings-Announcement-Drift.pdf — Zhou & Zhu, *FAJ* 68(3), 2012
- https://ideas.repec.org/a/taf/ufajxx/v65y2009i4p18-32.html — Chordia, Goyal, Sadka, Sadka & Shivakumar, *FAJ* 65(4), 2009
- https://rpc.cfainstitute.org/research/financial-analysts-journal/2009/liquidity-and-the-post-earnings-announcement-drift — same, CFA Institute page
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf — Martineau, "Rest in Peace Post-Earnings Announcement Drift", *CFR* (draft PDF)
- https://ideas.repec.org/a/now/jnlcfr/104.00000122.html — Martineau, *Critical Finance Review* 11(3–4), 2022 (RePEc)
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/ — UCLA Anderson Review, 21 Jan 2026 (Subrahmanyam; Dickerson–Julliard–Mueller; Hirshleifer–Peng–Wang)
- https://www.nber.org/papers/w13090 — Frazzini & Lamont, earnings announcement premium (May 2007)
- https://quantpedia.com/strategies/post-earnings-announcement-effect — Quantpedia PEAD entry (search result; not fetched)
- https://www.sciencedirect.com/science/article/pii/S2214635020303750 — "A review of the Post-Earnings-Announcement Drift" (search result; not fetched)
2025–2026 context
- https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_080726.pdf — FactSet Earnings Insight, 7 Aug 2026 (Q2 2026 reactions +0.4% / −2.3%)
- https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_050826.pdf — FactSet, 8 May 2026 (Q1 2026 +1.1%; search snippet)
- https://insight.factset.com/market-is-punishing-negative-eps-surprises-more-than-average-for-q1 — FactSet Insight (search result; not fetched)
- https://www.nasdaq.com/articles/breakaway-gap-why-its-top-setup-2026 — 2026 article (timed out; unverified)
- Sweep entries: `docs/research-raw/methods-sweeps/merged_compact.json` (this method; Episodic Pivot; TraderLion-school) and `merged_methods.json` key `peg`
