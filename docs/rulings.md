# Operator rulings

Dated decisions by the owner that change how something is defined, graded or allowed to trade. One line each:
`- YYYY-MM-DD <strategy slug or *>: ruling`. `swing_engine.ops.vocabulary` copies them into `docs/vocabulary.md`.

- 2026-10-08 *: Paper trading only; live needs SWING_ALLOW_LIVE=yes plus the gates in docs/gates.md.
- 2026-10-08 *: Free data tiers only; no Claude API calls from the automated pipeline (agent.llm_enabled stays false).
- 2026-10-08 *: Every new strategy or variant is a logged trial and is pre-registered before any replay.
- 2026-10-10 *: Research runs may use up to 44 GB of memory, at most two long-window replays at once.
- 2026-10-13 *: No strategy trades on paper: none survives costs and the multiple-testing haircut (docs/leaderboard.md). All run shadow-only.
- 2026-10-13 large_cap_net_repurchasers: Passed its absolute pre-registered rule but has no alpha over SPY; not enabled.
- 2026-10-13 *: The always-on cloud host waits for the owner's decision; the intraday lane is research only until then.
