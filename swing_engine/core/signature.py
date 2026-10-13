"""`engine_sig`: which code and which config made a decision.

``engine_signature(settings)`` = first ``SIG_LEN`` hex of sha256(git HEAD sha + sha256 of the resolved settings).
The git sha is read once per process; without git it is the literal ``nogit`` (so the signature then only tracks
the config). Stamped on every row of the ``events`` table (ops.receipts).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from functools import lru_cache

from swing_engine.core.config import ROOT, Settings

NO_GIT = "nogit"
SIG_LEN = 8
GIT_TIMEOUT_S = 5


@lru_cache(maxsize=1)
def git_sha() -> str:
    """HEAD commit sha of the repo this package runs from, or ``nogit``."""
    try:
        out = subprocess.run(  # noqa: S603, S607 - fixed argv, no shell
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return NO_GIT
    return out.stdout.strip() or NO_GIT


def config_hash(settings: Settings) -> str:
    """sha256 of the resolved settings as key-sorted JSON (secrets live in ``Secrets``, never in here)."""
    text = json.dumps(settings.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def engine_signature(settings: Settings) -> str:
    return hashlib.sha256(f"{git_sha()}{config_hash(settings)}".encode()).hexdigest()[:SIG_LEN]
