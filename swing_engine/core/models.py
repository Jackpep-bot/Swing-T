"""Shared data contracts. Every module imports from here; nothing here imports from other modules."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, Field


class Side(StrEnum):
    LONG = "long"
    SHORT = "short"


class EntryType(StrEnum):
    """How a signal enters on the next session: at the open, on a buy stop at ``entry``, or a limit at ``entry``."""

    OPEN = "open"
    STOP = "stop"
    LIMIT = "limit"


class Bar(BaseModel):
    symbol: str
    ts: datetime  # bar start, timezone-aware (America/New_York for daily)
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: float | None = None
    adj_close: float | None = None


class Signal(BaseModel):
    """A fully specified trade idea produced by a Strategy. All numbers are deterministic."""

    strategy: str
    symbol: str
    side: Side = Side.LONG
    as_of: date
    entry: float = Field(description="Reference entry price (next-open or limit)")
    entry_type: EntryType = Field(default=EntryType.OPEN, description="open: next open; stop/limit: at entry")
    stop: float
    target: float | None = None
    reward_risk: float | None = None
    score: float = Field(default=0.0, description="Strategy-specific ranking score, higher is better")
    features: dict[str, float] = Field(default_factory=dict)
    notes: str = ""

    def risk_per_share(self) -> float:
        return abs(self.entry - self.stop)


class ReviewDecision(StrEnum):
    APPROVE_FOR_RISK_CHECK = "approve_for_risk_check"
    REJECT = "reject"
    NEEDS_MORE_INFO = "needs_more_info"


class Review(BaseModel):
    """Claude's structured judgment on a Signal. Deliberately contains no prices or sizes."""

    symbol: str
    strategy: str
    thesis: str = Field(max_length=400)
    catalyst_within_hold_window: bool
    event_risk_flags: list[str] = Field(default_factory=list)
    news_contradicts_setup: bool
    insider_or_congress_signal: str = "none"
    liquidity_concern: bool
    rubric_scores: dict[str, int] = Field(default_factory=dict)
    decision: ReviewDecision
    evidence: list[str] = Field(default_factory=list)


class OrderIntent(BaseModel):
    """Output of the risk module. The only object the broker layer accepts."""

    symbol: str
    side: Side
    qty: int
    entry_limit: float | None
    stop: float
    target: float | None
    strategy: str
    client_order_id: str
    risk_dollars: float
    entry_type: EntryType = EntryType.OPEN
    notes: str = ""
    #: the entry Signal's features and date, persisted in the order ledger so live rule exits get the same
    #: PositionContext.entry_features / as_of as backtest and replay
    features: dict[str, float] = Field(default_factory=dict)
    signal_as_of: date | None = None


class Position(BaseModel):
    symbol: str
    qty: int
    avg_entry: float
    side: Side
    stop: float | None = None
    target: float | None = None
    strategy: str | None = None
    opened_at: datetime | None = None


@dataclass(frozen=True)
class PositionContext:
    """Read-only facts about a held position, the optional third argument of ``should_exit(row, bars_held, position)``.

    Built by the engines (``research.backtest``, ``research.replay`` and ``execution.position_manager``) when a
    strategy's ``should_exit`` accepts it. A fact the engine cannot recover is None (empty ``entry_features``): live,
    the order ledger keeps neither the signal's features nor its date. A rule that needs a missing fact must not fire.
    """

    entry_price: float | None = None  # entry fill (backtest / replay: slippage included; live: broker avg_entry)
    stop: float | None = None  # current stop (ratcheted by trails / breakeven)
    initial_stop: float | None = None
    bars_held: int = 0  # sessions since entry, the entry session counting as 1
    best_price: float | None = None  # highest high since entry for a long (lowest low for a short), today included
    entry_features: Mapping[str, float] = field(default_factory=dict)  # the entry Signal.features
    as_of: date | None = None  # the entry Signal.as_of

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_features", MappingProxyType(dict(self.entry_features or {})))


class Priority(StrEnum):
    P0 = "P0"  # dropped
    P1 = "P1"  # digest
    P2 = "P2"  # push, normal
    P3 = "P3"  # push, emergency, repeat until acknowledged


class Event(BaseModel):
    """Normalized item from any live feed (news, filing, halt, bar trigger, social post)."""

    event_id: str  # provider id or stable hash; UNIQUE in the event log
    source: str  # e.g. alpaca_news, edgar, nasdaq_halts, alpaca_bars, bluesky
    kind: str  # news | filing | halt | luld | ssr | bar_trigger | social | account
    ts_source: datetime
    ts_received: datetime
    symbols: list[str] = Field(default_factory=list)
    title: str = ""
    body: str = ""
    url: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    priority: Priority = Priority.P0
    rule_hits: list[str] = Field(default_factory=list)


class Classification(BaseModel):
    """Haiku's structured read of an Event. Enums only; no numbers that could size a trade."""

    relevance: str = Field(description="none|low|medium|high")
    event_type: str
    materiality: int = Field(ge=1, le=5)
    sentiment: str = Field(description="negative|neutral|positive")
    tickers: list[str] = Field(default_factory=list)
    rationale: str = Field(max_length=300)
    suggested_action: str = Field(description="ignore|watch|review|protect_position")
