"""HTTP layer: routing, validation, security headers, JSON. Standard library only.

``DashboardApp.handle(method, path, headers, body)`` is pure (no sockets) so tests drive it directly;
``DashboardHandler`` adapts it to ``http.server``. Every API answer is the ``data.ok`` / ``data.unavailable``
envelope with HTTP 200 (missing data is not an error); 400 is a bad parameter, 403 a non-local Host or a
cross-site API request, 404 an unknown route, 405 a wrong method, 413 an oversized body. An exception inside a reader
is logged and answered as ``unavailable`` (never a 500 with a traceback).

Security posture (the page is local but the browser that opens it also visits the internet):

* bound to 127.0.0.1 only; requests whose ``Host`` is not localhost / 127.0.0.1 / [::1] are refused
  (DNS rebinding);
* every ``/api/*`` request (GET too) must be same-origin: a ``Sec-Fetch-Site`` other than ``same-origin`` /
  ``none`` or an ``Origin`` that is not this server's own scheme+host+port is refused, and a request without
  ``Sec-Fetch-Site`` (older browsers, scripts) must carry ``X-Swing-Dashboard: 1``, which a cross-origin page
  cannot add without a preflight (refused). A hostile page therefore cannot even make the server work, e.g.
  open the DuckDB store for symbol after symbol and hold the lock against the nightly;
* POSTs also need ``Content-Type: application/json`` and a body of at most ``MAX_BODY_BYTES``;
* no CORS headers, so other origins cannot read responses;
* CSP: self plus the charting CDN (https://unpkg.com); inline scripts in the served HTML are allowed by hash
  only; nosniff, no-referrer, frame-ancestors none;
* every secret value from ``.env`` / the environment is scrubbed from every response body as a last guard.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import sys
import threading
import traceback
import webbrowser
from collections.abc import Callable, Iterable, Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from . import DEFAULT_HOST, DEFAULT_PORT
from .data import (
    DEFAULT_CHART_DAYS,
    EQUITY_PERIODS,
    MAX_CHART_DAYS,
    MAX_HOURS,
    ORDER_STATUSES,
    RATINGS,
    SHADOW_GROUPS,
    BadRequest,
    _redact,
    clean,
    parse_choice,
    parse_date,
    parse_event_id,
    parse_int,
    parse_symbol,
    unavailable,
)

log = logging.getLogger("swing_engine.dashboard")

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_BODY_BYTES = 2048
MAX_STATIC_BYTES = 8 * 1024 * 1024
ALLOWED_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})
API_HEADER = "X-Swing-Dashboard"  # required on /api/* when the browser sends no Sec-Fetch-Site (app.js adds it)
API_HEADER_VALUE = "1"
SAME_ORIGIN_SITES = frozenset({"same-origin", "none"})  # "none": typed into the address bar / a bookmark
CHART_CDN = "https://unpkg.com"
KILL_CONFIRM = "TRIP"
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
    ".map": "application/json",
}
SECRET_ENV_HINTS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "CHAT_ID")
MIN_SECRET_LEN = 6
REDACTED = "[redacted]"
INLINE_SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc\s*=)[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
EVENT_HANDLER_RE = re.compile(r"\son[a-z]+\s*=\s*\"([^\"]*)\"", re.IGNORECASE)

Provider = Any  # data.LiveData | demo.DemoData: same method names, each returns an envelope


# --------------------------------------------------------------------------------------------- secrets
def collect_secrets(extra: Iterable[str] | None = None, *, dotenv: bool = True) -> list[str]:
    """Values that must never appear in a response: every ``Secrets`` field that holds a credential (``dotenv``),
    any environment variable whose name looks like one, and ``extra`` (the provider's own secrets). Longest first
    so a secret containing another is scrubbed whole."""
    values: set[str] = set(v for v in (extra or []) if isinstance(v, str))
    if dotenv:
        try:
            from swing_engine.core.config import load_secrets

            values.update(secret_values(load_secrets()))
        except Exception:  # noqa: BLE001 - no .env / invalid values: the env scan below still runs
            pass
    for name, value in os.environ.items():
        if any(h in name.upper() for h in SECRET_ENV_HINTS) and isinstance(value, str):
            values.add(value)
    return sorted((v for v in values if len(v.strip()) >= MIN_SECRET_LEN), key=len, reverse=True)


def secret_values(secrets: Any) -> list[str]:
    """Credential strings held by a ``core.config.Secrets`` (not the paper flag or the EDGAR user agent)."""
    if secrets is None or not hasattr(secrets, "model_dump"):
        return []
    return [v for k, v in secrets.model_dump().items()
            if k not in ("alpaca_paper", "edgar_user_agent") and isinstance(v, str) and v]


def scrub(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s in text:
            text = text.replace(s, REDACTED)
        esc = json.dumps(s)[1:-1]
        if esc != s and esc in text:
            text = text.replace(esc, REDACTED)
    return text


# --------------------------------------------------------------------------------------------- headers
def _sha256_b64(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def csp_for(html: str | None = None) -> str:
    """Strict CSP; when serving HTML, its inline <script> blocks and on*="..." handlers are allowed by hash."""
    script_src = ["'self'", CHART_CDN]
    if html:
        hashes = {f"'sha256-{_sha256_b64(m)}'" for m in INLINE_SCRIPT_RE.findall(html)}
        handlers = {f"'sha256-{_sha256_b64(m)}'" for m in EVENT_HANDLER_RE.findall(html)}
        if handlers:
            script_src.append("'unsafe-hashes'")
        script_src.extend(sorted(hashes | handlers))
    return "; ".join([
        "default-src 'self'",
        f"script-src {' '.join(script_src)}",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])


def security_headers(content_type: str, csp: str) -> dict[str, str]:
    headers = {
        "Content-Type": content_type,
        "Content-Security-Policy": csp,
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    }
    return headers


def host_allowed(host: str | None) -> bool:
    """Only loopback names (any port). DNS rebinding sends the attacker's hostname here."""
    if not host:
        return False
    host = host.strip().lower()
    if host.startswith("["):
        name = host.split("]", 1)[0] + "]"
    else:
        name = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    return name in ALLOWED_HOSTNAMES


def _host_port(netloc: str) -> str:
    """``host:port`` lower-cased with the http default port filled in (``localhost`` -> ``localhost:80``)."""
    n = netloc.strip().lower()
    if n.startswith("["):
        name, _, rest = n.partition("]")
        name, port = name + "]", rest[1:] if rest.startswith(":") else ""
    elif n.count(":") == 1:
        name, port = n.split(":")
    else:
        name, port = n, ""
    return f"{name}:{port or '80'}"


def origin_allowed(origin: str | None, host: str | None = None) -> bool:
    """No ``Origin`` header, or exactly this server's origin: ``http`` plus the request's ``Host`` (host and
    port; the server never speaks TLS). Without ``host`` any loopback origin passes (kept for callers that have
    no request)."""
    if origin is None:
        return True
    try:
        parts = urlsplit(origin.strip())
    except ValueError:
        return False
    if parts.scheme != "http" or not host_allowed(parts.netloc) or parts.path not in ("", "/") or parts.query:
        return False
    return host is None or _host_port(parts.netloc) == _host_port(host)


def api_request_refusal(headers: Mapping[str, str]) -> str | None:
    """Why an ``/api/*`` request is refused (403), or None. ``headers`` are lower-cased names."""
    site = (headers.get("sec-fetch-site") or "").strip().lower()
    if site and site not in SAME_ORIGIN_SITES:
        return "cross-site request refused: the dashboard API answers its own page only"
    if not origin_allowed(headers.get("origin"), headers.get("host")):
        return "cross-origin request refused: the dashboard API answers its own page only"
    if not site and (headers.get(API_HEADER.lower()) or "").strip() != API_HEADER_VALUE:
        return f"send the header {API_HEADER}: {API_HEADER_VALUE} (scripts and older browsers; the page adds it)"
    return None


class Response:
    __slots__ = ("status", "headers", "body")

    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


# --------------------------------------------------------------------------------------------- app
class DashboardApp:
    """Routes a request to the provider and renders the response."""

    def __init__(self, provider: Provider, *, static_dir: Path | None = None, secrets: list[str] | None = None):
        self.provider = provider
        self.static_dir = (static_dir or STATIC_DIR).resolve()
        own = secret_values(getattr(provider, "secrets", None))
        if secrets is None:  # demo mode reads no files at all, so not .env either (the environment scan still runs)
            self.secrets = collect_secrets(own, dotenv=not getattr(provider, "demo", False))
        else:
            self.secrets = sorted({v for v in [*secrets, *own] if len(v.strip()) >= MIN_SECRET_LEN}, key=len,
                                  reverse=True)
        self._get: list[tuple[re.Pattern[str], Callable[..., Any]]] = [
            (re.compile(r"^/api/health$"), self._health),
            (re.compile(r"^/api/summary$"), self._summary),
            (re.compile(r"^/api/regime$"), self._regime),
            (re.compile(r"^/api/equity$"), self._equity),
            (re.compile(r"^/api/positions$"), self._positions),
            (re.compile(r"^/api/orders$"), self._orders),
            (re.compile(r"^/api/chart/(?P<symbol>[^/]+)$"), self._chart),
            (re.compile(r"^/api/signals$"), self._signals),
            (re.compile(r"^/api/shadow$"), self._shadow),
            (re.compile(r"^/api/alerts$"), self._alerts),
            (re.compile(r"^/api/journal$"), self._journal),
            (re.compile(r"^/api/replay$"), self._replay),
        ]
        self._post: list[tuple[re.Pattern[str], Callable[..., Any]]] = [
            (re.compile(r"^/api/alerts/(?P<event_id>[^/]+)/rate$"), self._rate),
            (re.compile(r"^/api/killswitch/trip$"), self._trip),
        ]

    # ------------------------------------------------------------------------------- entry point
    def handle(self, method: str, target: str, headers: Mapping[str, str], body: bytes = b"") -> Response:
        h = {k.lower(): v for k, v in headers.items()}
        if not host_allowed(h.get("host")):
            return self._error(HTTPStatus.FORBIDDEN, "host not allowed: the dashboard answers on localhost only")
        try:
            parts = urlsplit(target)
        except ValueError:
            return self._error(HTTPStatus.BAD_REQUEST, "malformed request target")
        path = parts.path or "/"
        query = {k: v[-1] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        if method == "HEAD":
            resp = self.handle("GET", target, headers, b"")
            return Response(resp.status, resp.headers, b"")
        if path.startswith("/api/"):
            refusal = api_request_refusal(h)
            if refusal is not None:  # before routing: a refused request never reaches a reader
                return self._error(HTTPStatus.FORBIDDEN, refusal)
            return self._api(method, path, query, h, body)
        if method != "GET":
            return self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed", allow="GET, HEAD")
        return self._static(path)

    # ------------------------------------------------------------------------------- API
    def _api(self, method: str, path: str, query: dict[str, str], h: dict[str, str], body: bytes) -> Response:
        routes = self._get if method == "GET" else self._post if method == "POST" else None
        if routes is None:
            return self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed", allow="GET, POST")
        for pattern, fn in routes:
            m = pattern.match(path)
            if not m:
                continue
            try:
                if method == "POST":
                    payload = self._json_body(h, body)
                    result = fn(payload, **m.groupdict())
                else:
                    result = fn(query, **m.groupdict())
            except BadRequest as exc:
                return self._error(HTTPStatus.BAD_REQUEST, str(exc))
            except _Forbidden as exc:
                return self._error(HTTPStatus.FORBIDDEN, str(exc))
            except _TooLarge as exc:
                return self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, str(exc))
            except Exception as exc:  # noqa: BLE001 - never a 500 with a traceback for the page
                log.error("dashboard endpoint %s failed: %s", path, scrub(_redact("".join(
                    traceback.format_exception_only(type(exc), exc)), 500), self.secrets))
                result = unavailable(f"internal error reading {path} ({type(exc).__name__}); see the server log")
            return self._json(HTTPStatus.OK, result)
        other = self._post if method == "GET" else self._get
        if any(p.match(path) for p, _ in other):
            return self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed",
                               allow="POST" if method == "GET" else "GET, HEAD")
        return self._error(HTTPStatus.NOT_FOUND, f"no such endpoint: {path}")

    def _json_body(self, h: dict[str, str], body: bytes) -> dict[str, Any]:
        refusal = api_request_refusal(h)  # handle() checked already; kept so a direct caller cannot skip it
        if refusal is not None:
            raise _Forbidden(refusal)
        ctype = (h.get("content-type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            raise BadRequest("Content-Type must be application/json")
        if len(body) > MAX_BODY_BYTES:
            raise _TooLarge(f"body larger than {MAX_BODY_BYTES} bytes")
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError) as exc:
            raise BadRequest("body must be a JSON object") from exc
        if not isinstance(payload, dict):
            raise BadRequest("body must be a JSON object")
        return payload

    # ---- GET handlers
    def _health(self, q: dict[str, str]) -> Any:
        result = self.provider.health()
        if result.get("ok") and isinstance(result.get("data"), dict):
            result["data"]["static_present"] = (self.static_dir / "index.html").is_file()
        return result

    def _summary(self, q: dict[str, str]) -> Any:
        return self.provider.summary()

    def _regime(self, q: dict[str, str]) -> Any:
        return self.provider.regime(parse_date(q.get("date")))

    def _equity(self, q: dict[str, str]) -> Any:
        return self.provider.equity(parse_choice(q.get("period"), "period", EQUITY_PERIODS, "6M", upper=True))

    def _positions(self, q: dict[str, str]) -> Any:
        return self.provider.positions()

    def _orders(self, q: dict[str, str]) -> Any:
        status = parse_choice(q.get("status"), "status", ORDER_STATUSES, "open")
        return self.provider.orders(status, parse_int(q.get("limit"), "limit", 50, 1, 500))

    def _chart(self, q: dict[str, str], symbol: str) -> Any:
        sym = parse_symbol(unquote(symbol))
        return self.provider.chart(sym, parse_int(q.get("days"), "days", DEFAULT_CHART_DAYS, 5, MAX_CHART_DAYS))

    def _signals(self, q: dict[str, str]) -> Any:
        return self.provider.signals(parse_date(q.get("date")))

    def _shadow(self, q: dict[str, str]) -> Any:
        return self.provider.shadow(parse_choice(q.get("by"), "by", SHADOW_GROUPS, "strategy"))

    def _alerts(self, q: dict[str, str]) -> Any:
        return self.provider.alerts(parse_int(q.get("hours"), "hours", 48, 1, MAX_HOURS))

    def _journal(self, q: dict[str, str]) -> Any:
        return self.provider.journal(parse_date(q.get("date")))

    def _replay(self, q: dict[str, str]) -> Any:
        return self.provider.replay()

    # ---- POST handlers
    def _rate(self, payload: dict[str, Any], event_id: str) -> Any:
        eid = parse_event_id(unquote(event_id))
        rating = payload.get("rating")
        if not isinstance(rating, str) or rating.strip().lower() not in RATINGS:
            raise BadRequest(f"rating must be one of {', '.join(RATINGS)}")
        return self.provider.rate(eid, rating.strip().lower())

    def _trip(self, payload: dict[str, Any]) -> Any:
        if payload.get("confirm") != KILL_CONFIRM:
            raise BadRequest(f'send {{"confirm": "{KILL_CONFIRM}"}} to trip the kill switch')
        return self.provider.trip_killswitch()

    # ------------------------------------------------------------------------------- static
    def _static(self, path: str) -> Response:
        rel = "index.html" if path in ("/", "/index.html") else None
        if rel is None and path.startswith("/static/"):
            rel = unquote(path[len("/static/"):])
        if rel is None and path == "/favicon.ico":
            rel = "favicon.ico"
        if not rel or "\x00" in rel or "\\" in rel:
            return self._not_found_page(path)
        if any(part in ("", ".", "..") or part.startswith(".") for part in rel.split("/")):
            return self._not_found_page(path)
        try:
            file = (self.static_dir / rel).resolve()
            file.relative_to(self.static_dir)
        except (ValueError, OSError):
            return self._not_found_page(path)
        ctype = STATIC_TYPES.get(file.suffix.lower())
        if ctype is None or not file.is_file():
            return self._not_found_page(path)
        try:
            if file.stat().st_size > MAX_STATIC_BYTES:
                return self._not_found_page(path)
            data = file.read_bytes()
        except OSError:
            return self._not_found_page(path)
        html = data.decode("utf-8", "replace") if file.suffix.lower() == ".html" else None
        headers = security_headers(ctype, csp_for(html))
        headers["Cache-Control"] = "no-cache"
        return Response(HTTPStatus.OK, headers, data)

    def _not_found_page(self, path: str) -> Response:
        if path in ("/", "/index.html"):
            msg = ("The dashboard page is not built yet (no swing_engine/dashboard/static/index.html). "
                   "The JSON API is up: try /api/health.")
        else:
            msg = "Not found."
        body = (f"<!doctype html><meta charset=utf-8><title>Not found</title>"
                f"<p>{msg}</p>").encode()
        return Response(HTTPStatus.NOT_FOUND, security_headers("text/html; charset=utf-8", csp_for(None)), body)

    # ------------------------------------------------------------------------------- rendering
    def _json(self, status: int, payload: Any) -> Response:
        if isinstance(payload, dict) and payload.get("ok") and isinstance(payload.get("data"), dict):
            for key in ("stale", "partial"):  # also inside dict-shaped data, for clients that unwrap `data`
                if payload.get(key) and key not in payload["data"]:
                    payload["data"][key] = payload[key]
        text = json.dumps(clean(payload), allow_nan=False, separators=(",", ":"))
        text = scrub(text, self.secrets)
        headers = security_headers("application/json; charset=utf-8", csp_for(None))
        headers["Cache-Control"] = "no-store"
        return Response(status, headers, text.encode("utf-8"))

    def _error(self, status: int, message: str, allow: str | None = None) -> Response:
        resp = self._json(status, {"ok": False, "unavailable": message, "error": HTTPStatus(status).phrase})
        if allow:
            resp.headers["Allow"] = allow
        return resp


class _Forbidden(Exception):
    pass


class _TooLarge(Exception):
    pass


# --------------------------------------------------------------------------------------------- http.server glue
class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "swing-dashboard"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    app: DashboardApp  # set on the subclass built by make_server

    def _dispatch(self, method: str) -> None:
        body = b""
        if method == "POST":
            if self.headers.get("Transfer-Encoding"):
                self._send(self.app._error(HTTPStatus.LENGTH_REQUIRED, "chunked bodies are not accepted"), close=True)
                return
            raw_len = self.headers.get("Content-Length")
            try:
                length = int(raw_len) if raw_len is not None else 0
            except ValueError:
                self._send(self.app._error(HTTPStatus.BAD_REQUEST, "bad Content-Length"), close=True)
                return
            if length < 0 or length > MAX_BODY_BYTES:
                self._send(self.app._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                           f"body larger than {MAX_BODY_BYTES} bytes"), close=True)
                return
            body = self.rfile.read(length) if length else b""
        resp = self.app.handle(method, self.path, dict(self.headers.items()), body)
        self._send(resp, head=method == "HEAD")

    def _send(self, resp: Response, head: bool = False, close: bool = False) -> None:
        self.send_response(resp.status)
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp.body)))
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if not head and resp.body:
            self.wfile.write(resp.body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self._dispatch("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch("HEAD")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._send(self.app._error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"), close=True)

    do_DELETE = do_PATCH = do_PUT  # noqa: N815

    def do_OPTIONS(self) -> None:  # noqa: N802 - no CORS: answer preflights without Allow-Origin
        self._send(self.app._error(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed"), close=True)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - http.server API
        log.info("%s %s", self.address_string(), format % args)


def build_provider(settings_path: str | None, demo: bool) -> Provider:
    if demo:
        from .demo import DemoData

        return DemoData()
    from .data import LiveData

    return LiveData(settings_path)


def make_server(provider: Provider, port: int = DEFAULT_PORT, *, host: str = DEFAULT_HOST,
                static_dir: Path | None = None) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise ValueError("the dashboard binds to localhost only")
    app = DashboardApp(provider, static_dir=static_dir)
    handler = type("BoundDashboardHandler", (DashboardHandler,), {"app": app})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve(settings_path: str | None = None, port: int = DEFAULT_PORT, demo: bool = False,
          open_browser: bool = False) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    provider = build_provider(settings_path, demo)
    settings_file = getattr(provider, "settings_path", None)
    if settings_file is not None and not Path(settings_file).exists():
        print(f"warning: settings file {settings_file} not found; using built-in defaults", file=sys.stderr)
    server = make_server(provider, port)
    url = f"http://{DEFAULT_HOST}:{server.server_address[1]}/"
    print(f"swing dashboard{' (DEMO data)' if demo else ''} on {url}  (Ctrl-C to stop)", file=sys.stderr)
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


__all__ = ["API_HEADER", "DashboardApp", "Response", "api_request_refusal", "build_provider", "collect_secrets",
           "csp_for", "host_allowed", "make_server", "origin_allowed", "scrub", "secret_values", "serve"]

mimetypes.init()  # harmless; keeps platform MIME map loaded for anyone extending STATIC_TYPES
