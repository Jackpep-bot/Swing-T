"""Build the batch-9 research store (docs/proposals/swing-methods-2026-10/batch9/): a copy of the batch-6 store
(scripts/build_b6_store.py: live store + 2016-24 bars for SVXY, IWD, IWF, BIL + `sic`) plus Alpaca SIP daily bars
2016-01-04 .. 2024-10-06 for SSO (card leveraged_sp500_trend_switch). The live store is not touched.

    nohup uv run python scripts/build_b9_store.py > data/logs/research/b9_store.log 2>&1 &
"""
from __future__ import annotations

import shutil
from datetime import date, timedelta

import pandas as pd

from swing_engine.core.config import ROOT, load_secrets, load_settings
from swing_engine.data.alpaca import AlpacaProvider
from swing_engine.data.ingest import run_ingest
from swing_engine.data.store import Store

SOURCE = ROOT / "data" / "live" / "replay_b6.duckdb"
TARGET = ROOT / "data" / "live" / "replay_b9.duckdb"
ETFS = ["SSO"]
EXTENSION_START = date(2016, 1, 4)


def main() -> None:
    settings, secrets = load_settings("config/live.yaml"), load_secrets()
    if not TARGET.exists():
        shutil.copyfile(SOURCE, TARGET)
        print(f"copied {SOURCE} to {TARGET}", flush=True)
    with Store(TARGET) as store:
        first = store.sql("select min(ts) as t from bars where symbol = 'SSO'")["t"].iloc[0]
        end = pd.Timestamp(first).tz_convert("America/New_York").date() - timedelta(days=1)
        if end > EXTENSION_START:
            prov = AlpacaProvider.from_settings(settings, secrets)
            prov.feed = "sip"  # historical bars older than 15 minutes are free on SIP
            res = run_ingest(settings, secrets, "alpaca", ETFS, EXTENSION_START, end, store, full=True, provider=prov,
                             mode="symbols")
            print({k: v for k, v in dict(res).items() if k != "errors"}, "errors:", res.get("errors"), flush=True)
        print(store.sql("select symbol, min(ts)::date as first, count(*) as bars from bars "
                        "where symbol in ('SSO', 'BIL', 'SPY') group by 1 order by 1").to_string(), flush=True)
    print("B9 STORE DONE", flush=True)


if __name__ == "__main__":
    main()
