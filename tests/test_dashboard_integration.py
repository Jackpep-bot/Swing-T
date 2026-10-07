"""Integration fixes found by running the dashboard against the sample store and a brand-new paper account:
no fake day P/L on a new account, a clear SPY note when the store ends before the account history, a nightly
still running, replay units, and demo mode never reading .env."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from swing_engine.dashboard.demo import DemoData
from swing_engine.dashboard.server import DashboardApp
from tests.test_dashboard_support import FakeBroker, FakeHTTP, live_data, write_json

H = {"Host": "localhost:8765", "X-Swing-Dashboard": "1"}  # what the page's fetch() sends


def get(app: DashboardApp, target: str) -> dict[str, Any]:
    resp = app.handle("GET", target, H)
    assert resp.status == 200, (target, resp.body[:400])
    return resp.json()


class NewAccountBroker(FakeBroker):
    """Alpaca reports last_equity 0 for an account that has not seen a close yet."""

    def account(self) -> dict[str, Any]:
        return {"equity": 100000.0, "last_equity": 0.0, "cash": 100000.0, "buying_power": 100000.0,
                "portfolio_value": 100000.0, "status": "ACTIVE"}


def test_new_account_has_no_day_change(tmp_path: Path) -> None:
    app = DashboardApp(live_data(tmp_path, broker=NewAccountBroker), secrets=[])
    acct = get(app, "/api/summary")["data"]["account"]
    assert acct["equity"] == 100000.0 and acct["last_equity"] == 0.0
    assert acct["day_pl"] is None and acct["day_pl_pct"] is None


def test_spy_note_names_where_the_store_ends(tmp_path: Path) -> None:
    after = int(datetime(2026, 10, 6, 4, 0, tzinfo=UTC).timestamp())  # one point after the store's last bar
    http = FakeHTTP(body={"timestamp": [after], "equity": [100000.0], "timeframe": "1D"})
    body = get(DashboardApp(live_data(tmp_path, http=http), secrets=[]), "/api/equity?period=1M")
    assert body["ok"] is True and body["data"]["spy"] == []
    note = body["partial"]["spy"]
    assert "end 2026-10-05" in note and "2026-10-06" in note


def test_nightly_without_finished_at_reads_as_running(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    write_json(data.runs.dir("nightly") / "2026-10-06.json", {
        "as_of": "2026-10-06", "started_at": "2026-10-06T10:30:00Z", "finished_at": None,
        "steps": [{"name": "ingest", "status": "ok", "detail": "", "elapsed_s": 1.0}]})
    n = get(DashboardApp(data, secrets=[]), "/api/summary")["data"]["nightly"]
    assert n["as_of"] == "2026-10-06" and n["ok"] is None


def test_replay_says_its_units(tmp_path: Path) -> None:
    app = DashboardApp(live_data(tmp_path), secrets=[])
    assert get(app, "/api/replay")["data"]["latest"]["units"] == "fraction"
    demo = get(DashboardApp(DemoData(), secrets=[]), "/api/replay")["data"]["latest"]
    assert demo["units"] == "fraction" and abs(demo["summary"]["cagr"]) < 1.5
    assert all("strategy" in row and "trades" in row for row in demo["by_strategy"])


def test_demo_mode_does_not_read_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    import swing_engine.core.config as config

    def boom() -> Any:
        raise AssertionError("demo mode must not read .env")

    monkeypatch.setattr(config, "load_secrets", boom)
    app = DashboardApp(DemoData())  # secrets=None: the server collects them itself
    assert get(app, "/api/summary")["ok"] is True


def test_demo_covers_every_registered_strategy() -> None:
    import importlib

    from swing_engine.core import registry

    importlib.import_module("swing_engine.strategies")
    registry.discover()
    rows = {r["group"] for r in get(DashboardApp(DemoData(), secrets=[]), "/api/shadow")["data"]["rows"]}
    assert set(registry.names("strategy")) <= rows


def test_reviews_from_an_earlier_run_are_flagged(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    app = DashboardApp(data, secrets=[])
    s = get(app, "/api/signals?date=2026-10-05")["data"]
    assert s["review_status"] is None  # no status file: reviews shown as they are
    assert all(x["review"]["current"] is True for x in s["signals"] if x["review"])
    write_json(data.runs.dir("review_status") / "2026-10-05.json",
               {"status": "skip", "detail": "ANTHROPIC_API_KEY not set", "at": "2026-10-06T10:31:00+00:00"})
    s = get(app, "/api/signals?date=2026-10-05")["data"]
    assert s["review_status"] == {"status": "skip", "detail": "ANTHROPIC_API_KEY not set", "at": "2026-10-06T10:31:00Z"}
    reviewed = [x for x in s["signals"] if x["review"]]
    assert reviewed and all(x["review"]["current"] is False for x in reviewed)
    write_json(data.runs.dir("review_status") / "2026-10-05.json", {"status": "ok", "detail": "2 reviewed"})
    assert all(x["review"]["current"] for x in get(app, "/api/signals?date=2026-10-05")["data"]["signals"] if x["review"])
