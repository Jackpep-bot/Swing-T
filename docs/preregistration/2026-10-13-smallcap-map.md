# Pre-registration: small-cap edge map (exploratory, every registered strategy)

Committed 2026-10-13 **before** any replay on this universe exists. This is a map, not a pass/fail test of one card:
it says in advance how cells are counted so the count cannot be bent afterwards, and it grants nothing by itself.

## Why
Every replay to date screened the 1,500 most liquid US stocks (`universe.max_symbols`). On that universe the edge
map of 2026-10-13 (docs/edge_map.md) found 0 of 711 strategy-by-liquidity cells positive against SPY in both
windows, where about 18 would pass by luck with no edge at all: the strategies are worse than nothing there.
The published evidence the research threads collected says the same thing from the other side: the edges that
survive (post-earnings drift, insider buying, short-term momentum) survive in small, thinly traded stocks, where
funds cannot trade size. A small account can. Those stocks have never been in a replay here.

## Universe (config/research_smallcap.yaml)
The live store after the 2026-10-13 rename repair. Each refresh: stocks passing price >= $3, 20-day average
dollar volume >= $1M and average volume >= 100,000 shares, ranked by dollar volume, **leaving out the top 1,500 and
taking the next 2,500**. No ETFs, no OTC (as before).

## Window
2024-10-07 .. 2026-10-05 only: the store has every US ticker, delisted ones included, only from 2024-10-07; before
that it holds names that were still liquid in 2024, which for small caps is survivorship bias. For the both-halves
rule the window is cut in two: **H1 2024-10-07 .. 2025-10-03** and **H2 2025-10-06 .. 2026-10-05**.
Two halves of one two-year stretch share a market regime; that is a weaker check than two separate eras and is why
nothing here can pass a strategy.

## Run
```
swing --settings config/research_smallcap.yaml research run --windows short --no-rebuild
python -m swing_engine.research.edge_map --settings <lane0.yaml> --store <lane1 store> --tag .small \
  --windows 2024-10-07:2025-10-03,2025-10-06:2026-10-05 --out docs/edge_map_smallcap.md
```
Every registered strategy, `--no-router`, graded from the replay shadow ledger at 5, 10 and 20 sessions as on the
leaderboard: net R per signal after costs, minus SPY's R over the same days. Costs: half the spread estimated from
daily bars (Abdi-Ranaldo), at least 20 bp a side. Real spreads in the thinnest names are often wider than the
estimate; the report says so. Every cell (strategy x liquidity band x horizon x half) is logged as a trial.

## Counting rule
- Cell = one strategy's signals in one band of 20-day dollar volume (under $5M, $5-20M, $20-100M, over $100M).
- **Candidate**: at one horizon, at least 100 traded signals, net R against SPY above 0 and block t >= 2 in **both**
  halves. A weaker list at t >= 1 is printed for reading only.
- The report prints how many cells had the chance to pass and how many would pass by luck with no edge
  (cells x P(t >= 2)^2). **The map has found something only if the candidates clearly outnumber that.** If they do
  not, the answer is that small caps do not rescue these strategies either.

## What a candidate gets
A forward test, nothing more: tracked in the shadow ledger on this universe, and on paper at a quarter of normal
risk if the owner has said yes to that. Both halves of history are used up by the selection, so only forward results
can confirm a candidate; `docs/gates.md` still decides anything beyond paper.
