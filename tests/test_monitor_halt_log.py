"""Tier-2 halt log: recording halt/resume events and the halted-runner statistic (tests/fixtures/outcomes)."""
from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing_engine.core.models import Event
from swing_engine.data.store import Store
from swing_engine.monitor.halt_log import (
    BUCKET_ALL,
    BUCKET_CAPPED,
    DIRECTION_DOWN,
    DIRECTION_INFERRED,
    DIRECTION_META,
    DIRECTION_UNKNOWN,
    DIRECTION_UP,
    HALT_DATASET_COLUMNS,
    HALT_LOG_TABLE,
    HALT_OUTCOMES_TABLE,
    HALT_STATS_COLUMNS,
    STATUS_HALTED,
    STATUS_RESUMED,
    halt_dataset,
    halt_statistics,
    record_halt,
)

FIXTURES = Path(__file__).parent / "fixtures" / "outcomes"
SESSION = date(2026, 10, 6)
LOGGED_HALTS = 4  # PUMP x2, TINY, ACME; MWC1 / luld band / orphan resume are ignored
# fixture arithmetic (daily_bars.csv): 2026-10-06 is session index 6, 2026-10-07 index 7
PUMP_PREV_CLOSE, PUMP_OPEN, PUMP_CLOSE, PUMP_NEXT_CLOSE = 2.75, 2.8, 2.7, 2.65
PUMP_HALT_1, PUMP_RESUME_1, PUMP_HALT_2 = 3.5, 3.3, 3.6
TINY_OPEN, TINY_CLOSE, TINY_RESUME = 5.8, 5.6, 5.9
ACME_HALT, ACME_OPEN_1007, ACME_CLOSE_1007 = 101.0, 106.5, 107.0
FIVE_HALTS = 5


def pct(price: float, ref: float) -> float:
    return (price / ref - 1.0) * 100.0


def halt_events() -> list[Event]:
    lines = (FIXTURES / "halt_events.jsonl").read_text(encoding="utf-8").splitlines()
    return [Event.model_validate(json.loads(line)) for line in lines if line.strip()]


def by_id(event_id: str) -> Event:
    return next(e for e in halt_events() if e.event_id == event_id)


@pytest.fixture
def store() -> Store:
    with Store(":memory:") as s:
        s.write_bars(pd.read_csv(FIXTURES / "daily_bars.csv"))
        yield s


@pytest.fixture
def logged(store: Store) -> Store:
    for event in halt_events():
        record_halt(event, store)
    return store


def halt_row(frame: pd.DataFrame, event_id: str) -> pd.Series:
    hit = frame[frame["halt_event_id"] == event_id]
    assert len(hit) == 1, event_id
    return hit.iloc[0]


def test_record_halt_ignores_non_halts_market_wide_and_orphan_resumes(store: Store) -> None:
    assert record_halt(by_id("h-luld-band"), store) == []
    assert record_halt(by_id("h-mwc"), store) == []
    assert record_halt(by_id("h-orphan-resume"), store) == []
    assert not store.has_table(HALT_LOG_TABLE)


def test_record_halt_opens_rows_and_fills_them_on_resume(logged: Store) -> None:
    rows = logged.read_table(HALT_LOG_TABLE)
    assert len(rows) == LOGGED_HALTS
    first = halt_row(rows, "h-pump-1")
    assert first["status"] == STATUS_RESUMED and first["resume_event_id"] == "h-pump-1r"
    assert first["code"] == "LUDP" and first["direction"] == DIRECTION_UP and first["source"] == "alpaca_stocks"
    assert first["halt_price"] == PUMP_HALT_1 and first["resume_price"] == PUMP_RESUME_1
    assert first["halt_ts"] == pd.Timestamp("2026-10-06 13:35", tz="UTC")
    assert first["resume_ts"] == pd.Timestamp("2026-10-06 13:40", tz="UTC")
    second = halt_row(rows, "h-pump-2")  # still halted; price from the RSS pause threshold string
    assert second["status"] == STATUS_HALTED and pd.isna(second["resume_ts"]) and math.isnan(second["resume_price"])
    assert second["halt_price"] == PUMP_HALT_2 and second["direction"] == DIRECTION_UNKNOWN
    assert second["market"] == "NASDAQ" and pd.isna(second["resume_event_id"])  # NULL VARCHAR reads back as NaN
    tiny = halt_row(rows, "h-tiny-t1")  # empty threshold => no halt price; resume price from `price`
    assert math.isnan(tiny["halt_price"]) and tiny["resume_price"] == TINY_RESUME
    assert tiny["status"] == STATUS_RESUMED and tiny["code"] == "T1"
    acme = halt_row(rows, "h-acme-down")
    assert acme["direction"] == DIRECTION_DOWN and acme["halt_price"] == ACME_HALT


def test_record_halt_returns_rows_and_is_idempotent(logged: Store) -> None:
    again = record_halt(by_id("h-pump-2"), logged)
    assert [(r["symbol"], r["status"], r["halt_price"]) for r in again] == [("PUMP", STATUS_HALTED, PUMP_HALT_2)]
    assert logged.count(HALT_LOG_TABLE) == LOGGED_HALTS
    resumed = record_halt(by_id("h-pump-1r"), logged)  # no open PUMP halt before 09:40 is left: nothing to fill
    assert resumed == [] or all(r["status"] == STATUS_RESUMED for r in resumed)
    assert logged.count(HALT_LOG_TABLE) == LOGGED_HALTS


def test_resume_matches_the_latest_open_halt_of_that_symbol(store: Store) -> None:
    record_halt(by_id("h-pump-1"), store)
    record_halt(by_id("h-pump-2"), store)
    late_resume = by_id("h-pump-1r").model_copy(update={"ts_source": datetime(2026, 10, 6, 14, 15, tzinfo=UTC)})
    rows = record_halt(late_resume, store)
    assert len(rows) == 1 and rows[0]["halt_event_id"] == "h-pump-2"
    table = store.read_table(HALT_LOG_TABLE)
    assert halt_row(table, "h-pump-2")["status"] == STATUS_RESUMED
    assert halt_row(table, "h-pump-1")["status"] == STATUS_HALTED


def test_halt_dataset_joins_session_prices_and_counts_halts(logged: Store) -> None:
    data = halt_dataset(logged)
    assert list(data.columns) == list(HALT_DATASET_COLUMNS) and len(data) == LOGGED_HALTS
    pump = data[data["symbol"] == "PUMP"].sort_values("halt_ts")
    assert pump["halts_that_day"].tolist() == [2, 2] and pump["halt_seq"].tolist() == [1, 2]
    assert (pump["session"] == SESSION).all()
    first, second = pump.iloc[0], pump.iloc[1]
    assert first["direction_source"] == DIRECTION_META
    assert second["direction"] == DIRECTION_UP and second["direction_source"] == DIRECTION_INFERRED  # 3.6 > 2.75
    assert (first["prev_close"], first["open"], first["close"], first["next_close"]) == (
        PUMP_PREV_CLOSE, PUMP_OPEN, PUMP_CLOSE, PUMP_NEXT_CLOSE,
    )
    assert first["resume_vs_halt_pct"] == pytest.approx(pct(PUMP_RESUME_1, PUMP_HALT_1))
    assert first["close_vs_halt_pct"] == pytest.approx(pct(PUMP_CLOSE, PUMP_HALT_1))
    assert first["close_vs_open_pct"] == pytest.approx(pct(PUMP_CLOSE, PUMP_OPEN))
    assert first["next_close_vs_close_pct"] == pytest.approx(pct(PUMP_NEXT_CLOSE, PUMP_CLOSE))
    assert bool(first["close_below_open"]) and bool(first["close_below_halt"]) and bool(first["next_close_below_close"])
    tiny = halt_row(data, "h-tiny-t1")
    assert tiny["halts_that_day"] == 1 and tiny["direction"] == DIRECTION_UNKNOWN  # no halt price to infer from
    assert bool(tiny["close_below_open"]) and pd.isna(tiny["close_below_halt"])
    assert math.isnan(tiny["close_vs_halt_pct"]) and math.isnan(tiny["resume_vs_halt_pct"])
    acme = halt_row(data, "h-acme-down")
    assert acme["session"] == date(2026, 10, 7) and (acme["open"], acme["close"]) == (ACME_OPEN_1007, ACME_CLOSE_1007)
    assert not acme["close_below_open"] and not acme["close_below_halt"]


def test_halt_statistics_by_halt_count(logged: Store) -> None:
    stats = halt_statistics(logged)
    assert list(stats.columns) == list(HALT_STATS_COLUMNS)
    assert stats["bucket"].tolist() == [BUCKET_ALL, "1", "2"]
    s = stats.set_index("bucket")
    assert s.loc[BUCKET_ALL, "n_halts"] == LOGGED_HALTS and s.loc[BUCKET_ALL, "n_symbol_days"] == 3
    assert s.loc[BUCKET_ALL, "n_up"] == 2 and s.loc[BUCKET_ALL, "n_down"] == 1
    assert s.loc[BUCKET_ALL, "share_close_below_open"] == pytest.approx(2 / 3)  # PUMP, TINY yes; ACME no
    assert s.loc[BUCKET_ALL, "share_close_below_halt"] == pytest.approx(2 / 3)  # TINY has no halt price
    assert s.loc["2", "n_halts"] == 2 and s.loc["2", "n_symbol_days"] == 1
    assert s.loc["2", "share_close_below_open"] == 1.0 and s.loc["2", "share_close_below_halt"] == 1.0
    assert s.loc["2", "share_next_close_below_close"] == 1.0
    assert s.loc["2", "median_close_vs_halt_pct"] == pytest.approx(
        (pct(PUMP_CLOSE, PUMP_HALT_1) + pct(PUMP_CLOSE, PUMP_HALT_2)) / 2
    )
    assert s.loc["1", "n_halts"] == 2 and s.loc["1", "share_close_below_open"] == 0.5
    assert s.loc["1", "share_close_below_halt"] == 0.0  # only ACME has a halt price in this bucket
    assert s.loc["1", "mean_close_vs_halt_pct"] == pytest.approx(pct(ACME_CLOSE_1007, ACME_HALT))
    assert logged.count(HALT_OUTCOMES_TABLE) == LOGGED_HALTS  # per-halt dataset persisted


def test_halt_statistics_persist_false_and_empty_store(logged: Store) -> None:
    with Store(":memory:") as fresh:
        assert halt_statistics(fresh).empty and list(halt_statistics(fresh).columns) == list(HALT_STATS_COLUMNS)
        assert halt_dataset(fresh).empty and list(halt_dataset(fresh).columns) == list(HALT_DATASET_COLUMNS)
    logged.delete(HALT_OUTCOMES_TABLE, "1=1")
    halt_statistics(logged, persist=False)
    assert logged.count(HALT_OUTCOMES_TABLE) == 0


def test_four_or_more_halts_share_one_bucket(store: Store) -> None:
    base = by_id("h-pump-1")
    for i in range(FIVE_HALTS):
        ts = datetime(2026, 10, 6, 14, i, tzinfo=UTC)
        record_halt(base.model_copy(update={"event_id": f"pump-{i}", "ts_source": ts}), store)
    stats = halt_statistics(store, persist=False).set_index("bucket")
    assert list(stats.index) == [BUCKET_ALL, BUCKET_CAPPED]
    assert stats.loc[BUCKET_CAPPED, "n_halts"] == FIVE_HALTS and stats.loc[BUCKET_CAPPED, "n_symbol_days"] == 1


def test_halt_dataset_without_bars_keeps_prices_unknown() -> None:
    with Store(":memory:") as bare:
        record_halt(by_id("h-pump-2"), bare)  # direction not in meta, no bars to infer from
        data = halt_dataset(bare)
        row = data.iloc[0]
        assert math.isnan(row["open"]) and math.isnan(row["close"]) and math.isnan(row["next_close"])
        assert row["direction"] == DIRECTION_UNKNOWN and pd.isna(row["close_below_open"])
        stats = halt_statistics(bare, persist=False).set_index("bucket")
        assert math.isnan(stats.loc[BUCKET_ALL, "share_close_below_open"])
        assert stats.loc[BUCKET_ALL, "n_halts"] == 1
