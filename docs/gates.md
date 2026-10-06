# Gates before any live capital

1. Paper phase: >= 3 months of forward paper trading and >= 100 closed trades with modeled costs
   (10 bps/side large caps, 20 bps otherwise, plus SEC $20.60 per $1M sold and FINRA TAF $0.000195/share).
2. Strategy must show deflated-Sharpe significance with the full trial count logged (`research/trials.py`).
3. Monitor validation: two-week paper run logging per-source latency, alerts per rule, duplicate rate and
   human useful/noise ratings; prune rules that never produce an acted-on P2+.
4. Pre-defined live kill criterion written down (max drawdown or rolling-Sharpe floor).
5. Decide the Section 475(f) mark-to-market election by the prior-year filing deadline; log wash sales.
