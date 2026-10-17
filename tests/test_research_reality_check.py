"""research.reality_check: block matrix, White RC / Hansen SPA / step-down p-values, PBO on synthetic matrices."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing_engine.research import reality_check as rc
from swing_engine.research.cards import WINDOWS

N_BOOT = 400


def noise(seed: int, n: int = 240, k: int = 20) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0, 1.0, size=(n, k))


def test_bootstrap_counts_resample_n_rows_and_are_seedable():
    a = rc.stationary_bootstrap_counts(50, 30, 4, np.random.default_rng(1))
    b = rc.stationary_bootstrap_counts(50, 30, 4, np.random.default_rng(1))
    assert a.shape == (30, 50) and (a.sum(axis=1) == 50).all() and (a == b).all()


def test_pure_noise_is_not_rejected():
    res = [rc.reality_check(noise(s), n_boot=N_BOOT, seed=1000 + s) for s in range(20)]  # not the data's seed
    for key in ("rc_p", "spa_p"):
        p = np.array([r[key] for r in res])
        assert 0.3 < p.mean() < 0.7  # roughly uniform under the null
        assert (p < 0.05).sum() <= 3
    assert min(r["table"]["p_adj"].min() for r in res[:5]) > 0.01
    pbo = np.mean([r["pbo"] for r in res])
    assert 0.35 < pbo < 0.65


def test_one_real_edge_among_noise_is_found():
    m = pd.DataFrame(noise(7), columns=[f"n{j}" for j in range(20)])
    m["edge"] = m["n0"] * 0.0 + np.random.default_rng(8).normal(0.5, 1.0, size=len(m))
    res = rc.reality_check(m, n_boot=N_BOOT, seed=3)
    top = res["table"].iloc[0]
    assert top["strategy"] == "edge" and top["p_adj"] < 0.01 and top["dsr"] > 0.95
    assert res["rc_p"] < 0.01 and res["spa_p"] < 0.01
    assert (res["table"]["p_adj"].iloc[1:] > 0.05).all()  # the noise columns stay unrejected
    assert res["pbo"] < 0.1
    assert rc.reality_check(m, n_boot=N_BOOT, seed=3)["rc_p"] == res["rc_p"]


def test_block_matrix_and_render():
    w = WINDOWS[0]
    days = pd.bdate_range(w.start, periods=100)
    rng = np.random.default_rng(0)
    daily = pd.concat([
        pd.DataFrame({"strategy": "a", "as_of": days, "horizon": 5, "total": rng.normal(1, 1, 100) * 4, "n": 4}),
        pd.DataFrame({"strategy": "b", "as_of": days[::2], "horizon": 5, "total": rng.normal(0, 1, 50), "n": 1}),
        pd.DataFrame({"strategy": "rare", "as_of": days[:3], "horizon": 5, "total": 1.0, "n": 1}),
        pd.DataFrame({"strategy": "a", "as_of": days[:1], "horizon": 10, "total": 1.0, "n": 1}),
    ], ignore_index=True)
    m = rc.block_matrix(daily, w, 5)
    assert list(m.columns) == ["a", "b"] and 20 <= len(m) <= 21  # "rare" traded in < MIN_BLOCKS blocks
    first = daily.loc[(daily.strategy == "a") & (daily.horizon == 5)].iloc[:5]
    assert abs(m["a"].iloc[0] - first["total"].sum() / first["n"].sum()) < 1e-12
    results = rc.run(daily, [w], (5, 10), n_boot=200, seed=1)
    assert [r["horizon"] for r in results] == [5]
    text = rc.render(results)
    assert "| a |" in text and "RC p" in text and "PBO" in text


def test_daily_net_uses_executable_traded_signals_net_of_cost():
    frame = pd.DataFrame({
        "strategy": "s", "symbol": ["A", "B", "C", "D"], "as_of": pd.Timestamp("2025-01-06"),
        "entry": 100.0, "stop": [95.0, 95.0, 99.99, 95.0], "entry_price": 100.0,
        "hit_5d": ["target_hit", "stop_hit", "target_hit", "entry_skipped"], "result_r_5d": [2.0, -1.0, 50.0, np.nan],
    })
    out = rc.daily_net(frame, (5, 10))
    cost = 2 * 10.0 / 1e4 * 100.0 / 5.0  # cards.cost_r at the default 10 bp a side
    assert len(out) == 1 and out["n"].iloc[0] == 2 and abs(out["total"].iloc[0] - (1.0 - 2 * cost)) < 1e-12
