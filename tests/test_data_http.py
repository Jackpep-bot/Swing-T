from __future__ import annotations

import httpx
import pytest
import respx

from swing_engine.data._http import Http, RawCache, TokenBucket
from tests.helpers_data import FakeClock


def test_token_bucket_bursts_then_paces() -> None:
    clock = FakeClock()
    bucket = TokenBucket(5, clock=clock, sleep=clock.sleep)
    assert [bucket.acquire() for _ in range(5)] == [0.0] * 5
    waited = bucket.acquire()  # sixth call within the minute must wait for one token (12 s at 5/min)
    assert waited == pytest.approx(12.0)
    assert clock.sleeps == [pytest.approx(12.0)]
    clock.now += 60
    assert bucket.acquire() == 0.0
    with pytest.raises(ValueError):
        TokenBucket(0)


def test_raw_cache_round_trip_and_key_stability(tmp_path) -> None:
    cache = RawCache(tmp_path / "raw")
    k1 = RawCache.key("https://x/y", {"b": 2, "a": 1})
    k2 = RawCache.key("https://x/y", {"a": 1, "b": 2})
    assert k1 == k2 and k1 != RawCache.key("https://x/y", {"a": 1, "b": 2}, salt="other")
    assert cache.get(k1) is None
    assert cache.put(k1, '{"ok": true}').exists()
    assert cache.get(k1) == '{"ok": true}'
    assert not RawCache(None).enabled and RawCache(None).put("k", "v") is None


@respx.mock
def test_http_retries_on_429_then_succeeds_and_caches(tmp_path) -> None:
    clock = FakeClock()
    route = respx.get("https://api.example.com/thing").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(503),
            httpx.Response(200, json={"v": 1}),
        ]
    )
    http = Http(rate_per_min=600, cache_dir=tmp_path, clock=clock, sleep=clock.sleep)
    assert http.get_json("https://api.example.com/thing", cache_key="k") == {"v": 1}
    assert route.call_count == 3
    assert clock.sleeps[0] == pytest.approx(3.0)  # Retry-After honoured
    assert clock.sleeps[1] == pytest.approx(2.0)  # exponential backoff for the second attempt
    assert http.get_json("https://api.example.com/thing", cache_key="k") == {"v": 1}
    assert route.call_count == 3  # served from the raw cache


@respx.mock
def test_http_gives_up_after_retries() -> None:
    clock = FakeClock()
    respx.get("https://api.example.com/down").mock(return_value=httpx.Response(500))
    http = Http(retries=2, clock=clock, sleep=clock.sleep)
    with pytest.raises(httpx.HTTPStatusError):
        http.get_text("https://api.example.com/down")
