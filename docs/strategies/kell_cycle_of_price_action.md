---
slug: kell_cycle_of_price_action
name: "Kell Cycle of Price Action (Wedge Pop, EMA Crossback, Base n' Break, Wedge Drop; QQQ 20 EMA gate)"
originators: ["Oliver Kell (2020 US Investing Championship stock division winner)", "TraderLion / Richard Moglen (co-produced write-ups)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [10, 60]   # Kell: 2-12 weeks
timeframe: daily (weekly context, 65-minute execution)
direction: long   # shorts exist but are out of scope
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Kell Cycle of Price Action

## One-line summary
Trade growth leaders through a repeating cycle around the daily 10/20 EMAs: buy the first reclaim after a capitulation
(Wedge Pop), the first pullback that holds (EMA Crossback) and tight 1-3 week bases (Base n' Break); trail the EMA, sell
extensions, exit on the Wedge Drop; gate exposure on QQQ vs its 20 EMA. Full research: docs/methods/12.

## Origin and lineage
Oliver Kell won the 2020 USIC stock division (< $1M) at +941.1%. Draws on O'Neil (selection), Livermore, Darvas,
Wyckoff (cycle thinking). Phases: Reversal Extension -> Wedge Pop -> EMA Crossback -> Base n' Break (repeat) ->
Exhaustion Extension -> Wedge Drop -> down-cycle.

## Exact rules (as taught; thresholds only where Kell published them)
- Universe: liquid growth leaders, big EPS/sales growth; scans: IPOs, liquids, Bull Snorts, 52-week highs. Deepvue's
  "Kell screens" (price > $20, avg vol >= 500K, cap $2-25B, growth >= 30%) are secondary and unverified as Kell's.
- Market gate: QQQ below its 20 EMA = correction mode: 1-2 names, exposure capped at 30%. Good tape: 6-7 core
  positions (he uses margin; engine does not).
- Wedge Pop: after a downside extension, price tightens under the EMAs and then closes back through both 10 and 20 EMA
  on above-average volume.
- EMA Crossback: first pullback to the rising 10/20 EMA after the pop that holds.
- Base n' Break: 1-3 weeks sideways riding the EMAs, breakout on volume.
- Not extended: Kell's own journal found nearly all losers were bought 3-4%+ above the MAs.
- Entry: intraday (65-minute triggers at daily support). Pieces: 15% position with a 1-2% stop (15-30 bps of account),
  add 15% on follow-through and raise the stop to the follow-through day's low. Never average down.
- Stop: breakout = pivot or day's low; support buy = the low at the 10/20 EMA being bought.
- Exits: no preset targets; trail the 10 or 20 EMA (whichever the stock respects); sell into extensions above the 10 EMA
  (index examples only: QQQ 4-5% above daily 10 EMA; NVDA 12-15% above the 10-week); full exit on the Wedge Drop.

## Why it should work
Trend/MA-distance premium (Avramov-Kaplanski-Subrahmanyam 2021: 21/200-day MA ratio, ~9%/yr alpha), 52-week-high
momentum (George-Hwang 2004), and short-term reversal at extremes (buy pullbacks, sell extensions). Counterparty:
capitulating sellers at the Reversal Extension and late chasers at the Exhaustion Extension.

## When it works and when it fails
- Works: V-shaped market turns and strong growth up-cycles (2020; Apr 2025 and May 2026 thrusts).
- Fails: chop around the EMAs (Kell's TSLA example: 4 trades, 2 scratches, 2 losses before one held); false index
  wedge pops in bear rallies (his 24 Mar 2025 buy signal preceded the April 2025 tariff crash).

## Parameters and sensitivity
| Knob | v1 value | Range | Source |
|---|---|---|---|
| ema_fast / ema_slow | 10 / 20 | 9-10 / 20-21 | Kell |
| downside/upside extension | 1.5 x atr_14 from ema_10 | 1.0-2.0 ATR or 5-8% | QuantVue (unverified as Kell) |
| pop window after extension | 15 bars | 10-20 | engine choice |
| max entry extension | ext_10 <= 3% | 2-4% | Kell journal |
| base length | 5-15 bars | 5-15 | TraderLion "1-3 weeks" |
| min rvol on pop/break | 1.5 | 1.2-2.0 | engine choice |
| trail | close < ema_20 | ema_10 / ema_20 | Kell |
Trap: phase labels depend on lookbacks; small changes reshuffle signals. Log every variant in research/trials.py.

## Evidence
- One contest year (+941.1%, 2020, margin, single account). Unaudited prior-year claims (~70-90%/yr).
- No independent test of the cycle or of any phase. Proxy: a plain 20-EMA timing rule on SPY returned 3.06% CAGR vs
  7.87% buy-and-hold (QuantifiedStrategies snippet): the EMA reclaim alone is not an edge.
- Grade D.

## Common mistakes
Buying extended breakout closes; copying 35% positions and margin; holding through earnings; treating every EMA reclaim
as a Wedge Pop without the prior downside extension.

## Discretionary parts and how to make them mechanical
- "Which EMA the stock respects": choose the EMA with fewer closes below it over the last 20 bars.
- "Tight": `bb_width_20` in the bottom 25% of its 120-bar range, or `vcp_contraction` low.
- Growth/story quality, NASI breadth colour, trendlines, 65-minute execution: leave to Claude review enums / human.

## Implementation spec for swing-engine
- Features (missing unless noted): `ema_10`, `ema_20` (patterns2 has `ema_20`; indicators has ema_9/ema_21),
  `ext_10 = close/ema_10 - 1`, `ext_10_atr = (close - ema_10)/atr_14`, `down_ext = high < ema_10 - 1.5*atr_14`,
  `bars_since_down_ext`, `wedge_pop = bars_since_down_ext <= 15 and close > max(ema_10, ema_20) and
  close[t-1] <= max(ema_10, ema_20)[t-1] and rvol_day >= 1.5`, weekly `ema_10w`, `ext_10w`, and `kell_phase` enum.
- Setups (each a separate variant): wedge_pop; crossback (first touch of ema_10/20 since the pop, close > prior high,
  ext_10 <= 0.03 — essentially pullback_trend with ema_10/20 and a pop prerequisite); base_break (close > max(high,
  5-15 prior bars), all base closes >= ema_20, rvol_day >= 1.5, ext_10 <= 0.03).
- Entry: next open (daily proxy for 65-minute trigger; expect worse R). Stop: wedge_pop/base_break = signal-day low;
  crossback = min(low, ema_20) - 0.1 x atr_14; skip if stop distance > 3%.
- Exit: `close < ema_20` (default) or wedge_drop (first close below both EMAs after `low > ema_10 + 1.5*atr_14`);
  partial sale at ext_10 >= 0.10 needs a scale-out hook. `min_reward_risk: 0.0`. max_hold_days: 60.
- Market gate: QQQ close > QQQ ema_20 (needs QQQ as a second market series; today only SPY `market_trend_state`).
- Sizing: risk_per_trade 0.25-0.5% matches his 15-30 bps per piece; pyramiding needs an add-on hook.
- Usable now without a new module: the not-extended filter (`close/ema_21 - 1 <= 0.03`) on pullback_trend, and a
  QQQ-20-EMA overlay in the playbook.

## What the router should know
healthy_uptrend only for the full system; in narrow_uptrend only crossback with half size; nothing when QQQ < its 20 EMA.
Overlaps pullback_trend (crossback) and breakout_52w / sr_breakout (base_break).

## Signs of decay to monitor
Cluster of small EMA-whipsaw losses (> 4 consecutive stop-outs), share of entries > 3% extended, false index pops.

## Sources
- docs/methods/12-kell-cycle-of-price-action.md (full source list)
- https://stockbsessed.substack.com/p/oliver-kell-interview-the-mind-and
- https://weeklieswatch.substack.com/p/holding-weekly-moving-averages
- https://traderlion.com/technical-analysis/chart-patterns/cycle-of-price-action-by-oliver-kell/
- https://www.businesswire.com/news/home/20210125005140/en/U.S.-Investing-Championship-2020-Final-Standings
- https://www.tradingview.com/script/GOkJ7o5J-Wedge-Pop-Drop-QuantVue
- https://www.quantifiedstrategies.com/20-ema-trading-strategy/
- https://ideas.repec.org/a/wly/revfec/v39y2021i2p127-145.html

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 14 | 1 | 54% | +0.45 | +0.32 | 38% | +0.05 | -0.08 | 31% | +0.40 | +0.27 | 1.72 |
| correction | 1 | 0 | 100% | +1.20 | +1.12 | 100% | +2.33 | +2.25 | 100% | +2.48 | +2.40 | inf |
| healthy_uptrend | 45 | 3 | 38% | +0.84 | +0.65 | 29% | -0.11 | -0.30 | 17% | -0.65 | -0.84 | 0.41 |
| high_vol_selloff | 6 | 0 | 50% | +0.69 | +0.58 | 50% | +0.71 | +0.59 | 17% | -0.74 | -0.85 | 0.43 |
| narrow_uptrend | 5 | 0 | 40% | -0.31 | -0.50 | 40% | -0.45 | -0.64 | 40% | -0.61 | -0.81 | 0.58 |
| **all** | 71 | 4 | 43% | +0.67 | +0.50 | 34% | +0.00 | -0.17 | 22% | -0.41 | -0.58 | 0.60 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 56 | 8 | 44% | +0.02 | -0.16 | 44% | +0.25 | +0.06 | 38% | +1.01 | +0.82 | 2.03 |
| correction | 16 | 1 | 40% | +0.85 | +0.73 | 33% | +1.41 | +1.29 | 27% | +1.04 | +0.92 | 2.29 |
| healthy_uptrend | 203 | 12 | 34% | -0.05 | -0.23 | 25% | -0.29 | -0.47 | 22% | -0.16 | -0.33 | 0.85 |
| high_vol_selloff | 64 | 5 | 27% | -0.46 | -0.59 | 24% | -0.69 | -0.83 | 19% | -0.63 | -0.76 | 0.52 |
| narrow_uptrend | 56 | 9 | 28% | -0.34 | -0.49 | 21% | -0.29 | -0.44 | 15% | -0.47 | -0.63 | 0.50 |
| **all** | 395 | 35 | 33% | -0.11 | -0.28 | 27% | -0.21 | -0.38 | 23% | -0.07 | -0.24 | 0.93 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
