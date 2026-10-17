# Research round-up, batches 5-23 (2026-10-15)

**Needed from Jack:** nothing urgent. The biggest lever is the free Tiingo signup (add `TIINGO_API_KEY=` to `.env` on the
Mac): it extends stock history to about 2010. The direction card's new data (10-K text, borrow fees, Wikipedia views)
still needs a yes or no.

## Bottom line
- **54 pre-registered cards, none passed `docs/gates.md`.** Every one was graded net of costs against SPY, with
  point-in-time data and delisted stocks kept.
- **One book is still standing: the S&P momentum-index replica** (batch 9), shadow-tracked nightly. Over 2017-01 to
  2026-10 it made +19.0% a year against SPY's +13.6% on price-only data, and +20.7% against +15.3% on total return.
  Alpha was +4.9% a year, but with t 1.51 against a bar of 2.24, which is not proof.
- **The robustness pass (batch 23) reads MIXED.**
  - Every one of 12 variants made money against SPY: 6 rebalance-month timings and 6 neighbouring settings.
  - It held up at 3x costs (+3.3%).
  - The bootstrap puts 95% of outcomes above about zero alpha.
  - But averaging the six rebalance timings gives only +2.2% a year (t 0.72). The registered Feb/Aug timing was one of
    the luckier ones.
  - Read it as: momentum in large caps probably helps a little; the backtest's +4.9% likely overstates it.
- **Construction note found by the Mac:** in batches 9, 10 and 16 the momentum score tilt never takes effect, because
  the weight caps bind for every name. The replica is in practice "the top 100 momentum names, cap-weighted". Its
  results are what they are, but batch 16's "momentum + profitability" was really a different selection, not a
  different weighting.

## What was tested (families, trials)
| Family | Trials | Best result | Verdict |
|---|---|---|---|
| Momentum (index replica, mid/small, industry-neutral, composite, vol-scaled, +profitability) | 7 | replica +4.9% alpha, t 1.51 | nearest miss; shadowed |
| Profitability / quality | 4+ | gross profitability 2017-24 t 1.43 | fail |
| Value (book/market) | in composite | -4.0% alpha alone | fail |
| Buybacks / shareholder yield | 3 | net repurchasers passed its own early rule, alpha ~0 | fail on gates |
| Mispricing short-leg exclusion | 2 | +13.2% vs 13.6% | fail |
| Earnings surprise (top 100, exclusion) | 3 | 2024-26 +8.8% alpha t 1.69, but 2017-24 -3.4% | fail |
| Insider buying | 5 | large-cap version -2.5% (t -2.35) | fail |
| Low volatility | 1 | -2.8% alpha | fail |
| Cross-asset trend / dual momentum | 2 | +0.7% alpha | fail |
| Dividend changes, index reconstitution, events, calendar, VRP | 1-2 each | none positive | fail |
| Chart / swing setups (engine cards, 146 methods earlier) | ~4,100 trials | none survive costs | fail |

## What the evidence says about why
1. **Short holds and high turnover always lose here.** Every engine card holding 10 sessions or less, and every book
   turning over more than 500% a year, had negative alpha after costs. This is settled for this data.
2. **2017-26 was a mega-cap-led market.** A long-only book that does not hold the biggest names has to out-pick a
   handful of giants, and almost none did. The books that came closest kept SPY-like weights and tilted.
3. **Ten years caps the evidence.** A real edge of 2-3% a year cannot reach t 2.2 in ten years with typical tracking
   error. 60-year checks help: French's big-stock momentum + profitability blend is strong since 1963 (t 3.71), while
   low variance did not pass its subperiod rule.
4. **Small caps had nothing net of costs.** 870 method x liquidity cells on the next 2,500 smaller stocks, none beat
   SPY in both halves.

## What would change the picture
- **Longer history (Tiingo to ~2010):** about 1.25x more reachable t for every family, and a 2010-16 out-of-sample
  check of the replica.
- **The forward record:** the replica's nightly shadow book accumulates real out-of-sample months from 2026-10-15.
- **New data** the free store lacks (filing text, short borrow, attention): the remaining untested families.

## Plain answer to "what makes money"
On this evidence, nothing beats simply holding SPY with confidence yet. The momentum replica is the only candidate,
and the honest expectation is SPY plus a small, uncertain extra, with SPY-like drawdowns. Research continues on longer
history and new data rather than more variations on the same ten years.
