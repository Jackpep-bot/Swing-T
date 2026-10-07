"""Stage-2 classifier: Claude Haiku 4.5 structured output -> core.models.Classification.

Safety properties: the system prompt is a frozen file (padded past the 4,096-token cache minimum and marked
`cache_control`), the response is constrained by a JSON schema, the returned tickers must be a subset of the event's
symbols, concurrency is bounded by a semaphore, and any API / parsing failure returns None so the pipeline falls
back to rules-only priorities. No number the model emits can reach an order: `Classification` has only enums,
an ordinal materiality and short text.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError

from swing_engine.core.models import Classification, Event

from .constants import (
    CLASSIFY_INPUT_MAX_CHARS,
    CLASSIFY_MAX_CONCURRENCY,
    CLASSIFY_MAX_TOKENS,
    CLASSIFY_TIMEOUT_S,
    RELEVANCE_LEVELS,
    SENTIMENTS,
    SUGGESTED_ACTIONS,
    SYSTEM_PROMPT_CHARS_PER_TOKEN,
    SYSTEM_PROMPT_MIN_TOKENS,
)

log = structlog.get_logger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "classify_system.md"
DEFAULT_MODEL = "claude-haiku-4-5"

EVENT_TYPES: tuple[str, ...] = (
    "earnings", "guidance", "merger_acquisition", "offering_dilution", "insider_buy", "insider_sell",
    "halt_or_suspension", "delisting_or_going_concern", "index_change", "fda_or_regulatory",
    "contract_or_partnership", "legal_or_investigation", "management_change", "analyst_rating", "product_launch",
    "macro", "social_promotion", "account_or_order", "other",
)

CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relevance": {"type": "string", "enum": list(RELEVANCE_LEVELS)},
        "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
        "materiality": {"type": "integer", "minimum": 1, "maximum": 5},
        "sentiment": {"type": "string", "enum": list(SENTIMENTS)},
        "tickers": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string", "maxLength": 300},
        "suggested_action": {"type": "string", "enum": list(SUGGESTED_ACTIONS)},
    },
    "required": ["relevance", "event_type", "materiality", "sentiment", "tickers", "rationale", "suggested_action"],
    "additionalProperties": False,
}

_PAD_HEADER = "\n\nReference appendix (stable; present only so the prefix clears the prompt-cache minimum).\n"
_PAD_LINES: tuple[str, ...] = (
    "8-K Item {n}: see the item table in the decision guide; severity is decided by code, not by you.",
    "Halt code note {n}: T1 pending news, T2 news out, T12 info requested, H10 SEC suspension, LUDP volatility.",
    "Offering note {n}: S-1, S-3, F-1, F-3, 424B1-424B7 and 8-K item 3.02 are offering_dilution events.",
    "Insider note {n}: Form 4 code P is an open-market purchase; code S is a sale; code A is a grant or award.",
    "Social note {n}: promotional phrasing from chat groups is social_promotion, negative for holders.",
    "Roundup note {n}: multi-ticker market-movers lists are low relevance and never split into ideas.",
)


def estimate_tokens(text: str) -> int:
    return int(len(text) / SYSTEM_PROMPT_CHARS_PER_TOKEN)


def pad_prompt(text: str, min_tokens: int = SYSTEM_PROMPT_MIN_TOKENS) -> str:
    """Deterministically append a reference appendix until the prompt clears the cacheable minimum."""
    if estimate_tokens(text) >= min_tokens:
        return text
    out = [text, _PAD_HEADER]
    n = 0
    total = len(text) + len(_PAD_HEADER)
    while total / SYSTEM_PROMPT_CHARS_PER_TOKEN < min_tokens:
        line = _PAD_LINES[n % len(_PAD_LINES)].format(n=n + 1) + "\n"
        out.append(line)
        total += len(line)
        n += 1
    return "".join(out)


def load_system_prompt(path: Path | str = PROMPT_PATH) -> str:
    return pad_prompt(Path(path).read_text(encoding="utf-8"))


def build_user_content(event: Event, ctx: dict[str, Any] | None = None) -> str:
    ctx = ctx or {}
    held = sorted({s.upper() for s in ctx.get("held", ())} & {s.upper() for s in event.symbols})
    payload = {
        "source": event.source,
        "kind": event.kind,
        "ts_source": event.ts_source.isoformat(),
        "symbols": [s.upper() for s in event.symbols],
        "held_symbols": held,
        "title": event.title[:CLASSIFY_INPUT_MAX_CHARS],
        "body": event.body[:CLASSIFY_INPUT_MAX_CHARS],
        "rule_hits": event.rule_hits,
        "stage1_priority": str(event.priority),
        "meta": {k: v for k, v in event.meta.items() if k in ("form_type", "items", "reason_code", "trigger", "event")},
    }
    return "<event>\n" + json.dumps(payload, ensure_ascii=False, default=str) + "\n</event>"


def parse_classification(text: str, allowed_symbols: list[str]) -> Classification | None:
    """Validate the model output. Tickers outside the event's symbols are a hard failure (returns None)."""
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        log.warning("classify.bad_json", snippet=str(text)[:120])
        return None
    try:
        cls = Classification.model_validate(data)
    except ValidationError as e:
        log.warning("classify.schema_mismatch", error=str(e)[:200])
        return None
    allowed = {s.upper() for s in allowed_symbols}
    tickers = [t.upper() for t in cls.tickers]
    if not set(tickers) <= allowed:
        log.warning("classify.ticker_not_subset", tickers=tickers, allowed=sorted(allowed))
        return None
    if cls.relevance not in RELEVANCE_LEVELS or cls.sentiment not in SENTIMENTS or cls.suggested_action not in SUGGESTED_ACTIONS:
        return None
    cls.tickers = tickers
    return cls


class HaikuClassifier:
    """Async classifier. `client` is injectable (tests pass a fake with `.messages.create`)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        system_prompt_path: Path | str = PROMPT_PATH,
        max_concurrency: int = CLASSIFY_MAX_CONCURRENCY,
        timeout_s: float = CLASSIFY_TIMEOUT_S,
        client: Any | None = None,
    ):
        self.model = model
        self.system_prompt = load_system_prompt(system_prompt_path)
        self.timeout_s = timeout_s
        self._sem = asyncio.Semaphore(max_concurrency)
        self._client = client
        self._api_key = api_key
        self.calls = 0
        self.failures = 0
        self.cache_reads = 0

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key, timeout=self.timeout_s, max_retries=1)
        return self._client

    @property
    def system_prompt_tokens_estimate(self) -> int:
        return estimate_tokens(self.system_prompt)

    def request_params(self, event: Event, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": CLASSIFY_MAX_TOKENS,
            "system": [{"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": build_user_content(event, ctx)}],
            "output_config": {"format": {"type": "json_schema", "schema": CLASSIFICATION_SCHEMA}},
        }

    async def classify(self, event: Event, ctx: dict[str, Any] | None = None) -> Classification | None:
        import anthropic

        params = self.request_params(event, ctx)
        async with self._sem:
            self.calls += 1
            try:
                response = await asyncio.wait_for(self.client.messages.create(**params), timeout=self.timeout_s)
            except anthropic.RateLimitError as e:
                self.failures += 1
                log.warning("classify.rate_limited", event_id=event.event_id, error=str(e)[:120])
                return None
            except anthropic.APIStatusError as e:
                self.failures += 1
                log.warning("classify.api_status", event_id=event.event_id, status=e.status_code)
                return None
            except (anthropic.APIConnectionError, TimeoutError) as e:
                self.failures += 1
                log.warning("classify.connection", event_id=event.event_id, error=type(e).__name__)
                return None
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.cache_reads += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        if getattr(response, "stop_reason", None) == "refusal":
            self.failures += 1
            return None
        text = ""
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text += getattr(block, "text", "")
        cls = parse_classification(text, event.symbols)
        if cls is None:
            self.failures += 1
        return cls
