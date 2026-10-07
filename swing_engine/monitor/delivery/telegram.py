"""Telegram Bot API deliverer: 1 msg/s token bucket, honors `retry_after` on 429 (capped at
`DELIVERY_RETRY_AFTER_MAX_S`, after which the send fails so the next channel is not held up), HTML-escaped text.

P2/P3 alerts that carry an ``event_id`` get an inline keyboard (Useful / Noise / Traded) whose callback data is
``<rating>:<event_id>`` (``monitor.rate``). The same bot client exposes ``get_updates`` (long poll) and
``answer_callback`` for ``service.TelegramUpdatesFeed``, which records the ratings.
"""
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
    DELIVERY_RETRY_AFTER_MAX_S,
    HTTP_TIMEOUT_S,
    HTTP_TOO_MANY,
    TELEGRAM_API,
    TELEGRAM_MAX_RETRIES,
    TELEGRAM_RATE_PER_S,
    TELEGRAM_TEXT_MAX,
)
from ..rate import AlertRating, callback_data
from ._ratelimit import TokenBucket

log = structlog.get_logger(__name__)

#: priorities whose alerts carry the rating keyboard (P1 only ever arrives as a digest)
RATED_PRIORITIES: frozenset[str] = frozenset({Priority.P2, Priority.P3})
RATING_BUTTON_LABELS: dict[AlertRating, str] = {
    AlertRating.USEFUL: "Useful",
    AlertRating.NOISE: "Noise",
    AlertRating.TRADED: "Traded",
}
#: getUpdates only needs button presses; plain messages to the bot are not commands
ALLOWED_UPDATES: tuple[str, ...] = ("callback_query",)
#: extra HTTP read time on top of the getUpdates long-poll timeout
LONG_POLL_HTTP_MARGIN_S = 10.0
CALLBACK_ANSWER_MAX = 200  # Telegram allows 0-200 characters in answerCallbackQuery.text
RETRY_AFTER_DEFAULT_S = 1.0


class TelegramAPIError(RuntimeError):
    """A Bot API call failed. ``retry_after`` is set on 429 so the caller can back off as instructed."""

    def __init__(self, method: str, status: int | None, description: str = "", retry_after: float | None = None):
        super().__init__(f"telegram {method} failed: status={status} {description}".strip())
        self.method = method
        self.status = status
        self.description = description
        self.retry_after = retry_after


def rating_keyboard(event_id: str) -> dict[str, Any] | None:
    """Inline keyboard with one button per rating, or None when the event id does not fit callback data."""
    buttons = []
    for rating, label in RATING_BUTTON_LABELS.items():
        data = callback_data(rating, event_id)
        if data is None:
            return None
        buttons.append({"text": label, "callback_data": data})
    return {"inline_keyboard": [buttons]}


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
        rating_buttons: bool = True,
    ):
        self.bot_token = bot_token
        self.rating_buttons = rating_buttons
        self.chat_id = chat_id
        self.base_url = base_url.rstrip("/")
        self._client = client
        self._owns_client = client is None
        self._sleep = sleeper
        self._bucket = TokenBucket(TELEGRAM_RATE_PER_S, capacity=1, sleeper=sleeper)

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

    def _url(self, method: str = "sendMessage") -> str:
        return f"{self.base_url}/bot{self.bot_token}/{method}"

    def _payload(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        text = f"<b>{html.escape(title)}</b>\n{html.escape(body)}"[:TELEGRAM_TEXT_MAX]
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": priority not in (Priority.P2, Priority.P3),
        }
        event_id = str((meta or {}).get("event_id") or "")
        if self.rating_buttons and priority in RATED_PRIORITIES and event_id:
            keyboard = rating_keyboard(event_id)
            if keyboard is not None:
                payload["reply_markup"] = keyboard
            else:
                log.info("telegram.rating_buttons_skipped", reason="event_id_too_long", event_id=event_id[:80])
        return payload

    async def send(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> bool:
        payload = self._payload(title, body, priority, meta)
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
                if retry_after > DELIVERY_RETRY_AFTER_MAX_S:
                    # a long ban must not stall the pipeline: give up on this channel, the next one runs
                    log.warning("telegram.rate_limited_giving_up", retry_after=retry_after, attempt=attempt)
                    return False
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

    # ---- updates (rating callbacks) ----------------------------------------------------------------------------
    async def get_updates(self, offset: int | None, timeout_s: float) -> list[dict[str, Any]]:
        """One ``getUpdates`` long poll. Raises :class:`TelegramAPIError` (with ``retry_after`` on 429) or
        ``httpx.HTTPError``; the caller owns backoff and offset tracking."""
        params: dict[str, Any] = {"timeout": int(timeout_s), "allowed_updates": list(ALLOWED_UPDATES)}
        if offset is not None:
            params["offset"] = offset
        resp = await self.client.post(
            self._url("getUpdates"), json=params, timeout=timeout_s + LONG_POLL_HTTP_MARGIN_S
        )
        data = self._result("getUpdates", resp)
        result = data.get("result")
        return [u for u in result if isinstance(u, dict)] if isinstance(result, list) else []

    async def answer_callback(self, callback_query_id: str, text: str = "") -> bool:
        """Acknowledge a button press (stops the client spinner); False on any failure."""
        payload = {"callback_query_id": callback_query_id, "text": text[:CALLBACK_ANSWER_MAX]}
        try:
            resp = await self.client.post(self._url("answerCallbackQuery"), json=payload)
            self._result("answerCallbackQuery", resp)
        except (httpx.HTTPError, TelegramAPIError) as e:
            log.warning("telegram.answer_callback_failed", error=f"{type(e).__name__}: {e}"[:200])
            return False
        return True

    @staticmethod
    def _result(method: str, resp: httpx.Response) -> dict[str, Any]:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if resp.status_code == HTTP_TOO_MANY:
            retry_after = RETRY_AFTER_DEFAULT_S
            params = data.get("parameters")
            if isinstance(params, dict):
                try:
                    retry_after = float(params.get("retry_after", retry_after))
                except (TypeError, ValueError):
                    pass
            raise TelegramAPIError(method, resp.status_code, str(data.get("description", "")), retry_after)
        if not resp.is_success or not data.get("ok", False):
            raise TelegramAPIError(method, resp.status_code, str(data.get("description", ""))[:200])
        return data
