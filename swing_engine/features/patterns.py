"""Pattern flags and base / contraction measures (daily bars, per symbol, point-in-time).

Columns produced by :func:`add_patterns` (see ``docs/feature-contract.md``)::

    vcp_contraction  range of the latest 20-bar segment / range of the segment two segments earlier
                     (60-bar lookback split into three 20-bar segments; lower = tighter, Minervini VCP proxy)
    base_len         bars since the close was last within 5% of its 52-week high (0 on such a bar)
    burst_4pct       Stockbee momentum burst: close/prev_close >= 1.04 and volume > prev_volume and volume >= 100000
    breakout_52w     close > prior high_52w and volume >= 1.5 * prior avg_vol_50d
    inside_day       high < prev_high and low > prev_low
    key_reversal     bullish key reversal: low < prev_low and close > prev_close and volume >= 1.5 * prior avg_vol_50d

Flags are ``int64`` 0/1 and are 0 while their inputs are warming up. The volume benchmarks use the
average of the *prior* bars (``avg_vol_50d.shift(1)``) so a bar never dilutes its own benchmark.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._common import CLOSE, HIGH, LOW, VOLUME, per_symbol, require_columns, shift_per_symbol, symbol_codes
from .cross_section import rolling_max, rolling_min

VCP_SEGMENT_LEN = 20
VCP_SEGMENTS = 3
BASE_NEAR_HIGH_FRAC = 0.05
BURST_CLOSE_RATIO = 1.04
BURST_MIN_VOLUME = 100_000.0
BREAKOUT_VOL_MULT = 1.5
KEY_REVERSAL_VOL_MULT = 1.5

PATTERN_COLUMNS: tuple[str, ...] = (
    "vcp_contraction",
    "base_len",
    "burst_4pct",
    "breakout_52w",
    "inside_day",
    "key_reversal",
)


def segment_range(high: pd.Series, low: pd.Series, seg_len: int = VCP_SEGMENT_LEN) -> pd.Series:
    """``max(high over seg_len) - min(low over seg_len)`` ending at each bar (default 20 bars)."""
    return rolling_max(high, seg_len) - rolling_min(low, seg_len)


def _contraction_ratio(seg: pd.Series, first: pd.Series) -> pd.Series:
    return (seg / first).where(first > 0)


def vcp_contraction(
    high: pd.Series, low: pd.Series, seg_len: int = VCP_SEGMENT_LEN, n_segments: int = VCP_SEGMENTS
) -> pd.Series:
    """Volatility-contraction ratio: ``segment_range[t] / segment_range[t - seg_len * (n_segments - 1)]``,
    i.e. the latest segment's high-low range over the first segment's range in a ``seg_len * n_segments``
    lookback (defaults 20 x 3 = 60 bars). Values below 1 mean the range has contracted; NaN while warming
    up or when the first segment had zero range.
    """
    seg = segment_range(high, low, seg_len)
    return _contraction_ratio(seg, seg.shift(seg_len * (n_segments - 1)))


def bars_since(flag: pd.Series) -> pd.Series:
    """Bars since ``flag`` was last True (0 on a True bar); NaN before the first True."""
    pos = pd.Series(np.arange(len(flag), dtype=float), index=flag.index)
    last = pos.where(flag.fillna(False).astype(bool)).ffill()
    return pos - last


def base_len(dist_52w_high: pd.Series, near_frac: float = BASE_NEAR_HIGH_FRAC) -> pd.Series:
    """Bars since ``dist_52w_high >= -near_frac`` last held (close within 5% of the 52-week high by default)."""
    return bars_since(dist_52w_high >= -near_frac)


def burst_4pct(
    close: pd.Series, prev_close: pd.Series, volume: pd.Series, prev_volume: pd.Series
) -> pd.Series:
    """Stockbee momentum burst ``close / prev_close >= 1.04 and volume > prev_volume and volume >= 100000`` as 0/1."""
    hit = (close / prev_close >= BURST_CLOSE_RATIO) & (volume > prev_volume) & (volume >= BURST_MIN_VOLUME)
    return hit.astype(np.int64)


def breakout_52w(
    close: pd.Series, prior_high_52w: pd.Series, volume: pd.Series, prior_avg_vol: pd.Series
) -> pd.Series:
    """``close > prior_high_52w and volume >= 1.5 * prior_avg_vol`` as 0/1 (52-week high of the bars before today)."""
    hit = (close > prior_high_52w) & (volume >= BREAKOUT_VOL_MULT * prior_avg_vol)
    return hit.astype(np.int64)


def inside_day(high: pd.Series, low: pd.Series, prev_high: pd.Series, prev_low: pd.Series) -> pd.Series:
    """``high < prev_high and low > prev_low`` as 0/1."""
    return ((high < prev_high) & (low > prev_low)).astype(np.int64)


def key_reversal(
    low: pd.Series,
    prev_low: pd.Series,
    close: pd.Series,
    prev_close: pd.Series,
    volume: pd.Series,
    prior_avg_vol: pd.Series,
) -> pd.Series:
    """Bullish key reversal ``low < prev_low and close > prev_close and volume >= 1.5 * prior_avg_vol`` as 0/1."""
    hit = (low < prev_low) & (close > prev_close) & (volume >= KEY_REVERSAL_VOL_MULT * prior_avg_vol)
    return hit.astype(np.int64)


def add_patterns(df: pd.DataFrame, key: pd.Series | None = None) -> pd.DataFrame:
    """Return ``df`` with every column in :data:`PATTERN_COLUMNS` appended.

    Requires the cross-section columns ``prev_close``, ``high_52w``, ``dist_52w_high`` and ``avg_vol_50d``
    (run :func:`cross_section.add_cross_section` first). ``df`` must be sorted by ``symbol, ts``.
    """
    require_columns(
        df,
        (HIGH, LOW, CLOSE, VOLUME, "prev_close", "high_52w", "dist_52w_high", "avg_vol_50d"),
        "add_patterns",
    )
    key = symbol_codes(df) if key is None else key
    high, low, close, volume = df[HIGH], df[LOW], df[CLOSE], df[VOLUME]
    seg = per_symbol(high, key, rolling_max, VCP_SEGMENT_LEN) - per_symbol(
        low, key, rolling_min, VCP_SEGMENT_LEN
    )
    first = shift_per_symbol(seg, key, VCP_SEGMENT_LEN * (VCP_SEGMENTS - 1))
    prev_high = shift_per_symbol(high, key, 1)
    prev_low = shift_per_symbol(low, key, 1)
    prev_volume = shift_per_symbol(volume, key, 1)
    prior_high_52w = shift_per_symbol(df["high_52w"], key, 1)
    prior_avg_vol = shift_per_symbol(df["avg_vol_50d"], key, 1)
    return df.assign(
        vcp_contraction=_contraction_ratio(seg, first),
        base_len=per_symbol(df["dist_52w_high"], key, base_len, BASE_NEAR_HIGH_FRAC),
        burst_4pct=burst_4pct(close, df["prev_close"], volume, prev_volume),
        breakout_52w=breakout_52w(close, prior_high_52w, volume, prior_avg_vol),
        inside_day=inside_day(high, low, prev_high, prev_low),
        key_reversal=key_reversal(low, prev_low, close, df["prev_close"], volume, prior_avg_vol),
    )
