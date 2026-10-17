from __future__ import annotations

import io
import zipfile
from datetime import date

import httpx
import numpy as np
import pytest
import respx

from swing_engine.core.registry import get
from swing_engine.data.tiingo import TIINGO_BASE_URL, TIINGO_TICKERS_URL, TiingoProvider, TiingoQuotaReached
from tests.helpers_data import FakeClock

ROWS = [{"date": "2014-06-06T00:00:00.000Z", "open": 650.0, "high": 651.0, "low": 644.0, "close": 645.0,
         "volume": 1000, "adjClose": 90.0, "divCash": 0.0, "splitFactor": 1.0},
        {"date": "2014-06-09T00:00:00.000Z", "open": 92.0, "high": 94.0, "low": 91.0, "close": 93.0,
         "volume": 7000, "adjClose": 91.0, "divCash": 0.0, "splitFactor": 7.0}]


def _provider(tmp_path, per_month: int = 500) -> TiingoProvider:
    clock = FakeClock()
    return TiingoProvider("tok", cache_dir=tmp_path, clock=clock, sleep=clock.sleep, symbols_per_month=per_month,
                          today=lambda: date(2026, 10, 14))


@respx.mock
def test_bars_split_adjusted_and_token_never_cached(tmp_path) -> None:
    route = respx.get(f"{TIINGO_BASE_URL}/tiingo/daily/aapl/prices").mock(return_value=httpx.Response(200, json=ROWS))
    p = _provider(tmp_path)
    bars = p.daily_bars(["AAPL"], date(2014, 6, 1), date(2014, 6, 30))
    assert route.calls[0].request.url.params["token"] == "tok"
    assert np.allclose(bars["close"], [645.0 / 7, 93.0]) and np.allclose(bars["volume"], [7000, 7000])
    assert bars["adj_close"].tolist() == [90.0, 91.0]
    assert not any("tok" in f.read_text() for f in tmp_path.glob("*.json"))
    p.daily_bars(["AAPL"], date(2014, 6, 1), date(2014, 6, 30))  # cached: no new request, no new charge
    assert route.call_count == 1 and p.symbols_used() == {"AAPL"}
    assert get("bar_provider", "tiingo") is TiingoProvider


@respx.mock
def test_monthly_symbol_cap(tmp_path) -> None:
    respx.get(url__regex=rf"{TIINGO_BASE_URL}/tiingo/daily/.*/prices").mock(return_value=httpx.Response(200, json=ROWS))
    p = _provider(tmp_path, per_month=1)
    p.daily_bars(["AAA"], date(2014, 6, 1), date(2014, 6, 30))
    with pytest.raises(TiingoQuotaReached):
        p.daily_bars(["BBB"], date(2014, 6, 1), date(2014, 6, 30))


@respx.mock
def test_symbol_list_marks_delisted(tmp_path) -> None:
    csv = ("ticker,exchange,assetType,priceCurrency,startDate,endDate\nAAPL,NASDAQ,Stock,USD,1980-12-12,2026-10-13\n"
           "LEH,NYSE,Stock,USD,1994-05-02,2008-09-17\nSPY,NYSE ARCA,ETF,USD,1993-01-29,2026-10-13\n"
           "XXX,SHE,Stock,CNY,2010-01-04,2026-10-13\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("supported_tickers.csv", csv)
    respx.get(TIINGO_TICKERS_URL).mock(return_value=httpx.Response(200, content=buf.getvalue()))
    df = _provider(tmp_path).list_symbols().set_index("symbol")
    assert sorted(df.index) == ["AAPL", "LEH", "SPY"]
    assert {s: bool(a) for s, a in df["active"].items()} == {"AAPL": True, "LEH": False, "SPY": True}
    assert df.loc["SPY", "type"] == "ETF"
