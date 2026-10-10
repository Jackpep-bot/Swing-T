"""On-demand feature registry for the catalog strategies (docs/catalog/catalog.json, docs/strategies/*.md).

``build_panel`` produces the fixed contract columns; everything else a strategy needs is named in its
``extra_features`` class attribute and attached by :func:`ensure_extra`, which computes only the columns the panel
lacks (cached panels from the store carry none of them). Names resolve two ways:

* exact names in :data:`EXTRA_FEATURES` (``connors_rsi``, ``psar``, ``tom_day``, ``mansfield_rs`` ...);
* parametric names in :data:`EXTRA_PATTERNS` (``ema_8``, ``atr_10``, ``stoch_k_14_3``, ``dc_high_20``, ``st_dir_10_3``,
  ``gapm_slope_40_20`` ...), plus three generic wrappers over any resolvable column: ``prev_<col>`` (previous bar of
  the same symbol), ``<col>_rank`` (cross-sectional percentile on the same session) and ``sma_<n>_of_<col>`` (any MA
  of any column).

Every column uses only bars at or before its own row (per symbol), the same session's rows (ranks), the market
proxy's bars at or before that session (relative strength, beta, correlation) or the published NYSE calendar (calendar
flags; ``pre_holiday_*`` count scheduled holidays only, never pandas_market_calendars' ad-hoc closures such as 9/11,
Hurricane Sandy or mourning days, which were not known in advance), so appending later bars never changes an earlier
value. Flags are float 0/1 and NaN while their inputs warm up.
Cumulative lines (``obv``, ``ad_line``) start at the first bar in the panel; use their changes, not their level.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from ._common import (
    CLOSE,
    OHLCV,
    SYMBOL_COL,
    TS_COL,
    per_symbol,
    session_key,
    shift_per_symbol,
    symbol_codes,
)
from .cross_section import pct_return, realized_vol, rolling_max, rolling_mean, rolling_min
from .indicators import ema, rsi, sma, true_range, wilder_smooth
from .panel import FEATURE_COLUMNS
from .patterns import bars_since
from .patterns2 import PATTERNS2_COLUMNS, _di, _dx, directional_movement

MARKET_SYMBOL = "SPY"  # market proxy when ensure_extra gets no market frame (ops.nightly.MARKET_SYMBOL)
SESSIONS_PER_MONTH = 21

# --- defaults named by the cards (docs/strategies/<slug>.md) and catalog formulas
BB_STD_MULT = 2.0
KC_ATR_MULT = 1.5  # TradeStation / TTM Keltner: sma_n +/- 1.5 x simple-mean ATR(n) (keltner_channel_breakout, ttm_squeeze)
CCI_CONSTANT = 0.015
KAMA_FAST = 2
KAMA_SLOW = 30
PSAR_AF_START = 0.02
PSAR_AF_STEP = 0.02
PSAR_AF_MAX = 0.20
SUPERTREND_ATR = 10
SUPERTREND_MULT = 3.0
CONNORS_RSI_PRICE = 3
CONNORS_RSI_STREAK = 2
CONNORS_PCTRANK = 100
WIDE_RANGE_MULT = 1.5
WIDE_RANGE_WINDOW = 20
HOT_BY_PRICE_SPAN = 20
RS_WINDOW = 252  # Mansfield RS (52 weeks of sessions), rs_line new high, beta default
ID_WINDOW = 252  # frog-in-the-pan information discreteness: months t-12 .. t-2
ID_SKIP = 21
IBD_RS_WEIGHTS: tuple[tuple[int, float], ...] = ((63, 2.0), (126, 1.0), (189, 1.0), (252, 1.0))
IBD_RS_MIN, IBD_RS_MAX = 1.0, 99.0
TENKAN, KIJUN, SENKOU_B = 9, 26, 52
KST_ROC: tuple[int, ...] = (10, 15, 20, 30)
KST_SMA: tuple[int, ...] = (10, 10, 10, 15)
KST_SIGNAL = 9
TSI_LONG, TSI_SHORT = 25, 13
UO_WINDOWS: tuple[int, ...] = (7, 14, 28)
UO_WEIGHTS: tuple[float, ...] = (4.0, 2.0, 1.0)
AO_FAST, AO_SLOW = 5, 34
VFI_COEF = 0.2
VFI_VCOEF = 2.5
VFI_STD_WINDOW = 30
VFI_SMOOTH = 3
GAPM_LENGTH = 40  # Kaufman gap momentum (Traders' Tips code, non-cumulative), defaults 40 / 20
GAPM_SIGNAL = 20
GAPM_NO_DOWN_GAPS = 1.0  # ratio when there were no down gaps in the window (published code)
EHLERS_WARMUP = 100  # bars per symbol before Ehlers filters are trusted (ehlers_dsp_family card)
TOM_MAX_OFFSET = 5  # tom_day defined for |offset| <= 5 sessions around the month end
TOM_WINDOW = (-1, 3)
TOM_PRE = (-5, -2)
SANTA_DEC_SESSIONS = 5  # last 5 December sessions + first 2 January sessions
SANTA_JAN_SESSIONS = 2
CALENDAR_PAD_DAYS = 40
PCT = 100.0

Feature = Callable[["_Ctx"], pd.Series]


# ----------------------------------------------------------------------------------------------- context
class _Ctx:
    """One computation over a panel sorted by ``symbol, ts`` (RangeIndex); memoises intermediate columns."""

    def __init__(self, df: pd.DataFrame, market: pd.DataFrame | None) -> None:
        self.df = df
        self.key = symbol_codes(df)
        self.market = market
        self.cache: dict[str, Any] = {}
        self.o, self.h, self.l, self.c, self.v = (df[c].astype(float) for c in OHLCV)
        brk = np.flatnonzero(np.diff(self.key.to_numpy()) != 0) + 1
        self.bounds = list(zip(np.r_[0, brk], np.r_[brk, len(df)], strict=True))

    def col(self, name: str) -> pd.Series:
        if name in self.df.columns:
            return self.df[name]
        if name not in self.cache:
            fn = resolve(name)
            if fn is None:
                raise KeyError(f"unknown feature {name!r}")
            self.cache[name] = fn(self).astype(float)
        return self.cache[name]

    def memo(self, key: str, thunk: Callable[[], Any]) -> Any:
        if key not in self.cache:
            self.cache[key] = thunk()
        return self.cache[key]

    def ps(self, x: pd.Series, fn: Callable[..., pd.Series], *args: Any) -> pd.Series:
        return per_symbol(x, self.key, fn, *args)

    def shift(self, x: pd.Series, n: int = 1) -> pd.Series:
        return shift_per_symbol(x, self.key, n)

    def loop(self, fn: Callable[..., Any], *cols: pd.Series) -> Any:
        """Run a numpy function on each symbol's contiguous slice; returns one array (or a tuple of arrays)."""
        arrs = [c.to_numpy(dtype=float) for c in cols]
        parts = [fn(*(a[s:e] for a in arrs)) for s, e in self.bounds]
        if parts and isinstance(parts[0], tuple):
            return tuple(np.concatenate(p) for p in zip(*parts, strict=True))
        return np.concatenate(parts) if parts else np.array([], dtype=float)

    def series(self, arr: np.ndarray) -> pd.Series:
        return pd.Series(arr, index=self.df.index, dtype=float)

    def prev_close(self) -> pd.Series:
        return self.memo("_prev_close", lambda: self.shift(self.c))

    def tr(self) -> pd.Series:
        return self.memo("_tr", lambda: true_range(self.h, self.l, self.prev_close()))

    def rsum(self, x: pd.Series, n: int) -> pd.Series:
        return self.ps(x, lambda s: s.rolling(n, min_periods=n).sum())


def _flag(cond: pd.Series, valid: pd.Series) -> pd.Series:
    return cond.astype(float).where(valid)


def _windows(a: np.ndarray, n: int) -> np.ndarray | None:
    return sliding_window_view(a, n) if len(a) >= n else None


# ----------------------------------------------------------------------------------------------- moving averages
def _wma_np(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    w = _windows(a, n)
    if w is not None:
        weights = np.arange(1, n + 1, dtype=float)
        out[n - 1 :] = w @ weights / weights.sum()
    return out


def _wma(s: pd.Series, n: int) -> pd.Series:
    return pd.Series(_wma_np(s.to_numpy(dtype=float), n), index=s.index)


def _hma(s: pd.Series, n: int) -> pd.Series:
    raw = 2.0 * _wma(s, max(n // 2, 1)) - _wma(s, n)
    return _wma(raw, max(int(np.sqrt(n)), 1))


def _dema(s: pd.Series, n: int) -> pd.Series:
    e = ema(s, n)
    return 2.0 * e - ema(e, n)


def _tema(s: pd.Series, n: int) -> pd.Series:
    e1 = ema(s, n)
    e2 = ema(e1, n)
    return 3.0 * e1 - 3.0 * e2 + ema(e2, n)


_MA: dict[str, Callable[[pd.Series, int], pd.Series]] = {
    "sma": sma, "ema": ema, "wma": _wma, "hma": _hma, "dema": _dema, "tema": _tema,
}


def _ma(ctx: _Ctx, kind: str, n: str, of: str | None) -> pd.Series:
    src = ctx.c if of is None else ctx.col(of)
    return ctx.ps(src.astype(float), _MA[kind], int(n))


def _sma_slope(ctx: _Ctx, n: str, k: str) -> pd.Series:
    m = ctx.col(f"sma_{n}")
    return m / ctx.shift(m, int(k)) - 1.0


# ----------------------------------------------------------------------------------------------- volatility / range
def _atr(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.tr(), wilder_smooth, int(n))


def _atr_sma(ctx: _Ctx, n: str) -> pd.Series:
    """Simple mean of true range (TradeStation AvgTrueRange / TTM), not Wilder."""
    return ctx.ps(ctx.tr(), rolling_mean, int(n))


def _atr_high(ctx: _Ctx, n: str) -> pd.Series:
    a = ctx.col("atr_14")
    hi = ctx.ps(a, rolling_max, int(n))
    return _flag(a >= hi, hi.notna())


def _bb(ctx: _Ctx, part: str, n: str) -> pd.Series:
    w = int(n)
    mid = ctx.col(f"sma_{w}")
    sd = ctx.ps(ctx.c, lambda s: s.rolling(w, min_periods=w).std(ddof=0))
    up, lo = mid + BB_STD_MULT * sd, mid - BB_STD_MULT * sd
    if part == "pctb":
        return ((ctx.c - lo) / (up - lo)).where(up > lo)
    return {"upper": up, "lower": lo, "width": (up - lo) / mid}[part]


def _kc(ctx: _Ctx, part: str, n: str) -> pd.Series:
    mid = ctx.col(f"sma_{n}")
    width = KC_ATR_MULT * ctx.col(f"atr_sma_{n}")
    return {"mid": mid, "upper": mid + width, "lower": mid - width}[part]


def _donchian(ctx: _Ctx, side: str, n: str) -> pd.Series:
    """Channel of the ``n`` bars BEFORE this one (Turtle / Donchian breakout reference)."""
    src, fn = (ctx.h, rolling_max) if side == "high" else (ctx.l, rolling_min)
    return ctx.shift(ctx.ps(src, fn, int(n)))


def _hilo(ctx: _Ctx, side: str, n: str) -> pd.Series:
    """Highest high / lowest low of the last ``n`` bars including this one."""
    return ctx.ps(ctx.h, rolling_max, int(n)) if side == "high" else ctx.ps(ctx.l, rolling_min, int(n))


def _wvf(ctx: _Ctx, n: str) -> pd.Series:
    hc = ctx.ps(ctx.c, rolling_max, int(n))
    return PCT * (hc - ctx.l) / hc


def _nr(ctx: _Ctx, n: str) -> pd.Series:
    """Narrowest range of the last ``n`` bars: range strictly below every one of the prior ``n - 1`` ranges."""
    rng = ctx.h - ctx.l
    prior = ctx.shift(ctx.ps(rng, rolling_min, int(n) - 1))
    return _flag(rng < prior, prior.notna())


def _inside(ctx: _Ctx) -> pd.Series:
    ph, pl = ctx.shift(ctx.h), ctx.shift(ctx.l)
    return _flag((ctx.h < ph) & (ctx.l > pl), ph.notna())


def _id_nr4(ctx: _Ctx) -> pd.Series:
    nr4, inside = ctx.col("nr4"), _inside(ctx)
    return (nr4 * inside).where(nr4.notna() & inside.notna())


def _wide_range_bar(ctx: _Ctx) -> pd.Series:
    """Range >= 1.5 x mean range of the PRIOR 20 bars (the bar does not dilute its own benchmark)."""
    rng = ctx.h - ctx.l
    avg = ctx.shift(ctx.ps(rng, rolling_mean, WIDE_RANGE_WINDOW))
    return _flag(rng >= WIDE_RANGE_MULT * avg, avg.notna())


# ----------------------------------------------------------------------------------------------- oscillators
def _rsi(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.c, rsi, int(n))


def _stochrsi(ctx: _Ctx, n: str) -> pd.Series:
    r = ctx.col(f"rsi_{n}")
    lo, hi = ctx.ps(r, rolling_min, int(n)), ctx.ps(r, rolling_max, int(n))
    return ((r - lo) / (hi - lo)).where(hi > lo)


def _roc(ctx: _Ctx, n: str) -> pd.Series:
    return PCT * ctx.ps(ctx.c, pct_return, int(n))


def _stoch_fast(ctx: _Ctx, n: int) -> pd.Series:
    hh, ll = ctx.ps(ctx.h, rolling_max, n), ctx.ps(ctx.l, rolling_min, n)
    return (PCT * (ctx.c - ll) / (hh - ll)).where(hh > ll)


def _stoch_k(ctx: _Ctx, n: str, slow: str | None) -> pd.Series:
    k = ctx.memo(f"_stochk_{n}", lambda: _stoch_fast(ctx, int(n)))
    return k if slow is None else ctx.ps(k, sma, int(slow))


def _stoch_d(ctx: _Ctx, n: str, slow: str, d: str) -> pd.Series:
    return ctx.ps(ctx.col(f"stoch_k_{n}_{slow}"), sma, int(d))


def _pct_r(ctx: _Ctx, n: str) -> pd.Series:
    """Williams %R in [-100, 0]."""
    hh, ll = ctx.ps(ctx.h, rolling_max, int(n)), ctx.ps(ctx.l, rolling_min, int(n))
    return (-PCT * (hh - ctx.c) / (hh - ll)).where(hh > ll)


def _mad(s: pd.Series, n: int) -> pd.Series:
    out = np.full(len(s), np.nan)
    w = _windows(s.to_numpy(dtype=float), n)
    if w is not None:
        out[n - 1 :] = np.abs(w - w.mean(axis=1, keepdims=True)).mean(axis=1)
    return pd.Series(out, index=s.index)


def _cci(ctx: _Ctx, n: str) -> pd.Series:
    tp = ctx.col("hlc3")
    mad = ctx.ps(tp, _mad, int(n))
    return ((tp - ctx.ps(tp, sma, int(n))) / (CCI_CONSTANT * mad)).where(mad > 0)


def _mfi(ctx: _Ctx, n: str) -> pd.Series:
    tp = ctx.col("hlc3")
    dtp = tp - ctx.shift(tp)
    flow = tp * ctx.v
    pos = ctx.rsum(flow.where(dtp > 0, 0.0).where(dtp.notna()), int(n))
    neg = ctx.rsum(flow.where(dtp < 0, 0.0).where(dtp.notna()), int(n))
    out = PCT - PCT / (1.0 + pos / neg)
    return out.where(neg > 0, PCT).where(pos.notna() & neg.notna())


def _cmo(ctx: _Ctx, n: str) -> pd.Series:
    d = ctx.c - ctx.prev_close()
    su, sd = ctx.rsum(d.clip(lower=0.0), int(n)), ctx.rsum((-d).clip(lower=0.0), int(n))
    return (PCT * (su - sd) / (su + sd)).where(su + sd > 0)


def _trix(ctx: _Ctx, n: str) -> pd.Series:
    w = int(n)
    e3 = ctx.ps(ctx.c, lambda s: ema(ema(ema(s, w), w), w))
    return PCT * (e3 / ctx.shift(e3) - 1.0)


def _tsi(ctx: _Ctx) -> pd.Series:
    d = ctx.c - ctx.prev_close()
    num = ctx.ps(d, lambda s: ema(ema(s, TSI_LONG), TSI_SHORT))
    den = ctx.ps(d.abs(), lambda s: ema(ema(s, TSI_LONG), TSI_SHORT))
    return (PCT * num / den).where(den > 0)


def _uo(ctx: _Ctx) -> pd.Series:
    pc = ctx.prev_close()
    low_ = np.minimum(ctx.l, pc.fillna(ctx.l))
    bp = ctx.c - low_
    tr = np.maximum(ctx.h, pc.fillna(ctx.h)) - low_
    avgs = [ctx.rsum(bp, w) / ctx.rsum(tr, w) for w in UO_WINDOWS]
    return PCT * sum(wt * a for wt, a in zip(UO_WEIGHTS, avgs, strict=True)) / sum(UO_WEIGHTS)


def _ao(ctx: _Ctx) -> pd.Series:
    mid = (ctx.h + ctx.l) / 2.0
    return ctx.ps(mid, sma, AO_FAST) - ctx.ps(mid, sma, AO_SLOW)


def _power(ctx: _Ctx, side: str, n: str) -> pd.Series:
    e = ctx.col(f"ema_{n}")
    return (ctx.h if side == "bull" else ctx.l) - e


def _pzo(ctx: _Ctx, n: str) -> pd.Series:
    d = ctx.c - ctx.prev_close()
    signed = (np.sign(d) * ctx.c).where(d.notna())
    return PCT * ctx.ps(signed, ema, int(n)) / ctx.ps(ctx.c.where(d.notna()), ema, int(n))


def _kst_parts(ctx: _Ctx) -> tuple[pd.Series, pd.Series]:
    def build() -> tuple[pd.Series, pd.Series]:
        rcma = [ctx.ps(PCT * ctx.ps(ctx.c, pct_return, r), sma, s) for r, s in zip(KST_ROC, KST_SMA, strict=True)]
        kst = sum((i + 1) * x for i, x in enumerate(rcma))
        return kst, ctx.ps(kst, sma, KST_SIGNAL)

    return ctx.memo("_kst", build)


# ----------------------------------------------------------------------------------------------- trend strength
def _adx_parts(ctx: _Ctx, n: int) -> dict[str, pd.Series]:
    def build() -> dict[str, pd.Series]:
        pc = ctx.prev_close()
        plus_dm, minus_dm = directional_movement(ctx.h, ctx.l, ctx.shift(ctx.h), ctx.shift(ctx.l))
        atr_s = ctx.ps(ctx.tr().where(pc.notna()), wilder_smooth, n)
        pdi = _di(ctx.ps(plus_dm, wilder_smooth, n), atr_s)
        mdi = _di(ctx.ps(minus_dm, wilder_smooth, n), atr_s)
        return {"adx": ctx.ps(_dx(pdi, mdi), wilder_smooth, n), "plus_di": pdi, "minus_di": mdi}

    return ctx.memo(f"_adx_{n}", build)


def _adx(ctx: _Ctx, part: str, n: str) -> pd.Series:
    return _adx_parts(ctx, int(n))[part]


def _er(ctx: _Ctx, n: str) -> pd.Series:
    """Kaufman efficiency ratio |C_t - C_{t-n}| / sum |dC| over n bars."""
    w = int(n)
    noise = ctx.rsum((ctx.c - ctx.prev_close()).abs(), w)
    return ((ctx.c - ctx.shift(ctx.c, w)).abs() / noise).where(noise > 0)


def _kama_np(c: np.ndarray, er: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(c), np.nan)
    if len(c) < n + 1:
        return out
    fast, slow = 2.0 / (KAMA_FAST + 1), 2.0 / (KAMA_SLOW + 1)
    out[n - 1] = c[:n].mean()  # seeded with an SMA (catalog: Kaufman)
    for t in range(n, len(c)):
        sc = (er[t] * (fast - slow) + slow) ** 2
        out[t] = out[t - 1] + sc * (c[t] - out[t - 1])
    return out


def _kama(ctx: _Ctx, n: str) -> pd.Series:
    w = int(n)
    return ctx.series(ctx.loop(lambda c, er: _kama_np(c, er, w), ctx.c, ctx.col(f"er_{n}")))


def _vhf(ctx: _Ctx, n: str) -> pd.Series:
    w = int(n)
    noise = ctx.rsum((ctx.c - ctx.prev_close()).abs(), w)
    span = ctx.ps(ctx.c, rolling_max, w) - ctx.ps(ctx.c, rolling_min, w)
    return (span / noise).where(noise > 0)


def _linreg(s: pd.Series, n: int, what: str) -> pd.Series:
    t = pd.Series(np.arange(len(s), dtype=float), index=s.index)
    r = s.rolling(n, min_periods=n)
    if what == "slope":
        return r.cov(t) / t.rolling(n, min_periods=n).var()
    return r.corr(t) ** 2


def _linreg_slope(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.c, _linreg, int(n), "slope")


def _r2(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.c, _linreg, int(n), "r2")


def _aroon(ctx: _Ctx, part: str, n: str) -> pd.Series:
    w = int(n)

    def since(a: np.ndarray, hi: bool) -> np.ndarray:
        out = np.full(len(a), np.nan)
        win = _windows(a, w + 1)
        if win is not None:
            rev = win[:, ::-1]  # most recent first: ties resolve to the latest extreme
            out[w:] = (rev.argmax(axis=1) if hi else rev.argmin(axis=1)).astype(float)
        return out

    up = PCT * (w - ctx.series(ctx.loop(lambda a: since(a, True), ctx.h))) / w
    dn = PCT * (w - ctx.series(ctx.loop(lambda a: since(a, False), ctx.l))) / w
    return {"up": up, "down": dn, "osc": up - dn}[part]


# ----------------------------------------------------------------------------------------------- volume
def _cmf(ctx: _Ctx, n: str) -> pd.Series:
    rng = ctx.h - ctx.l
    mfv = (((ctx.c - ctx.l) - (ctx.h - ctx.c)) / rng).where(rng > 0, 0.0) * ctx.v
    vol = ctx.rsum(ctx.v, int(n))
    return (ctx.rsum(mfv, int(n)) / vol).where(vol > 0)


def _ii_pct(ctx: _Ctx, n: str) -> pd.Series:
    rng = ctx.h - ctx.l
    ii = ((2.0 * ctx.c - ctx.h - ctx.l) / rng).where(rng > 0, 0.0) * ctx.v
    vol = ctx.rsum(ctx.v, int(n))
    return (PCT * ctx.rsum(ii, int(n)) / vol).where(vol > 0)


def _force(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps((ctx.c - ctx.prev_close()) * ctx.v, ema, int(n))


def _obv(ctx: _Ctx) -> pd.Series:
    step = (np.sign(ctx.c - ctx.prev_close()) * ctx.v).fillna(0.0)
    return ctx.ps(step, lambda s: s.cumsum())


def _ad_line(ctx: _Ctx) -> pd.Series:
    rng = ctx.h - ctx.l
    mfv = (((ctx.c - ctx.l) - (ctx.h - ctx.c)) / rng).where(rng > 0, 0.0) * ctx.v
    return ctx.ps(mfv, lambda s: s.cumsum())


def _vfi(ctx: _Ctx, n: str) -> pd.Series:
    """Katsanos Volume Flow Indicator (coef 0.2, vcoef 2.5, 30-bar cutoff stdev, EMA 3 smoothing)."""
    w = int(n)
    tp = ctx.col("hlc3")
    inter = np.log(tp) - np.log(ctx.shift(tp))
    cutoff = VFI_COEF * ctx.ps(inter, lambda s: s.rolling(VFI_STD_WINDOW, min_periods=VFI_STD_WINDOW).std()) * ctx.c
    vave = ctx.shift(ctx.ps(ctx.v, rolling_mean, w))
    vc = np.minimum(ctx.v, VFI_VCOEF * vave)
    mf = tp - ctx.shift(tp)
    vcp = vc.where(mf > cutoff, (-vc).where(mf < -cutoff, 0.0)).where(cutoff.notna() & vave.notna())
    return ctx.ps((ctx.rsum(vcp, w) / vave).where(vave > 0), ema, VFI_SMOOTH)


# ----------------------------------------------------------------------------------------------- streaks / mean reversion
def _streak_one(c: pd.Series) -> pd.Series:
    d = np.sign(c.diff())
    run = (d != d.shift()).cumsum()
    return ((d.groupby(run).cumcount() + 1) * d).where(d.notna())


def _streak(ctx: _Ctx) -> pd.Series:
    """Connors streak: +k after k consecutive up closes, -k after k down closes, 0 on an unchanged close."""
    return ctx.ps(ctx.c, _streak_one)


def _pct_rank_prior(s: pd.Series, n: int) -> pd.Series:
    """Percent (0-100) of the previous ``n`` values strictly below the current one (Connors PercentRank)."""
    out = np.full(len(s), np.nan)
    w = _windows(s.to_numpy(dtype=float), n + 1)
    if w is not None:
        below = (w[:, :-1] < w[:, -1:]).sum(axis=1) * PCT / n
        out[n:] = np.where(np.isnan(w).any(axis=1), np.nan, below)
    return pd.Series(out, index=s.index)


def _pctrank_ret(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.ps(ctx.c, pct_return, 1), _pct_rank_prior, int(n))


def _connors_rsi(ctx: _Ctx) -> pd.Series:
    """ConnorsRSI(3, 2, 100) = mean(RSI3(close), RSI2(streak), PercentRank100(ret_1d))."""
    streak_rsi = ctx.ps(ctx.col("streak"), rsi, CONNORS_RSI_STREAK)
    return (ctx.col(f"rsi_{CONNORS_RSI_PRICE}") + streak_rsi + ctx.col(f"pctrank_ret_{CONNORS_PCTRANK}")) / 3.0


# ----------------------------------------------------------------------------------------------- returns / momentum
def _mom(ctx: _Ctx, months: str, skip: str) -> pd.Series:
    long_, short = int(months) * SESSIONS_PER_MONTH, int(skip) * SESSIONS_PER_MONTH
    return ctx.shift(ctx.c, short) / ctx.shift(ctx.c, long_) - 1.0


def _max_ret(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.ps(ctx.c, pct_return, 1), rolling_max, int(n))


def _vol_max(ctx: _Ctx, n: str) -> pd.Series:
    return ctx.ps(ctx.v, rolling_max, int(n))


def _dist_52w_low(ctx: _Ctx) -> pd.Series:
    return ctx.c / ctx.ps(ctx.l, rolling_min, RS_WINDOW) - 1.0


def _id_score(ctx: _Ctx) -> pd.Series:
    """Da-Gurun-Warachka information discreteness sgn(PRET) x (%neg - %pos) over t-252 .. t-21 (lower = smoother)."""
    d = ctx.c - ctx.prev_close()
    n = ID_WINDOW - ID_SKIP
    pos = ctx.shift(ctx.rsum((d > 0).astype(float).where(d.notna()), n), ID_SKIP) / n
    neg = ctx.shift(ctx.rsum((d < 0).astype(float).where(d.notna()), n), ID_SKIP) / n
    return np.sign(ctx.col(f"mom_{ID_WINDOW // SESSIONS_PER_MONTH}_{ID_SKIP // SESSIONS_PER_MONTH}")) * (neg - pos)


def _hot_by_price(ctx: _Ctx) -> pd.Series:
    """IBKR Hot by Price, signed: (close - prev_close) / EMA20(|close - open|) of the PRIOR bars."""
    avg = ctx.shift(ctx.ps((ctx.c - ctx.o).abs(), ema, HOT_BY_PRICE_SPAN))
    return ((ctx.c - ctx.prev_close()) / avg).where(avg > 0)


def _rs_rating_ibd(ctx: _Ctx) -> pd.Series:
    """IBD RS rating reconstruction: percentile (1-99, same session) of 2*P/P63 + P/P126 + P/P189 + P/P252."""
    raw = sum(w * ctx.c / ctx.shift(ctx.c, n) for n, w in IBD_RS_WEIGHTS)
    pct = raw.groupby(session_key(ctx.df[TS_COL]), sort=False).rank(pct=True)
    return (pct * IBD_RS_MAX).round().clip(IBD_RS_MIN, IBD_RS_MAX)


# ----------------------------------------------------------------------------------------------- market-relative
def _market_close(ctx: _Ctx) -> tuple[pd.Series, pd.Series]:
    """(market close, market 1-session return) aligned to each row's session; NaN without a market proxy."""

    def build() -> tuple[pd.Series, pd.Series]:
        m = ctx.market
        if m is None:
            m = ctx.df.loc[ctx.df[SYMBOL_COL] == MARKET_SYMBOL]
        sess = session_key(ctx.df[TS_COL])
        if m is None or m.empty:
            nan = pd.Series(np.nan, index=ctx.df.index)
            return nan, nan
        mc = (
            m.assign(_s=session_key(pd.Series(pd.to_datetime(m[TS_COL]), index=m.index)))
            .sort_values("_s")
            .drop_duplicates("_s", keep="last")
            .set_index("_s")[CLOSE]
            .astype(float)
        )
        return sess.map(mc), sess.map(mc / mc.shift(1) - 1.0)

    return ctx.memo("_market", build)


def _rs_line(ctx: _Ctx) -> pd.Series:
    return ctx.c / _market_close(ctx)[0]


def _mansfield(ctx: _Ctx) -> pd.Series:
    rs = ctx.col("rs_line")
    return PCT * (rs / ctx.ps(rs, sma, RS_WINDOW) - 1.0)


def _rs_new_high(ctx: _Ctx) -> pd.Series:
    rs = ctx.col("rs_line")
    hi = ctx.ps(rs, rolling_max, RS_WINDOW)
    return _flag(rs >= hi, hi.notna())


def _rel_ret_1d(ctx: _Ctx) -> pd.Series:
    return ctx.ps(ctx.c, pct_return, 1) - _market_close(ctx)[1]


def _beta(ctx: _Ctx, n: str) -> pd.Series:
    w = int(n)
    r = ctx.ps(ctx.c, pct_return, 1)
    m = _market_close(ctx)[1]
    ok = r.notna() & m.notna()
    r, m = r.where(ok), m.where(ok)
    mean = lambda x: ctx.ps(x, rolling_mean, w)  # noqa: E731
    var = mean(m * m) - mean(m) ** 2
    return ((mean(r * m) - mean(r) * mean(m)) / var).where(var > 0)


def _corr_market(ctx: _Ctx, n: str) -> pd.Series:
    """Pearson correlation of the symbol's close with the market proxy's close over the last ``n`` bars (price
    levels, like np.corrcoef on the two closes); NaN while either window is incomplete or flat."""
    w = int(n)

    def corr(c: np.ndarray, m: np.ndarray) -> np.ndarray:
        return pd.Series(c).rolling(w, min_periods=w).corr(pd.Series(m)).replace([np.inf, -np.inf], np.nan).to_numpy()

    return ctx.series(ctx.loop(corr, ctx.c, _market_close(ctx)[0]))


# ----------------------------------------------------------------------------------------------- recursive stops
def _psar_np(h: np.ndarray, lo: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Wilder parabolic SAR. Row t holds the SAR for the NEXT bar, the direction after bar t and the AF in force."""
    n = len(h)
    sar_out, dir_out, af_out = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    if n < 2:
        return sar_out, dir_out, af_out
    up, sar, ep, af = True, lo[0], h[0], PSAR_AF_START
    for t in range(1, n):
        if up and lo[t] < sar:  # stop-and-reverse; the new SAR starts at the prior extreme point
            up, sar, ep, af = False, ep, lo[t], PSAR_AF_START
        elif not up and h[t] > sar:
            up, sar, ep, af = True, ep, h[t], PSAR_AF_START
        elif up and h[t] > ep:
            ep, af = h[t], min(af + PSAR_AF_STEP, PSAR_AF_MAX)
        elif not up and lo[t] < ep:
            ep, af = lo[t], min(af + PSAR_AF_STEP, PSAR_AF_MAX)
        nxt = sar + af * (ep - sar)
        # the SAR may not enter the range of this bar or the one before it
        nxt = min(nxt, lo[t], lo[t - 1]) if up else max(nxt, h[t], h[t - 1])
        sar_out[t], dir_out[t], af_out[t] = nxt, 1.0 if up else -1.0, af
        sar = nxt
    return sar_out, dir_out, af_out


def _psar(ctx: _Ctx, part: int) -> pd.Series:
    return ctx.series(ctx.memo("_psar", lambda: ctx.loop(_psar_np, ctx.h, ctx.l))[part])


def _supertrend_np(
    h: np.ndarray, lo: np.ndarray, c: np.ndarray, atr_: np.ndarray, mult: float
) -> tuple[np.ndarray, np.ndarray]:
    n = len(c)
    line, direction = np.full(n, np.nan), np.full(n, np.nan)
    mid = (h + lo) / 2.0
    bu, bl = mid + mult * atr_, mid - mult * atr_
    fu = fl = np.nan
    d = -1.0
    for t in range(n):
        if np.isnan(atr_[t]):
            continue
        if np.isnan(fu):  # first bar with an ATR: start in a downtrend (TradingView ta.supertrend)
            fu, fl = bu[t], bl[t]
        else:
            fu = bu[t] if (bu[t] < fu or c[t - 1] > fu) else fu
            fl = bl[t] if (bl[t] > fl or c[t - 1] < fl) else fl
            if d < 0 and c[t] > fu:
                d = 1.0
            elif d > 0 and c[t] < fl:
                d = -1.0
        line[t], direction[t] = (fl if d > 0 else fu), d
    return line, direction


def _supertrend(ctx: _Ctx, part: str, n: str | None, mult: str | None) -> pd.Series:
    w = int(n) if n else SUPERTREND_ATR
    m = float(mult) if mult else SUPERTREND_MULT
    atr_ = ctx.col(f"atr_{w}")
    res = ctx.memo(f"_st_{w}_{m}", lambda: ctx.loop(lambda h, lo, c, a: _supertrend_np(h, lo, c, a, m),
                                                   ctx.h, ctx.l, ctx.c, atr_))
    return ctx.series(res[0 if part == "line" else 1])


# ----------------------------------------------------------------------------------------------- Ehlers filters
def _super_smoother_np(x: np.ndarray, period: float) -> np.ndarray:
    a = np.exp(-1.414 * np.pi / period)
    c2 = 2.0 * a * np.cos(1.414 * np.pi / period)
    c3 = -a * a
    c1 = 1.0 - c2 - c3
    f = x.astype(float).copy()
    for t in range(2, len(x)):
        f[t] = c1 * (x[t] + x[t - 1]) / 2.0 + c2 * f[t - 1] + c3 * f[t - 2]
    return f


def _highpass_np(x: np.ndarray, period: float) -> np.ndarray:
    ang = 0.707 * 2.0 * np.pi / period
    alpha = (np.cos(ang) + np.sin(ang) - 1.0) / np.cos(ang)
    hp = np.zeros(len(x))
    for t in range(2, len(x)):
        hp[t] = ((1 - alpha / 2) ** 2 * (x[t] - 2 * x[t - 1] + x[t - 2]) + 2 * (1 - alpha) * hp[t - 1]
                 - (1 - alpha) ** 2 * hp[t - 2])
    return hp


def _warm(a: np.ndarray) -> np.ndarray:
    out = a.astype(float).copy()
    out[:EHLERS_WARMUP] = np.nan
    return out


def _ehlers(ctx: _Ctx, kind: str, n: str) -> pd.Series:
    fn = _super_smoother_np if kind == "ss" else _highpass_np
    return ctx.series(ctx.loop(lambda x: _warm(fn(x, float(n))), ctx.c))


def _roof(ctx: _Ctx, hp: str, ss: str) -> pd.Series:
    return ctx.series(ctx.loop(lambda x: _warm(_super_smoother_np(_highpass_np(x, float(hp)), float(ss))), ctx.c))


# ----------------------------------------------------------------------------------------------- gap momentum
def _gapm(ctx: _Ctx, part: str, length: str | None, signal: str | None) -> pd.Series:
    """Kaufman gap momentum: 100 x sum(up gaps) / sum(down gaps) over ``length`` (1 when no down gaps),
    signal = SMA(signal_length) of it, slope = sign of the signal's one-bar change."""
    n = int(length) if length else GAPM_LENGTH
    s = int(signal) if signal else GAPM_SIGNAL
    gap = ctx.o - ctx.prev_close()
    up, dn = ctx.rsum(gap.clip(lower=0.0), n), ctx.rsum((-gap).clip(lower=0.0), n)
    ratio = (PCT * up / dn).where(dn > 0, GAPM_NO_DOWN_GAPS).where(up.notna() & dn.notna())
    if part == "ratio":
        return ratio
    sig = ctx.ps(ratio, sma, s)
    if part == "signal":
        return sig
    return np.sign(sig - ctx.shift(sig))


# ----------------------------------------------------------------------------------------------- price transforms
def _heikin_ashi(ctx: _Ctx) -> dict[str, pd.Series]:
    def build() -> dict[str, pd.Series]:
        ha_c = (ctx.o + ctx.h + ctx.l + ctx.c) / 4.0
        seed = ctx.shift(ha_c).fillna((ctx.o + ctx.c) / 2.0)  # first bar of each symbol seeds (open + close) / 2
        ha_o = ctx.ps(seed, lambda s: s.ewm(alpha=0.5, adjust=False).mean())
        return {
            "ha_open": ha_o, "ha_close": ha_c,
            "ha_high": pd.concat([ctx.h, ha_o, ha_c], axis=1).max(axis=1),
            "ha_low": pd.concat([ctx.l, ha_o, ha_c], axis=1).min(axis=1),
        }

    return ctx.memo("_ha", build)


def _ichimoku(ctx: _Ctx, part: str) -> pd.Series:
    def mid(n: int) -> pd.Series:
        return (ctx.ps(ctx.h, rolling_max, n) + ctx.ps(ctx.l, rolling_min, n)) / 2.0

    if part == "tenkan":
        return mid(TENKAN)
    if part == "kijun":
        return mid(KIJUN)
    if part == "span_a":  # plotted KIJUN bars ahead, so the value in force at t was computed at t - KIJUN
        return ctx.shift((ctx.col(f"tenkan_{TENKAN}") + ctx.col(f"kijun_{KIJUN}")) / 2.0, KIJUN)
    return ctx.shift(mid(SENKOU_B), KIJUN)


def _cloud(ctx: _Ctx, side: str) -> pd.Series:
    a, b = ctx.col(f"span_a_{KIJUN}"), ctx.col(f"span_b_{KIJUN}")
    return np.maximum(a, b) if side == "high" else np.minimum(a, b)


def _pivots(ctx: _Ctx) -> dict[str, pd.Series]:
    """Floor-trader pivots from the symbol's PRIOR calendar month (H, L, C); daily charts use monthly pivots."""

    def build() -> dict[str, pd.Series]:
        month = session_key(ctx.df[TS_COL]).dt.to_period("M")
        g = pd.DataFrame({"k": ctx.key, "m": month, "h": ctx.h, "l": ctx.l, "c": ctx.c})
        agg = g.groupby(["k", "m"], sort=True).agg(h=("h", "max"), l=("l", "min"), c=("c", "last"))
        prev = agg.groupby(level="k").shift(1)
        p = (prev["h"] + prev["l"] + prev["c"]) / 3.0
        rng = prev["h"] - prev["l"]
        levels = {"piv_p": p, "piv_r1": 2 * p - prev["l"], "piv_s1": 2 * p - prev["h"],
                  "piv_r2": p + rng, "piv_s2": p - rng}
        idx = pd.MultiIndex.from_arrays([ctx.key, month])
        return {k: pd.Series(v.reindex(idx).to_numpy(), index=ctx.df.index) for k, v in levels.items()}

    return ctx.memo("_pivots", build)


# ----------------------------------------------------------------------------------------------- calendar
def _calendar(ctx: _Ctx) -> pd.DataFrame:
    """NYSE session table (published calendar, so known in advance) mapped to each row's session; pre-holiday flags
    ignore ad-hoc closures."""

    def build() -> pd.DataFrame:
        import pandas_market_calendars as pmc

        from swing_engine.data.calendar import CALENDAR_NAME, schedule

        sess = session_key(ctx.df[TS_COL])
        days = pd.DatetimeIndex(
            schedule((sess.min() - timedelta(days=CALENDAR_PAD_DAYS)).date(),
                     (sess.max() + timedelta(days=CALENDAR_PAD_DAYS)).date()).index
        )
        t = pd.DataFrame(index=days)
        month = days.to_period("M")
        pos = t.groupby(month).cumcount().to_numpy() + 1
        neg = -(t.groupby(month).cumcount(ascending=False).to_numpy() + 1)
        tom = np.where(pos <= TOM_MAX_OFFSET, pos, np.where(neg >= -TOM_MAX_OFFSET, neg, np.nan))
        nxt = np.r_[days[1:].to_numpy("datetime64[D]"), np.datetime64("NaT", "D")]
        cur = days.to_numpy("datetime64[D]")
        gap_weekdays = np.zeros(len(days))
        ok = ~np.isnat(nxt)
        # pmc's ad-hoc closures (9/11, Hurricane Sandy, mourning days) are not scheduled holidays and some were only
        # known after the fact, so they never count as a gap weekday
        adhoc = pd.DatetimeIndex(pmc.get_calendar(CALENDAR_NAME).adhoc_holidays).tz_localize(None)
        gap_weekdays[ok] = np.busday_count(cur[ok] + np.timedelta64(1, "D"), nxt[ok],
                                           holidays=adhoc.to_numpy("datetime64[D]"))
        ph1 = (gap_weekdays > 0).astype(float)
        ph1[~ok] = np.nan
        t["tom_day"] = tom
        t["tom_window"] = ((tom >= TOM_WINDOW[0]) & (tom <= TOM_WINDOW[1])).astype(float)
        t["tom_pre"] = ((tom >= TOM_PRE[0]) & (tom <= TOM_PRE[1])).astype(float)
        t["pre_holiday_1"] = ph1
        t["pre_holiday_2"] = np.r_[ph1[1:], np.nan]
        t["santa_window"] = (((days.month == 12) & (neg >= -SANTA_DEC_SESSIONS))
                             | ((days.month == 1) & (pos <= SANTA_JAN_SESSIONS))).astype(float)
        t["day_of_week"] = days.dayofweek.astype(float)
        return t.reindex(pd.DatetimeIndex(sess)).set_axis(ctx.df.index)

    return ctx.memo("_calendar", build)


# ----------------------------------------------------------------------------------------------- generic wrappers
def _prev(ctx: _Ctx, col: str) -> pd.Series:
    return ctx.shift(ctx.col(col))


def _rank(ctx: _Ctx, col: str) -> pd.Series:
    """Cross-sectional percentile (0, 1] of ``col`` among the symbols with a row on the same session."""
    return ctx.col(col).groupby(session_key(ctx.df[TS_COL]), sort=False).rank(pct=True)


# ----------------------------------------------------------------------------------------------- catalog batch 2
SEAS_MIN_YEARS = 3  # heston_sadka_seasonality card: average needs >= 3 of the lag years (fewer when the set is shorter)
MONTHS_PER_YEAR = 12


def _rolling_ext(ctx: _Ctx, fn: str, n: str, col: str) -> pd.Series:
    """``max_<n>_of_<col>`` / ``min_<n>_of_<col>``: rolling extreme of any column over the last ``n`` bars."""
    return ctx.ps(ctx.col(col), rolling_max if fn == "max" else rolling_min, int(n))


def _bars_since_ge(ctx: _Ctx, level: str, col: str) -> pd.Series:
    """``bars_since_ge_<level>_of_<col>``: bars since ``col`` was last >= ``level`` (0 on such a bar, NaN before the
    first). Compared with a position's ``bars_held`` it tells whether the level was reached since entry."""
    return ctx.ps(ctx.col(col) >= float(level), bars_since)


def _pctile(ctx: _Ctx, n: str, col: str) -> pd.Series:
    """``pctile_<n>_of_<col>``: percentile rank (0, 1] of the bar's value within its own last ``n`` bars (inclusive)."""
    w = int(n)
    return ctx.ps(ctx.col(col), lambda s: s.rolling(w, min_periods=w).rank(pct=True))


def _seas_month(ctx: _Ctx, a: str, b: str) -> pd.Series:
    """Heston-Sadka same-calendar-month seasonality: mean return of the row's calendar month in years Y-a .. Y-b.

    Month return = last close of the month / last close of the previous month - 1 (a missing month is NaN). Only
    months at least a year old enter, so the current month never leaks in.
    """
    s = session_key(ctx.df[TS_COL])
    mnum = (s.dt.year * MONTHS_PER_YEAR + s.dt.month).to_numpy()
    key = ctx.key.to_numpy()
    last = pd.Series(ctx.c.to_numpy(), index=pd.MultiIndex.from_arrays([key, mnum])).groupby(level=[0, 1]).last()
    k, m = last.index.get_level_values(0), last.index.get_level_values(1)
    prev = last.reindex(pd.MultiIndex.from_arrays([k, m - 1])).to_numpy()
    ret = pd.Series(last.to_numpy() / prev - 1.0, index=last.index)
    years = range(int(a), int(b) + 1)
    lags = np.vstack([ret.reindex(pd.MultiIndex.from_arrays([key, mnum - MONTHS_PER_YEAR * y])).to_numpy()
                      for y in years])
    count = (~np.isnan(lags)).sum(axis=0)
    total = np.nansum(lags, axis=0)
    ok = count >= min(SEAS_MIN_YEARS, len(years))
    return ctx.series(np.where(ok, total / np.maximum(count, 1), np.nan))


def _stoch_close(x: pd.Series, n: int) -> pd.Series:
    lo, hi = rolling_min(x, n), rolling_max(x, n)
    return (PCT * (x - lo) / (hi - lo)).where(hi > lo)


def _stress(ctx: _Ctx, n: str) -> pd.Series:
    """Kaufman Stress: stochastic(n) of [stochastic(n) of close - stochastic(n) of the market close] (kaufman_stress)."""
    w = int(n)
    d = ctx.ps(ctx.c, _stoch_close, w) - ctx.ps(ctx.col("market_close"), _stoch_close, w)
    return ctx.ps(d, _stoch_close, w)


def _rsmk(ctx: _Ctx, n: str, m: str) -> pd.Series:
    """Katsanos RSMK = 100 x EMA_m(ln(C/B) - ln(C/B)[n]) with B the market close (katsanos_rsmk card)."""
    rs = np.log(ctx.c / ctx.col("market_close"))
    return PCT * ctx.ps(rs - ctx.shift(rs, int(n)), ema, int(m))


def _szo(ctx: _Ctx, n: str) -> pd.Series:
    """Sentiment Zone Oscillator = 100 x TEMA_n(sign(close - prev close)) / n (sentiment_zone_oscillator card)."""
    w = int(n)
    r = np.sign(ctx.c - ctx.prev_close())
    return PCT * ctx.ps(r, _tema, w) / w


def _down_days(ctx: _Ctx, n: str) -> pd.Series:
    """``down_days_<n>``: count of closes below the previous close over the last ``n`` bars (connors_hpetf card)."""
    pc = ctx.prev_close()
    return ctx.rsum((ctx.c < pc).astype(float).where(pc.notna()), int(n))


# ----------------------------------------------------------------------------------------------- catalog batch 1
def _vwma(ctx: _Ctx, n: str) -> pd.Series:
    """``vwma_<n>``: volume-weighted MA sum(close x volume) / sum(volume) over ``n`` bars (ma_crossover_family)."""
    vol = ctx.rsum(ctx.v, int(n))
    return (ctx.rsum(ctx.c * ctx.v, int(n)) / vol).where(vol > 0)


def _hl_mid(ctx: _Ctx, n: str) -> pd.Series:
    """``hl_mid_<n>``: (highest high + lowest low) / 2 of the last ``n`` bars (Apirine MHL MA input)."""
    return (ctx.col(f"high_{n}") + ctx.col(f"low_{n}")) / 2.0


# ----------------------------------------------------------------------------------------------- catalog batch 5
#: traditional point-and-figure box table (upper price bound inclusive, box); point_and_figure_signals card
#: ("$5.01-$20 -> $0.50; $20.01-$100 -> $1.00; higher bands larger"), remaining bands from the StockCharts table
PF_BOX_TABLE: tuple[tuple[float, float], ...] = (
    (0.25, 0.0625), (1.0, 0.125), (5.0, 0.25), (20.0, 0.5), (100.0, 1.0), (200.0, 2.0), (500.0, 4.0),
    (1000.0, 5.0), (25000.0, 50.0), (np.inf, 500.0),
)
PF_REVERSAL = 3  # 3-box reversal
PF_COLUMNS = ("pf_dir", "pf_top", "pf_bot", "pf_box", "pf_prev_x_top", "pf_prev_x_top2", "pf_prev_o_bot")
TD_LOOKBACK = 4  # td_sequential card: setup compares the close 4 bars earlier ...
TD_SETUP = 9  # ... for 9 consecutive bars
TD_CD_LOOKBACK = 2  # countdown: close <= low 2 bars earlier ...
TD_COUNTDOWN = 13  # ... 13 times (not consecutive)
TD_QUALIFIER_BAR = 8  # countdown 13 needs low <= close of countdown bar 8
TD_COLUMNS = ("td_buy_setup", "td_buy_perfected", "td_tdst", "td_buy_countdown", "td_risk_level")


def _pf_box(price: float) -> float:
    return next(box for bound, box in PF_BOX_TABLE if price <= bound)


def _pf_np(h: np.ndarray, lo: np.ndarray) -> tuple[np.ndarray, ...]:
    """High/low point-and-figure columns, updated bar by bar (causal). The box comes from the table at each column's
    start price; the first column is treated as an X column. Row t: state after bar t (see PF_COLUMNS)."""
    out = [np.full(len(h), np.nan) for _ in PF_COLUMNS]
    d, top, bot, box, px1, px2, po = 0, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan
    for t in range(len(h)):
        if not (np.isfinite(h[t]) and np.isfinite(lo[t])):
            continue
        if d == 0:
            box = _pf_box(lo[t])
            d, bot = 1, np.ceil(lo[t] / box) * box
            top = max(np.floor(h[t] / box) * box, bot)
        elif d > 0:
            if np.floor(h[t] / box) * box >= top + box:
                top = np.floor(h[t] / box) * box
            elif top - np.ceil(lo[t] / box) * box >= PF_REVERSAL * box:  # reverse into an O column
                px2, px1, d = px1, top, -1
                top, box = top - box, _pf_box(lo[t])
                bot = np.ceil(lo[t] / box) * box
        elif np.ceil(lo[t] / box) * box <= bot - box:
            bot = np.ceil(lo[t] / box) * box
        elif np.floor(h[t] / box) * box - bot >= PF_REVERSAL * box:  # reverse into an X column
            po, d = bot, 1
            bot, box = bot + box, _pf_box(h[t])
            top = np.floor(h[t] / box) * box
        for arr, v in zip(out, (d, top, bot, box, px1, px2, po), strict=True):
            arr[t] = v
    return tuple(out)


def _td_np(h: np.ndarray, lo: np.ndarray, c: np.ndarray, tr: np.ndarray) -> tuple[np.ndarray, ...]:
    """DeMark TD Sequential, buy side (td_sequential card). Setup: consecutive closes < close 4 bars earlier, bar 1
    a price flip (prior close > close 4 bars before it); bar 9 completes it (perfected when min(low 8, low 9) <=
    min(low 6, low 7)); TDST = its highest high; risk = its lowest low minus that bar's true range. Countdown from
    setup bar 9: closes <= low 2 bars earlier, 13 needed, bar 13 deferred until low <= close of countdown bar 8;
    cancelled by a close above TDST or a completed sell setup; a new buy setup restarts it. On 13 the risk level is
    the countdown's lowest low minus that bar's true range."""
    n = len(c)
    setup, perf, tdst, cd, risk = (np.full(n, np.nan) for _ in TD_COLUMNS)
    bs = ss = cdn = 0
    counting, cur_tdst, cur_risk, bar8, cd_low, cd_tr = False, np.nan, np.nan, np.nan, np.inf, np.nan
    lb = TD_LOOKBACK
    for t in range(lb + 1, n):
        dn, up = c[t] < c[t - lb], c[t] > c[t - lb]
        bs = (bs + 1 if bs else int(c[t - 1] > c[t - 1 - lb])) if dn else 0
        ss = (ss + 1 if ss else int(c[t - 1] < c[t - 1 - lb])) if up else 0
        perf[t] = 0.0
        if bs == TD_SETUP:
            seg = slice(t - TD_SETUP + 1, t + 1)
            i = t - TD_SETUP + 1 + int(np.argmin(lo[seg]))
            cur_tdst, cur_risk = float(np.max(h[seg])), lo[i] - tr[i]
            perf[t] = float(min(lo[t], lo[t - 1]) <= min(lo[t - 2], lo[t - 3]))
            counting, cdn, bar8, cd_low, cd_tr = True, 0, np.nan, np.inf, np.nan
        if ss == TD_SETUP or (counting and c[t] > cur_tdst):
            counting, cdn = False, 0
        if counting and c[t] <= lo[t - TD_CD_LOOKBACK]:
            if lo[t] < cd_low:
                cd_low, cd_tr = lo[t], tr[t]
            if cdn < TD_COUNTDOWN - 1:
                cdn += 1
                bar8 = c[t] if cdn == TD_QUALIFIER_BAR else bar8
            elif lo[t] <= bar8:
                cdn = TD_COUNTDOWN
        setup[t], cd[t], tdst[t] = bs, cdn, cur_tdst
        if cdn == TD_COUNTDOWN:
            cur_risk, counting, cdn = cd_low - cd_tr, False, 0
        risk[t] = cur_risk
    return setup, perf, tdst, cd, risk


def _pf(ctx: _Ctx, name: str) -> pd.Series:
    return ctx.series(ctx.memo("_pf", lambda: ctx.loop(_pf_np, ctx.h, ctx.l))[PF_COLUMNS.index(name)])


def _td(ctx: _Ctx, name: str) -> pd.Series:
    res = ctx.memo("_td", lambda: ctx.loop(_td_np, ctx.h, ctx.l, ctx.c, ctx.tr()))
    return ctx.series(res[TD_COLUMNS.index(name)])


# ----------------------------------------------------------------------------------------------- catalog batch 4
EPOCH_DOW = 3  # 1970-01-01 was a Thursday (Monday = 0)
FRIDAY = 4


def last_pivot(x: np.ndarray, left: int, right: int, highs: bool) -> tuple[np.ndarray, np.ndarray]:
    """Most recent confirmed pivot as of each bar: (level, pivot index), NaN / -1 before the first one.

    Bar i is a pivot high when ``x[i]`` is strictly above each of the ``left`` bars before and ``right`` bars after
    it (TradeStation Pivot Reversal "strength"; lows mirror); it is known only from bar ``i + right``.
    """
    n = len(x)
    level, idx = np.full(n, np.nan), np.full(n, -1, dtype=int)
    if n < left + right + 1:
        return level, idx
    win = sliding_window_view(x, left + right + 1)
    centre = win[:, left]
    others = np.delete(win, left, axis=1)
    mask = (centre > others.max(axis=1)) if highs else (centre < others.min(axis=1))
    piv = np.flatnonzero(mask) + left  # pivot bar indices
    conf = piv + right  # bar on which each pivot becomes known
    k = np.searchsorted(conf, np.arange(n), side="right") - 1
    ok = k >= 0
    idx[ok] = piv[k[ok]]
    level[ok] = x[idx[ok]]
    return level, idx


def _last_pivot(ctx: _Ctx, side: str, left: str, right: str) -> pd.Series:
    """``last_pivot_(high|low)_<L>_<R>``: level of the latest confirmed pivot (pivot_reversal_breakout card)."""
    src = ctx.h if side == "high" else ctx.l
    return ctx.series(ctx.loop(lambda a: last_pivot(a, int(left), int(right), side == "high")[0], src))


def _sqz_mom(ctx: _Ctx, n: str) -> pd.Series:
    """TTM / LazyBear squeeze momentum: endpoint of the n-bar least-squares line of
    ``close - ((highest high_n + lowest low_n) / 2 + sma_n) / 2`` (ttm_squeeze card)."""
    w = int(n)
    delta = ctx.c - ((ctx.col(f"high_{w}") + ctx.col(f"low_{w}")) / 2.0 + ctx.col(f"sma_{w}")) / 2.0
    slope = ctx.ps(delta, _linreg, w, "slope")
    return ctx.ps(delta, rolling_mean, w) + slope * (w - 1) / 2.0


def _wk_macd_hist(ctx: _Ctx, lag: int) -> pd.Series:
    """Weekly (W-FRI) MACD(12,26,9) histogram of completed weeks: lag 0 = the latest week whose Friday is on or
    before the row's session, lag 1 = the week before (elder_triple_screen card: no unfinished week)."""

    def build() -> tuple[np.ndarray, np.ndarray]:
        from .indicators import macd

        day = session_key(ctx.df[TS_COL]).to_numpy("datetime64[D]")
        dow = (day.astype(np.int64) + EPOCH_DOW) % 7
        wk_end = day + ((FRIDAY - dow) % 7).astype("timedelta64[D]")
        c = ctx.c.to_numpy(dtype=float)
        out = (np.full(len(day), np.nan), np.full(len(day), np.nan))
        for s, e in ctx.bounds:
            we = wk_end[s:e]
            last = np.flatnonzero(np.r_[we[1:] != we[:-1], True])
            hist = macd(pd.Series(c[s:e][last]))["macd_hist"].to_numpy()
            k = np.searchsorted(we[last], day[s:e], side="right") - 1
            for j, arr in enumerate(out):
                kk = k - j
                arr[s:e] = np.where(kk >= 0, hist[np.maximum(kk, 0)], np.nan)
        return out

    return ctx.series(ctx.memo("_wk_macd", build)[lag])


# ----------------------------------------------------------------------------------------------- catalog batch 3
STIFFNESS_NUM_DEV = 0.2  # katsanos_stiffness card: close must clear SMA + 0.2 x StDev (thinkorswim reading of the offset)


def _linreg_slope_of(ctx: _Ctx, n: str, col: str) -> pd.Series:
    """``linreg_slope_<n>_of_<col>``: OLS slope of any column over its last ``n`` bars (kaufman_three_period_divergence,
    slope_performance_trend)."""
    return ctx.ps(ctx.col(col), _linreg, int(n), "slope")


def _lbr_rsi(ctx: _Ctx, n: str) -> pd.Series:
    """``lbr_rsi_<n>``: Raschke LBR/RSI = RSI(n) of the 1-day change close - prev close (momentum_pinball card)."""
    return ctx.ps(ctx.c - ctx.prev_close(), rsi, int(n))


def _stiffness(ctx: _Ctx, n: str, ma: str) -> pd.Series:
    """``stiffness_<n>_<ma>``: Katsanos Stiffness = 100 x share of the last ``n`` closes above
    SMA(ma) + 0.2 x StDev(ma) (population SD, as thinkorswim StDev)."""
    m = int(ma)
    thr = ctx.col(f"sma_{m}") + STIFFNESS_NUM_DEV * ctx.ps(ctx.c, lambda s: s.rolling(m, min_periods=m).std(ddof=0))
    return PCT * ctx.ps(_flag(ctx.c > thr, thr.notna()), rolling_mean, int(n))


def zigzag_np(c: np.ndarray, pct: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Non-repainting close ZigZag: (trend, last confirmed swing high, last confirmed swing low) after each bar.

    A swing high is confirmed on the bar whose close is ``pct`` below the highest close since the last confirmed low
    (lows mirror), so nothing is revised later. trend = +1 when the last two confirmed highs and lows both rise, -1 when
    both fall, else 0; NaN until two of each exist (rsi_trend_zigzag_luo card).
    """
    n = len(c)
    trend, hi_out, lo_out = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    highs: list[float] = []
    lows: list[float] = []
    mode, ext_hi, ext_lo = 0, np.nan, np.nan
    for t in range(n):
        x = c[t]
        if not np.isfinite(x):
            continue
        if np.isnan(ext_hi):
            ext_hi = ext_lo = x
        if mode >= 0:
            ext_hi = max(ext_hi, x)
        if mode <= 0:
            ext_lo = min(ext_lo, x)
        if mode >= 0 and x <= ext_hi * (1.0 - pct):
            highs.append(ext_hi)
            mode, ext_lo = -1, x
        elif mode <= 0 and x >= ext_lo * (1.0 + pct):
            lows.append(ext_lo)
            mode, ext_hi = 1, x
        if highs:
            hi_out[t] = highs[-1]
        if lows:
            lo_out[t] = lows[-1]
        if len(highs) >= 2 and len(lows) >= 2:
            up = highs[-1] > highs[-2] and lows[-1] > lows[-2]
            down = highs[-1] < highs[-2] and lows[-1] < lows[-2]
            trend[t] = 1.0 if up else (-1.0 if down else 0.0)
    return trend, hi_out, lo_out


def _zigzag(ctx: _Ctx, part: str, pct: str) -> pd.Series:
    """``zz_(trend|high|low)_<pct>``: :func:`zigzag_np` on close with a ``pct`` percent reversal."""
    res = ctx.memo(f"_zz_{pct}", lambda: ctx.loop(lambda c: zigzag_np(c, float(pct) / PCT), ctx.c))
    return ctx.series(res[("trend", "high", "low").index(part)])


# ----------------------------------------------------------------------------------------------- catalog batch 0
VPN_ATR_FACTOR = 0.1  # katsanos_vpn_breakout card: volume counts when |dTP| >= 0.1 x ATR (ATR length unstated: atr_14)
VPN_SMOOTH = 3  # katsanos_vpn_breakout card: EMA(3) smoothing (commonly cited, unverified)


def _rms(ctx: _Ctx, n: str, col: str) -> pd.Series:
    """``rms_<n>_of_<col>``: root mean square of any column over the last ``n`` bars (apirine_roc_bands card)."""
    x = ctx.col(col)
    return np.sqrt(ctx.ps(x * x, rolling_mean, int(n)))


def _vpn(ctx: _Ctx, n: str) -> pd.Series:
    """Katsanos VPN = EMA3(100 x (volume of up bars - volume of down bars) / total volume, ``n`` bars); a bar is up
    (down) when typical price moved at least 0.1 x atr_14 above (below) the prior bar's (katsanos_vpn_breakout)."""
    w = int(n)
    tp = ctx.col("hlc3")
    dtp, band = tp - ctx.shift(tp), VPN_ATR_FACTOR * ctx.col("atr_14")
    signed = ctx.v * ((dtp >= band).astype(float) - (dtp <= -band).astype(float))
    raw = (PCT * ctx.rsum(signed.where(dtp.notna() & band.notna()), w) / ctx.rsum(ctx.v, w)).replace(
        [np.inf, -np.inf], np.nan)
    return ctx.ps(raw, ema, VPN_SMOOTH)


def _resid_mom(ctx: _Ctx, n: str, form: str, skip: str) -> pd.Series:
    """Residual momentum, daily CAPM proxy of the residual_momentum card: fit r = a + b x r_mkt over the last ``n``
    bars, then (sum of that fit's residuals over bars t-skip-form+1 .. t-skip) / (their population std)."""
    w, f, s = int(n), int(form), int(skip)
    r, m = ctx.ps(ctx.c, pct_return, 1), _market_close(ctx)[1]
    ok = r.notna() & m.notna()
    r, m = r.where(ok), m.where(ok)

    def fit(x: pd.Series) -> pd.Series:
        return ctx.ps(x, rolling_mean, w)

    def form_mean(x: pd.Series) -> pd.Series:
        return ctx.shift(ctx.ps(x, rolling_mean, f), s)

    var_m = fit(m * m) - fit(m) ** 2
    beta = ((fit(r * m) - fit(r) * fit(m)) / var_m).where(var_m > 0)
    alpha = fit(r) - beta * fit(m)
    fr, fm = form_mean(r), form_mean(m)
    mean_e = fr - alpha - beta * fm
    var_e = (form_mean(r * r) - fr**2) + beta**2 * (form_mean(m * m) - fm**2) - 2.0 * beta * (form_mean(r * m) - fr * fm)
    return (f * mean_e / np.sqrt(var_e.where(var_e > 0))).astype(float)


FF3_COLUMNS = ("ff_mkt_rf", "ff_smb", "ff_hml")  # data.market_series panel columns (decimal daily returns)
FF_RF_COLUMN = "ff_rf"
#: data.market_series.FF_PUBLICATION_LAG_MONTHS: a French factor for month D is known from the 1st of month D + 2
FF_LAG_MONTHS = 2
VIX_CLOSE_COLUMN = "vix_close"  # data.market_series panel column (same value on every symbol's row)


def _window_sums(a: np.ndarray, n: int) -> np.ndarray:
    """Sum over the ``n`` rows ending at each row (NaN before ``n`` rows); ``a`` has no NaN."""
    c = np.cumsum(np.concatenate([np.zeros((1, *a.shape[1:])), a]), axis=0)
    out = np.full(a.shape, np.nan)
    if len(a) >= n:
        out[n - 1:] = c[n:] - c[:-n]
    return out


def _ff3_score(y: np.ndarray, mkt: np.ndarray, smb: np.ndarray, hml: np.ndarray, month: np.ndarray,
               w: int, f: int) -> np.ndarray:
    """One symbol: at each month's last row fit y = a + b'[mkt, smb, hml] over the last ``w`` rows, score the
    residuals (intercept excluded) over the last ``f`` rows as sum / population std; a row in month M gets the
    score from the last row of month M - FF_LAG_MONTHS (NaN if any input in either window is missing)."""
    k = len(y)
    x = np.column_stack([np.ones(k), mkt, smb, hml])
    ok = np.isfinite(y) & np.isfinite(x).all(axis=1)
    x0, y0 = np.where(ok[:, None], x, 0.0), np.where(ok, y, 0.0)
    xx, xy = x0[:, :, None] * x0[:, None, :], x0 * y0[:, None]
    cnt = ok.astype(float)
    month_end = np.r_[month[1:] != month[:-1], True]
    idx = np.flatnonzero(month_end & (_window_sums(cnt, w) == w) & (_window_sums(cnt, f) == f))
    out = np.full(k, np.nan)
    if idx.size == 0:
        return out
    b = (np.linalg.pinv(_window_sums(xx, w)[idx]) @ _window_sums(xy, w)[idx][..., None])[..., 0]
    sx, sxx, sxy = _window_sums(x0, f)[idx], _window_sums(xx, f)[idx], _window_sums(xy, f)[idx]
    sum_e = _window_sums(y0, f)[idx] - np.einsum("ij,ij->i", b, sx)
    sum_e2 = _window_sums(y0 * y0, f)[idx] - 2.0 * np.einsum("ij,ij->i", b, sxy) + np.einsum("ij,ijk,ik->i", b, sxx, b)
    var = sum_e2 / f - (sum_e / f) ** 2
    score = np.where(var > 0, sum_e / np.sqrt(np.where(var > 0, var, 1.0)), np.nan)
    ends = month[idx]
    pos = np.searchsorted(ends, month - FF_LAG_MONTHS)
    hit = pos < len(ends)
    hit[hit] = ends[pos[hit]] == (month - FF_LAG_MONTHS)[hit]
    out[hit] = score[pos[hit]]
    return out


def _ff3_resid_mom(ctx: _Ctx, n: str, form: str) -> pd.Series:
    """Residual momentum on the Fama-French 3 factors (Blitz-Huij-Martens 2011; residual_momentum card): regress
    daily excess returns (r - ff_rf) on ff_mkt_rf, ff_smb, ff_hml over ``n`` bars, score the residuals of the
    last ``form`` bars. Point-in-time under the French publication lag: a row in month M uses bars and factors
    through the end of month M-2 only (known from the 1st of M), which is also BHM's t-12 .. t-2 window. NaN when
    the panel has no ff_* columns (no `swing ingest-french`) or a window has a missing factor day."""
    if not all(c in ctx.df.columns for c in (FF_RF_COLUMN, *FF3_COLUMNS)):
        return pd.Series(np.nan, index=ctx.df.index)
    sess = session_key(ctx.df[TS_COL])
    month = (sess.dt.year * 12 + sess.dt.month).astype(float)
    y = ctx.ps(ctx.c, pct_return, 1) - ctx.df[FF_RF_COLUMN].astype(float)
    w, f = int(n), int(form)
    return ctx.series(ctx.loop(lambda *a: _ff3_score(*a, w=w, f=f), y, *(ctx.df[c] for c in FF3_COLUMNS), month))


def _vix_sma(ctx: _Ctx, n: str) -> pd.Series:
    """SMA(n) of the joined VIX close (data.market_series), per symbol; NaN without `swing ingest-vix`."""
    if VIX_CLOSE_COLUMN not in ctx.df.columns:
        return pd.Series(np.nan, index=ctx.df.index)
    return ctx.ps(ctx.df[VIX_CLOSE_COLUMN].astype(float), sma, int(n))


def _weeks(ctx: _Ctx) -> dict[str, np.ndarray]:
    """Completed W-FRI weeks per symbol, as in ``_wk_macd_hist``: weekly high / low / close / market close (``key``
    = symbol code) and, per row, ``pos`` = index of the latest week whose Friday is on or before the row's session
    (-1 before the first). A week is read only once its Friday has passed, so no row sees a later bar."""

    def build() -> dict[str, np.ndarray]:
        day = session_key(ctx.df[TS_COL]).to_numpy("datetime64[D]")
        dow = (day.astype(np.int64) + EPOCH_DOW) % 7
        wk_end = day + ((FRIDAY - dow) % 7).astype("timedelta64[D]")
        h, lo, c = (x.to_numpy(dtype=float) for x in (ctx.h, ctx.l, ctx.c))
        mkt = _market_close(ctx)[0].to_numpy(dtype=float)
        parts: dict[str, list[np.ndarray]] = {k: [] for k in ("key", "high", "low", "close", "mkt")}
        pos = np.full(len(day), -1)
        done = 0
        for code, (s, e) in enumerate(ctx.bounds):
            we = wk_end[s:e]
            first = np.flatnonzero(np.r_[True, we[1:] != we[:-1]])
            last = np.r_[first[1:] - 1, e - s - 1]
            parts["key"].append(np.full(len(first), code))
            parts["high"].append(np.maximum.reduceat(h[s:e], first))
            parts["low"].append(np.minimum.reduceat(lo[s:e], first))
            parts["close"].append(c[s:e][last])
            parts["mkt"].append(mkt[s:e][last])
            k = np.searchsorted(we[last], day[s:e], side="right") - 1
            pos[s:e] = np.where(k >= 0, k + done, -1)
            done += len(first)
        out = {k: np.concatenate(v) if v else np.array([]) for k, v in parts.items()}
        out["pos"] = pos
        return out

    return ctx.memo("_weeks", build)


def _wk(ctx: _Ctx, stat: Callable[[pd.DataFrame], pd.Series]) -> pd.Series:
    """Map a per-symbol weekly statistic onto the rows (value of the latest completed week)."""
    wk = _weeks(ctx)
    frame = pd.DataFrame({k: wk[k] for k in ("high", "low", "close", "mkt")})
    cuts = np.flatnonzero(np.diff(wk["key"]) != 0) + 1
    vals = np.concatenate([stat(frame.iloc[s:e].reset_index(drop=True)).to_numpy(dtype=float)
                           for s, e in zip(np.r_[0, cuts], np.r_[cuts, len(frame)], strict=True)] or [np.array([])])
    pos = wk["pos"]
    return ctx.series(np.where(pos >= 0, vals[np.maximum(pos, 0)] if len(vals) else np.nan, np.nan))


def _wk_stoch(ctx: _Ctx, n: str, smooth: str) -> pd.Series:
    """``wk_stoch_<n>_<s>``: weekly slow stochastic %K, n weeks, s-week SMA smoothing (last_stochastic_weekly)."""
    w, k = int(n), int(smooth)

    def stat(g: pd.DataFrame) -> pd.Series:
        hh, ll = rolling_max(g["high"], w), rolling_min(g["low"], w)
        return rolling_mean((PCT * (g["close"] - ll) / (hh - ll)).where(hh > ll), k)

    return _wk(ctx, stat)


def _wk_roc(ctx: _Ctx, n: str) -> pd.Series:
    """``wk_roc_<n>``: 100 x (weekly close / weekly close ``n`` weeks earlier - 1) (radge_weekend_trend_trader)."""
    return _wk(ctx, lambda g: PCT * pct_return(g["close"], int(n)))


def _wk_close_max(ctx: _Ctx, n: str) -> pd.Series:
    """``wk_close_max_<n>``: highest weekly close of the ``n`` weeks BEFORE the latest completed one."""
    return _wk(ctx, lambda g: rolling_max(g["close"].shift(1), int(n)))


def _mkt_wk_above(ctx: _Ctx, n: str) -> pd.Series:
    """``mkt_wk_above_<n>``: 1 when the market proxy's weekly close is above its ``n``-week SMA, else 0 (NaN while
    warming up or without a market proxy)."""
    w = int(n)
    return _wk(ctx, lambda g: _flag(g["mkt"] > rolling_mean(g["mkt"], w), rolling_mean(g["mkt"], w).notna()))


def _wk_fresh(ctx: _Ctx) -> pd.Series:
    """``wk_fresh``: 1 on the row where a new completed week first becomes visible (normally the Friday), else 0."""
    pos = pd.Series(_weeks(ctx)["pos"], index=ctx.df.index, dtype=float)
    return ((pos >= 0) & (pos != ctx.shift(pos))).astype(float)


def _gandalf_weak(ctx: _Ctx) -> pd.Series:
    """``gandalf_weak``: Gandalf Project Research System losing-trade weakness sets as 0/1 (thinkorswim; [k] = k bars
    ago, median = (H+L)/2, mid = (O+C)/2). C: ohlc4[1] < mid[1], median[2] == mid[3], mid[1] <= mid[4]; D: ohlc4[2] <
    mid[0], median[4] < ohlc4[3], mid[1] < ohlc4[1]. NaN until four prior bars exist."""
    sh, ohlc4 = ctx.shift, ctx.col("ohlc4")
    med, mid = (ctx.h + ctx.l) / 2.0, (ctx.o + ctx.c) / 2.0
    mid1, ohlc4_1 = sh(mid, 1), sh(ohlc4, 1)
    set_c = (ohlc4_1 < mid1) & (sh(med, 2) == sh(mid, 3)) & (mid1 <= sh(mid, 4))
    set_d = (sh(ohlc4, 2) < mid) & (sh(med, 4) < sh(ohlc4, 3)) & (mid1 < ohlc4_1)
    return _flag(set_c | set_d, sh(ohlc4, 4).notna())


# ----------------------------------------------------------------------------------------------- three picks
# docs/preregistration/2026-10-09-three-picks.md (cards ath_trend_following_wide_stop, composite_cost_aware_rank)
PRE_PANEL_HIGH, PRE_PANEL_BARS = "pre_panel_high", "pre_panel_bars"  # data.market_series.join_pre_panel_high
CCR_MIN_PRICE = 5.0  # composite card rule 1: price >= $5
CCR_DV_WINDOW = 63  # card rule 1: 63-day median dollar volume ...
CCR_MIN_MEDIAN_DOLLAR_VOL = 20_000_000.0  # ... >= $20M
CCR_SIZE_FLOOR_PCT = 0.20  # card rule 1: not in the bottom 20% of market cap (shares_outstanding x close)
CCR_VOL_WINDOW = 252  # card 2d: low 252-day volatility
CCR_INPUTS = 4  # card rule 2: momentum, gross profitability, 52-week-high proximity, low volatility


def _optional(ctx: _Ctx, name: str) -> pd.Series:
    """A joined column (EDGAR, store history) as float, or NaN when the panel was built without it."""
    return ctx.df[name].astype(float) if name in ctx.df.columns else pd.Series(np.nan, index=ctx.df.index)


def _ath_close(ctx: _Ctx) -> pd.Series:
    """``ath_close``: highest close from the symbol's first store bar through this row: the running max of the
    panel's closes, folded with ``pre_panel_high`` (store bars before the panel) when the panel carries it."""
    return np.fmax(ctx.c.groupby(ctx.key, sort=False).cummax(), _optional(ctx, PRE_PANEL_HIGH))


def _hist_bars(ctx: _Ctx) -> pd.Series:
    """``hist_bars``: bars of the symbol in the store up to and including this row (panel bars + ``pre_panel_bars``)."""
    pre = _optional(ctx, PRE_PANEL_BARS).fillna(0.0)
    return ctx.c.groupby(ctx.key, sort=False).cumcount().astype(float) + 1.0 + pre


def _med_dv(ctx: _Ctx, n: str) -> pd.Series:
    """``med_dv_<n>``: median of daily dollar volume (close x volume) over the last ``n`` bars, this one included."""
    w = int(n)
    return ctx.ps(ctx.c * ctx.v, lambda s: s.rolling(w, min_periods=w).median())


def _ccr_score(ctx: _Ctx) -> pd.Series:
    """``ccr_score``: equal-weight mean of the same-session percentile ranks of mom_12_1, gross_prof,
    dist_52w_high and minus 252-day realised vol, ranked among the session's eligible rows (close >= $5, 63-day
    median dollar volume >= $20M, market cap >= the session's 20th percentile, all four inputs known); NaN for the
    rest. ``gross_prof`` / ``shares_outstanding`` come from data.fundamentals.join_edgar (NaN without them)."""
    day = session_key(ctx.df[TS_COL])
    mcap = _optional(ctx, "shares_outstanding") * ctx.c
    floor = mcap.groupby(day, sort=False).transform(lambda x: x.quantile(CCR_SIZE_FLOOR_PCT))
    dv = ctx.col(f"med_dv_{CCR_DV_WINDOW}")
    inputs = [ctx.col("mom_12_1"), _optional(ctx, "gross_prof"), ctx.col("dist_52w_high"),
              -ctx.ps(ctx.c, realized_vol, CCR_VOL_WINDOW)]
    ok = (ctx.c >= CCR_MIN_PRICE) & (dv >= CCR_MIN_MEDIAN_DOLLAR_VOL) & (mcap >= floor)
    for x in inputs:
        ok &= x.notna()
    return sum(x.where(ok).groupby(day, sort=False).rank(pct=True) for x in inputs) / CCR_INPUTS


# ----------------------------------------------------------------------------------------------- registry
def _cal(name: str) -> Feature:
    return lambda ctx: _calendar(ctx)[name]


EXTRA_FEATURES: dict[str, Feature] = {
    "hlc3": lambda ctx: (ctx.h + ctx.l + ctx.c) / 3.0,
    "ohlc4": lambda ctx: (ctx.o + ctx.h + ctx.l + ctx.c) / 4.0,
    "ret_intraday": lambda ctx: ctx.c / ctx.o - 1.0,
    "streak": _streak,
    "up_streak": lambda ctx: ctx.col("streak").clip(lower=0.0),
    "down_streak": lambda ctx: (-ctx.col("streak")).clip(lower=0.0),
    "connors_rsi": _connors_rsi,
    "id_nr4": _id_nr4,
    "wide_range_bar": _wide_range_bar,
    "dist_52w_low": _dist_52w_low,
    "id_score": _id_score,
    "hot_by_price": _hot_by_price,
    "rs_rating_ibd": _rs_rating_ibd,
    "rs_line": _rs_line,
    "rs_line_new_high": _rs_new_high,
    "mansfield_rs": _mansfield,
    "rel_ret_1d": _rel_ret_1d,
    "obv": _obv,
    "ad_line": _ad_line,
    "kst": lambda ctx: _kst_parts(ctx)[0],
    "kst_signal": lambda ctx: _kst_parts(ctx)[1],
    "tsi": _tsi,
    "uo": _uo,
    "ao": _ao,
    "psar": lambda ctx: _psar(ctx, 0),
    "psar_dir": lambda ctx: _psar(ctx, 1),
    "psar_af": lambda ctx: _psar(ctx, 2),
    f"tenkan_{TENKAN}": lambda ctx: _ichimoku(ctx, "tenkan"),
    f"kijun_{KIJUN}": lambda ctx: _ichimoku(ctx, "kijun"),
    f"span_a_{KIJUN}": lambda ctx: _ichimoku(ctx, "span_a"),
    f"span_b_{KIJUN}": lambda ctx: _ichimoku(ctx, "span_b"),
    "cloud_high": lambda ctx: _cloud(ctx, "high"),
    "cloud_low": lambda ctx: _cloud(ctx, "low"),
    **{k: (lambda ctx, k=k: _heikin_ashi(ctx)[k]) for k in ("ha_open", "ha_high", "ha_low", "ha_close")},
    **{k: (lambda ctx, k=k: _pivots(ctx)[k]) for k in ("piv_p", "piv_r1", "piv_s1", "piv_r2", "piv_s2")},
    **{k: _cal(k) for k in ("tom_day", "tom_window", "tom_pre", "pre_holiday_1", "pre_holiday_2",
                            "santa_window", "day_of_week")},
    "market_close": lambda ctx: _market_close(ctx)[0],
    "ha_ohlc4": lambda ctx: sum(_heikin_ashi(ctx)[k] for k in ("ha_open", "ha_high", "ha_low", "ha_close")) / 4.0,
    "wk_macd_hist": lambda ctx: _wk_macd_hist(ctx, 0),
    "wk_macd_hist_prev": lambda ctx: _wk_macd_hist(ctx, 1),
    **{k: (lambda ctx, k=k: _pf(ctx, k)) for k in PF_COLUMNS},
    **{k: (lambda ctx, k=k: _td(ctx, k)) for k in TD_COLUMNS},
    "month_end": lambda ctx: (_calendar(ctx)["tom_day"] == -1).astype(float),  # 1 on the month's last NYSE session
    "gandalf_weak": _gandalf_weak,
    "ath_close": _ath_close,
    "hist_bars": _hist_bars,
    "ccr_score": _ccr_score,
    "dollar_vol": lambda ctx: ctx.c * ctx.v,  # daily dollar volume (GKM 2001 volume measure); rank it with pctile_<n>_of_dollar_vol
}

_N = r"(\d+)"
#: (pattern, builder(ctx, *groups), example name for tests, index of a group naming another column or None)
EXTRA_PATTERNS: list[tuple[re.Pattern[str], Callable[..., pd.Series], str, int | None]] = [
    (re.compile(rf"sma_{_N}_slope_{_N}"), _sma_slope, "sma_200_slope_21", None),
    (re.compile(rf"(sma|ema|wma|hma|dema|tema)_{_N}(?:_of_(\w+))?"), _ma, "hma_16", 2),
    (re.compile(rf"atr_{_N}"), _atr, "atr_10", None),
    (re.compile(rf"atr_pct_{_N}"), lambda ctx, n: ctx.col(f"atr_{n}") / ctx.c, "atr_pct_10", None),
    (re.compile(rf"atr_sma_{_N}"), _atr_sma, "atr_sma_20", None),
    (re.compile(rf"atr_high_{_N}"), _atr_high, "atr_high_14", None),
    (re.compile(rf"rsi_{_N}"), _rsi, "rsi_4", None),
    (re.compile(rf"stochrsi_{_N}"), _stochrsi, "stochrsi_14", None),
    (re.compile(rf"(adx|plus_di|minus_di)_{_N}"), _adx, "adx_10", None),
    (re.compile(rf"roc_{_N}"), _roc, "roc_10", None),
    (re.compile(rf"cci_{_N}"), _cci, "cci_20", None),
    (re.compile(rf"pct_r_{_N}"), _pct_r, "pct_r_14", None),
    (re.compile(rf"stoch_k_{_N}(?:_{_N})?"), _stoch_k, "stoch_k_14_3", None),
    (re.compile(rf"stoch_d_{_N}_{_N}_{_N}"), _stoch_d, "stoch_d_14_3_3", None),
    (re.compile(rf"mfi_{_N}"), _mfi, "mfi_14", None),
    (re.compile(rf"cmf_{_N}"), _cmf, "cmf_20", None),
    (re.compile(rf"ii_pct_{_N}"), _ii_pct, "ii_pct_21", None),
    (re.compile(rf"force_{_N}"), _force, "force_13", None),
    (re.compile(rf"vfi_{_N}"), _vfi, "vfi_130", None),
    (re.compile(rf"er_{_N}"), _er, "er_10", None),
    (re.compile(rf"kama_{_N}"), _kama, "kama_10", None),
    (re.compile(rf"vhf_{_N}"), _vhf, "vhf_28", None),
    (re.compile(rf"linreg_slope_{_N}"), _linreg_slope, "linreg_slope_20", None),
    (re.compile(rf"r2_{_N}"), _r2, "r2_20", None),
    (re.compile(rf"kc_(upper|mid|lower)_{_N}"), _kc, "kc_upper_20", None),
    (re.compile(rf"bb_(upper|lower|width|pctb)_{_N}"), _bb, "bb_pctb_20", None),
    (re.compile(rf"dc_(high|low)_{_N}"), _donchian, "dc_high_20", None),
    (re.compile(rf"(high|low)_{_N}"), _hilo, "high_60", None),
    (re.compile(rf"aroon_(up|down|osc)_{_N}"), _aroon, "aroon_osc_25", None),
    (re.compile(rf"wvf_{_N}"), _wvf, "wvf_22", None),
    (re.compile(rf"pzo_{_N}"), _pzo, "pzo_14", None),
    (re.compile(rf"cmo_{_N}"), _cmo, "cmo_14", None),
    (re.compile(rf"trix_{_N}"), _trix, "trix_15", None),
    (re.compile(rf"(bull|bear)_power_{_N}"), _power, "bull_power_13", None),
    (re.compile(rf"nr{_N}"), _nr, "nr7", None),
    (re.compile(rf"max_ret_{_N}"), _max_ret, "max_ret_21", None),
    (re.compile(rf"vol_max_{_N}"), _vol_max, "vol_max_252", None),
    (re.compile(rf"pctrank_ret_{_N}"), _pctrank_ret, "pctrank_ret_100", None),
    (re.compile(rf"beta_{_N}"), _beta, "beta_60", None),
    (re.compile(rf"corr_market_{_N}"), _corr_market, "corr_market_20", None),
    (re.compile(rf"mom_{_N}_{_N}"), _mom, "mom_6_1", None),
    (re.compile(r"st_(line|dir)(?:_(\d+)_(\d+(?:\.\d+)?))?"), _supertrend, "st_dir_10_3", None),
    (re.compile(r"gapm_(ratio|signal|slope)(?:_(\d+)_(\d+))?"), _gapm, "gapm_slope_40_20", None),
    (re.compile(rf"ehlers_(ss|hp)_{_N}"), _ehlers, "ehlers_ss_10", None),
    (re.compile(rf"roof_{_N}_{_N}"), _roof, "roof_48_10", None),
    (re.compile(r"prev_(\w+)"), _prev, "prev_rsi_4", 0),
    (re.compile(r"(\w+)_rank"), _rank, "mom_12_1_rank", 0),
    (re.compile(rf"(max|min)_{_N}_of_(\w+)"), _rolling_ext, "max_30_of_szo_14", 2),
    (re.compile(rf"pctile_{_N}_of_(\w+)"), _pctile, "pctile_126_of_bb_width_20", 1),
    (re.compile(rf"bars_since_ge_{_N}_of_(\w+)"), _bars_since_ge, "bars_since_ge_40_of_pzo_14", 1),
    (re.compile(rf"seas_month_{_N}_{_N}"), _seas_month, "seas_month_1_1", None),
    (re.compile(rf"stress_{_N}"), _stress, "stress_20", None),
    (re.compile(rf"rsmk_{_N}_{_N}"), _rsmk, "rsmk_90_3", None),
    (re.compile(rf"szo_{_N}"), _szo, "szo_14", None),
    (re.compile(rf"vwma_{_N}"), _vwma, "vwma_50", None),
    (re.compile(rf"hl_mid_{_N}"), _hl_mid, "hl_mid_10", None),
    (re.compile(rf"last_pivot_(high|low)_{_N}_{_N}"), _last_pivot, "last_pivot_low_4_4", None),
    (re.compile(rf"sqz_mom_{_N}"), _sqz_mom, "sqz_mom_20", None),
    (re.compile(rf"linreg_slope_{_N}_of_(\w+)"), _linreg_slope_of, "linreg_slope_5_of_stoch_k_14", 1),
    (re.compile(rf"lbr_rsi_{_N}"), _lbr_rsi, "lbr_rsi_3", None),
    (re.compile(rf"stiffness_{_N}_{_N}"), _stiffness, "stiffness_60_100", None),
    (re.compile(rf"zz_(trend|high|low)_{_N}"), _zigzag, "zz_trend_5", None),
    (re.compile(rf"down_days_{_N}"), _down_days, "down_days_5", None),
    (re.compile(rf"rms_{_N}_of_(\w+)"), _rms, "rms_20_of_roc_12", 1),
    (re.compile(rf"vpn_{_N}"), _vpn, "vpn_30", None),
    (re.compile(rf"resid_mom_{_N}_{_N}_{_N}"), _resid_mom, "resid_mom_120_60_10", None),
    (re.compile(rf"ff3_resid_mom_{_N}_{_N}"), _ff3_resid_mom, "ff3_resid_mom_60_20", None),
    (re.compile(rf"vix_sma_{_N}"), _vix_sma, "vix_sma_10", None),
    (re.compile(rf"wk_stoch_{_N}_{_N}"), _wk_stoch, "wk_stoch_10_3", None),
    (re.compile(rf"wk_roc_{_N}"), _wk_roc, "wk_roc_20", None),
    (re.compile(rf"wk_close_max_{_N}"), _wk_close_max, "wk_close_max_20", None),
    (re.compile(rf"mkt_wk_above_{_N}"), _mkt_wk_above, "mkt_wk_above_10", None),
    (re.compile(r"wk_fresh"), _wk_fresh, "wk_fresh", None),
    (re.compile(rf"med_dv_{_N}"), _med_dv, "med_dv_63", None),
    (re.compile(r"wk_close"), lambda ctx: _wk(ctx, lambda g: g["close"]), "wk_close", None),
]

_BASE_COLUMNS = frozenset((*OHLCV, *FEATURE_COLUMNS, *PATTERNS2_COLUMNS))


def _match(name: str) -> tuple[Callable[..., pd.Series], tuple[Any, ...]] | None:
    for rx, fn, _example, inner in EXTRA_PATTERNS:
        m = rx.fullmatch(name)
        if m and (inner is None or m.group(inner + 1) is None or _known(m.group(inner + 1))):
            return fn, m.groups()
    return None


def _known(name: str) -> bool:
    return name in _BASE_COLUMNS or is_extra(name)


def is_extra(name: str) -> bool:
    """True when ``name`` resolves to a registered extra feature (exact or parametric)."""
    return name in EXTRA_FEATURES or _match(name) is not None


def rank_base(name: str) -> str | None:
    """The column a ``<col>_rank`` extra ranks (``mom_12_1_rank`` -> ``mom_12_1``), else None."""
    hit = None if name in EXTRA_FEATURES else _match(name)
    return hit[1][0] if hit is not None and hit[0] is _rank else None


def resolve(name: str) -> Feature | None:
    if name in EXTRA_FEATURES:
        return EXTRA_FEATURES[name]
    hit = _match(name)
    if hit is None:
        return None
    fn, groups = hit
    return lambda ctx: fn(ctx, *groups)


def ensure_extra(panel: pd.DataFrame, names: Iterable[str], market: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return ``panel`` with every name in ``names`` present, computing only the missing ones.

    ``market`` is the market proxy's bars (SPY) for relative-strength features; when omitted the panel's own
    ``SPY`` rows are used. Row order and index of ``panel`` are preserved. Raises ``KeyError`` for unknown names.
    """
    missing = [n for n in dict.fromkeys(names) if n not in panel.columns]
    if not missing or panel.empty:
        return panel
    unknown = [n for n in missing if not is_extra(n)]
    if unknown:
        raise KeyError(f"unknown extra features {unknown}")
    order = panel.sort_values([SYMBOL_COL, TS_COL], kind="mergesort")
    ctx = _Ctx(order.reset_index(drop=True), market)
    new = pd.DataFrame({n: ctx.col(n).to_numpy() for n in missing}, index=order.index).reindex(panel.index)
    return pd.concat([panel, new], axis=1)


def required_extras(strategies: Iterable[Any] | None = None) -> list[str]:
    """Union (in order) of the ``extra_features`` of ``strategies`` (classes or instances); None = every
    registered strategy."""
    if strategies is None:
        from swing_engine.core import registry

        strategies = [registry.get("strategy", n) for n in registry.names("strategy")]
    out: dict[str, None] = {}
    for s in strategies:
        for n in getattr(s, "extra_features", None) or []:
            out[n] = None
    return list(out)
