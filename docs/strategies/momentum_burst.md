---
slug: momentum_burst
name: Stockbee 4% momentum burst
originators: [Pradeep Bonde (Stockbee)]
category: strategy
decision: have
holding_period_days: [3, 5]
timeframe: daily (taught entry is intraday, first 30 minutes)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: 0.47        # Alma 2025 raw trigger, 5-day hold, no stops, no costs, no filters
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: disabled
---

# Stockbee 4% momentum burst (`momentum_burst`)

## One-line summary
Buy the first range-expansion day (close up 4%+ on volume above yesterday's, closing near the high) out of a quiet
3-20 day base in a young trend; stop at the entry-day low; out within 3-5 days. Only when Market Monitor breadth says
breakouts are working.

## Origin and lineage
- Pradeep Bonde, stockbee.blogspot.com (rule posts 2013-2021; situational-awareness posts to Jul 2026). Scan
  `c/c1>=1.04 and v>v1 and v>100000`, used "for over 14 years" by 2014. Origin claim: a 1999-2000 Compustat study of
  25%+ moves (unpublished, outcome-conditioned).
- Related to Toby Crabel's range contraction/expansion (NR4/NR7); sibling of Bonde's Episodic Pivot; Kullamagi's
  day 3-5 partial sale descends from it.
- 2024 shorthand "2LYNCH": not up 2 days in a row, linear, prior day narrow or negative, orderly consolidation, close
  near high ("Y" undefined; "young trend" likely, unverified).

## Exact rules
As taught (primary blog posts, docs/methods/09):
- **Scan**: close/prior close >= 1.04, volume > prior volume, volume > 100k. Dollar variant for stocks > $40:
  close - open >= $0.90 on > 100k volume. Works best in small/mid caps and lower-priced stocks.
- **Quality filters** (remove "95% or more" of hits): prior day narrow-range or down; not up 3 days in a row
  (2024: not up 2); 3-20 day quiet base (5-10 ideal) with no prior burst; no 4% breakdowns in the base / last 3-5
  days; linear, orderly prior leg; close at or near the high; first to third breakout of a young trend.
- **Market filter**: Market Monitor breadth: 10-day ratio of 4%-up to 4%-down counts >= 2 favours longs; <= 0.5
  favours shorts; clusters of 300+ 4%-up days start bull moves. The stock's own MA trend is not a filter.
- **Entry**: intraday as soon as it breaks out (best candidates in the first 30 minutes); EOD scan with next-day
  entry explicitly allowed (18 Nov 2015). Anticipation: buy-stop 1 cent above a pre-computed trigger.
- **Initial stop**: low of the entry day.
- **Management**: breakeven intraday once +4-5%; exit same day if it fades.
- **Exits** (13 Jul 2017): +8% same or next day -> sell 50%, stop $0.25 under the day's high; sell at least 50% at the
  day-3 close and trail $0.25 under the high; gap of 20%+ on day 2-3 -> exit at the open; no follow-through in 3 days
  -> exit or breakeven. Overall 3-5 days.
- **Sizing**: 0.25-1% risk (up to 4% rarely); shares = capital x risk / (entry - low of day). Scale to 1-2% only after
  100-200 trades at 2:1 and ~50% wins.

## Why it should work
- Claimed mechanism: momentum starts with range expansion and lasts 3-5 days (Bonde). Academic default is the
  opposite: 1-2 week reversal after big up moves (Jegadeesh 1990; Lehmann 1990; Gutierrez & Kelley 2008 show the
  extreme-week portfolio loses in the first two weeks).
- Continuation is documented for high-volume / high-turnover stocks (Gervais-Kaniel-Mingelgrin 2001; Medhat &
  Schmeling RFS 2022) and for moves with news (Chan 2003; Savor 2012), so the edge, if any, comes from volume,
  catalyst and the quality filters. Counterparty: liquidity providers and short-term reversal traders.

## When it works and when it fails
- Works: breadth thrusts (e.g. Apr 24-25 2025), small/mid-cap participation.
- Fails: range-bound tapes, fast selling phases, near market turns. Bonde (20 Jul 2026): range-bound market,
  breakouts unlikely to follow through until a breadth thrust. Russell 2000 -7.52% in Q3 2026.
- Low-float meme bursts without follow-through (Barber et al. 2022 attention effect).

## Parameters and sensitivity
| Knob | Code default | Taught | Notes |
|---|---|---|---|
| `max_prev_move` | 0.02 (absolute) | prior day not up > 2% (one-sided) | code bug, see below |
| `max_up_days` | 2 | 2 (2024) or 3 (2014-17) | `up_days_3` includes today |
| `min_volume` | 100,000 | 100k (some posts 200k) | |
| `max_hold_days` | 5 | 3-5 | |
| `stop_atr_buffer` | 0.0 | 0 | entry-bar low |
| `target_r` | 2.0 | none (8% partial) | reference only |
| `min_trend_state` | -1 | none | |
| `min_market_trend_state` | 0 | breadth, not SPY trend | |
Rule drift (3 vs 2 up days, 3-20 vs <10 base, 100k vs 200k) multiplies trial count: lock one versioned set.

## Evidence
- Self-reported, unaudited: 100k -> 789k over 5 years (2014 post); 60% winners in 2014, worst loss 0.59% of equity.
- Tikam Singh Alma (18 Jun 2025): 1,227 raw-trigger events, S&P 500 + NIFTY750, 2020-Jun 2025, no stops/costs/
  filters: 5-day win rate 46.8%, average +0.88%, 12.8% reached +10% within 5 days.
- EasySwing panel has no momentum-burst detector (nearest, ROC breakout: PF 1.26, 32% wins, gross).
- No public, cost-inclusive walk-forward of the filtered rules. Raw trigger is too thin to survive 20 bps/side.
- Post-publication: rule set publicised since 2013; no decay study.

## Common mistakes
1. Trading the raw scan without the filters.
2. Entering at the close or next open, giving away 4-10% of an 8-20% burst; R:R collapses toward 1:1.
3. Buying day 2-3 of a run.
4. Holding past day 5.
5. Ignoring breadth; losses cluster in the same week.
6. Underestimating costs at 200-1,000 trades a year.
7. Tight-stop sizing producing 50%+ position sizes.

## Discretionary parts and how to make them mechanical
| Discretion | Proxy |
|---|---|
| Prior day narrow/down | `prior_ret_1d <= 0` or prior bar NR7 (missing `nr7`) |
| Quiet base | `bars_since(burst_4pct) >= 3`; base tightness `max(high,N)/min(low,N) - 1` over 5-20 bars |
| No breakdown | count of 4% down days over 5 bars == 0 (missing mirror flag) |
| Close near high | `close_pos >= 0.7` |
| Young trend | `ti65 = sma_7/sma_65 >= 1.05` (missing) or bursts since 63-day low <= 3 |
| Linear / orderly / A-quality | Claude `setup_quality` enum A/B/C for ranking only |

## Implementation spec for swing-engine
What `swing_engine/strategies/momentum_burst.py` does:
- Gates: `market_trend_state >= 0`; `trend_state >= -1` (off).
- Conditions: `burst_4pct == 1`; `abs(prior_ret_1d) <= 0.02`; `up_days_3 <= 2`; `volume >= 100000`; `atr_14 > 0`.
- Entry reference = trigger-day close, filled next open. Stop = trigger-day low (buffer 0). Target = close + 2R.
  Score = rvol vs `avg_vol_20d` x (1 + ret_1d).
- `should_exit`: `bars_held >= 5`.
Differences / bugs:
1. `abs(prior_ret_1d) > 0.02` rejects prior red days, which Bonde prefers (methods.md 7a #5). Fix: `prior_ret_1d <= 0.02`.
2. No close-near-high, base, no-breakdown, young-trend filters.
3. Gate is SPY trend, not Market Monitor breadth.
4. No breakeven at +4-5%, no 8% half sale, no day-3 half exit, no 20% gap exit.
5. Next-open fill with a trigger-day-low stop widens risk; make `stop_ref: trigger_low|entry_low` a param.
6. Universe floors ($5, 500k shares) exclude sub-$5 bursts by design.
Proposed v2 params: `prior_ret_max=0.02` one-sided, `min_close_pos=0.7`, `base_min_bars=3`, `base_max_bars=20`,
`no_breakdown_lookback=5`, `min_ti65=1.05` optional, `mm_ratio_min=2.0`, `partial_day=3`, `partial_frac=0.5`,
`strength_exit_pct=0.08`, `gap_exit_pct=0.20`, `breakeven_trigger_pct=0.045`, `max_hold_days=5`, risk 0.5%.
- Min reward:risk: not meaningful (time exit); keep local 1.0 for the reference target.
- Reuses: `burst_4pct`, `up_days_3`, `ret_1d`, `atr_14`, `avg_vol_20d`, `close_pos`, `inside_day`, features/breadth.py
  (4% up/down counts and the 10-day ratio feed the playbook).
- Missing: scale-out hook, intraday bars for first-30-minute entries, `nr7`, `breakdown_4pct`, `ti65`.

## What the router should know
- Settings: `enabled: false` (logged as a feature). Router lists it only in `healthy_uptrend`.
- Should require the Stockbee 10-day ratio >= 2 even inside `healthy_uptrend`. Turn on only after a breadth thrust.
- Correlated losses: many bursts fail together near turns; cap concurrent burst positions.

## Signs of decay to monitor
- Day-3 follow-through rate (+4-5% on day 2 or 3) falling.
- Win rate below ~45% after filters, or average gain < 2x round-trip cost.
- 10-day breadth ratio below 1 while signals keep firing.

## Sources
- docs/methods/09-stockbee-momentum-burst.md; docs/methods.md 1a #13, 6.9, 7a #5
- https://stockbee.blogspot.com/2013/12/stocks-move-in-short-term-momentum.html
- https://stockbee.blogspot.com/2014/01/how-to-identify-a-quality-setup.html
- https://stockbee.blogspot.com/2014/07/my-swing-trading-process-flow.html
- https://stockbee.blogspot.com/2014/08/how-i-control-my-risk.html
- https://stockbee.blogspot.com/2015/11/how-to-use-4-breakout-scan-to-make-money.html
- https://stockbee.blogspot.com/2017/07/my-process-loop-to-trade-4-bo-and-bo.html
- https://stockbee.blogspot.com/2011/08/how-to-use-market-breadth-to-avoid.html
- https://stockbee.blogspot.com/2026/07/situational-awareness-for-july-20-2026.html
- https://tikamalma.substack.com/p/4-momentum-burst-detailed-research (Alma, 18 Jun 2025)
- https://retailtradersrepository.substack.com/p/pradeep-bonde-momentum-bursts (2LYNCH notes, 2024)
- https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html (Gervais, Kaniel & Mingelgrin 2001)
- https://openaccess.city.ac.uk/id/eprint/31278/ (Medhat & Schmeling, Short-term Momentum)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1822 | 97 | 46% | +0.10 | -0.18 | 43% | +0.11 | -0.16 | 42% | +0.12 | -0.15 | 1.20 |
| correction | 222 | 18 | 57% | +0.52 | -0.26 | 58% | +0.65 | -0.13 | 58% | +0.69 | -0.09 | 2.87 |
| healthy_uptrend | 6605 | 325 | 42% | -0.03 | -0.26 | 39% | -0.04 | -0.27 | 36% | -0.04 | -0.27 | 0.94 |
| high_vol_selloff | 1093 | 43 | 48% | +0.10 | -0.08 | 57% | +0.26 | +0.08 | 55% | +0.36 | +0.18 | 1.85 |
| narrow_uptrend | 618 | 21 | 35% | -0.11 | -0.39 | 31% | -0.17 | -0.45 | 28% | -0.17 | -0.46 | 0.77 |
| **all** | 10360 | 504 | 43% | +0.01 | -0.23 | 41% | +0.03 | -0.22 | 39% | +0.04 | -0.20 | 1.07 |

Portfolio replay (net of costs, slots shared with its run): 14 trades, win 29%, avg -0.45R, PF 0.39, P&L $-1,675 on $100k, avg hold 3.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 5044 | 150 | 42% | -0.00 | -0.21 | 43% | +0.07 | -0.13 | 40% | +0.10 | -0.10 | 1.17 |
| correction | 4717 | 252 | 45% | +0.04 | -0.22 | 45% | +0.14 | -0.11 | 43% | +0.15 | -0.10 | 1.27 |
| healthy_uptrend | 15452 | 366 | 43% | -0.02 | -0.23 | 40% | -0.00 | -0.21 | 37% | -0.02 | -0.23 | 0.97 |
| high_vol_selloff | 2989 | 122 | 42% | -0.02 | -0.25 | 38% | -0.04 | -0.26 | 35% | -0.05 | -0.28 | 0.92 |
| narrow_uptrend | 4001 | 97 | 44% | +0.02 | -0.19 | 40% | +0.03 | -0.18 | 37% | +0.04 | -0.18 | 1.06 |
| **all** | 32203 | 987 | 43% | -0.00 | -0.22 | 41% | +0.03 | -0.19 | 38% | +0.03 | -0.19 | 1.05 |

Portfolio replay (net of costs, slots shared with its run): 88 trades, win 50%, avg +0.18R, PF 1.48, P&L $3,871 on $100k, avg hold 3.6 bars.
