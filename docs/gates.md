# Gates before any live capital

1. Paper phase: >= 3 months of forward paper trading and >= 100 closed trades with modeled costs
   (10 bps/side large caps, 20 bps otherwise, plus SEC $20.60 per $1M sold and FINRA TAF $0.000195/share).
2. Strategy must show deflated-Sharpe significance with the full trial count logged (`research/trials.py`).
   "Full" means ALL trials in the log, every strategy and sweep (`trial_count(None)`), not only this strategy's:
   every trial was a look at the same market data. `research.metrics.multiple_testing(sharpe, n_obs, skew, kurt)`
   returns both numbers below; `swing backtest` deflates by the total count.
   - Deflated Sharpe (Bailey-Lopez de Prado) >= 0.95 against the all-trials count.
   - Haircut rule (Harvey-Liu 2015, Bonferroni): the haircut Sharpe (`haircut_sharpe`, annual, all-trials count)
     must stay > 0 after costs, and planning uses the haircut Sharpe, never the raw one. For a rule taken from a
     paper or book, also assume the live edge is at most half the published edge (McLean-Pontiff post-publication
     decay, catalog `post_publication_haircut`).
   - Yardstick (owner, 2026-10-13): on the leaderboard, the cards and the reality check the edge is net R minus
     what SPY returned over the same holding span on the same dollars (`research.cards.market_r`, beta 1), because
     every strategy is long-only and most positive gross R was the index going up (docs/attribution.md).
     Pre-registered portfolio tests keep their own registered rule (alpha vs SPY with a Bonferroni t).
   - Full-period test (owner, 2026-10-14 16:14 UTC, decision card in the project chat: "Add full-period test").
     Every card pre-registered after that moment (batch 11 on) is graded three ways, all written into its
     pre-registration before it runs: the two windows as before (2017-01-01 .. 2024-10-04 and 2024-10-07 ..
     2026-10-05) and one pooled 2017-26 window. Engine cards: both windows are replayed for every card (no gating
     on the 2024-26 result) and the pooled window is the two replays joined end to end
     (`research.prereg_eval --pooled`, `scripts/run_prereg_batch.sh` with POOLED=1). Weights cards: the pooled
     window is one simulation over 2017-01-01 .. 2026-10-05. A card PASSES on either route: its registered rule
     met in both windows, or the same rule met in the pooled window (haircut Sharpe > 0, net R per trade > 0 for
     engine cards, alpha vs SPY > 0 with alpha t >= `alpha_t_critical(n_trials)`) with alpha vs SPY above zero in
     each window. The last condition and the joined-replay reading are the implementer's, recorded here so a pooled
     pass cannot rest on one half. The pooled view is part of the same trial (no extra trial is counted). Cards
     tested before (batches 5-10, including batch 8, which was registered before the decision) are not re-graded.
   - Bill rate (correctness fix, 2026-10-14; research thread's note in batch 11's README): the alpha regression
     takes BIL's daily return off both sides, (r - BIL) on (SPY - BIL) (`prereg_eval._vs_benchmark(rf=...)`, used by
     `prereg_eval` and `research.b9_books.grade`), so a book in bills cannot show the bill rate as alpha. The store's
     bars are price-only and BIL's price barely moves (91.38 in January 2016, 91.51 in October 2026), so with this
     store the change is about nil: re-grading batches 5-8 moved no alpha by more than 0.1% a year and changed no
     verdict. What price-only data still leaves out on both sides: dividends, and interest on a book's idle cash.
   - Total return (build, 2026-10-14; coordinator's survey item b): dividend-inclusive figures are reported BESIDE the
     registered price-only grade, never instead of it, until the owner says otherwise. Store: data/live/replay_b9_tr.duckdb
     (scripts/build_tr_store.py, config/prereg_b9_tr.yaml); summary docs/total_return/README.md. On it SPY made
     +15.3% a year pooled vs +13.6% price-only; no verdict changes.
   - CZ check (manual, catalog `open_factor_benchmark_cz`): for any signal that re-implements a published
     predictor (momentum, reversal, 52-week high, insider, accruals...), download the matching monthly long-short
     portfolio returns from Chen-Zimmermann Open Source Asset Pricing (openassetpricing.com) and compare them with
     our own implementation's monthly long-short returns over the overlapping window. Proceed only if the sign
     matches and the correlation is clearly positive; note the file, window and correlation in the strategy card.
     This is a hand step (download outside the engine; no network in tests or CI).
3. Monitor validation: two-week paper run logging per-source latency, alerts per rule, duplicate rate and
   human useful/noise ratings; prune rules that never produce an acted-on P2+.
4. Pre-defined live kill criterion written down (max drawdown or rolling-Sharpe floor).
5. Decide the Section 475(f) mark-to-market election by the prior-year filing deadline; log wash sales.
