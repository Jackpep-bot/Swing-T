# Source notes

## Schwab, "Swing Trading Stocks: Strategies and Indicators" (video, 2024-05-14, beginner)
What to implement:
- Swing trade = days to a couple of weeks; trade WITH the broader trend (upswings in uptrends, downswings in downtrends; both in sideways). -> `features/regime.py` trend classification; strategies take a `regime` argument.
- Three decisions before every trade: entry, exit, size. -> `Signal` always carries entry, stop, target; `risk/sizing.py` owns size.
- Support/resistance **bounce**: price reaches a prior S/R level and turns; target = the opposite prior level. (HON ~$170 low -> target ~$200 prior high.) -> `strategies/sr_bounce.py`.
- Support/resistance **breakout**: close beyond the level; target = breakout level +/- the prior range (measured move). (SLB $38-$44 range, breakout above $44 -> target $50.) -> `strategies/sr_breakout.py` with `features/levels.py` (pivot-based S/R detection).
- Two exits planned: target and stop. Stop may be an order or an alert + manual order; stop orders become market orders and can fill far from the stop. -> executor uses stop-limit with a configurable band OR alert-only mode; monitor P3 alert on stop proximity.
- Position size = portfolio risk / trade risk: $50,000 x 1% = $500; / $2 = 250 shares. -> `risk/sizing.py: fixed_fractional`.
- Reward:risk check: risk $2 to make $5 is acceptable; $2 to make $1 is not. -> `risk.min_reward_risk` (default 2.0) filters signals.
- Trail stops as price rises to lock gains; accept that targets may be overshot or just missed. -> trailing-stop option per strategy.
- Paper trade before real money. -> `docs/gates.md`.

## Massive (massive.com/stocks)
- Endpoints: aggregates `/v2/aggs/ticker/{t}/range/{mult}/{span}/{from}/{to}`; trades `/v3/trades/{t}`; quotes `/v3/quotes/{t}`; snapshots `/v2/snapshot/locale/us/markets/stocks`; indicators `/v1/indicators/{sma|ema|macd|rsi}/{t}`; reference `/v3/reference/tickers` (CIK, FIGI, shares outstanding, active flag); splits `/stocks/v1/splits`; financials `/stocks/financials/v1/ratios`; filings `/stocks/filings/vX/index`; news `/v2/reference/news`; short interest `/stocks/v1/short-interest`; market status `/v1/marketstatus/now`. WS `socket.massive.com` channels T/Q/A. Flat files `files.massive.com` (S3-compatible, daily gz CSV). MCP `mcp.massive.com` (4 tools).
- Coverage: 55+ venues, 32,345+ active+delisted tickers, extended hours 04:00-20:00, tick history to 2003, as-reported (never overwritten).
- Plans: Basic $0 (EOD, 5 calls/min, 2 yrs); Starter $29 (15-min delayed WS, 5 yrs, flat files, snapshots); Developer $79 (10 yrs, +trades); Advanced $199 (real-time, 20+ yrs, quotes, financials); Business $2,499. Individual plans are non-professional, non-redistribution.
- Decision: Massive is the default bar/reference provider. Basic tier is enough for the sample/paper phase on a screened universe at 5 calls/min (use flat files or Starter once the universe is >1,000 names or history > 2 years is needed). Short-interest and splits endpoints replace separate FINRA/CA pulls for nightly features.
