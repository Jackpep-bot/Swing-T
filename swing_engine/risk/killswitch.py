"""Kill switch: a file whose presence blocks every order.

Operators create it by hand (``touch state/KILL``) or via :func:`trip`. Nothing in the LLM layer is given a
tool that removes it; :func:`reset` exists for the human operator and the CLI only.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core.config import ROOT, RiskConfig

log = structlog.get_logger(__name__)

DEFAULT_KILL_SWITCH_FILE: str = RiskConfig.model_fields["kill_switch_file"].default


def resolve_state_path(path: str | Path) -> Path:
    """Relative paths (``state/KILL``, ``state/orders.sqlite``) resolve against the repo root, not the cwd."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else ROOT / p


def is_tripped(path: str | Path = DEFAULT_KILL_SWITCH_FILE) -> bool:
    """True when the kill-switch file exists. Any error reading the filesystem counts as tripped."""
    try:
        return resolve_state_path(path).exists()
    except OSError as exc:  # pragma: no cover - defensive: fail closed
        log.error("kill_switch_check_failed", path=str(path), error=str(exc))
        return True


def trip(path: str | Path = DEFAULT_KILL_SWITCH_FILE, reason: str = "") -> Path:
    """Create (or append to) the kill-switch file with a UTC timestamp and reason."""
    p = resolve_state_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {reason}".rstrip() + "\n")
    log.warning("kill_switch_tripped", path=str(p), reason=reason)
    return p


def reset(path: str | Path = DEFAULT_KILL_SWITCH_FILE) -> bool:
    """Remove the kill-switch file. Returns False when it was not set."""
    p = resolve_state_path(path)
    if not p.exists():
        return False
    p.unlink()
    log.warning("kill_switch_reset", path=str(p))
    return True


def status(path: str | Path = DEFAULT_KILL_SWITCH_FILE) -> dict[str, Any]:
    p = resolve_state_path(path)
    tripped = p.exists()
    return {"path": str(p), "tripped": tripped, "reason": p.read_text(encoding="utf-8").strip() if tripped else ""}
