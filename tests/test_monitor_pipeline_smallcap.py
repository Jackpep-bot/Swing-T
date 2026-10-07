from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd

from swing_engine.data.store import Store
from swing_engine.monitor.alerts import AlertPolicy
from swing_engine.monitor.delivery.console import ConsoleDeliverer
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.halt_log import HALT_LOG_TABLE
from swing_engine.monitor.pipeline import Pipeline
from swing_engine.monitor.replay import load_rules
from swing_engine.monitor.rules.market_wide_suppression import SUPPRESSED_HIT, note_circuit_breaker
from swing_engine.monitor.smallcap import SmallCapTrack
from tests.monitor_helpers import make_event

T_0800 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)  # 08:00 ET, Tuesday
REF = {"TINY": {"prev_close": 4.0, "avg_vol_20d": 400_000.0}}


class RecordingDeliverer(ConsoleDeliverer):
    def __init__(self, name: str, ok: bool = True):
        super().__init__(printer=lambda s: None)
        self.name = name
        self.ok = ok
        self.metas: list[dict] = []

    async def send(self, title, body, priority, meta=None):
        self.sent.append((title, body, priority))
        self.metas.append(dict(meta or {}))
        return self.ok


def float_store(shares: float | None = 8_000_000.0, as_of: date = date(2026, 9, 30)) -> Store:
    store = Store()
    frame = pd.DataFrame([{"symbol": "TINY", "as_of": as_of, "float_shares": shares,
                           "shares_outstanding": shares, "source": "edgar_companyfacts"}])
    store.write_table("float", frame, ["symbol", "as_of"])
    return store


def make(store=None, held=None, track=None, clock=T_0800, **kw):
    tg, po, co = RecordingDeliverer("telegram"), RecordingDeliverer("pushover"), RecordingDeliverer("console")
    track = track if track is not None else SmallCapTrack({}, reference=REF)
    p = Pipeline(
        rules=load_rules(),
        policy=AlertPolicy(clock=lambda: clock, quiet_hours_et=(0, 0)),
        deliverers=[tg, po, co],
        eventlog=EventLog(":memory:"),
        ctx={"held": held or set(), "watchlist": set()},
        smallcap=track,
        store=store,
        clock=lambda: clock,
        **kw,
    )
    return p, tg, po


def gap_bar(ts=T_0800, eid="b1", **meta):
    base = {"trigger": "gap", "gap_pct": 25.0, "rvol": 1.0, "cum_volume": 2_500_000.0}  # rvol below the rule gate
    base.update(meta)
    return make_event(eid, source="alpaca_stocks", kind="bar_trigger", symbols=["TINY"], ts=ts, meta=base)


def pr(ts=T_0800 - timedelta(hours=1), eid="n1", title="TINY receives FDA clearance"):
    return make_event(eid, kind="news", symbols=["TINY"], title=title, ts=ts)


async def test_float_map_loads_from_store_and_runner_alert_fires():
    p, tg, _ = make(store=float_store())
    assert p.smallcap.float_map["TINY"].float_shares == 8_000_000.0
    await p.process(pr())
    res = await p.process(gap_bar())
    sc = res.event.meta["smallcap"]
    assert sc["classifier"] == "runner" and sc["grade"] == "A" and sc["float_known"] and not sc["float_stale"]
    assert {"classifier", "grade", "bagholder_score", "reasons", "float_known", "float_stale"} <= set(sc)
    assert res.priority == "P2" and "smallcap:runner_A" in res.event.rule_hits
    assert "telegram" in res.delivered
    title, body, _ = tg.sent[-1]
    assert title.startswith("[RUNNER grade A") and "SMALL-CAP RUNNER" in body
    assert p.eventlog.get("b1").meta["smallcap"]["classifier"] == "runner"
    assert p.stats["smallcap_alerts"] == 1


async def test_no_float_map_means_no_long_alert():
    p, tg, _ = make(store=None)
    await p.process(pr())
    res = await p.process(gap_bar())
    sc = res.event.meta["smallcap"]
    assert sc["classifier"] == "none" and not sc["float_known"] and not sc["long_alert"]
    assert res.priority == "P0" and not any(h.startswith("smallcap:") for h in res.event.rule_hits)
    assert tg.sent == []


async def test_stale_float_means_no_long_alert():
    p, _, _ = make(store=float_store(as_of=date(2025, 1, 2)))
    await p.process(pr())
    res = await p.process(gap_bar())
    assert res.event.meta["smallcap"]["float_stale"] and res.priority == "P0"


async def test_after_the_early_window_there_is_no_long_alert():
    late = datetime(2026, 10, 6, 14, 30, tzinfo=UTC)  # 10:30 ET
    p, _, _ = make(store=float_store(), clock=late)
    await p.process(pr(ts=late - timedelta(hours=1)))
    res = await p.process(gap_bar(ts=late))
    assert res.event.meta["smallcap"]["classifier"] == "none" and res.priority == "P0"


async def test_ramp_and_dump_alert_says_do_not_buy():
    p, tg, _ = make(store=float_store())
    res = await p.process(gap_bar(ipo_months=8, ipo_price=5.0, ipo_proceeds_m=12.0, ipo_shares_m=2.5, gain_5d_pct=150.0))
    sc = res.event.meta["smallcap"]
    assert sc["classifier"] == "ramp_and_dump" and sc["do_not_buy"]
    assert res.priority == "P2" and "smallcap:ramp_and_dump" in res.event.rule_hits
    title, body, _ = tg.sent[-1]
    assert "DO NOT BUY" in title and "DO NOT BUY" in body


async def test_toxic_halt_on_held_name_goes_p3_with_do_not_buy_and_is_logged():
    store = float_store()
    p, tg, po = make(store=store, held={"TINY"})
    await p.process(gap_bar())
    halt = make_event("h1", source="nasdaq_halts", kind="halt", symbols=["TINY"], ts=T_0800 + timedelta(minutes=5),
                      meta={"status": "halted", "reason_code": "T12", "halt_price": 5.2})
    res = await p.process(halt)
    sc = res.event.meta["smallcap"]
    assert sc["classifier"] == "bagholder" and sc["do_not_buy"] and res.priority == "P3"
    assert any("DO NOT BUY" in t for t, _, _ in po.sent)
    rows = store.read_table(HALT_LOG_TABLE)
    assert len(rows) == 1 and rows.iloc[0]["code"] == "T12" and float(rows.iloc[0]["halt_price"]) == 5.2
    assert p.stats["halts_logged"] == 1


async def test_every_halt_is_logged_even_without_smallcap_or_alert():
    store = Store()
    p, tg, _ = make(store=store, track=None)
    p.smallcap = None
    halt = make_event("h2", source="alpaca_stocks", kind="halt", symbols=["BIG"], ts=T_0800,
                      meta={"status": "halted", "reason_code": "LUDP", "price": 101.0})
    resume = make_event("h3", source="alpaca_stocks", kind="halt", symbols=["BIG"], ts=T_0800 + timedelta(minutes=5),
                        meta={"status": "resumed", "reason_code": "LUDP", "price": 104.0})
    await p.process(halt)
    await p.process(resume)
    rows = store.read_table(HALT_LOG_TABLE)
    assert len(rows) == 1 and float(rows.iloc[0]["resume_price"]) == 104.0
    assert p.stats["halts_logged"] == 2


async def test_luld_band_updates_never_open_the_store():
    opened = []

    def factory():
        opened.append(1)
        return Store()

    p, _, _ = make(store=factory, track=None, load_floats=False)
    p.smallcap = None
    band = make_event("l1", source="alpaca_stocks", kind="luld", symbols=["BIG"], meta={"up": 1, "down": 2})
    await p.process(band)
    assert opened == [] and p.stats["halts_logged"] == 0


async def test_store_failures_never_block_alerts():
    def broken():
        raise RuntimeError("database is locked")

    p, tg, po = make(store=broken, held={"DOOM"}, track=None)  # float map load fails quietly
    p.smallcap = None
    halt = make_event("h4", source="nasdaq_halts", kind="halt", symbols=["DOOM"], ts=T_0800,
                      meta={"status": "halted", "reason_code": "T1"})
    res = await p.process(halt)
    assert res.priority == "P3" and "pushover" in res.delivered
    assert p.stats["halt_log_errors"] == 1 and p.stats["halts_logged"] == 0


async def test_store_factory_is_opened_and_closed_per_use():
    closed = []

    class Tracking(Store):
        def close(self):
            closed.append(1)
            super().close()

    p, _, _ = make(store=lambda: Tracking(), load_floats=True)
    assert closed == [1]  # float map load
    halt = make_event("h5", source="nasdaq_halts", kind="halt", symbols=["XYZ"], ts=T_0800,
                      meta={"status": "halted", "reason_code": "T1"})
    await p.process(halt)
    assert closed == [1, 1]


async def test_market_wide_suppression_keeps_non_held_smallcap_alerts_quiet():
    p, tg, _ = make(store=float_store())
    note_circuit_breaker(p.ctx, T_0800)
    await p.process(pr())
    res = await p.process(gap_bar())
    assert res.event.meta["smallcap"]["classifier"] == "runner" and SUPPRESSED_HIT in res.event.rule_hits
    assert res.priority == "P0" and tg.sent == []


async def test_multi_symbol_event_keeps_the_most_severe_assessment():
    track = SmallCapTrack({}, reference={"TINY": {"prev_close": 4.0}, "PUMP": {"prev_close": 4.0}})
    p, _, _ = make(track=track)
    track.observe(gap_bar())
    track.observe(make_event("pb", source="alpaca_stocks", kind="bar_trigger", symbols=["PUMP"], ts=T_0800,
                             meta={"gap_pct": 10.0, "ipo_months": 8, "ipo_price": 5.0, "ipo_proceeds_m": 12.0,
                                   "ipo_shares_m": 2.5, "gain_5d_pct": 150.0, "float_m": 3.0}))
    res = await p.process(make_event("n9", kind="news", symbols=["TINY", "PUMP"], title="Two names", ts=T_0800))
    assert res.event.meta["smallcap"]["symbol"] == "PUMP"
    assert res.event.meta["smallcap"]["classifier"] == "ramp_and_dump"


async def test_events_without_a_price_get_no_smallcap_meta():
    p, _, _ = make()
    res = await p.process(make_event("n2", kind="news", symbols=["NOPE"], title="hello", ts=T_0800))
    assert "smallcap" not in res.event.meta


async def test_p2_alert_meta_carries_event_id_for_rating_buttons():
    p, tg, _ = make(store=float_store())
    await p.process(pr())
    await p.process(gap_bar())
    assert tg.metas[-1]["event_id"] == "b1"
