"""Copy a research store and add Alpaca SIP daily bars from 2016-01-04 for symbols whose history starts later (the
Massive window). Same free source as scripts/extend_history_alpaca.py; the live store is not touched. Resumable.

    uv run python scripts/extend_research_store.py --source data/live/replay_b9.duckdb \
        --target data/live/replay_b12.duckdb --symbols EFA,EEM,VNQ,IEF,DBC,UUP
"""
from __future__ import annotations

import argparse
import shutil
from datetime import date, timedelta

import pandas as pd

from swing_engine.core.config import ROOT, load_secrets, load_settings
from swing_engine.data.alpaca import AlpacaProvider
from swing_engine.data.ingest import run_ingest
from swing_engine.data.store import Store

EXTENSION_START = date(2016, 1, 4)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--symbols", required=True)
    args = ap.parse_args()
    settings, secrets = load_settings("config/live.yaml"), load_secrets()
    source, target = ROOT / args.source, ROOT / args.target
    if not target.exists():
        shutil.copyfile(source, target)
        print(f"copied {source} to {target}", flush=True)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    with Store(target) as store:
        first = store.sql("select symbol, min(ts) as t from bars where symbol in (select unnest(?)) group by 1", [symbols])
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
                        "where symbol in (select unnest(?)) group by 1 order by 1", [symbols]).to_string(), flush=True)
    print("STORE DONE", flush=True)


if __name__ == "__main__":
    main()
