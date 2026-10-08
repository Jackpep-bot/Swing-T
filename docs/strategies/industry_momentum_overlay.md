---
slug: industry_momentum_overlay
name: Industry / sector momentum overlay
originators: [Moskowitz-Grinblatt (JF 1999)]
category: strategy
decision: implement
holding_period_days: [21, 252]
timeframe: monthly industry rank, applied daily as an overlay
direction: long (academic factor is long-short)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Industry momentum overlay

## One-line summary
Rank industries on their past 6-month value-weighted return (no skip month) and prefer swing longs in the top-ranked
industries; industry momentum is strongest in the first month and lasts up to a year.

## Origin and lineage
- Moskowitz & Grinblatt, "Do Industries Explain Momentum?", Journal of Finance 54(4), 1999.
- Practitioner echo: IBD group RS, "trade the leading theme", sector-ETF relative-strength rotation (methods.md 1b,
  grade C as a standalone system; use as a ranking input).

## Exact rules (HXZ implementation)
1. Fama-French 49 industries; drop financials, leaving 45.
2. Each month-end, compute each industry's value-weighted return over t-6..t-1 (no skip month).
3. Form 9 portfolios of 5 industries each, equal-weighted across industries.
4. Long the top portfolio, short the bottom; hold 1, 6 or 12 months.

## Why it should work
- Information diffuses slowly across firms in an industry (lead-lag); investors underreact to industry-wide shocks.
- MG find industry momentum explains much of individual-stock momentum; no 1-month reversal at industry level, hence
  no skip month.
- Other side: investors anchored to single-stock valuations, slow institutional rotation.

## When it works and when it fails
- Works: theme-driven markets (AI/semis 2024-25, rotation from chips to hyperscalers flagged mid-2026 by a Morgan
  Stanley strategist per Bloomberg headline in the catalog).
- Fails: abrupt rotations and junk rebounds; sector crowding unwinds (e.g. the Feb 2026 software rout).
- Coarse sector ETFs (11 GICS sectors) blur the signal relative to 45 industries.

## Parameters and sensitivity
| Knob | Published | Range |
|---|---|---|
| industry scheme | FF49 minus financials | SIC 2-digit, GICS sector ETFs, industry ETFs |
| formation | 6 months, no skip | 1-12 |
| weighting | VW within industry | EW fallback when caps are missing |
| buckets | 9 x 5 industries | top third / bottom third |
| hold | 1 month | 1-12 |
Traps: picking the industry scheme that backtests best; tiny industries with 3-5 members are noisy (require
>= 5 members).

## Evidence
- HXZ (VW, through 2014): Im1 0.67%/mo (t = 2.74), Im6 0.60% (t = 3.08), Im12 0.64% (t = 3.71).
- MG 1999: profitable after controlling for size, book-to-market, stock momentum and microstructure; strongest at 1
  month.
- Post-publication: survives the HXZ replication (catalog grade B). No cost-inclusive estimate in the sources read.

## Common mistakes
1. Using current SIC codes for history (firms change industries); use the code as of the filing date.
2. Equal-weighting tiny industries.
3. Treating it as a standalone system in a narrow market where one industry dominates the index.

## Discretionary parts and how to make them mechanical
Industry definition is the only judgement; fix one scheme per version. "Leading theme" judgement in reviews can be
mapped to this rank.

## Implementation spec for swing-engine
- Data: SIC code per CIK from SEC EDGAR company submissions (free; `data/edgar.py` has `company_tickers`, SIC ingest
  not yet built); map SIC to FF49 with French's definitions file. Fallback: 11 SPDR sector ETFs or industry ETFs as
  proxies (bars via the normal provider).
- Feature `ind_ret_126d` per industry and session: `sum_i(w_i * ret_126d_i) / sum_i w_i`, `w_i` = market cap
  (`close * shares_outstanding` from `data/float_data.py`, point-in-time) else equal weight; require >= 5 members.
- `ind_mom_rank` = percentile of `ind_ret_126d` across industries on that session; broadcast to member rows;
  recompute monthly (month-end) per the paper, or daily for a smoother variant (versioned).
- Overlay uses: score multiplier `1 + k * (ind_mom_rank - 0.5)` in candidate ranking; or hard filter
  `ind_mom_rank >= 0.67` for breakout family; sector cap stays `max_sector_pct: 30`.
- Add to ranker features.
- Missing: SIC ingest with history, FF49 mapping table, market caps history.
max_hold_days: n/a (overlay). Min reward:risk: n/a.

## What the router should know
- Use as a tilt in every long regime; most valuable in `narrow_uptrend` where leadership is concentrated.
- Combine with `max_sector_pct` to avoid concentrating all positions in the top industry.

## Signs of decay to monitor
- Top-third vs bottom-third industry spread of next-21-day returns <= 0 over 12 months.
- Overlay-filtered signals not outperforming unfiltered signals in the shadow ledger.

## Sources
- https://ideas.repec.org/a/bla/jfinan/v54y1999i4p1249-1290.html
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- https://www.bloomberg.com/news/articles/2026-07-06/morgan-stanley-s-wilson-sees-rotation-from-chips-to-hyperscalers
- https://www.reddit.com/r/swingtrading/comments/1v1oveh/
- Repo: `docs/catalog/catalog.json` (E03), `docs/methods.md` 1b

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 18 | 0 | 27% | -0.25 | -0.32 | 40% | -0.17 | -0.25 | 47% | +0.03 | -0.04 | 1.08 |
| healthy_uptrend | 39 | 0 | 51% | +0.08 | -0.01 | 59% | +0.14 | +0.06 | 38% | +0.01 | -0.07 | 1.02 |
| high_vol_selloff | 12 | 0 | 42% | -0.25 | -0.35 | 50% | -0.13 | -0.24 | 58% | -0.03 | -0.13 | 0.93 |
| narrow_uptrend | 3 | 0 | 67% | +0.68 | +0.58 | 67% | +0.68 | +0.58 | 100% | +1.27 | +1.17 | inf |
| **all** | 72 | 0 | 45% | -0.02 | -0.11 | 54% | +0.05 | -0.04 | 46% | +0.06 | -0.02 | 1.15 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 49 | 0 | 65% | +0.22 | +0.16 | 65% | +0.28 | +0.22 | 45% | +0.07 | +0.01 | 1.20 |
| correction | 29 | 0 | 66% | +0.18 | +0.09 | 83% | +0.31 | +0.22 | 69% | +0.44 | +0.35 | 2.78 |
| healthy_uptrend | 106 | 0 | 52% | -0.05 | -0.13 | 54% | +0.00 | -0.08 | 58% | +0.10 | +0.02 | 1.26 |
| high_vol_selloff | 38 | 0 | 71% | +0.27 | +0.19 | 63% | +0.08 | -0.01 | 68% | +0.21 | +0.12 | 1.62 |
| narrow_uptrend | 34 | 0 | 56% | +0.07 | +0.00 | 62% | +0.18 | +0.12 | 47% | -0.03 | -0.09 | 0.95 |
| **all** | 256 | 0 | 60% | +0.09 | +0.02 | 62% | +0.13 | +0.05 | 57% | +0.13 | +0.06 | 1.34 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
