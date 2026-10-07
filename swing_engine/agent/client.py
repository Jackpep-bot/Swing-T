"""Anthropic client factory plus the one call helper every agent module uses.

Design rules (see CLAUDE.md rule 1): the language model only ever returns enums and short text. Every
schema handed to the model passes through `assert_no_numeric_fields` first, so a future schema that
sneaks in an `int`/`float` field fails loudly before a request is made. Numbers that appear in prompts
are context only; the code that builds orders never reads anything back from a model response except
the enum/text fields of the validated pydantic object.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import anthropic
import structlog
from pydantic import BaseModel

from swing_engine.core.config import Secrets, Settings

log = structlog.get_logger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

Role = Literal["review", "lab", "summary"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]

# Model ids (verified against the claude-api skill, Oct 2026). Overridable from settings.agent.
DEFAULT_MODELS: dict[str, str] = {
    "review": "claude-sonnet-5-5",
    "lab": "claude-opus-5-5",
    "summary": "claude-haiku-4-5",
}
# settings.agent attribute that overrides each role (AgentConfig only defines the first two today;
# `summary_model` / `<role>_effort` are read with getattr so adding them to core.config just works).
_MODEL_SETTING_ATTR: dict[str, str] = {
    "review": "review_model",
    "lab": "lab_model",
    "summary": "summary_model",
}
DEFAULT_EFFORT: dict[str, Effort | None] = {"review": "medium", "lab": "high", "summary": None}
# Models that reject `output_config.effort` (Haiku 4.5 has no effort parameter).
_NO_EFFORT_PREFIXES: tuple[str, ...] = ("claude-haiku",)

# Output ceilings. Adaptive thinking tokens count against max_tokens, so these are not tight.
REVIEW_MAX_TOKENS = 8_192
SUMMARY_MAX_TOKENS = 4_096
LAB_MAX_TOKENS = 16_000
LAB_TIMEOUT_S = 600.0
DEFAULT_MAX_CONCURRENCY = 4
NUMERIC_JSON_TYPES = frozenset({"integer", "number"})



class NumericFieldError(ValueError):
    """Raised when a model-facing schema contains a numeric field."""


def get_client(secrets: Secrets | None = None) -> anthropic.Anthropic:
    """Sync client. Uses `secrets.anthropic_api_key` when set, else the SDK's own credential resolution."""
    if secrets is not None and secrets.anthropic_api_key:
        return anthropic.Anthropic(api_key=secrets.anthropic_api_key)
    return anthropic.Anthropic()


def get_async_client(secrets: Secrets | None = None) -> anthropic.AsyncAnthropic:
    if secrets is not None and secrets.anthropic_api_key:
        return anthropic.AsyncAnthropic(api_key=secrets.anthropic_api_key)
    return anthropic.AsyncAnthropic()


def model_for(role: Role, settings: Settings | None = None) -> str:
    agent = settings.agent if settings is not None else None
    override = getattr(agent, _MODEL_SETTING_ATTR[role], None) if agent is not None else None
    return override or DEFAULT_MODELS[role]


def effort_for(role: Role, model: str, settings: Settings | None = None) -> Effort | None:
    if not supports_effort(model):
        return None
    agent = settings.agent if settings is not None else None
    override = getattr(agent, f"{role}_effort", None) if agent is not None else None
    return override or DEFAULT_EFFORT[role]


def supports_effort(model: str) -> bool:
    return not model.startswith(_NO_EFFORT_PREFIXES)


@lru_cache
def load_prompt(name: str) -> str:
    """Read `agent/prompts/<name>.md`. Cached: the text must be byte-stable for prompt caching to hit."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def cached_system(text: str, *extra: str) -> list[dict[str, Any]]:
    """System blocks: the stable prompt carries the cache breakpoint; `extra` blocks follow it uncached."""
    blocks: list[dict[str, Any]] = [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
    blocks.extend({"type": "text", "text": e} for e in extra if e)
    return blocks


def assert_no_numeric_fields(schema: Mapping[str, Any]) -> None:
    """Walk a JSON schema (pydantic `model_json_schema()` output) and raise if any integer/number appears.

    The hard rule is that no LLM-produced number can reach an order. Rather than deciding field by field
    which numbers are "safe", agent schemas contain none at all: scores are grade enums mapped to ints
    in code, and every price/size/stop/target lives on the deterministic objects.
    """
    defs = schema.get("$defs", {}) if isinstance(schema, Mapping) else {}
    offenders: list[str] = []
    _walk(schema, "$", defs, offenders, set())
    if offenders:
        raise NumericFieldError(f"numeric fields are not allowed in model-facing schemas: {offenders}")


def _walk(node: Any, path: str, defs: Mapping[str, Any], out: list[str], seen: set[str]) -> None:
    if isinstance(node, list):
        for i, item in enumerate(node):
            _walk(item, f"{path}[{i}]", defs, out, seen)
        return
    if not isinstance(node, Mapping):
        return
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        name = ref.removeprefix("#/$defs/")
        if name not in seen:
            seen.add(name)
            _walk(defs.get(name, {}), f"{path}->{name}", defs, out, seen)
    typ = node.get("type")
    types = typ if isinstance(typ, list) else [typ]
    if any(t in NUMERIC_JSON_TYPES for t in types):
        out.append(path)
    for key in ("properties", "$defs"):
        sub = node.get(key)
        if isinstance(sub, Mapping):
            for k, v in sub.items():
                _walk(v, f"{path}.{k}", defs, out, seen)
    for key in ("items", "additionalProperties", "anyOf", "oneOf", "allOf", "prefixItems"):
        if key in node:
            _walk(node[key], f"{path}.{key}", defs, out, seen)


@dataclass
class StructuredResult:
    """What a structured call returns. `parsed` is None when the model refused or was cut off."""

    parsed: Any
    stop_reason: str | None
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.parsed is not None and self.error is None


def build_request(
    *,
    model: str,
    system_text: str,
    user_text: str,
    output_format: type[BaseModel],
    max_tokens: int,
    effort: Effort | None = None,
    extra_system: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Keyword arguments for `client.messages.parse` (minus `output_format`, which `structured_call` adds).

    Pure, so tests can inspect exactly what is sent. Raises NumericFieldError if the schema has numbers.
    """
    assert_no_numeric_fields(output_format.model_json_schema())
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": cached_system(system_text, extra_system or ""),
        "messages": [{"role": "user", "content": user_text}],
    }
    if effort is not None and supports_effort(model):
        kwargs["output_config"] = {"effort": effort}
    if timeout is not None:
        kwargs["timeout"] = timeout
    return kwargs


def _usage_dict(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    out: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
        val = getattr(usage, key, None)
        if isinstance(val, int):
            out[key] = val
    return out


def _to_result(response: Any, model: str, output_format: type[BaseModel]) -> StructuredResult:
    stop = getattr(response, "stop_reason", None)
    parsed = getattr(response, "parsed_output", None)
    result = StructuredResult(parsed=None, stop_reason=stop, model=model, usage=_usage_dict(response))
    if stop == "refusal":
        details = getattr(response, "stop_details", None)
        result.error = f"refusal:{getattr(details, 'category', None)}"
        return result
    if stop == "max_tokens":
        result.error = "max_tokens"
        return result
    if parsed is None:
        result.error = "empty_output"
        return result
    if not isinstance(parsed, output_format):
        try:
            parsed = output_format.model_validate(parsed)
        except Exception as e:  # pydantic.ValidationError or anything else: treat as invalid
            result.error = f"invalid_output:{type(e).__name__}"
            return result
    result.parsed = parsed
    return result


def _error_result(e: Exception, model: str) -> StructuredResult:
    log.warning("agent.call_failed", model=model, error=type(e).__name__, detail=str(e)[:200])
    return StructuredResult(parsed=None, stop_reason=None, model=model, error=f"{type(e).__name__}:{e}"[:300])


def structured_call(client: Any, output_format: type[BaseModel], **request: Any) -> StructuredResult:
    """Sync structured-output call. Never raises on API/validation problems; inspect `.ok` / `.error`."""
    model = request["model"]
    try:
        response = client.messages.parse(**request, output_format=output_format)
    except (anthropic.AnthropicError, ValueError, json.JSONDecodeError) as e:
        return _error_result(e, model)
    result = _to_result(response, model, output_format)
    log.info("agent.call", model=model, stop_reason=result.stop_reason, ok=result.ok, **result.usage)
    return result


async def structured_call_async(
    client: Any, output_format: type[BaseModel], **request: Any
) -> StructuredResult:
    model = request["model"]
    try:
        response = await client.messages.parse(**request, output_format=output_format)
    except (anthropic.AnthropicError, ValueError, json.JSONDecodeError) as e:
        return _error_result(e, model)
    result = _to_result(response, model, output_format)
    log.info("agent.call", model=model, stop_reason=result.stop_reason, ok=result.ok, **result.usage)
    return result
