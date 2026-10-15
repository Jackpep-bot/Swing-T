---
slug: month_end_rebalancing_avoidance_spy
name: Month-end rebalancing pressure, hold SPY except the last week of months in which stocks beat bonds (Harvey-Mazzoleni-Melone Calendar signal, long-only half)
originators: [Harvey, Mazzoleni & Melone, "The Unintended Consequences of Rebalancing", NBER WP 33554 (2025; SSRN 5122748, version of 2026-01-14)]
category: strategy
decision: implement
holding_period_days: [16, 250]
timeframe: daily bars (SPY, TLT); NYSE calendar
direction: long
regimes_good: []
regimes_bad: []
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: draft_card (research thread batch 4, 2026-10-13; not in catalog)
---

# Month-end rebalancing avoidance on SPY

## Why this one is different from what was tested
- `turn_of_month` (replayed, failed: vs SPY -0.106R, t -2.60 in 2024-26 and -0.084R, t -4.14 in 2017-24,
  `docs/leaderboard.md` read 2026-10-13) is unconditional and long only in a short window (QS rule: buy day -5,
  sell day +3). This card is the opposite position in the overlapping days and is conditional: it stays in SPY all
  month and steps out for the last week only when stocks have outperformed bonds month-to-date.
- `fomc_cycle_even_weeks` and `volatility_managed_spy` (batch 2, failed) time SPY on a calendar and on variance.
  This one times it on a flow signal (how far a 60/40 portfolio has drifted from target).
- It owns no single stocks, so the 2024-26 narrow-market problem does not apply. It has the same weakness as every
  SPY timing card here: few independent bets, so the alpha t-stat has little power (see Grading).

## One-line summary
Pension and target-date funds rebalance to fixed stock/bond weights near month-end; when stocks have beaten bonds
during the month they must sell stocks, and S&P 500 returns in the last week are lower. Hold SPY, but sit in cash
through the last week of any month in which a 60/40 portfolio has drifted overweight stocks.

## Origin and lineage
- Harvey, Mazzoleni & Melone, NBER WP 33554. Read in full this session from the 2026-01-14 version hosted by EDHEC:
  https://www.edhec.edu/sites/default/files/2026-03/Scientific%20paper.%20ssrn-5122748.pdf (text pulled from the PDF
  with a script; tables read as extracted text, so re-check any number against the PDF before quoting it elsewhere).
  NBER page: https://www.nber.org/papers/w33554. Working paper, not yet peer-reviewed as far as I could find.
- Related, peer-reviewed: Etula, Rinne, Suominen & Vaittinen, "Dash for Cash: Monthly Market Impact of Institutional
  Liquidity Needs", RFS 33(1) 2020 (https://academic.oup.com/rfs/article/33/1/75/5494694; not opened, cited in HMM
  and already cited in the batch 3 README): month-end selling ahead of the settlement cut-off, then a rebound.
- Not the same as Graziani (2024) end-of-month reversal: HMM Appendix Table D.11 report correlation of -0.062 with
  the Calendar signal and no effect on their result.

## Exact rules (as published)
1. Simulate a 60/40 stock/bond portfolio (S&P 500 futures, 10-year Treasury note futures) that is reset to 60/40 at
   the close of the last business day of each month. Calendar signal on day t = equity weight of that portfolio at
   the close of t minus 60% (eq. B.2). Positive = stocks overweight.
2. `week4` = 1 on the last 5 business days of the month.
3. Predictive regression (their eq. 4): next-day return on Calendar x week4. The strategy takes
   sign(-Calendar signal) on days in the last week (short stocks / long bonds when stocks are overweight), zero on
   other days, averaged with a second "Threshold" leg that trades every day.
4. They also flip the position on the first business day of the new month to catch the reversal. I could not read
   the exact expression for that leg from the extracted text; it is NOT used here. Unverified.

## Engine version (pre-register this one)
- Instrument: SPY only (`static_symbols: [SPY]`, as in `config/prereg_b2_spy.yaml`). Cash earns zero.
- Bond leg for the signal: **TLT**. Registered deviation: the paper uses 10-year note futures; the store has TLT bars
  from 2016-01-04 but IEF and AGG only from 2024-10-07 (checked read-only in `data/live/replay_p3.duckdb`). TLT moves
  about twice as much as the 10-year note, so the sign of the signal can differ in months when stocks and bonds
  move the same way by similar amounts. If IEF 2016-2024 is backfilled before pre-registration, use IEF in both
  windows instead and say so; do not mix instruments across windows.
- Signal: G_S, G_B = SPY and TLT close on session t divided by their close on the last session of the previous
  month (store `close`, split-adjusted, dividends excluded: registered approximation; distributions shift the signal
  by at most a few hundredths of a point). w_t = 0.6 G_S / (0.6 G_S + 0.4 G_B). Signal_t = w_t - 0.60.
- Rule: default position is 100% SPY. At the close of each of the last 5 NYSE sessions of the month (T-4 .. T): if
  Signal_t > 0, be flat for the next session; if Signal_t <= 0, be long for the next session. At the close of the
  first session of a new month, always long. The engine fills at the open, so "flat for the next session" means sell
  at the next open and (if the next close says long) buy at the open after: each avoided session runs open to open.
  Registered deviation from the paper's close-to-close timing.
- Typical month with stocks overweight: sell at the open of T-3, buy back at the open of the second session of the
  new month (5 sessions out). About 7 round trips and 35 sessions out per year (my estimate, not from the paper).
- No threshold on the signal size, no Threshold leg, no first-day reversal leg, no leverage, no bond position.
- Stop: the card has none. Use the SPY cards' convention: catastrophe stop `stop_pct` below the signal close so the
  engine can size a full position (`fomc_cycle_even_weeks.py` uses 0.15); `engine_trail = False`, `min_reward_risk = 0`,
  no regime gate.
- Costs: per-stock model for SPY (floor 10 bp per side). SPY's real spread is about 1 bp, so this is conservative by
  roughly 1.2 points a year at 7 round trips.

## Grading
Batch standard plus alpha vs SPY from daily net returns (OLS, intercept and beta free), two-sided Bonferroni over the
batch-4 group size. Also report sessions out per year, the mean SPY open-to-open return on avoided sessions against
all other sessions, and the count of months with a positive signal at T-4.

**Power, stated before any run (my arithmetic).** The strategy differs from SPY on about 35 sessions a year. At SPY's
daily volatility of about 1% that is a residual of roughly 6% a year. An alpha t of 2.241 (group of 2) then needs
about 4.8% a year over 7.75 years and about 9.5% a year over 2 years. The paper's own effect size, applied to the
long-only half, is about 4% a year net at best (see Evidence). So this card cannot pass the registered alpha rule in
the 2-year window even if the published effect is entirely real. The run can only tell us the sign and rough size.

## Evidence
All from HMM, sample 1997-09-10 to 2023-03-17, daily, 6,226 observations, unless noted.
- Table 1 (stock minus bond futures return, next day): Calendar x week4 coefficient -0.3029 (s.e. 0.0808), Threshold
  -0.4144 (0.1148). Text: a one-standard-deviation signal moves next-day equity returns by about 17 bp (Calendar)
  and 16 bp (Threshold).
- Table 3 (S&P 500 futures alone): Calendar x week4 -0.2667 (0.0758), so the equity leg carries the effect; the
  10-year leg is +0.0362 (0.0128).
- Figure 3: Calendar predictability peaks in the last four days of the month.
- Sign: the text says positive signal values significantly predict negative returns and negative values positive
  returns; predictability is not concentrated on one side. That is the side this card uses.
- Long sample (Table 4, CRSP market and Treasury total returns): Calendar x week4 -0.2569 (0.0670) in 1997-2023 but
  -0.0284 (0.0596) in 1961-1997. The effect is recent, which the authors tie to pension cash needs and target-date
  funds after the 2006 Pension Protection Act.
- Quarter months: coefficient -0.2509 (0.1590) in the first month of a quarter, -0.3487 (0.1062) in the second,
  -0.3400 (0.1300) in the third (Table 2 Panel B).
- Strategy (Table 6, long/short futures, both legs, position scaled by signal): 10.20% a year excess, 9.17% vol,
  Sharpe 1.11, skewness 5.23; CAPM alpha 9.61% (s.e. 1.77). Net of costs "close to 1" (authors' statement, futures
  costs). Excluding Sep 2008-Mar 2009 and March 2020 the Sharpe is 0.90.
- State dependence (Table 6 Panel C): 16.50% a year when VIX is above its median, 3.91% when below.
- Reversal (Figure 4): the Calendar effect troughs at day 2 and is statistically indistinguishable from zero by
  day 6, so the avoided return is expected to come back within about two weeks.
- Secondary summary read: CXO, 2025-02-20 (rules and sample only; results behind a paywall),
  https://cxoadvisory.com/calendar-effects/exploiting-predictable-institutional-portfolio-rebalancing
- Expected size for this card (my arithmetic, not in the paper): coefficient -0.27 times a typical positive signal
  of about 0.45 points gives about -12 bp a day on avoided sessions against roughly +5 bp on an average day, so
  about 15 bp x 35 sessions = 5% a year gross, 4% net of the engine's SPY cost. The signal's daily s.d. (about 0.56
  points) is inferred from "17 bp per s.d." and the coefficient; treat both figures as rough.
- Against, and gaps:
  - No independent replication and no test after March 2023 found (searched Quantpedia, QuantSeeker, Alpha Architect,
    CXO). All evidence is in-sample from one working paper.
  - The long-only half fires after stocks have outperformed, which is usually a calm market. The paper's profit is
    four times larger in high-VIX periods and its big gains (late 2008, March 2020) are from buying stocks with
    leverage after a fall, which this card cannot do. A haircut of half or more on the 5% is reasonable.
  - Settlement moved to T+1 in May 2024. The Etula et al. mechanism ties the selling window to the settlement lag, so
    the 2024-26 window may have a shifted, shorter window (an unverified secondary summary reports a one-day shift
    after the change). The last-5-sessions rule is kept as published.
  - The engine's own unconditional month-end test (`turn_of_month`) found nothing net of costs.
- Grade C: one recent working paper by credible authors, large t-statistics on the most liquid instrument, costs
  addressed for futures only, no out-of-sample or independent evidence.

## Why it might beat costs
One instrument, about 7 round trips a year, and a published per-event effect (tens of bp over the week) that is
several times SPY's real spread. At the engine's 10 bp per side the cost is about 1.4% a year, which is a third of
the best-case edge and probably most of a realistic one.

## Expectation stated before the run
- 2017-01..2024-10: small positive alpha vs SPY, 0 to +2% a year, alpha t below 1.5. FAIL on the rule.
- 2024-10..2026-10: about zero, either sign, alpha t inside +/-1 (about 14 events; T+1 settlement may have moved the
  window). FAIL on the rule.
- It earns a trial only as the one idea found in this batch whose published evidence is not contradicted for a
  liquid, long-only, low-turnover form. If the group has no other member, running it alone (critical t 1.96) does
  not change the conclusion in the 2-year window.

## Engine relatives already tested
- `turn_of_month`: failed in both windows (numbers above).
- `fomc_cycle_even_weeks`: alpha -8.5% a year (t -2.34) in 2017-24, -13.9% (t -2.21) in 2024-26
  (`docs/preregistration/2026-10-10-batch2-results.md`).
- `volatility_managed_spy`: alpha +0.6% (t 0.30) and -1.3% (t -0.38), same file.

## Data check
- `bars`: SPY 2016-01-04..2026-10-08 (2,707 rows) and TLT the same span, in `data/live/replay_p3.duckdb`. IEF, AGG,
  SHY, BIL start 2024-10-07, so they cannot serve the 2017-24 window without a backfill.
- NYSE sessions: `swing_engine/data/calendar.py` (`trading_days`, `next_trading_day`). `swing_engine/features/extra.py`
  already has `tom_day` (session offset around the month end, defined for |offset| <= 5, with -1 = the month's last
  session) and `month_end`; the last 5 sessions are `tom_day` in -5..-1. Confirm the offset convention in the code
  before relying on it (read from the comments only, not run).
- Strategy pattern to copy: `swing_engine/strategies/fomc_cycle_even_weeks.py` (single-symbol SPY, entry at a close,
  `should_exit` at a close, fill next open). The TLT closes must be available to the strategy on the same session:
  either add TLT to `static_symbols` and never signal on it, or precompute the signal as a feature.
- No fundamentals, filings, VIX or factor data needed.

## Risks
- Structural, not statistical: the test cannot reach the registered t in the 2-year window (see Grading).
- Single source, in-sample, recent sample only; publication in 2025 invites front-running that moves the effect
  earlier in the month.
- TLT proxy can flip the signal's sign relative to the paper's 10-year note.
- Open-to-open timing gives up the first overnight move after each signal.
- Skipping the turn-of-month sessions also skips any remaining turn-of-month strength on the first session of the
  month.

## Common mistakes
Counting calendar days instead of sessions; resetting the 60/40 weights on the wrong day; using the signal from the
same close it trades on; adding a signal threshold or the Threshold leg after seeing results.

## Signs of decay to monitor
Mean SPY return on avoided sessions not below the mean on other sessions over a trailing 3 years.
