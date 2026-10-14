"""Shadow books: weights cards followed forward with no orders (their trades are never sent anywhere).

Today one book: batch 9's `sp500_momentum_index_replica`, exactly as pre-registered (docs/preregistration/
2026-10-14-batch9.md; rules in research.b9_books). It failed its alpha-t bar but beat SPY in both windows, so it is
watched forward from START (the research thread's recommended option, relayed 2026-10-14; the owner's answer pending).

State lives in `<store dir>/runs/shadow_books/<book>.json`: the books in force (rebalance session -> weights) and the
latest forward record. The first book is the selection in force on START (rebalance 2026-09-21); each later March /
September rebalance is computed by the nightly with the same code over the store's whole history (the 80/120 buffer
depends on every earlier book), which takes a few minutes twice a year. The forward record buys the first book at
the open of the first session after START (10 bp a side, research.weights_book) and is read beside SPY's close-to-
close return from START's close.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research.prereg_eval import _bar_days
from swing_engine.research.weights_book import simulate

log = structlog.get_logger(__name__)

BOOK = b9.MOMENTUM
START = date(2026, 10, 14)  # the forward record starts here
SUBDIR = Path("runs") / "shadow_books"


def book_path(store_dir: Path, book: str = BOOK) -> Path:
    return store_dir / SUBDIR / f"{book}.json"


def load(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())
    return {"book": BOOK, "start": START.isoformat(), "orders": {}, "record": None}


def save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=1, sort_keys=True, default=str))


def rebalance_days(as_of: date) -> list[date]:
    """Every rebalance session of the card up to ``as_of`` (published calendar)."""
    sessions = trading_days(b9.DATA_START, as_of + timedelta(days=40))
    days = [b9.rebalance_day(ref, sessions) for ref in b9.reference_days(sessions)]
    return [d for d in days if d is not None and d <= as_of]


def needed_days(as_of: date) -> list[date]:
    """The book in force on START, and every rebalance after START up to ``as_of``."""
    days = rebalance_days(max(as_of, START))
    first = [d for d in days if d <= START][-1:]
    return first + [d for d in days if START < d <= as_of]


def compute_orders(store: Any, as_of: date) -> dict[date, pd.Series]:
    """The card's books over the store's whole history up to ``as_of`` (research.b9_books, unchanged)."""
    bars = store.read_bars(None, b9.DATA_START, as_of)
    bars = bars.assign(day=_bar_days(bars["ts"]))
    closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
    sessions = [d for d in trading_days(b9.DATA_START, as_of) if d in closes.index]
    return b9.momentum_orders(closes, b9.mcap_function(store, bars, closes), sessions)


def record(store: Any, state: dict[str, Any], as_of: date) -> dict[str, Any] | None:
    """Forward return of the book since START beside SPY's, through ``as_of``."""
    orders = {date.fromisoformat(d): pd.Series(w) for d, w in state["orders"].items()}
    days = [d for d in trading_days(START, as_of) if d > START]
    if not orders or not days:
        return None
    first, plan = days[0], {}
    for d in sorted(orders):
        plan[max(d, first)] = orders[d]  # the book in force on START is bought at the first session after it
    symbols = sorted({s for w in plan.values() for s in w.index} | {b9.MARKET})
    bars = store.read_bars(symbols, START, as_of)
    bars = bars.assign(day=_bar_days(bars["ts"]))
    closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
    opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
    span = closes.loc[first:as_of]
    if span.empty:
        return None
    book = simulate(opens.loc[first:as_of], span, None, plan)
    spy = closes[b9.MARKET]
    return {"as_of": str(span.index[-1]), "sessions": len(book), "book_return": float((1.0 + book["ret"]).prod() - 1.0),
            "spy_return": float(spy.loc[span.index[-1]] / spy.loc[START] - 1.0) if START in spy.index else None,
            "names": int(book["n_held"].iloc[-1]) if len(book) else 0}


def update(store: Any, store_dir: Path, as_of: date) -> dict[str, Any]:
    """Add any missing book (heavy: the whole history), refresh the forward record, save; returns the record."""
    path = book_path(store_dir)
    state = load(path)
    missing = [d for d in needed_days(as_of) if d.isoformat() not in state["orders"]]
    if missing:
        books = compute_orders(store, as_of)
        for d in missing:
            if d in books:
                state["orders"][d.isoformat()] = {s: float(w) for s, w in books[d].items()}
        log.info("shadow_books.books_added", book=BOOK, days=[str(d) for d in missing])
    if not state["orders"]:
        raise RuntimeError("no book in force: the store lacks the history the card needs")
    state["record"] = record(store, state, as_of)
    save(path, state)
    return state["record"] or {}


def summary_lines(store_dir: Path) -> list[str]:
    """The weekly report's section: the forward record beside SPY (empty without a saved state)."""
    path = book_path(store_dir)
    if not path.exists():
        return []
    rec = load(path).get("record")
    head = ["## Shadow books (no orders)", "",
            f"`{BOOK}` (batch 9, failed its alpha-t bar; followed forward with no orders since {START})."]
    if not rec:
        return [*head, "No forward session yet.", ""]
    spy = rec.get("spy_return")
    return [*head, f"Through {rec['as_of']} ({rec['sessions']} sessions, {rec['names']} names): book "
            f"{rec['book_return']:+.2%}, SPY {spy:+.2%}." if spy is not None else
            f"Through {rec['as_of']}: book {rec['book_return']:+.2%}.", ""]


__all__ = ["BOOK", "START", "book_path", "compute_orders", "needed_days", "record", "summary_lines", "update"]
