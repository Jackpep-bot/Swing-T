"""Delisted-entity keys, store repair, delisted ingest, delisting exit loss, point-in-time membership (no network)."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from swing_engine.core.config import Settings
from swing_engine.core.models import OrderIntent, Side
from swing_engine.data import delisted, repair
from swing_engine.data._common import session_ts
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store
from swing_engine.data.universe import build_universe
from swing_engine.execution.order_manager import validate_intent
from swing_engine.research.backtest import CostModel, ExitReason, run_backtest
from swing_engine.research.replay import _StoreListing
from swing_engine.research.shadow import Hit, grade_one
from tests.fixtures.research.strategies import ScriptedStrategy, long_signal
from tests.fixtures.research.synthetic_panel import make_bars, trading_dates


def _bars(symbol: str, start: str, end: str, close: float = 20.0, volume: float = 1e6) -> pd.DataFrame:
    days = trading_days(date.fromisoformat(start), date.fromisoformat(end))
    return pd.DataFrame({
        "symbol": symbol, "ts": [session_ts(d) for d in days], "open": close, "high": close * 1.01,
        "low": close * 0.99, "close": close, "volume": volume, "vwap": close, "adj_close": close,
    })


def _stitched() -> pd.DataFrame:
    """MON: Monsanto to 2018-06-06, zero-volume filler at $127.95 to 2018-12-31, a SPAC from 2021-03-01."""
    return pd.concat([
        _bars("MON", "2018-01-02", "2018-06-06", close=128.0),
        _bars("MON", "2018-06-07", "2018-12-31", close=127.95, volume=0.0),
        _bars("MON", "2021-03-01", "2021-06-30", close=10.0),
    ], ignore_index=True)


# ----------------------------------------------------------------------------------------------- key scheme


def test_entity_key_round_trip_and_live_filter():
    key = delisted.entity_key("mon", date(2018, 6, 6))
    assert key == "MON~20180606"
    assert delisted.split_key(key) == ("MON", date(2018, 6, 6))
    assert delisted.split_key("MON") == ("MON", None)
    assert delisted.is_entity_key(key) and not delisted.is_entity_key("MON")
    frame = pd.DataFrame({"symbol": ["MON", key]})
    assert delisted.drop_entity_keys(frame)["symbol"].tolist() == ["MON"]


def test_broker_layer_refuses_entity_keys():
    intent = OrderIntent(symbol="MON~20180606", side=Side.LONG, qty=10, stop=90.0, entry_limit=100.0, target=None,
                         strategy="t", client_order_id="x1", risk_dollars=100.0)
    assert "research key" in (validate_intent(intent) or "")
    assert validate_intent(intent.model_copy(update={"symbol": "MON"})) is None


# ----------------------------------------------------------------------------------------------- bar rules


def test_cut_entity_keeps_only_the_dead_company_traded_rows():
    seg = delisted.cut_entity(_stitched(), date(2018, 6, 8))
    days = pd.to_datetime(seg["ts"]).dt.date
    assert days.max() == date(2018, 6, 6) and days.min() == date(2018, 1, 2)
    assert (seg["volume"] > 0).all()
    later = delisted.cut_entity(_stitched(), date(2021, 7, 1))  # the reuse: only the segment after the gap
    assert pd.to_datetime(later["ts"]).dt.date.min() == date(2021, 3, 1)


def test_classify_delisting():
    assert delisted.classify_delisting([5.0] * 70 + [0.5]) == delisted.PERFORMANCE
    assert delisted.classify_delisting([100.0] * 70 + [40.0]) == delisted.PERFORMANCE  # bank-failure collapse
    assert delisted.classify_delisting([100.0] * 70 + [130.0]) == delisted.MERGER


# ----------------------------------------------------------------------------------------------- enumeration

AV_CSV = """symbol,name,exchange,assetType,ipoDate,delistingDate,status
MON,Monsanto Co,NYSE,Stock,2000-10-18,2018-06-07,Delisted
MON,Monsanto Co,NYSE,Stock,2000-10-18,2018-06-07,Delisted
TWTR,Twitter Inc,NYSE,Stock,2013-11-07,2022-10-28,Delisted
ABCW,ABC Corp Warrants,NASDAQ,Stock,2019-01-01,2020-01-01,Delisted
OLDX,Old X,NASDAQ,Stock,2001-01-01,2016-05-01,Delisted
SPY2,Some ETF,NYSE ARCA,ETF,2001-01-01,2019-05-01,Delisted
"""


def _massive_rows():
    return pd.DataFrame([
        {"ticker": "TWTR", "delist_date": date(2022, 10, 31), "name": "Twitter, Inc.", "cik": "1", "composite_figi": "F1",
         "type": "CS", "exchange": "XNYS", "source": "massive"},
        {"ticker": "FB", "delist_date": date(2022, 6, 9), "name": "Meta (old ticker)", "cik": "2", "composite_figi": "F2",
         "type": "CS", "exchange": "XNAS", "source": "massive"},
        {"ticker": "MON", "delist_date": date(2022, 3, 1), "name": "Some SPAC Holdings", "cik": "3",
         "composite_figi": "F3", "type": "CS", "exchange": "XNYS", "source": "massive"},
    ])


def test_parse_av_listing_keeps_common_stock_in_window():
    av = delisted.parse_av_listing(AV_CSV)
    assert sorted(set(av["ticker"])) == ["MON", "TWTR"]


def test_merge_candidates_recovers_earlier_owner_and_skips_renames():
    live = pd.DataFrame({"symbol": ["META"], "active": [True], "composite_figi": ["F2"]})
    c = delisted.merge_candidates(_massive_rows(), delisted.parse_av_listing(AV_CSV), live)
    got = {(r.ticker, r.delist_date, r.source, r.status) for r in c.itertuples()}
    assert ("MON", date(2018, 6, 7), "alphavantage", "pending") in got  # Monsanto: AV's earlier owner
    assert ("MON", date(2022, 3, 1), "massive", "pending") in got
    assert ("TWTR", date(2022, 10, 31), "massive", "pending") in got
    assert not any(t == "TWTR" and s == "alphavantage" for t, _, s, _ in got)  # same entity, AV date 3 days off
    assert ("FB", date(2022, 6, 9), "massive", "skipped_rename") in got


# ----------------------------------------------------------------------------------------------- ingest


class _FakeMassive:
    def __init__(self):
        self.calls = 0

    def _paginate(self, path, params, *, cache_salt, max_pages):
        self.calls += 1
        if params["type"] != "CS":
            return []
        return [{"ticker": "BNK", "name": "Failed Bank", "cik": "9", "composite_figi": "F9", "primary_exchange": "XNAS",
                 "delisted_utc": "2023-03-28T04:00:00Z"},
                {"ticker": "MON", "name": "Monsanto", "cik": "8", "composite_figi": "F8", "primary_exchange": "XNYS",
                 "delisted_utc": "2018-06-08T04:00:00Z"},
                {"ticker": "NEW", "name": "Recent", "delisted_utc": "2025-01-10T00:00:00Z"}]


class _FakeAlpaca:
    def __init__(self):
        self.requests = []

    def daily_bars(self, symbols, start, end):
        self.requests.append(list(symbols))
        bank = _bars("BNK", "2022-01-03", "2023-03-08", close=100.0)
        bank.loc[bank.index[-1], "close"] = 40.0  # collapse on the last day
        frames = [_stitched(), _bars("BNKQ", "2023-03-01", "2023-03-08", close=100.0), bank]
        out = pd.concat(frames, ignore_index=True)
        return out.loc[out["symbol"].isin(symbols)].reset_index(drop=True)


def test_run_delisted_ingest_writes_keys_listings_symbols_and_resumes():
    store = Store()
    alpaca = _FakeAlpaca()
    stats = delisted.run_delisted_ingest(store, alpaca, massive=_FakeMassive())
    assert stats["ok"] == 2 and stats["no_bars"] == 0
    assert set(store.symbols()) == {"BNK~20230308", "MON~20180606"}  # BNK beats the shorter BNKQ copy
    lst = store.read_table("listings").set_index("key")
    assert lst.at["BNK~20230308", "delist_reason"] == delisted.PERFORMANCE
    assert lst.at["MON~20180606", "delist_reason"] == delisted.MERGER
    assert (store.read_bars(["MON~20180606"])["volume"] > 0).all()
    sym = store.read_table("symbols").set_index("symbol")
    assert pd.Timestamp(sym.at["MON~20180606", "listed_at"]).date() == date(2018, 1, 2)
    assert pd.Timestamp(sym.at["MON~20180606", "delisted_at"]).date() == date(2018, 6, 7)
    again = delisted.run_delisted_ingest(store, alpaca)  # resumable: nothing pending, no request
    assert again["pending"] == 0 and len(alpaca.requests) == 1


# ----------------------------------------------------------------------------------------------- delisting exit


def test_delisting_returns_from_listings():
    store = Store()
    delisted.run_delisted_ingest(store, _FakeAlpaca(), massive=_FakeMassive())
    assert delisted.delisting_returns(store) == {"BNK~20230308": pytest.approx(0.7)}
    s = Settings.model_validate({"data": {"delist_return_performance": -1.0}})
    assert delisted.delisting_returns(store, s) == {"BNK~20230308": 0.0}
    assert delisted.delisting_returns(Store()) == {}


def test_backtest_applies_the_delisting_loss_to_performance_delistings():
    days = trading_dates(8, "2024-01-02")
    flat = (100.0, 101.0, 99.0, 100.0)
    dead = make_bars("AAA~20240105", [flat, flat, flat, (101.0, 103.0, 100.0, 102.0)])
    panel = pd.concat([dead, make_bars("BBB", [flat] * 8)], ignore_index=True)
    sig = long_signal("AAA~20240105", days[0].date(), 100.0, 90.0, 200.0)
    costs = CostModel(slippage_bps=0.0, sec_fee_per_million_sold=0.0, finra_taf_per_share=0.0)
    base = run_backtest(ScriptedStrategy({sig.as_of: [sig]}), panel, costs=costs).trades.iloc[0]
    hit = run_backtest(ScriptedStrategy({sig.as_of: [sig]}), panel, costs=costs,
                       delist_returns={"AAA~20240105": 0.7}).trades.iloc[0]
    assert base["exit_reason"] == hit["exit_reason"] == ExitReason.DELISTED
    assert base["exit_price"] == pytest.approx(102.0)
    assert hit["exit_price"] == pytest.approx(102.0 * 0.7)


def test_shadow_grade_applies_the_delisting_loss():
    bars = pd.DataFrame({"day": trading_days(date(2024, 1, 2), date(2024, 1, 4)), "open": 100.0, "high": 101.0,
                         "low": 99.0, "close": 100.0})
    g = grade_one("long", 90.0, None, bars, [10], delisted=True, delist_mult=0.7)
    out = g.by_horizon[10]
    assert out.hit == Hit.DELISTED.value and out.result_r == pytest.approx(-3.0)  # (70 - 100) / 10


# ----------------------------------------------------------------------------------------------- universe


def test_universe_admits_entity_keys_only_while_they_traded():
    store = Store()
    store.write_bars(pd.concat([_bars("OLD~20230505", "2022-06-01", "2023-05-05"),
                                _bars("OLD", "2024-01-02", "2024-06-28")], ignore_index=True))
    seg = store.read_bars(["OLD~20230505"])
    row = delisted.listing_row("OLD~20230505", seg, {"name": "Old Co"}, "repair")
    delisted.write_entities(store, [row], [{}])
    listing = _StoreListing(store.read_table("symbols"))
    s = Settings.model_validate({"universe": {"min_price": 1.0, "min_avg_dollar_volume": 1.0, "min_avg_volume": 1.0}})
    assert "OLD~20230505" in build_universe(listing, s, date(2023, 3, 1), store=store)
    assert build_universe(listing, s, date(2023, 6, 1), store=store) == []
    assert "OLD~20230505" not in build_universe(listing, s, date(2024, 5, 1), store=store)


# ----------------------------------------------------------------------------------------------- repair


def _contaminated_store() -> Store:
    store = Store()
    store.write_bars(pd.concat([
        _stitched(),
        _bars("SBNY", "2022-01-03", "2023-03-10", close=70.0),
        _bars("SBNY", "2023-03-13", "2023-06-30", close=70.0, volume=0.0),
        _bars("OK", "2023-01-03", "2024-12-31"),
        _bars("OK", "2024-11-01", "2024-11-29", volume=0.0),  # after the window start: left alone
        _bars("REN", "2023-01-03", "2024-10-04"),  # renamed: Alpaca history under the new ticker ...
        _bars("REN", "2025-03-03", "2025-03-31"),  # ... which the Massive window carries only after the rename
    ], ignore_index=True))
    return store


def test_repair_plan_counts_filler_and_joins_without_writing():
    store = _contaminated_store()
    before = store.count("bars")
    p = repair.plan(store)
    assert p["filler_symbols"] == 2  # MON and SBNY; OK's zero-volume rows are after 2024-10-07
    assert p["filler_rows"] == len(trading_days(date(2018, 6, 7), date(2018, 12, 31))) + len(
        trading_days(date(2023, 3, 13), date(2023, 6, 30)))
    sp = p["splits"]
    assert sp["symbol"].tolist() == ["MON"] and sp["new_symbol"].tolist() == ["MON~20180606"]
    assert sp["rows"].iloc[0] == len(trading_days(date(2018, 1, 2), date(2018, 6, 6)))
    assert sp["price_jump"].iloc[0] > 2.0  # $128 -> $10
    assert p["seam_gaps_skipped"] == 1  # REN's pause at the Alpaca/Massive seam is a rename, not a reuse
    assert store.count("bars") == before and not store.has_table("repairs")


def test_repair_apply_is_logged_and_undo_restores_the_store():
    store = _contaminated_store()
    snapshot = store.read_bars()
    res = repair.apply(store)
    assert store.read_bars(["MON"])["ts"].min() == session_ts("2021-03-01")
    assert len(store.read_bars(["MON~20180606"])) == res["split_rows"]
    assert not ((store.read_bars()["volume"] == 0) & (store.read_bars()["ts"] < session_ts("2024-10-07"))).any()
    log = store.read_table("repairs")
    assert set(log["action"]) == {"drop_filler", "split"} and (log["run_id"] == res["run_id"]).all()
    assert "MON~20180606" in set(store.read_table("listings")["key"])
    assert repair.plan(store)["split_segments"] == 0 and repair.plan(store)["filler_rows"] == 0  # idempotent
    repair.undo_repair(store, res["run_id"])
    after = store.read_bars()
    pd.testing.assert_frame_equal(after.reset_index(drop=True), snapshot.reset_index(drop=True))
    assert store.read_table("repairs")["reverted"].all()
    assert "MON~20180606" not in set(store.read_table("symbols")["symbol"])


def test_one_rejected_symbol_does_not_stop_the_chunk() -> None:
    from swing_engine.data import delisted as dl

    class Alp:
        def daily_bars(self, tickers, start, end):
            if "BAD" in tickers:
                raise RuntimeError('{"message":"invalid symbol: BAD"}')
            return pd.DataFrame({"symbol": tickers, "close": [1.0] * len(tickers)})

    out = dl._fetch_bars(Alp(), ["AAA", "BAD", "CCC"], date(2020, 1, 1))
    assert sorted(out["symbol"]) == ["AAA", "CCC"]
