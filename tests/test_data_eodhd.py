from __future__ import annotations

from datetime import date

import httpx
import numpy as np
import respx

from swing_engine.core.registry import get
from swing_engine.data.eodhd import EODHD_BASE_URL, EodhdProvider
from tests.helpers_data import FakeClock, fixture_json


def _provider(tmp_path) -> EodhdProvider:
    clock = FakeClock()
    return EodhdProvider("tok", cache_dir=tmp_path, clock=clock, sleep=clock.sleep, today=lambda: date(2024, 10, 1))


@respx.mock
def test_symbols_and_delisted(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_token"] == "tok"
        if request.url.params.get("delisted") == "1":
            return httpx.Response(200, json=fixture_json("eodhd_delisted.json"))
        return httpx.Response(200, json=fixture_json("eodhd_symbols.json"))

    respx.get(f"{EODHD_BASE_URL}/exchange-symbol-list/US").mock(side_effect=handler)
    df = _provider(tmp_path).list_symbols()
    assert df["symbol"].tolist() == ["AAPL", "SIVB", "SPY"]
    assert df.set_index("symbol")["active"].to_dict() == {"AAPL": True, "SIVB": False, "SPY": True}
    assert df.set_index("symbol").loc["SPY", "type"] == "ETF"
    assert _provider(tmp_path).delisted_symbols()["symbol"].tolist() == ["SIVB"]


@respx.mock
def test_daily_bars_split_adjusts_ohlc(tmp_path) -> None:
    respx.get(f"{EODHD_BASE_URL}/eod/AAPL.US").mock(return_value=httpx.Response(200, json=fixture_json("eodhd_eod_AAPL.json")))
    bars = _provider(tmp_path).daily_bars(["AAPL"], date(2024, 1, 2), date(2024, 1, 3))
    assert len(bars) == 2
    factor = 184.9 / 185.64
    assert np.isclose(bars["close"].iloc[0], 184.9) and np.isclose(bars["open"].iloc[0], 187.15 * factor)
    assert np.isclose(bars["volume"].iloc[0], 82488700 / factor)
    assert bars["adj_close"].tolist() == [184.9, 183.5]
    assert bars["vwap"].isna().all()
    assert get("bar_provider", "eodhd") is EodhdProvider
