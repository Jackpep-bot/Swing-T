"""The pre-registered batch-2 group (docs/preregistration/2026-10-10-batch2.md): fomc_cycle_even_weeks,
large_cap_net_repurchasers, volatility_managed_spy. Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.config import ROOT, load_settings
from swing_engine.core.models import PositionContext
from swing_engine.data.calendar import trading_days
from swing_engine.risk.sizing import ENTRY_LIMIT_BUFFER_PCT, size_signal_detail, strategy_min_reward_risk
from swing_engine.strategies import fomc_cycle_even_weeks as fomc
from tests.features_gbm import NY_TZ

FOMC, REPO, VOL = "fomc_cycle_even_weeks", "large_cap_net_repurchasers", "volatility_managed_spy"


def strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


def bars(symbol: str, days: list[date], close: np.ndarray) -> pd.DataFrame:
    prev = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"symbol": symbol, "ts": pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(NY_TZ), "open": prev,
                         "high": np.maximum(prev, close) * 1.001, "low": np.minimum(prev, close) * 0.999,
                         "close": close, "volume": 1e6})


def held(weight: float | None = None) -> PositionContext:
    return PositionContext(entry_price=100.0, stop=80.0, bars_held=3, best_price=101.0,
                           entry_features={} if weight is None else {"weight": weight}, as_of=None)


# ----------------------------------------------------------------------------------------------- FOMC cycle
def test_fomc_table_is_the_scheduled_calendar():
    assert len(fomc.FOMC_DAY0) == 96 and list(fomc.FOMC_DAY0) == sorted(fomc.FOMC_DAY0)
    assert all(d.weekday() in (2, 3) for d in fomc.FOMC_DAY0)  # Wednesday, or Thursday after an election / holiday
    sessions = set(trading_days("2016-01-01", "2027-12-31"))
    assert all(d in sessions for d in fomc.FOMC_DAY0)
    assert date(2020, 3, 18) in fomc.FOMC_DAY0  # scheduled, later cancelled: what was known in advance
    assert date(2020, 3, 3) not in fomc.FOMC_DAY0 and date(2019, 10, 4) not in fomc.FOMC_DAY0  # unscheduled


def test_fomc_even_weeks_count_sessions_and_defer_to_the_next_meeting():
    days = trading_days("2025-01-02", "2025-04-30")
    i0 = days.index(date(2025, 1, 29))
    assert days.index(date(2025, 3, 19)) - i0 == 34  # the next day 0
    even = fomc.even_week_sessions()
    got = {k for k in range(-6, 34) if days[i0 + k] in even}
    assert days[i0 - 7] in even  # day 19 of the December cycle (week 4)
    # weeks 0, 2, 4 as published; of week 6 (29..33) only day 33 = day -1 of the next meeting: days 28..32 are the
    # next meeting's week -1 (k_next -6..-2)
    assert got == {-1, 0, 1, 2, 3, *range(9, 14), *range(19, 24), 33}
    assert date(2025, 2, 17) not in even  # Presidents' Day: not a session, and not counted


def test_fomc_signal_the_close_before_an_even_week_and_exit_at_its_last_close():
    days = trading_days("2024-11-01", "2025-02-28")
    panel = pd.concat([bars("SPY", days, np.linspace(580.0, 600.0, len(days))),
                       bars("AAA", days, np.linspace(50.0, 60.0, len(days)))], ignore_index=True)
    s = strat(FOMC)
    (sig,) = s.signals(panel, date(2025, 1, 27))  # Jan 28 is day -1 of the Jan 29 meeting
    close = float(panel.loc[(panel["symbol"] == "SPY") & (panel["ts"].dt.date == date(2025, 1, 27)), "close"].iloc[0])
    assert sig.symbol == "SPY" and sig.target is None and sig.entry == pytest.approx(close)
    assert sig.stop == pytest.approx(0.85 * close)
    assert s.signals(panel, date(2025, 1, 24)) == []  # the next session (Jan 27, day -2) is an odd-week session
    assert s.signals(panel, date(2025, 1, 28)) == []  # already inside the even week
    assert s.signals(panel.loc[panel["symbol"] != "SPY"], date(2025, 1, 27)) == []
    row = lambda d: panel.loc[(panel["symbol"] == "SPY") & (panel["ts"].dt.date == d)].iloc[0]  # noqa: E731
    assert s.should_exit(row(date(2025, 2, 3)), 5) is True  # day 3: the next session is day 4
    assert s.should_exit(row(date(2025, 1, 30)), 3) is False
    assert s.engine_trail is False


# ----------------------------------------------------------------------------------------------- vol-managed SPY
def vol_panel(swing_before: float, swing_after: float = 0.0, last_day: str = "2025-02-14") -> tuple[pd.DataFrame, list]:
    """SPY alternating +/- `swing_before` a day up to the January month end, +/- `swing_after` afterwards."""
    days = trading_days("2024-10-01", last_day)
    end = days.index(date(2025, 1, 31))
    sign = np.where(np.arange(len(days)) % 2 == 0, 1.0, -1.0)
    step = np.where(np.arange(len(days)) <= end, swing_before, swing_after) * sign
    return bars("SPY", days, 600.0 * np.exp(np.cumsum(step))), days


def test_vol_managed_weight_comes_from_the_last_month_end():
    s = strat(VOL)
    c = s.params["target_variance"]
    assert c == pytest.approx(0.16**2 / 12)
    calm, days = vol_panel(0.005, 0.03)  # RV = 22 x 0.005^2 = 0.00055 < c: capped at 1; turbulent after month end
    for as_of in (date(2025, 1, 31), date(2025, 2, 14)):  # the target holds until the next month end
        (sig,) = s.signals(calm, as_of)
        assert sig.features["weight"] == 1.0 and sig.features["rvar_22"] == pytest.approx(22 * 0.005**2)
        assert sig.stop == pytest.approx(sig.entry * (1.01 - 0.20)) and sig.target is None
    mid, _ = vol_panel(0.015)  # RV = 0.00495: w = c / RV = 0.431
    (sig,) = s.signals(mid, days[-1])
    w = c / (22 * 0.015**2)
    assert sig.features["weight"] == pytest.approx(w) and sig.stop == pytest.approx(sig.entry * (1.01 - 0.20 / w))
    (sig,) = s.signals(vol_panel(0.03)[0], days[-1])  # w = 0.108: held as the smallest expressible weight
    assert sig.features["weight"] == 0.20 and 0 < sig.stop < 0.02 * sig.entry
    assert s.signals(vol_panel(0.06)[0], days[-1]) == []  # w = 0.027 < 0.10: cash
    assert s.signals(calm.assign(symbol="AAA"), days[-1]) == []  # SPY only
    assert s.signals(calm, date(2024, 10, 30)) == []  # no month end with 22 returns behind it yet


def test_vol_managed_stop_makes_the_sizer_buy_the_target_weight():
    s = strat(VOL)
    book = load_settings.__wrapped__(Path(ROOT) / "config" / "prereg_b2_spy.yaml")
    assert s.params["book_risk_pct"] == book.risk.risk_per_trade_pct
    assert s.params["limit_buffer_pct"] == ENTRY_LIMIT_BUFFER_PCT
    assert book.universe.static_symbols == ["SPY"] and book.risk.max_open_positions == 1
    equity = 100_000.0
    for swing in (0.005, 0.012, 0.015, 0.02, 0.03):
        panel, days = vol_panel(swing)
        (sig,) = s.signals(panel, days[-1])
        intent, why = size_signal_detail(sig, equity, book.risk, [], None, 0.0)
        assert intent is not None, why
        assert intent.qty * sig.entry / equity == pytest.approx(sig.features["weight"], abs=0.012)  # whole shares
        assert intent.qty * sig.entry <= equity
    fomc_sig = strat(FOMC).signals(*_fomc_panel())[0]
    intent, _ = size_signal_detail(fomc_sig, equity, book.risk, [], None, 0.0)
    assert 0.99 < intent.qty * fomc_sig.entry / equity <= 1.0  # the position cap binds, not the 15% stop


def _fomc_panel() -> tuple[pd.DataFrame, date]:
    days = trading_days("2024-11-01", "2025-02-28")
    return bars("SPY", days, np.linspace(580.0, 600.0, len(days))), date(2025, 1, 27)


def test_vol_managed_rebalances_only_outside_the_band_at_month_end():
    s = strat(VOL)
    c = s.params["target_variance"]
    row = lambda w, flag=1.0: pd.Series({"month_end": flag, "rvar_22": c / w})  # noqa: E731
    assert s.should_exit(row(0.85), 21, held(1.0)) is True
    assert s.should_exit(row(0.95), 21, held(1.0)) is False  # inside the 10-point band
    assert s.should_exit(row(0.90), 21, held(1.0)) is True  # the band edge trades
    assert s.should_exit(row(0.50), 21, held(0.45)) is False
    assert s.should_exit(row(0.50, 0.0), 10, held(1.0)) is False  # not a month end
    assert s.should_exit(row(0.05), 21, held(0.20)) is True  # target is cash
    assert s.should_exit(row(0.50), 21, held()) is False and s.should_exit(row(0.50), 21) is False  # weight unknown (live)


# ----------------------------------------------------------------------------------------------- repurchasers
def repo_panel() -> tuple[pd.DataFrame, list]:
    """20 names on 30 sessions ending at a month end; the join / extras columns are given: S00 has the lowest
    net issuance (rank 0.05), S19 the highest (1.00)."""
    days = trading_days("2025-09-01", "2025-10-31")[-30:]
    frames = []
    for i in range(20):
        f = bars(f"S{i:02d}", days, np.full(len(days), 50.0 + i))
        frames.append(f.assign(big_net_issuance=-0.10 + 0.01 * i, big_net_issuance_rank=(i + 1) / 20.0, atr_63=1.0,
                               month_end=[0.0] * (len(days) - 1) + [1.0]))
    return pd.concat(frames, ignore_index=True), days


def test_repurchasers_buy_the_bottom_decile_at_month_end_only():
    s = strat(REPO)
    panel, days = repo_panel()
    sigs = sorted(s.signals(panel, days[-1]), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == ["S00", "S01"]  # rank 0.05 and 0.10 of 20
    assert sigs[0].stop == pytest.approx(50.0 - 3.0) and sigs[0].target is None
    assert sigs[0].features["big_net_issuance"] == pytest.approx(-0.10)
    assert s.signals(panel, days[-2]) == []  # not the month's last session
    no_rank = panel.assign(big_net_issuance_rank=np.nan)
    assert s.signals(no_rank, days[-1]) == []  # a panel without the share join: silent
    assert s.engine_trail is False


def test_repurchasers_sell_outside_the_hold_zone():
    s = strat(REPO)
    row = lambda rank, flag=1.0: pd.Series({"month_end": flag, "big_net_issuance_rank": rank})  # noqa: E731
    assert s.should_exit(row(0.25), 21) is True
    assert s.should_exit(row(0.20), 21) is False and s.should_exit(row(0.15), 21) is False
    assert s.should_exit(row(np.nan), 21) is True  # left the 500 largest or lost its share counts
    assert s.should_exit(row(0.90, 0.0), 5) is False  # only on a rebalance session


# ----------------------------------------------------------------------------------------------- settings
def test_batch2_registered_disabled_and_books_fixed():
    settings = load_settings()
    for name in (FOMC, REPO, VOL):
        assert settings.strategies[name].get("enabled") is False
        assert strategy_min_reward_risk(settings.strategies, name) == 0.0
    book = load_settings.__wrapped__(Path(ROOT) / "config" / "prereg_b2.yaml")
    assert (book.risk.max_position_pct, book.risk.max_open_positions, book.risk.risk_per_trade_pct) == (2.0, 50, 0.5)
    assert book.execution.max_new_orders_per_day == 50 and book.data.store_path == "data/live/replay_p3.duckdb"
    assert book.universe.static_symbols == []
