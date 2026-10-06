"""Tiny plugin registry. Modules under swing_engine.strategies / data / monitor register by decorator;
`discover()` imports every module in those packages so registration side effects run.
"""
from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_REGISTRY: dict[str, dict[str, type]] = {
    "strategy": {},
    "bar_provider": {},
    "broker": {},
    "feed": {},
    "rule": {},
    "deliverer": {},
}


def register(kind: str, name: str | None = None) -> Callable[[type[T]], type[T]]:
    def deco(cls: type[T]) -> type[T]:
        key = name or getattr(cls, "name", cls.__name__)
        _REGISTRY[kind][key] = cls
        return cls

    return deco


def get(kind: str, name: str) -> type:
    discover()
    try:
        return _REGISTRY[kind][name]
    except KeyError as e:
        raise KeyError(f"No {kind} named {name!r}. Known: {sorted(_REGISTRY[kind])}") from e


def names(kind: str) -> list[str]:
    discover()
    return sorted(_REGISTRY[kind])


_DISCOVERED = False


def discover() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    for pkg in ("swing_engine.strategies", "swing_engine.data", "swing_engine.monitor.adapters",
                "swing_engine.monitor.rules", "swing_engine.monitor.delivery", "swing_engine.execution"):
        try:
            mod = importlib.import_module(pkg)
        except ModuleNotFoundError:
            continue
        for m in pkgutil.iter_modules(mod.__path__):
            if m.name.startswith("_"):
                continue
            importlib.import_module(f"{pkg}.{m.name}")
