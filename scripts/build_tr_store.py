"""Copy a research store and back-adjust its bars for cash dividends (data.dividends.total_return_adjust), so close-
to-close returns are total returns for every symbol the Alpaca dividend feed covers, stocks and ETFs alike (SPY,
BIL and the bond ETFs included). For grading weights cards with dividends BESIDE their price-only figures; the
price-only grade stays the registered one (docs/gates.md). Never run on the live store (the function refuses).

    uv run python scripts/build_tr_store.py --source data/live/replay_b9.duckdb --target data/live/replay_b9_tr.duckdb
"""
from __future__ import annotations

import argparse
import shutil

from swing_engine.core.config import ROOT, load_settings
from swing_engine.data.dividends import total_return_adjust
from swing_engine.data.store import Store


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    args = ap.parse_args()
    source, target = ROOT / args.source, ROOT / args.target
    if not target.exists():
        shutil.copyfile(source, target)
        print(f"copied {source} to {target}", flush=True)
    live = str(ROOT / load_settings("config/live.yaml").data.store_path)
    with Store(target) as store:
        print(total_return_adjust(store, live_path=live), flush=True)
    print("TR STORE DONE", flush=True)


if __name__ == "__main__":
    main()
