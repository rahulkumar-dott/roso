# Phase 3 — AI Drafting Pipeline (simplified 4-chain)

Status: depends on Phase 1 (RAW + Diff Engine) and Phase 2 (factual context). Runs in template
stub mode with zero credentials; upgrades to real GPT output once `OPENAI_API_KEY` is set.

## Why

SOW System 2.5: turn a RAW+enriched entity into publishable content — H1/meta/highlights/body/
FAQ plus 7 audience-specific snippet variants — only for entities whose latest diff was `MAJOR`
(carried over from Phase 1's hard rule), with a validation pass before anything is considered
draftable.

## What gets built

Data models (`app/models/entities.py` addition):
- `DraftedContent` — id, entity_id, version, h1, meta_title, meta_description, highlights (JSON
  list), body, faq (JSON list of Q/A), status (`draft`/`validated`/`failed`), created_at
- `AudienceVariant` — id, drafted_content_id, audience (one of the SOW's 7: first_time_visitor,
  family_traveler, couple_traveler, comfort_easy_pace_traveler, solo_social_traveler,
  interest_deep_dive_traveler, active_adventure_traveler), snippet_text

Pipeline (`app/services/drafting.py`), mirroring the SOW's 4 chains:
- **Chain 1 (retrieve)** — assemble `raw_data_enriched` from the entity's latest `RawVersion` +
  `EnrichedFact` rows into one context object
- **Chain 2 (draft)** — `LLMAdapter.draft(context)`. Stub mode: deterministic template fills
  (H1 = "{name} — {category} in {city}", body assembled from highlights/description, 5-10 FAQ
  stubs from factual data). Live mode: real OpenAI call using the same prompt shape the SOW
  describes, once `OPENAI_API_KEY` is set.
- **Chain 3 (refine)** — structural validation only for POC: required fields present, meta title
  60–75 chars, meta description 140–160 chars, no empty body/highlights. (Copyscape plagiarism
  scan and Screaming Frog N-gram repetition check are paid external tools outside POC scope —
  flagged explicitly here, not silently dropped; real integration is a Phase 7 candidate if the
  client provides those credentials.) Failure marks `status=failed` with reasons, does not publish.
- **Chain 4 (variants)** — generates the 7 `AudienceVariant` rows per the SOW's fixed list, stub
  mode via light templated rewording, live mode via one extra LLM call per variant (batched).

Similarity/duplicate gate (stands in for the SOW's Qdrant `pages_vectors`/`keywords_vectors`
gate without requiring vector DB infra): compute a TF-IDF cosine similarity between the new
draft's body and all previously drafted bodies; if OpenAI is live, use embeddings instead for a
closer match to the SOW's cosine thresholds (≥0.92 duplicate-blocked, 0.78–0.92 variant, <0.62
new-topic — same bands as SOW section 2.3). Flag but do not hard-block in POC; surfaced in the
response for a human decision, matching the SOW's "borderline = human decision" rule.

## Endpoints (`app/routers/drafting.py`)

- `POST /entities/{entity_id}/draft` — runs the 4 chains for the entity's latest MAJOR-classified
  version; 409 if the latest diff isn't MAJOR (nothing to draft)
- `GET /entities/{entity_id}/content` — latest `DraftedContent` + all 7 variants
- `GET /entities/{entity_id}/similarity` — similarity band + nearest existing entity, if any

## Verification

- Draft a fixture product with a MAJOR diff pending → returns filled H1/meta/highlights/body/FAQ
  + 7 variants, `status=validated`
- Attempt to draft an entity with no MAJOR diff → 409 with explanation
- Truncate a fixture's description to trigger a validation failure → `status=failed` with specific
  reasons returned
- Draft two near-identical fixture products → similarity endpoint reports them in the
  VARIANT/DUPLICATE band
- `pytest tests/test_drafting.py` — chain validation rules, stub determinism, similarity banding

## Needed from user

Nothing to start (stub mode). Optional: `OPENAI_API_KEY` in `.env` when you want real GPT-drafted
content instead of templates — no code change required, same endpoints.
