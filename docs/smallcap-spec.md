# Small-cap runner / pump track: specification (from docs/research-raw/smallcap-pump.json, 2026-10-06)

Default posture is WARN/FADE, not BUY. Every measured post-signal long horizon is negative (5-day -3% to -6% and 1-month -5% to -9%
after retail herding; -3% to -5% over 5 days after social spikes; 67% of 50%+ gappers close below the open; 73% gap down next day).
The only long edge is the early phase: pre-market to ~9:45 ET on catalyst-backed gappers with no dilution capacity. The detector is two
classifiers on one feed set, plus a bag-holder scorer that can fire on any ticker at any time.

## Universe gate (both classifiers)
price 1.00-20.00; float < 20M (hard; < 10M preferred; float unknown => NOT eligible for long alerts, only for warnings); market cap < 200M;
listed (Nasdaq/NYSE/NYSE American), not ETF/SPAC/OTC.

## Classifier A: "runner" (intraday catalyst gapper)
Long-candidate rules (all must hold; alert grade A if gap >= 20%, B if 10-20%):
- pre-market gap >= 10% vs prior close (A-grade >= 20%; pump-fade universe >= 50%)
- relative volume >= 5x 30-day ADV, computed on cumulative volume including pre-market; pre-market volume >= 50k shares by 08:00 ET
- a catalyst within 24h: PR / 8-K / 6-K / Benzinga headline (an offering is NOT a catalyst)
- no S-1 / S-3 / F-3 / 424B* / 8-K item 3.02 by the issuer's CIK in the last 5 sessions
- entry context only: pre-market-high break or 1-min opening-range break, above VWAP, window 07:00-11:00 ET; long alerts expire at 09:45;
  nothing after 10:30 is ever a long alert (85%+ of highs-of-day are in by 10:30; 46.6% by 09:45)
Score-down (any => downgrade one grade; two => no long alert): float rotation (cum volume / float) > 1x pre-market; pre-market volume > 50M shares;
prior-day run already >= 300% from breakout; reverse split in last 30 days; active ATM/shelf or cash runway < 6 months if known.

## Classifier B: "ramp-and-dump" (recent microcap IPO promoted in chat groups) — never emits a long alert
Structural profile (nightly score, computed from EDGAR F-1/S-1/424B4 and reference data): IPO within 24 months on Nasdaq Capital Market /
NYSE American; IPO price $4-$6; proceeds <= $25M; < 20M shares offered; Cayman/BVI holdco with China/HK/Singapore/Malaysia/Indonesia operations;
microcap underwriter list (seed: WestPark, D. Boral, Dominari, Revere, R.F. Lafferty, Cathay, Bancroft, Prime Number, Benjamin, Joseph Stone);
float < 20M. Behavioral trigger: 5-day gain >= 50% or 20-day gain >= 100% with zero EDGAR filings/PRs in the window (SEC's "no material news"
test), or close-to-close >= 100% over <= 5 sessions / >= 300% over <= 20 sessions on a sub-$300M name with no filings.
Alert text must say "promoted / do not buy"; add the ticker to a session blocklist. Maintain a tainted-issuer list seeded from SEC 12(k)
suspensions (sec.gov trading-suspensions RSS), Nasdaq T12 halts, and the underwriter list.

## Bag-holder scorer (fires any time on any ticker in the universe; alert "DO NOT HOLD / short watch" at >= 6, calibrate later)
+3 S-1/S-3/F-3/424B*/8-K 3.02 or "equity distribution agreement" filed in last 10 days or during the run (424B5s typically post ~16:05 ET;
   announcement-day average drop 20-30%) | +2 cash runway < 2 quarters or going-concern language | +2 float rotation > 5x pre-market |
+2 price below 09:30 open at 10:00 with falling 1-min volume (gap-and-crap) | +2 VWAP lost and not reclaimed by 09:45-10:00 |
+2 four or more up-halts today | +3 first red day after >= 3 green days and ~300% run | +3 ramp-and-dump structural profile |
+1 SSR triggered | +3 T12 or H10 halt (also: mark toxic for the session, block longs).

## Halt semantics (feed: Alpaca statuses/lulds + Nasdaq halts RSS 60 s + SEC suspensions RSS)
LUDP = 5-min volatility pause (count per 30 min; >= 2 up-halts in 30 min + rotation >= 1x = climax zone, not a buy); T1 = news pending
(pre-market halts are always T1, LULD is inactive before 09:30); T2 = news released; T12 = additional info requested (exit / no-trade);
H10 = SEC suspension (10 business days, often months). Tier 2 LULD bands: 10% above $3.00, 20% for $0.75-$3.00, lesser of $0.15 or 75% below $0.75.
SSR (Rule 201): >= 10% drop from prior close => short only above NBB rest of day + next day.

## Data needed and where it comes from
Pre-market trades 04:00-09:30 (Alpaca SIP $99 or Massive Advanced; free IEX misses most pre-market prints => runner classifier runs in
"degraded" mode and says so); float (not in Alpaca/Massive: FMP, sec-api, or EDGAR cover-page parse; refresh daily and on 8-K/424B/split);
EDGAR current filings by CIK (free Atom + EFTS); Nasdaq halts RSS; SEC suspensions RSS; Benzinga headlines (Alpaca news WS); optional
StockTwits/X mention anomalies (message count > trailing-year mean + 2 SD with >= 20 messages).

## Outcome logging (required from day one)
For every alert store: time, classifier, grade, structural score, bag-holder score, and realized returns at +5 min, +30 min, close, +1 d, +5 d, +20 d.
Also log every Tier 2 halt (code, direction, halt price, resume price, open, close, next close) to build the halted-runner statistic that no source publishes.
