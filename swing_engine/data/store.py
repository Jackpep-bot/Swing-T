"""DuckDB store: one file, single writer. The `bars` table is keyed on (symbol, ts); any other frame can be
upserted into a generic table keyed on the columns you name. Everything round-trips to Parquet.

`ts` is stored as TIMESTAMPTZ and read back as tz-aware America/New_York timestamps, so the frames this
returns are exactly what `features.panel.build_panel` expects.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import structlog

from ._common import BAR_COLUMNS, BAR_KEYS, TZ, as_date, empty_bars, normalize_bars, session_ts

log = structlog.get_logger(__name__)

BARS_TABLE = "bars"
BARS_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR",
    "ts": "TIMESTAMPTZ",
    "open": "DOUBLE",
    "high": "DOUBLE",
    "low": "DOUBLE",
    "close": "DOUBLE",
    "volume": "DOUBLE",
    "vwap": "DOUBLE",
    "adj_close": "DOUBLE",
}
MEMORY_PATH = ":memory:"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    """Only plain identifiers are accepted for table/column names (they are interpolated into SQL)."""
    if not _IDENT.match(name):
        raise ValueError(f"invalid SQL identifier: {name!r}")
    return name


def _quote(name: str) -> str:
    return f'"{_ident(name)}"'


class Store:
    """DuckDB-backed store. Use as a context manager or call `close()`; one process writes at a time."""

    def __init__(self, path: str | Path = MEMORY_PATH, *, read_only: bool = False) -> None:
        self.path = str(path)
        if self.path != MEMORY_PATH:
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(self.path, read_only=read_only)
        self._con.execute(f"SET TimeZone = '{TZ}'")
        self.read_only = read_only
        self._view_seq = 0

    # ---------------------------------------------------------------- lifecycle
    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------- introspection
    def tables(self) -> list[str]:
        rows = self._con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows]

    def has_table(self, name: str) -> bool:
        return _ident(name) in self.tables()

    def columns(self, name: str) -> list[str]:
        rows = self._con.execute(f"DESCRIBE {_quote(name)}").fetchall()
        return [r[0] for r in rows]

    def count(self, name: str) -> int:
        if not self.has_table(name):
            return 0
        return int(self._con.execute(f"SELECT count(*) FROM {_quote(name)}").fetchone()[0])

    def sql(self, query: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
        """Escape hatch for ad-hoc analysis queries (returns a DataFrame)."""
        return self._con.execute(query, list(params or [])).df()

    # ---------------------------------------------------------------- generic tables
    def _register(self, df: pd.DataFrame) -> str:
        self._view_seq += 1
        name = f"_src_{self._view_seq}"
        self._con.register(name, df)
        return name

    def _create_table_like(self, name: str, view: str, keys: Sequence[str], schema: dict[str, str] | None) -> None:
        if schema is None:
            described = self._con.execute(f"DESCRIBE SELECT * FROM {view}").fetchall()
            schema = {row[0]: row[1] for row in described}
        cols = ", ".join(f"{_quote(c)} {t}" for c, t in schema.items())
        pk = ", ".join(_quote(k) for k in keys)
        self._con.execute(f"CREATE TABLE {_quote(name)} ({cols}, PRIMARY KEY ({pk}))")

    def _add_missing_columns(self, name: str, view: str, df_cols: Iterable[str]) -> None:
        existing = set(self.columns(name))
        described = {row[0]: row[1] for row in self._con.execute(f"DESCRIBE SELECT * FROM {view}").fetchall()}
        for c in df_cols:
            if c not in existing:
                self._con.execute(f"ALTER TABLE {_quote(name)} ADD COLUMN {_quote(c)} {described[c]}")
                log.info("store_column_added", table=name, column=c, type=described[c])

    def write_table(
        self,
        name: str,
        df: pd.DataFrame,
        keys: Sequence[str],
        *,
        schema: dict[str, str] | None = None,
    ) -> int:
        """Upsert `df` into `name` on `keys` (creating the table on first write). Returns rows written.
        Duplicate keys inside `df` keep the last row. New columns are added to an existing table."""
        _ident(name)
        keys = [_ident(k) for k in keys]
        if not keys:
            raise ValueError("write_table needs at least one key column")
        if df is None or len(df) == 0:
            return 0
        missing = [k for k in keys if k not in df.columns]
        if missing:
            raise ValueError(f"key columns missing from frame: {missing}")
        frame = df.drop_duplicates(subset=keys, keep="last").reset_index(drop=True)
        cols = [_ident(c) for c in frame.columns]
        view = self._register(frame)
        try:
            if not self.has_table(name):
                self._create_table_like(name, view, keys, schema)
            else:
                self._add_missing_columns(name, view, cols)
            col_list = ", ".join(_quote(c) for c in cols)
            updates = [f"{_quote(c)} = excluded.{_quote(c)}" for c in cols if c not in keys]
            conflict = f"DO UPDATE SET {', '.join(updates)}" if updates else "DO NOTHING"
            pk = ", ".join(_quote(k) for k in keys)
            self._con.execute(
                f"INSERT INTO {_quote(name)} ({col_list}) SELECT {col_list} FROM {view} "
                f"ON CONFLICT ({pk}) {conflict}"
            )
        finally:
            self._con.unregister(view)
        log.debug("store_write", table=name, rows=len(frame))
        return len(frame)

    def read_table(
        self,
        name: str,
        where: str | None = None,
        params: Sequence[Any] | None = None,
        *,
        order_by: str | None = None,
    ) -> pd.DataFrame:
        """Read a table (optionally filtered by a SQL `where` fragment with `?` placeholders)."""
        if not self.has_table(name):
            return pd.DataFrame()
        query = f"SELECT * FROM {_quote(name)}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        return self._con.execute(query, list(params or [])).df()

    def delete(self, name: str, where: str, params: Sequence[Any] | None = None) -> None:
        if self.has_table(name):
            self._con.execute(f"DELETE FROM {_quote(name)} WHERE {where}", list(params or []))

    # ---------------------------------------------------------------- bars
    def write_bars(self, df: pd.DataFrame) -> int:
        """Upsert daily bars (contract columns) keyed on (symbol, ts)."""
        frame = normalize_bars(df)
        if frame.empty:
            return 0
        return self.write_table(BARS_TABLE, frame, BAR_KEYS, schema=BARS_SCHEMA)

    def read_bars(
        self,
        symbols: Iterable[str] | None = None,
        start: date | datetime | str | None = None,
        end: date | datetime | str | None = None,
    ) -> pd.DataFrame:
        """Long bars frame for `symbols` (all when None) between `start` and `end` inclusive (session dates)."""
        if not self.has_table(BARS_TABLE):
            return empty_bars()
        clauses: list[str] = []
        params: list[Any] = []
        if symbols is not None:
            syms = sorted({s.upper().strip() for s in symbols})
            if not syms:
                return empty_bars()
            clauses.append("symbol IN (SELECT unnest(?))")
            params.append(syms)
        if start is not None:
            clauses.append("ts >= ?")
            params.append(session_ts(start).to_pydatetime())
        if end is not None:
            clauses.append("ts < ?")
            params.append((session_ts(end) + timedelta(days=1)).to_pydatetime())
        where = " AND ".join(clauses) if clauses else None
        frame = self.read_table(BARS_TABLE, where, params, order_by="symbol, ts")
        if frame.empty:
            return empty_bars()
        frame["ts"] = frame["ts"].dt.tz_convert(TZ)
        return frame[BAR_COLUMNS].reset_index(drop=True)

    def symbols(self) -> list[str]:
        if not self.has_table(BARS_TABLE):
            return []
        rows = self._con.execute(f"SELECT DISTINCT symbol FROM {BARS_TABLE} ORDER BY symbol").fetchall()
        return [r[0] for r in rows]

    def last_bar_dates(self) -> dict[str, date]:
        """Latest session date stored per symbol (used by incremental ingest)."""
        if not self.has_table(BARS_TABLE):
            return {}
        rows = self._con.execute(f"SELECT symbol, max(ts) FROM {BARS_TABLE} GROUP BY symbol").fetchall()
        return {r[0]: as_date(r[1]) for r in rows}

    def snapshot_date(self) -> date | None:
        """Latest session date in the bars table, or None when empty."""
        if not self.has_table(BARS_TABLE):
            return None
        value = self._con.execute(f"SELECT max(ts) FROM {BARS_TABLE}").fetchone()[0]
        return None if value is None else as_date(value)

    # ---------------------------------------------------------------- parquet
    def export_parquet(self, name: str, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._con.execute(f"COPY {_quote(name)} TO '{p.as_posix()}' (FORMAT PARQUET)")
        return p

    def import_parquet(self, name: str, path: str | Path, keys: Sequence[str]) -> int:
        frame = self._con.execute(f"SELECT * FROM read_parquet('{Path(path).as_posix()}')").df()
        if name == BARS_TABLE:
            return self.write_bars(frame)
        return self.write_table(name, frame, keys)
