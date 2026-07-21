# Phase 8 — Admin Panel (CMS & Governance Layer)

## Context

The original AI SOW (`.context/Rosotravel_AI_SOW_v2.1_Final.pdf`) defines a full "System 4: CMS &
Governance Layer" — Marketing Panel, Product Ops Panel, SEO Governance, Optimization Inbox, and
a 5-role permission model. The WBS spreadsheet (`.context/RosoTravel __ Website - WBS
[Updated].xlsx`) then repeats a consistent "Admin Handling" block on almost every content
feature across every page sheet (Country_Page, City_Page, Attractions_Page, Homepage, Global
Components): **Content Source, Editable (often "editable / lockable"), Language Specific,
Version Controlled, CMS Field/Token**. This phase turns that scattered-but-consistent spec into
one coherent admin build plan, and corrects one deviation already in the code (see below).

An admin dashboard already exists (`web/src/app/admin/`, backed by `poc/app/routers/admin.py` +
`poc/app/services/admin.py`) with: an overview stat panel, a destinations tree with
publish/promote actions, a taxonomy-create panel (Country/Region/City/Attraction), a Product
Ops table (Pool/Set/draft/publish actions), an AI Content panel, and a Publishing/SEO panel with
a per-record content-lock form. This phase's job is to reconcile what exists against what the
docs actually specify, fix the one real deviation, and fill the gaps — not rebuild from scratch.

## Known deviation to correct

**The "Create Country / Region / City" taxonomy panel contradicts SOW System 1.1**, which is
explicit: *"Destination hierarchy is NOT supplied as a manual marketing file. It is ingested,
refreshed, and maintained from the Viator API feed... administrators review, approve, merge
duplicates... assign stable internal entity_ids."* The current `source="internal"` manual-create
path borrows the Product internal/external pattern (which SOW System 1.2 does explicitly allow
for products) and wrongly applies it to destinations, which the SOW treats as one Viator-sourced
pipeline with no manual side at all.

**Correct behavior to add** (does not require deleting the existing manual-create forms — they
stay as a POC convenience — but the doc-correct workflow must exist alongside them):
1. **"Sync from Viator" action** — calls the already-built `ViatorClient().destinations()`,
   ingests anything new as `pending_review` (not immediately `active`)
2. **Pending-review queue** — newly-synced destinations appear in a queue, not live
3. **Duplicate detection** — flag new destinations whose name+country closely match an
   already-approved one (Viator commonly returns re-numbered duplicates)
4. **Approve / Reject / Merge actions** — human decision per pending destination; merge
   reassigns any linked products from the duplicate to the canonical survivor
5. **Real activation gate** — a destination becomes `active` (publishable) only once *both*
   approved *and* has ≥1 linked product, per System 1.1: *"A destination becomes active once at
   least one product is linked to it."* Needs care: don't retroactively break the 21 already-active
   demo destinations — gate should apply to newly-ingested ones, existing ones grandfather in.

## Module 1 — Field-level Lock / Regenerate / Revert (the pattern used everywhere)

Every single CMS-editable content field across every page type (Country's Overview/Highlights/
Facts/FAQ/About-Rosotravel, City's equivalents, Attraction's Overview/History/Visitor-Info/FAQ,
Homepage's H1/Subheadline/Snippets) follows the **same** governance rule, stated identically
across dozens of WBS rows: *"AI-generated first draft; Human editable; Lockable in CMS...
locked ⇒ not overwritten by regeneration unless explicitly re-enabled."* This is also stated in the
original AI SOW's acceptance criteria: *"A regenerate trigger on a locked field produces a new AI
draft stored as a candidate — it does not overwrite the locked value until a human explicitly
accepts it. A revert action restores the most recent AI-generated version of a field, clearing the
manual lock."*

**Already built**: `content_locks` on `PublishedRecord`, `POST /published/{id}/content` (updates +
lock_fields + unlock_fields + edited_by), `ContentLockForm` in the admin UI.

**Gaps against the spec's exact 3-action model** (lock / regenerate-as-candidate / revert):
- No **regenerate-as-candidate** flow — regeneration today would just overwrite, there's no
  "candidate awaiting accept" state distinct from the live value
- No **revert-to-latest-AI-version** action (distinct from unlock)
- No version history view per field (WBS: "Version Controlled – Yes" on almost every field)

## Module 2 — Destination Governance (see deviation section above)

Sync-from-Viator, pending-review queue, duplicate detection, approve/reject/merge, real
activation gate tied to product-linkage.

## Module 3 — Marketing Panel (SOW System 4.1)

Per the SOW verbatim: *"AI & SEO Operations Console: pipeline status, batch activation controls
(Marketing Manager / Admin only), processing queue, daily cap monitoring... Keyword Ownership
Panel: full keyword_map view, allocation history, cannibalization risk alerts... Near-Page Control
Panel (High Risk): Stage 1 and Stage 2 near-page candidates... human approval gate before
indexing... Canonical & Duplicate Inspector: pages_vectors similarity scores... SEMrush Rules
Panel: configurable thresholds, cost governance."*

Our POC has no keyword/near-page/SEMrush subsystems built at all (Phase 7, deferred), so this
module is mostly **not buildable** until those exist. The one piece that *is* buildable now:
**Canonical & Duplicate Inspector** — we already compute similarity bands (`vector_similarity.py`)
for drafted content; expose that as an admin panel (which pages are DUPLICATE/VARIANT/
BORDERLINE against which others).

## Module 4 — Product Ops Panel (SOW System 4.2)

Per the SOW: *"Portfolio Governance: RAW > Pool > Set membership management, eligibility
threshold configuration... Algorithm Configuration: quality threshold settings, weight
multipliers... Explainability Panel: for every Set product, shows full reason code breakdown,
archetype winner decision, and what competing products were evaluated. Debugging Panel: full
trace of pipeline steps per entity, validation failure reasons, Diff Engine decisions."*

**Already built**: Pool/Set toggle, `model_c.explain_product()` surfaced per-product.
**Gaps**:
- **Algorithm Configuration UI** — `pool_min_quality_score` / `set_sparse_threshold` exist as
  Python config constants (`config.py`), not admin-editable
- **Debugging Panel** — no UI trace of Diff Engine severity history / validation failures per
  entity; the data exists (`DiffResult`, `DraftedContent.validation_errors`) but isn't surfaced

## Module 5 — SEO Governance (SOW System 4.3) + the Country "Lite Page" gate

Per the SOW: *"Indexation control per page type with eligibility gates... AggregateRating schema
gate: emitted only when rating is visible in UI and schema matches displayed value exactly...
Media rights governance integrated."*

**Already built**: country `noindex`/promote gate (this session), `content_locks` shown per
record.
**Gaps**:
- No admin view of `llms.txt` / `ai-sitemap.xml` / `ai-summary.json` regeneration status
- No media rights (Class A/B/C source_class) admin view — we don't have media rights tracking
  at all in this POC, would need System 1.5's `source_class`/`rights_status`/`indexable` fields
  added to media handling first (currently out of scope, no image-generation pipeline built)

## Module 6 — Roles & Permissions (SOW System 4.6)

Exact 5-role table from the SOW:

| Role | Key Permissions |
|---|---|
| Admin | Full system, restricted full re-run, role management, audit log, API cost governance |
| SEO Lead / Head of Content | Keyword ownership, canonical overrides, near-page approval (both stages), batch activation |
| Content Editor / Marketer | Manual edits, field locks/unlocks/reverts, optimization queue, batch QA review |
| Product Operations Lead | Portfolio Set management, winner rule configuration, reason code review, archetype configuration |
| Junior Editor | Read-only CMS, Optimization Inbox view, QA sampling tasks |

**Not built at all** — the admin dashboard today has no auth/role concept, every action is
available to anyone who can reach `/admin`. For a POC this may be acceptable to defer entirely,
or a thin version (a role selector that just filters which buttons render, no real auth) could
demonstrate the *shape* of the permission model without building real authentication.

## Module 7 — Homepage CMS Admin (WBS `Homepage` sheet)

The Homepage sheet defines ~15 CMS-editable blocks, all following the same Content
Source/Editable/CMS-Field pattern as everywhere else:

- **Hero**: `homepage_hero_media_id`, `homepage_h1` (explicitly *"manual brand copy, not
  AI-generated"* — the one field the docs say must NOT be AI-drafted), `homepage_subheadline`,
  `homepage_snippet_*` (7 audience variants, Phase-2), `homepage_search_placeholder`,
  `homepage_primary_cta`, `homepage_quick_categories`
- **Decision Narrative Strip**: `homepage_decision_strip_line1`/`_tooltip`/`_modal_content`/
  `_about_link` — copy explicitly *"must not mention AI curation (use 'RosoTravel experts' /
  'RosoTravel standards')"*
- **RosoTravel Live proof block**: `live_metrics_enabled` + `live_metrics_window_thresholds`
  (Product Ops config) — real computed metrics (tours_run/travelers_hosted/average_rating) with
  a hard rule: *"never show zeros as proof"* — needs a bookings/departures data model we don't
  have (same gap flagged for City's Live Snapshot, deferred there too)
- **Top Destinations**: `homepage_top_destinations[]` (System + CMS weighting) — ranking formula
  is fully specified (`0.45*bookings_28d_norm + 0.20*conversion_rate_28d_norm + ...`, editable
  weights via Product Ops config) plus `homepage_destination_pins[]`/`_exclusions[]` (force
  top / force hide, Admin-only)
- **Trending Experiences**: `homepage_trending_products[]` + ranking formula (same pattern) +
  `homepage_trending_pins[]` (Originals pinning, bounded tolerance)
- **Social Proof / Featured Guides / Blog Highlights / Email Capture Hook**: editorial CMS blocks,
  same lock/edit pattern as everywhere else

**Buildable now without new subsystems**: Hero copy fields, Decision Narrative Strip copy,
Quick Shortcuts config, pins/exclusions (`homepage_destination_pins[]` etc — just an admin-set
list, no ranking engine needed to make pinning work), Social Proof bullets, Blog Highlights list.
**Needs subsystems we don't have**: Live Metrics (bookings data), the two ranking formulas (need
real GA4/GSC/booking signals to normalize against — could stub with Model C's existing
quality_score as a rough proxy, clearly labeled as an approximation).

## Module 8 — Global Components Admin (WBS `Global Components` sheet)

Site-wide chrome, all `"Content Source – CMS"`, `"Editable – Yes"`:
- **Header**: logo, 5 mega-menus (Destinations/Experiences/Travel Guides/Experts/Explore Map) —
  each just a `Menu Configuration` token (label + landing URL + optional sub-links)
- **Navigation**: same Menu Configuration source; active-state and language handling are
  System-generated, not admin-editable
- **Footer**: 4 link sections (About/Explore/For Businesses/Support/Legal) via the same
  `Footer Menu Configuration` token, plus `Organization Schema` fields (name, official website,
  contactPoint, sameAs)
- **Cookie & Consent banner**: enable/configure, GDPR consent persists 12 months
- **Live Chat widget** (tawk.to): enable/disable only, Phase-2

**Buildable now**: this is genuinely simple — a handful of Menu Configuration list-editors (label +
URL pairs) and a couple of toggle switches. No subsystem dependencies at all. Lowest-risk,
highest-completeness-per-effort module in this whole phase.

## Module 9 — Optimization Inbox (SOW System 4.5, named explicitly, not yet built)

The SOW names a single unified queue with 10 specific signal types, *"every signal requires
explicit human resolution"*:
`OUTDATED`, `MISSING`, `CONFLICT`, `LOCKED_BLOCKED_UPDATE`, `AI_FAILED`, `AI_BACKLOG`,
`SCHEMA_INVALID`, `MEDIA_REVIEW_REQUIRED`, `EXTERNAL_API_FAILURE`, `NEAR_PAGE_READY_FOR_REVIEW`.

Cross-referenced against what we actually have real data for:
- **`AI_FAILED`** — buildable now, `DraftedContent.status == "failed"` already tracked with
  `validation_errors`
- **`SCHEMA_INVALID`** — buildable now, `schema_builder.validate()` already returns structured
  errors on publish (currently just a 422 response, not persisted as a standing signal)
- **`EXTERNAL_API_FAILURE`** — buildable now, and we have *real* examples already (the Groq
  429 rate-limit failures hit during this session's country/city drafting work) — just needs the
  failure persisted as a signal row instead of only surfacing as a one-off HTTP error
- **`OUTDATED`, `MISSING`, `CONFLICT`, `MEDIA_REVIEW_REQUIRED`, `NEAR_PAGE_READY_FOR_REVIEW`** —
  need GSC/GA4 signals, media rights tracking, or the near-page module — none of which exist;
  not buildable without building those subsystems first
- **`LOCKED_BLOCKED_UPDATE`, `AI_BACKLOG`** — buildable once Module 1's regenerate-as-candidate
  flow exists (a locked field blocking an attempted regeneration is exactly this signal)

## Module 10 — Audit Logging (cross-cutting, appears repeatedly, never called out on its own)

The docs require an audit trail for manual overrides in multiple places (*"Any manual override
requires Admin-only action and audit log"* — Homepage Live Metrics, Guest-loved bullets; *"role
management, audit log"* — Admin role permission in SOW 4.6). Needs one simple `AuditLog` table
(actor, action, entity_id, field, before/after, timestamp) written to by: field lock/unlock, content
edits, regenerate/revert, Set membership changes, country promote/demote, destination
approve/reject/merge. A single admin panel lists recent entries, filterable by entity/actor.

## Module 11 — API Cost Governance (SOW 4.6 Admin permission, System 10)

The SOW ties this to System 10's per-API governance (unit caps, endpoint allowlists, refresh
frequency). We already call Groq, Google Places, Wikidata, SEMrush, Viator live — buildable now
as a simple call-count/failure-count-per-service dashboard (reuse Module 9's
`EXTERNAL_API_FAILURE` signals as the failure half; add a basic counter incremented on each
outbound call for the volume half). Real cost/billing figures are out of reach without each
provider's billing API, so this stays at "call volume + failure rate," not real dollar costs.

## Priority recommendation

1. **Fix the destination-creation deviation** (Module 2) — the one place current code
   contradicts a clearly-stated rule, not just an unbuilt feature
2. **Field-level regenerate-as-candidate + revert** (Module 1) — the single most-repeated
   requirement across every page type in the WBS; currently only lock/unlock exist
3. **Global Components admin** (Module 8) — simplest, no subsystem dependencies, high
   completeness-per-effort
4. **Product Ops Debugging Panel** (Module 4) — data already exists, just needs surfacing
5. **Canonical & Duplicate Inspector** (Module 3) — data already exists (`vector_similarity.py`)
6. **Optimization Inbox, the 4 buildable signal types** (Module 9) — `AI_FAILED`,
   `SCHEMA_INVALID`, `EXTERNAL_API_FAILURE` now; `LOCKED_BLOCKED_UPDATE`/`AI_BACKLOG` once
   Module 1 lands
7. **Audit Logging** (Module 10) — small, cross-cutting, worth doing alongside Module 1/2 since
   those are exactly the actions that need logging
8. **Homepage CMS — the buildable half** (Module 7): hero/strip copy, pins/exclusions, editorial
   lists. Skip Live Metrics and the two ranking formulas until real booking/GA4 data exists
9. **API Cost Governance** (Module 11) — cheap once Module 9's failure tracking exists
10. Roles/auth (Module 6), keyword/near-page panels, media rights, Live Metrics, ranking
    formulas — need subsystems we don't have; flag as deferred, don't build speculatively

## Verification approach (once implemented)

- Sync-from-Viator against a country already in the demo set → new destinations land as
  `pending_review`, not immediately live; duplicate detection flags at least one known case
  (re-ingesting Rome should flag against `demo_dest_rome`)
- Approve a pending destination with 0 linked products → confirm it stays inactive
  (not publishable) until a product is linked
- Lock a field, trigger regenerate → confirm the locked value is untouched and a candidate is
  stored separately; accept the candidate → confirm it then becomes the live value
- Revert a locked field → confirm it restores the most recent AI version and clears the lock
- Debugging panel shows real Diff Engine severity history for at least one entity with >1 version
- Trigger a real Groq failure (or simulate one) → confirm it appears as an `EXTERNAL_API_FAILURE`
  signal in the Optimization Inbox, not just a one-off HTTP 500 to the caller
- Edit a Header menu link via Global Components admin → confirm it actually changes the live nav
- Every one of the above actions produces a matching row in the Audit Log panel

## Verification approach (once implemented)

- Sync-from-Viator against a country already in the demo set → new destinations land as
  `pending_review`, not immediately live; duplicate detection flags at least one known case
  (re-ingesting Rome should flag against `demo_dest_rome`)
- Approve a pending destination with 0 linked products → confirm it stays inactive
  (not publishable) until a product is linked
- Lock a field, trigger regenerate → confirm the locked value is untouched and a candidate is
  stored separately; accept the candidate → confirm it then becomes the live value
- Revert a locked field → confirm it restores the most recent AI version and clears the lock
- Debugging panel shows real Diff Engine severity history for at least one entity with >1 version
