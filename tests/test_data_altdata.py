from __future__ import annotations

from datetime import date

import httpx
import respx

from swing_engine.data.altdata import (
    FINRA_CNMS_URL,
    NASDAQ_REGSHO_URL,
    NASDAQ_SSR_URL,
    REGSHO_COLUMNS,
    SHORT_VOLUME_COLUMNS,
    SSR_COLUMNS,
    nightly_files,
    parse_finra_short_volume,
    parse_regsho_threshold,
    parse_ssr_list,
)
from tests.helpers_data import FakeClock, fixture_text


def test_parse_ssr_list() -> None:
    df = parse_ssr_list(fixture_text("nasdaq_shorthalts.txt"), date(2024, 10, 2))
    assert list(df.columns) == SSR_COLUMNS and len(df) == 3  # trailer dropped
    assert df["symbol"].tolist() == ["ABCD", "EFGH", "IJKL"]
    assert df["trigger_time"].iloc[0] == "09:45:12" and df["market_category"].iloc[1] == "G"
    assert (df["date"] == date(2024, 10, 2)).all()
    assert parse_ssr_list("").empty


def test_parse_regsho_threshold() -> None:
    df = parse_regsho_threshold(fixture_text("nasdaq_regsho.txt"), date(2024, 10, 2))
    assert list(df.columns) == REGSHO_COLUMNS and len(df) == 2
    assert df["threshold_flag"].tolist() == [True, True] and df["rule_3210"].tolist() == [False, True]


def test_parse_finra_short_volume() -> None:
    df = parse_finra_short_volume(fixture_text("finra_cnms.txt"))
    assert list(df.columns) == SHORT_VOLUME_COLUMNS and len(df) == 3
    assert df["date"].iloc[0] == date(2024, 10, 2) and df["short_volume"].iloc[0] == 12345678
    assert df["short_ratio"].iloc[1] == 0.5 and df["short_ratio"].isna().iloc[2]
    assert df["market"].iloc[0] == "B,Q,N"


@respx.mock
def test_nightly_files_fetches_parses_and_tolerates_missing(tmp_path) -> None:
    day = date(2024, 10, 2)
    respx.get(NASDAQ_SSR_URL.format(yyyymmdd="20241002")).mock(return_value=httpx.Response(200, text=fixture_text("nasdaq_shorthalts.txt")))
    respx.get(NASDAQ_REGSHO_URL.format(yyyymmdd="20241002")).mock(return_value=httpx.Response(404))
    finra = respx.get(FINRA_CNMS_URL.format(yyyymmdd="20241002")).mock(return_value=httpx.Response(200, text=fixture_text("finra_cnms.txt")))
    clock = FakeClock()
    out = nightly_files(day, cache_dir=tmp_path, sleep=clock.sleep)
    assert set(out) == {"ssr", "regsho_threshold", "short_volume"}
    assert len(out["ssr"]) == 3 and len(out["short_volume"]) == 3
    assert out["regsho_threshold"].empty and list(out["regsho_threshold"].columns) == REGSHO_COLUMNS
    again = nightly_files("2024-10-02", cache_dir=tmp_path, sleep=clock.sleep)
    assert finra.call_count == 1 and len(again["short_volume"]) == 3  # raw text cached
