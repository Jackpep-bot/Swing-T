---
slug: pre_holiday_effect
name: Pre-holiday effect
originators: [Fields (1934), Lakonishok and Smidt (RFS 1988), Ariel (JF 1990), Yale Hirsch / Stock Trader's Almanac]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 3]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Pre-holiday effect

## One-line summary
Index returns on the trading day before a US exchange holiday were historically many times the normal daily mean;
in large caps the premium has been insignificant since about 1990.

## Origin and lineage
Fields (1934) on the DJIA; Lakonishok and Smidt (1988, DJIA 1897-1986); Ariel (1990, CRSP indices 1963-1982, eight
holidays); Stock Trader's Almanac popularised a 1-2 day pre-holiday long. Ko and Yang (Critical Finance Review,
2021) extended to 2019.

## Exact rules
- Academic version (E34): hold the index for the single trading day before each exchange holiday (close t-1 to close t).
- Almanac version (P47/C58): buy 1-2 trading days before the holiday, sell just after it. Holidays: New Year, Presidents'
  Day, Good Friday, Memorial Day, July 4, Labor Day, Thanksgiving, Christmas (plus Juneteenth since 2022, not in the
  classic studies). Half-day sessions (July 3, day after Thanksgiving) are thin.
- No stop, no target, sizing unspecified.

## Why it should work
Proposed: short-sellers close before long breaks, retail optimism, low pre-holiday volume. No mechanism has
survived as a robust explanation; post-publication decay suggests arbitrage removed it where trading is cheap.

## When it works and when it fails
Survives only in small firms (limits to arbitrage). Large-cap / SPY version is noise since about 1990.

## Parameters and sensitivity
Days before holiday (1 vs 2), which holidays, exit day. Few events per year (~9-10), so any per-holiday tuning is overfit.

## Evidence
- Lakonishok-Smidt: DJIA pre-holiday mean 0.22% vs 0.0094% on other days (1897-1986).
- Ariel (1990): CRSP EW/VW pre-holiday returns 9-14x the non-pre-holiday mean, 1963-1982 (160 pre-holidays).
- Ko and Yang (CFR 2021), verified from the paper this session: extended to 1983-2019, the effect "now exists only among
  small firms"; for large firms the difference is insignificant, especially after 1990; after controlling for weekend and
  turn-of-year effects the CRSP VW index, DJIA and S&P 500 show no significant premium.

## Common mistakes
Trading SPY on it; counting Almanac averages that are pre-cost and pre-1990 heavy.

## Implementation spec for swing-engine
- Feature `pre_holiday_1` = 1 if the next NYSE session after `ts` is more than one weekday away for a holiday reason
  (use `data/calendar.py: next_trading_day` and the pandas_market_calendars holiday list; a normal weekend is not a holiday).
  `pre_holiday_2` = the session before that.
- Use: calendar flag only (tie-breaker on entries or a small-cap overlay test), not a standalone module.
- If replayed as a strategy: small-cap equal-weight basket (or IWM), entry at close of `pre_holiday_1`, exit next session
  close, `max_hold_days = 1`, catastrophic stop `3 * atr_14`. Needs MOC hook.
- Missing: `calendar_flags` feature module; MOC fills.

## What the router should know
Tie-breaker only; never raise risk on it. Irrelevant for large caps.

## Signs of decay to monitor
Small-cap pre-holiday mean minus normal-day mean <= 0 over a rolling 40-event window.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/the-pre-holiday-effect
- https://ideas.repec.org/a/bla/jfinan/v45y1990i5p1611-26.html
- https://nowpublishers.com/article/Details/CFR-0111
- https://cfr.ivo-welch.org/published/papers/ko2021pre.pdf
- https://www.redalyc.org/pdf/395/39523159003.pdf

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3807 | 27 | 70% | +0.16 | +0.09 | -0.12 | 72% | +0.31 | +0.24 | -0.08 | 54% | +0.13 | +0.05 | -0.18 | 1.39 |
| healthy_uptrend | 16563 | 118 | 47% | -0.01 | -0.09 | -0.06 | 48% | +0.01 | -0.07 | -0.08 | 46% | +0.02 | -0.06 | -0.02 | 1.05 |
| high_vol_selloff | 4948 | 28 | 72% | +0.24 | +0.15 | -0.19 | 70% | +0.31 | +0.22 | -0.27 | 70% | +0.51 | +0.43 | -0.37 | 3.50 |
| narrow_uptrend | 1173 | 6 | 31% | -0.07 | -0.14 | +0.06 | 47% | +0.00 | -0.07 | +0.07 | 68% | +0.35 | +0.28 | +0.11 | 2.81 |
| **all** | 26491 | 179 | 54% | +0.06 | -0.02 | -0.09 | 56% | +0.11 | +0.03 | -0.11 | 52% | +0.14 | +0.06 | -0.10 | 1.41 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 7020 | 96 | 48% | -0.02 | -0.09 | -0.08 | 65% | +0.20 | +0.13 | -0.10 | 60% | +0.24 | +0.17 | -0.11 | 1.94 |
| correction | 11605 | 72 | 68% | +0.14 | +0.08 | -0.03 | 60% | +0.20 | +0.13 | +0.01 | 53% | +0.09 | +0.03 | -0.01 | 1.27 |
| healthy_uptrend | 53476 | 597 | 46% | -0.04 | -0.12 | -0.12 | 51% | +0.02 | -0.06 | -0.12 | 50% | +0.06 | -0.01 | -0.15 | 1.16 |
| high_vol_selloff | 15585 | 149 | 65% | +0.12 | +0.04 | -0.11 | 56% | +0.10 | +0.03 | -0.08 | 56% | +0.12 | +0.05 | -0.07 | 1.40 |
| narrow_uptrend | 12943 | 79 | 55% | +0.02 | -0.05 | -0.11 | 53% | +0.07 | -0.00 | -0.05 | 47% | +0.03 | -0.04 | -0.02 | 1.08 |
| **all** | 100629 | 993 | 53% | +0.01 | -0.06 | -0.10 | 54% | +0.07 | -0.00 | -0.09 | 52% | +0.08 | +0.01 | -0.10 | 1.23 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
