# Pre-registration: batch <N> (<one line: what the cards have in common>)

Committed <date> **before** any replay or simulation of these rules exists on real data. The modules were written
and tested on synthetic data only. Nothing below may change after the first run except a harness-only amendment (a
bug that stops the rules as written from running), written into this file before results are read.

Cards: `docs/proposals/swing-methods-2026-10/batch<N>/` (branch `claude/batch<N>-cards` @ <commit>). Say which earlier
results existed when the cards were chosen, and whether any card is a RE-TEST (then count the family's trials).

| # | Card | Module | Kind (engine strategy / weights card) | Book |
|---|---|---|---|---|

## Expectation, stated before the run
<the cards' own expectations, and the expected verdict>

## Store
<settings file -> store; what was added to it and from where; price-only or total return; survivorship notes>

## The rules
<per card: the registered reading of its "Engine version", every deviation the module states>

## Harness check before the run (signal or order counts only; no price after a signal was read, nothing graded)
Engine cards: through `research.replay.run_replay` (a replay-shaped panel: the last 300 sessions handed to
`signals`), never by calling `signals` on a whole panel. Weights cards: the order list only.

## Windows and grading (docs/gates.md, including "Full-period test")
- Window A 2017-01-01 .. 2024-10-04, window B 2024-10-07 .. 2026-10-05, and the **pooled window 2017-01-01 ..
  2026-10-05**. Engine cards: both windows are replayed for every card; the pooled window joins the two replays end to
  end (`scripts/run_prereg_batch.sh` with POOLED=1). Weights cards: one simulation over the pooled window.
- Trials: <n> (one per card, or the family count for a re-test). Bar: `prereg_eval.alpha_t_critical(<n>)` = <value>.

## Pass rule
PASS on either route:
1. in both windows A and B: haircut Sharpe > 0, net R per trade > 0 (engine cards), alpha vs SPY > 0 with alpha t
   >= the bar; or
2. in the pooled window: the same conditions, with alpha vs SPY above zero in each of A and B.
<any card-specific extra condition>

## Beside the verdict (owner's terms)
Return per year, share of months up, deepest drop, SPY beside them. A failing card that made money steadily with
small drops may be listed as a forward-test candidate, labelled as a judgment made after the results.
