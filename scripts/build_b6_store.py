"""Build the batch-6 research store (docs/proposals/swing-methods-2026-10/batch6/README.md, "Data"): a copy of the
live store plus (1) Alpaca SIP daily bars before the Massive window for the ETFs the cards read and (2) the `sic`
table from EDGAR submissions (data.sic). The live store is only read. Resumable; run detached:

    nohup uv run python scripts/build_b6_store.py > data/logs/research/b6_store.log 2>&1 &
"""
from __future__ import annotations

import shutil
from datetime import date, timedelta

import pandas as pd

from swing_engine.core.config import ROOT, load_secrets, load_settings
from swing_engine.data.alpaca import AlpacaProvider
from swing_engine.data.edgar import Edgar
from swing_engine.data.ingest import run_ingest
from swing_engine.data.sic import run_sic_ingest
from swing_engine.data.store import Store

LIVE = "config/live.yaml"
TARGET = ROOT / "data" / "live" / "replay_b6.duckdb"
ETFS = ["SVXY", "IWD", "IWF", "BIL"]  # cards vrp_svxy_dual_signal (SVXY, BIL) and residual_reversal_ff3_etf (IWD, IWF)
EXTENSION_START = date(2016, 1, 4)  # scripts/extend_history_alpaca.py: the start of the store's Alpaca history


def main() -> None:
    settings, secrets = load_settings(LIVE), load_secrets()
    if not TARGET.exists():
        shutil.copyfile(ROOT / settings.data.store_path, TARGET)
        print(f"copied the live store to {TARGET}", flush=True)
    with Store(TARGET) as store:
        first = store.sql("select symbol, min(ts) as t from bars where symbol in (select unnest(?)) group by 1", [ETFS])
        late = [r.symbol for r in first.itertuples()
                if pd.Timestamp(r.t).tz_convert("America/New_York").date() > EXTENSION_START + timedelta(days=7)]
        if late:
            end = min(pd.Timestamp(t).tz_convert("America/New_York").date() for t in first["t"]) - timedelta(days=1)
            prov = AlpacaProvider.from_settings(settings, secrets)
            prov.feed = "sip"  # historical bars older than 15 minutes are free on SIP
            res = run_ingest(settings, secrets, "alpaca", late, EXTENSION_START, end, store, full=True, provider=prov,
                             mode="symbols")
            print({k: v for k, v in dict(res).items() if k != "errors"}, "errors:", res.get("errors"), flush=True)
        print(store.sql("select symbol, min(ts)::date as first, count(*) as bars from bars "
                        "where symbol in (select unnest(?)) group by 1 order by 1", [ETFS]).to_string(), flush=True)
        res = run_sic_ingest(store, Edgar(secrets.edgar_user_agent),
                             progress=lambda n, total: n % 500 == 0 and print(f"sic {n}/{total}", flush=True))
        print("sic", res, flush=True)
    print("B6 STORE DONE", flush=True)


if __name__ == "__main__":
    main()
