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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 15285 | 78 | 51% | +0.03 | -0.07 | 47% | -0.01 | -0.11 | 45% | +0.06 | -0.05 | 1.11 |
| correction | 1190 | 1 | 48% | -0.02 | -0.14 | 67% | +0.32 | +0.20 | 69% | +0.79 | +0.67 | 4.19 |
| healthy_uptrend | 40201 | 124 | 52% | +0.07 | -0.03 | 48% | +0.08 | -0.02 | 42% | +0.09 | -0.02 | 1.17 |
| high_vol_selloff | 5436 | 35 | 52% | +0.05 | -0.05 | 53% | +0.18 | +0.08 | 41% | +0.09 | -0.01 | 1.17 |
| narrow_uptrend | 7083 | 18 | 47% | -0.03 | -0.14 | 39% | -0.14 | -0.26 | 35% | -0.14 | -0.25 | 0.78 |
| **all** | 69195 | 256 | 51% | +0.05 | -0.06 | 48% | +0.05 | -0.05 | 42% | +0.08 | -0.03 | 1.14 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 40060 | 85 | 58% | +0.14 | +0.04 | 58% | +0.25 | +0.15 | 51% | +0.33 | +0.23 | 1.75 |
| correction | 16319 | 36 | 57% | +0.10 | -0.01 | 54% | +0.14 | +0.03 | 47% | +0.14 | +0.04 | 1.29 |
| healthy_uptrend | 138949 | 505 | 49% | -0.01 | -0.11 | 46% | +0.00 | -0.11 | 41% | +0.03 | -0.07 | 1.06 |
| high_vol_selloff | 32053 | 194 | 47% | -0.06 | -0.16 | 43% | -0.08 | -0.18 | 38% | -0.09 | -0.19 | 0.85 |
| narrow_uptrend | 34143 | 70 | 56% | +0.09 | -0.01 | 53% | +0.13 | +0.02 | 47% | +0.16 | +0.06 | 1.33 |
| **all** | 261524 | 890 | 51% | +0.03 | -0.08 | 49% | +0.05 | -0.05 | 44% | +0.09 | -0.02 | 1.17 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
