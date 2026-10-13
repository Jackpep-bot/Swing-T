"""DuckDB lock fallback: a writer holding the store -> the last good result with a `stale` note."""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import duckdb
import pytest

from swing_engine.dashboard.data import DuckReader, Unavailable
from swing_engine.dashboard.server import DashboardApp
from tests.test_dashboard_support import live_data

H = {"Host": "127.0.0.1:8765", "X-Swing-Dashboard": "1"}  # what the page's fetch() sends


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class FlakyConnect:
    """duckdb.connect that starts failing with DuckDB's lock error once `locked` is set."""

    def __init__(self) -> None:
        self.locked = False
        self.calls = 0

    def __call__(self, path: str, read_only: bool = False) -> Any:
        self.calls += 1
        assert read_only is True  # the dashboard never opens the store for writing
        if self.locked:
            raise duckdb.IOException(f'IO Error: Could not set lock on file "{path}": Conflicting lock is held')
        return duckdb.connect(path, read_only=True)


def _store(tmp_path: Path) -> Path:
    path = tmp_path / "s.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE t AS SELECT 42 AS x")
    con.close()
    return path


def test_cache_then_stale_then_unavailable(tmp_path: Path) -> None:
    clock, connect = Clock(), FlakyConnect()
    reader = DuckReader(_store(tmp_path), ttl=60, retries=2, retry_wait=0, connect=connect, clock=clock,
                        sleep=lambda s: None)
    q = lambda con: con.execute("SELECT x FROM t").fetchone()[0]  # noqa: E731
    assert reader.read("k", q) == (42, None)
    clock.t += 30
    assert reader.read("k", q) == (42, None) and connect.calls == 1  # within the TTL: no reopen
    connect.locked = True
    clock.t += 100
    value, stale = reader.read("k", q)
    assert value == 42 and stale is not None
    assert "locked by a writer" in stale["reason"] and stale["age_s"] == 130.0 and stale["cached_at"]
    assert connect.calls == 3  # two quick attempts, then the cache
    with pytest.raises(Unavailable, match="no cached copy yet"):
        reader.read("other", q)
    connect.locked = False
    assert reader.read("k", q) == (42, None)


def test_missing_store_is_unavailable(tmp_path: Path) -> None:
    reader = DuckReader(tmp_path / "nope.duckdb")
    with pytest.raises(Unavailable, match="no market store"):
        reader.read("k", lambda con: 1)
    assert not (tmp_path / "nope.duckdb").exists()


def test_query_error_is_unavailable(tmp_path: Path) -> None:
    reader = DuckReader(_store(tmp_path))
    with pytest.raises(Unavailable, match="store query failed"):
        reader.read("k", lambda con: con.execute("SELECT * FROM missing_table").fetchall())


def test_endpoints_serve_stale_copy_when_locked(tmp_path: Path) -> None:
    clock, connect = Clock(), FlakyConnect()
    data = live_data(tmp_path, duck_connect=connect, clock=clock, sleep=lambda s: None)
    app = DashboardApp(data, secrets=[])
    fresh = app.handle("GET", "/api/chart/AAA", H).json()
    assert fresh["ok"] and "stale" not in fresh
    assert app.handle("GET", "/api/shadow", H).json()["ok"]
    connect.locked = True
    clock.t += 3600
    stale = app.handle("GET", "/api/chart/AAA", H).json()
    assert stale["ok"] is True and stale["data"]["bars"] == fresh["data"]["bars"]
    assert "locked by a writer" in stale["stale"]["reason"]
    sh = app.handle("GET", "/api/shadow", H).json()
    assert sh["ok"] is True and sh["stale"]
    never = app.handle("GET", "/api/chart/BBB", H)
    assert never.status == 200 and never.json()["ok"] is False
    assert "locked" in never.json()["unavailable"]
    eq = app.handle("GET", "/api/equity", H).json()  # SPY never cached: account still shown, SPY reason given
    assert eq["ok"] is True and eq["data"]["spy"] == [] and "locked" in eq["data"]["unavailable"]["spy"]


def test_real_writer_process_holding_the_lock(tmp_path: Path) -> None:
    data = live_data(tmp_path, sleep=lambda s: None)
    app = DashboardApp(data, secrets=[])
    assert app.handle("GET", "/api/chart/AAA", H).json()["ok"]
    data.duck.ttl = 0  # force a reopen on the next read
    script = textwrap.dedent(f"""
        import duckdb, sys, time
        con = duckdb.connect({str(data.store_path)!r})
        con.execute("CREATE TABLE IF NOT EXISTS w (x INT)")
        print("ready", flush=True)
        sys.stdin.readline()
    """)
    proc = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "ready"
        body = app.handle("GET", "/api/chart/AAA", H).json()
        if "stale" not in body:  # platform without inter-process DuckDB locking: nothing to fall back from
            pytest.skip("DuckDB did not refuse the read-only open while a writer was attached")
        assert body["ok"] is True and body["data"]["bars"]
        other = app.handle("GET", "/api/chart/BBB", H).json()
        assert other["ok"] is False and "locked" in other["unavailable"]
    finally:
        assert proc.stdin is not None
        proc.stdin.write("\n")
        proc.stdin.flush()
        proc.wait(timeout=20)
