"""The float-map hook on `monitor.smallcap.SmallCapTrack`: unknown or stale float => warnings only, never a long alert."""
from __future__ import annotations

from datetime import UTC, date, datetime

from swing_engine.core.models import Priority
from swing_engine.data.float_data import FloatInfo
from swing_engine.monitor.smallcap import (
    FLOAT_STALE_WARNING,
    FLOAT_UNKNOWN_WARNING,
    FloatRecord,
    SmallCapSnapshot,
    SmallCapTrack,
)

T_0800 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)  # 08:00 ET
FLOAT_SHARES = 8_000_000.0


def snap(**kw) -> SmallCapSnapshot:
    base = dict(symbol="TINY", now=T_0800, price=5.0, prev_close=4.0, float_m=None, market_cap_m=60.0,
                premarket_volume=400_000, cum_volume=2_500_000, adv_30d=400_000, catalyst=True, above_vwap=True)
    base.update(kw)
    return SmallCapSnapshot(**base)


def fresh(symbol: str = "TINY", **kw) -> FloatInfo:
    base = dict(symbol=symbol, shares_outstanding=12_500_000.0, float_shares=FLOAT_SHARES,
                float_estimate_method="edgar_public_float_div_price", as_of=date(2026, 8, 3),
                source="edgar_companyfacts", stale=False)
    base.update(kw)
    return FloatInfo(**base)


def test_float_info_satisfies_the_track_protocol():
    assert isinstance(fresh(), FloatRecord)


def test_fresh_float_from_map_enables_long_alert():
    track = SmallCapTrack({}, float_map={"tiny": fresh()})
    a = track.evaluate(snap())
    assert a.eligible_long and a.long_alert and a.grade == "A" and "float 8.0M" in a.message
    assert "float_unknown" not in a.eligibility_reasons and FLOAT_UNKNOWN_WARNING not in a.warnings


def test_stale_float_is_warnings_only():
    track = SmallCapTrack({})
    track.set_float_map({"TINY": fresh(stale=True, stale_reason="event:424B5@2026-09-01")})
    a = track.evaluate(snap(dilution_filed_today=True, vwap_lost=True, ssr_triggered=True))
    assert not a.eligible_long and a.eligible_warn and "float_stale" in a.eligibility_reasons
    assert not a.long_alert and a.runner_blockers == []  # the runner never ran
    assert FLOAT_STALE_WARNING in a.warnings and "float 8.0M (stale)" in a.message
    assert a.bagholder_alert and a.priority == Priority.P2  # warnings still flow


def test_stale_float_alone_blocks_an_otherwise_perfect_runner():
    track = SmallCapTrack({}, float_map={"TINY": fresh(stale=True)})
    a = track.evaluate(snap())
    assert not a.long_alert and a.eligibility_reasons == ["float_stale"] and a.warnings == [FLOAT_STALE_WARNING]
    assert a.priority == Priority.P1


def test_unknown_float_in_map_stays_unknown():
    track = SmallCapTrack({}, float_map={"TINY": FloatInfo(symbol="TINY")})
    a = track.evaluate(snap())
    assert not a.long_alert and "float_unknown" in a.eligibility_reasons and FLOAT_UNKNOWN_WARNING in a.warnings
    missing = SmallCapTrack({}, float_map={"OTHR": fresh("OTHR")}).evaluate(snap())
    assert "float_unknown" in missing.eligibility_reasons


def test_snapshot_float_wins_over_map_and_explicit_stale_flag_is_honoured():
    track = SmallCapTrack({}, float_map={"TINY": fresh(float_shares=30_000_000.0)})
    a = track.evaluate(snap(float_m=8.0))
    assert a.eligible_long and a.long_alert  # caller-supplied 8M float, not the map's 30M
    explicit = track.evaluate(snap(float_m=8.0, float_stale=True))
    assert not explicit.long_alert and "float_stale" in explicit.eligibility_reasons


def test_apply_float_is_pure_and_set_float_map_replaces():
    track = SmallCapTrack({}, float_map={"TINY": fresh()})
    s = snap()
    filled = track.apply_float(s)
    assert s.float_m is None and filled.float_m == 8.0 and filled.float_stale is False
    track.set_float_map(None)
    assert track.float_map == {} and track.apply_float(s) is s
