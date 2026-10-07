"""In-memory stand-ins for the Anthropic client used by the agent tests (no network)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeUsage:
    input_tokens: int = 1200
    output_tokens: int = 300
    cache_read_input_tokens: int = 1000
    cache_creation_input_tokens: int = 0


@dataclass
class FakeStopDetails:
    category: str | None = "general_harms"


@dataclass
class FakeResponse:
    """Mimics the attributes `agent.client` reads from `ParsedMessage`."""

    parsed_output: Any = None
    stop_reason: str | None = "end_turn"
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_details: FakeStopDetails | None = None
    model: str = "fake"


class _Messages:
    def __init__(self, owner: FakeClient) -> None:
        self._owner = owner

    def parse(self, **kwargs: Any) -> FakeResponse:
        return self._owner._handle(kwargs)


class _AsyncMessages:
    def __init__(self, owner: FakeAsyncClient) -> None:
        self._owner = owner

    async def parse(self, **kwargs: Any) -> FakeResponse:
        self._owner.active += 1
        self._owner.max_active = max(self._owner.max_active, self._owner.active)
        try:
            await asyncio.sleep(self._owner.delay_s)
            return self._owner._handle(kwargs)
        finally:
            self._owner.active -= 1


class FakeClient:
    """`responder(kwargs) -> FakeResponse` (or raises). Records every call's kwargs in `calls`."""

    def __init__(self, responder: Any) -> None:
        self._responder = responder
        self.calls: list[dict[str, Any]] = []
        self.messages = _Messages(self)

    def _handle(self, kwargs: dict[str, Any]) -> FakeResponse:
        self.calls.append(kwargs)
        out = self._responder(kwargs)
        if isinstance(out, Exception):
            raise out
        return out


class FakeAsyncClient(FakeClient):
    def __init__(self, responder: Any, delay_s: float = 0.01) -> None:
        super().__init__(responder)
        self.delay_s = delay_s
        self.active = 0
        self.max_active = 0
        self.messages = _AsyncMessages(self)  # type: ignore[assignment]


def parsed(output_format: type, payload: dict[str, Any], **kw: Any) -> FakeResponse:
    """Build a response whose parsed_output is a validated instance, as the real SDK would."""
    return FakeResponse(parsed_output=output_format.model_validate(payload), **kw)
