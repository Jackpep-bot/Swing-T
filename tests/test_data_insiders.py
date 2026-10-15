"""data.insiders: Form 4 quarterly data-set parsing, CMP classification, panel features and the strategies (no network)."""
from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import pytest
import respx

from swing_engine import cli
from swing_engine.core.config import Secrets
from swing_engine.data import insiders as I
from swing_engine.data._common import session_ts
from swing_engine.data.calendar import prev_trading_day
from swing_engine.data.edgar import SEC_BASE_URL, Edgar
from swing_engine.data.fundamentals import join_edgar
from swing_engine.data.store import Store
from swing_engine.strategies.insider_cluster import InsiderCluster
from swing_engine.strategies.opportunistic_insider_purchases_cmp import OpportunisticInsiderPurchases
from tests import test_cli as cli_tests
from tests.fixtures.strategies.panel import last_date, make_panel
from tests.test_cli import runner

workdir = cli_tests.workdir

FIXTURES = Path(__file__).parent / "fixtures" / "insiders"
UA = "swing-engine test@example.com"
CIK_MAP = {"0000000111": ["ACME"], "0000000333": ["BRK.A", "BRK.B"]}


def fixture_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in FIXTURES.glob("*.tsv"):
            zf.write(p, p.name)
    return buf.getvalue()


_n = iter(range(10**6))


def trade(symbol: str, owner: str, filed: str, tdate: str | None = None, *, code: str = "P", value: float = 50_000.0,
          price: float = 10.0, acc: str | None = None, sk: str | None = None) -> dict:
    n = next(_n)
    return {
        "symbol": symbol, "cik": "0000000111", "accession": acc or f"acc-{n}", "trans_id": sk or str(n),
        "filing_date": date.fromisoformat(filed), "transaction_date": date.fromisoformat(tdate or filed),
        "owner_cik": owner, "owner_name": owner, "is_director": True, "is_officer": False, "officer_title": "",
        "is_ten_pct": False, "code": code, "shares": value / price, "price": price, "value": value,
    }


def frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=I.TRADE_COLUMNS)


def index(symbol: str, days: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"symbol": symbol, "ts": [session_ts(d) for d in days]})


def feature(trades: pd.DataFrame, symbol: str, days: list[str], col: str, cls: str | None = None) -> list[float]:
    labels = None if cls is None else pd.Series(cls, index=trades.index)
    return list(I.insider_features(trades, index(symbol, days), labels)[col])


# ------------------------------------------------------------------------------------------------ parsing
def test_parse_keeps_only_open_market_p_and_s_from_original_form4() -> None:
    df = I.parse_quarter(fixture_zip(), CIK_MAP)
    assert sorted(df["trans_id"]) == ["1", "10", "2", "9"]  # A/M/F, P-disposed, 4/A and Form 5 rows dropped
    assert set(df["code"]) == {"P", "S"}
    acme = df[df["trans_id"] == "1"].iloc[0]
    assert acme["symbol"] == "ACME" and acme["filing_date"] == date(2024, 1, 5)
    assert acme["transaction_date"] == date(2024, 1, 3) and acme["value"] == pytest.approx(1000.0)
    assert acme["is_director"] and acme["is_officer"] and not acme["is_ten_pct"] and acme["officer_title"] == "CEO"
    old = df[df["trans_id"] == "9"].iloc[0]
    assert old["symbol"] == "OLDCO" and old["is_ten_pct"]  # CIK not in today's map: the filed ticker
    assert df[df["trans_id"] == "10"].iloc[0]["symbol"] == "BRK.B"  # share class kept, store-style separator


def test_quarter_list_stops_at_last_completed_quarter() -> None:
    assert I.quarter_list(2025, date(2026, 10, 8))[-1] == "2026q3"
    assert I.quarter_list(2026, date(2026, 3, 31)) == []
    assert len(I.quarter_list(2006, date(2026, 10, 8))) == 83


# ------------------------------------------------------------------------------------------ classification
def test_cmp_routine_opportunistic_unclassified() -> None:
    rows = [trade("ACME", "R", f"{y}-03-10", code="S") for y in (2021, 2022, 2023)]
    rows += [trade("ACME", "O", d, code="S") for d in ("2021-02-10", "2022-05-10", "2023-08-10")]
    rows += [trade("ACME", "U", d, code="S") for d in ("2021-03-10", "2023-03-10")]  # no 2022 trade
    rows += [trade("ACME", who, "2024-03-12") for who in ("R", "O", "U")]
    t = frame(rows)
    labels = I.label_trades(t)
    got = dict(zip(t["owner_cik"][t["code"] == "P"], labels[t["code"] == "P"], strict=True))
    assert got == {"R": I.ROUTINE, "O": I.OPPORTUNISTIC, "U": I.UNCLASSIFIED}


def test_cmp_uses_only_trades_filed_before_the_year() -> None:
    late = [trade("ACME", "L", f"{y}-03-10", code="S") for y in (2021, 2022)]
    late.append(trade("ACME", "L", "2024-01-15", "2023-03-10", code="S"))  # 2023 trade filed late, in 2024
    late.append(trade("ACME", "L", "2024-03-12"))
    t = frame(late)
    assert I.label_trades(t).iloc[-1] == I.UNCLASSIFIED  # the late 2023 filing was not public on Jan 1 2024
    # future trades never change a past label
    base = frame([trade("ACME", "R", f"{y}-03-10", code="S") for y in (2021, 2022, 2023)] + [trade("ACME", "R", "2024-03-12")])
    more = pd.concat([base, frame([trade("ACME", "R", "2025-07-01"), trade("ACME", "R", "2026-01-05")])],
                     ignore_index=True)
    assert I.label_trades(more).iloc[3] == I.label_trades(base).iloc[3] == I.ROUTINE


# --------------------------------------------------------------------------------------------- features
def test_filing_visible_from_the_next_session() -> None:
    t = frame([trade("ACME", "A", "2024-01-05", "2024-01-03", value=40_000.0)])  # Friday filing
    days = ["2024-01-04", "2024-01-05", "2024-01-08", "2024-01-09"]
    assert feature(t, "ACME", days, "opp_buy_flag", I.OPPORTUNISTIC) == [0.0, 0.0, 1.0, 0.0]
    assert feature(t, "ACME", days, "opp_buy_value_21d", I.OPPORTUNISTIC) == [0.0, 0.0, 40_000.0, 40_000.0]


def test_opp_buy_value_21d_window_routine_and_joint_filers() -> None:
    t = frame([
        trade("ACME", "A", "2024-01-05", value=40_000.0, acc="x", sk="1"),
        trade("ACME", "B", "2024-01-05", value=40_000.0, acc="x", sk="1"),  # joint filer: same transaction
        trade("ACME", "C", "2024-01-10", value=10_000.0),
    ])
    # first visible 2024-01-08 (idx 0); 21 sessions later (2024-02-07, MLK holiday on 01-15) it has dropped out
    days = ["2024-01-08", "2024-01-11", "2024-02-06", "2024-02-07"]
    assert feature(t, "ACME", days, "opp_buy_value_21d", I.OPPORTUNISTIC) == [40_000.0, 50_000.0, 50_000.0, 10_000.0]
    assert feature(t, "ACME", days, "opp_buy_value_21d", I.ROUTINE) == [0.0] * 4
    assert feature(t, "OTHER", days, "opp_buy_value_21d", I.OPPORTUNISTIC) == [0.0] * 4


def test_cluster_score_counts_distinct_buyers_in_30_days() -> None:
    t = frame([
        trade("ACME", "A", "2024-01-02", "2023-12-28", price=10.0),
        trade("ACME", "B", "2024-01-10", "2024-01-09", price=11.0),
        trade("ACME", "C", "2024-01-25", "2024-01-24", price=12.0),
        trade("ACME", "C", "2024-01-25", "2024-01-24", price=12.5),
        trade("ACME", "D", "2024-01-25", "2024-01-24", code="S"),  # sellers never count
    ])
    days = ["2024-01-02", "2024-01-03", "2024-01-25", "2024-01-26", "2024-02-01", "2024-02-02"]
    # A visible 01-03 .. 02-01 (< 01-03 + 30 days); C from 01-26
    assert feature(t, "ACME", days, "insider_cluster_score") == pytest.approx([0.0, 1 / 3, 2 / 3, 1.0, 1.0, 2 / 3])


def test_cluster_rejected_when_trades_share_date_and_price() -> None:
    t = frame([trade("ACME", o, "2024-01-10", "2024-01-09", price=10.0) for o in "ABCD"])
    assert feature(t, "ACME", ["2024-01-11"], "insider_cluster_score") == [0.0]
    t.loc[0, "price"] = 9.0  # 3 of 4 identical = 75% < 80%: a real cluster
    assert feature(t, "ACME", ["2024-01-11"], "insider_cluster_score") == [4 / 3]


# ------------------------------------------------------------------------------------- store join + strategies
def test_join_is_a_no_op_without_the_table() -> None:
    idx = index("ACME", ["2024-01-08"])
    assert I.join_insiders(Store(), idx) is idx
    assert join_edgar(Store(), idx) is idx


def test_strategies_fire_from_joined_store_panel() -> None:
    panel = make_panel(("AAA", "BBB"), n_days=320, seed=5)
    as_of = last_date(panel)
    filed = prev_trading_day(as_of).isoformat()
    y = as_of.year
    rows = [trade("AAA", "X", f"{y - k}-{m:02d}-10", code="S") for k, m in ((3, 1), (2, 4), (1, 7))]  # opportunistic
    rows += [trade("AAA", "X", filed, value=60_000.0, price=10.0)]
    rows += [trade("AAA", o, filed, price=10.0 + i) for i, o in enumerate("YZ")]  # 3 distinct buyers
    rows += [trade("BBB", "W", filed, value=1_000_000.0)]  # unclassified: no history
    store = Store()
    store.write_table(I.TRADES_TABLE, frame(rows), I.TRADE_KEYS, schema=I.TRADE_SCHEMA)
    joined = I.join_insiders(store, panel)
    last = joined[joined["ts"].dt.date == as_of].set_index("symbol")
    assert last.loc["AAA", "insider_cluster_score"] == pytest.approx(1.0)
    assert last.loc["AAA", "opp_buy_value_21d"] == pytest.approx(60_000.0) and last.loc["AAA", "opp_buy_flag"] == 1.0
    assert last.loc["BBB", "opp_buy_value_21d"] == 0.0
    assert [s.symbol for s in InsiderCluster().signals(joined, as_of)] == ["AAA"]
    assert [s.symbol for s in OpportunisticInsiderPurchases().signals(joined, as_of)] == ["AAA"]
    earlier = joined[joined["ts"].dt.date < date.fromisoformat(filed)]
    assert (earlier[I.FEATURE_COLUMNS] == 0.0).all().all()  # nothing visible before the filing


# ------------------------------------------------------------------------------------------------ ingest
@respx.mock
def test_ingest_is_resumable_and_records_missing_quarters() -> None:
    respx.get(f"{SEC_BASE_URL}/files/company_tickers.json").mock(return_value=httpx.Response(
        200, json={"0": {"cik_str": 111, "ticker": "ACME", "title": "ACME CORP"}}))
    zip_bytes = fixture_zip()

    def dataset(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == UA
        return httpx.Response(404) if "2024q2" in request.url.path else httpx.Response(200, content=zip_bytes)

    route = respx.get(url__startswith=f"{SEC_BASE_URL}/files/structureddata/").mock(side_effect=dataset)
    store = Store()
    edgar = Edgar(UA, sleep=lambda s: None)
    r1 = I.run_insider_ingest(store, edgar, start_year=2024, today=date(2024, 7, 15))
    assert r1["fetched"] == 1 and r1["missing"] == 1 and r1["rows"] == 4
    assert store.count(I.TRADES_TABLE) == 4
    r2 = I.run_insider_ingest(store, edgar, start_year=2024, today=date(2024, 7, 15))
    assert r2["fetched"] == 0 and r2["missing"] == 1  # only the 404 quarter is retried
    assert route.call_count == 3
    assert I.run_insider_ingest(store, edgar, start_year=2024, quarters=0, today=date(2024, 7, 15))["missing"] == 0


# --------------------------------------------------------------------------------------------------- CLI


@respx.mock
def test_cli_ingest_insiders(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, edgar_user_agent=UA))
    respx.get(f"{SEC_BASE_URL}/files/company_tickers.json").mock(return_value=httpx.Response(200, json={}))
    respx.get(url__startswith=f"{SEC_BASE_URL}/files/structureddata/").mock(
        return_value=httpx.Response(200, content=fixture_zip()))
    result = runner.invoke(cli.app, ["ingest-insiders", "--start-year", "2024", "--quarters", "1"])
    assert result.exit_code == 0, result.output
    assert "Insider ingest" in result.output and UA not in result.output
    with Store(workdir / "data" / "swing.duckdb") as store:
        assert store.count(I.TRADES_TABLE) == 4


def test_cli_ingest_insiders_refuses_placeholder_agent(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, edgar_user_agent=""))
    result = runner.invoke(cli.app, ["ingest-insiders"])
    assert result.exit_code == cli.EXIT_REFUSED
