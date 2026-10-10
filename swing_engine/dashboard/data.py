"""Read side of the dashboard: every function returns plain JSON-able data in an envelope.

Envelope: ``{"ok": True, "data": ...}`` or ``{"ok": False, "unavailable": "<human reason>"}``. A successful
envelope may also carry ``stale`` (the DuckDB store was locked by a writer, so a cached copy is served),
``source`` (where the rows came from when there is more than one possible source) and ``partial``
(``{section: reason}`` for the parts of a composite answer that could not be read). Missing data is never an
exception: a fresh install, no nightly yet, no Alpaca keys, a locked store, all come back as reasons.

Sources (all read-only except the two documented writes):

* settings: ``core.config.load_settings(path)``; secrets: ``core.config.load_secrets()`` (never echoed).
* run files: ``<store dir>/runs/<kind>/<date>.json`` (``execution.autopilot.run_path``): nightly, signals,
  reviews, intents, autopilot, regime, replay, size skips in the nightly report.
* DuckDB store (``settings.data.store_path``): ``bars``, ``breadth``, ``shadow_signals``; opened
  ``read_only=True`` per request, closed straight after, results cached for ``CACHE_TTL_S``. When a writer holds
  the lock (a backfill or the nightly) the last good result is served with ``stale`` set.
* event log SQLite (``settings.data.event_log_path``) opened ``mode=ro``; the rate endpoint alone writes, through
  ``monitor.rate.rate_alert`` on an ``EventLog``.
* order ledger SQLite (``settings.execution.ledger_file``) opened ``mode=ro``: strategy, original stop/target.
* Alpaca (paper by default): ``execution.alpaca_broker.AlpacaBroker`` read methods (account, positions, orders);
  ``GET /v2/account/portfolio/history`` on the paper host only. Nothing here submits, replaces or cancels.
* kill switch ``settings.risk.kill_switch_file``: status, and ``risk.killswitch.trip`` (there is no clear).
* journal ``data/journal/<date>.md`` (``agent.journal.journal_path``).
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------------------------------------ constants
NY = ZoneInfo("America/New_York")
CACHE_TTL_S = 60.0  # DuckDB results and Alpaca portfolio history are reused for this long
CACHE_MAX_ITEMS = 256  # distinct cached results (one per charted symbol, period, table); oldest dropped first
BROKER_TTL_S = 15.0  # account / positions / open orders: the page polls, Alpaca should not be hammered
DUCK_RETRIES = 3  # read-only open attempts before falling back to the cache (DuckDB has no lock timeout)
DUCK_RETRY_WAIT_S = 0.15
SQLITE_TIMEOUT_S = 2.0
HTTP_TIMEOUT_S = 10.0
PAPER_API_HOST = "https://paper-api.alpaca.markets"
PORTFOLIO_HISTORY_PATH = "/v2/account/portfolio/history"
MARKET_SYMBOL = "SPY"
JOURNAL_MAX_BYTES = 512 * 1024
RUN_FILE_MAX_BYTES = 32 * 1024 * 1024
MAX_ALERTS = 500
MAX_HOURS = 24 * 30
MAX_CHART_DAYS = 3650
DEFAULT_CHART_DAYS = 180
SMA_FAST, SMA_SLOW = 20, 50
BREADTH_HISTORY_SESSIONS = 250
BREADTH_KEYS = ("pct_above_50", "pct_above_200", "ratio_10d", "up4_count", "down4_count", "new_highs", "new_lows",
                "n_symbols")
CLIENT_ORDER_PREFIX = "swing"
CLIENT_ORDER_RE = re.compile(r"^swing-(?P<strategy>[a-z0-9_]+)-(?P<symbol>.+)-(?P<day>\d{8})-(?P<side>long|short)$")
EQUITY_PERIODS: dict[str, int | None] = {"1M": 31, "3M": 92, "6M": 183, "1Y": 366, "ALL": None}
ALPACA_PERIODS = {"1M": "1M", "3M": "3M", "6M": "6M", "1Y": "1A", "ALL": "5A"}
ORDER_STATUSES = ("open", "closed")
SHADOW_GROUPS = ("strategy", "regime")
RATINGS = ("useful", "noise", "traded")
TAKEN_STATUSES = frozenset({"submitted", "duplicate", "done"})
SENT_LEDGER_STATUSES = frozenset(
    {"accepted", "new", "partially_filled", "filled", "canceled", "expired", "replaced", "pending_new", "held"}
)
STOP_TYPES = frozenset({"stop", "stop_limit", "trailing_stop"})
VETO_DECISIONS = frozenset({"reject", "needs_more_info"})  # agent.review decisions that stop an entry
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SYMBOL_RE = re.compile(r"^[A-Z.\-]{1,10}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,127}$")
RUN_NAME_RE = re.compile(r"^(?P<stem>[A-Za-z0-9][A-Za-z0-9_.\-]{0,127})\.json$")
DATE_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.(json|md)$")


# ------------------------------------------------------------------------------------------------ envelope
def ok(data: Any, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True, "data": data}
    out.update({k: v for k, v in extra.items() if v})
    return out


def unavailable(reason: str) -> dict[str, Any]:
    return {"ok": False, "unavailable": str(reason)}


class Unavailable(Exception):
    """Raised inside a reader to turn the whole answer into ``unavailable(reason)``."""


class BadRequest(ValueError):
    """Invalid query or body; the server answers 400 with the message."""


# ------------------------------------------------------------------------------------------------ validation
def parse_date(value: str | None, name: str = "date") -> date | None:
    """``YYYY-MM-DD`` or None (absent / empty); BadRequest otherwise."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise BadRequest(f"{name} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise BadRequest(f"{name} is not a calendar date") from exc


def parse_symbol(value: str) -> str:
    sym = (value or "").strip().upper()
    if not SYMBOL_RE.match(sym):
        raise BadRequest("symbol must match ^[A-Z.-]{1,10}$")
    return sym


def parse_event_id(value: str) -> str:
    if not isinstance(value, str) or not EVENT_ID_RE.match(value):
        raise BadRequest("event_id must be 1-128 characters of A-Z a-z 0-9 : _ . -")
    return value


def parse_int(value: str | None, name: str, default: int, lo: int, hi: int) -> int:
    if value is None or value == "":
        return default
    if not re.fullmatch(r"\d{1,7}", value):
        raise BadRequest(f"{name} must be a positive integer")
    n = int(value)
    if not lo <= n <= hi:
        raise BadRequest(f"{name} must be between {lo} and {hi}")
    return n


def parse_choice(value: str | None, name: str, choices: Iterable[str], default: str, *, upper: bool = False) -> str:
    if value is None or value == "":
        return default
    v = value.upper() if upper else value.lower()
    allowed = tuple(choices)
    if v not in allowed:
        raise BadRequest(f"{name} must be one of {', '.join(allowed)}")
    return v


# ------------------------------------------------------------------------------------------------ JSON helpers
def clean(obj: Any) -> Any:
    """Recursively JSON-safe: NaN/inf -> None, dates -> ISO, enums -> value, sets/tuples -> lists."""
    if obj is None or isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Mapping):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [clean(v) for v in obj]
    value = getattr(obj, "value", None)  # enums
    if isinstance(value, (str, int, float)):
        return clean(value)
    if hasattr(obj, "item"):  # numpy scalars
        try:
            return clean(obj.item())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(obj, "model_dump"):
        return clean(obj.model_dump(mode="json"))
    return str(obj)


def fnum(value: Any, digits: int | None = None) -> float | None:
    """Float or None (None for missing, unparsable, NaN or inf)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return round(f, digits) if digits is not None else f


def iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_dt(value: Any) -> datetime | None:
    """ISO text / datetime -> aware datetime (UTC assumed when naive); None when unparsable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def max_drawdown_pct(values: list[float]) -> float | None:
    peak = None
    worst = 0.0
    for v in values:
        if v is None or v <= 0:
            continue
        peak = v if peak is None else max(peak, v)
        worst = min(worst, v / peak - 1.0)
    return None if peak is None else round(worst * 100.0, 3)


def pct_change(first: float | None, last: float | None) -> float | None:
    if first in (None, 0) or last is None:
        return None
    return round((last / first - 1.0) * 100.0, 3)


def rebase(account: list[dict[str, Any]], spy: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Both series rebased to 100 at the first common date; stats over the common window."""
    a = {p["t"]: p["equity"] for p in account if p.get("equity")}
    s = {p["t"]: p["close"] for p in spy if p.get("close")}
    common = sorted(set(a) & set(s))
    normalized: list[dict[str, Any]] = []
    if common:
        a0, s0 = a[common[0]], s[common[0]]
        normalized = [
            {"t": t, "account": round(a[t] / a0 * 100.0, 4), "spy": round(s[t] / s0 * 100.0, 4)} for t in common
        ]
    acct_vals = [a[t] for t in common] if common else [p["equity"] for p in account if p.get("equity")]
    spy_vals = [s[t] for t in common] if common else [p["close"] for p in spy if p.get("close")]
    stats = {
        "return_pct": pct_change(acct_vals[0], acct_vals[-1]) if acct_vals else None,
        "spy_return_pct": pct_change(spy_vals[0], spy_vals[-1]) if spy_vals else None,
        "max_drawdown_pct": max_drawdown_pct(acct_vals) if acct_vals else None,
        "spy_max_drawdown_pct": max_drawdown_pct(spy_vals) if spy_vals else None,
        "common_start": common[0] if common else None,
        "common_end": common[-1] if common else None,
    }
    if stats["return_pct"] is not None and stats["spy_return_pct"] is not None:
        stats["excess_return_pct"] = round(stats["return_pct"] - stats["spy_return_pct"], 3)
    return normalized, stats


def sma_series(points: list[tuple[str, float]], window: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    total = 0.0
    for i, (t, c) in enumerate(points):
        total += c
        if i >= window:
            total -= points[i - window][1]
        if i >= window - 1:
            out.append({"t": t, "v": round(total / window, 4)})
    return out


def parse_client_order_id(coid: str | None) -> dict[str, str] | None:
    """``swing-<strategy>-<SYMBOL>-<YYYYMMDD>-<side>`` -> parts (None for anything else, e.g. ``rearm-*``)."""
    if not coid:
        return None
    m = CLIENT_ORDER_RE.match(str(coid))
    if not m:
        return None
    day = m.group("day")
    return {
        "strategy": m.group("strategy"),
        "symbol": m.group("symbol"),
        "as_of": f"{day[:4]}-{day[4:6]}-{day[6:]}",
        "side": m.group("side"),
    }


def client_order_id_for(strategy: str, symbol: str, as_of: str, side: str) -> str:
    """Same id ``risk.sizing.make_client_order_id`` builds for a signal (used to join signals to orders)."""
    try:
        from swing_engine.core.models import Signal
        from swing_engine.risk.sizing import make_client_order_id

        sig = Signal(strategy=strategy, symbol=symbol, side=side or "long", as_of=date.fromisoformat(as_of),
                     entry=1.0, stop=0.5)
        return make_client_order_id(sig)
    except Exception:  # noqa: BLE001 - fall back to the documented format
        return f"{CLIENT_ORDER_PREFIX}-{strategy}-{symbol}-{as_of.replace('-', '')}-{side or 'long'}"


def _redact(text: str, limit: int = 200) -> str:
    text = " ".join(str(text).split())
    try:
        from swing_engine.data._http import redact_secrets

        text = redact_secrets(text)
    except Exception:  # noqa: BLE001
        pass
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _err(exc: BaseException) -> str:
    return _redact(f"{type(exc).__name__}: {exc}")


def _to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, Mapping):
        return dict(obj)
    try:
        return dict(vars(obj))
    except TypeError:
        return {}


def _text(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


def _ny_date(value: Any) -> str | None:
    dt = parse_dt(value)
    return dt.astimezone(NY).date().isoformat() if dt else None


def _safe_url(url: Any) -> str | None:
    """Only http(s) links reach the page (an event's url is third-party text)."""
    if not isinstance(url, str):
        return None
    u = url.strip()
    return u if u.lower().startswith(("https://", "http://")) and len(u) <= 2048 else None


def _resolve(path: str | Path) -> Path:
    from swing_engine.core.config import ROOT

    p = Path(path).expanduser()
    return p if p.is_absolute() else ROOT / p


def sqlite_ro(path: Path) -> sqlite3.Connection:
    """Read-only SQLite connection (``mode=ro``): never creates the file, never takes a write lock."""
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=SQLITE_TIMEOUT_S,
                          check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _sqlite_tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


@dataclass
class _Cached:
    value: Any
    at: float  # monotonic
    wall: datetime


class TTLCache:
    """Thread-safe key -> value cache with per-read TTL; the oldest entries go past ``max_items``."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, max_items: int = CACHE_MAX_ITEMS) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, _Cached] = {}
        self.clock = clock
        self.max_items = max_items

    def get(self, key: str, ttl: float) -> Any | None:
        with self._lock:
            hit = self._items.get(key)
        return hit.value if hit is not None and self.clock() - hit.at < ttl else None

    def entry(self, key: str) -> _Cached | None:
        with self._lock:
            return self._items.get(key)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = _Cached(value, self.clock(), datetime.now(UTC))
            while len(self._items) > self.max_items:
                self._items.pop(next(iter(self._items)))


class DuckReader:
    """Short-lived read-only DuckDB connections with a result cache.

    DuckDB has one writer per file and a read-only open fails while another process holds the write lock (it does
    not wait). Each ``read`` reuses a result younger than ``ttl``; otherwise it opens the file ``read_only`` (a few
    quick attempts), runs ``fn(con)``, and closes it at once so the nightly or a backfill is never blocked for
    longer than one query. When the file stays locked the last good result for that key is returned with a
    ``stale`` note; with nothing cached the reader raises ``Unavailable``.
    """

    def __init__(self, path: Path, *, ttl: float = CACHE_TTL_S, retries: int = DUCK_RETRIES,
                 retry_wait: float = DUCK_RETRY_WAIT_S, connect: Callable[..., Any] | None = None,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.path = path
        self.ttl = ttl
        self.retries = max(1, retries)
        self.retry_wait = retry_wait
        self._connect = connect
        self.cache = TTLCache(clock)
        self.sleep = sleep
        self._io = threading.Lock()

    def _open(self) -> Any:
        connect = self._connect
        if connect is None:
            import duckdb

            connect = duckdb.connect
        return connect(str(self.path), read_only=True)

    def read(self, key: str, fn: Callable[[Any], Any]) -> tuple[Any, dict[str, Any] | None]:
        fresh = self.cache.get(key, self.ttl)
        if fresh is not None:
            return fresh, None
        if not self.path.exists():
            raise Unavailable(f"no market store at {self.path} yet (run `swing ingest`, then the nightly)")
        with self._io:
            con, error = None, None
            for attempt in range(self.retries):
                try:
                    con = self._open()
                    break
                except Exception as exc:  # noqa: BLE001 - duckdb.IOException / ConnectionException on a lock
                    error = exc
                    if attempt + 1 < self.retries:
                        self.sleep(self.retry_wait)
            if con is None:
                reason = self._lock_reason(error)
                hit = self.cache.entry(key)
                if hit is not None:
                    age = round(self.cache.clock() - hit.at, 1)
                    return hit.value, {"reason": reason, "cached_at": iso_utc(hit.wall), "age_s": age}
                raise Unavailable(f"{reason}; no cached copy yet, retry when it finishes")
            try:
                try:
                    con.execute("SET TimeZone = 'America/New_York'")
                except Exception:  # noqa: BLE001 - ICU missing: dates are still read as stored
                    pass
                value = fn(con)
            except Unavailable:
                raise
            except Exception as exc:  # noqa: BLE001
                raise Unavailable(f"store query failed: {_err(exc)}") from exc
            finally:
                try:
                    con.close()
                except Exception:  # noqa: BLE001
                    pass
        self.cache.put(key, value)
        return value, None

    def _lock_reason(self, error: BaseException | None) -> str:
        text = str(error or "")
        if "lock" in text.lower() or "different configuration" in text.lower():
            return ("the market store is locked by a writer (a backfill, an ingest or the nightly is running); "
                    "showing the last good copy")
        return f"the market store could not be opened read-only ({_err(error) if error else 'unknown error'})"


def duck_has_table(con: Any, name: str) -> bool:
    row = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?", [name]
    ).fetchone()
    return bool(row and row[0])


def duck_columns(con: Any, name: str) -> list[str]:
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'main' AND table_name = ? "
        "ORDER BY ordinal_position", [name]
    ).fetchall()
    return [r[0] for r in rows]


class RunFiles:
    """``<store dir>/runs/<kind>/<date>.json`` reader with an mtime-keyed parse cache."""

    def __init__(self, settings: Any, root: Path | None = None) -> None:
        self.root = root or self._root(settings)
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[int, int, Any]] = {}

    @staticmethod
    def _root(settings: Any) -> Path:
        try:
            from swing_engine.execution.autopilot import run_path

            return run_path(settings, "signals", date(2000, 1, 1)).parent.parent
        except Exception:  # noqa: BLE001 - same layout as execution.autopilot.runs_dir
            return _resolve(settings.data.store_path).parent / "runs"

    def dir(self, kind: str) -> Path:
        return self.root / kind

    def path(self, kind: str, day: date) -> Path:
        return self.dir(kind) / f"{day.isoformat()}.json"

    def dates(self, kind: str) -> list[str]:
        """Dates with a file, newest first."""
        d = self.dir(kind)
        try:
            names = os.listdir(d)
        except OSError:
            return []
        out = []
        for n in names:
            m = DATE_FILE_RE.match(n)
            if m and m.group(2) == "json":
                out.append(m.group(1))
        return sorted(out, reverse=True)

    def load_path(self, path: Path) -> Any | None:
        try:
            st = path.stat()
        except OSError:
            return None
        if st.st_size > RUN_FILE_MAX_BYTES:
            raise Unavailable(f"{path.name} is larger than {RUN_FILE_MAX_BYTES // (1024 * 1024)} MB; not loaded")
        key = str(path)
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
            return hit[2]
        try:
            value = json.loads(path.read_text(encoding="utf-8") or "null")
        except (OSError, ValueError) as exc:
            raise Unavailable(f"{path.parent.name}/{path.name} is unreadable ({_err(exc)})") from exc
        with self._lock:
            self._cache[key] = (st.st_mtime_ns, st.st_size, value)
        return value

    def load(self, kind: str, day: date | str) -> Any | None:
        d = day if isinstance(day, date) else date.fromisoformat(day)
        return self.load_path(self.path(kind, d))

    def latest(self, kind: str, on_or_before: date | None = None) -> tuple[str | None, Any]:
        for d in self.dates(kind):
            if on_or_before is not None and d > on_or_before.isoformat():
                continue
            try:
                value = self.load(kind, d)
            except Unavailable:
                continue
            if value is not None:
                return d, value
        return None, None


# ============================================================================================== live provider
class LiveData:
    """Reads the engine's own records. Same method names as ``demo.DemoData``; each returns an envelope.

    ``broker_factory`` / ``http_get`` / ``now`` / ``duck_connect`` are injectable so tests never touch the
    network. ``http_get(url, params, headers, timeout) -> (status_code, json_or_None)``.
    """

    demo = False

    def __init__(
        self,
        settings_path: str | Path | None = None,
        *,
        settings: Any | None = None,
        secrets: Any | None = None,
        broker_factory: Callable[[], Any] | None = None,
        http_get: Callable[..., tuple[int, Any]] | None = None,
        journal_dirs: list[Path] | None = None,
        now: Callable[[], datetime] | None = None,
        duck_connect: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        from swing_engine.core.config import ROOT, load_settings

        self.settings_path = self._settings_file(settings_path, ROOT)
        self.settings = settings if settings is not None else load_settings(str(self.settings_path))
        self._secrets = secrets
        self._secrets_error: str | None = None
        if self._secrets is None:
            try:
                from swing_engine.core.config import load_secrets

                self._secrets = load_secrets()
            except Exception as exc:  # noqa: BLE001 - a malformed .env must not take the page down
                self._secrets_error = f"secrets could not be loaded ({type(exc).__name__})"
        s = self.settings
        self.store_path = _resolve(s.data.store_path)
        self.event_log_path = _resolve(s.data.event_log_path)
        self.ledger_path = _resolve(s.execution.ledger_file)
        self.kill_path = _resolve(s.risk.kill_switch_file)
        self.runs = RunFiles(s)
        dirs = journal_dirs if journal_dirs is not None else [ROOT / "data" / "journal", self.store_path.parent / "journal"]
        seen: list[Path] = []
        for d in dirs:
            if d not in seen:
                seen.append(d)
        self.journal_dirs = seen
        self.duck = DuckReader(self.store_path, connect=duck_connect, clock=clock, sleep=sleep)
        self.cache = TTLCache(clock)
        self._broker_factory = broker_factory or self._default_broker
        self._http_get = http_get or _httpx_get
        self._now = now or (lambda: datetime.now(UTC))
        self._broker_obj: Any | None = None
        self._broker_lock = threading.Lock()
        self._hold_cache: dict[str, int | None] = {}

    @staticmethod
    def _settings_file(path: str | Path | None, root: Path) -> Path:
        if path is None or str(path) == "":
            return root / "config" / "settings.yaml"
        p = Path(path).expanduser()
        if p.is_absolute() or p.exists():
            return p.resolve()
        return root / p

    # ------------------------------------------------------------------------------------------ shared
    @property
    def secrets(self) -> Any:
        """The loaded ``Secrets`` (the server scrubs every value from responses; nothing here returns them)."""
        return self._secrets

    @property
    def paper(self) -> bool:
        return bool(getattr(self._secrets, "alpaca_paper", True))

    @property
    def mode(self) -> str:
        return "PAPER" if self.paper else "LIVE"

    def _has_alpaca_keys(self) -> bool:
        sec = self._secrets
        return bool(sec is not None and sec.alpaca_api_key and sec.alpaca_secret_key)

    def _default_broker(self) -> Any:
        if not self._has_alpaca_keys():
            raise Unavailable(self._secrets_error or "no Alpaca keys in .env (ALPACA_API_KEY / ALPACA_SECRET_KEY)")
        from swing_engine.execution.alpaca_broker import AlpacaBroker, LiveTradingBlocked

        try:
            return AlpacaBroker(secrets=self._secrets)
        except LiveTradingBlocked as exc:
            raise Unavailable("ALPACA_PAPER is false and SWING_ALLOW_LIVE is not 'yes': the live account is not "
                              "read") from exc

    def _broker(self) -> Any:
        with self._broker_lock:
            if self._broker_obj is not None:
                return self._broker_obj
            failed = self.cache.get("broker_error", 60.0)
            if failed is not None:
                raise Unavailable(failed)
            try:
                self._broker_obj = self._broker_factory()
            except Unavailable as exc:
                self.cache.put("broker_error", str(exc))
                raise
            except Exception as exc:  # noqa: BLE001
                reason = f"Alpaca broker unavailable ({_err(exc)})"
                self.cache.put("broker_error", reason)
                raise Unavailable(reason) from exc
            return self._broker_obj

    def _broker_read(self, key: str, what: str, fn: Callable[[Any], Any], ttl: float = BROKER_TTL_S) -> Any:
        hit = self.cache.get(key, ttl)
        if hit is not None:
            return hit
        broker = self._broker()
        try:
            value = fn(broker)
        except Unavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise Unavailable(f"Alpaca {what} failed ({_err(exc)})") from exc
        self.cache.put(key, value)
        return value

    def _account(self) -> dict[str, Any]:
        def read(b: Any) -> dict[str, Any]:
            acct = b.account() if callable(getattr(b, "account", None)) else _to_dict(b.client.get_account())
            return {k: fnum(acct.get(k)) for k in ("equity", "last_equity", "cash", "buying_power",
                                                    "portfolio_value")} | {"status": _text(acct.get("status"))}

        return self._broker_read("account", "account read", read)

    def _raw_positions(self) -> list[dict[str, Any]]:
        return self._broker_read("positions", "positions read",
                                 lambda b: [_to_dict(p) for p in b.client.get_all_positions()])

    def _open_orders(self) -> list[dict[str, Any]]:
        return self._broker_read("open_orders", "open orders read",
                                 lambda b: [_to_dict(o) for o in b.open_orders()])

    def _closed_orders(self, limit: int) -> list[dict[str, Any]]:
        def read(b: Any) -> list[dict[str, Any]]:
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=500, nested=True)
            return [_to_dict(o) for o in b.client.get_orders(req)]

        return self._broker_read("closed_orders", "closed orders read", read, ttl=CACHE_TTL_S)[:limit]

    # ------------------------------------------------------------------------------------------ ledger
    def _ledger_rows(self) -> list[dict[str, Any]]:
        """``state/orders.sqlite`` rows, oldest first (intent / broker JSON parsed); [] when absent."""
        hit = self.cache.get("ledger", 5.0)
        if hit is not None:
            return hit
        rows: list[dict[str, Any]] = []
        if self.ledger_path.exists():
            con = sqlite_ro(self.ledger_path)
            try:
                if "orders" in _sqlite_tables(con):
                    for r in con.execute("SELECT * FROM orders ORDER BY created_at ASC").fetchall():
                        d = dict(r)
                        for src, dst in (("intent_json", "intent"), ("broker_json", "broker")):
                            try:
                                d[dst] = json.loads(d.pop(src) or "null") or {}
                            except ValueError:
                                d[dst] = {}
                        rows.append(d)
            finally:
                con.close()
        self.cache.put("ledger", rows)
        return rows

    @staticmethod
    def _broker_fill(row: Mapping[str, Any]) -> tuple[str | None, float | None]:
        b = row.get("broker") or {}
        raw = b.get("raw", b) if isinstance(b, Mapping) else {}
        if not isinstance(raw, Mapping):
            raw = {}
        return raw.get("filled_at"), fnum(raw.get("filled_avg_price"))

    def _ledger_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        rows = [r for r in self._ledger_rows() if r.get("symbol") == symbol
                and _text(r.get("status")) not in ("canceled", "expired", "rejected", "error")]
        # newest live row: an older closed trade's `filled` row must not beat tonight's `accepted` entry
        # (statuses only advance at the next reconcile)
        return rows[-1] if rows else None

    # ------------------------------------------------------------------------------------------ health
    def health(self) -> dict[str, Any]:
        from swing_engine import __version__

        return ok({
            "version": __version__, "settings_path": str(self.settings_path),
            "settings_found": self.settings_path.exists(), "store_path": str(self.store_path),
            "store_exists": self.store_path.exists(), "event_log_path": str(self.event_log_path),
            "runs_dir": str(self.runs.root), "demo": False, "mode": self.mode,
            "alpaca_keys_present": self._has_alpaca_keys(),
        })

    # ------------------------------------------------------------------------------------------ summary
    def summary(self) -> dict[str, Any]:
        partial: dict[str, str] = {}
        account = self._summary_account(partial)
        data = {
            "mode": self.mode,
            "account": account,
            "kill_switch": self._kill_status(),
            "nightly": self._nightly(partial),
            "monitor": self._monitor(partial),
            "clock": self._clock(partial),
            "broker": {"name": "alpaca", "paper": self.paper, "keys_present": self._has_alpaca_keys(),
                       "configured": getattr(self.settings.execution, "broker", None)},
            "generated_at": iso_utc(self._now()),
        }
        return ok(data, partial=partial)

    def _summary_account(self, partial: dict[str, str]) -> dict[str, Any]:
        empty = {k: None for k in ("equity", "last_equity", "cash", "buying_power", "day_pl", "day_pl_pct")}
        try:
            a = self._account()
            source, as_of = f"alpaca {'paper' if self.paper else 'live'}", None
        except Unavailable as exc:
            snap = self._audit_snapshots()
            if not snap:
                partial["account"] = str(exc)
                return empty | {"source": None, "unavailable": str(exc)}
            as_of, a = snap[-1][0], snap[-1][1]
            source = f"autopilot audit {as_of} ({snap[-1][2]}); broker not read: {exc}"
            partial["account"] = source
        eq, last = fnum(a.get("equity")), fnum(a.get("last_equity"))
        # A brand-new account reports last_equity 0 (no previous close): there is no day change to show.
        day_pl = round(eq - last, 2) if eq is not None and last is not None and last > 0 else None
        return {
            "equity": eq, "last_equity": last, "cash": fnum(a.get("cash")), "buying_power": fnum(a.get("buying_power")),
            "day_pl": day_pl, "day_pl_pct": round((eq / last - 1) * 100, 3) if day_pl is not None else None,
            "source": source, "as_of": as_of,
        }

    def _audit_snapshots(self) -> list[tuple[str, dict[str, Any], str]]:
        """(date, account, broker) per autopilot audit file, oldest first; alpaca runs win over paper_sim."""
        out = []
        for d in sorted(self.runs.dates("autopilot")):
            try:
                payload = self.runs.load("autopilot", d) or {}
            except Unavailable:
                continue
            runs = payload.get("runs") if isinstance(payload, dict) else None
            best = None
            for run in runs or []:
                acct = run.get("account") or {}
                if fnum(acct.get("equity")) is None:
                    continue
                if best is None or run.get("broker") == "alpaca" or best.get("broker") != "alpaca":
                    best = run
            if best is not None:
                out.append((d, best["account"], str(best.get("broker") or "?")))
        return out

    def _kill_status(self) -> dict[str, Any]:
        try:
            tripped = self.kill_path.exists()
        except OSError:
            tripped = True  # fail closed, like risk.killswitch.is_tripped
        reason = ""
        if tripped:
            try:
                reason = self.kill_path.read_text(encoding="utf-8", errors="replace").strip()[-500:]
            except OSError:
                reason = ""
        return {"tripped": tripped, "path": str(self.kill_path), "reason": _redact(reason, 500)}

    def _nightly(self, partial: dict[str, str]) -> dict[str, Any]:
        try:
            day, report = self.runs.latest("nightly")
        except Unavailable as exc:
            day, report = None, None
            partial["nightly"] = str(exc)
        if not isinstance(report, dict):
            reason = partial.get("nightly") or "no nightly report yet (runs/nightly/<date>.json is written by `swing nightly`)"
            partial["nightly"] = reason
            return {"as_of": None, "finished_at": None, "ok": None, "steps": [], "unavailable": reason}
        steps = [{"name": s.get("name"), "status": s.get("status"), "detail": _redact(s.get("detail") or "", 400),
                  "elapsed_s": fnum(s.get("elapsed_s"))} for s in report.get("steps") or [] if isinstance(s, dict)]
        failed = any(s["status"] == "fail" for s in steps)
        return {
            "as_of": report.get("as_of") or day, "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "ok": False if failed else (True if report.get("finished_at") else None),  # None: still running
            "dry_run": report.get("dry_run"), "provider": report.get("provider"),
            "elapsed_s": fnum(report.get("elapsed_s")), "steps": steps,
            "regime": (report.get("regime") or {}).get("regime") if isinstance(report.get("regime"), dict) else None,
        }

    def _monitor(self, partial: dict[str, str]) -> dict[str, Any]:
        empty: dict[str, Any] = {"last_event_at": None, "feeds": {}, "alerts_24h": None}
        if not self.event_log_path.exists():
            reason = "no event log yet (the monitor has not run with this settings file)"
            partial["monitor"] = reason
            return empty | {"unavailable": reason}
        try:
            con = sqlite_ro(self.event_log_path)
            try:
                tables = _sqlite_tables(con)
                if "events" not in tables:
                    raise Unavailable("event log has no events table yet")
                feeds = {r[0]: r[1] for r in con.execute(
                    "SELECT source, max(ts_received) FROM events GROUP BY source ORDER BY source").fetchall()}
                since = (self._now() - timedelta(hours=24)).astimezone(UTC).isoformat()
                alerts = delivered = None
                if "alerts" in tables:
                    alerts, delivered = con.execute(
                        "SELECT count(*), coalesce(sum(delivered), 0) FROM alerts WHERE ts >= ?", [since]).fetchone()
            finally:
                con.close()
        except (sqlite3.Error, Unavailable) as exc:
            reason = f"event log unreadable ({_err(exc)})"
            partial["monitor"] = reason
            return empty | {"unavailable": reason}
        feeds_iso = {k: iso_utc(parse_dt(v)) for k, v in feeds.items() if v}
        last = max((parse_dt(v) for v in feeds.values() if v), default=None)
        return {"last_event_at": iso_utc(last), "feeds": feeds_iso, "alerts_24h": delivered,
                "alerts_24h_total": alerts}

    def _clock(self, partial: dict[str, str]) -> dict[str, Any]:
        try:
            from swing_engine.data import calendar as cal

            name = getattr(self.settings.data, "calendar", "NYSE") or "NYSE"
            now = self._now()
            is_open = bool(cal.is_open(now, name))
            nxt_open = cal.next_open(now, name)
            day = now.astimezone(NY).date() if is_open else nxt_open.date()
            bounds = cal.session_bounds(day, name)
            return {"is_open": is_open, "next_open": iso_utc(nxt_open.to_pydatetime()),
                    "next_close": iso_utc(bounds[1].to_pydatetime()) if bounds else None,
                    "source": f"{name} calendar"}
        except Exception as exc:  # noqa: BLE001
            reason = f"market calendar unavailable ({_err(exc)})"
            partial["clock"] = reason
            return {"is_open": None, "next_open": None, "next_close": None, "unavailable": reason}

    # ------------------------------------------------------------------------------------------ regime
    def regime(self, day: date | None = None) -> dict[str, Any]:
        partial: dict[str, str] = {}
        available = self.runs.dates("regime")
        payload, used = None, None
        try:
            used, payload = self.runs.latest("regime", day)
        except Unavailable as exc:
            partial["state"] = str(exc)
        if payload is None:  # fall back to the nightly report's copy (NightlyReport.regime / scan step data)
            nd, report = self.runs.latest("nightly", day)
            if isinstance(report, dict):
                payload = report.get("regime") if isinstance(report.get("regime"), dict) else None
                if payload is None:
                    scan = next((s for s in report.get("steps") or [] if s.get("name") == "scan"), None)
                    sdata = (scan or {}).get("data") or {}
                    if sdata.get("market_regime") or sdata.get("allowed") is not None:
                        payload = {"as_of": report.get("as_of"), "regime": sdata.get("market_regime"),
                                   "market_state": sdata.get("regime") or {}, "allowed": sdata.get("allowed"),
                                   "blocked": sdata.get("blocked")}
                used = nd if payload is not None else None
        state = self._regime_state(payload, used) if isinstance(payload, dict) else None
        if state is None:
            partial.setdefault("state", "no regime saved yet (the nightly scan writes runs/regime/<date>.json)")
        allowed = payload.get("allowed") if isinstance(payload, dict) else None
        if isinstance(payload, dict) and not isinstance(allowed, dict):
            partial["allowed"] = "the playbook router did not run (every enabled strategy at full risk)"
        try:
            history, stale = self._breadth_history(day)
        except Unavailable as exc:
            history, stale = [], None
            partial["breadth_history"] = str(exc)
        if state is None and not history:
            return unavailable("; ".join(partial.values()))
        return ok({
            "date": used, "state": state, "allowed": allowed if isinstance(allowed, dict) else None,
            "blocked": payload.get("blocked") if isinstance(payload, dict) else None,
            "breadth_history": history, "available_dates": available[:120],
        }, stale=stale, partial=partial)

    @staticmethod
    def _regime_state(payload: dict[str, Any], used: str | None) -> dict[str, Any]:
        ms = payload.get("market_state")
        ms = ms if isinstance(ms, dict) else {}

        def first(*keys: str) -> Any:
            for k in keys:
                if ms.get(k) is not None:
                    return ms[k]
            return None

        inputs = ms.get("inputs") if isinstance(ms.get("inputs"), dict) else {}
        pool = {**ms, **inputs, **(ms["breadth"] if isinstance(ms.get("breadth"), dict) else {})}
        breadth_values = {k: fnum(pool.get(k), 4) for k in BREADTH_KEYS if k in pool}
        breadth = ms.get("breadth")
        if isinstance(breadth, dict):
            breadth = breadth.get("state") or breadth.get("label")
        notes = first("notes", "reasons", "rationale", "explanation")
        if isinstance(notes, str):
            notes = [notes]
        return {
            "as_of": payload.get("as_of") or ms.get("as_of") or used,
            "regime": payload.get("regime") or ms.get("regime"),
            "spy_trend": first("spy_trend", "trend", "trend_state", "market_trend", "market_trend_state"),
            "vol_regime": first("vol_regime", "volatility", "vol_state", "market_vol_regime"),
            "breadth": breadth,
            "breadth_values": breadth_values,
            "notes": [str(n) for n in notes] if isinstance(notes, list) else [],
            "inputs": inputs,
        }

    def _breadth_history(self, day: date | None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        def q(con: Any) -> list[dict[str, Any]]:
            if not duck_has_table(con, "breadth"):
                raise Unavailable("no breadth table in the store yet (the nightly features step writes it)")
            cols = duck_columns(con, "breadth")
            date_col = next((c for c in ("date", "session", "ts") if c in cols), None)
            if date_col is None:
                raise Unavailable("breadth table has no date column")
            want = [c for c in ("pct_above_50", "pct_above_200", "ratio_10d", "new_highs", "new_lows", "n_symbols")
                    if c in cols]
            sel = ", ".join(f'"{c}"' for c in want)
            rows = con.execute(
                f'SELECT CAST("{date_col}" AS DATE) AS d{", " + sel if sel else ""} FROM breadth '
                f'ORDER BY d DESC LIMIT {BREADTH_HISTORY_SESSIONS * 4}'
            ).fetchall()
            out = []
            for r in reversed(rows):
                item = {"date": r[0].isoformat()}
                item.update({c: fnum(v, 4) for c, v in zip(want, r[1:], strict=True)})
                out.append(item)
            return out

        rows, stale = self.duck.read("breadth", q)
        if day is not None:
            rows = [r for r in rows if r["date"] <= day.isoformat()]
        return rows[-BREADTH_HISTORY_SESSIONS:], stale

    # ------------------------------------------------------------------------------------------ equity
    def equity(self, period: str = "6M") -> dict[str, Any]:
        notes: dict[str, str] = {}
        today = self._now().astimezone(NY).date()
        span = EQUITY_PERIODS.get(period)
        start = today - timedelta(days=span) if span else None
        account, source = [], None
        try:
            account = self._portfolio_history(period)
            source = "alpaca paper portfolio history"
        except Unavailable as exc:
            snaps = self._audit_snapshots()
            account = [{"t": d, "equity": fnum(a.get("equity"))} for d, a, _b in snaps]
            if account:
                source = "autopilot audit snapshots (one per nightly run)"
                notes["account"] = f"portfolio history not read: {exc}"
            else:
                notes["account"] = f"{exc}; no autopilot audit snapshots either"
        if start is not None:
            account = [p for p in account if p["t"] >= start.isoformat()]
        spy_from = start
        if account and (spy_from is None or account[0]["t"] > spy_from.isoformat()):
            spy_from = date.fromisoformat(account[0]["t"])
        stale = None
        try:
            spy, stale = self._closes(MARKET_SYMBOL, spy_from)
            if not spy:
                every, _ = self._closes(MARKET_SYMBOL, None)  # cached: same key as above
                if not every:
                    notes["spy"] = f"no {MARKET_SYMBOL} bars in the store (run `swing ingest`)"
                else:
                    notes["spy"] = (f"{MARKET_SYMBOL} bars in the store end {every[-1]['t']}, before this period's "
                                    f"first point {spy_from.isoformat() if spy_from else '?'}")
        except Unavailable as exc:
            spy = []
            notes["spy"] = str(exc)
        if not account and not spy:
            return unavailable("; ".join(f"{k}: {v}" for k, v in notes.items()))
        normalized, stats = rebase(account, spy)
        data = {"period": period, "account": account, "spy": spy, "normalized": normalized, "stats": stats,
                "account_source": source}
        if notes:
            data["unavailable"] = notes
        return ok(data, stale=stale, partial=notes)

    def _portfolio_history(self, period: str) -> list[dict[str, Any]]:
        key = f"history:{period}"
        hit = self.cache.get(key, CACHE_TTL_S)
        if hit is not None:
            return hit
        if not self._has_alpaca_keys():
            raise Unavailable(self._secrets_error or "no Alpaca keys in .env")
        if not self.paper:
            raise Unavailable("ALPACA_PAPER is false: portfolio history is read from the paper host only")
        sec = self._secrets
        headers = {"APCA-API-KEY-ID": sec.alpaca_api_key, "APCA-API-SECRET-KEY": sec.alpaca_secret_key,
                   "Accept": "application/json"}
        params = {"period": ALPACA_PERIODS[period], "timeframe": "1D"}
        try:
            status, body = self._http_get(PAPER_API_HOST + PORTFOLIO_HISTORY_PATH, params, headers, HTTP_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - network down, DNS, TLS
            raise Unavailable(f"Alpaca portfolio history request failed ({type(exc).__name__})") from exc
        if status != 200 or not isinstance(body, dict):
            raise Unavailable(f"Alpaca portfolio history returned HTTP {status}")
        stamps, equity = body.get("timestamp") or [], body.get("equity") or []
        out: dict[str, float] = {}
        for ts, eq in zip(stamps, equity, strict=False):
            v = fnum(eq)
            if v is None or v <= 0:
                continue  # before the account existed / no data
            try:
                d = datetime.fromtimestamp(int(ts), tz=UTC).astimezone(NY).date().isoformat()
            except (TypeError, ValueError, OverflowError, OSError):
                continue
            out[d] = round(v, 2)
        rows = [{"t": d, "equity": v} for d, v in sorted(out.items())]
        if not rows:
            raise Unavailable("Alpaca portfolio history has no equity points yet")
        self.cache.put(key, rows)
        return rows

    def _closes(self, symbol: str, since: date | None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        def q(con: Any) -> list[tuple[str, float]]:
            if not duck_has_table(con, "bars"):
                raise Unavailable("no bars table in the store yet (run `swing ingest`)")
            rows = con.execute(
                "SELECT CAST(ts AS DATE) AS d, close FROM bars WHERE symbol = ? ORDER BY ts", [symbol]
            ).fetchall()
            return [(r[0].isoformat(), float(r[1])) for r in rows if r[1] is not None]

        rows, stale = self.duck.read(f"closes:{symbol}", q)
        lo = since.isoformat() if since else ""
        return [{"t": d, "close": round(c, 4)} for d, c in rows if d >= lo], stale

    # ------------------------------------------------------------------------------------------ positions
    def positions(self) -> dict[str, Any]:
        try:
            raw = self._raw_positions()
        except Unavailable as exc:
            return unavailable(f"positions need the broker: {exc}")
        partial: dict[str, str] = {}
        try:
            orders = _flatten_orders(self._open_orders())
        except Unavailable as exc:
            orders = []
            partial["current_stop"] = str(exc)
        try:
            self._ledger_rows()
        except sqlite3.Error as exc:
            partial["ledger"] = f"order ledger unreadable ({_err(exc)})"
            self.cache.put("ledger", [])
        today = self._now().astimezone(NY).date()
        rows = [self._position_row(_to_dict(p), orders, today) for p in raw]
        rows.sort(key=lambda r: -(abs(r.get("market_value") or 0.0)))
        return ok(rows, source=f"alpaca {'paper' if self.paper else 'live'}", partial=partial)

    def _position_row(self, p: dict[str, Any], orders: list[dict[str, Any]], today: date) -> dict[str, Any]:
        symbol = str(p.get("symbol"))
        qty = fnum(p.get("qty")) or 0.0
        side_text = _text(p.get("side"))
        long = not (side_text.endswith("short") or qty < 0)
        avg = fnum(p.get("avg_entry_price"))
        current = fnum(p.get("current_price"))
        origin = self._origin(symbol)
        strategy, stop, target = origin.get("strategy"), origin.get("stop"), origin.get("target")
        exit_side = "sell" if long else "buy"
        legs = [o for o in orders if o.get("symbol") == symbol and _text(o.get("side")) == exit_side
                and _text(o.get("status")) not in ("filled", "canceled", "expired", "rejected", "replaced")]
        stop_legs = [fnum(o.get("stop_price")) for o in legs if _text(o.get("type") or o.get("order_type")) in STOP_TYPES]
        tp_legs = [fnum(o.get("limit_price")) for o in legs if _text(o.get("type") or o.get("order_type")) == "limit"]
        stop_legs = [s for s in stop_legs if s is not None]
        tp_legs = [t for t in tp_legs if t is not None]
        current_stop = (max(stop_legs) if long else min(stop_legs)) if stop_legs else None
        if target is None and tp_legs:
            target = min(tp_legs) if long else max(tp_legs)
        if strategy is None:
            for o in legs:
                parsed = parse_client_order_id(o.get("client_order_id") or o.get("_parent_client_order_id"))
                if parsed:
                    strategy = parsed["strategy"]
                    break
        initial = stop if stop is not None else current_stop
        rps = abs(avg - initial) if avg is not None and initial is not None else None
        r_mult = None
        if rps and current is not None and avg is not None:
            r_mult = round(((current - avg) if long else (avg - current)) / rps, 3)
        opened = origin.get("opened_at")
        return {
            "symbol": symbol, "side": "long" if long else "short", "qty": abs(qty), "avg_entry": avg,
            "current": current, "market_value": fnum(p.get("market_value")),
            "unrealized_pl": fnum(p.get("unrealized_pl")), "unrealized_plpc": fnum(p.get("unrealized_plpc")),
            "strategy": strategy, "stop": stop, "target": target, "current_stop": current_stop,
            "risk_per_share": round(rps, 4) if rps is not None else None, "r_multiple": r_mult,
            "days_held": self._sessions_held(opened, today), "max_hold_days": self._max_hold(strategy, origin),
            "opened_at": opened, "client_order_id": origin.get("client_order_id"),
            "origin": origin.get("source"),
        }

    def _origin(self, symbol: str) -> dict[str, Any]:
        """Strategy, original stop/target, open time for a held symbol: the order ledger first, else the newest
        intents run file that sized it."""
        row = self._ledger_for_symbol(symbol)
        if row is not None:
            intent = row.get("intent") or {}
            filled_at, _px = self._broker_fill(row)
            parsed = parse_client_order_id(row.get("client_order_id")) or {}
            return {"strategy": row.get("strategy") or parsed.get("strategy"), "stop": fnum(intent.get("stop")),
                    "target": fnum(intent.get("target")), "opened_at": filled_at or row.get("created_at"),
                    "client_order_id": row.get("client_order_id"), "as_of": parsed.get("as_of"), "source": "ledger"}
        for d in self.runs.dates("intents")[:30]:
            try:
                intents = self.runs.load("intents", d) or []
            except Unavailable:
                continue
            for it in intents if isinstance(intents, list) else []:
                if isinstance(it, dict) and it.get("symbol") == symbol:
                    return {"strategy": it.get("strategy"), "stop": fnum(it.get("stop")),
                            "target": fnum(it.get("target")), "opened_at": None,
                            "client_order_id": it.get("client_order_id"), "as_of": d, "source": f"intents {d}"}
        return {"source": None}

    def _sessions_held(self, opened: Any, today: date) -> int | None:
        start = _ny_date(opened)
        if start is None:
            return None
        d0 = date.fromisoformat(start)
        if d0 > today:
            return 0
        try:
            from swing_engine.data import calendar as cal

            return len(cal.trading_days(d0, today, getattr(self.settings.data, "calendar", "NYSE") or "NYSE"))
        except Exception:  # noqa: BLE001 - weekdays as a fallback
            return sum(1 for i in range((today - d0).days + 1) if (d0 + timedelta(days=i)).weekday() < 5)

    def _max_hold(self, strategy: str | None, origin: Mapping[str, Any]) -> int | None:
        if not strategy:
            return None
        as_of, symbol = origin.get("as_of"), None
        coid = origin.get("client_order_id")
        parsed = parse_client_order_id(coid)
        if parsed:
            symbol = parsed["symbol"]
        if as_of and symbol:  # the signal's own features carry its time stop (e.g. rsi2_meanrev)
            try:
                sigs = self.runs.load("signals", as_of) or []
            except Unavailable:
                sigs = []
            for s in sigs if isinstance(sigs, list) else []:
                if isinstance(s, dict) and s.get("symbol") == symbol and s.get("strategy") == strategy:
                    v = fnum((s.get("features") or {}).get("max_hold_days"))
                    if v:
                        return int(v)
        if strategy in self._hold_cache:
            return self._hold_cache[strategy]
        value: int | None = None
        cfg = (self.settings.strategies or {}).get(strategy) or {}
        params = cfg.get("params") if isinstance(cfg.get("params"), dict) else cfg
        for key in ("max_hold_days", "time_stop_days"):
            if params.get(key) is not None:
                value = int(params[key])
                break
        if value is None:
            try:
                import importlib

                from swing_engine.core import registry

                importlib.import_module("swing_engine.strategies")
                cls = registry.get("strategy", strategy)
                defaults = getattr(cls, "default_params", {}) or {}
                for key in ("max_hold_days", "time_stop_days"):
                    if defaults.get(key) is not None:
                        value = int(defaults[key])
                        break
            except Exception:  # noqa: BLE001 - unknown strategy: no time stop shown
                value = None
        self._hold_cache[strategy] = value
        return value

    # ------------------------------------------------------------------------------------------ orders
    def orders(self, status: str = "open", limit: int = 50) -> dict[str, Any]:
        try:
            ledger = {r["client_order_id"]: r for r in self._ledger_rows()}
        except sqlite3.Error:
            ledger = {}
        try:
            raw = self._open_orders() if status == "open" else self._closed_orders(limit)
        except Unavailable as exc:
            rows = self._ledger_orders(status, limit)
            if rows is None:
                return unavailable(f"orders need the broker: {exc}; the order ledger is empty")
            return ok(rows, source="order ledger (state/orders.sqlite); broker not read", partial={"broker": str(exc)})
        rows = [self._order_row(o, ledger) for o in raw][:limit]
        return ok(rows, source=f"alpaca {'paper' if self.paper else 'live'}")

    @staticmethod
    def _order_row(o: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict[str, Any]:
        coid = o.get("client_order_id")
        parsed = parse_client_order_id(coid)
        lrow = ledger.get(coid) if coid else None
        strategy = (lrow or {}).get("strategy") or (parsed or {}).get("strategy")
        return {
            "id": str(o.get("id")) if o.get("id") is not None else None, "client_order_id": coid,
            "symbol": o.get("symbol"), "side": _text(o.get("side")) or None,
            "type": _text(o.get("type") or o.get("order_type")) or None, "qty": fnum(o.get("qty")),
            "filled_qty": fnum(o.get("filled_qty")), "limit_price": fnum(o.get("limit_price")),
            "stop_price": fnum(o.get("stop_price")), "status": _text(o.get("status")) or None,
            "submitted_at": o.get("submitted_at"), "filled_at": o.get("filled_at"),
            "filled_avg_price": fnum(o.get("filled_avg_price")), "strategy": strategy,
            "order_class": _text(o.get("order_class")) or None,
            "legs": [LiveData._order_row(_to_dict(leg) | {"symbol": _to_dict(leg).get("symbol") or o.get("symbol")},
                                         ledger) for leg in o.get("legs") or []],
        }

    def _ledger_orders(self, status: str, limit: int) -> list[dict[str, Any]] | None:
        try:
            rows = self._ledger_rows()
        except sqlite3.Error:
            return None
        if not rows:
            return None
        terminal = {"filled", "canceled", "expired", "rejected", "replaced", "error"}
        out = []
        for r in reversed(rows):
            st = _text(r.get("status"))
            if (status == "open") == (st in terminal):
                continue
            intent = r.get("intent") or {}
            b = r.get("broker") or {}
            raw = b.get("raw", b) if isinstance(b, Mapping) else {}
            raw = raw if isinstance(raw, Mapping) else {}
            out.append({
                "id": r.get("broker_order_id"), "client_order_id": r.get("client_order_id"), "symbol": r.get("symbol"),
                "side": "buy" if _text(r.get("side")) == "long" else "sell", "type": "limit",
                "qty": fnum(r.get("qty")), "filled_qty": fnum(raw.get("filled_qty")),
                "limit_price": fnum(intent.get("entry_limit")), "stop_price": None, "status": st,
                "submitted_at": raw.get("submitted_at") or r.get("created_at"), "filled_at": raw.get("filled_at"),
                "filled_avg_price": fnum(raw.get("filled_avg_price")), "strategy": r.get("strategy"),
                "order_class": "bracket", "approved_by": r.get("approved_by"),
                "legs": [{"type": "stop", "side": "sell" if _text(r.get("side")) == "long" else "buy",
                          "stop_price": fnum(intent.get("stop")), "limit_price": None},
                         {"type": "limit", "side": "sell" if _text(r.get("side")) == "long" else "buy",
                          "stop_price": None, "limit_price": fnum(intent.get("target"))}],
            })
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------------------------------ chart
    def chart(self, symbol: str, days: int = DEFAULT_CHART_DAYS) -> dict[str, Any]:
        def q(con: Any) -> list[tuple[Any, ...]]:
            if not duck_has_table(con, "bars"):
                raise Unavailable("no bars table in the store yet (run `swing ingest`)")
            return con.execute(
                "SELECT CAST(ts AS DATE) AS d, open, high, low, close, volume FROM bars WHERE symbol = ? "
                "ORDER BY ts", [symbol]
            ).fetchall()

        try:
            rows, stale = self.duck.read(f"bars:{symbol}", q)
        except Unavailable as exc:
            return unavailable(str(exc))
        if not rows:
            return unavailable(f"no bars for {symbol} in the store")
        last = rows[-1][0]
        first = (last - timedelta(days=days)).isoformat()
        all_bars = [{"t": r[0].isoformat(), "o": fnum(r[1], 4), "h": fnum(r[2], 4), "l": fnum(r[3], 4),
                     "c": fnum(r[4], 4), "v": fnum(r[5])} for r in rows if r[4] is not None]
        bars = [b for b in all_bars if b["t"] >= first]
        closes = [(b["t"], b["c"]) for b in all_bars]
        sma20 = [p for p in sma_series(closes, SMA_FAST) if p["t"] >= first]
        sma50 = [p for p in sma_series(closes, SMA_SLOW) if p["t"] >= first]
        partial: dict[str, str] = {}
        levels, markers = self._chart_levels(symbol, partial), self._chart_markers(symbol, first, partial)
        return ok({"symbol": symbol, "bars": bars, "sma20": sma20, "sma50": sma50, "levels": levels,
                   "markers": markers, "last_bar": last.isoformat()}, stale=stale, partial=partial)

    def _chart_levels(self, symbol: str, partial: dict[str, str]) -> dict[str, Any]:
        levels: dict[str, Any] = {"entry": None, "stop": None, "target": None, "current_stop": None}
        held = None
        try:
            held = next((p for p in self._raw_positions() if p.get("symbol") == symbol), None)
            orders = _flatten_orders(self._open_orders())
        except Unavailable as exc:
            orders = None
            partial["levels"] = f"from the order ledger only (broker not read: {exc})"
        pending = orders is not None and any(
            o.get("symbol") == symbol and str(o.get("client_order_id") or "").startswith(f"{CLIENT_ORDER_PREFIX}-")
            and _text(o.get("status")) in ("new", "accepted", "pending_new", "partially_filled", "held")
            for o in orders)
        if orders is not None and held is None and not pending:
            return levels  # neither held nor a resting entry: no live levels to draw
        try:
            row = self._ledger_for_symbol(symbol)
        except sqlite3.Error:
            row = None
        if row is not None:
            intent = row.get("intent") or {}
            _at, px = self._broker_fill(row)
            levels.update(entry=px or fnum(intent.get("entry_limit")), stop=fnum(intent.get("stop")),
                          target=fnum(intent.get("target")))
        if held is not None:
            levels["entry"] = fnum(held.get("avg_entry_price")) or levels["entry"]
            long = not _text(held.get("side")).endswith("short")
            exit_side = "sell" if long else "buy"
            stops = [fnum(o.get("stop_price")) for o in orders or [] if o.get("symbol") == symbol
                     and _text(o.get("side")) == exit_side and _text(o.get("type") or o.get("order_type")) in STOP_TYPES
                     and _text(o.get("status")) not in ("filled", "canceled", "expired", "rejected", "replaced")]
            stops = [s for s in stops if s is not None]
            if stops:
                levels["current_stop"] = max(stops) if long else min(stops)
        return levels

    def _chart_markers(self, symbol: str, first: str, partial: dict[str, str]) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        try:
            ledger = self._ledger_rows()
        except sqlite3.Error:
            ledger = []
        sent = {r["client_order_id"]: r for r in ledger}
        for d in self.runs.dates("signals"):
            if d < first:
                break
            try:
                sigs = self.runs.load("signals", d) or []
            except Unavailable:
                continue
            for s in sigs if isinstance(sigs, list) else []:
                if not isinstance(s, dict) or s.get("symbol") != symbol:
                    continue
                coid = client_order_id_for(str(s.get("strategy")), symbol, d, str(s.get("side") or "long"))
                taken = _text((sent.get(coid) or {}).get("status")) in SENT_LEDGER_STATUSES
                markers.append({"t": d, "kind": "signal", "price": fnum(s.get("entry"), 4),
                                "text": f"{s.get('strategy')} signal{' (taken)' if taken else ''}"})
        for r in ledger:
            if r.get("symbol") != symbol:
                continue
            at, px = self._broker_fill(r)
            day = _ny_date(at)
            if day and px and day >= first:
                markers.append({"t": day, "kind": "entry", "price": px,
                                "text": f"{r.get('strategy')}: {'bought' if _text(r.get('side')) == 'long' else 'sold'} "
                                        f"{r.get('qty')} @ {px:.2f}"})
        try:
            closed = self._closed_orders(500)
        except Unavailable:
            closed = []
        for o in _flatten_orders(closed):
            if o.get("symbol") != symbol or _text(o.get("status")) != "filled":
                continue
            day = _ny_date(o.get("filled_at"))
            px = fnum(o.get("filled_avg_price"))
            if not day or px is None or day < first:
                continue
            coid = o.get("client_order_id") or ""
            is_entry = str(coid).startswith(f"{CLIENT_ORDER_PREFIX}-")
            if is_entry and any(m["kind"] == "entry" and m["t"] == day for m in markers):
                continue
            kind = "entry" if is_entry else "exit"
            verb = "bought" if _text(o.get("side")) == "buy" else "sold"
            markers.append({"t": day, "kind": kind, "price": px,
                            "text": f"{verb} {fnum(o.get('filled_qty')) or ''} @ {px:.2f} "
                                    f"({_text(o.get('type') or o.get('order_type'))})".replace("  ", " ")})
        markers.sort(key=lambda m: (m["t"], m["kind"]))
        return markers

    # ------------------------------------------------------------------------------------------ signals
    def signals(self, day: date | None = None) -> dict[str, Any]:
        available = self.runs.dates("signals")
        if not available:
            return unavailable("no signals saved yet (`swing scan` / the nightly writes runs/signals/<date>.json)")
        target = day.isoformat() if day else available[0]
        try:
            sigs = self.runs.load("signals", target)
        except Unavailable as exc:
            return unavailable(str(exc))
        if sigs is None:
            return unavailable(f"no signals saved for {target}")
        partial: dict[str, str] = {}

        def load(kind: str, default: Any) -> Any:
            try:
                value = self.runs.load(kind, target)
            except Unavailable as exc:
                partial[kind] = str(exc)
                return default
            return default if value is None else value

        reviews = {(r.get("symbol"), r.get("strategy")): r for r in load("reviews", []) if isinstance(r, dict)}
        # runs/review_status/<date>.json (ops.nightly): the latest review step's outcome. When it was skipped,
        # failed or never finished, a reviews file on disk is from an earlier run and was not applied this time.
        rs = load("review_status", None)
        review_status = ({"status": _text(rs.get("status")) or None, "detail": _redact(str(rs.get("detail") or ""), 300),
                          "at": iso_utc(parse_dt(rs.get("at")))} if isinstance(rs, dict) else None)
        reviews_current = review_status is None or review_status["status"] == "ok"
        # ops.nightly's review step keeps only approved intents (unreviewed ones too are dropped) and rewrites
        # runs/intents/<date>.json, so a veto leaves no audit entry: it is read from the review itself. Without a
        # status file (`swing review`) a veto blocks only under execution.require_review_approval (run_autopilot).
        reviews_ok = review_status is not None and review_status["status"] == "ok"
        veto_applies = reviews_ok or (review_status is None and bool(
            getattr(self.settings.execution, "require_review_approval", True)))
        review_cap = getattr(getattr(self.settings, "agent", None), "max_candidates_per_day", None)
        intents = {i.get("client_order_id"): i for i in load("intents", []) if isinstance(i, dict)}
        audit = load("autopilot", {})
        live_status: dict[str, dict[str, Any]] = {}
        dry_status: dict[str, dict[str, Any]] = {}
        for run in (audit.get("runs") if isinstance(audit, dict) else None) or []:
            bucket = dry_status if run.get("dry_run") else live_status
            for e in run.get("entries") or []:
                if e.get("client_order_id"):
                    bucket[e["client_order_id"]] = e
        skipped: dict[str, str] = {}
        size_step: dict[str, str] | None = None  # the size step's own outcome (skip / fail: nothing was sized)
        for kind in ("nightly", "cycle"):
            report = load(kind, {})
            for step in (report.get("steps") if isinstance(report, dict) else None) or []:
                if isinstance(step, dict) and step.get("name") == "size":
                    skipped.update({str(k): str(v) for k, v in ((step.get("data") or {}).get("skipped") or {}).items()})
                    if size_step is None:
                        size_step = {"status": _text(step.get("status")),
                                     "detail": _redact(str(step.get("detail") or ""), 200)}
        try:
            ledger = {r["client_order_id"]: r for r in self._ledger_rows()}
        except sqlite3.Error as exc:
            ledger = {}
            partial["ledger"] = f"order ledger unreadable ({_err(exc)})"
        regime_payload = load("regime", {})
        out = []
        # the file keeps the order the review step saw (score, best first): candidates = signals[:review_cap]
        for rank, s in enumerate(sigs if isinstance(sigs, list) else []):
            if not isinstance(s, dict):
                continue
            strategy, symbol = str(s.get("strategy")), str(s.get("symbol"))
            side = str(s.get("side") or "long")
            coid = client_order_id_for(strategy, symbol, str(s.get("as_of") or target), side)
            r = reviews.get((symbol, strategy))
            taken, status, reason = self._signal_outcome(
                coid, f"{strategy}:{symbol}", intents, live_status, dry_status, skipped, ledger, review=r,
                veto_applies=veto_applies, reviews_ok=reviews_ok, rank=rank, cap=review_cap, size_step=size_step)
            review = None
            if r is not None:
                review = {"decision": _text(r.get("decision")) or None, "thesis": r.get("thesis"),
                          "event_risk_flags": list(r.get("event_risk_flags") or []),
                          "rubric_scores": r.get("rubric_scores") or {}, "evidence": list(r.get("evidence") or [])[:8],
                          "current": reviews_current}
            feats = s.get("features") or {}
            out.append({
                "strategy": strategy, "symbol": symbol, "side": side, "entry": fnum(s.get("entry"), 4),
                "stop": fnum(s.get("stop"), 4), "target": fnum(s.get("target"), 4),
                "reward_risk": fnum(s.get("reward_risk"), 3), "score": fnum(s.get("score"), 4), "taken": taken,
                "skip_reason": reason, "status": status, "client_order_id": coid,
                "qty": (intents.get(coid) or {}).get("qty"), "rank_score": fnum(feats.get("rank_score"), 4),
                "notes": s.get("notes") or "", "review": review,
            })
        return ok({"date": target, "signals": out, "available_dates": available[:120],
                   "regime": regime_payload.get("regime") if isinstance(regime_payload, dict) else None,
                   "review_status": review_status}, partial=partial)

    @staticmethod
    def _signal_outcome(coid: str, key: str, intents: Mapping[str, Any], live: Mapping[str, Any],
                        dry: Mapping[str, Any], skipped: Mapping[str, str], ledger: Mapping[str, Any], *,
                        review: Mapping[str, Any] | None = None, veto_applies: bool = False,
                        reviews_ok: bool = False, rank: int | None = None, cap: int | None = None,
                        size_step: Mapping[str, str] | None = None) -> tuple[bool, str, str | None]:
        """(taken, status, skip_reason) for one signal, in pipeline order: the order ledger (sent), the autopilot
        audit, the size step's skips, the size step itself, Claude's review (a veto, or no review while the
        review step ran: ops.nightly drops both from the intents file), the intents file, a dry run."""
        lrow = ledger.get(coid)
        lstatus = _text((lrow or {}).get("status"))
        if lstatus in SENT_LEDGER_STATUSES:
            return True, lstatus if lstatus != "accepted" else "submitted", None
        entry = live.get(coid)
        if entry is not None:
            st = _text(entry.get("status"))
            if st in TAKEN_STATUSES:
                return True, st, None
            reasons = {
                "capped": "daily cap reached",
                "staged": "staged for a human approval (live account)",
            }
            raw = str(entry.get("reason") or "").strip()
            if st == "capped":  # the audit's reason is the config key ("max_new_orders_per_day=5 reached")
                return False, st, f"daily cap reached ({raw})" if raw else "daily cap reached (execution.max_new_orders_per_day)"
            return False, st or "unknown", raw or reasons.get(st) or st
        if lstatus in ("rejected", "error"):
            return False, lstatus, f"order {lstatus} at the broker"
        if key in skipped:
            return False, "skipped", skipped[key]
        step_status = _text((size_step or {}).get("status"))
        if coid not in intents and step_status in ("skip", "fail"):
            detail = str((size_step or {}).get("detail") or "").strip()
            verb = "was skipped" if step_status == "skip" else "failed"
            return False, "not_sized", f"not sized: the size step {verb}" + (f" ({detail})" if detail else "")
        decision = _text((review or {}).get("decision"))
        if review is not None and veto_applies and decision in VETO_DECISIONS:
            return False, "vetoed", f"vetoed by Claude's review ({decision.replace('_', ' ')})"
        if coid not in intents:
            if review is None and reviews_ok:
                why = (f"beyond agent.max_candidates_per_day={cap}" if cap is not None and rank is not None
                       and rank >= cap else "no review came back for it")
                return False, "not_reviewed", f"not reviewed by Claude ({why}); only approved signals are sent"
            return False, "not_sized", "not sized (no order intent was made for this signal)"
        d = dry.get(coid)
        if d is not None:
            st = _text(d.get("status"))
            return False, f"dry_run_{st}", f"dry run only: {d.get('reason') or st}"
        return False, "sized", "sized but not executed (execution off, --no-execute, or no broker)"

    # ------------------------------------------------------------------------------------------ shadow
    def shadow(self, by: str = "strategy") -> dict[str, Any]:
        def q(con: Any) -> Any:
            if not duck_has_table(con, "shadow_signals"):
                raise Unavailable("the shadow ledger is empty (the nightly's shadow step creates shadow_signals)")
            return con.execute("SELECT * FROM shadow_signals").df()

        try:
            frame, stale = self.duck.read("shadow", q)
        except Unavailable as exc:
            return unavailable(str(exc))
        if frame is None or len(frame) == 0:
            return unavailable("the shadow ledger has no rows yet")
        if by not in frame.columns:
            return unavailable(f"shadow_signals has no {by!r} column")
        try:
            from swing_engine.research.shadow import summarize_outcomes

            table = summarize_outcomes(frame.copy(), (by,))
            records = table.to_dict(orient="records")
        except Exception as exc:  # noqa: BLE001 - module mid-edit / schema drift
            return unavailable(f"shadow summary failed ({_err(exc)})")
        rows = []
        for rec in records:
            rows.append({
                "group": rec.get(by) if rec.get(by) is not None else "unknown", "n": int(rec.get("n") or 0),
                "win_rate": fnum(rec.get("win_rate"), 4), "avg_r": fnum(rec.get("avg_r"), 4),
                "expectancy_r": fnum(rec.get("expectancy"), 4), "profit_factor": fnum(rec.get("profit_factor"), 3),
                "profit_factor_infinite": rec.get("profit_factor") == math.inf,
                "pending": int(rec.get("n_pending") or 0), "n_signals": int(rec.get("n_signals") or 0),
                "n_taken": int(rec.get("n_taken") or 0), "n_skipped": int(rec.get("n_skipped") or 0),
                "total_r": fnum(rec.get("total_r"), 3), "avg_mfe_r": fnum(rec.get("avg_mfe_r"), 3),
                "avg_mae_r": fnum(rec.get("avg_mae_r"), 3),
            })
        updated = None
        for col in ("recorded_at", "graded_through"):
            if col in frame.columns:
                vals = [parse_dt(v) for v in frame[col].dropna().tolist()]
                vals = [v for v in vals if v]
                if vals:
                    cand = max(vals)
                    updated = cand if updated is None or cand > updated else updated
        return ok({"by": by, "rows": rows, "updated_at": iso_utc(updated), "signals": int(len(frame))}, stale=stale)

    def drift(self) -> dict[str, Any]:
        """research.drift over the store's live and replay shadow ledgers, as of the latest live signal."""
        import pandas as pd

        def q(con: Any) -> Any:
            if not duck_has_table(con, "shadow_signals"):
                raise Unavailable("the shadow ledger is empty (the nightly's shadow step creates shadow_signals)")
            replay = (con.execute("SELECT * FROM shadow_signals_replay").df()
                      if duck_has_table(con, "shadow_signals_replay") else pd.DataFrame())
            return con.execute("SELECT * FROM shadow_signals").df(), replay

        try:
            (live, replay), stale = self.duck.read("drift", q)
        except Unavailable as exc:
            return unavailable(str(exc))
        if live is None or len(live) == 0:
            return unavailable("the shadow ledger has no rows yet")
        try:
            from swing_engine.research.drift import DRIFT_MIN_N, DRIFT_SE_BAND, DRIFT_WINDOW_DAYS, drift_table

            as_of = pd.to_datetime(live["as_of"]).max().date()
            table = drift_table(live, replay, as_of)
        except Exception as exc:  # noqa: BLE001 - module mid-edit / schema drift
            return unavailable(f"drift computation failed ({_err(exc)})")
        return ok({"as_of": as_of.isoformat(), "window_days": DRIFT_WINDOW_DAYS, "min_n": DRIFT_MIN_N,
                   "band": DRIFT_SE_BAND, "replay_rows": int(len(replay)),
                   "rows": clean(table.to_dict(orient="records"))}, stale=stale)

    # ------------------------------------------------------------------------------------------ alerts
    def alerts(self, hours: float = 48) -> dict[str, Any]:
        if not self.event_log_path.exists():
            return unavailable("no event log yet (the monitor has not run with this settings file)")
        since = (self._now() - timedelta(hours=hours)).astimezone(UTC).isoformat()
        try:
            con = sqlite_ro(self.event_log_path)
            try:
                tables = _sqlite_tables(con)
                if "events" not in tables:
                    return unavailable("the event log has no events table yet")
                has_alerts = "alerts" in tables
                cond = "priority != 'P0'" + (" OR event_id IN (SELECT event_id FROM alerts)" if has_alerts else "")
                rows = con.execute(
                    f"SELECT event_id, source, kind, ts_source, ts_received, symbols, title, url, meta, priority, "
                    f"rule_hits FROM events WHERE ts_received >= ? AND ({cond}) ORDER BY ts_received DESC LIMIT ?",
                    [since, MAX_ALERTS],
                ).fetchall()
                delivered: dict[str, bool] = {}
                ratings: dict[str, str] = {}
                ids = [r["event_id"] for r in rows]
                if ids and has_alerts:
                    for chunk in _chunks(ids, 400):
                        marks = ",".join("?" * len(chunk))
                        for eid, dv in con.execute(
                                f"SELECT event_id, max(delivered) FROM alerts WHERE event_id IN ({marks}) "
                                f"GROUP BY event_id", chunk).fetchall():
                            delivered[eid] = bool(dv)
                if ids and "alert_ratings" in tables:
                    for chunk in _chunks(ids, 400):
                        marks = ",".join("?" * len(chunk))
                        for eid, rating in con.execute(
                                f"SELECT event_id, rating FROM alert_ratings WHERE event_id IN ({marks}) ORDER BY id",
                                chunk).fetchall():
                            ratings[eid] = rating
            finally:
                con.close()
        except sqlite3.Error as exc:
            return unavailable(f"event log unreadable ({_err(exc)})")
        out = []
        for r in rows:
            meta = _loads(r["meta"], {})
            out.append({
                "event_id": r["event_id"], "ts": iso_utc(parse_dt(r["ts_received"])),
                "ts_source": iso_utc(parse_dt(r["ts_source"])), "priority": r["priority"], "title": r["title"],
                "source": r["source"], "kind": r["kind"], "symbols": _loads(r["symbols"], []),
                "rule_hits": _loads(r["rule_hits"], []),
                "rating": (meta.get("rating") if isinstance(meta, dict) else None) or ratings.get(r["event_id"]),
                "url": _safe_url(r["url"]), "delivered": delivered.get(r["event_id"]),
            })
        return ok(out)

    def rate(self, event_id: str, rating: str) -> dict[str, Any]:
        if not self.event_log_path.exists():
            return unavailable("no event log yet (the monitor has not run with this settings file)")
        from swing_engine.monitor.eventlog import EventLog
        from swing_engine.monitor.rate import rate_alert

        log_ = EventLog(self.event_log_path)
        try:
            result = rate_alert(log_, event_id, rating, "dashboard")
        finally:
            log_.close()
        if not result.ok:
            if result.reason == "unknown_event":
                return unavailable(f"unknown event {event_id}")
            return unavailable(f"not rated ({result.reason})")
        return ok({"event_id": event_id, "rating": str(getattr(result.rating, "value", result.rating)),
                   "previous": result.previous})

    # ------------------------------------------------------------------------------------------ journal
    def journal(self, day: date | None = None) -> dict[str, Any]:
        found: dict[str, Path] = {}
        for d in self.journal_dirs:
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for n in names:
                m = DATE_FILE_RE.match(n)
                if m and m.group(2) == "md" and m.group(1) not in found:
                    found[m.group(1)] = d / n
        dates = sorted(found, reverse=True)
        if not dates:
            return unavailable("no journal entries yet (the nightly's journal step writes data/journal/<date>.md)")
        target = day.isoformat() if day else dates[0]
        path = found.get(target)
        if path is None:
            return unavailable(f"no journal entry for {target}")
        try:
            with path.open("rb") as fh:
                raw = fh.read(JOURNAL_MAX_BYTES + 1)
        except OSError as exc:
            return unavailable(f"journal unreadable ({_err(exc)})")
        text = raw[:JOURNAL_MAX_BYTES].decode("utf-8", "replace")
        if len(raw) > JOURNAL_MAX_BYTES:
            text += "\n\n*(truncated)*\n"
        return ok({"date": target, "markdown": text, "available_dates": dates[:365]})

    # ------------------------------------------------------------------------------------------ replay
    def replay(self) -> dict[str, Any]:
        d = self.runs.dir("replay")
        try:
            names = sorted(os.listdir(d))
        except OSError:
            names = []
        runs = []
        for n in names:
            m = RUN_NAME_RE.match(n)
            if not m:
                continue
            path = d / n
            try:
                payload = self.runs.load_path(path)
            except Unavailable:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                continue
            created = parse_dt(payload.get("created_at") or payload.get("finished_at") or payload.get("generated_at"))
            runs.append(({"id": str(payload.get("id") or payload.get("run_id") or m.group("stem")),
                          "start": _str_date(payload.get("start")), "end": _str_date(payload.get("end")),
                          "created_at": iso_utc(created or mtime)}, payload, created or mtime))
        if not runs:
            return unavailable("no replay runs yet (`swing replay` writes runs/replay/<id>.json)")
        runs.sort(key=lambda r: r[2], reverse=True)
        meta, payload, _ = runs[0]
        latest = {
            "id": meta["id"],
            "units": "fraction",  # research.metrics: returns, CAGR, drawdown and win rate as fractions (0.12)
            "summary": _first_dict(payload, "summary", "metrics", "stats"),
            "by_strategy": _as_rows(payload.get("by_strategy"), "strategy"),
            "by_regime": _as_rows(payload.get("by_regime"), "regime"),
            "equity_curve": _curve(payload.get("equity_curve") or payload.get("equity")),
        }
        return ok({"runs": [r[0] for r in runs], "latest": latest})

    # ------------------------------------------------------------------------------------------ kill switch
    def trip_killswitch(self) -> dict[str, Any]:
        from swing_engine.risk.killswitch import trip

        path = trip(self.kill_path, reason="tripped from the dashboard")
        return ok({"tripped": True, "path": str(path)})


# ============================================================================================== module helpers
def _flatten_orders(orders: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Top-level orders plus their nested bracket legs (legs inherit the parent's symbol and client id)."""
    out: list[dict[str, Any]] = []
    for o in orders:
        d = _to_dict(o)
        out.append(d)
        for leg in d.get("legs") or []:
            item = _to_dict(leg)
            item.setdefault("symbol", d.get("symbol"))
            item["_parent_client_order_id"] = d.get("client_order_id")
            out.append(item)
    return out


def _chunks(items: list[Any], n: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _loads(text: Any, default: Any) -> Any:
    try:
        value = json.loads(text) if isinstance(text, str) else text
    except ValueError:
        return default
    return default if value is None else value


def _str_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    text = str(value)
    return text[:10] if DATE_RE.match(text[:10]) else text


def _first_dict(payload: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    for k in keys:
        if isinstance(payload.get(k), dict):
            return clean(payload[k])
    return {}


def _as_rows(value: Any, key: str) -> list[dict[str, Any]]:
    """A per-group table stored as a list of records or as ``{group: {...}}``."""
    if isinstance(value, list):
        return [clean(v) for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        return [clean({key: k, **(v if isinstance(v, dict) else {"value": v})}) for k, v in value.items()]
    return []


MAX_CURVE_POINTS = 2000


def _curve(value: Any) -> list[dict[str, Any]]:
    """Equity curve in any of the shapes a report might use -> ``[{t, equity}]`` (downsampled to 2,000 points)."""
    pts: list[dict[str, Any]] = []
    if isinstance(value, dict):
        items = list(value.items())
        if set(value) >= {"t", "equity"} and isinstance(value.get("t"), list):
            items = list(zip(value["t"], value["equity"], strict=False))
        for t, v in items:
            if fnum(v) is not None:
                pts.append({"t": _str_date(t), "equity": fnum(v, 2)})
    elif isinstance(value, list):
        for p in value:
            if isinstance(p, dict):
                t = p.get("t") or p.get("date") or p.get("ts") or p.get("session")
                v = next((p[k] for k in ("equity", "value", "nav", "close") if k in p), None)
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                t, v = p[0], p[1]
            else:
                continue
            if t is not None and fnum(v) is not None:
                pts.append({"t": _str_date(t), "equity": fnum(v, 2)})
    if len(pts) > MAX_CURVE_POINTS:
        step = math.ceil(len(pts) / MAX_CURVE_POINTS)
        pts = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
    return pts


def _httpx_get(url: str, params: Mapping[str, Any], headers: Mapping[str, str], timeout: float) -> tuple[int, Any]:
    import httpx

    resp = httpx.get(url, params=dict(params), headers=dict(headers), timeout=timeout)
    try:
        body = resp.json()
    except ValueError:
        body = None
    return resp.status_code, body
