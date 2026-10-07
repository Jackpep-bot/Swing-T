from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing_engine.core.registry import get
from swing_engine.data._common import BAR_COLUMNS, TZ
from swing_engine.data.alpaca import AlpacaProvider


class _BarSet:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df


class _StubDataClient:
    def __init__(self) -> None:
        self.requests = []

    def get_stock_bars(self, request):
        self.requests.append(request)
        idx = pd.MultiIndex.from_tuples(
            [("AAPL", pd.Timestamp("2024-01-02 05:00", tz="UTC")), ("AAPL", pd.Timestamp("2024-01-03 05:00", tz="UTC"))],
            names=["symbol", "timestamp"],
        )
        return _BarSet(
            pd.DataFrame(
                {"open": [187.15, 184.22], "high": [188.44, 185.88], "low": [183.885, 183.43], "close": [185.64, 184.25],
                 "volume": [82488700, 58414500], "trade_count": [1, 2], "vwap": [185.9, 184.3]},
                index=idx,
            )
        )


def test_daily_bars_from_stub_client() -> None:
    client = _StubDataClient()
    p = AlpacaProvider("k", "s", data_client=client)
    bars = p.daily_bars(["aapl"], date(2024, 1, 2), date(2024, 1, 3))
    assert list(bars.columns) == BAR_COLUMNS and len(bars) == 2
    assert str(bars["ts"].dt.tz) == TZ and bars["ts"].iloc[0].strftime("%Y-%m-%d %H:%M") == "2024-01-02 00:00"
    assert bars["adj_close"].equals(bars["close"])
    req = client.requests[0]
    assert req.symbol_or_symbols == ["AAPL"] and req.adjustment.value == "split"
    assert get("bar_provider", "alpaca") is AlpacaProvider


def test_requires_keys_without_client() -> None:
    with pytest.raises(ValueError):
        AlpacaProvider("", "")
