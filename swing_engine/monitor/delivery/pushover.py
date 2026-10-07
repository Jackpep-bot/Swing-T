"""Pushover deliverer. P3 => emergency priority (retry/expire) so it repeats until acknowledged."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from swing_engine.core.interfaces import Deliverer
from swing_engine.core.registry import register

from ..constants import (
    HTTP_TIMEOUT_S,
    PUSHOVER_API,
    PUSHOVER_EMERGENCY_EXPIRE_S,
    PUSHOVER_EMERGENCY_RETRY_S,
    PUSHOVER_PRIORITY,
)

log = structlog.get_logger(__name__)
EMERGENCY = 2


@register("deliverer", "pushover")
class PushoverDeliverer(Deliverer):
    name = "pushover"

    def __init__(self, user_key: str, app_token: str, client: httpx.AsyncClient | None = None, url: str = PUSHOVER_API):
        self.user_key = user_key
        self.app_token = app_token
        self.url = url
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
        return self._client

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
        try:
            resp = await self.client.post(self.url, data=self._payload(title, body, priority, meta))
        except httpx.HTTPError as e:
            log.warning("pushover.http_error", error=type(e).__name__)
            return False
        if not resp.is_success:
            log.warning("pushover.failed", status=resp.status_code, body=resp.text[:200])
            return False
        try:
            return int(resp.json().get("status", 0)) == 1
        except ValueError:
            return True
