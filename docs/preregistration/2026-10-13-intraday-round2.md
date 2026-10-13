# Pre-registration: intraday lane, round 2 (two published intraday momentum rules)

Committed 2026-10-13 **before** any replay of these rules exists on any data. Nothing below may change after the
first run except a harness-only amendment (a bug that stops the rules as written from running), written into this
file before results are read.

## Why, and what this is not
Round 1 (`2026-10-13-intraday-chains.md`) tested the video's sweep -> shift -> zone chain. All three cards failed;
gross R was about zero, so costs were not the only problem. Those cards are **not** retuned here: no parameter,
timeframe or market of round 1 is touched, and no round-1 trade or refusal was used to choose anything below.

Round 2 asks a different question on the same data: do the two intraday rules that have published evidence on index
ETFs survive this engine's costs, and does the newer one hold up after its publication date?

| # | Card | Source | Published result (gross or at the authors' costs) |
|---|---|---|---|
| 1 | `noise_area_momentum` | Zarattini, Aziz & Barbon, "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", Swiss Finance Institute RP 24-97, first version 2024-05-10 (PDF read 2026-10-13) | SPY 2007 to early 2024, unlevered, stop at current band + VWAP: 9.7% a year, vol 7.7%, Sharpe 1.24, 7,668 trades, hit ratio 43%, at $0.0045 a share (about 0.1 bp a side) |
| 2 | `first_half_hour_momentum` | Gao, Han, Li & Zhou, "Market intraday momentum", JFE 129 (2018); numbers below from the paper's abstract and secondary summaries, paper tables not read | SPY 1993-2013: the first half-hour return (from the prior close) predicts the last half-hour return; timing strategy about 6.7% a year gross |

Expectation, stated before the run: card 1's edge per trade in the paper is about $0.09 a share, roughly 3 to 4 bp,
against this engine's 2 bp round trip, so it is close to break-even here and most likely fails the haircut. Card 2's
gross edge is about 2.6 bp a day against a 2 bp round trip; it most likely fails. Window B (2024 on) is almost
entirely after card 1's publication and is its first out-of-sample test here.

## Data and markets
- 1-minute bars, Alpaca free SIP, table `bars_1m` in `data/live/intraday.duckdb`: SPY, QQQ, IWM. Regular session only
  (`session = 'rth'`, 09:30 to the close, early closes respected). GLD and BTC/USD are not traded: neither paper
  makes a claim about them and BTC has no open or close.
- A minute bar is stamped with its opening minute. `P(HH:MM)` is the close of the last regular bar that ended at or
  before HH:MM on that day. `Open_t` is the open of the day's first regular bar; `Close_{t-1}` is the close of the
  previous session's last regular bar.
- A day is skipped for a symbol when its first regular bar opens after 09:31 or the previous session has no bar.

## Card 1: `noise_area_momentum` (the paper's unlevered "current band + VWAP" version)
1. For each check time HH:MM, `move_{d,HH:MM} = |P_d(HH:MM) / Open_d - 1|`. `sigma_{t,HH:MM}` is the mean of `move` over
   the **14** most recent earlier sessions that have that check time (an early-close day has none after its close).
   No trade at a check time with fewer than 14.
2. `UB = max(Open_t, Close_{t-1}) x (1 + sigma)`, `LB = min(Open_t, Close_{t-1}) x (1 - sigma)`. Volatility multiplier 1.
3. `VWAP(HH:MM)` = sum of typical price x volume over the day's regular bars that ended at or before HH:MM, divided by
   their volume; typical price = (high + low + close) / 3.
4. Check times: every HH:00 and HH:30 from **10:00** to 30 minutes before the close (15:30 on a normal day).
   At each check the target position is **+1** if `P > max(UB, VWAP)`, **-1** if `P < min(LB, VWAP)`, else **0**.
   (This is the paper's rule: enter beyond the noise area, exit as soon as price crosses the current band or the VWAP,
   stops checked only at the half hour; a long can flip to short at one check.)
5. A change of position fills at the open of the minute bar that starts at the check time. Any open position is
   closed at the close of the day's last regular bar.
6. Size: 100% of the symbol's sleeve at every entry, no leverage, no volatility targeting (the paper's 4x-levered
   variant is not tested).

## Card 2: `first_half_hour_momentum`
1. `r1 = P(10:00) / Close_{t-1} - 1`.
2. At 15:30 go long if `r1 > 0`, short if `r1 < 0`, nothing if 0; fill at the open of the 15:30 bar; exit at the
   close of the day's last regular bar.
3. Early-close days are skipped. Size 100% of the sleeve.
(The paper's second predictor, the 15:00-15:30 return, is not used: one rule, one trial per window.)

## Simulation and costs
- A day's return for one symbol = sum over its trades of `side x (exit / entry - 1)` minus costs. No compounding
  inside a day.
- Cost: **1.0 bp of traded notional per side** for SPY, QQQ and IWM (the round-1 constants), charged on every entry
  and exit; a flip pays two sides. The same run reported at the paper's 0.1 bp a side is descriptive only.
- The card's daily return is the equal-weight mean of the three symbols' daily returns (a symbol with no trade that
  day contributes 0; a skipped symbol-day contributes 0). Every session of the window counts, traded or not.

## Windows and trials
- Window A: 2016-01-01 .. 2023-12-31. Window B: 2024-01-01 .. 2026-10-09. The first sessions of A only build `sigma`.
- 2 cards x 2 windows = **4 trials**, logged to `data/trials.jsonl` with tag `intraday-round2`; the haircut uses
  every trial logged to date plus these.
- One run. Per-symbol, per-direction, per-year and 0.1 bp rows are descriptive and cannot rescue a card.

## Pass rule (per card)
PASS needs all of:
1. mean daily net return above 0 in both windows;
2. Harvey-Liu haircut Sharpe above 0 in both windows (annual Sharpe of the card's daily net returns, sqrt(252));
3. mean daily net return above 0 for at least 2 of the 3 symbols in window B.
Otherwise FAIL. Reported beside it, not criteria: trades, hit ratio, mean net bp per trade, max drawdown, and OLS
alpha and beta of the daily net return on SPY's close-to-close return.

## What a pass allows
Shadow-only tracking and a walk-forward. Paper trading of an intraday card additionally needs `docs/gates.md` and
the owner's decision on an always-on host; neither is granted here.
