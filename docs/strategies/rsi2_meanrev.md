---
slug: rsi2_meanrev
name: Connors RSI(2) mean reversion
originators: [Larry Connors, Cesar Alvarez]
category: strategy
decision: have
holding_period_days: [1, 5]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction]
typical_win_rate: 0.71        # Backtrex S&P 500 OOS 2016-2026 (NDX 0.75)
typical_payoff_ratio: 0.58    # computed here: avg win 1.22% / avg loss 2.10% (SPX); NDX 1.58/3.11 = 0.51
evidence_grade: B-
free_data_ok: true
status: enabled
---

# Connors RSI(2) mean reversion (`rsi2_meanrev`)

## One-line summary
Above the 200-day SMA, buy near the close after a sharp 2-7 day pullback drives the 2-period RSI under 5-10; sell the
first bounce (close above the 5-day SMA or RSI(2) above 65-70). High hit rate, small average gain, losers bigger
than winners.

## Origin and lineage
- Larry Connors, *How Markets Really Work* (2004); Connors & Alvarez, *Short Term Trading Strategies That Work*
  (2008): six rules (buy pullbacks, buy after drops, only above the 200-day, use the VIX, stops hurt, hold overnight)
  and the 2-period RSI chapter, plus Double 7s and cumulative RSI.
- Later family: *High Probability ETF Trading* (2009: R3, RSI 25/75 etc.), ConnorsRSI (~2012), ConnorsRSI Pullback
  for stocks (Active Trader, Mar 2013), weekly RSI-2 rotation in *The Alpha Formula* (Connors & Cain 2019).
- Academic root: short-term return reversal (Jegadeesh 1990; Lehmann 1990).

## Exact rules
As taught (classic, ChartSchool / book):
- **Universe**: index ETFs (SPY, QQQ) originally; stock versions use price > $5 and liquidity floors.
- **Filter**: close > 200-day SMA (shorts mirror below it).
- **Setup/trigger**: RSI(2) < 10 (aggressive < 5). Variants: Double 7s (close at a 7-day low); cumulative RSI(2)
  over 2 days < 35; R3 (RSI(2) down 3 days, first < 60, today < 10); optional wait for RSI(2) to cross back above 50.
- **Entry order**: just before the close (Connors' preference) or the next open.
- **Initial stop**: none; Connors' tests found stops hurt. *Alpha Formula* adds a 10% catastrophic stop.
- **Exit**: close above the 5-day SMA (classic); RSI(2) > 65-70 alternatives; Double 7s exits at a 7-day closing high.
- **Time**: typically 2-6 bars; Double 7s on SPY was in the market < 25% of the time 1993-2007.
- **Sizing**: fixed equity fraction with a cap on concurrent positions (no stop, so risk-per-stop sizing does not
  apply); *Alpha Formula* uses 10 equal-weight slots.

## Why it should work
- Short-term reversal is the return to supplying liquidity (Nagel, RFS 2012); it is predictable with the VIX and spikes
  in turmoil. Counterparty: forced/impatient sellers after a fast drop. The 200-day filter keeps the trade on the
  side of the long-term drift.
- Medhat & Schmeling (RFS 2022): low-turnover stocks reverse, high-turnover (news) stocks continue at one month, so
  heavy-volume, news-driven drops revert less.

## When it works and when it fails
- Works: pullbacks in established uptrends; concentrated momentum tapes where dips in leaders are bought quickly;
  higher-volatility days within an uptrend.
- Fails: trend breaks (NDX 2020: -12.2% on 2 trades); earnings/guidance gaps (information, not noise); the 200-day
  filter switches it off in corrections exactly when reversal returns are highest (Nagel).

## Parameters and sensitivity
| Knob | Code default | Taught | Notes |
|---|---|---|---|
| `rsi_entry` | 10 | 5-10 | pick a priori |
| `rsi_exit` | 70 | 65-70 | |
| `trend_ma` | `sma_200` | 200-day | |
| `exit_ma` | `sma_10` | 5-day SMA | `sma_5` not in the panel yet |
| `max_hold_days` | 5 | none | |
| `stop_atr_mult` | 2.0 | none | |
| `min_market_trend_state` | -1 (off) | instrument's own 200-day | |
| `min_reward_risk` | 0.0 | n/a | settings skip the 2:1 floor |
Traps: threshold menus (RSI < 2/5/10, Double 5s-10s, ConnorsRSI W/X/Y/Z grids) invite overfitting; RSI(2) values
depend on Wilder warm-up, small differences move readings across 5 or 10.

## Evidence
- In-sample (book excerpt): Double 7s on SPY 1993-2007, 153 trades, avg +0.85%, 80.4% correct. CXO (Jan 2009): no
  data-mining correction or OOS test, no cost sensitivity.
- Backtrex OOS (published 2 Oct 2026), S&P 500 index, 3 Oct 2016-1 Oct 2026, long RSI(2) < 5 above SMA200 plus short
  mirror, exit 5-day SMA or 200-day cross, 0.02%/side: CAGR 1.7% vs 13.5% buy-and-hold, 73 trades, 71.2% wins,
  PF 1.43, avg win 1.22% vs avg loss 2.10%, max DD -21.5%; 2025 +6.4%, 2026 YTD +6.5%. NDX: CAGR 2.4%, 65 trades,
  75.4% wins, PF 1.55, avg win 1.58% vs loss 3.11%; 2025 -0.6%, 2026 YTD +6.9%.
- Per-trade expectancy computed in doc 11: SPX about +0.27%, NDX about +0.43%; low exposure explains most of the CAGR
  gap. Sample of 65-73 trades is small. Long vs short P&L not split (unverified).
- Trading Time Machine (4 Mar 2026), Nasdaq-100 constituents 2006-2025, 4 slots: CAGR 17.84%, 64.3% wins, PF 1.45,
  max DD 29.15% (costs and survivorship handling not stated).
- Alpha Algo (4 Mar 2026), E-mini S&P 1997-2026: PF 2.15; with a VIX filter PF 2.99 and max DD roughly halved
  (in-sample).
- Alvarez (24 Jan 2024): mean reversion has out-performed on 5-day holds since about 1983 with little change since the
  mid-2000s; edges smaller.
- Grade conflict in the catalog: platforms B, methods.md B-, evidence.json D (thin OOS, negative skew).

## Common mistakes
1. Fitting thresholds to the 1995-2007 sample.
2. Treating "stops hurt" as "no tail risk" (negative skew).
3. Buying the next open instead of the close.
4. Buying RSI(2) lows after earnings misses.
5. Using today's index constituents (survivorship).
6. Comparing a ~10-25% exposure system with 100%-invested buy-and-hold.

## Discretionary parts and how to make them mechanical
Nothing in the classic rule is discretionary. Residue: news triage (Claude enum `NEWS_DRIVEN` / `NO_NEWS`, never a
price) and whether to override the 200-day gate in panics (a separately tested small-size sub-rule).

## Implementation spec for swing-engine
What `swing_engine/strategies/rsi2_meanrev.py` does:
- Gate: none on the market (`min_market_trend_state = -1`); `close > sma_200`; `rsi_2 < 10`; `atr_14 > 0`.
- Entry reference = as-of close; the backtester fills at the next open.
- Stop = `close - 2 * atr_14`. Target = `sma_10` if above close (resting limit), else None.
- Score = 10 - rsi_2.
- `should_exit`: `bars_held >= 5`, or `close > sma_10`, or `rsi_2 > 70`.
Differences from Connors:
1. Exit MA is `sma_10`, not the 5-day SMA (`sma_5` missing; `SMA_WINDOWS` = 10, 20, 50, 200).
2. Next-open fill instead of at-the-close; gives away part of the bounce.
3. Target as an intraday resting limit is an earlier exit than a close above the MA.
4. Adds a 2x ATR stop and a 5-day time stop (not taught).
Proposed (methods.md 7a #5): add `sma_5`, make `exit_ma: sma_5` the faithful variant; test `target=None` with the
close-based exit; limit-below-close or MOC entry mode (backtester hook missing); report with and without the ATR and
time stops; optional `close_pos < 0.25` confirm; earnings-window exclusion.
- `max_hold_days`: 5. Min reward:risk: 0 (settings), sized by the 10% notional cap in practice.
- Reuses: `rsi_2`, `sma_200`, `sma_10`, `atr_14`, `close_pos`, `market_vol_regime`.
- Missing: `sma_5`, ConnorsRSI, 7-day closing low, ADX(10), VIX series, MOC entry.

## What the router should know
- Settings: allowed in healthy (1.0), narrow (0.75), choppy (0.75), high_vol_selloff (0.25); not in correction.
- Low correlation with breakouts: it trades when breakout strategies are idle. Losses cluster on trend breaks.
- Nagel suggests the high-vol state is where reversal pays most; the 0.25 multiplier there is a risk choice.

## Signs of decay to monitor
- Win rate below ~65% over 50 trades with the same exit.
- Average loss / average win rising above ~2.5.
- Per-trade expectancy after costs <= 0.
- Many entries in the same week stopping out (trend break).

## Sources
- docs/methods/11-rsi2-connors-mean-reversion.md; docs/methods.md 1a #4, 6.11, 7a #5
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- https://backtrex.com/en/backtests/connors-rsi-2-sp-500
- https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100
- https://c.mql5.com/forextsd/forum/56/sttstw_chap10.pdf
- https://www.cxoadvisory.com/technical-trading/a-few-notes-on-short-term-trading-strategies-that-work/
- https://backtest.substack.com/p/the-2-period-rsi-a-simple-system
- https://algotr.substack.com/p/this-simple-mean-reversion-strategy
- https://alvarezquanttrading.com/blog/mean-reversion-vs-trend-following-through-the-years/
- https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html
- https://openaccess.city.ac.uk/id/eprint/31278/

## Empirical (replay)
_Pending: filled in from swing replay on real data._
