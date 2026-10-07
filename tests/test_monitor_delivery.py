from __future__ import annotations

import httpx
import pytest
import respx

from swing_engine.core import registry
from swing_engine.monitor.delivery._ratelimit import TokenBucket
from swing_engine.monitor.delivery.console import ConsoleDeliverer
from swing_engine.monitor.delivery.ntfy import NtfyDeliverer
from swing_engine.monitor.delivery.pushover import PushoverDeliverer
from swing_engine.monitor.delivery.telegram import TelegramDeliverer


class FakeSleep:
    def __init__(self):
        self.calls: list[float] = []

    async def __call__(self, s: float) -> None:
        self.calls.append(s)


def test_registry_has_all_deliverers():
    assert {"console", "telegram", "pushover", "ntfy"} <= set(registry.names("deliverer"))


async def test_console():
    out: list[str] = []
    d = ConsoleDeliverer(printer=out.append)
    assert await d.send("T", "B", "P2") is True
    assert out and out[0].startswith("[P2] T")


@respx.mock
async def test_telegram_sends_html_and_notification_flag():
    route = respx.post("https://api.telegram.org/bot123:abc/sendMessage").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("123:abc", "42", client=client, sleeper=FakeSleep())
        assert await d.send("Hi <b>", "body & more", "P2") is True
        assert await d.send("Digest", "x", "P1") is True
    assert route.call_count == 2
    import json

    body = json.loads(route.calls[0].request.read())
    assert body["chat_id"] == "42" and body["parse_mode"] == "HTML"
    assert body["text"] == "<b>Hi &lt;b&gt;</b>\nbody &amp; more" and body["disable_notification"] is False
    assert json.loads(route.calls[1].request.read())["disable_notification"] is True


@respx.mock
async def test_telegram_honors_retry_after():
    sleeper = FakeSleep()
    route = respx.post("https://api.telegram.org/bot1:a/sendMessage").mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 3}}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "7", client=client, sleeper=sleeper)
        assert await d.send("T", "B", "P3") is True
    assert route.call_count == 2 and 3.0 in sleeper.calls


@respx.mock
async def test_telegram_gives_up_on_4xx():
    respx.post("https://api.telegram.org/bot1:a/sendMessage").mock(return_value=httpx.Response(400, json={"ok": False}))
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "7", client=client, sleeper=FakeSleep())
        assert await d.send("T", "B", "P2") is False


async def test_token_bucket_enforces_one_per_second():
    sleeper = FakeSleep()
    now = [100.0]
    b = TokenBucket(1.0, capacity=1, clock=lambda: now[0], sleeper=sleeper)
    assert await b.acquire() == 0.0
    waited = await b.acquire()
    assert waited == pytest.approx(1.0)
    assert sleeper.calls == [pytest.approx(1.0)]


@respx.mock
async def test_pushover_emergency_for_p3():
    route = respx.post("https://api.pushover.net/1/messages.json").mock(return_value=httpx.Response(200, json={"status": 1}))
    async with httpx.AsyncClient() as client:
        d = PushoverDeliverer("ukey", "atoken", client=client)
        assert await d.send("Halt", "PUMP halted", "P3", {"url": "https://x"}) is True
        assert await d.send("Info", "digest", "P1") is True
    body = route.calls[0].request.read().decode()
    assert "priority=2" in body and "retry=30" in body and "expire=3600" in body and "url=https" in body
    body2 = route.calls[1].request.read().decode()
    assert "priority=-1" in body2 and "retry=" not in body2


@respx.mock
async def test_pushover_failure():
    respx.post("https://api.pushover.net/1/messages.json").mock(return_value=httpx.Response(400, json={"status": 0, "errors": ["bad token"]}))
    async with httpx.AsyncClient() as client:
        assert await PushoverDeliverer("u", "a", client=client).send("T", "B", "P2") is False


@respx.mock
async def test_ntfy_headers():
    route = respx.post("https://ntfy.sh/swing-alerts").mock(return_value=httpx.Response(200, json={"id": "x"}))
    async with httpx.AsyncClient() as client:
        d = NtfyDeliverer("swing-alerts", client=client, token="tok")
        assert await d.send("Title", "body", "P3", {"url": "https://sec.gov"}) is True
    req = route.calls[0].request
    assert req.headers["Priority"] == "5" and req.headers["Title"] == "Title"
    assert req.headers["Click"] == "https://sec.gov" and req.headers["Authorization"] == "Bearer tok"
    assert req.read() == b"body"
