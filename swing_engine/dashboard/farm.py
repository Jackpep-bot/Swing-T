"""Builders for the "farm" views (docs/proposals/video-model-plan.md P0 items 2-4, P1 item 9): chart layers from
decision receipts, the intraday market-structure chart, coverage and vocabulary. Pure functions shared by
``data.LiveData`` and ``demo.DemoData``: nothing here opens a store for writing or writes a file.

A drawable ``object`` is ``{id, layer, shape, t, t2, price, price2, dir, text, ref}``; ``shape`` is ``marker``
(on bar ``t``), ``line`` (``t, price`` to ``t2, price2``), ``zone`` (``price..price2`` from ``t`` to ``t2``) or
``band`` (background from ``t`` to ``t2``). ``ref`` keys ``receipts``: the JSON the Inspector shows. ``t`` is a
``YYYY-MM-DD`` session on the daily chart and wall-clock seconds on the intraday chart (New York for the ETFs, UTC
for crypto), the form the chart library takes.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# key, label, part of the "declutter" preset
SWING_LAYERS: tuple[tuple[str, str, bool], ...] = (
    ("taken", "Signals taken", True),
    ("seen", "Setups seen (shadow)", True),
    ("refusals", "Refusals", True),
    ("entries", "Entries", True),
    ("stops", "Stops", False),
    ("targets", "Targets", False),
    ("exits", "Exits", True),
    ("levels", "Support / resistance", False),
    ("regime", "Regime shading", False),
)
# key, label, features.market_structure kinds, part of the "declutter" preset (grouped as in the video)
INTRADAY_LAYERS: tuple[tuple[str, str, tuple[str, ...], bool], ...] = (
    ("pools", "Pools", ("pool_formed", "pool_swept"), False),
    ("sweeps", "Sweeps", ("sweep",), True),
    ("manip", "Manipulation legs", ("manip_leg",), True),
    ("inducements", "Inducements", ("inducement",), False),
    ("swings", "Swing structure", ("swing_high", "swing_low", "zigzag"), False),
    ("breaks", "Structure breaks", ("structure_break",), True),
    ("mss", "MSS / failed", ("mss", "mss_failed"), True),
    ("ob", "OB zones", ("ob_confirmed", "ob_mitigated", "ob_invalidated", "ob_expired", "ob_consumed"), True),
    ("fvg", "FVG / inversions", ("fvg_formed", "fvg_inverted", "ifvg_retest"), False),
    ("sessions", "Session opens", ("session_open",), True),
    ("rejections", "Rejections", ("rejection",), False),
)
INTRADAY_TFS = ("2m", "5m", "15m", "30m", "1h", "4h")
INTRADAY_DEFAULT_TF = "5m"
ZONE_KINDS = frozenset({"ob_confirmed", "fvg_formed", "fvg_inverted"})
LINE_KINDS = frozenset({"pool_formed", "pool_swept", "sweep", "inducement", "structure_break", "mss", "mss_failed"})
WARMUP_EXTRA_BARS = 50  # on top of the extractor's longest look-back (see intraday_window)
ETF_MINUTES_PER_DAY = 16 * 60  # Alpaca's extended session, 04:00-20:00 New York
LAYER_MAX_EVENTS = 5000  # receipts of one symbol on one chart
COVERAGE_DAYS = 60
COVERAGE_MAX_SYMBOLS = 40  # heatmap rows in the symbols view (busiest first)
STOP_TARGET_DEFAULT_DAYS = 14  # a stop / target line with no graded exit yet is drawn this many calendar days


def _f(value: Any, digits: int = 4) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return round(out, digits) if math.isfinite(out) else None


def _layer_rows(spec: Iterable[tuple], objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    n = Counter(o["layer"] for o in objects)
    return [{"key": row[0], "label": row[1], "count": n.get(row[0], 0), "default": bool(row[-1])} for row in spec]


def _obj(oid: str, layer: str, shape: str, t: Any, ref: str, *, t2: Any = None, price: float | None = None,
         price2: float | None = None, direction: str | None = None, text: str = "") -> dict[str, Any]:
    return {"id": oid, "layer": layer, "shape": shape, "t": t, "t2": t2, "price": price, "price2": price2,
            "dir": direction, "text": text, "ref": ref}


# ------------------------------------------------------------------------------------------------ daily chart
def _levels_of(payload: Mapping[str, Any]) -> tuple[float | None, float | None, str]:
    """(stop, target, side) of a receipt: the sized intent when there is one, else the signal."""
    intent = payload.get("intent") if isinstance(payload.get("intent"), Mapping) else {}
    signal = payload.get("signal") if isinstance(payload.get("signal"), Mapping) else {}
    pick = lambda key: _f(intent.get(key)) or _f(signal.get(key)) or _f(payload.get(key))  # noqa: E731
    return pick("stop"), pick("target"), str(intent.get("side") or signal.get("side") or payload.get("side") or "long")


def swing_objects(events: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Objects and receipts for ops.receipts rows of ONE symbol (``payload`` already parsed), oldest first.

    fire -> a ``taken`` (or ``seen`` when ``payload.shadow``) marker plus its stop and target lines, drawn to the
    last graded exit of that signal; refusal -> a marker; outcome -> one ``entries`` marker per signal (the fill,
    or "no fill") and one ``exits`` marker per distinct (exit date, hit); exit -> an ``exits`` marker. Notes are
    not drawn.
    """
    rows = [dict(e) for e in events]
    receipts = {str(e["event_id"]): e for e in rows}
    ends: dict[tuple[str, str], str] = {}
    for e in rows:
        p = e.get("payload") or {}
        if e.get("kind") == "outcome" and p.get("signal_as_of") and p.get("exit_date"):
            key = (str(e.get("strategy")), str(p["signal_as_of"]))
            ends[key] = max(ends.get(key, ""), str(p["exit_date"]))
    objects: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for e in rows:
        eid, kind, day, strategy = str(e["event_id"]), e.get("kind"), str(e.get("as_of")), str(e.get("strategy") or "")
        p = e.get("payload") or {}
        stop, target, side = _levels_of(p)
        direction = "bear" if side == "short" else "bull"
        if kind == "fire":
            layer = "seen" if p.get("shadow") else "taken"
            objects.append(_obj(f"{eid}:fire", layer, "marker", day, eid, direction=direction, text=strategy))
            end = ends.get((strategy, day)) or (date.fromisoformat(day) + timedelta(days=STOP_TARGET_DEFAULT_DAYS)).isoformat()
            for name, px in (("stops", stop), ("targets", target)):
                if px is not None:
                    objects.append(_obj(f"{eid}:{name}", name, "line", day, eid, t2=end, price=px, price2=px,
                                        text=f"{name[:-1]} {px:g}"))
        elif kind == "refusal":
            objects.append(_obj(f"{eid}:refusal", "refusals", "marker", day, eid, direction=direction,
                                text=str(e.get("step") or "refused")))
        elif kind == "outcome":
            sig_day, hit = str(p.get("signal_as_of") or ""), str(p.get("hit") or e.get("reason") or "")
            if (key := ("entry", strategy, sig_day)) not in seen:
                seen.add(key)
                px, at = _f(p.get("entry_price")), p.get("entry_date")
                objects.append(_obj(f"{eid}:entry", "entries", "marker", str(at or day), eid, direction=direction,
                                    text=f"entry {px:g}" if px is not None and at else "no fill"))
            if hit != "entry_skipped" and (key := ("exit", strategy, sig_day, day, hit)) not in seen:
                seen.add(key)
                r = _f(p.get("gross_r"), 2)
                objects.append(_obj(f"{eid}:exit", "exits", "marker", day, eid, direction=direction,
                                    text=hit.replace("_", " ") + (f" {r:+g}R" if r is not None else "")))
        elif kind == "exit":
            objects.append(_obj(f"{eid}:exit", "exits", "marker", day, eid, direction=direction,
                                text=str(e.get("step") or "exit")))
    return objects, receipts


def level_objects(days: list[str], high: list[float], low: list[float], close: list[float], start: str,
                  end: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """features.levels support_1 / resistance_1 over the whole history given, as one horizontal line per run of an
    unchanged level inside ``start..end`` (point-in-time: each bar's level uses confirmed pivots only)."""
    import numpy as np

    from swing_engine.features.levels import LEVEL_LOOKBACK, PIVOT_WIDTH, support_resistance_arrays

    objects: list[dict[str, Any]] = []
    receipts: dict[str, Any] = {}
    if len(days) <= LEVEL_LOOKBACK - PIVOT_WIDTH:
        return objects, receipts
    sup, res = support_resistance_arrays(np.asarray(high, dtype=float), np.asarray(low, dtype=float),
                                         np.asarray(close, dtype=float))
    for name, arr, direction in (("support_1", sup, "bull"), ("resistance_1", res, "bear")):
        run: list[Any] | None = None  # [first day, last day, level]
        for d, v in [*zip(days, arr.tolist(), strict=True), ("", float("nan"))]:
            level = _f(v) if start <= d <= end else None
            if run is not None and level == run[2]:
                run[1] = d
                continue
            if run is not None:
                ref = f"level:{name}:{run[0]}"
                receipts[ref] = {"kind": name, "level": run[2], "from": run[0], "to": run[1], "lookback_bars":
                                 LEVEL_LOOKBACK, "pivot_width": PIVOT_WIDTH, "source": "features.levels",
                                 "definition": "nearest confirmed pivot " + ("low below" if name == "support_1" else
                                                                             "high above") + " the prior close"}
                objects.append(_obj(ref, "levels", "line", run[0], ref, t2=run[1], price=run[2], price2=run[2],
                                    direction=direction, text=name))
            run = [d, d, level] if level is not None else None
    return objects, receipts


def regime_objects(by_day: Mapping[str, tuple[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """One ``band`` per run of the same regime over the days it is known for; ``by_day[day] = (regime, source)``."""
    objects: list[dict[str, Any]] = []
    receipts: dict[str, Any] = {}
    run: list[str] | None = None  # [first day, last day, regime, source]
    for d, (regime, source) in [*sorted(by_day.items()), ("", ("", ""))]:
        if run is not None and regime == run[2]:
            run[1] = d
            continue
        if run is not None:
            ref = f"regime:{run[0]}"
            receipts[ref] = {"kind": "regime", "regime": run[2], "from": run[0], "to": run[1], "source": run[3]}
            objects.append(_obj(ref, "regime", "band", run[0], ref, t2=run[1], text=run[2]))
        run = [d, d, regime, source] if regime else None
    return objects, receipts


def layers_payload(symbol: str, start: str, end: str, events: list[Mapping[str, Any]],
                   extra: Iterable[tuple[list[dict[str, Any]], dict[str, Any]]] = (),
                   engine_sig: str | None = None) -> dict[str, Any]:
    objects, receipts = swing_objects(events)
    for objs, recs in extra:
        objects += objs
        receipts.update(recs)
    kinds = Counter(str(e.get("kind")) for e in events)
    sig = next((e.get("engine_sig") for e in reversed(events) if e.get("engine_sig")), None) or engine_sig
    return {"symbol": symbol, "start": start, "end": end, "layers": _layer_rows(SWING_LAYERS, objects),
            "objects": objects, "receipts": receipts,
            "status": {"events": len(events), "fires": kinds.get("fire", 0), "refusals": kinds.get("refusal", 0),
                       "outcomes": kinds.get("outcome", 0), "engine_sig": sig}}


# ------------------------------------------------------------------------------------------------ intraday
def intraday_symbol(value: str) -> str:
    """``SPY`` / ``BTC-USD`` / ``BTC/USD`` -> the stored symbol; ValueError when it is not an ingested market."""
    from swing_engine.data.intraday import DEFAULT_SYMBOLS

    sym = (value or "").strip().upper().replace("-", "/")
    if sym not in DEFAULT_SYMBOLS:
        raise ValueError("symbol must be one of " + ", ".join(s.replace("/", "-") for s in DEFAULT_SYMBOLS))
    return sym


def market_tz(symbol: str) -> str:
    return "UTC" if "/" in symbol else "America/New_York"


def intraday_window(symbol: str, day: date, tf: str) -> tuple[Any, Any, Any]:
    """(warm-up start, day start, day end) as UTC instants. The day is the market's own calendar day (New York for
    the ETFs, UTC for crypto). The warm-up covers the extractor's longest look-back in bars of ``tf``."""
    import pandas as pd

    from swing_engine.data.intraday import TIMEFRAMES
    from swing_engine.features import market_structure as ms

    # ponytail: pools never expire, so a pool formed before the warm-up is not drawn; lengthen the warm-up (it
    # costs read time) if old PDH/EQH levels matter on the chart.
    bars = max(ms.FVG_MAX_AGE_BARS, ms.IFVG_MAX_AGE_BARS, ms.OB_MAX_AGE_BARS) + WARMUP_EXTRA_BARS
    tz = market_tz(symbol)
    lo = pd.Timestamp(day.isoformat(), tz=tz)
    hi = pd.Timestamp((day + timedelta(days=1)).isoformat(), tz=tz)
    crypto = "/" in symbol
    sessions = math.ceil(bars * TIMEFRAMES[tf] / (24 * 60 if crypto else ETF_MINUTES_PER_DAY))
    days = sessions + 1 if crypto else math.ceil(sessions * 7 / 5) + 4  # weekends plus a holiday or two
    return (lo - pd.Timedelta(days=days)).tz_convert("UTC"), lo.tz_convert("UTC"), hi.tz_convert("UTC")


def intraday_payload(symbol: str, day: date, tf: str, bars: Any, *, engine_sig: str | None = None,
                     first_day: str | None = None, last_day: str | None = None) -> dict[str, Any]:
    """Candles of ``day`` and the market-structure events whose ``ts_event`` falls inside it. ``bars`` are the
    complete ``tf`` bars of the warm-up plus the day (data.intraday.read_bars columns, ``ts`` tz-aware)."""
    import pandas as pd

    from swing_engine.features.market_structure import EXTRACTOR_VERSION, extract_events, extract_zones

    tz = market_tz(symbol)
    _, lo, hi = intraday_window(symbol, day, tf)
    frame = bars.assign(ts=pd.to_datetime(bars["ts"], utc=True).dt.tz_convert(tz)).reset_index(drop=True)
    in_day = frame[(frame["ts"] >= lo) & (frame["ts"] < hi)]

    def wall(ts: Any) -> int | None:  # wall-clock seconds on the market's clock: what the chart's time axis shows
        if ts is None or pd.isna(ts):
            return None
        return int((pd.Timestamp(ts).tz_convert(tz).tz_localize(None) - pd.Timestamp(0)) // pd.Timedelta(seconds=1))

    def iso(ts: Any) -> str | None:
        return None if ts is None or pd.isna(ts) else pd.Timestamp(ts).tz_convert("UTC").isoformat()

    out_bars = [{"t": wall(r.ts), "o": _f(r.open), "h": _f(r.high), "l": _f(r.low), "c": _f(r.close),
                 "v": _f(r.volume, 2), "session": r.session} for r in in_day.itertuples()]
    objects: list[dict[str, Any]] = []
    receipts: dict[str, Any] = {}
    if len(in_day):
        events = extract_events(frame, symbol, tf)
        zones = extract_zones(frame, symbol, tf)
        zone_end = {(z.event_id, z.kind): z.ts_to for z in zones.itertuples()}
        layer_of = {kind: key for key, _label, kinds, _d in INTRADAY_LAYERS for kind in kinds}
        events = events[(events["ts_event"] >= lo) & (events["ts_event"] < hi)]
        for n, e in enumerate(events.to_dict("records")):
            kind, eid = e["kind"], f"{e['event_id']}:{e['kind']}:{n}"  # lifecycle events share an anchor: n keeps ids unique
            level, zl, zh = _f(e["level"]), _f(e["zone_low"]), _f(e["zone_high"])
            t_event, t_anchor = wall(e["ts_event"]), wall(e["ts_anchor"])
            receipts[eid] = {**{k: e[k] for k in ("event_id", "kind", "symbol", "timeframe", "direction", "label",
                                                   "ref_event_id")},
                             "ts_event": iso(e["ts_event"]), "ts_anchor": iso(e["ts_anchor"]),
                             **{k: _f(e[k], 6) for k in ("level", "high", "low", "zone_low", "zone_high", "strength")},
                             "meta": e["meta"] or {}}
            text = str(e["label"] or kind)
            common = {"direction": e["direction"], "text": text}
            layer = layer_of.get(kind, "swings")
            if kind in ZONE_KINDS and zl is not None and zh is not None:
                objects.append(_obj(eid, layer, "zone", t_event, eid, t2=wall(zone_end.get((e["event_id"], kind))),
                                    price=zl, price2=zh, **common))
            elif kind == "zigzag" and level is not None:
                other = _f(e["low"] if e["direction"] == "bull" else e["high"])
                start = wall(pd.Timestamp((e["meta"] or {}).get("leg_start"))) if (e["meta"] or {}).get("leg_start") else None
                objects.append(_obj(eid, layer, "line", start if start is not None else t_anchor, eid, t2=t_anchor,
                                    price=other if start is not None and other is not None else level, price2=level,
                                    **common))
            elif kind in LINE_KINDS and level is not None:
                objects.append(_obj(eid, layer, "line", t_anchor, eid, t2=t_event, price=level, price2=level, **common))
            else:
                pivot = kind in ("swing_high", "swing_low") and e["ts_anchor"] >= lo  # drawn on the pivot bar
                direction = {"swing_high": "bear", "swing_low": "bull"}.get(kind, e["direction"])
                objects.append(_obj(eid, layer, "marker", t_anchor if pivot else t_event, eid, direction=direction,
                                    text=text))
    else:
        events = []
    return {"symbol": symbol, "day": day.isoformat(), "tf": tf, "tz": tz, "bars": out_bars,
            "layers": _layer_rows(INTRADAY_LAYERS, objects), "objects": objects, "receipts": receipts,
            "first_day": first_day, "last_day": last_day,
            "status": {"bars": len(out_bars), "events": len(events), "warmup_bars": int(len(frame) - len(in_day)),
                       "extractor_version": EXTRACTOR_VERSION, "engine_sig": engine_sig}}


# ------------------------------------------------------------------------------------------------ coverage
def coverage_payload(rows: Iterable[tuple[str, str, str, str, int]], totals: Mapping[str, int],
                     days_window: int = COVERAGE_DAYS) -> dict[str, Any]:
    """Heatmap cells from ``(day, strategy, symbol, kind, n)`` rows of the events table and the summary tiles."""
    grids: dict[str, dict[str, Counter]] = {"strategies": {}, "symbols": {}}
    days: set[str] = set()
    for day, strategy, symbol, _kind, n in rows:
        days.add(day)
        for view, key in (("strategies", strategy), ("symbols", symbol)):
            if key:
                grids[view].setdefault(key, Counter())[day] += int(n)
    out: dict[str, Any] = {"window_days": days_window, "days": sorted(days), "tiles": dict(totals)}
    for view, grid in grids.items():
        ranked = sorted(grid.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
        limit = COVERAGE_MAX_SYMBOLS if view == "symbols" else len(ranked)
        out[view] = {"total": len(ranked),
                     "rows": [{"key": k, "total": sum(c.values()), "cells": dict(c)} for k, c in ranked[:limit]]}
    return out


# ------------------------------------------------------------------------------------------------ vocabulary
def vocabulary_payload() -> dict[str, Any]:
    """ops.vocabulary: every strategy with its definition and dated rulings, plus the market-structure kinds."""
    from swing_engine.ops import vocabulary as vocab

    rulings = vocab.read_rulings()
    as_rows = lambda items: [{"date": d, "text": t} for d, t in sorted(items)]  # noqa: E731
    return {
        "rulings_for_everything": as_rows(rulings.get("*", [])),
        "strategies": [{**e, "rulings": as_rows(e["rulings"])} for e in vocab.entries()],
        "structure": [{**e, "rulings": as_rows(r for k in e["kinds"] for r in rulings.get(k, []))}
                      for e in vocab.structure_entries()],
        "structure_doc": f"docs/{vocab.STRUCTURE_DOC}",
    }
