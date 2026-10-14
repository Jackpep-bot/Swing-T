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
from collections.abc import Sequence

import pandas as pd

from swing_engine.core.config import ROOT

CZ_DIR = ROOT / "data" / "research" / "chen_zimmermann"
LIST_OUT = "docs/preregistration/2026-10-14-batch18-list.md"
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


def main(argv: Sequence[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--step", choices=["list"], required=True)
    args = ap.parse_args(argv)
    doc = pd.read_csv(CZ_DIR / "SignalDoc.csv")
    if args.step == "list":
        lines = build_list(doc)
        (ROOT / LIST_OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{LIST_OUT}: {sum(1 for ln in lines if '| yes |' in ln)} buildable of {len(predictors(doc))}")


if __name__ == "__main__":
    main()
