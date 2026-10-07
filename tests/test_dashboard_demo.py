"""Demo mode: every endpoint answers with deterministic, contract-shaped fake data."""
from __future__ import annotations

import json

import pytest

from swing_engine.dashboard.demo import DEMO_KILL_PATH, DemoData
from swing_engine.dashboard.server import DashboardApp
from swing_engine.risk.killswitch import resolve_state_path

H = {"Host": "127.0.0.1:8765", "X-Swing-Dashboard": "1"}  # what the page's fetch() sends
JSON_POST = {**H, "Content-Type": "application/json"}


@pytest.fixture()
def app() -> DashboardApp:
    return DashboardApp(DemoData(), secrets=[])


def get(app: DashboardApp, target: str) -> dict:
    resp = app.handle("GET", target, H)
    assert resp.status == 200, (target, resp.body[:300])
    body = resp.json()
    assert body["ok"] is True, (target, body)
    return body["data"]


def test_health_and_summary(app: DashboardApp) -> None:
    health = get(app, "/api/health")
    assert health["demo"] is True and health["version"]
    s = get(app, "/api/summary")
    assert s["mode"] == "DEMO"
    assert set(s["account"]) >= {"equity", "last_equity", "cash", "buying_power", "day_pl", "day_pl_pct"}
    assert s["kill_switch"] == {"tripped": False, "path": DEMO_KILL_PATH, "reason": ""}
    assert {"as_of", "finished_at", "ok", "steps"} <= set(s["nightly"])
    assert all({"name", "status", "detail", "elapsed_s"} <= set(st) for st in s["nightly"]["steps"])
    assert {"last_event_at", "feeds", "alerts_24h"} <= set(s["monitor"])
    assert {"is_open", "next_open", "next_close"} <= set(s["clock"])
    assert s["generated_at"]


def test_regime(app: DashboardApp) -> None:
    r = get(app, "/api/regime")
    assert {"as_of", "regime", "spy_trend", "vol_regime", "breadth", "notes"} <= set(r["state"])
    assert r["allowed"] and all(0 < v <= 1 for v in r["allowed"].values())
    assert r["breadth_history"] and {"date", "pct_above_50", "pct_above_200", "ratio_10d"} <= set(r["breadth_history"][0])
    older = get(app, "/api/regime?date=2026-09-01")
    assert older["state"]["as_of"] == "2026-09-01"
    assert older["breadth_history"][-1]["date"] <= "2026-09-01"


@pytest.mark.parametrize("period", ["1M", "3M", "6M", "1Y", "ALL", "6m"])
def test_equity_periods(app: DashboardApp, period: str) -> None:
    e = get(app, f"/api/equity?period={period}")
    assert e["account"] and e["spy"] and e["normalized"]
    first = e["normalized"][0]
    assert first["account"] == 100.0 and first["spy"] == 100.0
    assert set(e["stats"]) >= {"return_pct", "spy_return_pct", "max_drawdown_pct"}
    assert e["stats"]["max_drawdown_pct"] <= 0


def test_six_months_of_equity(app: DashboardApp) -> None:
    e = get(app, "/api/equity?period=6M")
    assert len(e["account"]) > 120


def test_positions_have_levels(app: DashboardApp) -> None:
    rows = get(app, "/api/positions")
    assert len(rows) >= 3
    keys = {"symbol", "side", "qty", "avg_entry", "current", "market_value", "unrealized_pl", "unrealized_plpc",
            "strategy", "stop", "target", "risk_per_share", "r_multiple", "days_held", "max_hold_days", "opened_at"}
    for p in rows:
        assert keys <= set(p)
        assert p["stop"] < p["current"] < p["target"]
        assert p["stop"] < p["avg_entry"] < p["target"]
    assert any(p["current_stop"] != p["stop"] for p in rows)  # one stop trailed to breakeven


@pytest.mark.parametrize("status", ["open", "closed"])
def test_orders(app: DashboardApp, status: str) -> None:
    rows = get(app, f"/api/orders?status={status}&limit=5")
    assert 0 < len(rows) <= 5
    keys = {"id", "client_order_id", "symbol", "side", "type", "qty", "filled_qty", "limit_price", "stop_price",
            "status", "submitted_at", "filled_at", "filled_avg_price", "strategy", "legs"}
    assert all(keys <= set(o) for o in rows)


def test_chart_for_position_and_unknown_symbol(app: DashboardApp) -> None:
    sym = get(app, "/api/positions")[0]["symbol"]
    c = get(app, f"/api/chart/{sym}?days=120")
    assert c["symbol"] == sym and 80 <= len(c["bars"]) <= 90  # 120 calendar days of weekday sessions
    assert c["bars"][0]["t"] >= "2026-06-08" and c["bars"][-1]["t"] == "2026-10-06"
    assert {"t", "o", "h", "l", "c", "v"} <= set(c["bars"][0])
    assert c["sma20"] and c["sma50"] and c["sma50"][0]["t"] >= c["bars"][0]["t"]
    assert c["levels"]["stop"] and c["levels"]["target"] and c["levels"]["entry"]
    assert {m["kind"] for m in c["markers"]} >= {"entry", "signal"}
    other = get(app, "/api/chart/ZZZZ")
    assert other["levels"] == {"entry": None, "stop": None, "target": None, "current_stop": None}


def test_signals_taken_and_skipped_with_reviews(app: DashboardApp) -> None:
    s = get(app, "/api/signals")
    sigs = s["signals"]
    assert any(x["taken"] for x in sigs) and any(not x["taken"] for x in sigs)
    for x in sigs:
        assert {"strategy", "symbol", "side", "entry", "stop", "target", "reward_risk", "score", "taken",
                "skip_reason", "review"} <= set(x)
        assert (x["skip_reason"] is None) == x["taken"]
    reviewed = [x for x in sigs if x["review"]]
    assert {r["review"]["decision"] for r in reviewed} >= {"approve", "needs_more_info", "reject"}
    assert all({"decision", "thesis", "event_risk_flags"} <= set(r["review"]) for r in reviewed)
    missing = app.handle("GET", "/api/signals?date=2020-01-01", H).json()
    assert missing["ok"] is False and "2020-01-01" in missing["unavailable"]


@pytest.mark.parametrize("by", ["strategy", "regime"])
def test_shadow(app: DashboardApp, by: str) -> None:
    sh = get(app, f"/api/shadow?by={by}")
    assert sh["rows"] and sh["updated_at"]
    assert all({"group", "n", "win_rate", "avg_r", "expectancy_r", "profit_factor", "pending"} <= set(r)
               for r in sh["rows"])


def test_alerts_and_rating(app: DashboardApp) -> None:
    alerts = get(app, "/api/alerts?hours=48")
    assert {a["priority"] for a in alerts} >= {"P1", "P2", "P3"}
    assert alerts == sorted(alerts, key=lambda a: a["ts"], reverse=True)
    assert len(get(app, "/api/alerts?hours=6")) < len(alerts)
    target = next(a for a in alerts if a["rating"] is None)
    resp = app.handle("POST", f"/api/alerts/{target['event_id']}/rate", JSON_POST, b'{"rating": "traded"}')
    assert resp.status == 200 and resp.json()["data"] == {"event_id": target["event_id"], "rating": "traded"}
    again = {a["event_id"]: a for a in get(app, "/api/alerts?hours=48")}
    assert again[target["event_id"]]["rating"] == "traded"
    unknown = app.handle("POST", "/api/alerts/nope:1/rate", JSON_POST, b'{"rating": "noise"}').json()
    assert unknown["ok"] is False


def test_journal_and_replay(app: DashboardApp) -> None:
    j = get(app, "/api/journal")
    assert j["markdown"].startswith("# Trade journal") and j["date"] == j["available_dates"][0]
    r = get(app, "/api/replay")
    assert r["runs"] and {"id", "start", "end", "created_at"} <= set(r["runs"][0])
    assert {"summary", "by_strategy", "by_regime", "equity_curve"} <= set(r["latest"])
    assert r["latest"]["equity_curve"][0].keys() == {"t", "equity"}


def test_demo_kill_switch_is_in_memory(app: DashboardApp) -> None:
    real = resolve_state_path("state/KILL")
    existed = real.exists()
    resp = app.handle("POST", "/api/killswitch/trip", JSON_POST, b'{"confirm": "TRIP"}')
    assert resp.status == 200 and resp.json()["data"]["tripped"] is True
    assert get(app, "/api/summary")["kill_switch"]["tripped"] is True
    assert real.exists() == existed  # demo never touches the real file


def test_demo_is_deterministic() -> None:
    a, b = DashboardApp(DemoData(), secrets=[]), DashboardApp(DemoData(), secrets=[])
    for target in ("/api/positions", "/api/equity?period=1Y", "/api/signals", "/api/chart/ORCA", "/api/shadow",
                   "/api/regime", "/api/replay", "/api/summary"):
        assert a.handle("GET", target, H).body == b.handle("GET", target, H).body, target


def test_every_demo_response_is_strict_json(app: DashboardApp) -> None:
    for target in ("/api/health", "/api/summary", "/api/regime", "/api/equity", "/api/positions", "/api/orders",
                   "/api/orders?status=closed", "/api/chart/KITE", "/api/signals", "/api/shadow?by=regime",
                   "/api/alerts", "/api/journal", "/api/replay"):
        body = app.handle("GET", target, H).body.decode()
        assert "NaN" not in body and "Infinity" not in body, target
        json.loads(body)
