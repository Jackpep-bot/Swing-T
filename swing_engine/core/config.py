"""Settings: environment variables (.env) for secrets, config/settings.yaml for everything else."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    massive_api_key: str | None = None
    eodhd_api_key: str | None = None
    alphavantage_api_key: str | None = None
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_paper: bool = True
    quiver_api_key: str | None = None
    fmp_api_key: str | None = None  # Financial Modeling Prep: optional float/shares vendor (data.float_data)
    anthropic_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    pushover_user_key: str | None = None
    pushover_app_token: str | None = None
    edgar_user_agent: str = "swing-engine contact@example.com"


class RiskConfig(BaseModel):
    account_equity_override: float | None = None
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 10.0
    max_open_positions: int = 8
    max_sector_pct: float = 30.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 15.0
    min_reward_risk: float = 2.0
    vol_target_annual_pct: float | None = None  # if set, size = min(fixed-fractional, vol-targeted)
    kill_switch_file: str = "state/KILL"
    limits_state_file: str = "state/limits.json"  # persisted peak / day-start equity for the drawdown gate


class UniverseConfig(BaseModel):
    min_price: float = 5.0
    min_avg_dollar_volume: float = 5_000_000
    min_avg_volume: float = 500_000
    exclude_otc: bool = True
    include_etfs: bool = False
    max_symbols: int = 1500
    static_symbols: list[str] = Field(default_factory=list)


class DataConfig(BaseModel):
    bar_provider: str = "massive"  # massive | eodhd | alpaca | sample
    history_years: int = 5
    store_path: str = "data/swing.duckdb"
    event_log_path: str = "data/events.sqlite"
    calendar: str = "NYSE"
    massive_calls_per_min: float | None = None  # paid Massive plans; None = Basic's 5/min (env MASSIVE_CALLS_PER_MIN wins)


class MonitorConfig(BaseModel):
    feeds: list[str] = Field(default_factory=lambda: ["alpaca_news", "alpaca_stocks", "edgar", "nasdaq_halts"])
    watchlist: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    rvol_gate: float = 2.0
    gap_pct_alert: float = 8.0
    per_ticker_cooldown_min: int = 15
    hourly_alert_cap: int = 20
    quiet_hours_et: tuple[int, int] = (22, 6)
    classify_model: str = "claude-haiku-4-5"
    smallcap: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    review_model: str = "claude-sonnet-5-5"
    lab_model: str = "claude-opus-5-5"
    max_candidates_per_day: int = 20


class ExecutionConfig(BaseModel):
    """Autopilot and position-management rules (execution.autopilot, execution.position_manager).

    Orders are approved automatically only on a paper broker (`auto_submit_paper`); a live broker additionally
    needs `auto_submit_live` AND env SWING_ALLOW_LIVE=yes, otherwise intents are staged for a human.
    """

    auto_submit_paper: bool = True
    auto_submit_live: bool = False
    max_new_orders_per_day: int = Field(default=5, ge=0)
    require_review_approval: bool = True  # enforced only when reviews exist for the day
    cancel_unfilled_entries_after_sessions: int = Field(default=1, ge=1)
    breakeven_after_r: float | None = 1.0  # stop -> entry once the close is this many R in profit (None = off)
    trail_after_r: float | None = 2.0  # then trail to the lowest low of `trail_lookback_days` (None = off)
    trail_lookback_days: int = Field(default=10, ge=1)
    earnings_exit_days: int = Field(default=1, ge=0)  # close when earnings are within this many sessions
    max_signal_age_days: int = Field(default=3, ge=0)  # `swing autopilot` refuses older saved signals (weekend = 3)
    broker: str | None = None  # broker for `swing autopilot` and the nightly (alpaca | paper_sim); None = none
    nightly_execute: bool = False  # nightly runs positions -> execute when a broker is configured
    ledger_file: str = "state/orders.sqlite"  # OrderManager idempotency ledger


#: Market regimes the playbook router classifies (strategies.playbook.market_state; docs/methods.md 2a, 3c).
PLAYBOOK_REGIMES: tuple[str, ...] = (
    "healthy_uptrend",
    "narrow_uptrend",
    "choppy",
    "correction",
    "high_vol_selloff",
)


def default_playbook_table() -> dict[str, dict[str, float]]:
    """Regime -> {strategy: risk multiplier in [0, 1]}; a strategy absent from a regime may not open there.

    Derived from docs/methods.md (section 0 items 2-5, 3b, 3c, 7a.1) and
    docs/methods/06-breadth-regime-filters.md: breakout families only when participation confirms (Stockbee:
    breadth cross-overs mark "safe periods for breakout trading"); pullbacks in leaders in healthy and narrow
    uptrends, at reduced size in the narrow tape; RSI-2 mean reversion is the diversifier in uptrends and chop
    (Nagel 2012: reversal pays most when volatility is high, hence a small allocation in a high-vol selloff);
    no new longs in a correction (SPY below its 200-day or in a downtrend). The multipliers are an exposure
    ladder to backtest, not a published rule (doc 06, position sizing).
    """
    return {
        "healthy_uptrend": {
            "breakout_52w": 1.0,
            "sr_breakout": 1.0,
            "momentum_burst": 1.0,
            "pullback_trend": 1.0,
            "sr_bounce": 1.0,
            "rsi2_meanrev": 1.0,
            "insider_cluster": 1.0,
            # docs/methods.md 7b P1 modules: breakout families need confirmed participation (methods.md 0.3)
            "pullback_holy_grail": 1.0,
            "base_breakout": 1.0,
            "power_gap": 1.0,
            "qullamaggie_flag": 1.0,
            "episodic_pivot": 1.0,
        },
        "narrow_uptrend": {  # Oct 2026 posture: reduced size, leaders-only pullbacks, RSI-2 diversifier
            "pullback_trend": 0.5,
            "pullback_holy_grail": 0.5,  # pullback family with the RS / 52-week-high leader gate (methods.md 6.1)
            # sr_bounce: no RS / leader filter and accepts trend_state 0, so not in the leaders-only tape (3b, 3c)
            "rsi2_meanrev": 0.75,
            "insider_cluster": 0.5,
        },
        "choppy": {"rsi2_meanrev": 0.75},
        "correction": {},
        "high_vol_selloff": {"rsi2_meanrev": 0.25},
    }


class PlaybookConfig(BaseModel):
    """Market-regime router (strategies.playbook): breadth / trend / volatility thresholds and the table.

    Breadth thresholds cite docs/methods/06-breadth-regime-filters.md: % above the 50-day > 60 strong /
    < 40 weak (Hill's 60 / 40 hysteresis band, applied to the fast line), Keller's 50% line, and the
    Stockbee 10-day 4% ratio >= 2.0 (long-side swing trading favoured) / <= 0.5 (start of a bearish move).
    These are absolute levels taken from other universes; recalibrate on the engine's own universe
    (doc 06, pitfall 9).
    """

    enabled: bool = True  # False: select_strategies returns every enabled strategy at 1.0 (router off)
    market_symbol: str = "SPY"  # index proxy for the trend filter (docs/methods.md 2a: SPY vs its 200-day)
    breadth_strong_pct_above_50: float = Field(default=60.0, ge=0.0, le=100.0)
    breadth_weak_pct_above_50: float = Field(default=40.0, ge=0.0, le=100.0)
    # Keller's 50% line: a ratio-led "strong" read also needs this much of the universe above the 50-day
    breadth_confirm_pct_above_50: float = Field(default=50.0, ge=0.0, le=100.0)
    breadth_strong_ratio_10d: float = Field(default=2.0, ge=0.0)
    breadth_weak_ratio_10d: float = Field(default=0.5, ge=0.0)
    # Hill's slow line with hysteresis: % above the 200-day turns "on" above 60 and stays on until it drops below
    # 40 (doc 06 C). "strong" (breakouts allowed) needs ratio_10d >= breadth_strong_ratio_10d or this line on,
    # plus Keller's 50% confirmation (docs/methods.md 7a #1); pct_above_50 alone is never sufficient
    breadth_on_pct_above_200: float = Field(default=60.0, ge=0.0, le=100.0)
    breadth_off_pct_above_200: float = Field(default=40.0, ge=0.0, le=100.0)
    min_breadth_symbols: int = Field(default=20, ge=1)  # fewer names: breadth reads as unavailable (neutral)
    # SPY vol_21d percentile within its trailing `vol_lookback` bars; same bands as features/regime.py
    vol_low_pct: float = Field(default=0.25, ge=0.0, le=1.0)
    vol_high_pct: float = Field(default=0.75, ge=0.0, le=1.0)
    vol_lookback: int = Field(default=252, ge=2)
    near_high_pct: float = Field(default=5.0, ge=0.0)  # SPY within this % of its 52w high: bifurcation note
    regimes: dict[str, dict[str, float]] = Field(default_factory=default_playbook_table)

    @field_validator("regimes")
    @classmethod
    def _check_regimes(cls, v: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        unknown = sorted(set(v) - set(PLAYBOOK_REGIMES))
        if unknown:
            raise ValueError(f"playbook.regimes: unknown regime(s) {unknown}; known {list(PLAYBOOK_REGIMES)}")
        for regime, table in v.items():
            for name, mult in (table or {}).items():
                if not 0.0 <= float(mult) <= 1.0:
                    raise ValueError(f"playbook.regimes.{regime}.{name}: multiplier {mult} outside [0, 1]")
        return {r: dict(t or {}) for r, t in v.items()}

    @model_validator(mode="after")
    def _check_bands(self) -> PlaybookConfig:
        if self.breadth_weak_pct_above_50 > self.breadth_strong_pct_above_50:
            raise ValueError("playbook: breadth_weak_pct_above_50 must be <= breadth_strong_pct_above_50")
        if self.breadth_weak_ratio_10d > self.breadth_strong_ratio_10d:
            raise ValueError("playbook: breadth_weak_ratio_10d must be <= breadth_strong_ratio_10d")
        if self.breadth_off_pct_above_200 > self.breadth_on_pct_above_200:
            raise ValueError("playbook: breadth_off_pct_above_200 must be <= breadth_on_pct_above_200")
        if self.vol_low_pct > self.vol_high_pct:
            raise ValueError("playbook: vol_low_pct must be <= vol_high_pct")
        return self


class Settings(BaseModel):
    data: DataConfig = DataConfig()
    universe: UniverseConfig = UniverseConfig()
    risk: RiskConfig = RiskConfig()
    monitor: MonitorConfig = MonitorConfig()
    agent: AgentConfig = AgentConfig()
    execution: ExecutionConfig = ExecutionConfig()
    playbook: PlaybookConfig = PlaybookConfig()
    strategies: dict[str, dict[str, Any]] = Field(default_factory=dict)  # name -> params/enabled


@lru_cache
def load_settings(path: str | Path | None = None) -> Settings:
    p = Path(path) if path else ROOT / "config" / "settings.yaml"
    raw: dict[str, Any] = {}
    if p.exists():
        raw = yaml.safe_load(p.read_text()) or {}
    return Settings.model_validate(raw)


@lru_cache
def load_secrets() -> Secrets:
    return Secrets()
