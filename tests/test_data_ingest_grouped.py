"""run_ingest grouped-daily mode (resumable whole-market backfill) and the symbols-mode reference fix."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import httpx
import pandas as pd
import pytest
import respx

from swing_engine.core.config import Secrets, Settings
from swing_engine.data import ingest
from swing_engine.data.ingest import (
    GROUPED_DAYS_TABLE,
    SYMBOLS_TABLE,
    estimate_backfill_seconds,
    grouped_days_present,
    resolve_mode,
    run_ingest,
)
from swing_engine.data.massive import MASSIVE_BASE_URL, MassiveProvider
from swing_engine.data.sample import SampleProvider
from swing_engine.data.store import Store
from tests.helpers_data import FakeClock, fixture_json
from tests.test_data_massive_grouped import reference_handler

TICKERS = f"{MASSIVE_BASE_URL}/v3/reference/tickers"
GROUPED = f"{MASSIVE_BASE_URL}/v2/aggs/grouped/locale/us/market/stocks"
GROUPED_RE = re.escape(GROUPED) + r"/(?P<day>\d{4}-\d{2}-\d{2})"
SPLITS = f"{MASSIVE_BASE_URL}/v3/reference/splits"
TEMPLATE = fixture_json("massive_grouped_2024-01-03.json")
TEMPLATE_TICKERS = len(TEMPLATE["results"])
JAN_SESSIONS = 9  # 2024-01-02 .. 2024-01-12 (no holiday in between)


class Day:
    def __init__(self, d: date) -> None:
        self.d = d

    def __call__(self) -> date:
        return self.d


def grouped_payload(day: str) -> dict[str, Any]:
    scale = int(day[-2:]) / 10.0  # distinct prices per session
    rows = [dict(r, c=round(r["c"] * scale, 4)) for r in TEMPLATE["results"]]
    return {**TEMPLATE, "results": rows, "request_id": f"req-{day}"}


class GroupedApi:
    """respx side effect for the grouped endpoint: records requested sessions, can refuse some."""

    def __init__(self, refuse: dict[str, int] | None = None, empty: set[str] | None = None) -> None:
        self.days: list[str] = []
        self.refuse = refuse or {}
        self.empty = empty or set()

    def __call__(self, request: httpx.Request, day: str) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.params.get("adjusted") == "true"
        self.days.append(day)
        if day in self.refuse:
            return httpx.Response(self.refuse[day], json=fixture_json("massive_grouped_not_authorized.json"))
        if day in self.empty:
            return httpx.Response(200, json=fixture_json("massive_grouped_empty.json"))
        return httpx.Response(200, json=grouped_payload(day))


@pytest.fixture
def today(monkeypatch: pytest.MonkeyPatch) -> Day:
    clock = Day(date(2024, 1, 31))
    monkeypatch.setattr(ingest, "_today", clock)
    return clock


def _settings(**universe: Any) -> Settings:
    return Settings.model_validate({"data": {"bar_provider": "massive", "history_years": 1}, "universe": universe})


def _provider(tmp_path, today: Day, clock: FakeClock | None = None) -> MassiveProvider:
    clock = clock or FakeClock()
    return MassiveProvider("test-key", cache_dir=tmp_path / "raw", clock=clock, sleep=clock.sleep, today=today)


def _run(prov: MassiveProvider, store: Store, start: date, end: date, **kw: Any) -> dict[str, Any]:
    kw.setdefault("reference", False)
    return run_ingest(_settings(), Secrets(_env_file=None), "massive", None, start, end, store, provider=prov, **kw)


def test_resolve_mode_and_estimate(tmp_path, today: Day) -> None:
    massive, sample, s = _provider(tmp_path, today), SampleProvider(), _settings()
    assert resolve_mode("auto", massive, None, s) == "grouped"
    assert resolve_mode("auto", massive, ["SPY"], s) == "symbols"
    assert resolve_mode("auto", massive, None, _settings(static_symbols=["SPY"])) == "symbols"
    assert resolve_mode("auto", sample, None, s) == "symbols"
    assert resolve_mode("symbols", massive, None, s) == "symbols"
    for bad in (("grouped", sample, None), ("grouped", massive, ["SPY"]), ("nightly", massive, None)):
        with pytest.raises(ValueError):
            resolve_mode(bad[0], bad[1], bad[2], s)
    assert estimate_backfill_seconds(504, 5) == pytest.approx(504 * 12.0)  # two free-tier years ~ 1h41m
    assert estimate_backfill_seconds(10, None) is None


@respx.mock
def test_symbols_mode_never_pages_the_reference_list(tmp_path, today: Day) -> None:
    listing = respx.get(TICKERS).mock(side_effect=AssertionError("full reference list must not be paged"))
    details = respx.get(url__regex=re.escape(TICKERS) + r"/(?P<sym>[A-Z]+)$").mock(
        side_effect=lambda request, sym: httpx.Response(
            200, json={"status": "OK", "results": {**fixture_json("massive_grouped_ticker_AAPL.json")["results"], "ticker": sym}}
        )
    )
    page = {k: v for k, v in fixture_json("massive_aggs_AAPL_p1.json").items() if k != "next_url"}
    aggs = respx.get(url__regex=r".*/v2/aggs/ticker/(?P<sym>[A-Z]+)/range/1/day/.*").mock(
        side_effect=lambda request, sym: httpx.Response(200, json={**page, "ticker": sym})
    )
    clock = FakeClock()
    prov = _provider(tmp_path, today, clock)
    with Store(":memory:") as store:
        res = run_ingest(
            _settings(), Secrets(_env_file=None), "massive", ["SPY", "aapl", "NVDA"], date(2024, 1, 2), date(2024, 1, 4),
            store, provider=prov,
        )
        assert res["mode"] == "symbols" and res["symbols_with_bars"] == 3 and res["bars_written"] == 6
        assert listing.call_count == 0 and details.call_count == 3 and aggs.call_count == 3
        assert sum(clock.sleeps) == pytest.approx(12.0)  # 6 calls at 5/min: one 12 s wait, not minutes
        assert set(store.read_table(SYMBOLS_TABLE)["symbol"]) == {"AAPL", "NVDA", "SPY"}
        # a re-run only refreshes bars: metadata for known names is not fetched again
        run_ingest(_settings(), Secrets(_env_file=None), "massive", ["SPY", "AAPL", "NVDA"], date(2024, 1, 2),
                   date(2024, 1, 4), store, provider=prov, full=True)
        assert details.call_count == 3 and listing.call_count == 0


@respx.mock
def test_grouped_backfill_is_resumable_and_ignores_sparse_symbol_days(tmp_path, today: Day) -> None:
    api = GroupedApi()
    respx.get(url__regex=GROUPED_RE).mock(side_effect=api)
    prov = _provider(tmp_path, today)
    with Store(":memory:") as store:
        # a few --symbols names already stored for these sessions must not make them look ingested
        store.write_bars(SampleProvider().daily_bars(["SPY", "ACME"], date(2024, 1, 2), date(2024, 1, 12)))
        assert grouped_days_present(store, date(2024, 1, 2), date(2024, 1, 12)) == set()

        class Interrupt(BaseException):
            pass

        def interrupt_on_jan8(request: httpx.Request, day: str) -> httpx.Response:
            if day == "2024-01-08":
                raise Interrupt
            return api(request, day)

        respx.routes.clear()
        respx.get(url__regex=GROUPED_RE).mock(side_effect=interrupt_on_jan8)
        with pytest.raises(Interrupt):
            _run(prov, store, date(2024, 1, 2), date(2024, 1, 12))
        assert api.days == ["2024-01-12", "2024-01-11", "2024-01-10", "2024-01-09"]  # newest first
        assert store.count(GROUPED_DAYS_TABLE) == 4  # progress survives the interruption

        respx.routes.clear()
        respx.get(url__regex=GROUPED_RE).mock(side_effect=api)
        res = _run(prov, store, date(2024, 1, 2), date(2024, 1, 12))
        assert api.days[4:] == ["2024-01-08", "2024-01-05", "2024-01-04", "2024-01-03", "2024-01-02"]
        assert res["mode"] == "grouped" and res["sessions"] == JAN_SESSIONS
        assert res["sessions_present"] == 4 and res["sessions_fetched"] == 5 and res["errors"] == []
        assert res["bars_written"] == 5 * TEMPLATE_TICKERS and res["symbols_with_bars"] == TEMPLATE_TICKERS
        assert store.count(GROUPED_DAYS_TABLE) == JAN_SESSIONS
        aapl = store.read_bars(["AAPL"], date(2024, 1, 2), date(2024, 1, 12))
        assert len(aapl) == JAN_SESSIONS and aapl["close"].iloc[0] == pytest.approx(184.25 * 0.2)

        # nightly: one call per missing session (Jan 15 is MLK day -> 16, 17 only)
        res = _run(prov, store, date(2024, 1, 2), date(2024, 1, 17))
        assert api.days[9:] == ["2024-01-17", "2024-01-16"] and res["sessions_fetched"] == 2
        assert res["sessions_present"] == JAN_SESSIONS

        # full=True refetches every session
        res = _run(prov, store, date(2024, 1, 2), date(2024, 1, 5), full=True)
        assert res["sessions_fetched"] == 4 and len(api.days) == 15


@respx.mock
def test_dense_stored_sessions_count_as_present(tmp_path, today: Day, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "GROUPED_PRESENT_MIN_SYMBOLS", TEMPLATE_TICKERS)
    api = GroupedApi()
    respx.get(url__regex=GROUPED_RE).mock(side_effect=api)
    with Store(":memory:") as store:
        store.write_bars(_bars_for("2024-01-03"))
        res = _run(_provider(tmp_path, today), store, date(2024, 1, 2), date(2024, 1, 4))
        assert "2024-01-03" not in api.days and res["sessions_present"] == 1 and res["sessions_fetched"] == 2


def _bars_for(day: str) -> pd.DataFrame:
    rows = grouped_payload(day)["results"]
    return pd.DataFrame(
        {"symbol": [r["T"] for r in rows], "ts": [pd.Timestamp(day)] * len(rows), "open": [r["o"] for r in rows],
         "high": [r["h"] for r in rows], "low": [r["l"] for r in rows], "close": [r["c"] for r in rows],
         "volume": [r["v"] for r in rows], "vwap": [r["vw"] for r in rows], "adj_close": [r["c"] for r in rows]}
    )


@respx.mock
def test_estimate_progress_and_rate_limit(tmp_path, today: Day) -> None:
    respx.get(url__regex=GROUPED_RE).mock(side_effect=GroupedApi())
    clock = FakeClock()
    messages: list[str] = []
    with Store(":memory:") as store:
        res = _run(_provider(tmp_path, today, clock), store, date(2023, 12, 1), date(2024, 1, 5), progress=messages.append)
    sessions = res["sessions"]
    assert sessions == 24 and res["sessions_fetched"] == sessions
    assert res["estimate_s"] == pytest.approx(sessions * 12.0)  # days x 12 s on the free tier
    assert messages[0].startswith(f"grouped ingest via massive: {sessions} of {sessions} sessions to fetch (~4m 48s")
    progress = [m for m in messages if "sessions (at" in m]
    assert [m.split(" ")[0] for m in progress] == ["10/24", "20/24"]
    # the shared token bucket paced the calls: 5 burst tokens, then 12 s per call
    assert sum(clock.sleeps) == pytest.approx((sessions - 5) * 12.0)


@respx.mock
def test_plan_history_limit_stops_the_walk_and_is_remembered(tmp_path, today: Day) -> None:
    api = GroupedApi(refuse={d: 403 for d in ("2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05")})
    respx.get(url__regex=GROUPED_RE).mock(side_effect=api)
    prov = _provider(tmp_path, today)
    with Store(":memory:") as store:
        res = _run(prov, store, date(2024, 1, 2), date(2024, 1, 12))
        assert api.days == ["2024-01-12", "2024-01-11", "2024-01-10", "2024-01-09", "2024-01-08", "2024-01-05"]
        assert res["plan_limit_at"] == "2024-01-05" and res["sessions_beyond_plan"] == 4
        assert res["errors"] == [] and res["sessions_fetched"] == 5
        # the next (nightly) run does not spend a call rediscovering the limit
        res = _run(prov, store, date(2024, 1, 2), date(2024, 1, 12))
        assert len(api.days) == 6 and res["sessions_beyond_plan"] == 4 and res["errors"] == []
        assert res["plan_limit_at"] == "2024-01-05"


@respx.mock
def test_unpublished_today_is_pending_and_empty_sessions_retry(tmp_path, today: Day) -> None:
    today.d = date(2024, 1, 12)
    api = GroupedApi(refuse={"2024-01-12": 403}, empty={"2024-01-11"})
    respx.get(url__regex=GROUPED_RE).mock(side_effect=api)
    prov = _provider(tmp_path, today)
    with Store(":memory:") as store:
        res = _run(prov, store, date(2024, 1, 9), date(2024, 1, 31))  # end beyond today is clamped
        assert api.days == ["2024-01-12", "2024-01-11", "2024-01-10", "2024-01-09"]
        assert res["sessions_pending"] == 1 and res["sessions_empty"] == 1 and res["sessions_fetched"] == 2
        assert res["errors"] == [] and res["plan_limit_at"] is None
        _run(prov, store, date(2024, 1, 9), date(2024, 1, 12))
        assert api.days[4:] == ["2024-01-12", "2024-01-11"]  # neither was recorded, both retried


@respx.mock
def test_consecutive_failures_abort_without_burning_quota(tmp_path, today: Day) -> None:
    api = GroupedApi(refuse={f"2024-01-{d:02d}": 401 for d in range(1, 32)})
    respx.get(url__regex=GROUPED_RE).mock(side_effect=api)
    with Store(":memory:") as store:
        res = _run(_provider(tmp_path, today), store, date(2024, 1, 2), date(2024, 1, 12))
    assert len(api.days) == ingest.GROUPED_MAX_CONSECUTIVE_ERRORS
    assert len(res["errors"]) == 3 and res["sessions_remaining"] == JAN_SESSIONS - 3 and res["bars_written"] == 0
    assert all("test-key" not in e["error"] for e in res["errors"])


@respx.mock
def test_split_repair_refetches_names_that_split_since_the_last_run(tmp_path, today: Day) -> None:
    respx.get(url__regex=GROUPED_RE).mock(side_effect=GroupedApi())
    splits = respx.get(SPLITS).mock(return_value=httpx.Response(200, json=fixture_json("massive_grouped_splits.json")))
    adjusted = {k: v for k, v in fixture_json("massive_aggs_AAPL_p1.json").items() if k != "next_url"}
    adjusted["results"] = [dict(r, c=1.0) for r in adjusted["results"]]
    refetch = respx.get(f"{MASSIVE_BASE_URL}/v2/aggs/ticker/AAPL/range/1/day/2024-01-02/2024-02-02").mock(
        return_value=httpx.Response(200, json=adjusted)
    )
    prov = _provider(tmp_path, today)
    with Store(":memory:") as store:
        first = _run(prov, store, date(2024, 1, 2), date(2024, 1, 12))
        assert first["splits_repaired"] == [] and splits.call_count == 0  # nothing stored before this run
        today.d = date(2024, 2, 7)
        res = _run(prov, store, date(2024, 1, 2), date(2024, 2, 2))
        assert splits.call_count == 1
        assert splits.calls[0].request.url.params.get("execution_date.gte") == "2024-01-31"
        # AAPL split 2024-02-05 after Jan bars were stored -> refetched (bypassing the raw cache);
        # MSFT's split predates the check window and NOTSTORED has no bars
        assert res["splits_repaired"] == ["AAPL"] and refetch.call_count == 1
        aapl = store.read_bars(["AAPL"], date(2024, 1, 2), date(2024, 1, 3))
        assert aapl["close"].tolist() == [1.0, 1.0]
        # same-day re-run: the check is already done
        _run(prov, store, date(2024, 1, 2), date(2024, 2, 2))
        assert splits.call_count == 1


@respx.mock
def test_grouped_run_refreshes_the_symbols_reference_table(tmp_path, today: Day) -> None:
    respx.get(url__regex=GROUPED_RE).mock(side_effect=GroupedApi())
    route = respx.get(TICKERS).mock(side_effect=reference_handler)
    prov = _provider(tmp_path, today)
    with Store(":memory:") as store:
        res = _run(prov, store, date(2024, 1, 2), date(2024, 1, 3), reference=True)
        assert res["reference_error"] is None and res["symbols_listed"] == 6
        symbols = store.read_table(SYMBOLS_TABLE).set_index("symbol")
        assert set(symbols.index) == {"AAPL", "MSFT", "OLDCO", "PENNY", "PNKX", "THIN"}
        assert str(symbols.loc["OLDCO", "delisted_at"])[:10] == "2024-02-20" and not bool(symbols.loc["OLDCO", "active"])
        calls = route.call_count
        _run(prov, store, date(2024, 1, 2), date(2024, 1, 4), reference=True)
        assert route.call_count == calls  # reference served from the 7-day disk cache
