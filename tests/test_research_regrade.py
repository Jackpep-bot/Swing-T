"""1R-target regrade (research.regrade): target hit, stop first, time exit; the source ledger is not touched."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.data.store import Store
from swing_engine.research.cards import WINDOWS
from swing_engine.research.regrade import (
    SUFFIX,
    build_report,
    read_original,
    read_regraded,
    regrade_store,
    regraded_strategies,
)
from swing_engine.research.shadow import REPLAY_SHADOW_TABLE, Hit, grade_signals, record_signals
from tests.fixtures.research.strategies import long_signal
from tests.fixtures.research.synthetic_panel import make_bars

FLAT = (100.0, 101.0, 99.0, 100.0)
START = "2025-01-02"
N_AFTER = 25
SHAPES = {
    "UP": (100.0, 106.0, 99.5, 105.0),  # reaches entry + 1R (105) without touching the stop (95)
    "BOTH": (100.0, 106.0, 94.0, 100.0),  # touches the 1R target and the stop in one bar
    "FLAT": FLAT,
}


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "replay_x.duckdb"
    with Store(str(path)) as store:
        for sym, bar in SHAPES.items():
            store.write_bars(make_bars(sym, [FLAT, FLAT, bar, *[FLAT] * (N_AFTER - 2)], START))
        day = pd.Timestamp(START).date()
        signals = [long_signal(sym, day, 100.0, 95.0, 130.0, strategy="scripted") for sym in SHAPES]
        signals.append(long_signal("UP", day, 100.0, 95.0, 130.0, strategy="scripted@liq50"))  # a variant: left out
        record_signals(store, signals, set(), day, "bull", source="replay", table=REPLAY_SHADOW_TABLE)
        grade_signals(store, store.snapshot_date(), table=REPLAY_SHADOW_TABLE, delist_returns={})
    return path


def test_regrade_target_hit_stop_first_and_time_exit(source, tmp_path):
    with Store(str(tmp_path / "scratch.duckdb")) as scratch:
        assert regrade_store(source, scratch) == len(SHAPES)
        assert regrade_store(source, scratch) == 0  # resumes: the chunk is already there
        assert regraded_strategies(scratch, [source]) == ["scripted"]  # the @ variant is not a base strategy
        new = read_regraded(scratch, [source], "scripted").set_index("symbol")
    assert (new["hit_20d"].to_dict(), new["result_r_20d"].to_dict()) == (
        {"UP": Hit.TARGET, "BOTH": Hit.STOP, "FLAT": Hit.TIME}, {"UP": 1.0, "BOTH": -1.0, "FLAT": 0.0})
    assert new.loc["UP", "hit_5d"] == Hit.TARGET and new.loc["FLAT", "hit_5d"] == Hit.TIME
    old = read_original([source], "scripted").set_index("symbol")
    assert old.loc["UP", "hit_20d"] == Hit.TIME  # own target (130) never reached: the source ledger is unchanged
    assert old.loc["UP", "result_r_20d"] == pytest.approx(0.0)

    text, board, summary = build_report(["scripted"], lambda _: (old.reset_index(), new.reset_index()), WINDOWS[:1])
    assert set(board["strategy"]) == {"scripted" + SUFFIX}
    assert summary["n_trials"] == 3 and summary["pooled_pass"] is False and summary["survivors"] == []
    assert "Pooled test" in text and "| scripted |" in text
