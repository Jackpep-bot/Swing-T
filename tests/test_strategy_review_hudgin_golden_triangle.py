"""Review regressions for strategies/hudgin_golden_triangle.py."""
from swing_engine.core import registry
from swing_engine.strategies import hudgin_golden_triangle as mod
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows


def _mild_accel_rows() -> list[list[float]]:
    """Golden-triangle shape whose pivot sits only 5-10% above the 50 SMA."""
    rows = trend_rows(230, start=50.0, step=0.3)
    top = rows[-1][3]
    rows += [[c + 1, c + 1.2, c - 0.3, c, 1e6] for c in (top - 6, top - 11, top - 14)]
    base = top - 13.5
    rows += [[base, base + 0.4, base - 0.4, base, 1e6] for _ in range(6)]
    c = top - 10
    return [*rows, [base, c + 0.2, base - 0.1, c, 3e6]]


def test_accel_min_is_the_cards_ten_percent():
    p = add_features(bars_from_ohlc("AAA", _mild_accel_rows(), start="2024-01-02"))
    cls = registry.get("strategy", mod.NAME)
    assert cls(None).params["accel_min"] == 0.10
    assert cls(None).signals(p, last_date(p)) == []  # card rejects a pivot < 10% above sma_50
    assert len(cls({"accel_min": 0.05}).signals(p, last_date(p))) == 1  # the panel otherwise fires


def test_docstring_states_drop_low_rule_exit_needs_entry_features():
    doc = " ".join(mod.__doc__.split())
    assert "close below the entry signal's drop low" in doc and "is not modelled" not in doc
