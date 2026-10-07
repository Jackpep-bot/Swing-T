"""Extend the real-data store's history backward with Alpaca's free historical SIP daily bars (2016+).

Massive's free tier gives 2 years of every US ticker (survivorship-free for that window). Alpaca's free account
serves split-adjusted consolidated (SIP) daily bars back to 2016 for any symbol you name. This script names the
symbols that were liquid in the Massive window (common stocks/ADRs plus index and sector ETFs) and fetches their
history before the Massive window starts.

Caveat recorded in the store (ingest_meta 'alpaca_extension'): names that were delisted BEFORE the Massive
window are absent, so results before that window carry survivorship bias and should be read as optimistic.

    uv run python scripts/extend_history_alpaca.py --settings config/live.yaml
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from swing_engine.core.config import load_secrets, load_settings
from swing_engine.data.alpaca import AlpacaProvider
from swing_engine.data.ingest import run_ingest
from swing_engine.data.store import Store

EXTENSION_START = date(2016, 1, 4)
MIN_AVG_DOLLAR_VOLUME = 1_000_000.0
MIN_AVG_PRICE = 2.0
MIN_SESSIONS = 60
ALWAYS = ["SPY", "QQQ", "IWM", "DIA", "MDY", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB",
          "XLRE", "XLC", "SMH", "XBI", "KRE", "ITB", "GLD", "TLT", "HYG"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settings", default="config/live.yaml")
    ap.add_argument("--start", default=EXTENSION_START.isoformat())
    args = ap.parse_args()
    settings, secrets = load_settings(args.settings), load_secrets()
    store = Store(settings.data.store_path)
    try:
        first = store.sql("select min(ts) as t from bars").iloc[0]["t"]
        end = pd.Timestamp(first).tz_convert("America/New_York").date() - timedelta(days=1)
        liquid = store.sql(
            """with s as (select symbol, avg(close*volume) dv, avg(close) px, count(*) n from bars group by symbol)
               select s.symbol from s join symbols y on y.symbol = s.symbol
               where y.type in ('CS', 'ADRC') and dv >= ? and px >= ? and n >= ?""",
            [MIN_AVG_DOLLAR_VOLUME, MIN_AVG_PRICE, MIN_SESSIONS],
        )["symbol"].tolist()
        symbols = sorted(set(liquid) | set(ALWAYS))
        print(f"extending {len(symbols)} symbols from {args.start} to {end} via Alpaca SIP (split-adjusted)")
        prov = AlpacaProvider.from_settings(settings, secrets)
        prov.feed = "sip"  # historical bars older than 15 minutes are free on SIP
        result = run_ingest(settings, secrets, "alpaca", symbols, date.fromisoformat(args.start), end, store,
                            full=True, provider=prov, mode="symbols")
        store.write_table("ingest_meta", pd.DataFrame({"key": ["alpaca_extension"], "value": [
            f"{args.start}..{end} for {len(symbols)} symbols liquid in the Massive window; pre-window names that "
            "were delisted are missing (survivorship bias before the Massive window)"]}), ["key"])
        print({k: v for k, v in dict(result).items() if k != "errors"}, "errors:", len(result.get("errors") or []))
    finally:
        store.close()


if __name__ == "__main__":
    main()
