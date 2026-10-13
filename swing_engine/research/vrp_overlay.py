"""Batch 6 card `vrp_svxy_dual_signal`: SPY with a small SVXY sleeve sized by VIX when VIX is in contango.

The spec is the card's section of ``docs/preregistration/2026-10-13-batch6.md``; this module implements it and
nothing else. It is a daily two-ETF simulation, not an engine strategy: the replay sizes by stop distance and can
hold a weight only as a full round trip (strategies/volatility_managed_spy.py), which cannot express a 10-25% sleeve
beside an 80% core. Run once::

    uv run python -m swing_engine.research.vrp_overlay --settings config/prereg_b6.yaml

No look-ahead: the target weight of a session uses VIX, VIX3M and SPY closes up to that session and is traded at the
next session's open.
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.research.costs import cost_table
from swing_engine.research.metrics import haircut_sharpe
from swing_engine.research.prereg_eval import _bar_days, _vs_benchmark, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-13-batch6.md"
OUT = "docs/preregistration/2026-10-13-batch6-vrp-results.md"
CARD = "vrp_svxy_dual_signal"
TAG = "prereg-b6"
CORE, SLEEVE = "SPY", "SVXY"
RV_SESSIONS = 10  # card: realised vol from the last 10 SPY close-to-close returns
FULL_DIVISOR, HALF_DIVISOR = 100.0, 200.0  # card: weight VIX/100 with a positive premium, VIX/200 without
TRADE_BAND = 0.02  # card: trade when the target moves by more than 2 points of the account, or crosses zero
SESSIONS_PER_YEAR = 252
BPS = 1e4
#: card: A starts with SVXY's -0.5x form (2018-03-01); B is the project's survivorship-free window
WINDOWS: dict[str, tuple[date, date]] = {"A": (date(2018, 3, 1), date(2024, 10, 4)),
                                         "B": (date(2024, 10, 7), date(2026, 10, 5))}
PRE_2018 = (date(2016, 1, 4), date(2018, 2, 28))  # -1x SVXY: descriptive only, never a trial
N_GROUP_TRIALS = 5  # batch 6: one trial per card (SPEC, "Pass rule")
WARMUP_DAYS = 30  # calendar days of bars read before a window for the realised-vol input


def target_weights(vix: pd.Series, vix3m: pd.Series, spy_close: pd.Series) -> pd.Series:
    """SVXY target weight per session (index of ``spy_close``); NaN while an input is missing."""
    rv = 100.0 * math.sqrt(SESSIONS_PER_YEAR) * spy_close.pct_change().rolling(RV_SESSIONS).std(ddof=1)
    vix, vix3m = vix.reindex(spy_close.index), vix3m.reindex(spy_close.index)
    w = pd.Series(np.where(vix < vix3m, np.where(vix - rv > 0, vix / FULL_DIVISOR, vix / HALF_DIVISOR), 0.0),
                  index=spy_close.index)
    return w.where(vix.notna() & vix3m.notna() & rv.notna())


def simulate(px: pd.DataFrame, target: pd.Series) -> pd.DataFrame:
    """Daily book over the rows of ``px`` (index session; columns core_open, core_close, sleeve_open, sleeve_close,
    core_cost, sleeve_cost in bp per side). ``target`` is the sleeve weight known at each session's CLOSE; it is
    traded at the next row's open when it differs from the weight last traded by more than TRADE_BAND or one of the
    two is zero and the other is not. The first row only supplies closes and a target. Returns per session from the
    second row: ret (close to close, net), weight (sleeve weight last traded), turnover and cost (fractions of
    equity)."""
    core, sleeve, held = 0.0, 0.0, None  # dollar values per $1 of starting equity; `held` = weight last traded
    equity = 1.0
    rows: list[dict[str, Any]] = []
    for i in range(1, len(px)):
        prev, cur = px.iloc[i - 1], px.iloc[i]
        core *= cur["core_open"] / prev["core_close"]
        sleeve *= cur["sleeve_open"] / prev["sleeve_close"]
        at_open = core + sleeve if held is not None else equity
        want = target.iloc[i - 1]
        turnover = cost = 0.0
        if held is None:
            want = 0.0 if not math.isfinite(want) else float(want)
        if math.isfinite(want) and (held is None or abs(want - held) > TRADE_BAND or (want == 0.0) != (held == 0.0)):
            new_sleeve, new_core = want * at_open, (1.0 - want) * at_open
            d_sleeve, d_core = abs(new_sleeve - sleeve), abs(new_core - core)
            cost = (d_sleeve * prev["sleeve_cost"] + d_core * prev["core_cost"]) / BPS
            turnover = (d_sleeve + d_core) / at_open
            core, sleeve, held = new_core - cost, new_sleeve, float(want)
        core *= cur["core_close"] / cur["core_open"]
        sleeve *= cur["sleeve_close"] / cur["sleeve_open"]
        rows.append({"day": px.index[i], "ret": (core + sleeve) / equity - 1.0, "weight": held,
                     "turnover": turnover, "cost": cost / at_open})
        equity = core + sleeve
    return pd.DataFrame(rows).set_index("day") if rows else pd.DataFrame(columns=["ret", "weight", "turnover", "cost"])


def stats(daily: pd.Series, n_trials: int) -> dict[str, float]:
    """Return, risk and the owner's income view of a daily return series indexed by session date."""
    mean, sd = float(daily.mean()), float(daily.std(ddof=1))
    sr = mean / sd * math.sqrt(SESSIONS_PER_YEAR) if sd > 0 else math.nan
    curve = (1.0 + daily).cumprod()
    months = (1.0 + daily).groupby([d.strftime("%Y-%m") for d in daily.index]).prod() - 1.0
    years = len(daily) / SESSIONS_PER_YEAR
    return {"days": float(len(daily)), "cagr": float(curve.iloc[-1] ** (1.0 / years) - 1.0),
            "ann_vol": sd * math.sqrt(SESSIONS_PER_YEAR), "sharpe": sr,
            "haircut_sharpe": haircut_sharpe(sr, years, n_trials)[0] if sr > 0 else sr,
            "max_dd": float((1.0 - curve / curve.cummax()).max()), "worst_day": float(daily.min()),
            "worst_month": float(months.min()), "months_up": float((months > 0).mean())}


def run_window(store: Any, lo: date, hi: date, n_trials: int) -> dict[str, Any]:
    """One window: read the two ETFs and VIX, simulate, grade against buy-and-hold SPY (close to close)."""
    bars = store.read_bars([CORE, SLEEVE], lo - pd.Timedelta(days=WARMUP_DAYS), hi)
    bars = bars.assign(day=_bar_days(bars["ts"]))
    costs = cost_table(bars).assign(day=lambda t: t["as_of"]).pivot(index="day", columns="symbol", values="cost_bps")
    wide = bars.pivot(index="day", columns="symbol", values=["open", "close"]).dropna()
    vix = store.read_table("vix").assign(day=lambda t: pd.to_datetime(t["date"]).dt.date).set_index("day")
    target = target_weights(vix["vix_close"].astype(float), vix["vix3m_close"].astype(float), wide["close"][CORE])
    px = pd.DataFrame({"core_open": wide["open"][CORE], "core_close": wide["close"][CORE],
                       "sleeve_open": wide["open"][SLEEVE], "sleeve_close": wide["close"][SLEEVE],
                       "core_cost": costs[CORE].reindex(wide.index), "sleeve_cost": costs[SLEEVE].reindex(wide.index)})
    first = next(i for i, d in enumerate(px.index) if d >= lo)
    book = simulate(px.iloc[max(first - 1, 0):], target.iloc[max(first - 1, 0):])
    spy = wide["close"][CORE].pct_change().reindex(book.index)
    return {"book": book, "spy": spy, "stats": stats(book["ret"], n_trials), "spy_stats": stats(spy, n_trials),
            "vs": _vs_benchmark(book["ret"], spy, n_trials), "trades": int((book["turnover"] > 0).sum()),
            "avg_weight": float(book["weight"].mean()), "cost_ann": float(book["cost"].mean() * SESSIONS_PER_YEAR)}


def verdict(res: dict[str, dict[str, Any]]) -> tuple[list[bool], str]:
    """SPEC pass rule over windows A and B: haircut Sharpe > 0, alpha vs SPY > 0, alpha t >= the Bonferroni value."""
    crit = alpha_t_critical(N_GROUP_TRIALS)
    rules = [all(res[w]["stats"]["haircut_sharpe"] > 0 for w in WINDOWS),
             all(res[w]["vs"].get("alpha_ann", -1.0) > 0 for w in WINDOWS),
             all(res[w]["vs"].get("alpha_t", -1.0) >= crit for w in WINDOWS)]
    return rules, "PASS" if all(rules) else "FAIL"


def _pct(x: float, spec: str = "+.1%") -> str:
    return format(x, spec) if isinstance(x, float) and math.isfinite(x) else "n/a"


def render(res: dict[str, dict[str, Any]], pre: dict[str, Any] | None) -> list[str]:
    rules, word = verdict(res)
    crit = alpha_t_critical(N_GROUP_TRIALS)
    lines = [f"# Batch 6 results: `{CARD}`", "",
             f"Spec: `{SPEC}`. Generated by `swing_engine.research.vrp_overlay`; net of costs, price-only bars.", "",
             f"## Verdict: {word}", "",
             f"- haircut Sharpe > 0 in both windows: {'yes' if rules[0] else 'no'}",
             f"- alpha against SPY > 0 in both windows: {'yes' if rules[1] else 'no'}",
             f"- alpha t >= {crit:.2f} in both windows: {'yes' if rules[2] else 'no'}", "",
             "## Per window (the book beside buy-and-hold SPY)", "",
             "| window | book | return/yr | deepest drop | worst day | worst month | months up | Sharpe | alpha/yr | "
             "alpha t | beta | avg SVXY weight | trades | costs/yr |", "|" + "---|" * 14]
    blocks = [(w, res[w]) for w in WINDOWS] + ([("2016-18 (descriptive)", pre)] if pre else [])
    for name, r in blocks:
        for label, s, extra in (("overlay", r["stats"], r), ("SPY", r["spy_stats"], None)):
            vs = extra["vs"] if extra else {}
            lines.append(
                f"| {name} | {label} | {_pct(s['cagr'])} | {_pct(-s['max_dd'])} | {_pct(s['worst_day'])} | "
                f"{_pct(s['worst_month'])} | {_pct(s['months_up'], '.0%')} | {s['sharpe']:.2f} | "
                + (f"{_pct(vs.get('alpha_ann', math.nan))} | {vs.get('alpha_t', math.nan):.2f} | "
                   f"{vs.get('beta', math.nan):.2f} | {_pct(extra['avg_weight'], '.1%')} | {extra['trades']} | "
                   f"{_pct(extra['cost_ann'], '.2%')} |" if extra else "| | | | | |"))
    return lines


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH) -> dict[str, Any]:
    """The whole pre-registered run: both windows, the two trials (once), the markdown."""
    from swing_engine.data.store import Store

    with Store(str(store_path), read_only=True) as store:
        res = {w: run_window(store, lo, hi, N_GROUP_TRIALS) for w, (lo, hi) in WINDOWS.items()}
        pre = run_window(store, *PRE_2018, N_GROUP_TRIALS)
    word = verdict(res)[1]
    if not any(r.get("name") == CARD and TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        for w, (lo, hi) in WINDOWS.items():
            log_trial(CARD, {"window": w, "start": lo, "end": hi, "spec": SPEC, "n_trials": N_GROUP_TRIALS},
                      {**res[w]["stats"], **res[w]["vs"]}, trials_path, tags=[TAG, f"window-{w}"],
                      notes=f"pre-registered batch 6 card; verdict {word}")
    lines = render(res, pre)
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return res


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b6.yaml")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out)


if __name__ == "__main__":
    main()
