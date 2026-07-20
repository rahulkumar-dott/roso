# Phase 1 — Scaffold + Ingestion & Versioning Engine

Status: ready to build. Zero external dependencies — nothing needed from the user.

## Why

This is the foundation every later phase reads from: a RAW store of destinations/products with
full version history, and the Diff Engine that decides whether a change is worth reprocessing
(SOW System 1). Nothing downstream (drafting, Model C, publishing) can exist without this.

## What gets built

Project scaffold (`poc/`):
- `app/main.py` — FastAPI app, CORS for local frontend dev, router registration, `/health`
- `app/core/config.py` — Pydantic Settings: `DATABASE_URL` (default `sqlite:///./poc.db`), stub
  flags for later phases (`OPENAI_API_KEY`, `GOOGLE_PLACES_API_KEY`, unset = stub mode)
- `app/core/db.py` — SQLAlchemy engine/session, `get_db` dependency
- `requirements.txt`, `.env.example`, `README.md` (run instructions)

Data models (`app/models/entities.py`):
- `Destination` — id, entity_id (stable), name, country, region, city, source (`viator`/`internal`),
  status (`inactive`/`active`), created_at
- `Product` — id, entity_id, destination_id (FK), name, category_group (`01_tours` /
  `02_tickets` / `03_transfers`), source (`viator`/`internal`), status
- `RawVersion` — id, entity_type (`destination`/`product`), entity_id, version_number, payload
  (JSON, the raw ingested blob), content_hash, factual_hash, media_hash, offer_hash,
  realtime_offer_hash, created_at
- `DiffResult` — id, entity_id, from_version, to_version, severity (`MINOR`/`MEDIUM`/`MAJOR`),
  changed_domains (JSON list), created_at

## Diff Engine (`app/services/diff_engine.py`)

Given a new payload and the previous `RawVersion`:
1. Compute 5 SHA-256 hashes over normalized sub-fields of the payload, matching the SOW's
   domains: `content_hash` (title/description/highlights), `factual_hash` (hours/address/
   geo/phone/ratings), `media_hash` (image/video refs), `offer_hash` (options/inclusions/
   cancellation), `realtime_offer_hash` (price/availability)
2. Compare against the previous version's stored hashes per domain
3. Classify severity by the SOW's rule table: any `content_hash` or `factual_hash` change →
   `MAJOR`; `media_hash` or `offer_hash` change (with no MAJOR trigger) → `MEDIUM`;
   `realtime_offer_hash`-only change → `MINOR`
4. Store the `DiffResult`. Hard rule carried into Phase 3: only `MAJOR` ever queues AI drafting.

## Endpoints (`app/routers/ingestion.py`, `entities.py`)

- `POST /ingest/destinations` — body: array of Viator-destination-shaped objects (or omit body
  to load the bundled fixture). Upserts `Destination` rows, creates a `RawVersion` each time,
  runs the Diff Engine if a prior version exists.
- `POST /ingest/products` — same pattern for `Product`.
- `GET /entities/{entity_id}` — current record + latest version summary
- `GET /entities/{entity_id}/versions` — full version history
- `GET /entities/{entity_id}/diff/latest` — most recent `DiffResult`

## Fixtures (`app/fixtures/`)

- `sample_viator_destinations.json` — ~5 destinations (e.g. Rome, Paris, Rome/Colosseum region
  nesting) shaped like a plausible Viator destination feed response
- `sample_viator_products.json` — ~10 products across those destinations, with enough fields
  (title, description, highlights, price, duration, images, cancellation policy) to exercise all 5
  hash domains
- A second variant of each fixture (`*_v2.json`) with deliberate changes in different domains, to
  demo MINOR/MEDIUM/MAJOR classification on re-ingestion

## Verification

- `uvicorn app.main:app --reload`, browse `/docs`
- `POST /ingest/destinations` then `/ingest/products` with no body → fixtures load, entity IDs
  returned
- Re-POST the `_v2` fixtures → new `RawVersion` per changed entity, `GET .../diff/latest` shows
  correct severity per the domain that changed
- `pytest tests/test_diff_engine.py` — unit tests for hash classification (MINOR/MEDIUM/MAJOR
  cases, no-change case)

## Needed from user

Nothing. Confirm scope, then build.
