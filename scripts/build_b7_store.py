"""Build the batch-7 research store (docs/proposals/swing-methods-2026-10/batch7/README.md): a copy of the batch-6
store (scripts/build_b6_store.py) plus table `form_events` (DEFM14A, SC TO-T and 424B filings from the EDGAR
submissions pages, data.b7). The live store is not touched. Resumable; run detached:

    nohup uv run python scripts/build_b7_store.py > data/logs/research/b7_store.log 2>&1 &
"""
from __future__ import annotations

import shutil

from swing_engine.core.config import ROOT, load_secrets
from swing_engine.data.b7 import run_form_ingest
from swing_engine.data.edgar import Edgar
from swing_engine.data.store import Store

SOURCE = ROOT / "data" / "live" / "replay_b6.duckdb"
TARGET = ROOT / "data" / "live" / "replay_b7.duckdb"


def main() -> None:
    if not TARGET.exists():
        shutil.copyfile(SOURCE, TARGET)
        print(f"copied {SOURCE} to {TARGET}", flush=True)
    with Store(TARGET) as store:
        res = run_form_ingest(store, Edgar(load_secrets().edgar_user_agent),
                              progress=lambda n, total: n % 250 == 0 and print(f"forms {n}/{total}", flush=True))
        print("forms", res, flush=True)
        print(store.sql("select form, count(*) as n, min(filing_date) as first, max(filing_date) as last "
                        "from form_events group by 1 order by 1").to_string(), flush=True)
    print("B7 STORE DONE", flush=True)


if __name__ == "__main__":
    main()
