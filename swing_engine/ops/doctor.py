"""`swing doctor`: pre-flight checks for a fresh machine or a new set of keys.

Offline checks never touch the network and are always run: `.env` present, each secret present/absent,
`settings.yaml` parses, store path writable, trading calendar loads, plugin registry imports, kill switch
state, `state/limits.json` readable, Python and package versions.

Live checks run only with ``live_checks=True`` and only for vendors whose key exists. Each one is a single
cheap request with a :data:`LIVE_TIMEOUT_S` timeout; failures become a ``fail`` check with the HTTP status
or exception name, never an exception. Secret values are scrubbed from every detail string (Telegram puts
the bot token in the URL path, Alpha Vantage in the query string) so the report is safe to paste.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from enum import StrEnum
from importlib import metadata
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml
from pydantic import BaseModel

from swing_engine.core import registry
from swing_engine.core.config import ROOT, Secrets, Settings

log = structlog.get_logger(__name__)

# ---- timing / sizes ------------------------------------------------------------------------------------------
LIVE_TIMEOUT_S = 10.0
CALENDAR_PROBE_DAYS = 7  # a one-week window is enough to prove the calendar loads and has sessions
HEAD_BYTES = 2048  # Alpha Vantage's calendar CSV is large; the doctor reads only its head
DETAIL_PREVIEW_CHARS = 160
MIN_SECRET_LEN = 4  # shorter values are not scrubbed: they would blank ordinary words
MIN_PYTHON = (3, 12)
REDACTED = "***"

# ---- endpoints (shared constants where the project already has them) -----------------------------------------
MASSIVE_TICKERS_URL = "https://api.massive.com/v3/reference/tickers"
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_URL = "https://api.alpaca.markets"
ALPACA_ACCOUNT_PATH = "/v2/account"
ALPACA_DATA_LATEST_BAR_URL = "https://data.alpaca.markets/v2/stocks/SPY/bars/latest"
ALPACA_DATA_FEED = "iex"
ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"
ALPHAVANTAGE_FUNCTION = "EARNINGS_CALENDAR"
ALPHAVANTAGE_HORIZON = "3month"
EDGAR_CURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
EDGAR_PROBE_FORM = "8-K"
NASDAQ_HALTS_RSS = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
TELEGRAM_API = "https://api.telegram.org"
PUSHOVER_VALIDATE_URL = "https://api.pushover.net/1/users/validate.json"
ANTHROPIC_DOCTOR_MODEL = "claude-haiku-4-5"  # cheapest model: the call proves the key, nothing else
ANTHROPIC_DOCTOR_MAX_TOKENS = 1
ANTHROPIC_DOCTOR_PROMPT = "ping"
TELEGRAM_TEST_TEXT = "swing doctor: test message"

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY = 429

PACKAGES = ("pandas", "numpy", "duckdb", "pydantic", "httpx", "anthropic", "alpaca-py", "scikit-learn", "lightgbm")
OPTIONAL_IMPORTS = {"lightgbm": "ranker falls back to scikit-learn HistGradientBoosting (brew install libomp)"}
PLUGIN_KINDS = ("bar_provider", "strategy", "broker", "feed", "rule", "deliverer")
#: Secrets fields that are credentials (scrubbed from details). The others are flags or a contact string.
CREDENTIAL_FIELDS = (
    "massive_api_key",
    "eodhd_api_key",
    "alphavantage_api_key",
    "alpaca_api_key",
    "alpaca_secret_key",
    "quiver_api_key",
    "anthropic_api_key",
    "telegram_bot_token",
    "telegram_chat_id",
    "pushover_user_key",
    "pushover_app_token",
)


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class Check(BaseModel):
    name: str
    status: CheckStatus
    detail: str = ""


class Redactor:
    """Blank every secret value (and credential-looking query parameters) in free text."""

    def __init__(self, secrets: Secrets) -> None:
        values = [str(getattr(secrets, f) or "") for f in CREDENTIAL_FIELDS]
        self.values = sorted({v for v in values if len(v) >= MIN_SECRET_LEN}, key=len, reverse=True)

    def __call__(self, text: Any) -> str:
        out = str(text)
        for value in self.values:
            out = out.replace(value, REDACTED)
        try:
            from swing_engine.data._http import redact_secrets

            out = redact_secrets(out)
        except Exception:  # pragma: no cover - the data package is optional for the doctor
            pass
        return out


def _resolve(path: str | Path) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else ROOT / p


def _preview(text: str, limit: int = DETAIL_PREVIEW_CHARS) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _guarded(name: str, fn: Callable[[], Check], redact: Redactor) -> Check:
    """Run one check; any exception becomes a ``fail`` with a redacted, single-line reason."""
    try:
        check = fn()
    except httpx.TimeoutException:
        check = Check(name=name, status=CheckStatus.FAIL, detail=f"timed out after {LIVE_TIMEOUT_S:.0f} s")
    except Exception as e:
        check = Check(name=name, status=CheckStatus.FAIL, detail=f"{type(e).__name__}: {_preview(str(e))}")
    check.detail = redact(check.detail)
    log.info("doctor_check", name=check.name, status=check.status.value)
    return check


# ----------------------------------------------------------------------------------------------------------
# offline checks
# ----------------------------------------------------------------------------------------------------------
def check_env_file(env_path: Path) -> Check:
    if env_path.exists():
        return Check(name="env_file", status=CheckStatus.OK, detail=str(env_path))
    return Check(
        name="env_file",
        status=CheckStatus.WARN,
        detail=f"{env_path} not found; copy .env.example and fill in the keys you have",
    )


def check_secrets(secrets: Secrets) -> list[Check]:
    """One check per `.env` key: present / missing / default. Values are never part of the detail."""
    out: list[Check] = []
    for name, field in Secrets.model_fields.items():
        value = getattr(secrets, name)
        label = f"secret:{name.upper()}"
        if isinstance(value, bool):
            status = CheckStatus.OK if value else CheckStatus.WARN
            detail = "paper trading" if value else "LIVE keys expected: docs/gates.md applies"
        elif value in (None, ""):
            status, detail = CheckStatus.WARN, "missing"
        elif value == field.default:
            status, detail = CheckStatus.WARN, "default value; set your own"
        else:
            status, detail = CheckStatus.OK, "set"
        out.append(Check(name=label, status=status, detail=detail))
    return out


def check_settings_file(settings_path: Path) -> Check:
    if not settings_path.exists():
        return Check(name="settings_yaml", status=CheckStatus.WARN, detail=f"{settings_path} missing; defaults in use")
    raw = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
    parsed = Settings.model_validate(raw)
    enabled = [n for n, cfg in parsed.strategies.items() if (cfg or {}).get("enabled", True)]
    return Check(
        name="settings_yaml",
        status=CheckStatus.OK,
        detail=f"{settings_path}: provider={parsed.data.bar_provider}, strategies={','.join(enabled) or '-'}",
    )


def check_store_writable(settings: Settings) -> Check:
    path = _resolve(settings.data.store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".doctor-", delete=True) as fh:
        fh.write(b"ok")
    state = f"exists ({path.stat().st_size:,} bytes)" if path.exists() else "not created yet (run `swing ingest`)"
    return Check(name="store_path", status=CheckStatus.OK, detail=f"{path} writable; {state}")


def check_calendar(settings: Settings, today: date | None = None) -> Check:
    cal = importlib.import_module("swing_engine.data.calendar")
    end = today or date.today()
    days = cal.trading_days(end - timedelta(days=CALENDAR_PROBE_DAYS), end, settings.data.calendar)
    if not days:
        raise RuntimeError(f"{settings.data.calendar} calendar returned no sessions in the last {CALENDAR_PROBE_DAYS} days")
    return Check(
        name="calendar",
        status=CheckStatus.OK,
        detail=f"{settings.data.calendar}: {len(days)} sessions in the last {CALENDAR_PROBE_DAYS} days, last {days[-1]}",
    )


def check_registry() -> Check:
    counts: dict[str, int] = {}
    for kind in PLUGIN_KINDS:
        counts[kind] = len(registry.names(kind))
    empty = [k for k, n in counts.items() if n == 0]
    detail = ", ".join(f"{k}={n}" for k, n in counts.items())
    status = CheckStatus.WARN if empty else CheckStatus.OK
    return Check(name="registry_plugins", status=status, detail=detail + (f"; none registered for {empty}" if empty else ""))


def check_kill_switch(settings: Settings) -> Check:
    killswitch = importlib.import_module("swing_engine.risk.killswitch")
    state = killswitch.status(settings.risk.kill_switch_file)
    if state["tripped"]:
        reason = _preview(state.get("reason") or "")
        return Check(name="kill_switch", status=CheckStatus.WARN, detail=f"TRIPPED ({state['path']}) {reason}".rstrip())
    return Check(name="kill_switch", status=CheckStatus.OK, detail=f"clear ({state['path']})")


def check_limits_state(settings: Settings) -> Check:
    path = _resolve(settings.risk.limits_state_file)
    if not path.exists():
        return Check(name="limits_state", status=CheckStatus.SKIP, detail=f"{path} not written yet (created by `swing paper`)")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return Check(
        name="limits_state",
        status=CheckStatus.OK,
        detail=f"{path}: day={data.get('day')} peak_equity={data.get('peak_equity')} updated_at={data.get('updated_at')}",
    )


def check_python() -> Check:
    version = sys.version_info[:3]
    text = ".".join(str(v) for v in version)
    if version[:2] < MIN_PYTHON:
        return Check(name="python", status=CheckStatus.FAIL, detail=f"{text} < {'.'.join(map(str, MIN_PYTHON))}")
    return Check(name="python", status=CheckStatus.OK, detail=f"{text} ({sys.executable})")


def check_packages(packages: Iterable[str] = PACKAGES) -> list[Check]:
    out: list[Check] = []
    for name in packages:
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError:
            out.append(Check(name=f"package:{name}", status=CheckStatus.WARN, detail="not installed"))
            continue
        detail = version
        status = CheckStatus.OK
        if name in OPTIONAL_IMPORTS:
            try:
                importlib.import_module(name)
            except Exception as e:  # lightgbm raises OSError without libomp on macOS
                status = CheckStatus.WARN
                detail = f"{version} installed but not importable ({type(e).__name__}); {OPTIONAL_IMPORTS[name]}"
        out.append(Check(name=f"package:{name}", status=status, detail=detail))
    return out


# ----------------------------------------------------------------------------------------------------------
# live checks
# ----------------------------------------------------------------------------------------------------------
def _status_check(name: str, response: httpx.Response, ok_detail: str) -> Check:
    code = response.status_code
    if code == HTTP_OK:
        return Check(name=name, status=CheckStatus.OK, detail=ok_detail)
    if code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
        return Check(name=name, status=CheckStatus.FAIL, detail=f"HTTP {code}: credentials rejected")
    if code == HTTP_TOO_MANY:
        return Check(name=name, status=CheckStatus.WARN, detail=f"HTTP {code}: rate limited; retry later")
    return Check(name=name, status=CheckStatus.FAIL, detail=f"HTTP {code}: {_preview(response.text)}")


def _rate_limit_headers(response: httpx.Response) -> str:
    found = {k: v for k, v in response.headers.items() if "ratelimit" in k.lower().replace("-", "")}
    return ", ".join(f"{k}={v}" for k, v in sorted(found.items())) if found else "no rate-limit headers"


def live_massive(client: httpx.Client, secrets: Secrets) -> Check:
    response = client.get(
        MASSIVE_TICKERS_URL,
        params={"limit": 1},
        headers={"Authorization": f"Bearer {secrets.massive_api_key}", "Accept": "application/json"},
    )
    if response.status_code != HTTP_OK:
        return _status_check("live:massive", response, "")
    payload = response.json()
    results = len(payload.get("results") or [])
    return Check(
        name="live:massive",
        status=CheckStatus.OK,
        detail=f"status={payload.get('status')} results={results}; {_rate_limit_headers(response)}",
    )


def _alpaca_headers(secrets: Secrets) -> dict[str, str]:
    return {"APCA-API-KEY-ID": secrets.alpaca_api_key or "", "APCA-API-SECRET-KEY": secrets.alpaca_secret_key or ""}


def live_alpaca_account(client: httpx.Client, secrets: Secrets) -> Check:
    base = ALPACA_PAPER_URL if secrets.alpaca_paper else ALPACA_LIVE_URL
    mode = "paper" if secrets.alpaca_paper else "LIVE"
    response = client.get(f"{base}{ALPACA_ACCOUNT_PATH}", headers=_alpaca_headers(secrets))
    if response.status_code != HTTP_OK:
        return _status_check("live:alpaca_account", response, "")
    account = response.json()
    detail = (
        f"{mode} ({base}): status={account.get('status')} equity={account.get('equity')} "
        f"cash={account.get('cash')} trading_blocked={account.get('trading_blocked')}"
    )
    status = CheckStatus.OK if secrets.alpaca_paper else CheckStatus.WARN
    return Check(name="live:alpaca_account", status=status, detail=detail)


def live_alpaca_data(client: httpx.Client, secrets: Secrets) -> Check:
    response = client.get(ALPACA_DATA_LATEST_BAR_URL, params={"feed": ALPACA_DATA_FEED}, headers=_alpaca_headers(secrets))
    if response.status_code != HTTP_OK:
        return _status_check("live:alpaca_data", response, "")
    bar = response.json().get("bar") or {}
    return Check(
        name="live:alpaca_data",
        status=CheckStatus.OK,
        detail=f"SPY latest bar t={bar.get('t')} c={bar.get('c')} v={bar.get('v')} (feed={ALPACA_DATA_FEED})",
    )


def _head_text(client: httpx.Client, url: str, params: dict[str, Any]) -> tuple[int, str]:
    """Status and the first :data:`HEAD_BYTES` of the body; the connection is closed without reading the rest."""
    chunks: list[bytes] = []
    size = 0
    with client.stream("GET", url, params=params) as response:
        status = response.status_code
        for chunk in response.iter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size >= HEAD_BYTES:
                break
    return status, b"".join(chunks)[:HEAD_BYTES].decode("utf-8", errors="replace")


def live_alphavantage(client: httpx.Client, secrets: Secrets) -> Check:
    params = {"function": ALPHAVANTAGE_FUNCTION, "horizon": ALPHAVANTAGE_HORIZON, "apikey": secrets.alphavantage_api_key}
    status, head = _head_text(client, ALPHAVANTAGE_URL, params)
    if status != HTTP_OK:
        return Check(name="live:alphavantage", status=CheckStatus.FAIL, detail=f"HTTP {status}: {_preview(head)}")
    if head.lstrip().startswith("{"):
        return Check(name="live:alphavantage", status=CheckStatus.WARN, detail=f"JSON instead of CSV (throttled or bad key): {_preview(head)}")
    header = head.splitlines()[0] if head.strip() else ""
    if "symbol" not in header.lower():
        return Check(name="live:alphavantage", status=CheckStatus.FAIL, detail=f"unexpected body: {_preview(head)}")
    return Check(name="live:alphavantage", status=CheckStatus.OK, detail=f"{ALPHAVANTAGE_FUNCTION} csv header: {header}")


def live_edgar(client: httpx.Client, secrets: Secrets) -> Check:
    agent = secrets.edgar_user_agent or ""
    if "@" not in agent:
        return Check(name="live:edgar", status=CheckStatus.FAIL, detail="EDGAR_USER_AGENT must include a contact email (SEC fair-access policy)")
    default_agent = agent == Secrets.model_fields["edgar_user_agent"].default
    params = {"action": "getcurrent", "type": EDGAR_PROBE_FORM, "owner": "exclude", "count": 1, "output": "atom"}
    response = client.get(EDGAR_CURRENT_URL, params=params, headers={"User-Agent": agent})
    if response.status_code == HTTP_FORBIDDEN:
        return Check(name="live:edgar", status=CheckStatus.FAIL, detail="HTTP 403: SEC fair-access block; set a real EDGAR_USER_AGENT and slow down")
    if response.status_code != HTTP_OK:
        return _status_check("live:edgar", response, "")
    entries = response.text.count("<entry")
    detail = f"{entries} {EDGAR_PROBE_FORM} entries; User-Agent " + ("is the default placeholder: set EDGAR_USER_AGENT" if default_agent else "ok")
    return Check(name="live:edgar", status=CheckStatus.WARN if default_agent else CheckStatus.OK, detail=detail)


def live_nasdaq_halts(client: httpx.Client) -> Check:
    response = client.get(NASDAQ_HALTS_RSS)
    if response.status_code != HTTP_OK:
        return _status_check("live:nasdaq_halts", response, "")
    items = response.text.count("<item")
    return Check(name="live:nasdaq_halts", status=CheckStatus.OK, detail=f"{items} halt items in the RSS feed")


def live_anthropic(secrets: Secrets, anthropic_client: Any | None = None) -> Check:
    import anthropic

    client = anthropic_client or anthropic.Anthropic(api_key=secrets.anthropic_api_key, timeout=LIVE_TIMEOUT_S, max_retries=0)
    try:
        response = client.messages.create(
            model=ANTHROPIC_DOCTOR_MODEL,
            max_tokens=ANTHROPIC_DOCTOR_MAX_TOKENS,
            messages=[{"role": "user", "content": ANTHROPIC_DOCTOR_PROMPT}],
        )
    except anthropic.AuthenticationError:
        return Check(name="live:anthropic", status=CheckStatus.FAIL, detail="HTTP 401: ANTHROPIC_API_KEY rejected")
    except anthropic.RateLimitError:
        return Check(name="live:anthropic", status=CheckStatus.WARN, detail="HTTP 429: rate limited; retry later")
    except anthropic.APIStatusError as e:
        return Check(name="live:anthropic", status=CheckStatus.FAIL, detail=f"HTTP {e.status_code}: {type(e).__name__}")
    except anthropic.APIConnectionError as e:
        return Check(name="live:anthropic", status=CheckStatus.FAIL, detail=f"connection error: {type(e).__name__}")
    usage = getattr(response, "usage", None)
    detail = (
        f"model={getattr(response, 'model', ANTHROPIC_DOCTOR_MODEL)} stop={getattr(response, 'stop_reason', None)} "
        f"in={getattr(usage, 'input_tokens', None)} out={getattr(usage, 'output_tokens', None)}"
    )
    return Check(name="live:anthropic", status=CheckStatus.OK, detail=detail)


def live_telegram(client: httpx.Client, secrets: Secrets, send_test: bool) -> Check:
    base = f"{TELEGRAM_API}/bot{secrets.telegram_bot_token}"
    response = client.get(f"{base}/getMe")
    if response.status_code != HTTP_OK:
        return _status_check("live:telegram", response, "")
    me = response.json().get("result") or {}
    detail = f"bot @{me.get('username')} reachable"
    if not secrets.telegram_chat_id:
        return Check(name="live:telegram", status=CheckStatus.WARN, detail=f"{detail}; TELEGRAM_CHAT_ID missing, alerts cannot be delivered")
    if not send_test:
        return Check(name="live:telegram", status=CheckStatus.OK, detail=f"{detail}; chat id set (use --send-test to send a message)")
    sent = client.post(f"{base}/sendMessage", json={"chat_id": secrets.telegram_chat_id, "text": TELEGRAM_TEST_TEXT})
    if sent.status_code != HTTP_OK:
        return Check(name="live:telegram", status=CheckStatus.FAIL, detail=f"{detail}; sendMessage HTTP {sent.status_code}: {_preview(sent.text)}")
    message_id = (sent.json().get("result") or {}).get("message_id")
    return Check(name="live:telegram", status=CheckStatus.OK, detail=f"{detail}; test message sent (message_id={message_id})")


def live_pushover(client: httpx.Client, secrets: Secrets) -> Check:
    response = client.post(PUSHOVER_VALIDATE_URL, data={"token": secrets.pushover_app_token, "user": secrets.pushover_user_key})
    payload: dict[str, Any] = {}
    try:
        payload = response.json()
    except ValueError:
        pass
    if response.status_code == HTTP_OK and payload.get("status") == 1:
        devices = ", ".join(payload.get("devices") or []) or "-"
        return Check(name="live:pushover", status=CheckStatus.OK, detail=f"user/token valid; devices: {devices}")
    if response.status_code == HTTP_BAD_REQUEST:
        errors = "; ".join(str(e) for e in payload.get("errors") or []) or _preview(response.text)
        return Check(name="live:pushover", status=CheckStatus.FAIL, detail=f"HTTP 400: {errors}")
    return _status_check("live:pushover", response, "")


def _needs(name: str, *keys: str | None, hint: str) -> Check | None:
    """A ``skip`` check when any required key is absent, else None (the live check may run)."""
    if all(keys):
        return None
    return Check(name=name, status=CheckStatus.SKIP, detail=f"{hint} not set")


def run_live_checks(
    secrets: Secrets,
    *,
    send_test: bool = False,
    client: httpx.Client | None = None,
    anthropic_client: Any | None = None,
) -> list[Check]:
    """Every vendor probe, each guarded; vendors without a key are reported as ``skip``."""
    redact = Redactor(secrets)
    own_client = client is None
    http = client or httpx.Client(timeout=LIVE_TIMEOUT_S, follow_redirects=True)
    specs: list[tuple[str, Check | None, Callable[[], Check]]] = [
        ("live:massive", _needs("live:massive", secrets.massive_api_key, hint="MASSIVE_API_KEY"), lambda: live_massive(http, secrets)),
        (
            "live:alpaca_account",
            _needs("live:alpaca_account", secrets.alpaca_api_key, secrets.alpaca_secret_key, hint="ALPACA_API_KEY/ALPACA_SECRET_KEY"),
            lambda: live_alpaca_account(http, secrets),
        ),
        (
            "live:alpaca_data",
            _needs("live:alpaca_data", secrets.alpaca_api_key, secrets.alpaca_secret_key, hint="ALPACA_API_KEY/ALPACA_SECRET_KEY"),
            lambda: live_alpaca_data(http, secrets),
        ),
        (
            "live:alphavantage",
            _needs("live:alphavantage", secrets.alphavantage_api_key, hint="ALPHAVANTAGE_API_KEY"),
            lambda: live_alphavantage(http, secrets),
        ),
        ("live:edgar", None, lambda: live_edgar(http, secrets)),
        ("live:nasdaq_halts", None, lambda: live_nasdaq_halts(http)),
        (
            "live:anthropic",
            _needs("live:anthropic", secrets.anthropic_api_key, hint="ANTHROPIC_API_KEY"),
            lambda: live_anthropic(secrets, anthropic_client),
        ),
        (
            "live:telegram",
            _needs("live:telegram", secrets.telegram_bot_token, hint="TELEGRAM_BOT_TOKEN"),
            lambda: live_telegram(http, secrets, send_test),
        ),
        (
            "live:pushover",
            _needs("live:pushover", secrets.pushover_user_key, secrets.pushover_app_token, hint="PUSHOVER_USER_KEY/PUSHOVER_APP_TOKEN"),
            lambda: live_pushover(http, secrets),
        ),
    ]
    out: list[Check] = []
    try:
        for name, skip, fn in specs:
            out.append(skip if skip is not None else _guarded(name, fn, redact))
    finally:
        if own_client:
            http.close()
    return out


# ----------------------------------------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------------------------------------
def run_doctor(
    settings: Settings,
    secrets: Secrets,
    live_checks: bool = False,
    *,
    send_test: bool = False,
    settings_path: str | Path | None = None,
    env_path: str | Path | None = None,
    client: httpx.Client | None = None,
    anthropic_client: Any | None = None,
    today: date | None = None,
) -> list[Check]:
    """Offline checks, then (with ``live_checks``) one cheap request per vendor whose key exists.

    Keyword arguments exist for tests and the CLI: ``settings_path`` / ``env_path`` default to the repo's
    `config/settings.yaml` and `.env`; ``client`` / ``anthropic_client`` inject HTTP and Anthropic clients.
    """
    redact = Redactor(secrets)
    settings_file = Path(settings_path) if settings_path else ROOT / "config" / "settings.yaml"
    env_file = Path(env_path) if env_path else ROOT / ".env"
    checks: list[Check] = [check_env_file(env_file), *check_secrets(secrets)]
    offline: list[tuple[str, Callable[[], Check]]] = [
        ("settings_yaml", lambda: check_settings_file(settings_file)),
        ("store_path", lambda: check_store_writable(settings)),
        ("calendar", lambda: check_calendar(settings, today)),
        ("registry_plugins", check_registry),
        ("kill_switch", lambda: check_kill_switch(settings)),
        ("limits_state", lambda: check_limits_state(settings)),
        ("python", check_python),
    ]
    checks.extend(_guarded(name, fn, redact) for name, fn in offline)
    checks.extend(check_packages())
    if live_checks:
        checks.extend(run_live_checks(secrets, send_test=send_test, client=client, anthropic_client=anthropic_client))
    else:
        checks.append(Check(name="live", status=CheckStatus.SKIP, detail="vendor probes skipped; pass --live to run them"))
    log.info(
        "doctor_done",
        ok=sum(c.status is CheckStatus.OK for c in checks),
        warn=sum(c.status is CheckStatus.WARN for c in checks),
        fail=sum(c.status is CheckStatus.FAIL for c in checks),
        skip=sum(c.status is CheckStatus.SKIP for c in checks),
    )
    return checks
