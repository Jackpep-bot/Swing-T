"""Cross-validation splitters that respect time: purged walk-forward, purged K-fold and combinatorial purged CV.

All functions take a sorted, unique sequence of dates (or any ordered observation keys) and return
``(train_idx, test_idx)`` pairs of positional index arrays. ``purge`` is the label horizon in observations
(training labels that would overlap the test window are dropped); ``embargo`` is an extra gap for serial
correlation (Lopez de Prado, *Advances in Financial Machine Learning*, ch. 7).

Purging is symmetric: a label at ``t`` spans ``t .. t + purge``, so training rows up to ``purge`` observations
*before* a test block overlap its first labels, and training rows up to ``purge`` observations *after* it
carry labels that overlap the block's last labels (and features made of the prices inside those label
windows). Both sides are removed; ``embargo`` is added on top after the block.
"""
from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger(__name__)

Split = tuple[np.ndarray, np.ndarray]

DEFAULT_N_SPLITS = 5
DEFAULT_CPCV_GROUPS = 6
DEFAULT_CPCV_TEST_GROUPS = 2


def _check_dates(dates: Sequence[Any] | pd.Index | np.ndarray) -> int:
    n = len(dates)
    if n < 2:
        raise ValueError("need at least two observations")
    arr = pd.Index(dates)
    if not arr.is_monotonic_increasing or not arr.is_unique:
        raise ValueError("dates must be sorted ascending and unique")
    return n


def purged_walk_forward(
    dates: Sequence[Any] | pd.Index | np.ndarray,
    n_splits: int = DEFAULT_N_SPLITS,
    purge: int = 0,
    embargo: int = 0,
    *,
    test_size: int | None = None,
    window: int | None = None,
    min_train: int = 1,
) -> list[Split]:
    """Chronological walk-forward folds (train strictly before test), like sklearn's TimeSeriesSplit.

    The last ``n_splits * test_size`` observations are cut into contiguous test folds (``test_size`` defaults
    to ``n // (n_splits + 1)``); the leading remainder seeds the first train set. The train set ends
    ``purge + embargo`` observations before the test fold starts and is expanding unless ``window`` (a
    rolling number of observations) is given. Folds whose train set is shorter than ``min_train`` are skipped.
    """
    n = _check_dates(dates)
    if n_splits < 1:
        raise ValueError("n_splits must be >= 1")
    if purge < 0 or embargo < 0:
        raise ValueError("purge and embargo must be >= 0")
    size = test_size if test_size is not None else n // (n_splits + 1)
    if size < 1 or n_splits * size >= n:
        raise ValueError(f"cannot cut {n_splits} test folds of {size} from {n} observations")
    gap = purge + embargo
    splits: list[Split] = []
    first_test = n - n_splits * size
    for test_start in range(first_test, n, size):
        test = np.arange(test_start, min(test_start + size, n))
        train_end = test_start - gap
        train_start = 0 if window is None else max(0, train_end - window)
        train = np.arange(train_start, max(train_end, 0))
        if train.size < max(min_train, 1):
            log.warning("cv.fold_skipped", test_start=test_start, train_size=int(train.size), min_train=min_train)
            continue
        splits.append((train, test))
    if not splits:
        raise ValueError("no usable folds: shrink purge/embargo or n_splits")
    return splits


def purged_kfold(
    dates: Sequence[Any] | pd.Index | np.ndarray,
    n_splits: int = DEFAULT_N_SPLITS,
    purge: int = 0,
    embargo: int = 0,
) -> list[Split]:
    """Purged K-fold: contiguous test blocks; train is everything else minus ``purge`` observations on
    either side of the block and ``embargo`` further observations after it."""
    n = _check_dates(dates)
    if n_splits < 2 or n_splits > n:
        raise ValueError("n_splits must be between 2 and the number of observations")
    if purge < 0 or embargo < 0:
        raise ValueError("purge and embargo must be >= 0")
    idx = np.arange(n)
    splits: list[Split] = []
    for test in np.array_split(idx, n_splits):
        lo, hi = int(test[0]), int(test[-1])
        train = idx[(idx < lo - purge) | (idx > hi + purge + embargo)]
        splits.append((train, test))
    return splits


def combinatorial_purged(
    dates: Sequence[Any] | pd.Index | np.ndarray,
    n_groups: int = DEFAULT_CPCV_GROUPS,
    n_test_groups: int = DEFAULT_CPCV_TEST_GROUPS,
    purge: int = 0,
    embargo: int = 0,
) -> list[Split]:
    """Combinatorial purged CV: every choice of ``n_test_groups`` of ``n_groups`` contiguous blocks is a test
    set; train is the rest minus ``purge`` on either side of each test block and ``embargo`` after it."""
    n = _check_dates(dates)
    if not 1 <= n_test_groups < n_groups <= n:
        raise ValueError("need 1 <= n_test_groups < n_groups <= number of observations")
    if purge < 0 or embargo < 0:
        raise ValueError("purge and embargo must be >= 0")
    idx = np.arange(n)
    blocks = np.array_split(idx, n_groups)
    splits: list[Split] = []
    for combo in itertools.combinations(range(n_groups), n_test_groups):
        test = np.concatenate([blocks[g] for g in combo])
        keep = np.ones(n, dtype=bool)
        for g in combo:
            lo, hi = int(blocks[g][0]), int(blocks[g][-1])
            keep &= (idx < lo - purge) | (idx > hi + purge + embargo)
        splits.append((idx[keep], test))
    return splits


def fold_dates(dates: Sequence[Any] | pd.Index | np.ndarray, split: Split) -> tuple[pd.Index, pd.Index]:
    """Translate a positional split back into the date values it covers."""
    arr = pd.Index(dates)
    return arr[split[0]], arr[split[1]]
