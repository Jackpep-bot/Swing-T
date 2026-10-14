# What successful trading systems do, and what would move Swing T forward

Written 2026-10-14 for Jack. Sources are linked at the bottom. Where a claim is my inference rather than a source,
it says so.

## The short version

1. **Swing T's machinery is already at the level of serious systematic shops.** It has pre-registration, a full
   trial log, deflated Sharpe, Harvey-Liu haircuts, PBO/CSCV, White's reality check, point-in-time data with
   delisted names, a kill switch, broker reconciliation, a shadow ledger and live-vs-replay drift. Most open-source
   frameworks (freqtrade, backtrader, Lean, Qlib) ship none of the statistics layer. Another framework or more
   tooling will not find an edge; that is not what is missing.
2. **The gate asks for something even top professional managers rarely show over ten years.** An alpha t-stat
   is roughly information ratio x sqrt(years). With about 9.8 years pooled, alpha t 2.24 needs an information ratio
   of about 0.72 against SPY; t 2.5 needs about 0.80. The long-standing practitioner rule of thumb (Grinold & Kahn)
   calls 0.5 "good", 0.75 "very good" and 1.0 "exceptional". The momentum replica's pooled t 1.51 is an
   information ratio near 0.48, which is good-manager territory. *(Arithmetic is mine; the IR scale is a textbook
   convention, not a measured survey.)* The gate is right to stay strict before real money, but "no survivor"
   partly means "ten years of daily data can't prove a realistic edge", not "every idea is worthless".
3. **What the big firms have that Swing T can't copy:** proprietary and very fast data, execution at fractions of a
   basis point, hundreds of researchers combining thousands of weak signals, leverage and shorting at institutional
   rates, and capacity limits that cut the other way (Medallion's edge only works at small size and is closed to
   outsiders). Retail-scale, free-data systems do not rival them on alpha. Anyone selling a bot that does is
   selling the bot, not the returns: in Brazil, 97% of people who day-traded for 300+ days lost money and about 1% earned
   more than minimum wage; in Taiwan, under 1% of day traders were reliably profitable.
4. **What a small system *can* do better than the big ones:** be patient (hold for months, so costs and taxes stay
   tiny), ignore capacity limits (small and mid caps a $10B fund can't trade), avoid career risk (sit through a
   bad year of a sound tilt), and manage taxes directly. These are real, measured advantages; none of them is a
   secret signal.

## Traits shared by systems that last

Ranked by how much the evidence supports them.

| Trait | Evidence | Swing T today |
|---|---|---|
| Few, slow, economically motivated signals, combined | Published anomalies mostly replicate (Chen-Zimmermann: 117 of 118 clear predictors reproduce), but lose about a third after publication (McLean-Pontiff), and trading costs erase most of what's left in short-hold versions | Has the lesson ("short holds lose to costs"); still tests signals **one at a time** |
| Combining signals into one portfolio rather than picking one winner | AQR's "Value and Momentum Everywhere": value and momentum are negatively correlated, the blend has a much higher Sharpe than either | Not done as a pre-registered book (composite_cost_aware_rank was a 5-20 day engine card, not a monthly blend) |
| Risk control on the whole book, not per trade | Volatility-scaled momentum (Barroso & Santa-Clara; Daniel & Moskowitz) roughly doubles Sharpe and cuts the worst month from -77% to about -28% for long-short momentum; long-only gains are smaller and untested in that work | Per-trade stops and position limits; no book-level volatility target in the weights books |
| Costs measured and modeled honestly | A 2026 study ran the same strategies through five backtest engines: identical at zero cost, up to 3.7% total-return gap at realistic costs; one popular library undercharged commission 100x by default | Explicit cost model with SEC/TAF fees; one engine only |
| Testing discipline (pre-registration, trial counting) | Harvey-Liu: t > 3 for new factors; Bailey-Lopez de Prado deflated Sharpe | Fully in place, stricter than most shops |
| Forward tracking before money | Every serious shop paper- or incubation-trades | Shadow books running (momentum replica from today) |
| Tax management | Tax-managed factor tilts added about 1.6-1.9% a year after tax in a 1995-2018 backtest; tax-managed indexing about 2.3% | Not modeled at all (Alpaca paper has no tax) |
| Operations that don't break | Dead-man alerts, reconciliation, always-on host | Reconcile, doctor and Telegram alerts exist; the host is a laptop that sleeps |

## Strategies that the evidence supports, for a system like this

US equities and ETFs first. Most of these are **already in batches 1-12**; I'm listing them so it's clear what the
honest menu is, not to restart them.

- **Cross-sectional momentum, monthly or semi-annual, large caps.** The nearest miss (pooled +19.0%/yr vs SPY
  13.6%, alpha t 1.51). Now in shadow. The evidence-backed improvement is volatility scaling of the book, which
  the research thread can register as a *new* trial (it is a different rule, not a resubmission).
- **Profitability / quality tilt.** Robust in replication; gross profitability already in shadow.
- **Value.** Weak in US large caps since 2007, but negatively correlated with momentum, which is its main use here.
- **Trend following on asset classes.** Real long-run evidence, but in ETFs it mostly works as a crisis hedge; it
  lost to SPY here (+2.2%/yr), as expected in a bull decade. Futures versions need paid data and margin.
- **Post-earnings drift.** Recent evidence says it is now concentrated in microcaps (about 3% of market value,
  illiquid); t falls to 1.43 once microcaps are dropped. Not worth more trials at this account size with free data.
- **Short-term reversal, intraday patterns, SMC/ICT setups.** Swing T's own tests agree with the literature: they
  don't survive costs. Drop them.
- **Crypto and futures (brief):** crypto trend/momentum has stronger raw backtests but short, regime-heavy history
  and exchange risk; futures trend following needs paid continuous-contract data (Norgate-type) and a margin
  account. Both are outside "free tiers only" today.

## Secondary programs and tools, judged against Swing T

| Tool | What it's good at | Verdict for Swing T |
|---|---|---|
| freqtrade | Crypto bots, strategy hyperopt | No: crypto-only, and hyperopt is the overfitting Swing T guards against |
| QuantConnect Lean | Event-driven engine, broker adapters incl. Alpaca, cloud data | Useful only as a **second engine** to cross-check costs on the one or two finalists; not a replacement |
| Qlib (Microsoft) | ML factor research pipeline, fast data format | No for now: no broker layer, its free US data is basic Yahoo data, and ML on price-only daily data is where overfitting is worst |
| FinRL / RL trading | Reinforcement-learning agents | No: out-of-sample record is poor and it fights the "LLM/ML never sets size" rule |
| NautilusTrader | Fast event-driven engine with backtest/live parity | No: built for intraday/HFT; swing horizons don't need it |
| vectorbt | Very fast vectorized sweeps | No: speeds up exactly the parameter sweeping that inflates trial counts |
| skfolio / Riskfolio-Lib | Portfolio construction (risk parity, HRP, constraints) with scikit-learn style validation | **Maybe**: only if a combined book is built and needs a weighting rule; equal or inverse-vol is usually as good out of sample |
| alphalens-reloaded / pyfolio-reloaded | Factor tear sheets, performance reports | Low value: Swing T's own reports cover this |
| Numerai Signals | Submit a weekly stock ranking; scored live against a 60-day target **after removing known factors**; no stake needed | **Yes, cheap and useful**: a free, independent, live out-of-sample check that tells you whether a signal is new or just repackaged momentum/value. Needs a free signup (Jack's call) |
| Chen-Zimmermann open-source data | Monthly returns of 200+ published predictors | Already in gates.md as the "CZ check"; still needs Jack's OK to download one file |
| Norgate / Sharadar | Survivorship-free prices, historical index membership, fundamentals | Paid. Only if a card passes and needs total-return data or exact index membership |
| healthchecks.io-style dead-man switch | Alerts when the nightly *doesn't* run | **Yes**: free, tiny, and the Mac sleeping has already cost hours |
| Oracle Always Free VM | Always-on host | **Yes**, still waiting on Jack's signup decision |

## What would actually move Swing T forward, ranked

Value for this project first, then effort.

1. **Build one combined book instead of hunting for one winner** (high value, medium effort). Register a single
   S&P 500 book that blends the signals already in shadow (momentum, gross profitability, net repurchases, plus
   value as a diversifier), monthly, with a 10/20 rank band and a book-level volatility target, graded as **one
   trial** on the pooled window. This is how the big firms actually earn their Sharpe, and it's the one idea the
   batches haven't tried. Goes to the research thread as a card.
2. **Give the forward test real time and scale** (high value, no effort). The shadow books are the only evidence
   that can't be overfit. Three to six months of the replica, profitability and repurchase books side by side
   with SPY will say more than another twenty backtests.
3. **Always-on host plus a dead-man alert** (medium value, low effort, needs Jack's signup). Every stalled night is
   lost forward evidence.
4. **Numerai Signals, unstaked** (medium value, low effort, needs Jack's free signup). Weekly submission of the
   momentum/combined ranking gives an outside, factor-neutral verdict for free.
5. **Total-return data** (medium value, low effort). Alpaca dividends are already in the store; turning the price
   series into total-return series removes the known bias against dividend-tilted books (SPY too, both sides).
6. **Model taxes in the reports** (medium value for Jack's real money, low effort). A strategy that turns over
   300% a year can lose to SPY *after tax* even with positive alpha; long holds keep gains long-term.
7. **Second-engine cost check for any finalist** (low-medium value, medium effort). Run the finalist through Lean or
   a minimal independent re-implementation and compare net returns.
8. **Decide what "success" means for the account** (high value, Jack's decision, no build). If the goal is
   "consistent income I can scale", the evidence-backed answer is a low-cost core (SPY or the combined book) with
   strict risk and taxes managed, not a stream of short trades. Beating SPY risk-adjusted by a few points a year
   after costs and tax would already put Swing T ahead of most professional funds.

What I'd **not** do: add ML/RL frameworks, intraday/SMC lanes, crypto bots, or more parameter sweeps. Each one
adds trials faster than it adds evidence.

## Addendum: the history limit, and free data from before 2016

The Mac's scoreboard (docs/research_scoreboard.md, 42 cards) says the binding limit is history: with a store that
starts in 2016, even a 10-point-a-year edge scores only about t 1.5. That matches the arithmetic above (t is
about IR x sqrt(years)), and it means **more years of data raise the reachable t faster than any new signal
does**. Doubling history multiplies t by about 1.4; sixty years instead of ten multiplies it by about 2.5.

Free options, best first:

1. **Ken French Data Library, already approved (round 1, "Fama-French").** Monthly returns from 1927 (profitability
   and investment sorts from 1963) for size x momentum, size x profitability, size x value and size x investment
   portfolios, built from CRSP with delisted stocks included and NYSE breakpoints. The "Big / High momentum" and
   "Big / Robust profitability" portfolios are long-only large-cap books. A blend of them over 1963-2026 tests the
   *premise* of the combined book over 60+ years at no cost and with no new approval. Limits: no trading costs,
   monthly only, French's construction rather than ours, so it proves the idea, not our code. Pair it with the
   10-year implementation test and check that the two move together (the same logic as the CZ check).
2. **AQR datasets** (free download, no signup): Quality Minus Junk, Betting Against Beta, Value and Momentum
   Everywhere, time-series momentum, mostly from the 1980s or earlier. Same use: long-history evidence for a
   premise. A new download, so Jack's word first.
3. **Chen-Zimmermann Open Source Asset Pricing**: monthly long-short returns for 200+ published predictors, most
   from the 1960s or earlier. Already named in gates.md as the CZ check; still waiting on Jack's OK to download.
4. **Stock-level prices 2009-2015 with delisted names**: Tiingo's free plan is reported to include delisted
   securities and 30+ years of end-of-day history, capped at 500 unique symbols and 50 requests an hour (needs a
   free signup by Jack; delisted coverage should be spot-checked before relying on it). Paired with EDGAR XBRL
   fundamentals, which Swing T already reads and which start around 2009-2011, this could push the stock-level
   store back to about 2010, roughly 16 years instead of 10. At the hourly cap a ~6,000-name backfill would take
   days of throttled pulls, which is fine for a one-off.
5. **Not good enough:** Quandl/Nasdaq WIKI prices (frozen since April 2018, delisted coverage unclear), Yahoo and
   Stooq (survivors only, as far as I could find), FMP free (lists delisted symbols, but free history depth is not
   stated). True point-in-time fundamentals before 2009 are effectively paid only (Sharadar from 1990,
   Norgate for prices and index membership, CRSP/Compustat through a university).

Recommendation: start with item 1 now, since it's already approved, then ask Jack about AQR + CZ downloads and a
free Tiingo signup together.

## Sources

- [Is there a replication crisis? (Swedroe, summarizing Chen-Zimmermann, McLean-Pontiff, Jensen-Kelly-Pedersen)](https://www.evidenceinvestor.com/post/is-there-a-replication-crisis-1)
- [Open Source Asset Pricing data and code (CXO summary)](https://www.cxoadvisory.com/big-ideas/open-source-stock-predictor-data-and-code/)
- [Andrew Chen on cross-sectional asset pricing (Rational Reminder 316)](https://rationalreminder.ca/podcast/316)
- [Is post-earnings drift a thing again? (UCLA Anderson Review)](https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/)
- [Avoiding momentum crashes (Alpha Architect)](https://alphaarchitect.com/avoiding-momentum-crashes/)
- [AQR Value and Momentum Everywhere data](https://www.aqr.com/Insights/Datasets/Value-and-Momentum-Everywhere-Portfolios-Monthly)
- [Tracking trend: managed futures index replication (HedgeNordic)](https://hedgenordic.com/2025/09/tracking-trend-a-closer-look-at-managed-futures-index-replication/)
- [Implementation risk in portfolio backtesting (arXiv 2603.20319)](https://arxiv.org/pdf/2603.20319)
- [The Deflated Sharpe Ratio (Bailey & Lopez de Prado)](https://papers.ssrn.com/abstract=2460551)
- [Campbell Harvey on multiple testing (Wharton)](https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2015/05/3-Campbell-Harvey.pdf)
- [Day Trading for a Living? (Chague, De-Losso, Giovannetti)](https://econpapers.repec.org/RePEc:fgv:eesptd:525)
- [Tax management for equity factor strategies (Quantpedia)](https://quantpedia.com/tax-mangement-is-extremely-important-for-equity-factor-strategies/)
- [Numerai Signals overview](https://docs.numer.ai/numerai-signals/signals-overview)
- [Qlib assessment](https://tianpan.co/forum/t/microsoft-qlib-a-panoramic-assessment-for-quantitative-trading-infrastructure/167)
- [NautilusTrader overview](https://nautilustrader.io/docs/latest/concepts/overview/)
- [skfolio paper (arXiv 2507.04176)](https://arxiv.org/pdf/2507.04176)
- [Norgate data toolkit (Concretum)](https://concretumgroup.com/the-complete-norgate-data-toolkit-three-python-workflows-every-quant-researcher-needs/)
- [Sharadar via QuantRocket](https://www.quantrocket.com/pricing/data/sharadar)
- [Renaissance Technologies case (Harvard D3)](https://d3.harvard.edu/platform-digit/submission/renaissance-technologies-generating-alpha-without-wall-street-veterans-or-mbas/)
- [Ken French: 6 portfolios on size and momentum](https://mba.tuck.dartmouth.edu/pages/faculty/ken.French/Data_Library/det_6_port_form_sz_pr_12_2.html)
- [12 EOD stock data APIs compared (Business Quant, vendor-authored)](https://businessquant.com/resources/eod-stock-data-apis)
- [Quandl WIKI status (MarketParquet, vendor-authored)](https://marketparquet.com/vs/quandl)
- [FMP free API and delisted companies](https://site.financialmodelingprep.com/how-to/how-to-handle-delisted-companies-and-historical-symbols-with-a-free-api)
- [Alpaca market data docs](https://docs.alpaca.markets/us/docs/about-market-data-api)
