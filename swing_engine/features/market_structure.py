"""Market-structure event extractor (plan P1 item 6): swings, structure breaks, liquidity, imbalances, zones.

Pure functions over the OHLCV bars of ONE symbol on ONE timeframe (``ts`` = bar open time, sorted). Every rule and
threshold is written out in ``docs/market-structure.md``; the constants below are the versioned defaults
(``EXTRACTOR_VERSION``) and ``params`` overrides them by lower-case name.

No look-ahead: every family is a single forward pass that emits an event on the bar whose CLOSE completes it
(``ts_event``), reading only that bar and earlier ones. Truncating the input at any bar T therefore leaves every
event with ``ts_event <= T`` unchanged (``tests/test_features_market_structure.py`` checks all kinds).
ATR is the Wilder ATR of the PREVIOUS bar, so a candle is never measured against a range it inflated itself.
"""

from __future__ import annotations

import hashlib
import heapq
from bisect import bisect_right
from collections import defaultdict

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .indicators import atr as wilder_atr

EXTRACTOR_VERSION = "2026-10-13"

ATR_PERIOD = 14  # Wilder (1978) default
SWING_LEFT = 3  # fractal pivot: bars to the left that must be strictly lower (higher for lows); engine choice
SWING_RIGHT = 3  # bars to the right; the pivot is confirmed this many bars late; engine choice
ZIGZAG_ATR_MULT = 3.0  # a zigzag extreme is confirmed by a reversal of this many ATR; engine choice
DISPLACEMENT_ATR_MULT = 1.5  # displacement candle: body >= this x ATR; engine choice (the video shows "disp 1.57")
MSS_FAIL_BARS = 20  # an MSS fails if price closes back beyond its origin within this many bars; engine choice
MSS_SWEEP_LOOKBACK_BARS = 50  # an MSS "follows" the latest opposite-side sweep at most this many bars back
EQ_TOLERANCE_ATR_MULT = 0.1  # equal highs / lows: swing levels within this x ATR of each other; engine choice
MANIP_ATR_MULT = 1.5  # manipulation leg: body >= this x ATR on the bar that takes a pool (video: "at least 1.5x")
INDUCEMENT_MAX_ATR_MULT = 5.0  # a minor swing is an inducement only if a pool rests within this x ATR beyond it
FVG_MIN_ATR_MULT = 0.1  # ignore fair value gaps smaller than this x ATR; engine choice
FVG_MAX_AGE_BARS = 300  # a gap can be inverted for this many bars after it forms; engine choice
IFVG_MAX_AGE_BARS = 300  # an inverted gap can be retested for this many bars after the inversion; engine choice
OB_LOOKBACK_BARS = 10  # search this many bars before the break for the last opposite candle; engine choice
OB_MAX_AGE_BARS = 200  # an order block expires this many bars after confirmation; engine choice
REJECTION_WICK_FRAC = 0.5  # rejection candle: the wick into the zone is >= this share of the bar's range

DEFAULT_PARAMS: dict = {
    "atr_period": ATR_PERIOD, "swing_left": SWING_LEFT, "swing_right": SWING_RIGHT,
    "zigzag_atr_mult": ZIGZAG_ATR_MULT, "displacement_atr_mult": DISPLACEMENT_ATR_MULT,
    "mss_fail_bars": MSS_FAIL_BARS, "mss_sweep_lookback_bars": MSS_SWEEP_LOOKBACK_BARS,
    "eq_tolerance_atr_mult": EQ_TOLERANCE_ATR_MULT, "manip_atr_mult": MANIP_ATR_MULT,
    "inducement_max_atr_mult": INDUCEMENT_MAX_ATR_MULT, "fvg_min_atr_mult": FVG_MIN_ATR_MULT,
    "fvg_max_age_bars": FVG_MAX_AGE_BARS, "ifvg_max_age_bars": IFVG_MAX_AGE_BARS,
    "ob_lookback_bars": OB_LOOKBACK_BARS, "ob_max_age_bars": OB_MAX_AGE_BARS,
    "rejection_wick_frac": REJECTION_WICK_FRAC,
    # {"london": "03:00", "ny": "09:30"}: session open times on the wall clock of ``ts``; used when the bars carry
    # no ``session`` column. None = no session events.
    "session_opens": None,
}

BAR_COLUMNS = ("ts", "open", "high", "low", "close", "volume")
FLOAT_COLUMNS = ("level", "high", "low", "zone_low", "zone_high", "strength")
EVENT_COLUMNS = ("event_id", "kind", "symbol", "timeframe", "ts_event", "ts_anchor", "direction", "label",
                 *FLOAT_COLUMNS, "ref_event_id", "meta")
ZONE_COLUMNS = ("event_id", "kind", "direction", "zone_low", "zone_high", "ts_from", "ts_to")
KINDS = (
    "swing_high", "swing_low", "zigzag", "structure_break", "mss", "mss_failed", "pool_formed", "pool_swept",
    "sweep", "manip_leg", "inducement", "fvg_formed", "fvg_inverted", "ifvg_retest", "ob_confirmed",
    "ob_mitigated", "ob_invalidated", "ob_expired", "ob_consumed", "session_open", "rejection",
)
DIRECTION = {1: "bull", -1: "bear"}


class _Ctx:
    """The bars as plain lists (fast scalar loops), the previous bar's ATR, and the event sink."""

    def __init__(self, bars: pd.DataFrame, symbol: str, timeframe: str, params: dict | None) -> None:
        unknown = set(params or {}) - set(DEFAULT_PARAMS)
        if unknown:
            raise ValueError(f"unknown market-structure params: {sorted(unknown)}")
        missing = [col for col in BAR_COLUMNS if col not in bars.columns]
        if missing:
            raise ValueError(f"bars lack columns {missing}")
        self.p = {**DEFAULT_PARAMS, **(params or {})}
        self.symbol, self.timeframe = symbol, timeframe
        self.ts = pd.DatetimeIndex(bars["ts"])
        if not (self.ts.is_monotonic_increasing and self.ts.is_unique):
            raise ValueError("bars must be one symbol on one timeframe, sorted by a unique ts")
        px = bars[["open", "high", "low", "close"]].to_numpy(dtype=float)
        if not np.isfinite(px).all():
            raise ValueError("bars hold non-finite prices")
        self.n = len(bars)
        self.O, self.H, self.L, self.C = px.T
        self.o, self.h, self.l, self.c = (a.tolist() for a in px.T)
        s = bars.reset_index(drop=True)
        a = wilder_atr(s["high"], s["low"], s["close"], int(self.p["atr_period"])).shift(1).to_numpy(dtype=float)
        self.atr = np.where(a > 0, a, np.nan).tolist()  # NaN in warm-up and on dead-flat data: every rule then skips
        self.ns = self.ts.asi8.tolist()
        self.rows: list[tuple] = []

    def emit(self, kind: str, e: int, a: int, direction: str | None = None, label: str | None = None,
             level: float | None = None, high: float | None = None, low: float | None = None,
             zone_low: float | None = None, zone_high: float | None = None, strength: float | None = None,
             ref: str | None = None, key: str = "", **meta) -> str:
        """Record one event confirmed at bar ``e`` about bar ``a``; return its id.

        The id hashes kind, symbol, timeframe and the anchor fields (anchor ts, direction, label, level, ``key``),
        never the confirm bar or anything derived from later data.
        """
        raw = f"{kind}|{self.symbol}|{self.timeframe}|{self.ns[a]}|{direction}|{label}|{level!r}|{key}"
        eid = hashlib.blake2b(raw.encode(), digest_size=8).hexdigest()
        self.rows.append((e, eid, kind, a, direction, label, level, high, low, zone_low, zone_high, strength, ref, meta))
        return eid


def _pivots(x: np.ndarray, left: int, right: int, highs: bool) -> np.ndarray:
    """Indices of strict fractal pivots (same rule as ``features.extra.last_pivot``)."""
    if len(x) < left + right + 1:
        return np.empty(0, dtype=int)
    win = sliding_window_view(x, left + right + 1)
    others = np.delete(win, left, axis=1)
    mask = (win[:, left] > others.max(axis=1)) if highs else (win[:, left] < others.min(axis=1))
    return np.flatnonzero(mask) + left


def _swings(cx: _Ctx) -> dict[int, list[tuple]]:
    """``swing_high`` / ``swing_low``. Returns per side (+1 highs, -1 lows) ``(confirm bar, pivot bar, level, id)``."""
    left, right = int(cx.p["swing_left"]), int(cx.p["swing_right"])
    out: dict[int, list[tuple]] = {}
    for s, x, kind, above, below in ((1, cx.H, "swing_high", "HH", "LH"), (-1, cx.L, "swing_low", "HL", "LL")):
        prev, found = None, []
        for i in _pivots(x, left, right, s > 0).tolist():
            lev = float(x[i])
            label = None if prev is None else (above if lev > prev else below)
            if s < 0 and prev is not None and lev == prev:
                label = above  # an equal low is "not lower": HL, as an equal high is "not higher": LH
            found.append((i + right, i, lev, cx.emit(kind, i + right, i, label=label, level=lev)))
            prev = lev
        out[s] = found
    return out


def _zigzag(cx: _Ctx) -> None:
    """``zigzag``: one event per completed leg, confirmed by an ATR-multiple reversal off the leg's extreme."""
    h, lo, atr, mult = cx.h, cx.l, cx.atr, cx.p["zigzag_atr_mult"]
    mode, ext, ei, prev = 0, 0.0, -1, None
    for t in range(cx.n):
        a = atr[t]
        if a != a:
            continue
        if mode == 0:  # first bar with an ATR: start by tracking a high; the first extreme emits no leg
            mode, ext, ei = 1, h[t], t
            continue
        x, y = (h[t], lo[t]) if mode > 0 else (-lo[t], -h[t])  # mirrored: x extends the leg, y reverses it
        if x > ext:
            ext, ei = x, t
        elif ext - y >= mult * a:
            price = ext * mode
            if prev is not None:
                cx.emit("zigzag", t, ei, DIRECTION[mode], level=price, high=max(price, prev[1]),
                        low=min(price, prev[1]), strength=abs(price - prev[1]) / a, leg_start=str(cx.ts[prev[0]]))
            prev, mode = (ei, price), -mode
            ext, ei = -y, t


def _session_keys(cx: _Ctx, bars: pd.DataFrame, wall: pd.DatetimeIndex) -> tuple[list, list] | None:
    """(run key, session name) per bar: from the ``session`` column, else from ``params['session_opens']``."""
    if "session" in bars.columns:
        col = bars["session"]
        names = [None if pd.isna(v) else str(v) for v in col.tolist()]
        key, k = [], 0
        for i, v in enumerate(names):
            k += i > 0 and v != names[i - 1]
            key.append(k)
        return key, names
    opens = cx.p["session_opens"]
    if not opens:
        return None
    order = sorted(opens, key=lambda name: _minutes(opens[name]))
    mins = np.array([_minutes(opens[name]) for name in order])
    k = np.searchsorted(mins, wall.hour * 60 + wall.minute, side="right")
    day = wall.normalize().asi8 // 86_400_000_000_000
    return (day * len(order) + k).tolist(), [order[(i - 1) % len(order)] for i in k.tolist()]


def _minutes(hhmm: str) -> int:
    hh, mm = hhmm.split(":")
    return int(hh) * 60 + int(mm)


def _sessions(cx: _Ctx, bars: pd.DataFrame) -> dict[int, dict[int, list]]:
    """``session_open`` events, and the prior day / prior session extremes to turn into pools.

    Returns ``{side: {bar: [(level, anchor bar, label, period name)]}}``: a period's high and low are known only
    on the first bar of the next period, so that is the bar they are scheduled on.
    """
    wall = cx.ts.tz_localize(None)
    runs = [("D", wall.normalize().asi8.tolist(), None)]
    sess = _session_keys(cx, bars, wall)
    if sess is not None:
        runs.append(("S", *sess))
    sched: dict[int, dict[int, list]] = {1: defaultdict(list), -1: defaultdict(list)}
    h, lo = cx.h, cx.l
    for tag, key, names in runs:
        hi = lw = hi_i = lw_i = None
        for t in range(cx.n):
            if t and key[t] != key[t - 1]:
                if names is None or names[t - 1] is not None:
                    name = str(wall[t - 1].date()) if names is None else names[t - 1]
                    sched[1][t].append((hi, hi_i, f"P{tag}H", name))
                    sched[-1][t].append((lw, lw_i, f"P{tag}L", name))
                if names is not None and names[t] is not None:
                    cx.emit("session_open", t, t, label=names[t], level=cx.o[t])
                hi = lw = None
            if hi is None or h[t] > hi:
                hi, hi_i = h[t], t
            if lw is None or lo[t] < lw:
                lw, lw_i = lo[t], t
    return sched


def _liquidity_side(cx: _Ctx, s: int, swings: list[tuple], sched: dict[int, list]) -> list[tuple]:
    """Pools, sweeps, manipulation legs and inducements on one side (+1 buy-side above price, -1 sell-side below).

    Prices are mirrored by ``s`` so the body reads as the buy-side case. Returns ``(bar, sweep id)`` per sweep.
    """
    p, atr = cx.p, cx.atr
    x = cx.h if s > 0 else [-v for v in cx.l]
    o, c = (cx.o, cx.c) if s > 0 else ([-v for v in cx.o], [-v for v in cx.c])
    side, eq_label, against, with_ = ("BSL", "EQH", "bear", "bull") if s > 0 else ("SSL", "EQL", "bull", "bear")
    heap: list[tuple] = []  # live pools, nearest level first: (level, seq, pool)
    stack: list[list] = []  # unpierced swings, levels non-increasing towards the top: [level, pivot bar, id, pool]
    sweeps: list[tuple] = []
    k = seq = 0

    def new_pool(t: int, level: float, anchor: int, label: str, lo_: float, hi_: float, ref=None, **meta) -> dict:
        nonlocal seq
        zl, zh = (lo_, hi_) if s > 0 else (-hi_, -lo_)
        pid = cx.emit("pool_formed", t, anchor, label=label, level=level * s, zone_low=zl, zone_high=zh, ref=ref,
                      side=side, **meta)
        pool = {"id": pid, "level": level, "anchor": anchor, "label": label, "alive": True}
        seq += 1
        heapq.heappush(heap, (level, seq, pool))
        return pool

    for t in range(cx.n):
        a = atr[t]
        for lev, anchor, label, name in sched.get(t, ()):
            new_pool(t, lev * s, anchor, label, lev * s, lev * s, period=name)
        while k < len(swings) and swings[k][0] == t:
            _, piv, raw, eid = swings[k]
            k += 1
            sw = [raw * s, piv, eid, None]
            j = len(stack)
            while j > 0 and stack[j - 1][0] - sw[0] <= p["eq_tolerance_atr_mult"] * a:
                j -= 1
            if j < len(stack):  # equal highs: this swing plus the unpierced swings within tolerance just above it
                members = [*stack[j:], sw]
                old = None
                for m in reversed(members):
                    if m[3] is not None and m[3]["alive"]:
                        m[3]["alive"] = False  # superseded by the wider cluster: one live pool per level
                        old = old or m[3]["id"]
                pool = new_pool(t, members[0][0], piv, eq_label, sw[0], members[0][0], ref=old,
                                n_swings=len(members), swing_ids=[m[2] for m in members])
                for m in members:
                    m[3] = pool
            stack.append(sw)
        xt = x[t]
        taken = []
        while heap and heap[0][0] < xt:
            pool = heapq.heappop(heap)[2]
            if pool["alive"]:
                pool["alive"] = False
                taken.append(pool)
        if taken:
            near = taken[0]
            how = "closed_back" if c[t] <= near["level"] else "acceptance"
            sid = cx.emit("sweep", t, near["anchor"], against, how, level=near["level"] * s, high=cx.h[t],
                          low=cx.l[t], strength=(xt - near["level"]) / a, ref=near["id"], key=near["label"],
                          side=side, pool_ids=[pl["id"] for pl in taken])
            for pl in taken:
                cx.emit("pool_swept", t, pl["anchor"], against, "closed_back" if c[t] <= pl["level"] else "acceptance",
                        level=pl["level"] * s, ref=pl["id"], key=pl["label"], side=side, sweep_id=sid)
            body = c[t] - o[t]
            if body >= p["manip_atr_mult"] * a:
                cx.emit("manip_leg", t, t, with_, level=near["level"] * s, high=cx.h[t], low=cx.l[t],
                        strength=body / a, ref=sid, side=side)
            sweeps.append((t, sid))
        minor = None
        while stack and stack[-1][0] < xt:
            sw = stack.pop()
            if sw[3] is None:
                minor = sw  # the last one popped is the furthest minor swing this bar took
        if minor is not None and not taken:
            while heap and not heap[0][2]["alive"]:
                heapq.heappop(heap)
            if heap and heap[0][0] - minor[0] <= p["inducement_max_atr_mult"] * a:
                pool = heap[0][2]
                cx.emit("inducement", t, minor[1], against, level=minor[0] * s, high=cx.h[t], low=cx.l[t],
                        strength=(pool["level"] - minor[0]) / a, ref=pool["id"], side=side, swing_id=minor[2])
    return sweeps


def _structure(cx: _Ctx, swings: dict[int, list[tuple]], sweeps: dict[int, list[tuple]]) -> list[tuple]:
    """``structure_break`` (BOS / CHoCH), ``mss``, ``mss_failed``.

    Returns the displacement breaks ``(bar, side, break id, displacement)`` that order blocks are built from.
    """
    p, o, c, atr = cx.p, cx.o, cx.c, cx.atr
    ref: dict[int, list | None] = {1: None, -1: None}  # latest confirmed, unbroken swing: [level, pivot bar, id]
    ptr = {1: 0, -1: 0}
    sweep_bars = {s: [t for t, _ in sweeps[-s]] for s in (1, -1)}  # a bull MSS follows a sell-side sweep
    trend, watches, breaks = 0, [], []
    for t in range(cx.n):
        ct = c[t]
        if watches:
            keep = []
            for w in watches:
                t0, s, origin, mid = w
                if t - t0 > p["mss_fail_bars"]:
                    continue
                if (ct - origin) * s < 0:
                    cx.emit("mss_failed", t, t0, DIRECTION[s], level=origin, ref=mid)
                else:
                    keep.append(w)
            watches = keep
        for s in (1, -1):
            r = ref[s]
            if r is None or (ct - r[0]) * s <= 0:
                continue
            a, body = atr[t], (ct - o[t]) * s
            label = "CHoCH" if trend == -s else "BOS"
            bid = cx.emit("structure_break", t, r[1], DIRECTION[s], label, level=r[0], strength=body / a, ref=r[2])
            ref[s], trend = None, s
            if not body >= p["displacement_atr_mult"] * a:
                continue
            breaks.append((t, s, bid, body / a))
            if label == "CHoCH":
                origin = min(cx.l[r[1]:t + 1]) if s > 0 else max(cx.h[r[1]:t + 1])
                j = bisect_right(sweep_bars[s], t) - 1
                swept = j >= 0 and t - sweep_bars[s][j] <= p["mss_sweep_lookback_bars"]
                mid = cx.emit("mss", t, r[1], DIRECTION[s], level=r[0], strength=body / a,
                              ref=sweeps[-s][j][1] if swept else None, structure_break_id=bid, origin=origin,
                              **{"low" if s > 0 else "high": origin})
                watches.append((t, s, origin, mid))
        for s in (1, -1):  # swings confirmed on this bar become the reference from the next bar on
            lst, k = swings[s], ptr[s]
            while k < len(lst) and lst[k][0] == t:
                ref[s] = [lst[k][2], lst[k][1], lst[k][3]]
                k += 1
            ptr[s] = k
    return breaks


def _fvg(cx: _Ctx) -> list[list]:
    """``fvg_formed``, ``fvg_inverted``, ``ifvg_retest``. Returns the zones ``[from bar, to bar, low, high, side,
    id, kind]`` a rejection can happen at (live on bars ``from < t <= to``)."""
    p, h, lo, c, atr = cx.p, cx.h, cx.l, cx.c, cx.atr
    age, iage, pop, push = p["fvg_max_age_bars"], p["ifvg_max_age_bars"], heapq.heappop, heapq.heappush
    zones: list[list] = []
    gaps: dict[int, list] = {1: [], -1: []}  # un-inverted gaps of side s, the first one to invert on top
    inv: dict[int, list] = {1: [], -1: []}  # inverted gaps whose NEW side is s, the first one to be retested on top
    for t in range(cx.n):
        ht, lt, ct = h[t], lo[t], c[t]
        for s, px in ((-1, ht), (1, -lt)):  # retest: price trades back into the inverted gap
            hp = inv[s]
            while hp and hp[0][0] <= px:
                _, t0, zl, zh, iid, anchor = pop(hp)
                if t - t0 <= iage:
                    held = ct <= zh if s < 0 else ct >= zl
                    cx.emit("ifvg_retest", t, anchor, DIRECTION[s], "held" if held else "failed", high=ht, low=lt,
                            zone_low=zl, zone_high=zh, ref=iid)
        for s in (1, -1):  # inversion: a close through the far edge of the gap
            hp = gaps[s]
            while hp and hp[0][0] < ct * -s:
                _, t0, zl, zh, fid, zone = pop(hp)
                if t - t0 > age:
                    continue
                iid = cx.emit("fvg_inverted", t, t0 - 1, DIRECTION[-s], level=zl if s > 0 else zh, zone_low=zl,
                              zone_high=zh, ref=fid)
                zone[1] = t
                zones.append([t, t + iage, zl, zh, -s, iid, "fvg_inverted"])
                push(inv[-s], (zl if s > 0 else -zh, t, zl, zh, iid, t0 - 1))
        if t < 2:
            continue
        a = atr[t]
        for s, zl, zh in ((1, h[t - 2], lt), (-1, ht, lo[t - 2])):
            if zh > zl and zh - zl >= p["fvg_min_atr_mult"] * a:
                fid = cx.emit("fvg_formed", t, t - 1, DIRECTION[s], zone_low=zl, zone_high=zh, strength=(zh - zl) / a)
                zone = [t, t + age, zl, zh, s, fid, "fvg_formed"]
                zones.append(zone)
                push(gaps[s], (-zl if s > 0 else zh, t, zl, zh, fid, zone))
    return zones


def _order_blocks(cx: _Ctx, breaks: list[tuple]) -> list[list]:
    """``ob_confirmed`` and its lifecycle (``ob_mitigated``, then one of ``ob_invalidated`` / ``ob_consumed`` /
    ``ob_expired``). Returns rejection zones as :func:`_fvg` does."""
    p, o, h, lo, c = cx.p, cx.o, cx.h, cx.l, cx.c
    max_age, look = p["ob_max_age_bars"], p["ob_lookback_bars"]
    zones: list[list] = []
    live: list[list] = []  # ponytail: linear scan; order blocks are rare (displacement breaks only), a handful live
    seen: set[tuple] = set()
    k = 0
    for t in range(cx.n):
        if live:
            keep = []
            for ob in live:
                t0, s, zl, zh, oid, anchor, mitigated, zone = ob
                near, far = (lo[t] <= zh, lo[t] <= zl) if s > 0 else (h[t] >= zl, h[t] >= zh)
                if near and not mitigated:
                    cx.emit("ob_mitigated", t, anchor, DIRECTION[s], high=h[t], low=lo[t], zone_low=zl, zone_high=zh,
                            ref=oid)
                    ob[6] = True
                if far:
                    through = c[t] < zl if s > 0 else c[t] > zh
                    end = "ob_invalidated" if through else "ob_consumed"
                elif t - t0 >= max_age:
                    end = "ob_expired"
                else:
                    keep.append(ob)
                    continue
                cx.emit(end, t, anchor, DIRECTION[s], high=h[t], low=lo[t], zone_low=zl, zone_high=zh, ref=oid)
                zone[1] = t
            live = keep
        while k < len(breaks) and breaks[k][0] == t:
            _, s, bid, disp = breaks[k]
            k += 1
            for j in range(t - 1, max(t - 1 - look, -1), -1):
                if (c[j] - o[j]) * s < 0:  # the last opposite candle before the break
                    cleared = c[t] > h[j] if s > 0 else c[t] < lo[j]
                    if cleared and (j, s) not in seen:
                        seen.add((j, s))
                        oid = cx.emit("ob_confirmed", t, j, DIRECTION[s], zone_low=lo[j], zone_high=h[j],
                                      strength=disp, ref=bid)
                        zone = [t, t + max_age, lo[j], h[j], s, oid, "ob_confirmed"]
                        zones.append(zone)
                        live.append([t, s, lo[j], h[j], oid, j, False, zone])
                    break
    return zones


def _rejections(cx: _Ctx, zones: list[list]) -> None:
    """``rejection``: a wick-rejection candle at a live zone (one per bar and side, at the newest zone touched)."""
    frac = cx.p["rejection_wick_frac"]
    rng = cx.H - cx.L
    wick = {1: np.minimum(cx.O, cx.C) - cx.L, -1: cx.H - np.maximum(cx.O, cx.C)}
    flag = {s: (rng > 0) & (w >= frac * rng) for s, w in wick.items()}
    zones = sorted(zones, key=lambda z: z[0])
    h, lo, c = cx.h, cx.l, cx.c
    active: list[list] = []
    k = 0
    for t in np.flatnonzero(flag[1] | flag[-1]).tolist():
        while k < len(zones) and zones[k][0] < t:
            active.append(zones[k])
            k += 1
        active = [z for z in active if z[1] >= t]
        for s in (1, -1):
            if not flag[s][t]:
                continue
            for _, _, zl, zh, zs, zid, zkind in reversed(active):
                if zs == s and (lo[t] <= zh and c[t] >= zl if s > 0 else h[t] >= zl and c[t] <= zh):
                    cx.emit("rejection", t, t, DIRECTION[s], high=h[t], low=lo[t], zone_low=zl, zone_high=zh,
                            strength=float(wick[s][t] / rng[t]), ref=zid, zone_kind=zkind)
                    break


def _run(bars: pd.DataFrame, symbol: str, timeframe: str, params: dict | None) -> tuple[_Ctx, list[list]]:
    cx = _Ctx(bars, symbol, timeframe, params)
    swings = _swings(cx)
    _zigzag(cx)
    sched = _sessions(cx, bars)
    sweeps = {s: _liquidity_side(cx, s, swings[s], sched[s]) for s in (1, -1)}
    breaks = _structure(cx, swings, sweeps)
    zones = _fvg(cx) + _order_blocks(cx, breaks)
    _rejections(cx, zones)
    return cx, zones


def _frame(cx: _Ctx) -> pd.DataFrame:
    rows = sorted(cx.rows, key=lambda r: r[0])  # stable: by confirm bar, then family, then emission order
    cols = [list(col) for col in zip(*rows, strict=True)] if rows else [[] for _ in range(14)]
    e, eid, kind, a, direction, label, level, high, low, zl, zh, strength, ref, meta = cols
    n = len(rows)

    def obj(values: list) -> pd.Series:  # object dtype whatever the rows hold: None stays None
        return pd.Series(values, dtype=object)

    out = pd.DataFrame({
        "event_id": obj(eid), "kind": obj(kind), "symbol": obj([cx.symbol] * n),
        "timeframe": obj([cx.timeframe] * n), "ts_event": cx.ts[e], "ts_anchor": cx.ts[a],
        "direction": obj(direction), "label": obj(label),
        **{name: pd.Series(col, dtype=float) for name, col in zip(FLOAT_COLUMNS, (level, high, low, zl, zh, strength),
                                                                  strict=True)},
        "ref_event_id": obj(ref), "meta": obj(meta),
    }, columns=list(EVENT_COLUMNS))
    out.attrs["extractor_version"] = EXTRACTOR_VERSION
    return out


def extract_events(bars: pd.DataFrame, symbol: str, timeframe: str, params: dict | None = None) -> pd.DataFrame:
    """Every market-structure event of one symbol on one timeframe, ordered by ``ts_event``.

    ``bars``: columns ts, open, high, low, close, volume (+ optional ``session``), sorted by ``ts`` (bar open time).
    ``ts_event`` is the bar whose close completes the event: the only time a consumer may act on it.
    """
    return _frame(_run(bars, symbol, timeframe, params)[0])


def extract_zones(bars: pd.DataFrame, symbol: str, timeframe: str, params: dict | None = None) -> pd.DataFrame:
    """The zones a rejection can happen at (fair value gaps, inverted gaps, order blocks) with their live window:
    bars with ``ts_from < ts <= ts_to`` (``ts_to`` NaT = still live at the end of the data)."""
    cx, zones = _run(bars, symbol, timeframe, params)
    last = cx.n - 1
    return pd.DataFrame({
        "event_id": [z[5] for z in zones], "kind": [z[6] for z in zones],
        "direction": [DIRECTION[z[4]] for z in zones],
        "zone_low": [z[2] for z in zones], "zone_high": [z[3] for z in zones],
        "ts_from": cx.ts[[z[0] for z in zones]],
        "ts_to": cx.ts[[min(z[1], last) for z in zones]].where(np.array([z[1] <= last for z in zones], dtype=bool)),
    }, columns=list(ZONE_COLUMNS))


def rejections(bars: pd.DataFrame, symbol: str, timeframe: str, zones: pd.DataFrame,
               params: dict | None = None, zone_lag: pd.Timedelta | None = None) -> pd.DataFrame:
    """``rejection`` events of ``bars`` at ``zones`` from :func:`extract_zones`, usually of a HIGHER timeframe.

    A higher-timeframe zone is known only at the close of its bar: pass ``zone_lag`` = higher bar length minus
    this bar length, which is added to ``ts_from`` and ``ts_to``.
    """
    cx = _Ctx(bars, symbol, timeframe, params)
    lag = zone_lag or pd.Timedelta(0)
    start = np.searchsorted(cx.ts, pd.DatetimeIndex(zones["ts_from"]) + lag, side="right") - 1
    to = pd.DatetimeIndex(zones["ts_to"]) + lag
    end = np.where(to.isna(), cx.n, np.searchsorted(cx.ts, to, side="right") - 1)
    side = zones["direction"].map({"bull": 1, "bear": -1})
    _rejections(cx, [list(z) for z in zip(start.tolist(), end.tolist(), zones["zone_low"], zones["zone_high"], side,
                                          zones["event_id"], zones["kind"], strict=True)])
    return _frame(cx)
