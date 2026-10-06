# Feature panel contract

`features.panel.build_panel(bars: pd.DataFrame, market: pd.DataFrame | None = None) -> pd.DataFrame`
Input `bars` is long format from `data.store.Store.read_bars`: columns `symbol, ts, open, high, low, close, volume, vwap, adj_close`
(`ts` is a tz-aware America/New_York daily timestamp). `market` is the same shape for SPY (optional). Output is the same long
frame with these columns appended (all computed per symbol with only past data; NaN until warm-up):

Indicators (`features/indicators.py`): sma_10 sma_20 sma_50 sma_200 ema_9 ema_21 rsi_2 rsi_14 macd macd_signal macd_hist
bb_upper_20 bb_lower_20 bb_width_20 atr_14 atr_pct_14 (atr/close).
Cross-section (`features/cross_section.py`): ret_1d ret_5d ret_21d ret_63d ret_126d ret_252d mom_12_1 (252d return skipping last 21d)
rev_5d rev_21d vol_21d vol_63d (annualized realized vol) dollar_vol_20d avg_vol_20d avg_vol_50d amihud_21d high_52w low_52w
dist_52w_high (close/high_52w - 1) rvol_day (volume/avg_vol_20d) gap_pct (open/prev_close - 1) range_pct ((high-low)/close)
close_pos ((close-low)/(high-low)) up_days_3 prev_close.
Levels (`features/levels.py`, pivot-based support/resistance over a lookback, default 60 bars, pivot width 5):
support_1 resistance_1 (nearest level below/above prior close) range_width (resistance_1 - support_1) level_touch_pct
(distance of low to support_1 as % of close) level_break (1 if close > prior resistance_1 else 0).
Patterns (`features/patterns.py`): vcp_contraction (ratio of last contraction range to first, lower = tighter) base_len
(bars since 52w high was within 5%) burst_4pct (Stockbee: close/prev_close>=1.04 & volume>prev_volume & volume>=100000)
breakout_52w (close > prior high_52w & volume >= 1.5*avg_vol_50d) inside_day key_reversal (new low then close > prev close on volume>=1.5x).
Regime (`features/regime.py`): trend_state (1 up: close>sma_50>sma_200 and sma_50 rising; -1 down: mirror; else 0)
vol_regime (0 low / 1 normal / 2 high by rolling percentile of vol_21d) and, when `market` is given, market_trend_state and
market_vol_regime broadcast to every row.
RVOL profile (`features/rvol.py`): `build_rvol_profile(intraday_bars, days=20)` returns per-symbol cumulative-volume-by-minute averages
used by the live monitor (`rvol_now(symbol, cum_volume, minute_of_day, profile)`).

Rules: pure pandas/numpy, vectorized by `groupby("symbol")`, no look-ahead (verify with the shift test in tests), deterministic.
