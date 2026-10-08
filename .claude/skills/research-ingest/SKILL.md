---
name: research-ingest
description: Turn a paper, blog post or book chapter into a fact-checked strategy card (docs/strategies/<slug>.md) and a matching docs/catalog/catalog.json item and CATALOG.md row, citing only numbers read in the source.
---
## Read first
The source itself, all of it. Then `docs/catalog/CATALOG.md` (decision and grade legend, the section tables, the
"Strategy cards to write" table, the fact-check table at the end), the `legend` in `docs/catalog/catalog.json`, and one
finished card of the same kind (e.g. `docs/strategies/breakout_52w.md`, `rsi2_meanrev.md`).

## Hard rules
- Never write a number you did not read in the source in this session. Training-memory numbers do not count. If the
  source cannot be opened, write "not checked" and no number.
- Every number carries its source: URL, or author, year and venue, with page or table where possible. State the
  sample, the period, and whether it is gross or net of costs.
- Label the source type in each Evidence bullet: peer-reviewed, working paper, book, practitioner/vendor blog
  (originator or seller of the method), or independent test. Grade with the catalog legend: A replicated OOS after
  costs; B peer-reviewed or independent OOS; C vendor or independent gross; D originator or anecdote; Neg; none.
  Practitioner-only evidence is C at best, and D when it comes from the method's seller.
- Paraphrase. Quote at most a short phrase. Never copy tables or passages.

## Steps
1. Slug: lower_snake_case. Search first: `grep -rl "<key term>" docs/strategies docs/catalog/catalog.json`. If an item
   or variant already exists, update it instead of adding a duplicate; a variant becomes a param of the existing item.
2. Card `docs/strategies/<slug>.md`: same frontmatter keys and section headings as the existing cards (slug, name,
   originators, category, decision, holding_period_days, timeframe, direction, regimes_good/bad, typical_win_rate,
   typical_payoff_ratio, evidence_grade, free_data_ok, status; then One-line summary ... Sources). Write "Exact rules"
   so add-strategy can code them, with every threshold explicit and point-in-time (what is known at the close of
   `as_of`; filings by filing date). Keep an existing `## Empirical (replay)` section: `research.cards` writes it.
3. Decision, with a reason in the card and the catalog `notes`:
   - `implement`: decent evidence, free daily data.
   - `implement_disabled_for_comparison`: weak or negative evidence, or a control.
   - `approximate`: a proprietary rating rebuilt.
   - `blocked_paid_data`: needs data the free stack lacks.
   - `avoid`: untestable or no evidence.
   - `have`: covered already; set `maps_to`.
   For a published predictor, name the matching Chen-Zimmermann signal for the manual gate-2 CZ check, and note that
   planning assumes at most half the published edge.
4. Catalog: add or update the item in `docs/catalog/catalog.json["items"]` with the same keys as its neighbours (slug,
   name, brands, category, kind, rules_or_formula, formula_status, data_needed, free_data_ok, evidence_grade, decision,
   batch, maps_to, notes, holding_period, evidence_text, source_urls ...). Update `counts` and `strategies_to_card` to
   match. Validate with
   `uv run python -c "import json; d=json.load(open('docs/catalog/catalog.json')); print(len(d['items']), d['counts']['by_decision'])"`.
5. `CATALOG.md`:
   - add the row to the matching section table (`| **Name** \`slug\` | Brands / origin | Decision | Grade | Free data | Maps to | Rationale |`)
     and fix that section's count line;
   - fix the decision and batch count tables;
   - add the row to "Strategy cards to write";
   - add one row per number checked to the fact-check table: Claim | File(s) | Verdict (confirmed / refuted (fixed
     <date>) / not yet checked) | Evidence URL.
6. Fact-check pass: re-open the source and tick every number in the card, the catalog item and the CATALOG row against
   it. Fix or delete anything that does not match.
7. Hand off: implementing is the add-strategy skill, testing is the research-loop skill. Ingesting never changes
   settings.
