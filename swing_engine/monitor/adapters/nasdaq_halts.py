"""Nasdaq trade-halts RSS (`nasdaqtrader.com/rss.aspx?feed=tradehalts`), 60 s cadence, full diff per poll.

Fields (ndaq namespace): IssueSymbol, IssueName, Market, ReasonCode, PauseThresholdPrice, HaltDate, HaltTime,
ResumptionDate, ResumptionQuoteTime, ResumptionTradeTime. Times are ET. A row that gains a ResumptionTradeTime
emits a second "resumed" event.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx
import structlog

from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import HTTP_TIMEOUT_S, NASDAQ_HALTS_INTERVAL_S, NASDAQ_HALTS_RSS
from ..hours import ET as ET_TZ
from ._base import PollingFeed, now_utc, stable_id

log = structlog.get_logger(__name__)
SOURCE = "nasdaq_halts"
_FIELDS = (
    "IssueSymbol", "IssueName", "Market", "ReasonCode", "PauseThresholdPrice", "HaltDate", "HaltTime",
    "ResumptionDate", "ResumptionQuoteTime", "ResumptionTradeTime",
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_halts_rss(text: str) -> list[dict[str, str]]:
    root = ET.fromstring(text)
    rows: list[dict[str, str]] = []
    for item in root.iter():
        if _local(item.tag) != "item":
            continue
        row = {f: "" for f in _FIELDS}
        for child in item:
            name = _local(child.tag)
            if name in row:
                row[name] = (child.text or "").strip()
        if row["IssueSymbol"]:
            row["IssueSymbol"] = row["IssueSymbol"].upper()
            rows.append(row)
    return rows


def _et_datetime(d: str, t: str, fallback: datetime) -> datetime:
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(f"{d} {t}", fmt).replace(tzinfo=ET_TZ)
        except ValueError:
            continue
    return fallback


def halt_key(row: dict[str, str]) -> str:
    return f"{row['IssueSymbol']}|{row['HaltDate']}|{row['HaltTime']}"


def row_to_event(row: dict[str, str], resumed: bool = False, received: datetime | None = None) -> Event:
    now = received or now_utc()
    ts = _et_datetime(row["HaltDate"], row["HaltTime"], now)
    code = row["ReasonCode"].upper()
    status = "resumed" if resumed else "halted"
    title = f"{row['IssueSymbol']} {status} {code} {row['IssueName']}".strip()
    if resumed:
        ts = _et_datetime(row["ResumptionDate"] or row["HaltDate"], row["ResumptionTradeTime"], now)
    return Event(
        event_id=stable_id(SOURCE, halt_key(row), status),
        source=SOURCE,
        kind="halt",
        ts_source=ts,
        ts_received=now,
        symbols=[row["IssueSymbol"]],
        title=title,
        meta={
            "status": status,
            "reason_code": code,
            "market": row["Market"],
            "halt_date": row["HaltDate"],
            "halt_time": row["HaltTime"],
            "pause_threshold_price": row["PauseThresholdPrice"],
            "resumption_quote_time": row["ResumptionQuoteTime"],
            "resumption_trade_time": row["ResumptionTradeTime"],
            "name": row["IssueName"],
        },
    )


class HaltDiff:
    """Stateful diff of successive RSS snapshots -> new halt / resume events."""

    def __init__(self) -> None:
        self.known: dict[str, dict[str, str]] = {}

    def apply(self, rows: list[dict[str, str]], received: datetime | None = None) -> list[Event]:
        out: list[Event] = []
        for row in rows:
            key = halt_key(row)
            prev = self.known.get(key)
            if prev is None:
                out.append(row_to_event(row, received=received))
                if row["ResumptionTradeTime"]:
                    out.append(row_to_event(row, resumed=True, received=received))
            elif row["ResumptionTradeTime"] and not prev["ResumptionTradeTime"]:
                out.append(row_to_event(row, resumed=True, received=received))
            self.known[key] = row
        return out


@register("feed", SOURCE)
class NasdaqHaltsFeed(PollingFeed):
    name = SOURCE

    def __init__(
        self,
        interval_s: float = NASDAQ_HALTS_INTERVAL_S,
        client: httpx.AsyncClient | None = None,
        url: str = NASDAQ_HALTS_RSS,
        **kw: Any,
    ):
        super().__init__(interval_s=interval_s, **kw)
        self.url = url
        self._client = client
        self.diff = HaltDiff()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
        return self._client

    async def _poll(self) -> list[Event]:
        resp = await self.client.get(self.url)
        resp.raise_for_status()
        return self.diff.apply(parse_halts_rss(resp.text))
