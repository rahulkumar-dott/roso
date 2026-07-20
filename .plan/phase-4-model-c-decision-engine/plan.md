# Phase 4 — Model C Decision Engine

Status: depends on Phase 1 (products) and ideally Phase 3 (drafted content for decision-proof
text, though it can run on raw product data alone). Zero external dependencies.

## Why

Per the SOW, Model C is "the core of the Rosotravel Decision Platform" (System 3) — without it
this is just an AI SEO engine, not a curation product. It's also the piece with no external API
dependency at all, so it's a good phase to build and demo independent of any credentials.

## What gets built

Data models (`app/models/entities.py` addition):
- `ProductQualityScore` — product_id, quality_score, completeness_score, computed_at
- `PoolMembership` — product_id, in_pool (bool), reasons (JSON), computed_at
- `SetMembership` — product_id, in_set (bool), confirmed_by (nullable — simulates the Product
  Ops Lead manual confirmation step from the SOW), confirmed_at
- `Archetype` — id, city_id, name (e.g. "colosseum_skip_the_line", derived from category +
  keyword heuristics for POC), 
- `ArchetypeMembership` — product_id, archetype_id
- `WinnerSelection` — id, city_id, slot (`best_value`/`premium`/`rail_n`), product_id, reason_codes
  (JSON list, e.g. `top_rated`, `best_value`, `multi_language`), computed_at

Logic (`app/services/model_c.py`):
- **Pool eligibility** — simple scoring: has description + highlights + ≥1 image + valid price →
  eligible. Threshold configurable in `config.py`.
- **Set confirmation** — `POST` endpoint simulating the Product Ops Lead's manual action (SOW
  requires human confirmation to move Pool→Set); for POC demo purposes also expose a
  `bulk_auto_confirm` dev-only endpoint so the flow can be exercised without a human in the loop
  every time.
- **Archetype grouping** — group Set products per city by category_group + simple keyword
  clustering on title (e.g. "skip-the-line", "private", "small-group") — a lightweight stand-in for
  the SOW's full archetype taxonomy.
- **Winner logic** — within each archetype: `best_value` = highest (rating/price) ratio;
  `premium` = highest rating among products flagged small-group/private. Rails = one winner per
  represented archetype, never two from the same archetype (SOW hard rule).
- **Sparse handling** — if a city's Set has fewer products than a configured minimum, suppress
  the block (return `suppressed: true` with reason) instead of forcing near-duplicate picks.
- **Decision proof content** — templated (or reusing Phase 3's `DraftedContent` if present):
  "why you see a shortlist", 2–4 "why these picks" bullets from reason codes, 2–4 "what we
  skipped" bullets naming the excluded archetype siblings.

## Endpoints (`app/routers/decisions.py`)

- `POST /model-c/recompute` — recompute quality scores, Pool, and archetype grouping for all
  products (dev convenience; in production this would be triggered by ingestion events)
- `POST /products/{product_id}/set` — confirm/remove Set membership (the human-in-the-loop
  action)
- `GET /cities/{city_id}/picks` — full Model C output: best_value/premium/rails winners, reason
  codes, decision proof text, or `suppressed` if sparse
- `GET /products/{product_id}/explain` — Explainability panel equivalent: why this product won
  or didn't, what it competed against

## Verification

- Recompute → fixture products land in Pool per completeness rules
- Confirm a handful into Set → `GET /cities/{city_id}/picks` returns winners with reason codes and
  decision-proof text, never two products from the same archetype in the same rail
- Reduce a city's Set below the sparse threshold → block reports `suppressed: true`, not a forced
  pick
- `pytest tests/test_model_c.py` — winner logic, archetype exclusivity, sparse suppression

## Needed from user

Nothing. This phase runs entirely on Phase 1 ingested data.
