"""Purged walk-forward / K-fold / combinatorial splitters."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.research.cv import combinatorial_purged, fold_dates, purged_kfold, purged_walk_forward

N = 100
DATES = pd.bdate_range("2023-01-02", periods=N)
PURGE, EMBARGO = 5, 2


def test_walk_forward_is_chronological_purged_and_expanding():
    splits = purged_walk_forward(DATES, n_splits=4, purge=PURGE, embargo=EMBARGO)
    assert len(splits) == 4
    prev_train_len = 0
    prev_test_end = -1
    for train, test in splits:
        assert train.max() < test.min()
        assert test.min() - train.max() == PURGE + EMBARGO + 1  # gap of exactly purge + embargo observations
        assert np.array_equal(test, np.arange(test.min(), test.max() + 1))  # contiguous
        assert test.min() > prev_test_end
        assert train.min() == 0 and len(train) > prev_train_len  # expanding from the start
        prev_train_len, prev_test_end = len(train), test.max()
    covered = np.concatenate([t for _, t in splits])
    assert covered.min() == N - 4 * (N // 5) and covered.max() == N - 1


def test_walk_forward_rolling_window_and_test_size():
    splits = purged_walk_forward(DATES, n_splits=3, purge=0, embargo=0, window=30, test_size=10)
    assert len(splits) == 3
    for train, test in splits:
        assert len(train) == 30 and len(test) == 10
        assert train.max() + 1 == test.min()


def test_walk_forward_skips_short_train_folds():
    splits = purged_walk_forward(np.arange(40), n_splits=3, purge=5, min_train=8)
    assert len(splits) < 3
    assert all(len(train) >= 8 for train, _ in splits)
    with pytest.raises(ValueError):
        purged_walk_forward(np.arange(40), n_splits=3, purge=35)


def test_walk_forward_validation():
    with pytest.raises(ValueError):
        purged_walk_forward(DATES[::-1], n_splits=3)
    with pytest.raises(ValueError):
        purged_walk_forward(np.array([1, 1, 2, 3]), n_splits=2)
    with pytest.raises(ValueError):
        purged_walk_forward(DATES, n_splits=200)
    with pytest.raises(ValueError):
        purged_walk_forward(DATES, n_splits=2, purge=-1)


def test_purged_kfold_removes_purge_before_and_embargo_after_test():
    splits = purged_kfold(DATES, n_splits=5, purge=PURGE, embargo=EMBARGO)
    assert len(splits) == 5
    for train, test in splits:
        lo, hi = test.min(), test.max()
        forbidden = np.arange(max(lo - PURGE, 0), min(hi + EMBARGO, N - 1) + 1)
        assert not np.intersect1d(train, forbidden).size
        assert not np.intersect1d(train, test).size
    # every observation is tested exactly once
    assert np.array_equal(np.sort(np.concatenate([t for _, t in splits])), np.arange(N))


def test_combinatorial_purged_counts_and_purging():
    splits = combinatorial_purged(DATES, n_groups=6, n_test_groups=2, purge=3, embargo=1)
    assert len(splits) == 15
    blocks = np.array_split(np.arange(N), 6)
    for train, test in splits:
        assert len(test) in {len(blocks[0]) * 2, len(blocks[0]) + len(blocks[-1]), len(blocks[-1]) * 2}
        assert not np.intersect1d(train, test).size
        for b in blocks:
            if np.intersect1d(b, test).size:
                assert not np.intersect1d(train, np.arange(b[0] - 3, b[-1] + 2)).size


def test_fold_dates_maps_back_to_values():
    (train, test), *_ = purged_walk_forward(DATES, n_splits=2, purge=1)
    tr_dates, te_dates = fold_dates(DATES, (train, test))
    assert tr_dates[-1] < te_dates[0]
    assert len(te_dates) == len(test) and te_dates[0] == DATES[test[0]]
