# Batch 9: slow, fully invested books (research thread, 2026-10-14)

Follows the batch 5-7 lessons in the batch 8 README: short holds lose to costs, and part-invested books cannot beat
a strong SPY. Both cards here are fully invested, trade rarely, and are **weights cards** (fixed target weights, not
stop-sized), as the Mac asked to be told up front.

| # | Card | Different because | Grade | Turnover | Expectation stated before the run |
|---|---|---|---|---|---|
| 1 | [sp500_momentum_index_replica](sp500_momentum_index_replica.md) | cap x score weights, vol-adjusted 12-1, twice-yearly, no stops; copies a live index with +4.4%/yr alpha since 2015 | B- | 80-150%/yr | alpha 0 to +3% 2017-24, +3 to +8% 2024-26; likely FAIL on t in one window |
| 2 | [leveraged_sp500_trend_switch](leveraged_sp500_trend_switch.md) | no stock picking; 2x index only above the 200-day, T-bills below | C | a few switches/yr | beats SPY on return with deeper drops; alpha ~0; judged on money made and drawdown |

Data: card 1 uses the store's bars and `mcap_pit`; card 2 needs daily SSO bars from 2016 (same Alpaca bars source as
SVXY/IWD/IWF/BIL). Nothing new to approve.

Honesty note on card 1: it was chosen knowing the live ETF's record, and its alpha is concentrated in 2023-2026, the
strongest momentum stretch since the dot-com years. A pass means a forward test, nothing more.

## Rejected this sweep
- **MSCI USA Momentum (MTUM rules).** Live alpha only +0.63% a year since Oct 2015, beta 1.05
  (https://etfsavant.com/mtum-vs-spmo/, opened); the S&P version (card 1) is the stronger record of the two.
- **3x leverage rotation.** Same source family as card 2; 3x daily-reset funds had -99% buy-and-hold drawdowns in the
  long history, and one trial of the idea is enough.
