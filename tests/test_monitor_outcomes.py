"""Alert outcome tracking over a synthetic event log + bars (tests/fixtures/outcomes)."""
from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from swing_engine.core.config import DataConfig, Settings
from swing_engine.core.models import Event
from swing_engine.data.store import Store
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.outcomes import (
    ALL_RULES,
    INTRADAY_BARS_TABLE,
    OUTCOME_COLUMNS,
    OUTCOMES_TABLE,
    REF_DAILY_CLOSE,
    REF_DAILY_OPEN,
    REF_INTRADAY,
    REF_NONE,
    RETURN_COLUMNS,
    compute_outcomes,
    summarize_outcomes,
)

FIXTURES = Path(__file__).parent / "fixtures" / "outcomes"
NOW = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)  # one-day window covers every 2026-10-06 alert, not ev-old
SESSION = date(2026, 10, 6)
NEXT_SESSION = date(2026, 10, 7)
FAR_FUTURE = datetime(2030, 1, 1, tzinfo=UTC)  # the window is "since now - days", so only a later `now` empties it
ALL_HISTORY_DAYS = 10_000
# fixture arithmetic: ACME daily close = 100 + session index (2026-09-28 is index 0, 2026-10-06 is index 6);
# ACME 1-min opens on 2026-10-06 = 100 + 0.01 * minutes since 09:30 ET
ACME_CLOSE_1006 = 106.0
ACME_OPEN_1007 = 106.5
ACME_CLOSE_1007 = 107.0
ACME_CLOSE_5D_AFTER_1006 = 111.0
ACME_CLOSE_20D_AFTER_1006 = 126.0
ACME_CLOSE_20D_AFTER_1007 = 127.0
ACME_OPEN_0930 = 100.0
ACME_OPEN_0935 = 100.05
ACME_OPEN_1000 = 100.30
ACME_OPEN_1005 = 100.35
ACME_OPEN_1030 = 100.60
TINY_OPEN_1006 = 5.8
TINY_CLOSE_1006 = 5.6
TINY_CLOSE_1007 = 5.7
PUMP_CLOSE_1006 = 2.7
PUMP_CLOSE_1007 = 2.65
ALERT_ROWS = 7  # 5 single-symbol alerts + ev-multi (ACME, TINY)


def pct(price: float, ref: float) -> float:
    return (price / ref - 1.0) * 100.0


def load_events() -> list[Event]:
    lines = (FIXTURES / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [Event.model_validate(json.loads(line)) for line in lines if line.strip()]


def fill_store(store: Store, intraday: bool = True) -> Store:
    store.write_bars(pd.read_csv(FIXTURES / "daily_bars.csv"))
    if intraday:
        frame = pd.read_csv(FIXTURES / "intraday_bars.csv")
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.tz_convert("America/New_York")
        store.write_table(INTRADAY_BARS_TABLE, frame, ["symbol", "ts"])
    return store


@pytest.fixture
def eventlog() -> EventLog:
    log = EventLog(":memory:")
    for event in load_events():
        assert log.append(event)
    yield log
    log.close()


@pytest.fixture
def store() -> Store:
    with Store(":memory:") as s:
        yield fill_store(s)


@pytest.fixture
def outcomes(eventlog: EventLog, store: Store) -> pd.DataFrame:
    return compute_outcomes(Settings(), 1, eventlog=eventlog, store=store, now=NOW)


def row(df: pd.DataFrame, event_id: str, symbol: str) -> pd.Series:
    hit = df[(df["event_id"] == event_id) & (df["symbol"] == symbol)]
    assert len(hit) == 1, (event_id, symbol)
    return hit.iloc[0]


def test_alert_set_is_priority_p1_plus_inside_the_window(outcomes: pd.DataFrame) -> None:
    assert list(outcomes.columns) == list(OUTCOME_COLUMNS)
    assert len(outcomes) == ALERT_ROWS
    ids = set(outcomes["event_id"])
    assert "ev-dropped" not in ids  # P0 and never delivered
    assert "ev-old" not in ids  # outside the 1-day window
    assert sorted(outcomes.loc[outcomes["event_id"] == "ev-multi", "symbol"]) == ["ACME", "TINY"]


def test_intraday_reference_and_every_horizon(outcomes: pd.DataFrame) -> None:
    r = row(outcomes, "ev-acme-news", "ACME")  # 10:00 ET
    assert r["ref_source"] == REF_INTRADAY and r["session"] == SESSION
    assert r["ref_price"] == pytest.approx(ACME_OPEN_1000)
    assert r["ref_ts"] == pd.Timestamp("2026-10-06 14:00", tz="UTC")
    assert r["ret_5m_pct"] == pytest.approx(pct(ACME_OPEN_1005, ACME_OPEN_1000))
    assert r["ret_30m_pct"] == pytest.approx(pct(ACME_OPEN_1030, ACME_OPEN_1000))
    assert r["ret_close_pct"] == pytest.approx(pct(ACME_CLOSE_1006, ACME_OPEN_1000))
    assert r["ret_1d_pct"] == pytest.approx(pct(ACME_CLOSE_1007, ACME_OPEN_1000))
    assert r["ret_5d_pct"] == pytest.approx(pct(ACME_CLOSE_5D_AFTER_1006, ACME_OPEN_1000))
    assert r["ret_20d_pct"] == pytest.approx(pct(ACME_CLOSE_20D_AFTER_1006, ACME_OPEN_1000))


def test_pre_open_alert_takes_first_print_at_or_after(outcomes: pd.DataFrame) -> None:
    acme = row(outcomes, "ev-multi", "ACME")  # 09:00 ET, intraday bars start 09:30
    assert acme["ref_source"] == REF_INTRADAY and acme["ref_price"] == pytest.approx(ACME_OPEN_0930)
    assert acme["ret_5m_pct"] == pytest.approx(pct(ACME_OPEN_0935, ACME_OPEN_0930))  # 09:05 target -> 09:35 bar
    tiny = row(outcomes, "ev-multi", "TINY")  # no intraday bars: session open
    assert tiny["ref_source"] == REF_DAILY_OPEN and tiny["ref_price"] == pytest.approx(TINY_OPEN_1006)
    assert tiny["ref_ts"] == pd.Timestamp("2026-10-06 09:30", tz="America/New_York")
    assert math.isnan(tiny["ret_5m_pct"]) and math.isnan(tiny["ret_30m_pct"])
    assert tiny["ret_close_pct"] == pytest.approx(pct(TINY_CLOSE_1006, TINY_OPEN_1006))
    assert tiny["ret_1d_pct"] == pytest.approx(pct(TINY_CLOSE_1007, TINY_OPEN_1006))


def test_regular_hours_alert_without_intraday_uses_session_close(outcomes: pd.DataFrame) -> None:
    r = row(outcomes, "ev-pump-bag", "PUMP")  # 11:00 ET
    assert r["ref_source"] == REF_DAILY_CLOSE and r["ref_price"] == pytest.approx(PUMP_CLOSE_1006)
    assert r["ref_ts"] == pd.Timestamp("2026-10-06 16:00", tz="America/New_York")
    assert r["ret_close_pct"] == pytest.approx(0.0)
    assert r["ret_1d_pct"] == pytest.approx(pct(PUMP_CLOSE_1007, PUMP_CLOSE_1006))
    assert math.isnan(r["ret_5m_pct"])


def test_after_close_alert_uses_next_session_open(outcomes: pd.DataFrame) -> None:
    r = row(outcomes, "ev-acme-afterhours", "ACME")  # 17:00 ET
    assert r["ref_source"] == REF_DAILY_OPEN and r["session"] == NEXT_SESSION
    assert r["ref_price"] == pytest.approx(ACME_OPEN_1007)
    assert r["ret_close_pct"] == pytest.approx(pct(ACME_CLOSE_1007, ACME_OPEN_1007))
    assert r["ret_20d_pct"] == pytest.approx(pct(ACME_CLOSE_20D_AFTER_1007, ACME_OPEN_1007))
    assert math.isnan(r["ret_5m_pct"]) and math.isnan(r["ret_30m_pct"])


def test_symbol_without_bars_is_nan_everywhere(outcomes: pd.DataFrame) -> None:
    r = row(outcomes, "ev-unknown-symbol", "ZZZZ")
    assert r["ref_source"] == REF_NONE and math.isnan(r["ref_price"]) and r["session"] is None
    assert pd.isna(r["ref_ts"])
    assert all(math.isnan(r[c]) for c in RETURN_COLUMNS)


def test_rows_carry_rules_classifier_smallcap_and_rating_tags(outcomes: pd.DataFrame) -> None:
    news = row(outcomes, "ev-acme-news", "ACME")
    assert news["rule_hits"] == "news:watchlist|haiku:upgrade" and news["primary_rule"] == "news:watchlist"
    assert news["priority"] == "P2" and news["source"] == "alpaca_news" and news["kind"] == "news"
    assert (news["cls_relevance"], news["cls_event_type"], news["cls_sentiment"], news["cls_action"]) == (
        "high", "earnings", "positive", "watch",
    )
    assert news["cls_materiality"] == 4.0 and news["rating"] == "useful"
    assert news["sc_grade"] is None and math.isnan(news["sc_bagholder_score"])
    runner = row(outcomes, "ev-tiny-runner", "TINY")
    assert (runner["sc_classifier"], runner["sc_grade"]) == ("runner", "A")
    assert runner["sc_structural_score"] == 1.0 and runner["sc_bagholder_score"] == 2.0
    assert runner["rating"] == "noise" and runner["cls_relevance"] is None
    bag = row(outcomes, "ev-pump-bag", "PUMP")
    assert bag["sc_bagholder_score"] == 7.0 and bag["rating"] == "useful"  # `useful: true` shorthand
    assert row(outcomes, "ev-multi", "ACME")["rating"] is None
    assert not outcomes["delivered"].any() and (outcomes["channels"] == "").all()


def test_outcomes_are_upserted_into_the_store(eventlog: EventLog, store: Store, outcomes: pd.DataFrame) -> None:
    assert store.count(OUTCOMES_TABLE) == ALERT_ROWS
    again = compute_outcomes(Settings(), 1, eventlog=eventlog, store=store, now=NOW)
    assert len(again) == ALERT_ROWS and store.count(OUTCOMES_TABLE) == ALERT_ROWS
    saved = store.read_table(OUTCOMES_TABLE)
    assert set(saved.columns) == set(OUTCOME_COLUMNS)
    kept = saved.set_index(["event_id", "symbol"]).loc[("ev-acme-news", "ACME")]
    assert kept["ret_close_pct"] == pytest.approx(pct(ACME_CLOSE_1006, ACME_OPEN_1000))
    assert kept["rating"] == "useful" and kept["rule_hits"] == "news:watchlist|haiku:upgrade"


def test_empty_window_and_persist_false(eventlog: EventLog, store: Store) -> None:
    empty = compute_outcomes(Settings(), 1, eventlog=eventlog, store=store, now=FAR_FUTURE)
    assert empty.empty and list(empty.columns) == list(OUTCOME_COLUMNS)
    assert not store.has_table(OUTCOMES_TABLE)
    frame = compute_outcomes(Settings(), 1, eventlog=eventlog, store=store, now=NOW, persist=False)
    assert len(frame) == ALERT_ROWS and not store.has_table(OUTCOMES_TABLE)
    summary = summarize_outcomes(empty)
    assert summary.empty and "precision_proxy" in summary.columns


def test_daily_only_store_still_prices_every_horizon_it_can(eventlog: EventLog) -> None:
    with Store(":memory:") as daily_only:
        fill_store(daily_only, intraday=False)
        frame = compute_outcomes(Settings(), 1, eventlog=eventlog, store=daily_only, now=NOW, persist=False)
    r = row(frame, "ev-acme-news", "ACME")  # 10:00 ET, regular hours -> close of the session
    assert r["ref_source"] == REF_DAILY_CLOSE and r["ref_price"] == pytest.approx(ACME_CLOSE_1006)
    assert math.isnan(r["ret_5m_pct"]) and r["ret_close_pct"] == pytest.approx(0.0)
    assert r["ret_1d_pct"] == pytest.approx(pct(ACME_CLOSE_1007, ACME_CLOSE_1006))


def test_alert_audit_rows_join_delivery_and_include_delivered_p0(eventlog: EventLog, store: Store) -> None:
    eventlog.record_alert("ev-acme-news", "P2", ["telegram", "console"], True, "ok")
    eventlog.record_alert("ev-dropped", "P0", [], False, "cooldown")
    frame = compute_outcomes(
        Settings(), ALL_HISTORY_DAYS, eventlog=eventlog, store=store, now=datetime.now(UTC), persist=False
    )
    news = row(frame, "ev-acme-news", "ACME")
    assert news["delivered"] and news["channels"] == "telegram|console"
    dropped = row(frame, "ev-dropped", "ACME")  # audited => tracked even though the policy dropped it
    assert not dropped["delivered"] and dropped["priority"] == "P0"
    assert "ev-old" in set(frame["event_id"])


def test_summarize_outcomes_per_rule(outcomes: pd.DataFrame) -> None:
    summary = summarize_outcomes(outcomes).set_index("rule")
    assert summary.index[0] == ALL_RULES
    assert summary.loc[ALL_RULES, "n"] == ALERT_ROWS
    assert summary.loc[ALL_RULES, "rated"] == 3 and summary.loc[ALL_RULES, "useful"] == 2
    assert summary.loc[ALL_RULES, "precision_proxy"] == pytest.approx(2 / 3)
    assert set(summary.index) == {
        ALL_RULES, "news:watchlist", "haiku:upgrade", "smallcap:runner", "smallcap:bagholder", "filing:8-K:major",
        "news:keyword", "halt:T1",
    }
    runner = summary.loc["smallcap:runner"]
    assert runner["n"] == 1 and runner["precision_proxy"] == 0.0
    assert runner["hit_close"] == 0.0  # TINY closes below its open every day
    assert runner["mean_close"] == pytest.approx(pct(TINY_CLOSE_1006, TINY_OPEN_1006))
    assert math.isnan(runner["hit_5m"])  # no intraday bars for TINY
    halt = summary.loc["halt:T1"]  # ACME (intraday) + TINY (daily only)
    assert halt["n"] == 2 and halt["hit_5m"] == 1.0 and math.isnan(halt["precision_proxy"])
    assert halt["median_5m"] == pytest.approx(pct(ACME_OPEN_0935, ACME_OPEN_0930))
    news = summary.loc["news:watchlist"]
    assert news["hit_close"] == 1.0 and news["hit_20d"] == 1.0 and news["precision_proxy"] == 1.0
    assert math.isnan(summary.loc["news:keyword", "hit_close"])  # ZZZZ has no bars


def test_compute_outcomes_opens_store_and_event_log_from_settings(tmp_path: Path) -> None:
    log_path = tmp_path / "events.sqlite"
    store_path = tmp_path / "swing.duckdb"
    log = EventLog(log_path)
    for event in load_events():
        log.append(event)
    log.close()
    with Store(store_path) as s:
        fill_store(s)
    settings = Settings(data=DataConfig(store_path=str(store_path), event_log_path=str(log_path)))
    frame = compute_outcomes(settings, 1, now=NOW)
    assert len(frame) == ALERT_ROWS
    with Store(store_path, read_only=True) as s:
        assert s.count(OUTCOMES_TABLE) == ALERT_ROWS
