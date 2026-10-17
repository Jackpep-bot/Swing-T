"""research.attribution: market component arithmetic, exit mix, concentration and buckets on synthetic frames."""
from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest

from swing_engine.research import attribution as at
from swing_engine.research.cards import Window

WINDOW = Window(date(2024, 1, 1), date(2024, 12, 31), "w")
DAYS = pd.bdate_range("2024-01-02", periods=60)
# SPY opens at 100 + i and closes 1 higher on session i
SPY = pd.DataFrame({"open": [100.0 + i for i in range(60)], "close": [101.0 + i for i in range(60)]}, index=DAYS.date)


def ledger(n: int = 30, r: float = 0.5) -> pd.DataFrame:
    rows = {"strategy": "s", "symbol": "X", "as_of": DAYS[:n].date, "entry": 100.0, "stop": 95.0,
            "entry_price": 100.0, "entry_date": DAYS[1:n + 1].date, "cost_bps": 10.0, "dollar_volume": 5e7}
    for h in (5, 10, 20):
        rows |= {f"hit_{h}d": "time_exit", f"result_r_{h}d": r, f"mfe_r_{h}d": 1.0, f"mae_r_{h}d": 0.4,
                 f"exit_date_{h}d": DAYS[h:n + h].date}
    return pd.DataFrame(rows)


def test_market_component_is_spy_return_in_r_units():
    f = ledger(1)
    # entry session 1 opens at 101; the 5d exit (session 5) closes at 106; R multiple = 100 / (100 - 95) = 20
    assert at.market_r(f, SPY, 5).iloc[0] == pytest.approx((106 / 101 - 1) * 20)
    # without entry_date the span starts on the session after as_of: same answer
    assert at.market_r(f.drop(columns="entry_date"), SPY, 5).iloc[0] == pytest.approx((106 / 101 - 1) * 20)
    f["exit_date_5d"] = date(2030, 1, 2)  # no SPY bar
    assert math.isnan(at.market_r(f, SPY, 5).iloc[0])


def test_market_table_subtracts_market_and_cost():
    daily, signals = at.chunk_stats(ledger(), SPY)
    assert len(signals) == 30 and set(daily["horizon"]) == {5, 10, 20}
    row = at.market_table(daily, [WINDOW]).set_index("horizon").loc[5]
    mkt = at.market_r(ledger(), SPY, 5).mean()
    cost = 2 * 10 / 1e4 * 20  # round trip of 10 bp a side at 20 R per unit return
    assert row["n"] == 30 and row["gross_r"] == pytest.approx(0.5) and row["mkt_r"] == pytest.approx(mkt)
    assert row["adj_gross_r"] == pytest.approx(0.5 - mkt)
    assert row["adj_net_r"] == pytest.approx(0.5 - mkt - cost)
    assert row["blocks"] < at.MIN_BLOCKS and math.isnan(row["t"])
    assert at.market_table(daily, [Window(date(2020, 1, 1), date(2020, 12, 31), "x")]).empty


def test_exit_mix_and_top_share():
    s = pd.DataFrame({"hit": ["stop_hit"] * 5 + ["target_hit"] * 2 + ["time_exit"] * 2 + ["delisted"],
                      "mfe": [1.0] * 10, "mae": [0.5] * 10})
    mix = at.exit_mix(s)
    assert (mix["stop"], mix["target"], mix["time"], mix["mfe"], mix["mae"]) == (0.5, 0.2, 0.2, 1.0, 0.5)
    r = pd.Series([10.0] + [1.0] * 19)  # 20 signals: the top 5% is the single +10 of a total of 29
    assert at.top_share(r) == pytest.approx(10 / 29)
    assert math.isnan(at.top_share(pd.Series([1.0, -2.0])))


def test_buckets_and_mix_table():
    s = pd.DataFrame({"strategy": "s", "as_of": pd.Timestamp("2024-03-01"), "hit": "time_exit", "mfe": 1.0,
                      "mae": 0.5, "r": [1.0, 3.0, 2.0, -1.0],
                      "entry": [5.0, 9.99, 10.0, 80.0], "dollar_volume": [1e6, 2e7, 9e7, float("nan")]})
    price = at.bucket_means(s, "entry", at.PRICE_EDGES, at.PRICE_LABELS)
    assert price == {"<$10": 2.0, "$10-50": 2.0, ">$50": -1.0}
    liq = at.bucket_means(s, "dollar_volume", at.LIQUIDITY_EDGES, at.LIQUIDITY_LABELS)
    assert liq["<$20M"] == 1.0 and liq["$20-100M"] == 2.5 and math.isnan(liq[">$100M"])
    row = at.mix_table(s, [WINDOW]).iloc[0]
    assert row["n20"] == 4 and row["time"] == 1.0 and row["<$10"] == 2.0 and row["top_share"] == pytest.approx(3 / 5)


def test_render_reports_market_explained_strategies():
    daily, signals = at.chunk_stats(pd.concat([ledger(40, 0.1), ledger(40, 10.0).assign(strategy="edge")]), SPY)
    market, mix = at.market_table(daily, [WINDOW]), at.mix_table(signals, [WINDOW])
    text = at.render(market, mix, signals, [WINDOW])
    assert "2 of 2 strategies have a positive gross R" in text and "1 of those 2 have a non-positive" in text
    assert text.index("| edge |") < text.index("| s |")
