"""features.market_structure: hand-built sequences per family (expected events and their confirm bars written out
by hand from docs/market-structure.md), the truncation (no look-ahead) property for every kind, determinism, lineage.

Hand-built frames start with 16 flat bars (range 1.0, so ATR is ~1.0 and nothing fires); bars are numbered from 0 and
an expected event reads ``(kind, confirm bar, anchor bar, direction, label, level)``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import market_structure as ms

FLAT = (100.0, 100.5, 99.5, 100.0)
WARM = [FLAT] * 16
T0 = pd.Timestamp("2026-03-02 09:30", tz="America/New_York")
BAR = pd.Timedelta(minutes=2)
FAST = {"swing_left": 1, "swing_right": 1}  # 1-bar fractals keep the hand-built sequences short


def _mk(rows: list[tuple], start: pd.Timestamp = T0, next_day_from: int | None = None) -> pd.DataFrame:
    ts = [start + i * BAR for i in range(len(rows))]
    if next_day_from is not None:  # bars from this index on belong to the next calendar day
        ts = [t if i < next_day_from else t + pd.Timedelta(days=1) for i, t in enumerate(ts)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    df.insert(0, "ts", pd.DatetimeIndex(ts))
    return df.assign(volume=1000.0)


def _got(ev: pd.DataFrame, bars: pd.DataFrame, kinds: tuple[str, ...]) -> list[tuple]:
    pos = {t: i for i, t in enumerate(bars["ts"])}
    sub = ev[ev["kind"].isin(kinds)]
    return [(r.kind, pos[r.ts_event], pos[r.ts_anchor], r.direction, r.label, None if pd.isna(r.level) else r.level)
            for r in sub.itertuples()]


def _zones(ev: pd.DataFrame, kind: str) -> list[tuple]:
    return [(r.zone_low, r.zone_high) for r in ev[ev["kind"] == kind].itertuples()]


def _one(ev: pd.DataFrame, kind: str, **where) -> pd.Series:
    sub = ev[ev["kind"] == kind]
    for col, val in where.items():
        sub = sub[sub[col] == val]
    assert len(sub) == 1, f"{kind} {where}: {len(sub)} rows"
    return sub.iloc[0]


# ----------------------------------------------------------------------------------------------- swings
def test_swings_default_fractal_confirmed_three_bars_late():
    # each bar: high = x, low = x - 1. Highs peak at bar 19 (105) and bar 25 (104); lows trough at 22 and 30.
    xs = [101, 102, 103, 105, 103, 102, 101, 102, 103, 104, 103.5, 103, 102.5, 102, 101.5, 102, 103, 104]
    bars = _mk(WARM + [(x - 0.5, x, x - 1.0, x - 0.5) for x in xs])
    ev = ms.extract_events(bars, "TEST", "2m")
    assert _got(ev, bars, ("swing_high", "swing_low")) == [
        ("swing_high", 22, 19, None, None, 105.0),  # first swing high: nothing to compare with
        ("swing_low", 25, 22, None, None, 100.0),
        ("swing_high", 28, 25, None, "LH", 104.0),  # 104 < 105
        ("swing_low", 33, 30, None, "HL", 100.5),  # 100.5 > 100
    ]


def test_zigzag_leg_confirmed_by_atr_reversal():
    # centre p, bar = (p, p + .5, p - .5, p): up to 105.5 at bar 20, down to 96.5 at bar 24, back up.
    ps = [101, 102, 103, 104, 105, 103, 101, 99, 97, 99, 103]
    bars = _mk(WARM + [(p, p + 0.5, p - 0.5, p) for p in ps])
    ev = ms.extract_events(bars, "TEST", "2m")
    # the high (bar 20) is confirmed on bar 22 (low 100.5 is 5.0 below, ATR ~1.3) but is the first extreme: no leg.
    # the low (bar 24) is confirmed on bar 26 (high 103.5 is 7.0 above, ATR ~1.6): the down leg 105.5 -> 96.5.
    assert _got(ev, bars, ("zigzag",)) == [("zigzag", 26, 24, "bear", None, 96.5)]
    leg = _one(ev, "zigzag")
    assert (leg["high"], leg["low"], leg["meta"]["leg_start"]) == (105.5, 96.5, str(bars["ts"][20]))
    assert 9.0 / 2.5 < leg["strength"] < 9.0  # 9 points in ATRs; ATR is between 1 and 2.5 here


# ----------------------------------------------------------------------------------------------- structure, FVG, OB
STRUCTURE_ROWS = WARM + [
    (100.0, 101.0, 99.8, 100.8),   # 16
    (100.8, 102.0, 100.5, 101.5),  # 17 swing high 102.0 (confirmed 18)
    (101.5, 101.6, 100.6, 101.0),  # 18
    (101.0, 101.4, 100.2, 100.6),  # 19 swing low 100.2 (confirmed 20)
    (100.6, 101.8, 100.4, 101.6),  # 20
    (101.6, 103.0, 101.3, 102.8),  # 21 close 102.8 > 102.0: bullish BOS (no trend yet); body 1.2 is no displacement
    (102.8, 103.5, 102.6, 103.2),  # 22 swing high 103.5 (confirmed 23); low 102.6 > high[20] 101.8: bullish FVG
    (103.2, 103.3, 102.2, 102.4),  # 23
    (102.4, 102.9, 102.0, 102.7),  # 24 swing low 102.0 (confirmed 25)
    (102.7, 103.1, 102.3, 102.9),  # 25 swing high 103.1 (confirmed 26); the last up candle before bar 26
    (102.9, 103.0, 98.5, 98.8),    # 26 close 98.8 < 102.0 in an uptrend: bearish CHoCH, body 4.1 -> MSS + OB(25)
    (98.8, 99.5, 98.6, 99.3),      # 27 high 99.5 < low[25] 102.3: bearish FVG 99.5-102.3; swing low 98.5 confirmed
    (99.3, 101.0, 99.2, 100.8),    # 28
    (100.8, 103.6, 100.7, 103.4),  # 29 close 103.4 > MSS origin 103.1: failed; > swing high 103.1: bullish CHoCH+MSS
]


@pytest.fixture(scope="module")
def structure_case():
    bars = _mk(STRUCTURE_ROWS)
    return bars, ms.extract_events(bars, "TEST", "2m", FAST)


def test_swing_labels(structure_case):
    bars, ev = structure_case
    assert _got(ev, bars, ("swing_high", "swing_low")) == [
        ("swing_high", 18, 17, None, None, 102.0),
        ("swing_low", 20, 19, None, None, 100.2),
        ("swing_high", 23, 22, None, "HH", 103.5),
        ("swing_low", 25, 24, None, "HL", 102.0),
        ("swing_high", 26, 25, None, "LH", 103.1),
        ("swing_low", 27, 26, None, "LL", 98.5),
    ]


def test_bos_choch_mss_and_failed_mss(structure_case):
    bars, ev = structure_case
    assert _got(ev, bars, ("structure_break", "mss", "mss_failed")) == [
        ("structure_break", 21, 17, "bull", "BOS", 102.0),
        ("structure_break", 26, 24, "bear", "CHoCH", 102.0),
        ("mss", 26, 24, "bear", None, 102.0),
        ("mss_failed", 29, 26, "bear", None, 103.1),  # level = the MSS origin: highest high of bars 24..26
        ("structure_break", 29, 25, "bull", "CHoCH", 103.1),
        ("mss", 29, 25, "bull", None, 103.1),
    ]
    bear, bull = _one(ev, "mss", direction="bear"), _one(ev, "mss", direction="bull")
    assert bear["high"] == 103.1 and bear["meta"]["origin"] == 103.1
    assert bull["low"] == 98.5  # lowest low of bars 25..29
    assert bear["strength"] >= ms.DISPLACEMENT_ATR_MULT and bull["strength"] >= ms.DISPLACEMENT_ATR_MULT
    assert pd.isna(bear["ref_event_id"]) and pd.isna(bull["ref_event_id"])  # no pool was swept before either
    choch = _one(ev, "structure_break", direction="bear")
    assert bear["meta"]["structure_break_id"] == choch["event_id"]
    assert choch["ref_event_id"] == _one(ev, "swing_low", level=102.0)["event_id"]
    assert _one(ev, "mss_failed")["ref_event_id"] == bear["event_id"]
    bos = _one(ev, "structure_break", label="BOS")
    assert bos["strength"] < ms.DISPLACEMENT_ATR_MULT  # 1.2 points on an ATR of ~1.1


def test_fvg_formed_inverted_retested(structure_case):
    bars, ev = structure_case
    assert _got(ev, bars, ("fvg_formed", "fvg_inverted", "ifvg_retest")) == [
        ("fvg_formed", 22, 21, "bull", None, None),  # anchor = the middle candle
        ("fvg_inverted", 26, 21, "bear", None, 101.8),  # close 98.8 < 101.8: now a bearish inverted gap
        ("fvg_formed", 27, 26, "bear", None, None),
        ("ifvg_retest", 29, 21, "bear", "failed", None),  # high 103.6 is back in 101.8-102.6 but the close is above it
        ("fvg_inverted", 29, 26, "bull", None, 102.3),  # close 103.4 > 102.3
        ("fvg_formed", 29, 28, "bull", None, None),  # low 100.7 > high[27] 99.5
    ]
    assert _zones(ev, "fvg_formed") == [(101.8, 102.6), (99.5, 102.3), (99.5, 100.7)]
    first = ev[ev["kind"] == "fvg_formed"].iloc[0]
    assert _one(ev, "fvg_inverted", direction="bear")["ref_event_id"] == first["event_id"]
    assert _one(ev, "ifvg_retest")["ref_event_id"] == _one(ev, "fvg_inverted", direction="bear")["event_id"]


def test_ifvg_retest_held():
    # same bullish gap (101.8-102.6) inverted on bar 26; bar 27 trades back into it and closes inside: held
    bars = _mk(STRUCTURE_ROWS[:27] + [(98.8, 102.0, 98.7, 101.9)])
    ev = ms.extract_events(bars, "TEST", "2m", FAST)
    assert _got(ev, bars, ("ifvg_retest",)) == [("ifvg_retest", 27, 21, "bear", "held", None)]


def test_order_block_lifecycle(structure_case):
    bars, ev = structure_case
    kinds = ("ob_confirmed", "ob_mitigated", "ob_invalidated", "ob_consumed", "ob_expired")
    assert _got(ev, bars, kinds) == [
        ("ob_confirmed", 26, 25, "bear", None, None),  # bar 25 = last up candle before the displacement break
        ("ob_mitigated", 29, 25, "bear", None, None),  # high 103.6 returns into 102.3-103.1
        ("ob_invalidated", 29, 25, "bear", None, None),  # and closes above 103.1
        ("ob_confirmed", 29, 26, "bull", None, None),  # bar 26 = last down candle before the bullish break
    ]
    assert _zones(ev, "ob_confirmed") == [(102.3, 103.1), (98.5, 103.0)]
    ob = _one(ev, "ob_confirmed", direction="bear")
    assert ob["ref_event_id"] == _one(ev, "structure_break", direction="bear")["event_id"]
    assert set(ev.loc[ev["kind"].isin(kinds[1:3]), "ref_event_id"]) == {ob["event_id"]}


def test_order_block_consumed_and_expired():
    head = STRUCTURE_ROWS[:27]  # bearish OB 102.3-103.1 confirmed on bar 26
    # bar 27 wicks through the whole zone (high 103.2 >= 103.1) but closes back below it: mitigated + consumed
    bars = _mk(head + [(98.8, 103.2, 98.7, 99.0)])
    ev = ms.extract_events(bars, "TEST", "2m", FAST)
    assert _got(ev, bars, ("ob_mitigated", "ob_consumed", "ob_invalidated")) == [
        ("ob_mitigated", 27, 25, "bear", None, None), ("ob_consumed", 27, 25, "bear", None, None)]
    # price never returns: the block expires ob_max_age_bars (3 here) after its confirmation on bar 26
    bars = _mk(head + [(98.8, 99.0, 98.6, 98.8)] * 4)
    ev = ms.extract_events(bars, "TEST", "2m", {**FAST, "ob_max_age_bars": 3})
    assert _got(ev, bars, ("ob_mitigated", "ob_consumed", "ob_invalidated", "ob_expired")) == [
        ("ob_expired", 29, 25, "bear", None, None)]


# ----------------------------------------------------------------------------------------------- liquidity
LIQUIDITY_ROWS = [FLAT] * 10 + [(100.0, 100.5, 99.0, 100.0)] + [FLAT] * 5 + [  # day 1: high 100.5 (bar 0), low 99.0 (10)
    (100.0, 100.4, 99.6, 100.2),     # 16 first bar of day 2: PDH 100.5 and PDL 99.0 become pools
    (100.2, 101.2, 100.1, 101.0),    # 17 high 101.2 > PDH and closes above it: sweep, acceptance
    (101.0, 102.0, 100.9, 101.8),    # 18 swing high 102.0 (confirmed 19)
    (101.8, 101.9, 101.2, 101.4),    # 19
    (101.4, 101.6, 100.8, 101.0),    # 20 swing low 100.8
    (101.0, 101.95, 100.9, 101.7),   # 21 swing high 101.95 (confirmed 22): within 0.1 ATR of 102.0 -> EQH pool
    (101.7, 101.8, 101.0, 101.2),    # 22
    (101.2, 101.3, 100.95, 101.1),   # 23 swing low 100.95 (0.15 above 100.8: not equal lows)
    (101.1, 101.6, 101.0, 101.5),    # 24 swing high 101.6 (confirmed 25): a minor high under the pool
    (101.5, 101.55, 101.1, 101.2),   # 25
    (101.2, 101.8, 101.15, 101.7),   # 26 high 101.8 takes the minor high, not the pool at 102.0: inducement
    (101.7, 102.3, 101.6, 101.9),    # 27 high 102.3 > 102.0, close 101.9 back under it: sweep, closed_back
    (101.9, 102.0, 98.2, 98.4),      # 28 low 98.2 < PDL 99.0, close below, body 3.5: sweep acceptance + manip_leg
]


def test_pools_sweeps_inducement_and_manip_leg():
    bars = _mk(LIQUIDITY_ROWS, next_day_from=16)
    ev = ms.extract_events(bars, "TEST", "2m", FAST)
    kinds = ("pool_formed", "pool_swept", "sweep", "manip_leg", "inducement")
    assert _got(ev, bars, kinds) == [
        ("pool_formed", 16, 0, None, "PDH", 100.5),
        ("pool_formed", 16, 10, None, "PDL", 99.0),
        ("sweep", 17, 0, "bear", "acceptance", 100.5),
        ("pool_swept", 17, 0, "bear", "acceptance", 100.5),
        ("pool_formed", 22, 21, None, "EQH", 102.0),
        ("inducement", 26, 24, "bear", None, 101.6),
        ("sweep", 27, 21, "bear", "closed_back", 102.0),
        ("pool_swept", 27, 21, "bear", "closed_back", 102.0),
        ("sweep", 28, 10, "bull", "acceptance", 99.0),
        ("pool_swept", 28, 10, "bull", "acceptance", 99.0),
        ("manip_leg", 28, 28, "bear", None, 99.0),
    ]
    eqh = _one(ev, "pool_formed", label="EQH")
    assert (eqh["zone_low"], eqh["zone_high"], eqh["meta"]["side"], eqh["meta"]["n_swings"]) == (101.95, 102.0, "BSL", 2)
    assert eqh["meta"]["swing_ids"] == [_one(ev, "swing_high", level=lv)["event_id"] for lv in (102.0, 101.95)]
    assert _one(ev, "pool_formed", label="PDL")["meta"]["side"] == "SSL"
    assert _one(ev, "inducement")["ref_event_id"] == eqh["event_id"]
    assert _one(ev, "inducement")["meta"]["swing_id"] == _one(ev, "swing_high", level=101.6)["event_id"]
    sweep = _one(ev, "sweep", label="closed_back")
    assert sweep["ref_event_id"] == eqh["event_id"] and sweep["high"] == 102.3
    assert _one(ev, "pool_swept", label="closed_back")["meta"]["sweep_id"] == sweep["event_id"]
    manip = _one(ev, "manip_leg")
    assert manip["ref_event_id"] == _one(ev, "sweep", direction="bull")["event_id"]
    assert manip["strength"] >= ms.MANIP_ATR_MULT


def test_mss_follows_the_sweep_it_came_after():
    # the bar-28 sell-side sweep is followed by a bullish CHoCH with displacement: the MSS points back to it
    rows = LIQUIDITY_ROWS + [(98.4, 98.9, 98.3, 98.8), (98.8, 103.0, 98.7, 102.9)]
    bars = _mk(rows, next_day_from=16)
    ev = ms.extract_events(bars, "TEST", "2m", FAST)
    mss = _one(ev, "mss", direction="bull")
    assert bars["ts"].tolist().index(mss["ts_event"]) == 30
    assert mss["ref_event_id"] == _one(ev, "sweep", direction="bull")["event_id"]


@pytest.mark.parametrize("how", ["column", "open_times"])
def test_session_open_and_prior_session_pools(how):
    rows = [FLAT] * 5 + [(100.0, 101.0, 99.5, 100.0)] + [FLAT] * 10 + [(100.0, 100.4, 99.6, 100.2)] * 2
    bars = _mk(rows, start=pd.Timestamp("2026-03-02 02:28", tz="Europe/London"))  # bar 16 opens at 03:00
    params = None
    if how == "column":
        bars["session"] = ["asia"] * 16 + ["london"] * 2
    else:
        params = {"session_opens": {"london": "03:00", "ny": "09:30"}}
    ev = ms.extract_events(bars, "TEST", "2m", params)
    assert _got(ev, bars, ("session_open", "pool_formed")) == [
        ("session_open", 16, 16, None, "london", 100.0),
        ("pool_formed", 16, 5, None, "PSH", 101.0),
        ("pool_formed", 16, 0, None, "PSL", 99.5),
    ]


# ----------------------------------------------------------------------------------------------- rejection
REJECTION_ROWS = WARM + [
    (100.0, 100.6, 99.9, 100.5),    # 16
    (100.5, 103.0, 100.4, 102.9),   # 17
    (102.9, 103.5, 102.0, 103.2),   # 18 low 102.0 > high[16] 100.6: bullish FVG 100.6-102.0
    (103.2, 103.4, 101.5, 103.0),   # 19 low 101.5 is inside the gap, close above it, lower wick 1.5 of a 1.9 range
]


def test_rejection_at_a_zone_and_across_timeframes():
    bars = _mk(REJECTION_ROWS)
    ev = ms.extract_events(bars, "TEST", "2m")
    assert _got(ev, bars, ("rejection",)) == [("rejection", 19, 19, "bull", None, None)]
    rej, gap = _one(ev, "rejection"), _one(ev, "fvg_formed")
    assert rej["ref_event_id"] == gap["event_id"] and rej["meta"]["zone_kind"] == "fvg_formed"
    assert (rej["zone_low"], rej["zone_high"]) == (100.6, 102.0)
    assert rej["strength"] == pytest.approx(1.5 / 1.9)
    # bar 18 has a long lower wick too, but the gap is only confirmable at its close: no rejection on bar 18
    zones = ms.extract_zones(bars, "TEST", "2m")
    assert zones["ts_from"].tolist() == [bars["ts"][18]] and zones["ts_to"].isna().all()
    again = ms.rejections(bars, "TEST", "2m", zones)
    pd.testing.assert_frame_equal(again, ev[ev["kind"] == "rejection"].reset_index(drop=True))
    # a zone that becomes known one bar later (higher-timeframe close) cannot be rejected on bar 19
    assert ms.rejections(bars, "TEST", "2m", zones, zone_lag=BAR).empty


# ----------------------------------------------------------------------------------------------- properties
def _random_walk(n: int, seed: int) -> pd.DataFrame:
    """Fat-tailed 2-minute random walk, 195 bars per New York session, with an am / pm ``session`` column."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.standard_t(4, n) * 0.0006))
    open_ = np.r_[close[0], close[:-1]] * (1.0 + rng.normal(0.0, 0.0001, n))
    high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0.0, 0.0004, n)))
    low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0.0, 0.0004, n)))
    days = pd.bdate_range("2026-01-05", periods=n // 195 + 1, tz="America/New_York")
    ts = (days.repeat(195) + pd.to_timedelta(np.tile(np.arange(195) * 2 + 570, len(days)), unit="m"))[:n]
    out = pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": 1000.0})
    out["session"] = np.where(out["ts"].dt.hour < 12, "am", "pm")
    return out


N_WALK = 4000
N_CUTS = 60


@pytest.fixture(scope="module")
def walk():
    bars = _random_walk(N_WALK, seed=7)
    return bars, ms.extract_events(bars, "RW", "2m")


def test_every_kind_occurs_on_the_random_walk(walk):
    _, ev = walk
    assert set(ev["kind"]) == set(ms.KINDS)  # so the properties below cover all of them
    assert list(ev.columns) == list(ms.EVENT_COLUMNS) and ev.attrs["extractor_version"] == ms.EXTRACTOR_VERSION


@pytest.mark.parametrize("params", [None, FAST], ids=["default", "fast_swings"])
def test_truncation_leaves_past_events_unchanged(walk, params):
    bars, full = walk
    if params is not None:
        full = ms.extract_events(bars, "RW", "2m", params)
    cuts = np.random.default_rng(1).integers(1, N_WALK, N_CUTS).tolist() + [1, 20, 195, 196, N_WALK]
    for k in cuts:
        cut = ms.extract_events(bars.iloc[:k], "RW", "2m", params)
        want = full[full["ts_event"] <= bars["ts"].iloc[k - 1]].reset_index(drop=True)
        pd.testing.assert_frame_equal(cut, want, check_exact=True, obj=f"events of the first {k} bars")
        assert cut["meta"].tolist() == want["meta"].tolist()


def test_events_never_precede_their_anchor_and_ids_are_unique(walk):
    _, ev = walk
    assert (ev["ts_event"] >= ev["ts_anchor"]).all()
    assert ev["event_id"].is_unique and ev["ts_event"].is_monotonic_increasing


def test_deterministic_ids(walk):
    bars, ev = walk
    again = ms.extract_events(bars.copy(), "RW", "2m")
    pd.testing.assert_frame_equal(again, ev, check_exact=True)
    other = ms.extract_events(bars, "RW2", "2m")
    assert not set(other["event_id"]) & set(ev["event_id"])  # the symbol is part of the id
    assert not set(ms.extract_events(bars, "RW", "5m")["event_id"]) & set(ev["event_id"])  # so is the timeframe


LINEAGE = {  # kind -> kinds its ref_event_id may point at (None: the reference is optional)
    "swing_high": (), "swing_low": (), "zigzag": (), "session_open": (), "fvg_formed": (),
    "pool_formed": ("pool_formed", None),  # a wider equal-highs cluster supersedes the earlier pool
    "pool_swept": ("pool_formed",), "sweep": ("pool_formed",), "manip_leg": ("sweep",),
    "inducement": ("pool_formed",), "structure_break": ("swing_high", "swing_low"),
    "mss": ("sweep", None), "mss_failed": ("mss",), "fvg_inverted": ("fvg_formed",),
    "ifvg_retest": ("fvg_inverted",), "ob_confirmed": ("structure_break",), "ob_mitigated": ("ob_confirmed",),
    "ob_invalidated": ("ob_confirmed",), "ob_expired": ("ob_confirmed",), "ob_consumed": ("ob_confirmed",),
    "rejection": ("fvg_formed", "fvg_inverted", "ob_confirmed"),
}


def test_lineage_points_at_an_earlier_existing_event(walk):
    _, ev = walk
    by_id = ev.set_index("event_id")
    assert set(LINEAGE) == set(ms.KINDS)
    for kind, allowed in LINEAGE.items():
        sub = ev[ev["kind"] == kind]
        has = sub["ref_event_id"].notna()
        if None not in allowed:
            assert has.all() if allowed else not has.any(), kind
        ref = by_id.loc[sub.loc[has, "ref_event_id"]]  # KeyError = a reference to an event that does not exist
        assert set(ref["kind"]) <= set(allowed), kind
        assert (ref["ts_event"].to_numpy() <= sub.loc[has, "ts_event"].to_numpy()).all(), kind
    assert ev.loc[ev["kind"] == "mss", "ref_event_id"].notna().any()  # some MSS do follow a sweep
    assert ev.loc[ev["kind"] == "pool_formed", "ref_event_id"].notna().any()


def test_bad_input_is_refused():
    bars = _mk(WARM)
    with pytest.raises(ValueError, match="unknown"):
        ms.extract_events(bars, "TEST", "2m", {"swing_lft": 2})
    with pytest.raises(ValueError, match="sorted"):
        ms.extract_events(bars.iloc[::-1], "TEST", "2m")
    with pytest.raises(ValueError, match="columns"):
        ms.extract_events(bars.drop(columns="volume"), "TEST", "2m")
    assert ms.extract_events(bars.iloc[:0], "TEST", "2m").empty
