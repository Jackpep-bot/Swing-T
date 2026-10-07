"""Append-only JSONL trial log. Every backtest / parameter sweep is a trial; the count feeds the Deflated
Sharpe Ratio (docs/gates.md gate 2), so log before looking at the result and never prune the file."""
from __future__ import annotations

import json
import math
from collections.abc import Iterator, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import structlog

from swing_engine.core.config import ROOT

log = structlog.get_logger(__name__)

DEFAULT_TRIALS_PATH = "data/trials.jsonl"
TRIAL_ID_LEN = 12
TS_FIELD = "ts"


def resolve_path(path: str | Path = DEFAULT_TRIALS_PATH) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _clean(obj: Any) -> Any:
    """JSON-safe copy: numpy scalars/arrays to Python, NaN/inf to None, dates to ISO strings."""
    if isinstance(obj, Mapping):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple | set | np.ndarray):
        return [_clean(v) for v in obj]
    if isinstance(obj, pd.Series):
        return _clean(obj.to_dict())
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, bool | str) or obj is None:
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, datetime | date | pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def log_trial(
    name: str,
    params: Mapping[str, Any],
    metrics: Mapping[str, Any],
    path: str | Path = DEFAULT_TRIALS_PATH,
    *,
    notes: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Append one trial record and return it. ``name`` groups trials (usually the strategy name)."""
    record = {
        "trial_id": uuid4().hex[:TRIAL_ID_LEN],
        TS_FIELD: datetime.now(UTC).isoformat(timespec="seconds"),
        "name": name,
        "params": _clean(params),
        "metrics": _clean(metrics),
        "notes": notes,
        "tags": list(tags or []),
    }
    p = resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    log.info("trial.logged", name=name, trial_id=record["trial_id"], path=str(p))
    return record


def iter_trials(path: str | Path = DEFAULT_TRIALS_PATH) -> Iterator[dict[str, Any]]:
    p = resolve_path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                log.warning("trial.malformed_line", path=str(p), line=lineno)


def trial_count(name: str | None = None, path: str | Path = DEFAULT_TRIALS_PATH) -> int:
    """Number of logged trials, optionally only those with ``name``."""
    return sum(1 for rec in iter_trials(path) if name is None or rec.get("name") == name)


def read_trials(path: str | Path = DEFAULT_TRIALS_PATH) -> pd.DataFrame:
    """All trials as a flat frame (``params.*`` and ``metrics.*`` columns), empty when the log is missing."""
    records = list(iter_trials(path))
    if not records:
        return pd.DataFrame(columns=["trial_id", TS_FIELD, "name", "notes", "tags"])
    return pd.json_normalize(records)
