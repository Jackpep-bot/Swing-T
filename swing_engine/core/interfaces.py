"""Plugin interfaces. Implementations register themselves via `registry` decorators so that new
strategies, data providers, feeds, rules and brokers can be added by dropping in a module.
"""
from __future__ import annotations

import inspect
import sys
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import date
from functools import cache
from typing import Any

import pandas as pd

from .models import Event, OrderIntent, Position, Signal


class BarProvider(ABC):
    """Daily (and optionally intraday) OHLCV history. Must include delisted symbols where the vendor allows."""

    name: str

    @abstractmethod
    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        """Columns: symbol, name, exchange, type, active, listed_at, delisted_at."""

    @abstractmethod
    def daily_bars(self, symbols: Iterable[str], start: date, end: date) -> pd.DataFrame:
        """Long format: symbol, ts, open, high, low, close, volume, vwap, adj_close. Adjusted for splits."""

    def intraday_bars(self, symbols: Iterable[str], start: date, end: date, minutes: int = 1) -> pd.DataFrame:
        raise NotImplementedError(f"{self.name} has no intraday bars")


class Strategy(ABC):
    """A swing setup. Everything is computed from a feature panel so backtest and live scan share code.

    `scan` returns candidate symbols; `signals` turns the panel for those symbols into Signals with
    entry/stop/target already filled. Parameters live in `params` and are set from settings.yaml.
    """

    name: str
    description: str = ""
    default_params: dict[str, Any] = {}

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = {**self.default_params, **(params or {})}

    @abstractmethod
    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        """panel: long-format feature frame (symbol, ts, open..close, volume, feature columns)."""

    def required_features(self) -> list[str]:
        return []


@cache
def _positional_arity(func: Callable[..., Any]) -> int:
    try:
        params = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return 0
    if any(p.kind is p.VAR_POSITIONAL for p in params):
        return sys.maxsize
    return sum(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in params)


def exit_takes_position(hook: Callable[..., Any]) -> bool:
    """True when a ``should_exit`` hook accepts a third positional argument, the ``models.PositionContext``.

    Engines pass the context only then; a ``should_exit(row, bars_held)`` hook keeps the two-argument call.
    The signature is inspected once per function (cached).
    """
    func = getattr(hook, "__func__", hook)  # bound method -> function, whose signature still lists self
    return _positional_arity(func) - (func is not hook) >= 3


class Broker(ABC):
    name: str

    @abstractmethod
    def account(self) -> dict[str, Any]: ...

    @abstractmethod
    def positions(self) -> list[Position]: ...

    @abstractmethod
    def submit(self, intent: OrderIntent) -> dict[str, Any]:
        """Idempotent on intent.client_order_id. Bracket order where supported."""

    @abstractmethod
    def open_orders(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def cancel(self, order_id: str) -> None: ...


class Feed(ABC):
    """Async source of normalized Events for the live monitor."""

    name: str

    @abstractmethod
    def events(self) -> AsyncIterator[Event]: ...

    async def catch_up(self, since_event_id: str | None) -> list[Event]:
        """Replay after reconnect. Default: nothing."""
        return []


class Rule(ABC):
    """Deterministic stage-1 rule. Returns (hit_name, priority) or None. Must be <1 ms and have no I/O."""

    name: str

    @abstractmethod
    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None: ...


class Deliverer(ABC):
    name: str

    @abstractmethod
    async def send(self, title: str, body: str, priority: str, meta: dict[str, Any] | None = None) -> bool: ...
