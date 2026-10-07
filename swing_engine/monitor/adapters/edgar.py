"""EDGAR current-filings Atom poller (`browse-edgar?action=getcurrent&type=8-K&owner=exclude&count=100&output=atom`).

Rules: identify with a User-Agent ("App contact@email"), stay under 10 req/s (token bucket), poll every 15-30 s,
cursor = newest accession number seen. Entry titles look like "8-K - ACME CORP (0001234567) (Filer)"; the HTML
summary carries Filed / AccNo / Items lines. CIK -> ticker is resolved through an injected map (SEC company_tickers).
"""
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from typing import Any

import feedparser
import httpx
import structlog

from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import (
    EDGAR_COUNT,
    EDGAR_CURRENT_URL,
    EDGAR_DEFAULT_FORMS,
    EDGAR_POLL_INTERVAL_S,
    EDGAR_RATE_PER_S,
    HTTP_TIMEOUT_S,
)
from ..delivery._ratelimit import TokenBucket
from ..rules.eightk_items import parse_items
from ._base import PollingFeed, now_utc, parse_ts

log = structlog.get_logger(__name__)
SOURCE = "edgar"
_TITLE_RE = re.compile(r"^\s*(?P<form>.+?)\s+-\s+(?P<name>.+?)\s+\((?P<cik>\d{6,10})\)\s*\((?P<role>[^)]+)\)\s*$")
_ACC_RE = re.compile(r"AccNo:\s*</b>\s*(?P<acc>\d{10}-\d{2}-\d{6})", re.I)
_ACC_PLAIN_RE = re.compile(r"(\d{10}-\d{2}-\d{6})")
_FILED_RE = re.compile(r"Filed:\s*</b>\s*(?P<d>\d{4}-\d{2}-\d{2})", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_title(title: str) -> dict[str, str]:
    m = _TITLE_RE.match(title or "")
    if not m:
        return {"form": "", "name": title.strip(), "cik": "", "role": ""}
    d = m.groupdict()
    d["form"] = d["form"].strip().upper()
    d["cik"] = d["cik"].lstrip("0") or "0"
    return d


def parse_atom(text: str, cik_map: Mapping[str, str] | None = None, received: Any = None) -> list[Event]:
    """Return one Event per filing entry (issuer/filer entries only; Form 4 'Reporting' rows are skipped)."""
    feed = feedparser.parse(text)
    cik_map = {str(k).lstrip("0"): v.upper() for k, v in (cik_map or {}).items()}
    out: list[Event] = []
    for entry in feed.entries:
        info = parse_title(entry.get("title", ""))
        role = info["role"].lower()
        if role.startswith("reporting"):
            continue
        summary = entry.get("summary", "") or ""
        acc_m = _ACC_RE.search(summary) or _ACC_PLAIN_RE.search(entry.get("id", "") or entry.get("link", "") or summary)
        acc = acc_m.group(1) if acc_m else ""
        if not acc:
            continue
        form = info["form"] or next((t.get("term", "") for t in entry.get("tags", []) if t.get("term")), "")
        plain = html.unescape(_TAG_RE.sub(" ", summary))
        filed_m = _FILED_RE.search(summary)
        ts = parse_ts(entry.get("updated") or entry.get("published") or (filed_m.group("d") if filed_m else None))
        sym = cik_map.get(info["cik"])
        items = parse_items(plain) if form.upper().startswith("8-K") else []
        out.append(
            Event(
                event_id=f"{SOURCE}:{acc}",
                source=SOURCE,
                kind="filing",
                ts_source=ts,
                ts_received=received or now_utc(),
                symbols=[sym] if sym else [],
                title=f"{form} {info['name']}" + (f" items {', '.join(items)}" if items else ""),
                body=plain.strip()[:1000],
                url=entry.get("link"),
                meta={
                    "form_type": form.upper(),
                    "cik": info["cik"],
                    "company": info["name"],
                    "accession": acc,
                    "items": items,
                    "role": info["role"],
                },
            )
        )
    return out


@register("feed", SOURCE)
class EdgarFeed(PollingFeed):
    name = SOURCE

    def __init__(
        self,
        user_agent: str,
        form_types: tuple[str, ...] | list[str] = EDGAR_DEFAULT_FORMS,
        cik_map: Mapping[str, str] | None = None,
        interval_s: float = EDGAR_POLL_INTERVAL_S,
        client: httpx.AsyncClient | None = None,
        base_url: str = EDGAR_CURRENT_URL,
        cursor: str | None = None,
        **kw: Any,
    ):
        super().__init__(interval_s=interval_s, **kw)
        self.user_agent = user_agent
        self.form_types = list(form_types)
        self.cik_map = cik_map or {}
        self.base_url = base_url
        self._client = client
        self.cursor = cursor
        self._bucket = TokenBucket(EDGAR_RATE_PER_S, sleeper=self._sleep)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S, headers={"User-Agent": self.user_agent})
        return self._client

    def _params(self, form: str) -> dict[str, Any]:
        owner = "only" if form == "4" else "exclude"
        return {"action": "getcurrent", "type": form, "owner": owner, "count": EDGAR_COUNT, "output": "atom"}

    async def _poll(self) -> list[Event]:
        events: list[Event] = []
        for form in self.form_types:
            await self._bucket.acquire()
            resp = await self.client.get(self.base_url, params=self._params(form), headers={"User-Agent": self.user_agent})
            resp.raise_for_status()
            events.extend(parse_atom(resp.text, self.cik_map))
        events.sort(key=lambda e: e.ts_source)
        if events:
            self.cursor = events[-1].meta["accession"]
        return events

    async def catch_up(self, since_event_id: str | None) -> list[Event]:
        fresh = await self._poll()
        if since_event_id is None:
            return fresh
        return [e for e in fresh if e.event_id > since_event_id]
