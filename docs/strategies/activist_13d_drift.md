---
slug: activist_13d_drift
name: Activist Schedule 13D drift
originators: [Brav, Jiang, Partnoy and Thomas (Journal of Finance 2008)]
category: event_driven
decision: implement_disabled_for_comparison
holding_period_days: [5, 20]
timeframe: daily
direction: long
regimes_good: [any]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: built_disabled
---

# Activist 13D drift

## One-line summary
Buy at the open of the session after an original Schedule 13D (a >5% holder declaring intent) becomes public on EDGAR,
hold 10 sessions (card range 5-20), 2 ATR catastrophic stop.

## Exact rules
- Signal: `days_since_13d == 0` on the session (the first session whose close can react to the filing's EDGAR
  acceptance time; `data.filings`). Only "SC 13D" / "SCHEDULE 13D" originals; amendments (13D/A) never trigger.
- Entry: next session open (`EntryType.OPEN`).
- Stop: entry - 2 x atr_14. Target: none (`min_reward_risk` 0). Exit: time stop `max_hold_days` (default 10).
- Filter: close >= $5 (`min_price`, engine choice, not from the source: spread cost on sub-$5 targets).
- `engine_trail: False` (breakeven / N-day-low overlay off; the published drift is slow).

## Why it should work
Activists target undervalued firms and push for payouts, sales or strategy changes; the paper reads the post-filing
return as the market pricing that expected value, with no later reversal.

## When it works and when it fails
Only part of the published return is tradable after the filing is public (see Evidence). Every original 13D is used,
not just hedge-fund activists (EDGAR submissions do not say who files or why), so passive >5% holders and M&A
bidders dilute the signal. Small, illiquid targets dominate.

## Evidence
- Brav, Jiang, Partnoy and Thomas (2008), "Hedge Fund Activism, Corporate Governance, and Firm Performance", *Journal of
  Finance* 63(4), 1729-1775. **Peer-reviewed.** Read this session (final working version,
  https://corpgov.law.harvard.edu/wp-content/uploads/2008/03/hedge_fund_activism-final.pdf ):
  - sample 2001-2006, 1,059 hedge fund-target pairs, 882 target companies (hand-collected, hedge-fund activists only);
  - Figure 1 (buy-and-hold return in excess of the CRSP value-weighted index, days -20..+20 around the 13D filing
    date): about +3.2% from day -10 to day -1, about +2.0% on the filing day and the next day, total about +7.2% by
    day +20; no reversal after day 20 or in the following 20 days; gross of costs;
  - the filing-date abnormal return fell from 15.9% (2001) to 3.4% (2006).
  - Tradable part (derived here, not stated by the paper): entering after the filing is public skips the run-up and
    the filing-day jump, leaving roughly 7.2 - 3.2 - 2.0 = about 2% over the remaining ~18 sessions, gross, for
    hedge-fund activists in 2001-2006.
- Gate 2 haircut (docs/gates.md): planning edge = half of that, about **+1% gross over ~18 sessions**, before the
  dilution from non-activist 13Ds and the decline the paper itself reports. Treat a replay below that as no edge.
- Rule changes since the sample (13D deadline shortened in 2024; structured "SCHEDULE 13D" form): **not checked** this
  session; the parser accepts both form spellings.

## Parameters and sensitivity
`max_hold_days` 10 (each of 5 / 20 is a separate trial), `stop_atr_mult` 2.0, `signal_day` 0.

## Implementation spec for swing-engine
`strategies/activist_13d_drift.py`; data `swing ingest-edgar` (or `--8k-only`) -> table `sched13d` -> `days_since_13d`
via `join_edgar`. Settings: `activist_13d_drift: {enabled: false, max_hold_days: 10}`. Tests:
tests/test_strategy_event_filters.py.

## Sources
- https://corpgov.law.harvard.edu/wp-content/uploads/2008/03/hedge_fund_activism-final.pdf

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 29 | 0 | 45% | +0.05 | -0.06 | 31% | -0.16 | -0.27 | 41% | +0.04 | -0.08 | 1.07 |
| correction | 3 | 0 | 67% | +0.38 | +0.11 | 33% | +0.26 | -0.01 | 33% | +0.31 | +0.03 | 1.78 |
| healthy_uptrend | 87 | 0 | 43% | -0.07 | -0.17 | 33% | -0.25 | -0.34 | 28% | -0.29 | -0.39 | 0.55 |
| high_vol_selloff | 13 | 0 | 31% | -0.26 | -0.34 | 31% | -0.00 | -0.09 | 38% | -0.02 | -0.10 | 0.97 |
| narrow_uptrend | 14 | 0 | 64% | +0.17 | +0.05 | 50% | -0.04 | -0.16 | 46% | +0.23 | +0.11 | 1.46 |
| **all** | 146 | 0 | 45% | -0.03 | -0.13 | 34% | -0.18 | -0.28 | 33% | -0.14 | -0.25 | 0.75 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 114 | 0 | 44% | -0.08 | -0.18 | 46% | -0.03 | -0.13 | 42% | +0.03 | -0.07 | 1.05 |
| correction | 49 | 0 | 61% | +0.04 | -0.04 | 61% | +0.22 | +0.13 | 59% | +0.35 | +0.26 | 1.98 |
| healthy_uptrend | 375 | 1 | 46% | -0.00 | -0.10 | 42% | -0.04 | -0.14 | 38% | -0.10 | -0.20 | 0.84 |
| high_vol_selloff | 122 | 0 | 48% | +0.03 | -0.05 | 52% | +0.08 | -0.00 | 44% | -0.03 | -0.11 | 0.93 |
| narrow_uptrend | 89 | 0 | 47% | +0.08 | -0.02 | 54% | +0.09 | -0.01 | 40% | -0.11 | -0.21 | 0.78 |
| **all** | 749 | 1 | 47% | +0.00 | -0.09 | 47% | +0.01 | -0.09 | 41% | -0.04 | -0.14 | 0.93 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
