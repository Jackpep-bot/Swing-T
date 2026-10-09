"""News / filing filter variants of existing strategies (owner-approved 2026-10-09). Each is its own registered
strategy, so each counts as a trial; the base strategy's rules, stops and exits are unchanged.

* `<base>_no_news` for the three mean-reversion strategies with the most leaderboard signals (docs/leaderboard.md,
  2024-26 window: connors_rsi2_variants 67,741, connors_tps_scale_in 46,100, connors_hpetf_rsi_variants 37,206):
  keep a signal only when the symbol had NO news on the signal session (Chan 2003: large moves without news tend to
  reverse, moves with news drift). Cards: docs/strategies/<slug>.md.
* `pullback_trend_avoid_402`: pullback_trend minus symbols with an 8-K Item 4.02 (non-reliance / restatement)
  visible in the last `avoid_402_sessions` sessions. Shows the mechanism; docs/methods.md describes the general
  filter.

`news_source` picks the no-news measure: `benzinga` = `news_flag_1d` (data.news), `8k` = `news_8k_flag_1d`
(data.filings), `auto` = benzinga where the session is covered, else the 8-K flag. A signal whose measure is NaN or
whose column is absent is dropped: "no news" must be shown, never assumed.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import SYMBOL, TS, _local_day, finite
from .connors_hpetf_rsi_variants import ConnorsHPETF
from .connors_rsi2_variants import ConnorsRSI2Variants
from .connors_tps_scale_in import ConnorsTPS
from .pullback_trend import PullbackTrend

NEWS_COL, EIGHTK_COL, DAYS_402_COL = "news_flag_1d", "news_8k_flag_1d", "days_since_402"
SRC_AUTO, SRC_BENZINGA, SRC_8K = "auto", "benzinga", "8k"
P_NEWS_SOURCE = "news_source"
AVOID_402_SESSIONS = 63  # ~one quarter; engine choice, not from a source (docs/strategies/pullback_trend_avoid_402.md)


def _session_rows(panel: pd.DataFrame, as_of: date, symbols: set[str], cols: list[str]) -> pd.DataFrame:
    """The `cols` of each symbol's bar on the latest session <= as_of (the session `rows_as_of` scans)."""
    day = _local_day(panel[TS])
    cutoff = pd.Timestamp(as_of)
    if not (day <= cutoff).any():
        return pd.DataFrame(columns=[SYMBOL, *cols]).set_index(SYMBOL)
    sub = panel.loc[(day == day[day <= cutoff].max()) & panel[SYMBOL].isin(symbols), [SYMBOL, *cols]]
    return sub.drop_duplicates(SYMBOL, keep="last").set_index(SYMBOL)


def _no_news(row: pd.Series, source: str) -> bool:
    bz, ek = row.get(NEWS_COL), row.get(EIGHTK_COL)
    if source == SRC_BENZINGA:
        flag = bz
    elif source == SRC_8K:
        flag = ek
    elif source == SRC_AUTO:
        flag = bz if finite(bz) else ek
    else:
        raise ValueError(f"unknown {P_NEWS_SOURCE} {source!r}")
    return finite(flag) and float(flag) == 0.0


class _NoNewsFilter:
    """Mixin: the base strategy's signals, kept only when the symbol had no news on the signal session."""

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        cols = [c for c in (NEWS_COL, EIGHTK_COL) if c in panel.columns]
        if not cols:
            return []
        sigs = super().signals(panel, as_of, regime)  # type: ignore[misc]
        if not sigs:
            return sigs
        rows = _session_rows(panel, as_of, {s.symbol for s in sigs}, cols)
        source = str(self.params[P_NEWS_SOURCE])  # type: ignore[attr-defined]
        return [s for s in sigs if s.symbol in rows.index and _no_news(rows.loc[s.symbol], source)]


@register("strategy", "connors_rsi2_variants_no_news")
class ConnorsRSI2VariantsNoNews(_NoNewsFilter, ConnorsRSI2Variants):
    name = "connors_rsi2_variants_no_news"
    description = "connors_rsi2_variants, only when the symbol had no news on the signal session (Chan 2003)."
    default_params: dict[str, Any] = {**ConnorsRSI2Variants.default_params, P_NEWS_SOURCE: SRC_AUTO}


@register("strategy", "connors_tps_scale_in_no_news")
class ConnorsTPSNoNews(_NoNewsFilter, ConnorsTPS):
    name = "connors_tps_scale_in_no_news"
    description = "connors_tps_scale_in, only when the symbol had no news on the signal session (Chan 2003)."
    default_params: dict[str, Any] = {**ConnorsTPS.default_params, P_NEWS_SOURCE: SRC_AUTO}


@register("strategy", "connors_hpetf_rsi_variants_no_news")
class ConnorsHPETFNoNews(_NoNewsFilter, ConnorsHPETF):
    name = "connors_hpetf_rsi_variants_no_news"
    description = "connors_hpetf_rsi_variants, only when the symbol had no news on the signal session (Chan 2003)."
    default_params: dict[str, Any] = {**ConnorsHPETF.default_params, P_NEWS_SOURCE: SRC_AUTO}


@register("strategy", "pullback_trend_avoid_402")
class PullbackTrendAvoid402(PullbackTrend):
    name = "pullback_trend_avoid_402"
    description = "pullback_trend, skipping symbols with an 8-K Item 4.02 restatement in the last N sessions."
    default_params: dict[str, Any] = {**PullbackTrend.default_params, "avoid_402_sessions": AVOID_402_SESSIONS}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if DAYS_402_COL not in panel.columns:  # no 8-K table: the filter cannot be shown, so no trial
            return []
        sigs = super().signals(panel, as_of, regime)
        if not sigs:
            return sigs
        rows = _session_rows(panel, as_of, {s.symbol for s in sigs}, [DAYS_402_COL])
        n = int(self.params["avoid_402_sessions"])

        def recent_402(sym: str) -> bool:
            d = rows.loc[sym, DAYS_402_COL] if sym in rows.index else None
            return finite(d) and float(d) < n  # NaN = no 4.02 on record

        return [s for s in sigs if not recent_402(s.symbol)]
