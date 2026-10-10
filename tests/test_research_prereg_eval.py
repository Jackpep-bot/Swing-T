"""research.prereg_eval: cost top-up, net R, booked costs on the equity curve."""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import prereg_eval as pe
from swing_engine.research.cards import WINDOWS


def test_top_up_charges_only_above_the_replay_cost() -> None:
    payload = {
        "trades": [{"symbol": "A", "signal_date": "2025-01-02T00:00:00", "exit_ts": "2025-01-10T04:00:00Z", "qty": 100,
                    "entry_price": 10.0, "exit_price": 12.0, "initial_stop": 9.0, "pnl": 200.0, "bars_held": 5}],
        "equity_curve": [{"ts": f"2025-01-{d:02d}T04:00:00Z", "equity": 100_000.0 + (200.0 if d >= 10 else 0.0),
                          "exposure": 0.01} for d in range(2, 15)],
    }
    costs = {("A", date(2025, 1, 2)): 30.0, ("A", date(2025, 1, 10)): 10.0}  # 20 bp extra on entry only
    g = pe.grade_run(payload, costs)
    # extra = 0.002 x 10 x 100 = $2 -> net R = (200 - 2) / (100 x 1) = 1.98
    assert g["trades"] == 1 and g["net_r"] == pytest.approx(1.98)
    assert g["total_return"] == pytest.approx((100_198.0) / 100_000.0 - 1.0)
    assert g["exposure"] == pytest.approx(0.01)


def test_build_report_for_another_group(tmp_path) -> None:
    """--slugs / --tag-prefix / --n-trials: files are found by tag prefix, the haircut uses the group's n_trials,
    a missing window fails the strategy; the three-pick defaults are unchanged."""
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2025-01-02", periods=300)
    equity = 100_000.0 * (1.0 + rng.normal(0.002, 0.005, len(days))).cumprod()
    payload = {
        "trades": [{"symbol": "A", "signal_date": "2025-01-02T00:00:00", "exit_ts": "2025-01-10T04:00:00Z", "qty": 100,
                    "entry_price": 10.0, "exit_price": 12.0, "initial_stop": 9.0, "pnl": 200.0, "bars_held": 5}],
        "equity_curve": [{"ts": d.isoformat(), "equity": float(e)} for d, e in zip(days, equity, strict=True)],
    }
    for w in WINDOWS:
        (tmp_path / f"{w.start.isoformat()}_{w.end.isoformat()}_prereg2-good.json").write_text(json.dumps(payload))
    w = WINDOWS[0]
    (tmp_path / f"{w.start.isoformat()}_{w.end.isoformat()}_prereg2-half.json").write_text(json.dumps(payload))
    lines = pe.build_report(tmp_path, {}, ("good", "half"), "prereg2-", 2, "docs/preregistration/x-results.md")
    assert lines[0] == "# Pre-registered group of 2: results" and "x.md (n_trials = 2)" in lines[2]
    assert lines[-2:] == ["- **good**: PASS", "- **half**: FAIL"]
    assert pe.grade_run(payload, {}, 2)["haircut_sharpe"] > pe.grade_run(payload, {})["haircut_sharpe"] > 0
    default = pe.build_report(tmp_path, {})
    assert default[0] == "# Three-pick group: results" and "2026-10-09-three-picks.md (n_trials = 3)" in default[2]
    assert default[-3:] == [f"- **{s}**: FAIL" for s in pe.SLUGS]


def _timing_payload(days, equity) -> dict:
    return {
        "trades": [{"symbol": "SPY", "signal_date": days[0].isoformat(), "exit_ts": days[5].isoformat(), "qty": 100,
                    "entry_price": 10.0, "exit_price": 9.0, "initial_stop": 8.0, "pnl": -100.0, "bars_held": 5}],
        "equity_curve": [{"ts": d.isoformat(), "equity": float(e), "exposure": 0.5}
                         for d, e in zip(days, equity, strict=True)],
    }


def test_benchmark_excess_return_and_information_ratio() -> None:
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2025-01-02", periods=253)
    spy_ret = rng.normal(0.002, 0.01, len(days))  # a rising market
    spy = pd.Series(400.0 * (1.0 + spy_ret).cumprod(), index=[d.date() for d in days])
    edge = np.where(np.arange(len(days)) % 2 == 0, 0.0005, 0.0001)  # +3 bp a day on average over SPY
    equity = 100_000.0 * (1.0 + spy_ret + edge).cumprod()
    g = pe.grade_run(_timing_payload(days, equity), {}, 3, spy)
    excess = pd.Series(equity).pct_change().dropna().to_numpy() - spy_ret[1:]
    assert g["excess_ann"] == pytest.approx(excess.mean() * 252)
    assert g["ir"] == pytest.approx(excess.mean() / excess.std(ddof=1) * np.sqrt(252))
    assert 0 < g["haircut_ir"] < g["ir"]  # 3 trials
    assert g["beta"] == pytest.approx(1.0, abs=0.01) and g["alpha_ann"] == pytest.approx(g["excess_ann"], abs=0.01)
    assert g["sharpe"] > 0 and g["net_r"] < 0  # the absolute columns are still there
    assert "ir" not in pe.grade_run(_timing_payload(days, equity), {}, 3)  # no benchmark: unchanged
    # a half-invested copy of SPY: positive Sharpe in a rising market, negative excess return and IR
    half = 100_000.0 * (1.0 + 0.5 * spy_ret).cumprod()
    h = pe.grade_run(_timing_payload(days, half), {}, 3, spy)
    assert h["sharpe"] > 0 and h["ir"] < 0 and h["haircut_ir"] == h["ir"] and h["beta"] == pytest.approx(0.5, abs=0.01)


def test_benchmark_slugs_pass_on_haircut_ir_only(tmp_path) -> None:
    rng = np.random.default_rng(2)
    days = pd.bdate_range("2025-01-02", periods=300)
    spy_ret = rng.normal(0.0005, 0.01, len(days))
    spy = pd.Series(400.0 * (1.0 + spy_ret).cumprod(), index=[d.date() for d in days])
    payload = _timing_payload(days, 100_000.0 * (1.0 + spy_ret + 0.001).cumprod())  # beats SPY; net R < 0
    for w in WINDOWS:
        for slug in ("timer", "picker"):
            (tmp_path / f"{w.start.isoformat()}_{w.end.isoformat()}_b2-{slug}.json").write_text(json.dumps(payload))
    lines = pe.build_report(tmp_path, {}, ("timer", "picker"), "b2-", 3, "x-results.md", spy, ("timer",), "SPY")
    assert lines[-2:] == ["- **timer**: PASS", "- **picker**: FAIL"]  # picker keeps the absolute rule (net R < 0)
    assert "## Against buy-and-hold SPY" in lines and sum("| timer |" in x for x in lines) == 4
    plain = pe.build_report(tmp_path, {}, ("timer", "picker"), "b2-", 3, "x-results.md")
    assert plain[-2:] == ["- **timer**: FAIL", "- **picker**: FAIL"] and not any("buy-and-hold" in x for x in plain)


def test_alpha_slugs_need_the_standard_rule_and_a_bonferroni_significant_alpha(tmp_path) -> None:
    assert pe.alpha_t_critical(2) == pytest.approx(2.2414, abs=1e-4)  # two-sided 5% over 2 trials
    assert pe.alpha_t_critical(1) == pytest.approx(1.96, abs=1e-3)
    rng = np.random.default_rng(3)
    days = pd.bdate_range("2025-01-02", periods=300)
    spy_ret = rng.normal(0.002, 0.01, len(days))  # a rising market: anything long passes the standard rule
    spy = pd.Series(400.0 * (1.0 + spy_ret).cumprod(), index=[d.date() for d in days])
    noise = rng.normal(0.0, 0.002, len(days))
    noise -= noise.mean()

    def payload(edge: float) -> dict:
        p = _timing_payload(days, 100_000.0 * (1.0 + spy_ret + edge + noise).cumprod())
        p["trades"][0].update(exit_price=12.0, pnl=200.0)  # net R > 0
        return p

    for w in WINDOWS:
        for slug, edge in (("alpha", 0.001), ("beta", 0.0)):
            (tmp_path / f"{w.start.isoformat()}_{w.end.isoformat()}_b3-{slug}.json").write_text(json.dumps(payload(edge)))
    g = pe.grade_run(payload(0.001), {}, 2, spy)
    assert g["alpha_t"] > 5 and g["turnover_ann"] == pytest.approx((10.0 + 12.0) * 100 / 2 / g_mean(payload(0.001)) / (299 / 252))
    assert abs(pe.grade_run(payload(0.0), {}, 2, spy)["alpha_t"]) < 1
    args = (tmp_path, {}, ("alpha", "beta"), "b3-", 2, "x-results.md", spy, (), "SPY")
    lines = pe.build_report(*args, ("alpha", "beta"))
    assert lines[-2:] == ["- **alpha**: PASS", "- **beta**: FAIL"]  # beta: positive Sharpe and net R, no alpha
    assert any("alpha t >= 2.241" in x for x in lines) and any("turnover / yr" in x for x in lines)
    assert pe.build_report(*args)[-2:] == ["- **alpha**: PASS", "- **beta**: PASS"]  # the standard rule alone
    assert pe.build_report(*args[:6], None, (), "", ("alpha",))[-2] == "- **alpha**: FAIL"  # no benchmark: no alpha


def g_mean(payload: dict) -> float:
    return float(np.mean([r["equity"] for r in payload["equity_curve"]]))
