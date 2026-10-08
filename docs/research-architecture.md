# Architecture research (verified 2026-10-06)

## Data providers
| Provider | Plan | Price | Notes |
|---|---|---|---|
| Massive (ex-Polygon) | Stocks Basic | $0 | EOD, 5 calls/min, 2 yrs history, MCP + REST. 32k+ active+delisted tickers (survivorship-bias free via `active=false`). Technical indicators server-side (SMA/EMA/MACD/RSI). Short interest, splits (2008+), filings index, news (hourly). |
| Massive | Starter / Developer / Advanced | $29 / $79 / $199 | 15-min delayed WS (Starter, Developer) vs real-time WS + quotes (Advanced). History 5 / 10 / 20+ yrs. Flat files on Starter+. Unlimited calls. Non-pro only. MCP repo: github.com/massive-com/mcp_massive. |
| EODHD | EOD All World (+ S&P constituents add-on) | $19.99 (+ $29.99) | `delisted=1` symbol list; point-in-time index membership needs the add-on. |
| Alpaca | Basic / Algo Trader Plus | $0 / $99 | Basic: IEX prints, 30 WS symbols, 200 req/min, ~08:00-17:00 ET effective; Plus: SIP, unlimited symbols, 04:00-20:00. News WS (Benzinga) believed free on Basic (verify on paper key). Corporate actions endpoint free. Paper trading free, no funding. |
| Alpha Vantage | free | $0 | `EARNINGS_CALENDAR` CSV (25 req/day free) for earnings blackout. NEWS_SENTIMENT is premium now. |
| Quiver Quant | Hobbyist / Trader | $30 / $75 | REST api.quiverquant.com (55 paths, bearer token), official MCP mcp.quiverquant.com (18 tools; Hobbyist 10). Tier 2 ($75) has Form 4 insiders which is the dataset with academic evidence (Cohen-Malloy-Pomorski 2012: opportunistic insider long-short ~82 bps/mo VW alpha; buys +90 bps/mo vs all insider trades). Congressional trades: no post-STOCK-Act alpha, 30-45 day lag. Timestamp on ReportDate/Filed/Quiver_Upload_Time, never TransactionDate; drop ExcessReturn/PriceChange fields (look-ahead). |
| SEC EDGAR | free | $0 | Form 4 (parse XML: transactionCode P + acquiredDisposedCode A), current filings Atom feed, EFTS full-text. 10 req/s, User-Agent with contact required. |

## Backtest / ML stack
- vectorbt 1.1.1 (Python 3.11-3.14) for vectorized sweeps + rolling/expanding walk-forward; plain pandas engine as fallback.
- backtrader unmaintained (last release 2023-04). zipline-reloaded/backtesting.py research-only. Lumibot 4.6.4 if event-driven live parity on Alpaca is wanted.
- LightGBM 4.7 cross-sectional rank model on 30-100 price/volume features (momentum 1-12m, 1w/1m reversal, realized/idio vol, dollar volume, Amihud, 52w-high distance, volume shocks). Predict 5-20 day forward return RANK. Expect monthly R2oos ~0.3-0.5%; 60%+ haircut after microcaps and costs.
- Methodology: walk-forward (expanding, retrain yearly) + combinatorial purged CV (purge = label horizon, embargo), log every trial, Deflated Sharpe with true trial count, t-stat > 3, 10/20 bps per side, delisting returns, point-in-time constituents.
- Regime overlay: GARCH / realized-vol thresholds or 2-3 state HMM with FILTERED probabilities, lagged one day; scales exposure, judged by drawdown reduction.
- Avoid as alpha: LSTM/transformer price regression, TA-Lib candlestick/chart-pattern libraries as triggers, end-to-end LLM trading agents (StockBench/Alpha Illusion: underperform buy-and-hold, look-ahead contamination).

## Broker / legal
- FINRA retired the Pattern Day Trader rule effective 2026-06-04 (brokers phase in to 2027-10-20). Alpaca: intraday margin framework; $2,000 min for margin/short. Read the broker's current treatment; do not hardcode $25k.
- Cash accounts: T+1 settlement; good-faith violations if selling before settlement; size from settled cash.
- Fees: SEC $20.60 per $1M sold (FY2026), FINRA TAF $0.000195/share capped $9.79.
- Taxes: short-term = ordinary income; wash sales apply unless Section 475(f) elected by prior-year deadline.

## Liquid (liquid.trade)
LiquidX AI, Inc. (Delaware). Non-custodial perp-DEX aggregator (Hyperliquid, Lighter, Ostium). "Stocks" are leveraged synthetic perps up to 20x; not a broker-dealer by its own ToS; Co-Invest MCP (OAuth 2.1, read/trade scopes, $10k paper mode) launched 2026-05-26. Decision: never an execution venue for the equity book; read scope only if connected.

## Claude usage
- Haiku 4.5 ($1/$5 per MTok, cache read $0.10; min cacheable prefix 4,096 tokens) for bulk classification.
- Sonnet 5.5 ($2/$10) for the daily rubric review with structured outputs (`output_config.format` json_schema).
- Opus 5.5 ($4/$20) for weekly strategy-code iteration.
- Agent SDK governance: PreToolUse hooks deny order tools without approval; PostToolUse audit log; close_all/cancel_all disallowed.
