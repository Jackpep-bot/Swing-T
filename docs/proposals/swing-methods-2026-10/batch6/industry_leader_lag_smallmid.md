---
slug: industry_leader_lag_smallmid
name: Small/mid stocks that have not yet followed a strong week by their industry's large caps, hold one week
originators: [Hou, "Industry information diffusion and the lead-lag effect in stock returns", RFS 20(4) 2007; Cohen & Lou, "Complicated firms", JFE 2012]
category: strategy
decision: implement
holding_period_days: [5, 5]
timeframe: daily bars, weekly rebalance; SIC codes
direction: long
universe: followers = SMALLMID (batch 5 definition); leaders = the 500 largest store stocks
regimes_good: []
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: draft_card (research thread batch 6, 2026-10-13; needs SIC codes as within_industry_reversal_no_news)
---

# Industry leaders lead, small caps lag

## Why this one is genuinely different
Nothing in the catalog uses one stock's move to trade another. This card trades slow information flow: when an
industry's big companies rally on news, the small companies in the same industry tend to catch up over the next
week or so because fewer people watch them. It uses the small/mid universe Jack said is fine, and the signal comes
from large, liquid stocks, so it is not the small cap's own noisy price history.

## One-line summary
Each Friday, find industries whose large caps rose most this week; buy that industry's small/mid stocks that
lagged; sell the next Friday.

## Evidence
- Hou 2007 (RFS; https://ideas.repec.org/a/oup/rfinst/v20y2007i4p1113-1138.html): within-industry, big-firm
  returns lead small-firm returns at weekly horizons, 1963-2001; the effect is mostly within industry. A 2013
  Management Science paper (https://pubsonline.informs.org/doi/fpi/10.1287/mnsc.2013.1722, abstract opened)
  treats within-industry diffusion as the established baseline and argues cross-industry versions are spurious.
- Against: sample ends 2001; small-firm costs; no net test. Grade D.

## Engine version (pre-register this one)
- Industry: two-digit SIC (see `within_industry_reversal_no_news`). Industries need >= 3 leaders and >= 10 followers.
- Leader return L = equal-weight 5-session return of the industry's leaders, Friday close to Friday close.
- Signal industries: L in the top 20% of industries that week and L >= +3%.
- Followers bought: in a signal industry, follower 5-session return <= L - 3 points, close >= $3, `med_dv_63` >= $1M.
  Up to 30 names, ranked by (L - own return), equal weight.
- Entry Monday open, exit Friday close (5 sessions). No stop beyond catastrophe 15%.
- `event_avoid_filters` applies; skip followers with their own 8-K 2.02 in the week.

## Grading
Batch standard plus alpha vs SPY and IWM in both windows, haircut over this batch's trials.

## Expectation stated before the run
Gross +0.2% to +0.5% a week over IWM; net close to zero after small-cap spreads.

## Common mistakes
Leaders and followers overlapping (a 500th-largest stock in both); using the current mcap rank instead of the
signal-day rank.
