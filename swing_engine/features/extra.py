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
proxy's bars at or before that session (relative strength, beta) or the published NYSE calendar (calendar flags), so
appending later bars never changes an earlier value. Flags are float 0/1 and NaN while their inputs warm up.
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
from .cross_section import pct_return, rolling_max, rolling_mean, rolling_min
from .indicators import ema, rsi, sma, true_range, wilder_smooth
from .panel import FEATURE_COLUMNS
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
    """NYSE session table (published calendar, so known in advance) mapped to each row's session."""

    def build() -> pd.DataFrame:
        from swing_engine.data.calendar import schedule

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
        gap_weekdays[ok] = np.busday_count(cur[ok] + np.timedelta64(1, "D"), nxt[ok])
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
    (re.compile(rf"mom_{_N}_{_N}"), _mom, "mom_6_1", None),
    (re.compile(r"st_(line|dir)(?:_(\d+)_(\d+(?:\.\d+)?))?"), _supertrend, "st_dir_10_3", None),
    (re.compile(r"gapm_(ratio|signal|slope)(?:_(\d+)_(\d+))?"), _gapm, "gapm_slope_40_20", None),
    (re.compile(rf"ehlers_(ss|hp)_{_N}"), _ehlers, "ehlers_ss_10", None),
    (re.compile(rf"roof_{_N}_{_N}"), _roof, "roof_48_10", None),
    (re.compile(r"prev_(\w+)"), _prev, "prev_rsi_4", 0),
    (re.compile(r"(\w+)_rank"), _rank, "mom_12_1_rank", 0),
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
