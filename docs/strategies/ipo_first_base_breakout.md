---
slug: ipo_first_base_breakout
name: IPO first-base breakout
originators: [William J. O'Neil, Investor's Business Daily, MarketSmith/MarketSurge]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 60]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# IPO first-base breakout

## One-line summary
Skip the first-day pop. Wait for a recent IPO to form its first consolidation, then buy the breakout above that
base's high on clearly rising volume. The stop goes under the base low or a fixed percentage below entry, and the
lockup expiry is treated as a supply event.

## Origin and lineage
- The IPO base is one of the seven base types in O'Neil's taxonomy (MarketSmith/MarketSurge pattern recognition).
  It is the exception to the usual minimum base lengths.
- IBD runs articles on how to buy new issues.
- `docs/methods.md` 1b concludes: trade first-base breakouts only, because day-1 pops faded in 2025.

## Exact rules
Sources: a LuxAlgo summary and search-result summaries of IBD's rules. None of these were checked against IBD's
own text, so all numbers are unverified.
- **Universe:** stocks listed within roughly the past 12 months (the first year, often the first few months).
- **Base:**
  - starts within about 25 sessions of the first trade
  - length often under 5 weeks, as short as about 7 sessions
  - depth usually 20% or less, up to about 50% in volatile markets
- **Pivot:** the base high (left-side high). An earlier, riskier entry uses a trendline across the descending
  highs.
- **Trigger:** close above the pivot on a clear volume pickup. Same buy zone as other bases (pivot to pivot + 5%).
- **Stop:** below the base low or a fixed percentage. MarketSurge's loss-cutting zone is 5-8% below the pivot.
- **Targets:** MarketSurge's profit-taking zone is 20-25% above the pivot.
- **Lockup:** expiry is typically 90-180 days after listing; the pattern either absorbs the new supply or breaks.

## Why it should work
- A new issue has no overhead supply from earlier buyers.
- The first base shows the post-IPO sellers (flippers, early allocations) being absorbed.
- A volume breakout signals institutions building positions they could not fill in the deal.
- Thin float amplifies moves both ways.
- The other side: allocation holders taking profits and short-sellers betting on the IPO underperformance anomaly.

## When it works and when it fails
- **Works:** in hot, healthy markets with institutional demand for growth issues (the cited example is Google's
  first base in Sep 2004).
- **Fails:** when IPO pops reverse.
  - Wolf Street (29 Dec 2025): 14 of the 20 largest 2025 IPOs traded below their IPO price, and 11 of the 20
    were more than 40% below their peaks. Examples: Figma -73%, Circle -73%, Firefly -68% and Fermi -76% from
    their peaks.
  - Lockup expiries and follow-on offerings inside the hold also cause failures.

## Parameters and sensitivity
| Parameter | Value |
|---|---|
| `max_days_since_ipo` | 250 (also try 120) |
| `base_start_max_days` | 25 |
| `base_min_bars` | 7 |
| `base_max_bars` | 40 |
| `base_max_depth` | 0.25 (also 0.35, 0.50) |
| `vol_mult` | 1.5 |
| `max_extension` | 0.05 |
| `stop_pct` | 0.08 |
| `target_pct` | 0.20 |
| `lockup_buffer_days` | 5 |

The sample is tiny (a few dozen liquid IPOs a year) and clusters in IPO waves, so expect large variance.

## Evidence
- Catalog grade C: O'Neil's model-book studies, which are descriptive. No independent test was found.
- Academic backdrop (from knowledge, not fetched this run): IPOs underperform comparable firms over 3-5 years
  (Ritter 1991, *J. Finance*). That is a base rate against the long side, not a test of first-base breakouts.
- The 2025 Wolf Street figures above describe pop-then-fade behavior. They are not breakout statistics.

## Common mistakes
- Buying the day-1 or day-2 pop.
- Calling a 3-day pause a "base".
- Ignoring the lockup calendar and S-1/S-3 follow-ons.
- Sizing a thin-float issue on the ATR of its first 20 bars, which is unstable.

## Discretionary parts and how to make them mechanical
- **IPO date:** from EDGAR 424B4 / S-1 effectiveness, or the first bar in a survivorship-free bar store (Massive
  with `active=false`). The first bar alone is not enough: spin-offs, uplistings and SPACs look like IPOs.
  Exclude SPAC de-SPACs and uplistings with an enum or a form-type check.
- **Lockup date:** IPO date + 180 days by default, or parsed from the prospectus (manual).

## Implementation spec for swing-engine
**Features:**
- `days_since_ipo` (sessions since the first bar, or the 424B4 date)
- `ipo_base_high` = max(high) over [base start, as_of - 1]
- `ipo_base_low`
- `ipo_base_depth = 1 - ipo_base_low / ipo_base_high`
- `post_ipo_high` = max high since listing

**Base search:** with `days_since_ipo <= max_days_since_ipo`, scan windows starting 0-25 sessions after listing.
A valid base:
- satisfies `base_min_bars <= len <= base_max_bars` and `depth <= base_max_depth`
- has no earlier breakout above the base high, which makes it the first base

**Signal:**
- close > `ipo_base_high` and close / `ipo_base_high` - 1 <= 0.05
- volume / mean(volume since listing, excluding day 1) >= 1.5. The standard `avg_vol_50d_prev` needs 50 bars,
  which a new issue does not have.

**Orders:**
- Entry at the close, or next open.
- Stop = max(`ipo_base_low`, entry x 0.92).
- Target entry x 1.20.
- Exit on a close back below the pivot within 3 bars, and before `lockup_date - lockup_buffer_days`.
- `max_hold_days` 40. Minimum R:R 2.0.

**Reuse:** the `flat_base` detector from `features/patterns2.py` with relaxed minimum bars; `base_breakout` exits.

**Missing:**
- an IPO-date source (EDGAR form index for 424B4)
- lockup dates
- short-history fallbacks for features that need 50-252 bars: `rs_63d_rank` and `trend_state` are NaN for new
  issues, so `trend_ok` fails today
- the `universe.min_avg_volume` 500k screen also needs a short-history path

## What the router should know
- `healthy_uptrend` only.
- `trend_state` is NaN for new issues, so the default `trend_ok` silently rejects every IPO. This strategy must use
  `min_trend_state` = -1 plus its own checks.
- Correlated with IPO-market sentiment, so cap the number of concurrent IPO positions at 2 (param).

## Signs of decay to monitor
- Fraction of the year's IPOs trading below their offer price (the Wolf Street measure).
- First-base failure rate within 10 bars.
- Performance through lockup windows.

## Sources
- https://www.luxalgo.com/library/concept/ipo-base.md (fetched 2026-10-07)
- https://wolfstreet.com/2025/12/29/ipo-bloodletting-after-the-pop-in-2025-venture-global-coreweave-figma-klarna-bullish-circle-internet-naven-firefly-fermi/ (fetched 2026-10-07)
- https://levelup.gitconnected.com/trading-cup-and-handles-with-marketsmith-pattern-recognition-3b869d0cfe2a
- https://www.scribd.com/document/781709581/Using-MarketSurge
- https://traderlion.com/profile/chhirag-kedia/master-ipo-base-trading/ (search result; not read)
- https://finance.yahoo.com/news/own-ipo-stock-weigh-8-211500240.html (IBD; listed in `docs/methods.md`, not read)
- `docs/methods.md` 1b (IPO after-market row, sweep 42)
- Ritter, J. (1991), "The Long-Run Performance of Initial Public Offerings", *J. Finance* 46(1). Cited from
  memory, not fetched.

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4 | 0 | 0% | -0.98 | -1.00 | 0% | -0.98 | -1.00 | 0% | -0.98 | -1.00 | 0.00 |
| healthy_uptrend | 56 | 0 | 41% | -0.04 | -0.08 | 5% | -0.28 | -0.32 | 59% | -0.02 | -0.06 | 0.92 |
| **all** | 60 | 0 | 38% | -0.10 | -0.14 | 5% | -0.33 | -0.37 | 55% | -0.09 | -0.13 | 0.75 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2 | 0 | 100% | +2.29 | +2.27 | 100% | +2.29 | +2.27 | 100% | +2.29 | +2.27 | inf |
| correction | 1 | 0 | 100% | +0.23 | +0.20 | 0% | -1.25 | -1.28 | 0% | -1.25 | -1.28 | 0.00 |
| healthy_uptrend | 20 | 0 | 55% | +0.36 | +0.34 | 50% | +0.36 | +0.33 | 50% | +0.41 | +0.39 | 1.98 |
| high_vol_selloff | 2 | 1 | 100% | +0.06 | +0.03 | 0% | -1.31 | -1.33 | 0% | -1.31 | -1.33 | 0.00 |
| narrow_uptrend | 7 | 0 | 86% | +0.59 | +0.56 | 86% | +0.53 | +0.51 | 57% | +0.80 | +0.78 | 3.24 |
| **all** | 32 | 1 | 68% | +0.52 | +0.50 | 58% | +0.42 | +0.39 | 52% | +0.51 | +0.49 | 2.18 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
