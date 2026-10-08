"""Shared plumbing for panel-driven strategies.

Not a registered strategy (leading underscore keeps `registry.discover()` from importing it as one).
Every number a strategy emits is arithmetic on panel columns and `params`; nothing here calls a model.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date
from typing import Any, NamedTuple

import pandas as pd
import structlog

from swing_engine.core.interfaces import Strategy
from swing_engine.core.models import Side, Signal

log = structlog.get_logger(__name__)

SYMBOL = "symbol"
TS = "ts"
BAR_COLUMNS: list[str] = [SYMBOL, TS, "open", "high", "low", "close", "volume"]
PRIOR_PREFIX = "prior_"

#: `regime` dict keys the strategies understand (produced by features.regime when `market` is given).
REGIME_MARKET_TREND = "market_trend_state"
REGIME_MARKET_VOL = "market_vol_regime"

#: trend_state values from features/regime.py
TREND_UP = 1
TREND_FLAT = 0
TREND_DOWN = -1

#: Parameter names shared by every strategy (each strategy still lists them in `default_params`).
P_MIN_RR = "min_reward_risk"
P_MIN_TREND = "min_trend_state"
P_MIN_MARKET_TREND = "min_market_trend_state"


class RollingSpec(NamedTuple):
    """A per-symbol rolling aggregate to attach to the as-of rows.

    `prior=True` shifts the window by one bar so it excludes the as-of bar (e.g. the prior swing high).
    Output column: `f"{fn}_{column}_{window}"`, prefixed with `prior_` when `prior` is set.
    """

    column: str
    fn: str  # "min" | "max" | "mean"
    window: int
    prior: bool = False

    @property
    def out(self) -> str:
        base = f"{self.fn}_{self.column}_{self.window}"
        return f"{PRIOR_PREFIX}{base}" if self.prior else base


def _finite(x: Any) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _local_day(ts: pd.Series) -> pd.Series:
    """Calendar day of each bar in its own timezone (tz-aware NY stamps -> NY date), as naive Timestamps."""
    s = pd.to_datetime(ts)
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_localize(None)
    return s.dt.normalize()


class PanelStrategy(Strategy):
    """Base class: `signals()` implementations call `self.rows_as_of(...)` then `self.build_signal(...)`."""

    name = "panel_base"
    description = ""
    #: panel columns the strategy reads beyond the bar columns; validated before scanning
    features_required: list[str] = []
    #: on-demand columns from `features.extra` (e.g. "ema_8", "psar", "tom_day"); the panel builders attach them
    #: via `ensure_extra(panel, required_extras(...))` before scanning
    extra_features: list[str] = []
    #: bar columns copied from the previous bar as `prior_<col>`
    prior_columns: list[str] = ["open", "high", "low", "close", "volume"]
    #: False opts out of the engine-wide breakeven-at-+1R / N-day-low trail overlay (settings.execution) in
    #: replay and the live position manager, and of `BacktestConfig.trailing` in `run_backtest`. A
    #: `params["engine_trail"]` value wins over this attribute. Cards: docs/strategies/qullamaggie_flag.md,
    #: episodic_pivot.md (the overlay cuts the winners those methods depend on).
    engine_trail: bool = True

    def required_features(self) -> list[str]:
        return list(dict.fromkeys([*self.features_required, *self.extra_features]))

    # ----------------------------------------------------------------------------- regime gate
    def market_ok(self, regime: dict[str, Any] | None) -> bool:
        """Apply the market-trend gate from `params[min_market_trend_state]` when a regime dict is given."""
        if not regime:
            return True
        state = regime.get(REGIME_MARKET_TREND)
        if state is None or not _finite(state):
            return True
        return int(state) >= int(self.params.get(P_MIN_MARKET_TREND, TREND_DOWN))

    # ----------------------------------------------------------------------------- panel slicing
    def rows_as_of(
        self,
        panel: pd.DataFrame,
        as_of: date,
        rolling: Iterable[RollingSpec] = (),
        required: Iterable[str] | None = None,
    ) -> pd.DataFrame:
        """One row per symbol for the last bar on or before `as_of`, plus `prior_*` and rolling helpers.

        Only bars dated <= `as_of` are used (point-in-time). Symbols whose last bar is older than the
        as-of session (delisted, halted, missing data) are dropped rather than scanned on stale data.
        Raises KeyError when a required column is missing so a mis-built panel fails loudly.
        """
        req = list(BAR_COLUMNS) + list(required if required is not None else self.features_required)
        missing = [c for c in req if c not in panel.columns]
        if missing:
            raise KeyError(f"{self.name}: panel is missing required columns {missing}")
        if panel.empty:
            return panel.iloc[0:0]

        day = _local_day(panel[TS])
        cutoff = pd.Timestamp(as_of)
        sub = panel.loc[day <= cutoff]
        if sub.empty:
            return sub
        sub = sub.sort_values([SYMBOL, TS], kind="stable")
        day = _local_day(sub[TS])
        grp = sub.groupby(SYMBOL, sort=False)

        extra: dict[str, pd.Series] = {}
        for col in self.prior_columns:
            extra[f"{PRIOR_PREFIX}{col}"] = grp[col].shift(1)
        for spec in rolling:
            series = grp[spec.column].transform(
                lambda s, spec=spec: getattr(s.rolling(spec.window, min_periods=spec.window), spec.fn)()
            )
            if spec.prior:
                series = series.groupby(sub[SYMBOL], sort=False).shift(1)
            extra[spec.out] = series
        sub = sub.assign(**extra, _day=day)

        session = sub["_day"].max()
        cur = sub.loc[sub["_day"] == session].groupby(SYMBOL, sort=False).tail(1)
        return cur.drop(columns="_day")

    # ----------------------------------------------------------------------------- signal builder
    def build_signal(
        self,
        row: pd.Series,
        as_of: date,
        *,
        entry: float,
        stop: float,
        target: float | None,
        score: float,
        features: dict[str, Any] | None = None,
        notes: str = "",
    ) -> Signal | None:
        """Validate geometry and wrap it in a `Signal`. Returns None for unusable geometry.

        Long only: requires stop < entry and, when a target is given, target > entry and
        reward_risk >= params[min_reward_risk].
        """
        if not (_finite(entry) and _finite(stop)) or float(stop) >= float(entry):
            return None
        entry_f, stop_f = float(entry), float(stop)
        risk = entry_f - stop_f
        target_f: float | None = None
        reward_risk: float | None = None
        if target is not None:
            if not _finite(target) or float(target) <= entry_f:
                return None
            target_f = float(target)
            reward_risk = (target_f - entry_f) / risk
            if reward_risk < float(self.params.get(P_MIN_RR, 0.0)):
                return None
        feats = {k: float(v) for k, v in (features or {}).items() if _finite(v)}
        return Signal(
            strategy=self.name,
            symbol=str(row[SYMBOL]),
            side=Side.LONG,
            as_of=as_of,
            entry=entry_f,
            stop=stop_f,
            target=target_f,
            reward_risk=reward_risk,
            score=float(score) if _finite(score) else 0.0,
            features=feats,
            notes=notes,
        )

    def trend_ok(self, row: pd.Series) -> bool:
        """`trend_state >= params[min_trend_state]`; NaN trend_state (warm-up) never passes."""
        state = row.get("trend_state")
        return _finite(state) and int(state) >= int(self.params.get(P_MIN_TREND, TREND_DOWN))

    def volume_ratio(self, row: pd.Series, avg_col: str) -> float:
        """volume / avg_col, NaN when the average is missing or zero."""
        avg = row.get(avg_col)
        if not _finite(avg) or float(avg) <= 0:
            return math.nan
        return float(row["volume"]) / float(avg)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """Rule-based exit hook for strategies whose exit is not a fixed stop/target (default: never).

        `row` is the panel row of the held symbol on the evaluation day; `bars_held` counts sessions since
        entry. Backtest/execution may call this in addition to stop/target handling.
        """
        return False

    def trail_stop(self, row: pd.Series) -> float | None:
        """Indicator trailing stop for a held position (supertrend, PSAR, chandelier, swing low), or None.

        `row` is the held symbol's panel row at the close. The engine ratchets the stop to this level (never
        loosens it, never through the close), live from the next session, in `run_backtest`, replay and the
        position manager alike. Default: no strategy trail.
        """
        return None

    trail_stop.default_hook = True  # type: ignore[attr-defined]  # engines skip the per-day row lookup

    def log_scan(self, as_of: date, n_rows: int, n_signals: int) -> None:
        log.debug("strategy.scan", strategy=self.name, as_of=str(as_of), rows=n_rows, signals=n_signals)


def finite(x: Any) -> bool:
    """Public alias used by strategy modules."""
    return _finite(x)
