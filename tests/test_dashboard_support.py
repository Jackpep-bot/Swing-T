"""Shared fixtures for the dashboard tests: a temp store / event log / ledger / run files, a read-only fake
broker (any order call fails the test) and a fake portfolio-history endpoint. No network anywhere."""
from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import Event, OrderIntent, Priority, Side
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store
from swing_engine.execution.ledger import OrderLedger
from swing_engine.monitor.eventlog import EventLog

NOW = datetime(2026, 10, 6, 19, 45, tzinfo=UTC)  # Tuesday 15:45 ET: market open
AS_OF = date(2026, 10, 5)
FAKE_KEY = "PKFAKEKEY1234567890ZZ"
FAKE_SECRET = "fakeSecretValue0987654321abcdefXYZ"
FAKE_ANTHROPIC = "sk-ant-fake-0000111122223333"
FAKE_TELEGRAM = "123456789:AAFakeTelegramTokenValue"


def fake_secrets(**overrides: Any) -> Secrets:
    values: dict[str, Any] = {
        "alpaca_api_key": FAKE_KEY, "alpaca_secret_key": FAKE_SECRET, "alpaca_paper": True,
        "anthropic_api_key": FAKE_ANTHROPIC, "telegram_bot_token": FAKE_TELEGRAM,
    }
    values.update(overrides)
    return Secrets(_env_file=None, **values)


def no_key_secrets() -> Secrets:
    return Secrets(_env_file=None, alpaca_api_key=None, alpaca_secret_key=None, alpaca_paper=True)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    return path


def make_settings(root: Path) -> Settings:
    return Settings.model_validate({
        "data": {"store_path": str(root / "data" / "store.duckdb"), "event_log_path": str(root / "data" / "events.sqlite")},
        "execution": {"ledger_file": str(root / "state" / "orders.sqlite")},
        "risk": {"kill_switch_file": str(root / "state" / "KILL")},
        "strategies": {"pullback_trend": {"enabled": True, "max_hold_days": 20}},
    })


def _path(i: int, base: float, drift: float) -> float:
    return base * math.exp(drift * i + 0.02 * math.sin(i / 5.0))


def build_store(root: Path) -> Path:
    path = root / "data" / "store.duckdb"
    days = trading_days(date(2025, 6, 2), AS_OF)
    rows = []
    for sym, base, drift in (("SPY", 500.0, 0.0006), ("AAA", 40.0, 0.001), ("BBB", 90.0, -0.0002)):
        for i, d in enumerate(days):
            c = _path(i, base, drift)
            rows.append({"symbol": sym, "ts": pd.Timestamp(d), "open": c * 0.995, "high": c * 1.01, "low": c * 0.985,
                         "close": c, "volume": 1_000_000 + i})
    breadth = pd.DataFrame({
        "date": days[-300:], "pct_above_50": [40 + (i % 30) for i in range(300)],
        "pct_above_200": [55.0] * 300, "ratio_10d": [1.0 + (i % 7) / 10 for i in range(300)],
        "n_symbols": [56] * 300,
    })
    shadow = pd.DataFrame([
        {"strategy": "pullback_trend", "symbol": "AAA", "as_of": date(2026, 9, 1), "side": "long", "entry": 40.0,
         "stop": 38.0, "target": 45.0, "taken": True, "regime": "healthy_uptrend", "hit": "target_hit",
         "result_r": 2.5, "mfe_r": 2.6, "mae_r": 0.3, "recorded_at": "2026-09-01T10:31:00+00:00",
         "graded_through": date(2026, 9, 30)},
        {"strategy": "pullback_trend", "symbol": "BBB", "as_of": date(2026, 9, 2), "side": "long", "entry": 90.0,
         "stop": 87.0, "target": 97.0, "taken": False, "regime": "narrow_uptrend", "hit": "stop_hit",
         "result_r": -1.0, "mfe_r": 0.4, "mae_r": 1.0, "recorded_at": "2026-09-02T10:31:00+00:00",
         "graded_through": date(2026, 9, 30)},
        {"strategy": "rsi2_meanrev", "symbol": "CCC", "as_of": date(2026, 10, 5), "side": "long", "entry": 20.0,
         "stop": 19.0, "target": 21.0, "taken": False, "regime": "narrow_uptrend", "hit": "pending",
         "result_r": None, "mfe_r": None, "mae_r": None, "recorded_at": "2026-10-05T10:31:00+00:00",
         "graded_through": date(2026, 10, 5)},
    ])
    with Store(path) as store:
        store.write_bars(pd.DataFrame(rows))
        store.write_table("breadth", breadth, ["date"])
        store.write_table("shadow_signals", shadow, ["strategy", "symbol", "as_of"])
    return path


def build_eventlog(root: Path) -> Path:
    path = root / "data" / "events.sqlite"
    log = EventLog(path)
    spec = [
        ("alpaca_news:1", "alpaca_news", "news", 1, Priority.P2, ["AAA"], "AAA beats estimates",
         "https://example.com/a", ["watchlist_hit"]),
        ("edgar:0001-26-1", "edgar", "filing", 3, Priority.P3, ["AAA"], "AAA 8-K item 2.02",
         "javascript:alert(1)", ["held_8k"]),
        ("nasdaq_halts:x", "nasdaq_halts", "halt", 5, Priority.P0, ["ZZZ"], "ZZZ halted (log only)", None, []),
        ("alpaca_news:old", "alpaca_news", "news", 100, Priority.P2, ["BBB"], "old news", None, ["watchlist_hit"]),
    ]
    for eid, source, kind, hours, prio, syms, title, url, rules in spec:
        ts = NOW - timedelta(hours=hours)
        log.append(Event(event_id=eid, source=source, kind=kind, ts_source=ts, ts_received=ts, symbols=syms,
                         title=title, url=url, priority=prio, rule_hits=rules))
    with log._lock:  # record_alert stamps "now"; pin the audit rows inside the 24 h window of NOW
        log._conn.execute(
            "INSERT INTO alerts (event_id, ts, priority, channels, delivered, reason) VALUES (?,?,?,?,?,?)",
            ("alpaca_news:1", (NOW - timedelta(hours=1)).isoformat(), "P2", '["telegram"]', 1, ""))
        log._conn.execute(
            "INSERT INTO alerts (event_id, ts, priority, channels, delivered, reason) VALUES (?,?,?,?,?,?)",
            ("edgar:0001-26-1", (NOW - timedelta(hours=3)).isoformat(), "P3", '["pushover"]', 0, "quiet"))
    log.close()
    return path


def build_ledger(root: Path) -> Path:
    path = root / "state" / "orders.sqlite"
    ledger = OrderLedger(path)
    intent = OrderIntent(symbol="AAA", side=Side.LONG, qty=100, entry_limit=41.0, stop=38.0, target=48.5,
                         strategy="pullback_trend", client_order_id="swing-pullback_trend-AAA-20260928-long",
                         risk_dollars=300.0)
    ledger.reserve(intent, "autopilot:paper")
    ledger.update(intent.client_order_id, "filled", "brk-1", {
        "broker_order_id": "brk-1", "status": "filled",
        "raw": {"id": "brk-1", "filled_at": "2026-09-29T13:31:05Z", "filled_avg_price": "40.5", "filled_qty": "100"},
    })
    intent2 = OrderIntent(symbol="BBB", side=Side.LONG, qty=10, entry_limit=91.0, stop=87.0, target=99.0,
                          strategy="sr_bounce", client_order_id="swing-sr_bounce-BBB-20261005-long", risk_dollars=40.0)
    ledger.reserve(intent2, "autopilot:paper")
    ledger.update(intent2.client_order_id, "accepted", "brk-2", {"broker_order_id": "brk-2", "status": "accepted"})
    ledger.close()
    return path


def build_runs(root: Path) -> Path:
    runs = root / "data" / "runs"
    d = AS_OF.isoformat()
    signals = [
        {"strategy": "sr_bounce", "symbol": "BBB", "side": "long", "as_of": d, "entry": 90.5, "stop": 87.0,
         "target": 99.0, "reward_risk": 2.4, "score": 3.0, "features": {"rank_score": 0.61}, "notes": "bounce"},
        {"strategy": "pullback_trend", "symbol": "CCC", "side": "long", "as_of": d, "entry": 20.0, "stop": 19.0,
         "target": 23.0, "reward_risk": 3.0, "score": 2.5, "features": {}, "notes": ""},
        {"strategy": "pullback_trend", "symbol": "DDD", "side": "long", "as_of": d, "entry": 30.0, "stop": 29.0,
         "target": 33.0, "reward_risk": 3.0, "score": 2.0, "features": {}, "notes": ""},
        {"strategy": "rsi2_meanrev", "symbol": "EEE", "side": "long", "as_of": d, "entry": 50.0, "stop": 48.0,
         "target": 51.0, "reward_risk": 0.5, "score": 1.0, "features": {"max_hold_days": 5.0}, "notes": ""},
        {"strategy": "sr_bounce", "symbol": "FFF", "side": "long", "as_of": d, "entry": 10.0, "stop": 9.5,
         "target": 10.8, "reward_risk": 1.6, "score": 0.5, "features": {}, "notes": ""},
        {"strategy": "pullback_trend", "symbol": "GGG", "side": "long", "as_of": d, "entry": 60.0, "stop": 57.0,
         "target": 69.0, "reward_risk": 3.0, "score": 0.4, "features": {}, "notes": ""},
    ]
    write_json(runs / "signals" / f"{d}.json", signals)
    write_json(runs / "signals" / "2026-09-28.json", [
        {"strategy": "pullback_trend", "symbol": "AAA", "side": "long", "as_of": "2026-09-28", "entry": 40.8,
         "stop": 38.0, "target": 48.5, "reward_risk": 2.7, "score": 2.0, "features": {"max_hold_days": 15.0}}])
    write_json(runs / "reviews" / f"{d}.json", [
        {"symbol": "CCC", "strategy": "pullback_trend", "thesis": "No catalyst data.", "catalyst_within_hold_window": False,
         "event_risk_flags": ["earnings_in_window"], "news_contradicts_setup": False, "liquidity_concern": False,
         "rubric_scores": {"setup_quality": 3}, "decision": "needs_more_info", "evidence": ["x"]},
        {"symbol": "DDD", "strategy": "pullback_trend", "thesis": "Clean.", "catalyst_within_hold_window": False,
         "event_risk_flags": [], "news_contradicts_setup": False, "liquidity_concern": False,
         "rubric_scores": {}, "decision": "approve", "evidence": []},
    ])

    def intent(sym: str, strat: str) -> dict[str, Any]:
        return {"symbol": sym, "side": "long", "qty": 10, "entry_limit": 1.0, "stop": 0.5, "target": 2.0,
                "strategy": strat, "client_order_id": f"swing-{strat}-{sym}-20261005-long", "risk_dollars": 5.0}

    # as ops.nightly leaves it: the review step rewrote the file without CCC (needs_more_info), and the audit has
    # no entry for it (run_autopilot never saw the vetoed intent)
    write_json(runs / "intents" / f"{d}.json", [intent("BBB", "sr_bounce"), intent("DDD", "pullback_trend"),
                                               intent("GGG", "pullback_trend")])
    write_json(runs / "autopilot" / f"{d}.json", {"as_of": d, "runs": [
        {"as_of": d, "broker": "alpaca", "paper": True, "mode": "paper", "dry_run": False,
         "account": {"equity": 101000.0, "last_equity": 100500.0, "cash": 50000.0, "buying_power": 100000.0},
         "entries": [
             {"kind": "entry", "symbol": "DDD", "status": "capped", "strategy": "pullback_trend",
              "client_order_id": "swing-pullback_trend-DDD-20261005-long", "reason": ""},
         ], "exits": []},
        {"as_of": d, "broker": "alpaca", "paper": True, "mode": "dry_run", "dry_run": True,
         "account": {"equity": 101100.0, "last_equity": 100500.0},
         "entries": [{"kind": "entry", "symbol": "GGG", "status": "planned", "strategy": "pullback_trend",
                      "client_order_id": "swing-pullback_trend-GGG-20261005-long", "reason": ""}], "exits": []},
    ]})
    write_json(runs / "autopilot" / "2026-10-02.json", {"as_of": "2026-10-02", "runs": [
        {"broker": "alpaca", "dry_run": False, "account": {"equity": 100200.0, "last_equity": 100000.0},
         "entries": [], "exits": []}]})
    write_json(runs / "nightly" / f"{d}.json", {
        "as_of": d, "provider": "massive", "dry_run": False, "started_at": "2026-10-05T10:30:00Z",
        "finished_at": "2026-10-05T10:33:00Z", "elapsed_s": 180.0,
        "steps": [
            {"name": "ingest", "status": "ok", "elapsed_s": 40.0, "detail": "ok", "data": {}},
            {"name": "size", "status": "ok", "elapsed_s": 0.0, "detail": "4 intents",
             "data": {"skipped": {"sr_bounce:FFF": "reward_risk 1.60 below min 2.0"}}},
            {"name": "review", "status": "fail", "elapsed_s": 1.0,
             "detail": f"AuthenticationError: bad key {FAKE_ANTHROPIC}", "data": {}},
        ],
    })
    write_json(runs / "regime" / f"{d}.json", {
        "as_of": d, "regime": "narrow_uptrend",
        "market_state": {"as_of": d, "spy_trend": "up", "vol_regime": "high", "breadth": "neutral",
                         "regime": "narrow_uptrend", "notes": ["SPY uptrend but breadth neutral"],
                         "inputs": {"pct_above_50": 55.4, "pct_above_200": 60.7, "ratio_10d": 1.05, "n_symbols": 56}},
        "allowed": {"pullback_trend": 0.5, "rsi2_meanrev": 0.75, "sr_bounce": 0.5},
        "blocked": {"breakout_52w": "not in the playbook table for this regime"},
    })
    write_json(runs / "replay" / "run-a.json", {
        "id": "run-a", "start": "2024-10-01", "end": "2026-09-30", "created_at": "2026-10-01T20:00:00Z",
        "summary": {"trades": 10, "win_rate": 0.5},
        "by_strategy": {"pullback_trend": {"n": 6, "win_rate": 0.5}},
        "equity_curve": {"2026-09-29": 100000.0, "2026-09-30": 100500.0},
    })
    write_json(runs / "replay" / "run-b.json", {
        "start": "2025-01-01", "end": "2026-09-30", "created_at": "2026-10-04T20:00:00Z",
        "metrics": {"trades": 20}, "by_regime": [{"regime": "narrow_uptrend", "n": 4}],
        "equity_curve": [{"date": "2026-09-29", "equity": 1.0}, {"date": "2026-09-30", "equity": 1.1}],
    })
    return runs


def build_journal(root: Path) -> Path:
    j = root / "journal"
    j.mkdir(parents=True, exist_ok=True)
    (j / "2026-10-02.md").write_text("# Trade journal 2026-10-02\n", encoding="utf-8")
    (j / "2026-10-05.md").write_text("# Trade journal 2026-10-05\n\nhello\n", encoding="utf-8")
    (j / "notes.md").write_text("not a date", encoding="utf-8")
    return j


# ----------------------------------------------------------------------------------------------- fakes
class _NoTrading:
    """Any order-placing call is a test failure: the dashboard is read-only toward the broker."""

    def __getattr__(self, name: str) -> Any:
        if any(w in name for w in ("submit", "cancel", "replace", "close", "place")):
            raise AssertionError(f"dashboard called a trading method: {name}")
        raise AttributeError(name)


class FakeClient(_NoTrading):
    def __init__(self, positions: list[dict[str, Any]], open_orders: list[dict[str, Any]],
                 closed: list[dict[str, Any]]) -> None:
        self._positions, self._open, self._closed = positions, open_orders, closed
        self.calls: list[str] = []

    def get_all_positions(self) -> list[dict[str, Any]]:
        self.calls.append("get_all_positions")
        return self._positions

    def get_orders(self, req: Any) -> list[dict[str, Any]]:
        self.calls.append(f"get_orders:{getattr(req.status, 'value', req.status)}")
        return self._closed if "closed" in str(getattr(req.status, "value", req.status)) else self._open

    def get_account(self) -> dict[str, Any]:
        return {"equity": "101500", "last_equity": "101000", "cash": "40000", "buying_power": "80000"}


class FakeBroker(_NoTrading):
    paper = True

    def __init__(self) -> None:
        positions = [{"symbol": "AAA", "qty": "100", "side": "long", "avg_entry_price": "40.5", "current_price": "44.0",
                      "market_value": "4400", "unrealized_pl": "350", "unrealized_plpc": "0.0864",
                      "asset_id": "secret-ish-internal-id", "exchange": "NASDAQ"}]
        open_orders = [
            {"id": "brk-1", "client_order_id": "swing-pullback_trend-AAA-20260928-long", "symbol": "AAA", "side": "buy",
             "type": "limit", "qty": "100", "filled_qty": "100", "limit_price": "41.0", "status": "filled",
             "order_class": "bracket", "submitted_at": "2026-09-28T10:31:00Z", "filled_at": "2026-09-29T13:31:05Z",
             "filled_avg_price": "40.5",
             "legs": [
                 {"id": "leg-stop", "side": "sell", "type": "stop", "qty": "100", "stop_price": "40.5", "status": "new"},
                 {"id": "leg-tp", "side": "sell", "type": "limit", "qty": "100", "limit_price": "48.5", "status": "new"},
             ]},
            {"id": "brk-2", "client_order_id": "swing-sr_bounce-BBB-20261005-long", "symbol": "BBB", "side": "buy",
             "type": "limit", "qty": "10", "filled_qty": "0", "limit_price": "91.0", "status": "new",
             "order_class": "bracket", "submitted_at": "2026-10-05T10:32:00Z", "legs": []},
        ]
        closed = [
            {"id": "c-1", "client_order_id": "manual-1", "symbol": "AAA", "side": "sell", "type": "market", "qty": "5",
             "filled_qty": "5", "status": "filled", "submitted_at": "2026-09-30T14:00:00Z",
             "filled_at": "2026-09-30T14:00:01Z", "filled_avg_price": "42.0", "legs": []},
        ]
        self.client = FakeClient(positions, open_orders, closed)
        self.account_calls = 0

    def account(self) -> dict[str, Any]:
        self.account_calls += 1
        return {"equity": 101500.0, "last_equity": 101000.0, "cash": 40000.0, "buying_power": 80000.0,
                "portfolio_value": 101500.0, "status": "ACTIVE", "raw": {"account_number": "PA-SECRET-NUMBER"}}

    def open_orders(self) -> list[dict[str, Any]]:
        return self.client._open


class FakeHTTP:
    def __init__(self, status: int = 200, body: Any = None) -> None:
        self.status = status
        days = trading_days(date(2026, 7, 1), AS_OF)
        stamps = [int(datetime(d.year, d.month, d.day, 4, 0, tzinfo=UTC).timestamp()) for d in days]
        equity: list[float | None] = [100000.0 + 50 * i for i in range(len(days))]
        equity[0] = 0.0  # before the account existed: dropped
        self.body = body if body is not None else {"timestamp": stamps, "equity": equity, "timeframe": "1D"}
        self.calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    def __call__(self, url: str, params: Any, headers: Any, timeout: float) -> tuple[int, Any]:
        self.calls.append((url, dict(params), dict(headers)))
        return self.status, self.body


def build_all(root: Path) -> dict[str, Any]:
    build_store(root)
    build_eventlog(root)
    build_ledger(root)
    build_runs(root)
    journal = build_journal(root)
    return {"settings": make_settings(root), "journal": journal}


def live_data(root: Path, *, broker: Any | None = "fake", http: Any | None = None, secrets: Secrets | None = None,
              **kw: Any) -> Any:
    from swing_engine.dashboard.data import LiveData

    env = build_all(root)
    factory = (lambda: FakeBroker()) if broker == "fake" else broker
    return LiveData(None, settings=env["settings"], secrets=secrets or fake_secrets(), broker_factory=factory,
                    http_get=http or FakeHTTP(), journal_dirs=[env["journal"]], now=lambda: NOW, **kw)
