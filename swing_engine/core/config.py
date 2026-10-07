"""Settings: environment variables (.env) for secrets, config/settings.yaml for everything else."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
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


class Settings(BaseModel):
    data: DataConfig = DataConfig()
    universe: UniverseConfig = UniverseConfig()
    risk: RiskConfig = RiskConfig()
    monitor: MonitorConfig = MonitorConfig()
    agent: AgentConfig = AgentConfig()
    execution: ExecutionConfig = ExecutionConfig()
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
