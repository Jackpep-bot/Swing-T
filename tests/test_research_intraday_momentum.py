"""research.intraday_momentum: band and VWAP arithmetic, fills, the 14-session history, costs, and no look-ahead."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from swing_engine.data import intraday as I
from swing_engine.data.store import Store
from swing_engine.research import intraday_momentum as M
from swing_engine.research.trials import trial_count

NY = "America/New_York"


def session(day: str, path, symbol: str = "SPY", n: int = 390) -> pd.DataFrame:
    """One regular session of flat-range minute bars; ``path(k)`` = the price of the minute that opens at ``k``
    (its open; its close is ``path(k + 1)``)."""
    ts = pd.date_range(f"{day} 09:30", periods=n, freq="1min", tz=NY).tz_convert("UTC")
    o = np.array([path(k) for k in range(n)], dtype=float)
    c = np.array([path(k + 1) for k in range(n)], dtype=float)
    df = pd.DataFrame({"symbol": symbol, "ts": ts, "open": o, "high": np.maximum(o, c), "low": np.minimum(o, c),
                       "close": c, "volume": 100.0, "vwap": (o + c) / 2, "trade_count": 1})
    df["session"] = I.label_sessions(df["symbol"], df["ts"])
    return df


def one_day(path, day: str = "2024-03-05", **kw) -> M.Day:
    return M.split_days(session(day, path, **kw))[0]


def test_split_days_counts_minutes_from_the_open_and_knows_early_closes():
    days = M.split_days(pd.concat([session("2024-07-02", lambda k: 100.0), session("2024-07-03", lambda k: 100.0, n=210)]))
    assert [d.length for d in days] == [390, 210]  # 2024-07-03 closed at 13:00
    assert days[0].m[0] == 0 and days[0].m[-1] == 389
    assert list(days[1].checks()) == [30, 60, 90, 120, 150, 180]


def test_noise_area_goes_long_above_band_and_vwap_and_exits_when_price_falls_back():
    # up 1% by 10:00 and holding, back to the open from 12:00 on
    d = one_day(lambda k: 100.0 + min(k, 30) / 30 if k < 150 else 100.0)
    sigma = {k: 0.004 for k in d.checks()}
    trades = M.noise_area_trades(d, 100.0, sigma)
    assert len(trades) == 1
    t = trades[0]
    assert (t["side"], t["entry_min"], t["exit_min"]) == (1, 30, 150)  # checks at 10:00 ... 12:00
    assert t["entry"] == 101.0 and t["exit"] == 100.0 and math.isclose(t["gross"], 100.0 / 101.0 - 1.0)
    # the gap adjustment: a previous close above the open lifts the upper band out of reach
    assert M.noise_area_trades(d, 100.8, sigma) == []
    # not enough history: no band, no trade
    assert M.noise_area_trades(d, 100.0, {}) == []


def test_noise_area_flips_and_closes_at_the_session_close():
    d = one_day(lambda k: 100.0 if k == 0 else 101.0 if k < 200 else 99.0)
    trades = M.noise_area_trades(d, 100.0, {k: 0.004 for k in d.checks()})
    assert [(t["side"], t["entry_min"], t["exit_min"]) for t in trades] == [(1, 30, 210), (-1, 210, 390)]
    assert trades[0]["exit"] == trades[1]["entry"] == 99.0


def test_decisions_do_not_read_bars_after_the_check():
    base = lambda k: 100.0 + min(k, 30) / 30  # noqa: E731
    later = lambda k: base(k) if k <= 60 else 90.0  # noqa: E731  (different from 10:31 on)
    sigma = {k: 0.004 for k in range(30, 361, 30)}
    a, b = (M.noise_area_trades(one_day(p), 100.0, sigma)[0] for p in (base, later))
    assert (a["entry_min"], a["entry"]) == (b["entry_min"], b["entry"]) == (30, 101.0)
    d = one_day(base)
    assert d.price_at(30) == base(30) and d.open_at(30) == base(30) and math.isnan(d.price_at(0))
    assert math.isclose(d.vwap_at(1), (100.0 + base(1) + base(1)) / 3)  # only the 09:30 bar has ended by 09:31


def test_sigma_needs_fourteen_earlier_sessions():
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-03-04", periods=17)]
    bars = pd.concat([session(day, lambda k: 100.0 + min(k, 30) / 30) for day in days])
    trades = [t for t in M.simulate("SPY", M.split_days(bars)) if t["card"] == M.CARD_NOISE]
    # day 1 has no previous close; days 2-15 build the history (move 1%, so the band is never beaten afterwards)
    assert trades == []
    wild = pd.concat([session(day, lambda k: 100.0) for day in days[:-1]] + [session(days[-1], lambda k: 100.0 + min(k, 30) / 30)])
    trades = [t for t in M.simulate("SPY", M.split_days(wild)) if t["card"] == M.CARD_NOISE]
    assert [str(t["day"]) for t in trades] == [days[-1]] and trades[0]["side"] == 1


def test_first_half_hour_trades_the_last_half_hour_in_the_morning_direction():
    d = one_day(lambda k: 99.0 if k < 360 else 99.0 - (k - 360) / 30)  # down at 10:00, down 1 more into the close
    t = M.first_half_hour_trades(d, 100.0)[0]
    assert (t["side"], t["entry_min"], t["entry"], t["exit"]) == (-1, 360, 99.0, 98.0)
    assert math.isclose(t["gross"], 1.0 / 99.0)
    assert M.first_half_hour_trades(d, 99.0) == []  # r1 = 0
    assert M.first_half_hour_trades(one_day(lambda k: 99.0, day="2024-07-03", n=210), 100.0) == []  # early close


def test_grade_charges_two_sides_and_averages_the_three_symbols(tmp_path):
    day = pd.Timestamp("2024-03-05").date()
    trades = pd.DataFrame([{"card": M.CARD_FHH, "symbol": "SPY", "day": day, "side": 1, "entry_min": 360,
                            "entry": 100.0, "exit_min": 390, "exit": 100.1, "gross": 0.001}], columns=M.TRADE_COLUMNS)
    by_symbol = M.daily_returns(trades, M.CARD_FHH, "B", 1.0)
    assert math.isclose(by_symbol.loc[day, "SPY"], 0.001 - 0.0002) and by_symbol.loc[day, "QQQ"] == 0.0
    assert len(by_symbol) == len(M.trading_days(*M.WINDOWS["B"]))
    res = M.grade(trades, 10, pd.Series(dtype=float))
    assert res[M.CARD_FHH]["verdict"] == "FAIL" and res[M.CARD_FHH]["stats"]["B"]["trades"] == 1


def test_run_writes_results_and_logs_the_trials_once(tmp_path):
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2024-03-04", periods=17)]
    store_path = tmp_path / "intraday.duckdb"
    with Store(str(store_path)) as store:
        for sym in M.SYMBOLS:
            bars = pd.concat([session(day, lambda k: 100.0 + (k > 300), symbol=sym) for day in days])
            store.write_table(I.TABLE, bars, ["symbol", "ts"])
    trials = tmp_path / "trials.jsonl"
    for _ in range(2):
        res = M.run(store_path, tmp_path / "out.md", tmp_path / "data", trials)
    assert trial_count(None, trials) == M.N_GROUP_TRIALS
    assert set(res) == set(M.CARDS) and "## Verdict" in (tmp_path / "out.md").read_text()
    assert (tmp_path / "data" / "trades.parquet").exists()
