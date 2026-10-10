"""Review fix: bollinger_band_mean_reversion enters at the next open; a buy stop at the band (below the close) was
marketable and a next open near the signal close fell outside the 1% entry limit, so the fill was skipped."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from swing_engine.core.models import EntryType
from swing_engine.features.extra import ensure_extra
from swing_engine.research.backtest import entry_fill
from swing_engine.risk.sizing import entry_limit_for
from tests.fixtures.strategies.panel import add_features, bars_from_closes, last_date


def test_next_open_at_signal_close_fills_inside_entry_limit():
    s = registry.get("strategy", "bollinger_band_mean_reversion")(None)
    panel = ensure_extra(add_features(bars_from_closes("AAA", [*[100.0, 100.5] * 130, 97.0, 100.0])), s.extra_features)
    (sig,) = s.signals(panel, last_date(panel))
    assert float(panel["bb_lower_20"].iloc[-1]) * 1.01 < 100.0  # the band-priced stop would have been skipped
    assert sig.entry_type == EntryType.OPEN and sig.entry == pytest.approx(100.0)
    price, skip = entry_fill(sig, 100.0, 100.5, 99.5)  # next session opens at the signal close
    assert skip is None and price <= entry_limit_for(sig)
