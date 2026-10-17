"""Intraday lane, round 2: two published intraday momentum rules on SPY, QQQ, IWM (1-minute bars).

The spec is ``docs/preregistration/2026-10-13-intraday-round2.md``; this module implements it and nothing else.
Every place the spec left a choice open is listed in ``READINGS`` (printed in the results file). Run once::

    uv run python -m swing_engine.research.intraday_momentum --settings config/live.yaml

Shape: ``split_days`` (one symbol's regular-hours minutes -> one ``Day`` per session), ``noise_area_trades`` and
``first_half_hour_trades`` (pure: one day -> its trades), ``simulate`` (a symbol's days in order, carrying the
14-session ``sigma`` and the previous close), ``grade`` and ``render``.

No look-ahead: a decision at minute ``k`` reads only bars that ended at or before ``k`` and sessions before today;
the fill is the open of the bar that starts at ``k``.
"""
from __future__ import annotations

import argparse
import math
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.data.calendar import trading_days
from swing_engine.data.intraday import TABLE, _bounds, _utc
from swing_engine.research.metrics import haircut_sharpe
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-13-intraday-round2.md"
OUT = "docs/preregistration/2026-10-13-intraday-round2-results.md"
DATA_DIR = "data/research/intraday_round2"
TAG = "intraday-round2"

CARD_NOISE, CARD_FHH = "noise_area_momentum", "first_half_hour_momentum"
CARDS = (CARD_NOISE, CARD_FHH)
SYMBOLS = ("SPY", "QQQ", "IWM")
SIGMA_DAYS = 14  # sessions averaged into the noise band (Zarattini, Aziz & Barbon 2024)
VOL_MULTIPLIER = 1.0
CHECK_STEP = 30  # minutes: decisions at HH:00 and HH:30
FIRST_CHECK = 30  # minutes after the open: 10:00
LAST_CHECK_BEFORE_CLOSE = 30  # minutes: 15:30 on a normal day
FULL_SESSION = 390  # minutes, 09:30-16:00
MAX_OPEN_DELAY = 1  # a day whose first regular bar opens after 09:31 is skipped
COST_BPS_PER_SIDE = 1.0  # the round-1 constant for SPY, QQQ, IWM
PAPER_COST_BPS_PER_SIDE = 0.1  # the paper's $0.0045 a share on SPY, descriptive only
BPS = 1e4
SESSIONS_PER_YEAR = 252
WINDOWS: dict[str, tuple[date, date]] = {"A": (date(2016, 1, 1), date(2023, 12, 31)),
                                         "B": (date(2024, 1, 1), date(2026, 10, 9))}
N_GROUP_TRIALS = 4  # 2 cards x 2 windows
MIN_SYMBOLS_POSITIVE_B = 2  # pass rule 3
TRADE_COLUMNS = ["card", "symbol", "day", "side", "entry_min", "entry", "exit_min", "exit", "gross"]

READINGS: tuple[str, ...] = (
    "Minutes are counted from the session open in the NYSE calendar. A check at minute k reads the close of the last "
    "bar that started before k; the fill is the open of the bar that starts at k, or of the next bar that exists "
    "when that minute has no trade.",
    "sigma for a check time is the plain mean of |P / Open - 1| over the 14 most recent earlier sessions of the same "
    "symbol that reached that check time and were not skipped. With fewer than 14 the target position is 0.",
    "A skipped symbol-day (first regular bar after 09:31, or no previous session) trades nothing and adds nothing to "
    "sigma; its last close is still the next day's previous close.",
    "VWAP uses (high + low + close) / 3 x volume of the regular bars that started before the check minute.",
    "Card 1 holds a position only while the half-hourly check keeps it: +1 above max(UB, VWAP), -1 below "
    "min(LB, VWAP), flat otherwise. A flip is two trades at the same fill price.",
    "Card 2 needs a full 390-minute session; r1 uses the close of the last bar before 10:00.",
    "The session close fill is the close of the day's last regular bar.",
    "Cost per trade = 2 x the per-side rate (entry and exit), in return units; a symbol's daily net return is the sum "
    "of its trades' side x (exit / entry - 1) minus their costs.",
    "The card's daily return is the mean of the three symbols' daily net returns over every NYSE session of the "
    "window (0 for a symbol with no trade). Sharpe = mean / s.d. x sqrt(252); the haircut uses the window's length "
    "in calendar years.",
    "Max drawdown is on the cumulative sum of daily returns (no compounding, as the returns are per unit sleeve).",
    "Alpha and beta: OLS of the card's daily net return on SPY's close-to-close return from the regular-hours "
    "minutes, over the window's sessions.",
)


@dataclass(frozen=True)
class Day:
    day: date
    m: np.ndarray  # minutes from the session open to each bar's own open
    o: np.ndarray
    h: np.ndarray
    lo: np.ndarray
    c: np.ndarray
    v: np.ndarray
    length: int  # session length in minutes (390; 210 on an early close)

    def price_at(self, k: int) -> float:
        """Close of the last bar that ended at or before minute ``k`` (NaN before the first bar)."""
        i = int(np.searchsorted(self.m, k, side="left")) - 1
        return float(self.c[i]) if i >= 0 else math.nan

    def open_at(self, k: int) -> float:
        """Open of the bar that starts at minute ``k``, else of the next bar (the last close if none)."""
        i = int(np.searchsorted(self.m, k, side="left"))
        return float(self.o[i]) if i < len(self.m) else float(self.c[-1])

    def vwap_at(self, k: int) -> float:
        i = int(np.searchsorted(self.m, k, side="left"))
        vol = self.v[:i].sum()
        return float(((self.h[:i] + self.lo[:i] + self.c[:i]) / 3.0 * self.v[:i]).sum() / vol) if vol > 0 else math.nan

    def checks(self) -> range:
        return range(FIRST_CHECK, self.length - LAST_CHECK_BEFORE_CLOSE + 1, CHECK_STEP)


def split_days(bars_1m: pd.DataFrame) -> list[Day]:
    """Regular-hours rows of one symbol's ``bars_1m`` -> sessions in date order."""
    b = bars_1m.loc[bars_1m["session"] == "rth"].sort_values("ts")
    if b.empty:
        return []
    ts = _utc(b["ts"])
    day, open_, close = _bounds(ts)
    minute = ((ts - open_) / pd.Timedelta(minutes=1)).round().astype(int).to_numpy()
    length = ((close - open_) / pd.Timedelta(minutes=1)).round().astype(int).to_numpy()
    cols = {k: b[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume")}
    out = []
    keys = day.dt.date.to_numpy()
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    for a, z in zip(starts, np.r_[starts[1:], len(keys)], strict=True):
        out.append(Day(keys[a], minute[a:z], cols["open"][a:z], cols["high"][a:z], cols["low"][a:z],
                       cols["close"][a:z], cols["volume"][a:z], int(length[a])))
    return out


def noise_area_trades(d: Day, prev_close: float, sigma: dict[int, float]) -> list[dict[str, Any]]:
    """Card 1 on one day. ``sigma``: check minute -> the 14-session mean move (missing = not enough history)."""
    trades: list[dict[str, Any]] = []
    pos, entry, entry_min = 0, math.nan, 0
    hi_ref, lo_ref = max(d.o[0], prev_close), min(d.o[0], prev_close)

    def close_trade(k: int, price: float) -> None:
        trades.append({"side": pos, "entry_min": entry_min, "entry": entry, "exit_min": k, "exit": price,
                       "gross": pos * (price / entry - 1.0)})

    for k in d.checks():
        s, p = sigma.get(k), d.price_at(k)
        target = 0
        if s is not None and math.isfinite(p):
            vwap = d.vwap_at(k)
            ub, lb = hi_ref * (1.0 + VOL_MULTIPLIER * s), lo_ref * (1.0 - VOL_MULTIPLIER * s)
            if p > max(ub, vwap):
                target = 1
            elif p < min(lb, vwap):
                target = -1
        if target != pos:
            fill = d.open_at(k)
            if pos:
                close_trade(k, fill)
            pos, entry, entry_min = target, fill, k
    if pos:
        close_trade(d.length, float(d.c[-1]))
    return trades


def first_half_hour_trades(d: Day, prev_close: float) -> list[dict[str, Any]]:
    """Card 2 on one day: the sign of the return from the previous close to 10:00, traded 15:30 to the close."""
    if d.length != FULL_SESSION:
        return []
    r1 = d.price_at(FIRST_CHECK) / prev_close - 1.0
    side = int(np.sign(r1)) if math.isfinite(r1) else 0
    if side == 0:
        return []
    k = FULL_SESSION - LAST_CHECK_BEFORE_CLOSE
    entry, exit_ = d.open_at(k), float(d.c[-1])
    return [{"side": side, "entry_min": k, "entry": entry, "exit_min": d.length, "exit": exit_,
             "gross": side * (exit_ / entry - 1.0)}]


def simulate(symbol: str, days: Sequence[Day]) -> list[dict[str, Any]]:
    """Both cards over one symbol's sessions in order."""
    history: dict[int, deque[float]] = {}
    out: list[dict[str, Any]] = []
    prev_close: float | None = None
    for d in days:
        if prev_close is not None and d.m[0] <= MAX_OPEN_DELAY:
            sigma = {k: float(np.mean(q)) for k, q in history.items() if len(q) == SIGMA_DAYS}
            for card, trades in ((CARD_NOISE, noise_area_trades(d, prev_close, sigma)),
                                 (CARD_FHH, first_half_hour_trades(d, prev_close))):
                out += [{"card": card, "symbol": symbol, "day": d.day, **t} for t in trades]
            for k in d.checks():  # today's moves are history only for later sessions
                p = d.price_at(k)
                if math.isfinite(p):
                    history.setdefault(k, deque(maxlen=SIGMA_DAYS)).append(abs(p / d.o[0] - 1.0))
        prev_close = float(d.c[-1])
    return out


# ============================================================================================== grading
def window_of(day: date) -> str | None:
    return next((w for w, (lo, hi) in WINDOWS.items() if lo <= day <= hi), None)


def daily_returns(trades: pd.DataFrame, card: str, window: str, cost_bps: float,
                  symbols: Sequence[str] = SYMBOLS) -> pd.DataFrame:
    """Sessions of ``window`` x symbols: each symbol's daily net return (0 without a trade)."""
    lo, hi = WINDOWS[window]
    sessions = pd.Index(trading_days(lo, hi), name="day")
    t = trades.loc[trades["card"] == card]
    net = (t["gross"] - 2.0 * cost_bps / BPS).groupby([t["day"], t["symbol"]]).sum().unstack("symbol")
    return net.reindex(index=sessions, columns=list(symbols)).fillna(0.0)


def stats(daily: pd.Series, years: float, n_trials: int) -> dict[str, float]:
    mean, sd = float(daily.mean()), float(daily.std(ddof=1))
    sr = mean / sd * math.sqrt(SESSIONS_PER_YEAR) if sd > 0 else math.nan
    cum = daily.cumsum()
    return {"days": float(len(daily)), "mean_bp": mean * BPS, "ann_return": mean * SESSIONS_PER_YEAR,
            "ann_vol": sd * math.sqrt(SESSIONS_PER_YEAR), "sharpe": sr,
            "haircut_sharpe": haircut_sharpe(sr, years, n_trials)[0] if sr > 0 else sr,
            "max_dd": float((cum.cummax() - cum).max()) if len(cum) else math.nan}


def alpha_beta(daily: pd.Series, spy: pd.Series) -> tuple[float, float, float]:
    """(alpha per year, alpha t, beta) of ``daily`` on SPY's close-to-close return over the same sessions."""
    x = spy.reindex(daily.index)
    ok = x.notna()
    y, x = daily[ok].to_numpy(float), x[ok].to_numpy(float)
    if len(y) < 3 or x.std() == 0:
        return math.nan, math.nan, math.nan
    beta = float(np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1))
    alpha = float(y.mean() - beta * x.mean())
    resid = y - alpha - beta * x
    se = float(resid.std(ddof=2) / math.sqrt(len(y)))
    return alpha * SESSIONS_PER_YEAR, alpha / se if se > 0 else math.nan, beta


def grade(trades: pd.DataFrame, n_trials: int, spy: pd.Series, symbols: Sequence[str] = SYMBOLS) -> dict[str, dict]:
    """Per card: stats per window at the registered cost, the three pass rules and the verdict."""
    res: dict[str, dict] = {}
    for card in CARDS:
        st: dict[str, dict[str, float]] = {}
        per_symbol: dict[str, pd.Series] = {}
        for w, (lo, hi) in WINDOWS.items():
            by_symbol = daily_returns(trades, card, w, COST_BPS_PER_SIDE, symbols)
            daily = by_symbol.mean(axis=1)
            years = ((hi - lo).days + 1) / 365.25
            a, t, b = alpha_beta(daily, spy)
            tw = trades.loc[(trades["card"] == card) & (trades["day"].map(window_of) == w)]
            net = tw["gross"] - 2.0 * COST_BPS_PER_SIDE / BPS
            st[w] = {**stats(daily, years, n_trials), "trades": float(len(tw)),
                     "hit": float((net > 0).mean()) if len(tw) else math.nan,
                     "gross_bp_per_trade": float(tw["gross"].mean() * BPS) if len(tw) else math.nan,
                     "net_bp_per_trade": float(net.mean() * BPS) if len(tw) else math.nan,
                     "alpha": a, "alpha_t": t, "beta": b,
                     "sharpe_paper_cost": stats(daily_returns(trades, card, w, PAPER_COST_BPS_PER_SIDE, symbols)
                                                .mean(axis=1), years, n_trials)["sharpe"]}
            per_symbol[w] = by_symbol.mean() * BPS
        n_pos = int((per_symbol["B"] > 0).sum())
        rules = [all(s["mean_bp"] > 0 for s in st.values()), all(s["haircut_sharpe"] > 0 for s in st.values()),
                 n_pos >= MIN_SYMBOLS_POSITIVE_B]
        res[card] = {"stats": st, "per_symbol": per_symbol, "symbols_positive_b": n_pos, "rules": rules,
                     "verdict": "PASS" if all(rules) else "FAIL"}
    return res


# ============================================================================================== report
def _f(x: float, spec: str = "+.2f") -> str:
    return "-" if x is None or not math.isfinite(x) else format(x, spec)


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head), *("| " + " | ".join(r) + " |" for r in rows), ""]


def render(trades: pd.DataFrame, res: dict[str, dict], n_trials: int, n_before: int,
           symbols: Sequence[str] = SYMBOLS) -> list[str]:
    ok = lambda b: "ok" if b else "no"  # noqa: E731
    names = {"A": "A 2016-01..2023-12", "B": "B 2024-01..2026-10"}
    passed = [c for c in CARDS if res[c]["verdict"] == "PASS"]
    lines = [
        "# Intraday lane, round 2: results", "",
        f"Graded per `{SPEC}`. One run. Haircut over n_trials = {n_trials} ({n_before} logged before this group + "
        f"{N_GROUP_TRIALS}). Costs {COST_BPS_PER_SIDE:g} bp of traded notional per side. Returns are per unit of "
        f"sleeve, equal weight over {', '.join(symbols)}; no leverage, no compounding.", "",
        "## Verdict", "",
        ("**Passes: " + ", ".join(f"`{c}`" for c in passed) + ".**" if passed
         else "**Nothing passes.** No card meets the pre-registered rule."), "",
    ]
    rows = []
    for c in CARDS:
        a, b, r = res[c]["stats"]["A"], res[c]["stats"]["B"], res[c]["rules"]
        rows.append([f"`{c}`", f"**{res[c]['verdict']}**",
                     f"{_f(a['mean_bp'])} / {_f(b['mean_bp'])} ({ok(r[0])})",
                     f"{_f(a['haircut_sharpe'])} / {_f(b['haircut_sharpe'])} ({ok(r[1])})",
                     f"{res[c]['symbols_positive_b']} of {len(symbols)} ({ok(r[2])})"])
    lines += _table(["card", "verdict", "1. mean daily net return A / B, bp (> 0)", "2. haircut Sharpe A / B (> 0)",
                     f"3. symbols with net return > 0 in B (>= {MIN_SYMBOLS_POSITIVE_B})"], rows)
    lines += ["## Per card and window", "",
              "Daily figures are the equal-weight card. `Sharpe at 0.1 bp` is the same run at the paper's cost, "
              "descriptive only. Alpha and beta are against SPY's close-to-close return.", ""]
    rows = []
    for c in CARDS:
        for w in WINDOWS:
            s = res[c]["stats"][w]
            rows.append([f"`{c}`", names[w], f"{s['trades']:.0f}", _f(s["hit"], ".1%"), _f(s["gross_bp_per_trade"]),
                         _f(s["net_bp_per_trade"]), _f(s["mean_bp"]), _f(s["ann_return"], "+.1%"),
                         _f(s["ann_vol"], ".1%"), _f(s["sharpe"]), _f(s["haircut_sharpe"]), _f(s["max_dd"], ".1%"),
                         _f(s["alpha"], "+.1%"), _f(s["alpha_t"]), _f(s["beta"]), _f(s["sharpe_paper_cost"])])
    lines += _table(["card", "window", "trades", "hit ratio", "gross bp / trade", "net bp / trade",
                     "mean daily net bp", "net return / yr", "vol / yr", "Sharpe", "haircut Sharpe", "max drawdown",
                     "alpha / yr", "alpha t", "beta", "Sharpe at 0.1 bp"], rows)
    lines += ["## By symbol", "", "Mean daily net return in bp of the symbol's own sleeve. Rule 3 reads window B.", ""]
    lines += _table(["card", "window", *symbols],
                    [[f"`{c}`", names[w], *(_f(res[c]["per_symbol"][w][s]) for s in symbols)]
                     for c in CARDS for w in WINDOWS])
    lines += ["## By year and by direction", "", "Descriptive only. Net bp per trade at the registered cost.", ""]
    t = trades.assign(net_bp=(trades["gross"] - 2.0 * COST_BPS_PER_SIDE / BPS) * BPS,
                      year=[d.year for d in trades["day"]], direction=np.where(trades["side"] > 0, "long", "short"))
    for key in ("year", "direction"):
        g = t.groupby(["card", key])["net_bp"].agg(["count", "mean"]).reset_index()
        lines += _table(["card", key, "trades", "net bp / trade"],
                        [[f"`{r.card}`", str(getattr(r, key)), str(int(r.count)), _f(r.mean)] for r in g.itertuples()])
    lines += ["## How the spec was read", "",
              "Each point is a choice the spec left open, fixed in code before the run.", "",
              *(f"{n}. {text}" for n, text in enumerate(READINGS, 1)), ""]
    return lines


# ============================================================================================== runner
def spy_daily_returns(days: Sequence[Day]) -> pd.Series:
    close = pd.Series([float(d.c[-1]) for d in days], index=pd.Index([d.day for d in days], name="day"))
    return close.pct_change()


def run(store_path: str | Path, out: str | Path = OUT, data_dir: str | Path = DATA_DIR,
        trials_path: str | Path = DEFAULT_TRIALS_PATH, symbols: Sequence[str] = SYMBOLS) -> dict[str, dict]:
    """The whole pre-registered run: both cards on every symbol, parquet, the 4 trials (once), the markdown."""
    from swing_engine.data.store import Store

    t0 = time.time()
    rows: list[dict[str, Any]] = []
    spy = pd.Series(dtype=float)
    with Store(str(store_path), read_only=True) as store:
        for sym in symbols:
            days = split_days(store.read_table(TABLE, "symbol = ? AND session = 'rth'", [sym], order_by="ts"))
            if sym == "SPY":
                spy = spy_daily_returns(days)
            got = simulate(sym, days)
            rows += got
            print(f"{sym}: {len(days)} sessions, {len(got)} trades ({time.time() - t0:.0f}s)", flush=True)
    trades = pd.DataFrame(rows, columns=TRADE_COLUMNS)
    folder = Path(data_dir) if Path(data_dir).is_absolute() else ROOT / data_dir
    folder.mkdir(parents=True, exist_ok=True)
    trades.to_parquet(folder / "trades.parquet", index=False)

    logged = list(iter_trials(trials_path))
    mine = sum(TAG in (r.get("tags") or []) for r in logged)
    n_before = len(logged) - mine
    n_trials = n_before + N_GROUP_TRIALS
    res = grade(trades, n_trials, spy, symbols)
    if mine == 0:
        for card in CARDS:
            for w, (lo, hi) in WINDOWS.items():
                log_trial(card, {"window": w, "start": lo, "end": hi, "symbols": list(symbols), "spec": SPEC,
                                 "n_trials": n_trials}, res[card]["stats"][w], trials_path,
                          tags=[TAG, f"window-{w}"],
                          notes=f"pre-registered intraday round 2 card; verdict {res[card]['verdict']}")
    lines = render(trades, res, n_trials, n_before, symbols)
    out_path = Path(out) if Path(out).is_absolute() else ROOT / out
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"done in {time.time() - t0:.0f}s; trials {'logged' if mine == 0 else 'already logged, not repeated'}; "
          f"wrote {out_path}", flush=True)
    print("\n".join(lines[: lines.index("## Per card and window")]), flush=True)
    return res


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/live.yaml")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    run(ROOT / settings.data.intraday_store_path, args.out)


if __name__ == "__main__":
    main()
