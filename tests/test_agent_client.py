"""agent.client: model routing, schema guard, request shape, structured call result handling."""
from __future__ import annotations

import anthropic
import pytest
from pydantic import BaseModel

from swing_engine.agent import client as agent_client
from swing_engine.agent.client import (
    DEFAULT_MODELS,
    NumericFieldError,
    assert_no_numeric_fields,
    build_request,
    effort_for,
    load_prompt,
    model_for,
    structured_call,
    supports_effort,
)
from swing_engine.core.config import Settings
from tests.agent_fakes import FakeClient, FakeResponse, FakeStopDetails, parsed


class TextOnly(BaseModel):
    verdict: str
    tags: list[str] = []


class WithNumber(BaseModel):
    verdict: str
    qty: int


class Nested(BaseModel):
    inner: WithNumber


class OptionalFloat(BaseModel):
    price: float | None = None


def test_default_models_match_task_spec() -> None:
    assert DEFAULT_MODELS == {
        "review": "claude-sonnet-5-5",
        "lab": "claude-opus-5-5",
        "summary": "claude-haiku-4-5",
    }


def test_model_for_reads_settings_overrides() -> None:
    s = Settings.model_validate({"agent": {"review_model": "claude-opus-5-5", "lab_model": "claude-sonnet-5-5"}})
    assert model_for("review", s) == "claude-opus-5-5"
    assert model_for("lab", s) == "claude-sonnet-5-5"
    assert model_for("summary", s) == "claude-haiku-4-5"  # no settings field yet -> default
    assert model_for("review", None) == "claude-sonnet-5-5"


def test_effort_rules() -> None:
    assert supports_effort("claude-sonnet-5-5")
    assert not supports_effort("claude-haiku-4-5")
    assert effort_for("review", "claude-sonnet-5-5") == "medium"
    assert effort_for("lab", "claude-opus-5-5") == "high"
    assert effort_for("summary", "claude-haiku-4-5") is None
    assert effort_for("review", "claude-haiku-4-5") is None


def test_schema_guard_accepts_text_only_and_rejects_numbers() -> None:
    assert_no_numeric_fields(TextOnly.model_json_schema())
    with pytest.raises(NumericFieldError, match="qty"):
        assert_no_numeric_fields(WithNumber.model_json_schema())
    with pytest.raises(NumericFieldError):
        assert_no_numeric_fields(Nested.model_json_schema())  # follows $ref into $defs
    with pytest.raises(NumericFieldError):
        assert_no_numeric_fields(OptionalFloat.model_json_schema())  # anyOf[number, null]


def test_build_request_shape_and_guard() -> None:
    req = build_request(
        model="claude-sonnet-5-5",
        system_text="SYSTEM",
        user_text="USER",
        output_format=TextOnly,
        max_tokens=100,
        effort="medium",
        extra_system="EXTRA",
    )
    assert req["system"][0] == {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    assert req["system"][1] == {"type": "text", "text": "EXTRA"}
    assert req["messages"] == [{"role": "user", "content": "USER"}]
    assert req["output_config"] == {"effort": "medium"}
    assert "output_format" not in req  # structured_call adds it
    assert "thinking" not in req  # adaptive by default on current models
    haiku = build_request(model="claude-haiku-4-5", system_text="S", user_text="U", output_format=TextOnly, max_tokens=5)
    assert "output_config" not in haiku
    with pytest.raises(NumericFieldError):
        build_request(model="claude-sonnet-5-5", system_text="S", user_text="U", output_format=WithNumber, max_tokens=5)


def test_structured_call_ok_and_passes_output_format() -> None:
    fake = FakeClient(lambda kw: parsed(TextOnly, {"verdict": "fine", "tags": ["a"]}))
    res = structured_call(fake, TextOnly, model="m", max_tokens=10, messages=[], system="s")
    assert res.ok and res.parsed.verdict == "fine"
    assert fake.calls[0]["output_format"] is TextOnly
    assert res.usage["cache_read_input_tokens"] == 1000


@pytest.mark.parametrize(
    "response, expected",
    [
        (FakeResponse(parsed_output=None, stop_reason="refusal", stop_details=FakeStopDetails()), "refusal:general_harms"),
        (FakeResponse(parsed_output=None, stop_reason="max_tokens"), "max_tokens"),
        (FakeResponse(parsed_output=None, stop_reason="end_turn"), "empty_output"),
        (FakeResponse(parsed_output={"verdict": 3}, stop_reason="end_turn"), "invalid_output:ValidationError"),
    ],
)
def test_structured_call_failure_modes(response: FakeResponse, expected: str) -> None:
    fake = FakeClient(lambda kw: response)
    res = structured_call(fake, TextOnly, model="m", max_tokens=10, messages=[], system="s")
    assert not res.ok
    assert res.error == expected


def test_structured_call_api_error_is_captured() -> None:
    fake = FakeClient(lambda kw: anthropic.AnthropicError("boom"))
    res = structured_call(fake, TextOnly, model="m", max_tokens=10, messages=[], system="s")
    assert not res.ok and res.error is not None and res.error.startswith("AnthropicError")


def test_prompts_exist_and_are_cacheable_length() -> None:
    for name in ("review_system", "journal_system", "lab_system"):
        text = load_prompt(name)
        assert text and text == load_prompt(name)  # byte-stable across calls
    # Sonnet 5.5's minimum cacheable prefix is 512 tokens; the review prompt must be comfortably above it.
    assert len(load_prompt("review_system")) > 3000
    assert (agent_client.PROMPTS_DIR / "review_system.md").exists()
