"""Helpers shared by the catalog batch-1 strategy modules (docs/strategies/*.md). Not a registered strategy."""
from __future__ import annotations

from datetime import date

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.features.extra import ensure_extra, is_extra
from swing_engine.features.patterns2 import AsOfView, as_of_view

from ._base import PRIOR_PREFIX, PanelStrategy


def with_extras(strat: PanelStrategy, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` with the strategy's ``features.extra`` columns attached (no-op when the builders already did)."""
    extra = [c for c in strat.required_features() if c not in panel.columns and is_extra(c)]
    return ensure_extra(panel, extra) if extra and not panel.empty else panel


def rows(strat: PanelStrategy, panel: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """As-of rows (``PanelStrategy.rows_as_of``) after attaching extras; empty frame for an empty panel."""
    if panel.empty:
        cols = [*panel.columns, *strat.required_features(), *(f"{PRIOR_PREFIX}{c}" for c in strat.prior_columns)]
        return pd.DataFrame(columns=list(dict.fromkeys(cols)))
    return strat.rows_as_of(with_extras(strat, panel), as_of, required=strat.required_features())


def view(strat: PanelStrategy, panel: pd.DataFrame, as_of: date, columns: list[str]) -> AsOfView:
    """``patterns2.as_of_view`` over bars + required features + ``columns`` after attaching extras."""
    return as_of_view(with_extras(strat, panel), as_of, ["open", "high", "low", "close", "volume", *columns,
                                                         *strat.required_features()])


def stop_entry(sig: Signal | None) -> Signal | None:
    """Mark a signal as a buy stop at ``sig.entry`` for the next session (EntryType.STOP)."""
    return sig.model_copy(update={"entry_type": EntryType.STOP}) if sig else None


def top_fraction(values: pd.Series, frac: float) -> pd.Series:
    """Boolean mask of the finite ``values`` in the top ``frac`` by cross-sectional percentile (decile sort)."""
    return (values.rank(pct=True) > 1.0 - frac).fillna(False)
