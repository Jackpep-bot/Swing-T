"""Cross-sectional rank model: labels, normalization, walk-forward training and prediction."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.research.ranker import (
    LABEL_COLUMN,
    PRED_COLUMN,
    RANKER_FEATURES,
    RankerModel,
    backend_name,
    forward_return,
    forward_return_rank,
    normalize_cross_section,
    train_ranker,
)
from tests.fixtures.research.synthetic_panel import PLANTED_FEATURE, make_ranker_panel

HORIZON = 10
N_DAYS = 300
TRAIN_END_IDX = 199
FAST_PARAMS_SKLEARN = {"max_iter": 60}
FAST_PARAMS_LGBM = {"n_estimators": 60}


def _fast_params() -> dict:
    return FAST_PARAMS_LGBM if backend_name() == "lightgbm" else FAST_PARAMS_SKLEARN


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return make_ranker_panel(n_symbols=40, n_days=N_DAYS, seed=1, strength=0.6, horizon=HORIZON)


@pytest.fixture(scope="module")
def dates(panel) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(panel["ts"].unique()))


def _oos_ic(model: RankerModel, panel: pd.DataFrame, dates: pd.DatetimeIndex, first: int, last: int) -> float:
    ics = []
    label = forward_return_rank(panel, HORIZON)
    for d in dates[first:last]:
        rows = panel[panel["ts"] == d]
        pred = model.predict(rows)
        realized = pd.Series(label.loc[rows.index].to_numpy(), index=rows["symbol"].to_numpy())
        ics.append(pred.corr(realized, method="spearman"))
    return float(np.nanmean(ics))


def test_backend_is_guarded():
    assert backend_name() in {"lightgbm", "sklearn"}


def test_forward_return_and_rank_alignment(panel):
    one = panel[panel["symbol"] == "RNK000"].sort_values("ts")
    fwd = forward_return(panel, HORIZON).loc[one.index]
    manual = one["close"].shift(-HORIZON) / one["close"] - 1
    pd.testing.assert_series_equal(fwd.reset_index(drop=True), manual.reset_index(drop=True), check_names=False)
    assert fwd.tail(HORIZON).isna().all()
    rank = forward_return_rank(panel, HORIZON)
    assert rank.name == LABEL_COLUMN
    valid = rank.dropna()
    assert 0.0 < valid.min() and valid.max() <= 1.0
    # per-date ranks are a permutation of i/N on each date
    per_date = rank.groupby(panel["ts"].to_numpy()).nunique().dropna()
    assert per_date[per_date > 0].min() == 40


def test_normalize_cross_section_rank_and_zscore(panel):
    day = panel[panel["ts"] == panel["ts"].iloc[0]].copy()
    ranked = normalize_cross_section(day, list(RANKER_FEATURES[:3]), "rank")
    assert ranked.shape == (40, 3)
    assert ranked.min().min() > -0.5 and ranked.max().max() <= 0.5
    assert (ranked.mean() - 0.5 / 40).abs().max() < 1e-9  # pct rank of N items averages 0.5 + 0.5/N
    z = normalize_cross_section(day, [PLANTED_FEATURE], "zscore")
    assert z[PLANTED_FEATURE].mean() == pytest.approx(0.0, abs=1e-9)
    assert z[PLANTED_FEATURE].std() == pytest.approx(1.0)
    missing = normalize_cross_section(day, ["not_a_feature"], "rank")
    assert missing["not_a_feature"].isna().all()
    with pytest.raises(ValueError):
        normalize_cross_section(day, [PLANTED_FEATURE], "minmax")


def test_walk_forward_training_learns_planted_edge(panel, dates):
    model = train_ranker(panel, HORIZON, end=dates[TRAIN_END_IDX].date(), n_splits=3, params=_fast_params())
    assert model.backend == backend_name()
    assert model.horizon == HORIZON and model.features == list(RANKER_FEATURES)
    assert model.trained_end <= dates[TRAIN_END_IDX - HORIZON].date()  # last horizon days have no label
    assert model.report["n_splits"] == 3
    assert model.report["ic_mean"] > 0.1
    assert len(model.report["ic_by_split"]) == 3
    oos = _oos_ic(model, panel, dates, TRAIN_END_IDX + 1, N_DAYS - HORIZON)
    assert oos > 0.15


def test_no_edge_panel_gives_no_out_of_sample_ic(dates):
    noise = make_ranker_panel(n_symbols=40, n_days=N_DAYS, seed=5, strength=0.0, horizon=HORIZON)
    model = train_ranker(noise, HORIZON, end=dates[TRAIN_END_IDX].date(), params=_fast_params())
    assert abs(_oos_ic(model, noise, dates, TRAIN_END_IDX + 1, N_DAYS - HORIZON)) < 0.1


def test_predict_index_shapes_and_persistence(panel, dates, tmp_path):
    model = train_ranker(panel, HORIZON, end=dates[TRAIN_END_IDX].date(), params=_fast_params())
    single = model.predict(panel[panel["ts"] == dates[250]])
    assert single.name == PRED_COLUMN and single.index.name == "symbol" and len(single) == 40
    multi = model.predict(panel[panel["ts"].isin(dates[250:252])])
    assert isinstance(multi.index, pd.MultiIndex) and len(multi) == 80
    assert model.predict(panel.iloc[0:0]).empty
    p = model.save(tmp_path / "ranker.pkl")
    loaded = RankerModel.load(p)
    pd.testing.assert_series_equal(loaded.predict(panel[panel["ts"] == dates[250]]), single)


def test_missing_feature_column_is_tolerated(panel, dates):
    model = train_ranker(panel, HORIZON, end=dates[TRAIN_END_IDX].date(), params=_fast_params())
    day = panel[panel["ts"] == dates[260]].drop(columns=["rsi_2", "vol_regime"])
    pred = model.predict(day)
    assert len(pred) == 40 and pred.notna().all()


def test_train_ranker_validation(panel):
    with pytest.raises(KeyError):
        train_ranker(panel.drop(columns=["close"]), HORIZON)
    with pytest.raises(ValueError):
        train_ranker(panel, HORIZON, start=pd.Timestamp("2030-01-01").date())
    with pytest.raises(ValueError):
        train_ranker(panel.head(40), HORIZON)  # one symbol, nothing labelled across dates
