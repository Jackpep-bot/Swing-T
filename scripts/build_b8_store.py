"""Add the deal filings' headers (table `form_parties`, data.b8) to the batch-7 research store, which batch 8 also
uses (docs/preregistration/2026-10-14-batch8.md). The live store is not touched. Resumable; run detached:

    nohup uv run python scripts/build_b8_store.py > data/logs/research/b8_store.log 2>&1 &
"""
from __future__ import annotations

from swing_engine.core.config import ROOT, load_secrets
from swing_engine.data.b8 import run_header_ingest
from swing_engine.data.edgar import Edgar
from swing_engine.data.store import Store

TARGET = ROOT / "data" / "live" / "replay_b7.duckdb"


def main() -> None:
    edgar = Edgar(load_secrets().edgar_user_agent)
    with Store(TARGET) as store:
        res = run_header_ingest(store, edgar.http.get_text,
                                progress=lambda n, total: n % 200 == 0 and print(f"headers {n}/{total}", flush=True))
        print("headers", res, flush=True)
        print(store.sql("select role, count(*) as n, count(distinct accession) as filings from form_parties group by 1")
              .to_string(), flush=True)
    print("B8 STORE DONE", flush=True)


if __name__ == "__main__":
    main()
