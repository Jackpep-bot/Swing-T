"""data.market_series (Cboe VIX family, Ken French daily factors), the ff3 / vix extras, the vix_high overlay and the
`swing ingest-vix` / `swing ingest-french` commands. Fixtures are excerpts of the real files (fetched 2026-10-08)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing_engine import cli
from swing_engine.core.config import PlaybookConfig, PlaybookOverlay
from swing_engine.data import market_series as ms
from swing_engine.data.store import Store
from swing_engine.features import extra as ex
from swing_engine.strategies import playbook as pb
from tests import test_cli as cli_tests
from tests.test_cli import runner

workdir = cli_tests.workdir
FIX = Path(__file__).parent / "fixtures" / "market_series"
TODAY = date(2026, 10, 8)


def _fetch(url: str) -> bytes:
    return (FIX / url.rsplit("/", 1)[1]).read_bytes()


def _ingested() -> Store:
    store = Store()
    ms.run_vix_ingest(store, _fetch, today=TODAY)
    ms.run_french_ingest(store, _fetch, today=TODAY)
    return store


def test_vix_ingest_parses_cboe_and_drops_todays_partial_row():
    store = _ingested()
    vix = store.read_table(ms.VIX_TABLE).sort_values("date").reset_index(drop=True)
    assert pd.Timestamp(vix["date"].max()).date() == date(2026, 10, 7)  # VIX9D/VIX3M 10/08 partial rows dropped
    last = vix.iloc[-1]
    assert (last["vix_open"], last["vix_high"], last["vix_low"], last["vix_close"]) == (15.21, 16.01, 14.97, 15.08)
    assert last["vix9d_close"] == 11.78 and last["vix3m_close"] == 17.72
    labor_day = vix.loc[pd.to_datetime(vix["date"]) == "2026-09-07"].iloc[0]  # Cboe prints VIX on Labor Day only
    assert np.isnan(labor_day["vix9d_close"])
    meta = store.read_table(ms.META_TABLE)
    assert set(meta["source"]) == {"cboe_vix", "cboe_vix9d", "cboe_vix3m", "french_ff3_daily", "french_mom_daily"}
    assert (pd.to_datetime(meta["downloaded_on"]).dt.date == TODAY).all()


def test_french_ingest_decimals_vintage_and_publication_rule():
    store = _ingested()
    ff = store.read_table(ms.FF_TABLE).sort_values("date").reset_index(drop=True)
    first = ff.iloc[0]  # 20260701 file row: -0.04, -0.49 ... in percent
    assert pd.Timestamp(first["date"]).date() == date(2026, 7, 1)
    assert first["rf"] == pytest.approx(0.0002) and first["mom"] == pytest.approx(-0.0366)
    assert pd.Timestamp(ff["date"].max()).date() == date(2026, 8, 31)
    kf = pd.to_datetime(ff.set_index(pd.to_datetime(ff["date"]))["known_from"])
    assert kf["2026-07-31"] == pd.Timestamp("2026-09-01") and kf["2026-08-31"] == pd.Timestamp("2026-10-01")
    meta = store.read_table(ms.META_TABLE).set_index("source")
    assert meta.loc["french_ff3_daily", "vintage"] == "202608"
    assert meta.loc["french_ff3_daily", "url"] == ms.FF3_URL


def test_french_missing_values_are_nan():
    text = "pre\n\n,Mkt-RF,SMB,HML,RF\n20260701,  -99.99,   1.00,  -999,  0.01\n\nCopyright\n"
    row = ms.parse_french_daily(text).iloc[0]
    assert np.isnan(row["mkt_rf"]) and np.isnan(row["hml"]) and row["smb"] == pytest.approx(0.01)


def _panel(days: list[str], symbols=("SPY", "AAA")) -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize("America/New_York")
    return pd.DataFrame([{"symbol": s, "ts": t, "close": 1.0} for s in symbols for t in ts])


def test_join_adds_same_values_to_every_symbol_and_is_a_noop_without_tables():
    p = _panel(["2026-08-31", "2026-10-07"])
    assert ms.join_market_series(Store(), p) is p
    assert ms.join_market_series(object(), p) is p
    out = ms.join_market_series(_ingested(), p)
    on = out.loc[out["ts"].dt.day == 7]
    assert list(on["vix_close"]) == [15.08, 15.08] and list(on["vix9d_close"]) == [11.78, 11.78]
    aug = out.loc[out["ts"].dt.month == 8]
    assert aug["ff_mkt_rf"].notna().all() and aug["vix_close"].isna().all()  # VIX excerpt starts 2026-09-01
    assert on["ff_mkt_rf"].isna().all()  # no factor for October yet
    assert ms.join_market_series(_ingested(), out) is out  # columns present: unchanged


def _ff_panel(n: int = 260, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-01-02", periods=n, tz="America/New_York")
    f = rng.normal(0, 0.01, (n, 3))
    r = 0.0001 + f @ np.array([1.2, 0.5, -0.3]) + rng.normal(0, 0.01, n)
    close = 50 * np.cumprod(1 + r)
    return pd.DataFrame({"symbol": "AAA", "ts": days, "open": close, "high": close, "low": close, "close": close,
                         "volume": 1e6, "ff_mkt_rf": f[:, 0], "ff_smb": f[:, 1], "ff_hml": f[:, 2], "ff_rf": 0.0001})


def test_ff3_resid_mom_matches_ols_and_lags_two_months():
    w, f = 60, 20
    p = _ff_panel()
    out = ex.ensure_extra(p, [f"ff3_resid_mom_{w}_{f}"])[f"ff3_resid_mom_{w}_{f}"]
    month = p["ts"].dt.tz_localize(None).dt.to_period("M")
    target = month.unique()[-1]
    end = int(np.flatnonzero(month == target - 2)[-1])  # last session of month M-2
    y = (p["close"].pct_change() - p["ff_rf"]).to_numpy()
    x = np.column_stack([np.ones(len(p)), p[["ff_mkt_rf", "ff_smb", "ff_hml"]].to_numpy()])
    b = np.linalg.lstsq(x[end - w + 1:end + 1], y[end - w + 1:end + 1], rcond=None)[0]
    e = y[end - f + 1:end + 1] - x[end - f + 1:end + 1] @ b  # regression residuals (intercept removed)
    rows = out[month == target]
    assert rows.nunique() == 1 and rows.iloc[0] == pytest.approx(e.sum() / e.std(), rel=1e-6)
    # point-in-time: factor values after the end of month M-2 never move month M's score
    later = p.index > end
    shocked = p.assign(ff_mkt_rf=np.where(later, 0.5, p["ff_mkt_rf"]))
    again = ex.ensure_extra(shocked, [f"ff3_resid_mom_{w}_{f}"])[f"ff3_resid_mom_{w}_{f}"]
    assert again[month == target].iloc[0] == pytest.approx(rows.iloc[0])
    assert ex.ensure_extra(p.drop(columns=["ff_mkt_rf"]), [f"ff3_resid_mom_{w}_{f}"]).iloc[:, -1].isna().all()


def _overlay_cfg(**params) -> PlaybookConfig:
    return PlaybookConfig(overlays={"vix_high": PlaybookOverlay(enabled=True, params=params)})


@pytest.mark.parametrize(("vix", "v9", "fires"), [(31.0, 25.0, True), (20.0, 21.0, True), (20.0, 19.0, False),
                                                  (np.nan, np.nan, False)])
def test_vix_high_overlay(vix, v9, fires):
    p = _panel(["2026-10-06", "2026-10-07"]).assign(vix_close=[12.0, vix, 12.0, vix], vix9d_close=[50.0, v9, 50.0, v9])
    fired, _, inputs = pb.fired_overlays(p, date(2026, 10, 7), None, None, _overlay_cfg())
    assert (fired == ["vix_high"]) is fires
    fired, _, _ = pb.fired_overlays(p, date(2026, 10, 6), None, None, _overlay_cfg())
    assert fired == ["vix_high"]  # 10/06: ratio 50 / 12; never reads 10/07 on 10/06
    assert pb.fired_overlays(_panel(["2026-10-07"]), date(2026, 10, 7), None, None, _overlay_cfg())[0] == []


def test_vix_high_default_is_off_and_risk_reducing():
    o = PlaybookConfig().overlays["vix_high"]
    assert not o.enabled and o.multiplier <= 1.0
    assert set(pb.OVERLAYS["vix_high"]) == set(o.params)


def test_cli_ingest_commands(workdir: Path, monkeypatch: pytest.MonkeyPatch):
    import swing_engine.data.market_series as mod

    monkeypatch.setattr(mod, "_default_fetch", lambda: _fetch)
    for cmd in ("ingest-vix", "ingest-french"):
        result = runner.invoke(cli.app, [cmd])
        assert result.exit_code == 0, result.output
    with Store(workdir / "data" / "swing.duckdb") as store:
        assert store.count(ms.VIX_TABLE) >= 27 and store.count(ms.FF_TABLE) == 43
