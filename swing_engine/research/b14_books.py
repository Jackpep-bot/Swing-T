"""Batch 14 (docs/preregistration/2026-10-14-batch14.md is the spec; this module implements it and nothing else):

* `sp500_four_signal_composite` (weights card): monthly, the 100 of the 500 largest names with the best composite of
  volatility-adjusted 12-1 momentum, gross profit / assets, minus net share issuance and book-to-market (rank band
  90 / 120), weighted mcap x the replica's score map, capped; re-weighted only on a name change or a 25% drift.
* `vol_scaled_momentum_replica` (weights card): batch 9's replica with exposure min(1, 0.15 / its own 126-session
  volatility), changed monthly when it moves by 0.10 or more; the rest in BIL.
* `premise_check_french_momentum_profitability`: not a trial and not a pass route; 0.5 BIG HiPRIOR + 0.5 BIG HiOP
  from the Ken French library, CAPM alpha 1963-07 .. latest.

Run once::

    uv run python -m swing_engine.research.b14_books --settings config/prereg_b9.yaml
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
from swing_engine.research import b9_books as b9
from swing_engine.research import b11_books as b11
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch14.md"
OUT = "docs/preregistration/2026-10-14-batch14-results.md"
TAG = "prereg-b14"
COMPOSITE, SCALED = "sp500_four_signal_composite", "vol_scaled_momentum_replica"
PREMISE = "premise_check_french_momentum_profitability"
N_TRIALS = 6  # cards: the momentum family's count after this batch; bar alpha_t_critical(6)
MARKET, BILL = "SPY", "BIL"
FIRST_SIGNAL = date(2017, 1, 31)  # composite card: SPY before its first signal day
# composite card
TOP, MIN_CLOSE, MIN_HISTORY = 500, 10.0, 273
MOM_SKIP, MOM_LONG, VOL_SESSIONS = 21, 273, 252
Z_CLIP, MIN_SIGNALS = 3.0, 3
HOLD, ENTER, STAY = 100, 90, 120
DRIFT_LIMIT = 0.25  # re-weight when any weight is more than 25% away from its target
SIGNALS = ("momentum", "gp_assets", "net_repurchase", "book_to_market")
# scaled card
TARGET_VOL, VOL_LOOKBACK, EXPOSURE_STEP = 0.15, 126, 0.10
# premise check
FRENCH_DIR = ROOT / "data" / "research" / "french"
FRENCH_FILES = {"prior": "6_Portfolios_ME_Prior_12_2_CSV.zip", "op": "6_Portfolios_ME_OP_2x3_CSV.zip",
                "ff3": "F-F_Research_Data_Factors_CSV.zip"}
SUBPERIODS = (("1963-07", "1989-12"), ("1990-01", "2016-12"), ("2017-01", "2100-12"))
NW_LAGS, SUPPORT_T, CONSISTENT_CORR = 6, 3.0, 0.5


# ------------------------------------------------------------------------------------------------ composite card
def zscore(x: pd.Series) -> pd.Series:
    """z across the names, winsorised at +/-Z_CLIP, then z again."""
    z = ((x - x.mean()) / x.std(ddof=1)).clip(-Z_CLIP, Z_CLIP)
    return (z - z.mean()) / z.std(ddof=1)


def composite(signals: pd.DataFrame, use: Sequence[str] = SIGNALS) -> pd.Series:
    """Z of the mean of the available signal z-scores (at least MIN_SIGNALS of the four; 1 when one signal is used)."""
    z = pd.DataFrame({s: zscore(signals[s]) for s in use})
    need = MIN_SIGNALS if len(use) == len(SIGNALS) else 1
    mean = z.mean(axis=1).where(z.notna().sum(axis=1) >= need)
    return (mean - mean.mean()) / mean.std(ddof=1)


def score_map(z: pd.Series) -> pd.Series:
    """The replica's mapping: 1 + Z above zero, 1 / (1 - Z) below."""
    return pd.Series(np.where(z > 0, 1.0 + z, 1.0 / (1.0 - z)), index=z.index)


def target_weights(mcap: pd.Series, z: pd.Series, held: Sequence[str]) -> pd.Series:
    """mcap x s(Z) over ``held``, capped at 9% and 3 x cap weight (b9.caps_for), the rest in SPY."""
    if not held:
        return pd.Series({MARKET: 1.0})
    caps = b9.caps_for((mcap / mcap.sum()).reindex(held))
    w = b9.capped_weights(mcap.reindex(held) * score_map(z.reindex(held)), caps)
    rest = 1.0 - float(w.sum())
    return pd.concat([w, pd.Series({MARKET: rest})]) if rest > 1e-9 else w


def needs_reset(drifted: pd.Series, target: pd.Series) -> bool:
    """A name enters or leaves, or a weight is more than DRIFT_LIMIT away from its target (relative)."""
    names_d, names_t = set(drifted.index) - {MARKET}, set(target.index) - {MARKET}
    if names_d != names_t:
        return True
    both = target.drop(MARKET, errors="ignore")
    return bool(((drifted.reindex(both.index) / both - 1.0).abs() > DRIFT_LIMIT).any())


def drift(weights: pd.Series, closes: pd.DataFrame, since: date, to: date) -> pd.Series:
    """``weights`` set at ``since`` carried to ``to`` by close-to-close moves, renormalised."""
    move = (closes.loc[to] / closes.loc[since]).reindex(weights.index).fillna(1.0)
    w = weights * move
    return w / w.sum()


def composite_orders(closes: pd.DataFrame, snap_at: Any, sessions: Sequence[date], use: Sequence[str] = SIGNALS,
                     drift_rule: bool = True) -> dict[date, pd.Series]:
    """Monthly books from FIRST_SIGNAL (``snap_at(day) -> DataFrame`` of the universe with mcap_pit and the four
    signals); SPY before. ``drift_rule`` False: reset every month (the universe benchmark uses a plain monthly reset)."""
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    held_w, held_at = None, None
    for t in sorted(d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m)):
        k = sessions.index(t)
        if t < FIRST_SIGNAL or k + 1 >= len(sessions):
            continue
        snap = snap_at(t)
        z = composite(snap, use).dropna()
        held = b9.select(z, current, hold=HOLD, enter=ENTER, stay=STAY)
        target = target_weights(snap["mcap_pit"], z, held)
        if not drift_rule or held_w is None or needs_reset(drift(held_w, closes, held_at, t), target):
            orders[sessions[k + 1]] = target
            held_w, held_at = target, t
        current = set(held)
    return orders


# ------------------------------------------------------------------------------------------------ scaled card
def scaled_orders(base: dict[date, pd.Series], base_returns: pd.Series, closes: pd.DataFrame,
                  sessions: Sequence[date]) -> tuple[dict[date, pd.Series], pd.Series]:
    """The replica's books scaled by exposure e (changed monthly when it moves >= EXPOSURE_STEP), rest in BIL; SPY
    before the first base book. Returns (orders, exposure held per session)."""
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({MARKET: 1.0})}
    first = min((d for d in base if d > sessions[0]), default=None)
    e, w_base, base_at = 1.0, None, None
    month_ends = set(d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m))
    held = pd.Series(np.nan, index=list(sessions))
    for k, d in enumerate(sessions):
        if d in base and first is not None and d >= first:
            w_base, base_at = base[d], d
            orders[d] = pd.concat([e * w_base, pd.Series({BILL: 1.0 - e})]) if e < 1 else w_base
        if w_base is not None and d in month_ends and k + 1 < len(sessions):
            r = base_returns.loc[:d].dropna().tail(VOL_LOOKBACK)
            sigma = float(r.std(ddof=1) * math.sqrt(252)) if len(r) >= VOL_LOOKBACK else math.nan
            e_new = min(1.0, TARGET_VOL / sigma) if math.isfinite(sigma) and sigma > 0 else 1.0
            if abs(e_new - e) >= EXPOSURE_STEP:
                e = e_new
                cur = drift(w_base, closes, base_at, d)
                orders[sessions[k + 1]] = pd.concat([e * cur, pd.Series({BILL: 1.0 - e})]) if e < 1 else cur
        held.iloc[k] = e if w_base is not None else np.nan
    return orders, held


# ------------------------------------------------------------------------------------------------ premise check
def french_monthly(text: str) -> pd.DataFrame:
    """The first block (value-weighted, monthly) of a French CSV: index yyyy-mm, decimal returns."""
    lines = text.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith(","))
    cols = [c.strip() for c in lines[head].split(",")[1:]]
    rows = []
    for ln in lines[head + 1:]:
        cells = [c.strip() for c in ln.split(",")]
        if not (cells[0].isdigit() and len(cells[0]) == 6):
            break
        rows.append([f"{cells[0][:4]}-{cells[0][4:]}", *[float(c) for c in cells[1:]]])
    out = pd.DataFrame(rows, columns=["month", *cols]).set_index("month") / 100.0
    return out.where(out > -0.99)  # -99.99 is French's missing value


def capm(excess: pd.Series, mkt: pd.Series) -> dict[str, float]:
    """Monthly OLS of ``excess`` on ``mkt``: alpha per year, OLS t and Newey-West (NW_LAGS) t."""
    both = pd.DataFrame({"y": excess, "x": mkt}).dropna()
    x = np.column_stack([np.ones(len(both)), both["x"].to_numpy()])
    y = both["y"].to_numpy()
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    e = y - x @ beta
    n = len(y)
    xtx_inv = np.linalg.inv(x.T @ x)
    ols_se = math.sqrt(float(e @ e) / (n - 2) * xtx_inv[0, 0])
    s = (x * e[:, None]).T @ (x * e[:, None])
    for lag in range(1, NW_LAGS + 1):
        w = 1.0 - lag / (NW_LAGS + 1)
        g = (x[lag:] * e[lag:, None]).T @ (x[:-lag] * e[:-lag, None])
        s += w * (g + g.T)
    nw_se = math.sqrt(float((xtx_inv @ s @ xtx_inv)[0, 0]))
    return {"months": n, "alpha_ann": float(beta[0] * 12), "t_ols": float(beta[0] / ols_se),
            "t_nw": float(beta[0] / nw_se), "beta": float(beta[1])}


def premise_check(texts: dict[str, str], ours: pd.Series | None) -> tuple[list[str], dict[str, Any]]:
    """The card's test on the French files; ``ours``: monthly (50/50 momentum-only + profitability-only) - SPY."""
    prior, op, ff = french_monthly(texts["prior"]), french_monthly(texts["op"]), french_monthly(texts["ff3"])
    data = pd.DataFrame({"mom": prior["BIG HiPRIOR"], "op": op["BIG HiOP"], "mkt": ff["Mkt-RF"], "rf": ff["RF"]}).dropna()
    data = data.loc[data.index >= "1963-07"]
    blend = 0.5 * (data["mom"] + data["op"])
    full = capm(blend - data["rf"], data["mkt"])
    subs = {f"{lo} .. {min(hi, data.index[-1])}": capm((blend - data["rf"]).loc[lo:hi], data["mkt"].loc[lo:hi])
            for lo, hi in SUBPERIODS}
    legs = {name: capm(data[name] - data["rf"], data["mkt"]) for name in ("mom", "op")}
    resid = {}
    for name in ("mom", "op"):
        b = legs[name]["beta"]
        resid[name] = (data[name] - data["rf"]) - b * data["mkt"]
    supported = full["t_ols"] >= SUPPORT_T and all(r["alpha_ann"] > 0 for r in subs.values())
    lines = [f"## `{PREMISE}`: premise {'SUPPORTED' if supported else 'NOT SUPPORTED'}", "",
             f"Ken French library, value-weighted monthly, {data.index[0]} .. {data.index[-1]}; blend = 0.5 BIG HiPRIOR "
             f"+ 0.5 BIG HiOP; CAPM on Mkt-RF. Not a trial and not a pass route. Support needs OLS alpha t >= "
             f"{SUPPORT_T:.1f} over the full window and alpha > 0 in each subperiod.", "",
             "| series | months | alpha/yr | t (OLS) | t (Newey-West 6) | beta |", "|---|---|---|---|---|---|",
             f"| blend, full window | {full['months']} | {full['alpha_ann']:+.2%} | {full['t_ols']:.2f} | {full['t_nw']:.2f} | "
             f"{full['beta']:.2f} |",
             *[f"| blend, {k} | {v['months']} | {v['alpha_ann']:+.2%} | {v['t_ols']:.2f} | {v['t_nw']:.2f} | {v['beta']:.2f} |"
               for k, v in subs.items()],
             *[f"| {name} leg alone, full | {v['months']} | {v['alpha_ann']:+.2%} | {v['t_ols']:.2f} | {v['t_nw']:.2f} | "
               f"{v['beta']:.2f} |" for name, v in legs.items()], "",
             f"Correlation of the two legs' CAPM residuals: {resid['mom'].corr(resid['op']):.2f}."]
    out: dict[str, Any] = {"supported": supported, "full": full}
    if ours is not None:
        french_ex = (blend - (data["mkt"] + data["rf"])).loc["2017-01":]
        both = pd.DataFrame({"french": french_ex, "ours": ours}).dropna()
        corr = float(both["french"].corr(both["ours"])) if len(both) > 2 else math.nan
        same = bool(np.sign(both["french"].mean()) == np.sign(both["ours"].mean())) if len(both) else False
        consistent = corr >= CONSISTENT_CORR and same
        lines += ["", f"Link to our books (2017-01 .. {both.index[-1] if len(both) else '-'}, {len(both)} months): correlation "
                  f"of French blend minus market with our 50/50 momentum-only + profitability-only books minus SPY: "
                  f"{corr:.2f}; means {both['french'].mean():+.2%} and {both['ours'].mean():+.2%} a month. "
                  f"{'Consistent' if consistent else 'Not consistent'} with the premise (needs correlation >= "
                  f"{CONSISTENT_CORR} and same-sign means)."]
        out.update(corr=corr, consistent=consistent)
    return lines + [""], out


# ------------------------------------------------------------------------------------------------ run
def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    from swing_engine.data.b5_fundamentals import _read_facts, event_values
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.fundamentals import EVENTS_TABLE, SPLITS_TABLE, _norm_ts, share_issuance_features
    from swing_engine.data.market_series import unzip_text
    from swing_engine.data.store import Store

    end = b11.WINDOWS["pooled"][1]
    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, b9.DATA_START, end)
        bars = bars.assign(day=_bar_days(bars["ts"]))
        closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
        opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
        dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
            index="day", columns="symbol", values="dv").reindex(closes.index)
        delist = delisting_returns(store)
        filings, splits = store.read_table(EVENTS_TABLE), store.read_table(SPLITS_TABLE)
        facts = _read_facts(store, sorted(set(filings["symbol"].astype(str).str.upper())))
        replica = b9.momentum_orders(closes, b9.mcap_function(store, bars, closes),
                                     [d for d in trading_days(b9.DATA_START, end) if d in closes.index])
    vals = event_values(facts, filings, splits)
    vals = vals.assign(avail=_norm_ts(vals["avail_ts"]).dt.date).dropna(subset=["avail"]).sort_values("avail", kind="mergesort")
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    idx = {d: i for i, d in enumerate(closes.index)}
    hist = closes.notna().cumsum()
    rets = closes.pct_change(fill_method=None)
    cache: dict[date, pd.DataFrame] = {}

    def snap_at(t: date) -> pd.DataFrame:
        if t in cache:
            return cache[t]
        i = idx[t]
        rows = bars.loc[bars["day"] == t, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        s = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy(),
                          "nsi": f["net_share_issuance"].to_numpy()}, index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:t].tail(b9.DV_SESSIONS).median().reindex(s.index)
        s = s.loc[(s["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv) & (s["close_as_traded"] >= MIN_CLOSE)
                  & (hist.iloc[i].reindex(s.index) >= MIN_HISTORY)]
        s = s.loc[s["mcap_pit"].sort_values(ascending=False, kind="mergesort").index[:TOP]]
        names = s.index
        vol = rets.iloc[i - MOM_SKIP - VOL_SESSIONS + 1:i - MOM_SKIP + 1][names].std(ddof=1)
        latest = vals.loc[vals["avail"] <= t].drop_duplicates("symbol", keep="last").set_index("symbol")
        equity = latest["equity"].reindex(names)
        s = s.assign(momentum=(closes.iloc[i - MOM_SKIP][names] / closes.iloc[i - MOM_LONG][names] - 1.0) / vol,
                     gp_assets=latest["gp_assets"].reindex(names), net_repurchase=-s["nsi"],
                     book_to_market=(equity / s["mcap_pit"]).where(equity > 0))
        cache[t] = s
        return s

    plans = {COMPOSITE: composite_orders(closes, snap_at, sessions)}
    singles = {sig: composite_orders(closes, snap_at, sessions, use=(sig,)) for sig in SIGNALS}
    universe = {d: (snap_at(t)["mcap_pit"] / snap_at(t)["mcap_pit"].sum()) for d, t in
                ((sessions[sessions.index(t) + 1], t) for t in sorted(cache))}
    traded_names = {s for p in [*plans.values(), *singles.values(), replica, universe] for w in p.values() for s in w.index}
    costs = cost_table(bars.loc[bars["symbol"].isin(sorted(traded_names | {MARKET, BILL}))]).pivot(
        index="as_of", columns="symbol", values="cost_bps")
    pooled = b11.WINDOWS["pooled"]
    base_book = b11.book_for(replica, opens, closes, costs, delist, *pooled)
    plans[SCALED], exposure = scaled_orders(replica, base_book["ret"], closes, sessions)
    if counts_only:
        for card, orders in plans.items():
            sizes = [len(set(w.index) - {MARKET, BILL}) for d, w in orders.items() if d != sessions[0]]
            print(card, "orders", len(orders), "first after SPY", min(d for d in orders if d != sessions[0]),
                  "names min/median/max", min(sizes), int(np.median(sizes)), max(sizes), flush=True)
        e = exposure.dropna()
        print(SCALED, "exposure mean", round(float(e.mean()), 2), "share of days below 1", round(float((e < 1).mean()), 2),
              "changes", int((e.diff().abs() > 0).sum()), flush=True)
        return {}
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[BILL].pct_change(fill_method=None)
    results = {card: {w: b9.grade(b11.book_for(orders, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
                      for w, (lo, hi) in b11.WINDOWS.items()} for card, orders in plans.items()}
    # descriptive
    extra = ["## Descriptive (not part of the verdicts)", "", "| book | window | return/yr | deepest drop | worst month | "
             "alpha/yr | alpha t |", "|---|---|---|---|---|---|---|"]
    monthly: dict[str, pd.Series] = {}
    for name, orders in [*((f"composite, {s} only", o) for s, o in singles.items()),
                         ("the universe cap-weighted (monthly)", universe), ("batch 9 replica, unscaled", replica)]:
        book = b11.book_for(orders, opens, closes, costs, delist, *pooled)
        g = b9.grade(book, spy, N_TRIALS, rf)
        extra.append(f"| {name} | pooled | {b9._pct(g['stats']['cagr'])} | {b9._pct(-g['stats']['max_dd'])} | "
                     f"{b9._pct(g['stats']['worst_month'])} | {b9._pct(g['vs'].get('alpha_ann', math.nan))} | "
                     f"{g['vs'].get('alpha_t', math.nan):.2f} |")
        monthly[name] = (1.0 + book["ret"]).groupby([d.strftime("%Y-%m") for d in book.index]).prod() - 1.0
    uni = monthly["the universe cap-weighted (monthly)"]
    tmu = pd.DataFrame({s: monthly[f"composite, {s} only"] - uni for s in SIGNALS}).dropna()
    extra += ["", "Pairwise correlations of the four one-signal books' monthly returns minus the universe's:", "",
              "| | " + " | ".join(SIGNALS) + " |", "|---|" + "---|" * len(SIGNALS),
              *[f"| {a} | " + " | ".join(f"{tmu[a].corr(tmu[b]):.2f}" for b in SIGNALS) + " |" for a in SIGNALS]]
    e = exposure.loc[pooled[0]:pooled[1]].dropna()
    extra += ["", f"`{SCALED}`: average exposure {e.mean():.2f}, below 1.0 on {(e < 1).mean():.0%} of sessions; worst month "
              f"{b9._pct(results[SCALED]['pooled']['stats']['worst_month'])} vs the unscaled replica's "
              f"{b9._pct(b9.grade(base_book, spy, N_TRIALS, rf)['stats']['worst_month'])} (pooled window).", ""]
    spy_m = (1.0 + spy.loc[pooled[0]:pooled[1]]).groupby([d.strftime("%Y-%m") for d in spy.loc[pooled[0]:pooled[1]].index]).prod() - 1.0
    ours = 0.5 * (monthly["composite, momentum only"] + monthly["composite, gp_assets only"]) - spy_m
    texts = {k: unzip_text((FRENCH_DIR / v).read_bytes()) for k, v in FRENCH_FILES.items()}
    premise_lines, _premise = premise_check(texts, ours)
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        for card in (COMPOSITE, SCALED):
            log_trial(card, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                             "n_trials": N_TRIALS}, {**results[card]["pooled"]["stats"], **results[card]["pooled"]["vs"]},
                      trials_path, tags=[TAG], notes=f"pre-registered batch 14 card; verdict "
                                                      f"{b11.verdict(results[card], N_TRIALS)[1]}")
    lines = ["# Batch 14 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b14_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Momentum family trials {N_TRIALS}, bar alpha t >= "
             f"{alpha_t_critical(N_TRIALS):.3f}.", ""]
    for card in (COMPOSITE, SCALED):
        res = results[card]
        routes, word = b11.verdict(res, N_TRIALS)
        lines += [f"## `{card}`: {word}", "", f"Route 1 (both halves): {'met' if routes[0] else 'not met'}. Route 2 "
                  f"(pooled, alpha > 0 in each half): {'met' if routes[1] else 'not met'}.", "",
                  "| window | from | book | return/yr | deepest drop | worst month | months up | Sharpe | haircut SR | "
                  "alpha/yr | alpha t | beta | turnover/yr | costs/yr |", "|" + "---|" * 14]
        for w, r in res.items():
            for label, s in (("book", r["stats"]), ("SPY", r["spy_stats"])):
                vs = r["vs"] if label == "book" else {}
                tail = (f"{s['haircut_sharpe']:.2f} | {b9._pct(vs.get('alpha_ann', math.nan))} | "
                        f"{vs.get('alpha_t', math.nan):.2f} | {vs.get('beta', math.nan):.2f} | "
                        f"{b9._pct(r['turnover_ann'], '.0%')} | {b9._pct(r['cost_ann'], '.2%')} |") if label == "book" else "| | | | | |"
                lines.append(f"| {w} | {r['start']} | {label} | {b9._pct(s['cagr'])} | {b9._pct(-s['max_dd'])} | "
                             f"{b9._pct(s['worst_month'])} | {b9._pct(s['months_up'], '.0%')} | {s['sharpe']:.2f} | " + tail)
        lines.append("")
    lines += [*premise_lines, *extra, "", "## Verdicts",
              *[f"- **{c}**: {b11.verdict(results[c], N_TRIALS)[1]}" for c in (COMPOSITE, SCALED)]]
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return results


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts only, no graded simulation")
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out, counts_only=args.counts_only)


if __name__ == "__main__":
    main()
