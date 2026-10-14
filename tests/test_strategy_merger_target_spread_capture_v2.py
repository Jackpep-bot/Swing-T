"""merger_target_spread_capture_v2 (docs/proposals/swing-methods-2026-10/batch8/merger_target_spread_capture_v2.md)
on hand-built price paths: a pinned target, an acquirer with no premium, a target still moving, and a late pin."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import merger_target_spread_capture_v2 as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2025-01-02", "2025-09-30")
K = len(DAYS)
S = K - 40  # the candidate filing's session
A = S - 30  # its anchor (the agreement 8-K)


def path(kind: str) -> np.ndarray:
    c = np.full(K, 40.0)
    if kind == "acquirer":
        return c  # no jump: never reaches the premium
    c[A:] = 50.0  # +25% on the announcement
    if kind == "noisy":
        c[A:] = 50.0 * (1.0 + 0.03 * (np.arange(K - A) % 2))  # +-3% a day: never pinned
    if kind == "late":
        c[A:S + 5] = 50.0 * (1.0 + 0.03 * (np.arange(S + 5 - A) % 2))  # pins from S + 5 on
    return c


def make_panel() -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = []
    for sym in ("PINNED", "acquirer", "noisy", "late"):
        c = path(sym if sym != "PINNED" else "pinned")
        days = np.where((np.arange(K) >= S) & (np.arange(K) <= S + 20), np.arange(K) - S, np.nan)
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "open": c, "high": c, "low": c, "close": c, "volume": 1e6,
                                    "mcap_pit": 1e9, "med_dv_63": 1e7, "deal_v2_days": days, "deal_v2_anchor": float(S - A)}))
    return pd.concat(frames, ignore_index=True)


def fired(panel: pd.DataFrame, s=None) -> dict[str, str]:
    s = s or mod.MergerTargetSpreadCaptureV2()
    return {x.symbol: str(day) for day in DAYS[S:S + 22] for x in s.signals(panel, day)}


def test_signals_once_on_the_first_pinned_premium_session():
    panel = make_panel()
    c = path("late")
    first = next(i for i in range(S, S + 21) if np.std(c[i - 9:i + 1] / c[i - 10:i] - 1.0, ddof=1) <= 0.01)
    assert S + 5 < first < S + 15  # the last swing has to leave most of the 10-return window first
    assert fired(panel) == {"PINNED": str(DAYS[S]), "late": str(DAYS[first])}
    sig = mod.MergerTargetSpreadCaptureV2().signals(panel, DAYS[S])[0]
    assert sig.features["premium"] == pytest.approx(1.25) and sig.stop == pytest.approx(50.0 * 0.85)
    assert sig.target is None and mod.MergerTargetSpreadCaptureV2().params["max_hold_days"] == 180


def test_thresholds_bind_and_silence_without_the_join():
    panel = make_panel()
    assert "PINNED" not in fired(panel, mod.MergerTargetSpreadCaptureV2({"min_premium": 1.30}))
    assert "noisy" in fired(panel, mod.MergerTargetSpreadCaptureV2({"max_pin_std": 0.05}))
    small = panel.assign(mcap_pit=np.where(panel["symbol"] == "PINNED", 2e8, 1e9))
    assert "PINNED" not in fired(small)
    later = panel["ts"].dt.date > DAYS[S]
    shocked = panel.assign(close=panel["close"].where(~later, 1.0))
    s = mod.MergerTargetSpreadCaptureV2()
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, DAYS[S])]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    for col in ("deal_v2_days", "deal_v2_anchor", "mcap_pit"):
        assert s.signals(panel.drop(columns=col), DAYS[S]) == []
