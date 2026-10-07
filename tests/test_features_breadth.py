"""features.breadth: per-session market breadth (docs/methods/06-breadth-regime-filters.md C, D)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import breadth as br
from swing_engine.features.panel import build_panel
from tests.features_gbm import gbm_bars

NY = "America/New_York"


def _bars(symbol: str, closes, volumes, start: str = "2026-01-05") -> pd.DataFrame:
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    idx = pd.bdate_range(start, periods=len(c), tz=NY)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "ts": idx,
            "open": o,
            "high": np.maximum(o, c) * 1.001,
            "low": np.minimum(o, c) * 0.999,
            "close": c,
            "volume": np.asarray(volumes, dtype=float),
        }
    )


@pytest.fixture(scope="module")
def gbm_panel() -> pd.DataFrame:
    return build_panel(gbm_bars(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"], n_bars=320, seed=3))


@pytest.fixture(scope="module")
def gbm_breadth(gbm_panel: pd.DataFrame) -> pd.DataFrame:
    return br.market_breadth(gbm_panel)


def test_schema_index_and_dtypes(gbm_panel: pd.DataFrame, gbm_breadth: pd.DataFrame) -> None:
    out = gbm_breadth
    assert tuple(out.columns) == br.BREADTH_COLUMNS
    assert out.index.name == "session" and isinstance(out.index, pd.DatetimeIndex)
    assert out.index.tz is None and out.index.is_monotonic_increasing and out.index.is_unique
    assert len(out) == gbm_panel["ts"].nunique()
    assert (out["n_symbols"] == 6).all()
    for col in ("up4_count", "down4_count", "new_highs", "new_lows", "n_symbols"):
        assert out[col].dtype == np.int64
    pct = out[["pct_above_50", "pct_above_200"]].stack().dropna()
    assert ((pct >= 0) & (pct <= 100)).all()


def test_pct_above_matches_hand_computation(gbm_panel: pd.DataFrame, gbm_breadth: pd.DataFrame) -> None:
    day = gbm_panel["ts"].dt.tz_localize(None).dt.normalize()
    for window in (50, 200):
        col = f"sma_{window}"
        warm = gbm_panel[col].notna()
        expect = (gbm_panel["close"] > gbm_panel[col])[warm].groupby(day[warm]).mean() * 100.0
        got = gbm_breadth[f"pct_above_{window}"].dropna()
        pd.testing.assert_series_equal(
            got, expect, check_names=False, check_index_type=False, check_freq=False
        )
    # warm-up: no symbol has an sma_200 for the first 199 sessions
    assert gbm_breadth["pct_above_200"].iloc[:199].isna().all()
    assert gbm_breadth["pct_above_50"].iloc[49:].notna().all()


def test_up4_count_equals_burst_4pct_sum(gbm_panel: pd.DataFrame, gbm_breadth: pd.DataFrame) -> None:
    day = gbm_panel["ts"].dt.tz_localize(None).dt.normalize()
    expect = gbm_panel["burst_4pct"].fillna(0).groupby(day).sum().astype("int64")
    np.testing.assert_array_equal(gbm_breadth["up4_count"].to_numpy(), expect.to_numpy())


def test_four_percent_days_need_volume_expansion_and_floor() -> None:
    n = 12
    flat = np.full(n, 100.0)
    up = flat.copy()
    up[5:] = 105.0  # +5% on day 5
    down = flat.copy()
    down[7:] = 95.0  # -5% on day 7
    quiet_up = flat.copy()
    quiet_up[5:] = 105.0  # +5% on day 5 but volume falls
    thin_up = flat.copy()
    thin_up[5:] = 105.0  # +5% with rising volume below 100k shares
    vol = np.full(n, 1_000_000.0)
    vol_up5 = vol.copy()
    vol_up5[5] = 2_000_000.0
    vol_up7 = vol.copy()
    vol_up7[7] = 2_000_000.0
    vol_down5 = vol.copy()
    vol_down5[5] = 500_000.0
    thin = np.full(n, 50_000.0)
    thin[5] = 90_000.0
    bars = pd.concat(
        [
            _bars("UP", up, vol_up5),
            _bars("DN", down, vol_up7),
            _bars("QUIET", quiet_up, vol_down5),
            _bars("THIN", thin_up, thin),
        ],
        ignore_index=True,
    )
    out = br.market_breadth(bars)  # bare bars: features computed on the fly
    assert out["up4_count"].tolist() == [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    assert out["down4_count"].tolist() == [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]
    assert out["ratio_10d"].iloc[:9].isna().all()
    # window of sessions 0-9 holds one up and one down day; sessions 1-10 and 2-11 too
    assert out["ratio_10d"].iloc[9:].tolist() == [1.0, 1.0, 1.0]


def test_ratio_10d_floor_and_quiet_windows() -> None:
    up = pd.Series([0, 3, 0, 2, 0, 0, 0, 0, 0, 5, 0, 0])
    down = pd.Series([0] * 12)
    r = br.ratio_10d(up, down)
    assert r.iloc[:9].isna().all()
    assert r.iloc[9] == 10.0  # no decliner in the window: denominator floored at 1
    assert r.iloc[10] == 10.0 and r.iloc[11] == 7.0
    quiet = br.ratio_10d(pd.Series([0] * 12), pd.Series([0] * 12))
    assert quiet.isna().all(), "a window with no 4% move is undefined, not bearish"
    bear = br.ratio_10d(pd.Series([1] * 10), pd.Series([4] * 10))
    assert bear.iloc[-1] == pytest.approx(0.25)


def test_new_highs_and_lows() -> None:
    n = 300
    rising = 50.0 * np.exp(np.linspace(0.0, 0.5, n))
    falling = 80.0 * np.exp(np.linspace(0.0, -0.5, n))
    vol = np.full(n, 1_000_000.0)
    out = br.market_breadth(build_panel(pd.concat([_bars("UPP", rising, vol), _bars("DWN", falling, vol)])))
    assert (out["new_highs"].iloc[:251] == 0).all(), "52-week high needs 252 bars"
    assert (out["new_highs"].iloc[251:] == 1).all()
    assert (out["new_lows"].iloc[251:] == 1).all()


def test_point_in_time_truncation(gbm_panel: pd.DataFrame, gbm_breadth: pd.DataFrame) -> None:
    bars = gbm_bars(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"], n_bars=320, seed=3)
    cut = bars["ts"].sort_values().unique()[260]
    truncated = br.market_breadth(build_panel(bars.loc[bars["ts"] <= cut]))
    pd.testing.assert_frame_equal(truncated, gbm_breadth.loc[truncated.index])
    same_panel = br.market_breadth(gbm_panel.loc[gbm_panel["ts"] <= cut])
    pd.testing.assert_frame_equal(same_panel, truncated)


def test_bare_bars_match_panel(gbm_breadth: pd.DataFrame) -> None:
    bars = gbm_bars(["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"], n_bars=320, seed=3)
    pd.testing.assert_frame_equal(br.market_breadth(bars), gbm_breadth, check_exact=False, rtol=1e-9)


def test_exclude_population_and_late_listing(gbm_panel: pd.DataFrame) -> None:
    out = br.market_breadth(gbm_panel, exclude=("AAA", "BBB"))
    assert (out["n_symbols"] == 4).all()
    late = gbm_panel.loc[(gbm_panel["symbol"] != "FFF") | (gbm_panel.index % 320 >= 100)]
    counts = br.market_breadth(late)["n_symbols"]
    assert counts.iloc[0] == 5 and counts.iloc[-1] == 6


def test_duplicates_and_empty(gbm_panel: pd.DataFrame, gbm_breadth: pd.DataFrame) -> None:
    doubled = pd.concat([gbm_panel, gbm_panel.tail(3)], ignore_index=True)
    pd.testing.assert_frame_equal(br.market_breadth(doubled), gbm_breadth)
    empty = br.market_breadth(gbm_panel.iloc[0:0])
    assert empty.empty and tuple(empty.columns) == br.BREADTH_COLUMNS
    assert br.market_breadth(gbm_panel, exclude=gbm_panel["symbol"].unique()).empty
    with pytest.raises(ValueError, match="missing columns"):
        br.market_breadth(gbm_panel.drop(columns=["volume"]))


def test_breadth_as_of_lookup(gbm_breadth: pd.DataFrame) -> None:
    last = gbm_breadth.index[-1]
    row = br.breadth_as_of(gbm_breadth, last.date())
    assert row is not None and row.name == last
    # a weekend / holiday as_of resolves to the prior session
    friday = gbm_breadth.index[gbm_breadth.index.dayofweek == 4][-2]
    row = br.breadth_as_of(gbm_breadth, (friday + pd.Timedelta(days=1)).date())
    assert row is not None and row.name == friday
    assert br.breadth_as_of(gbm_breadth, date(2000, 1, 3)) is None
    assert br.breadth_as_of(None, last.date()) is None
    # index given as tz-aware timestamps or python dates works the same
    aware = gbm_breadth.set_axis(gbm_breadth.index.tz_localize(NY))
    assert br.breadth_as_of(aware, last.date()).name == last
    as_dates = gbm_breadth.set_axis([d.date() for d in gbm_breadth.index])
    assert br.breadth_as_of(as_dates, pd.Timestamp(last, tz=NY)).name == last


def test_four_pct_share_floor_reads_as_traded_volume_through_the_splits_table() -> None:
    """A later 1:10 reverse split shows 500k traded shares as 50k adjusted: with the splits table the name still
    counts on its +5% day; a later 4:1 split inflates 30k traded shares to 120k: it no longer counts."""
    days = pd.bdate_range("2026-03-02", periods=3, tz="America/New_York")

    def bars(sym: str, vols: list[float]) -> pd.DataFrame:
        close = [10.0, 10.0, 10.5]  # +5% on the last day
        return pd.DataFrame({"symbol": sym, "ts": days, "open": close, "high": close, "low": close, "close": close,
                             "volume": vols})

    panel = pd.concat([bars("REV", [40_000.0, 40_000.0, 50_000.0]), bars("FWD", [100_000.0, 100_000.0, 120_000.0])],
                      ignore_index=True)
    splits = pd.DataFrame({"symbol": ["REV", "FWD"], "ex_date": [date(2026, 4, 1), date(2026, 4, 1)],
                           "ratio": [0.1, 4.0]})
    adjusted = br.market_breadth(panel)
    traded = br.market_breadth(panel, splits=splits)
    assert int(adjusted["up4_count"].iloc[-1]) == 1  # FWD's inflated 120k passes, REV's deflated 50k does not
    assert int(traded["up4_count"].iloc[-1]) == 1  # REV (500k traded) counts, FWD (30k traded) does not
    flags = br.market_breadth(panel.loc[panel["symbol"] == "REV"], splits=splits)
    assert int(flags["up4_count"].iloc[-1]) == 1
    assert int(br.market_breadth(panel.loc[panel["symbol"] == "FWD"], splits=splits)["up4_count"].iloc[-1]) == 0
    # a split dated on or before the bar does not un-adjust it
    early = splits.assign(ex_date=[date(2026, 3, 1), date(2026, 3, 1)])
    assert br.market_breadth(panel, splits=early)["up4_count"].tolist() == adjusted["up4_count"].tolist()
