from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from swing_engine.core.models import Priority
from swing_engine.monitor.smallcap import (
    CLASSIFIER_BAGHOLDER,
    CLASSIFIER_NONE,
    CLASSIFIER_RAMP,
    CLASSIFIER_RUNNER,
    FLOAT_UNKNOWN_WARNING,
    SmallCapTrack,
    assessment_meta,
    classify_assessment,
)
from tests.monitor_helpers import make_event

T_0800 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)  # 08:00 ET
T_1000 = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)


@dataclass
class Rec:
    float_shares: float | None
    stale: bool = False


def bar(sym="TINY", ts=T_0800, **meta):
    base = {"trigger": "gap", "gap_pct": 25.0, "rvol": 9.0, "cum_volume": 2_500_000.0}
    base.update(meta)
    return make_event(f"bar-{sym}-{ts.isoformat()}", source="alpaca_stocks", kind="bar_trigger", symbols=[sym],
                      ts=ts, meta=base)


def news(sym="TINY", ts=T_0800 - timedelta(hours=1), title="TINY wins FDA approval", eid="n1"):
    return make_event(eid, kind="news", symbols=[sym], title=title, ts=ts)


def track(**kw):
    ref = {"TINY": {"prev_close": 4.0, "avg_vol_20d": 400_000.0}}
    return SmallCapTrack({}, float_map={"TINY": Rec(8_000_000.0)}, reference=ref, **kw)


def run(t: SmallCapTrack, *events, held=()):
    out = []
    for ev in events:
        t.observe(ev)
        out = t.assess_event(ev, held)
    return out


def test_bar_trigger_with_catalyst_and_fresh_float_is_a_runner():
    t = track()
    [(snap, a)] = run(t, news(), bar())
    assert snap.price == 5.0 and snap.prev_close == 4.0 and snap.float_m == 8.0
    assert snap.adv_30d == 400_000.0 and snap.premarket_volume == 2_500_000.0 and snap.catalyst
    assert a.long_alert and a.grade == "A" and a.priority == Priority.P2
    meta = assessment_meta(snap, a, "09:45")
    assert meta["classifier"] == CLASSIFIER_RUNNER and meta["float_known"] and not meta["float_stale"]
    assert meta["grade"] == "A" and not meta["do_not_buy"] and "09:45" in meta["headline"]
    assert set(meta) >= {"classifier", "grade", "bagholder_score", "reasons", "float_known", "float_stale"}


def test_no_long_after_the_early_window():
    t = track()
    [(_, a)] = run(t, news(ts=T_1000 - timedelta(hours=1)), bar(ts=T_1000))
    assert not a.long_alert and "long_alert_expired" in a.runner_blockers


def test_unknown_or_stale_float_never_gives_a_long():
    for fm in ({}, {"TINY": Rec(8_000_000.0, stale=True)}, {"TINY": Rec(None)}):
        t = SmallCapTrack({}, float_map=fm, reference={"TINY": {"prev_close": 4.0, "avg_vol_20d": 400_000.0}})
        [(snap, a)] = run(t, news(), bar())
        assert not a.long_alert
        meta = assessment_meta(snap, a, "09:45")
        assert meta["classifier"] == CLASSIFIER_NONE  # float warning alone is not an alert
        assert not (meta["float_known"] and not meta["float_stale"])


def test_offering_headline_is_not_a_catalyst():
    t = track()
    [(snap, a)] = run(t, news(title="TINY announces $5M registered direct offering"), bar())
    assert snap.catalyst_is_offering and not a.long_alert and "no_catalyst" in a.runner_blockers


def test_roundup_headlines_and_old_news_are_not_catalysts():
    t = track()
    roundup = make_event("r1", kind="news", symbols=["TINY", "AAA", "BBB", "CCC"], title="Movers", ts=T_0800)
    old = news(ts=T_0800 - timedelta(hours=30), eid="old")
    [(snap, _)] = run(t, roundup, old, bar())
    assert not snap.catalyst


def test_toxic_halt_says_do_not_buy_and_blocks_longs():
    t = track()
    halt = make_event("h1", source="nasdaq_halts", kind="halt", symbols=["TINY"], ts=T_0800,
                      meta={"status": "halted", "reason_code": "T12"})
    out = run(t, news(), bar(), halt)
    [(snap, a)] = out
    meta = assessment_meta(snap, a, "09:45")
    assert a.toxic and not a.long_alert and meta["classifier"] == CLASSIFIER_BAGHOLDER and meta["do_not_buy"]
    assert "DO NOT BUY" in meta["headline"]
    held_out = t.assess_event(halt, held={"tiny"})
    assert held_out[0][1].priority == Priority.P3


def test_promoted_ramp_profile_says_do_not_buy():
    t = track()
    ev = bar(ipo_months=6, ipo_price=4.0, ipo_proceeds_m=10.0, ipo_shares_m=3.0, gain_5d_pct=120.0)
    [(snap, a)] = run(t, ev)
    meta = assessment_meta(snap, a, "09:45")
    assert a.promoted and classify_assessment(a) == CLASSIFIER_RAMP and meta["do_not_buy"]
    assert "PROMOTED / DO NOT BUY" in meta["headline"] and "TINY" in t.blocklist


def test_dilution_filing_feeds_bagholder_score():
    t = track()
    filing = make_event("f1", source="edgar", kind="filing", symbols=["TINY"], ts=T_0800,
                        meta={"form_type": "424B5"})
    [(_, a)] = run(t, bar(), filing)
    assert "dilution_filing" in a.bagholder_reasons and not a.long_alert


def test_skips_symbols_without_price_or_outside_universe():
    t = SmallCapTrack({})
    assert t.assess_event(news()) == []  # no price, no prev close
    big = SmallCapTrack({}, reference={"MEGA": {"prev_close": 400.0}})
    assert run(big, bar("MEGA", gap_pct=1.0)) == []  # $404 is outside the universe
    assert t.assess_event(make_event("a", kind="account", symbols=["TINY"])) == []


def test_multi_symbol_meta_is_not_attributed_and_explicit_price_wins():
    t = track()
    t.observe(make_event("m", kind="news", symbols=["TINY", "AAA"], meta={"price": 99.0}))
    assert t.quote("TINY") == {}
    t.observe(bar(close=6.0, gap_pct=10.0))
    snap = t.snapshot_for("TINY", T_0800)
    assert snap is not None and snap.price == 6.0


def test_bad_meta_value_is_ignored_safely():
    t = track()
    t.observe(bar(market_cap_m="n/a"))
    snap = t.snapshot_for("TINY", T_0800)
    assert snap is not None and snap.market_cap_m is None and "market_cap_m" not in t.quote("TINY")


def test_reset_session_forgets_quotes_but_keeps_reference():
    t = track()
    run(t, bar())
    t.reset_session()
    assert t.quote("TINY") == {}
    snap = t.snapshot_for("TINY", T_0800)
    assert snap is None  # reference has prev_close but no price today


def test_float_warning_text_constant_is_in_warnings():
    t = SmallCapTrack({}, reference={"TINY": {"prev_close": 4.0}})
    [(_, a)] = run(t, bar())
    assert FLOAT_UNKNOWN_WARNING in a.warnings


def test_degraded_feed_flag_reaches_the_message():
    t = track(degraded_feed=True)
    [(snap, a)] = run(t, news(), bar())
    assert snap.degraded_feed and "DEGRADED" in a.message


def test_dilution_memory_survives_the_session_reset_and_expires():
    """Finding: a 424B5 filed Friday 17:00 was forgotten at midnight, so Monday's gap could get a long alert."""
    from datetime import UTC, datetime

    from swing_engine.monitor.smallcap import SmallCapTrack, dilution_label

    assert dilution_label({"form_type": "424B5"}) == "424B5"
    assert dilution_label({"form_type": "8-K", "items": ["3.02", "9.01"]}) == "8-K 3.02"
    assert dilution_label({"form_type": "8-K", "items": ["2.02"]}) is None
    track = SmallCapTrack()
    friday = datetime(2026, 10, 2, 21, 0, tzinfo=UTC)  # 17:00 ET
    track.remember_dilution("tiny", friday, "424B5")
    track.reset_session()  # weekend rollovers
    monday = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # 08:00 ET
    assert track.dilution_recent("TINY", monday) == (1, False)
    later = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)  # 7 sessions later: outside the 5-session lookback
    assert track.dilution_recent("TINY", later) == (0, False)
    track.seed_dilution([("TINY", datetime(2026, 9, 20, 14, 0, tzinfo=UTC), "reverse_split")])
    assert track.dilution_recent("TINY", monday)[1] is True  # reverse split within 30 days
