import numpy as np
import pandas as pd
import pytest

from swing_engine.data.b6 import FACTOR_COLUMNS, etf_factors, join_b6
from swing_engine.data.store import Store

DAYS = pd.date_range("2024-01-02", periods=4, freq="B", tz="America/New_York")


def _bars(closes: dict[str, list[float]]) -> pd.DataFrame:
    rows = [{"symbol": s, "ts": d, "open": c, "high": c, "low": c, "close": c, "volume": 1e6}
            for s, cs in closes.items() for d, c in zip(DAYS, cs, strict=False)]
    return pd.DataFrame(rows)


ETFS = {"SPY": [100.0, 101.0, 101.0, 102.01], "IWM": [50.0, 51.0, 51.0, 51.0],
        "IWD": [10.0, 10.2, 10.2, 10.2], "IWF": [20.0, 20.2, 20.2]}  # IWF has no bar on the last day


def test_factor_proxies_are_same_day_returns_and_nan_when_an_etf_is_missing():
    f = etf_factors(_bars(ETFS))
    assert f["etf_mkt"].iloc[1] == pytest.approx(0.01) and f["etf_smb"].iloc[1] == pytest.approx(0.02 - 0.01)
    assert f["etf_hml"].iloc[1] == pytest.approx(0.02 - 0.01)
    assert f.iloc[0].isna().all()  # no previous close
    assert np.isnan(f["etf_hml"].iloc[3]) and f["etf_mkt"].iloc[3] == pytest.approx(0.01)


def test_join_is_a_no_op_without_the_sic_table_and_adds_columns_with_it():
    panel = _bars({"AAA": [5.0, 5.0, 5.0, 5.0], "BBB": [7.0, 7.0, 7.0, 7.0]})
    with Store() as store:
        store.write_bars(_bars(ETFS))
        assert join_b6(store, panel) is panel  # not the batch-6 store: untouched
        store.write_table("sic", pd.DataFrame({"symbol": ["AAA"], "cik": ["1"], "sic": ["3674"]}), ["symbol"])
        out = join_b6(store, panel)
    assert out.loc[out["symbol"] == "AAA", "sic2"].eq(36.0).all() and out.loc[out["symbol"] == "BBB", "sic2"].isna().all()
    for sym in ("AAA", "BBB"):  # the same factor value on every symbol's row of a session
        rows = out.loc[out["symbol"] == sym]
        assert rows["etf_mkt"].iloc[1] == pytest.approx(0.01) and np.isnan(rows["etf_mkt"].iloc[0])
    assert set(FACTOR_COLUMNS) <= set(out.columns)
