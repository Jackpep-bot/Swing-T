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
