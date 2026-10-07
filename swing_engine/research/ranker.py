"""Cross-sectional rank model: predict the per-date rank of the forward ``horizon``-day return from the
feature-contract columns (docs/feature-contract.md).

Label = forward N-day close-to-close return, ranked within each date (percentile in [0, 1]).
Features are normalized per date (rank percentile centred at 0, or z-score) so the model sees relative
standing, not levels. LightGBM is used when it imports (it fails on Macs without libomp), otherwise
sklearn's HistGradientBoostingRegressor; both take NaN natively. Walk-forward validation uses the purged
splitter with ``purge = horizon`` so no training label overlaps a test window.

The ranker only ranks: it never produces a price, size or stop.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import HistGradientBoostingRegressor

from swing_engine.research.cv import purged_walk_forward

log = structlog.get_logger(__name__)

SYMBOL = "symbol"
TS = "ts"
CLOSE = "close"
LABEL_COLUMN = "fwd_rank"
PRED_COLUMN = "rank_score"
DEFAULT_HORIZON = 10
MIN_SYMBOLS_PER_DATE = 5
RANK_CENTER = 0.5
ZSCORE_CLIP = 5.0
RANDOM_STATE = 0
ERROR_PREVIEW_CHARS = 120
NORMALIZE_METHODS = ("rank", "zscore")

#: Feature-contract columns with cross-sectional meaning (momentum, reversal, vol, liquidity, position, regime).
RANKER_FEATURES: tuple[str, ...] = (
    "ret_1d", "ret_5d", "ret_21d", "ret_63d", "ret_126d", "ret_252d", "mom_12_1", "rev_5d", "rev_21d",
    "vol_21d", "vol_63d", "dollar_vol_20d", "amihud_21d", "dist_52w_high", "rvol_day", "gap_pct", "range_pct",
    "close_pos", "up_days_3", "atr_pct_14", "rsi_2", "rsi_14", "macd_hist", "bb_width_20", "vcp_contraction",
    "base_len", "level_touch_pct", "trend_state", "vol_regime",
)

LGBM_PARAMS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "verbose": -1,
}
HGB_PARAMS: dict[str, Any] = {
    "max_iter": 300,
    "learning_rate": 0.05,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 50,
    "l2_regularization": 1.0,
}


@lru_cache(maxsize=1)
def _lightgbm() -> Any | None:
    try:
        import lightgbm
    except Exception as exc:  # ImportError, or OSError when libomp is missing on macOS
        log.debug("ranker.lightgbm_unavailable", error=str(exc)[:ERROR_PREVIEW_CHARS])
        return None
    return lightgbm


def backend_name() -> str:
    return "lightgbm" if _lightgbm() is not None else "sklearn"


def _make_estimator(params: dict[str, Any] | None, random_state: int) -> Any:
    lgb = _lightgbm()
    if lgb is not None:
        return lgb.LGBMRegressor(**{**LGBM_PARAMS, **(params or {})}, random_state=random_state)
    return HistGradientBoostingRegressor(**{**HGB_PARAMS, **(params or {})}, random_state=random_state)


# ----------------------------------------------------------------------------------------------- labels / features


def forward_return(panel: pd.DataFrame, horizon: int = DEFAULT_HORIZON) -> pd.Series:
    """close[t+horizon] / close[t] - 1 per symbol, aligned to ``panel``'s rows (NaN for the last ``horizon``)."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    base = panel[[SYMBOL, TS, CLOSE]].reset_index(drop=True)
    ordered = base.sort_values([SYMBOL, TS], kind="stable")
    fwd = ordered.groupby(SYMBOL, sort=False)[CLOSE].shift(-horizon) / ordered[CLOSE] - 1.0
    return pd.Series(fwd.sort_index().to_numpy(dtype=float), index=panel.index, name=f"fwd_ret_{horizon}")


def forward_return_rank(panel: pd.DataFrame, horizon: int = DEFAULT_HORIZON) -> pd.Series:
    """Per-date percentile rank of :func:`forward_return` (the training label)."""
    fwd = forward_return(panel, horizon)
    ranked = fwd.groupby(panel[TS].to_numpy()).rank(pct=True)
    return pd.Series(ranked.to_numpy(dtype=float), index=panel.index, name=LABEL_COLUMN)


def normalize_cross_section(frame: pd.DataFrame, features: list[str], method: str = "rank") -> pd.DataFrame:
    """Per-date normalization of ``features``: 'rank' (percentile - 0.5) or 'zscore' (clipped)."""
    if method not in NORMALIZE_METHODS:
        raise ValueError(f"normalize must be one of {NORMALIZE_METHODS}")
    x = pd.DataFrame(index=frame.index)
    missing = [f for f in features if f not in frame.columns]
    for f in features:
        x[f] = frame[f].astype(float) if f in frame.columns else np.nan
    if missing:
        log.warning("ranker.features_missing", missing=missing)
    keys = frame[TS].to_numpy()
    grouped = x.groupby(keys)
    if method == "rank":
        return grouped.rank(pct=True) - RANK_CENTER
    z = (x - grouped.transform("mean")) / grouped.transform("std")
    return z.clip(-ZSCORE_CLIP, ZSCORE_CLIP)


def _filter_dates(frame: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if start is None and end is None:
        return frame
    days = frame[TS].dt.date
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= days >= start
    if end is not None:
        mask &= days <= end
    return frame[mask]


def _ic_by_date(ts_values: np.ndarray, pred: np.ndarray, label: np.ndarray) -> float:
    """Mean per-date Spearman rank correlation between prediction and label."""
    df = pd.DataFrame({TS: ts_values, "pred": pred, "label": label})
    per_date = df.groupby(TS)[["pred", "label"]].apply(lambda g: g["pred"].corr(g["label"], method="spearman"))
    return float(per_date.mean()) if len(per_date) else float("nan")


def _fit(data: pd.DataFrame, features: list[str], params: dict[str, Any] | None, random_state: int) -> Any:
    est = _make_estimator(params, random_state)
    est.fit(data[features].to_numpy(dtype=float), data[LABEL_COLUMN].to_numpy(dtype=float))
    return est


# ----------------------------------------------------------------------------------------------- model


@dataclass
class RankerModel:
    model: Any
    features: list[str]
    horizon: int
    normalize: str
    backend: str
    trained_start: date | None = None
    trained_end: date | None = None
    report: dict[str, Any] = field(default_factory=dict)

    def predict(self, panel_as_of: pd.DataFrame) -> pd.Series:
        """Rank score per row (higher = expected to rank higher over the horizon).

        Indexed by symbol when the frame holds a single date, else by (ts, symbol).
        """
        if panel_as_of.empty:
            return pd.Series(dtype=float, name=PRED_COLUMN)
        df = panel_as_of.reset_index(drop=True)
        x = normalize_cross_section(df, self.features, self.normalize)
        pred = self.model.predict(x[self.features].to_numpy(dtype=float))
        if df[TS].nunique() == 1:
            index: pd.Index = pd.Index(df[SYMBOL].astype(str), name=SYMBOL)
        else:
            index = pd.MultiIndex.from_arrays([df[TS], df[SYMBOL].astype(str)], names=[TS, SYMBOL])
        return pd.Series(np.asarray(pred, dtype=float), index=index, name=PRED_COLUMN)

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as fh:
            pickle.dump(self, fh)
        return p

    @classmethod
    def load(cls, path: str | Path) -> RankerModel:
        with Path(path).open("rb") as fh:
            obj = pickle.load(fh)  # noqa: S301 - our own artifact
        if not isinstance(obj, cls):
            raise TypeError(f"{path} does not hold a RankerModel")
        return obj


def train_ranker(
    panel: pd.DataFrame,
    horizon: int = DEFAULT_HORIZON,
    start: date | None = None,
    end: date | None = None,
    *,
    features: list[str] | tuple[str, ...] | None = None,
    normalize: str = "rank",
    n_splits: int = 0,
    purge: int | None = None,
    embargo: int = 0,
    params: dict[str, Any] | None = None,
    min_symbols_per_date: int = MIN_SYMBOLS_PER_DATE,
    random_state: int = RANDOM_STATE,
) -> RankerModel:
    """Fit the rank model on ``panel`` rows dated in [start, end].

    When ``n_splits`` > 0 a purged walk-forward evaluation runs first (``purge`` defaults to ``horizon``) and
    the out-of-sample rank IC per split lands in ``RankerModel.report``. The final model is refit on every
    labelled row; rows in the last ``horizon`` days have no label and are not used.
    """
    feats = list(features or RANKER_FEATURES)
    for col in (SYMBOL, TS, CLOSE):
        if col not in panel.columns:
            raise KeyError(f"panel is missing column {col!r}")
    df = _filter_dates(panel.reset_index(drop=True), start, end)
    if df.empty:
        raise ValueError("no panel rows in the requested window")
    label = forward_return_rank(df, horizon)
    data = normalize_cross_section(df, feats, normalize)
    data[LABEL_COLUMN] = label.to_numpy()
    data[TS] = df[TS].to_numpy()
    data[SYMBOL] = df[SYMBOL].to_numpy()
    data = data[data[LABEL_COLUMN].notna()]
    per_date = data.groupby(TS)[SYMBOL].transform("size")
    data = data[per_date >= min_symbols_per_date]
    if data.empty:
        raise ValueError("no labelled rows (panel too short for the horizon or too few symbols per date)")
    dates = pd.DatetimeIndex(sorted(data[TS].unique()))
    report: dict[str, Any] = {
        "backend": backend_name(),
        "n_rows": int(len(data)),
        "n_dates": int(len(dates)),
        "n_features": len(feats),
        "horizon": horizon,
        "normalize": normalize,
    }
    if n_splits > 0:
        splits = purged_walk_forward(dates, n_splits, purge=horizon if purge is None else purge, embargo=embargo)
        ics: list[float] = []
        for train_idx, test_idx in splits:
            train_mask = data[TS].isin(dates[train_idx])
            test_mask = data[TS].isin(dates[test_idx])
            est = _fit(data[train_mask], feats, params, random_state)
            test = data[test_mask]
            pred = est.predict(test[feats].to_numpy(dtype=float))
            ics.append(_ic_by_date(test[TS].to_numpy(), np.asarray(pred), test[LABEL_COLUMN].to_numpy()))
        report.update(
            n_splits=len(splits),
            ic_by_split=ics,
            ic_mean=float(np.nanmean(ics)) if ics else float("nan"),
            ic_std=float(np.nanstd(ics)) if ics else float("nan"),
        )
    model = _fit(data, feats, params, random_state)
    out = RankerModel(
        model=model,
        features=feats,
        horizon=horizon,
        normalize=normalize,
        backend=report["backend"],
        trained_start=dates[0].date(),
        trained_end=dates[-1].date(),
        report=report,
    )
    log.info(
        "ranker.trained",
        backend=out.backend,
        rows=report["n_rows"],
        dates=report["n_dates"],
        horizon=horizon,
        ic_mean=report.get("ic_mean"),
    )
    return out
