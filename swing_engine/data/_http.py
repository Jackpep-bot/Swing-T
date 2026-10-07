"""HTTP plumbing shared by every network provider: a token bucket (vendor rate limits), a raw-response
cache under `data/raw/<provider>/`, and a GET with retry/backoff on 429 and 5xx responses.

Providers construct one `Http` and route every request through it, so tests can inject an `httpx.Client`
(or let `respx` intercept the default one) together with a fake clock/sleep to keep the suite instant.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import structlog

from swing_engine.core.config import ROOT

from ._common import RAW_CACHE_DIR

log = structlog.get_logger(__name__)

DEFAULT_TIMEOUT_S = 30.0
MAX_RETRIES = 4
BACKOFF_BASE_S = 1.0
BACKOFF_MAX_S = 60.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
SECONDS_PER_MINUTE = 60.0
CACHE_SUFFIX = ".json"
#: query parameters vendors use for credentials (EODHD `api_token`, AlphaVantage `apikey`, ...); their values
#: never appear in exception text, logs or ingest results.
SECRET_QUERY_PARAMS = frozenset({"api_token", "apikey", "api_key", "apiKey", "token", "key", "secret", "access_token"})
REDACTED = "***"
_SECRET_IN_TEXT = re.compile(r"(?i)\b(api_token|apikey|api_key|access_token|token|key|secret)=([^&\s'\"]+)")


def redact_url(url: str) -> str:
    """``url`` with the values of :data:`SECRET_QUERY_PARAMS` replaced by ``***``."""
    parts = urlsplit(str(url))
    if not parts.query:
        return str(url)
    query = [
        (k, REDACTED if k.lower() in {p.lower() for p in SECRET_QUERY_PARAMS} else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(parts._replace(query=urlencode(query, safe=REDACTED)))


def redact_secrets(text: str) -> str:
    """Blank credential-looking ``name=value`` pairs in free text (exception messages, log lines)."""
    return _SECRET_IN_TEXT.sub(lambda m: f"{m.group(1)}={REDACTED}", str(text))


def status_error(response: httpx.Response) -> httpx.HTTPStatusError:
    """``HTTPStatusError`` whose message carries the status and a redacted URL, never the credentials."""
    kind = "Client" if response.status_code < 500 else "Server"
    message = (
        f"{kind} error '{response.status_code} {response.reason_phrase}' for url '{redact_url(str(response.url))}'"
    )
    return httpx.HTTPStatusError(message, request=response.request, response=response)


class TokenBucket:
    """Classic token bucket: `rate_per_min` tokens are added per minute up to `capacity`; `acquire`
    blocks (via the injected `sleep`) until a token is available and returns the seconds waited."""

    def __init__(
        self,
        rate_per_min: float,
        capacity: int | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if rate_per_min <= 0:
            raise ValueError("rate_per_min must be positive")
        self.rate_per_s = rate_per_min / SECONDS_PER_MINUTE
        self.capacity = float(capacity if capacity is not None else max(1, int(rate_per_min)))
        self._tokens = self.capacity
        self._clock = clock
        self._sleep = sleep
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate_per_s)
        self._last = now

    def acquire(self) -> float:
        self._refill()
        waited = 0.0
        if self._tokens < 1.0:
            waited = (1.0 - self._tokens) / self.rate_per_s
            self._sleep(waited)
            self._refill()
        self._tokens = max(self._tokens - 1.0, 0.0)
        return waited


class RawCache:
    """Raw response cache keyed by a digest of URL + params. Disabled when `root` is None."""

    def __init__(self, root: str | Path | None) -> None:
        self.root = Path(root) if root is not None else None

    @property
    def enabled(self) -> bool:
        return self.root is not None

    @staticmethod
    def key(url: str, params: Mapping[str, Any] | None = None, *, salt: str = "") -> str:
        payload = json.dumps({"url": url, "params": dict(sorted((params or {}).items())), "salt": salt}, default=str)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def path(self, key: str, suffix: str = CACHE_SUFFIX) -> Path | None:
        return None if self.root is None else self.root / f"{key}{suffix}"

    def get(self, key: str, suffix: str = CACHE_SUFFIX) -> str | None:
        p = self.path(key, suffix)
        if p is None or not p.exists():
            return None
        return p.read_text(encoding="utf-8")

    def put(self, key: str, text: str, suffix: str = CACHE_SUFFIX) -> Path | None:
        p = self.path(key, suffix)
        if p is None:
            return None
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


def default_cache_dir(provider: str) -> Path:
    return ROOT / RAW_CACHE_DIR / provider


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), BACKOFF_MAX_S)
        except ValueError:
            pass
    return min(BACKOFF_BASE_S * (2**attempt), BACKOFF_MAX_S)


class Http:
    """One HTTP session per provider: rate limit + raw cache + retries."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        rate_per_min: float | None = None,
        burst: int | None = None,
        cache_dir: str | Path | None = None,
        headers: Mapping[str, str] | None = None,
        retries: int = MAX_RETRIES,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client or httpx.Client(timeout=DEFAULT_TIMEOUT_S, follow_redirects=True)
        self.bucket = TokenBucket(rate_per_min, burst, clock=clock, sleep=sleep) if rate_per_min else None
        self.cache = RawCache(cache_dir)
        self.headers = dict(headers or {})
        self.retries = retries
        self._sleep = sleep

    def get_text(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cache_key: str | None = None,
        cache_suffix: str = CACHE_SUFFIX,
    ) -> str:
        if cache_key is not None:
            hit = self.cache.get(cache_key, cache_suffix)
            if hit is not None:
                log.debug("http_cache_hit", url=url, key=cache_key)
                return hit
        merged = {**self.headers, **(headers or {})}
        for attempt in range(self.retries + 1):
            if self.bucket is not None:
                waited = self.bucket.acquire()
                if waited:
                    log.debug("rate_limit_wait", url=url, seconds=round(waited, 2))
            response = self.client.get(url, params=params, headers=merged)
            if response.status_code in RETRY_STATUSES and attempt < self.retries:
                delay = _retry_delay(response, attempt)
                log.warning("http_retry", url=url, status=response.status_code, attempt=attempt, delay=delay)
                self._sleep(delay)
                continue
            if response.is_error:
                raise status_error(response)  # raise_for_status() would embed the query string (API key)
            text = response.text
            if cache_key is not None:
                self.cache.put(cache_key, text, cache_suffix)
            return text
        raise RuntimeError("unreachable: retry loop exhausted without a response")  # pragma: no cover

    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cache_key: str | None = None,
    ) -> Any:
        return json.loads(self.get_text(url, params=params, headers=headers, cache_key=cache_key))
