---
slug: ttm_squeeze
name: TTM Squeeze (Bollinger Bands inside Keltner Channel, momentum "fire")
originators: [John Carter (Trade the Markets / Simpler Trading), LazyBear (TradingView variant)]
category: volatility_breakout
decision: implement_disabled_for_comparison
holding_period_days: [3, 15]
timeframe: daily
direction: long            # Carter trades both sides; swing-engine strategies are long-only
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# TTM Squeeze

## One-line summary
When Bollinger Bands contract inside the Keltner Channel ("squeeze on") and then expand back out ("fired"), trade in
the direction of a smoothed momentum histogram; exit after two bars of fading momentum (moves "typically 8-10 bars").

## Origin and lineage
John Carter, *Mastering the Trade* (2005 onward). Built into thinkorswim as TTM_Squeeze; LazyBear's "Squeeze Momentum
Indicator" on TradingView is the most-used open variant. Descends from Bollinger's Squeeze (`bollinger_squeeze_breakout.md`)
and uses the Keltner channel (`keltner_channel_breakout.md`).

## Exact rules
- BB: SMA20(close) +/- 2.0 x stdev20.
- KC: 20-period average +/- 1.5 x ATR(20) (Carter). LazyBear: SMA20 basis, width 1.5 x SMA20(true range).
  StockCharts builds its TTM version on Keltner's original formula.
- Squeeze ON: upper BB < upper KC and lower BB > lower KC. OFF/fired: both bands back outside KC (LazyBear also has a
  "no squeeze" state when neither condition holds).
- Momentum: `val = linreg_20( close - ((HH20 + LL20)/2 + SMA20(close))/2 )`, i.e. the endpoint of a 20-bar
  least-squares line fitted to that delta. Carter's original reportedly used simple momentum instead of linreg.
- Trade: on the first fired bar after one or more squeeze-on bars, buy if momentum > 0 and rising (short if < 0 and
  falling). thinkorswim's strategy description instead allows entry while squeeze is on with rising positive momentum
  (cyan) and holds until two consecutive dark-blue (falling) bars.
- Exit: two consecutive bars of declining momentum (two darker histogram bars). LazyBear: exit on colour change.
- Stop: not specified by the indicator; practitioners use the recent swing low or the opposite KC.
- Sizing: not taught.

## Why it should work
Same mechanism as the Bollinger squeeze: volatility contraction precedes expansion (vol clustering). The momentum
histogram adds a direction guess from where the close sits relative to the 20-bar range midpoint and mean. The other
side is range traders still fading the edges of the compressed range.

## When it works and when it fails
- Works: trending leaders pausing in tight bases.
- Fails: direction is roughly a coin flip without context; in choppy tapes fires reverse; a squeeze on daily bars can
  last weeks, so "first fired bar" can be a late, extended entry.

## Parameters and sensitivity
BB SD 2.0, KC mult 1.0/1.5/2.0 (thinkorswim offers "squeeze tightness" variants), length 20, minimum squeeze bars
(1 vs 5+). Trap: optimising KC multiplier and min squeeze length jointly per symbol.

## Evidence
- No broker/platform performance data; no peer-reviewed test located.
- CXO Advisory (14 Jan 2010): exactly the BB(20,2)-inside-KC(20,1.5 x avg range) condition on SPY, 1993-2010; 86
  breakout events; breakout direction vs next 18-day trend correlation -0.11, R^2 0.01. No directional edge.
- Promoter claims (e.g. "75% success") are unaudited.

## Common mistakes
- Taking every fire regardless of trend; ignoring that the histogram is lagging (linreg of a 20-bar construct).
- Mixing KC definitions (EMA vs SMA basis, ATR vs average range) and comparing results across platforms.

## Discretionary parts and how to make them mechanical
- "Rising": `mom_t > mom_{t-1}`. "Two darker bars": `mom_t < mom_{t-1} and mom_{t-1} < mom_{t-2}` while `mom > 0`.
- Trend context: require `trend_state >= 1` as a variant.

## Implementation spec for swing-engine
- Features (new): `atr_20s` = SMA20(true range) (LazyBear/Carter-style, distinct from Wilder `atr_14`);
  `kc_upper_20 = sma_20 + 1.5*atr_20s`, `kc_lower_20 = sma_20 - 1.5*atr_20s`;
  `sqz_on = bb_upper_20 < kc_upper_20 and bb_lower_20 > kc_lower_20`;
  `sqz_mom_20 = linreg_endpoint_20(close - ((max(high,20)+min(low,20))/2 + sma_20)/2)`.
  Note: engine `bb_*_20` use population stdev; Pine `stdev` is also population, so they match.
- Setup/trigger at close t: `sqz_on_{t-1} and not sqz_on_t` and `sqz_on` held >= `MIN_SQZ_BARS` (param, 1; test 5);
  `sqz_mom_t > 0 and sqz_mom_t > sqz_mom_{t-1}`.
- Entry: next open (current backtester OK). Stop: `max(min(low, 5 bars) - 0.01, entry - 2*atr_14)`.
- Exit rule (`should_exit`): two consecutive declines in `sqz_mom` or `sqz_mom < 0`. `max_hold_days: 15`.
- Target: none -> `min_reward_risk: 0.0`.
- Reuses: sma_20, bb_upper_20, bb_lower_20, atr_14, trend_state. Missing: KC columns, linreg helper.

## What the router should know
Comparison only. If enabled, `healthy_uptrend` only. Many concurrent fires on the same day signal a market-wide vol
regime shift, not stock-specific setups; cap per day.

## Signs of decay to monitor
Win rate under ~45% with payoff < 1.3; average hold under 4 bars (fires failing immediately).

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/T-U/TTM-Squeeze
- https://www.tradingview.com/script/nqQ1DT5a-Squeeze-Momentum-Indicator-LazyBear/
- https://pastebin.com/raw/UCpcX8d7
- https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze
- https://www.cxoadvisory.com/volatility-effects/testing-a-complex-breakout-indicator/

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1551 | 30 | 51% | +0.07 | -0.09 | -0.34 | 45% | -0.10 | -0.26 | -0.60 | 43% | -0.09 | -0.25 | -0.93 | 0.88 |
| correction | 387 | 5 | 76% | +0.56 | +0.06 | -0.68 | 69% | +0.63 | +0.14 | -0.94 | 61% | +0.47 | -0.02 | -1.27 | 2.24 |
| healthy_uptrend | 5251 | 94 | 43% | -0.10 | -0.26 | -0.25 | 38% | -0.17 | -0.33 | -0.30 | 34% | -0.14 | -0.30 | -0.31 | 0.80 |
| high_vol_selloff | 592 | 24 | 47% | -0.02 | -0.19 | -0.10 | 42% | -0.08 | -0.25 | -0.21 | 30% | -0.18 | -0.35 | -0.25 | 0.75 |
| narrow_uptrend | 442 | 11 | 35% | -0.22 | -0.38 | -0.35 | 29% | -0.31 | -0.47 | -0.39 | 26% | -0.36 | -0.54 | -0.67 | 0.49 |
| **all** | 8223 | 164 | 46% | -0.04 | -0.21 | -0.28 | 41% | -0.12 | -0.30 | -0.38 | 36% | -0.11 | -0.29 | -0.49 | 0.84 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3876 | 55 | 50% | +0.03 | -0.13 | -0.21 | 48% | +0.04 | -0.11 | -0.26 | 43% | +0.11 | -0.04 | -0.27 | 1.20 |
| correction | 2964 | 28 | 50% | +0.03 | -0.13 | -0.24 | 52% | +0.17 | +0.01 | -0.25 | 46% | +0.22 | +0.05 | -0.25 | 1.44 |
| healthy_uptrend | 19388 | 304 | 48% | +0.01 | -0.15 | -0.18 | 44% | +0.01 | -0.15 | -0.20 | 37% | -0.01 | -0.16 | -0.25 | 0.99 |
| high_vol_selloff | 2183 | 42 | 48% | -0.03 | -0.22 | -0.19 | 43% | -0.07 | -0.26 | -0.22 | 38% | -0.05 | -0.24 | -0.19 | 0.91 |
| narrow_uptrend | 3903 | 47 | 52% | +0.09 | -0.06 | -0.14 | 48% | +0.08 | -0.08 | -0.19 | 41% | +0.11 | -0.05 | -0.19 | 1.19 |
| **all** | 32314 | 476 | 49% | +0.02 | -0.14 | -0.19 | 45% | +0.03 | -0.13 | -0.21 | 39% | +0.04 | -0.12 | -0.24 | 1.07 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
