# Phase 7 — Real Integration Swap-In (stretch)

Status: not started until the user supplies credentials for a given service. Each earlier phase
was built with a live/stub seam specifically so this phase is a config change per integration, not
a rewrite. Tackle these independently, in whatever order credentials arrive.

## Why

Phases 1–6 prove the architecture end-to-end on sample/mock data. This phase replaces each
mock adapter with the real external service the SOW specifies, one at a time, so the POC
gradually becomes a real pipeline without ever being blocked waiting on all credentials at once.

## Swap-in list (independent, do in any order)

| Integration | Unlocks | What's needed from user | Where the seam already is |
|---|---|---|---|
| Viator / OTA API | Real destination + product ingestion instead of fixtures | API credentials + feed access (SOW section 8.1) | `app/routers/ingestion.py` — fixture loader becomes a Viator API client behind the same `POST /ingest/*` contract |
| OpenAI (GPT) | Real drafted content instead of templates | `OPENAI_API_KEY` | `app/services/drafting.py::LLMAdapter` |
| OpenAI embeddings | Real cosine-similarity dedup instead of TF-IDF | Same `OPENAI_API_KEY` | `app/services/drafting.py` similarity gate |
| Google Places | Real hours/address/coordinates/rating | `GOOGLE_PLACES_API_KEY` | `app/services/enrichment.py::GooglePlacesAdapter` |
| SEMrush | Real keyword volume/intent/PAA for content targeting | SEMrush API key (Business plan+) | New: `app/services/keyword_intel.py`, feeds into Phase 3 drafting context |
| Google Search Console | Real CTR/impressions for the optimization loop | GSC API access for target domain(s) | New: `app/services/gsc.py` — not yet scoped as a POC phase; SOW's daily/weekly optimization loop (System 2.15) is production-scale and a reasonable next POC phase once this data source exists |
| Qdrant | Swap the TF-IDF/embedding similarity check for the SOW's actual 4-collection vector setup | A running Qdrant instance (local Docker or hosted) | `app/services/drafting.py` similarity gate — interface already returns the same similarity-band shape |
| Postgres | Move off local SQLite onto the project's real database | Reachable connection (the `10.0.12.236:5432` instance seen via this session's Postgres MCP tool timed out — needs VPN/network access or a different host) | `DATABASE_URL` env var only — SQLAlchemy models are already portable |
| Copyscape / Screaming Frog | Real plagiarism + AI-footprint checks in Chain 3 | Copyscape API key; Screaming Frog is a desktop/CLI tool, needs a decision on how it's invoked from a backend service | `app/services/drafting.py` Chain 3 — currently does structural validation only, explicitly flagged as a gap in Phase 3's plan |
| Cloudinary | Real media pipeline (WebP/CDN/lazy-load) instead of raw image URLs from fixtures | Cloudinary account + quota | Not yet scoped as a POC phase — media handling was out of scope for Phases 1–6; add as a dedicated phase once needed |

## How to proceed

For each row: drop the credential in `.env`, confirm the adapter's stub-vs-live toggle picks it up
automatically (each earlier phase's plan.md documents this), then re-run that phase's
verification checklist against the live service instead of the stub. No endpoint contracts change.

## Needed from user

Tell me which row to tackle first once Phases 1–6 are built and demoed — and provide that row's
credential/access at that time. No need to gather all of these upfront.
