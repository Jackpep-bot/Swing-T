"""Console deliverer: prints alerts (used by dry runs and as the always-on local channel)."""
from __future__ import annotations

from typing import Any

import structlog

from swing_engine.core.interfaces import Deliverer
from swing_engine.core.registry import register

log = structlog.get_logger(__name__)


@register("deliverer", "console")
class ConsoleDeliverer(Deliverer):
    name = "console"

    def __init__(self, printer=print):
        self._print = printer
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> bool:
        self.sent.append((title, body, priority))
        self._print(f"[{priority}] {title}\n{body}\n")
        log.info("alert.console", priority=priority, title=title[:80])
        return True
