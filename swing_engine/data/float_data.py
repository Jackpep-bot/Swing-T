"""Free float / shares-outstanding source for the small-cap track (docs/smallcap-spec.md: float < 20M is a hard
gate; float unknown or stale => warnings only, never a long alert).

Providers, in the order `FloatSource.lookup` consults them:
1. EDGAR XBRL companyfacts (free; 10 req/s + User-Agent per the SEC fair-access policy, shared token bucket):
   `dei:EntityCommonStockSharesOutstanding` (cover-page count; latest `end` filed on or before `as_of`) and
   `dei:EntityPublicFloat` (USD, annual). float_shares = public_float / price-on-that-date when a price is
   available, else shares_outstanding (an upper bound). Multi-class filers report one entry per class with the
   same `end`/`accn`: those are summed; exact duplicates (frame re-statements) are dropped.
2. Massive `/v3/reference/tickers/{ticker}` `share_class_shares_outstanding` / `weighted_shares_outstanding`
   as a sanity cross-check on the EDGAR count (and the fallback count when EDGAR has nothing).
3. A vendor adapter (FMP `shares_float` shape) behind `VendorFloatAdapter`; the shipped `FMPFloatAdapter`
   raises NotImplementedError until an API key is configured.

Every number here is a fact read from a filing or a vendor record, never an LLM output. Point-in-time: with
`as_of` only facts *filed* on or before that date are used, and `FloatInfo.as_of` is the cover-page date the
count is valid for. Staleness is recomputed on read: older than `STALE_AFTER_DAYS`, or an 8-K item 3.02 /
424B* / reverse split for the symbol dated after `as_of` in the optional `events` frame.
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import structlog
from pydantic import BaseModel

from swing_engine.core.config import Secrets, Settings

from ._common import as_date
from ._http import Http, RawCache, default_cache_dir
from .edgar import CIK_WIDTH, COMPANY_TICKERS_PATH, EDGAR_BURST, EDGAR_CALLS_PER_MIN, SEC_BASE_URL
from .massive import MASSIVE_BASE_URL, MASSIVE_BASIC_CALLS_PER_MIN, TICKERS_PATH
from .store import Store

log = structlog.get_logger(__name__)

FLOAT_VERSION = "2026.10.06"
PROVIDER_NAME = "float"
FLOAT_TABLE = "float"
FLOAT_KEYS: list[str] = ["symbol", "as_of"]
STALE_AFTER_DAYS = 120
#: EDGAR vs Massive share counts further apart than this fraction are flagged `cross_check="mismatch"`.
CROSS_CHECK_TOLERANCE = 0.25
#: when deriving a price from stored bars, use the last close within this many calendar days before the date.
PRICE_LOOKBACK_DAYS = 7
SHARES_PER_M = 1_000_000.0

# ---- EDGAR companyfacts ------------------------------------------------------------------------------------
SEC_DATA_BASE_URL = "https://data.sec.gov"
COMPANYFACTS_PATH = "/api/xbrl/companyfacts/CIK{cik}.json"
DEI_TAXONOMY = "dei"
SHARES_OUTSTANDING_CONCEPT = "EntityCommonStockSharesOutstanding"
PUBLIC_FLOAT_CONCEPT = "EntityPublicFloat"
SHARES_UNIT = "shares"
USD_UNIT = "USD"
HTTP_NOT_FOUND = 404

# ---- vendor (FMP) --------------------------------------------------------------------------------------------
FMP_BASE_URL = "https://financialmodelingprep.com"
FMP_SHARES_FLOAT_PATH = "/api/v4/shares_float"
FMP_CALLS_PER_MIN = 300  # starter plan; the bucket only keeps a burst from tripping the vendor limit
FMP_API_KEY_ENV = "FMP_API_KEY"

# ---- methods / sources -----------------------------------------------------------------------------------------
METHOD_PUBLIC_FLOAT_PRICE = "edgar_public_float_div_price"
METHOD_PUBLIC_FLOAT_ADJ = "edgar_public_float_plus_new_shares"  # float then + shares issued since (dilution)
SHARES_NEAR_FLOAT_WINDOW_DAYS = 100  # a cover-page share count this close to the float date is "the count then"
METHOD_SHARES_OUTSTANDING = "edgar_shares_outstanding"
METHOD_MASSIVE_SHARES = "massive_shares_outstanding"
METHOD_VENDOR = "vendor_float"
METHOD_UNKNOWN = "unknown"
SOURCE_EDGAR = "edgar_companyfacts"
SOURCE_MASSIVE = "massive_reference"
SOURCE_VENDOR = "vendor"
SOURCE_NONE = "none"
CROSS_CHECK_OK = "ok"
CROSS_CHECK_MISMATCH = "mismatch"
CROSS_CHECK_UNAVAILABLE = "unavailable"
CROSS_CHECK_SKIPPED = "skipped"
STALE_AGE = "age"
STALE_NO_DATA = "no_data"

# ---- events frame (optional input to the staleness rule) -------------------------------------------------------
EVENT_SYMBOL_COL = "symbol"
EVENT_DATE_COLS: tuple[str, ...] = ("filed_at", "date", "ex_date", "ts")
EVENT_FORM_COL = "form_type"
EVENT_ITEMS_COL = "items"
EVENT_KIND_COL = "kind"
EVENT_RATIO_COL = "ratio"
PROSPECTUS_PREFIX = "424B"
EIGHTK_PREFIX = "8-K"
UNREGISTERED_SALE_ITEM = "3.02"
REVERSE_SPLIT_KINDS: frozenset[str] = frozenset({"reverse_split", "split"})

FLOAT_COLUMNS: list[str] = [
    "symbol", "as_of", "shares_outstanding", "float_shares", "float_estimate_method", "source", "stale",
    "stale_reason", "filed", "float_as_of", "public_float_usd", "price_used", "cross_check", "cik", "refreshed_on",
]
FLOAT_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR",
    "as_of": "DATE",
    "shares_outstanding": "DOUBLE",
    "float_shares": "DOUBLE",
    "float_estimate_method": "VARCHAR",
    "source": "VARCHAR",
    "stale": "BOOLEAN",
    "stale_reason": "VARCHAR",
    "filed": "DATE",
    "float_as_of": "DATE",
    "public_float_usd": "DOUBLE",
    "price_used": "DOUBLE",
    "cross_check": "VARCHAR",
    "cik": "VARCHAR",
    "refreshed_on": "DATE",
}

PriceLookup = Callable[[str, date], float | None]


class FloatInfo(BaseModel):
    """One symbol's share count and float estimate, with provenance. `float_shares` None => unknown."""

    symbol: str
    shares_outstanding: float | None = None
    float_shares: float | None = None
    float_estimate_method: str = METHOD_UNKNOWN
    as_of: date | None = None
    source: str = SOURCE_NONE
    stale: bool = True
    stale_reason: str | None = None
    filed: date | None = None
    float_as_of: date | None = None
    public_float_usd: float | None = None
    price_used: float | None = None
    cross_check: str | None = None
    cik: str | None = None

    @property
    def float_m(self) -> float | None:
        return None if self.float_shares is None else self.float_shares / SHARES_PER_M

    @property
    def known(self) -> bool:
        return self.float_shares is not None and self.as_of is not None


class VendorFloat(BaseModel):
    """Normalized vendor record (FMP `shares_float` shape: floatShares / outstandingShares / date)."""

    symbol: str
    float_shares: float | None = None
    shares_outstanding: float | None = None
    as_of: date | None = None
    vendor: str


class VendorFloatAdapter:
    """Pluggable vendor interface: return a `VendorFloat` or None, raise NotImplementedError when unusable."""

    name = "vendor"

    @property
    def available(self) -> bool:
        return False

    def shares_float(self, symbol: str) -> VendorFloat | None:  # pragma: no cover - interface
        raise NotImplementedError(f"{self.name}: no vendor float adapter configured")


class FMPFloatAdapter(VendorFloatAdapter):
    """Financial Modeling Prep `/api/v4/shares_float?symbol=` adapter. Stub without a key: `shares_float`
    raises NotImplementedError; `parse` is usable on recorded payloads either way."""

    name = "fmp"

    def __init__(
        self,
        api_key: str | None,
        *,
        base_url: str = FMP_BASE_URL,
        client: httpx.Client | None = None,
        calls_per_min: float = FMP_CALLS_PER_MIN,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or None
        self.base_url = base_url.rstrip("/")
        self.http = Http(client=client, rate_per_min=calls_per_min, clock=clock, sleep=sleep) if self.api_key else None

    @property
    def available(self) -> bool:
        return self.api_key is not None

    @staticmethod
    def parse(payload: Any, symbol: str) -> VendorFloat | None:
        rows = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        rows = [r for r in rows if isinstance(r, dict) and str(r.get("symbol", symbol)).upper() == symbol.upper()]
        if not rows:
            return None
        row = max(rows, key=lambda r: str(r.get("date", "")))
        float_shares = pd.to_numeric(row.get("floatShares"), errors="coerce")
        outstanding = pd.to_numeric(row.get("outstandingShares"), errors="coerce")
        stamp = pd.to_datetime(row.get("date"), errors="coerce")
        return VendorFloat(
            symbol=symbol.upper(),
            float_shares=float(float_shares) if pd.notna(float_shares) else None,
            shares_outstanding=float(outstanding) if pd.notna(outstanding) else None,
            as_of=stamp.date() if pd.notna(stamp) else None,
            vendor=FMPFloatAdapter.name,
        )

    def shares_float(self, symbol: str) -> VendorFloat | None:
        if self.http is None:
            raise NotImplementedError(f"fmp: set {FMP_API_KEY_ENV} to enable the vendor float adapter")
        payload = self.http.get_json(
            f"{self.base_url}{FMP_SHARES_FLOAT_PATH}", params={"symbol": symbol.upper(), "apikey": self.api_key}
        )
        return self.parse(payload, symbol)


# ---- staleness --------------------------------------------------------------------------------------------------
def _event_dates(events: pd.DataFrame) -> pd.Series:
    col = next((c for c in EVENT_DATE_COLS if c in events.columns), None)
    if col is None:
        raise ValueError(f"events frame needs one of {EVENT_DATE_COLS}")
    parsed = pd.to_datetime(events[col], errors="coerce", format="mixed", utc=True)
    return parsed.dt.date.where(parsed.notna(), None)


def _items_of(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value]


def _float_event_label(row: pd.Series) -> str | None:
    """Label of a float-invalidating event in this row, or None when the row does not affect the float."""
    kind = str(row.get(EVENT_KIND_COL, "") or "").lower()
    if kind in REVERSE_SPLIT_KINDS:
        ratio = pd.to_numeric(row.get(EVENT_RATIO_COL), errors="coerce")
        if kind == "reverse_split" or (pd.notna(ratio) and float(ratio) < 1.0):
            return "reverse_split"
    form = str(row.get(EVENT_FORM_COL, "") or "").upper()
    if form.startswith(PROSPECTUS_PREFIX):
        return form
    if form.startswith(EIGHTK_PREFIX) and UNREGISTERED_SALE_ITEM in _items_of(row.get(EVENT_ITEMS_COL)):
        return f"{form} {UNREGISTERED_SALE_ITEM}"
    return None


def float_events_after(events: pd.DataFrame | None, symbol: str, after: date) -> list[tuple[date, str]]:
    """(date, label) of every float-invalidating event for `symbol` dated strictly after `after`."""
    if events is None or len(events) == 0:
        return []
    frame = events[events[EVENT_SYMBOL_COL].astype(str).str.upper() == symbol.upper()]
    if frame.empty:
        return []
    dates = _event_dates(frame)
    hits: list[tuple[date, str]] = []
    for (_, row), d in zip(frame.iterrows(), dates, strict=True):
        if d is None or d <= after:
            continue
        label = _float_event_label(row)
        if label is not None:
            hits.append((d, label))
    return sorted(hits)


def stale_reason(
    as_of: date | None,
    today: date,
    symbol: str,
    events: pd.DataFrame | None = None,
    *,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> str | None:
    """Why a float dated `as_of` is stale on `today`, or None when it is fresh."""
    if as_of is None:
        return STALE_NO_DATA
    age = (today - as_of).days
    if age > stale_after_days:
        return f"{STALE_AGE}:{age}d"
    hits = float_events_after(events, symbol, as_of)
    if hits:
        d, label = hits[-1]
        return f"event:{label}@{d.isoformat()}"
    return None


STALE_UNDATED = "undated_reference"  # a share count with no date can never prove the float is fresh


def _staleness(info: FloatInfo, today: date, events: pd.DataFrame | None, stale_after_days: int) -> str | None:
    """Staleness reason for `info`: undated reference counts are always stale (warnings only, never a long)."""
    if info.float_estimate_method == METHOD_MASSIVE_SHARES:
        return STALE_UNDATED
    return stale_reason(info.as_of, today, info.symbol, events, stale_after_days=stale_after_days)


def restamp(info: FloatInfo, today: date, events: pd.DataFrame | None = None, *, stale_after_days: int = STALE_AFTER_DAYS) -> FloatInfo:
    """Copy of `info` with `stale`/`stale_reason` recomputed for `today`."""
    reason = _staleness(info, today, events, stale_after_days)
    return info.model_copy(update={"stale": reason is not None, "stale_reason": reason})


# ---- companyfacts parsing ----------------------------------------------------------------------------------------
def _facts(payload: Mapping[str, Any], concept: str, unit: str) -> list[dict[str, Any]]:
    try:
        rows = payload["facts"][DEI_TAXONOMY][concept]["units"][unit]
    except (KeyError, TypeError):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("end") and r.get("val") is not None]


def _filed_on_or_before(rows: Iterable[dict[str, Any]], as_of: date | None) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        filed = pd.to_datetime(r.get("filed"), errors="coerce")
        if pd.isna(filed):
            continue
        if as_of is None or filed.date() <= as_of:
            out.append(r)
    return out


def latest_fact(payload: Mapping[str, Any], concept: str, unit: str, as_of: date | None = None) -> dict[str, Any] | None:
    """Latest `concept` fact by (end, filed) among those filed on or before `as_of`. Entries sharing that
    end/accn (one per share class) are summed after exact duplicates are dropped. Returns
    {"val", "end", "filed", "accn", "form"} or None."""
    rows = _filed_on_or_before(_facts(payload, concept, unit), as_of)
    if not rows:
        return None
    key = max(((r["end"], r["filed"]) for r in rows), key=lambda k: (str(k[0]), str(k[1])))
    group = [r for r in rows if (r["end"], r["filed"]) == key]
    accn = max((str(r.get("accn", "")) for r in group), default="")
    group = [r for r in group if str(r.get("accn", "")) == accn]
    seen: set[tuple[Any, ...]] = set()
    total = 0.0
    for r in group:
        sig = (r.get("val"), r.get("fp"), r.get("fy"))
        if sig in seen:
            continue
        seen.add(sig)
        total += float(r["val"])
    return {
        "val": total,
        "end": as_date(key[0]),
        "filed": as_date(key[1]),
        "accn": accn or None,
        "form": group[0].get("form"),
    }


def fact_nearest(
    payload: Mapping[str, Any], concept: str, unit: str, on: date, *, window_days: int, as_of: date | None = None
) -> dict[str, Any] | None:
    """The `concept` fact (filed on or before `as_of`) whose `end` is closest to `on`, within `window_days`."""
    rows = _filed_on_or_before(_facts(payload, concept, unit), as_of)
    ends = {as_date(r["end"]) for r in rows}
    near = [e for e in ends if abs((e - on).days) <= window_days]
    if not near:
        return None
    end = min(near, key=lambda e: (abs((e - on).days), e))
    # same share-class summing as latest_fact: newest filing for that end, newest accession, exact dups dropped
    same_end = [r for r in rows if as_date(r["end"]) == end]
    filed = max(str(r["filed"]) for r in same_end)
    group = [r for r in same_end if str(r["filed"]) == filed]
    accn = max((str(r.get("accn", "")) for r in group), default="")
    group = [r for r in group if str(r.get("accn", "")) == accn]
    seen: set[tuple[Any, ...]] = set()
    total = 0.0
    for r in group:
        sig = (r.get("val"), r.get("fp"), r.get("fy"))
        if sig not in seen:
            seen.add(sig)
            total += float(r["val"])
    return {"val": total, "end": end, "filed": as_date(filed)}


def bars_price_lookup(store: Store, *, lookback_days: int = PRICE_LOOKBACK_DAYS) -> PriceLookup:
    """Price function backed by the store's daily bars: last close on or before the date within `lookback_days`."""

    def price(symbol: str, on: date) -> float | None:
        bars = store.read_bars([symbol], on - timedelta(days=lookback_days), on)
        if bars.empty:
            return None
        close = bars.sort_values("ts")["close"].dropna()
        return float(close.iloc[-1]) if len(close) else None

    return price


def _resolve_price(price: float | PriceLookup | None, symbol: str, on: date | None) -> float | None:
    if price is None or on is None:
        return None
    if callable(price):
        value = price(symbol, on)
    else:
        value = price
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return value if value is not None and value > 0 else None


# ---- the source --------------------------------------------------------------------------------------------------
class FloatSource:
    """Float / shares-outstanding lookups with EDGAR as the free primary, Massive as the cross-check and an
    optional vendor adapter. One SEC token bucket covers company_tickers.json and companyfacts."""

    name = PROVIDER_NAME

    def __init__(
        self,
        user_agent: str,
        *,
        massive_api_key: str | None = None,
        massive_calls_per_min: float = MASSIVE_BASIC_CALLS_PER_MIN,
        vendor: VendorFloatAdapter | None = None,
        cik_map: Mapping[str, str] | None = None,
        sec_base_url: str = SEC_BASE_URL,
        sec_data_base_url: str = SEC_DATA_BASE_URL,
        massive_base_url: str = MASSIVE_BASE_URL,
        client: httpx.Client | None = None,
        cache_dir: str | Path | None = None,
        stale_after_days: int = STALE_AFTER_DAYS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError("float_data: user_agent must include a contact email (SEC fair-access policy)")
        self.user_agent = user_agent
        self.sec_base_url = sec_base_url.rstrip("/")
        self.sec_data_base_url = sec_data_base_url.rstrip("/")
        self.massive_base_url = massive_base_url.rstrip("/")
        self.vendor = vendor
        self.stale_after_days = stale_after_days
        self._today = today
        cache = default_cache_dir(self.name) if cache_dir is None else cache_dir
        self.sec = Http(
            client=client,
            rate_per_min=EDGAR_CALLS_PER_MIN,
            burst=EDGAR_BURST,
            cache_dir=cache,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            clock=clock,
            sleep=sleep,
        )
        self.massive: Http | None = None
        if massive_api_key:
            self.massive = Http(
                client=client,
                rate_per_min=massive_calls_per_min,
                cache_dir=cache,
                headers={"Authorization": f"Bearer {massive_api_key}", "Accept": "application/json"},
                clock=clock,
                sleep=sleep,
            )
        self._cik_map: dict[str, str] | None = (
            {k.upper(): str(v).zfill(CIK_WIDTH) for k, v in cik_map.items()} if cik_map is not None else None
        )

    @classmethod
    def from_settings(cls, settings: Settings, secrets: Secrets, **kw: Any) -> FloatSource:
        fmp_key = getattr(secrets, "fmp_api_key", None) or os.environ.get(FMP_API_KEY_ENV)
        return cls(
            secrets.edgar_user_agent,
            massive_api_key=secrets.massive_api_key,
            vendor=FMPFloatAdapter(fmp_key),
            **kw,
        )

    # ---- CIK resolution ----------------------------------------------------------------------------------------
    def cik_for(self, symbol: str) -> str | None:
        sym = symbol.upper().strip()
        if self._cik_map is None:
            payload = self.sec.get_json(
                f"{self.sec_base_url}{COMPANY_TICKERS_PATH}",
                cache_key=RawCache.key(COMPANY_TICKERS_PATH, salt=self._today().isoformat()),
            )
            rows = payload.values() if isinstance(payload, dict) else payload
            self._cik_map = {str(r["ticker"]).upper(): str(r["cik_str"]).zfill(CIK_WIDTH) for r in rows}
        return self._cik_map.get(sym)

    # ---- providers ---------------------------------------------------------------------------------------------
    def companyfacts(self, cik: str) -> dict[str, Any] | None:
        """Raw companyfacts payload for a zero-padded CIK; None on 404 (no XBRL facts for that filer)."""
        path = COMPANYFACTS_PATH.format(cik=str(cik).zfill(CIK_WIDTH))
        try:
            return self.sec.get_json(
                f"{self.sec_data_base_url}{path}", cache_key=RawCache.key(path, salt=self._today().isoformat())
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_NOT_FOUND:
                log.info("float_companyfacts_missing", cik=cik)
                return None
            raise

    def massive_reference(self, symbol: str) -> dict[str, Any] | None:
        """Massive ticker reference `results` (share counts, cik) or None when unavailable."""
        if self.massive is None:
            return None
        url = f"{self.massive_base_url}{TICKERS_PATH}/{symbol.upper()}"
        try:
            payload = self.massive.get_json(url, cache_key=RawCache.key(url, salt=self._today().isoformat()))
        except httpx.HTTPStatusError as exc:
            log.warning("float_massive_reference_failed", symbol=symbol, status=exc.response.status_code)
            return None
        results = payload.get("results") if isinstance(payload, dict) else None
        return results if isinstance(results, dict) else None

    @staticmethod
    def _massive_shares(ref: Mapping[str, Any] | None) -> float | None:
        if not ref:
            return None
        for key in ("share_class_shares_outstanding", "weighted_shares_outstanding"):
            value = pd.to_numeric(ref.get(key), errors="coerce")
            if pd.notna(value) and float(value) > 0:
                return float(value)
        return None

    def _vendor_float(self, symbol: str) -> VendorFloat | None:
        if self.vendor is None or not self.vendor.available:
            return None
        try:
            return self.vendor.shares_float(symbol)
        except NotImplementedError:
            return None
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("float_vendor_failed", symbol=symbol, vendor=self.vendor.name, error=str(exc))
            return None

    # ---- lookup --------------------------------------------------------------------------------------------------
    def lookup(
        self,
        symbol: str,
        as_of: date | datetime | str | None = None,
        *,
        price: float | PriceLookup | None = None,
        events: pd.DataFrame | None = None,
    ) -> FloatInfo:
        """FloatInfo for `symbol` using facts filed on or before `as_of` (all when None). `price` is either the
        price on the public-float date or a `(symbol, date) -> price` lookup; without it the float estimate
        falls back to the cover-page share count. Never raises for a missing symbol: returns an unknown record."""
        sym = symbol.upper().strip()
        cutoff = as_date(as_of) if as_of is not None else None
        today = self._today()
        info = FloatInfo(symbol=sym)
        ref = self.massive_reference(sym)
        cik = self.cik_for(sym) or (str(ref.get("cik")).zfill(CIK_WIDTH) if ref and ref.get("cik") else None)
        info.cik = cik
        facts = self.companyfacts(cik) if cik else None
        if facts is not None:
            self._apply_edgar(info, facts, cutoff, price)
        massive_shares = self._massive_shares(ref)
        if cutoff is not None:
            massive_shares_for_float = None  # current reference data must never describe a historical date
        else:
            massive_shares_for_float = massive_shares
        if info.shares_outstanding is None and massive_shares_for_float is not None:
            info.shares_outstanding = massive_shares_for_float
            info.source = SOURCE_MASSIVE
            info.cross_check = CROSS_CHECK_SKIPPED
            if info.float_shares is None:
                info.float_shares = massive_shares_for_float
                info.float_estimate_method = METHOD_MASSIVE_SHARES
                info.as_of = today  # reference data carries no date; always stale for the long gate (below)
        elif info.shares_outstanding is not None:
            info.cross_check = self._cross_check(sym, info.shares_outstanding, massive_shares)
        vendor = self._vendor_float(sym) if cutoff is None else None
        if vendor is not None and vendor.float_shares is not None:
            info.float_shares = vendor.float_shares
            info.float_estimate_method = METHOD_VENDOR
            info.source = f"{SOURCE_VENDOR}:{vendor.vendor}"
            info.float_as_of = vendor.as_of
            info.price_used = None
            info.public_float_usd = None
            if vendor.shares_outstanding is not None and info.shares_outstanding is None:
                info.shares_outstanding = vendor.shares_outstanding
            # the vendor float is dated by the vendor, never by a newer EDGAR cover page
            if vendor.as_of is not None:
                info.as_of = vendor.as_of
        reason = _staleness(info, today, events, self.stale_after_days)
        info.stale, info.stale_reason = reason is not None, reason
        log.debug(
            "float_lookup", symbol=sym, method=info.float_estimate_method, source=info.source,
            float_shares=info.float_shares, as_of=info.as_of, stale=info.stale,
        )
        return info

    def _apply_edgar(
        self, info: FloatInfo, facts: Mapping[str, Any], cutoff: date | None, price: float | PriceLookup | None
    ) -> None:
        shares = latest_fact(facts, SHARES_OUTSTANDING_CONCEPT, SHARES_UNIT, cutoff)
        public_float = latest_fact(facts, PUBLIC_FLOAT_CONCEPT, USD_UNIT, cutoff)
        if shares is None and public_float is None:
            return
        info.source = SOURCE_EDGAR
        if shares is not None:
            info.shares_outstanding = shares["val"]
            info.as_of = shares["end"]
            info.filed = shares["filed"]
        if public_float is not None:
            info.public_float_usd = public_float["val"]
            info.float_as_of = public_float["end"]
            px = _resolve_price(price, info.symbol, public_float["end"])
            if px is not None:
                estimate = public_float["val"] / px
                method = METHOD_PUBLIC_FLOAT_PRICE
                # The public float is measured once a year (last Q2 end). Its date is what makes it fresh or
                # stale, not the newer cover page. When a share count from near the float date exists, shares
                # issued since then are assumed to have gone to the public (dilution), and the estimate is
                # dated by the newer cover page instead.
                measured = public_float["end"]
                if shares is not None and shares["end"] > public_float["end"]:
                    then = fact_nearest(
                        facts, SHARES_OUTSTANDING_CONCEPT, SHARES_UNIT, public_float["end"],
                        window_days=SHARES_NEAR_FLOAT_WINDOW_DAYS, as_of=cutoff,
                    )
                    if then is not None:
                        estimate += max(0.0, shares["val"] - then["val"])
                        method = METHOD_PUBLIC_FLOAT_ADJ
                        measured = shares["end"]
                if info.shares_outstanding is not None:
                    estimate = min(estimate, info.shares_outstanding)
                info.float_shares = estimate
                info.price_used = px
                info.float_estimate_method = method
                if info.as_of is None or measured < info.as_of:
                    info.as_of = measured
                    if measured == public_float["end"]:
                        info.filed = public_float["filed"]
                return
        if info.shares_outstanding is not None:
            info.float_shares = info.shares_outstanding
            info.float_estimate_method = METHOD_SHARES_OUTSTANDING

    @staticmethod
    def _cross_check(symbol: str, edgar_shares: float, massive_shares: float | None) -> str:
        if massive_shares is None:
            return CROSS_CHECK_UNAVAILABLE
        gap = abs(edgar_shares - massive_shares) / max(edgar_shares, massive_shares)
        if gap > CROSS_CHECK_TOLERANCE:
            log.warning("float_cross_check_mismatch", symbol=symbol, edgar=edgar_shares, massive=massive_shares, gap=round(gap, 3))
            return CROSS_CHECK_MISMATCH
        return CROSS_CHECK_OK

    # ---- store ---------------------------------------------------------------------------------------------------
    def refresh(
        self,
        symbols: Iterable[str],
        store: Store,
        *,
        as_of: date | datetime | str | None = None,
        prices: Mapping[str, float] | PriceLookup | None = None,
        events: pd.DataFrame | None = None,
    ) -> dict[str, Any]:
        """Look up every symbol and upsert the known ones into the `float` table keyed on (symbol, as_of).
        `prices` defaults to the store's own daily bars (close on the public-float date). Returns counts."""
        price: float | PriceLookup | None
        if prices is None:
            price = bars_price_lookup(store)
        elif isinstance(prices, Mapping):
            table = {k.upper(): float(v) for k, v in prices.items()}
            price = lambda symbol, _on: table.get(symbol.upper())  # noqa: E731 - closes over the mapping
        else:
            price = prices
        rows: list[dict[str, Any]] = []
        unknown: list[str] = []
        errors: dict[str, str] = {}
        today = self._today()
        for sym in sorted({s.upper().strip() for s in symbols if s}):
            try:
                info = self.lookup(sym, as_of, price=price, events=events)
            except httpx.HTTPError as exc:
                errors[sym] = str(exc)
                log.warning("float_refresh_failed", symbol=sym, error=str(exc))
                continue
            if not info.known:
                unknown.append(sym)
                continue
            rows.append({**info.model_dump(), "refreshed_on": today})
        written = 0
        if rows:
            frame = pd.DataFrame(rows, columns=FLOAT_COLUMNS)
            written = store.write_table(FLOAT_TABLE, frame, FLOAT_KEYS, schema=FLOAT_SCHEMA)
        log.info("float_refresh", written=written, unknown=len(unknown), errors=len(errors))
        return {"written": written, "unknown": unknown, "errors": errors}


def _date_or_none(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
        return None
    return as_date(value)


def _float_or_none(value: Any) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def load_float_map(
    store: Store,
    *,
    today: date | None = None,
    events: pd.DataFrame | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> dict[str, FloatInfo]:
    """Latest `float` row per symbol as FloatInfo, with staleness recomputed for `today` (default: today)."""
    frame = store.read_table(FLOAT_TABLE, order_by="symbol, as_of")
    if frame.empty:
        return {}
    on = today or date.today()
    out: dict[str, FloatInfo] = {}
    for _, row in frame.drop_duplicates(subset=["symbol"], keep="last").iterrows():
        info = FloatInfo(
            symbol=str(row["symbol"]).upper(),
            shares_outstanding=_float_or_none(row.get("shares_outstanding")),
            float_shares=_float_or_none(row.get("float_shares")),
            float_estimate_method=str(row.get("float_estimate_method") or METHOD_UNKNOWN),
            as_of=_date_or_none(row.get("as_of")),
            source=str(row.get("source") or SOURCE_NONE),
            filed=_date_or_none(row.get("filed")),
            float_as_of=_date_or_none(row.get("float_as_of")),
            public_float_usd=_float_or_none(row.get("public_float_usd")),
            price_used=_float_or_none(row.get("price_used")),
            cross_check=None if pd.isna(row.get("cross_check")) else str(row.get("cross_check")),
            cik=None if pd.isna(row.get("cik")) else str(row.get("cik")),
        )
        out[info.symbol] = restamp(info, on, events, stale_after_days=stale_after_days)
    return out


__all__ = [
    "FLOAT_COLUMNS",
    "FLOAT_KEYS",
    "FLOAT_TABLE",
    "STALE_AFTER_DAYS",
    "FMPFloatAdapter",
    "FloatInfo",
    "FloatSource",
    "VendorFloat",
    "VendorFloatAdapter",
    "bars_price_lookup",
    "float_events_after",
    "latest_fact",
    "load_float_map",
    "restamp",
    "stale_reason",
]
