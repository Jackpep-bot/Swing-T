"""Where does each strategy's gross edge come from? A diagnostic over the replay shadow ledgers (no trial logged).

Per strategy, research window and horizon ``h`` (leaderboard's signal set: executable, traded, planned-risk R):

* market component: SPY's return from the open of the signal's entry session to the close of its ``h``-session
  exit date, in the signal's R units (``spy_return x entry / (entry - stop)``); market-adjusted R = gross - that;
  market-adjusted net R also subtracts ``cards.cost_r``; block t as in ``leaderboard.edge_stats``;
* exit mix at 20 sessions (stop / target / time shares, mean MFE and MAE in R);
* concentration at 20 sessions: share of the total gross R made by the top 5% of signals, mean gross R by
  price and by dollar-volume bucket.

Run::

    uv run python -m swing_engine.research.attribution --settings config/replay_r2.yaml \
        --store data/live/replay_r1.duckdb --store data/live/replay_news.duckdb --out docs/attribution.md
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from swing_engine.research.cards import ROOT, WINDOWS, Window, cost_r, executable, with_costs
from swing_engine.research.leaderboard import MIN_BLOCKS, _sessions
from swing_engine.research.shadow import (
    DEFAULT_HORIZONS,
    REPLAY_SHADOW_TABLE,
    TRADE_HITS,
    Hit,
    horizon_column,
)

MARKET_SYMBOL = "SPY"
MIX_HORIZON = 20  # exit mix and concentration are reported at the longest graded horizon
TOP_SHARE = 0.05
PRICE_EDGES = (10.0, 50.0)  # $ per share: <$10, $10-50, >$50
LIQUIDITY_EDGES = (20e6, 100e6)  # 20-day mean dollar volume: <$20M, $20-100M, >$100M
PRICE_LABELS = ("<$10", "$10-50", ">$50")
LIQUIDITY_LABELS = ("<$20M", "$20-100M", ">$100M")
TOP_ROWS, BOTTOM_ROWS = 25, 10
NOTABLE_T = 2.0
DAILY_COLUMNS = ("strategy", "as_of", "horizon", "n", "gross", "mkt", "cost")
SIGNAL_COLUMNS = ("strategy", "as_of", "r", "hit", "mfe", "mae", "entry", "dollar_volume")
_BASE = ("strategy", "symbol", "as_of", "entry", "stop", "entry_price", "entry_date")
_PER_HORIZON = ("hit", "result_r", "mfe_r", "mae_r", "exit_date")


# ----------------------------------------------------------------------------------------------- per signal


def market_r(frame: pd.DataFrame, spy: pd.DataFrame, horizon: int) -> pd.Series:
    """SPY's return over each signal's holding span in the signal's R units. ``spy``: ``open``/``close`` indexed
    by session date. The span runs from the open of ``entry_date`` (the session after ``as_of`` when missing) to
    the close of ``exit_date_<h>d``; NaN when either session has no SPY bar or the stop is not below the entry."""
    sessions = pd.DatetimeIndex(pd.to_datetime(spy.index))
    opens = pd.Series(spy["open"].to_numpy(float), index=sessions)
    closes = pd.Series(spy["close"].to_numpy(float), index=sessions)
    as_of = pd.to_datetime(frame["as_of"])
    nxt = np.searchsorted(sessions.values, as_of.values.astype("datetime64[ns]"), side="right")
    after = pd.Series(sessions.append(pd.DatetimeIndex([pd.NaT]))[np.minimum(nxt, len(sessions))], index=frame.index)
    start = pd.to_datetime(frame["entry_date"]).fillna(after) if "entry_date" in frame.columns else after
    end = pd.to_datetime(frame[horizon_column("exit_date", horizon)])
    ret = end.map(closes).to_numpy(float) / start.map(opens).to_numpy(float) - 1.0
    entry, stop = frame["entry"].astype(float), frame["stop"].astype(float)
    return pd.Series(ret, index=frame.index) * entry / (entry - stop).where(entry > stop)


def chunk_stats(frame: pd.DataFrame, spy: pd.DataFrame,
                horizons: Sequence[int] = DEFAULT_HORIZONS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One ledger chunk -> (``DAILY_COLUMNS`` sums per strategy-day and horizon, ``SIGNAL_COLUMNS`` per traded
    signal at ``MIX_HORIZON``). Signals without a SPY bar on either end of the span are left out of the sums."""
    frame = executable(frame)
    daily, signals = [], pd.DataFrame(columns=list(SIGNAL_COLUMNS))
    if frame.empty:
        return pd.DataFrame(columns=list(DAILY_COLUMNS)), signals
    cost = cost_r(frame).fillna(0.0)
    for h in horizons:
        hit, r = horizon_column("hit", h), horizon_column("result_r", h)
        if hit not in frame.columns:
            continue
        traded = frame[hit].astype(str).isin(TRADE_HITS) & frame[r].notna()
        if h == MIX_HORIZON:
            t = frame.loc[traded]
            signals = pd.DataFrame({
                "strategy": t["strategy"].astype(str), "as_of": pd.to_datetime(t["as_of"]),
                "r": t[r].astype("float32"), "hit": t[hit].astype(str),
                "mfe": t[horizon_column("mfe_r", h)].astype("float32"),
                "mae": t[horizon_column("mae_r", h)].astype("float32"), "entry": t["entry"].astype("float32"),
                "dollar_volume": (t["dollar_volume"] if "dollar_volume" in t.columns else np.nan),
            }).astype({"strategy": "category", "hit": "category", "dollar_volume": "float32"})
        mkt = market_r(frame, spy, h)
        traded &= mkt.notna()
        vals = pd.DataFrame({"gross": frame.loc[traded, r].astype(float), "mkt": mkt[traded], "cost": cost[traded]})
        keys = [frame.loc[traded, "strategy"].astype(str), pd.to_datetime(frame.loc[traded, "as_of"])]
        g = vals.groupby(keys).sum()
        g["n"] = vals.groupby(keys).size()
        daily.append(g.reset_index().assign(horizon=int(h)))
    if not daily:
        return pd.DataFrame(columns=list(DAILY_COLUMNS)), signals
    return pd.concat(daily, ignore_index=True)[list(DAILY_COLUMNS)], signals


# ----------------------------------------------------------------------------------------------- ledgers


def load(paths: Sequence[Path], cost_store: Path,
         horizons: Sequence[int] = DEFAULT_HORIZONS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`chunk_stats` over the replay ledgers of ``paths``, one store and one calendar year at a time (read-only).
    A strategy-day present in several stores is taken from the last one listed (as reality_check.load_daily)."""
    import duckdb

    from swing_engine.data.store import Store

    store = Store(str(cost_store), read_only=True)
    try:
        bars = store.read_bars([MARKET_SYMBOL])
    finally:
        store.close()
    spy = bars.assign(d=pd.to_datetime(bars["ts"]).dt.date).set_index("d")[["open", "close"]].sort_index()

    def table_of(con) -> bool:  # noqa: ANN001
        return REPLAY_SHADOW_TABLE in {r[0] for r in con.execute("SHOW TABLES").fetchall()}

    owners = []
    for order, path in enumerate(paths):
        con = duckdb.connect(str(path), read_only=True)
        try:
            if table_of(con):
                owners.append(con.execute(f"SELECT DISTINCT strategy, as_of FROM {REPLAY_SHADOW_TABLE}").df()
                              .assign(_owner=order))
        finally:
            con.close()
    if not owners:
        return chunk_stats(pd.DataFrame(), spy, horizons)
    owner = pd.concat(owners, ignore_index=True).groupby(["strategy", "as_of"], as_index=False)["_owner"].max()
    owner["as_of"] = pd.to_datetime(owner["as_of"])

    wanted = [*_BASE, *(horizon_column(k, h) for h in horizons for k in _PER_HORIZON)]
    daily, signals = [], []
    for order, path in enumerate(paths):
        con = duckdb.connect(str(path), read_only=True)
        try:
            if not table_of(con):
                continue
            have = {r[0] for r in con.execute(f"DESCRIBE {REPLAY_SHADOW_TABLE}").fetchall()}
            cols = ", ".join(c for c in wanted if c in have)
            years = [r[0] for r in con.execute(
                f"SELECT DISTINCT year(as_of) FROM {REPLAY_SHADOW_TABLE} ORDER BY 1").fetchall()]
            for y in years:
                frame = con.execute(f"SELECT {cols} FROM {REPLAY_SHADOW_TABLE} WHERE year(as_of) = ?", [y]).df()
                frame["as_of"] = pd.to_datetime(frame["as_of"])
                frame = frame.merge(owner, on=["strategy", "as_of"], how="left")
                frame = frame.loc[frame["_owner"] == order].drop(columns="_owner")
                d, s = chunk_stats(with_costs(frame, cost_store), spy, horizons)
                daily.append(d)
                signals.append(s)
        finally:
            con.close()
    daily, signals = [d for d in daily if not d.empty], [s for s in signals if not s.empty]
    if not daily:
        return chunk_stats(pd.DataFrame(), spy, horizons)
    sig = pd.concat([s.astype({"strategy": str, "hit": str}) for s in signals], ignore_index=True)
    return pd.concat(daily, ignore_index=True), sig.astype({"strategy": "category", "hit": "category"})


# ----------------------------------------------------------------------------------------------- tables


def _in_window(dates: pd.Series, w: Window) -> pd.Series:
    d = pd.to_datetime(dates)
    return (d >= pd.Timestamp(w.start)) & (d <= pd.Timestamp(w.end))


def market_table(daily: pd.DataFrame, windows: Iterable[Window] = WINDOWS) -> pd.DataFrame:
    """One row per (strategy, window, horizon): ``n``, mean ``gross_r``, ``mkt_r``, ``adj_gross_r``,
    ``adj_net_r`` (per signal), ``blocks`` and the block ``t`` of the market-adjusted net R."""
    rows = []
    for w in windows:
        sub = daily.loc[_in_window(daily["as_of"], w)] if len(daily) else daily
        for (strat, h), g in sub.groupby(["strategy", "horizon"], observed=True) if len(sub) else []:
            n = float(g["n"].sum())
            adj_net = g["gross"] - g["mkt"] - g["cost"]
            block = _sessions(g["as_of"]) // int(h)
            means = adj_net.groupby(block).sum() / g["n"].groupby(block).sum()
            t = math.nan
            if len(means) >= MIN_BLOCKS and means.std(ddof=1) > 0:
                t = float(means.mean() / means.std(ddof=1) * math.sqrt(len(means)))
            rows.append({"strategy": strat, "window": w.start.year, "horizon": int(h), "n": n,
                         "gross_r": g["gross"].sum() / n, "mkt_r": g["mkt"].sum() / n,
                         "adj_gross_r": (g["gross"].sum() - g["mkt"].sum()) / n, "adj_net_r": adj_net.sum() / n,
                         "blocks": float(len(means)), "t": t})
    return pd.DataFrame(rows)


def exit_mix(signals: pd.DataFrame) -> dict[str, float]:
    """Shares of signals ending by stop, target and time (the rest delisted) and mean MFE / MAE in R."""
    hit = signals["hit"].astype(str)
    return {"stop": float((hit == Hit.STOP.value).mean()), "target": float((hit == Hit.TARGET.value).mean()),
            "time": float((hit == Hit.TIME.value).mean()), "mfe": float(signals["mfe"].astype(float).mean()),
            "mae": float(signals["mae"].astype(float).mean())}


def top_share(r: pd.Series, share: float = TOP_SHARE) -> float:
    """Share of the total gross R made by the best ``share`` of signals (rounded up); NaN when the total is <= 0."""
    r = np.sort(r.astype(float).dropna().to_numpy())[::-1]
    total = r.sum()
    return float(r[: math.ceil(len(r) * share)].sum() / total) if len(r) and total > 0 else math.nan


def bucket_means(signals: pd.DataFrame, column: str, edges: Sequence[float], labels: Sequence[str]) -> dict[str, float]:
    """Mean gross R per signal in each bucket of ``column`` (left-closed: a value on an edge goes up); NaN if empty."""
    bucket = pd.cut(signals[column].astype(float), [-math.inf, *edges, math.inf], labels=list(labels), right=False)
    means = signals["r"].astype(float).groupby(bucket, observed=False).mean()
    return {label: float(means.get(label, math.nan)) for label in labels}


def mix_table(signals: pd.DataFrame, windows: Iterable[Window] = WINDOWS) -> pd.DataFrame:
    """One row per (strategy, window): `exit_mix`, `top_share` and the price / liquidity `bucket_means`."""
    rows = []
    for w in windows:
        sub = signals.loc[_in_window(signals["as_of"], w)] if len(signals) else signals
        for strat, g in sub.groupby("strategy", observed=True) if len(sub) else []:
            rows.append({"strategy": str(strat), "window": w.start.year, "n20": float(len(g)), **exit_mix(g),
                         "top_share": top_share(g["r"]),
                         **bucket_means(g, "entry", PRICE_EDGES, PRICE_LABELS),
                         **bucket_means(g, "dollar_volume", LIQUIDITY_EDGES, LIQUIDITY_LABELS)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------- report


def _f(x: float | None, spec: str = "+.3f") -> str:
    return "-" if x is None or not math.isfinite(x) else format(x, spec)


def _says(market: pd.DataFrame, mix: pd.DataFrame, signals: pd.DataFrame, w: Window) -> list[str]:
    m = market.loc[(market["window"] == w.start.year) & (market["horizon"] == MIX_HORIZON)]
    x = mix.loc[mix["window"] == w.start.year]
    if m.empty or x.empty:
        return []
    pos = m.loc[m["gross_r"] > 0]
    sub = signals.loc[_in_window(signals["as_of"], w)]
    price = bucket_means(sub, "entry", PRICE_EDGES, PRICE_LABELS)
    liq = bucket_means(sub, "dollar_volume", LIQUIDITY_EDGES, LIQUIDITY_LABELS)
    med = x[["stop", "target", "time", "mfe", "mae", "top_share"]].median()
    return [
        f"- {w.start.year} window, {MIX_HORIZON}d: {len(pos)} of {len(m)} strategies have a positive gross R per "
        f"signal; {int((pos['adj_gross_r'] <= 0).sum())} of those {len(pos)} have a non-positive market-adjusted "
        f"gross R.",
        f"- {w.start.year}: median gross {_f(m['gross_r'].median())}R, median market component "
        f"{_f(m['mkt_r'].median())}R, median market-adjusted net {_f(m['adj_net_r'].median())}R; "
        f"{int((m['adj_net_r'] > 0).sum())} strategies have a positive market-adjusted net R, "
        f"{int((m['t'] > NOTABLE_T).sum())} with block t above {NOTABLE_T:g} and {int((m['t'] < -NOTABLE_T).sum())} "
        f"below -{NOTABLE_T:g} (no multiple-testing haircut applied here).",
        f"- {w.start.year}: the median strategy ends {_f(med['stop'] * 100, '.0f')}% of signals at the stop, "
        f"{_f(med['target'] * 100, '.0f')}% at the target and {_f(med['time'] * 100, '.0f')}% on time; median MFE "
        f"{_f(med['mfe'], '.2f')}R against median MAE {_f(med['mae'], '.2f')}R.",
        f"- {w.start.year}: among strategies with a positive total, the median share of gross R made by the top "
        f"{TOP_SHARE:.0%} of signals is {_f(med['top_share'] * 100, '.0f')}% (above 100% means the other "
        f"{1 - TOP_SHARE:.0%} lose money in total).",
        f"- {w.start.year}: pooled over every signal, mean gross R by price is "
        + ", ".join(f"{k} {_f(v)}" for k, v in price.items()) + "; by dollar volume "
        + ", ".join(f"{k} {_f(v)}" for k, v in liq.items()) + ".",
    ]


def render(market: pd.DataFrame, mix: pd.DataFrame, signals: pd.DataFrame,
           windows: Sequence[Window] = WINDOWS) -> str:
    lines = [
        "# Attribution: where each strategy's gross edge comes from",
        "",
        "Generated by `swing_engine.research.attribution` from the replay shadow ledgers. A diagnostic, not a "
        "strategy trial: nothing here is logged or haircut.",
        "",
        "Every strategy in the replay is long-only, so part of what a signal earns is simply the market going up "
        f"while it is held. For each signal this report takes {MARKET_SYMBOL}'s return over the same days (open of "
        "the entry session to the close of the exit date at that horizon), converts it into the signal's own R "
        "(return x entry / (entry - stop)) and subtracts it. What is left, the market-adjusted R, is what the "
        "stock did beyond the index. `mkt` is the market component, `adj gross` = gross - mkt, `adj net` also "
        "subtracts the per-stock round-trip cost used by the leaderboard, and `t` is the t-stat of adj net over "
        "non-overlapping blocks of the horizon. Caveats: the adjustment assumes a beta of 1 and uses unadjusted "
        f"{MARKET_SYMBOL} prices (dividends ignored); a signal stopped out early is still charged the market's "
        "move to the horizon exit date only if that is its recorded exit date; limit and stop entries fill "
        "intraday but are measured from the open.",
        "",
        f"The second table per window is at {MIX_HORIZON} sessions: how signals end (stop / target / time; the "
        "small remainder is delistings), the average best (MFE) and worst (MAE) excursion in R, the share of the "
        f"strategy's total gross R made by its best {TOP_SHARE:.0%} of signals (`-` when the total is not "
        "positive), and mean gross R per signal by share price and by 20-day dollar volume.",
    ]
    said: list[str] = []
    for w in windows:
        m = market.loc[market["window"] == w.start.year] if len(market) else market
        if m.empty:
            continue
        said += _says(market, mix, signals, w)
        best = m.sort_values("t", ascending=False, na_position="last").drop_duplicates("strategy")
        best = best.loc[best["t"].notna()]
        x = mix.loc[mix["window"] == w.start.year].set_index("strategy")
        lines += ["", f"## {w.start} .. {w.end} ({w.label})", "",
                  f"Best horizon per strategy by market-adjusted net t; {len(best)} strategies with at least "
                  f"{MIN_BLOCKS} blocks. R per signal."]
        parts = [(f"Top {TOP_ROWS}", best.head(TOP_ROWS))]
        if len(best) > TOP_ROWS:
            parts.append((f"Bottom {BOTTOM_ROWS}", best.iloc[TOP_ROWS:].tail(BOTTOM_ROWS)))
        for title, part in parts:
            lines += ["", f"### {title}: market attribution", "",
                      "| strategy | horizon | signals | gross R | mkt | adj gross | adj net | t |",
                      "|---|---|---|---|---|---|---|---|"]
            for r in part.itertuples():
                lines.append(f"| {r.strategy} | {r.horizon}d | {int(r.n)} | {_f(r.gross_r)} | {_f(r.mkt_r)} | "
                             f"{_f(r.adj_gross_r)} | {_f(r.adj_net_r)} | {_f(r.t, '.2f')} |")
            lines += ["", f"### {title}: exit mix and concentration at {MIX_HORIZON}d", "",
                      "| strategy | stop | target | time | MFE | MAE | top 5% share | "
                      + " | ".join((*PRICE_LABELS, *LIQUIDITY_LABELS)) + " |", "|---" * 13 + "|"]
            for strat in part["strategy"]:
                if strat not in x.index:
                    continue
                r = x.loc[strat]
                lines.append(f"| {strat} | {_f(r['stop'] * 100, '.0f')}% | {_f(r['target'] * 100, '.0f')}% | "
                             f"{_f(r['time'] * 100, '.0f')}% | {_f(r['mfe'], '.2f')} | {_f(r['mae'], '.2f')} | "
                             f"{_f(r['top_share'] * 100, '.0f')}% | "
                             + " | ".join(_f(r[k], "+.2f") for k in (*PRICE_LABELS, *LIQUIDITY_LABELS)) + " |")
    lines += ["", "## What this says", "", *said]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/replay.yaml")
    ap.add_argument("--store", action="append", default=[], help="extra replay store (repeatable)")
    ap.add_argument("--out", default="docs/attribution.md")
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    store_path = ROOT / settings.data.store_path
    daily, signals = load([store_path, *(ROOT / s for s in args.store)], store_path)
    market, mix = market_table(daily), mix_table(signals)
    (ROOT / args.out).write_text(render(market, mix, signals))
    print(f"{len(market)} market rows, {len(mix)} mix rows, {len(signals)} signals at {MIX_HORIZON}d -> {args.out}")
    return market, mix


if __name__ == "__main__":
    main()


__all__ = ["bucket_means", "chunk_stats", "exit_mix", "load", "market_r", "market_table", "mix_table", "render",
           "top_share"]
