from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing_engine.data._common import BAR_COLUMNS, TZ
from swing_engine.data.store import Store


def _bars(symbol: str, days: list[str], close: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": symbol,
            "ts": pd.to_datetime(days),
            "open": close,
            "high": [c * 1.01 for c in close],
            "low": [c * 0.99 for c in close],
            "close": close,
            "volume": [1_000_000.0] * len(close),
            "vwap": close,
            "adj_close": close,
        }
    )


@pytest.fixture
def store() -> Store:
    with Store(":memory:") as s:
        yield s


def test_write_bars_upserts_on_symbol_and_ts(store: Store) -> None:
    assert store.write_bars(_bars("AAA", ["2024-01-02", "2024-01-03"], [10.0, 11.0])) == 2
    # overlapping write: same key, new close -> updated, not duplicated
    assert store.write_bars(_bars("AAA", ["2024-01-03", "2024-01-04"], [99.0, 12.0])) == 2
    out = store.read_bars(["AAA"])
    assert list(out.columns) == BAR_COLUMNS
    assert out["close"].tolist() == [10.0, 99.0, 12.0]
    assert str(out["ts"].dt.tz) == TZ
    assert store.count("bars") == 3


def test_write_bars_dedupes_within_batch_keeping_last(store: Store) -> None:
    df = pd.concat([_bars("AAA", ["2024-01-02"], [1.0]), _bars("AAA", ["2024-01-02"], [2.0])])
    assert store.write_bars(df) == 1
    assert store.read_bars()["close"].tolist() == [2.0]


def test_read_bars_filters_symbols_and_dates(store: Store) -> None:
    store.write_bars(_bars("AAA", ["2024-01-02", "2024-01-03", "2024-01-04"], [1.0, 2.0, 3.0]))
    store.write_bars(_bars("bbb", ["2024-01-02"], [5.0]))
    out = store.read_bars(["AAA"], start=date(2024, 1, 3), end="2024-01-04")
    assert out["close"].tolist() == [2.0, 3.0]
    assert store.read_bars(["BBB"])["symbol"].tolist() == ["BBB"]  # symbols are upper-cased on write
    assert store.read_bars([]).empty
    assert store.read_bars(["NOPE"]).empty
    assert store.symbols() == ["AAA", "BBB"]
    assert store.last_bar_dates() == {"AAA": date(2024, 1, 4), "BBB": date(2024, 1, 2)}


def test_empty_store_reads_empty_frames(store: Store) -> None:
    assert store.read_bars().empty
    assert list(store.read_bars().columns) == BAR_COLUMNS
    assert store.snapshot_date() is None
    assert store.read_table("nothing").empty
    assert store.write_bars(pd.DataFrame()) == 0


def test_snapshot_date(store: Store) -> None:
    store.write_bars(_bars("AAA", ["2024-01-02", "2024-02-15"], [1.0, 2.0]))
    assert store.snapshot_date() == date(2024, 2, 15)


def test_generic_table_upsert_and_schema_evolution(store: Store) -> None:
    df = pd.DataFrame({"symbol": ["A", "B"], "date": [date(2024, 1, 2)] * 2, "short_volume": [10.0, 20.0]})
    assert store.write_table("short_volume", df, keys=["symbol", "date"]) == 2
    df2 = pd.DataFrame({"symbol": ["B", "C"], "date": [date(2024, 1, 2)] * 2, "short_volume": [25.0, 30.0], "market": ["Q", "N"]})
    assert store.write_table("short_volume", df2, keys=["symbol", "date"]) == 2
    out = store.read_table("short_volume", order_by="symbol")
    assert out["short_volume"].tolist() == [10.0, 25.0, 30.0]
    assert pd.isna(out["market"].iloc[0]) and out["market"].tolist()[1:] == ["Q", "N"]
    filtered = store.read_table("short_volume", where="short_volume >= ?", params=[25.0], order_by="symbol")
    assert filtered["symbol"].tolist() == ["B", "C"]
    assert "short_volume" in store.tables()


def test_write_table_rejects_bad_identifiers_and_missing_keys(store: Store) -> None:
    df = pd.DataFrame({"symbol": ["A"], "x": [1]})
    with pytest.raises(ValueError):
        store.write_table("bad name; drop", df, keys=["symbol"])
    with pytest.raises(ValueError):
        store.write_table("ok", df, keys=["missing"])
    with pytest.raises(ValueError):
        store.write_table("ok", df, keys=[])


def test_file_store_persists_and_parquet_round_trip(tmp_path) -> None:
    path = tmp_path / "nested" / "swing.duckdb"
    with Store(path) as s:
        s.write_bars(_bars("AAA", ["2024-01-02", "2024-01-03"], [1.0, 2.0]))
        pq = s.export_parquet("bars", tmp_path / "bars.parquet")
    assert pq.exists()
    with Store(path) as s:
        assert s.count("bars") == 2
        assert s.snapshot_date() == date(2024, 1, 3)
    with Store(":memory:") as fresh:
        assert fresh.import_parquet("bars", pq, keys=["symbol", "ts"]) == 2
        assert fresh.read_bars()["close"].tolist() == [1.0, 2.0]
    assert pd.read_parquet(pq).shape[0] == 2
