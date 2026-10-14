# Total-return figures beside the registered price-only grades

Build (b), 2026-10-14. The same registered rules run on `data/live/replay_b9_tr.duckdb` (scripts/build_tr_store.py: every bar back-adjusted for the cash dividends in the Alpaca feed, stocks and ETFs alike, SPY and BIL included). **Descriptive only**: the registered grade stays the price-only one and no verdict changes (docs/gates.md, Total return). Full outputs: docs/total_return/b*-tr.md. Caveat: on the total-return store the books are reselected from dividend-adjusted closes (momentum ranks, the $5 / $10 price floors and the dollar-volume guard all read adjusted prices, and the trend switch reads SPY's total-return series), so a difference is not only the dividends; that is why a few books show a lower total-return figure. Batch 12 needs its own store (replay_b12) and was not rerun; batches 15-18 report their total-return figure inside their own results where the card asked.

| batch | card | window | price-only return/yr | alpha/yr (t) | total-return return/yr | alpha/yr (t) | SPY price-only | SPY total-return |
|---|---|---|---|---|---|---|---|---|
| b9 | sp500_momentum_index_replica | A | +17.0% | +4.1% (1.30) | +18.3% | +3.7% (1.14) | +12.4% | +14.2% |
| b9 | sp500_momentum_index_replica | B | +27.0% | +7.1% (0.73) | +25.5% | +6.1% (0.63) | +16.4% | +17.6% |
| b9 | leveraged_sp500_trend_switch | A | +14.5% | +4.2% (0.63) | +12.7% | +0.5% (0.08) | +12.9% | +14.8% |
| b9 | leveraged_sp500_trend_switch | B | +19.3% | +4.2% (0.36) | +20.7% | +4.3% (0.37) | +16.4% | +17.6% |
| b10 | midcap_momentum_index_replica | A | +13.0% | +0.0% (0.00) | +13.7% | -1.3% (-0.30) | +12.4% | +14.2% |
| b10 | midcap_momentum_index_replica | B | +8.2% | -5.6% (-0.26) | +9.1% | -9.0% (-0.89) | +16.4% | +17.6% |
| b10 | smallcap_momentum_index_replica | A | +13.8% | +0.4% (0.07) | +13.7% | -1.5% (-0.28) | +12.4% | +14.2% |
| b10 | smallcap_momentum_index_replica | B | +16.9% | -1.1% (-0.11) | +17.6% | -1.1% (-0.12) | +16.4% | +17.6% |
| b11 | dividend_increase_drift | A | +8.6% | -4.1% (-1.24) | +10.9% | -3.7% (-1.13) | +12.9% | +14.8% |
| b11 | dividend_increase_drift | B | +6.3% | -7.5% (-1.20) | +8.3% | -6.9% (-1.10) | +16.4% | +17.6% |
| b11 | dividend_increase_drift | pooled | +8.1% | -5.0% (-1.68) | +10.3% | -4.4% (-1.52) | +13.6% | +15.3% |
| b11 | russell_recon_migrant_drift | A | +7.7% | -5.1% (-0.86) | +10.6% | -4.1% (-0.68) | +12.9% | +14.8% |
| b11 | russell_recon_migrant_drift | B | +2.4% | -10.6% (-0.96) | +2.6% | -11.7% (-1.10) | +16.4% | +17.6% |
| b11 | russell_recon_migrant_drift | pooled | +6.6% | -6.6% (-1.25) | +8.9% | -5.8% (-1.10) | +13.6% | +15.3% |
| b13 | mispricing_short_leg_exclusion_large | A | +12.7% | -0.3% (-0.29) | +15.2% | +0.1% (0.15) | +12.9% | +14.8% |
| b13 | mispricing_short_leg_exclusion_large | B | +15.5% | +0.2% (0.10) | +17.0% | +0.2% (0.12) | +16.4% | +17.6% |
| b13 | mispricing_short_leg_exclusion_large | pooled | +13.2% | -0.4% (-0.39) | +15.5% | +0.0% (0.03) | +13.6% | +15.3% |
| b13 | mispricing_short_leg_exclusion_mid | A | +8.2% | -5.0% (-1.33) | +10.0% | -5.0% (-1.33) | +12.9% | +14.8% |
| b13 | mispricing_short_leg_exclusion_mid | B | +7.6% | -6.2% (-0.81) | +9.3% | -5.9% (-0.76) | +16.4% | +17.6% |
| b13 | mispricing_short_leg_exclusion_mid | pooled | +8.0% | -5.5% (-1.64) | +9.8% | -5.3% (-1.59) | +13.6% | +15.3% |
| b14 | sp500_four_signal_composite | A | +9.1% | -3.3% (-1.20) | +10.7% | -3.4% (-1.26) | +12.9% | +14.8% |
| b14 | sp500_four_signal_composite | B | +25.9% | +8.9% (1.17) | +25.8% | +7.9% (1.10) | +16.4% | +17.6% |
| b14 | sp500_four_signal_composite | pooled | +12.3% | -0.9% (-0.35) | +13.6% | -1.2% (-0.46) | +13.6% | +15.3% |
| b14 | vol_scaled_momentum_replica | A | +11.7% | +1.1% (0.37) | +12.9% | +0.5% (0.15) | +12.9% | +14.8% |
| b14 | vol_scaled_momentum_replica | B | +19.8% | +4.7% (0.66) | +20.7% | +4.4% (0.61) | +16.4% | +17.6% |
| b14 | vol_scaled_momentum_replica | pooled | +13.3% | +1.9% (0.68) | +14.4% | +1.3% (0.46) | +13.6% | +15.3% |
