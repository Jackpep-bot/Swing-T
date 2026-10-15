# Pre-registration: intraday chain cards (video-model plan, P1 item 7)

Committed 2026-10-13 **before** any intraday replay exists. No chain has been run on any data; the extractor's
thresholds were set without looking at outcomes (`docs/market-structure.md`, `EXTRACTOR_VERSION = "2026-10-13"`).
Nothing below may change after the first replay except a harness-only amendment (a bug that stops the rules as
written from running), written into this file before results are read.

## Why
Jack's reference video shows an intraday "liquidity sweep -> structure shift -> order block" engine and reports only
gross R. There is no peer-reviewed evidence the style beats costs. This group tests it under the same rules as every
daily strategy: logged trials, costs, haircut, two windows.

## Data and markets
- 1-minute bars, Alpaca free SIP: SPY, QQQ, IWM, GLD (2016-01-01 on); BTC/USD Alpaca venue bars (2021-01-01 on).
- ETFs trade regular hours only (09:30-16:00 New York, early closes respected). BTC/USD trades all hours.
- Structure timeframe 15m, trigger timeframe 2m, both resampled with `data.intraday.resample` (complete bars only).
- Events from `features.market_structure.extract_events` at default parameters. An event may be used only at or
  after its `ts_event`.

## Cards (3)
All trade both directions. `d` is the trade direction.

### 1. `lit_chain_ob`
1. **Sweep.** A 15m `sweep` labelled `closed_back`, direction `d`, of any pool.
2. **Shift.** A 15m `mss` in direction `d` whose `ref_event_id` is that sweep, with no `mss_failed` for it before entry.
3. **Zone.** The 15m `ob_confirmed` in direction `d` that refers to that shift's structure break. Price must trade back
   into the zone (`ob_mitigated`) within 26 15m bars of the shift; the zone must not be invalidated, consumed or expired.
4. **Trigger.** The first 2m `rejection` in direction `d` at that zone at or after the mitigation
   (`rejections(..., zone_lag=13 minutes)`).
- Entry: open of the next 2m bar after the rejection's `ts_event`.
- Stop: the sweep bar's extreme (low for longs, high for shorts) less/plus one tick ($0.01 ETFs, $1 BTC).
- Target: the nearest pool level on the opposite side that is unswept at entry and at least 1R from entry; if none, 2R.

### 2. `lit_chain_fvg`
Steps 1 and 2 as card 1. Step 3: the most recent 15m `fvg_formed` in direction `d` with `ts_event` between the sweep and
one bar after the shift; price must trade back into the gap within 26 15m bars; the gap must not be inverted. Step 4,
entry, stop and target as card 1, with the gap as the zone.

### 3. `sweep_reversal_control`
The control: does the chain add anything to the bare sweep? A 15m `sweep` labelled `closed_back` of a `PDH` or `PDL`
pool, direction `d`. Entry at the open of the next 15m bar. Stop as card 1. Target 2R.

### Rules common to all cards
- A chain that stops at a step logs a refusal naming the step: `no_shift`, `shift_failed`, `no_zone`, `no_retrace`,
  `zone_dead`, `no_trigger`, `stop_too_tight` (stop distance under 0.05% of price), `no_room` (does not apply: 2R
  fallback), `daily_cap`, `position_open`, `too_late`.
- At most 5 entries per symbol per day (New York date for ETFs, UTC date for BTC); one open position per symbol.
- ETFs: no entry after 15:30; any open position is closed at the open of the 15:55 bar. BTC: closed 24 hours after entry.
- Risk unit R = |entry - stop|. No sizing: results are in R.

## Simulation and costs
- Walked on 1-minute bars from the entry minute. If a minute's range contains both stop and target, the stop fills.
  A gap through the stop fills at that minute's open.
- Costs per side, charged on entry and exit, as fixed constants in the grader:
  SPY, QQQ, IWM 1.0 bp; GLD 1.5 bp (half spread plus slippage; commission free);
  BTC/USD 25 bp taker fee plus 5 bp slippage. Net R = gross R - round-trip cost / stop distance.
- Reported per card and window: trades, win rate, gross R, net R, MFE and MAE in R, refusals by step, per-symbol
  rows, and by SPY daily regime (descriptive only).

## Windows and trials
- Window A: 2016-01-01 .. 2023-12-31. Window B: 2024-01-01 .. 2026-10-09. BTC joins from 2021-01-01.
- Primary result per card: all five symbols pooled. 3 cards x 2 windows = **6 trials**, logged to `data/trials.jsonl`
  with tag `intraday-chains`; the haircut uses every trial logged to date plus these.
- One run. Per-symbol and per-direction rows are descriptive and cannot rescue a card.

## Pass rule (per card)
PASS needs all of:
1. at least 200 trades in each window;
2. pooled net R per trade above 0 in both windows;
3. Harvey-Liu haircut Sharpe above 0 in both windows, t-stats on daily blocks (mean net R per trading day);
4. net R above 0 on at least 3 of the 5 symbols in window B.
Otherwise FAIL. For cards 1 and 2 the results also state whether net R beats the control's in both windows.

## What a pass allows
Walk-forward and shadow-only tracking. Paper trading of an intraday card additionally needs `docs/gates.md` and the
owner's decision on an always-on host; neither is granted here.
