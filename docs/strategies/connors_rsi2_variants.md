---
slug: connors_rsi2_variants
name: Connors RSI(2) family variants (Double 7s, Cumulative RSI, R3, ConnorsRSI Pullback, Alpha Formula)
originators: [Larry Connors, Cesar Alvarez, Chris Cain (Alpha Formula)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 10]   # Alpha Formula is weekly (weeks)
timeframe: daily (Alpha Formula weekly)
direction: long (shorts mirror; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: 0.63-0.80   # 80.4% Double 7s SPY in-sample; 63% Alpha Formula replication; 71-75% OOS classic RSI(2)
typical_payoff_ratio: 0.5-0.6 # OOS classic RSI(2): avg win/avg loss 1.22/2.10 SPX, 1.58/3.11 NDX
evidence_grade: C
free_data_ok: true
status: not_built   # the classic rule is built and enabled as rsi2_meanrev; these variants are not
---

# Connors RSI(2) family variants

## One-line summary
These are alternative oversold triggers to the classic `rsi2_meanrev` rule. Each needs an uptrend filter, buys the close,
uses no stop, and exits on the first bounce. Use them as comparison arms against the built strategy, not as new edges.

## Origin and lineage
*Short Term Trading Strategies That Work* (Connors & Alvarez, 2008) gave Double 7s and Cumulative RSI. *High Probability ETF
Trading* (2009) gave R3. ConnorsRSI (about 2012) and the ConnorsRSI Pullback system for stocks were published in Active Trader (Mar 2013).
*The Alpha Formula* (Connors & Cain, 2019) has the weekly RSI(2) rotation. The full lineage and sources are in
`docs/methods/11-rsi2-connors-mean-reversion.md`.

## Exact rules (from methods/11)
| Variant | Setup / trigger | Entry | Exit | Source tag |
|---|---|---|---|---|
| Double 7s | close > SMA(200); close = lowest close of last 7 bars | close | close = highest close of last 7 | primary (book ch. 10) |
| Cumulative RSI | close > SMA(200); RSI(2)[t] + RSI(2)[t-1] < 35 | close | RSI(2) > 65 | secondary |
| R3 | close > SMA(200); RSI(2) falls 3 days in a row, first day < 60, today < 10 | close | RSI(2) > 70 | secondary |
| ConnorsRSI Pullback (stocks) | price > $5, 21-d avg vol >= 250k, ADX(10) > 30; low >= W% below prior close (W 2/4/6/8, coded 4); close in bottom X% of range (X 10/25, coded 25); ConnorsRSI(3,2,100) < Y (5-15, coded 15) | next day, limit Z% below the close (Z 4-10, coded 4) | ConnorsRSI > 50-80 (coded 50) | secondary (Wealth-Lab) |
| Alpha Formula (weekly) | SPY 126-d return > 0; top-500 by 200-d dollar volume; weekly RSI(2) < 20; take 10 lowest 100-d HV | end of week, equal weight | weekly RSI(2) > 80; 10% catastrophic stop | secondary (QuantConnect) |

ConnorsRSI = (RSI(3) of close + RSI(2) of the up/down streak length + PercentRank(100) of the 1-day return) / 3.
There is no price stop in any variant except the Alpha Formula 10%. Connors' "stops hurt" claim is about average return, not tail risk.

## Why it should work
Short-term reversal is liquidity provision (Nagel 2012). Pullbacks in low-turnover names revert, while heavy-turnover (news)
moves can continue (Medhat & Schmeling 2022).

## When it works and when it fails
Uptrending, low-to-normal-vol tapes are fine. It fails on trend breaks, where the no-stop hold carries the whole drawdown (the NDX RSI(2) version lost
12.2% on two trades in 2020, Backtrex). In single stocks, earnings gaps produce oversold readings that are information, not noise.

## Parameters and sensitivity
The threshold menus (Double 5s-10s, the W/X/Y/Z grids) invite overfitting. Pick the coded defaults above once, register each
variant as its own trial, and walk forward.

## Evidence
- Double 7s, SPY 1993-2007: 153 trades, average +0.85%, 80.4% winners. QQQ: 68 trades, +0.93%, 79.4% (in-sample, primary).
- Alpha Formula replication, 1998 onward: CAGR 12.5%, max drawdown 22.8%, 63% win (QuantConnect forum, secondary).
- Out-of-sample for the classic rule (Backtrex, Oct 2016 - Oct 2026): SPX 71.2% win, PF 1.43, about +0.27%/trade; NDX 75.4%, PF 1.55,
  about +0.43%/trade. Cumulative RSI, R3 and ConnorsRSI Pullback: no independent statistics were verified (the Quantified Strategies R3 and StrategyQuant
  Double 7s pages were not read).
- CXO (2009): the book's tests make no data-mining correction and have no out-of-sample or cost analysis.

## Common mistakes
Different RSI warm-ups move readings across thresholds. Mixing ConnorsRSI with RSI(2). Using current index membership
(survivorship). Next-open fills that give away the overnight bounce.

## Discretionary parts and how to make them mechanical
None in the rules. News triage on single stocks can be done by the agent as an enum (`NEWS_DRIVEN` / `NO_NEWS`) excluding signals; it emits no prices.

## Implementation spec for swing-engine
- What the code does today: `rsi2_meanrev` enters when `close > sma_200 and rsi_2 < 10` and fills at the **next open**. It exits on `close > sma_10`,
  `rsi_2 > 70`, or 5 bars. It adds a `2*atr_14` stop. Its reference target is `sma_10`. Connors' classic rule differs: an sma_5 exit, no stop, no time stop, and a close fill.
- Variants as a `variant` param or separate registered modules:
  - Double 7s: `min_close_7 = rolling_min(close, 7)`, `max_close_7`; entry `close <= min_close_7`, exit `close >= max_close_7`.
    Use the `RollingSpec` helper in `_base.py` (`RollingSpec("close","min",7)`).
  - Cumulative RSI: `rsi_2 + rsi_2.shift(1) < 35`, exit `rsi_2 > 65`.
  - R3: `rsi_2` strictly falling for 3 bars, `rsi_2[t-2] < 60`, `rsi_2 < 10`, exit `rsi_2 > 70`.
  - ConnorsRSI Pullback: new features `streak`, `rsi_streak_2`, `pctrank_ret_100`, `connors_rsi`, `adx_10` (all missing).
    Entry uses the existing `entry_limit` = close * (1 - 0.04), filled next day if low <= limit. **Note:** `_fill_entry` currently fills
    at the open and only rejects if the open is above the limit; it does not model an intraday limit touch, so that needs a limit-fill hook.
  - Alpha Formula: weekly RSI(2) on week-end bars (resampler missing), SPY `ret_126d > 0`, rank by `vol_63d` ascending (a proxy
    for 100-day HV), 10 equal-weight slots, 10% stop.
- All variants: `min_reward_risk` 0, `max_hold_days` 5-10 (weekly: 8 weeks), catastrophic stop `2*atr_14` or 10%, sized by
  fixed equity fraction.
- Missing: `sma_5`, close-fill (MOC) mode, intraday-limit fill, ConnorsRSI parts, ADX, weekly resampler.

## What the router should know
All variants share exposure with `rsi2_meanrev`. They are comparison arms, so shadow them and do not stack them. Nagel's work suggests
reversal pays most in high vol, which is the opposite of the 200-day gate. That should be tested, not assumed.

## Signs of decay to monitor
Per variant: rolling 40-trade expectancy <= 0. Win rate under 65%. Average loss more than 2.5x the average win. Correlation with the breakout
book above 0.5 (it loses its diversifier role).

## Sources
- docs/methods/11-rsi2-connors-mean-reversion.md (full source list)
- https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf
- https://www.whselfinvest.de/en-de/trading-platform/free-trading-strategies/tradingsystem/81-r3-larry-connors
- https://wl6.wealth-lab.com/Strategy/Details/254
- https://www.quantconnect.com/forum/discussion/18219/quot-the-alpha-formula-quot-mean-reversion-strategy-by-cabedovestment/
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://www.cxoadvisory.com/technical-trading/a-few-notes-on-short-term-trading-strategies-that-work/

## Empirical (replay)
_Pending: filled in from swing replay on real data._
