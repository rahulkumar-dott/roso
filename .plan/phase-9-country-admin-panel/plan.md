# Phase 9 — Unified Country Admin Panel (City follows after)

## Context

This phase consolidates everything a Country page needs into **one admin screen per country**,
instead of today's split across two tabs (`/admin/destinations` has publish/promote/approve/
reject/merge; `/admin/content` has edit/lock/hero-image). Nothing here is new backend
functionality — every action below already has a working endpoint. This is a UI consolidation,
plus one small backend addition (see "New: empty-country signal" below) and one explicit
non-goal confirmed against the docs.

Grounded in `.context/Rosotravel_AI_SOW_v2.1_Final.pdf` (System 1.1, System 4) and
`.context/Scope 1_ affiliation front-end & backend + cancellation system 1.4 - Viator.pdf`.
City gets the same treatment in the next phase, once this one is confirmed working.

## What belongs on the unified Country screen

1. **Approve / Reject / Merge** (if the country itself is still `pending_review`)
   Confirmed in code (`sync_viator_destinations`): every newly-synced row, at every level —
   COUNTRY, REGION, CITY — lands as `review_status = "pending_review"`, not auto-approved.
   So a freshly-synced country genuinely can be sitting in the pending queue, same as a city.
   Already built (`/admin/destinations/{id}/approve|reject|merge`), currently only reachable
   from the Destinations tab.

2. **Publish**
   Recomputes content + schema from current source data. Already built
   (`POST /countries/{country}/publish`), currently only reachable from the Destinations tab.

3. **Promote / Demote** (WBS "Lite Page" governance)
   A country page publishes as `noindex,follow` until a human manually promotes it. Already
   built (`POST /countries/{country}/promote`), currently only reachable from the Destinations
   tab. Show current `index_state` prominently on the unified screen.

4. **Edit content, field by field**
   H1, meta title/description, overview, highlights, facts, FAQ, top_regions, top_cities —
   Lock / Regenerate-as-candidate / Accept / Reject / Revert. Already built and entity-type
   generic; currently only on the Content tab.

5. **Hero image**
   Generate (Nano Banana Pro, AI) with a manual upload override, or Accept/Reject a
   regenerated candidate. Already built this session; currently only on the Content tab.

6. **Governance status at a glance**
   Locked fields, pending candidates (text + hero image), last published/modified timestamps,
   review_status if still pending — all in one place instead of cross-referencing two tabs.

## Explicit non-goal, confirmed against the docs

**No manual "activate" / "deactivate" toggle for the country itself.** Searched all 7 source
documents for "activate"/"deactivate" — the only real hit is a per-**product** three-dot menu
("Single trip management panel – Affiliations... The three dots give you the following
options: - deactivate - activate", Scope 1 doc). Nothing equivalent exists for destinations.
A destination's active/inactive state is explicitly **derived**, never manually toggled:

> "A destination becomes active once at least one product is linked to it." (SOW System 1.1)

> "If Viator deletes a destination (e.g. a country): ...the Rosotravel destination is not
> deleted, Rosotravel products remain active." (Scope 1 doc — destinations are never deleted,
> even by the upstream source)

So: no delete button, no activate/deactivate button, for country or city. Do not build one -
it would contradict "the destination tree is protected."

## New: empty-country signal (small backend addition, not yet built)

Real gap identified in this session: `destination_activation_error()` (the active/inactive
gate) is only checked for **cities** — never for the country page itself. If every city under
a country loses all its products, the country page stays exactly as published (including
`index_state: indexed` if already promoted) with an empty "Cities in {country}" section, and
nothing flags it. This scenario isn't directly addressed in the docs (they describe Viator
deleting a destination outright, not a country's cities going quietly inactive one by one), so
treat this as an inference consistent with the existing derived-state philosophy, not a literal
doc requirement:

- On `publish_country_page`, if the country now has zero cities passing
  `destination_activation_error`, auto-set `index_state = "noindex"` (mirrors the existing
  promote/demote gate, stays consistent with "derived, not manual") and log it to the audit
  trail as a visible signal, rather than letting it silently stay indexed with nothing to show.

## Out of scope for this phase

- Homepage CMS, Roles/Permissions, Optimization Inbox, API Cost Governance, Global
  Components live-site wiring — separate, already-identified gaps, not part of "Country."
- City's unified panel — next phase, same pattern, different field set (see prior discussion:
  `about_rosotravel`/`local_tips`/`top_pick_titles` instead of `facts`/`top_regions`/
  `top_cities`, and hero image is upload-only, no AI-generate button).

## Implementation shape

- New frontend route: `/admin/countries/[countrySlug]` (or a modal/drawer opened from a
  country list) — server component fetching the country's `AdminPublishingRow` + `PublishedRecord`
  + pending-queue entry (if any) in parallel, rendering all 6 sections above.
  - Uses **all existing** components as-is: `ContentLockForm`, `HeroImageForm`,
    `AdminAction` (for publish/promote/approve/reject), `MergeDestinationForm`.
- `/admin/destinations` and `/admin/content` stay as list/overview screens but their per-row
  actions link into the new unified detail screen instead of duplicating every action inline.
- One new backend change: the empty-country auto-noindex signal in `publish_country_page`.

## Verification approach

- Open the unified screen for a country with a pending Viator-synced duplicate → confirm
  Approve/Reject/Merge all work from this screen without switching tabs.
- Publish, then Promote a country from this screen → confirm `index_state` flips and is
  reflected immediately in the governance status section.
- Lock a field, regenerate it, accept the candidate, revert it → confirm all four actions and
  their resulting states are visible without leaving the screen.
- Generate a hero image, then upload an override → confirm both paths work and the governance
  section shows the correct `generator` (AI vs upload).
- Zero out every product under every city of a test country, republish → confirm the country
  auto-flips to `noindex` and an audit log entry records why.
