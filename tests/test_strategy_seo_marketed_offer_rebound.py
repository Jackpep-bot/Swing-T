"""seo_marketed_offer_rebound (docs/proposals/swing-methods-2026-10/batch7/seo_marketed_offer_rebound.md) on a
hand-built offering day: one clean signal and one name for each thing the card excludes."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import seo_marketed_offer_rebound as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2025-09-02", "2025-09-22")
AT = len(DAYS) - 3
SIGNAL = DAYS[AT]
# symbol -> (close path factor applied from 6 sessions before the signal to the session before it, overrides)
CASES = {"OFFER": (0.95, {}), "MILD": (0.97, {}), "MARKET": (0.95, {"mkt": 0.97}), "NOEVENT": (0.95, {"offer_event": 0.0}),
         "CHEAP": (0.95, {"price": 4.0}), "THIN": (0.95, {"med_dv_63": 1e6}),
         "SPLIT": (0.95, {"days_since_reverse_split": 30.0})}


def make_panel() -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = []
    for sym, (fall, case) in CASES.items():
        case = dict(case)
        price, mkt = case.pop("price", 20.0), case.pop("mkt", 1.0)
        close = np.full(len(DAYS), price)
        close[AT - 5:] = price * fall  # lower from 5 sessions before the signal on
        market = np.full(len(DAYS), 500.0)
        market[AT - 5:] = 500.0 * mkt
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "open": close, "high": close * 1.01, "low": close * 0.99,
                                    "close": close, "volume": 1e6, "market_close": market, "med_dv_63": 5e6,
                                    "offer_event": [float(d == SIGNAL) for d in DAYS], **case}))
    return pd.concat(frames, ignore_index=True)


def test_buys_only_the_offering_that_followed_a_drop_against_the_market():
    panel, s = make_panel(), mod.SeoMarketedOfferRebound()
    sigs = s.signals(panel, SIGNAL)
    assert [x.symbol for x in sigs] == ["OFFER"]  # MARKET fell 5% with a market down 3%: only -2% relative
    sig = sigs[0]
    assert sig.features["pre_offer_return"] == pytest.approx(-0.05) and sig.features["pre_offer_vs_spy"] == pytest.approx(-0.05)
    assert sig.stop == pytest.approx(19.0 * 0.88) and sig.target is None
    assert s.params["max_hold_days"] == 7 and s.signals(panel, DAYS[AT + 1]) == []
    loose = mod.SeoMarketedOfferRebound({"max_drop": -0.02, "max_relative_drop": -0.01, "min_close": 3.0,
                                         "min_dollar_volume": 5e5})
    assert {x.symbol for x in loose.signals(panel, SIGNAL)} == {"OFFER", "MILD", "MARKET", "CHEAP", "THIN"}  # SPLIT avoided


def test_point_in_time_short_history_and_silence_without_the_join():
    panel, s = make_panel(), mod.SeoMarketedOfferRebound()
    later = panel["ts"].dt.date > SIGNAL
    shocked = panel.assign(close=panel["close"].where(~later, 50.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, SIGNAL)]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    assert s.signals(panel.loc[panel["ts"].dt.date >= DAYS[AT - 5]], SIGNAL) == []  # 6 closes: one short
    assert s.signals(panel.drop(columns="offer_event"), SIGNAL) == []
