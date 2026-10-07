"""Pushover deliverer. P3 => emergency priority (retry/expire) so it repeats until acknowledged.

Transient failures (connection errors, 429 with `Retry-After`, 5xx) are retried a few times with short waits;
other 4xx responses fail immediately. The pipeline sends P3 to every channel concurrently, so a slow Pushover
never delays Telegram.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import structlog

from swing_engine.core.interfaces import Deliverer
from swing_engine.core.registry import register

from ..constants import (
    DELIVERY_RETRY_AFTER_MAX_S,
    HTTP_SERVER_ERROR,
    HTTP_TIMEOUT_S,
    HTTP_TOO_MANY,
    PUSHOVER_API,
    PUSHOVER_BACKOFF_BASE_S,
    PUSHOVER_EMERGENCY_EXPIRE_S,
    PUSHOVER_EMERGENCY_RETRY_S,
    PUSHOVER_MAX_RETRIES,
    PUSHOVER_PRIORITY,
)

log = structlog.get_logger(__name__)
EMERGENCY = 2


def retry_after_s(resp: httpx.Response, attempt: int, base: float = PUSHOVER_BACKOFF_BASE_S) -> float:
    """Seconds to wait before retrying: `Retry-After` when present (capped), else linear backoff."""
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), DELIVERY_RETRY_AFTER_MAX_S)
        except ValueError:
            pass
    return base * (attempt + 1)


@register("deliverer", "pushover")
class PushoverDeliverer(Deliverer):
    name = "pushover"

    def __init__(
        self,
        user_key: str,
        app_token: str,
        client: httpx.AsyncClient | None = None,
        url: str = PUSHOVER_API,
        sleeper: Callable[[float], Any] = asyncio.sleep,
    ):
        self.user_key = user_key
        self.app_token = app_token
        self.url = url
        self._client = client
        self._owns_client = client is None
        self._sleep = sleeper

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _payload(self, title: str, body: str, priority: str, meta: dict[str, Any] | None) -> dict[str, Any]:
        po = PUSHOVER_PRIORITY.get(priority, 0)
        data: dict[str, Any] = {
            "token": self.app_token,
            "user": self.user_key,
            "title": title[:250],
            "message": body[:1024],
            "priority": po,
        }
        if po == EMERGENCY:
            data["retry"] = PUSHOVER_EMERGENCY_RETRY_S
            data["expire"] = PUSHOVER_EMERGENCY_EXPIRE_S
        if meta and meta.get("url"):
            data["url"] = str(meta["url"])
        return data

    async def send(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> bool:
        payload = self._payload(title, body, priority, meta)
        for attempt in range(PUSHOVER_MAX_RETRIES + 1):
            last = attempt == PUSHOVER_MAX_RETRIES
            try:
                resp = await self.client.post(self.url, data=payload)
            except httpx.HTTPError as e:
                log.warning("pushover.http_error", error=type(e).__name__, attempt=attempt)
                if last:
                    return False
                await self._sleep(PUSHOVER_BACKOFF_BASE_S * (attempt + 1))
                continue
            if resp.status_code == HTTP_TOO_MANY or resp.status_code >= HTTP_SERVER_ERROR:
                log.warning("pushover.retryable", status=resp.status_code, attempt=attempt, body=resp.text[:200])
                if last:
                    return False
                await self._sleep(retry_after_s(resp, attempt))
                continue
            if not resp.is_success:
                log.warning("pushover.failed", status=resp.status_code, body=resp.text[:200])
                return False
            try:
                return int(resp.json().get("status", 0)) == 1
            except ValueError:
                return True
        return False  # pragma: no cover - every branch above returns on the last attempt
