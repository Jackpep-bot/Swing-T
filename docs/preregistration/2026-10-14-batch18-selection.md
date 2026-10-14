# Batch 18, step 2: the blind selection

Committed 2026-10-14 before the book is built. Rule (card, fixed before any statistic): among the step-1 buildable predictors (`docs/preregistration/2026-10-14-batch18-list.md`), value-weighted original CZ series only (no VWforce file on the Mac), momentum family and GP excluded; mean monthly long-short return from January after publication through 2016-12, at least 60 months, t >= 2.0, and a positive in-sample mean; at most 10 by t. Returns after 2016-12 were dropped before anything was computed and were not looked at.

**Selected: none: no card (the rule leaves nothing)**

| predictor | EW/VW | published | months | post-pub mean/yr | t | in-sample mean/yr | result |
|---|---|---|---|---|---|---|---|
| IdioVol3F | VW | 2006 | 120 | +3.74% | 0.59 | +11.62% | post-publication t 0.59 < 2.0 |
| RealizedVol | VW | 2006 | 120 | +4.16% | 0.58 | +10.18% | post-publication t 0.58 < 2.0 |
| IdioVolAHT | VW | 2003 | 156 | +3.18% | 0.55 | +10.73% | post-publication t 0.55 < 2.0 |
| Coskewness | VW | 2000 | 192 | +1.10% | 0.48 | +3.43% | post-publication t 0.48 < 2.0 |
| MaxRet | VW | 2011 | 60 | +2.66% | 0.36 | +10.63% | post-publication t 0.36 < 2.0 |
| betaVIX | VW | 2006 | 120 | +0.83% | 0.24 | +13.08% | post-publication t 0.24 < 2.0 |
| AM | EW | 1992 | 288 | - | - | - | equal-weighted original series (no VWforce file) |
| AnnouncementReturn | EW | 1996 | 240 | - | - | - | equal-weighted original series (no VWforce file) |
| AssetGrowth | EW | 2008 | 96 | - | - | - | equal-weighted original series (no VWforce file) |
| Beta | EW | 1973 | 516 | - | - | - | equal-weighted original series (no VWforce file) |
| BetaFP | EW | 2014 | 24 | - | - | - | equal-weighted original series (no VWforce file) |
| BidAskSpread | EW | 1986 | 360 | - | - | - | equal-weighted original series (no VWforce file) |
| ChEQ | EW | 2010 | 72 | - | - | - | equal-weighted original series (no VWforce file) |
| CompEquIss | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |
| CoskewACX | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |
| DelEqu | EW | 2005 | 132 | - | - | - | equal-weighted original series (no VWforce file) |
| DivYieldST | EW | 1979 | 444 | - | - | - | equal-weighted original series (no VWforce file) |
| DolVol | EW | 1998 | 216 | - | - | - | equal-weighted original series (no VWforce file) |
| EP | EW | 1977 | 468 | - | - | - | equal-weighted original series (no VWforce file) |
| EarnSupBig | EW | 2007 | 108 | - | - | - | equal-weighted original series (no VWforce file) |
| EarningsConsistency | EW | 2009 | 84 | - | - | - | equal-weighted original series (no VWforce file) |
| EarningsSurprise | EW | 1984 | 384 | - | - | - | equal-weighted original series (no VWforce file) |
| GP | VW | 2013 | 36 | - | - | - | excluded by family (card) |
| High52 | EW | 2004 | 144 | - | - | - | equal-weighted original series (no VWforce file) |
| Illiquidity | EW | 2002 | 168 | - | - | - | equal-weighted original series (no VWforce file) |
| IndMom | EW | 1999 | 204 | - | - | - | excluded by family (card) |
| IndRetBig | EW | 2007 | 108 | - | - | - | equal-weighted original series (no VWforce file) |
| IntMom | VW | 2012 | 48 | - | - | - | excluded by family (card) |
| LRreversal | EW | 1985 | 372 | - | - | - | excluded by family (card) |
| MRreversal | EW | 1985 | 372 | - | - | - | excluded by family (card) |
| MeanRankRevGrowth | EW | 1994 | 264 | - | - | - | equal-weighted original series (no VWforce file) |
| Mom12m | EW | 1993 | 276 | - | - | - | excluded by family (card) |
| Mom12mOffSeason | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| Mom6m | EW | 1993 | 276 | - | - | - | excluded by family (card) |
| MomOffSeason | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| MomRev | EW | 2006 | 120 | - | - | - | excluded by family (card) |
| MomSeason | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| MomSeasonShort | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| MomVol | EW | 2000 | 192 | - | - | - | excluded by family (card) |
| NumEarnIncrease | EW | 2012 | 48 | - | - | - | equal-weighted original series (no VWforce file) |
| PctAcc | EW | 2011 | 60 | - | - | - | equal-weighted original series (no VWforce file) |
| Price | EW | 1973 | 516 | - | - | - | equal-weighted original series (no VWforce file) |
| PriceDelayRsq | EW | 2005 | 132 | - | - | - | equal-weighted original series (no VWforce file) |
| PriceDelaySlope | EW | 2005 | 132 | - | - | - | equal-weighted original series (no VWforce file) |
| PriceDelayTstat | EW | 2005 | 132 | - | - | - | equal-weighted original series (no VWforce file) |
| ResidualMomentum | EW | 2011 | 60 | - | - | - | excluded by family (card) |
| ReturnSkew | EW | 2015 | 12 | - | - | - | equal-weighted original series (no VWforce file) |
| ReturnSkew3F | EW | 2015 | 12 | - | - | - | equal-weighted original series (no VWforce file) |
| RevenueSurprise | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |
| RoE | EW | 1996 | 240 | - | - | - | equal-weighted original series (no VWforce file) |
| SP | EW | 1996 | 240 | - | - | - | equal-weighted original series (no VWforce file) |
| STreversal | EW | 1990 | 312 | - | - | - | excluded by family (card) |
| ShareIss1Y | EW | 2008 | 96 | - | - | - | equal-weighted original series (no VWforce file) |
| ShareIss5Y | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |
| ShareVol | EW | 1998 | 216 | - | - | - | equal-weighted original series (no VWforce file) |
| Size | EW | 1981 | 420 | - | - | - | equal-weighted original series (no VWforce file) |
| TrendFactor | EW | 2016 | 0 | - | - | - | excluded by family (card) |
| VolMkt | EW | 1996 | 240 | - | - | - | equal-weighted original series (no VWforce file) |
| VolSD | EW | 2001 | 180 | - | - | - | equal-weighted original series (no VWforce file) |
| VolumeTrend | EW | 1996 | 240 | - | - | - | equal-weighted original series (no VWforce file) |
| cfp | EW | 2004 | 144 | - | - | - | equal-weighted original series (no VWforce file) |
| roaq | EW | 2010 | 72 | - | - | - | equal-weighted original series (no VWforce file) |
| std_turn | EW | 2001 | 180 | - | - | - | equal-weighted original series (no VWforce file) |
| zerotrade12M | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |
| zerotrade1M | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |
| zerotrade6M | EW | 2006 | 120 | - | - | - | equal-weighted original series (no VWforce file) |

