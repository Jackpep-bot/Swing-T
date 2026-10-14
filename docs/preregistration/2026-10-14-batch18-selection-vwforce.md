# Batch 18, step 2 rerun (amendment 1): the blind selection on VWforce series

Step 2 was rerun once after the first pass (VW originals only, `2026-10-14-batch18-selection.md`) came back empty; amendment `2026-10-14-batch18-amendment.md` was committed first. Series: CZ `PredictorAltPorts_LiqScreen_VWforce.zip` (long-short, value-weighted rebuild of every predictor). Everything else as below.

Committed 2026-10-14 before the book is built. Rule (card, fixed before any statistic): among the step-1 buildable predictors (`docs/preregistration/2026-10-14-batch18-list.md`), value-weighted original CZ series only (no VWforce file on the Mac), momentum family and GP excluded; mean monthly long-short return from January after publication through 2016-12, at least 60 months, t >= 2.0, and a positive in-sample mean; at most 10 by t. Returns after 2016-12 were dropped before anything was computed and were not looked at.

**Selected: DivYieldST, VolumeTrend**

| predictor | EW/VW | published | months | post-pub mean/yr | t | in-sample mean/yr | result |
|---|---|---|---|---|---|---|---|
| DivYieldST | EW | 1979 | 444 | +5.26% | 3.91 | +4.27% | SELECTED |
| VolumeTrend | EW | 1996 | 240 | +5.47% | 2.13 | +0.28% | SELECTED |
| cfp | EW | 2004 | 144 | +6.92% | 1.96 | +3.84% | post-publication t 1.96 < 2.0 |
| Illiquidity | EW | 2002 | 168 | +3.91% | 1.94 | +4.58% | post-publication t 1.94 < 2.0 |
| DolVol | EW | 1998 | 216 | +4.77% | 1.90 | +1.74% | post-publication t 1.90 < 2.0 |
| EP | EW | 1977 | 468 | +3.34% | 1.89 | +3.61% | post-publication t 1.89 < 2.0 |
| SP | EW | 1996 | 240 | +6.21% | 1.88 | +4.08% | post-publication t 1.88 < 2.0 |
| AnnouncementReturn | EW | 1996 | 240 | +3.95% | 1.73 | +9.26% | post-publication t 1.73 < 2.0 |
| EarningsConsistency | EW | 2009 | 84 | +5.85% | 1.64 | +3.00% | post-publication t 1.64 < 2.0 |
| ChEQ | EW | 2010 | 72 | +3.88% | 1.63 | +3.49% | post-publication t 1.63 < 2.0 |
| CompEquIss | EW | 2006 | 120 | +5.58% | 1.61 | +2.63% | post-publication t 1.61 < 2.0 |
| ReturnSkew3F | EW | 2015 | 12 | +7.53% | 1.57 | -1.60% | post-publication window 12 months (< 60) |
| DelEqu | EW | 2005 | 132 | +3.23% | 1.43 | +1.60% | post-publication t 1.43 < 2.0 |
| RevenueSurprise | EW | 2006 | 120 | +2.58% | 1.37 | -0.32% | post-publication t 1.37 < 2.0 |
| ShareIss5Y | EW | 2006 | 120 | +3.20% | 1.36 | +6.55% | post-publication t 1.36 < 2.0 |
| ReturnSkew | EW | 2015 | 12 | +8.77% | 1.33 | -1.37% | post-publication window 12 months (< 60) |
| zerotrade1M | EW | 2006 | 120 | +4.42% | 1.06 | +4.17% | post-publication t 1.06 < 2.0 |
| VolSD | EW | 2001 | 180 | +2.70% | 1.06 | +4.12% | post-publication t 1.06 < 2.0 |
| IndRetBig | EW | 2007 | 108 | +5.26% | 0.97 | +27.54% | post-publication t 0.97 < 2.0 |
| zerotrade12M | EW | 2006 | 120 | +4.12% | 0.95 | +5.14% | post-publication t 0.95 < 2.0 |
| zerotrade6M | EW | 2006 | 120 | +4.24% | 0.94 | +5.20% | post-publication t 0.94 < 2.0 |
| RoE | EW | 1996 | 240 | +2.56% | 0.90 | -0.16% | post-publication t 0.90 < 2.0 |
| MeanRankRevGrowth | EW | 1994 | 264 | +1.52% | 0.76 | +5.65% | post-publication t 0.76 < 2.0 |
| AssetGrowth | EW | 2008 | 96 | +2.79% | 0.75 | +10.34% | post-publication t 0.75 < 2.0 |
| AM | EW | 1992 | 288 | +2.31% | 0.65 | +2.65% | post-publication t 0.65 < 2.0 |
| ShareIss1Y | EW | 2008 | 96 | +1.76% | 0.64 | +6.75% | post-publication t 0.64 < 2.0 |
| IdioVol3F | VW | 2006 | 120 | +3.74% | 0.59 | +11.62% | post-publication t 0.59 < 2.0 |
| RealizedVol | VW | 2006 | 120 | +4.16% | 0.58 | +10.18% | post-publication t 0.58 < 2.0 |
| IdioVolAHT | VW | 2003 | 156 | +3.18% | 0.55 | +10.73% | post-publication t 0.55 < 2.0 |
| Coskewness | VW | 2000 | 192 | +1.10% | 0.48 | +3.43% | post-publication t 0.48 < 2.0 |
| MaxRet | VW | 2011 | 60 | +2.66% | 0.36 | +10.63% | post-publication t 0.36 < 2.0 |
| VolMkt | EW | 1996 | 240 | +1.22% | 0.28 | -0.02% | post-publication t 0.28 < 2.0 |
| Beta | EW | 1973 | 516 | +1.09% | 0.27 | +6.54% | post-publication t 0.27 < 2.0 |
| betaVIX | VW | 2006 | 120 | +0.83% | 0.24 | +13.08% | post-publication t 0.24 < 2.0 |
| roaq | EW | 2010 | 72 | +1.07% | 0.14 | +4.86% | post-publication t 0.14 < 2.0 |
| PriceDelaySlope | EW | 2005 | 132 | +0.42% | 0.10 | -0.52% | post-publication t 0.10 < 2.0 |
| PriceDelayTstat | EW | 2005 | 132 | +0.39% | 0.10 | -0.40% | post-publication t 0.10 < 2.0 |
| BetaFP | EW | 2014 | 24 | +1.22% | 0.06 | -0.06% | post-publication window 24 months (< 60) |
| PctAcc | EW | 2011 | 60 | -0.02% | -0.00 | +0.76% | post-publication t -0.00 < 2.0 |
| Size | EW | 1981 | 420 | -0.21% | -0.09 | +3.66% | post-publication t -0.09 < 2.0 |
| High52 | EW | 2004 | 144 | -0.50% | -0.12 | +3.63% | post-publication t -0.12 < 2.0 |
| CoskewACX | EW | 2006 | 120 | -0.67% | -0.15 | +2.01% | post-publication t -0.15 < 2.0 |
| ShareVol | EW | 1998 | 216 | -1.15% | -0.28 | +2.73% | post-publication t -0.28 < 2.0 |
| Price | EW | 1973 | 516 | -1.94% | -0.46 | +10.38% | post-publication t -0.46 < 2.0 |
| std_turn | EW | 2001 | 180 | -4.33% | -0.65 | +9.26% | post-publication t -0.65 < 2.0 |
| EarningsSurprise | EW | 1984 | 384 | -1.29% | -0.89 | +7.31% | post-publication t -0.89 < 2.0 |
| NumEarnIncrease | EW | 2012 | 48 | -1.85% | -0.95 | +1.45% | post-publication window 48 months (< 60) |
| EarnSupBig | EW | 2007 | 108 | -4.17% | -1.04 | +4.68% | post-publication t -1.04 < 2.0 |
| PriceDelayRsq | EW | 2005 | 132 | -6.52% | -1.49 | -3.25% | post-publication t -1.49 < 2.0 |
| BidAskSpread | EW | 1986 | 360 | -9.26% | -1.63 | +2.69% | post-publication t -1.63 < 2.0 |
| GP | VW | 2013 | 36 | - | - | - | excluded by family (card) |
| IndMom | EW | 1999 | 204 | - | - | - | excluded by family (card) |
| IntMom | VW | 2012 | 48 | - | - | - | excluded by family (card) |
| LRreversal | EW | 1985 | 372 | - | - | - | excluded by family (card) |
| MRreversal | EW | 1985 | 372 | - | - | - | excluded by family (card) |
| Mom12m | EW | 1993 | 276 | - | - | - | excluded by family (card) |
| Mom12mOffSeason | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| Mom6m | EW | 1993 | 276 | - | - | - | excluded by family (card) |
| MomOffSeason | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| MomRev | EW | 2006 | 120 | - | - | - | excluded by family (card) |
| MomSeason | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| MomSeasonShort | EW | 2008 | 96 | - | - | - | excluded by family (card) |
| MomVol | EW | 2000 | 192 | - | - | - | excluded by family (card) |
| ResidualMomentum | EW | 2011 | 60 | - | - | - | excluded by family (card) |
| STreversal | EW | 1990 | 312 | - | - | - | excluded by family (card) |
| TrendFactor | EW | 2016 | 0 | - | - | - | excluded by family (card) |

