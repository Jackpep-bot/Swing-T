"""Live provider against a temp store / event log / ledger / run files, a fake read-only broker and a fake
portfolio-history endpoint. Covers every endpoint, fresh-install fallbacks, the kill switch and secrets."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing_engine.core.config import Settings
from swing_engine.dashboard.data import LiveData, Unavailable
from swing_engine.dashboard.server import DashboardApp
from swing_engine.monitor.eventlog import EventLog
from tests.test_dashboard_support import (
    FAKE_ANTHROPIC,
    FAKE_KEY,
    FAKE_SECRET,
    FAKE_TELEGRAM,
    NOW,
    FakeBroker,
    FakeHTTP,
    fake_secrets,
    live_data,
    no_key_secrets,
    write_json,
)

H = {"Host": "localhost:8765", "X-Swing-Dashboard": "1"}  # what the page's fetch() sends
JSON_POST = {**H, "Content-Type": "application/json"}
ENDPOINTS = ["/api/health", "/api/summary", "/api/regime", "/api/regime?date=2026-10-01", "/api/equity",
             "/api/equity?period=1M", "/api/equity?period=ALL", "/api/positions", "/api/orders",
             "/api/orders?status=closed&limit=10", "/api/chart/AAA", "/api/chart/SPY?days=30", "/api/chart/QQQ",
             "/api/signals", "/api/signals?date=2026-10-05", "/api/signals?date=2026-01-01", "/api/shadow",
             "/api/shadow?by=regime", "/api/alerts", "/api/alerts?hours=200", "/api/journal",
             "/api/journal?date=2026-10-02", "/api/journal?date=2026-01-01", "/api/replay"]


def _no_broker() -> Any:
    raise Unavailable("no Alpaca keys in .env (test)")


@pytest.fixture()
def data(tmp_path: Path) -> LiveData:
    return live_data(tmp_path)


@pytest.fixture()
def app(data: LiveData) -> DashboardApp:
    return DashboardApp(data, secrets=[])


def get(app: DashboardApp, target: str) -> dict[str, Any]:
    resp = app.handle("GET", target, H)
    assert resp.status == 200, (target, resp.body[:400])
    return resp.json()


def test_every_endpoint_answers_200(app: DashboardApp) -> None:
    for target in ENDPOINTS:
        body = get(app, target)
        assert body["ok"] in (True, False)
        if not body["ok"]:
            assert isinstance(body["unavailable"], str) and body["unavailable"]


def test_summary(app: DashboardApp, tmp_path: Path) -> None:
    s = get(app, "/api/summary")["data"]
    assert s["mode"] == "PAPER"
    acct = s["account"]
    assert acct["equity"] == 101500.0 and acct["day_pl"] == 500.0 and acct["day_pl_pct"] == pytest.approx(0.495)
    assert s["kill_switch"] == {"tripped": False, "path": str(tmp_path / "state" / "KILL"), "reason": ""}
    n = s["nightly"]
    assert n["as_of"] == "2026-10-05" and n["ok"] is False
    assert [st["name"] for st in n["steps"]] == ["ingest", "size", "review"]
    m = s["monitor"]
    assert set(m["feeds"]) == {"alpaca_news", "edgar", "nasdaq_halts"}
    assert m["alerts_24h"] == 1 and m["alerts_24h_total"] == 2
    assert m["last_event_at"] == "2026-10-06T18:45:00Z"
    clock = s["clock"]
    assert clock["is_open"] is True and clock["next_close"] == "2026-10-06T20:00:00Z"
    assert clock["next_open"] == "2026-10-07T13:30:00Z"
    assert s["generated_at"] == "2026-10-06T19:45:00Z"


def test_summary_without_broker_uses_audit_snapshot(tmp_path: Path) -> None:
    app = DashboardApp(live_data(tmp_path, broker=_no_broker), secrets=[])
    body = get(app, "/api/summary")
    acct = body["data"]["account"]
    assert acct["equity"] == 101100.0 and acct["as_of"] == "2026-10-05"
    assert "autopilot audit" in acct["source"] and "account" in body["partial"]


def test_regime(app: DashboardApp) -> None:
    r = get(app, "/api/regime")["data"]
    st = r["state"]
    assert st["regime"] == "narrow_uptrend" and st["spy_trend"] == "up" and st["vol_regime"] == "high"
    assert st["breadth"] == "neutral" and st["breadth_values"]["pct_above_50"] == 55.4
    assert st["notes"] == ["SPY uptrend but breadth neutral"]
    assert r["allowed"] == {"pullback_trend": 0.5, "rsi2_meanrev": 0.75, "sr_bounce": 0.5}
    assert r["blocked"] == {"breakout_52w": "not in the playbook table for this regime"}
    hist = r["breadth_history"]
    assert 0 < len(hist) <= 250 and hist[-1]["date"] == "2026-10-05"
    assert {"date", "pct_above_50", "pct_above_200", "ratio_10d"} <= set(hist[0])
    past = get(app, "/api/regime?date=2026-10-01")
    assert past["ok"] and past["data"]["state"] is None and "state" in past["partial"]
    assert past["data"]["breadth_history"][-1]["date"] <= "2026-10-01"


def test_regime_falls_back_to_nightly_scan_data(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    (data.runs.root / "regime" / "2026-10-05.json").unlink()
    report = json.loads((data.runs.root / "nightly" / "2026-10-05.json").read_text())
    report["steps"].append({"name": "scan", "status": "ok", "data": {
        "market_regime": "choppy", "allowed": {"rsi2_meanrev": 0.75}, "blocked": {"sr_bounce": "x"},
        "regime": {"market_trend_state": 0.0, "market_vol_regime": 1.0}}})
    (data.runs.root / "nightly" / "2026-10-05.json").write_text(json.dumps(report))
    r = data.regime(None)["data"]
    assert r["state"]["regime"] == "choppy" and r["allowed"] == {"rsi2_meanrev": 0.75}
    assert r["state"]["spy_trend"] == 0.0


def test_equity_from_portfolio_history(tmp_path: Path) -> None:
    http = FakeHTTP()
    app = DashboardApp(live_data(tmp_path, http=http), secrets=[])
    e = get(app, "/api/equity?period=3M")["data"]
    assert e["account_source"] == "alpaca paper portfolio history"
    assert e["account"][0]["equity"] > 0  # the zero point before the account existed is dropped
    assert e["normalized"][0]["account"] == 100.0 and e["normalized"][0]["spy"] == 100.0
    assert e["stats"]["return_pct"] > 0 and e["stats"]["max_drawdown_pct"] <= 0
    assert e["spy"][0]["t"] >= e["account"][0]["t"]
    url, params, headers = http.calls[0]
    assert url == "https://paper-api.alpaca.markets/v2/account/portfolio/history"
    assert params == {"period": "3M", "timeframe": "1D"}
    assert headers["APCA-API-KEY-ID"] == FAKE_KEY
    get(app, "/api/equity?period=3M")
    assert len(http.calls) == 1  # cached
    get(app, "/api/equity?period=ALL")
    assert http.calls[-1][1]["period"] == "5A"


def test_equity_falls_back_to_audit_snapshots(tmp_path: Path) -> None:
    for http in (FakeHTTP(status=403, body={"message": "forbidden"}), FakeHTTP(body={"oops": 1})):
        data = live_data(tmp_path / str(http.status) / str(len(str(http.body))), http=http)
        e = data.equity("1M")
        assert e["ok"] is True
        d = e["data"]
        assert d["account_source"].startswith("autopilot audit")
        assert [p["t"] for p in d["account"]] == ["2026-10-02", "2026-10-05"]
        assert "account" in d["unavailable"]


def test_equity_without_keys_never_calls_http(tmp_path: Path) -> None:
    http = FakeHTTP()
    data = live_data(tmp_path, broker=_no_broker, http=http, secrets=no_key_secrets())
    assert data.equity("6M")["ok"] is True
    assert http.calls == []


def test_live_mode_is_shown_but_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWING_ALLOW_LIVE", raising=False)
    http = FakeHTTP()
    data = live_data(tmp_path, broker=None, http=http, secrets=fake_secrets(alpaca_paper=False))
    data._broker_factory = data._default_broker  # the real factory: refuses live without SWING_ALLOW_LIVE
    app = DashboardApp(data, secrets=[])
    assert get(app, "/api/summary")["data"]["mode"] == "LIVE"
    pos = get(app, "/api/positions")
    assert pos["ok"] is False and "SWING_ALLOW_LIVE" in pos["unavailable"]
    assert get(app, "/api/equity")["ok"] is True  # audit snapshots + SPY
    assert http.calls == []  # portfolio history is read on the paper host only


def test_positions(app: DashboardApp) -> None:
    body = get(app, "/api/positions")
    assert body["source"] == "alpaca paper"
    (p,) = body["data"]
    assert p["symbol"] == "AAA" and p["side"] == "long" and p["qty"] == 100
    assert p["strategy"] == "pullback_trend"
    assert p["stop"] == 38.0 and p["target"] == 48.5  # original intent from the ledger
    assert p["current_stop"] == 40.5  # the open stop leg (moved to breakeven)
    assert p["risk_per_share"] == 2.5 and p["r_multiple"] == pytest.approx((44.0 - 40.5) / 2.5, abs=1e-3)
    assert p["opened_at"] == "2026-09-29T13:31:05Z" and p["days_held"] == 6
    assert p["max_hold_days"] == 15  # from the signal's own features
    assert "asset_id" not in p


def test_positions_and_orders_without_broker(tmp_path: Path) -> None:
    data = live_data(tmp_path, broker=_no_broker)
    pos = data.positions()
    assert pos["ok"] is False and "broker" in pos["unavailable"]
    orders = data.orders("open", 50)
    assert orders["ok"] is True and "ledger" in orders["source"]
    assert [o["symbol"] for o in orders["data"]] == ["BBB"]
    closed = data.orders("closed", 50)["data"]
    assert [o["symbol"] for o in closed] == ["AAA"]
    assert closed[0]["filled_avg_price"] == 40.5 and closed[0]["legs"][0]["stop_price"] == 38.0


def test_orders(app: DashboardApp) -> None:
    rows = get(app, "/api/orders")["data"]
    assert [o["symbol"] for o in rows] == ["AAA", "BBB"]
    assert rows[0]["strategy"] == "pullback_trend" and rows[1]["strategy"] == "sr_bounce"
    assert [leg["type"] for leg in rows[0]["legs"]] == ["stop", "limit"]
    assert rows[0]["legs"][0]["stop_price"] == 40.5
    closed = get(app, "/api/orders?status=closed&limit=1")["data"]
    assert len(closed) == 1 and closed[0]["status"] == "filled"


def test_chart(app: DashboardApp) -> None:
    c = get(app, "/api/chart/AAA?days=60")["data"]
    assert c["symbol"] == "AAA" and c["last_bar"] == "2026-10-05"
    assert 35 <= len(c["bars"]) <= 45 and c["bars"][-1]["t"] == "2026-10-05"
    assert {"t", "o", "h", "l", "c", "v"} == set(c["bars"][0])
    assert c["sma20"][-1]["t"] == "2026-10-05" and c["sma50"][0]["t"] >= c["bars"][0]["t"]
    closes = [b["c"] for b in c["bars"]]
    assert c["sma20"][-1]["v"] == pytest.approx(sum(closes[-20:]) / 20, rel=1e-4)
    assert c["levels"] == {"entry": 40.5, "stop": 38.0, "target": 48.5, "current_stop": 40.5}
    kinds = {(m["kind"], m["t"]) for m in c["markers"]}
    assert ("signal", "2026-09-28") in kinds and ("entry", "2026-09-29") in kinds and ("exit", "2026-09-30") in kinds
    spy = get(app, "/api/chart/SPY")["data"]
    assert spy["levels"] == {"entry": None, "stop": None, "target": None, "current_stop": None}
    missing = get(app, "/api/chart/QQQ")
    assert missing["ok"] is False and "QQQ" in missing["unavailable"]


def test_signals_join(app: DashboardApp) -> None:
    s = get(app, "/api/signals")["data"]
    assert s["date"] == "2026-10-05" and s["regime"] == "narrow_uptrend"
    by = {x["symbol"]: x for x in s["signals"]}
    assert by["BBB"]["taken"] is True and by["BBB"]["skip_reason"] is None  # in the ledger (accepted)
    assert by["CCC"]["taken"] is False and by["CCC"]["status"] == "vetoed"  # from the review: no audit entry
    assert by["CCC"]["skip_reason"] == "vetoed by Claude's review (needs more info)"
    assert by["CCC"]["review"]["decision"] == "needs_more_info"
    assert by["CCC"]["review"]["event_risk_flags"] == ["earnings_in_window"]
    assert by["DDD"]["status"] == "capped" and "daily cap" in by["DDD"]["skip_reason"]
    assert by["DDD"]["review"]["decision"] == "approve"
    assert by["EEE"]["status"] == "not_sized" and by["EEE"]["review"] is None
    assert by["EEE"]["skip_reason"] == "not sized (no order intent was made for this signal)"
    assert by["FFF"]["skip_reason"] == "reward_risk 1.60 below min 2.0"
    assert by["GGG"]["status"] == "dry_run_planned" and "dry run" in by["GGG"]["skip_reason"]
    assert by["BBB"]["rank_score"] == 0.61 and by["BBB"]["qty"] == 10
    for x in s["signals"]:
        assert (x["skip_reason"] is None) == x["taken"]
    assert s["available_dates"] == ["2026-10-05", "2026-09-28"]


def _nightly_signal_files(data: LiveData, *, size_status: str = "ok") -> None:
    """runs/ as a real nightly leaves them: review_status ok, reviews for the top agent.max_candidates_per_day
    signals only, intents rewritten to the approved ones, an audit with no vetoed / unreviewed entries."""
    d = "2026-10-05"
    data.settings.agent.max_candidates_per_day = 3  # BBB, CCC, DDD (file order = score order) get reviewed

    def review(sym: str, strategy: str, decision: str) -> dict[str, Any]:
        return {"symbol": sym, "strategy": strategy, "thesis": "t", "event_risk_flags": [], "rubric_scores": {},
                "decision": decision, "evidence": []}

    write_json(data.runs.dir("review_status") / f"{d}.json", {"status": "ok", "detail": "3 reviewed"})
    write_json(data.runs.dir("reviews") / f"{d}.json", [
        review("BBB", "sr_bounce", "approve_for_risk_check"), review("CCC", "pullback_trend", "needs_more_info"),
        review("DDD", "pullback_trend", "approve_for_risk_check")])
    intents = [] if size_status != "ok" else [
        {"symbol": sym, "side": "long", "qty": 10, "entry_limit": 1.0, "stop": 0.5, "target": 2.0, "strategy": st,
         "client_order_id": f"swing-{st}-{sym}-20261005-long", "risk_dollars": 5.0}
        for sym, st in (("BBB", "sr_bounce"), ("DDD", "pullback_trend"))]
    write_json(data.runs.dir("intents") / f"{d}.json", intents)
    write_json(data.runs.dir("autopilot") / f"{d}.json", {"as_of": d, "runs": [
        {"broker": "alpaca", "dry_run": False, "started_at": "2026-10-05T10:32:00Z",
         "account": {"equity": 101000.0, "last_equity": 100500.0},
         "entries": [{"kind": "entry", "symbol": "DDD", "status": "capped", "strategy": "pullback_trend",
                      "client_order_id": "swing-pullback_trend-DDD-20261005-long", "reason": ""}]}]})
    report = json.loads((data.runs.dir("nightly") / f"{d}.json").read_text())
    size = next(st for st in report["steps"] if st["name"] == "size")
    if size_status != "ok":
        size.update(status=size_status, detail="equity unknown: pass --equity, set risk.account_equity_override",
                    data={})
    (data.runs.dir("nightly") / f"{d}.json").write_text(json.dumps(report))


def test_signals_dropped_by_the_nightly_review_say_why(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    _nightly_signal_files(data)
    by = {x["symbol"]: x for x in data.signals(None)["data"]["signals"]}
    assert by["BBB"]["taken"] is True
    assert by["CCC"]["status"] == "vetoed" and "needs more info" in by["CCC"]["skip_reason"]
    assert by["DDD"]["status"] == "capped"
    assert by["FFF"]["skip_reason"] == "reward_risk 1.60 below min 2.0"  # the size step's own skip comes first
    for sym in ("EEE", "GGG"):  # sized or not, beyond the review cap: dropped by the review step
        assert by[sym]["status"] == "not_reviewed", sym
        assert "max_candidates_per_day=3" in by[sym]["skip_reason"] and by[sym]["review"] is None
    for x in by.values():
        assert "not sized" not in (x["skip_reason"] or "")


def test_signals_when_the_size_step_was_skipped(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    _nightly_signal_files(data, size_status="skip")
    by = {x["symbol"]: x for x in data.signals(None)["data"]["signals"]}
    assert by["BBB"]["taken"] is True  # the ledger still says it was sent
    for sym in ("CCC", "EEE", "FFF", "GGG"):
        assert by[sym]["status"] == "not_sized", sym
        assert by[sym]["skip_reason"].startswith("not sized: the size step was skipped (equity unknown"), sym


def test_a_review_without_a_status_file_vetoes_only_under_require_review_approval(tmp_path: Path) -> None:
    data = live_data(tmp_path)  # reviews on disk, no runs/review_status (`swing review`)
    assert {x["symbol"]: x for x in data.signals(None)["data"]["signals"]}["CCC"]["status"] == "vetoed"
    data.settings.execution.require_review_approval = False
    ccc = {x["symbol"]: x for x in data.signals(None)["data"]["signals"]}["CCC"]
    assert ccc["status"] == "not_sized" and ccc["review"]["decision"] == "needs_more_info"


def test_shadow(app: DashboardApp) -> None:
    sh = get(app, "/api/shadow")["data"]
    rows = {r["group"]: r for r in sh["rows"]}
    pt = rows["pullback_trend"]
    assert pt["n"] == 2 and pt["win_rate"] == 0.5 and pt["avg_r"] == 0.75 and pt["expectancy_r"] == 0.75
    assert pt["profit_factor"] == 2.5 and pt["pending"] == 0
    assert rows["rsi2_meanrev"]["n"] == 0 and rows["rsi2_meanrev"]["pending"] == 1
    assert rows["rsi2_meanrev"]["win_rate"] is None
    assert sh["updated_at"] == "2026-10-05T10:31:00Z"
    reg = {r["group"]: r for r in get(app, "/api/shadow?by=regime")["data"]["rows"]}
    assert reg["healthy_uptrend"]["profit_factor"] is None and reg["healthy_uptrend"]["profit_factor_infinite"]


def test_alerts(app: DashboardApp) -> None:
    alerts = get(app, "/api/alerts")["data"]
    assert [a["event_id"] for a in alerts] == ["alpaca_news:1", "edgar:0001-26-1"]  # P0 and >48 h excluded
    a, b = alerts
    assert a["priority"] == "P2" and a["delivered"] is True and a["url"] == "https://example.com/a"
    assert b["url"] is None  # javascript: links never reach the page
    assert b["delivered"] is False and a["symbols"] == ["AAA"] and a["rule_hits"] == ["watchlist_hit"]
    assert len(get(app, "/api/alerts?hours=200")["data"]) == 3


def test_rating_goes_through_rate_alert(app: DashboardApp, data: LiveData) -> None:
    resp = app.handle("POST", "/api/alerts/alpaca_news:1/rate", JSON_POST, b'{"rating": "useful"}')
    assert resp.status == 200 and resp.json()["data"]["rating"] == "useful"
    resp = app.handle("POST", "/api/alerts/alpaca_news%3A1/rate", JSON_POST, b'{"rating": "traded"}')
    assert resp.json()["data"] == {"event_id": "alpaca_news:1", "rating": "traded", "previous": "useful"}
    log = EventLog(data.event_log_path)
    try:
        ev = log.get("alpaca_news:1")
        assert ev.meta["rating"] == "traded" and ev.meta["rating_source"] == "dashboard"
        rows = log._conn.execute("SELECT rating, source FROM alert_ratings ORDER BY id").fetchall()
        assert [tuple(r) for r in rows] == [("useful", "dashboard"), ("traded", "dashboard")]
    finally:
        log.close()
    assert get(app, "/api/alerts")["data"][0]["rating"] == "traded"
    unknown = app.handle("POST", "/api/alerts/alpaca_news:999/rate", JSON_POST, b'{"rating": "noise"}').json()
    assert unknown["ok"] is False and "unknown event" in unknown["unavailable"]


def test_reads_never_write_the_event_log(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    path = data.event_log_path
    before = path.read_bytes()
    for fn in (data.summary, lambda: data.alerts(48)):
        fn()
    assert path.read_bytes() == before


def test_journal(app: DashboardApp) -> None:
    j = get(app, "/api/journal")["data"]
    assert j["date"] == "2026-10-05" and "hello" in j["markdown"]
    assert j["available_dates"] == ["2026-10-05", "2026-10-02"]
    assert get(app, "/api/journal?date=2026-10-02")["data"]["markdown"].startswith("# Trade journal 2026-10-02")
    assert get(app, "/api/journal?date=2026-01-01")["ok"] is False


def test_replay(app: DashboardApp) -> None:
    r = get(app, "/api/replay")["data"]
    assert [x["id"] for x in r["runs"]] == ["run-b", "run-a"]
    latest = r["latest"]
    assert latest["id"] == "run-b" and latest["summary"] == {"trades": 20}
    assert latest["by_regime"] == [{"regime": "narrow_uptrend", "n": 4}]
    assert latest["equity_curve"] == [{"t": "2026-09-29", "equity": 1.0}, {"t": "2026-09-30", "equity": 1.1}]


def test_kill_switch_trip_creates_the_file(app: DashboardApp, data: LiveData) -> None:
    assert not data.kill_path.exists()
    assert app.handle("POST", "/api/killswitch/trip", JSON_POST, b'{"confirm": "yes"}').status == 400
    assert not data.kill_path.exists()
    resp = app.handle("POST", "/api/killswitch/trip", JSON_POST, b'{"confirm": "TRIP"}')
    assert resp.status == 200
    assert resp.json()["data"] == {"tripped": True, "path": str(data.kill_path)}
    assert data.kill_path.exists() and "dashboard" in data.kill_path.read_text()
    ks = get(app, "/api/summary")["data"]["kill_switch"]
    assert ks["tripped"] is True and "dashboard" in ks["reason"]
    from swing_engine.risk.killswitch import is_tripped

    assert is_tripped(data.kill_path)
    for path in ("/api/killswitch/clear", "/api/killswitch/reset"):
        assert app.handle("POST", path, JSON_POST, b'{"confirm": "TRIP"}').status == 404
    assert data.kill_path.exists()


def test_no_secret_in_any_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY", FAKE_KEY)
    monkeypatch.setenv("ALPACA_SECRET_KEY", FAKE_SECRET)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE_ANTHROPIC)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", FAKE_TELEGRAM)
    monkeypatch.setattr("swing_engine.core.config.load_secrets", lambda: fake_secrets())  # never the real .env
    data = live_data(tmp_path)
    app = DashboardApp(data)  # the production path: collects secrets from the provider and the environment
    bodies = []
    for target in ENDPOINTS:
        bodies.append(app.handle("GET", target, H).body)
    bodies.append(app.handle("POST", "/api/alerts/alpaca_news:1/rate", JSON_POST, b'{"rating": "noise"}').body)
    bodies.append(app.handle("POST", "/api/killswitch/trip", JSON_POST, b'{"confirm": "TRIP"}').body)
    blob = b"\n".join(bodies)
    for secret in (FAKE_KEY, FAKE_SECRET, FAKE_ANTHROPIC, FAKE_TELEGRAM, "PA-SECRET-NUMBER"):
        assert secret.encode() not in blob, secret
    assert b"[redacted]" in blob  # the nightly step detail quoting the Anthropic key was scrubbed


def test_fresh_install_never_errors(tmp_path: Path) -> None:
    settings = Settings.model_validate({
        "data": {"store_path": str(tmp_path / "d" / "s.duckdb"), "event_log_path": str(tmp_path / "d" / "e.sqlite")},
        "execution": {"ledger_file": str(tmp_path / "st" / "o.sqlite")},
        "risk": {"kill_switch_file": str(tmp_path / "st" / "KILL")},
    })
    data = LiveData(None, settings=settings, secrets=no_key_secrets(), http_get=FakeHTTP(), journal_dirs=[tmp_path],
                    now=lambda: NOW)
    app = DashboardApp(data, secrets=[])
    results = {t: get(app, t) for t in ENDPOINTS}
    assert results["/api/health"]["ok"] and results["/api/summary"]["ok"]
    s = results["/api/summary"]["data"]
    assert s["account"]["equity"] is None and "unavailable" in s["account"]
    assert s["nightly"]["steps"] == [] and s["monitor"]["feeds"] == {}
    for t in ENDPOINTS[2:]:
        assert results[t]["ok"] is False, t
    assert not (tmp_path / "d").exists()  # reading never creates the store or the event log
    assert not (tmp_path / "st").exists()


def test_corrupt_run_file_is_a_reason(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    (data.runs.root / "signals" / "2026-10-05.json").write_text("{not json")
    s = data.signals(None)
    assert s["ok"] is False and "unreadable" in s["unavailable"]
    assert data.summary()["ok"] is True


def test_broken_ledger_does_not_break_positions(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    data.ledger_path.unlink()
    data.ledger_path.write_bytes(b"this is not sqlite" * 100)
    try:
        sqlite3.connect(data.ledger_path).execute("select 1 from orders")
    except sqlite3.DatabaseError:
        pass
    pos = data.positions()
    assert pos["ok"] is True and "ledger" in pos["partial"]
    assert pos["data"][0]["current_stop"] == 40.5


def test_broker_is_cached_and_only_read(tmp_path: Path) -> None:
    brokers: list[FakeBroker] = []

    def factory() -> FakeBroker:
        brokers.append(FakeBroker())
        return brokers[-1]

    data = live_data(tmp_path, broker=factory)
    for _ in range(3):
        data.summary()
        data.positions()
    assert len(brokers) == 1 and brokers[0].account_calls == 1
    assert brokers[0].client.calls.count("get_all_positions") == 1


def test_chart_levels_for_a_resting_entry(app: DashboardApp) -> None:
    c = get(app, "/api/chart/BBB")["data"]  # not held, but its swing-* bracket entry is still working
    assert c["levels"] == {"entry": 91.0, "stop": 87.0, "target": 99.0, "current_stop": None}
    assert ("signal", "2026-10-05") in {(m["kind"], m["t"]) for m in c["markers"]}


def test_result_cache_is_bounded() -> None:
    from swing_engine.dashboard.data import TTLCache

    cache = TTLCache(max_items=3)
    for i in range(5):
        cache.put(f"k{i}", i)
    assert cache.get("k0", 60) is None and cache.get("k1", 60) is None
    assert [cache.get(f"k{i}", 60) for i in (2, 3, 4)] == [2, 3, 4]
    cache.put("k2", 22)  # re-put moves the key to the newest end
    cache.put("k5", 5)
    assert cache.get("k3", 60) is None and cache.get("k2", 60) == 22


def test_ledger_row_prefers_newest_entry_over_older_filled_trade(tmp_path: Path) -> None:
    from swing_engine.core.models import OrderIntent, Side
    from swing_engine.execution.ledger import OrderLedger

    data = live_data(tmp_path)  # AAA: a September row already `filled`
    ledger = OrderLedger(tmp_path / "state" / "orders.sqlite")
    newer = OrderIntent(symbol="AAA", side=Side.LONG, qty=50, entry_limit=45.0, stop=43.0, target=50.0,
                        strategy="sr_bounce", client_order_id="swing-sr_bounce-AAA-20261006-long", risk_dollars=100.0)
    ledger.reserve(newer, "autopilot:paper")
    ledger.update(newer.client_order_id, "accepted", "brk-9", {"broker_order_id": "brk-9", "status": "accepted"})
    ledger.close()
    row = data._ledger_for_symbol("AAA")
    assert row is not None and row["intent"]["stop"] == 43.0 and row["strategy"] == "sr_bounce"
