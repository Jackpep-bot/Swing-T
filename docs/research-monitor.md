# Live monitor research (verified 2026-10-06)

## Purpose (in priority order)
1. No surprises on HELD positions (halts, SSR, severe 8-K items, order rejections, adverse moves) — sub-minute matters only here.
2. Catalyst tagging for next-open entries (moves with news + volume continue; without them they reverse — Chan 2003).
3. Candidate funnel into the nightly ranker. Everything is logged as a feature even if not alerted.

## Feeds
Tier A (free, always on): Alpaca news WS `wss://stream.data.alpaca.markets/v1beta1/news` (`news:["*"]`, Benzinga, 600-900/day);
Alpaca stock WS `/v2/iex` (Basic) or `/v2/sip` (Plus) channels trades/bars/updatedBars/statuses/lulds (`statuses` T="s" fields sc/sm/rc/rm; `lulds` T="l" u/d/i);
Alpaca account WS `wss://paper-api.alpaca.markets/stream` (`trade_updates`);
EDGAR `browse-edgar?action=getcurrent&type=8-K&owner=exclude&count=100&output=atom` every 15-30 s (also type=4&owner=only, SC 13D, S-3, 424B, NT 10-K); EFTS `efts.sec.gov/LATEST/search-index?q=...&forms=8-K` for keywords; 10 req/s + User-Agent "App contact@email";
Nasdaq halts RSS `nasdaqtrader.com/rss.aspx?feed=tradehalts` every 60 s (ttl 1 min; fields IssueSymbol, HaltTime, ReasonCode, ResumptionQuoteTime, ResumptionTradeTime); NYSE `nyse.com/api/trade-halts/current/download`;
Alpaca `/v2/calendar`, `/v2/clock`.
Nightly into DuckDB: Nasdaq SSR `dynamic/symdir/shorthalts/shorthaltsYYYYMMDD.txt`; Reg SHO threshold `dynamic/symdir/regsho/nasdaqthYYYYMMDD.txt`; FINRA `cdn.finra.org/equity/regsho/daily/CNMSshvolYYYYMMDD.txt` (by 18:00 ET); Alpaca `/v1/corporate-actions`; Nasdaq SymbolDirectory; earnings/FOMC/BLS/index-rebalance calendars; ApeWisdom `/api/v1.0/filter/wallstreetbets` and Tradestie `/api/v1/apps/reddit` (15-30 min).
Tier B (best effort, 1-15 min polls, some must run from a residential IP): FDA press RSS, defense.gov contracts (17:00 ET, >= $7.5M), ClinicalTrials.gov v2, SAM.gov, SEC trading-suspension RSS, Google News RSS, Substack `/feed`, Bluesky Jetstream (cashtags), Telethon on curated public Telegram channels, YouTube PubSubHubbub.
Paid, in order: Finviz Elite $39.50 (gapper/RVOL CSV 04:00-20:00), Alpaca Plus $99 at go-live, NewsFilter ~$10 (unverified), sec-api.io $49 (stream is NOT on the free tier), X pay-per-use filtered stream ($0.005/post read, 3M/month cap; $20-50 credit cap).
Skip: Unusual Whales ($150), Databento/Massive Advanced firehose, Reddit Data API (new access ends 2026-10-31, all public access ends 2027-03), StockTwits, Discord self-bots, Truth Social scraping, Nitter (dead 2026-08-24).

## Pipeline
adapter -> normalize (symbol master; UTC + source ts + receipt ts) -> dedup (provider id, then SimHash title+ticker in 30-min window) -> SQLite WAL event log UNIQUE(event_id), replay cursor -> stage-1 rules (deterministic, <1 ms) -> priority P0-P3 -> stage-2 Haiku 4.5 structured output on survivors (system prompt cached, > 4,096 tokens; tickers must be subset of input; no tools; semaphore ~5; rules-only fallback on 429) -> alert policy -> delivery -> JSONL audit -> nightly DuckDB load + Batch relabel.
Matcher: ahocorasick over tickers + company aliases (SEC company_tickers.json) + keywords; for word-like or <=2-char tickers require cashtag, exchange qualifier ("NASDAQ: ON") or company-name co-occurrence within ~60 chars.

## Stage-1 rules (versioned constants)
- holdings/watchlist hit; 8-K items 1.01 2.02 5.02 8.01 + 4.02 3.01 1.03 4.01 2.04 2.05 2.06 3.02 1.02 5.01 7.01; NT 10-K/10-Q; SC 13D; Form 144; S-1/S-3/424B/ATM supplements.
- Form 4 open-market buys (code P, A); insider cluster = >= 3 distinct insiders within 30 days, reject clusters with >= 80% identical date+price.
- halts T1/T2/T12/H10 and LULD pauses; SSR trigger; index-inclusion phrases ("Set to Join S&P").
- RVOL (time-of-day-adjusted cumulative volume / 10-20 day profile) >= 2 as the gate (>= 3 to escalate) for: pre-market gap >= 8%; Stockbee burst `c/c1>=1.04 and v>v1 and v>=100000` (feature only); 52w/ATH break on >= 1.5x volume; PEG `gain>=10% and vol>=3x avg50 and eps_surprise>=20%` holding day-1 low at 15:30 ET.
- Suppress single-name alerts on market-wide circuit-breaker / FOMC / CPI days unless held.
- Reversal candles, sympathy moves, options sweeps: log only.

## Alert policy
P3 (Pushover emergency, repeat until ack): halt/SSR/8-K 4.02,3.01,1.03 on a HELD position; >= 5% adverse move or order rejection on a holding; feed dead during market hours; kill switch tripped.
P2 (Telegram with sound): watchlist T1/T2 halts, insider clusters, index inclusion, PEG survivors, 52w breakouts, pre-market gap >= 8% with RVOL >= 2 and a news tag.
P1: digests 08:30, 15:45, 18:30 ET. Per-ticker 15-min cooldown, hourly cap, quiet hours. Haiku-off path still delivers P3.

## Ops
One asyncio process; `websockets` reconnect loop (ping 20 s, re-auth + resubscribe); per-feed staleness watchdog that is market-hours aware; healthchecks.io dead-man ping; systemd Restart=always, LoadCredential secrets; chrony; append-only JSONL audit; catch-up on reconnect via REST (news since last id, Atom last 100, halts full diff, orders reconcile). One Alpaca socket per endpoint: nightly job uses REST only. Inbound webhooks (TradingView, PubSubHubbub) carry no execution authority. Telegram approval callbacks bound to chat_id + PIN, expire in 10 min.

## Cost tiers
Paper ~$10-20/mo (VPS $6, Haiku $3-10, Pushover $4.99 once). Live ~$160-200 (+Alpaca Plus $99, Finviz $39.50). Full ~$250-300 (+sec-api $49, X credits).
