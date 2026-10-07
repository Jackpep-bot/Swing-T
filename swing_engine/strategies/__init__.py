"""Swing setups. One module per strategy; each registers itself with `@register("strategy", name)`.

All strategies are long-only, read only feature-panel columns from docs/feature-contract.md, and emit fully
specified `Signal`s (entry = as-of close as the next-open reference, stop, target, reward_risk, score).
Every threshold is a `default_params` entry overridable from `config/settings.yaml`.

Registered strategies (`registry.names("strategy")`):

- ``sr_bounce``       Schwab support bounce: low touches support_1, close back above, stop an ATR multiple
                      below the level, target = resistance_1. Trend filter trend_state >= 0.
- ``sr_breakout``     Schwab breakout: close > prior resistance_1 on >= 1.5x avg_vol_50d, measured-move
                      target = level + range_width, stop just below the level (or ATR multiple).
- ``pullback_trend``  Raschke/Qullamaggie pullback in an uptrend (trend_state == 1) to ema_21/sma_20 on
                      drying volume; entry on close > prior high, stop below the pullback low, target 2R
                      or the prior swing high.
- ``breakout_52w``    Minervini-style 52-week-high breakout on >= 1.5x avg_vol_50d with the close near the
                      high, ATR-multiple stop, 2R target, optional VCP tightness filter.
- ``momentum_burst``  Stockbee 4% momentum burst from a quiet prior day (<= 2% move, not up 3 days);
                      stop below the entry bar low, 2R reference target, 3-5 day time exit (`max_hold_days`).
- ``rsi2_meanrev``    Connors RSI-2: close > sma_200 and rsi_2 < 10; exit on close > sma_10, rsi_2 > 70 or a
                      5-day time stop (`max_hold_days`); protective stop = ATR multiple; target = sma_10.
- ``insider_cluster`` Form 4 cluster-buy follow-through: needs an optional panel column
                      `insider_cluster_score` (returns [] when absent); ATR stop, 2R target.

Shared plumbing lives in `_base.PanelStrategy` (point-in-time slicing, prior-bar columns, signal geometry
checks, market-regime gate). Strategies with rule exits implement `should_exit(row, bars_held)`; their time limit is the `max_hold_days`
param, which `research.backtest` also reads as its per-strategy hold cap.
"""
