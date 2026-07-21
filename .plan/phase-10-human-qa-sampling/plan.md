# Phase 10 — Human QA Sampling (SOW 2.11)

## Context

Grounded in `Rosotravel_AI_SOW_v2.1_Final.pdf` §2.11:

> "3–5% of every batch is selected for manual review by an SEO specialist. Criteria: tone,
> factual accuracy, keyword usage, decision-platform content quality... style consistency, no
> misleading claims. If sample passes → full batch proceeds. If sample fails → prompts or
> keyword rules are adjusted and batch regenerates. Gate applies to every batch without
> exception."

Confirmed a "batch" = one city's worth of AI-drafted content, produced by one "Run AI Batch
Processing" run (WBS City_Page: *"Generated during the city-level 'Run AI Batch
Processing'"*). Acceptance criteria (SOW 9.2) frames it the same way: *"Human QA sample
passes on first review for at least one complete city batch."*

## Design decision (agreed)

Build this as a **new, additive action**, not a modification to the existing
`publish_city_page` endpoint's default behavior. Reasons: (1) nothing like a "pending" content
state exists yet in the POC, this is genuinely new; (2) forcing it onto every publish call by
default would silently break the seed scripts and the hero-image auto-generate-on-first-publish
logic built in Phase 9, which both assume publish is instant/synchronous. Same pattern already
used for the destination-creation deviation: add the doc-correct path alongside the existing
one, don't rip out something working.

## Backend

**New column**: `PublishedRecord.pending_batch: dict | None` (JSON), migrated via
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, matching every other schema addition this session.

Shape:
```json
{
  "content": { /* full freshly-computed content snapshot */ },
  "sampled_fields": ["overview", "faq"],
  "status": "pending_qa",
  "reviewed_by": null,
  "reviewed_at": null,
  "notes": null,
  "created_at": "..."
}
```

**`run_ai_batch(db, city_id, actor)`**
- Recomputes fresh content via `_city_content_snapshot` (same source as `publish_city_page`),
  but stores it in `pending_batch` instead of overwriting live `content`.
- Picks `max(1, round(0.04 * len(editable_fields)))` fields at random as the sample (4% midpoint
  of the 3–5% range; rounds up to at least 1 given how few fields a city has).
- Audit log `batch_run`.

**`review_qa_sample(db, city_id, decision, actor, notes=None)`**
- `decision == "pass"`: `pending_batch["content"]` becomes the live `content` (through the
  existing `_apply_content_locks` + schema rebuild path, same as `accept_candidate`), clears
  `pending_batch`, audit log `batch_pass`.
- `decision == "fail"`: discards `pending_batch`, audit log `batch_fail` with `notes` — city
  stays on its previous live content, matching "batch regenerates" (a human re-runs the batch
  after adjusting whatever needed fixing).

**Endpoints**
- `POST /cities/{city_id}/batch/run`
- `POST /cities/{city_id}/batch/review` (body: `decision`, `notes`)
- `pending_batch` included in `PublishOut` so the admin UI can render it.

## Frontend

New section on the City admin detail page (`/admin/cities/[cityId]`), between Publish and Hero
Image: **"Run AI Batch (Human QA Sampling)"**
- "Run AI Batch" button → calls `run_ai_batch`.
- If `pending_batch` exists: show the sampled fields (old value vs proposed new value),
  Pass / Fail buttons, optional notes field.
- Pass → batch content goes live, matches existing "accept candidate" visual pattern.
- Fail → pending batch cleared, city stays on its current content, failure reason logged.

## Out of scope for this phase

- Country-level batches — SOW only ever says "city batch," not country; leave country's
  existing instant-publish behavior untouched.
- Automatic prompt/rule adjustment on failure — the docs describe this as a human action
  ("prompts or keyword rules are adjusted"), not something to automate.
- Role-gating (SEO specialist only) — Roles/Permissions (Module 6) is still deferred entirely;
  the review action stays open to anyone who can reach `/admin`, same as everything else today.

## Verification approach

- Run a batch for a city with existing locked fields → confirm locked fields are excluded from
  the freshly-computed pending content (same lock-respecting behavior as regular publish).
- Pass a batch → confirm live content updates and `pending_batch` clears.
- Fail a batch → confirm live content is untouched and the failure is visible in the audit log.
- Confirm `publish_city_page` (the existing endpoint) behaves exactly as before — unaffected by
  this addition.
