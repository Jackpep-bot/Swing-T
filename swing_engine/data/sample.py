"""Deterministic synthetic universe for tests and the no-keys quick start.

~60 symbols (including SPY as the market) over six years of NYSE sessions. Each path is a geometric
Brownian motion driven by a market factor plus idiosyncratic regime segments (trending up, trending down,
sideways). A couple of names split, a couple delist (one bankruptcy-style collapse, one acquisition at a
premium), one IPOs late. Everything derives from `seed`, builds in well under a second and never touches
the network. Prices are split-adjusted (`adjusted=True`, the default), so `adj_close == close`.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from functools import cached_property
from typing import Any

import numpy as np
import pandas as pd
import structlog

from swing_engine.core.interfaces import BarProvider
from swing_engine.core.registry import register

from ._common import empty_bars, normalize_bars, normalize_symbols, session_ts
from .calendar import trading_days

log = structlog.get_logger(__name__)

SAMPLE_SEED = 42
SAMPLE_YEARS = 6
SAMPLE_END = date(2026, 9, 30)
MARKET_SYMBOL = "SPY"
TRADING_DAYS_PER_YEAR = 252

# (annual drift, annual volatility) per regime; segment lengths in sessions
STOCK_REGIMES: dict[str, tuple[float, float]] = {"up": (0.35, 0.28), "down": (-0.30, 0.38), "flat": (0.0, 0.22)}
MARKET_REGIMES: dict[str, tuple[float, float]] = {"up": (0.18, 0.13), "down": (-0.25, 0.30), "flat": (0.03, 0.11)}
REGIME_SEGMENT_SESSIONS = (60, 250)
BETA_RANGE = (0.5, 1.6)
START_PRICE_RANGE = (8.0, 250.0)  # log-uniform
MARKET_START_PRICE = 300.0
BASE_VOLUME_RANGE = (3e5, 2e7)  # log-uniform shares/day
MARKET_BASE_VOLUME = 8e7
GAP_VOL_FRACTION = 0.35  # overnight gap sigma as a fraction of daily sigma
RANGE_VOL_FRACTION = 0.6  # intraday wick sigma as a fraction of daily sigma
VOLUME_NOISE_SIGMA = 0.45
VOLUME_MOVE_SENSITIVITY = 2.5  # volume multiplier per sigma of absolute return
MIN_PRICE = 0.01

SPLITS: dict[str, list[tuple[date, int]]] = {  # symbol -> [(ex_date, new shares per old share)]
    "NVTX": [(date(2024, 6, 10), 10)],
    "TSLX": [(date(2022, 8, 25), 3)],
}
DELISTINGS: dict[str, tuple[str, date]] = {  # symbol -> (reason, last session on or before)
    "BNKR": ("bankruptcy", date(2024, 3, 15)),
    "ACQD": ("acquired", date(2025, 7, 1)),
}
BANKRUPTCY_COLLAPSE_SESSIONS = 120
BANKRUPTCY_DAILY_DRIFT = -0.04
ACQUISITION_PREMIUM = 0.30
ACQUISITION_QUIET_SESSIONS = 60
ACQUISITION_QUIET_VOL = 0.002
LATE_IPOS: dict[str, date] = {"IPOX": date(2024, 9, 16)}

SECTORS = ["Technology", "Health Care", "Financials", "Energy", "Industrials", "Consumer", "Materials", "Utilities"]
EXCHANGES = ["XNAS", "XNYS"]

SAMPLE_STOCKS: list[str] = [
    "ACME", "BLUE", "CRST", "DUNE", "ECHO", "FJRD", "GLXY", "HRBR", "IRON", "JUNO",
    "KITE", "LUMN", "MRDN", "NOVA", "ORCA", "PLNT", "QUAR", "RVER", "SOLR", "TIDE",
    "UMBR", "VLTA", "WREN", "XENO", "YARD", "ZEPH", "ARBR", "BRGE", "CNDL", "DRFT",
    "EMBR", "FLNT", "GRNT", "HLIX", "INDG", "JVLN", "KRNL", "LGCY", "MGMA", "NMBS",
    "OPAL", "PRSM", "QNTM", "RDAR", "STRM", "TRRA", "ULTR", "VRTX", "WLDR", "XCEL",
    "YLLW", "ZNTH", "AMBR", "BSLT", "NVTX", "TSLX", "BNKR", "ACQD", "IPOX",
]


def _log_uniform(rng: np.random.Generator, lo: float, hi: float) -> float:
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


def _regime_path(rng: np.random.Generator, n: int, regimes: dict[str, tuple[float, float]]) -> tuple[np.ndarray, np.ndarray]:
    """Per-session (daily drift, daily sigma) arrays built from random regime segments."""
    names = list(regimes)
    mu = np.empty(n)
    sigma = np.empty(n)
    i = 0
    while i < n:
        length = int(rng.integers(REGIME_SEGMENT_SESSIONS[0], REGIME_SEGMENT_SESSIONS[1] + 1))
        name = names[int(rng.integers(len(names)))]
        annual_mu, annual_sigma = regimes[name]
        mu[i : i + length] = annual_mu / TRADING_DAYS_PER_YEAR
        sigma[i : i + length] = annual_sigma / np.sqrt(TRADING_DAYS_PER_YEAR)
        i += length
    return mu, sigma


def _ohlcv(
    rng: np.random.Generator, close: np.ndarray, sigma: np.ndarray, ret: np.ndarray, base_volume: float
) -> dict[str, np.ndarray]:
    n = len(close)
    prev_close = np.concatenate([[close[0] / np.exp(ret[0])], close[:-1]])
    gap = rng.normal(0.0, 1.0, n) * sigma * GAP_VOL_FRACTION
    open_ = prev_close * np.exp(gap)
    wick_hi = np.abs(rng.normal(0.0, 1.0, n)) * sigma * RANGE_VOL_FRACTION
    wick_lo = np.abs(rng.normal(0.0, 1.0, n)) * sigma * RANGE_VOL_FRACTION
    high = np.maximum(open_, close) * np.exp(wick_hi)
    low = np.minimum(open_, close) * np.exp(-wick_lo)
    low = np.maximum(low, MIN_PRICE)
    move = np.abs(ret) / np.maximum(sigma, 1e-9)
    volume = base_volume * np.exp(rng.normal(0.0, VOLUME_NOISE_SIGMA, n)) * (1.0 + VOLUME_MOVE_SENSITIVITY * move)
    volume = np.floor(volume)
    vwap = (high + low + close) / 3.0
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume, "vwap": vwap}


@register("bar_provider", "sample")
class SampleProvider(BarProvider):
    name = "sample"

    def __init__(
        self,
        seed: int = SAMPLE_SEED,
        *,
        years: int = SAMPLE_YEARS,
        end: date = SAMPLE_END,
        symbols: Iterable[str] | None = None,
    ) -> None:
        self.seed = int(seed)
        self.years = int(years)
        self.end = end
        self.start = date(end.year - self.years, end.month, end.day)
        self.stocks = list(symbols) if symbols is not None else list(SAMPLE_STOCKS)

    @classmethod
    def from_settings(cls, settings: Any, secrets: Any = None) -> SampleProvider:
        years = max(SAMPLE_YEARS, int(getattr(settings.data, "history_years", SAMPLE_YEARS)))
        return cls(SAMPLE_SEED, years=years)

    # ------------------------------------------------------------------ generation
    @cached_property
    def sessions(self) -> list[date]:
        return trading_days(self.start, self.end)

    @cached_property
    def _built(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(adjusted bars, symbols) built once per instance."""
        sessions = self.sessions
        n = len(sessions)
        ts = pd.Series([session_ts(d) for d in sessions])
        session_index = {d: i for i, d in enumerate(sessions)}
        seeds = np.random.SeedSequence(self.seed).spawn(len(self.stocks) + 1)
        frames: list[pd.DataFrame] = []
        symbol_rows: list[dict[str, Any]] = []

        # market factor
        rng_m = np.random.default_rng(seeds[0])
        mu_m, sigma_m = _regime_path(rng_m, n, MARKET_REGIMES)
        ret_m = mu_m - 0.5 * sigma_m**2 + sigma_m * rng_m.normal(0.0, 1.0, n)
        close_m = MARKET_START_PRICE * np.exp(np.cumsum(ret_m))
        market = _ohlcv(rng_m, close_m, sigma_m, ret_m, MARKET_BASE_VOLUME)
        frames.append(pd.DataFrame({"symbol": MARKET_SYMBOL, "ts": ts, **market}))
        symbol_rows.append(
            {
                "symbol": MARKET_SYMBOL, "name": "Sample S&P 500 ETF", "exchange": "ARCX", "type": "ETF",
                "active": True, "listed_at": self.start, "delisted_at": None, "sector": "Index",
            }
        )

        for i, sym in enumerate(self.stocks):
            rng = np.random.default_rng(seeds[i + 1])
            beta = float(rng.uniform(*BETA_RANGE))
            mu, sigma = _regime_path(rng, n, STOCK_REGIMES)
            eps = rng.normal(0.0, 1.0, n)
            ret = beta * ret_m + mu - 0.5 * sigma**2 + sigma * eps
            first = 0
            last = n - 1
            delisted_at: date | None = None
            if sym in LATE_IPOS:
                first = max(session_index.get(LATE_IPOS[sym], 0), 0)
            if sym in DELISTINGS:
                reason, last_day = DELISTINGS[sym]
                last = max(idx for d, idx in session_index.items() if d <= last_day)
                delisted_at = sessions[last]
                if reason == "bankruptcy":
                    lo = max(first, last - BANKRUPTCY_COLLAPSE_SESSIONS)
                    ret[lo : last + 1] += BANKRUPTCY_DAILY_DRIFT
                else:
                    lo = max(first, last - ACQUISITION_QUIET_SESSIONS)
                    ret[lo] += np.log1p(ACQUISITION_PREMIUM)
                    ret[lo + 1 : last + 1] = ACQUISITION_QUIET_VOL * eps[lo + 1 : last + 1]
                    sigma[lo + 1 : last + 1] = ACQUISITION_QUIET_VOL
            p0 = _log_uniform(rng, *START_PRICE_RANGE)
            close = p0 * np.exp(np.cumsum(ret))
            base_volume = _log_uniform(rng, *BASE_VOLUME_RANGE)
            bars = _ohlcv(rng, close, sigma, ret, base_volume)
            frame = pd.DataFrame({"symbol": sym, "ts": ts, **bars}).iloc[first : last + 1]
            frames.append(frame)
            symbol_rows.append(
                {
                    "symbol": sym, "name": f"{sym.title()} Corp", "exchange": EXCHANGES[i % len(EXCHANGES)],
                    "type": "CS", "active": delisted_at is None, "listed_at": sessions[first],
                    "delisted_at": delisted_at, "sector": SECTORS[i % len(SECTORS)],
                }
            )

        bars = pd.concat(frames, ignore_index=True)
        bars["adj_close"] = bars["close"]
        return normalize_bars(bars), normalize_symbols(pd.DataFrame(symbol_rows))

    # ------------------------------------------------------------------ reference data
    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        syms = self._built[1]
        if not include_delisted:
            syms = syms[syms["active"]]
        return syms.reset_index(drop=True)

    def splits(self) -> pd.DataFrame:
        rows = [
            {"symbol": s, "ex_date": d, "split_from": 1, "split_to": r, "ratio": float(r)}
            for s, events in SPLITS.items()
            if s in self.stocks
            for d, r in events
        ]
        return pd.DataFrame(rows, columns=["symbol", "ex_date", "split_from", "split_to", "ratio"])

    def delistings(self) -> pd.DataFrame:
        rows = [
            {"symbol": s, "reason": reason, "delisted_at": d}
            for s, (reason, d) in DELISTINGS.items()
            if s in self.stocks
        ]
        return pd.DataFrame(rows, columns=["symbol", "reason", "delisted_at"])

    # ------------------------------------------------------------------ bars
    def daily_bars(
        self, symbols: Iterable[str], start: date, end: date, *, adjusted: bool = True
    ) -> pd.DataFrame:
        wanted = {s.upper() for s in symbols}
        bars = self._built[0]
        frame = bars[bars["symbol"].isin(wanted)]
        frame = frame[(frame["ts"] >= session_ts(start)) & (frame["ts"] <= session_ts(end))]
        if frame.empty:
            return empty_bars()
        frame = frame.copy()
        if not adjusted:
            frame = self._unadjust(frame)
        return frame.reset_index(drop=True)

    def _unadjust(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Undo split adjustment: before the ex-date, raw prices were `ratio`x higher, volume `ratio`x lower."""
        price_cols = ["open", "high", "low", "close", "vwap"]
        for sym, events in SPLITS.items():
            for ex_date, ratio in events:
                mask = (frame["symbol"] == sym) & (frame["ts"] < session_ts(ex_date))
                frame.loc[mask, price_cols] = frame.loc[mask, price_cols] * ratio
                frame.loc[mask, "volume"] = np.floor(frame.loc[mask, "volume"] / ratio)
        return frame

    def all_bars(self) -> pd.DataFrame:
        """Every adjusted bar in the universe (convenience for tests and quick starts)."""
        return self._built[0].copy()


__all__ = ["SampleProvider", "SAMPLE_STOCKS", "MARKET_SYMBOL", "SPLITS", "DELISTINGS", "LATE_IPOS"]
