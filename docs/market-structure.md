# Market-structure events

`swing_engine/features/market_structure.py`, `EXTRACTOR_VERSION = "2026-10-13"`. Plan: `docs/proposals/video-model-plan.md`, P1 item 6.
Tests: `tests/test_features_market_structure.py`.

This is a vocabulary, not a strategy. Nothing here has been shown to make money; the chain cards (P1 item 7) and the
gates decide that. The definitions are this engine's own explicit choices: ICT / "smart money" terms have no single
agreed definition, and the video shows names, not rules.

## Contract

- Input: the bars of **one symbol on one timeframe**, columns `ts, open, high, low, close, volume`, sorted by a unique
  `ts` (= bar open time). Optional `session` column. Non-finite prices, unsorted bars and unknown params raise.
- `extract_events(bars, symbol, timeframe, params=None)` returns one row per event, ordered by `ts_event`.
- `params` overrides a constant by its lower-case name (`{"swing_left": 5}`); `session_opens` is the only extra key.
- Speed: one forward pass per family, O(n log n) at worst. 100,000 two-minute bars (about a year of one symbol)
  take about 0.45 s and give about 124,000 events on a fat-tailed random walk (Apple-silicon Mac, one core).

### No look-ahead

- **`ts_event` is the bar whose close completes the event. A consumer may act on an event only after that bar has
  closed** (`ts_event` + one bar length, since `ts` is the bar's open time).
- An event reads only bars up to and including `ts_event`. Cutting the input at any bar T leaves every event with
  `ts_event <= T` identical (same ids, same fields). The test checks this for every kind at 65 cut points.
- Nothing is ever revised: a later fact is a new event that points back (`ref_event_id`), never an edit.
- **ATR** everywhere below means Wilder ATR(`ATR_PERIOD`) **of the previous bar**, so a candle is not measured against
  a range it inflated itself. During the first 14 bars there is no ATR and every rule that needs one stays silent.

### Columns

| column | meaning |
|---|---|
| `event_id` | 16-hex hash of kind, symbol, timeframe, `ts_anchor`, direction, label, level (and the pool label for sweeps). It does not depend on the confirm bar, the params or the version. |
| `kind`, `symbol`, `timeframe` | |
| `ts_event` | bar that completes the event (see above) |
| `ts_anchor` | bar of the pivot / candle / level the event is about |
| `direction` | `bull`, `bear` or None (per kind, below) |
| `label` | sub-type: `HH/HL/LH/LL`, `BOS/CHoCH`, `EQH/EQL/PDH/PDL/PSH/PSL`, `closed_back/acceptance`, `held/failed`, session name |
| `level` | the single price the event is about |
| `high`, `low` | the event bar's high / low (or a leg's extremes), where stated |
| `zone_low`, `zone_high` | the zone, where the event has one |
| `strength` | size in ATR multiples (or a wick share for `rejection`), where stated |
| `ref_event_id` | lineage: the earlier event this one refers to |
| `meta` | small dict of extras |

Frame-level: `events.attrs["extractor_version"]`.

## Thresholds

All are **engine choices** unless a source is named. None has been tuned on data.

| constant | value | used by | source |
|---|---|---|---|
| `ATR_PERIOD` | 14 | everything | Wilder (1978) default |
| `SWING_LEFT`, `SWING_RIGHT` | 3, 3 | swings | engine choice (same strict-pivot rule as `features.extra.last_pivot`) |
| `ZIGZAG_ATR_MULT` | 3.0 | zigzag | engine choice |
| `DISPLACEMENT_ATR_MULT` | 1.5 | mss, order blocks | engine choice; the video's one example reads "disp 1.57 held", which is consistent with 1.5 but does not prove it |
| `MSS_FAIL_BARS` | 20 | mss_failed | engine choice |
| `MSS_SWEEP_LOOKBACK_BARS` | 50 | mss lineage | engine choice |
| `EQ_TOLERANCE_ATR_MULT` | 0.1 | equal highs / lows | engine choice |
| `MANIP_ATR_MULT` | 1.5 | manip_leg | the video's vocabulary page says "at least 1.5x the engine's factor"; which factor is unknown, so ATR is the engine's reading |
| `INDUCEMENT_MAX_ATR_MULT` | 5.0 | inducement | engine choice |
| `FVG_MIN_ATR_MULT` | 0.1 | fvg_formed | engine choice |
| `FVG_MAX_AGE_BARS`, `IFVG_MAX_AGE_BARS` | 300, 300 | fvg_inverted, ifvg_retest | engine choice |
| `OB_LOOKBACK_BARS` | 10 | ob_confirmed | engine choice |
| `OB_MAX_AGE_BARS` | 200 | ob_expired | engine choice |
| `REJECTION_WICK_FRAC` | 0.5 | rejection | engine choice |

## Swings

**`swing_high` / `swing_low`**. Bar *i* is a swing high when its high is strictly above the highs of the `SWING_LEFT`
bars before it and the `SWING_RIGHT` bars after it (lows mirror). `ts_anchor` = bar *i*, `ts_event` = bar
*i* + `SWING_RIGHT`, `level` = the pivot price, `direction` None.
`label`: a swing high is `HH` if above the previous confirmed swing high, else `LH` (equal counts as `LH`); a swing
low is `LL` if below the previous swing low, else `HL`. The first swing of each side has no label.

**`zigzag`**. One event per completed leg. Starting from the first bar with an ATR, track the running high; the high
is confirmed on the first later bar whose low is at least `ZIGZAG_ATR_MULT` x ATR below it (a bar that makes a new
high cannot confirm it). Then the running low is tracked the same way, and so on. The event is the leg that ends at
the newly confirmed extreme: `ts_anchor` = bar of that extreme, `ts_event` = the confirming bar, `direction` = `bull`
for a leg ending at a high, `level` = the extreme, `high` / `low` = the leg's two ends, `strength` = leg size in ATR,
`meta.leg_start`. The very first extreme starts no leg and emits nothing.

## Structure

State: the latest confirmed, not-yet-broken swing high and swing low, and a trend (none / up / down). A swing
confirmed on bar *t* becomes the reference from bar *t* + 1; older unbroken swings are dropped.

**`structure_break`**. A bar **closes** above the reference swing high (`bull`) or below the reference swing low
(`bear`). `label` = `CHoCH` if the trend was the opposite way, else `BOS` (including the first break, when there is no
trend yet). The trend becomes the break's direction. Each swing can be broken once, so there is one event per physical
break. `ts_anchor` = the broken swing's bar, `level` = its price, `strength` = the breaking candle's body in the
break's direction / ATR, `ref_event_id` = the swing.

**`mss`**. A `CHoCH` whose breaking candle is a displacement candle: body (in the break's direction) >=
`DISPLACEMENT_ATR_MULT` x ATR. Same bar, anchor, direction and level as the break. `strength` = the displacement.
Origin = the lowest low (bull) / highest high (bear) from the broken swing's bar to the breaking bar, stored in
`low` / `high` and `meta.origin`. `ref_event_id` = the latest sweep of the opposite side (sell-side for a bull MSS) at
most `MSS_SWEEP_LOOKBACK_BARS` bars back, or None when there was none (the video's "non-structural"). The break itself is
`meta.structure_break_id`.

**`mss_failed`**. Within `MSS_FAIL_BARS` bars after an MSS, a bar closes back beyond the origin (below it for a bull
MSS). `direction` = the failed MSS's direction, `ts_anchor` = the MSS bar, `level` = the origin, `ref_event_id` = the MSS.

## Liquidity

Side: `BSL` (buy-side, resting above price) or `SSL` (sell-side, below), in `meta.side`.

**`pool_formed`**, `direction` None, `label`:
- `EQH` / `EQL`: when a swing high is confirmed, it is grouped with the still-unpierced swing highs directly above it
  that lie within `EQ_TOLERANCE_ATR_MULT` x ATR. `level` = the highest of the group (the price that must be exceeded to
  take it), `zone_low..zone_high` = the group's span, `ts_anchor` = the newest pivot, `meta.swing_ids`, `meta.n_swings`.
  If a member already belonged to a live pool, the new pool replaces it (`ref_event_id` = the replaced pool), so a level
  never carries two live pools.
- `PDH` / `PDL`: the previous calendar day's high / low (calendar date of `ts` on its own clock). `ts_anchor` = the
  bar that made it. `ts_event` = **the first bar of the next day**: without a calendar the extractor only knows a day
  is over when the next one starts.
- `PSH` / `PSL`: the same for the previous session, when sessions are known (see `session_open`).

A pool stays live until it is pierced. Pools do not expire with age.

**`sweep`** and **`pool_swept`**. A bar's high goes strictly above a live BSL pool's level (low strictly below an SSL
level). The pool is then dead, so there is one event per physical pierce.
- `pool_swept`: one per pool taken. `ref_event_id` = the pool, `level` = its level, `ts_anchor` = its anchor.
- `sweep`: one per bar and side, however many pools the bar took. It refers to the nearest pool (the first one hit);
  all of them are in `meta.pool_ids`. `high` / `low` = the bar, `strength` = the pierce depth past that pool in ATR.
- `label`: `closed_back` when the same bar closes back at or inside the level, `acceptance` when it closes beyond.
- `direction`: the side opposite the liquidity taken (`bear` for buy-side), i.e. the reversal a closed-back sweep sets up.

**`manip_leg`**. The bar that takes a pool is itself a displacement candle in the direction of the take: body >=
`MANIP_ATR_MULT` x ATR (up candle through buy-side, down candle through sell-side). `direction` = the candle's,
`strength` = body / ATR, `ref_event_id` = the sweep.

**`inducement`**. A bar pierces a confirmed, unpierced swing that belongs to no pool (a minor swing), does **not**
take a pool on that side on the same bar, and the nearest live pool beyond it is within `INDUCEMENT_MAX_ATR_MULT` x
ATR. `ts_anchor` = the minor swing (the furthest one, if the bar took several), `level` = its price, `direction` as
for sweeps, `strength` = distance to the pool in ATR, `ref_event_id` = that pool, `meta.swing_id`.

## Imbalance

**`fvg_formed`**. Three candles: bullish when the third candle's low is above the first candle's high (bearish:
third high below first low) and the gap is >= `FVG_MIN_ATR_MULT` x ATR. Zone = the gap. `ts_anchor` = the middle
candle, `ts_event` = the third candle. `strength` = gap / ATR.

**`fvg_inverted`**. Within `FVG_MAX_AGE_BARS` bars, a bar closes through the far side of the gap (below a bullish
gap's `zone_low`). `direction` = the **new** polarity (a bullish gap closed through becomes `bear`), `level` = the
edge closed through, `ref_event_id` = the gap. A gap is inverted at most once. Partial fills are not events.

**`ifvg_retest`**. The first later bar (within `IFVG_MAX_AGE_BARS` of the inversion) that trades back into the
inverted gap. `label` = `held` if it closes without going out through the other side, else `failed`. One per inverted
gap. `ref_event_id` = the inversion.

## Zones (order blocks)

**`ob_confirmed`**. A `structure_break` (BOS or CHoCH) whose breaking candle is a displacement candle
(`DISPLACEMENT_ATR_MULT`). The order block is the last opposite-colour candle in the `OB_LOOKBACK_BARS` bars before the
break (last down candle before a bullish break). Zone = that candle's full low..high. Required: the breaking bar
closes beyond the zone, and that candle is not already an order block of the same direction. `ts_anchor` = the
candle, `ts_event` = the breaking bar, `strength` = the displacement, `ref_event_id` = the break.

Lifecycle, from the bar after confirmation (all refer to the `ob_confirmed` event):
- **`ob_mitigated`**: the first bar that trades into the zone. Once only; the block stays live.
- **`ob_invalidated`**: a bar closes through the far side of the zone. Terminal.
- **`ob_consumed`**: a bar trades through the whole zone (reaches the far side) but closes back inside or on the near
  side. Terminal: the zone has been fully traded.
- **`ob_expired`**: `OB_MAX_AGE_BARS` bars after confirmation with no terminal event (mitigated or not). Terminal.

Each block gets exactly one terminal event if the data runs long enough. A bar can mitigate and end a block at once.

## Other

**`session_open`**. The first bar of a session, `label` = the session name, `level` = that bar's open. Sessions come
from a `session` column (a new session starts when the value changes; null = no session) or from
`params["session_opens"] = {"london": "03:00", "ny": "09:30"}` (times on the clock of `ts`). The first bar of the data
never emits one. The session that just ended yields the `PSH` / `PSL` pools on the same bar.

**`rejection`** (the lower-timeframe entry trigger; the video's `rejection_2m`). A bar that wicks into a live zone and
is turned away. Bullish: the lower wick (`min(open, close) - low`) is >= `REJECTION_WICK_FRAC` of the bar's range, the
low is at or inside the zone's top, and the close is not below the zone's bottom. Bearish mirrors. Zones: a fair
value gap from the bar after it forms until it is inverted or `FVG_MAX_AGE_BARS` old; an inverted gap (new
polarity) for `IFVG_MAX_AGE_BARS`; an order block from the bar after confirmation until its terminal event. At most
one per bar and direction, at the most recently formed matching zone. `zone_low/high` = the zone, `strength` = the
wick share, `ref_event_id` = the zone's event, `meta.zone_kind`.

`extract_events` uses the zones of the **same** timeframe. For the intended use (2-minute rejections at 15-minute
zones): `zones = extract_zones(htf_bars, ...)` then `rejections(ltf_bars, symbol, "2m", zones, zone_lag=htf_bar -
ltf_bar)`. `zone_lag` is required for correctness there: a higher-timeframe zone exists only once its bar has closed.

## Not built

- `manip_seq` (a run of candles that together take pools): the video gives no rule for where a run starts or ends.
- The "fires / refusals / outcomes" chain: that is P1 items 7 and 8, built on these events.
- Pool expiry, partial-fill tracking of gaps, order-block "breaker" flips, volume in any rule (`volume` is required
  in the input but unused).
- Multi-symbol or multi-timeframe input: call once per symbol and timeframe.
