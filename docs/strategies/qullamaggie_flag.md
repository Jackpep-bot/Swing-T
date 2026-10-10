---
slug: qullamaggie_flag
name: Qullamaggie momentum flag breakout
originators: [Kristjan Kullamagi (Qullamaggie)]
category: strategy
decision: have
holding_period_days: [3, 60]
timeframe: daily (taught entry is intraday opening-range high)
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [narrow_uptrend, choppy, correction, high_vol_selloff]
typical_win_rate: 0.27        # EasySwing mechanical panel, 16,943 trades, gross; self-reported 0.25-0.35
typical_payoff_ratio: 3.0     # derived: PF 1.10 x (1-0.27)/0.27 ~ 2.97 (EasySwing gross); not published directly
evidence_grade: C-
free_data_ok: true
status: shadow_only
---

# Qullamaggie flag breakout

## One-line summary
Buy a top-1-2% momentum leader (+30-100% in 1-3 months, ADR >= 5%) the day it breaks out of a 2-week-to-2-month
tightening flag that rides its rising 10/20-day MAs; stop at the low of the entry day (never wider than 1 ADR);
sell 1/3-1/2 after 3-5 days and trail the rest to the first close below the 10- or 20-day MA.

## Origin and lineage
- O'Neil's high tight flag (Bulkowski formalised it: >= 90% rise in <= 2 months then a shallow pause), Minervini and
  Zanger continuation breakouts, Stockbee momentum-burst scans.
- Kullamagi (Sweden) streamed it from 2019 and published "My 3 timeless setups" (Jan 2021) and a FAQ; he calls the
  flag breakout the setup most of his money came from (stream notes, Oct 2019).
- Sister setups: episodic pivot (`docs/strategies/episodic_pivot.md`), parabolic short (not in this long-only engine).
- Full write-up: `docs/methods/05-qullamaggie-breakout.md`; summary `docs/methods.md` 6.5, 7b #4.

## Exact rules (as taught)
| Step | Rule | Source tag |
|---|---|---|
| Universe | Top 1-2% performers over 1, 3 and 6 months (interview: 1/3/6/12/18 m); liquid; trade no more than 1% of a stock's daily volume | primary site; CWT 212 notes |
| Prior move | +30% to +100%+ within the past 1-3 months | primary |
| ADR% | `100 * (mean(H/L over 20 bars) - 1)`; avoid < 2%; community scans use > 5% | primary formula; secondary threshold |
| Setup | Orderly flag 2 weeks to 2 months, higher lows, tightening range, volume drying up, price "surfing" rising 10/20-day MAs | primary + stream notes |
| Trigger | Break of the flag high | primary |
| Entry order | Buy stop at the opening-range high of the 1-, 5- or 60-minute candle; buy in one go; never buy a stock already up more than its ATR/ADR on the day | primary; streams 1-5, 95 |
| Initial stop | Low of the entry day, never wider than 1 ADR; market stops only | primary |
| Targets | None; bull-market winners run "10-20x+ initial risk" | primary |
| Partial | Sell 1/3-1/2 after 3-5 days, move stop to breakeven (interview: 20-25%) | primary / secondary |
| Trail | First daily close below the 10-day (fast names) or 20-day MA (slower names) | primary |
| Sizing | Risk 0.25-1% per trade (FAQ: 0.3-0.5%); positions 10-20% (FAQ 5-25%); never > 30% of the account overnight in one stock | primary |
| Market | Qualitative: breakouts fail in corrections; rebuild exposure over weeks | stream notes |

## Why it should work
- Mechanism: momentum continuation (Jegadeesh-Titman) and 52-week-high anchoring (George-Hwang 2004): investors
  under-react to the news behind a leader's move; a tight flag is supply drying up after early holders take profits.
- Other side: profit-takers and anchored sellers in the flag, short-term mean-reversion traders fading the breakout,
  and institutions still accumulating. The payoff is asymmetric: tight LOD stop vs MA-trailed multi-week winners.

## When it works and when it fails
- Works: post-correction, theme-driven bull phases with broad participation (clean flags clustered Jul-Oct 2025 per a
  Financial Wisdom TV survey, survivorship-conditioned).
- Fails: corrections and high-vol tapes (EasySwing detector Sharpe -3.59 in 2007-2010); momentum crashes after
  market declines (Daniel-Moskowitz 2016); narrow markets where breakouts get sold (2026 "famine" since Mar 2026,
  anecdotal); second flags and late-cycle themes.

## Parameters and sensitivity
| Knob | Taught / code default | Sensible range | Notes |
|---|---|---|---|
| `rs_rank_min` | 0.98 | 0.95-0.99 | Below 0.95 it becomes a generic breakout |
| `prior_move_min` | 0.30 | 0.25-0.50 | |
| `pole_max_bars` | 42 | 21-63 | methods 7b says 63 bars; code uses 42 |
| `adr_min` | 0.05 | 0.035-0.06 | Higher = more small caps, more slippage |
| `flag_min_bars`/`flag_max_bars` | 10/40 | 5-15 / 30-45 | Bulkowski: 10-29-day flags did best |
| `flag_depth_max` | 0.25 | 0.15-0.35 | Bulkowski: 10-34% retrace best |
| `breakout_rvol_min` | 1.5 | 1.2-2.0 | |
| `max_extension_adr` | 1.0 | 0.5-1.0 | |
| `trail_ma` | sma_20 | sma_10 / sma_20 | Doc lets the trader choose per name: a discretion trap |
| `max_hold_days` | 60 | 40-90 | |
Overfitting traps: ten-plus knobs and few true winners per year; log every variant as one family in
`research/trials.py` and judge with deflated Sharpe. Never tune the partial fraction or the trail MA per regime.

## Evidence
- Self-reported (unaudited): win rate 25% (2019) / ~35% (2020); CAGR 268% 2013-2019; largest drawdown 50% (2014).
- Stonks Capital "Modeling Kullamagi part 2" (Feb 2025): end-2007 to 2025, 2,382 trades, CAGR 19%, max DD -21%,
  SPY > 140-day EMA gate; costs and win rate not disclosed. Stop at 1 ATR "didn't work"; they used wider.
- EasySwing panel (updated 7 Jul 2026, ~2,000 US stocks, 5-year walk-forward, no fees/slippage): 16,943 trades, win
  27%, avg +0.1R, PF 1.10, average hold 7 days. Same panel: trend pullback PF 1.45, cup and handle PF 1.57.
- EasySwing detector write-up (May 2026, different rules): Sharpe -3.59 in 2007-2010.
- Bulkowski high-tight-flag statistics (bull market, 1,028 trades): break-even failure 15%, average rise 39%.
- Post-publication decay: the method was popularised 2019-2021; no before/after study exists. The thin gross PF
  (1.10) suggests the mechanical edge is near zero after 10-20 bps/side costs.

## Common mistakes
1. Buying more than 1 ADR above the pivot or late after a big gap (stop gets wide).
2. Trading it in corrections; ignoring the market gate.
3. Reading top-100-winner case studies (20:1 R:R) as expectancy.
4. Taking second and third flags, or flags in stale themes.
5. Holding through earnings (method says check and avoid).
6. Oversizing high-ADR small caps (gaps and halts blow through LOD stops).

## Discretionary parts and how to make them mechanical
| Discretionary | Mechanical proxy |
|---|---|
| "Clean, linear" leader | `rs_63d_rank >= 0.98` plus pole/flag geometry; Claude review enum for theme quality |
| Tightening flag | second-half low >= first-half low (code); could add range contraction (`vcp_contraction`, `bb_width_20`) and volume dry-up (mean flag volume / `avg_vol_50d_prev` < 1) |
| ORH entry | Not reproducible on daily bars; daily version = close of breakout bar, filled next open |
| 10 vs 20-day trail | Fix one per version (code: sma_20) |
| Partial at day 3-5 | Needs a scale-out hook (missing) |
| Market feel | `min_market_trend_state = 1` + router regime `healthy_uptrend` only |

## Implementation spec for swing-engine
Module: `swing_engine/strategies/qullamaggie_flag.py` (built; `enabled: false, shadow_only: true`).
What the code actually does (as of 2026-10-07):
- Features reused: `rs_63d_rank` (same-session percentile of 63-bar return, `features/patterns2.py`; replay re-ranks
  inside the universe), `adr_pct_20 = mean(high/low, 20) - 1`, `rvol_day = volume / avg_vol_20d.shift(1)`,
  `sma_10`, `sma_20`, `trend_state`.
- Screen on the as-of bar t: `rs_63d_rank >= 0.98`, `adr_pct_20 >= 0.05`, `rvol_day >= 1.5`, `close > sma_20`,
  `sma_10 >= sma_20`, `trend_state >= 0`, market `market_trend_state >= 1`.
- Flag = `patterns2.flag(high, low, end=t-1, max_bars=40)`: top = highest high of the last 40 bars before t;
  pivot = that high; length = bars from top to t-1 (must be 10-40); depth = (pivot - min low)/pivot <= 0.25;
  higher_lows = min low of second half >= min low of first half.
- Trigger: `pivot < close_t <= pivot + 1.0 * adr_pct_20 * close_t`.
- Pole: `pivot / min(low over the 42 bars before the flag top) - 1 >= 0.30`.
- MAs rising: `sma_10[t] > sma_10[t-5]` and `sma_20[t] > sma_20[t-5]`.
- Entry = close_t (signal); backtest/replay fill at next open with slippage. Stop = `max(low_t, close_t * (1 - adr))`.
  Target = entry + 10R (reference only). `min_reward_risk` 2.0 always passes.
- Exit: `should_exit` on the first close < `sma_20` or `bars_held >= 60`. Score = rs rank + pole gain.
- Replay/autopilot also apply `execution.breakeven_after_r: 1.0` and `trail_after_r: 2.0` (10-day lowest low) on
  top of the strategy rule, and live positions are flattened 1 session before earnings (`earnings_exit_days: 1`);
  replay does not model the earnings exit.
Differences from the originator:
1. No ORH intraday entry; next-open fill can gap above the 1-ADR extension cap and widen the real stop.
2. RS uses only the 63-day return, not 1/3/6-month tops.
3. No partial sale at day 3-5 (no scale-out hook); the engine's breakeven-at-1R is a substitute.
4. No volume dry-up or "near the 10/20 MA" proximity check in the flag; higher-lows test is coarse.
5. Pole window 42 bars (methods 7b says 63).
6. No earnings-date avoidance at entry.
Missing: scale-out hook (methods 7a #4), intraday bars for ORH, breadth gate (`dcr_10d >= 2`, methods 7a #1),
optional `higher_lows_n`, volume dry-up feature.
max_hold_days: 60. Minimum reward:risk: not meaningful (trail exit); keep `min_reward_risk` at 2.0 with the 10R
reference target or set 0.0 like `rsi2_meanrev`.

## What the router should know
- Allowed only in `healthy_uptrend` (multiplier 1.0) per `config/settings.yaml`; correctly excluded from
  `narrow_uptrend`, `choppy`, `correction`, `high_vol_selloff`.
- Signals cluster in themes; respect `max_sector_pct: 30`.
- Low hit rate: expect strings of 8-10 losers; do not shut it off on a short losing streak inside a healthy regime.
- High-ADR names: use the 20 bps/side slippage tier.

## Signs of decay to monitor
- Shadow-ledger win rate < 20% or average R < 0 over 50+ signals in `healthy_uptrend`.
- Share of signals stopped on day 1-2 (gap-and-fail) rising above ~50%.
- Next-open fill above `pivot + 1 ADR` in more than a third of signals (extension creep).
- Largest-winner R shrinking (no trades > 5R in a year of healthy regime).

## Sources
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://qullamaggie.com/faq/
- https://tradingresourcehub.substack.com/i/132995655/introduction
- https://retailtradersrepository.substack.com/p/kristjan-kullamagi-qullamaggie-stream
- https://retailtradersrepository.substack.com/p/qullamaggie-stream-91-95-review
- https://stonkscapital.substack.com/p/modeling-kullamagi-part-2-momentum
- https://easyswing.trading/performance
- https://easyswing.trading/blog/qullamaggie-breakout-continuation-setup/
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://thepatternsite.com/htf.html
- https://thepatternsite.com/HTFStudy.html
- https://www.nber.org/papers/w20439
- Repo: `docs/methods/05-qullamaggie-breakout.md`, `docs/methods.md` (1a #11, 6.5, 7b #4), `swing_engine/strategies/qullamaggie_flag.py`, `swing_engine/features/patterns2.py`

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 3 | 0 | 33% | -0.52 | -0.66 | 0% | -0.84 | -0.98 | 0% | -0.84 | -0.98 | 0.00 |
| **all** | 3 | 0 | 33% | -0.52 | -0.66 | 0% | -0.84 | -0.98 | 0% | -0.84 | -0.98 | 0.00 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| healthy_uptrend | 26 | 0 | 46% | +0.18 | -0.00 | 35% | +0.07 | -0.11 | 19% | -0.27 | -0.45 | 0.68 |
| **all** | 26 | 0 | 46% | +0.18 | -0.00 | 35% | +0.07 | -0.11 | 19% | -0.27 | -0.45 | 0.68 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
