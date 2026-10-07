from __future__ import annotations

from datetime import date

from swing_engine.core.config import Secrets, Settings
from swing_engine.data.ingest import SYMBOLS_TABLE, make_provider, run_ingest
from swing_engine.data.sample import SampleProvider
from swing_engine.data.store import Store


def _settings() -> Settings:
    return Settings.model_validate({"data": {"bar_provider": "sample", "history_years": 1}})


def test_run_ingest_sample_into_store_and_incremental() -> None:
    settings = _settings()
    secrets = Secrets(_env_file=None)
    with Store(":memory:") as store:
        res = run_ingest(settings, secrets, "sample", ["SPY", "ACME"], date(2024, 1, 1), date(2024, 3, 31), store)
        assert res["provider"] == "sample" and res["symbols_requested"] == 2 and res["symbols_with_bars"] == 2
        assert res["bars_written"] == store.count("bars") > 100
        assert res["errors"] == [] and res["snapshot_date"] == "2024-03-28"
        assert store.count(SYMBOLS_TABLE) == len(SampleProvider().list_symbols())
        # incremental: only the overlap + new sessions are fetched; the upsert keeps the row count exact
        res2 = run_ingest(settings, secrets, "sample", ["SPY", "ACME"], date(2024, 1, 1), date(2024, 4, 30), store)
        assert res2["bars_written"] < res["bars_written"]
        assert store.count("bars") == len(SampleProvider().daily_bars(["SPY", "ACME"], date(2024, 1, 1), date(2024, 4, 30)))
        # full refresh refetches everything
        res3 = run_ingest(settings, secrets, "sample", ["SPY", "ACME"], date(2024, 1, 1), date(2024, 4, 30), store, full=True)
        assert res3["bars_written"] == store.count("bars")


def test_run_ingest_defaults_to_provider_listing_and_static_symbols() -> None:
    secrets = Secrets(_env_file=None)
    with Store(":memory:") as store:
        res = run_ingest(_settings(), secrets, "sample", None, date(2024, 1, 1), date(2024, 1, 10), store)
        assert res["symbols_requested"] == res["symbols_listed"] > 50
        assert res["symbols_with_bars"] < res["symbols_requested"]  # delisted names have no bars in the window
    settings = Settings.model_validate({"data": {"bar_provider": "sample"}, "universe": {"static_symbols": ["spy"]}})
    with Store(":memory:") as store:
        res = run_ingest(settings, secrets, None, None, date(2024, 1, 1), date(2024, 1, 10), store)
        assert res["symbols_requested"] == 1 and store.symbols() == ["SPY"]


def test_run_ingest_redacts_credentials_in_provider_errors() -> None:
    secret = "SECRET-TOKEN-123"

    class Broken(SampleProvider):
        name = "broken"

        def daily_bars(self, symbols, start, end):
            raise RuntimeError(f"Client error '401' for url 'https://eodhd.com/api/eod/SPY.US?api_token={secret}&fmt=json'")

    with Store(":memory:") as store:
        res = run_ingest(_settings(), Secrets(_env_file=None), None, ["SPY"], date(2024, 1, 1), date(2024, 1, 10), store, provider=Broken())
    assert len(res["errors"]) == 1 and res["bars_written"] == 0
    assert secret not in res["errors"][0]["error"] and "api_token=***" in res["errors"][0]["error"]


def test_make_provider_uses_registry_and_from_settings() -> None:
    prov = make_provider("sample", _settings(), Secrets(_env_file=None))
    assert isinstance(prov, SampleProvider)
    try:
        make_provider("nope", _settings(), Secrets(_env_file=None))
    except KeyError as exc:
        assert "nope" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown provider must raise KeyError")
