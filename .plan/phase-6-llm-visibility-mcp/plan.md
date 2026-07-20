# Phase 6 — LLM Visibility Layer + MCP Server

Status: depends on Phase 5 (Published Records). Zero external dependencies. This is the phase
that produces something a frontend or an AI agent (Claude, ChatGPT, etc.) can directly call.

## Why

SOW Systems 6+7: make the platform discoverable and queryable by LLMs/agents independent of
Google, via static feeds plus a read-only tool interface — and critically, that interface must read
only from the published cache, never the canonical DB, and must never leak drafts, noindex
entities, or raw supplier content.

## What gets built

Feeds (`app/routers/llm_visibility.py`), generated live from `PublishedRecord` (POC scale doesn't
need pre-generation/caching, but the query is deliberately scoped to published-only rows to
mirror the SOW's indexable-gate rule):
- `GET /llms.txt` — plain text entry point describing the platform + links to the other feeds
- `GET /ai-sitemap.xml` — one entry per published record: url, entity_type, geo (if present),
  isPartOf/hasPart (from `Destination`/`Product` relations), lastmod
- `GET /ai-summary.json` — per entity: name, url, entity_type, summary_short, highlights,
  key_faq, geo, lastmod — deterministic, no audience personalization (matches SOW: DEE variants
  never appear here)
- `GET /api/tours/feed` — cursor-paginated commercial catalog (id, canonical_url, name,
  short_summary, highlights, key_faq, booking_url placeholder, price_from, currency,
  availability_state, duration). Explicitly excludes anything supplier-sourced per the SOW's hard
  rule — a field-allowlist serializer, not a blocklist, so nothing new can leak by accident.

MCP-style tool endpoints (`app/routers/mcp.py`) — implemented as plain REST for POC (a thin
JSON-RPC 2.1 wrapper can be layered on after the underlying logic is proven; the SOW's
functional contract is what matters here, not the transport):
- `POST /mcp/search_tours` — input: country, city, categories[], max_results. Output: entity_id,
  name, canonical_url, price_from, currency, duration_minutes, rating_average, source_type.
  Reads only `PublishedRecord` rows, deterministic ordering, no personalization.
- `POST /mcp/get_tour` — input: entity_id. Output: full structured detail excluding availability
  calendars/variant matrices/supplier metadata.
- `POST /mcp/get_availability_link` — input: entity_id, date (optional). Output: a
  booking_url placeholder (POC has no real booking system — returns a well-formed but inert
  URL) plus a note that date is a routing hint only, matching the SOW's contract.
- All three log agent_id (from a required `X-Agent-Key` header, POC accepts any non-empty value)
  + tool_name + params + response hash, for the audit trail the SOW requires.

## Verification

- With ≥1 published entity: `GET /ai-summary.json` and `/ai-sitemap.xml` include it;
  unpublished/draft entities never appear in any feed (test by publishing one, leaving one
  unpublished, asserting the draft's entity_id is absent from every feed response)
- `POST /mcp/search_tours` with a city filter returns only published entities in that city
- `POST /mcp/get_tour` response contains no field named anything like `supplier_id`/
  `supplier_url`/raw payload keys — assert via an explicit denylist test
- Point an actual MCP-capable client (or Claude Code itself) at `/mcp/*` and confirm it can search
  and retrieve a tour — this is the "frontend/agent can use it today" milestone for the whole POC
- `pytest tests/test_llm_visibility.py`, `tests/test_mcp.py`

## Needed from user

Nothing to build it. Once built: decide whether you want a real JSON-RPC 2.1 MCP transport
wrapper (for genuine MCP client compatibility) or the REST shape is sufficient for your frontend
team's needs — that's a quick follow-up either way.
