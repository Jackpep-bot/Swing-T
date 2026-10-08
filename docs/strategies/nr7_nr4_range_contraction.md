---
slug: nr7_nr4_range_contraction
name: NR7 / NR4 / ID-NR4 range-contraction breakout (Crabel)
originators: [Toby Crabel, Linda Raschke & Larry Connors (Street Smarts, ID/NR4)]
category: volatility_breakout
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]       # Crabel; Bulkowski's 7%/7% test averaged 31 calendar days
timeframe: daily
direction: long                   # Crabel trades OCO both sides; swing-engine strategies are long-only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: 0.57            # Bulkowski 7% target / 7% stop, bull-market up-breakouts, 1990-2013
typical_payoff_ratio: 0.95        # same test: avg win $705 vs avg loss $743
evidence_grade: C
free_data_ok: true
status: not_built                 # inside_day exists; no NR feature, module or settings entry
---

# NR7 / NR4 / ID-NR4 range contraction

## One-line summary
When today's high-low range is the narrowest of the last 7 (or 4) days, place a buy stop just above its high (and, in
Crabel's form, a sell stop below its low); take the expansion and get out fast if it does not come.

## Origin and lineage
Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990), with Stocks & Commodities
articles 1988-89. Raschke & Connors, *Street Smarts* (1995) popularised ID/NR4. StockCharts ChartSchool publishes a
filtered stock scan. Stockbee's momentum burst cites Crabel's contraction-expansion idea (docs/methods/09).

## Exact rules
- NR7: `range_t = high_t - low_t` is smaller than each of the prior 6 ranges. NR4: smaller than each of the prior 3.
- ID/NR4: NR4 that is also an inside day (`high_t < high_{t-1}` and `low_t > low_{t-1}`).
- Entry (next day): buy stop 1 tick above the NR bar high; sell stop 1 tick below its low; the first filled is the
  position and the other becomes its stop (ID/NR4 allows stop-and-reverse).
- Stop: the opposite side of the NR bar. ChartSchool alternatives: Parabolic SAR or 2 x ATR.
- Exit: Crabel took profits fast, at the close of the entry day or the first profitable close; failure to expand at
  once is the first warning. Raschke/Connors: exit within 1-2 days if no expansion, trail when it comes.
- ChartSchool filtered long scan: NR7 that is also an inside day; Aroon Up(63) > Aroon Down(63); min CCI(10) over the
  last 5 days < -100 (pullback in an uptrend); 20-day avg volume > 100k; 60-day SMA of price > $20.
- Sizing: not taught.

## Why it should work
Range contraction is low realised volatility; vol clusters and mean-reverts, so the next day's range is likely
larger. Direction comes from the stop entry itself (the market shows its hand first). The other side: range traders
selling the top of a quiet range and stops resting just beyond the NR bar.

## When it works and when it fails
- Works: in trending names where the NR bar is a pause; in futures it was an intraday edge in the 1980s.
- Fails: whipsaw (both stops hit), choppy tapes, and after costs on a 1-day hold: Oxford Capital found it not
  tradeable in futures after costs without extra rules.

## Parameters and sensitivity
N in {4, 7} (Oxford tested 1-20; better above 5 before costs); hold 1-40 days; inside-day requirement; trend filter.
Trap: optimising N and the hold jointly; the cost assumption decides the sign.

## Evidence
- Bulkowski (thepatternsite.com/nr7.html): 1,201 stocks, Jan 1990-Mar 2013, price >= $5. Bull-market up-breakouts
  failed to move 5% 46% of the time (down-breakouts 47%). A 7% target / 7% stop test entering at the open after the
  breakout won 57% in bull-market up-breakouts, average about +$79 per trade (~+0.8% on $10,000) after $10
  commissions, average hold 31 calendar days, avg win $705 vs avg loss $743.
- Oxford Capital Strategies: 42 US futures, 1980 to Jan 2016 (all three Oxford NR7 pages), NR_Length 1-20,
  hold 1-40 days, ORB-stretch entries: pre-cost results better for NR > 5 and longer holds; "not currently tradeable"
  after costs without more rules.
- No independent test of the ID/NR4 rule set located.

## Common mistakes
- Holding a failed NR breakout hoping for expansion (Crabel's edge was the fast exit).
- Using true range vs high-low inconsistently (Crabel uses high-low).
- Ignoring same-day reversals on daily bars: both sides can trade in one day.

## Discretionary parts and how to make them mechanical
"First profitable close" = first close above entry fill; "failure to follow through" = close on entry day below entry.

## Implementation spec for swing-engine
- Features (new, `features/patterns.py`): `range_hl = high - low`; `nr7 = range_hl < min(range_hl[t-6..t-1])`;
  `nr4 = range_hl < min(range_hl[t-3..t-1])`; `id_nr4 = nr4 and inside_day`. NR window lengths are versioned constants.
  methods.md 7 also asks for `nr7` as an alternative prior-day filter in `momentum_burst`.
- Setup at close t: `nr7_t` (variant `id_nr4_t`), `trend_state >= 1`, `avg_vol_20d >= 100_000`, `close >= 5`.
- Entry: buy stop `high_t + 0.01`, valid 1 session. **Missing hook**: stop-entry fill
  (`max(open_{t+1}, trigger)` if `high_{t+1} >= trigger`, else cancel); the backtester only fills at next open.
- Stop: `low_t - 0.01`. Risk is tiny by construction; cap size via `max_position_pct`.
- Exits: variant A (Crabel) exit at the first profitable close or after 3 bars (`max_hold_days: 3`); variant B
  (Bulkowski) target entry x 1.07, stop entry x 0.93, `max_hold_days: 40`. Variant A needs `min_reward_risk: 0.0`.
- Same-bar fill-and-stop: if the stop is touched on the entry bar, assume stopped (worst case).
- Reuses: `inside_day`, `trend_state`, `avg_vol_20d`, `atr_14`.

## What the router should know
Short-hold comparison strategy; very frequent signals (an NR7 occurs on roughly 1 of 7 days per symbol by chance), so
it needs a trend filter and a per-day cap. Not in `choppy`.

## Signs of decay to monitor
Next-day range expansion ratio (range_{t+1}/range_t) falling toward 1; entry-day stop-outs above 40%.

## Sources
- https://thepatternsite.com/nr7.html
- https://oxfordstrat.com/trading-strategies/nr7/
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7
- https://www.tradingsetupsreview.com/inside-daynr4
- https://technical.traders.com/tradersonline/display.asp?art=2666

## Empirical (replay)
_Pending: filled in from swing replay on real data._
