"""`swing ingest-edgar`: real Edgar client + data.fundamentals against respx-mocked SEC endpoints (no network)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from swing_engine import cli
from swing_engine.core.config import Secrets
from swing_engine.data.edgar import SEC_BASE_URL, SEC_DATA_BASE_URL
from swing_engine.data.fundamentals import read_earnings, read_fundamentals
from swing_engine.data.store import Store
from tests import test_cli as cli_tests
from tests.test_cli import runner

workdir = cli_tests.workdir
EDGAR_FIXTURES = Path(__file__).parent / "fixtures" / "edgar"
DATA_FIXTURES = Path(__file__).parent / "fixtures" / "data_layer"
UA = "swing-engine test@example.com"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _secrets(monkeypatch: pytest.MonkeyPatch, agent: str) -> None:
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, edgar_user_agent=agent))


def _mock_sec() -> None:
    """AAPL (CIK 320193) is served the ACME fixtures; MSFT has no XBRL facts (404)."""
    respx.get(f"{SEC_BASE_URL}/files/company_tickers.json").mock(
        return_value=httpx.Response(200, json=_json(DATA_FIXTURES / "edgar_company_tickers.json"))
    )

    def data(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == UA
        name = request.url.path.rsplit("/", 1)[-1]
        if "0000789019" in name:
            return httpx.Response(404)
        if request.url.path.startswith("/api/xbrl/companyfacts/"):
            return httpx.Response(200, json=_json(EDGAR_FIXTURES / "companyfacts_CIK0000123456.json"))
        fixture = "submissions_CIK0000123456.json" if name.startswith("CIK0000320193") else name
        return httpx.Response(200, json=_json(EDGAR_FIXTURES / fixture))

    respx.get(url__startswith=f"{SEC_DATA_BASE_URL}/").mock(side_effect=data)


@pytest.mark.parametrize("agent", ["", "swing-engine", Secrets.model_fields["edgar_user_agent"].default])
def test_ingest_edgar_refuses_placeholder_user_agent(workdir: Path, monkeypatch: pytest.MonkeyPatch, agent: str) -> None:
    _secrets(monkeypatch, agent)
    result = runner.invoke(cli.app, ["ingest-edgar", "-s", "AAPL"])
    assert result.exit_code == cli.EXIT_REFUSED
    assert "EDGAR_USER_AGENT" in result.output


@respx.mock
def test_ingest_edgar_writes_tables_and_prints_mapping(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, UA)
    _mock_sec()
    result = runner.invoke(cli.app, ["ingest-edgar", "-s", "AAPL,MSFT", "-s", "GONE"])
    assert result.exit_code == 0, result.output
    assert "ticker -> CIK" in result.output and "no_cik_symbols" in result.output and "GONE" in result.output
    assert UA not in result.output
    with Store(workdir / "data" / "swing.duckdb") as store:
        assert len(read_earnings(store, ["AAPL"])) == 6
        assert len(read_fundamentals(store, ["AAPL"])) > 0
        assert read_fundamentals(store, ["MSFT"]).empty


def test_ingest_edgar_without_symbols_needs_a_store(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _secrets(monkeypatch, UA)
    result = runner.invoke(cli.app, ["ingest-edgar"])
    assert result.exit_code == cli.EXIT_NO_DATA
