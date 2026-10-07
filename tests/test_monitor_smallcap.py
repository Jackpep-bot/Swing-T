from __future__ import annotations

from datetime import UTC, datetime

import pytest

from swing_engine.core.config import load_settings
from swing_engine.core.models import Priority
from swing_engine.monitor.smallcap import SmallCapSnapshot, SmallCapThresholds, SmallCapTrack
from tests.monitor_helpers import make_event

T_0800 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)  # 08:00 ET
T_0930 = datetime(2026, 10, 6, 13, 30, tzinfo=UTC)
T_1000 = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)
T_1100 = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)


def snap(**kw) -> SmallCapSnapshot:
    base = dict(symbol="TINY", now=T_0800, price=5.0, prev_close=4.0, float_m=8.0, market_cap_m=60.0,
                premarket_volume=400_000, cum_volume=2_500_000, adv_30d=400_000, catalyst=True, above_vwap=True)
    base.update(kw)
    return SmallCapSnapshot(**base)


def test_thresholds_load_from_settings_yaml():
    t = SmallCapThresholds.from_settings(load_settings().monitor.smallcap)
    assert t.rvol_min == 5.0 and t.max_float_m == 20.0 and t.gap_pct_a_grade == 20.0 and t.bagholder_alert_threshold == 6
    assert SmallCapThresholds.from_settings(None) == SmallCapThresholds()


def test_runner_grade_a_in_early_window():
    a = SmallCapTrack({}).evaluate(snap())
    assert a.eligible_long and a.long_alert and a.grade == "A" and a.priority == Priority.P2
    assert "RUNNER grade A" in a.message


def test_runner_grade_b_and_score_downs():
    t = SmallCapTrack({})
    b = t.evaluate(snap(price=4.6))  # +15% gap => B
    assert b.long_alert and b.grade == "B"
    down = t.evaluate(snap(reverse_split_recent=True))  # A with one score-down => B
    assert down.long_alert and down.grade == "B" and down.score_downs == ["reverse_split_recent"]
    b_down = t.evaluate(snap(price=4.6, reverse_split_recent=True))  # B with one score-down => no long
    assert not b_down.long_alert and b_down.runner_blockers == ["score_down_on_b_grade"]
    two = t.evaluate(snap(reverse_split_recent=True, prior_day_run_pct=350))
    assert not two.long_alert and two.runner_blockers == ["score_downs"]


@pytest.mark.parametrize(
    "kw,blocker",
    [
        ({"catalyst": False}, "no_catalyst"),
        ({"catalyst_is_offering": True}, "no_catalyst"),
        ({"dilution_filings_recent": 1}, "dilution_filing_recent"),
        ({"adv_30d": 2_000_000}, "rvol_below_min"),
        ({"premarket_volume": 10_000}, "premarket_volume_low"),
        ({"price": 4.3}, "gap_below_b_grade"),
        ({"above_vwap": False}, "below_vwap"),
        ({"now": T_1000}, "long_alert_expired"),
        ({"now": T_1100}, "after_never_long_cutoff"),
    ],
)
def test_runner_blockers(kw, blocker):
    a = SmallCapTrack({}).evaluate(snap(**kw))
    assert not a.long_alert and blocker in a.runner_blockers


def test_float_unknown_means_warnings_only():
    a = SmallCapTrack({}).evaluate(snap(float_m=None, dilution_filed_today=True, vwap_lost=True, ssr_triggered=True))
    assert not a.eligible_long and a.eligible_warn and "float_unknown" in a.eligibility_reasons
    assert not a.long_alert and a.bagholder_score == 6 and a.bagholder_alert and a.priority == Priority.P2
    assert "float unknown: warnings only" in a.warnings


def test_universe_gate_rejects_out_of_scope():
    t = SmallCapTrack({})
    big = t.evaluate(snap(price=45.0, prev_close=30.0))
    assert not big.eligible_warn and big.priority == Priority.P0 and "price_out_of_range" in big.eligibility_reasons
    assert "excluded_type" in t.universe_ok(snap(security_type="ETF"))[2]
    assert "not_listed" in t.universe_ok(snap(exchange="OTC"))[2]
    assert "market_cap_too_large" in t.universe_ok(snap(market_cap_m=500))[2]
    assert "float_too_large" in t.universe_ok(snap(float_m=25))[2]


def test_ramp_and_dump_promoted_blocklists_and_never_long():
    t = SmallCapTrack({})
    s = snap(ipo_months=6, ipo_price=4.5, ipo_proceeds_m=8.0, ipo_shares_m=1.5, offshore_holdco=True, microcap_underwriter=True,
             gain_5d_pct=80.0, filings_in_window=0)
    a = t.evaluate(s)
    assert a.structural_score == 7 and a.ramp_profile and a.ramp_behavioral and a.promoted and a.blocklisted
    assert not a.long_alert and "promoted / do not buy" in a.warnings and a.priority == Priority.P2
    assert "TINY" in t.blocklist
    quiet = t.evaluate(s.model_copy(update={"gain_5d_pct": 10.0, "gain_20d_pct": 10.0}))
    assert not quiet.promoted and quiet.ramp_profile
    news = t.ramp_and_dump(s.model_copy(update={"filings_in_window": 2}))
    assert news[1] is False
    held = t.evaluate(s.model_copy(update={"held": True}))
    assert held.priority == Priority.P3


def test_bagholder_scorer_weights():
    t = SmallCapTrack({})
    s = snap(now=T_1000, dilution_filed_today=True, going_concern=True, cum_volume=50_000_000, below_open_at_10=True,
             volume_falling=True, vwap_lost=True, up_halts_today=4, first_red_day_after_run=True, ssr_triggered=True,
             halt_codes_today=["T12"])
    score, reasons = t.bagholder_score(s, ramp_profile=False)
    assert score == 3 + 2 + 2 + 2 + 2 + 2 + 3 + 1 + 3
    assert set(reasons) == {"dilution_filing", "runway_or_going_concern", "float_rotation_extreme", "gap_and_crap",
                            "vwap_lost", "up_halts_exhaustion", "first_red_day", "ssr", "toxic_halt"}
    a = t.evaluate(s)
    assert a.toxic and a.bagholder_alert and not a.long_alert and "DO NOT HOLD" in a.message
    assert t.bagholder_score(snap(), ramp_profile=False) == (0, [])


def test_climax_zone_warning():
    a = SmallCapTrack({}).evaluate(snap(up_halts_today=2, cum_volume=9_000_000))  # rotation > 1x with 2 up-halts
    assert any(w.startswith("climax zone") for w in a.warnings) and not a.long_alert


def test_session_memory_from_events():
    t = SmallCapTrack({})
    t.observe(make_event("h1", kind="halt", symbols=["TINY"], meta={"reason_code": "LUDP", "status": "paused"}))
    t.observe(make_event("h2", kind="halt", symbols=["TINY"], meta={"reason_code": "LUDP", "status": "paused"}))
    t.observe(make_event("h3", kind="halt", symbols=["TINY"], meta={"reason_code": "LUDP", "status": "resumed"}))
    t.observe(make_event("f1", kind="filing", symbols=["TINY"], meta={"form_type": "8-K", "items": ["3.02"]}))
    t.observe(make_event("s1", kind="ssr", symbols=["TINY"]))
    st = t.session_state("TINY")
    assert st["up_halts"] == 2 and st["dilution"] is True and st["ssr"] is True and st["halt_codes"] == ["LUDP"]
    a = t.evaluate(snap())
    assert not a.long_alert and "dilution_filing_recent" in a.runner_blockers and "ssr" in a.bagholder_reasons
    t.observe(make_event("h4", kind="halt", symbols=["SCAM"], meta={"reason_code": "H10"}))
    assert "SCAM" in t.blocklist and "SCAM" in t.tainted
    t.reset_session()
    assert t.session_state("TINY") == {} and "SCAM" in t.tainted


def test_degraded_feed_is_flagged():
    a = SmallCapTrack({}).evaluate(snap(degraded_feed=True))
    assert a.degraded and "DEGRADED" in a.message
