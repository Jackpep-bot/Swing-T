"""Telegram Bot API deliverer: 1 msg/s token bucket, honors `retry_after` on 429, HTML-escaped text."""
from __future__ import annotations

import asyncio
import html
from typing import Any

import httpx
import structlog

from swing_engine.core.interfaces import Deliverer
from swing_engine.core.models import Priority
from swing_engine.core.registry import register

from ..constants import (
    HTTP_TIMEOUT_S,
    TELEGRAM_API,
    TELEGRAM_MAX_RETRIES,
    TELEGRAM_RATE_PER_S,
    TELEGRAM_TEXT_MAX,
)
from ._ratelimit import TokenBucket

log = structlog.get_logger(__name__)
HTTP_TOO_MANY = 429


@register("deliverer", "telegram")
class TelegramDeliverer(Deliverer):
    name = "telegram"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        client: httpx.AsyncClient | None = None,
        base_url: str = TELEGRAM_API,
        sleeper=asyncio.sleep,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = base_url.rstrip("/")
        self._client = client
        self._sleep = sleeper
        self._bucket = TokenBucket(TELEGRAM_RATE_PER_S, capacity=1, sleeper=sleeper)

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
        return self._client

    def _url(self) -> str:
        return f"{self.base_url}/bot{self.bot_token}/sendMessage"

    def _payload(self, title: str, body: str, priority: str) -> dict[str, Any]:
        text = f"<b>{html.escape(title)}</b>\n{html.escape(body)}"[:TELEGRAM_TEXT_MAX]
        return {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": priority not in (Priority.P2, Priority.P3),
        }

    async def send(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> bool:
        payload = self._payload(title, body, priority)
        for attempt in range(TELEGRAM_MAX_RETRIES + 1):
            await self._bucket.acquire()
            try:
                resp = await self.client.post(self._url(), json=payload)
            except httpx.HTTPError as e:
                log.warning("telegram.http_error", error=type(e).__name__, attempt=attempt)
                await self._sleep(1.0 + attempt)
                continue
            if resp.status_code == HTTP_TOO_MANY:
                retry_after = 1.0
                try:
                    retry_after = float(resp.json().get("parameters", {}).get("retry_after", retry_after))
                except (ValueError, AttributeError):
                    pass
                log.warning("telegram.rate_limited", retry_after=retry_after, attempt=attempt)
                await self._sleep(retry_after)
                continue
            if resp.is_success:
                try:
                    ok = bool(resp.json().get("ok", True))
                except ValueError:
                    ok = True
                return ok
            log.warning("telegram.failed", status=resp.status_code, body=resp.text[:200])
            return False
        return False
