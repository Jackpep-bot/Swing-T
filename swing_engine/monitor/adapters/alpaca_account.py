"""Alpaca account websocket (`wss://paper-api.alpaca.markets/stream`), `trade_updates` stream."""
from __future__ import annotations

import json
from typing import Any

import structlog

from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import ALPACA_ACCOUNT_WS_LIVE, ALPACA_ACCOUNT_WS_PAPER
from ._base import WebSocketFeed, decode_frame, now_utc, parse_ts, stable_id

log = structlog.get_logger(__name__)
SOURCE = "alpaca_account"


def parse_trade_update(msg: dict[str, Any]) -> Event | None:
    if msg.get("stream") != "trade_updates":
        return None
    data = msg.get("data") or {}
    order = data.get("order") or {}
    sym = str(order.get("symbol", "")).upper()
    ev_name = str(data.get("event", "")).lower()
    ts = parse_ts(data.get("timestamp") or order.get("updated_at"))
    oid = order.get("id") or order.get("client_order_id") or "na"
    title = f"{sym} order {ev_name} {order.get('side', '')} {order.get('filled_qty') or order.get('qty', '')}".strip()
    return Event(
        event_id=stable_id(SOURCE, oid, ev_name, data.get("execution_id") or ts.isoformat()),
        source=SOURCE,
        kind="account",
        ts_source=ts,
        ts_received=now_utc(),
        symbols=[sym] if sym else [],
        title=title,
        body=str(order.get("status", "")),
        meta={
            "event": ev_name,
            "order_id": order.get("id"),
            "client_order_id": order.get("client_order_id"),
            "side": order.get("side"),
            "status": order.get("status"),
            "qty": order.get("qty"),
            "filled_qty": order.get("filled_qty"),
            "filled_avg_price": order.get("filled_avg_price"),
            "position_qty": data.get("position_qty"),
        },
    )


def parse_frame(raw: str | bytes) -> list[Event]:
    data = decode_frame(raw)
    if not isinstance(data, dict):
        return []
    stream = data.get("stream")
    if stream == "authorization" and (data.get("data") or {}).get("status") != "authorized":
        raise ConnectionError("alpaca account stream: not authorized")
    ev = parse_trade_update(data)
    return [ev] if ev is not None else []


@register("feed", SOURCE)
class AlpacaAccountFeed(WebSocketFeed):
    name = SOURCE

    def __init__(self, api_key: str, secret_key: str, paper: bool = True, **kw: Any):
        super().__init__(**kw)
        self.url = ALPACA_ACCOUNT_WS_PAPER if paper else ALPACA_ACCOUNT_WS_LIVE
        self.api_key = api_key
        self.secret_key = secret_key

    async def _handshake(self, ws: Any) -> None:
        await ws.send(json.dumps({"action": "auth", "key": self.api_key, "secret": self.secret_key}))
        await ws.send(json.dumps({"action": "listen", "data": {"streams": ["trade_updates"]}}))

    def _parse_frame(self, raw: str | bytes) -> list[Event]:
        return parse_frame(raw)
