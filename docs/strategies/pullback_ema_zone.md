---
slug: pullback_ema_zone
name: EMA-zone pullback (low in the 20-50 EMA band after 2 respected tests)
originators: [Rayner Teo (as summarised by Financial Wisdom TV), lineage Dave Landry, Linda Raschke, TradeZella]
category: strategy
decision: implement
holding_period_days: [3, 60]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: 0.26        # proxy: EasySwing "Trend Pullback" detector (different rules), gross; trail exits give 25-40%
typical_payoff_ratio: 4.1     # derived from the same proxy: PF 1.45 x 0.74 / 0.26; not a test of this exact rule set
evidence_grade: B-
free_data_ok: true
status: not_built
---

# EMA-zone pullback

## One-line summary
In an established uptrend, buy when price dips into the band between the 20- and 50-day EMAs after the 20 EMA has
already held at least twice, on a turn back up; stop 2x ATR below entry, no target, exit on a close below the 50 EMA.

## Origin and lineage
- The oldest swing family: pullback to a rising MA in a trend (Raschke/Connors "Holy Grail" 1995, Landry 2000/2003).
- The "EMA zone" variant is Rayner Teo's (TradingwithRayner): use the 20 and 50 EMA, price must respect the zone at
  least twice, enter on the third pullback, 2x ATR stop, exit on a close beyond the 50 EMA (Financial Wisdom TV course
  review, 7 Dec 2024; secondary).
- Sibling in the engine: `pullback_holy_grail` (built, shadow) and `pullback_trend` (enabled). methods 7b #1 lists
  both variants as one family; log them as one family in `research/trials.py`.

## Exact rules (as taught; Rayner version via secondary summary)
| Step | Rule |
|---|---|
| Universe | Trending stocks; TradeZella adds price above the 200 EMA |
| Trend | 20 EMA above 50 EMA, both rising (implied by "trending charts") |
| Setup | Price pulls back into the 20-50 EMA zone; the zone has been respected at least twice before |
| Trigger | Enter on the third pullback into the zone (exact candle trigger not specified in the summary) |
| Entry order | Not specified; family convention is a buy above the reversal/touch bar high |
| Initial stop | 2x ATR at entry (worked example ~5.4%); a TradingView script modelled on his settings draws 1.5x ATR(20) |
| Target | None |
| Trail / exit | Exit when price closes beyond (below) the 50 EMA; "do not rush stops to breakeven" |
| Sizing | Risk no more than 1% of capital per trade |

## Why it should work
- Medium-term momentum plus 1-month reversal: buying a short dip inside a winner improves entry price vs a breakout
  (Jegadeesh 1990; Novy-Marx 2012; Dimensional/Medhat-Novy-Marx 2023 describe reversals as a timing overlay).
- Other side: short-term holders and mean-reversion sellers taking profits; trend buyers re-enter at the average.
- Grimes' work (secondary) finds MAs have no magic level; the edge is trend + shallow quiet dip + trigger, not the
  number 20 or 50.

## When it works and when it fails
- Works: steady trends with orderly 3-7 bar dips on lighter volume; 2026 crowd and EasySwing data favoured
  pullbacks over breakouts.
- Fails: choppy tapes with flat EMAs; first leg of a trend change (dip into the 50 on heavy volume); dips caused by
  earnings misses; late fourth/fifth tests in mature advances (Kell's "first pullback" view contradicts Rayner's
  "third pullback" rule: an open experiment).

## Parameters and sensitivity
| Knob | Proposed default | Range | Note |
|---|---|---|---|
| `fast_ema` / `slow_ema` | ema_20 / ema_50 | 20-21 / 50 | |
| `min_prior_tests` | 2 | 1-3 | Core rule of the variant |
| `test_lookback` | 60 bars | 40-120 | |
| `test_separation` | 5 bars and a new 20-bar high between tests | 3-10 | |
| `touch_pct` | 0.01 | 0-0.02 | low <= ema_20 * (1 + touch) |
| `stop_atr_mult` | 2.0 | 1.5-2.5 | |
| `exit_ma` | ema_50 (close below) | ema_50 / 2 closes < ema_20 | |
| `max_hold_days` | 60 | 30-90 | |
Traps: MA type/length shopping (5/10/20/21/50, EMA vs SMA) has no theory; fix one spec, log variants as one family.

## Evidence
- No independent test of the exact Rayner rules was found.
- EasySwing "Trend Pullback (EMA20/SMA50, RS >= 96)" panel (updated 7 Jul 2026, 5-year walk-forward, no costs):
  1,092 trades, win 26%, +0.3R, PF 1.45, average hold 3 days; parameters were tuned on the data (optimistic).
- QuantifiedStrategies SPY stochastic pullback (29 Jul 2026): 195 trades, 74% win, PF 2.3 (index, short holds; a
  cousin, not this rule).
- Academic: short-term reversal inside momentum (above); Brock-Lakonishok-LeBaron 1992 MA rules weaken after
  data-snooping correction (Sullivan-Timmermann-White 1999).
- Grade B- is for the family (catalog); the zone variant itself is untested.

## Common mistakes
1. Limit-buying the touch instead of waiting for a turn.
2. Buying dips that started with an earnings gap down.
3. Placing the stop just under the obvious MA (shakeout target).
4. Trading it when the 50 EMA is flat or falling.
5. Tight stops on gap-prone names: gap-through losses of 2-3R.

## Discretionary parts and how to make them mechanical
| Discretionary | Mechanical proxy |
|---|---|
| "Respected the zone" | count prior touch events: bar low <= ema_20*(1+touch) and close >= ema_50, separated by >= 5 bars with a new 20-bar high between them |
| "Trending chart" | `trend_state == 1` plus ema_20 > ema_50, both above their value 5 bars earlier |
| Reversal candle | close > prior bar high and close > ema_20 (family trigger) |
| Orderly dip | mean pullback volume / `avg_vol_20d` <= 1.0 (reuse `pullback_trend` logic) |

## Implementation spec for swing-engine
Proposed module `swing_engine/strategies/pullback_ema_zone.py` (not built; register `enabled: false,
shadow_only: true`, family `pullback`).
- New feature: `ema_50` (add span 50 to `EMA_SPANS` in `features/indicators.py` or to `features/patterns2.py`;
  `ema_20` already exists in patterns2). EMA: `ema[t] = a*close[t] + (1-a)*ema[t-1]`, `a = 2/(span+1)`.
- Setup on bar t (as-of): `trend_state == 1`; `ema_20[t] > ema_50[t]`; `ema_20[t] > ema_20[t-5]`,
  `ema_50[t] > ema_50[t-5]`; zone touch in the last 1-3 bars k: `low[k] <= ema_20[k] * 1.01` and
  `low[k] >= ema_50[k] * 0.99` (not a slice through the 50); `prior_tests >= 2` in the 60 bars before k.
- Trigger: `close[t] > high[t-1]` and `close[t] > ema_20[t]`; mean volume over the pullback bars /
  `avg_vol_20d` <= 1.0.
- Entry: signal at close t, next-open fill (backtester convention). Stop = `entry - 2.0 * atr_14[t]`.
- Target: None; `should_exit` = `close < ema_50` or `bars_held >= 60`. Set per-strategy `min_reward_risk: 0.0`
  (as `rsi2_meanrev` does) because there is no fixed target.
- Score: `rs_63d_rank` (prefer leaders) or `ret_63d`.
- Reuses: `trend_state`, `atr_14`, `avg_vol_20d`, `ema_20`, `rs_63d_rank`, `as_of_view`.
- Conflict: engine-wide `breakeven_after_r: 1.0` contradicts "do not rush stops to breakeven"; replay will apply it
  unless a per-strategy override exists (missing hook).
- Missing: `ema_50`, touch-count helper, per-strategy breakeven override, earnings-window exclusion.
max_hold_days: 60. Min reward:risk: n/a (trail); risk per trade 1%.

## What the router should know
- Same placement as the pullback family: full size in `healthy_uptrend`, 0.5 in `narrow_uptrend` with an RS gate
  (rank >= 0.90 or within 10% of the 52-week high), off in `choppy`, `correction`, `high_vol_selloff`.
- Overlaps heavily with `pullback_trend` and `pullback_holy_grail`; deduplicate by symbol.

## Signs of decay to monitor
- Rising share of trades exiting on the first `ema_50` close within 5 bars.
- Win rate below 20% with average winner < 3R over 50+ shadow signals.
- Touch counts drifting: most signals on 4th+ tests (late-cycle).

## Sources
- https://www.financialwisdomtv.com/post/make-your-money-work-for-you-trend-following-by-rayner-teo
- https://in.tradingview.com/script/srm3ovD0-Rayner-Teo-s-EMA-Setting
- https://www.tradezella.com/blog/swing-trading-strategies
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329
- https://easyswing.trading/performance
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/23-trend-pullback.md
- https://quantifiedstrategies.substack.com/p/a-simple-stochastic-pullback-strategy
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx
- Repo: `docs/methods/01-pullback-20-50-ma-uptrend.md`, `docs/methods.md` 7b #1, `swing_engine/strategies/pullback_trend.py`, `swing_engine/strategies/pullback_holy_grail.py`

## Empirical (replay)
_Pending: filled in from swing replay on real data._
