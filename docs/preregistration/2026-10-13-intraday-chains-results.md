# Intraday chain cards: results

Graded per `docs/preregistration/2026-10-13-intraday-chains.md`. One run. Haircut over n_trials = 3253 (3247 logged before this group + 6). Extractor version 2026-10-13. R is |entry - stop|; net R is after the spec's per-side costs. No sizing, no equity curve.
Trades: 7124 (last entry 2026-10-12); refusals: 17696. Rows in `data/research/intraday_chains/trades.parquet` and `refusals.parquet`, each trade with its chain lineage line.

## Verdict

**Nothing passes.** No card meets the pre-registered rule.

| card | verdict | 1. trades A / B (>= 200) | 2. net R per trade A / B (> 0) | 3. haircut Sharpe A / B (> 0) | 4. symbols with net R > 0 in B (>= 3) | net R beats control in both windows |
|---|---|---|---|---|---|---|
| `lit_chain_ob` | **FAIL** | 167 / 59 (no) | -0.616 / -0.935 (no) | -1.52 / -1.78 (no) | 1 of 5 (no) | no |
| `lit_chain_fvg` | **FAIL** | 341 / 134 (no) | -0.245 / -0.468 (no) | -1.37 / -1.75 (no) | 3 of 5 (ok) | yes |
| `sweep_reversal_control` | **FAIL** | 4542 / 1877 (ok) | -0.456 / -0.986 (no) | -5.35 / -10.49 (no) | 0 of 5 (no) | - |

## Pooled, per card and window

Win = net R above 0. t is on daily blocks (mean net R per day with a trade, all symbols pooled); Sharpe = t / sqrt(window years).

| card | window | trades | win rate | gross R | net R | MFE R | MAE R | days | t | Sharpe | haircut Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `lit_chain_ob` | A 2016-01..2023-12 | 167 | 33.5% | -0.109 | -0.616 | 1.20 | 0.70 | 154 | -4.31 | -1.52 | -1.52 |
| `lit_chain_ob` | B 2024-01..2026-10 | 59 | 32.2% | +0.016 | -0.935 | 1.22 | 0.74 | 59 | -2.97 | -1.78 | -1.78 |
| `lit_chain_fvg` | A 2016-01..2023-12 | 341 | 41.3% | -0.029 | -0.245 | 0.70 | 0.58 | 299 | -3.87 | -1.37 | -1.37 |
| `lit_chain_fvg` | B 2024-01..2026-10 | 134 | 41.8% | +0.074 | -0.468 | 0.81 | 0.57 | 121 | -2.92 | -1.75 | -1.75 |
| `sweep_reversal_control` | A 2016-01..2023-12 | 4542 | 31.6% | -0.069 | -0.456 | 1.00 | 0.79 | 1868 | -15.12 | -5.35 | -5.35 |
| `sweep_reversal_control` | B 2024-01..2026-10 | 1877 | 28.4% | -0.008 | -0.986 | 1.05 | 0.78 | 745 | -17.47 | -10.49 | -10.49 |

## Chains and refusals by step

Every closed-back 15m sweep starts a chain (card 3: PDH / PDL sweeps only). `no_room` cannot occur (2R fallback).

| card | window | chains | traded | no_shift | shift_failed | no_zone | no_retrace | zone_dead | no_trigger | stop_too_tight | daily_cap | position_open | too_late |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `lit_chain_ob` | A | 5999 | 167 | 5332 | 49 | 8 | 284 | 125 | 0 | 30 | 0 | 0 | 4 |
| `lit_chain_ob` | B | 2679 | 59 | 2389 | 24 | 1 | 121 | 72 | 0 | 11 | 0 | 0 | 2 |
| `lit_chain_fvg` | A | 5999 | 341 | 5332 | 16 | 40 | 106 | 119 | 18 | 14 | 0 | 4 | 9 |
| `lit_chain_fvg` | B | 2679 | 134 | 2389 | 9 | 16 | 44 | 71 | 8 | 5 | 0 | 1 | 2 |
| `sweep_reversal_control` | A | 5264 | 4542 | 0 | 0 | 0 | 0 | 0 | 0 | 526 | 1 | 70 | 125 |
| `sweep_reversal_control` | B | 2190 | 1877 | 0 | 0 | 0 | 0 | 0 | 0 | 224 | 0 | 40 | 49 |

## By symbol

Descriptive, except that rule 4 reads window B here.

| card | window | symbol | trades | win rate | gross R | net R | MFE R | MAE R |
|---|---|---|---|---|---|---|---|---|
| `lit_chain_ob` | A | SPY | 23 | 30.4% | -0.201 | -0.300 | 0.87 | 0.65 |
| `lit_chain_ob` | A | QQQ | 34 | 52.9% | +0.433 | +0.365 | 1.36 | 0.62 |
| `lit_chain_ob` | A | IWM | 38 | 47.4% | +0.168 | +0.118 | 1.00 | 0.58 |
| `lit_chain_ob` | A | GLD | 27 | 33.3% | -0.286 | -0.432 | 0.81 | 0.69 |
| `lit_chain_ob` | A | BTC/USD | 45 | 8.9% | -0.598 | -2.250 | 1.65 | 0.91 |
| `lit_chain_ob` | B | SPY | 4 | 50.0% | +0.012 | -0.024 | 0.57 | 0.45 |
| `lit_chain_ob` | B | QQQ | 8 | 50.0% | +0.326 | +0.263 | 1.23 | 0.56 |
| `lit_chain_ob` | B | IWM | 10 | 20.0% | -0.516 | -0.556 | 0.71 | 0.81 |
| `lit_chain_ob` | B | GLD | 6 | 50.0% | -0.075 | -0.264 | 0.78 | 0.74 |
| `lit_chain_ob` | B | BTC/USD | 31 | 25.8% | +0.125 | -1.613 | 1.55 | 0.80 |
| `lit_chain_fvg` | A | SPY | 48 | 31.2% | -0.114 | -0.164 | 0.61 | 0.58 |
| `lit_chain_fvg` | A | QQQ | 71 | 39.4% | -0.027 | -0.065 | 0.64 | 0.56 |
| `lit_chain_fvg` | A | IWM | 71 | 47.9% | -0.010 | -0.043 | 0.58 | 0.52 |
| `lit_chain_fvg` | A | GLD | 58 | 65.5% | +0.165 | +0.081 | 0.59 | 0.43 |
| `lit_chain_fvg` | A | BTC/USD | 93 | 28.0% | -0.122 | -0.780 | 0.96 | 0.75 |
| `lit_chain_fvg` | B | SPY | 13 | 46.2% | -0.076 | -0.124 | 0.57 | 0.44 |
| `lit_chain_fvg` | B | QQQ | 19 | 47.4% | +0.126 | +0.097 | 0.63 | 0.43 |
| `lit_chain_fvg` | B | IWM | 21 | 57.1% | +0.157 | +0.132 | 0.60 | 0.39 |
| `lit_chain_fvg` | B | GLD | 17 | 47.1% | +0.144 | +0.094 | 0.51 | 0.34 |
| `lit_chain_fvg` | B | BTC/USD | 64 | 32.8% | +0.044 | -1.052 | 1.05 | 0.75 |
| `sweep_reversal_control` | A | SPY | 875 | 32.5% | -0.094 | -0.247 | 0.98 | 0.81 |
| `sweep_reversal_control` | A | QQQ | 1028 | 33.8% | -0.045 | -0.168 | 1.03 | 0.79 |
| `sweep_reversal_control` | A | IWM | 1115 | 32.5% | -0.084 | -0.205 | 0.99 | 0.79 |
| `sweep_reversal_control` | A | GLD | 796 | 34.0% | -0.049 | -0.284 | 0.97 | 0.77 |
| `sweep_reversal_control` | A | BTC/USD | 728 | 23.8% | -0.075 | -1.685 | 1.03 | 0.79 |
| `sweep_reversal_control` | B | SPY | 284 | 30.3% | -0.153 | -0.312 | 1.01 | 0.81 |
| `sweep_reversal_control` | B | QQQ | 298 | 34.2% | -0.053 | -0.169 | 1.02 | 0.80 |
| `sweep_reversal_control` | B | IWM | 345 | 31.9% | -0.137 | -0.238 | 0.96 | 0.78 |
| `sweep_reversal_control` | B | GLD | 245 | 40.0% | +0.105 | -0.098 | 1.05 | 0.75 |
| `sweep_reversal_control` | B | BTC/USD | 705 | 19.6% | +0.093 | -2.277 | 1.12 | 0.78 |

## By direction

Descriptive only.

| card | window | direction | trades | win rate | gross R | net R | MFE R | MAE R |
|---|---|---|---|---|---|---|---|---|
| `lit_chain_ob` | A | long | 68 | 36.8% | -0.052 | -0.617 | 1.22 | 0.66 |
| `lit_chain_ob` | A | short | 99 | 31.3% | -0.148 | -0.616 | 1.19 | 0.73 |
| `lit_chain_ob` | B | long | 21 | 33.3% | +0.131 | -0.882 | 1.15 | 0.73 |
| `lit_chain_ob` | B | short | 38 | 31.6% | -0.048 | -0.964 | 1.26 | 0.75 |
| `lit_chain_fvg` | A | long | 148 | 43.9% | +0.018 | -0.212 | 0.71 | 0.56 |
| `lit_chain_fvg` | A | short | 193 | 39.4% | -0.065 | -0.270 | 0.69 | 0.60 |
| `lit_chain_fvg` | B | long | 52 | 46.2% | +0.301 | -0.416 | 0.97 | 0.58 |
| `lit_chain_fvg` | B | short | 82 | 39.0% | -0.070 | -0.501 | 0.70 | 0.56 |
| `sweep_reversal_control` | A | long | 2379 | 31.8% | -0.075 | -0.415 | 0.99 | 0.79 |
| `sweep_reversal_control` | A | short | 2163 | 31.4% | -0.063 | -0.500 | 1.01 | 0.79 |
| `sweep_reversal_control` | B | long | 971 | 28.7% | -0.014 | -0.994 | 1.04 | 0.79 |
| `sweep_reversal_control` | B | short | 906 | 28.1% | -0.003 | -0.978 | 1.05 | 0.78 |

## By SPY daily regime

Descriptive only. SPY's prior regular-session close against its 200-session average, both known before the entry day.

| card | window | regime | trades | win rate | gross R | net R | MFE R | MAE R |
|---|---|---|---|---|---|---|---|---|
| `lit_chain_ob` | A | above | 120 | 27.5% | -0.363 | -0.839 | 1.02 | 0.74 |
| `lit_chain_ob` | A | below | 40 | 45.0% | +0.395 | -0.288 | 1.59 | 0.64 |
| `lit_chain_ob` | A | unknown | 7 | 71.4% | +1.377 | +1.324 | 2.05 | 0.47 |
| `lit_chain_ob` | B | above | 57 | 31.6% | -0.000 | -0.881 | 1.23 | 0.73 |
| `lit_chain_ob` | B | below | 2 | 50.0% | +0.468 | -2.459 | 0.98 | 0.89 |
| `lit_chain_fvg` | A | above | 244 | 38.9% | -0.089 | -0.288 | 0.65 | 0.59 |
| `lit_chain_fvg` | A | below | 77 | 44.2% | +0.111 | -0.202 | 0.88 | 0.59 |
| `lit_chain_fvg` | A | unknown | 20 | 60.0% | +0.166 | +0.124 | 0.60 | 0.50 |
| `lit_chain_fvg` | B | above | 126 | 42.9% | +0.101 | -0.444 | 0.83 | 0.57 |
| `lit_chain_fvg` | B | below | 8 | 25.0% | -0.348 | -0.850 | 0.42 | 0.60 |
| `sweep_reversal_control` | A | above | 3142 | 32.7% | -0.051 | -0.435 | 1.01 | 0.79 |
| `sweep_reversal_control` | A | below | 1056 | 27.9% | -0.134 | -0.598 | 0.98 | 0.82 |
| `sweep_reversal_control` | A | unknown | 344 | 33.7% | -0.042 | -0.202 | 0.94 | 0.77 |
| `sweep_reversal_control` | B | above | 1737 | 28.3% | -0.004 | -1.006 | 1.05 | 0.78 |
| `sweep_reversal_control` | B | below | 140 | 30.7% | -0.059 | -0.742 | 0.99 | 0.79 |

## By exit

How trades ended: target, stop, stop_gap (opened through the stop), time (15:55 / 24h).

| card | window | exit reason | trades | win rate | gross R | net R | MFE R | MAE R |
|---|---|---|---|---|---|---|---|---|
| `lit_chain_ob` | A | stop | 84 | 0.0% | -1.000 | -1.790 | 0.94 | 1.00 |
| `lit_chain_ob` | A | stop_gap | 2 | 0.0% | -1.034 | -4.682 | 1.38 | 1.03 |
| `lit_chain_ob` | A | target | 9 | 100.0% | +3.326 | +3.154 | 3.33 | 0.25 |
| `lit_chain_ob` | A | time | 72 | 65.3% | +0.528 | +0.394 | 1.23 | 0.40 |
| `lit_chain_ob` | B | stop | 29 | 0.0% | -1.000 | -2.290 | 0.87 | 1.00 |
| `lit_chain_ob` | B | stop_gap | 3 | 0.0% | -1.043 | -3.739 | 0.10 | 1.04 |
| `lit_chain_ob` | B | target | 6 | 100.0% | +3.286 | +2.442 | 3.29 | 0.36 |
| `lit_chain_ob` | B | time | 21 | 61.9% | +0.635 | +0.373 | 1.26 | 0.44 |
| `lit_chain_fvg` | A | stop | 114 | 0.0% | -1.000 | -1.392 | 0.43 | 1.00 |
| `lit_chain_fvg` | A | stop_gap | 2 | 0.0% | -1.393 | -2.315 | 0.65 | 1.39 |
| `lit_chain_fvg` | A | target | 31 | 96.8% | +1.937 | +1.599 | 1.94 | 0.31 |
| `lit_chain_fvg` | A | time | 194 | 57.2% | +0.242 | +0.156 | 0.66 | 0.37 |
| `lit_chain_fvg` | B | stop | 36 | 0.0% | -1.000 | -2.210 | 0.50 | 1.00 |
| `lit_chain_fvg` | B | stop_gap | 5 | 0.0% | -1.030 | -2.834 | 0.48 | 1.03 |
| `lit_chain_fvg` | B | target | 20 | 95.0% | +1.997 | +1.412 | 2.00 | 0.46 |
| `lit_chain_fvg` | B | time | 73 | 50.7% | +0.153 | +0.038 | 0.65 | 0.35 |
| `sweep_reversal_control` | A | stop | 2836 | 0.0% | -1.000 | -1.414 | 0.56 | 1.00 |
| `sweep_reversal_control` | A | stop_gap | 18 | 0.0% | -1.166 | -3.145 | 0.58 | 1.17 |
| `sweep_reversal_control` | A | target | 1168 | 95.5% | +2.000 | +1.582 | 2.01 | 0.40 |
| `sweep_reversal_control` | A | time | 520 | 61.7% | +0.395 | +0.285 | 1.14 | 0.53 |
| `sweep_reversal_control` | B | stop | 1082 | 0.0% | -1.000 | -1.843 | 0.58 | 1.00 |
| `sweep_reversal_control` | B | stop_gap | 74 | 0.0% | -1.090 | -3.812 | 0.54 | 1.09 |
| `sweep_reversal_control` | B | target | 542 | 77.5% | +2.000 | +0.704 | 2.01 | 0.39 |
| `sweep_reversal_control` | B | time | 179 | 63.7% | +0.352 | +0.246 | 1.14 | 0.56 |

## Costs

| symbol | cost per side | mean round-trip cost in R | median stop distance (bp of price) |
|---|---|---|---|
| SPY | 1 bp | 0.148 | 15.4 |
| QQQ | 1 bp | 0.114 | 22.6 |
| IWM | 1 bp | 0.109 | 24.4 |
| GLD | 1.5 bp | 0.216 | 16.2 |
| BTC/USD | 30 bp | 1.868 | 46.6 |

## How the spec was read

Each point is a choice the spec left open, fixed in code before the run.

1. ETF structure is built from regular-hours minutes only (pre- and post-market bars are dropped before resampling), so PDH / PDL are regular-session highs and lows. BTC uses every minute; its day is the UTC date.
2. `extract_events` gets only ts/open/high/low/close/volume at default parameters, so there are no session events and no PSH / PSL pools: the pools are EQH, EQL, PDH, PDL.
3. An event is usable once its bar has closed (docs/market-structure.md), not at the bar's open. Entry is at or after the close of every 15m and 2m bar the plan used.
4. 'At or after the mitigation' (step 4): the 2m rejection bar must close at or after the close of the 15m bar that mitigated the zone. A rejection inside the mitigating 15m bar does not count unless it closes with it.
5. 'A rejection at that zone' is a `rejection` event whose `ref_event_id` is the zone. The extractor attributes a bar to the newest matching zone only, so a wick into two overlapping zones counts for the newer one.
6. Step 2 takes the first `mss` whose `ref_event_id` is the sweep. `shift_failed` / `zone_dead`: the `mss_failed` or the zone's terminal event (ob_invalidated / ob_consumed / ob_expired, fvg_inverted) is known at or before the entry instant, or before the step at which the chain would otherwise have stopped (the 26-bar deadline for `no_retrace`; any time for `no_trigger`). If both apply the earlier one is logged; a tie logs `shift_failed`.
7. 'Within 26 15m bars of the shift' counts bars of the 15m frame (for ETFs 26 bars is one regular session), not clock time.
8. Card 2: the gap is the latest bullish/bearish `fvg_formed` whose bar is from the sweep bar to one bar after the shift bar, inclusive. 'Trade back into the gap' is the first 15m bar after both the gap and the shift whose low is at or below the gap's top (longs; mirrored for shorts), at most 26 bars after the shift. A gap that ages out (300 bars) without a rejection logs `no_trigger`.
9. Card 3: a closed-back sweep qualifies when any pool the bar took (`meta.pool_ids`) is a PDH or PDL.
10. Stop distance is signed: an entry price at or beyond the stop also logs `stop_too_tight`.
11. Target pools: `pool_formed` levels on the opposite side (buy-side pools for longs) whose forming bar closed by entry, not pierced by any 15m bar closed by entry (a level whose pool the extractor replaced with a wider cluster still counts while unpierced), at least 1R beyond entry; the nearest one. Otherwise 2R.
12. Refusal order when several apply: `stop_too_tight`, `too_late`, `daily_cap`, `position_open`. A refused chain does not count towards the daily cap. Cap and one-position rule are per card and symbol.
13. ETF clock rules are measured from that day's close: no entry later than 30 minutes before it (15:30 on a normal day, 12:30 on a 13:00 close), out at the open of the minute 5 minutes before it (15:55 / 12:55). An entry bar that falls on a later day than its trigger (trigger in the day's last bar) logs `too_late`.
14. Time exits fill at the open of the first 1-minute bar at or after the exit instant (BTC: entry + 24h). If the data has no such bar before the close, the last bar's close is used.
15. The stop is checked before the target in every minute, including the entry minute. A minute that opens through the stop fills at its open; the target fills at the target price, never better.
16. A position is open through the minute in which its stop or target filled; a new entry needs a later minute. After a fill at a minute's open (gap, time exit) an entry at that same open is allowed.
17. Round-trip cost = per-side rate x (entry price + exit price). Win rate is the share of trades with net R > 0.
18. MFE / MAE use the full range of every minute before the exit minute, plus the exit minute's open and the exit price. MAE is reported as a positive number of R.
19. A trade belongs to the window of its entry day (New York date for ETFs, UTC date for BTC); a refusal to the window of its entry day if the chain got that far, else of its sweep bar. Daily blocks pool all symbols by that date. Sharpe = t / sqrt(window years), haircut as in research.leaderboard (no t below 8 trading days; a non-positive Sharpe is reported unhaircut).
20. Rule 4 counts a symbol with no window-B trades as not above 0.
21. Regime: SPY's last regular-session close against its 200-session simple average, both as of the session before the entry day (from the 1-minute data). 'unknown' for the first 200 sessions.

