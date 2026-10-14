"""Batch 9: two fully invested weights cards, simulated with research.weights_book (docs/preregistration/
2026-10-14-batch9.md is the spec; this module implements it and nothing else):

* `sp500_momentum_index_replica`: twice a year, the 100 of the 500 largest names (`mcap_pit`) with the best
  volatility-adjusted 12-1 momentum, weighted by market cap x momentum score, capped.
* `leveraged_sp500_trend_switch`: SSO while SPY trends above its 200-session average, BIL otherwise, with a 1% band.

Run once::

    uv run python -m swing_engine.research.b9_books --settings config/prereg_b9.yaml

No look-ahead: a selection uses closes and filings up to its reference date; a switch uses SPY's close and is traded
at the next open; weights are traded at the open of their rebalance session.
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
from swing_engine.data.calendar import trading_days
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, _vs_benchmark, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial
from swing_engine.research.vrp_overlay import _pct, stats
from swing_engine.research.weights_book import simulate

SPEC = "docs/preregistration/2026-10-14-batch9.md"
OUT = "docs/preregistration/2026-10-14-batch9-results.md"
TAG = "prereg-b9"
MOMENTUM, SWITCH = "sp500_momentum_index_replica", "leveraged_sp500_trend_switch"
N_GROUP_TRIALS = 2  # one per card (SPEC, "Pass rule")
WINDOWS: dict[str, tuple[date, date]] = {"A": (date(2017, 1, 1), date(2024, 10, 4)),
                                         "B": (date(2024, 10, 7), date(2026, 10, 5))}
DATA_START = date(2016, 1, 4)
# momentum card
UNIVERSE_N, HOLD_N, ENTER_RANK, KEEP_RANK = 500, 100, 80, 120  # card: top 100 of the 500 largest, 80/120 buffer
MAX_WEIGHT, MAX_CAP_MULT = 0.09, 3.0  # card: each name <= 9% and <= 3 x its cap weight in the 500
Z_CLIP = 3.0  # card: z winsorised at +/-3
MIN_HISTORY = 252  # card: at least 252 sessions of history on the reference date
#: harness finding (2026-10-14): some filed share counts are off by about 1,000x (Alcoa at $3,300 trillion). A name
#: whose mcap_pit is more than this many times its median daily dollar volume (63 sessions) is dropped: real large
#: caps sit near 50-2,000, the unit errors near 30,000-1,000,000.
MAX_MCAP_TO_DOLLAR_VOLUME = 10_000.0
DV_SESSIONS = 63
REF_MONTHS, REBAL_MONTHS = (2, 8), (3, 9)  # card: reference = last session of Feb / Aug; rebalance in Mar / Sep
LOOKBACK_MONTHS, SKIP_MONTHS = 13, 1  # card: from 13 months before the reference date to 1 month before
# trend card
LONG, CASH, MARKET = "SSO", "BIL", "SPY"
SMA_SESSIONS = 200  # card: 200-session simple average
UPPER, LOWER = 1.01, 0.99  # card: into SSO at >= 1.01 x the average, into BIL at <= 0.99 x


# ------------------------------------------------------------------------------------------------ momentum card
def reference_days(sessions: Sequence[date]) -> list[date]:
    """Last session of each February and August."""
    s = pd.Series(sessions, index=pd.to_datetime(sessions))
    last = s.groupby([s.index.year, s.index.month]).last()
    return [d for (_, m), d in last.items() if m in REF_MONTHS]


def rebalance_day(ref: date, sessions: Sequence[date]) -> date | None:
    """First session after the third Friday of the month after ``ref`` (March for February, September for August)."""
    month = REBAL_MONTHS[REF_MONTHS.index(ref.month)]
    first = date(ref.year, month, 1)
    third_friday = first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)
    later = [d for d in sessions if d > third_friday]
    return later[0] if later else None


def momentum_values(closes: pd.DataFrame, ref: date) -> pd.Series:
    """(close 1 month before ``ref`` / close 13 months before - 1) / sd of the daily returns between them, for the
    symbols with MIN_HISTORY closes up to ``ref`` and both end closes."""
    idx = closes.index
    ref_ts = pd.Timestamp(ref)
    end = idx[idx <= (ref_ts - pd.DateOffset(months=SKIP_MONTHS)).date()]
    start = idx[idx <= (ref_ts - pd.DateOffset(months=LOOKBACK_MONTHS)).date()]
    if not len(end) or not len(start):
        return pd.Series(dtype=float)
    span = closes.loc[start[-1]:end[-1]]
    hist = closes.loc[:ref].notna().sum()
    rets = span.pct_change(fill_method=None).iloc[1:]
    value = (span.iloc[-1] / span.iloc[0] - 1.0) / rets.std(ddof=1)
    return value.where(hist >= MIN_HISTORY).replace([np.inf, -np.inf], np.nan).dropna()


def scores(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    """(winsorised z, score) of momentum values: score = 1 + z above zero, 1 / (1 - z) below."""
    z = ((values - values.mean()) / values.std(ddof=1)).clip(-Z_CLIP, Z_CLIP)
    return z, pd.Series(np.where(z > 0, 1.0 + z, 1.0 / (1.0 - z)), index=z.index)


def select(z: pd.Series, current: set[str]) -> list[str]:
    """100 names: holdings ranked in the top 120 stay; new names only from the top 80; then fill by rank."""
    order = list(z.sort_values(ascending=False, kind="mergesort").index)
    rank = {s: i + 1 for i, s in enumerate(order)}
    keep = [s for s in order if s in current and rank[s] <= KEEP_RANK][:HOLD_N]
    for pool in ([s for s in order if rank[s] <= ENTER_RANK], order):
        for s in pool:
            if len(keep) >= HOLD_N:
                break
            if s not in keep:
                keep.append(s)
    return keep


def capped_weights(raw: pd.Series, caps: pd.Series) -> pd.Series:
    """``raw`` normalised to 1, each weight at most its cap; the excess goes pro rata to the names under their cap.
    The caps must add up to at least 1 (``caps_for``)."""
    w = raw / raw.sum()
    for _ in range(len(w)):
        over = w > caps + 1e-12
        if not over.any():
            break
        excess = float((w[over] - caps[over]).sum())
        w[over] = caps[over]
        free = ~over & (w < caps)
        w[free] += excess * w[free] / w[free].sum()
    return w


def caps_for(cap_weight: pd.Series) -> pd.Series:
    """min(MAX_WEIGHT, k x cap weight) with k = MAX_CAP_MULT, or the smallest larger k at which the caps add up to 1
    (registered reading: when the 100 names' 3 x cap weights cannot hold 100%, the multiple is raised, never the 9%)."""
    if MAX_WEIGHT * len(cap_weight) < 1.0:  # too few names to hold 100% under the 9% cap
        return pd.Series(MAX_WEIGHT, index=cap_weight.index)
    lo, hi = MAX_CAP_MULT, MAX_CAP_MULT
    while np.minimum(MAX_WEIGHT, hi * cap_weight).sum() < 1.0:
        lo, hi = hi, hi * 2.0
    for _ in range(60):
        if hi - lo < 1e-9:
            break
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if np.minimum(MAX_WEIGHT, mid * cap_weight).sum() < 1.0 else (lo, mid)
    return np.minimum(MAX_WEIGHT, hi * cap_weight)


def momentum_orders(closes: pd.DataFrame, mcap_at: Any, sessions: Sequence[date]) -> dict[date, pd.Series]:
    """Target weights at each rebalance session (``mcap_at(ref) -> Series`` of point-in-time market caps)."""
    orders: dict[date, pd.Series] = {}
    current: set[str] = set()
    for ref in reference_days(sessions):
        day = rebalance_day(ref, sessions)
        values = momentum_values(closes, ref)
        mcap = mcap_at(ref).reindex(values.index).dropna()
        if day is None or len(mcap) < UNIVERSE_N:
            continue
        uni = mcap.sort_values(ascending=False, kind="mergesort").iloc[:UNIVERSE_N]
        z, score = scores(values.reindex(uni.index))
        held = select(z, current)
        caps = caps_for((uni / uni.sum()).reindex(held))
        orders[day] = capped_weights(uni.reindex(held) * score.reindex(held), caps)
        current = set(held)
    return orders


def mcap_function(store: Any, bars: pd.DataFrame, closes: pd.DataFrame) -> Any:
    """``ref -> Series``: point-in-time market caps on ``ref`` (data.fundamentals.join_share_issuance), without the
    names failing the MAX_MCAP_TO_DOLLAR_VOLUME check."""
    from swing_engine.data.fundamentals import join_share_issuance

    dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(index="day", columns="symbol",
                                                                        values="dv").reindex(closes.index)

    def mcap_at(ref: date) -> pd.Series:
        rows = bars.loc[bars["day"] == ref, ["symbol", "ts", "close"]]
        mcap = join_share_issuance(store, rows).set_index("symbol")["mcap_pit"].astype(float)
        dv = dollar_volume.loc[:ref].tail(DV_SESSIONS).median()
        return mcap.where(mcap <= MAX_MCAP_TO_DOLLAR_VOLUME * dv.reindex(mcap.index)).dropna()

    return mcap_at


# ------------------------------------------------------------------------------------------------ trend card
def switch_states(spy: pd.Series) -> pd.Series:
    """1 (SSO) or 0 (BIL) at each close: the first state is close > average; then the 1% band decides."""
    sma = spy.rolling(SMA_SESSIONS).mean()
    out, state = [], None
    for px, avg in zip(spy, sma, strict=True):
        if not math.isfinite(avg):
            out.append(np.nan)
            continue
        if state is None:
            state = 1 if px > avg else 0
        elif px >= UPPER * avg:
            state = 1
        elif px <= LOWER * avg:
            state = 0
        out.append(state)
    return pd.Series(out, index=spy.index)


def switch_orders(states: pd.Series, start: date) -> dict[date, pd.Series]:
    """An order at the open of the first session on or after ``start`` (the state at the close before it) and at
    the open after each later change of state."""
    days = list(states.index)
    first = next((i for i, d in enumerate(days) if d >= start), None)
    orders: dict[date, pd.Series] = {}
    if first is None or first == 0:
        return orders
    for i in range(first, len(days)):
        prev = states.iloc[i - 1]
        if not math.isfinite(prev) or (i > first and prev == states.iloc[i - 2]):
            continue
        orders[days[i]] = pd.Series({LONG: 1.0} if prev == 1 else {CASH: 1.0})
    return orders


# ------------------------------------------------------------------------------------------------ run
def grade(book: pd.DataFrame, spy: pd.Series) -> dict[str, Any]:
    spy = spy.reindex(book.index)
    return {"stats": stats(book["ret"], N_GROUP_TRIALS), "spy_stats": stats(spy, N_GROUP_TRIALS),
            "vs": _vs_benchmark(book["ret"], spy, N_GROUP_TRIALS), "start": book.index[0],
            "turnover_ann": float(book["turnover"].sum() / (len(book) / 252.0)),
            "cost_ann": float(book["cost"].mean() * 252.0), "orders": int((book["turnover"] > 0).sum()),
            "avg_held": float(book["n_held"].mean())}


def verdict(res: dict[str, dict[str, Any]]) -> tuple[list[bool], str]:
    crit = alpha_t_critical(N_GROUP_TRIALS)
    rules = [all(res[w]["stats"]["haircut_sharpe"] > 0 for w in WINDOWS),
             all(res[w]["vs"].get("alpha_ann", -1.0) > 0 for w in WINDOWS),
             all(res[w]["vs"].get("alpha_t", -1.0) >= crit for w in WINDOWS)]
    return rules, "PASS" if all(rules) else "FAIL"


def render(results: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    crit = alpha_t_critical(N_GROUP_TRIALS)
    lines = ["# Batch 9 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b9_books`; net of costs, "
             "price-only bars (dividends credited neither to the books nor to SPY).", ""]
    for card, res in results.items():
        rules, word = verdict(res)
        lines += [f"## `{card}`: {word}", "",
                  f"haircut Sharpe > 0 in both windows: {'yes' if rules[0] else 'no'}; alpha > 0 in both: "
                  f"{'yes' if rules[1] else 'no'}; alpha t >= {crit:.2f} in both: {'yes' if rules[2] else 'no'}.", "",
                  "| window | from | book | return/yr | deepest drop | worst month | months up | Sharpe | alpha/yr | "
                  "alpha t | beta | turnover/yr | costs/yr | trading days | names held |", "|" + "---|" * 15]
        for w in WINDOWS:
            r = res[w]
            for label, s in (("book", r["stats"]), ("SPY", r["spy_stats"])):
                vs = r["vs"] if label == "book" else {}
                extra = (f"{_pct(vs.get('alpha_ann', math.nan))} | {vs.get('alpha_t', math.nan):.2f} | "
                         f"{vs.get('beta', math.nan):.2f} | {_pct(r['turnover_ann'], '.0%')} | {_pct(r['cost_ann'], '.2%')} | "
                         f"{r['orders']} | {r['avg_held']:.0f} |") if label == "book" else "| | | | | | |"
                lines.append(f"| {w} | {r['start']} | {label} | {_pct(s['cagr'])} | {_pct(-s['max_dd'])} | "
                             f"{_pct(s['worst_month'])} | {_pct(s['months_up'], '.0%')} | {s['sharpe']:.2f} | " + extra)
        lines.append("")
    lines += ["## Verdicts", *[f"- **{card}**: {verdict(res)[1]}" for card, res in results.items()]]
    return lines


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH) -> dict[str, Any]:
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.store import Store

    end = max(hi for _, hi in WINDOWS.values())
    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, DATA_START, end)
        bars = bars.assign(day=_bar_days(bars["ts"]))
        closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
        opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
        delist = delisting_returns(store)

        mcap_at = mcap_function(store, bars, closes)
        sessions = [d for d in trading_days(DATA_START, end) if d in closes.index]
        mom_orders = momentum_orders(closes, mcap_at, sessions)
    traded = sorted({s for w in mom_orders.values() for s in w.index} | {LONG, CASH, MARKET})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy = closes[MARKET].pct_change(fill_method=None)
    states = switch_states(closes[MARKET].dropna())
    results: dict[str, dict[str, dict[str, Any]]] = {MOMENTUM: {}, SWITCH: {}}
    for w, (lo, hi) in WINDOWS.items():
        span = closes.loc[lo:hi]
        before = [d for d in sorted(mom_orders) if d <= span.index[0]]
        orders = {d: o for d, o in mom_orders.items() if span.index[0] < d <= span.index[-1]}
        if before:
            orders[span.index[0]] = mom_orders[before[-1]]
        book = simulate(opens.loc[lo:hi], span, costs, orders, delist)
        results[MOMENTUM][w] = grade(book, spy)
        sw = switch_orders(states.loc[:hi], lo)
        book = simulate(opens.loc[lo:hi, [LONG, CASH]], span[[LONG, CASH]], costs, sw)
        results[SWITCH][w] = grade(book, spy)
    logged = any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path))
    if not logged:
        for card, res in results.items():
            word = verdict(res)[1]
            for w, (lo, hi) in WINDOWS.items():
                log_trial(card, {"window": w, "start": lo, "end": hi, "spec": SPEC, "n_trials": N_GROUP_TRIALS},
                          {**res[w]["stats"], **res[w]["vs"]}, trials_path, tags=[TAG, f"window-{w}"],
                          notes=f"pre-registered batch 9 card; verdict {word}")
    lines = render(results)
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return results


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out)


if __name__ == "__main__":
    main()
