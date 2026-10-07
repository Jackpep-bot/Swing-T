"""Sizing math: Schwab example, caps, reward:risk gate, vol target, sector room, id stability."""
from __future__ import annotations

from datetime import date

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import Position, Side, Signal
from swing_engine.risk.sizing import (
    CLIENT_ORDER_ID_MAX_LEN,
    effective_equity,
    make_client_order_id,
    size_signal,
    size_signal_detail,
)

AS_OF = date(2026, 10, 6)
EQUITY = 50_000.0


def make_signal(**overrides) -> Signal:
    base = {"strategy": "sr_bounce", "symbol": "AAPL", "as_of": AS_OF, "entry": 10.0, "stop": 8.0, "target": 16.0}
    base.update(overrides)
    return Signal(**base)


def test_schwab_example_sized_on_the_worst_case_fill():
    # Schwab: $50,000 x 1% = $500 / $2 = 250 shares at the reference entry. The engine's marketable limit is $10.10,
    # so it sizes on $2.10 of risk per share: floor(500 / 2.10) = 238 shares, risk at the limit $499.80 <= $500.
    intent = size_signal(make_signal(), EQUITY, RiskConfig(risk_per_trade_pct=1.0), open_positions=[])
    assert intent is not None
    assert intent.qty == 238
    assert intent.risk_dollars == 499.8 and intent.risk_dollars <= EQUITY * 0.01
    assert intent.stop == 8.0 and intent.target == 16.0
    assert intent.entry_limit == 10.1  # reference entry + 1% marketable buffer
    assert intent.side == Side.LONG and intent.strategy == "sr_bounce"
    assert intent.client_order_id == "swing-sr_bounce-AAPL-20261006-long"


def test_max_position_pct_caps_qty_at_the_limit_price():
    sig = make_signal(entry=100.0, stop=99.0, target=103.0)  # $1 risk/share -> 500 shares uncapped
    intent = size_signal(sig, EQUITY, RiskConfig(max_position_pct=10.0))
    assert intent is not None
    assert intent.qty == 49  # floor(5000 / 101)
    assert intent.qty * intent.entry_limit <= EQUITY * 0.10


def test_rejects_low_reward_risk():
    intent, reason = size_signal_detail(make_signal(target=11.0), EQUITY, RiskConfig(min_reward_risk=2.0))
    assert intent is None
    assert "reward_risk 0.50" in reason


def test_uses_explicit_reward_risk_when_no_target():
    intent = size_signal(make_signal(target=None, reward_risk=2.5), EQUITY, RiskConfig())
    assert intent is not None and intent.target is None and intent.qty == 238


def test_rejects_when_reward_risk_cannot_be_verified():
    intent, reason = size_signal_detail(make_signal(target=None), EQUITY, RiskConfig())
    assert intent is None and "unknown" in reason


def test_vol_target_caps_size():
    # 50k * 20% / 8 slots = $1250 vol budget; / 0.6 vol = $2083 notional; / 10.1 = 206 shares (< 238 fixed-fractional)
    sig = make_signal(features={"vol_21d": 0.6})
    intent = size_signal(sig, EQUITY, RiskConfig(vol_target_annual_pct=20.0, max_open_positions=8))
    assert intent is not None and intent.qty == 206
    assert "vol=206" in intent.notes


def test_vol_target_skipped_when_feature_missing():
    intent = size_signal(make_signal(), EQUITY, RiskConfig(vol_target_annual_pct=20.0))
    assert intent is not None and intent.qty == 238


def test_open_symbol_and_full_book_are_rejected():
    open_same = [Position(symbol="AAPL", qty=10, avg_entry=9.0, side=Side.LONG)]
    assert size_signal(make_signal(), EQUITY, RiskConfig(), open_same) is None
    full = [Position(symbol=f"S{i}", qty=1, avg_entry=1.0, side=Side.LONG) for i in range(8)]
    assert size_signal(make_signal(), EQUITY, RiskConfig(max_open_positions=8), full) is None


def test_sector_cap_reduces_qty_to_remaining_room():
    # 30% of 50k = $15,000 sector budget; MSFT already $14,000 -> $1,000 room / 10.1 = 99 shares
    positions = [Position(symbol="MSFT", qty=140, avg_entry=100.0, side=Side.LONG)]
    sector_map = {"AAPL": "tech", "MSFT": "tech"}
    intent = size_signal(make_signal(), EQUITY, RiskConfig(max_sector_pct=30.0), positions, sector_map)
    assert intent is not None and intent.qty == 99


def test_sector_cap_full_rejects():
    positions = [Position(symbol="MSFT", qty=150, avg_entry=100.0, side=Side.LONG)]
    intent, reason = size_signal_detail(
        make_signal(), EQUITY, RiskConfig(), positions, {"AAPL": "tech", "MSFT": "tech"}
    )
    assert intent is None and "sector" in reason


def test_bad_geometry_rejected_and_short_side_sized():
    assert size_signal(make_signal(stop=12.0), EQUITY, RiskConfig()) is None
    short = make_signal(side=Side.SHORT, entry=10.0, stop=11.0, target=7.0)
    intent = size_signal(short, EQUITY, RiskConfig())
    assert intent is not None
    assert intent.side == Side.SHORT and intent.entry_limit == 9.9 and intent.qty == 454  # 500 / (11.0 - 9.9)


def test_size_rounding_to_zero_is_rejected():
    intent, reason = size_signal_detail(make_signal(entry=10_000.0, stop=9_000.0, target=13_000.0), EQUITY, RiskConfig())
    assert intent is None and "zero" in reason


def test_client_order_id_is_stable_and_bounded():
    assert make_client_order_id(make_signal()) == make_client_order_id(make_signal())
    long_a = make_client_order_id(make_signal(strategy="x" * 80))
    long_b = make_client_order_id(make_signal(strategy="y" * 80))
    assert len(long_a) <= CLIENT_ORDER_ID_MAX_LEN and long_a != long_b
    assert " " not in make_client_order_id(make_signal(strategy="weird name/with:chars"))


def test_effective_equity_override():
    assert effective_equity(EQUITY, RiskConfig(account_equity_override=25_000)) == 25_000
    assert effective_equity(EQUITY, RiskConfig()) == EQUITY


def test_per_strategy_min_reward_risk_override_admits_rule_exit_strategies():
    """RSI-2 style signals have small fixed targets; a per-strategy floor of 0 admits them, the default rejects."""
    from swing_engine.core.config import RiskConfig
    from swing_engine.core.models import Signal
    from swing_engine.risk.sizing import size_signal_detail, strategy_min_reward_risk

    sig = Signal(strategy="rsi2_meanrev", symbol="ABC", as_of=__import__("datetime").date(2026, 9, 30),
                 entry=100.0, stop=96.0, target=101.0)
    cfg = RiskConfig(min_reward_risk=2.0, max_position_pct=100.0)
    rejected, reason = size_signal_detail(sig, 50_000, cfg)
    assert rejected is None and "below min 2.0" in reason
    floor = strategy_min_reward_risk({"rsi2_meanrev": {"enabled": True, "min_reward_risk": 0.0}}, "rsi2_meanrev")
    assert floor == 0.0
    intent, reason = size_signal_detail(sig, 50_000, cfg, min_reward_risk=floor)
    assert intent is not None and intent.qty == 100  # 50,000 x 1% = 500 / (101 limit - 96 stop = 5 risk at the limit)
    assert strategy_min_reward_risk({"other": {}}, "rsi2_meanrev") is None



def test_fill_at_the_limit_never_exceeds_the_risk_budget():
    """Finding: sizing on the reference entry let a fill at the 1% marketable limit risk up to ~2x the budget."""
    for entry, stop in ((100.0, 98.0), (100.0, 99.5), (10.0, 9.9), (50.0, 45.0)):
        sig = make_signal(entry=entry, stop=stop, target=entry + 3 * (entry - stop))
        intent = size_signal(sig, EQUITY, RiskConfig(risk_per_trade_pct=1.0, max_position_pct=100.0))
        assert intent is not None
        assert intent.qty * (intent.entry_limit - stop) <= EQUITY * 0.01 + 1e-9
