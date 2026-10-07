---
slug: stine_insider_superstock_weekly
name: Stine insider-buy superstocks (weekly volume thrust, magic line)
originators: [Jesse C. Stine]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [35, 190]
timeframe: weekly
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null   # Stine: "a MAJORITY of my trades didn't work out" (no number)
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built   # superstock_weekly.py proposed; insider_cluster exists but is disabled
---

# Stine insider-buy superstocks (weekly)

## One-line summary
Buy a low-priced, small-float earnings winner when a huge weekly volume thrust (500-5,000%) carries it out of a
long base above its 30-week MA at about 45 degrees, ideally with open-market insider buying. Add on low-volume
pullbacks to the 10-week "magic line". Sell 7-10 weeks after a thrust, on parabolic or largest-range weeks, on
offerings, or on a weekly close below the magic line.

## Origin and lineage
- Jesse Stine, *Insider Buy Superstocks* (2013).
- The 30-week breakout comes from Weinstein, the earnings-and-volume angle from O'Neil, and the insider angle from
  insider-purchase research.
- Do not confuse it with Kenneth Fisher's *Super Stocks* (1984).

## Exact rules
From `docs/methods/14-insider-buy-superstocks-stine.md`. "Book excerpt" means a promo site whose operator is
unnamed.

**Screen:**
- Price under $15 (sweet spot $4-10).
- Market cap under $100M.
- Float under 10M shares, ideally 4-8M.
- Annualized PE run rate (latest quarter EPS x 4) of 10 or less.
- A "blockbuster" quarter.
- Short interest under 20% of outstanding shares.
- No analyst coverage and no listed options are preferred.
- At least 12 months of trading history.
- Insider buying is a bonus, not a must-have, in Stine's own summary.

**Must-haves at the breakout week:**
- A base of 8 weeks to a year or more.
- A weekly close above the 30-week MA.
- Weekly volume up 500-5,000%.
- A high angle of attack (about 45 degrees).
- Price under $15.

**Adds:**
- Buy 2-3 weeks after an earnings breakout once the gap is tested.
- Buy aggressively at the magic line (10-week SMA for the best performers) on the lowest recent weekly volume.
- Superstocks touch the magic line about every 10-12 weeks.

**Stop:** no number was found. The rule-consistent version is a weekly close below the magic line, or below the
30-week MA / base top for a fresh breakout.

**Sells:**
- 7-10 weeks after the thrust.
- About 9 months into the advance.
- Parabolic weeks, the largest weekly range, or a weekly gap at a new high.
- The 4th-5th surge off the magic line.
- About 60% above the 10-week line (trim) or more than 100% above it (exit). These figures are secondary.
- Offerings or private placements, insider selling, or splits.
- Some stocks "must be sold at $25" (mechanism unverified).

**Sizing:** concentrated and Kelly-style. Stine reports early-career drawdowns of 61-106%. Do not copy this sizing.

## Why it should work
Insider purchases in small firms are informative. Small, uncovered stocks under-react to earnings (PEAD is
strongest there), and a volume thrust from a long base marks the moment the information is priced. The sellers
are long-suffering base holders and value investors who missed the earnings change.

## When it works and when it fails
- **Works:** small-cap bull and value-rotation tapes, such as Stine's 2003-06 window and the Russell 2000's H1
  2026 run with value leadership.
- **Fails:**
  - Bear markets (Stine: superstocks fall too).
  - Dilution waves: in 2025-26 the sub-$15, low-float pool is full of reverse-split survivors and ATM users.
  - Pump-and-dumps that share the price and float profile.

## Parameters and sensitivity
| Parameter | Value |
|---|---|
| `max_price` | 15 |
| `max_float` | 10e6 |
| `max_mcap` | 100e6 |
| `max_pe_run_rate` | 10 |
| `min_wk_vol_ratio` | 5.0 |
| `min_base_weeks` | 35 |
| `ma_slow_weeks` | 30 |
| `magic_line_weeks` | 10 |
| `require_insider` | test both values |
| `trim_ext` / `exit_ext` | 0.6 / 1.0 |
| `thrust_time_stop_weeks` | 7-10 |
| `max_hold_sessions` | 190 |

Choosing "the MA the stock respects" after the fact is curve fitting. TradingSkeptic says exactly this.

## Evidence
- Self-reported: $45,721 -> $6,845,342, 26 Sep 2003 to 27 Jan 2006. Brokerage statements are posted but there is
  no CPA attestation, and no results after 2006.
- There is no independent backtest. One out-of-sample anecdote: AOI (2018) passed most technical checks, had no
  insider buying, and later went through Chapter 11.
- The components have support:
  - Opportunistic insider trades earn 82 bp/month (Cohen, Malloy & Pomorski 2012).
  - Insider purchase informativeness is concentrated in small firms (Lakonishok & Lee 2001).
  - MA timing works best in high-volatility deciles (Han, Yang & Zhou 2013).
- Lottery-like low-priced stocks underperform on average (Bali, Cakici & Whitelaw 2011; cited from memory).
- Grade D.

## Common mistakes
- Requiring insider buying and finding nothing, or dropping the earnings and PE filters and buying pumps.
- Trading without stops (Stine's own 2008 failure).
- Size larger than weekly liquidity allows.
- Annualizing a one-off quarter.

## Discretionary parts and how to make them mechanical
- **"Sustainable earnings", "super theme", "It factor":** Claude enums.
- **Angle of attack:** 8-week return of at least 50%, or the log-slope of `wk_sma_10`.
- **Insider quality:** C-suite or director open-market buys (Form 4 code P) above a dollar floor. Salary data is
  not used.

## Implementation spec for swing-engine
**Features:**
- `features/weekly.py` (shared with Weinstein): `wk_sma_10`, `wk_sma_30`,
  `wk_vol_ratio = wk_volume / mean(wk_volume.shift(1), 10)`, `wk_range`, `wk_range_rank`, `wk_base_len`.
- Float from `data/float_data.py`.
- `pe_run_rate = close / (4 x latest diluted quarterly EPS)` from EDGAR XBRL, by filing date. Not ingested.
- `insider_cluster_score` from the Form 4 ingest.

**Signal (on a completed week):**
- `wk_close > wk_sma_30` and `wk_close > wk_base_high`
- `wk_vol_ratio >= 5`
- `wk_base_len >= 35`
- close < 15, float < 10M, `pe_run_rate` in (0, 10]

**Orders and exits:**
- Entry at the next open. Add-ons when the low is within 2% of `wk_sma_10` on the lowest weekly volume of the
  last 8 weeks. Scaling in needs a pyramiding hook, which does not exist.
- Stop: weekly close < `wk_sma_30` for a fresh breakout, or < `wk_sma_10` after adds.
- `should_exit`: weekly close < `wk_sma_10`; 10 weeks since the last thrust; close / `wk_sma_10` - 1 >= 1.0; any
  S-1/S-3/424B/8-K 3.02 filing (already detected for the small-cap track); 190 sessions.
- No target. `min_reward_risk` 0.
- **Universe conflict:** `universe.min_price` 5 and `min_avg_volume` 500k exclude much of Stine's universe. The
  strategy needs its own universe, plus an ADV participation cap of 1-2% of 20-day dollar volume.
- `earnings_exit_days` must be overridden: earnings are the catalyst.

## What the router should know
- Small-cap trend matters more than SPY. Add an IWM > 30-week MA gate.
- Use tiny size and at most 1-2 concurrent positions.
- Its candidate sets overlap the small-cap monitor, whose posture is warn/fade.
- Expect 8-10 candidates a year at most.

## Signs of decay to monitor
- Share of qualifiers that file an offering within 60 days.
- Thrust-week follow-through (next 4 weeks above the thrust close).
- Russell 2000 EPS revisions.

## Sources
- https://www.jessestine.com/
- https://jessestine.com/investment-documentation/
- https://jessestine.com/25-shocking-highlights/
- https://insiderbuysuperstocks.weebly.com/the-elusive-superstock.html
- https://tradingskeptic.com/insider-buy-superstocks-review/
- https://www.financialwisdomtv.com/post/insider-buy-superstocks-by-jesse-stine
- https://papers.ssrn.com/abstract=1692517
- https://ideas.repec.org/a/cup/jfinqa/v48y2013i05p1433-1461_00.html
- https://www.vcm.com/assets/market-insights/Integrity-Monthly-Commentary-July-2026.pdf
- `docs/methods/14-insider-buy-superstocks-stine.md`; `docs/methods.md` 1a #14, 6.14

## Empirical (replay)
_Pending: filled in from swing replay on real data._
