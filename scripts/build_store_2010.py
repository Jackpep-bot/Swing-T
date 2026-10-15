"""Build the 2010-2026 research store (docs/plan-store-2010.md; pieces in swing_engine/data/history2010.py).

Copies a research store and adds 2010-01-04 .. its first bar for the large caps of 2009-2015, dead ones included, from
Tiingo, plus their splits, dividends and (dead CIKs) EDGAR fundamentals. The live store is never touched.

    uv run python scripts/build_store_2010.py --source data/live/replay_b9.duckdb --target data/live/replay_2010.duckdb

Nothing goes to the network unless TIINGO_API_KEY is set (the owner adds it to .env himself). Resumable: EDGAR and
Tiingo responses are cached under data/raw/, writes are upserts, and when the month's free Tiingo allowance (500
symbols) runs out it stops and prints how far it got; rerun next month. Grading on 2010-2015 needs the owner's word.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date

import httpx
import pandas as pd

from swing_engine.core.config import ROOT, load_secrets
from swing_engine.data import history2010 as H
from swing_engine.data.store import Store

ETFS = ("SPY", "BIL")  # the grade's benchmark and bill rate need the early years too
OUT_DIR = ROOT / "data" / "research" / "store2010"


def store_map(store: Store) -> dict[str, str]:
    """CIK -> the store's symbol for it (a live ticker before a delisted key)."""
    frames = [store.sql(f"select cik, symbol from {t} where cik is not null") for t in ("symbols", "sic")
              if store.has_table(t)]
    m = pd.concat(frames, ignore_index=True).dropna()
    m["cik"] = m["cik"].astype(str).str.zfill(10)
    m = m.assign(dead=m["symbol"].str.contains("~")).sort_values(["cik", "dead"], kind="mergesort")
    return dict(m.drop_duplicates("cik").set_index("cik")["symbol"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default="data/live/replay_b9.duckdb")
    ap.add_argument("--target", default="data/live/replay_2010.duckdb")
    ap.add_argument("--top", type=int, default=H.TOP_FLOAT)
    args = ap.parse_args()
    secrets = load_secrets()
    if not secrets.tiingo_api_key:
        print("TIINGO_API_KEY is not set in .env: nothing fetched. Add the key from your free Tiingo account and rerun.")
        sys.exit(2)
    from swing_engine.data.edgar import Edgar
    from swing_engine.data.tiingo import TiingoProvider, TiingoQuotaReached

    edgar = Edgar(secrets.edgar_user_agent, cache_dir=ROOT / "data" / "raw" / "edgar2010")
    tiingo = TiingoProvider(secrets.tiingo_api_key)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source, target = ROOT / args.source, ROOT / args.target
    if not target.exists():
        shutil.copyfile(source, target)
        print(f"copied {source} -> {target}", flush=True)

    # 1. every annual filer 2009-2015 and its public float
    annual = pd.concat([H.parse_form_index(edgar.http.get_text(H.FULL_INDEX_URL.format(year=y, quarter=q),
                                                               cache_key=f"form-idx-{y}-{q}", cache_suffix=".idx"))
                        for y in H.FLOAT_YEARS for q in range(1, 5)], ignore_index=True)
    annual.to_parquet(OUT_DIR / "annual_filings.parquet")
    def companyfacts(cik: str) -> dict | None:
        """Cached (resumable) companyfacts; None when the filer has none."""
        try:
            return edgar.http.get_json(f"{edgar.data_base_url}/api/xbrl/companyfacts/CIK{cik}.json",
                                       cache_key=f"companyfacts-{cik}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    floats = []
    for i, cik in enumerate(sorted(annual["cik"].unique())):
        floats.append(H.public_floats(companyfacts(cik), cik))
        if i % 500 == 0:
            print(f"companyfacts {i} / {annual['cik'].nunique()}", flush=True)
    cands = H.candidates(pd.concat(floats, ignore_index=True), top=args.top)
    cands.to_parquet(OUT_DIR / "candidates.parquet")
    print(f"{len(cands)} candidate CIKs", flush=True)

    # 2. live names from the store; tickers for the dead ones from their last 10-K's instance file
    with Store(target, read_only=True) as store:
        known = store_map(store)
    spans = tiingo.ticker_spans()
    names = [H.Name("", e, e) for e in ETFS]
    hand_check = {}
    for r in cands.itertuples(index=False):
        if r.cik in known:
            names.append(H.Name(r.cik, known[r.cik].split("~")[0], known[r.cik]))
            continue
        filings = annual.loc[annual["cik"] == r.cik].sort_values("filed")
        last = filings.iloc[-1]
        accession = last["path"].rsplit("/", 1)[-1].removesuffix(".txt").replace("-", "")
        index = edgar.http.get_json(H.FILING_INDEX_URL.format(cik=int(r.cik), accession=accession),
                                    cache_key=f"filing-index-{accession}")
        guess = H.instance_ticker(i.get("name", "") for i in (index.get("directory") or {}).get("item") or [])
        ticker, why = H.match_ticker(guess, filings["filed"].iloc[0], last["filed"], spans)
        if ticker is None:
            hand_check[r.cik] = f"{last['company']}: {why}"
        else:
            names.append(H.Name(r.cik, ticker))
    (OUT_DIR / "hand_check.json").write_text(json.dumps(hand_check, indent=1))
    print(f"{len(names)} names to extend, {len(hand_check)} for a hand check", flush=True)

    # 3-4. bars, actions, dead fundamentals; stops cleanly at the month's free allowance
    done: list[H.Name] = []
    report = H.Report()
    with Store(target) as store:
        for n in names:
            try:
                part = H.extend(store, tiingo.daily_rows, [n], facts_for=companyfacts)
            except TiingoQuotaReached as e:
                print(f"stopped: {e}. {len(done)} of {len(names)} names done; rerun next month to continue.", flush=True)
                break
            report.written.update(part.written)
            report.rejected.update(part.rejected)
            report.seams.update(part.seams)
            done.append(n)
    summary = {"as_of": str(date.today()), "names": len(names), "done": len(done), "written": report.written,
               "rejected": report.rejected, "seams": {k: list(v) for k, v in report.seams.items()},
               "hand_check": len(hand_check)}
    (OUT_DIR / "report.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"wrote bars for {len(report.written)} names, rejected {len(report.rejected)}; report {OUT_DIR / 'report.json'}")
    print("STORE 2010 DONE" if len(done) == len(names) else "STORE 2010 PARTIAL", flush=True)


if __name__ == "__main__":
    main()
