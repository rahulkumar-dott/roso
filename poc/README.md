# Rosotravel AI Platform - POC

Phase-by-phase proof-of-concept backend for the Rosotravel AI & Programmatic Decision
Platform. See `.plan/` at the repo root for the phase-by-phase plan; this README covers how to
run what's built so far.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd poc
uv sync
cp .env.example .env   # optional - defaults work with zero config
```

Optional live LLM drafting:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

Optional local PostgreSQL:

```bash
docker run --name roso-postgres \
  -e POSTGRES_USER=roso \
  -e POSTGRES_PASSWORD=roso_dev_password \
  -e POSTGRES_DB=roso_poc \
  -p 5432:5432 \
  -v roso_postgres_data:/var/lib/postgresql/data \
  -d postgres:16
```

Then set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+psycopg://roso:roso_dev_password@127.0.0.1:5432/roso_poc
```

Optional local PostgreSQL with pgvector:

```bash
docker run --name roso-pgvector \
  -e POSTGRES_USER=roso \
  -e POSTGRES_PASSWORD=roso_dev_password \
  -e POSTGRES_DB=roso_poc \
  -p 5433:5432 \
  -v roso_pgvector_data:/var/lib/postgresql/data \
  -d pgvector/pgvector:pg16
```

Then set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+psycopg://roso:roso_dev_password@127.0.0.1:5433/roso_poc
VECTOR_SIMILARITY_ENABLED=true
SENTENCE_TRANSFORMER_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Optional live Viator ingestion:

```env
VIATOR_API_BASE_URL=https://api.sandbox.viator.com/partner
VIATOR_API_KEY=your_viator_api_key
VIATOR_PARTNER_ID=your_partner_or_campaign_id
```

Optional SEMrush keyword intelligence:

```env
SEMRUSH_API_KEY=your_semrush_api_key
SEMRUSH_DATABASE=us
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs for interactive API docs.

## Phase 1 - Ingestion & Versioning Engine

- `POST /ingest/destinations` - loads the bundled fixture by default, or accepts a JSON body of
  destination objects. Pass `?fixture=sample_viator_destinations_v2.json` to load the modified
  variant.
- `POST /ingest/products` - same pattern for products (`sample_viator_products_v2.json` for the
  modified variant).
- `POST /ingest/attractions` - loads the bundled POI fixture by default, or accepts a JSON body of
  attraction objects.
- `GET /entities/{entity_id}` - current state of a destination, product, or attraction
- `GET /entities/{entity_id}/versions` - full RAW version history
- `GET /entities/{entity_id}/diff/latest` - most recent Diff Engine classification

### Try it end-to-end

```bash
# 1. Ingest the initial fixtures (first ingestion is always classified MAJOR)
curl -X POST http://127.0.0.1:8000/ingest/destinations
curl -X POST http://127.0.0.1:8000/ingest/products

# 2. Re-ingest the v2 variants to see the Diff Engine classify what changed
curl -X POST "http://127.0.0.1:8000/ingest/destinations?fixture=sample_viator_destinations_v2.json"
curl -X POST "http://127.0.0.1:8000/ingest/products?fixture=sample_viator_products_v2.json"

# 3. Inspect a specific entity's diff history
curl http://127.0.0.1:8000/entities/prod_rome_food_tour/diff/latest   # expect MAJOR (description changed)
curl http://127.0.0.1:8000/entities/prod_colosseum_skip/diff/latest   # expect MINOR (price changed)
curl http://127.0.0.1:8000/entities/prod_vatican_tour/diff/latest     # expect MEDIUM (image added)
curl http://127.0.0.1:8000/entities/prod_louvre_tour/diff/latest      # expect NONE (unchanged)
```

## Phase 2 - Factual Enrichment

- `POST /entities/{entity_id}/enrich` - fetches Google Places and Wikidata facts, stores source
  rows, applies optional manual overrides, and reports changed factual hashes.
- `GET /entities/{entity_id}/facts` - returns stored source facts plus resolved facts after source
  priority is applied.

Google Places uses live mode when `GOOGLE_PLACES_API_KEY` is set in `.env`; otherwise it returns
deterministic stub facts. Wikidata uses the public API.

```bash
# 1. Ingest destinations and POIs
curl -X POST http://127.0.0.1:8000/ingest/destinations
curl -X POST http://127.0.0.1:8000/ingest/attractions

# 2. Enrich a POI
curl -X POST http://127.0.0.1:8000/entities/poi_colosseum/enrich

# 3. Enrich with a manual override
curl -X POST http://127.0.0.1:8000/entities/poi_colosseum/enrich \
  -H "Content-Type: application/json" \
  -d "{\"manual_overrides\":{\"phone\":\"+39 06 3996 7700\"}}"

# 4. Inspect resolved facts
curl http://127.0.0.1:8000/entities/poi_colosseum/facts
```

## Phase 3 - AI Drafting Pipeline

- `POST /entities/{entity_id}/draft` - runs retrieval, drafting, validation, audience variants,
  and similarity analysis for the entity's latest MAJOR version.
- `GET /entities/{entity_id}/content` - returns the latest drafted content and all 7 audience
  variants.
- `GET /entities/{entity_id}/similarity` - returns the nearest drafted entity and similarity band.

Drafting uses deterministic templates unless `GROQ_API_KEY` is configured. When configured, it
uses Groq's OpenAI-compatible chat completions API and `GROQ_MODEL`.

```bash
# 1. Ingest a product. First ingestion is MAJOR, so drafting is allowed.
curl -X POST http://127.0.0.1:8000/ingest/products

# 2. Draft content for a MAJOR-classified entity.
curl -X POST http://127.0.0.1:8000/entities/prod_colosseum_skip/draft

# 3. Inspect drafted content and variants.
curl http://127.0.0.1:8000/entities/prod_colosseum_skip/content

# 4. Inspect similarity band.
curl http://127.0.0.1:8000/entities/prod_colosseum_skip/similarity
```

## Phase 4 - Model C Decision Engine

- `POST /model-c/recompute` - recomputes quality scores, Pool eligibility, and archetype grouping.
- `POST /model-c/bulk-auto-confirm` - dev helper that confirms all Pool products into Set.
- `POST /products/{product_id}/set` - simulates Product Ops Set confirmation/removal.
- `GET /cities/{city_id}/picks` - returns Set-only city picks or sparse suppression.
- `GET /countries/{country}/picks` - returns country-level rollup from city outputs.
- `GET /products/{product_id}/explain` - explains Pool/Set status, score, archetype, and winner slots.

```bash
# 1. Ingest fixtures
curl -X POST http://127.0.0.1:8000/ingest/destinations
curl -X POST http://127.0.0.1:8000/ingest/products

# 2. Compute Pool and archetype grouping
curl -X POST http://127.0.0.1:8000/model-c/recompute

# 3. Confirm Pool products into Set for POC demo
curl -X POST http://127.0.0.1:8000/model-c/bulk-auto-confirm

# 4. Inspect city and country decisions
curl http://127.0.0.1:8000/cities/dest_rome/picks
curl http://127.0.0.1:8000/countries/Italy/picks

# 5. Explain one product
curl http://127.0.0.1:8000/products/prod_colosseum_skip/explain
```

## Phase 5 - Schema Publishing

- `POST /entities/{entity_id}/publish` - validates and atomically writes a published record.
- `POST /cities/{city_id}/publish` - writes a dedicated city landing page record.
- `POST /countries/{country}/publish` - writes a dedicated country landing page record.
- `GET /published/{entity_id}` - returns the published content snapshot and JSON-LD.
- `GET /published` - lists published records for frontend/feed consumers.

Published records include backend-generated JSON-LD under `schema_json`. A frontend can later
render this value inside a `<script type="application/ld+json">` tag.

```bash
# Publish a validated drafted entity.
curl -X POST http://127.0.0.1:8000/entities/prod_colosseum_skip/publish

# Publish city/country landing pages.
curl -X POST http://127.0.0.1:8000/cities/dest_rome/publish
curl -X POST http://127.0.0.1:8000/countries/Italy/publish

# Fetch the published content + JSON-LD.
curl http://127.0.0.1:8000/published/prod_colosseum_skip
curl http://127.0.0.1:8000/published/dest_rome
curl http://127.0.0.1:8000/published/country_italy

# List records.
curl http://127.0.0.1:8000/published
```

## Phase 6 - LLM Visibility + MCP-Style Tools

All Phase 6 feeds and tools read only from `PublishedRecord` rows with `status=published`.

- `GET /llms.txt` - machine-readable entry point with feed/tool links.
- `GET /ai-summary.json` - deterministic published entity summary feed.
- `GET /ai-sitemap.xml` - sitemap-style XML over published records.
- `GET /api/tours/feed` - allowlisted commercial product feed.
- `POST /mcp/search_tours` - published-only tour search.
- `POST /mcp/get_tour` - safe published tour detail.
- `POST /mcp/get_availability_link` - inert booking URL placeholder.

MCP-style endpoints require a non-empty `X-Agent-Key` header and write an audit row with a response
hash.

```bash
curl http://127.0.0.1:8000/llms.txt
curl http://127.0.0.1:8000/ai-summary.json
curl http://127.0.0.1:8000/ai-sitemap.xml
curl http://127.0.0.1:8000/api/tours/feed

curl -X POST http://127.0.0.1:8000/mcp/search_tours \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: local-demo-agent" \
  -d "{\"city\":\"Rome\",\"max_results\":5}"

curl -X POST http://127.0.0.1:8000/mcp/get_tour \
  -H "Content-Type: application/json" \
  -H "X-Agent-Key: local-demo-agent" \
  -d "{\"entity_id\":\"prod_colosseum_skip\"}"
```

## Phase 7 - SQL / Persistence

The POC uses SQLAlchemy models and can run on either SQLite or PostgreSQL through `DATABASE_URL`.
For local SQL testing, use the Docker PostgreSQL setup above. The app creates the current POC
tables on startup.

## Phase 7 - Viator Live Ingestion

Fixture ingestion remains the default. To use live Viator data, configure the Viator environment
variables and pass `source=viator`.

```bash
# Ingest a small taxonomy sample.
curl -X POST "http://127.0.0.1:8000/ingest/destinations?source=viator&limit=10"

# Ingest a small product sample from /products/modified-since.
curl -X POST "http://127.0.0.1:8000/ingest/products?source=viator&count=10&limit=10"
```

Viator products can reference destination IDs that are not in the local taxonomy yet. In that case,
the raw `viator_primary_destination_id` is preserved and the relational destination link is left
empty until the matching destination is ingested.

## Phase 7 - SEMrush Keyword Intelligence

SEMrush keyword data is optional and feeds Phase 3 drafting context when present.

- `POST /entities/{entity_id}/keywords` - fetch and store related keywords plus phrase questions.
- `GET /entities/{entity_id}/keywords` - return the latest stored keyword intelligence.

```bash
curl -X POST "http://127.0.0.1:8000/entities/prod_colosseum_skip/keywords?database=us&limit=10"
curl http://127.0.0.1:8000/entities/prod_colosseum_skip/keywords
```

Drafting automatically includes the latest stored keyword context for the entity.

## Phase 7 - Vector Similarity

The duplicate/similarity gate uses sentence-transformer embeddings and Postgres `pgvector` when the
database supports the `vector` extension. SQLite and non-pgvector databases continue to use the
TF-IDF fallback.

The app creates a `content_vectors` table on first vector similarity use:

- embedding model: `SENTENCE_TRANSFORMER_MODEL`
- default dimension: `384`
- similarity method in API response: `pgvector_sentence_transformer` or `tfidf_fallback`

## Admin POC

Read endpoints for the frontend admin dashboard:

- `GET /admin/overview` - counts for destinations, products, published records, drafts, Pool, Set.
- `GET /admin/destinations` - countries, cities, publication state, city inventory state.
- `GET /admin/products` - Product Ops view: quality, Pool, Set, draft, publish status.
- `GET /admin/content` - AI content view: diff severity, draft status, validation errors, variants.
- `GET /admin/publishing` - SEO/publishing view: published records, canonical URLs, JSON-LD nodes.

Write actions intentionally reuse existing governed endpoints:

- Recompute decisions: `POST /model-c/recompute`
- Confirm Pool to Set: `POST /model-c/bulk-auto-confirm`
- Add/remove one product from Set: `POST /products/{product_id}/set`
- Generate AI draft: `POST /entities/{entity_id}/draft`
- Publish pages: `POST /entities/{entity_id}/publish`, `/cities/{city_id}/publish`,
  `/countries/{country}/publish`

## Tests

```bash
uv run pytest
```
