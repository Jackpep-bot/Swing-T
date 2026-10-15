# Batch 5 candidates: online traders, educators and published event methods (research thread, 2026-10-13)

Ask (Jack, 2026-10-13): scan as many online traders and published strategy sources as possible and turn their
methods into fixed-rule tests. Focus set by the project: the 1,500 most liquid stocks gave 0 of 711 method/liquidity
cells beating SPY after costs, Jack wants consistent income on about a $10k account, and small or thin stocks are
fine. So this batch favours small and mid caps and event or catalyst setups.

49 ideas were checked against the catalog (283 items, 146 built and replayed; `docs/catalog/catalog.json` and
`docs/strategies/` on `claude/project-thread-4wq9xa`) and against the store. **16 kept** (15 strategies, 1 filter),
**33 rejected** below (32 entries; one entry covers two setups) with the reason or the data that would unblock them.

Plainly about evidence: none of the kept cards has clean, net-of-cost, post-2015 US evidence. Most trader material is
the seller's own claim (Morales-Kacher, Wish, Sykes, Bensdorp); most academic event effects shrank after 2000. The
two with the most recent positive numbers are the Russell deletion rebound (Dimensional 2014-2023, about +2% in the
20 days after recon) and the CEO/CFO purchase filing reaction (front-loaded into the first days since 2002). The
event filters card has the strongest evidence of all, but it removes losers rather than finding winners.

## Kept

Grades: B- strong, C mixed or decayed, D seller's claim or no independent test.

| # | Card | Source | Universe | Hold | Grade | Expectation stated before the run |
|---|---|---|---|---|---|---|
| 1 | [russell_recon_deletion_rebound](russell_recon_deletion_rebound.md) | Cai-Houge; Dimensional 2014-23 | proxy R2000 deletions | 20 sessions | C | +0.5% to +1% over IWM per event net; 10 events, sign only |
| 2 | [russell_recon_addition_frontrun](russell_recon_addition_frontrun.md) | Madhavan 2003; Petajisto | proxy R2000 additions | rank day to recon day | D | about zero net |
| 3 | [tax_loss_loser_rebound](tax_loss_loser_rebound.md) | Ritter 1988; Lynch-Puckett-Yan 2014; Kozlowski-Lytle 2023 | SMALLMID YTD losers | 15 sessions | C | positive in down years, net depends on spreads |
| 4 | [ceo_cfo_buy_5day](ceo_cfo_buy_5day.md) | Wang-Shin-Francis 2012; Hossain 2010 | SMALLMID | 5 sessions | C | +0.5% to +1% gross, near zero net |
| 5 | [pre_earnings_runup_winners](pre_earnings_runup_winners.md) | Aboody-Lehavy-Trueman 2010 | all >= $5 | days -4..-1 | C | +0.3% to +0.8% gross, about zero net |
| 6 | [double_surprise_smallmid](double_surprise_smallmid.md) | Jegadeesh-Livnat 2006 | SMALLMID | 63 sessions | C | small + gross 2017-24, zero net |
| 7 | [shareholder_yield_smallmid](shareholder_yield_smallmid.md) | Boudoukh et al. 2007; Faber; SYLD | SMALLMID | monthly band | C | ~0 vs SPY 2017-24, negative 2024-26 |
| 8 | [clenow_stocks_on_the_move_midcap](clenow_stocks_on_the_move_midcap.md) | Clenow 2015; Koker; QuantConnect | mcap ranks 501-1,500 | weekly | C | negative vs SPY (as in S&P replications) |
| 9 | [piotroski_fscore8_small_value](piotroski_fscore8_small_value.md) | Piotroski 2000; Krauss 2015 | SMALLMID cheapest 30% | 63-126 sessions | D | about zero to negative |
| 10 | [code33_trend_template](code33_trend_template.md) | Minervini; He-Narayanamoorthy 2020 | SMALLMID | to 63 sessions | D | few signals, about zero net |
| 11 | [pocket_pivot_morales_kacher](pocket_pivot_morales_kacher.md) | Morales & Kacher 2010 | SMALLMID | to 63 sessions | D | like the breakout family: negative net 2024-26 |
| 12 | [green_line_breakout_wish](green_line_breakout_wish.md) | Eric Wish (Wishing Wealth) | SMALLMID | to 126 sessions | D | low win rate, ~zero alpha net |
| 13 | [bensdorp_mr_selloff](bensdorp_mr_selloff.md) | Bensdorp 2020 (system 3) | ATR% >= 5, vol >= 1M | 1-3 sessions | D | high win rate, ~zero net |
| 14 | [bensdorp_adx_reversal](bensdorp_adx_reversal.md) | Bensdorp 2020 | ATR% >= 4 | 1-6 sessions | D | ~zero net |
| 15 | [sykes_first_green_day](sykes_first_green_day.md) | Tim Sykes | $1-$20, cap <= $2B | 1-2 sessions | D | likely negative net (spreads) |
| 16 | [event_avoid_filters](event_avoid_filters.md) (filter) | Kim-Klein-Rosenfeld 2008; Lerman-Livnat 2010; Field-Hanka 2001 | applied to small-cap map winners | n/a | B- | removes 2-5% of signals, removed group 0.1-0.3R worse |

Suggested replay order (cheapest, most evidence first): 16 on the small-cap map's best rows, then 1, 4, 3, 5, 13,
14, 11, 12, 6, 7, 8, 9, 10, 15, 2.

## Shared definitions (every card uses these unless it says otherwise)

- **SMALLMID universe**: US common stocks in the store ranked 501-3,000 by `mcap_pit` (close x point-in-time EDGAR
  shares) on the signal day, close >= $3, `med_dv_63` >= $1M (the floors of `config/research_smallcap.yaml`).
  Different from the small-cap map, which ranks by liquidity (skip the 1,500 most liquid, take the next 2,500).
- **Fills**: signals at a close, fills at the next open, unless the card says limit or close. Several cards ask for
  a close fill (recon day, overnight holds) with a stated next-open fallback; record which ran.
- **Costs**: the engine's per-stock cost model on traded notional. Small caps make this the deciding term; report
  gross and net.
- **Grading**: batch standard (prereg_eval, net, own holding period) plus alpha vs SPY from daily net returns, and vs
  IWM for small/mid cards, haircut over this batch's 15 strategy trials. Pass = standard rule AND positive haircut
  alpha in both windows (2017-01..2024-10 and 2024-10..2026-10). Annual-event cards (1, 2, 3) have 8-10 events and
  cannot reach significance; they report sign and size only and go to a forward test, not to paper, if positive.
- **Point-in-time**: every EDGAR value from the session after its filed date; Form 4 from the session after filing;
  8-K from its reaction session; dividends by ex-date; no restated values; delisted names kept.
- **Long only. No options or futures.** Nothing here touches the intraday lane.

Data check: every input exists in the store per the code on `claude/project-thread-4wq9xa`
(`data/fundamentals.py` CONCEPT_TAGS, `data/filings.py` raw `eightk_items` items list, `data/insiders.py`
`officer_title`/`cmp_labels`, `data/dividends.py`, `splits` table, `features` `mcap_pit`, `med_dv_63`,
`sessions_to_expected_earnings`, `rs_rating_ibd`). New feature columns some cards need: `adx_7`, `rsi_3`, a 90-day
log-regression slope and R-squared, monthly highs for the green line, a yearly `mcap_pit` rank snapshot on Russell
rank days. No new data source is needed.

## Rejected

Each with the reason, or the data that would unblock it.

**Published effect gone, or evidence points the other way**
- **Forward split drift after the ex-date (Ikenberry, Rankine & Stice 1996).** Gharghori & Nguyen 2017
  (https://acfr.aut.ac.nz/__data/assets/pdf_file/0005/105476/89582-Splits-Longrun-2017.pdf, opened): ex-date BHAR
  2.36% (t 3.41) over 1975-2011, but 0.22% (t 0.13) in 2000-2011; most of the drift is before the ex-date, between
  announcement and split, and the store has no announcement dates.
- **IPO quiet-period expiry (Bradley, Jordan & Ritter 2003).** 3.1% around expiry in 1996-2000, 1.4% and insignificant
  in 2001-02 (https://site.warrington.ufl.edu/ritter/files/2016/01/The-IPO-Quiet-Period-Revisited-2004-02.pdf,
  opened); FINRA Rule 2241 cut the period to 10 days in 2015, and no post-2015 test exists. Store also lacks IPO dates.
- **IPO lockup-expiry rebound.** Field & Hanka and later work find the expiry negative, not a rebound; used as an
  avoid window in card 16 instead.
- **Dividend increase / initiation drift (Michaely, Thaler & Womack 1995).** Boehme & Sorescu 2002: equal-weighted only,
  insignificant value-weighted, "may be a product of chance"; Chen, Chou & Lee 2014 not robust; Hartzmark & Solomon
  2013 find a reversal after the ex-date, the only date the store has (no declaration dates). Batch 1 already
  rejected initiations.
- **8-K Item 7.01 (Reg FD) drift.** The only positive-drift item in Lerman & Livnat: +0.69% over 90 days, 2005-06,
  gross. Too small to clear small-cap costs; no later test.
- **Low-float "day 2" continuation (Ross Cameron / Warrior Trading).** The method is intraday; no published daily rule
  (the "5 pillars" thresholds come from a third-party script). Independent evidence is reversal, not continuation:
  US stocks 2010-2024 show significant negative abnormal returns 1-21 days after +20% days (Aalto thesis,
  https://aaltodoc3.org.aalto.fi/items/323aea28-873b-40ef-ac56-e26143d10c32/full, opened). A long-only engine cannot
  take the other side.
- **Weekly short-term reversal (Lehmann 1990).** De Groot, Huij & Zhou 2012 (JBF), net of Nomura costs 1990-2009:
  +29 bp a week in the largest 100 stocks, +10.6 bp in the largest 500, -31.4 bp in the largest 1,500. Robeco 2023:
  classic reversal has largely vanished. The version that still works (Da, Liu & Schaumburg 2014, within-industry
  residual, net alpha about 0.54% a month) needs industry codes. Unblock: SIC codes from EDGAR submissions (free).
- **PEAD re-run in small caps.** Already running in the small-cap map (`pead_sue`, `revenue_surprise` on the next
  2,500); Martineau 2022 and Chordia et al. 2009 say drift outside microcaps is gone and costs absorb 70-100% of it
  inside them. Card 6 tests the one variant with a stated difference.
- **Earnings-announcement-return continuation (Brandt et al. 2008; Chan-Jegadeesh-Lakonishok).** Covered by
  `earnings_announcement_return_abr`; Novy-Marx's net figure for 1994-2012 is 0.11% a month, t 0.84
  (https://mysimon.rochester.edu/novy-marx/research/FMFM.pdf, opened).
- **Breitstein capitulation / parabolic long reversal.** Catalog marks `parabolic_short_long_reversal` avoid (intraday);
  card 15 is the only daily form with a defined rule.

**Covered by an existing catalog item (no stated rule difference)**
- **Bensdorp "Long Trend High Momentum"** (SMA25 x SMA50, ROC200 rank, 25% trail, $50M turnover): `ma_crossover_family`
  + `xs_momentum_rank`; large caps only by its own filter.
- **Bensdorp "Weekly Rotation" (30-Minute Stock Trader)**: top-10 ROC200 in the S&P 500, weekly; `xs_momentum_rank`.
- **Minervini Power Play / high tight flag**: `bull_flag_breakout` (HTF geometry) and `qullamaggie_flag`.
- **Ripster EMA clouds (5/12 and 34/50)**: `ma_crossover_family` with different lengths.
- **Stockbee anticipation / TI65 scans**: `momentum_burst`, `vcp_sepa_breakout`; the scan thresholds are not a trade rule.
- **Zanger / Brandt classical patterns, double-volume breakouts**: `base_breakout`, `classic_pattern_detector_lmw`.
- **Turn of the month in small caps**: `turn_of_month`; batch 3 shows the effect gone after 2001.
- **TradingRush "MACD + 200 EMA" YouTube strategy**: `oscillator_cross_family` / `macd_zero_line_swing_points`.
- **Bill Williams alligator/fractals**: indicator in the library; no published trade rule beyond the MA-cross family.
- **Morales-Kacher buyable gap-up**: `power_gap`. **Undercut and rally**: `wyckoff_spring_accumulation`/`turtle_soup`.

**Needs data the store does not have**
- **Greenblatt Magic Formula.** Needs EBIT, total debt, cash, net PP&E, current assets and liabilities. Unblock: add
  those XBRL concepts to `CONCEPT_TAGS` (free, same EDGAR fetch). Independent tests show it far below the book's
  claims after 2005.
- **Graham net-nets.** Needs current assets and total liabilities (same unblock); post-2012 US net-nets are few and
  illiquid (median caps a few $M).
- **Full 9-signal Piotroski.** Same unblock (current ratio, long-term debt); card 9 uses 8 of 9 with stated proxies.
- **Intra-industry information transfer (Thomas & Zhang 2008; Ramnath 2002).** Needs industry codes; the two papers
  disagree on sign; about 1% gross per event at best.
- **Spin-offs (Greenblatt).** Needs Form 10-12B / distribution dates (EDGAR index; free but not ingested).
- **Secondary-offering (SEO) drop rebound.** Needs 424B prospectus dates (EDGAR index).
- **S&P 400/600 index additions.** Needs S&P announcement history (not free).
- **13F guru cloning (Pabrai-style), ARK trade copying.** Needs 13F / daily fund holdings history.
- **Short-volume ratio / squeeze screens.** The store has FINRA short volume nightly only, no history.
- **Analyst initiations, upgrades, estimate revisions.** No free history.
- **Chris Camillo social arbitrage, Unusual Whales options flow.** Social / options data, out of scope (no options).
- **Jeff Sun ADR breakouts, Kunal Desai / Humbled Trader setups.** No published fixed rules found; intraday-taught.
