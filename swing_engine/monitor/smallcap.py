"""Small-cap runner / pump track (docs/smallcap-spec.md). Posture is WARN/FADE: the only long edge is the early
window on catalyst-backed gappers with no dilution capacity.

Two classifiers on one snapshot plus the bag-holder scorer:
- Classifier A "runner": long candidate (grade A/B) inside 07:00-09:45 ET, expired after 09:45, never after 10:30.
- Classifier B "ramp-and-dump": structural IPO profile + behavioral no-news run => "promoted / do not buy", blocklisted.
- Bag-holder scorer: fires on any ticker at any time; >= threshold => "DO NOT HOLD / short watch".
Float unknown => warnings only, never a long alert. All thresholds come from settings.monitor.smallcap
(SmallCapThresholds mirrors config/settings.yaml); structural weights are versioned constants below.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel, Field

from swing_engine.core.models import Event, Priority

from .constants import DILUTION_FORM_PREFIXES, LULD_CODES, TOXIC_HALT_CODES
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
    def __init__(self, thresholds: SmallCapThresholds | dict[str, Any] | None = None):
        self.t = thresholds if isinstance(thresholds, SmallCapThresholds) else SmallCapThresholds.from_settings(thresholds)
        self.blocklist: set[str] = set()
        self.tainted: set[str] = set()
        self._session: dict[str, dict[str, Any]] = {}

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
            a.warnings.append("float unknown: warnings only")
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
            parts.append(f"float {s.float_m:.1f}M")
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
        """Record halts / dilution filings / SSR from pipeline events so later snapshots inherit them."""
        for sym in event.symbols:
            st = self._session.setdefault(sym.upper(), {"up_halts": 0, "halt_codes": set(), "dilution": False, "ssr": False})
            if event.kind == "halt" and event.meta.get("status", "halted") != "resumed":
                code = str(event.meta.get("reason_code", "")).upper()
                st["halt_codes"].add(code)
                if code in LULD_CODES:
                    st["up_halts"] += 1
                if code in TOXIC_HALT_CODES:
                    self.blocklist.add(sym.upper())
                    self.tainted.add(sym.upper())
            elif event.kind == "filing":
                form = str(event.meta.get("form_type", "")).upper()
                items = [str(i) for i in event.meta.get("items", [])]
                if any(form.startswith(p) for p in DILUTION_FORM_PREFIXES) or "3.02" in items:
                    st["dilution"] = True
            elif event.kind == "ssr":
                st["ssr"] = True

    def session_state(self, symbol: str) -> dict[str, Any]:
        st = self._session.get(symbol.upper(), {})
        return {k: (sorted(v) if isinstance(v, set) else v) for k, v in st.items()}

    def reset_session(self) -> None:
        self._session.clear()
        self.blocklist.clear()
