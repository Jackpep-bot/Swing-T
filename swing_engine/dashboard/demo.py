"""Deterministic fake data for every dashboard endpoint (``python -m swing_engine.dashboard --demo``).

Nothing here touches the disk, the network, the broker or the kill-switch file: ratings and the kill switch
live in memory for the life of the process. Tickers are fictional (the sample provider's style) so a screenshot
can never be mistaken for a recommendation. Same output on every run: the clock is pinned to ``DEMO_NOW`` and
every series comes from a ``random.Random`` seeded with the CRC32 of its name.
"""
from __future__ import annotations

import math
import random
import threading
import zlib
from datetime import UTC, date, datetime, timedelta
from typing import Any

from swing_engine.core.config import default_playbook_table

from .data import (
    EQUITY_PERIODS,
    MAX_ALERTS,
    SMA_FAST,
    SMA_SLOW,
    clean,
    ok,
    rebase,
    sma_series,
    unavailable,
)

DEMO_AS_OF = date(2026, 10, 6)
DEMO_NOW = datetime(2026, 10, 6, 19, 45, tzinfo=UTC)  # 15:45 ET, market open
DEMO_KILL_PATH = "demo://state/KILL (in memory; the real file is never touched in demo mode)"
ACCOUNT_START = date(2026, 4, 1)
HISTORY_START = date(2025, 6, 2)
STRATEGIES = ("pullback_trend", "sr_bounce", "sr_breakout", "breakout_52w", "rsi2_meanrev", "momentum_burst",
              "insider_cluster", "pullback_holy_grail", "base_breakout", "power_gap", "qullamaggie_flag",
              "episodic_pivot")
REGIMES = ("healthy_uptrend", "narrow_uptrend", "choppy", "correction", "high_vol_selloff")
NARROW_TABLE = dict(default_playbook_table()["narrow_uptrend"])  # the same table the real router uses


def _rng(name: str) -> random.Random:
    return random.Random(zlib.crc32(name.encode()))


def _sessions(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _walk(name: str, start_value: float, days: list[date], drift: float, vol: float) -> list[float]:
    rng = _rng(name)
    v, out = start_value, []
    for _ in days:
        v *= math.exp(drift + vol * rng.gauss(0.0, 1.0))
        out.append(v)
    return out


def _ts(d: date, hh: int = 13, mm: int = 30) -> str:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=UTC).isoformat().replace("+00:00", "Z")


class DemoData:
    """Same interface as ``data.LiveData``; every method returns an envelope."""

    demo = True

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ratings: dict[str, str] = {}
        self._killed = False
        self.days = _sessions(HISTORY_START, DEMO_AS_OF)
        self.spy = _walk("SPY", 520.0, self.days, 0.0005, 0.009)
        acct_days = [d for d in self.days if d >= ACCOUNT_START]
        self.account_days = acct_days
        self.account = _walk("account", 100_000.0, acct_days, 0.0007, 0.006)
        self.account[0] = 100_000.0
        self._positions = self._make_positions()
        self._signals_cache: dict[date, list[dict[str, Any]]] = {}
        self._alerts = self._make_alerts()

    # ------------------------------------------------------------------------------------------- helpers
    def bars(self, symbol: str, days: int = 400) -> list[dict[str, Any]]:
        sessions = self.days[-days:]
        rng = _rng(f"bars:{symbol}")
        base = 20.0 + rng.random() * 280.0
        drift = 0.0012 if symbol in {p["symbol"] for p in getattr(self, "_positions", [])} else 0.0004
        closes = _walk(f"close:{symbol}", base, sessions, drift, 0.017)
        out, prev = [], closes[0]
        for d, c in zip(sessions, closes, strict=True):
            o = prev * (1 + rng.gauss(0, 0.004))
            h = max(o, c) * (1 + abs(rng.gauss(0, 0.007)))
            low = min(o, c) * (1 - abs(rng.gauss(0, 0.007)))
            v = int(800_000 * (0.6 + rng.random()))
            out.append({"t": d.isoformat(), "o": round(o, 2), "h": round(h, 2), "l": round(low, 2), "c": round(c, 2),
                        "v": v})
            prev = c
        return out

    def _make_positions(self) -> list[dict[str, Any]]:
        spec = [("ORCA", "pullback_trend", 12, 0.5), ("KITE", "sr_bounce", 6, 0.5),
                ("WREN", "rsi2_meanrev", 3, 0.75), ("NOVA", "insider_cluster", 18, 0.5)]
        self._positions = [{"symbol": s} for s, *_ in spec]
        out = []
        for symbol, strategy, held, _mult in spec:
            bars = self.bars(symbol)
            entry_bar = bars[-held - 1]
            entry = round(entry_bar["o"], 2)
            risk = round(entry * 0.055, 2)
            stop = round(entry - risk, 2)
            target = round(entry + 2.5 * risk, 2)
            current = bars[-1]["c"]
            if current <= stop:
                stop = round(current * 0.95, 2)
                risk = round(entry - stop, 2)
            if current >= target:
                target = round(current * 1.05, 2)
            r_mult = (current - entry) / risk if risk else None
            current_stop = stop
            if r_mult is not None and r_mult >= 1.0:
                current_stop = entry  # position manager: breakeven at +1R
            rng = _rng(f"qty:{symbol}")
            qty = max(1, int(1000 / risk)) if risk else 10
            qty = int(qty * (0.8 + 0.4 * rng.random()))
            mv = round(qty * current, 2)
            upl = round(qty * (current - entry), 2)
            max_hold = {"rsi2_meanrev": 5, "sr_bounce": 15, "pullback_trend": 20, "insider_cluster": 30}[strategy]
            out.append({
                "symbol": symbol, "side": "long", "qty": qty, "avg_entry": entry, "current": current,
                "market_value": mv, "unrealized_pl": upl, "unrealized_plpc": round((current / entry - 1), 5),
                "strategy": strategy, "stop": stop, "target": target, "current_stop": current_stop,
                "risk_per_share": round(entry - stop, 4), "r_multiple": round(r_mult, 3) if r_mult is not None else None,
                "days_held": held, "max_hold_days": max_hold, "opened_at": _ts(date.fromisoformat(entry_bar["t"])),
                "client_order_id": f"swing-{strategy}-{symbol}-{entry_bar['t'].replace('-', '')}-long",
            })
        return out

    def _make_alerts(self) -> list[dict[str, Any]]:
        spec = [
            (0.4, "P3", "alpaca_account", "account", ["KITE"], ["held_position_move"], "KITE down 5.2% from entry intraday"),
            (1.1, "P2", "nasdaq_halts", "halt", ["BRGE"], ["watchlist_halt"], "BRGE halted: LULD pause (M)"),
            (2.6, "P2", "edgar", "filing", ["NOVA"], ["insider_cluster"], "NOVA Form 4: 3 insiders bought within 5 days"),
            (3.0, "P1", "alpaca_news", "news", ["ORCA"], ["watchlist_hit"], "ORCA raises full-year guidance"),
            (5.5, "P2", "alpaca_stocks", "bar_trigger", ["TSLX"], ["break_52w_high", "rvol_gate"],
             "TSLX breaks 52-week high on 3.1x relative volume"),
            (7.2, "P1", "alpaca_news", "news", ["HRBR"], ["watchlist_hit"], "HRBR added to an index rebalance list"),
            (9.8, "P2", "alpaca_stocks", "bar_trigger", ["CRST"], ["gap_rvol_news"], "CRST gaps +9% with news and 2.4x RVOL"),
            (18.0, "P3", "edgar", "filing", ["WREN"], ["held_8k_severe"], "WREN 8-K item 4.02 (non-reliance) filed"),
            (22.5, "P2", "smallcap", "bar_trigger", ["ZNTH"], ["smallcap_dump_warning"],
             "ZNTH small-cap runner: avoid, float rotation 6x"),
            (26.0, "P1", "alpaca_news", "news", ["BLUE"], ["watchlist_hit"], "BLUE analyst day scheduled next week"),
            (31.0, "P2", "nasdaq_halts", "halt", ["AMBR"], ["watchlist_halt"], "AMBR halted: news pending (T1)"),
            (40.0, "P2", "alpaca_stocks", "bar_trigger", ["YLLW"], ["break_52w_high"], "YLLW breaks 52-week high"),
        ]
        initial = {2: "useful", 3: "noise", 7: "traded", 8: "noise", 10: "useful"}
        out = []
        for i, (hours_ago, prio, source, kind, syms, rules, title) in enumerate(spec):
            ts = DEMO_NOW - timedelta(hours=hours_ago)
            eid = f"{source}:demo{i:03d}"
            if i in initial:
                self._ratings[eid] = initial[i]
            out.append({"event_id": eid, "ts": ts.isoformat().replace("+00:00", "Z"), "priority": prio, "title": title,
                        "source": source, "kind": kind, "symbols": syms, "rule_hits": rules,
                        "url": None, "delivered": prio != "P1"})
        return out

    # ------------------------------------------------------------------------------------------- endpoints
    def health(self) -> dict[str, Any]:
        from swing_engine import __version__

        return ok({"version": __version__, "settings_path": None, "store_path": None, "demo": True})

    def summary(self) -> dict[str, Any]:
        eq, last = self.account[-1], self.account[-2]
        with self._lock:
            killed = self._killed
        steps = [
            ("ingest", "ok", "61 bars for 61 symbols via massive (grouped, 1 session)", 41.2),
            ("float", "ok", "3 float rows refreshed", 4.1),
            ("features", "ok", "312,400 rows x 64 columns for 1,412 symbols; 1 breadth rows", 38.7),
            ("scan", "ok", "9 signals from 4 strategies; regime narrow_uptrend: allowed pullback_trend x0.5, "
                           "sr_bounce x0.5, rsi2_meanrev x0.75, insider_cluster x0.5", 6.3),
            ("rank", "ok", "1,412 symbols scored, 9 signals tagged", 2.2),
            ("size", "ok", "7 intents from 9 signals at equity 104,880; 2 skipped by risk", 0.1),
            ("review", "ok", "7 reviewed: 4 approve, 2 needs_more_info, 1 reject", 48.9),
            ("shadow", "ok", "9 signals recorded, 14 graded", 1.4),
            ("positions", "ok", "1 exit action (replace_stop)", 0.6),
            ("execute", "ok", "paper: entries {'submitted': 3, 'vetoed': 3, 'capped': 1}; exits {'done': 1}", 2.8),
            ("journal", "ok", "entry written to data/journal/2026-10-06.md", 9.5),
        ]
        data = {
            "mode": "DEMO",
            "account": {"equity": round(eq, 2), "last_equity": round(last, 2), "cash": round(eq * 0.41, 2),
                        "buying_power": round(eq * 0.82, 2), "day_pl": round(eq - last, 2),
                        "day_pl_pct": round((eq / last - 1) * 100, 3), "source": "demo"},
            "kill_switch": {"tripped": killed, "path": DEMO_KILL_PATH,
                            "reason": "tripped from the dashboard (demo)" if killed else ""},
            "nightly": {"as_of": DEMO_AS_OF.isoformat(), "started_at": "2026-10-06T10:30:02Z",
                        "finished_at": "2026-10-06T10:32:38Z", "ok": True, "dry_run": False, "provider": "massive",
                        "steps": [{"name": n, "status": s, "detail": d, "elapsed_s": e} for n, s, d, e in steps]},
            "monitor": {
                "last_event_at": "2026-10-06T19:44:51Z",
                "feeds": {"alpaca_news": "2026-10-06T19:44:51Z", "alpaca_stocks": "2026-10-06T19:44:00Z",
                          "alpaca_account": "2026-10-06T19:21:13Z", "edgar": "2026-10-06T19:43:30Z",
                          "nasdaq_halts": "2026-10-06T19:40:05Z"},
                "alerts_24h": sum(1 for a in self._alerts if a["delivered"] and self._hours_ago(a) <= 24),
            },
            "clock": {"is_open": True, "next_open": "2026-10-07T13:30:00Z", "next_close": "2026-10-06T20:00:00Z",
                      "source": "demo"},
            "generated_at": DEMO_NOW.isoformat().replace("+00:00", "Z"),
        }
        return ok(data)

    def _hours_ago(self, alert: dict[str, Any]) -> float:
        ts = datetime.fromisoformat(alert["ts"].replace("Z", "+00:00"))
        return (DEMO_NOW - ts).total_seconds() / 3600.0

    def regime(self, day: date | None = None) -> dict[str, Any]:
        as_of = min(day or DEMO_AS_OF, DEMO_AS_OF)
        hist = []
        rng = _rng("breadth")
        p50, p200, ratio = 55.0, 62.0, 1.5
        for d in self.days[-250:]:
            p50 = min(90, max(10, p50 + rng.gauss(0, 3.0)))
            p200 = min(90, max(15, p200 + rng.gauss(0, 1.2)))
            ratio = min(4.0, max(0.2, ratio * math.exp(rng.gauss(0, 0.12))))
            if d <= as_of:
                hist.append({"date": d.isoformat(), "pct_above_50": round(p50, 1), "pct_above_200": round(p200, 1),
                             "ratio_10d": round(ratio, 2)})
        last = hist[-1] if hist else {}
        blocked = {s: "not in the playbook table for this regime" for s in STRATEGIES if s not in NARROW_TABLE}
        state = {
            "as_of": as_of.isoformat(), "regime": "narrow_uptrend", "spy_trend": "up",
            "vol_regime": "normal", "breadth": "neutral",
            "breadth_values": {k: last.get(k) for k in ("pct_above_50", "pct_above_200", "ratio_10d")},
            "inputs": {"spy_close": round(self.spy[-1], 2), "spy_dist_52w_high_pct": -2.4, "spy_vol_pct": 0.48},
            "notes": ["SPY within 5% of its 52-week high while fewer than half of stocks are above their 50-day: "
                      "a narrow, leader-driven tape", "breakout families need breadth confirmation; pullbacks at half size"],
        }
        return ok({"state": state, "allowed": dict(NARROW_TABLE), "blocked": blocked, "breadth_history": hist,
                   "available_dates": [d.isoformat() for d in self.days[-10:]][::-1]})

    def equity(self, period: str = "6M") -> dict[str, Any]:
        days = EQUITY_PERIODS.get(period)
        start = DEMO_AS_OF - timedelta(days=days) if days else date.min
        account = [{"t": d.isoformat(), "equity": round(v, 2)} for d, v in zip(self.account_days, self.account,
                                                                                  strict=True) if d >= start]
        spy_start = max(start, self.account_days[0])
        spy = [{"t": d.isoformat(), "close": round(v, 2)} for d, v in zip(self.days, self.spy, strict=True)
               if d >= spy_start]
        normalized, stats = rebase(account, spy)
        return ok({"period": period, "account": account, "spy": spy, "normalized": normalized, "stats": stats,
                   "account_source": "demo"})

    def positions(self) -> dict[str, Any]:
        return ok(clean([{k: v for k, v in p.items() if k != "client_order_id"} for p in self._positions]),
                  source="demo")

    def orders(self, status: str = "open", limit: int = 50) -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        if status == "open":
            for i, p in enumerate(self._positions):
                parent = p["client_order_id"]
                out.append(self._order(f"demo-stop-{i}", f"{parent}-stop", p["symbol"], "sell", "stop", p["qty"], 0,
                                       None, p["current_stop"], "new", p["opened_at"], None, None, p["strategy"]))
                out.append(self._order(f"demo-tp-{i}", f"{parent}-tp", p["symbol"], "sell", "limit", p["qty"], 0,
                                       p["target"], None, "new", p["opened_at"], None, None, p["strategy"]))
            entry = self._order("demo-entry-9", "swing-pullback_trend-TSLX-20261006-long", "TSLX", "buy", "limit", 40,
                                0, 182.4, None, "new", "2026-10-06T10:32:11Z", None, None, "pullback_trend")
            entry["order_class"] = "bracket"
            entry["legs"] = [
                self._order("demo-entry-9-sl", None, "TSLX", "sell", "stop", 40, 0, None, 171.9, "held",
                            "2026-10-06T10:32:11Z", None, None, "pullback_trend"),
                self._order("demo-entry-9-tp", None, "TSLX", "sell", "limit", 40, 0, 208.6, None, "held",
                            "2026-10-06T10:32:11Z", None, None, "pullback_trend"),
            ]
            out.insert(0, entry)
        else:
            for i, p in enumerate(self._positions):
                out.append(self._order(f"demo-fill-{i}", p["client_order_id"], p["symbol"], "buy", "limit", p["qty"],
                                       p["qty"], round(p["avg_entry"] * 1.01, 2), None, "filled", p["opened_at"],
                                       p["opened_at"], p["avg_entry"], p["strategy"]))
            closed = [("BLUE", "pullback_trend", 61.2, 68.9, "limit", "2026-09-14", "2026-09-25"),
                      ("AMBR", "sr_breakout", 140.5, 133.1, "stop", "2026-09-08", "2026-09-11"),
                      ("CRST", "rsi2_meanrev", 33.4, 35.2, "market", "2026-09-21", "2026-09-24")]
            for j, (sym, strat, ent, ext, typ, d0, d1) in enumerate(closed):
                coid = f"swing-{strat}-{sym}-{d0.replace('-', '')}-long"
                out.append(self._order(f"demo-c{j}-in", coid, sym, "buy", "limit", 50, 50, round(ent * 1.01, 2), None,
                                       "filled", _ts(date.fromisoformat(d0)), _ts(date.fromisoformat(d0), 13, 31),
                                       ent, strat))
                out.append(self._order(f"demo-c{j}-out", None, sym, "sell", typ, 50, 50,
                                       ext if typ == "limit" else None, ext if typ == "stop" else None, "filled",
                                       _ts(date.fromisoformat(d0), 13, 31), _ts(date.fromisoformat(d1), 15, 2), ext,
                                       strat))
            out.sort(key=lambda o: o["filled_at"] or o["submitted_at"] or "", reverse=True)
        return ok(out[:limit], source="demo")

    @staticmethod
    def _order(oid: str, coid: str | None, symbol: str, side: str, typ: str, qty: int, filled: int,
               limit: float | None, stop: float | None, status: str, submitted: str | None, filled_at: str | None,
               avg: float | None, strategy: str | None) -> dict[str, Any]:
        return {"id": oid, "client_order_id": coid, "symbol": symbol, "side": side, "type": typ, "qty": qty,
                "filled_qty": filled, "limit_price": limit, "stop_price": stop, "status": status,
                "submitted_at": submitted, "filled_at": filled_at, "filled_avg_price": avg, "strategy": strategy,
                "order_class": None, "legs": []}

    def chart(self, symbol: str, days: int = 180) -> dict[str, Any]:
        all_bars = self.bars(symbol)
        first = (DEMO_AS_OF - timedelta(days=days)).isoformat()  # calendar days back from the last bar, as live
        bars = [b for b in all_bars if b["t"] >= first]
        closes = [(b["t"], b["c"]) for b in all_bars]
        sma20 = [p for p in sma_series(closes, SMA_FAST) if p["t"] >= first]
        sma50 = [p for p in sma_series(closes, SMA_SLOW) if p["t"] >= first]
        pos = next((p for p in self._positions if p["symbol"] == symbol), None)
        levels = {"entry": None, "stop": None, "target": None, "current_stop": None}
        markers: list[dict[str, Any]] = []
        if pos:
            levels = {"entry": pos["avg_entry"], "stop": pos["stop"], "target": pos["target"],
                      "current_stop": pos["current_stop"]}
            opened = pos["opened_at"][:10]
            sig_day = (date.fromisoformat(opened) - timedelta(days=1 if date.fromisoformat(opened).weekday() else 3))
            markers.append({"t": sig_day.isoformat(), "kind": "signal", "price": round(pos["avg_entry"] * 0.99, 2),
                            "text": f"{pos['strategy']} signal"})
            markers.append({"t": opened, "kind": "entry", "price": pos["avg_entry"],
                            "text": f"bought {pos['qty']} @ {pos['avg_entry']:.2f}"})
        else:
            rng = _rng(f"markers:{symbol}")
            k = len(bars) - 1 - rng.randint(5, max(6, len(bars) // 3))
            if k > 0:
                b = bars[k]
                markers.append({"t": b["t"], "kind": "signal", "price": b["c"], "text": "sr_bounce signal (not taken: "
                                "daily cap)"})
        return ok({"symbol": symbol, "bars": bars, "sma20": sma20, "sma50": sma50, "levels": levels,
                   "markers": markers})

    def _signals_for(self, day: date) -> list[dict[str, Any]]:
        if day in self._signals_cache:
            return self._signals_cache[day]
        rng = _rng(f"signals:{day.isoformat()}")
        names = ["TSLX", "HRBR", "CRST", "BLUE", "YLLW", "AMBR", "BSLT", "ZNTH", "OPAL"]
        strategies = ["pullback_trend", "sr_bounce", "rsi2_meanrev", "insider_cluster", "pullback_trend",
                      "sr_bounce", "rsi2_meanrev", "rsi2_meanrev", "sr_bounce"]
        outcomes = [
            (True, None, "approve"),
            (True, None, "approve"),
            (True, None, "approve"),
            (False, "review decision needs_more_info", "needs_more_info"),
            (False, "review decision reject", "reject"),
            (False, "daily cap reached (execution.max_new_orders_per_day = 5)", "approve"),
            (False, "review decision needs_more_info", "needs_more_info"),
            (False, "reward_risk 1.62 below min 2.0", None),
            (False, "reward_risk 1.20 below min 2.0", None),
        ]
        theses = {
            "approve": "Orderly pullback to the rising 20-day in a group leader; volume dried up on the dip and no "
                       "earnings fall inside the hold window.",
            "needs_more_info": "Setup is clean on price, but no news or filings were supplied, so the catalyst and "
                               "event risk cannot be checked.",
            "reject": "An 8-K filed after the close discloses an offering; supply overhang contradicts the bounce "
                      "thesis.",
        }
        out = []
        for i, (sym, strat) in enumerate(zip(names, strategies, strict=True)):
            taken, reason, decision = outcomes[i]
            entry = round(20 + rng.random() * 250, 2)
            risk = round(entry * (0.03 + rng.random() * 0.04), 2)
            rr = 2.0 + rng.random() * 1.5 if reason is None or "reward_risk" not in reason else float(reason.split()[1])
            review = None
            if decision is not None:
                flags = ["offering"] if decision == "reject" else (["earnings_in_window"] if i == 6 else [])
                review = {"decision": decision, "thesis": theses[decision], "event_risk_flags": flags,
                          "rubric_scores": {"setup_quality": 4 if decision == "approve" else 3, "catalyst": 3,
                                            "news_alignment": 2 if decision == "reject" else 3, "liquidity": 4,
                                            "event_risk": 2 if flags else 4, "evidence": 3},
                          "evidence": ["candidate block: pattern and levels match the strategy's definition."],
                          "current": True}
            out.append({"strategy": strat, "symbol": sym, "side": "long", "entry": entry, "stop": round(entry - risk, 2),
                        "target": round(entry + rr * risk, 2), "reward_risk": round(rr, 2),
                        "score": round(9 - i * 0.7 + rng.random() * 0.3, 3), "taken": taken, "skip_reason": reason,
                        "status": "submitted" if taken else ("vetoed" if decision in ("reject", "needs_more_info")
                                                             else ("capped" if "cap" in (reason or "") else "skipped")),
                        "notes": f"{strat} setup on {sym}", "rank_score": round(0.45 + rng.random() * 0.3, 3),
                        "review": review})
        self._signals_cache[day] = out
        return out

    def signals(self, day: date | None = None) -> dict[str, Any]:
        available = [d for d in self.days[-15:]][::-1]
        target = day or DEMO_AS_OF
        if target not in available:
            return unavailable(f"no signals saved for {target.isoformat()} (demo has the last 15 sessions)")
        return ok({"date": target.isoformat(), "signals": self._signals_for(target),
                   "available_dates": [d.isoformat() for d in available], "regime": "narrow_uptrend",
                   "review_status": {"status": "ok", "detail": "7 reviewed: 3 approve, 3 needs_more_info, 1 reject",
                                     "at": _ts(target, 10, 31)}})

    def shadow(self, by: str = "strategy") -> dict[str, Any]:
        groups = STRATEGIES if by == "strategy" else REGIMES
        rows = []
        for g in groups:
            rng = _rng(f"shadow:{by}:{g}")
            n = 0 if g in ("correction",) else rng.randint(8, 60)
            pending = rng.randint(0, 6)
            if n == 0:
                rows.append({"group": g, "n": 0, "win_rate": None, "avg_r": None, "expectancy_r": None,
                             "profit_factor": None, "pending": pending, "n_signals": pending, "n_taken": 0,
                             "total_r": 0.0})
                continue
            win = 0.35 + rng.random() * 0.25
            avg_win, avg_loss = 1.2 + rng.random() * 1.2, -(0.8 + rng.random() * 0.25)
            exp = win * avg_win + (1 - win) * avg_loss
            pf = (win * avg_win) / ((1 - win) * -avg_loss)
            rows.append({"group": g, "n": n, "win_rate": round(win, 4), "avg_r": round(exp, 4),
                         "expectancy_r": round(exp, 4), "profit_factor": round(pf, 3), "pending": pending,
                         "n_signals": n + pending + rng.randint(0, 4), "n_taken": int(n * 0.4),
                         "total_r": round(exp * n, 2)})
        return ok({"by": by, "rows": rows, "updated_at": "2026-10-06T10:31:40Z"})

    def alerts(self, hours: float = 48) -> dict[str, Any]:
        with self._lock:
            ratings = dict(self._ratings)
        out = [dict(a, rating=ratings.get(a["event_id"])) for a in self._alerts if self._hours_ago(a) <= hours]
        out.sort(key=lambda a: a["ts"], reverse=True)
        return ok(out[:MAX_ALERTS], source="demo")

    def rate(self, event_id: str, rating: str) -> dict[str, Any]:
        if not any(a["event_id"] == event_id for a in self._alerts):
            return unavailable(f"unknown event {event_id}")
        with self._lock:
            self._ratings[event_id] = rating
        return ok({"event_id": event_id, "rating": rating})

    def journal(self, day: date | None = None) -> dict[str, Any]:
        dates = [d.isoformat() for d in self.days[-3:]][::-1]
        target = (day or DEMO_AS_OF).isoformat()
        if target not in dates:
            return unavailable(f"no journal entry for {target}")
        md = (
            f"# Trade journal {target}\n\n"
            "## Market\nRegime **narrow_uptrend**: SPY above its 200-day and near its high, but under half of the "
            "universe is above its 50-day. Allowed: pullback_trend x0.5, sr_bounce x0.5, rsi2_meanrev x0.75, "
            "insider_cluster x0.5.\n\n"
            "## Candidates\n| strategy | symbol | entry | stop | target | R:R | review | outcome |\n"
            "|---|---|---|---|---|---|---|---|\n"
            "| pullback_trend | TSLX | 182.40 | 171.90 | 208.60 | 2.50 | approve | submitted |\n"
            "| sr_bounce | HRBR | 54.10 | 51.70 | 60.20 | 2.54 | approve | submitted |\n"
            "| insider_cluster | BLUE | 61.90 | 58.80 | 69.70 | 2.52 | needs_more_info | vetoed |\n\n"
            "## Positions\n- ORCA: stop raised to breakeven at +1R.\n- WREN: day 3 of 5 (rsi2 time exit).\n\n"
            "## Notes\nDemo data: every number on this page is generated, not traded.\n"
        )
        return ok({"date": target, "markdown": md, "available_dates": dates})

    def replay(self) -> dict[str, Any]:
        """Shaped like ``swing replay`` output (research.replay): fractions, rows keyed by strategy / regime."""
        days = _sessions(date(2024, 10, 1), date(2026, 9, 30))
        curve = _walk("replay", 100_000.0, days, 0.0004, 0.007)
        years = len(curve) / 252
        summary = {
            "start": days[0].isoformat(), "end": days[-1].isoformat(), "trades": 412, "win_rate": 0.47,
            "avg_r": 0.21, "avg_win_r": 1.12, "avg_loss_r": -0.6, "expectancy": 61.4, "profit_factor": 1.38,
            "total_return": round(curve[-1] / curve[0] - 1, 4),
            "cagr": round((curve[-1] / curve[0]) ** (1 / years) - 1, 4),
            "max_dd": round(-max_dd_pct(curve) / 100, 4), "sharpe": 0.94, "sortino": 1.31, "turnover": 14.2,
            "cost_drag": 0.021, "total_costs": 4210.55, "avg_hold_bars": 6.8, "avg_exposure": 0.46,
            "sessions": len(days), "n_orders": 437, "n_signals": 3120, "n_entries_skipped": 1180,
            "strategies": list(STRATEGIES), "use_router": True,
            "skip_reasons": {"below_min_reward_risk": 240, "daily_order_cap": 31, "no_free_slot": 655,
                             "symbol_busy": 254},
            "regime_days": {"healthy_uptrend": 188, "narrow_uptrend": 142, "choppy": 96, "correction": 52,
                            "high_vol_selloff": 24},
        }

        def rows(key: str, groups: tuple[str, ...]) -> list[dict[str, Any]]:
            out = []
            for g in groups:
                rng = _rng(f"replay:{key}:{g}")
                trades = 0 if g == "correction" else rng.randint(6, 90)
                if not trades:
                    continue
                win = 0.36 + rng.random() * 0.24
                avg_r = round(win * (1.1 + rng.random()) - (1 - win) * 0.85, 4)
                out.append({key: g, "trades": trades, "win_rate": round(win, 4), "avg_r": avg_r,
                            "expectancy_r": avg_r, "profit_factor": round(0.8 + rng.random() * 1.2, 3),
                            "total_pnl": round(avg_r * trades * 410, 2), "avg_hold_bars": round(3 + rng.random() * 12, 1)})
            return out

        runs = [{"id": "2024-10-01_2026-09-30", "start": "2024-10-01", "end": "2026-09-30",
                 "created_at": "2026-10-05T22:31:02Z"},
                {"id": "2024-10-01_2026-09-30-pullbacks", "start": "2024-10-01", "end": "2026-09-30",
                 "created_at": "2026-10-02T20:14:44Z"}]
        return ok({"runs": runs, "latest": {"id": runs[0]["id"], "units": "fraction", "summary": summary,
                                            "by_strategy": rows("strategy", STRATEGIES),
                                            "by_regime": rows("regime", REGIMES),
                                            "equity_curve": [{"t": d.isoformat(), "equity": round(v, 2)}
                                                             for d, v in zip(days, curve, strict=True)]}})

    def trip_killswitch(self) -> dict[str, Any]:
        with self._lock:
            self._killed = True
        return ok({"tripped": True, "path": DEMO_KILL_PATH})


def max_dd_pct(values: list[float]) -> float:
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return round(worst * 100, 2)
