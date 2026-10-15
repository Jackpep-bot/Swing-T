# Batch 3 candidates (research thread, 2026-10-10)

Five candidates were fact-checked in parallel. Only two are worth a trial, and both are low-prior. Every one of the
five turned out to exist in the catalog already; the two kept here were never tested in their published form
(large-cap, monthly portfolio, graded on alpha vs SPY).

| # | Card | Universe | Evidence | Expectation stated before the run |
|---|---|---|---|---|
| 1 | [large_cap_gross_profitability](large_cap_gross_profitability.md) | top-500 non-financials | C: peer-reviewed, cost-proof (0.03%/month), large-cap long side mostly beta; RMW -10% in 2025 | small + alpha 2017-24, negative 2024-26 |
| 2 | [large_cap_residual_momentum](large_cap_residual_momentum.md) | top-500 | C: strong long-short history incl. largest decile; weak after 2009 | near-zero alpha both windows |

Both register alpha vs SPY from daily net returns as a pass condition (the grader addition batch 2 needed), because
batch 2's repurchasers passed the standard rule and had zero alpha.

Data check (claude/project-thread-jdz24e @ 9d828c1): `data.fundamentals.gross_profitability_asof` and the
`ff3_resid_mom_756_231` feature already exist; no new data needed.

Side finding: the leaderboard's `residual_momentum` 2024-26 row is 108 signals, all `narrow_uptrend`, 0% win and
exactly -0.74R gross at 5, 10 and 20 sessions. That looks like one batch stopped out together or a scoring fault and
is worth checking before that row counts as evidence.

## Looked at and rejected
- **Earnings announcement premium (Frazzini-Lamont; Savor-Wilson)**: Heitz, Narayanamoorthy & Zekhnini ("The
  Disappearing Earnings Announcement Premium", SSRN 3296537, rev. 2025) find the weekly announcer premium fell from
  32.6 bp value-weighted (t=3.5) in 1994-2003 to 8.7 bp (t=0.97) in 2005-2016, tied to 2004 8-K rules. The S&P 500
  announcement-day excess in 2010-21 is about 8 bp (Liu, Mao, Tang & Zhou, AFA 2024), below a 20 bp round trip. No
  net-of-cost study exists. Leaderboard version already about -0.00R net at 20 sessions.
- **Turn of the month on SPY (McConnell-Xu 2008)**: Han, Han & Tian (FRL 71, 2025) find the effect disappears after
  2001; QuantSeeker (2025) finds the classic window "largely disappeared over the past decade" on SPY and cost-included
  CAGR below buy-and-hold. 12 round trips cost about 2.4%/yr at the engine's floor. Settlement moved to T+2 (2017) and
  T+1 (2024), which shifts the Etula et al. (RFS 2020) payment-flow window. Already replayed on SPY (`turn_of_month`).
- **Pre-holiday effect**: Ko & Yang (Critical Finance Review) find it vanished in the value-weighted index after 1990
  (t=1.19) and in the S&P 500 1983-2019 (t=0.64); survives only in small caps.
- **Large-cap low volatility / low beta (Baker-Bradley-Wurgler; Blitz-van Vliet)**: pre-2008 CAPM alpha about +2%/yr
  (t=2.03), but the live S&P 500 Low Volatility index (2011-Mar 2026) returned 10.45%/yr vs 13.24% with risk-adjusted
  0.90 vs 0.94, and lagged by 25.6, 10.8 and 13.5 points in 2023, 2024 and 2025. Novy-Marx (2016) finds the large-cap
  alpha insignificant once profitability and value are controlled. Narrow mega-cap rallies are its known failure mode.
