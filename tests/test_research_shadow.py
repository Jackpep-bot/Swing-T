"""Shadow ledger: recording, first-touch grading (stop-first, gap-through skip), horizons and the report."""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.models import Side
from swing_engine.data.store import Store
from swing_engine.research.shadow import (
    SHADOW_TABLE,
    Hit,
    grade_one,
    grade_signals,
    horizon_column,
    record_signals,
    shadow_report,
    signal_key,
)
from tests.fixtures.research.strategies import long_signal
from tests.fixtures.research.synthetic_panel import FLAG_COLUMN, make_bars, make_panel, trading_dates

ENTRY, STOP, TARGET = 100.0, 95.0, 110.0
FLAT = (100.0, 101.0, 99.0, 100.0)
START = "2024-01-02"


def _bars(ohlc: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    days = [d.date() for d in trading_dates(len(ohlc), "2024-01-03")]
    arr = np.asarray(ohlc, dtype=float)
    return pd.DataFrame({"day": days, "open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2], "close": arr[:, 3]})


# ----------------------------------------------------------------------------------------------- grade_one


def test_stop_first_when_stop_and_target_touch_in_one_bar():
    g = grade_one(Side.LONG, STOP, TARGET, _bars([FLAT, (100.0, 112.0, 94.0, 105.0), FLAT]), (5,))
    out = g.by_horizon[5]
    assert out.hit == Hit.STOP
    assert out.result_r == pytest.approx(-1.0)
    assert out.exit_price == STOP
    assert out.mfe_r == pytest.approx(0.2)  # the stop bar's high earns no credit (stop assumed first)


def test_entry_skipped_when_next_open_gaps_through_stop():
    g = grade_one(Side.LONG, STOP, TARGET, _bars([(94.0, 99.0, 93.0, 98.0), FLAT]), (5, 10))
    assert g.skip_reason == "open_through_stop"
    assert {o.hit for o in g.by_horizon.values()} == {Hit.SKIPPED}
    assert all(math.isnan(o.result_r) for o in g.by_horizon.values())


def test_entry_skipped_when_next_open_is_above_target():
    g = grade_one(Side.LONG, STOP, TARGET, _bars([(111.0, 112.0, 109.0, 111.0)]), (5,))
    assert g.by_horizon[5].hit == Hit.SKIPPED
    assert g.skip_reason == "open_through_target"


def test_later_gap_through_stop_fills_at_open():
    g = grade_one(Side.LONG, STOP, TARGET, _bars([FLAT, (90.0, 92.0, 88.0, 89.0)]), (5,))
    out = g.by_horizon[5]
    assert out.hit == Hit.STOP
    assert out.result_r == pytest.approx(-2.0)  # (90 - 100) / 5: worse than the planned 1R
    assert out.mae_r == pytest.approx(2.0)


def test_target_hit_and_time_exit_and_pending_horizons():
    tgt = grade_one(Side.LONG, STOP, TARGET, _bars([FLAT, (101.0, 111.0, 100.0, 108.0)]), (5,))
    assert tgt.by_horizon[5].hit == Hit.TARGET
    assert tgt.by_horizon[5].result_r == pytest.approx(2.0)

    drift = [(100.0 + k, 101.5 + k, 99.0 + k, 101.0 + k) for k in range(7)]
    g = grade_one(Side.LONG, STOP, TARGET, _bars(drift), (5, 10, 20))
    assert g.by_horizon[5].hit == Hit.TIME
    assert g.by_horizon[5].result_r == pytest.approx((105.0 - 100.0) / 5.0)
    assert g.by_horizon[5].bars_held == 5
    assert g.by_horizon[10].hit == Hit.PENDING
    assert g.by_horizon[20].hit == Hit.PENDING


def test_resolution_before_horizon_finalises_longer_horizons_early():
    g = grade_one(Side.LONG, STOP, TARGET, _bars([FLAT, (99.0, 100.0, 94.0, 96.0)]), (5, 10, 20))
    assert {o.hit for o in g.by_horizon.values()} == {Hit.STOP}


def test_short_side_is_mirrored():
    g = grade_one(Side.SHORT, 105.0, 90.0, _bars([FLAT, (99.0, 100.0, 89.0, 91.0)]), (5,))
    assert g.by_horizon[5].hit == Hit.TARGET
    assert g.by_horizon[5].result_r == pytest.approx(2.0)


# ----------------------------------------------------------------------------------------------- store round trip


def _store_with(ohlc: list[tuple[float, float, float, float]], symbol: str = "AAA") -> Store:
    store = Store()
    store.write_bars(make_bars(symbol, ohlc, start=START))
    return store


def test_record_then_grade_through_store_and_regrade_is_idempotent():
    store = _store_with([FLAT, FLAT, (100.0, 112.0, 94.0, 105.0), FLAT, FLAT, FLAT])
    as_of = date(2024, 1, 2)
    sig = long_signal("AAA", as_of, ENTRY, STOP, TARGET, strategy="s1")
    other = long_signal("AAA", as_of, ENTRY, 90.0, 120.0, strategy="s2")
    assert record_signals(store, [sig, other], {signal_key(sig)}, as_of, "healthy_uptrend") == 2
    rows = store.read_table(SHADOW_TABLE).set_index("strategy")
    assert bool(rows.loc["s1", "taken"]) and not bool(rows.loc["s2", "taken"])
    assert rows.loc["s1", "regime"] == "healthy_uptrend"

    assert grade_signals(store, date(2024, 1, 9), horizons=(5,)) == 2
    rows = store.read_table(SHADOW_TABLE).set_index("strategy")
    assert rows.loc["s1", "hit"] == Hit.STOP and rows.loc["s1", "result_r"] == pytest.approx(-1.0)
    assert rows.loc["s2", horizon_column("hit", 5)] == Hit.TIME  # 90 / 120 never touched in 5 sessions
    assert grade_signals(store, date(2024, 1, 9), horizons=(5,)) == 0  # nothing left to resolve

    # re-recording keeps the graded outcome
    record_signals(store, [sig], set(), as_of, "choppy")
    rows = store.read_table(SHADOW_TABLE).set_index("strategy")
    assert rows.loc["s1", "hit"] == Hit.STOP and not bool(rows.loc["s1", "taken"])


def test_grading_uses_only_bars_after_signal_and_on_or_before_as_of():
    store = _store_with([FLAT, FLAT, FLAT, (100.0, 101.0, 90.0, 92.0)])
    as_of = date(2024, 1, 2)
    record_signals(store, [long_signal("AAA", as_of, ENTRY, STOP, TARGET)], set(), as_of, None)
    grade_signals(store, date(2024, 1, 4), horizons=(5,))
    row = store.read_table(SHADOW_TABLE).iloc[0]
    assert row["hit"] == Hit.PENDING  # the stop-out on 2024-01-05 is after the grading date
    assert pd.Timestamp(row["entry_date"]).date() == date(2024, 1, 3)
    grade_signals(store, date(2024, 1, 5), horizons=(5,))
    assert store.read_table(SHADOW_TABLE).iloc[0]["hit"] == Hit.STOP


def test_taken_accepts_client_order_ids_and_symbols():
    from swing_engine.risk.sizing import make_client_order_id

    store = Store()
    d = date(2024, 1, 2)
    a = long_signal("AAA", d, ENTRY, STOP, TARGET, strategy="s1")
    b = long_signal("BBB", d, ENTRY, STOP, TARGET, strategy="s1")
    c = long_signal("CCC", d, ENTRY, STOP, TARGET, strategy="s1")
    record_signals(store, [a, b, c], {make_client_order_id(a), "BBB"}, d, None)
    taken = store.read_table(SHADOW_TABLE).set_index("symbol")["taken"].astype(bool).to_dict()
    assert taken == {"AAA": True, "BBB": True, "CCC": False}


# ----------------------------------------------------------------------------------------------- planted edge


def _flag_signals(panel: pd.DataFrame) -> dict[date, list]:
    out: dict[date, list] = {}
    for r in panel.loc[panel[FLAG_COLUMN] == 1].itertuples(index=False):
        d = r.ts.date()
        out.setdefault(d, []).append(long_signal(r.symbol, d, r.close, r.close * 0.97, r.close * 1.06, strategy="flag"))
    return out


def _shadow_run(edge: float) -> pd.DataFrame:
    panel = make_panel(n_symbols=20, n_days=300, seed=7, edge=edge)
    store = Store()
    store.write_bars(panel)
    for d, sigs in sorted(_flag_signals(panel).items()):
        record_signals(store, sigs, set(), d, "healthy_uptrend")
    grade_signals(store, panel["ts"].max().date(), horizons=(5, 10))
    return shadow_report(store, group_by=("strategy",))


def test_planted_edge_shows_positive_expectancy_and_zero_edge_does_not():
    edge = _shadow_run(0.08).iloc[0]
    noise = _shadow_run(0.0).iloc[0]
    assert edge["n"] >= 100 and noise["n"] >= 100
    assert edge["expectancy"] > 0.25
    assert edge["avg_r"] == pytest.approx(edge["expectancy"])
    assert edge["profit_factor"] > 1.3
    assert edge["win_rate"] > 0.5
    assert noise["expectancy"] < 0.1
    assert edge["expectancy"] - noise["expectancy"] > 0.3


def test_report_groups_filters_and_handles_empty_store():
    empty = shadow_report(Store())
    assert empty.empty and {"strategy", "regime", "n", "expectancy"} <= set(empty.columns)

    store = _store_with([FLAT, (100.0, 111.0, 99.0, 110.0), FLAT, FLAT, FLAT, FLAT])
    d = date(2024, 1, 2)
    record_signals(store, [long_signal("AAA", d, ENTRY, STOP, TARGET, strategy="s1")], set(), d, None)
    record_signals(store, [long_signal("AAA", d, ENTRY, 90.0, 104.0, strategy="s2")], {"s2:AAA"}, d, "choppy")
    grade_signals(store, date(2024, 1, 10), horizons=(5,))
    rep = shadow_report(store)
    assert list(rep["regime"]) == ["unknown", "choppy"] or set(rep["regime"]) == {"unknown", "choppy"}
    s1 = rep.set_index("strategy").loc["s1"]
    assert s1["n"] == 1 and s1["win_rate"] == 1.0 and s1["profit_factor"] == math.inf
    only_taken = shadow_report(store, group_by=(), taken=True)
    assert len(only_taken) == 1 and only_taken.iloc[0]["n_taken"] == 1
    assert shadow_report(store, since=date(2024, 2, 1), group_by=()).iloc[0]["n_signals"] == 0


# ----------------------------------------------------------------------------------------------- splits


def _split_store(rows: int = 14) -> tuple[Store, list[tuple[float, float, float, float]]]:
    # signal day 2024-01-02, then sessions drifting inside the 93 / 114 bracket (never touched)
    ohlc = [FLAT] + [(100.0 + 0.2 * k, 101.0 + 0.2 * k, 99.0 + 0.2 * k, 100.5 + 0.2 * k) for k in range(rows - 1)]
    return _store_with(ohlc), ohlc


def test_a_split_during_grading_keeps_final_horizons_and_regrades_in_adjusted_prices():
    store, ohlc = _split_store()
    as_of = date(2024, 1, 2)
    days = [d.date() for d in trading_dates(len(ohlc), START)]
    record_signals(store, [long_signal("AAA", as_of, ENTRY, 93.0, 114.0)], set(), as_of, None)
    grade_signals(store, days[6], horizons=(5, 10))
    first = store.read_table(SHADOW_TABLE).iloc[0]
    assert first[horizon_column("hit", 5)] == Hit.TIME and first[horizon_column("hit", 10)] == Hit.PENDING
    r5 = float(first[horizon_column("result_r", 5)])

    # a 2:1 split on session 8: repair_splits re-fetches the whole history split-adjusted (every bar halved)
    halved = [tuple(x / 2.0 for x in bar) for bar in ohlc]
    store.write_bars(make_bars("AAA", halved, start=START))
    store.write_table("splits", pd.DataFrame({"symbol": ["AAA"], "ex_date": [days[8]], "ratio": [2.0]}),
                      ["symbol", "ex_date"])
    assert grade_signals(store, days[-1], horizons=(5, 10)) == 1
    row = store.read_table(SHADOW_TABLE).iloc[0]
    assert row[horizon_column("hit", 5)] == Hit.TIME and float(row[horizon_column("result_r", 5)]) == pytest.approx(r5)
    assert row[horizon_column("hit", 10)] == Hit.TIME  # not entry_skipped: stop 93 became 46.5 like the bars
    assert pd.isna(row["skip_reason"])
    entry, close10 = ohlc[1][0], ohlc[10][3]
    assert float(row[horizon_column("result_r", 10)]) == pytest.approx((close10 - entry) / (entry - 93.0))


def test_a_final_horizon_is_never_rewritten_even_without_a_splits_table():
    store, ohlc = _split_store()
    as_of = date(2024, 1, 2)
    days = [d.date() for d in trading_dates(len(ohlc), START)]
    record_signals(store, [long_signal("AAA", as_of, ENTRY, 93.0, 114.0)], set(), as_of, None)
    grade_signals(store, days[6], horizons=(5, 10))
    r5 = float(store.read_table(SHADOW_TABLE).iloc[0][horizon_column("result_r", 5)])
    store.write_bars(make_bars("AAA", [tuple(x / 2.0 for x in bar) for bar in ohlc], start=START))
    grade_signals(store, days[-1], horizons=(5, 10))
    row = store.read_table(SHADOW_TABLE).iloc[0]
    assert row[horizon_column("hit", 5)] == Hit.TIME and float(row[horizon_column("result_r", 5)]) == pytest.approx(r5)


# ----------------------------------------------------------------------------------------------- delisted


def test_a_symbol_that_stops_trading_resolves_as_delisted_at_its_last_close():
    store = _store_with([FLAT, FLAT, FLAT, (100.0, 102.0, 99.0, 101.0)], symbol="GONE")  # 3 sessions after the signal
    store.write_bars(make_bars("LIVE", [FLAT] * 15, start=START))  # the market keeps trading
    as_of = date(2024, 1, 2)
    record_signals(store, [long_signal("GONE", as_of, ENTRY, STOP, TARGET)], set(), as_of, None)
    last_live = trading_dates(15, START)[-1].date()
    assert grade_signals(store, last_live, horizons=(5, 10)) == 1
    row = store.read_table(SHADOW_TABLE).iloc[0]
    for h in (5, 10):
        assert row[horizon_column("hit", h)] == Hit.DELISTED
        assert float(row[horizon_column("result_r", h)]) == pytest.approx((101.0 - 100.0) / (100.0 - STOP))
    rep = shadow_report(store, group_by=(), horizon=5).iloc[0]
    assert rep["n"] == 1 and rep["n_pending"] == 0  # counted, not left out as a survivor-only statistic


def test_a_stale_store_does_not_mark_names_delisted():
    store = _store_with([FLAT, FLAT, FLAT, FLAT], symbol="AAA")  # the whole store ends here
    as_of = date(2024, 1, 2)
    record_signals(store, [long_signal("AAA", as_of, ENTRY, STOP, TARGET)], set(), as_of, None)
    grade_signals(store, date(2024, 2, 1), horizons=(5,))  # weeks later, but no newer bar anywhere
    assert store.read_table(SHADOW_TABLE).iloc[0][horizon_column("hit", 5)] == Hit.PENDING
