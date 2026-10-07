"""ntfy.sh deliverer (self-hostable). Priority maps to ntfy 1-5."""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from swing_engine.core.interfaces import Deliverer
from swing_engine.core.registry import register

from ..constants import HTTP_TIMEOUT_S, NTFY_BASE, NTFY_PRIORITY

log = structlog.get_logger(__name__)


@register("deliverer", "ntfy")
class NtfyDeliverer(Deliverer):
    name = "ntfy"

    def __init__(self, topic: str, base_url: str = NTFY_BASE, token: str | None = None, client: httpx.AsyncClient | None = None):
        self.topic = topic
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
        return self._client

    def _headers(self, title: str, priority: str, meta: dict[str, Any] | None) -> dict[str, str]:
        headers = {
            "Title": title.encode("ascii", "ignore").decode()[:200],
            "Priority": NTFY_PRIORITY.get(priority, "3"),
            "Tags": f"{priority.lower()},swing",
        }
        if meta and meta.get("url"):
            headers["Click"] = str(meta["url"])
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def send(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> bool:
        try:
            resp = await self.client.post(
                f"{self.base_url}/{self.topic}", content=body.encode("utf-8"), headers=self._headers(title, priority, meta)
            )
        except httpx.HTTPError as e:
            log.warning("ntfy.http_error", error=type(e).__name__)
            return False
        if not resp.is_success:
            log.warning("ntfy.failed", status=resp.status_code)
        return resp.is_success
