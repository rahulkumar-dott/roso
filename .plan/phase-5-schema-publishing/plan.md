# Phase 5 — Schema & Publishing Layer

Status: depends on Phase 3 (drafted content) and Phase 4 (Model C output, optional but
recommended for decision-proof fields). Zero external dependencies.

## Why

SOW Systems 2.9/2.12: nothing goes live without passing schema validation, and publishing is
atomic — a partially-failed job can never produce a broken indexable page. This is also the
layer everything in Phase 6 (frontend/LLM-facing feeds) reads from, so it's the last internal
phase before the platform has something externally consumable.

## What gets built

Data model (`app/models/entities.py` addition):
- `PublishedRecord` — id, entity_id, entity_type, canonical_url, schema_json (JSON-LD), content
  (denormalized snapshot of `DraftedContent` + winning `AudienceVariant` set + Model C output at
  publish time), date_published, date_modified, version, status (`published`/`held`)

Schema Builder (`app/services/schema_builder.py`):
- Builds JSON-LD per entity type (`TouristAttraction`/`Product`/`City` equivalents from
  schema.org) using only factual-layer + drafted-content fields — never fabricates values
- Stable `@id` (canonical URL + entity type prefix), `datePublished` set once and never updated,
  `dateModified` updated per republish
- `AggregateRating` block included only if a rating value is present in the source data (mirrors
  the SOW's UI-schema parity gate — since POC has no separate rendered UI, this means "only if
  rating exists in the record being published")

Validation gates (`app/services/schema_builder.py::validate`):
- Required fields present (title, meta description, H1, canonical) → block if missing
- JSON-LD structurally valid (has `@context`, `@type`, `@id`)
- Factual integrity: coordinates/hours/phone in schema must trace back to an `EnrichedFact` row,
  never drafted content — reject if a factual-looking field wasn't sourced from Phase 2

Publisher (`app/services/publisher.py`):
- Deterministic winner rule for what gets published: human-locked content (out of POC's
  scope — noted as a Phase 7+ CMS feature) > AI-drafted content > raw seed. For POC: publish
  the latest `validated` `DraftedContent`.
- Atomic: build the full `PublishedRecord` in memory, run all validation gates, only commit to DB
  if every gate passes. Any failure returns a structured list of what blocked it — nothing partial
  is ever written.

## Endpoints (`app/routers/publishing.py`)

- `POST /entities/{entity_id}/publish` — runs validation, atomically writes `PublishedRecord` or
  returns 422 with the specific gate failures
- `GET /published/{entity_id}` — the published record (content + schema)
- `GET /published` — list all published records (paginated), for the frontend to build listing
  pages against

## Verification

- Publish a fully-drafted, Model-C-confirmed fixture entity → `PublishedRecord` created,
  `GET /published/{id}` returns valid JSON-LD passing a JSON-LD structural check
- Attempt to publish an entity missing meta description → 422 naming exactly that gate
- Publish, then re-publish after a content change → `date_modified` updates, `date_published`
  unchanged, same `@id`
- `pytest tests/test_publishing.py` — atomicity (a failing gate leaves no partial record), @id
  stability across republishes

## Needed from user

Nothing. Runs entirely on internally generated data from Phases 1–4.
