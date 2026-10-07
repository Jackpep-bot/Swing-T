"""execution.position_manager: exits for open positions on paper_sim and an Alpaca-shaped fake (no network)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from swing_engine.core.config import Settings
from swing_engine.core.models import OrderIntent, Position, Side
from swing_engine.execution.ledger import OrderLedger, OrderStatus
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.execution.position_manager import (
    ExitAction,
    ExitKind,
    ExitReason,
    flatten_orders,
    review_positions,
    sessions_between,
    strategy_from_client_order_id,
    trading_sessions_until,
)
from swing_engine.strategies.rsi2_meanrev import RSI2MeanRev

NY = ZoneInfo("America/New_York")
AS_OF = date(2026, 9, 30)  # Wednesday; no NYSE holiday in the preceding three weeks
SESSIONS = [d.date() for d in pd.bdate_range(date(2026, 9, 10), AS_OF)]
ENTRY = 100.0
STOP = 95.0  # 1R = 5.00


class HoldOnly:
    """A strategy stand-in with only a time stop (`max_hold_days`)."""

    name = "hold_only"

    def __init__(self, hold: int = 3) -> None:
        self.params = {"max_hold_days": hold}

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return False


class RuleOnly(HoldOnly):
    name = "rule_only"

    def __init__(self) -> None:
        self.params = {}
        self.seen: list[int] = []

    def exit_rule(self, row: pd.Series, position: Any) -> bool:
        self.seen.append(position.bars_held)
        return float(row["close"]) < float(row["sma_10"])


def make_settings(tmp_path: Path, **execution: Any) -> Settings:
    return Settings.model_validate(
        {
            "data": {"store_path": str(tmp_path / "data" / "swing.duckdb")},
            "risk": {"kill_switch_file": str(tmp_path / "state" / "KILL")},
            "execution": {"ledger_file": str(tmp_path / "state" / "orders.sqlite"), **execution},
        }
    )


def panel_for(symbol: str, closes: list[float], lows: list[float] | None = None, **cols: list[float]) -> pd.DataFrame:
    days = SESSIONS[-len(closes):]
    lows = lows or [c - 1 for c in closes]
    frame = pd.DataFrame(
        {
            "symbol": symbol,
            "ts": [pd.Timestamp(d) for d in days],
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": lows,
            "close": closes,
            "volume": 1_000_000.0,
        }
    )
    for name, values in cols.items():
        frame[name] = values
    return frame


def intent(symbol: str = "ACME", strategy: str = "hold_only", day: date = SESSIONS[-6], **kw: Any) -> OrderIntent:
    base = {
        "symbol": symbol, "side": Side.LONG, "qty": 100, "entry_limit": 101.0, "stop": STOP, "target": 120.0,
        "strategy": strategy, "client_order_id": f"swing-{strategy}-{symbol}-{day:%Y%m%d}-long", "risk_dollars": 500.0,
    }
    base.update(kw)
    return OrderIntent(**base)


def sim_with_position(entry_day: date, strategy: str = "hold_only", stop: float = STOP) -> PaperSimBroker:
    broker = PaperSimBroker(slippage_bps=0.0)
    broker.submit(intent(strategy=strategy, day=entry_day, stop=stop))
    broker.fill_open({"ACME": ENTRY}, ts=datetime.combine(entry_day, time(9, 30), tzinfo=NY))
    return broker


def kinds(actions: list[ExitAction]) -> list[tuple[str, str]]:
    return [(a.kind.value, a.reason.value) for a in actions]


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def test_strategy_from_client_order_id() -> None:
    assert strategy_from_client_order_id("swing-sr_bounce-AAPL-20261006-long") == "sr_bounce"
    assert strategy_from_client_order_id("swing-sr_bounce-BRK-B-20261006-long", ["sr", "sr_bounce"]) == "sr_bounce"
    assert strategy_from_client_order_id("manual-AAPL") is None and strategy_from_client_order_id(None) is None


def test_flatten_orders_tags_nested_legs() -> None:
    flat = flatten_orders([{"id": "p", "symbol": "AAPL", "client_order_id": "swing-x-AAPL", "legs": [{"id": "l1"}]}])
    assert [o["id"] for o in flat] == ["p", "l1"]
    assert flat[1]["symbol"] == "AAPL" and flat[1]["_parent_client_order_id"] == "swing-x-AAPL"


def test_session_counting_uses_closes_and_trading_days() -> None:
    submitted = datetime(2026, 9, 29, 10, 30, tzinfo=UTC)  # 06:30 ET Tuesday, before that day's close
    assert sessions_between(submitted, datetime(2026, 9, 29, 15, 0, tzinfo=UTC)) == 0  # same morning
    assert sessions_between(submitted, datetime(2026, 9, 30, 10, 30, tzinfo=UTC)) == 1  # next morning
    assert trading_sessions_until(AS_OF, AS_OF) == 0
    assert trading_sessions_until(AS_OF, date(2026, 10, 1)) == 1
    assert trading_sessions_until(AS_OF, date(2026, 10, 5)) == 3  # Thu, Fri, Mon


# ----------------------------------------------------------------------------------------------------------
# trailing rules
# ----------------------------------------------------------------------------------------------------------
def test_breakeven_after_one_r(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-2], strategy="hold_only")
    panel = panel_for("ACME", [101.0, 106.0])  # +1.2R
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": HoldOnly(hold=10)})
    assert kinds(actions) == [("replace_stop", "breakeven")]
    a = actions[0]
    assert a.new_stop == ENTRY and a.symbol == "ACME" and a.strategy == "hold_only" and a.qty == 100


def test_trail_after_two_r_uses_lowest_low_and_never_loosens(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-12], strategy="hold_only")
    closes = [100.0 + i for i in range(12)]  # last close 111 = +2.2R
    lows = [c - 1 for c in closes]
    panel = panel_for("ACME", closes, lows)
    strategies = {"hold_only": HoldOnly(hold=50)}
    settings = make_settings(tmp_path, trail_lookback_days=5)
    actions = review_positions(settings, broker, panel, AS_OF, strategies)
    assert kinds(actions) == [("replace_stop", "trail")]
    assert actions[0].new_stop == min(lows[-5:]) == 106.0

    broker.positions()[0].stop = 107.0  # already tighter than the trail candidate
    assert review_positions(settings, broker, panel, AS_OF, strategies) == []


def test_no_trailing_below_one_r_or_when_disabled(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-2])
    panel = panel_for("ACME", [101.0, 104.0])  # +0.8R
    assert review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": HoldOnly(10)}) == []
    panel = panel_for("ACME", [101.0, 112.0])  # +2.4R but both rules off
    settings = make_settings(tmp_path, breakeven_after_r=None, trail_after_r=None)
    assert review_positions(settings, broker, panel, AS_OF, {"hold_only": HoldOnly(10)}) == []


# ----------------------------------------------------------------------------------------------------------
# closes
# ----------------------------------------------------------------------------------------------------------
def test_time_stop_from_strategy_params(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-4])
    panel = panel_for("ACME", [100.0, 101.0, 100.5, 101.0, 102.0, 101.0])
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": HoldOnly(hold=3)})
    assert kinds(actions) == [("close", "time_stop")]
    assert actions[0].qty == 100 and actions[0].ref_price == 101.0 and "4 sessions" in actions[0].detail
    assert review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": HoldOnly(hold=5)}) == []


def test_rsi2_rule_exit_fires_on_close_above_exit_ma(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-2], strategy="rsi2_meanrev")
    panel = panel_for(
        "ACME", [99.0, 100.5], rsi_2=[5.0, 40.0], atr_14=[2.0, 2.0], sma_200=[90.0, 90.0], sma_10=[100.0, 100.2]
    )
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, ["rsi2_meanrev"])
    assert kinds(actions) == [("close", "strategy_exit")] and actions[0].strategy == "rsi2_meanrev"
    still = panel.assign(sma_10=[100.0, 101.0])  # close below the exit MA, rsi below 70, 2 of 5 days
    assert review_positions(make_settings(tmp_path), broker, still, AS_OF, {"rsi2_meanrev": RSI2MeanRev()}) == []


def test_exit_rule_hook_receives_bars_held(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-3], strategy="rule_only")
    rule = RuleOnly()
    panel = panel_for("ACME", [100.0, 101.0, 99.0], sma_10=[100.0, 100.0, 100.0])
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"rule_only": rule})
    assert kinds(actions) == [("close", "strategy_exit")] and rule.seen == [3]


def test_close_before_earnings(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-2])
    panel = panel_for("ACME", [101.0, 106.0])
    strategies = {"hold_only": HoldOnly(10)}
    soon = pd.DataFrame({"symbol": ["ACME", "OTHER"], "report_date": ["2026-10-01", "2026-10-01"]})
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, strategies, earnings=soon)
    assert kinds(actions) == [("close", "earnings")]  # the earnings close wins over the breakeven move
    later = pd.DataFrame({"symbol": ["ACME"], "report_date": ["2026-10-05"]})
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, strategies, earnings=later)
    assert kinds(actions) == [("replace_stop", "breakeven")]
    wider = make_settings(tmp_path, earnings_exit_days=3)
    assert kinds(review_positions(wider, broker, panel, AS_OF, strategies, earnings=later)) == [("close", "earnings")]


# ----------------------------------------------------------------------------------------------------------
# orphans, missing data, stale entries
# ----------------------------------------------------------------------------------------------------------
class AlpacaShaped:
    """Positions without strategy/stop (as Alpaca reports them) and nested open orders."""

    name = "alpaca_fake"

    def __init__(self, positions: list[Position], orders: list[dict[str, Any]]) -> None:
        self._positions = positions
        self._orders = orders

    def positions(self) -> list[Position]:
        return list(self._positions)

    def open_orders(self) -> list[dict[str, Any]]:
        return list(self._orders)


def test_orphan_is_flagged_not_closed_even_near_earnings(tmp_path: Path) -> None:
    broker = AlpacaShaped([Position(symbol="MANU", qty=10, avg_entry=50.0, side=Side.LONG)], [])
    panel = panel_for("MANU", [50.0, 70.0])
    earnings = pd.DataFrame({"symbol": ["MANU"], "report_date": ["2026-10-01"]})
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {}, earnings=earnings)
    assert kinds(actions) == [("flag", "orphan")] and "earnings" in actions[0].detail


def test_strategy_position_without_panel_rows_is_flagged(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-2])
    actions = review_positions(make_settings(tmp_path), broker, panel_for("OTHER", [1.0]), AS_OF, {"hold_only": HoldOnly()})
    assert kinds(actions) == [("flag", "no_data")]


def test_alpaca_shaped_legs_ledger_initial_stop_and_stop_leg_id(tmp_path: Path) -> None:
    cid = "swing-sr_bounce-AAPL-20260925-long"
    ledger = OrderLedger(":memory:")
    ledger.reserve(intent(symbol="AAPL", strategy="sr_bounce", client_order_id=cid, stop=STOP), "jane")
    ledger.update(cid, OrderStatus.FILLED, broker_order_id="parent",
                  broker_json={"filled_at": "2026-09-28T13:30:05Z"})
    orders = [
        {"id": "parent", "client_order_id": cid, "symbol": "AAPL", "status": "filled", "side": "buy",
         "filled_at": "2026-09-28T13:30:05Z", "legs": [
             {"id": "leg-tp", "client_order_id": "x1", "order_type": "limit", "side": "sell", "limit_price": "120"},
             {"id": "leg-stop", "client_order_id": "x2", "order_type": "stop", "side": "sell", "stop_price": "98.00"},
         ]},
    ]  # fmt: skip
    broker = AlpacaShaped([Position(symbol="AAPL", qty=100, avg_entry=ENTRY, side=Side.LONG)], orders)
    panel = panel_for("AAPL", [100.0, 104.0, 107.0])  # +1.4R against the ledger's 95 initial stop
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, ["sr_bounce"], ledger=ledger)
    assert kinds(actions) == [("replace_stop", "breakeven")]
    a = actions[0]
    assert a.order_id == "leg-stop" and a.new_stop == ENTRY and a.strategy == "sr_bounce" and a.client_order_id == cid


def test_strategy_recovered_from_ledger_when_broker_has_no_orders(tmp_path: Path) -> None:
    cid = "swing-hold_only-ACME-20260924-long"
    ledger = OrderLedger(":memory:")
    ledger.reserve(intent(client_order_id=cid), "autopilot:paper")
    ledger.update(cid, OrderStatus.FILLED, broker_json={"raw": {"filled_at": "2026-09-24T13:31:00Z"}})
    broker = AlpacaShaped([Position(symbol="ACME", qty=100, avg_entry=ENTRY, side=Side.LONG)], [])
    panel = panel_for("ACME", [100.0, 100.0, 100.0, 101.0, 100.0])  # Sep 24..30 = 5 sessions held
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": HoldOnly(5)}, ledger=ledger)
    assert kinds(actions) == [("close", "time_stop")] and actions[0].client_order_id == cid


def test_stale_unfilled_entry_is_cancelled_after_n_sessions(tmp_path: Path) -> None:
    broker = PaperSimBroker()
    broker.submit(intent(symbol="WAIT", day=AS_OF))
    broker.submit(intent(symbol="MAN", client_order_id="manual-1"))  # not ours: never touched
    for order in broker._orders.values():
        order["submitted_at"] = "2026-09-29T10:30:00+00:00"  # 06:30 ET Tuesday
    settings = make_settings(tmp_path)
    tuesday_noon = datetime(2026, 9, 29, 16, 0, tzinfo=UTC)
    assert review_positions(settings, broker, None, AS_OF, {}, now=tuesday_noon) == []
    actions = review_positions(settings, broker, None, AS_OF, {}, now=datetime(2026, 9, 30, 10, 30, tzinfo=UTC))
    assert kinds(actions) == [("cancel_order", "stale_entry")]
    assert actions[0].order_id == "sim-1" and actions[0].client_order_id.startswith("swing-hold_only-WAIT")
    two = make_settings(tmp_path, cancel_unfilled_entries_after_sessions=2)
    assert review_positions(two, broker, None, AS_OF, {}, now=datetime(2026, 9, 30, 10, 30, tzinfo=UTC)) == []


def test_default_now_for_a_past_as_of_is_end_of_that_day(tmp_path: Path) -> None:
    broker = PaperSimBroker()
    broker.submit(intent(symbol="WAIT", day=AS_OF))
    broker._orders["sim-1"]["submitted_at"] = (datetime(2026, 9, 28, 10, 0, tzinfo=UTC)).isoformat()
    actions = review_positions(make_settings(tmp_path), broker, None, AS_OF, {})
    assert kinds(actions) == [("cancel_order", "stale_entry")] and "3 session" in actions[0].detail


def test_actions_are_ordered_cancel_close_replace_flag(tmp_path: Path) -> None:
    broker = sim_with_position(SESSIONS[-2])
    broker.submit(intent(symbol="WAIT", day=AS_OF))
    broker._orders["sim-2"]["submitted_at"] = (datetime(2026, 9, 28, 10, 0, tzinfo=UTC)).isoformat()
    broker._positions["MANU"] = Position(symbol="MANU", qty=1, avg_entry=1.0, side=Side.LONG)
    panel = pd.concat([panel_for("ACME", [101.0, 106.0]), panel_for("MANU", [1.0])])
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": HoldOnly(10)})
    assert [a.kind for a in actions] == [ExitKind.CANCEL_ORDER, ExitKind.REPLACE_STOP, ExitKind.FLAG]
    assert {a.reason for a in actions} == {ExitReason.STALE_ENTRY, ExitReason.BREAKEVEN, ExitReason.ORPHAN}


@pytest.mark.parametrize("hold_key", ["max_hold_days", "time_stop_days"])
def test_both_hold_param_names_are_honoured(tmp_path: Path, hold_key: str) -> None:
    strat = HoldOnly()
    strat.params = {hold_key: 2}
    broker = sim_with_position(SESSIONS[-2])
    panel = panel_for("ACME", [100.0, 100.5])
    assert kinds(review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"hold_only": strat})) == [
        ("close", "time_stop")
    ]



# ----------------------------------------------------------------------------------------------------------
# regressions: unprotected positions, isolated failures, partial fills, ledger row by client_order_id
# ----------------------------------------------------------------------------------------------------------
def _filled_ledger(cid: str, symbol: str, stop: float, filled_at: str) -> OrderLedger:
    ledger = OrderLedger(":memory:")
    ledger.reserve(intent(symbol=symbol, strategy="hold_only", client_order_id=cid, stop=stop), "autopilot:paper")
    ledger.update(cid, OrderStatus.FILLED, broker_json={"raw": {"filled_at": filled_at}})
    return ledger


def test_position_without_an_open_stop_is_rearmed_closed_or_flagged(tmp_path: Path) -> None:
    """A held position whose stop leg is gone (expired GTC, failed close) must not stay unprotected."""
    cid = "swing-hold_only-ACME-20260928-long"
    ledger = _filled_ledger(cid, "ACME", STOP, "2026-09-28T13:31:00Z")
    broker = AlpacaShaped([Position(symbol="ACME", qty=100, avg_entry=ENTRY, side=Side.LONG)], [])
    strategies = {"hold_only": HoldOnly(10)}
    actions = review_positions(make_settings(tmp_path), broker, panel_for("ACME", [100.0, 101.0]), AS_OF,
                               strategies, ledger=ledger)
    assert kinds(actions) == [("place_stop", "no_stop")] and actions[0].new_stop == STOP and actions[0].qty == 100
    # +1.2R: the re-armed stop takes the R-ladder level (breakeven) rather than the old initial stop
    up = review_positions(make_settings(tmp_path), broker, panel_for("ACME", [101.0, 106.0]), AS_OF, strategies,
                          ledger=ledger)
    assert kinds(up) == [("place_stop", "no_stop")] and up[0].new_stop == ENTRY
    # already through the recorded stop: close instead of arming a stop above the market
    down = review_positions(make_settings(tmp_path), broker, panel_for("ACME", [97.0, 94.0]), AS_OF, strategies,
                            ledger=ledger)
    assert kinds(down) == [("close", "no_stop")] and down[0].ref_price == 94.0
    # no ledger row: nothing to re-arm from, so it is flagged for a human
    bare = review_positions(make_settings(tmp_path), AlpacaShaped(
        [Position(symbol="ACME", qty=100, avg_entry=ENTRY, side=Side.LONG, strategy="hold_only")], []),
        panel_for("ACME", [100.0, 101.0]), AS_OF, strategies, ledger=OrderLedger(":memory:"))
    assert kinds(bare) == [("flag", "no_stop")]


class Boom(HoldOnly):
    name = "boom"

    def __init__(self) -> None:
        self.params = {}

    def exit_rule(self, row: pd.Series, position: Any) -> bool:
        raise KeyError("missing_feature")


def test_one_failing_position_is_flagged_and_the_rest_are_still_reviewed(tmp_path: Path) -> None:
    broker = PaperSimBroker(slippage_bps=0.0)
    broker.submit(intent(symbol="BAD", strategy="boom", day=SESSIONS[-4]))
    broker.submit(intent(symbol="ACME", strategy="hold_only", day=SESSIONS[-4]))
    broker.fill_open({"BAD": ENTRY, "ACME": ENTRY}, ts=datetime.combine(SESSIONS[-4], time(9, 30), tzinfo=NY))
    closes = [100.0, 101.0, 100.5, 101.0, 102.0, 101.0]
    panel = pd.concat([panel_for("BAD", closes), panel_for("ACME", closes)])
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"boom": Boom(), "hold_only": HoldOnly(3)})
    assert sorted((a.symbol, a.kind.value, a.reason.value) for a in actions) == [
        ("ACME", "close", "time_stop"), ("BAD", "flag", "error"),
    ]  # fmt: skip
    assert "KeyError" in next(a for a in actions if a.symbol == "BAD").detail


def test_partially_filled_entry_remainder_is_cancelled_on_the_stale_clock(tmp_path: Path) -> None:
    cid = "swing-sr_bounce-AAPL-20260928-long"
    orders = [
        {"id": "parent", "client_order_id": cid, "symbol": "AAPL", "status": "partially_filled", "side": "buy",
         "qty": "500", "filled_qty": "200", "submitted_at": "2026-09-28T10:30:00Z", "legs": [
             {"id": "leg-stop", "order_type": "stop", "side": "sell", "stop_price": "95.00", "status": "held"},
         ]},
    ]  # fmt: skip
    broker = AlpacaShaped([Position(symbol="AAPL", qty=200, avg_entry=ENTRY, side=Side.LONG)], orders)
    panel = panel_for("AAPL", [100.0, 100.5])
    now = datetime(2026, 9, 30, 10, 30, tzinfo=UTC)
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, ["sr_bounce"], now=now)
    assert kinds(actions) == [("cancel_order", "stale_entry")]
    assert actions[0].order_id == "parent" and "partial fill" in actions[0].detail
    fresh = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)  # same session: not stale yet
    assert review_positions(make_settings(tmp_path), broker, panel, AS_OF, ["sr_bounce"], now=fresh) == []


def test_r_ladder_uses_the_live_trade_ledger_row_not_an_older_trade_in_the_symbol(tmp_path: Path) -> None:
    """An older closed AAPL trade stays 'filled' in the ledger forever; the live position's own client_order_id
    must pick the row (else a stale tighter initial stop shrinks 1R and moves the stop to breakeven early)."""
    old, new = "swing-sr_bounce-AAPL-20260901-long", "swing-sr_bounce-AAPL-20260928-long"
    ledger = OrderLedger(":memory:")
    ledger.reserve(intent(symbol="AAPL", strategy="sr_bounce", client_order_id=old, stop=173.0,
                          entry_limit=176.0, target=190.0), "autopilot:paper")
    ledger.update(old, OrderStatus.FILLED)
    ledger.reserve(intent(symbol="AAPL", strategy="sr_bounce", client_order_id=new, stop=170.0,
                          entry_limit=176.0, target=190.0), "autopilot:paper")  # still 'submitting': not reconciled
    orders = [
        {"id": "p2", "client_order_id": new, "symbol": "AAPL", "status": "filled", "side": "buy",
         "filled_at": "2026-09-29T13:30:05Z", "legs": [
             {"id": "leg-stop", "order_type": "stop", "side": "sell", "stop_price": "170.00", "status": "held"},
         ]},
    ]  # fmt: skip
    broker = AlpacaShaped([Position(symbol="AAPL", qty=100, avg_entry=175.0, side=Side.LONG)], orders)
    panel = panel_for("AAPL", [175.0, 178.0])  # +0.6R against the live 170 stop (would be 1.5R against 173)
    assert review_positions(make_settings(tmp_path), broker, panel, AS_OF, ["sr_bounce"], ledger=ledger) == []
