# Batch 8: one re-test, started early because batches 5-7 finished (research thread, 2026-10-14)

## What batches 5-7 showed (all on claude/project-thread-fesglg, docs/preregistration/)
22 methods, none passed. Patterns that steer this and later batches:
- **Short holds lose to costs.** Every card holding 1-10 sessions lost money net in 2024-26
  (bensdorp_mr_selloff -49%, industry_leader_lag_smallmid -52%, ceo_cfo_buy_5day -28%), with turnover of 650-3,450%
  a year. New cards should trade far less.
- **Part-invested books cannot beat a strong SPY.** SPY made about 16% a year in 2024-26 (Sharpe 1.0). Low-beta or
  part-invested cards (merger, SEO, VRP overlay) lost to it on alpha even when their own trades were near flat.
  This is not special to this project: S&P's SPIVA scorecard has 79% of US large-cap active funds behind the S&P 500 in
  2025 and at least 80% of equity funds behind over 10 years
  (https://www.spglobal.com/spdji/en/spiva/article/spiva-us/, opened).
- **One near miss, not a candidate:** tax_loss_loser_rebound +29.7% over 2017-24 (net R t 3.00, alpha t 1.00), -3.1%
  in 2024-26.
- **Batch 7's merger card tested the wrong thing** (1 of 52 trades was a completed deal). Card 1 below fixes the flag
  and is counted as a second trial of that family.

## Kept

| # | Card | Different because | Grade | Expectation stated before the run |
|---|---|---|---|---|
| 1 | [merger_target_spread_capture_v2](merger_target_spread_capture_v2.md) (RE-TEST, 2 trials) | deal-spread payoff; flag now needs subject-only tenders or proxy + 8-K 1.01, a 10% premium and a pinned price | C | 15-30 deals/yr, +2 to +5%/yr on capital in use, likely FAIL vs SPY; read the exit table |

Not a weights card. Data: `form_events` (filer and subject CIKs), 8-K items, daily bars incl. delisted. Nothing new.

## Rejected this sweep
- **Option-implied-volatility deal screen (Alpha Architect 2018).** Needs target option IV history, not free; card 1
  uses a pinned-price stand-in.
- **More short-hold event or reversal cards found this sweep.** Not kept: batches 5-7 show holds under two weeks
  losing to costs across every family tried.

## Where the next batches look
Low-turnover, fully invested books that hold roughly market beta but tilt toward one stated edge, so the comparison
with SPY is about selection rather than exposure. Each must say its expected turnover; anything above 200% a year
needs a reason.
