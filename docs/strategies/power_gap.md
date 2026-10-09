---
slug: power_gap
name: Power earnings gap / buyable gap-up, consolidation entry
originators: [Trader Stewie (PEG label), Gil Morales & Chris Kacher (Buyable Gap-Up), Kristjan Kullamagi / Pradeep Bonde (earnings Episodic Pivot)]
category: strategy
decision: have
holding_period_days: [3, 60]
timeframe: daily (gap-day ORH entries need intraday bars)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: 0.30        # Bulkowski BGU test 28-32% winners (2001-2010)
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: shadow_only
---

# Power gap / buyable gap-up, consolidation entry (`power_gap`)

## One-line summary
After a hard earnings gap-up (10%+ or 0.75x ATR(40)+, on 2x+ average volume, closing strong), wait for a 2-30 day
tight hold above the gap-day low and buy the first close above that consolidation; stop at the gap-day low (capped
at 1.5 ADR); trail the 20-day.

## Origin and lineage
- **PEG**: popularised by @traderstewie (Art of Trading); numeric thresholds credited to John Pocorobba & Jason
  Thompson via a TradingView script (gain >= 10%, volume "200% above" the 50-day average, EPS surprise >= 20%).
  Stewie's trade is the consolidation after the gap. No primary Stewie text was accessed.
- **BGU**: Kacher & Morales, *Active Trader* Dec 2010; *In The Trading Cockpit with the O'Neil Disciples* (Wiley 2012):
  gap >= 0.75x 40-day ATR (prior bar), volume >= 1.5x 50-day; gap-day intraday low is the sell guide; MA "violation"
  exits.
- **Earnings EP**: Bonde named it; Kullamagi codified the earnings version (10% gap, ADV traded in the first 15-20
  minutes, 1-minute ORH entry, LOD stop <= 1-1.5 ADR). Separate card: `episodic_pivot`.
- Academic backbone: post-earnings-announcement drift, strongest when sorted on the price reaction (EAR / jump).

## Exact rules
As taught (docs/methods/13):
- **Universe**: liquid, fundamentally sound leaders (BGU); "not while a stock is in a downtrend".
- **Event**: quarterly earnings gap day (first session after an after-close or pre-open release).
- **Gap**: >= 10% (PEG/EP) or >= 0.75x ATR(40) through the prior bar (BGU). "Monster gap": >= 20% on "300% above" volume.
- **Volume**: "200% above" 50-day average (ambiguous: 2x or 3x) for PEG; >= 1.5x for BGU.
- **Close**: strong close in the upper part of the range; high-volume close (HVC) is a reference level.
- **Entries** (three different trades): (1) gap-day opening-range high (1-minute ORH); (2) consolidation breakout
  after a 2-5 day (up to ~30-bar) tight hold, volume drying up, buy the break of the consolidation high on volume;
  (3) pullback to the gap-day low (BGU), with a 2-4% cushion.
- **Initial stop**: gap-day low (EP: <= 1-1.5 ADR from entry); BGU 2-3% below the gap-day low; consolidation low; or
  gap midpoint (TradeZella).
- **Exits**: 1/3-1/2 after 3-5 days or +8-20%, stop to breakeven; trail the 10/20-day MA (Kullamagi: first close
  below); Morales violation = close below the MA then a lower low the next day (10-day if held >= 7 weeks, else 50-day);
  failure = close below the gap-day low or a gap fill.
- **Sizing**: 0.25-1% risk (Kullamagi); 50-75% of normal size (TradeZella); sector cap in earnings season.

## Why it should work
- Under-reaction to large earnings news: price-reaction (EAR) and jump-based PEAD. Counterparty: holders anchored to
  pre-report value and slow institutional repositioning that keeps buying for weeks.
- Frazzini & Lamont (2007): announcement premium tied to attention and past announcement volume.

## When it works and when it fails
- Works: true leaders with real fundamental surprises, constructive or neglected prior base, supportive market;
  consolidation entries in range tapes.
- Fails: "gap and crap" same-day reversals; gap fills; repeat gappers (Kullamagi: higher failure rate); microcaps where
  costs eat drift; earnings-season sector clustering. Q2 2026 S&P beats earned only +0.4% (-2 to +2 days) vs +1.0%
  five-year average (FactSet), so only extreme reactions matter.

## Parameters and sensitivity
| Knob | Default | Range |
|---|---|---|
| `min_gap_pct` | 0.10 | 0.08-0.20 |
| `min_gap_atr40` | 0.75 | 0.75-1.5 |
| `min_volume_ratio` | 2.0 | 1.5-3.0 (vs prior 50-day) |
| `min_close_pos` | 0.7 | 0.5-0.8 |
| `consol_min_bars` / `consol_max_bars` | 2 / 30 | 2-5 / 10-30 |
| `breakout_rvol_min` | 1.5 | 1.2-2.0 |
| `max_stop_adr` | 1.5 | 1-1.5 |
| `trail_ma` | sma_20 | sma_10 / sma_20 / sma_50 |
| `target_r` | 10 (reference only) | |
| `max_hold_days` | 60 | 20-60 |
| `min_market_trend_state` | 1 | |
| `min_reward_risk` | 2.0 | |
Traps: definition drift ("200% above" = 2x or 3x; open gap vs close gain; true gap vs open gap); few true monster gaps
per season, many knobs.

## Evidence
- Brandt, Kishore, Santa-Clara & Venkatachalam (WP 2007, 1987-2004): EAR long-short 6.3%/yr abnormal vs 5.6% for
  SUE; combined ~11-11.5%/yr; reduced but not eliminated in large caps.
- Zhou & Zhu (FAJ 2012, 1971-2009): long positive-jump / short negative-jump, hold t+2 to t+61: 3.63%/quarter
  (~15.3%/yr) FF alpha, Sharpe 1.52.
- Chordia et al. (FAJ 2009): drift 0.04%/month in the most liquid vs 2.43%/month in the most illiquid; costs eat
  70-100%.
- Martineau (CFR 2022): large-stock PEAD non-existent since 2006. Subrahmanyam (WP, UCLA Anderson Review 21 Jan 2026):
  2001-2024 t = 2.18 all stocks, 1.43 ex-microcaps.
- Bulkowski BGU test (557 stocks, 12 Mar 2001-1 Oct 2010, up to 1,504 trades, no fundamental filter): average gain
  1.2-3.1%, 28-32% winners, 29-43 day holds; one outlier lifts the best variant from 2.6% to 3.1%; not recommended.
- No post-2010, net-of-cost, liquid-universe test of the price-reaction version and no test of the exact PEG
  definition was found.

## Common mistakes
1. Treating a volume gap without an earnings event as a PEG (the code does exactly this today; see label).
2. Gap-day LOD stops on 10%-range days -> tiny or oversized positions.
3. Chasing the gap-day close in a daily backtest and calling it an ORH entry.
4. No sector cap in earnings season.
5. Undecided policy on holding through the next report (academic drift partly sits there).

## Discretionary parts and how to make them mechanical
- Report quality (guidance raise, acceleration, one-offs): Claude review enum from 8-K text; never a price.
- "Neglect" / not extended: `ret_126d` cap, no prior qualifying gap in 252 bars.
- "Tight" consolidation: max(high)/min(low) - 1 over the consolidation <= k x ADR (missing; current code only
  requires lows above the gap-day low).
- Volume dry-up: 5-bar mean volume < 50-bar mean (missing).

## Implementation spec for swing-engine
What `swing_engine/strategies/power_gap.py` does:
- Gates: `market_trend_state >= 1`; `trend_state >= 0`; as-of `rvol_day >= 1.5`.
- Gap day g = the most recent qualifying bar with t-1-30 <= g <= t-1-2 (`gap_consolidation`, end = t-1, so the
  consolidation g+1..t-1 is 2-30 bars long): (`gap_pct >= 0.10` or `gap_atr40 >= 0.75`) and `vol_ratio_50d_prev >= 2.0` and `close_pos >= 0.7`; every bar g+1..t-1 has low > gap-day low.
- Trigger: `close_t > pivot` (highest high of g+1..t-1) and no earlier close in the consolidation broke its running
  high (one entry per gap).
- Entry reference = close, next-open fill. Stop = max(gap-day low, close x (1 - 1.5 x adr_pct_20)).
  Target = close + 10R (reference). Score = gap-day volume ratio.
- `should_exit`: `bars_held >= 60` or close < `sma_20`.
- Label: `earnings_verified = 0`; signals are volume gaps, not verified earnings gaps (no point-in-time earnings dates).
Differences from the originators: no earnings requirement or EPS surprise; no consolidation tightness or volume dry-up
test; close-based breakout filled next open; no partial sale at day 3-5; SMA-20 close exit instead of the Morales
violation rule; no sector cap at the strategy level (portfolio `max_sector_pct` 30 applies). Also note
`execution.earnings_exit_days: 1` flattens positions before the next report, which takes the practitioner side of the
hold-through-earnings question.
- `max_hold_days`: 60. Min reward:risk: 2.0 (reference target makes it always pass).
- Reuses (features/patterns2.py): `gap_atr40`, `vol_ratio_50d_prev`, `adr_pct_20`, `atr_40`; cross_section `gap_pct`,
  `close_pos`, `rvol_day`; `sma_20`.
- Missing: point-in-time earnings dates (EDGAR 8-K Item 2.02 acceptance time), EPS surprise, `true_gap`, scale-out
  hook, intraday bars for ORH entries, gap-low pullback entry mode.

## What the router should know
- Settings: `enabled: false, shadow_only: true`; router allows it only in `healthy_uptrend`; code also requires SPY
  trend up. Stays out of execution until earnings dates exist (methods.md 7b #3).
- Earnings-season clustering: many signals in the same industry within weeks; count them against sector caps.

## Signs of decay to monitor
- Shadow win rate < 25% or average R <= 0 over 50 gaps.
- Share of consolidations failing (close below gap-day low) within 5 bars after entry.
- FactSet-style average reaction to beats shrinking further (fewer qualifying gaps).

## Sources
- docs/methods/13-power-earnings-gap.md; docs/methods.md 1a #10, 6.13, 7b #3
- https://tradingsim.com/blog/episodic-pivot-power-earnings-gap-buyable-gap-up-explained/
- https://www.thepatternsite.com/KacherMorales.html
- https://www.tradingview.com/script/KWTJ9jeC-Earnings-Gap-Ups/
- https://usethinkscript.com/threads/power-earnings-gaps-peg-scanner-for-thinkorswim.82/
- https://qullamaggie.com/how-to-master-a-setup-episodic-pivots/
- https://www.tradezella.com/blog/swing-trading-strategies
- https://www.anderson.ucla.edu/documents/areas/fac/finance/ear.pdf
- https://bpb-us-w2.wpmucdn.com/sites.udel.edu/dist/a/855/files/2020/07/Jump-on-the-Post%E2%80%93Earnings-Announcement-Drift.pdf
- https://ideas.repec.org/a/taf/ufajxx/v65y2009i4p18-32.html
- https://cfr.ivo-welch.org/published/papers/martineau2021rest.pdf
- https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/Earnings%20Insight/EarningsInsight_080726.pdf

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 160 | 4 | 34% | -0.17 | -0.28 | 33% | -0.15 | -0.27 | 26% | -0.17 | -0.28 | 0.77 |
| narrow_uptrend | 19 | 0 | 44% | -0.16 | -0.26 | 38% | -0.21 | -0.30 | 17% | -0.66 | -0.75 | 0.23 |
| **all** | 179 | 4 | 35% | -0.17 | -0.28 | 33% | -0.16 | -0.27 | 26% | -0.20 | -0.32 | 0.73 |

Portfolio replay (net of costs, slots shared with its run): 10 trades, win 10%, avg -0.40R, PF 0.41, P&L $-1,963 on $100k, avg hold 8.3 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 463 | 11 | 44% | -0.01 | -0.15 | 40% | +0.01 | -0.12 | 35% | +0.05 | -0.09 | 1.08 |
| narrow_uptrend | 64 | 0 | 41% | +0.01 | -0.14 | 45% | +0.10 | -0.06 | 36% | +0.06 | -0.10 | 1.10 |
| **all** | 527 | 11 | 43% | -0.01 | -0.15 | 41% | +0.02 | -0.11 | 35% | +0.05 | -0.09 | 1.08 |

Portfolio replay (net of costs, slots shared with its run): 26 trades, win 23%, avg -0.33R, PF 0.37, P&L $-5,180 on $100k, avg hold 11.0 bars.
