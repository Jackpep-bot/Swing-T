"""Decision receipts: engine signature, the events table, the nightly's fire / refusal receipts on the sample
provider, the backfill and the dashboard endpoint. No network; in-memory or tmp stores only."""
from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from swing_engine.core import registry, signature
from swing_engine.core.config import Settings
from swing_engine.core.models import OrderIntent, Side, Signal
from swing_engine.dashboard.demo import DemoData
from swing_engine.dashboard.server import DashboardApp
from swing_engine.data.store import Store
from swing_engine.execution.ledger import OrderLedger
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.ops import receipts
from swing_engine.ops.nightly import run_nightly
from swing_engine.research.shadow import SHADOW_TABLE, table_schema
from tests.test_dashboard_support import live_data
from tests.test_ops_nightly import AS_OF, install_contract, make_settings, no_secrets

H = {"Host": "localhost:8765", "X-Swing-Dashboard": "1"}


# ----------------------------------------------------------------------------------------------- signature
def test_signature_is_stable_and_changes_with_the_config(monkeypatch: pytest.MonkeyPatch) -> None:
    a, b = Settings(), Settings()
    sig = signature.engine_signature(a)
    assert sig == signature.engine_signature(b) and len(sig) == signature.SIG_LEN and int(sig, 16) >= 0
    changed = a.model_copy(update={"risk": a.risk.model_copy(update={"risk_per_trade_pct": a.risk.risk_per_trade_pct / 2})})
    assert signature.config_hash(changed) != signature.config_hash(a)
    assert signature.engine_signature(changed) != sig

    def no_git(*args: Any, **kw: Any) -> Any:
        raise FileNotFoundError("git")

    signature.git_sha.cache_clear()
    monkeypatch.setattr(subprocess, "run", no_git)
    try:
        assert signature.git_sha() == signature.NO_GIT
        assert len(signature.engine_signature(a)) == signature.SIG_LEN
        assert signature.engine_signature(a) != signature.engine_signature(changed)
    finally:
        signature.git_sha.cache_clear()


# ----------------------------------------------------------------------------------------------- table
def test_events_round_trip_and_append_only() -> None:
    st = receipts.stamp(Settings())
    rows = [
        receipts.make_event(receipts.FIRE, "broker", "submitted", AS_OF, "s1", "AAA", {"x": float("nan"), "d": AS_OF},
                            key="swing-s1-AAA", **st),
        receipts.make_event(receipts.REFUSAL, "reward_risk", "reward_risk 1.00 below min 2.0", AS_OF, "s1", "BBB", **st),
        receipts.make_event(receipts.REFUSAL, "router", "multiplier 0 in this regime", date(2026, 9, 29), "s2", **st),
    ]
    with Store() as store:
        assert receipts.read_events(store).empty
        assert receipts.write_events(store, rows) == 3
        again = {**rows[0], "reason": "rewritten"}  # same natural key: the first record stays
        assert receipts.write_events(store, [again, *rows]) == 0
        frame = receipts.read_events(store)
        assert list(frame.columns) == list(receipts.EVENTS_SCHEMA) and len(frame) == 3
        assert set(frame["engine_sig"]) == {st["engine_sig"]} and set(frame["run_id"]) == {st["run_id"]}
        fire = receipts.read_events(store, as_of=AS_OF, kind="fire")
        assert fire["reason"].tolist() == ["submitted"] and fire["source"].tolist() == ["live"]
        assert json.loads(fire["payload"].iloc[0]) == {"x": None, "d": AS_OF.isoformat()}
        assert len(receipts.read_events(store, strategy="s1")) == 2
        assert receipts.read_events(store, symbol="BBB", limit=5)["step"].tolist() == ["reward_risk"]
    assert receipts.write_events(object(), rows) == 0  # a broken store is logged, never raised


def test_step_for_maps_the_engines_reason_strings() -> None:
    cases = {
        "reward_risk 1.20 below min 2.0": "reward_risk", "max open positions reached (8/8)": "slot",
        "AAA already has an open position": "slot", "size rounds to zero (binding cap: ff)": "sizing",
        "strategy not allowed by the playbook in this regime": "router", "limit check failed: daily loss": "limits",
        "kill switch tripped at state/KILL": "kill_switch", "max_new_orders_per_day=1 reached": "daily_cap",
        "review decision reject": "review", "daily_order_cap": "daily_cap", "symbol_busy": "slot",
    }
    assert {reason: receipts.step_for(reason) for reason in cases} == cases


# ----------------------------------------------------------------------------------------------- nightly
class _Many:
    """Three signals: two sound ones (so the daily cap of 1 stops the second) and one below the R:R floor."""

    name = "rcpt_many"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: Any = None) -> list[Signal]:
        a, b, c = sorted(set(panel["symbol"]) - {"SPY"})[:3]
        mk = lambda sym, target, score: Signal(  # noqa: E731
            strategy=self.name, symbol=sym, as_of=as_of, entry=50.0, stop=47.5, target=target, score=score,
            features={"atr_14": 1.25})
        return [mk(a, 57.5, 9.0), mk(b, 57.5, 8.0), mk(c, 51.0, 7.0)]


class _Blocked(_Many):
    name = "rcpt_blocked"


class _Shadow(_Many):
    name = "rcpt_shadow"


def test_nightly_writes_fire_and_refusal_receipts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for cls in (_Many, _Blocked, _Shadow):
        monkeypatch.setitem(registry._REGISTRY["strategy"], cls.name, cls)
    install_contract(monkeypatch, table={"rcpt_many": 0.5})
    settings = make_settings(
        tmp_path, risk={"max_position_pct": 50.0}, execution={"max_new_orders_per_day": 1},
        strategies={"sr_bounce": {"enabled": False}, "pullback_trend": {"enabled": False},
                    "rsi2_meanrev": {"enabled": False}, "rcpt_many": {"enabled": True},
                    "rcpt_blocked": {"enabled": True}, "rcpt_shadow": {"enabled": False, "shadow_only": True}},
    )
    broker = PaperSimBroker(starting_cash=80_000.0)
    with Store() as store:
        report = run_nightly(settings, no_secrets(), AS_OF, "sample", None, False, store=store, broker=broker,
                             execute=True, journal_root=tmp_path)
        assert report.ok, report.failed
        events = receipts.read_events(store)
        first = len(events)
        run_nightly(settings, no_secrets(), AS_OF, "sample", None, False, store=store, broker=broker, execute=True,
                    journal_root=tmp_path)
        assert len(receipts.read_events(store)) == first  # a re-run of the same night adds no duplicate receipts
    assert set(events["source"]) == {"live"} and set(events["lane"]) == {"swing"}
    assert set(events["engine_sig"]) == {signature.engine_signature(settings)} and events["run_id"].nunique() == 1
    by = {(r["kind"], r["step"], r["strategy"]): r for r in events.to_dict("records")}

    router = by[("refusal", "router", "rcpt_blocked")]
    assert router["symbol"] == "" and "playbook table" in router["reason"]
    assert json.loads(router["payload"])["regime"] == "healthy_uptrend"

    floor = json.loads(by[("refusal", "reward_risk", "rcpt_many")]["payload"])
    assert "below min" in by[("refusal", "reward_risk", "rcpt_many")]["reason"]
    assert floor["signal"]["target"] == 51.0 and floor["min_reward_risk"] == settings.risk.min_reward_risk
    assert floor["multiplier"] == 0.5 and floor["equity"] == 80_000.0

    capped = by[("refusal", "daily_cap", "rcpt_many")]
    assert "max_new_orders_per_day=1" in capped["reason"]

    fires = events.loc[(events["kind"] == "fire") & (events["step"] == "broker")]
    assert len(fires) == 1 == len(broker.open_orders())
    chain = json.loads(fires["payload"].iloc[0])  # regime -> multiplier -> signal geometry -> size -> order id
    assert chain["regime"] == "healthy_uptrend" and chain["multiplier"] == 0.5
    assert chain["signal"]["stop"] == 47.5 and chain["signal"]["features"] == {"atr_14": 1.25}
    assert chain["intent"]["qty"] > 0 and chain["order"]["client_order_id"] == chain["intent"]["client_order_id"]
    assert chain["approved_by"] == "autopilot:paper" and fires["symbol"].iloc[0] != capped["symbol"]

    shadow = events.loc[events["strategy"] == "rcpt_shadow"]
    assert len(shadow) == 3 and set(shadow["kind"]) == {"fire"} and set(shadow["step"]) == {"scan"}
    assert all(json.loads(p)["shadow"] is True for p in shadow["payload"])


def test_dry_run_and_kill_switch_refusals_name_their_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(registry._REGISTRY["strategy"], _Many.name, _Many)
    install_contract(monkeypatch, table={"rcpt_many": 1.0})
    settings = make_settings(tmp_path, risk={"max_position_pct": 50.0}, strategies={
        "sr_bounce": {"enabled": False}, "pullback_trend": {"enabled": False}, "rsi2_meanrev": {"enabled": False},
        "rcpt_many": {"enabled": True}})
    with Store() as store:
        run_nightly(settings, no_secrets(), AS_OF, "sample", 80_000.0, True, store=store, journal_root=tmp_path)
        dry = receipts.read_events(store, kind="refusal")
        assert "dry run: no orders" in set(dry["reason"]) and not len(receipts.read_events(store, kind="fire"))
        kill = Path(settings.risk.kill_switch_file)
        kill.parent.mkdir(parents=True, exist_ok=True)
        kill.write_text("stop")
        broker = PaperSimBroker(starting_cash=80_000.0)
        run_nightly(settings, no_secrets(), AS_OF, "sample", None, False, store=store, broker=broker, execute=True,
                    journal_root=tmp_path)
        killed = receipts.read_events(store, kind="refusal")
        assert "kill_switch" in set(killed["step"]) and broker.open_orders() == []
        assert not len(receipts.read_events(store, kind="fire"))


# ----------------------------------------------------------------------------------------------- backfill
def _shadow_rows() -> pd.DataFrame:
    base = {"side": "long", "entry_type": "open", "entry": 50.0, "stop": 47.5, "target": 57.5, "reward_risk": 3.0,
            "score": 1.0, "regime": "healthy_uptrend", "source": "live", "recorded_at": "2026-09-01T10:31:00+00:00",
            "entry_date": date(2026, 9, 2), "entry_price": 50.0, "graded_through": date(2026, 9, 30)}
    done = {"hit_5d": "target_hit", "result_r_5d": 3.0, "mfe_r_5d": 3.1, "mae_r_5d": 0.2,
            "exit_date_5d": date(2026, 9, 4), "hit_10d": "target_hit", "result_r_10d": 3.0,
            "exit_date_10d": date(2026, 9, 4), "hit_20d": "pending"}
    rows = [
        {**base, **done, "strategy": "s1", "symbol": "AAA", "as_of": date(2026, 9, 1), "taken": True},  # ordered
        {**base, **done, "strategy": "s1", "symbol": "BBB", "as_of": date(2026, 9, 1), "taken": False},
        {**base, "strategy": "shadow_s", "symbol": "CCC", "as_of": date(2026, 9, 1), "taken": False,
         "hit_5d": "entry_skipped", "skip_reason": "open_through_stop", "exit_date_5d": date(2026, 9, 2)},
        {**base, **done, "strategy": "s1", "symbol": "DDD", "as_of": date(2026, 9, 1), "taken": False,
         "side": "short", "stop": 52.5, "target": 42.5},
    ]
    return pd.DataFrame(rows)


def _intent(symbol: str, day: date) -> OrderIntent:
    return OrderIntent(symbol=symbol, side=Side.LONG, qty=10, entry_limit=50.5, stop=47.5, target=57.5, strategy="s1",
                       client_order_id=f"swing-s1-{symbol}-{day:%Y%m%d}-long", risk_dollars=30.0, signal_as_of=day)


def test_backfill_is_idempotent_and_keeps_live_receipts() -> None:
    settings = Settings.model_validate({"strategies": {"s1": {"enabled": True},
                                                       "shadow_s": {"enabled": False, "shadow_only": True}}})
    ledger = OrderLedger(":memory:")
    ledger.reserve(_intent("AAA", date(2026, 9, 2)), "autopilot:paper")  # a pre-open run: the day after the bar
    ledger.update("swing-s1-AAA-20260902-long", "filled", broker_order_id="b1")
    ledger.reserve(_intent("EEE", date(2026, 9, 3)), "autopilot:paper")
    ledger.update("swing-s1-EEE-20260903-long", "canceled", broker_json={"filled_qty": "0"})
    orders = ledger.all()
    ledger.close()
    with Store() as store:
        store.write_table(SHADOW_TABLE, _shadow_rows(), ["strategy", "symbol", "as_of"], schema=table_schema())
        counts = receipts.backfill(store, settings, orders)
        events = receipts.read_events(store)
        assert counts["written"] == len(events) > 0 and set(events["source"]) == {"backfill"}
        again = receipts.backfill(store, settings, orders)
        assert again["written"] == 0 and len(receipts.read_events(store)) == len(events)

    def rows(kind: str, symbol: str) -> list[dict[str, Any]]:
        return events.loc[(events["kind"] == kind) & (events["symbol"] == symbol)].to_dict("records")

    (fire,) = rows("fire", "AAA")  # the ledger order; its shadow row (taken, one session earlier) adds nothing
    assert fire["step"] == "broker" and fire["as_of"].date() == date(2026, 9, 2) and not rows("refusal", "AAA")
    assert json.loads(fire["payload"])["order"]["broker_order_id"] == "b1"
    assert [r["step"] for r in rows("fire", "EEE")] == ["broker"]
    assert [(r["step"], r["reason"]) for r in rows("refusal", "EEE")] == [("fill", "entry canceled unfilled")]
    (refusal,) = rows("refusal", "BBB")
    assert refusal["step"] == receipts.STEP_UNKNOWN and "not taken" in refusal["reason"]
    (shadow,) = rows("fire", "CCC")
    assert shadow["step"] == "scan" and json.loads(shadow["payload"])["shadow"] is True

    outcomes = {(r["symbol"], json.loads(r["payload"])["horizon"]): r for r in events.to_dict("records")
                if r["kind"] == "outcome"}
    assert set(outcomes) == {("AAA", 5), ("AAA", 10), ("BBB", 5), ("BBB", 10), ("CCC", 5), ("DDD", 5), ("DDD", 10)}
    won = json.loads(outcomes[("AAA", 5)]["payload"])
    assert outcomes[("AAA", 5)]["step"] == "target" and outcomes[("AAA", 5)]["as_of"].date() == date(2026, 9, 4)
    assert won["gross_r"] == 3.0 and won["cost_r"] == pytest.approx(2 * 10 / 1e4 * 50.0 / 2.5)
    assert won["net_r"] == pytest.approx(3.0 - won["cost_r"]) and "default" in won["cost_note"]
    assert outcomes[("CCC", 5)]["step"] == "fill" and outcomes[("CCC", 5)]["reason"] == "open_through_stop"
    short = json.loads(outcomes[("DDD", 5)]["payload"])
    assert short["net_r"] is None and short["gross_r"] == 3.0 and "gross only" in short["cost_note"]


def test_backfill_skips_signals_with_a_live_receipt() -> None:
    settings = Settings.model_validate({"strategies": {"s1": {"enabled": True}}})
    with Store() as store:
        store.write_table(SHADOW_TABLE, _shadow_rows().head(2), ["strategy", "symbol", "as_of"], schema=table_schema())
        live = receipts.make_event(receipts.REFUSAL, "reward_risk", "reward_risk 1.00 below min 2.0", date(2026, 9, 2),
                                   "s1", "BBB", **receipts.stamp(settings))
        receipts.write_events(store, [live])
        receipts.backfill(store, settings)
        bbb = receipts.read_events(store, symbol="BBB", kind="refusal")
        assert bbb["step"].tolist() == ["reward_risk"] and bbb["source"].tolist() == ["live"]


def test_cli_backfill_and_show(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from swing_engine import cli

    settings = make_settings(tmp_path)
    with Store(settings.data.store_path) as store:
        store.write_table(SHADOW_TABLE, _shadow_rows(), ["strategy", "symbol", "as_of"], schema=table_schema())
    ledger = OrderLedger(settings.execution.ledger_file)
    ledger.reserve(_intent("AAA", date(2026, 9, 2)), "autopilot:paper")
    ledger.close()
    runner, base = CliRunner(env={"COLUMNS": "250"}), ["--settings", str(tmp_path / "settings.yaml"), "receipts"]
    first = runner.invoke(cli.app, [*base, "backfill"])
    assert first.exit_code == 0, first.output
    with Store(settings.data.store_path, read_only=True) as store:
        n = len(receipts.read_events(store))
    assert n > 0 and runner.invoke(cli.app, [*base, "backfill"]).exit_code == 0
    with Store(settings.data.store_path, read_only=True) as store:
        assert len(receipts.read_events(store)) == n
    shown = runner.invoke(cli.app, [*base, "show", "--as-of", "2026-09-01", "--symbol", "bbb", "--kind", "refusal",
                                    "--payload"])
    assert shown.exit_code == 0 and "unknown" in shown.output and "not taken" in shown.output, shown.output
    none = runner.invoke(cli.app, [*base, "show", "--as-of", "2020-01-01"])
    assert none.exit_code == 0 and "no events" in none.output


# ----------------------------------------------------------------------------------------------- dashboard
def test_events_api_demo_and_validation() -> None:
    app = DashboardApp(DemoData(), secrets=[])
    body = app.handle("GET", "/api/events", H).json()
    assert body["ok"] and {e["kind"] for e in body["data"]["events"]} == {"fire", "refusal", "exit", "outcome"}
    assert all(set(receipts.EVENTS_SCHEMA) <= set(e) and isinstance(e["payload"], dict) for e in body["data"]["events"])
    only = app.handle("GET", "/api/events?as_of=2026-10-06&kind=refusal&strategy=sr_bounce&symbol=KITE&limit=5", H).json()
    assert [e["step"] for e in only["data"]["events"]] == ["reward_risk"]
    for bad in ("/api/events?as_of=yesterday", "/api/events?kind=bogus", "/api/events?strategy=a;b",
                "/api/events?symbol=..%2F", "/api/events?limit=0", "/api/events?limit=99999"):
        assert app.handle("GET", bad, H).status == 400, bad
    assert app.handle("POST", "/api/events", H).status == 405


def test_events_api_reads_the_live_store(tmp_path: Path) -> None:
    data = live_data(tmp_path)
    app = DashboardApp(data, secrets=[])
    empty = app.handle("GET", "/api/events", H).json()
    assert empty["ok"] is False and "receipts" in empty["unavailable"]
    st = receipts.stamp(data.settings)
    with Store(data.store_path) as store:
        receipts.write_events(store, [
            receipts.make_event(receipts.FIRE, "broker", "submitted", AS_OF, "pullback_trend", "AAA", {"qty": 5}, **st),
            receipts.make_event(receipts.REFUSAL, "daily_cap", "max_new_orders_per_day=1 reached", AS_OF, "sr_bounce",
                                "BBB", **st),
        ])
    body = app.handle("GET", f"/api/events?as_of={AS_OF.isoformat()}&kind=fire", H).json()
    (event,) = body["data"]["events"]
    assert event["symbol"] == "AAA" and event["payload"] == {"qty": 5} and event["as_of"] == AS_OF.isoformat()
    assert event["engine_sig"] == st["engine_sig"] and body["data"]["count"] == 1
    assert app.handle("GET", "/api/events?as_of=2020-01-01", H).json()["data"]["events"] == []
