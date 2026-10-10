"""Review regressions for strategies/calhoun_mean_reversion_swing.py."""
from __future__ import annotations

from swing_engine.core import registry
from swing_engine.research.replay import SIGNAL_LOOKBACK_SESSIONS
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date

NAME = "calhoun_mean_reversion_swing"


def test_replay_window_and_full_history_pick_the_same_leg():
    # A deep low 389 bars back sits inside a 400-bar max_len but outside replay's 300-session window: with it as
    # the leg start the 50% retracement fails, without it the recent 100 -> 120 leg fires. Replay and the nightly
    # (years of history) must agree, so max_len has to fit inside the replay window.
    flat = [100.5, 101.0, 100.2, 100.5, 1e6]
    rows = [flat] * 30 + [[100.5, 101.0, 50.0, 100.5, 1e6]] + [flat] * 357
    for i in range(26):  # leg: low 100 to high 120
        c = 100.5 + i * 0.76
        rows.append([c - 0.3, c + 0.5, c - 0.5, c, 1e6])
    for c in (118, 116, 114, 112):
        rows.append([c + 1, c + 1.2, c - 0.4, c, 1e6])
    rows += [[111, 111.2, 110.0, 110.4, 1e6], [110.4, 110.9, 110.2, 110.7, 1e6]]  # pullback low 110 = 50%; bounce
    p = add_features(bars_from_ohlc("AAA", rows, start="2023-01-03"))
    p["trend_state"] = 0.0
    assert len(p) - 1 - 400 <= 30 < len(p) - SIGNAL_LOOKBACK_SESSIONS  # the deep low is in 400, not in replay
    strat = registry.get("strategy", NAME)(None)
    full = strat.signals(p, last_date(p))
    replay = strat.signals(p.iloc[-SIGNAL_LOOKBACK_SESSIONS:], last_date(p))
    assert len(full) == len(replay) == 1
    assert (full[0].entry, full[0].stop, full[0].target) == (replay[0].entry, replay[0].stop, replay[0].target)
    assert full[0].features["leg_low"] == replay[0].features["leg_low"] == 100.0
