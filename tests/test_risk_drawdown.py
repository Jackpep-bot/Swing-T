"""Monthly loss stop (latched, persisted), drawdown-scaled sizing equity and book vol scaling."""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Side
from swing_engine.risk.limits import LimitState
from swing_engine.risk.sizing import book_vol_scale, drawdown_scaled_equity, sizing_equity


def _intent() -> OrderIntent:
    return OrderIntent(symbol="AAA", side=Side.LONG, qty=1, entry_limit=10.0, stop=9.0, target=None, strategy="s",
                       client_order_id="c", risk_dollars=1.0)


def _acct(equity: float, day: date) -> dict:
    return {"equity": equity, "as_of": day}


def test_monthly_stop_off_by_default():
    state = LimitState(RiskConfig(max_daily_loss_pct=50))
    state.check(_intent(), _acct(100_000, date(2026, 10, 1)))
    ok, _ = state.check(_intent(), _acct(93_000, date(2026, 10, 2)))
    assert ok


def test_monthly_stop_latches_for_the_month_and_persists(tmp_path):
    path = tmp_path / "limits.json"
    cfg = RiskConfig(max_monthly_loss_pct=6.0, max_daily_loss_pct=50, max_drawdown_pct=50)
    state = LimitState(cfg, state_path=path)
    assert state.check(_intent(), _acct(100_000, date(2026, 10, 1)))[0]
    ok, reason = state.check(_intent(), _acct(93_900, date(2026, 10, 2)))
    assert not ok and "monthly loss stop" in reason
    # recovery inside the month does not unblock, and a fresh process reads the latch from the state file
    assert json.loads(path.read_text())["month_stopped"] is True
    fresh = LimitState(cfg, state_path=path)
    ok, reason = fresh.check(_intent(), _acct(99_000, date(2026, 10, 20)))
    assert not ok and "monthly loss stop" in reason
    # a new month resets the baseline
    ok, _ = fresh.check(_intent(), _acct(99_000, date(2026, 11, 2)))
    assert ok and fresh.month == "2026-11" and fresh.month_start_equity == 99_000


def test_drawdown_scaled_equity_turtle_rule():
    assert drawdown_scaled_equity(90_000, 100_000, 2.0) == pytest.approx(72_000)  # 10% dd -> 20% smaller account
    assert drawdown_scaled_equity(90_000, 100_000, None) == 90_000
    assert drawdown_scaled_equity(110_000, 100_000, 2.0) == 110_000  # above the stale peak: no scaling
    assert drawdown_scaled_equity(40_000, 100_000, 2.0) == 0.0


def test_book_vol_scale():
    rng = np.random.default_rng(0)
    rets = rng.normal(0, 0.02, 300)  # ~32% annual
    cfg = RiskConfig(book_vol_target_annual_pct=12.0)
    realized = np.std(rets[-126:], ddof=1) * np.sqrt(252)
    assert book_vol_scale(rets, cfg) == pytest.approx(0.12 / realized)
    assert book_vol_scale(rets, RiskConfig()) == 1.0  # off
    assert book_vol_scale(rets[:50], cfg) == 1.0  # not enough history
    assert book_vol_scale(rets * 0.01, cfg) == 1.0  # quiet book: capped at max_scale 1.0 (never levers)
    assert book_vol_scale(rets * 0.01, cfg.model_copy(update={"book_vol_max_scale": 2.0})) == 2.0


def test_sizing_equity_identity_when_off():
    assert sizing_equity(90_000, RiskConfig(), peak_equity=100_000, book_returns=np.ones(200)) == 90_000
