from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from swing_engine.monitor.classify import (
    CLASSIFICATION_SCHEMA,
    HaikuClassifier,
    build_user_content,
    estimate_tokens,
    load_system_prompt,
    pad_prompt,
    parse_classification,
)
from swing_engine.monitor.constants import SYSTEM_PROMPT_MIN_TOKENS
from tests.monitor_helpers import base_ctx, fixture_text, make_event


def _response(text: str, cache_read: int = 0, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(cache_read_input_tokens=cache_read),
        stop_reason=stop_reason,
    )


class FakeMessages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls: list[dict] = []
        self.active = 0
        self.max_active = 0

    async def create(self, **params):
        self.calls.append(params)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome):
        self.messages = FakeMessages(outcome)


def _rate_limit_error():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(429, request=req, headers={"retry-after": "7"}, json={"error": {"message": "slow down"}})
    return anthropic.RateLimitError("rate limited", response=resp, body=None)


def test_system_prompt_is_padded_past_cache_minimum():
    p = load_system_prompt()
    assert estimate_tokens(p) >= SYSTEM_PROMPT_MIN_TOKENS
    assert p.startswith("You are the stage-2 classifier")
    assert pad_prompt("short", 10) == pad_prompt("short", 10)  # deterministic
    assert estimate_tokens(pad_prompt("x", 50)) >= 50


def test_request_params_shape():
    c = HaikuClassifier(client=FakeClient(_response("{}")))
    e = make_event(symbols=["ACME"], title="t")
    params = c.request_params(e, base_ctx())
    assert params["model"] == "claude-haiku-4-5"
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert params["output_config"]["format"] == {"type": "json_schema", "schema": CLASSIFICATION_SCHEMA}
    assert "<event>" in params["messages"][0]["content"]
    content = build_user_content(e, base_ctx(held={"ACME"}))
    payload = json.loads(content.removeprefix("<event>\n").removesuffix("\n</event>"))
    assert payload["held_symbols"] == ["ACME"] and payload["symbols"] == ["ACME"]


async def test_classify_happy_path_and_cache_counter():
    text = fixture_text("haiku_classification.json")
    c = HaikuClassifier(client=FakeClient(_response(text, cache_read=4200)))
    e = make_event(symbols=["ACME"], title="Acme beats")
    cls = await c.classify(e, base_ctx())
    assert cls is not None and cls.event_type == "earnings" and cls.tickers == ["ACME"] and cls.materiality == 4
    assert c.calls == 1 and c.failures == 0 and c.cache_reads == 4200


async def test_tickers_must_be_subset():
    bad = json.dumps({"relevance": "high", "event_type": "earnings", "materiality": 4, "sentiment": "positive",
                      "tickers": ["ACME", "NVDA"], "rationale": "x", "suggested_action": "review"})
    c = HaikuClassifier(client=FakeClient(_response(bad)))
    assert await c.classify(make_event(symbols=["ACME"]), base_ctx()) is None
    assert c.failures == 1
    assert parse_classification(bad, ["ACME", "NVDA"]) is not None


def test_parse_rejects_bad_json_and_schema():
    assert parse_classification("not json", ["A"]) is None
    assert parse_classification(json.dumps({"relevance": "high"}), ["A"]) is None
    assert parse_classification(json.dumps({"relevance": "high", "event_type": "x", "materiality": 9, "sentiment": "positive",
                                            "tickers": [], "rationale": "r", "suggested_action": "watch"}), []) is None


@pytest.mark.parametrize("exc", [_rate_limit_error(), anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")), TimeoutError()])
async def test_fallback_on_api_errors(exc):
    c = HaikuClassifier(client=FakeClient(exc))
    assert await c.classify(make_event(symbols=["ACME"]), base_ctx()) is None
    assert c.failures == 1


async def test_refusal_falls_back():
    c = HaikuClassifier(client=FakeClient(_response("", stop_reason="refusal")))
    assert await c.classify(make_event(symbols=["ACME"]), base_ctx()) is None


async def test_semaphore_bounds_concurrency():
    text = fixture_text("haiku_classification.json")
    client = FakeClient(_response(text))
    c = HaikuClassifier(client=client, max_concurrency=2)
    events = [make_event(f"e{i}", symbols=["ACME"]) for i in range(6)]
    out = await asyncio.gather(*(c.classify(e, base_ctx()) for e in events))
    assert all(o is not None for o in out)
    assert client.messages.max_active <= 2
