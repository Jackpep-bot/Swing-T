from __future__ import annotations

import json

import httpx
import pytest
import respx

from swing_engine.monitor.delivery.telegram import TelegramAPIError, TelegramDeliverer, rating_keyboard

BASE = "https://api.telegram.org/bot1:a"


class FakeSleep:
    def __init__(self):
        self.calls: list[float] = []

    async def __call__(self, s: float) -> None:
        self.calls.append(s)


def test_rating_keyboard_layout_and_long_ids():
    kb = rating_keyboard("edgar:0001234567-26-000001")
    assert kb is not None
    row = kb["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["Useful", "Noise", "Traded"]
    assert [b["callback_data"] for b in row] == [
        "useful:edgar:0001234567-26-000001", "noise:edgar:0001234567-26-000001", "traded:edgar:0001234567-26-000001",
    ]
    assert rating_keyboard("x" * 60) is None


@respx.mock
async def test_p2_and_p3_carry_rating_buttons_but_p1_and_digest_do_not():
    route = respx.post(f"{BASE}/sendMessage").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "42", client=client, sleeper=FakeSleep())
        assert await d.send("t", "b", "P2", {"event_id": "e1", "url": None})
        assert await d.send("t", "b", "P3", {"event_id": "e2"})
        assert await d.send("t", "b", "P1", {"event_id": "e3"})
        assert await d.send("Digest", "b", "P1", {"digest": True})
        assert await d.send("t", "b", "P2", {"event_id": "y" * 70})  # too long for callback data
        assert await d.send("t", "b", "P2")
    bodies = [json.loads(c.request.read()) for c in route.calls]
    assert bodies[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "useful:e1"
    assert bodies[1]["reply_markup"]["inline_keyboard"][0][2]["callback_data"] == "traded:e2"
    assert all("reply_markup" not in b for b in bodies[2:])


@respx.mock
async def test_rating_buttons_can_be_switched_off():
    route = respx.post(f"{BASE}/sendMessage").mock(return_value=httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "42", client=client, sleeper=FakeSleep(), rating_buttons=False)
        assert await d.send("t", "b", "P3", {"event_id": "e1"})
    assert "reply_markup" not in json.loads(route.calls[0].request.read())


@respx.mock
async def test_get_updates_sends_offset_timeout_and_filter():
    route = respx.post(f"{BASE}/getUpdates").mock(
        return_value=httpx.Response(200, json={"ok": True, "result": [{"update_id": 7}, "junk"]})
    )
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "42", client=client)
        assert await d.get_updates(5, 30) == [{"update_id": 7}]
        assert await d.get_updates(None, 30) == [{"update_id": 7}]
    first = json.loads(route.calls[0].request.read())
    assert first == {"timeout": 30, "allowed_updates": ["callback_query"], "offset": 5}
    assert "offset" not in json.loads(route.calls[1].request.read())


@respx.mock
async def test_get_updates_errors_carry_retry_after():
    respx.post(f"{BASE}/getUpdates").mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "description": "Too Many", "parameters": {"retry_after": 7}}),
            httpx.Response(409, json={"ok": False, "description": "Conflict: webhook is active"}),
            httpx.Response(200, json={"ok": False, "description": "nope"}),
        ]
    )
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "42", client=client)
        with pytest.raises(TelegramAPIError) as e429:
            await d.get_updates(0, 30)
        assert e429.value.retry_after == 7.0 and e429.value.status == 429
        with pytest.raises(TelegramAPIError) as e409:
            await d.get_updates(0, 30)
        assert e409.value.status == 409 and e409.value.retry_after is None and "webhook" in e409.value.description
        with pytest.raises(TelegramAPIError):
            await d.get_updates(0, 30)


@respx.mock
async def test_answer_callback_ok_and_failure():
    route = respx.post(f"{BASE}/answerCallbackQuery").mock(
        side_effect=[httpx.Response(200, json={"ok": True}), httpx.Response(400, json={"ok": False}),
                     httpx.ConnectError("down")]
    )
    async with httpx.AsyncClient() as client:
        d = TelegramDeliverer("1:a", "42", client=client)
        assert await d.answer_callback("cb1", "Rated useful") is True
        assert await d.answer_callback("cb2", "x" * 500) is False
        assert await d.answer_callback("cb3") is False
    assert json.loads(route.calls[0].request.read()) == {"callback_query_id": "cb1", "text": "Rated useful"}
    assert len(json.loads(route.calls[1].request.read())["text"]) == 200
