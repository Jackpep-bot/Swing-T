"""research.intraday_chains: every refusal step, the walker (stop before target, gap fill, time exits), the daily
cap and one-position rule, cost arithmetic, and no look-ahead (plans survive cutting the data at the entry bar)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from swing_engine.data import intraday as I
from swing_engine.data.store import Store
from swing_engine.research import intraday_chains as C
from swing_engine.research.trials import trial_count

NY = "America/New_York"
BTC = "BTC/USD"
T0 = pd.Timestamp("2024-03-05 00:00", tz="UTC")
M15, M1 = pd.Timedelta(minutes=15), pd.Timedelta(minutes=1)
NAN = float("nan")


def minutes(symbol: str, start: pd.Timestamp, n: int, slope: float = 1.0, base: float = 1000.0) -> pd.DataFrame:
    """One bar per minute; price = base + slope x minutes since ``start``, range +-0.5 around it."""
    ts = pd.date_range(start, periods=n, freq="1min").tz_convert("UTC")
    px = base + slope * np.arange(n, dtype=float)
    df = pd.DataFrame({"symbol": symbol, "ts": ts, "open": px, "high": px + 0.5, "low": px - 0.5, "close": px,
                       "volume": 10.0, "vwap": px, "trade_count": 1})
    df["session"] = I.label_sessions(df["symbol"], df["ts"])
    return df


def ev(kind: str, i: int, eid: str, direction: str | None = None, label: str | None = None, level: float = NAN,
       high: float = NAN, low: float = NAN, zl: float = NAN, zh: float = NAN, strength: float = NAN,
       ref: str | None = None, start: pd.Timestamp = T0, **meta) -> dict:
    return {"event_id": eid, "kind": kind, "ts_event": start + M15 * i, "direction": direction, "label": label,
            "level": level, "high": high, "low": low, "zone_low": zl, "zone_high": zh, "strength": strength,
            "ref_event_id": ref, "meta": meta}


def rej(minute: int, eid: str, zone: str, direction: str = "bull") -> dict:
    return {"event_id": eid, "kind": "rejection", "ts_event": T0 + M1 * minute, "direction": direction,
            "ref_event_id": zone}


def ctx(symbol: str, bars1: pd.DataFrame, events: list[dict], rejs: list[dict]) -> C.Ctx:
    frame = pd.DataFrame(events).sort_values("ts_event", kind="stable").reset_index(drop=True)
    rj = pd.DataFrame(rejs, columns=["event_id", "kind", "ts_event", "direction", "ref_event_id"])
    return C.Ctx(symbol, I.resample(bars1, "15m"), frame, I.resample(bars1, "2m"), rj.sort_values("ts_event"), bars1)


# Rising BTC tape, price = 1000 + minute. Long chain: sweep bar 2, shift + order block bar 4, mitigation bar 6
# (closes at minute 105), rejection in the 2m bar 106 (an earlier one at 100 closes before the mitigation and must
# be skipped), entry at the open of minute 108 = 1108, stop 1100 - 1 = 1099 (R = 9), buy-side pool at 1120.
BASE = {
    "p1": ev("pool_formed", 0, "p1", label="PDL", level=1000.0, side="SSL"),
    "p2": ev("pool_formed", 0, "p2", label="EQH", level=1120.0, side="BSL"),
    "s1": ev("sweep", 2, "s1", "bull", "closed_back", level=1000.0, high=1101.0, low=1100.0, ref="p1", pool_ids=["p1"]),
    "m1": ev("mss", 4, "m1", "bull", level=1050.0, strength=1.8, ref="s1", structure_break_id="b1"),
    "z1": ev("ob_confirmed", 4, "z1", "bull", zl=1040.0, zh=1045.0, ref="b1"),
    "t1": ev("ob_mitigated", 6, "t1", "bull", ref="z1"),
}
REJS = [rej(100, "r0", "z1"), rej(106, "r1", "z1")]


def scenario(drop: tuple[str, ...] = (), extra: tuple[dict, ...] = (), rejs: list[dict] | None = None,
             **override: dict) -> C.Ctx:
    events = [v for k, v in {**BASE, **override}.items() if k not in drop] + list(extra)
    return ctx(BTC, minutes(BTC, T0, 600), events, REJS if rejs is None else rejs)


def one(cx: C.Ctx, card: str) -> dict:
    (out,) = C.chain_outcomes(cx, card)
    return out


def test_order_block_chain_plan_and_trade() -> None:
    cx = scenario()
    plan = one(cx, C.CARD_OB)
    assert plan["refusal"] is None and plan["trigger_id"] == "r1"  # r0 closed before the mitigation bar did
    assert plan["entry_ts"] == T0 + M1 * 108 and plan["entry"] == 1108.0
    assert plan["stop"] == 1099.0 and plan["target"] == 1120.0 and plan["target_kind"] == "pool EQH"
    assert (plan["sweep_id"], plan["mss_id"], plan["zone_id"], plan["target_pool_id"]) == ("s1", "m1", "z1", "p2")
    assert "sweep PDL" in plan["lineage"] and "OB zone 1040.00–1045.00" in plan["lineage"]
    assert plan["lineage"].endswith("entry 1108.00 sl 1099.00 tp 1120.00 (pool EQH)")
    (trade,), refusals = C.simulate(cx, C.CARD_OB)
    assert not refusals and trade["exit_reason"] == "target" and trade["exit_ts"] == T0 + M1 * 120
    assert trade["gross_r"] == pytest.approx(12 / 9)
    cost_r = (25 + 5) / 1e4 * (1108 + 1120) / 9  # BTC: 30 bp a side on entry and exit prices, over the stop distance
    assert trade["cost_r"] == pytest.approx(cost_r) and trade["net_r"] == pytest.approx(12 / 9 - cost_r)
    assert trade["mfe_r"] == pytest.approx(12 / 9) and trade["mae_r"] == pytest.approx(0.5 / 9)


def test_target_falls_back_to_2r_when_the_pool_is_too_near_or_already_pierced() -> None:
    near = scenario(p2=ev("pool_formed", 0, "p2", label="EQH", level=1112.0, side="BSL"))  # under 1R away
    assert one(near, C.CARD_OB)["target"] == 1108.0 + 2 * 9 and one(near, C.CARD_OB)["target_kind"] == "2R"
    pierced = scenario(extra=(ev("pool_swept", 5, "x", ref="p2"),))
    assert one(pierced, C.CARD_OB)["target_kind"] == "2R"


@pytest.mark.parametrize(("step", "kwargs"), [
    ("no_shift", {"drop": ("m1",)}),
    ("shift_failed", {"extra": (ev("mss_failed", 5, "f1", "bull", ref="m1"),)}),
    ("no_zone", {"drop": ("z1",)}),
    ("no_retrace", {"drop": ("t1",)}),
    ("no_retrace", {"t1": ev("ob_mitigated", 4 + C.RETRACE_MAX_BARS + 1, "t1", "bull", ref="z1")}),
    ("zone_dead", {"extra": (ev("ob_invalidated", 6, "d1", "bull", ref="z1"),)}),
    ("no_trigger", {"rejs": [REJS[0]]}),
    ("stop_too_tight", {"s1": ev("sweep", 2, "s1", "bull", "closed_back", high=1109.0, low=1108.6, ref="p1",
                                 pool_ids=["p1"])}),  # stop 1107.6: 0.4 from entry, under 0.05% of 1108
])
def test_each_chain_refusal_step(step: str, kwargs: dict) -> None:
    cx = scenario(**kwargs)
    assert one(cx, C.CARD_OB)["refusal"] == step
    trades, refusals = C.simulate(cx, C.CARD_OB)
    assert not trades and [r["refusal"] for r in refusals] == [step]


def test_failure_or_dead_zone_after_entry_does_not_refuse() -> None:
    late = (ev("mss_failed", 8, "f1", "bull", ref="m1"), ev("ob_consumed", 8, "d1", "bull", ref="z1"))
    assert one(scenario(extra=late), C.CARD_OB)["refusal"] is None
    at_entry = (ev("ob_expired", 7, "d1", "bull", ref="z1"),)  # bar 7 closes at minute 120, after the 108 entry
    assert one(scenario(extra=at_entry), C.CARD_OB)["refusal"] is None


def test_fvg_card_zone_retrace_and_refusals() -> None:
    gap = ev("fvg_formed", 5, "g1", "bull", zl=1085.0, zh=1095.0)  # bar 6 (low 1089.5) trades back into it
    rejs = [rej(106, "r1", "g1")]
    plan = one(scenario(extra=(gap,), rejs=rejs), C.CARD_FVG)
    assert plan["refusal"] is None and plan["zone_id"] == "g1" and plan["retrace_ts"] == T0 + M15 * 6
    assert plan["entry_ts"] == T0 + M1 * 108 and "FVG zone" in plan["lineage"]
    older = ev("fvg_formed", 3, "g0", "bull", zl=1085.0, zh=1095.0)
    assert one(scenario(extra=(older, gap), rejs=rejs), C.CARD_FVG)["zone_id"] == "g1"  # the most recent one
    too_new = ev("fvg_formed", 6, "g1", "bull", zl=1085.0, zh=1095.0)  # two bars after the shift
    assert one(scenario(extra=(too_new,), rejs=rejs), C.CARD_FVG)["refusal"] == "no_zone"
    before_sweep = ev("fvg_formed", 1, "g1", "bull", zl=1085.0, zh=1095.0)
    assert one(scenario(extra=(before_sweep,), rejs=rejs), C.CARD_FVG)["refusal"] == "no_zone"
    far = ev("fvg_formed", 5, "g1", "bull", zl=1040.0, zh=1045.0)  # the rising tape never comes back to it
    assert one(scenario(extra=(far,), rejs=rejs), C.CARD_FVG)["refusal"] == "no_retrace"
    inverted = ev("fvg_inverted", 6, "v1", "bear", ref="g1")
    assert one(scenario(extra=(gap, inverted), rejs=rejs), C.CARD_FVG)["refusal"] == "zone_dead"
    assert one(scenario(extra=(gap,), rejs=[]), C.CARD_FVG)["refusal"] == "no_trigger"


def control_sweep(i: int, risk: float, eid: str, start: pd.Timestamp = T0, base: float = 1000.0,
                  slope: float = 1.0, tick: float = 1.0) -> dict:
    """A PDL sweep on bar ``i`` whose stop sits ``risk`` under the next bar's open."""
    low = base + slope * 15 * (i + 1) - risk + tick
    return ev("sweep", i, eid, "bull", "closed_back", high=low + 1, low=low, ref="p1", start=start, pool_ids=["p1"])


def test_control_ignores_non_pd_pools_and_enforces_the_daily_cap() -> None:
    pool = ev("pool_formed", 0, "p1", label="PDL", level=1000.0, side="SSL")
    eq = ev("pool_formed", 0, "q1", label="EQL", level=1000.0, side="SSL")
    other = ev("sweep", 1, "e1", "bull", "closed_back", high=1001.0, low=1000.0, ref="q1", pool_ids=["q1"])
    sweeps = [control_sweep(i, 3.0, f"s{i}") for i in (2, 4, 6, 8, 10, 12)]
    cx = ctx(BTC, minutes(BTC, T0, 600), [pool, eq, other, *sweeps], [])
    trades, refusals = C.simulate(cx, C.CARD_CONTROL)
    assert [t["sweep_id"] for t in trades] == ["s2", "s4", "s6", "s8", "s10"]  # e1 is not a chain start
    assert all(t["exit_reason"] == "target" and t["gross_r"] == pytest.approx(2.0) for t in trades)
    assert trades[0]["entry_ts"] == T0 + M15 * 3 and trades[0]["target_kind"] == "2R"
    assert [(r["sweep_id"], r["refusal"]) for r in refusals] == [("s12", "daily_cap")]
    assert len(C.chain_outcomes(cx, C.CARD_OB)) == 7  # cards 1 and 2 start a chain on every closed-back sweep


def test_one_position_per_symbol() -> None:
    pool = ev("pool_formed", 0, "p1", label="PDL", level=1000.0, side="SSL")
    cx = ctx(BTC, minutes(BTC, T0, 600), [pool, control_sweep(2, 51.0, "a"), control_sweep(3, 3.0, "b"),
                                           control_sweep(12, 3.0, "c")], [])
    trades, refusals = C.simulate(cx, C.CARD_CONTROL)
    assert [t["sweep_id"] for t in trades] == ["a", "c"]  # a exits at +102 (minute 147), before c enters at 195
    assert [(r["sweep_id"], r["refusal"]) for r in refusals] == [("b", "position_open")]


def test_etf_no_entry_after_1530_and_flat_at_1555() -> None:
    day = pd.Timestamp("2024-03-05 09:30", tz=NY)
    bars = minutes("SPY", day, 390, slope=0.0, base=100.0)  # flat tape: neither stop nor target is reached
    pool = ev("pool_formed", 0, "p1", label="PDL", level=99.0, side="SSL", start=day)
    sweeps = [control_sweep(i, 1.01, f"s{i}", start=day, base=100.0, slope=0.0, tick=0.01) for i in (22, 23, 24, 25)]
    cx = ctx("SPY", bars, [pool, *sweeps], [])
    trades, refusals = C.simulate(cx, C.CARD_CONTROL)
    (trade,) = trades  # sweep in the 15:00 bar, entry 15:15
    assert trade["entry_ts"] == pd.Timestamp("2024-03-05 15:15", tz=NY)
    assert trade["exit_reason"] == "time" and trade["exit_ts"] == pd.Timestamp("2024-03-05 15:55", tz=NY)
    assert trade["exit"] == 100.0 and trade["gross_r"] == 0.0
    assert trade["net_r"] == pytest.approx(-1.0 / 1e4 * (100 + 100) / 1.01)  # SPY: 1 bp a side
    # 15:30 itself is allowed (refused only because the first trade is still open); 15:45 and "next day" are late
    assert sorted((r["sweep_id"], r["refusal"]) for r in refusals) == [
        ("s23", "position_open"), ("s24", "too_late"), ("s25", "too_late")]


def test_early_close_shifts_the_clock_rules() -> None:
    day = pd.Timestamp("2024-11-29 09:30", tz=NY)  # 13:00 close
    bars = minutes("SPY", day, 210, slope=0.0, base=100.0)
    pool = ev("pool_formed", 0, "p1", label="PDH", level=101.0, side="BSL", start=day)
    sweeps = [ev("sweep", i, f"s{i}", "bear", "closed_back", high=101.0, low=100.0, ref="p1", start=day,
                 pool_ids=["p1"]) for i in (11, 12)]  # entries 12:30 (allowed) and 12:45
    trades, refusals = C.simulate(ctx("SPY", bars, [pool, *sweeps], []), C.CARD_CONTROL)
    assert [(t["direction"], t["exit_reason"], t["exit_ts"]) for t in trades] == [
        ("short", "time", pd.Timestamp("2024-11-29 12:55", tz=NY))]
    assert trades[0]["stop"] == pytest.approx(101.01) and trades[0]["target"] == pytest.approx(100 - 2 * 1.01)
    assert [r["refusal"] for r in refusals] == ["too_late"]


def bars(rows: list[tuple[float, float, float, float]]) -> tuple[np.ndarray, ...]:
    t = np.arange(len(rows), dtype=np.int64) * C.MINUTE
    return (t, *np.array(rows, dtype=float).T)


def test_walk_stop_fills_before_target_in_the_same_minute() -> None:
    tape = bars([(100, 100.5, 99.5, 100), (100, 103, 98, 102), (102, 104, 101, 103)])
    res = C.walk(*tape, 0, 100.0, 99.0, 102.0, 1, 10 * C.MINUTE)
    assert (res["exit_reason"], res["exit"], res["gross_r"]) == ("stop", 99.0, -1.0)
    assert res["free_ns"] == 2 * C.MINUTE and res["mfe_r"] == 0.5 and res["mae_r"] == 1.0
    up = C.walk(*bars([(100, 100.5, 99.5, 100), (100, 103, 99.5, 102)]), 0, 100.0, 99.0, 102.0, 1, 10 * C.MINUTE)
    assert (up["exit_reason"], up["exit"], up["gross_r"]) == ("target", 102.0, 2.0)
    short = C.walk(*tape, 0, 100.0, 101.0, 98.0, -1, 10 * C.MINUTE)  # minute 1 holds both: the stop fills
    assert (short["exit_reason"], short["exit"], short["gross_r"]) == ("stop", 101.0, -1.0)


def test_walk_gap_through_the_stop_fills_at_the_open() -> None:
    tape = bars([(100, 100.5, 99.5, 100), (97, 103, 96, 102)])
    res = C.walk(*tape, 0, 100.0, 99.0, 102.0, 1, 10 * C.MINUTE, cost=0.001)
    assert (res["exit_reason"], res["exit"], res["gross_r"]) == ("stop_gap", 97.0, -3.0)
    assert res["cost_r"] == pytest.approx(0.001 * (100 + 97)) and res["net_r"] == pytest.approx(-3.0 - 0.197)
    assert res["free_ns"] == C.MINUTE
    short = C.walk(*bars([(100, 100.5, 99.5, 100), (104, 105, 97, 98)]), 0, 100.0, 101.0, 98.0, -1, 10 * C.MINUTE)
    assert (short["exit_reason"], short["exit"], short["gross_r"]) == ("stop_gap", 104.0, -4.0)


def test_walk_time_exit_at_the_open_and_at_the_last_close() -> None:
    tape = bars([(100, 100.5, 99.5, 100), (100.2, 100.6, 99.8, 100.4), (100.3, 110, 90, 100)])
    res = C.walk(*tape, 0, 100.0, 99.0, 102.0, 1, 2 * C.MINUTE)
    assert (res["exit_reason"], res["exit"]) == ("time", 100.3) and res["mfe_r"] == pytest.approx(0.6)
    held = C.walk(*tape, 0, 100.0, 99.0, 102.0, 1, 2 * C.MINUTE, hard_ns=2 * C.MINUTE)  # no bar before the close
    assert (held["exit_reason"], held["exit"]) == ("time_last_close", 100.4)


def random_minutes(symbol: str, start: pd.Timestamp, n: int, seed: int, base: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = base * np.exp(np.cumsum(rng.standard_t(3, n) * 0.0006))
    open_ = np.concatenate([[base], close[:-1]])
    spread = np.abs(rng.normal(0, 0.0004, (2, n))) * base
    df = pd.DataFrame({"symbol": symbol, "ts": pd.date_range(start, periods=n, freq="1min").tz_convert("UTC"),
                       "open": open_, "high": np.maximum(open_, close) + spread[0],
                       "low": np.minimum(open_, close) - spread[1], "close": close, "volume": 10.0, "vwap": close,
                       "trade_count": 1})
    df["session"] = I.label_sessions(df["symbol"], df["ts"])
    return df


def test_no_look_ahead_plans_survive_truncation_at_the_entry_bar() -> None:
    tape = random_minutes(BTC, T0, 12 * 1440, seed=7, base=50_000.0)
    cx = C.build_ctx(BTC, tape)
    checked = 0
    for card, tf in ((C.CARD_OB, pd.Timedelta(minutes=2)), (C.CARD_FVG, pd.Timedelta(minutes=2)), (C.CARD_CONTROL, M15)):
        plans = [p for p in C.chain_outcomes(cx, card) if p["refusal"] is None]
        assert plans, card
        for p in plans:
            used = {k: p[k] for k in ("sweep_ts", "mss_ts", "zone_ts", "retrace_ts") if k in p}
            assert all(p["entry_ts"] >= ts + M15 for ts in used.values()), (card, p["lineage"])  # 15m bars closed
            if "trigger_ts" in p:
                assert p["entry_ts"] >= p["trigger_ts"] + tf
        for p in plans[:: max(1, len(plans) // 4)]:
            cut = C.build_ctx(BTC, tape.loc[tape["ts"] < p["entry_ts"] + tf])  # nothing after the entry bar
            again = next(q for q in C.chain_outcomes(cut, card) if q["sweep_id"] == p["sweep_id"])
            assert again == p, (card, p["lineage"])
            checked += 1
    assert checked >= 6


def test_run_writes_parquet_report_and_logs_the_six_trials_once(tmp_path) -> None:
    spy = pd.concat([random_minutes("SPY", pd.Timestamp(f"2024-03-{d:02d} 09:30", tz=NY), 390, seed=d, base=500.0)
                     for d in (4, 5, 6, 7, 8)])
    btc = random_minutes(BTC, pd.Timestamp("2024-03-04", tz="UTC"), 5 * 1440, seed=3, base=50_000.0)
    path = tmp_path / "intraday.duckdb"
    with Store(str(path)) as store:
        store.write_table(I.TABLE, pd.concat([spy, btc]), I.KEYS, schema=I.SCHEMA)
    trials = tmp_path / "trials.jsonl"
    kwargs = {"out": tmp_path / "results.md", "data_dir": tmp_path / "out", "trials_path": trials,
              "symbols": ("SPY", BTC)}
    res = C.run(path, **kwargs)
    assert set(res) == set(C.CARDS) and all(r["verdict"] == "FAIL" for r in res.values())  # under 200 trades
    text = (tmp_path / "results.md").read_text()
    assert text.index("## Verdict") < text.index("## Pooled") and "**Nothing passes.**" in text
    assert "n_trials = 6 (0 logged before this group + 6)" in text
    trades = pd.read_parquet(tmp_path / "out" / "trades.parquet")
    refusals = pd.read_parquet(tmp_path / "out" / "refusals.parquet")
    assert len(trades) and trades["lineage"].notna().all() and set(trades["window"]) == {"B"}
    assert set(refusals["refusal"]) <= set(C.REFUSAL_STEPS) and len(refusals)
    assert trial_count(None, trials) == 6
    C.run(path, **kwargs)
    assert trial_count(None, trials) == 6  # a rerun does not log again, and the haircut count does not move
    assert "n_trials = 6 (0 logged before this group + 6)" in (tmp_path / "results.md").read_text()


def test_grade_pass_rule() -> None:
    days = pd.date_range("2016-01-04", "2026-10-09", freq="B").date
    rng = np.random.default_rng(0)
    rows = [{"card": card, "symbol": sym, "day": d, "window": C.window_of(d), "net_r": edge + rng.normal(0, 1),
             "gross_r": 0.1, "mfe_r": 1.0, "mae_r": 0.5}
            for card, edge in ((C.CARD_OB, 0.5), (C.CARD_FVG, -0.1), (C.CARD_CONTROL, 0.0))
            for sym in ("SPY", "QQQ", "IWM") for d in days[::5]]
    res = C.grade(pd.DataFrame(rows), 3000, C.DEFAULT_SYMBOLS)
    assert res[C.CARD_OB]["verdict"] == "PASS" and res[C.CARD_OB]["beats_control"]
    assert res[C.CARD_FVG]["verdict"] == "FAIL" and not res[C.CARD_FVG]["beats_control"]
    assert res[C.CARD_OB]["stats"]["A"]["haircut_sharpe"] < res[C.CARD_OB]["stats"]["A"]["sharpe"]
    two = pd.DataFrame([r for r in rows if r["symbol"] != "IWM"])  # positive on only 2 of 5 symbols in window B
    assert C.grade(two, 3000, C.DEFAULT_SYMBOLS)[C.CARD_OB]["rules"] == [True, True, True, False]
    assert math.isnan(C.edge_stats(two.iloc[0:0], 8.0, 10)["net_r"])
