"""Farm views: chart layers, intraday market-structure chart, studies, coverage and vocabulary endpoints, on the
demo provider and on the live provider against tmp stores. No network; every store is read-only to the dashboard."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing_engine.dashboard import farm
from swing_engine.dashboard.demo import DemoData
from swing_engine.dashboard.server import DashboardApp
from swing_engine.data import intraday
from swing_engine.data.store import Store
from swing_engine.features.market_structure import KINDS
from swing_engine.ops import receipts, vocabulary
from tests.test_dashboard_support import AS_OF, live_data

H = {"Host": "localhost:8765", "X-Swing-Dashboard": "1"}
OBJECT_KEYS = {"id", "layer", "shape", "t", "t2", "price", "price2", "dir", "text", "ref"}
DAY = date(2026, 10, 2)  # a Friday


def get(app: DashboardApp, target: str) -> dict:
    resp = app.handle("GET", target, H)
    assert resp.status == 200, (target, resp.body[:300])
    body = resp.json()
    assert body["ok"] is True, (target, body)
    return body["data"]


def check_layers(data: dict, keys: list[str]) -> None:
    assert [layer["key"] for layer in data["layers"]] == keys
    assert all(set(o) == OBJECT_KEYS and o["ref"] in data["receipts"] for o in data["objects"])
    assert len({o["id"] for o in data["objects"]}) == len(data["objects"])
    counts = {layer["key"]: layer["count"] for layer in data["layers"]}
    assert counts == {k: sum(o["layer"] == k for o in data["objects"]) for k in keys}


# ----------------------------------------------------------------------------------------------- demo
@pytest.fixture()
def demo() -> DashboardApp:
    return DashboardApp(DemoData(), secrets=[])


def test_demo_chart_layers(demo: DashboardApp) -> None:
    data = get(demo, "/api/chart/ORCA/layers")
    check_layers(data, [row[0] for row in farm.SWING_LAYERS])
    counts = {layer["key"]: layer["count"] for layer in data["layers"]}
    assert counts["taken"] == 1 and counts["seen"] == 0 and counts["refusals"] == 1 and counts["entries"] == 1
    assert counts["stops"] == 1 and counts["targets"] == 1 and counts["exits"] == 2 and counts["levels"] and counts["regime"]
    assert data["status"] == {"events": 4, "fires": 1, "refusals": 1, "outcomes": 1, "engine_sig": "demo0000"}
    fire = next(o for o in data["objects"] if o["layer"] == "taken")
    assert data["receipts"][fire["ref"]]["payload"]["intent"]["stop"]  # the Inspector shows the whole event row
    shadow = get(demo, "/api/chart/ZZZ/layers?start=2026-08-01&end=2026-10-06")
    assert {layer["key"]: layer["count"] for layer in shadow["layers"]}["seen"] == 1
    assert all(o["t"] >= "2026-08-01" for o in shadow["objects"])


@pytest.mark.parametrize("target,bars", [("/api/intraday/SPY", 78), ("/api/intraday/BTC-USD?tf=1h&day=2026-10-01", 24),
                                         ("/api/intraday/btc%2Fusd?tf=4h", 6), ("/api/intraday/GLD?tf=2m", None)])
def test_demo_intraday(demo: DashboardApp, target: str, bars: int | None) -> None:
    data = get(demo, target)
    check_layers(data, [row[0] for row in farm.INTRADAY_LAYERS])
    assert data["bars"] and (bars is None or len(data["bars"]) == bars)
    times = [b["t"] for b in data["bars"]]
    assert times == sorted(set(times)) and data["status"]["bars"] == len(times)
    assert data["status"]["events"] == len(data["objects"]) > 0 and data["status"]["warmup_bars"] > 300
    lo, hi = pd.Timestamp(data["day"], tz=data["tz"]), pd.Timestamp(data["day"], tz=data["tz"]) + pd.Timedelta(days=1)
    for receipt in data["receipts"].values():  # only events confirmed inside the day are drawn
        assert lo <= pd.Timestamp(receipt["ts_event"]) < hi and receipt["kind"] in KINDS
    assert {o["shape"] for o in data["objects"]} <= {"marker", "line", "zone"}


def test_demo_studies_coverage_vocabulary(demo: DashboardApp) -> None:
    listing = get(demo, "/api/studies")
    assert [s["date"] for s in listing["studies"]] == ["2026-10-06"]
    study = get(demo, "/api/studies/2026-10-06")
    assert study["markdown"].startswith("# ") and "| strategy |" in study["markdown"]
    assert demo.handle("GET", "/api/studies/2026-10-01", H).json()["ok"] is False
    cov = get(demo, "/api/coverage?days=30")
    assert set(cov["tiles"]) == {"days_covered", "events", "fires", "refusals", "outcomes", "studies"}
    assert cov["days"] == sorted(cov["days"]) and cov["strategies"]["rows"] and cov["symbols"]["rows"]
    for view in ("strategies", "symbols"):
        assert all(r["total"] == sum(r["cells"].values()) and set(r["cells"]) <= set(cov["days"]) for r in cov[view]["rows"])
    vocab = get(demo, "/api/vocabulary")
    assert vocab["strategies"][1]["rulings"][0]["date"] == "2026-10-06" and vocab["structure"][0]["kinds"]


@pytest.mark.parametrize("target", [
    "/api/chart/..%2F..%2Fetc/layers", "/api/chart/AAPL1/layers", "/api/chart/SPY/layers?start=yesterday",
    "/api/chart/SPY/layers?end=2026-02-30", "/api/chart/SPY/layers?start=2026-10-06&end=2026-10-01",
    "/api/chart/SPY/layers?start=2000-01-01&end=2026-10-01", "/api/intraday/AAPL", "/api/intraday/..%2F..%2Fetc",
    "/api/intraday/SPY?tf=1m", "/api/intraday/SPY?tf=..", "/api/intraday/SPY?day=2026-13-01", "/api/intraday/SPY?day=today",
    "/api/studies/..%2F..%2Fetc%2Fpasswd", "/api/studies/2026-10-06.md", "/api/studies/2026-02-30", "/api/studies/%00",
    "/api/studies/20261006", "/api/coverage?days=0", "/api/coverage?days=9999", "/api/coverage?days=abc",
])
def test_bad_parameters_are_400(demo: DashboardApp, target: str) -> None:
    resp = demo.handle("GET", target, H)
    assert resp.status == 400, target
    assert resp.json()["ok"] is False


def test_routes_are_get_only_and_same_origin(demo: DashboardApp) -> None:
    for target in ("/api/chart/SPY/layers", "/api/intraday/SPY", "/api/studies", "/api/studies/2026-10-06",
                   "/api/coverage", "/api/vocabulary"):
        assert demo.handle("POST", target, {**H, "Content-Type": "application/json"}, b"{}").status == 405, target
        assert demo.handle("GET", target, {"Host": "localhost:8765"}).status == 403, target
        assert demo.handle("GET", target, {**H, "Origin": "https://evil.example"}).status == 403, target
        body = demo.handle("GET", target, H).body.decode()
        assert "NaN" not in body and "Infinity" not in body, target
        json.loads(body)
    for target in ("/api/studies/2026-10-06/x", "/api/studies/../../etc/passwd", "/api/chart/SPY/layers/x"):
        assert demo.handle("GET", target, H).status == 404, target


def test_demo_farm_views_are_deterministic() -> None:
    a, b = DashboardApp(DemoData(), secrets=[]), DashboardApp(DemoData(), secrets=[])
    for target in ("/api/chart/ORCA/layers", "/api/intraday/QQQ?tf=15m", "/api/coverage", "/api/vocabulary"):
        assert a.handle("GET", target, H).body == b.handle("GET", target, H).body, target


# ----------------------------------------------------------------------------------------------- builders
def test_swing_objects_from_receipts() -> None:
    def ev(n: int, kind: str, as_of: str, payload: dict, step: str = "scan") -> dict:
        return {"event_id": f"e{n}", "kind": kind, "as_of": as_of, "strategy": "s", "symbol": "AAA", "step": step,
                "reason": "", "payload": payload, "engine_sig": "abc"}

    sig = {"signal": {"entry": 10.0, "stop": 9.0, "target": None, "side": "long"}}
    out = {"signal_as_of": "2026-10-01", "entry_date": "2026-10-02", "entry_price": 10.1, "exit_date": "2026-10-06",
           "hit": "stop_hit", "gross_r": -1.0}
    events = [
        ev(1, "fire", "2026-10-01", {**sig, "shadow": True}),
        ev(2, "outcome", "2026-10-06", {**out, "horizon": 5}),
        ev(3, "outcome", "2026-10-06", {**out, "horizon": 10}),  # same exit at a longer horizon: drawn once
        ev(4, "outcome", "2026-10-07", {"signal_as_of": "2026-10-02", "hit": "entry_skipped"}, "fill"),
        ev(5, "refusal", "2026-10-02", sig, "router"),
        ev(6, "note", "2026-10-02", {}),
    ]
    objects, recs = farm.swing_objects(events)
    by_layer = {k: [o for o in objects if o["layer"] == k] for k in ("seen", "taken", "stops", "targets", "entries",
                                                                     "exits", "refusals")}
    assert len(by_layer["seen"]) == 1 and not by_layer["taken"] and not by_layer["targets"]
    (stop,) = by_layer["stops"]
    assert (stop["t"], stop["t2"], stop["price"], stop["ref"]) == ("2026-10-01", "2026-10-06", 9.0, "e1")
    assert [(o["t"], o["text"]) for o in by_layer["entries"]] == [("2026-10-02", "entry 10.1"), ("2026-10-07", "no fill")]
    assert [(o["t"], o["text"]) for o in by_layer["exits"]] == [("2026-10-06", "stop hit -1R")]
    assert by_layer["refusals"][0]["text"] == "router" and set(recs) == {f"e{n}" for n in range(1, 7)}
    payload = farm.layers_payload("AAA", "2026-10-01", "2026-10-07", events)
    assert payload["status"] == {"events": 6, "fires": 1, "refusals": 1, "outcomes": 3, "engine_sig": "abc"}


def test_level_and_regime_runs() -> None:
    n = 120
    days = [d.date().isoformat() for d in pd.bdate_range("2026-01-01", periods=n)]
    close = [100 + 10 * np.sin(i / 6) for i in range(n)]
    objects, recs = farm.level_objects(days, [c + 1 for c in close], [c - 1 for c in close], close, days[80], days[-1])
    assert objects and all(o["shape"] == "line" and o["price"] == o["price2"] and days[80] <= o["t"] <= o["t2"] for o in objects)
    assert {recs[o["ref"]]["kind"] for o in objects} == {"support_1", "resistance_1"}
    for kind in ("support_1", "resistance_1"):  # runs of one side never overlap
        runs = sorted((recs[o["ref"]]["from"], recs[o["ref"]]["to"]) for o in objects if o["text"] == kind)
        assert all(a[1] < b[0] for a, b in zip(runs, runs[1:], strict=False))
    assert farm.level_objects(days[:10], close[:10], close[:10], close[:10], days[0], days[9]) == ([], {})
    bands, _ = farm.regime_objects({"2026-10-01": ("choppy", "x"), "2026-10-02": ("choppy", "x"), "2026-10-05": ("correction", "x")})
    assert [(b["t"], b["t2"], b["text"]) for b in bands] == [("2026-10-01", "2026-10-02", "choppy"),
                                                              ("2026-10-05", "2026-10-05", "correction")]


def test_structure_entries_cover_every_kind() -> None:
    entries = vocabulary.structure_entries()
    assert {k for e in entries for k in e["kinds"]} == set(KINDS)
    assert all(e["definition"] and e["section"] in vocabulary.STRUCTURE_SECTIONS for e in entries)
    assert vocabulary.structure_entries(Path("/nonexistent/market-structure.md")) == []


# ----------------------------------------------------------------------------------------------- live
def _minute_bars(symbol: str, start: str, end: str, tz: str, seed: int) -> pd.DataFrame:
    """One bar a minute over regular hours (ETF) or round the clock (crypto), a seeded random walk."""
    ts = pd.date_range(start, end, freq="1min", tz=tz, inclusive="left")
    if "/" not in symbol:
        minute = ts.hour * 60 + ts.minute
        ts = ts[(ts.dayofweek < 5) & (minute >= 570) & (minute < 960)]
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.0006, len(ts))))
    open_ = np.concatenate([[100.0], close[:-1]])
    spread = np.abs(rng.normal(0, 0.0004, len(ts)))
    df = pd.DataFrame({"symbol": symbol, "ts": ts.tz_convert("UTC"), "open": open_,
                       "high": np.maximum(open_, close) * (1 + spread), "low": np.minimum(open_, close) * (1 - spread),
                       "close": close, "volume": 1000.0, "vwap": close, "trade_count": 10})
    df["session"] = intraday.label_sessions(df["symbol"], df["ts"])
    return df


def _tree(root: Path) -> dict[str, tuple[int, int]]:
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture()
def live(tmp_path: Path) -> tuple[DashboardApp, Path]:
    studies = tmp_path / "studies"
    studies.mkdir()
    (studies / "2026-10-02.md").write_text("# Daily study: 2026-10-02\n\n| a | b |\n|---|---|\n| <script>x</script> | 1 |\n")
    (studies / "2026-10-05.md").write_text("# Daily study: 2026-10-05\n")
    (studies / "notes.md").write_text("not a study")
    (tmp_path / "secret.md").write_text("outside the studies dir")
    data = live_data(tmp_path, studies_dir=studies)
    st = receipts.stamp(data.settings)
    sig = {"signal": {"entry": 40.0, "stop": 38.0, "target": 45.0, "side": "long"}, "regime": "narrow_uptrend"}
    with Store(data.store_path) as store:
        receipts.write_events(store, [
            receipts.make_event(receipts.FIRE, "scan", "shadow-only signal", AS_OF, "pullback_trend", "AAA",
                                {**sig, "shadow": True}, **st),
            receipts.make_event(receipts.REFUSAL, "daily_cap", "max_new_orders_per_day=1 reached", AS_OF, "sr_bounce",
                                "AAA", sig, **st),
            receipts.make_event(receipts.FIRE, "broker", "submitted", date(2026, 9, 28), "pullback_trend", "BBB",
                                {"intent": {"stop": 87.0, "target": 99.0}}, **st),
        ])
    with Store(data.intraday_path) as store:
        for i, (sym, tz) in enumerate((("SPY", "America/New_York"), ("BTC/USD", "UTC"))):
            store.write_table(intraday.TABLE, _minute_bars(sym, "2026-09-21", "2026-10-03", tz, i), intraday.KEYS,
                              schema=intraday.SCHEMA)
    return DashboardApp(data, secrets=[]), tmp_path


def test_live_chart_layers(live: tuple[DashboardApp, Path]) -> None:
    app, _root = live
    data = get(app, f"/api/chart/AAA/layers?start=2026-06-01&end={AS_OF.isoformat()}")
    check_layers(data, [row[0] for row in farm.SWING_LAYERS])
    counts = {layer["key"]: layer["count"] for layer in data["layers"]}
    assert counts["seen"] == 1 and counts["refusals"] == 1 and counts["stops"] == 1 and counts["targets"] == 1
    assert counts["levels"] > 0 and counts["regime"] >= 1
    assert data["status"]["events"] == 2 and data["status"]["fires"] == 1 and len(data["status"]["engine_sig"]) == 8
    refusal = next(o for o in data["objects"] if o["layer"] == "refusals")
    receipt = data["receipts"][refusal["ref"]]
    assert receipt["step"] == "daily_cap" and receipt["payload"]["signal"]["stop"] == 38.0 and receipt["as_of"] == AS_OF.isoformat()
    assert get(app, "/api/chart/BBB/layers?start=2026-10-01&end=2026-10-05")["status"]["events"] == 0  # outside the window
    nothing = get(app, "/api/chart/ZZZ/layers")  # no bars, no receipts: only the market-wide regime, not an error
    assert {o["layer"] for o in nothing["objects"]} <= {"regime"} and nothing["status"]["events"] == 0


def test_live_intraday_reads_the_store_read_only(live: tuple[DashboardApp, Path]) -> None:
    app, root = live
    before = _tree(root)
    latest = get(app, "/api/intraday/SPY")
    assert (latest["day"], latest["tf"], latest["first_day"], latest["last_day"]) == ("2026-10-02", "5m", "2026-09-21", "2026-10-02")
    data = get(app, f"/api/intraday/SPY?day={DAY.isoformat()}&tf=5m")
    assert data == latest
    assert len(data["bars"]) == 78 and data["bars"][0]["session"] == "rth"  # 09:30-16:00 in 5-minute bars
    first = pd.Timestamp(data["bars"][0]["t"], unit="s")
    assert (first.hour, first.minute) == (9, 30)  # the time axis is New York wall-clock time
    check_layers(data, [row[0] for row in farm.INTRADAY_LAYERS])
    lo = pd.Timestamp(DAY.isoformat(), tz="America/New_York")
    assert data["objects"] and all(lo <= pd.Timestamp(r["ts_event"]) < lo + pd.Timedelta(days=1) for r in data["receipts"].values())
    assert data["status"]["warmup_bars"] > 300 and data["status"]["extractor_version"]
    for tf, n in (("2m", 195), ("15m", 26), ("30m", 13), ("1h", 7), ("4h", 2)):
        assert len(get(app, f"/api/intraday/SPY?day={DAY.isoformat()}&tf={tf}")["bars"]) == n, tf
    btc = get(app, "/api/intraday/BTC-USD?tf=1h&day=2026-10-01")
    assert btc["tz"] == "UTC" and len(btc["bars"]) == 24 and btc["symbol"] == "BTC/USD"
    closed = get(app, "/api/intraday/SPY?day=2026-09-27")  # a Sunday: no bars is an empty chart, not an error
    assert closed["bars"] == [] and closed["objects"] == []
    missing = app.handle("GET", "/api/intraday/QQQ", H).json()
    assert missing["ok"] is False and "QQQ" in missing["unavailable"]
    studies = get(app, "/api/studies")
    get(app, "/api/coverage")
    get(app, f"/api/chart/AAA/layers?end={AS_OF.isoformat()}")
    assert studies["count"] == 2
    assert _tree(root) == before  # no store, wal, study or run file was created or touched by any read


def test_live_intraday_without_a_store(tmp_path: Path) -> None:
    app = DashboardApp(live_data(tmp_path), secrets=[])
    body = app.handle("GET", "/api/intraday/SPY", H).json()
    assert body["ok"] is False and "ingest-intraday" in body["unavailable"]
    assert not (tmp_path / "data" / "intraday.duckdb").exists()  # reading never creates the store


def test_live_studies(live: tuple[DashboardApp, Path]) -> None:
    app, _root = live
    listing = get(app, "/api/studies")
    assert [(s["date"], s["title"]) for s in listing["studies"]] == [("2026-10-05", "Daily study: 2026-10-05"),
                                                                    ("2026-10-02", "Daily study: 2026-10-02")]
    study = get(app, "/api/studies/2026-10-02")
    assert "<script>x</script>" in study["markdown"]  # served as markdown text; the page escapes it before rendering
    assert study["available_dates"] == ["2026-10-05", "2026-10-02"]
    gone = app.handle("GET", "/api/studies/2026-10-03", H).json()
    assert gone["ok"] is False and "no study" in gone["unavailable"]
    for target in ("/api/studies/..%2Fsecret", "/api/studies/..%2Fsecret.md", "/api/studies/notes",
                   "/api/studies/2026-10-02%2F..%2F..%2Fsecret"):
        resp = app.handle("GET", target, H)
        assert resp.status == 400 and b"outside the studies dir" not in resp.body, target


def test_live_coverage_and_vocabulary(live: tuple[DashboardApp, Path], tmp_path: Path) -> None:
    app, _root = live
    cov = get(app, "/api/coverage")
    assert cov["tiles"] == {"days_covered": 2, "events": 3, "fires": 2, "refusals": 1, "outcomes": 0, "studies": 2}
    assert cov["days"] == ["2026-09-28", "2026-10-05"]
    assert {r["key"]: r["cells"] for r in cov["strategies"]["rows"]} == {
        "pullback_trend": {"2026-09-28": 1, "2026-10-05": 1}, "sr_bounce": {"2026-10-05": 1}}
    assert cov["symbols"]["rows"][0] == {"key": "AAA", "total": 2, "cells": {"2026-10-05": 2}}
    assert get(app, "/api/coverage?days=3")["days"] == ["2026-10-05"]  # the heatmap window; the tiles stay all-time
    vocab = get(app, "/api/vocabulary")
    assert {e["slug"] for e in vocab["strategies"]} >= {"pullback_trend", "sr_bounce"}
    assert {k for e in vocab["structure"] for k in e["kinds"]} == set(KINDS)
    assert all(set(r) == {"date", "text"} for r in vocab["rulings_for_everything"])
    fresh = DashboardApp(live_data(tmp_path / "fresh"), secrets=[])
    assert fresh.handle("GET", "/api/coverage", H).json()["ok"] is False  # no events table yet: a reason, not an error


def test_intraday_chart_draws_the_chain_replay_rows(live: tuple[DashboardApp, Path]) -> None:
    app, root = live
    ts = lambda hhmm: pd.Timestamp(f"{DAY.isoformat()} {hhmm}", tz="America/New_York").tz_convert("UTC")  # noqa: E731
    base = {"symbol": "SPY", "sweep_pool": "PDL", "mss_ts": pd.NaT, "zone_ts": pd.NaT, "retrace_ts": pd.NaT,
            "trigger_ts": pd.NaT, "day": DAY}
    trade = {**base, "card": "lit_chain_ob", "direction": "long", "refusal": None, "sweep_ts": ts("10:00"),
             "entry_ts": ts("10:30"), "entry": 100.0, "stop": 99.0, "target": 102.0, "exit_ts": ts("11:00"), "exit": 101.0,
             "net_r": 0.9, "lineage": "sweep PDL -> entry 100"}
    refused = {**base, "card": "lit_chain_fvg", "direction": "short", "refusal": "no_retrace", "sweep_ts": ts("12:00"),
               "mss_ts": ts("13:00"), "entry_ts": pd.NaT}
    other = {**trade, "symbol": "QQQ"}
    (root / "chains").mkdir()
    pd.DataFrame([trade, other]).to_parquet(root / "chains" / "trades.parquet")
    pd.DataFrame([refused]).to_parquet(root / "chains" / "refusals.parquet")
    data = get(app, f"/api/intraday/SPY?day={DAY.isoformat()}&tf=5m")
    counts = {layer["key"]: layer["count"] for layer in data["layers"]}
    assert (counts["taken"], counts["stops"], counts["targets"], counts["seen"]) == (2, 1, 1, 1)  # marker + path
    marker = next(o for o in data["objects"] if o["layer"] == "taken" and o["shape"] == "marker")
    assert marker["text"] == "ob +0.9R" and marker["dir"] == "bull"
    assert data["receipts"][marker["ref"]]["lineage"] == "sweep PDL -> entry 100"
    seen = next(o for o in data["objects"] if o["layer"] == "seen")
    assert seen["text"] == "no_retrace" and pd.Timestamp(seen["t"], unit="s").hour == 13  # where the chain stopped
