"""HTTP layer: validation, Host guard, CSRF guard, security headers, static files, no clear endpoint."""
from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from swing_engine.dashboard import __main__ as cli
from swing_engine.dashboard.data import ok
from swing_engine.dashboard.demo import DemoData
from swing_engine.dashboard.server import (
    MAX_BODY_BYTES,
    DashboardApp,
    collect_secrets,
    csp_for,
    host_allowed,
    make_server,
    origin_allowed,
    scrub,
)

H = {"Host": "127.0.0.1:8765", "X-Swing-Dashboard": "1"}  # what the page's fetch() sends
JSON_POST = {**H, "Content-Type": "application/json"}


@pytest.fixture()
def app() -> DashboardApp:
    return DashboardApp(DemoData(), secrets=[])


def status(app: DashboardApp, target: str, method: str = "GET", headers: dict | None = None, body: bytes = b"") -> int:
    return app.handle(method, target, headers or H, body).status


# ------------------------------------------------------------------------------------------- validation
@pytest.mark.parametrize("target", [
    "/api/regime?date=2026-1-01", "/api/regime?date=2026-02-30", "/api/signals?date=yesterday",
    "/api/journal?date=../../etc/passwd", "/api/signals?date=2026-10-05T00:00",
    "/api/chart/..%2F..%2Fetc", "/api/chart/AAPL1", "/api/chart/TOOLONGSYMBOL", "/api/chart/A%20B",
    "/api/chart/%00", "/api/chart/SPY?days=0", "/api/chart/SPY?days=-5", "/api/chart/SPY?days=abc",
    "/api/chart/SPY?days=999999", "/api/equity?period=2Y", "/api/orders?status=all", "/api/orders?limit=0",
    "/api/orders?limit=10000", "/api/shadow?by=symbol", "/api/alerts?hours=0", "/api/alerts?hours=1e9",
])
def test_bad_parameters_are_400(app: DashboardApp, target: str) -> None:
    resp = app.handle("GET", target, H)
    assert resp.status == 400, target
    body = resp.json()
    assert body["ok"] is False and body["unavailable"]


@pytest.mark.parametrize("target", ["/api/chart/brk.b", "/api/chart/BF-B", "/api/regime?date=2026-09-30",
                                    "/api/orders?status=closed&limit=500", "/api/equity?period=all"])
def test_good_parameters(app: DashboardApp, target: str) -> None:
    assert status(app, target) == 200


def test_unknown_routes_and_methods(app: DashboardApp) -> None:
    assert status(app, "/api/nope") == 404
    assert status(app, "/api/killswitch/trip") == 405  # GET on a POST route
    assert status(app, "/api/summary", "POST", JSON_POST, b"{}") == 405
    assert status(app, "/api/summary", "DELETE") == 405
    assert status(app, "/", "POST", JSON_POST, b"{}") == 405


@pytest.mark.parametrize("path", ["/api/killswitch/clear", "/api/killswitch/reset", "/api/killswitch",
                                  "/api/killswitch/untrip"])
def test_there_is_no_clear_endpoint(app: DashboardApp, path: str) -> None:
    for method in ("GET", "POST"):
        resp = app.handle(method, path, JSON_POST, b'{"confirm": "TRIP"}')
        assert resp.status == 404, (method, path)


def test_kill_switch_requires_exact_confirm(app: DashboardApp) -> None:
    for body in (b"{}", b'{"confirm": "trip"}', b'{"confirm": true}', b'{"confirm": "TRIP "}'):
        assert status(app, "/api/killswitch/trip", "POST", JSON_POST, body) == 400
    s = app.handle("GET", "/api/summary", H).json()["data"]
    assert s["kill_switch"]["tripped"] is False


# ------------------------------------------------------------------------------------------- host / csrf
@pytest.mark.parametrize("host,allowed", [
    ("127.0.0.1:8765", True), ("localhost:8765", True), ("localhost", True), ("[::1]:8765", True),
    ("LOCALHOST:1", True), ("evil.com", False), ("evil.com:8765", False), ("127.0.0.1.nip.io:8765", False),
    ("localhost.evil.com", False), ("", False), (None, False), ("0.0.0.0:8765", False), ("192.168.1.5:8765", False),
])
def test_host_guard(host: str | None, allowed: bool) -> None:
    assert host_allowed(host) is allowed


def test_non_local_host_is_refused_everywhere(app: DashboardApp) -> None:
    for target in ("/", "/api/summary", "/static/index.html"):
        resp = app.handle("GET", target, {"Host": "attacker.example:8765"})
        assert resp.status == 403
        assert resp.json()["ok"] is False
    assert app.handle("GET", "/api/summary", {}).status == 403
    resp = app.handle("POST", "/api/killswitch/trip", {"Host": "rebind.example", "Content-Type": "application/json"},
                      b'{"confirm": "TRIP"}')
    assert resp.status == 403


def test_post_guards(app: DashboardApp) -> None:
    body = b'{"confirm": "TRIP"}'
    assert status(app, "/api/killswitch/trip", "POST", {**H, "Content-Type": "text/plain"}, body) == 400
    assert status(app, "/api/killswitch/trip", "POST", {**H, "Content-Type": "application/x-www-form-urlencoded"},
                  b"confirm=TRIP") == 400
    assert status(app, "/api/killswitch/trip", "POST", {**JSON_POST, "Origin": "https://evil.example"}, body) == 403
    assert status(app, "/api/killswitch/trip", "POST", {**JSON_POST, "Sec-Fetch-Site": "cross-site"}, body) == 403
    assert status(app, "/api/killswitch/trip", "POST", JSON_POST, b"[1,2]") == 400
    assert status(app, "/api/killswitch/trip", "POST", JSON_POST, b"{not json") == 400
    assert status(app, "/api/killswitch/trip", "POST", JSON_POST, b"\xff\xfe") == 400
    big = json.dumps({"confirm": "TRIP", "pad": "x" * MAX_BODY_BYTES}).encode()
    assert status(app, "/api/killswitch/trip", "POST", JSON_POST, big) == 413
    same = {**JSON_POST, "Origin": "http://127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"}
    assert status(app, "/api/killswitch/trip", "POST", same, body) == 200


class CountingDemo(DemoData):
    """Records every provider read: a refused request must never reach one (no DuckDB open, no broker call)."""

    def __init__(self) -> None:
        super().__init__()
        self.reads: list[str] = []

    def chart(self, symbol: str, days: int = 180) -> Any:
        self.reads.append(f"chart:{symbol}")
        return super().chart(symbol, days)

    def summary(self) -> Any:
        self.reads.append("summary")
        return super().summary()

    def shadow(self, by: str = "strategy") -> Any:
        self.reads.append("shadow")
        return super().shadow(by)


@pytest.mark.parametrize("target", ["/api/chart/AAPL?days=5", "/api/summary", "/api/shadow", "/api/health",
                                    "/api/nope"])
def test_cross_site_gets_are_refused_before_any_read(target: str) -> None:
    provider = CountingDemo()
    app = DashboardApp(provider, secrets=[])
    host = {"Host": "127.0.0.1:8765"}
    refused = [
        {**host, "Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},  # fetch(..., {mode: "no-cors"})
        {**host, "Sec-Fetch-Site": "cross-site"},  # <img src>, top-level navigation from another site
        {**host, "Sec-Fetch-Site": "same-site"},  # another localhost port is same-site but not same-origin
        {**host, "Origin": "https://evil.example", "X-Swing-Dashboard": "1"},
        {**host, "Origin": "http://localhost:3000", "X-Swing-Dashboard": "1"},  # loopback, other origin
        {**host, "Origin": "null", "X-Swing-Dashboard": "1"},
        host,  # no fetch metadata (older Safari, scripts) and no custom header
        {**host, "X-Swing-Dashboard": "yes"},
    ]
    for headers in refused:
        resp = app.handle("GET", target, headers)
        assert resp.status == 403, (target, headers)
        assert resp.json()["ok"] is False
    assert provider.reads == []
    allowed = [
        {**host, "Sec-Fetch-Site": "same-origin", "Origin": "http://127.0.0.1:8765"},  # the page's own fetch()
        {**host, "Sec-Fetch-Site": "none"},  # typed into the address bar
        {**host, "X-Swing-Dashboard": "1"},  # a script that sends the header
        {"Host": "localhost", "Origin": "http://localhost:80", "X-Swing-Dashboard": "1"},
    ]
    for headers in allowed:
        assert app.handle("GET", target, headers).status == (404 if target == "/api/nope" else 200), headers


def test_post_needs_the_exact_origin() -> None:
    app = DashboardApp(DemoData(), secrets=[])
    body = b'{"confirm": "TRIP"}'
    post = {"Host": "127.0.0.1:8765", "Content-Type": "application/json", "X-Swing-Dashboard": "1"}
    for origin in ("http://localhost:3000", "http://127.0.0.1:9999", "https://127.0.0.1:8765", "http://localhost:8765"):
        assert app.handle("POST", "/api/killswitch/trip", {**post, "Origin": origin}, body).status == 403, origin
    assert app.handle("POST", "/api/killswitch/trip", {k: v for k, v in post.items() if k != "X-Swing-Dashboard"},
                      body).status == 403
    assert app.handle("GET", "/api/summary", post).json()["data"]["kill_switch"]["tripped"] is False
    ok_post = {**post, "Origin": "http://127.0.0.1:8765", "Sec-Fetch-Site": "same-origin"}
    assert app.handle("POST", "/api/killswitch/trip", ok_post, body).status == 200


@pytest.mark.parametrize("origin,host,allowed", [
    (None, "127.0.0.1:8765", True), ("http://127.0.0.1:8765", "127.0.0.1:8765", True),
    ("http://LOCALHOST:8765", "localhost:8765", True), ("http://[::1]:8765", "[::1]:8765", True),
    ("http://localhost", "localhost:80", True), ("http://localhost:3000", "127.0.0.1:8765", False),
    ("http://localhost:8765", "127.0.0.1:8765", False), ("https://127.0.0.1:8765", "127.0.0.1:8765", False),
    ("http://evil.example:8765", "127.0.0.1:8765", False), ("null", "127.0.0.1:8765", False),
    ("http://127.0.0.1:8765/path", "127.0.0.1:8765", False),
])
def test_origin_is_compared_with_the_host(origin: str | None, host: str, allowed: bool) -> None:
    assert origin_allowed(origin, host) is allowed


def test_rate_validation(app: DashboardApp) -> None:
    eid = app.handle("GET", "/api/alerts", H).json()["data"][0]["event_id"]
    assert status(app, f"/api/alerts/{eid}/rate", "POST", JSON_POST, b'{"rating": "great"}') == 400
    assert status(app, f"/api/alerts/{eid}/rate", "POST", JSON_POST, b'{"rating": 1}') == 400
    assert status(app, "/api/alerts/bad%20id!/rate", "POST", JSON_POST, b'{"rating": "useful"}') == 400
    assert status(app, f"/api/alerts/{'x' * 200}/rate", "POST", JSON_POST, b'{"rating": "useful"}') == 400
    assert status(app, f"/api/alerts/{eid}/rate", "POST", JSON_POST, b'{"rating": "Noise"}') == 200


# ------------------------------------------------------------------------------------------- headers
def _assert_security_headers(headers: dict[str, str]) -> None:
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "https://unpkg.com" in csp and "frame-ancestors 'none'" in csp
    assert "'unsafe-eval'" not in csp
    assert "Access-Control-Allow-Origin" not in headers


def test_security_headers_on_every_kind_of_response(app: DashboardApp) -> None:
    for method, target, hdrs in (("GET", "/api/summary", H), ("GET", "/api/nope", H), ("GET", "/", H),
                                 ("GET", "/static/nope.js", H), ("GET", "/api/chart/123", H),
                                 ("GET", "/api/summary", {"Host": "evil"})):
        resp = app.handle(method, target, hdrs)
        _assert_security_headers(resp.headers)
    api = app.handle("GET", "/api/summary", H)
    assert api.headers["Content-Type"].startswith("application/json")
    assert api.headers["Cache-Control"] == "no-store"


def test_csp_allows_inline_scripts_only_by_hash() -> None:
    html = '<script>var a=1;</script><script src="/static/app.js"></script><img onerror="x()">'
    csp = csp_for(html)
    assert "'unsafe-inline'" not in csp.split("script-src", 1)[1].split(";", 1)[0]
    assert csp.count("'sha256-") == 2 and "'unsafe-hashes'" in csp
    assert "'sha256-" not in csp_for(None)


# ------------------------------------------------------------------------------------------- static
@pytest.fixture()
def static_app(tmp_path: Path) -> DashboardApp:
    static = tmp_path / "static"
    (static / "css").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>x</title><script>window.t=1</script>", encoding="utf-8")
    (static / "app.js").write_text("console.log(1)", encoding="utf-8")
    (static / "css" / "s.css").write_text("body{}", encoding="utf-8")
    (static / ".hidden.js").write_text("secret", encoding="utf-8")
    (static / "tool.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "outside.js").write_text("nope", encoding="utf-8")
    return DashboardApp(DemoData(), static_dir=static, secrets=[])


def test_static_serving(static_app: DashboardApp) -> None:
    root = static_app.handle("GET", "/", H)
    assert root.status == 200 and root.headers["Content-Type"].startswith("text/html")
    assert "'sha256-" in root.headers["Content-Security-Policy"]
    assert static_app.handle("GET", "/static/app.js", H).headers["Content-Type"].startswith("text/javascript")
    assert static_app.handle("GET", "/static/css/s.css", H).status == 200
    head = static_app.handle("HEAD", "/static/app.js", H)
    assert head.status == 200 and head.body == b""


@pytest.mark.parametrize("target", [
    "/static/../outside.js", "/static/%2e%2e/outside.js", "/static/..%2Foutside.js", "/static/.hidden.js",
    "/static/tool.py", "/static/", "/static/css", "/static/css/../../outside.js", "/static//etc/passwd",
    "/static/%00app.js", "/static/..\\outside.js", "/etc/passwd", "/server.py", "/static/missing.js",
])
def test_static_refuses_traversal_and_unknown(static_app: DashboardApp, target: str) -> None:
    resp = static_app.handle("GET", target, H)
    assert resp.status == 404, target
    assert b"nope" not in resp.body and b"secret" not in resp.body and b"print" not in resp.body


def test_missing_static_dir_is_a_clean_404(tmp_path: Path) -> None:
    app = DashboardApp(DemoData(), static_dir=tmp_path / "absent", secrets=[])
    resp = app.handle("GET", "/", H)
    assert resp.status == 404 and b"/api/health" in resp.body
    assert app.handle("GET", "/api/health", H).json()["data"]["static_present"] is False


# ------------------------------------------------------------------------------------------- failures
class Exploding(DemoData):
    def positions(self) -> Any:
        raise RuntimeError("boom with ALPACA_SECRET_KEY=abc123secretvalue in it")

    def summary(self) -> Any:
        return ok({"weird": float("nan"), "inf": float("inf")})


def test_reader_exception_is_unavailable_not_500() -> None:
    app = DashboardApp(Exploding(), secrets=[])
    resp = app.handle("GET", "/api/positions", H)
    assert resp.status == 200
    body = resp.json()
    assert body["ok"] is False and "RuntimeError" in body["unavailable"]
    assert b"abc123secretvalue" not in resp.body and b"Traceback" not in resp.body
    s = app.handle("GET", "/api/summary", H).json()
    assert s["data"] == {"weird": None, "inf": None}


def test_scrub_and_collect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_API_KEY", "env-secret-value-123")
    monkeypatch.setenv("HOME_DIR_PATH", "not-a-secret-name")
    secrets = collect_secrets(["provider-secret-xyz", "abc"], dotenv=False)
    assert "env-secret-value-123" in secrets and "provider-secret-xyz" in secrets
    assert "abc" not in secrets and "not-a-secret-name" not in secrets
    assert scrub('{"a":"x env-secret-value-123 y"}', secrets) == '{"a":"x [redacted] y"}'


# ------------------------------------------------------------------------------------------- real socket
def _request(port: int, method: str, path: str, headers: dict[str, str] | None = None,
             body: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, {k: v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def test_real_server_on_loopback() -> None:
    server = make_server(DemoData(), 0)
    port = server.server_address[1]
    assert server.server_address[0] == "127.0.0.1"
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    try:
        api = {"X-Swing-Dashboard": "1"}
        code, headers, body = _request(port, "GET", "/api/health", api)
        assert code == 200 and json.loads(body)["ok"] is True
        assert _request(port, "GET", "/api/health")[0] == 403  # a script without the header
        assert _request(port, "GET", "/")[0] in (200, 404)  # the page itself needs no header
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "Python" not in headers.get("Server", "")
        code, _h, _b = _request(port, "GET", "/api/health", {"Host": "evil.example"})
        assert code == 403
        code, _h, body = _request(port, "POST", "/api/killswitch/trip",
                                  {"Content-Type": "application/json", "Content-Length": str(10 ** 7)})
        assert code == 413
        code, _h, body = _request(port, "POST", "/api/killswitch/trip", {"Content-Type": "application/json", **api},
                                  b'{"confirm": "TRIP"}')
        assert code == 200 and json.loads(body)["data"]["tripped"] is True
        code, _h, _b = _request(port, "OPTIONS", "/api/killswitch/trip", {"Origin": "https://evil.example"})
        assert code == 405
        code, _h, _b = _request(port, "PUT", "/api/summary")
        assert code == 405
    finally:
        server.shutdown()
        server.server_close()


def test_make_server_refuses_public_bind() -> None:
    with pytest.raises(ValueError):
        make_server(DemoData(), 0, host="0.0.0.0")


def test_main_rejects_bad_port() -> None:
    with pytest.raises(SystemExit):
        cli.main(["--port", "70000"])


def test_main_wires_serve(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(cli, "serve", lambda **kw: seen.update(kw))
    assert cli.main(["--demo", "--port", "9999", "--open", "--settings", "config/live.yaml"]) == 0
    assert seen == {"settings_path": "config/live.yaml", "port": 9999, "demo": True, "open_browser": True}
