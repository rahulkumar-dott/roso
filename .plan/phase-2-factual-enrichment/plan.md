# Phase 2 — Factual Enrichment

Status: depends on Phase 1 models. Wikidata works with zero credentials; Google Places runs in
stub mode until a key is supplied.

## Why

SOW System 1.4: factual data (hours, address, coordinates, phone, ratings, encyclopedic facts)
must come from a governed factual layer, never be fabricated by AI, and carry its own hash so
factual changes trigger schema refreshes without necessarily triggering a content rewrite.

## What gets built

Data model (`app/models/entities.py` addition):
- `EnrichedFact` — id, entity_id, source (`google_places`/`wikidata`), fields (JSON: opening_hours,
  formatted_address, lat, lng, phone, rating, review_count for Places; inception_year,
  architectural_style, entity_type, sameAs, isPartOf/hasPart for Wikidata), factual_hash,
  fetched_at

Adapters (`app/services/enrichment.py`):
- `WikidataAdapter` — live by default (public API, no key). Given an entity name/city, queries
  Wikidata's SPARQL or REST entity search, extracts the SOW's listed fields.
- `GooglePlacesAdapter` — `STUB` mode returns deterministic mock data (fixed fake hours/address/
  rating keyed off entity name) when `GOOGLE_PLACES_API_KEY` is unset; calls the real Places API
  once a key is present. Same method signature either way, so no caller code changes when the
  key is added later.
- Both adapters compute `factual_hash` over their returned fields the same way the Diff Engine
  does, so a factual change is independently detectable from a content change.

## Endpoints (`app/routers/enrichment.py`)

- `POST /entities/{entity_id}/enrich` — runs both adapters, stores/updates `EnrichedFact` rows,
  returns what changed vs the previous factual_hash (if any)
- `GET /entities/{entity_id}/facts` — current stored facts from both sources

## Verification

- Enrich a fixture destination (e.g. "Rome") — Wikidata returns real inception/entity data
- Enrich a product location with no `GOOGLE_PLACES_API_KEY` set — stub adapter returns
  consistent mock hours/address/rating, `source=google_places (stub)` flagged in the response so
  it's never confused with real data
- Re-enrich with unchanged inputs — `factual_hash` unchanged, no update recorded
- `pytest tests/test_enrichment.py` — adapter stub determinism, hash stability

## Needed from user

Nothing to start. Optional: a Google Places API key when you want live enrichment instead of the
stub (drop it in `.env` as `GOOGLE_PLACES_API_KEY`, no code change needed).
