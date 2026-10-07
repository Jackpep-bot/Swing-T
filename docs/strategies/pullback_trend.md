---
slug: pullback_trend
name: Pullback to a rising 20/50 MA in an uptrend
originators: ["Linda Raschke & Laurence Connors (Holy Grail, 1995)", "Dave Landry (2000, 2003)", "Rayner Teo", "Steve Burns", "Kristjan Kullamagi (MA-surfing exits)"]
category: strategy
decision: have
holding_period_days: [2, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: 0.26        # EasySwing Trend Pullback panel (MA-trail-style exits, gross); 0.5-0.75 is quoted for tight 2R / swing-high exits
typical_payoff_ratio: 4.1     # computed here from EasySwing PF 1.45 and 26% wins: 1.45 * 0.74 / 0.26; gross of costs
evidence_grade: B-
free_data_ok: true
status: enabled
---

# Pullback to a rising 20/50 MA in an uptrend (`pullback_trend`)

## One-line summary
In a stock already trending up (close > rising SMA50 > SMA200), wait for a short, quiet dip into the 20-day EMA/SMA,
buy when price turns back above the prior bar's high, stop under the dip low, and take 2R or the prior swing high.

## Origin and lineage
- The oldest and most widely taught swing setup; it is a family, not one rule set. Every teacher uses a different
  MA (5/10/20/21/50, EMA vs SMA), trigger and exit (docs/methods/01).
- Raschke & Connors, *Street Smarts* (1995): the Holy Grail (ADX(14) > 30, touch of the 20 EMA, buy stop over the
  touch-bar high). Separate card: `pullback_holy_grail`.
- Dave Landry (*Dave Landry on Swing Trading*, 2000; *10 Best Swing Trading Patterns*, 2003): trend qualifiers
  ("Proper Order" 10-SMA > 20-EMA > 30-EMA), pullback of at least 2 lower lows, buy over the prior bar high.
- Modern retail forms: Rayner Teo (20-50 EMA zone, 2x ATR stop, exit on a close beyond the 50 EMA), Steve Burns
  (10-day EMA pullbacks near 52-week highs, SPY 200-day gate, 1% risk; MoneyShow 2012), Oliver Kell (EMA
  Crossback), TradeZella (20 EMA, 2-close exit), EasySwing/sofus-nl (coded detector with an RS >= 96 gate).
- Academic cousin: short-term (1-month) reversal inside medium-term momentum (Jegadeesh 1990; Novy-Marx 2012;
  Medhat & Novy-Marx, Dimensional 2023).

## Exact rules
As taught (composite from docs/methods/01; each number has a named source there):
- **Universe/screen**: price >= $5, liquid; close > SMA50 > SMA200 with SMA50 rising; leader: RS rank >= 96
  (EasySwing) or within 5-10% of the 52-week high (Burns, EasySwing proximity variant); optional ADX(14) > 30.
- **Setup**: 2-7 bar dip (Landry: >= 2 lower lows) on volume below the 20-day average; the low tags the 20-day
  EMA/SMA (within ~1-2% or 1 ATR) or enters the 20-50 band; closes hold near or above it ("touch, not slice").
- **Trigger**: buy stop one tick above the touch/pivot bar high (Holy Grail, Landry); TradeZella allows the reversal
  candle close or a break of its high next day.
- **Entry order**: buy-stop at prior high + tick, good for the next session.
- **Initial stop**: below the touch bar / new swing low (Raschke, Landry); 2x ATR (Rayner); 1.5x ATR or below EMA20,
  whichever is tighter (EasySwing); below the reversal candle or 1.5% under the 20 EMA (TradeZella).
- **Targets**: prior swing high (Holy Grail; TradeZella first target); 50% at +2 ATR (EasySwing); Landry "2-for-1":
  half off at +1R and stop to breakeven (book rule, wording unverified online).
- **Trailing / time exits**: close beyond the 50 EMA (Rayner); 2 consecutive closes below the 20 EMA (TradeZella);
  2 closes below SMA50 (EasySwing); break of the 5/10-day EMA (Burns). Swing variants hold 2-10 sessions
  (EasySwing average 3 days); trail variants hold weeks.
- **Sizing**: 1% of equity per trade (Burns, Rayner); shares = equity x 1% / (entry - stop), capped by notional.

## Why it should work
- Mechanism: a leader in a persistent uptrend has a temporary liquidity-driven dip (profit-taking, sector rotation,
  index selling). Short-horizon reversal pays the buyer who supplies liquidity; medium-term momentum keeps the
  trend. The counterparty is short-term sellers and late shorts; the buyer pays a smaller premium than on a breakout.
- Grimes' work (secondary summary) finds MA touches themselves are random: the edge, if any, is trend + short quiet
  dip + reversal trigger, not the specific line.
- Dimensional (2023): reversals are strongest over a few weeks; the practical use is as an entry-timing overlay, and
  dips into real news (earnings) are repricings, not liquidity events.

## When it works and when it fails
- Works: stacked rising MAs, leaders near highs, first and second pullbacks after a base breakout, broad or narrow
  uptrend if restricted to leaders. 2025 was a dip-buyer's year at the index level (unverified flow figures).
- Fails: chop (flat 50-day, ADX < 20-25), the start of a trend change (the dip that "touches the 50" is the first
  leg of every top), dips on heavy volume or after an earnings gap, late 3rd-4th tests. In Oct 2026 only ~27% of US
  stocks were above their 50-day, so pullbacks to the 50 in the average stock keep failing (docs/methods/06).

## Parameters and sensitivity
| Knob | Code default | Sensible range | Notes |
|---|---|---|---|
| `pullback_ma` | `ema_21` | `ema_20`, `sma_20`, `ema_21`; zone 20-50 | Teachers disagree; no theory for one value |
| `touch_pct` | 0.01 | 0.01-0.02 or 1 ATR | wider = more, worse signals |
| `pullback_bars` | 4 | 2-7 | Landry >= 2 lower lows |
| `max_pullback_volume_ratio` | 1.0 | 0.8-1.0 | vs `avg_vol_20d` |
| `stop_atr_buffer` | 0.1 | 0-0.5 | larger buffer avoids MA stop runs |
| `target_mode` / `target_r` | r_multiple / 2.0 | 1.5-3R or swing high | win rate is set almost entirely by the exit |
| `swing_high_bars` | 20 | 10-40 | |
| `min_trend_state` | 1 | 1 | |
| `min_market_trend_state` | 0 | 0-1 | |
| `min_reward_risk` | 1.0 (settings risk floor 2.0) | | |
Overfitting traps: dozens of knobs (MA length/type, touch width, RSI 40-55, etc.) with no theory; log all variants
as one family in `research/trials.py`; deflated Sharpe gate.

## Evidence
- EasySwing.trading panel (updated 7 Jul 2026): Trend Pullback detector, ~2,000 US stocks, 5-year walk-forward,
  1,092 trades, 26% wins, +0.3R average, PF 1.45, 3-day average hold. **Gross: no fees or slippage**; parameters
  were tuned on the same data (sofus-nl spec says "Tuned"). Same panel: 52w-high proximity pullback PF 1.33.
- QuantifiedStrategies (29 Jul 2026): SPY stochastic pullback in an uptrend, 195 trades, 74% wins, +0.6%/trade,
  PF 2.3, CAGR 3.6%, 7% time in market (index, not single stocks; parameters paywalled).
- Academic: indirect only. Jegadeesh (1990) reversal; Novy-Marx (2012) recent month behaves like reversal; George &
  Hwang (2004) 52-week-high proximity predicts returns; Brock-Lakonishok-LeBaron (1992) MA rules beat nulls on the DJIA
  1897-1986, much weakened after data-snooping correction (Sullivan-Timmermann-White 1999).
- No independent cost-inclusive test of the Holy Grail or Rayner Teo rules on single stocks was found. TradeZella's
  "55-65% win rate" is unsupported.
- Decay: PF 1.45 / +0.3R with a 3-day hold shrinks materially after 10-20 bps per side; not yet measured in the
  engine's cost model.

## Common mistakes
1. Buying the touch with a limit instead of the turn (catches the dips that keep falling).
2. Trading laggards: no RS / near-high filter (the current code has none).
3. Buying a dip that started with an earnings gap down or a downgrade.
4. Fourth test of the 50-day late in an advance.
5. Stop exactly under the obvious MA (Landry's Trend Knockout runs it).
6. Ignoring gap risk: a 3% stop on a stock that gaps 7% overnight is a -2R+ loss.
7. Quoting win rates without the exit rule.

## Discretionary parts and how to make them mechanical
| Discretion | Mechanical proxy |
|---|---|
| "Leader" | `rs_63d_rank >= 0.96` or `dist_52w_high >= -0.10` (both exist via features/patterns2.py and cross_section) |
| "Orderly, quiet dip" | `max_pullback_volume_ratio <= 1.0`; no bar in the dip with `range_pct > 2 x atr_pct_14` and `close_pos < 0.3` |
| "First/second pullback" | count of prior touches of the MA since the last 52w-high breakout (missing feature) |
| "Not news-driven" | earnings within the dip window -> skip (needs point-in-time earnings dates); Claude enum `NEWS_DRIVEN/NO_NEWS` |
| "Not extended" (Kell) | entry <= ~3% above `ema_20` (methods.md 7a #5) |

## Implementation spec for swing-engine
What `swing_engine/strategies/pullback_trend.py` does today:
- Gate: `market_ok` (`market_trend_state >= 0`), `trend_state == 1`.
- Rolling helpers: `min_low_5` (lowest low of the 4 pullback bars plus the as-of bar), `prior_mean_volume_4`
  (mean volume of the 4 bars before as-of), `prior_max_high_20` (highest high of the 20 bars before as-of).
- Conditions: `close > prior_high` and `close > ma`; `pb_low <= ma * (1 + touch_pct)`;
  `pb_vol / avg_vol_20d <= max_pullback_volume_ratio`.
- Entry reference = as-of close; the backtester and autopilot fill at the next open.
- Stop = `pb_low - stop_atr_buffer * atr_14`.
- Target = `close + target_r * (close - stop)` (default 2R) or the 20-bar prior swing high if `target_mode=swing_high`
  and it is above entry.
- Score = reward_risk + max(ret_63d, 0).
- No `should_exit` and no `max_hold_days`: exits are stop, target, the backtester's 20-bar default time stop, plus
  the execution layer's breakeven at +1R and lowest-low-of-10-days trail from +2R (settings `execution`).

Differences from the originators (flag):
1. Trigger is a close above the prior bar high, filled next open, not an intrabar buy stop at prior high + tick:
   entry is later and the risk wider.
2. MA is `ema_21`, not the taught 20 EMA/SMA (`ema_20` now exists in patterns2).
3. No leader/RS gate, no ADX, no earnings exclusion, no lower-lows shape check.
4. No MA trail exit (Rayner/TradeZella/Burns); no scale-out.

Proposed spec (methods.md 7a #5):
- `should_exit(row, bars_held)`: True if `close < ema_50` (missing feature; or `sma_50`) or two consecutive closes
  `< ema_20` (needs prior-bar `close` and `ema_20`), or `bars_held >= max_hold_days`.
- `max_hold_days`: 10 for the 2R/swing-high variant; 40 for a trail-only variant (`target=None`, `min_reward_risk: 0`).
- Leader gate: `rs_63d_rank >= 0.96 or dist_52w_high >= -0.10` (copy `leader_ok` from `pullback_holy_grail`).
- Not-extended: `close / ema_20 - 1 <= 0.03`.
- Earnings: skip if an earnings date falls inside the pullback window or the next 5 sessions.
- Min reward:risk: 2.0 portfolio floor (settings `risk.min_reward_risk`); local floor 1.0.
- Reuses: `trend_state`, `atr_14`, `avg_vol_20d`, `ret_63d`, `ema_21`, `rs_63d_rank`, `dist_52w_high`, `ema_20`.
- Missing: `ema_50`, prior-touch count, point-in-time earnings dates, a buy-stop entry mode (next-bar stop at prior
  high), partial-exit hook.

## What the router should know
- Settings: allowed at 1.0 in `healthy_uptrend`, 0.5 in `narrow_uptrend`; not allowed in choppy, correction,
  high_vol_selloff.
- In narrow tapes it is only defensible with the leader gate, which the code lacks; `pullback_holy_grail` has it.
- Correlated with `pullback_holy_grail` and `sr_bounce` (same names, same days); count them as one family for exposure.

## Signs of decay to monitor
- Rolling 50-trade win rate below ~40% with the 2R exit (TradeZella's chop diagnostic is below 50%).
- Share of exits that are `STOP_GAP` rising (news-driven dips).
- Median MFE before stop falling below 0.5R.
- Signal count spiking while breadth falls (dips in non-leaders).
- Net expectancy after costs <= 0 over 100 trades.

## Sources
- docs/methods/01-pullback-20-50-ma-uptrend.md; docs/methods.md 1a #3, 6.1, 7a #5
- https://investinglive.com/Education/!/how-to-trade-by-holy-grail-strategy-20210329
- https://tradingsetupsreview.com/the-holy-grail-trading-setup
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry
- https://moneyshow.com/articles/dailyguru-26029
- https://www.financialwisdomtv.com/post/make-your-money-work-for-you-trend-following-by-rayner-teo
- https://www.tradezella.com/blog/swing-trading-strategies
- https://easyswing.trading/performance
- https://raw.githubusercontent.com/sofus-nl/swing-trading-strategies/main/strategies/23-trend-pullback.md
- https://quantifiedstrategies.substack.com/p/a-simple-stochastic-pullback-strategy
- https://www.dimensional.com/us-en/insights/q-and-a-on-short-run-reversals-with-mamdouh-medhat-and-robert-novy-marx
- https://ideas.repec.org/a/bla/jfinan/v47y1992i5p1731-64.html
- https://elitetrader.com/et/threads/moving-averages-are-random.299801/post-4280395

## Empirical (replay)
_Pending: filled in from swing replay on real data._
