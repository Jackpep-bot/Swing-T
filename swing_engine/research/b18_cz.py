"""Batch 18 (`cz_blind_presample_composite`; card docs/proposals/swing-methods-2026-10/batch18/): a Chen-Zimmermann
composite chosen by a rule blind to 2017+. Three steps, each committed before the next:

1. ``--step list``: BUILDABLE below, every CZ Accounting / Price / Trading predictor with in / out and why, written to
   docs/preregistration/2026-10-14-batch18-list.md. No statistic is computed in this step.
2. ``--step select``: post-publication .. 2016-12 value-weighted long-short t >= 2 (>= 60 months) and a positive
   in-sample mean; momentum family and GP excluded; at most 10 by t.
3. ``--step book``: the pre-registered book (docs/preregistration/2026-10-14-batch18.md).

Store items a predictor may use (2026-10-14): daily bars and volume (2016-01 on), `mcap_pit`, split-adjusted shares
from EDGAR cover pages (2009 on), XBRL diluted EPS, revenue, gross profit, operating cash flow, total assets,
stockholders' equity (2009 on, quarterly and annual), current 4-digit SIC, dividends (2016 on), 8-K earnings dates,
daily Fama-French factors, VIX, exchange.
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

CZ_DIR = ROOT / "data" / "research" / "chen_zimmermann"
LIST_OUT = "docs/preregistration/2026-10-14-batch18-list.md"
SELECT_OUT = "docs/preregistration/2026-10-14-batch18-selection.md"
SELECT_VW_OUT = "docs/preregistration/2026-10-14-batch18-selection-vwforce.md"  # amendment 1
VWFORCE_FILE = "PredictorAltPorts_LiqScreen_VWforce.zip"
CUTOFF = "2016-12"  # card: post-publication evidence through 2016-12 only; nothing later is read
MIN_MONTHS, MIN_T, MAX_SELECTED = 60, 2.0, 10  # card
#: card: price-momentum predictors (any whose definition is a past-return sort) and GP are excluded by family
EXCLUDED = frozenset({"GP", "Mom6m", "Mom12m", "MomVol", "IntMom", "Mom12mOffSeason", "FirmAgeMom", "IndMom",
                      "LRreversal", "MRreversal", "STreversal", "MomOffSeason", "MomRev", "MomSeason", "MomSeasonShort",
                      "ResidualMomentum", "TrendFactor"})
CATEGORIES = ("Accounting", "Price", "Trading")
MAX_HISTORY_MONTHS = 60  # card: a predictor needing more than 60 months of history is out

_ITEMS = "needs {} (not in the store)"
#: acronym -> (buildable, reason). Every CZ Predictor in CATEGORIES appears exactly once (checked by build_list).
BUILDABLE: dict[str, tuple[bool, str]] = {
    # --- accounting
    "AM": (True, "total assets / market equity: assets, mcap_pit"),
    "AbnormalAccruals": (False, _ITEMS.format("receivables and PP&E for the industry Jones-model regression")),
    "Accruals": (False, _ITEMS.format("current assets, cash, current liabilities, current debt (balance-sheet accruals)")),
    "AccrualsBM": (False, _ITEMS.format("balance-sheet accruals and tangible book equity")),
    "AdExp": (False, _ITEMS.format("advertising expense (xad)")),
    "AssetGrowth": (True, "annual growth of total assets: assets now and four quarters back"),
    "BM": (False, _ITEMS.format("tangible book equity (ceqt: intangibles)")),
    "BMdec": (False, _ITEMS.format("tangible book equity (BMdec is BM with December market equity)")),
    "BPEBM": (False, _ITEMS.format("cash, debt, preferred dividends in arrears, treasury stock")),
    "BookLeverage": (False, _ITEMS.format("deferred taxes and preferred stock")),
    "BrandInvest": (False, _ITEMS.format("advertising expense")),
    "CBOperProf": (False, _ITEMS.format("SG&A, R&D, receivables, inventory, prepaid expenses, deferred revenue, payables")),
    "CF": (False, _ITEMS.format("depreciation (dp)")),
    "Cash": (False, _ITEMS.format("cash and short-term investments")),
    "CashProd": (False, _ITEMS.format("cash and short-term investments")),
    "ChAssetTurnover": (False, _ITEMS.format("net operating assets (receivables, inventory, PP&E, payables)")),
    "ChEQ": (True, "book equity / book equity a year earlier: stockholders' equity"),
    "ChInv": (False, _ITEMS.format("inventory")),
    "ChInvIA": (False, _ITEMS.format("capital expenditure / PP&E")),
    "ChNNCOA": (False, _ITEMS.format("current assets, investments, liabilities, debt")),
    "ChNWC": (False, _ITEMS.format("current assets, cash, current liabilities, current debt")),
    "ChTax": (False, _ITEMS.format("quarterly total taxes (txtq)")),
    "CompEquIss": (True, "5-year market-equity growth minus 5-year return: EDGAR shares from 2009 give the share growth; "
                         "needs 60 months of bars for the return, so available from 2021 only"),
    "CompositeDebtIssuance": (False, _ITEMS.format("long-term and current debt")),
    "ConvDebt": (False, _ITEMS.format("deferred charges, shares reserved for conversion")),
    "DebtIssuance": (False, _ITEMS.format("long-term debt issuance (dltis)")),
    "DelCOA": (False, _ITEMS.format("current assets and cash")),
    "DelCOL": (False, _ITEMS.format("current liabilities and current debt")),
    "DelDRC": (False, _ITEMS.format("deferred revenue")),
    "DelEqu": (True, "change in book equity / average total assets: equity, assets"),
    "DelFINL": (False, _ITEMS.format("debt and preferred stock")),
    "DelLTI": (False, _ITEMS.format("investments and advances (ivao)")),
    "DelNetFin": (False, _ITEMS.format("short-term investments, investments, debt, preferred stock")),
    "DivYieldST": (True, "predicted next-month dividend yield from the past 12 months of regular dividends: dividends feed"),
    "EBM": (False, _ITEMS.format("cash, debt, deferred charges, preferred dividends, treasury stock")),
    "EP": (True, "net income / market equity 6 months earlier, NYSE only: EPS x shares, mcap_pit, exchange"),
    "EarnSupBig": (True, "EarningsSurprise of the 30% largest firms in the same Fama-French 48 industry: quarterly EPS, "
                         "mcap_pit, 4-digit SIC (current, not point-in-time)"),
    "EarningsConsistency": (True, "average annual EPS growth over 48 months: quarterly / annual diluted EPS from 2009"),
    "EarningsStreak": (False, _ITEMS.format("analyst forecasts (IBES)")),
    "EarningsSurprise": (True, "standardised unexpected quarterly EPS with drift: diluted EPS by quarter"),
    "EntMult": (False, _ITEMS.format("debt, cash, deferred charges, operating income before depreciation")),
    "EquityDuration": (False, "SignalDoc gives no definition ('see code'); its items cannot be checked against the store"),
    "FR": (False, _ITEMS.format("pension assets and obligations")),
    "Frontier": (False, _ITEMS.format("debt, capex, R&D, advertising")),
    "GP": (True, "gross profit / total assets (excluded at step 2 by family: batch 3's card)"),
    "GrAdExp": (False, _ITEMS.format("advertising expense")),
    "GrLTNOA": (False, _ITEMS.format("receivables, inventory, PP&E, intangibles, payables")),
    "GrSaleToGrInv": (False, _ITEMS.format("inventory")),
    "GrSaleToGrOverhead": (False, _ITEMS.format("SG&A")),
    "IntanBM": (False, _ITEMS.format("tangible book equity; also 5-year returns plus 5-year lags (more than 60 months)")),
    "IntanCFP": (False, _ITEMS.format("depreciation; also more than 60 months of returns")),
    "IntanEP": (False, "needs 5-year returns regressed on 5-year-lagged EP: more than 60 months of history"),
    "IntanSP": (False, "needs 5-year returns regressed on 5-year-lagged SP: more than 60 months of history"),
    "InvGrowth": (False, _ITEMS.format("inventory")),
    "InvestPPEInv": (False, _ITEMS.format("PP&E and inventory")),
    "Investment": (False, _ITEMS.format("capital expenditure")),
    "Leverage": (False, _ITEMS.format("total liabilities (lt)")),
    "MS": (False, _ITEMS.format("R&D, capex, advertising (Mohanram G-score)")),
    "MeanRankRevGrowth": (True, "weighted ranks of annual revenue growth over 5 years: revenue from 2009"),
    "NOA": (False, _ITEMS.format("cash, debt, minority interest, preferred stock")),
    "NetDebtFinance": (False, _ITEMS.format("debt issuance and reduction")),
    "NetDebtPrice": (False, _ITEMS.format("debt, preferred stock, cash")),
    "NetEquityFinance": (False, _ITEMS.format("sale and purchase of common stock (sstk, prstkc)")),
    "NetPayoutYield": (False, _ITEMS.format("purchase and sale of stock (prstkc, sstk)")),
    "NumEarnIncrease": (True, "consecutive quarterly earnings increases (up to 8): quarterly EPS x shares"),
    "OPLeverage": (False, _ITEMS.format("SG&A")),
    "OScore": (False, _ITEMS.format("total liabilities, current assets and liabilities, funds from operations")),
    "OperProf": (False, _ITEMS.format("SG&A and interest expense")),
    "OperProfRD": (False, _ITEMS.format("SG&A and R&D")),
    "OrderBacklog": (False, _ITEMS.format("order backlog")),
    "OrderBacklogChg": (False, _ITEMS.format("order backlog")),
    "OrgCap": (False, _ITEMS.format("SG&A")),
    "PS": (False, _ITEMS.format("long-term debt, current ratio, shares issued (Piotroski)")),
    "PayoutYield": (False, _ITEMS.format("purchase of stock and preferred redemption value")),
    "PctAcc": (True, "(net income - operating cash flow) / |net income|: EPS x shares, operating cash flow"),
    "PctTotAcc": (False, _ITEMS.format("stock purchases and sales, dividends, financing and investing cash flows")),
    "PredictedFE": (False, _ITEMS.format("analyst forecasts")),
    "RD": (False, _ITEMS.format("R&D expense")),
    "RDAbility": (False, _ITEMS.format("R&D expense")),
    "RDS": (False, _ITEMS.format("dirty-surplus items (marketable securities, retained earnings adjustments)")),
    "RDcap": (False, _ITEMS.format("R&D expense")),
    "RevenueSurprise": (True, "standardised change in quarterly revenue per share: revenue, shares"),
    "RoE": (True, "net income / book equity: EPS x shares, equity"),
    "SP": (True, "annual sales / market equity: revenue, mcap_pit"),
    "ShareIss1Y": (True, "split-adjusted share growth t-18 .. t-6 months: EDGAR shares"),
    "ShareIss5Y": (True, "5-year split-adjusted share growth: EDGAR shares from 2009"),
    "ShareRepurchase": (False, _ITEMS.format("purchase of common stock (prstkc)")),
    "SurpriseRD": (False, _ITEMS.format("R&D expense")),
    "Tax": (False, _ITEMS.format("federal and foreign income taxes")),
    "TotalAccruals": (False, _ITEMS.format("current assets and liabilities, investments, debt")),
    "VarCF": (False, _ITEMS.format("depreciation")),
    "XFIN": (False, _ITEMS.format("stock and debt issuance and repurchase")),
    "cfp": (True, "operating cash flow / market equity: operating cash flow, mcap_pit"),
    "dNoa": (False, _ITEMS.format("cash, debt, minority interest, preferred stock")),
    "grcapx": (False, _ITEMS.format("capital expenditure / PP&E")),
    "grcapx3y": (False, _ITEMS.format("capital expenditure / PP&E")),
    "realestate": (False, _ITEMS.format("PP&E detail (buildings, land)")),
    "roaq": (True, "quarterly net income / lagged quarterly assets: EPS x shares, assets"),
    "tang": (False, _ITEMS.format("cash, receivables, inventory, PP&E")),
    # --- price
    "AnnouncementReturn": (True, "market-adjusted return around earnings announcements: daily bars, 8-K earnings dates "
                                 "(EDGAR instead of IBES dates)"),
    "Beta": (True, "60-month CAPM beta on monthly returns: bars (fewer months until 2021; CZ requires 20)"),
    "BetaFP": (True, "Frazzini-Pedersen beta from daily returns (1-year vol, 5-year correlation): bars"),
    "BetaLiquidityPS": (False, _ITEMS.format("the Pastor-Stambaugh liquidity series")),
    "BetaTailRisk": (False, "needs a 120-month tail-risk regression: more than 60 months of history"),
    "Coskewness": (True, "coskewness from 60 months of monthly returns: bars (exactly 60, fewer until 2021)"),
    "CoskewACX": (True, "coskewness from 12 months of daily returns: bars"),
    "FirmAgeMom": (False, _ITEMS.format("CRSP first listing date (firm age)")),
    "High52": (True, "price / 12-month high: bars (a price-level ratio, not a past-return sort)"),
    "IdioVol3F": (True, "residual volatility on daily Fama-French 3 factors, past month: bars, ff_factors"),
    "IdioVolAHT": (True, "residual volatility on the daily market, past year: bars"),
    "IndMom": (True, "6-month return of the 2-digit industry: bars, SIC (momentum family: excluded at step 2)"),
    "IndRetBig": (True, "return of the largest 30% in the Fama-French 48 industry: bars, mcap_pit, 4-digit SIC"),
    "IntMom": (True, "return t-12 .. t-6: bars (momentum family: excluded at step 2)"),
    "LRreversal": (True, "return t-36 .. t-13: bars (past-return sort: excluded at step 2)"),
    "MRreversal": (True, "return t-18 .. t-13: bars (past-return sort: excluded at step 2)"),
    "MaxRet": (True, "largest daily return in the past month: bars"),
    "Mom12m": (True, "return t-12 .. t-1: bars (momentum family: excluded at step 2)"),
    "Mom12mOffSeason": (True, "average return in the other months of the past year: bars (excluded at step 2)"),
    "Mom6m": (True, "return t-6 .. t-1: bars (momentum family: excluded at step 2)"),
    "Mom6mJunk": (False, _ITEMS.format("credit ratings")),
    "MomOffSeason": (True, "off-season returns years 2-5: bars, 60 months (past-return sort: excluded at step 2)"),
    "MomOffSeason06YrPlus": (False, "years 6-10 of returns: more than 60 months of history"),
    "MomOffSeason11YrPlus": (False, "years 11-15 of returns: more than 60 months of history"),
    "MomOffSeason16YrPlus": (False, "years 16-20 of returns: more than 60 months of history"),
    "MomRev": (True, "6-month and 36-month return quintiles: bars (past-return sort: excluded at step 2)"),
    "MomSeason": (True, "same-month returns years 2-5: bars, 60 months (past-return sort: excluded at step 2)"),
    "MomSeason06YrPlus": (False, "years 6-10 of returns: more than 60 months of history"),
    "MomSeason11YrPlus": (False, "years 11-15 of returns: more than 60 months of history"),
    "MomSeason16YrPlus": (False, "years 16-20 of returns: more than 60 months of history"),
    "MomSeasonShort": (True, "same-month return last year: bars (past-return sort: excluded at step 2)"),
    "MomVol": (True, "6-month return x volume sort: bars (momentum family: excluded at step 2)"),
    "Price": (True, "log price: bars"),
    "PriceDelayRsq": (True, "R-squared gain from lagged market returns, daily, one year: bars"),
    "PriceDelaySlope": (True, "share of beta on lagged market returns, daily, one year: bars"),
    "PriceDelayTstat": (True, "t-adjusted price delay, daily, one year: bars"),
    "RealizedVol": (True, "CAPM residual volatility, past month of daily returns: bars"),
    "ResidualMomentum": (True, "36-month FF3-residual momentum: bars, ff_factors (momentum family: excluded at step 2)"),
    "ReturnSkew": (True, "skewness of daily returns, past month: bars"),
    "ReturnSkew3F": (True, "skewness of daily FF3 residuals, past month: bars, ff_factors"),
    "STreversal": (True, "last month's return: bars (past-return sort: excluded at step 2)"),
    "Size": (True, "log market equity: mcap_pit"),
    "TrendFactor": (True, "moving-average price trend signal: bars (a past-price sort: excluded at step 2 with momentum)"),
    "betaVIX": (True, "daily beta on VIX changes, past month: bars, VIX (CZ uses VXO)"),
    "retConglomerate": (False, _ITEMS.format("Compustat segment data")),
    # --- trading
    "BidAskSpread": (True, "Corwin-Schultz spread from daily highs and lows: bars"),
    "DolVol": (True, "log dollar volume two months back: bars"),
    "Illiquidity": (True, "Amihud |return| / dollar volume, 12 months: bars"),
    "ProbInformedTrading": (False, _ITEMS.format("external PIN estimates")),
    "ShareVol": (True, "3-month share turnover above 10%: volume, EDGAR shares"),
    "ShortInterest": (False, _ITEMS.format("short interest")),
    "VolMkt": (True, "12-month dollar volume / market equity: bars, mcap_pit"),
    "VolSD": (True, "36-month standard deviation of monthly volume, NYSE only: bars, exchange"),
    "VolumeTrend": (True, "60-month trend in monthly volume: bars (exactly 60, fewer until 2021)"),
    "std_turn": (True, "36-month standard deviation of turnover: volume, EDGAR shares"),
    "zerotrade12M": (True, "zero-volume days and turnover, 12 months: bars, shares"),
    "zerotrade1M": (True, "zero-volume days and turnover, 1 month: bars, shares"),
    "zerotrade6M": (True, "zero-volume days and turnover, 6 months: bars, shares"),
}


def predictors(doc: pd.DataFrame) -> pd.DataFrame:
    """CZ Predictors in CATEGORIES (SignalDoc rows), without any return statistic."""
    keep = (doc["Cat.Signal"] == "Predictor") & doc["Cat.Data"].isin(CATEGORIES)
    return doc.loc[keep, ["Acronym", "Cat.Data", "Stock Weight", "Year", "SampleStartYear", "SampleEndYear",
                          "LongDescription"]].set_index("Acronym").sort_index()


def build_list(doc: pd.DataFrame) -> list[str]:
    p = predictors(doc)
    missing, extra = sorted(set(p.index) - set(BUILDABLE)), sorted(set(BUILDABLE) - set(p.index))
    if missing or extra:
        raise ValueError(f"BUILDABLE does not match SignalDoc: missing {missing}, extra {extra}")
    n_in = sum(BUILDABLE[a][0] for a in p.index)
    lines = ["# Batch 18, step 1: which Chen-Zimmermann predictors the store can build", "",
             "Committed 2026-10-14 **before any statistic of any predictor was computed** (card "
             "`docs/proposals/swing-methods-2026-10/batch18/cz_blind_presample_composite.md`, step 1). Source: "
             "`SignalDoc.csv` of the CZ v2.0.0 release in data/research/chen_zimmermann/ (owner-approved download). "
             f"{len(p)} predictors in {', '.join(CATEGORIES)}; {n_in} buildable. Generated by "
             "`uv run python -m swing_engine.research.b18_cz --step list` from `b18_cz.BUILDABLE`.", "",
             "Weighting note for step 2: the VWforce file is not among the downloaded CZ files, so step 2 uses each "
             "predictor's original long-short series and keeps only those CZ built value-weighted (column EW/VW).", "",
             "| predictor | data | EW/VW | published | buildable | why |", "|---|---|---|---|---|---|"]
    for a, r in p.iterrows():
        ok, why = BUILDABLE[a]
        lines.append(f"| {a} | {r['Cat.Data']} | {r['Stock Weight']} | {int(r['Year'])} | {'yes' if ok else 'no'} | {why} |")
    return lines + [""]


def vwforce_returns(path: Path) -> pd.DataFrame:
    """The VWforce file's long-short rows (port "LS"), wide by predictor, date index, percent; rows after CUTOFF are
    dropped while reading."""
    df = pd.read_csv(path, usecols=["signalname", "port", "date", "ret"], dtype={"port": str})
    df = df.loc[(df["port"] == "LS") & (df["date"].str[:7] <= CUTOFF)]
    wide = df.pivot(index="date", columns="signalname", values="ret")
    wide.index = pd.to_datetime(wide.index)
    return wide


def selection(doc: pd.DataFrame, returns: pd.DataFrame, vwforce: bool = False) -> pd.DataFrame:
    """Step 2 on every buildable predictor; ``returns``: CZ long-short monthly returns (percent), date index. Rows
    after CUTOFF are dropped before anything is computed. ``vwforce``: the returns are CZ's value-weighted rebuild of
    every predictor (amendment 1), so the original weighting no longer excludes."""
    from swing_engine.research.premise_library import mean_t

    p = predictors(doc)
    r = returns.loc[returns.index.strftime("%Y-%m") <= CUTOFF] / 100.0
    r.index = r.index.strftime("%Y-%m")
    rows = []
    for a, d in p.iterrows():
        if not BUILDABLE[a][0]:
            continue
        why = ("excluded by family (card)" if a in EXCLUDED else
               "equal-weighted original series (no VWforce file)" if d["Stock Weight"] != "VW" and not vwforce else
               "no returns in the CZ file" if a not in r.columns else "")
        s = r[a] if a in r.columns else pd.Series(dtype=float)
        post = s.loc[f"{int(d['Year']) + 1}-01":].dropna()
        ins = s.loc[f"{int(d['SampleStartYear'])}-01":f"{int(d['SampleEndYear'])}-12"].dropna()
        mp, tp, n = mean_t(post) if why == "" else (float("nan"), float("nan"), len(post))
        mi = float(ins.mean() * 12) if why == "" and len(ins) else float("nan")
        if why == "":
            why = (f"post-publication window {n} months (< {MIN_MONTHS})" if n < MIN_MONTHS else
                   f"post-publication t {tp:.2f} < {MIN_T}" if not tp >= MIN_T else
                   "in-sample mean not positive" if not mi > 0 else "")
        rows.append({"predictor": a, "weight": d["Stock Weight"], "published": int(d["Year"]), "months": n,
                     "post_mean": mp, "post_t": tp, "in_sample_mean": mi, "passes": why == "", "why": why or "passes"})
    out = pd.DataFrame(rows).set_index("predictor")
    passing = out.loc[out["passes"]].sort_values("post_t", ascending=False)
    out["selected"] = out.index.isin(passing.index[:MAX_SELECTED])
    return out


def _f(x: float, spec: str) -> str:
    return "-" if pd.isna(x) else format(x, spec)


def selection_lines(table: pd.DataFrame, vwforce: bool = False) -> list[str]:
    chosen = table.loc[table["selected"]].sort_values("post_t", ascending=False)
    head = (["# Batch 18, step 2 rerun (amendment 1): the blind selection on VWforce series", "",
             "Step 2 was rerun once after the first pass (VW originals only, `2026-10-14-batch18-selection.md`) came back "
             f"empty; amendment `2026-10-14-batch18-amendment.md` was committed first. Series: CZ `{VWFORCE_FILE}` "
             "(long-short, value-weighted rebuild of every predictor). Everything else as below.", ""] if vwforce else
            ["# Batch 18, step 2: the blind selection", ""])
    lines = [*head,
             f"Committed 2026-10-14 before the book is built. Rule (card, fixed before any statistic): among the step-1 "
             f"buildable predictors (`{LIST_OUT}`), value-weighted original CZ series only (no VWforce file on the Mac), "
             f"momentum family and GP excluded; mean monthly long-short return from January after publication through "
             f"{CUTOFF}, at least {MIN_MONTHS} months, t >= {MIN_T}, and a positive in-sample mean; at most "
             f"{MAX_SELECTED} by t. Returns after {CUTOFF} were dropped before anything was computed and were not looked at.",
             "", f"**Selected: {', '.join(chosen.index) if len(chosen) else 'none: no card (the rule leaves nothing)'}**", "",
             "| predictor | EW/VW | published | months | post-pub mean/yr | t | in-sample mean/yr | result |",
             "|---|---|---|---|---|---|---|---|"]
    for a, r in table.sort_values(["passes", "post_t"], ascending=False).iterrows():
        lines.append(f"| {a} | {r['weight']} | {r['published']} | {r['months']} | {_f(r['post_mean'], '+.2%')} | "
                     f"{_f(r['post_t'], '.2f')} | {_f(r['in_sample_mean'], '+.2%')} | "
                     f"{'SELECTED' if r['selected'] else r['why']} |")
    return lines + [""]


# ------------------------------------------------------------------------------------------------ step 3: the book
SPEC = "docs/preregistration/2026-10-14-batch18.md"
OUT = "docs/preregistration/2026-10-14-batch18-results.md"
TAG = "prereg-b18"
CARD = "cz_blind_presample_composite"
N_TRIALS = 3  # card: 1 trial, bar raised one step: alpha_t_critical(3)
MARKET = "SPY"
#: step 2 rerun (amendment 1, commit f274aad) -> CZ's Sign (+1: high is the long side)
SELECTED: dict[str, int] = {"DivYieldST": 1, "VolumeTrend": -1}
REF_MONTHS = (5, 11)  # card: last session of May / November; trade after the third Friday of June / December
FIRST_TRADE = date(2017, 6, 1)  # card: SPY before the first rebalance (June 2017)
TOP, MIN_CLOSE = 500, 5.0  # card
HOLD, STAY, MAX_WEIGHT = 100, 150, 0.05  # card
# DivYieldST (CZ definition): regular dividends of quarterly / semiannual / annual payers; the dividend expected next
# month is the one 2 / 5 / 11 months before the reference month; yield buckets 0 | (0, 0.5%] | (0.5%, 1%] | > 1%
DIV_LAG_MONTHS = {"quarterly": 2, "semiannual": 5, "annual": 11}
DIV_BUCKETS = (0.005, 0.010)
# VolumeTrend (CZ definition): slope of monthly volume on time over 60 months (at least 30) / mean volume
TREND_MONTHS, TREND_MIN_MONTHS = 60, 30


def _month(d: Any) -> int:
    return pd.Timestamp(d).year * 12 + pd.Timestamp(d).month - 1


def div_yield_st(div: pd.DataFrame, ref: date, close: pd.Series) -> pd.Series:
    """Per symbol of ``close`` (split-adjusted closes on ``ref``): the discretised expected dividend yield for the
    month after ``ref``; ``div``: store_symbol, ex_date, rate_adj, special (regular dividends are special == False)."""
    from swing_engine.data.dividends import MONTHLY_MIN_EX_MONTHS

    m = _month(ref)
    d = div.loc[~div["special"].fillna(False).astype(bool)]
    d = d.assign(month=pd.to_datetime(d["ex_date"]).map(_month))
    d = d.loc[(d["month"] > m - 12) & (d["month"] <= m)]
    months = d.groupby("store_symbol")["month"].nunique()
    kind = months.map(lambda n: "monthly" if n >= MONTHLY_MIN_EX_MONTHS else "quarterly" if n >= 3 else
                      "semiannual" if n == 2 else "annual")
    out = pd.Series(0.0, index=close.index)
    for sym, k in kind.items():
        if sym not in out.index or k == "monthly" or not close.get(sym, 0) > 0:
            continue
        hit = d.loc[(d["store_symbol"] == sym) & (d["month"] == m - DIV_LAG_MONTHS[k]), "rate_adj"]
        y = float(hit.sum()) / float(close[sym])
        out[sym] = 0.0 if y <= 0 else 1.0 if y <= DIV_BUCKETS[0] else 2.0 if y <= DIV_BUCKETS[1] else 3.0
    return out


def volume_trend(monthly_volume: pd.DataFrame, ref: date) -> pd.Series:
    """Slope of monthly volume on a time index over the TREND_MONTHS months ending with ``ref``'s month, divided by
    the mean volume; NaN under TREND_MIN_MONTHS months. ``monthly_volume``: month number (``_month``) x symbol."""
    m = _month(ref)
    v = monthly_volume.loc[(monthly_volume.index > m - TREND_MONTHS) & (monthly_volume.index <= m)]
    t = pd.Series(v.index.to_numpy(dtype=float), index=v.index)
    ok = v.notna()
    n = ok.sum()
    tc = ok.mul(t, axis=0).where(ok)
    t_mean = tc.sum() / n
    v_mean = v.sum() / n
    cov = (tc.sub(t_mean) * v.sub(v_mean)).sum()
    var = (tc.sub(t_mean) ** 2).sum()
    slope = cov / var
    return (slope / v_mean).where((n >= TREND_MIN_MONTHS) & (v_mean > 0))


def composite_score(signals: pd.DataFrame) -> pd.Series:
    """Mean of each selected signal's percentile within the universe (1 = CZ's long side); NaN with fewer than half."""
    pct = pd.DataFrame({k: (signals[k] * sign).rank(pct=True) for k, sign in SELECTED.items()}, index=signals.index)
    return pct.mean(axis=1).where(pct.notna().sum(axis=1) >= len(SELECTED) / 2.0)


def book_plan(universes: dict[date, pd.DataFrame], first_day: date, use: Sequence[str] | None = None
              ) -> dict[date, pd.Series]:
    """Orders per rebalance session (``universes``: mcap_pit and the SELECTED signals per rebalance session); ``use``:
    one predictor's own book (descriptive)."""
    orders: dict[date, pd.Series] = {first_day: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    for day in sorted(universes):
        u = universes[day]
        if use is None:
            score = composite_score(u).dropna()
        else:
            score = (u[use[0]] * SELECTED[use[0]]).rank(pct=True).dropna()
        held = select_names(score, current)
        orders[day] = cap_weights(u["mcap_pit"], held)
        current = set(held)
    return orders


def select_names(score: pd.Series, current: set[str]) -> list[str]:
    from swing_engine.research import b9_books as b9

    return b9.select(score, current, hold=HOLD, enter=len(score), stay=STAY)


def cap_weights(mcap: pd.Series, held: Sequence[str]) -> pd.Series:
    """mcap_pit weights capped at 5%; with fewer than HOLD names the book is scaled to names / HOLD, the rest SPY."""
    from swing_engine.research import b9_books as b9

    if not held:
        return pd.Series({MARKET: 1.0})
    w = b9.capped_weights(mcap.reindex(held), pd.Series(MAX_WEIGHT, index=list(held))) * min(1.0, len(held) / HOLD)
    rest = 1.0 - float(w.sum())
    return pd.concat([w, pd.Series({MARKET: rest})]) if rest > 1e-9 else w


def run_book(store_path: str | Path, out: str | Path = OUT, counts_only: bool = False,
             tr_store_path: str | Path | None = None) -> dict[str, Any]:
    from swing_engine.data.calendar import trading_days
    from swing_engine.data.dividends import mapped
    from swing_engine.data.fundamentals import share_issuance_features
    from swing_engine.data.store import Store
    from swing_engine.research import b9_books as b9
    from swing_engine.research import b11_books as b11
    from swing_engine.research import b12_books as b12
    from swing_engine.research.b17_books import _load, _monthly
    from swing_engine.research.costs import cost_table
    from swing_engine.research.prereg_eval import alpha_t_critical
    from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

    bars, closes, opens, delist, filings, splits = _load(store_path)
    with Store(str(store_path), read_only=True) as store:
        div = mapped(store)
    end = b11.WINDOWS["pooled"][1]
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
        index="day", columns="symbol", values="dv").reindex(closes.index)
    volume = bars.pivot(index="day", columns="symbol", values="volume").reindex(closes.index)
    monthly_volume = volume.groupby([_month(d) for d in volume.index]).sum(min_count=1)
    universes: dict[date, pd.DataFrame] = {}
    for ref in sorted(d for m in REF_MONTHS for d in b11.last_session_of_month(sessions, m)):
        day = b12._after_third_friday(ref, sessions)
        if day is None or day < FIRST_TRADE:
            continue
        rows = bars.loc[bars["day"] == ref, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        s = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy()},
                         index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:ref].tail(b9.DV_SESSIONS).median().reindex(s.index)
        s = s.loc[(s["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv) & (s["close_as_traded"] >= MIN_CLOSE)]
        s = s.loc[s["mcap_pit"].sort_values(ascending=False, kind="mergesort").index[:TOP]]
        s = s.assign(DivYieldST=div_yield_st(div, ref, closes.loc[ref].reindex(s.index)),
                     VolumeTrend=volume_trend(monthly_volume, ref).reindex(s.index))
        universes[day] = s
    orders = book_plan(universes, sessions[0])
    if counts_only:
        books = [w for d, w in orders.items() if d != sessions[0]]
        names = [len(set(w.index) - {MARKET}) for w in books]
        changes = [len((set(b.index) ^ set(a.index)) - {MARKET}) // 2 for a, b in zip(books, books[1:], strict=False)]
        cover = {k: [int(u[k].notna().sum()) for u in universes.values()] for k in SELECTED}
        dys = [int((u["DivYieldST"] > 0).sum()) for u in universes.values()]
        print(CARD, "rebalances", len(books), "first", min(d for d in orders if d != sessions[0]), "names min/max",
              min(names), max(names), "changed per rebalance median", int(np.median(changes)), "largest weight",
              round(max(float(w.drop(MARKET, errors="ignore").max()) for w in books), 3), "SPY max",
              round(max(float(w.get(MARKET, 0.0)) for w in books), 3), "coverage", cover,
              "DivYieldST > 0 per rebalance", dys, flush=True)
        return {}
    singles = {k: book_plan(universes, sessions[0], use=(k,)) for k in SELECTED}
    with Store(str(store_path), read_only=True) as store:
        replica = {sessions[0]: pd.Series({MARKET: 1.0}),
                   **b9.momentum_orders(closes, b9.mcap_function(store, bars, closes), sessions)}
    traded = sorted({s for p in (orders, replica, *singles.values()) for w in p.values() for s in w.index}
                    | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    rep = b11.book_for(replica, opens, closes, costs, delist, *b11.WINDOWS["pooled"])
    rep_m = _monthly(rep["ret"]) - _monthly(spy.reindex(rep.index))
    tr: dict[str, dict[str, Any]] = {}
    if tr_store_path is not None:
        _b, tc, to, tdel, _f, _s = _load(tr_store_path)
        tspy, trf = tc[MARKET].pct_change(fill_method=None), tc[b11.BILL].pct_change(fill_method=None)
        tr = {w: b9.grade(b11.book_for(orders, to, tc, costs, tdel, lo, hi), tspy, N_TRIALS, trf)
              for w, (lo, hi) in b11.WINDOWS.items()}
    extra = ["## Descriptive (not part of the verdict)", "", "| window | tracking error vs SPY | monthly excess correlation "
             "with batch 9's replica | total-return store: return/yr, alpha/yr (t) |", "|---|---|---|---|"]
    for w, book in books.items():
        ex = book["ret"] - spy.reindex(book.index)
        ours = _monthly(book["ret"]) - _monthly(spy.reindex(book.index))
        t = tr.get(w)
        tr_text = (f"{b9._pct(t['stats']['cagr'])}, {b9._pct(t['vs'].get('alpha_ann', math.nan))} "
                   f"({t['vs'].get('alpha_t', math.nan):.2f})") if t else "not run"
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {ours.corr(rep_m.reindex(ours.index)):.2f} | {tr_text} |")
    extra += ["", "Each selected predictor's own top-100 book (same rules), descriptive:", "",
              "| book | window | return/yr | deepest drop | alpha/yr | alpha t |", "|---|---|---|---|---|---|"]
    for k, o in singles.items():
        for w, (lo, hi) in b11.WINDOWS.items():
            g = b9.grade(b11.book_for(o, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
            extra.append(f"| {k} only | {w} | {b9._pct(g['stats']['cagr'])} | {b9._pct(-g['stats']['max_dd'])} | "
                         f"{b9._pct(g['vs'].get('alpha_ann', math.nan))} | {g['vs'].get('alpha_t', math.nan):.2f} |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(DEFAULT_TRIALS_PATH)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS, "selected": list(SELECTED)},
                  {**res["pooled"]["stats"], **res["pooled"]["vs"]}, DEFAULT_TRIALS_PATH,
                  tags=[TAG], notes=f"pre-registered batch 18 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 18 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b18_cz --step book`; net of "
             f"costs, price-only bars; alpha from (book - BIL) on (SPY - BIL). One trial, bar alpha t >= "
             f"{alpha_t_critical(N_TRIALS):.3f}. Selected predictors: {', '.join(SELECTED)}.", "",
             f"## `{CARD}`: {word}", "", f"Route 1 (both halves): {'met' if routes[0] else 'not met'}. Route 2 "
             f"(pooled, alpha > 0 in each half): {'met' if routes[1] else 'not met'}.", "",
             "| window | from | book | return/yr | deepest drop | worst month | months up | Sharpe | haircut SR | "
             "alpha/yr | alpha t | beta | turnover/yr | costs/yr |", "|" + "---|" * 14]
    for w, r in res.items():
        for label, st in (("book", r["stats"]), ("SPY", r["spy_stats"])):
            vs = r["vs"] if label == "book" else {}
            tail = (f"{st['haircut_sharpe']:.2f} | {b9._pct(vs.get('alpha_ann', math.nan))} | "
                    f"{vs.get('alpha_t', math.nan):.2f} | {vs.get('beta', math.nan):.2f} | "
                    f"{b9._pct(r['turnover_ann'], '.0%')} | {b9._pct(r['cost_ann'], '.2%')} |") if label == "book" else "| | | | | |"
            lines.append(f"| {w} | {r['start']} | {label} | {b9._pct(st['cagr'])} | {b9._pct(-st['max_dd'])} | "
                         f"{b9._pct(st['worst_month'])} | {b9._pct(st['months_up'], '.0%')} | {st['sharpe']:.2f} | " + tail)
    lines += ["", *extra, "", "## Verdict", f"- **{CARD}**: {word}"]
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return res


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--step", choices=["list", "select", "select-vwforce", "book"], required=True)
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--tr-settings", default="config/prereg_b9_tr.yaml", help="total-return store, descriptive only")
    ap.add_argument("--counts-only", action="store_true", help="step 3 harness check: order counts only")
    args = ap.parse_args(argv)
    if args.step == "book":
        from swing_engine.core.config import load_settings

        store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
        tr = ROOT / load_settings.__wrapped__(Path(args.tr_settings)).data.store_path
        run_book(store, counts_only=args.counts_only, tr_store_path=tr)
        return
    doc = pd.read_csv(CZ_DIR / "SignalDoc.csv")
    if args.step == "list":
        lines = build_list(doc)
        (ROOT / LIST_OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{LIST_OUT}: {sum(1 for ln in lines if '| yes |' in ln)} buildable of {len(predictors(doc))}")
    elif args.step == "select":
        ret = pd.read_csv(CZ_DIR / "PredictorLSretWide.csv", na_values=["NA"], parse_dates=["date"]).set_index("date")
        lines = selection_lines(selection(doc, ret))
        (ROOT / SELECT_OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines[:7]))
    elif args.step == "select-vwforce":
        lines = selection_lines(selection(doc, vwforce_returns(CZ_DIR / VWFORCE_FILE), vwforce=True), vwforce=True)
        (ROOT / SELECT_VW_OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines[:9]))


if __name__ == "__main__":
    main()
