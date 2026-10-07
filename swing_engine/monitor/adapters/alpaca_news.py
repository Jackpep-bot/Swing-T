"""Alpaca news websocket (Benzinga): `wss://stream.data.alpaca.markets/v1beta1/news`, subscribe news:["*"]."""
from __future__ import annotations

import json
from typing import Any

import structlog

from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import ALPACA_NEWS_WS
from ._base import WebSocketFeed, decode_frame, now_utc, parse_ts

log = structlog.get_logger(__name__)
SOURCE = "alpaca_news"


def parse_news_message(msg: dict[str, Any]) -> Event | None:
    if msg.get("T") != "n":
        return None
    nid = msg.get("id")
    if nid is None:
        return None
    return Event(
        event_id=f"{SOURCE}:{nid}",
        source=SOURCE,
        kind="news",
        ts_source=parse_ts(msg.get("created_at") or msg.get("updated_at")),
        ts_received=now_utc(),
        symbols=[s.upper() for s in msg.get("symbols", []) if isinstance(s, str)],
        title=str(msg.get("headline", "")).strip(),
        body=str(msg.get("summary") or "").strip(),
        url=msg.get("url"),
        meta={"provider": msg.get("source"), "author": msg.get("author"), "provider_id": nid},
    )


def parse_frame(raw: str | bytes) -> list[Event]:
    data = decode_frame(raw)
    msgs = data if isinstance(data, list) else [data]
    out: list[Event] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if m.get("T") == "error":
            raise ConnectionError(f"alpaca news error {m.get('code')}: {m.get('msg')}")
        ev = parse_news_message(m)
        if ev is not None:
            out.append(ev)
    return out


@register("feed", SOURCE)
class AlpacaNewsFeed(WebSocketFeed):
    name = SOURCE
    url = ALPACA_NEWS_WS

    def __init__(self, api_key: str, secret_key: str, symbols: list[str] | None = None, **kw: Any):
        super().__init__(**kw)
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbols = symbols or ["*"]

    async def _handshake(self, ws: Any) -> None:
        await ws.send(json.dumps({"action": "auth", "key": self.api_key, "secret": self.secret_key}))
        await ws.send(json.dumps({"action": "subscribe", "news": self.symbols}))

    def _parse_frame(self, raw: str | bytes) -> list[Event]:
        return parse_frame(raw)
