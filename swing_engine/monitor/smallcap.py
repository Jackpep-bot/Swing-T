"""Small-cap runner / pump track (docs/smallcap-spec.md). Posture is WARN/FADE: the only long edge is the early
window on catalyst-backed gappers with no dilution capacity.

Two classifiers on one snapshot plus the bag-holder scorer:
- Classifier A "runner": long candidate (grade A/B) inside 07:00-09:45 ET, expired after 09:45, never after 10:30.
- Classifier B "ramp-and-dump": structural IPO profile + behavioral no-news run => "promoted / do not buy", blocklisted.
- Bag-holder scorer: fires on any ticker at any time; >= threshold => "DO NOT HOLD / short watch".
Float unknown or stale => warnings only, never a long alert. A float map (`data.float_data.load_float_map`)
can be attached with `float_map=` / `set_float_map`; it fills `float_m` on snapshots that lack one and carries
the stale flag. All thresholds come from settings.monitor.smallcap (SmallCapThresholds mirrors
config/settings.yaml); structural weights are versioned constants below.

Live use (`Pipeline`): `observe(event)` keeps per-session memory (halts, dilution, SSR), per-symbol quote fields
read from single-symbol event meta (any `SmallCapSnapshot` field name, plus `price`/`close`/`halt_price` and
`gap_pct`) and a 24 h catalyst memory (news headlines / 8-K / 6-K; offerings are not catalysts).
`assess_event(event, held)` builds a snapshot per symbol from that memory, the bar reference
(`set_reference`: prev_close, avg_vol_*) and the float map, and evaluates it; symbols without a known price and
prior close, or outside the universe, are skipped. `assessment_meta` is what lands in `event.meta["smallcap"]`.
Every number in a snapshot is read from a feed, a filing or the store; nothing is guessed.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any, Protocol, runtime_checkable

import structlog
from pydantic import BaseModel, Field, ValidationError

from swing_engine.core.models import Event, Priority

from .constants import (
    DILUTION_FORM_PREFIXES,
    HALT_OPENING_STATUSES,
    LULD_CODES,
    REGULAR_OPEN,
    TOXIC_HALT_CODES,
)
from .hours import parse_hhmm, to_et

log = structlog.get_logger(__name__)

SMALLCAP_VERSION = "2026.10.06"
PCT = 100.0
SHARES_PER_M = 1_000_000.0
# Runner score-downs
PRIOR_RUN_MAX_PCT = 300.0
RUNWAY_MIN_MONTHS = 6.0
SCORE_DOWNS_NO_LONG = 2
# Ramp-and-dump
RAMP_STRUCTURAL_MIN = 4  # of 7 structural points => "profile"
RAMP_CAP_MAX_M = 300.0
RAMP_CLOSE_5S_PCT = 100.0
RAMP_CLOSE_20S_PCT = 300.0
LISTED_EXCHANGES: frozenset[str] = frozenset({"NASDAQ", "NYSE", "NYSE AMERICAN", "AMEX", "NYSEAMERICAN", "NYSE MKT"})
EXCLUDED_TYPES: frozenset[str] = frozenset({"ETF", "ETN", "SPAC", "OTC", "WARRANT", "RIGHT", "UNIT"})
# Bag-holder weights
BAG_DILUTION = 3
BAG_RUNWAY = 2
BAG_ROTATION = 2
BAG_GAP_AND_CRAP = 2
BAG_VWAP_LOST = 2
BAG_UP_HALTS = 2
BAG_FIRST_RED_DAY = 3
BAG_RAMP_PROFILE = 3
BAG_SSR = 1
BAG_TOXIC_HALT = 3
DILUTION_BAGHOLDER_DAYS = 10
RUNWAY_BAGHOLDER_MONTHS = 6.0  # < 2 quarters
WINDOW_START_ET = "07:00"
WINDOW_END_ET = "11:00"
FLOAT_UNKNOWN_WARNING = "float unknown: warnings only"
FLOAT_STALE_WARNING = "float stale: warnings only"
FLOAT_WARNINGS: frozenset[str] = frozenset({FLOAT_UNKNOWN_WARNING, FLOAT_STALE_WARNING})
# ---- live evaluation (pipeline) ---------------------------------------------------------------------------
#: event kinds the pipeline evaluates the track on
SMALLCAP_EVENT_KINDS: frozenset[str] = frozenset({"bar_trigger", "halt", "filing", "news"})
CATALYST_KINDS: frozenset[str] = frozenset({"news", "filing"})
CATALYST_FORM_PREFIXES: tuple[str, ...] = ("8-K", "6-K")
CATALYST_WINDOW_H = 24.0
#: a catalyst stamped slightly after the evaluating event (feed clock skew) still counts
CATALYST_CLOCK_SKEW_MIN = 5.0
#: a headline tagging more symbols than this is a list / round-up, not a catalyst for any one of them
CATALYST_MAX_SYMBOLS = 3
OFFERING_KEYWORDS: tuple[str, ...] = (
    "offering", "registered direct", "private placement", "at-the-market", "equity distribution agreement",
    "warrant inducement", "shelf registration",
)
UNREGISTERED_SALE_ITEM = "3.02"
#: meta keys read as the current price, in order (bar close, halt price, last trade)
PRICE_META_KEYS: tuple[str, ...] = ("price", "last_price", "close", "halt_price")
GAP_META_KEY = "gap_pct"
#: average-volume keys for the spec's 30-day ADV, in order; avg_vol_20d (bar reference) is the stored proxy
ADV_META_KEYS: tuple[str, ...] = ("adv_30d", "avg_vol_30d", "avg_vol_20d")
_CONTEXT_FIELDS: frozenset[str] = frozenset({"symbol", "now", "held"})
_REQUIRED_FIELDS: frozenset[str] = frozenset({"symbol", "now", "price", "prev_close"})
CLASSIFIER_RUNNER = "runner"
CLASSIFIER_RAMP = "ramp_and_dump"
CLASSIFIER_BAGHOLDER = "bagholder"
CLASSIFIER_WARNING = "warning"
CLASSIFIER_NONE = "none"
DO_NOT_BUY_CLASSIFIERS: frozenset[str] = frozenset({CLASSIFIER_RAMP, CLASSIFIER_BAGHOLDER})
#: tie-break between symbols of one event with the same priority (higher = more severe)
CLASSIFIER_SEVERITY: dict[str, int] = {
    CLASSIFIER_NONE: 0, CLASSIFIER_WARNING: 1, CLASSIFIER_RUNNER: 2, CLASSIFIER_BAGHOLDER: 3, CLASSIFIER_RAMP: 4,
}


@runtime_checkable
class FloatRecord(Protocol):
    """What the track needs from a float-map value (`data.float_data.FloatInfo` satisfies it)."""

    float_shares: float | None
    stale: bool


class SmallCapThresholds(BaseModel):
    enabled: bool = True
    min_price: float = 1.0
    max_price: float = 20.0
    max_float_m: float = 20.0
    preferred_float_m: float = 10.0
    max_market_cap_m: float = 200.0
    gap_pct_b_grade: float = 10.0
    gap_pct_a_grade: float = 20.0
    rvol_min: float = 5.0
    premarket_volume_min: float = 50_000
    premarket_volume_exhaustion: float = 50_000_000
    float_rotation_warn: float = 1.0
    float_rotation_no_trade: float = 5.0
    long_alert_cutoff_et: str = "09:45"
    never_long_after_et: str = "10:30"
    dilution_lookback_sessions: int = 5
    bagholder_alert_threshold: int = 6
    ramp_ipo_months: float = 24
    ramp_ipo_price_range: tuple[float, float] = (4.0, 6.0)
    ramp_ipo_max_proceeds_m: float = 25.0
    ramp_ipo_max_shares_m: float = 20.0
    ramp_5d_gain_pct: float = 50.0
    ramp_20d_gain_pct: float = 100.0
    up_halts_climax: int = 2
    up_halts_exhaustion: int = 4

    @classmethod
    def from_settings(cls, raw: dict[str, Any] | None) -> SmallCapThresholds:
        return cls.model_validate(raw or {})


class SmallCapSnapshot(BaseModel):
    """Everything the track needs about one symbol at one instant. Unknown fields stay None (=> warnings only)."""

    symbol: str
    now: datetime
    price: float
    prev_close: float
    float_m: float | None = None
    float_stale: bool = False
    market_cap_m: float | None = None
    exchange: str = "NASDAQ"
    security_type: str = "CS"
    premarket_volume: float = 0.0
    cum_volume: float = 0.0
    adv_30d: float | None = None
    premarket_high: float | None = None
    above_vwap: bool | None = None
    catalyst: bool = False
    catalyst_is_offering: bool = False
    dilution_filings_recent: int = 0
    dilution_filed_today: bool = False
    reverse_split_recent: bool = False
    prior_day_run_pct: float = 0.0
    atm_or_shelf_active: bool | None = None
    cash_runway_months: float | None = None
    going_concern: bool = False
    up_halts_today: int = 0
    halt_codes_today: list[str] = Field(default_factory=list)
    below_open_at_10: bool = False
    volume_falling: bool = False
    vwap_lost: bool = False
    first_red_day_after_run: bool = False
    ssr_triggered: bool = False
    ipo_months: float | None = None
    ipo_price: float | None = None
    ipo_proceeds_m: float | None = None
    ipo_shares_m: float | None = None
    offshore_holdco: bool = False
    microcap_underwriter: bool = False
    filings_in_window: int = 0
    gain_5d_pct: float | None = None
    gain_20d_pct: float | None = None
    degraded_feed: bool = False
    held: bool = False

    @property
    def gap_pct(self) -> float:
        return (self.price / self.prev_close - 1.0) * PCT if self.prev_close > 0 else 0.0

    @property
    def rvol(self) -> float | None:
        return self.cum_volume / self.adv_30d if self.adv_30d else None

    @property
    def float_rotation(self) -> float | None:
        return self.cum_volume / (self.float_m * SHARES_PER_M) if self.float_m else None


class SmallCapAssessment(BaseModel):
    symbol: str
    eligible_long: bool
    eligible_warn: bool
    eligibility_reasons: list[str] = Field(default_factory=list)
    long_alert: bool = False
    grade: str | None = None
    score_downs: list[str] = Field(default_factory=list)
    runner_blockers: list[str] = Field(default_factory=list)
    structural_score: int = 0
    ramp_profile: bool = False
    ramp_behavioral: bool = False
    promoted: bool = False
    bagholder_score: int = 0
    bagholder_reasons: list[str] = Field(default_factory=list)
    bagholder_alert: bool = False
    toxic: bool = False
    blocklisted: bool = False
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list)
    priority: Priority = Priority.P0
    message: str = ""


class SmallCapTrack:
    def __init__(
        self,
        thresholds: SmallCapThresholds | dict[str, Any] | None = None,
        *,
        float_map: Mapping[str, FloatRecord] | None = None,
        reference: Mapping[str, Mapping[str, Any]] | None = None,
        degraded_feed: bool = False,
    ):
        self.t = thresholds if isinstance(thresholds, SmallCapThresholds) else SmallCapThresholds.from_settings(thresholds)
        self.blocklist: set[str] = set()
        self.tainted: set[str] = set()
        self._session: dict[str, dict[str, Any]] = {}
        self._quotes: dict[str, dict[str, Any]] = {}
        #: symbol -> (last non-offering catalyst ts, last offering headline/filing ts)
        self._catalysts: dict[str, dict[str, datetime]] = {}
        self.degraded_feed = degraded_feed
        self.float_map: dict[str, FloatRecord] = {}
        self.set_float_map(float_map)
        self.reference: dict[str, dict[str, Any]] = {}
        self._dilution: dict[str, list[tuple[datetime, str]]] = {}  # survives reset_session
        # (symbol, ET day) -> (cumulative volume, pre-market volume) from the live bar engine; see service.py
        self.volume_source: Callable[[str, date], tuple[float, float] | None] | None = None
        self.set_reference(reference)

    # ---- float lookup hook ---------------------------------------------------------------------------------------
    def set_float_map(self, float_map: Mapping[str, FloatRecord] | None) -> None:
        """Attach (or replace) the symbol -> float record map produced by `data.float_data.load_float_map`."""
        self.float_map = {k.upper(): v for k, v in (float_map or {}).items()}

    def apply_float(self, s: SmallCapSnapshot) -> SmallCapSnapshot:
        """Fill `float_m` / `float_stale` from the float map when the snapshot carries no float of its own.
        A caller-supplied float wins; a stale map entry marks the snapshot stale (=> warnings only)."""
        rec = self.float_map.get(s.symbol.upper())
        if rec is None or s.float_m is not None:
            return s
        update: dict[str, Any] = {"float_stale": s.float_stale or bool(rec.stale)}
        if rec.float_shares is not None:
            update["float_m"] = float(rec.float_shares) / SHARES_PER_M
        return s.model_copy(update=update)

    # ---- universe gate ----------------------------------------------------------------------------------------
    def universe_ok(self, s: SmallCapSnapshot) -> tuple[bool, bool, list[str]]:
        """(eligible_long, eligible_warn, reasons)."""
        reasons: list[str] = []
        warn_ok = True
        if not (self.t.min_price <= s.price <= self.t.max_price):
            reasons.append("price_out_of_range")
            warn_ok = False
        if s.exchange.upper() not in LISTED_EXCHANGES:
            reasons.append("not_listed")
            warn_ok = False
        if s.security_type.upper() in EXCLUDED_TYPES:
            reasons.append("excluded_type")
            warn_ok = False
        if s.market_cap_m is not None and s.market_cap_m >= self.t.max_market_cap_m:
            reasons.append("market_cap_too_large")
            warn_ok = False
        long_ok = warn_ok
        if s.float_m is None:
            reasons.append("float_unknown")
            long_ok = False
        elif s.float_stale:
            reasons.append("float_stale")
            long_ok = False
        elif s.float_m >= self.t.max_float_m:
            reasons.append("float_too_large")
            long_ok = False
        return long_ok, warn_ok, reasons

    # ---- classifier A: runner ---------------------------------------------------------------------------------
    def runner(self, s: SmallCapSnapshot) -> tuple[str | None, list[str], list[str]]:
        """(grade or None, score_downs, blockers)."""
        blockers: list[str] = []
        et = to_et(s.now).time()
        if et > parse_hhmm(self.t.never_long_after_et):
            blockers.append("after_never_long_cutoff")
        elif et > parse_hhmm(self.t.long_alert_cutoff_et):
            blockers.append("long_alert_expired")
        if et < parse_hhmm(WINDOW_START_ET):
            blockers.append("before_window")
        gap = s.gap_pct
        if gap < self.t.gap_pct_b_grade:
            blockers.append("gap_below_b_grade")
        rvol = s.rvol
        if rvol is None or rvol < self.t.rvol_min:
            blockers.append("rvol_below_min")
        if s.premarket_volume < self.t.premarket_volume_min:
            blockers.append("premarket_volume_low")
        if not s.catalyst or s.catalyst_is_offering:
            blockers.append("no_catalyst")
        if s.dilution_filings_recent > 0 or s.dilution_filed_today:
            blockers.append("dilution_filing_recent")
        if s.above_vwap is False:
            blockers.append("below_vwap")
        if s.symbol.upper() in self.blocklist or s.symbol.upper() in self.tainted:
            blockers.append("blocklisted")
        score_downs: list[str] = []
        rot = s.float_rotation
        if rot is not None and rot > self.t.float_rotation_warn:
            score_downs.append("float_rotation")
        if s.premarket_volume > self.t.premarket_volume_exhaustion:
            score_downs.append("premarket_volume_exhaustion")
        if s.prior_day_run_pct >= PRIOR_RUN_MAX_PCT:
            score_downs.append("prior_run_extended")
        if s.reverse_split_recent:
            score_downs.append("reverse_split_recent")
        if s.atm_or_shelf_active or (s.cash_runway_months is not None and s.cash_runway_months < RUNWAY_MIN_MONTHS):
            score_downs.append("atm_shelf_or_short_runway")
        if s.up_halts_today >= self.t.up_halts_climax and rot is not None and rot >= self.t.float_rotation_warn:
            score_downs.append("climax_zone")
        if blockers:
            return None, score_downs, blockers
        grade = "A" if gap >= self.t.gap_pct_a_grade else "B"
        if len(score_downs) >= SCORE_DOWNS_NO_LONG:
            return None, score_downs, ["score_downs"]
        if len(score_downs) == 1:
            if grade == "A":
                grade = "B"
            else:
                return None, score_downs, ["score_down_on_b_grade"]
        return grade, score_downs, blockers

    # ---- classifier B: ramp-and-dump ----------------------------------------------------------------------------
    def ramp_and_dump(self, s: SmallCapSnapshot) -> tuple[int, bool, bool]:
        """(structural_score, behavioral_trigger, promoted)."""
        score = 0
        lo, hi = self.t.ramp_ipo_price_range
        if s.ipo_months is not None and s.ipo_months <= self.t.ramp_ipo_months:
            score += 1
        if s.ipo_price is not None and lo <= s.ipo_price <= hi:
            score += 1
        if s.ipo_proceeds_m is not None and s.ipo_proceeds_m <= self.t.ramp_ipo_max_proceeds_m:
            score += 1
        if s.ipo_shares_m is not None and s.ipo_shares_m <= self.t.ramp_ipo_max_shares_m:
            score += 1
        if s.offshore_holdco:
            score += 1
        if s.microcap_underwriter:
            score += 1
        if s.float_m is not None and s.float_m < self.t.max_float_m:
            score += 1
        profile = score >= RAMP_STRUCTURAL_MIN
        g5 = s.gain_5d_pct or 0.0
        g20 = s.gain_20d_pct or 0.0
        no_news = s.filings_in_window == 0
        behavioral = no_news and (g5 >= self.t.ramp_5d_gain_pct or g20 >= self.t.ramp_20d_gain_pct)
        small = s.market_cap_m is None or s.market_cap_m < RAMP_CAP_MAX_M
        if no_news and small and (g5 >= RAMP_CLOSE_5S_PCT or g20 >= RAMP_CLOSE_20S_PCT):
            behavioral = True
        promoted = profile and behavioral
        return score, behavioral, promoted

    # ---- bag-holder scorer ------------------------------------------------------------------------------------
    def bagholder_score(self, s: SmallCapSnapshot, ramp_profile: bool | None = None) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        if s.dilution_filed_today or s.dilution_filings_recent > 0:
            score += BAG_DILUTION
            reasons.append("dilution_filing")
        if s.going_concern or (s.cash_runway_months is not None and s.cash_runway_months < RUNWAY_BAGHOLDER_MONTHS):
            score += BAG_RUNWAY
            reasons.append("runway_or_going_concern")
        rot = s.float_rotation
        if rot is not None and rot > self.t.float_rotation_no_trade:
            score += BAG_ROTATION
            reasons.append("float_rotation_extreme")
        if s.below_open_at_10 and s.volume_falling:
            score += BAG_GAP_AND_CRAP
            reasons.append("gap_and_crap")
        if s.vwap_lost:
            score += BAG_VWAP_LOST
            reasons.append("vwap_lost")
        if s.up_halts_today >= self.t.up_halts_exhaustion:
            score += BAG_UP_HALTS
            reasons.append("up_halts_exhaustion")
        if s.first_red_day_after_run:
            score += BAG_FIRST_RED_DAY
            reasons.append("first_red_day")
        if ramp_profile is None:
            ramp_profile = self.ramp_and_dump(s)[0] >= RAMP_STRUCTURAL_MIN
        if ramp_profile:
            score += BAG_RAMP_PROFILE
            reasons.append("ramp_profile")
        if s.ssr_triggered:
            score += BAG_SSR
            reasons.append("ssr")
        if any(c.upper() in TOXIC_HALT_CODES for c in s.halt_codes_today):
            score += BAG_TOXIC_HALT
            reasons.append("toxic_halt")
        return score, reasons

    # ---- combined ---------------------------------------------------------------------------------------------
    def evaluate(self, s: SmallCapSnapshot) -> SmallCapAssessment:
        sym = s.symbol.upper()
        s = self.apply_float(s)
        st = self._session.get(sym, {})
        if st:
            s = s.model_copy(
                update={
                    "up_halts_today": max(s.up_halts_today, st.get("up_halts", 0)),
                    "halt_codes_today": sorted(set(s.halt_codes_today) | set(st.get("halt_codes", ()))),
                    "dilution_filed_today": s.dilution_filed_today or st.get("dilution", False),
                    "ssr_triggered": s.ssr_triggered or st.get("ssr", False),
                }
            )
        long_ok, warn_ok, reasons = self.universe_ok(s)
        a = SmallCapAssessment(symbol=sym, eligible_long=long_ok, eligible_warn=warn_ok, eligibility_reasons=reasons)
        a.degraded = s.degraded_feed
        if not warn_ok:
            a.message = f"{sym}: outside small-cap universe ({', '.join(reasons)})"
            return a
        a.structural_score, a.ramp_behavioral, a.promoted = self.ramp_and_dump(s)
        a.ramp_profile = a.structural_score >= RAMP_STRUCTURAL_MIN
        a.bagholder_score, a.bagholder_reasons = self.bagholder_score(s, a.ramp_profile)
        a.toxic = "toxic_halt" in a.bagholder_reasons
        a.bagholder_alert = a.bagholder_score >= self.t.bagholder_alert_threshold
        if a.promoted or a.toxic:
            self.blocklist.add(sym)
        a.blocklisted = sym in self.blocklist
        if a.promoted:
            a.warnings.append("promoted / do not buy")
        if a.toxic:
            a.warnings.append("toxic halt (T12/H10): no longs this session")
        if a.bagholder_alert:
            a.warnings.append(f"DO NOT HOLD / short watch (bag-holder {a.bagholder_score})")
        if s.up_halts_today >= self.t.up_halts_climax and (s.float_rotation or 0.0) >= self.t.float_rotation_warn:
            a.warnings.append("climax zone: >= 2 up-halts with float rotation, not a buy")
        if s.float_m is None:
            a.warnings.append(FLOAT_UNKNOWN_WARNING)
        elif s.float_stale:
            a.warnings.append(FLOAT_STALE_WARNING)
        if long_ok and not a.promoted and not a.toxic and not a.bagholder_alert:
            grade, downs, blockers = self.runner(s)
            a.score_downs, a.runner_blockers = downs, blockers
            if grade is not None:
                a.long_alert = True
                a.grade = grade
        elif long_ok:
            a.runner_blockers = ["warning_state"]
        a.priority = self._priority(a, s)
        a.message = self._message(a, s)
        return a

    def _priority(self, a: SmallCapAssessment, s: SmallCapSnapshot) -> Priority:
        if s.held and (a.toxic or a.bagholder_alert or a.promoted):
            return Priority.P3
        if a.promoted or a.toxic or a.bagholder_alert or a.long_alert:
            return Priority.P2
        if a.warnings:
            return Priority.P1
        return Priority.P0

    @staticmethod
    def _message(a: SmallCapAssessment, s: SmallCapSnapshot) -> str:
        parts = [f"{a.symbol} gap {s.gap_pct:+.0f}%"]
        if s.rvol is not None:
            parts.append(f"rvol {s.rvol:.1f}x")
        if s.float_m is not None:
            parts.append(f"float {s.float_m:.1f}M" + (" (stale)" if s.float_stale else ""))
        if a.long_alert:
            parts.append(f"RUNNER grade {a.grade} (early window only; expires 09:45 ET)")
        if a.score_downs:
            parts.append("score-downs: " + ", ".join(a.score_downs))
        parts.extend(a.warnings)
        if a.bagholder_reasons:
            parts.append("bag-holder: " + ", ".join(a.bagholder_reasons))
        if a.degraded:
            parts.append("DEGRADED: IEX feed misses most pre-market prints")
        return " | ".join(parts)

    # ---- session memory from the live event stream -------------------------------------------------------------
    def observe(self, event: Event) -> None:
        """Record halts / dilution filings / SSR from pipeline events so later snapshots inherit them; also the
        quote fields of single-symbol events and the catalyst memory (see the module docstring)."""
        self._remember_quote(event)
        self._remember_catalyst(event)
        for sym in event.symbols:
            st = self._session.setdefault(sym.upper(), {"up_halts": 0, "halt_codes": set(), "dilution": False, "ssr": False})
            if event.kind == "halt" and str(event.meta.get("status", "halted")).lower() in HALT_OPENING_STATUSES:
                code = str(event.meta.get("reason_code", "")).upper()
                st["halt_codes"].add(code)
                if code in LULD_CODES:
                    st["up_halts"] += 1
                if code in TOXIC_HALT_CODES:
                    self.blocklist.add(sym.upper())
                    self.tainted.add(sym.upper())
            elif event.kind == "filing":
                label = dilution_label(event.meta)
                if label is not None:
                    st["dilution"] = True
                    self.remember_dilution(sym, event.ts_source, label)
            elif event.kind == "ssr":
                st["ssr"] = True

    def session_state(self, symbol: str) -> dict[str, Any]:
        st = self._session.get(symbol.upper(), {})
        return {k: (sorted(v) if isinstance(v, set) else v) for k, v in st.items()}

    def reset_session(self) -> None:
        """New ET session: forget halts, quotes and the session blocklist (catalysts age out after 24 h).
        Dilution memory is NOT cleared: it spans ``dilution_lookback_sessions`` and is pruned by age."""
        self._session.clear()
        self._quotes.clear()
        self.blocklist.clear()

    # ---- multi-session dilution memory -----------------------------------------------------------------------
    def remember_dilution(self, symbol: str, when: datetime, label: str) -> None:
        """Record a dilution filing (424B*, S-1/S-3/F-1/F-3, 8-K item 3.02) or a reverse split for ``symbol``."""
        sym = symbol.upper()
        entries = self._dilution.setdefault(sym, [])
        if (when, label) not in entries:
            entries.append((when, label))

    def seed_dilution(self, rows: Iterable[tuple[str, datetime, str]]) -> int:
        """Load dilution history (symbol, when, label), e.g. from the event log at startup. Returns rows kept."""
        n = 0
        for sym, when, label in rows:
            self.remember_dilution(sym, when, label)
            n += 1
        return n

    def dilution_recent(self, symbol: str, now: datetime) -> tuple[int, bool]:
        """(number of dilution filings within the lookback, reverse split within REVERSE_SPLIT_RECENT_DAYS)."""
        entries = self._dilution.get(symbol.upper(), [])
        if not entries:
            return 0, False
        today = to_et(now).date()
        horizon = max(self.t.dilution_lookback_sessions, 1)
        kept: list[tuple[datetime, str]] = []
        filings, split = 0, False
        for when, label in entries:
            day = to_et(when).date()
            age_days = (today - day).days
            if age_days > max(REVERSE_SPLIT_RECENT_DAYS, horizon * CALENDAR_DAYS_PER_SESSION_MAX):
                continue  # pruned
            kept.append((when, label))
            if label == REVERSE_SPLIT_LABEL:
                split = split or age_days <= REVERSE_SPLIT_RECENT_DAYS
            elif _sessions_between(day, today) <= horizon:
                filings += 1
        self._dilution[symbol.upper()] = kept
        return filings, split

    # ---- live evaluation -----------------------------------------------------------------------------------
    def set_reference(self, reference: Mapping[str, Mapping[str, Any]] | None) -> None:
        """Attach the bar reference (`adapters.alpaca_stocks.reference_from_panel`: prev_close, avg_vol_20d, ...)."""
        self.reference = {k.upper(): dict(v) for k, v in (reference or {}).items()}

    def quote(self, symbol: str) -> dict[str, Any]:
        return dict(self._quotes.get(symbol.upper(), {}))

    def snapshot_for(self, symbol: str, now: datetime, *, held: bool = False) -> SmallCapSnapshot | None:
        """Snapshot from quote memory + bar reference + catalyst memory; None without a price and prior close.
        The price falls back to prev_close * (1 + gap_pct) when a bar trigger reported only the gap."""
        sym = symbol.upper()
        q = self._quotes.get(sym, {})
        ref = self.reference.get(sym, {})
        prev_close = _num(q.get("prev_close")) or _num(ref.get("prev_close"))
        price = _num(q.get("price"))
        gap = _num(q.get(GAP_META_KEY))
        if price is None and prev_close and gap is not None:
            price = prev_close * (1.0 + gap / PCT)
        if price is None or not prev_close or price <= 0:
            return None
        data: dict[str, Any] = {k: v for k, v in q.items() if k in SmallCapSnapshot.model_fields}
        data.update(symbol=sym, now=now, price=price, prev_close=prev_close, held=held)
        if data.get("adv_30d") is None:
            adv = next((v for v in (_num(q.get(k)) or _num(ref.get(k)) for k in ADV_META_KEYS) if v), None)
            if adv is not None:
                data["adv_30d"] = adv
        live = self.volume_source(sym, to_et(now).date()) if self.volume_source is not None else None
        if live is not None:
            cum_live, pre_live = live
            data["cum_volume"] = max(float(data.get("cum_volume") or 0.0), cum_live)
            data["premarket_volume"] = max(float(data.get("premarket_volume") or 0.0), pre_live)
        if "premarket_volume" not in data and data.get("cum_volume") is not None and to_et(now).time() < REGULAR_OPEN:
            data["premarket_volume"] = data["cum_volume"]  # before the open, cumulative volume is pre-market volume
        catalyst, offering = self._catalyst_flags(sym, now)
        filings, split = self.dilution_recent(sym, now)
        data["dilution_filings_recent"] = max(int(data.get("dilution_filings_recent") or 0), filings)
        data["reverse_split_recent"] = bool(data.get("reverse_split_recent")) or split
        data["catalyst"] = bool(data.get("catalyst")) or catalyst
        data["catalyst_is_offering"] = bool(data.get("catalyst_is_offering")) or offering
        if self.degraded_feed:
            data["degraded_feed"] = True
        try:
            return SmallCapSnapshot.model_validate(data)
        except ValidationError as exc:
            bad = {str(e["loc"][0]) for e in exc.errors() if e.get("loc")}
            log.warning("smallcap.snapshot_invalid", symbol=sym, fields=sorted(bad))
        if bad & _REQUIRED_FIELDS:
            return None
        for key in bad:  # forget the unusable meta value so it cannot poison later snapshots
            data.pop(key, None)
            q.pop(key, None)
        try:
            return SmallCapSnapshot.model_validate(data)
        except ValidationError:
            return None

    def assess_event(
        self, event: Event, held: Iterable[str] = ()
    ) -> list[tuple[SmallCapSnapshot, SmallCapAssessment]]:
        """Evaluate every symbol of a `SMALLCAP_EVENT_KINDS` event that has a snapshot and is in the universe.
        Call `observe(event)` first so the event's own halt / filing / quote is part of the snapshot."""
        if event.kind not in SMALLCAP_EVENT_KINDS:
            return []
        held_set = {s.upper() for s in held}
        out: list[tuple[SmallCapSnapshot, SmallCapAssessment]] = []
        for sym in dict.fromkeys(s.upper() for s in event.symbols if s):
            snap = self.snapshot_for(sym, event.ts_received, held=sym in held_set)
            if snap is None:
                continue
            snap = self.apply_float(snap)
            a = self.evaluate(snap)
            if a.eligible_warn:
                out.append((snap, a))
        return out

    # ---- memory helpers ------------------------------------------------------------------------------------
    def _remember_quote(self, event: Event) -> None:
        if len(event.symbols) != 1 or not event.meta:
            return  # a multi-symbol event's numbers cannot be attributed to one symbol
        meta = event.meta
        fields = {
            k: v for k, v in meta.items()
            if k in SmallCapSnapshot.model_fields and k not in _CONTEXT_FIELDS and v is not None
        }
        price = next((p for p in (_num(meta.get(k)) for k in PRICE_META_KEYS) if p is not None and p > 0), None)
        if price is not None:
            fields["price"] = price
        gap = _num(meta.get(GAP_META_KEY))
        if gap is not None:
            fields[GAP_META_KEY] = gap
        for key in ADV_META_KEYS:
            adv = _num(meta.get(key))
            if adv is not None:
                fields[key] = adv
        if fields:
            self._quotes.setdefault(event.symbols[0].upper(), {}).update(fields)

    def _remember_catalyst(self, event: Event) -> None:
        if event.kind not in CATALYST_KINDS or not event.symbols or len(event.symbols) > CATALYST_MAX_SYMBOLS:
            return
        offering = False
        catalyst = False
        if event.kind == "filing":
            form = str(event.meta.get("form_type", "")).upper()
            items = [str(i) for i in event.meta.get("items", []) or []]
            if any(form.startswith(p) for p in DILUTION_FORM_PREFIXES) or UNREGISTERED_SALE_ITEM in items:
                offering = True
            elif any(form.startswith(p) for p in CATALYST_FORM_PREFIXES):
                catalyst = True
        else:
            text = f"{event.title} {event.body}".lower()
            offering = any(k in text for k in OFFERING_KEYWORDS)
            catalyst = not offering
        if not (offering or catalyst):
            return
        key = "offering" if offering else "catalyst"
        for sym in event.symbols:
            mem = self._catalysts.setdefault(sym.upper(), {})
            prev = mem.get(key)
            if prev is None or event.ts_source > prev:
                mem[key] = event.ts_source

    def _catalyst_flags(self, symbol: str, now: datetime) -> tuple[bool, bool]:
        mem = self._catalysts.get(symbol, {})
        window = timedelta(hours=CATALYST_WINDOW_H)
        skew = timedelta(minutes=CATALYST_CLOCK_SKEW_MIN)

        def recent(key: str) -> bool:
            ts = mem.get(key)
            return ts is not None and -skew <= now - ts <= window

        return recent("catalyst"), recent("offering")


def classify_assessment(a: SmallCapAssessment) -> str:
    """Which classifier fired, most severe first (ramp-and-dump, bag-holder/toxic, runner, warning, none).
    Float unknown/stale on its own is not a warning worth an alert (it only blocks longs)."""
    if a.promoted:
        return CLASSIFIER_RAMP
    if a.bagholder_alert or a.toxic:
        return CLASSIFIER_BAGHOLDER
    if a.long_alert:
        return CLASSIFIER_RUNNER
    if any(w not in FLOAT_WARNINGS for w in a.warnings):
        return CLASSIFIER_WARNING
    return CLASSIFIER_NONE


def alert_headline(a: SmallCapAssessment, classifier: str, long_cutoff_et: str) -> str:
    if classifier == CLASSIFIER_RAMP:
        return "PROMOTED / DO NOT BUY (ramp-and-dump profile)"
    if classifier == CLASSIFIER_BAGHOLDER:
        if a.toxic and not a.bagholder_alert:
            return "TOXIC HALT / DO NOT BUY (no longs this session)"
        return f"DO NOT HOLD / DO NOT BUY: short watch (bag-holder {a.bagholder_score})"
    if classifier == CLASSIFIER_RUNNER:
        return f"RUNNER grade {a.grade}: early window only, expires {long_cutoff_et} ET"
    if classifier == CLASSIFIER_WARNING:
        return "small-cap warning: " + next(w for w in a.warnings if w not in FLOAT_WARNINGS)
    return ""


def assessment_meta(s: SmallCapSnapshot, a: SmallCapAssessment, long_cutoff_et: str) -> dict[str, Any]:
    """JSON-safe dict for ``event.meta["smallcap"]`` (read by `monitor.outcomes`)."""
    classifier = classify_assessment(a)
    reasons = list(dict.fromkeys([*a.bagholder_reasons, *a.score_downs, *a.runner_blockers, *a.eligibility_reasons]))
    return {
        "symbol": a.symbol,
        "classifier": classifier,
        "grade": a.grade,
        "bagholder_score": a.bagholder_score,
        "structural_score": a.structural_score,
        "reasons": reasons,
        "warnings": list(a.warnings),
        "float_known": s.float_m is not None,
        "float_stale": bool(s.float_stale),
        "long_alert": a.long_alert,
        "do_not_buy": classifier in DO_NOT_BUY_CLASSIFIERS,
        "priority": str(a.priority),
        "headline": alert_headline(a, classifier, long_cutoff_et),
        "message": a.message,
        "version": SMALLCAP_VERSION,
    }


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


REVERSE_SPLIT_LABEL = "reverse_split"
REVERSE_SPLIT_RECENT_DAYS = 30  # docs/smallcap-spec.md: "reverse split in last 30 days"
CALENDAR_DAYS_PER_SESSION_MAX = 2  # generous pruning bound (weekends, holidays) for the session lookback
UNREGISTERED_SALE_ITEM = "3.02"


def dilution_label(meta: Mapping[str, Any]) -> str | None:
    """Label for a filing that adds shares (424B*, S-1/S-3/F-1/F-3, 8-K item 3.02), or None."""
    form = str(meta.get("form_type", "") or "").upper()
    items = [str(i) for i in (meta.get("items") or [])]
    if any(form.startswith(p) for p in DILUTION_FORM_PREFIXES):
        return form
    if UNREGISTERED_SALE_ITEM in items:
        return f"{form or '8-K'} {UNREGISTERED_SALE_ITEM}"
    return None


def _sessions_between(start: date, end: date) -> int:
    """Weekday sessions after ``start`` up to and including ``end`` (holidays ignored: conservative)."""
    import numpy as np

    if end <= start:
        return 0
    return int(np.busday_count(start + timedelta(days=1), end + timedelta(days=1)))
