"""NYSE current trade halts CSV (`nyse.com/api/trade-halts/current/download`). Columns vary slightly over time, so
lookups are by lower-cased substring (halt date / halt time / symbol / name / reason / resume ...)."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

import httpx
import structlog

from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import HTTP_TIMEOUT_S, NYSE_HALTS_CSV, NYSE_HALTS_INTERVAL_S
from ..hours import ET as ET_TZ
from ._base import PollingFeed, now_utc, stable_id

log = structlog.get_logger(__name__)
SOURCE = "nyse_halts"
_REASON_MAP = {
    "news pending": "T1",
    "news released": "T2",
    "news dissemination": "T2",
    "additional information requested": "T12",
    "sec trading suspension": "H10",
    "luld pause": "LUDP",
    "volatility trading pause": "LUDP",
    "market wide circuit breaker": "MWC1",
}


def _pick(row: dict[str, str], *needles: str) -> str:
    for k, v in row.items():
        kl = (k or "").lower()
        if all(n in kl for n in needles):
            return (v or "").strip()
    return ""


def normalize_reason(reason: str) -> str:
    r = reason.strip()
    if not r:
        return ""
    if r.upper() in {"T1", "T2", "T12", "H10", "LUDP", "MWC1", "M"}:
        return r.upper()
    rl = r.lower()
    for needle, code in _REASON_MAP.items():
        if needle in rl:
            return code
    return r.upper()


def parse_halts_csv(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in csv.DictReader(io.StringIO(text)):
        sym = _pick(raw, "symbol").upper()
        if not sym:
            continue
        rows.append(
            {
                "IssueSymbol": sym,
                "IssueName": _pick(raw, "name"),
                "Market": "NYSE",
                "ReasonCode": normalize_reason(_pick(raw, "reason")),
                "HaltDate": _pick(raw, "halt", "date"),
                "HaltTime": _pick(raw, "halt", "time"),
                "ResumptionDate": _pick(raw, "resume", "date") or _pick(raw, "resumption", "date"),
                "ResumptionTradeTime": _pick(raw, "resume", "time") or _pick(raw, "resumption", "time"),
            }
        )
    return rows


def _ts(d: str, t: str, fallback: datetime) -> datetime:
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(f"{d} {t}", fmt).replace(tzinfo=ET_TZ)
        except ValueError:
            continue
    return fallback


def row_to_event(row: dict[str, str], resumed: bool = False, received: datetime | None = None) -> Event:
    now = received or now_utc()
    status = "resumed" if resumed else "halted"
    key = f"{row['IssueSymbol']}|{row['HaltDate']}|{row['HaltTime']}"
    ts = _ts(row["ResumptionDate"] or row["HaltDate"], row["ResumptionTradeTime"], now) if resumed else _ts(
        row["HaltDate"], row["HaltTime"], now
    )
    return Event(
        event_id=stable_id(SOURCE, key, status),
        source=SOURCE,
        kind="halt",
        ts_source=ts,
        ts_received=now,
        symbols=[row["IssueSymbol"]],
        title=f"{row['IssueSymbol']} {status} {row['ReasonCode']} {row['IssueName']}".strip(),
        meta={"status": status, "reason_code": row["ReasonCode"], "market": "NYSE", "name": row["IssueName"],
              "halt_date": row["HaltDate"], "halt_time": row["HaltTime"],
              "resumption_trade_time": row["ResumptionTradeTime"]},
    )


@register("feed", SOURCE)
class NyseHaltsFeed(PollingFeed):
    name = SOURCE

    def __init__(
        self, interval_s: float = NYSE_HALTS_INTERVAL_S, client: httpx.AsyncClient | None = None, url: str = NYSE_HALTS_CSV, **kw: Any
    ):
        super().__init__(interval_s=interval_s, **kw)
        self.url = url
        self._client = client
        self.known: dict[str, dict[str, str]] = {}

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
        return self._client

    def diff(self, rows: list[dict[str, str]]) -> list[Event]:
        out: list[Event] = []
        for row in rows:
            key = f"{row['IssueSymbol']}|{row['HaltDate']}|{row['HaltTime']}"
            prev = self.known.get(key)
            if prev is None:
                out.append(row_to_event(row))
                if row["ResumptionTradeTime"]:
                    out.append(row_to_event(row, resumed=True))
            elif row["ResumptionTradeTime"] and not prev["ResumptionTradeTime"]:
                out.append(row_to_event(row, resumed=True))
            self.known[key] = row
        return out

    async def _poll(self) -> list[Event]:
        resp = await self.client.get(self.url)
        resp.raise_for_status()
        return self.diff(parse_halts_csv(resp.text))
