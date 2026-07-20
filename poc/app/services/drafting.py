import json
import math
import re
import time
from collections import Counter
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import AudienceVariant, DiffResult, DraftedContent, EnrichedFact, RawVersion
from app.services.enrichment import compute_factual_hash, resolve_fields
from app.services.keyword_intel import get_keyword_intel
from app.services import vector_similarity

AUDIENCES = [
    "first_time_visitor",
    "family_traveler",
    "couple_traveler",
    "comfort_easy_pace_traveler",
    "solo_social_traveler",
    "interest_deep_dive_traveler",
    "active_adventure_traveler",
]


def _latest_raw_version(db: Session, entity_id: str) -> RawVersion | None:
    return db.scalar(
        select(RawVersion)
        .where(RawVersion.entity_id == entity_id)
        .order_by(RawVersion.version_number.desc())
        .limit(1)
    )


def _latest_diff(db: Session, entity_id: str) -> DiffResult | None:
    return db.scalar(
        select(DiffResult)
        .where(DiffResult.entity_id == entity_id)
        .order_by(DiffResult.to_version.desc())
        .limit(1)
    )


def _source_facts(db: Session, entity_id: str) -> list[EnrichedFact]:
    return list(db.scalars(select(EnrichedFact).where(EnrichedFact.entity_id == entity_id)).all())


def retrieve_context(db: Session, entity_id: str) -> dict[str, Any] | None:
    raw_version = _latest_raw_version(db, entity_id)
    if raw_version is None:
        return None

    facts = _source_facts(db, entity_id)
    resolved_facts = resolve_fields(facts)
    keyword_context = get_keyword_intel(db, entity_id)
    return {
        "entity_id": entity_id,
        "entity_type": raw_version.entity_type,
        "version": raw_version.version_number,
        "raw_payload": raw_version.payload,
        "keyword_intel": keyword_context,
        "resolved_facts": resolved_facts,
        "resolved_factual_hash": compute_factual_hash(resolved_facts),
        "source_facts": [
            {
                "source": fact.source,
                "fields": fact.fields,
                "factual_hash": fact.factual_hash,
                "is_stub": fact.is_stub,
            }
            for fact in facts
        ],
    }


class LLMAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def is_live(self) -> bool:
        return bool(self.settings.groq_api_key)

    def draft(self, context: dict[str, Any]) -> dict[str, Any]:
        if self.is_live:
            return self._normalize_draft(context, self._groq_draft(context))
        return self._stub_draft(context)

    def variants(self, context: dict[str, Any], draft: dict[str, Any]) -> list[dict[str, str]]:
        if self.is_live:
            live_variants = self._groq_variants(context, draft)
            return self._complete_variants(context, draft, live_variants)
        return self._stub_variants(context, draft)

    def _stub_draft(self, context: dict[str, Any]) -> dict[str, Any]:
        raw = context["raw_payload"]
        facts = context["resolved_facts"]
        name = raw.get("title") or raw.get("name") or context["entity_id"]
        # Every Destination row (country, region, city, town...) has name ==
        # the place's own name - never a product-style title distinct from
        # its city. That collapses the "{name} in {city}" pattern below into
        # "Italy in Italy" for a COUNTRY-level row, and equally into "Rome in
        # Rome" for a CITY-level row (its `city` field is also "Rome"). Both
        # get the "Discover {name}" pattern instead; only products/attractions
        # (where name is a distinct title) use "{name} in {city}".
        is_destination_level = context["entity_type"] == "destination"
        city = raw.get("city") or facts.get("city") or raw.get("country") or "the destination"
        if is_destination_level:
            city = name
        category = raw.get("category_group") or context["entity_type"]
        description = raw.get("description") or f"Plan a clear, well-paced visit to {name}."
        keyword_intel = context.get("keyword_intel") or {}
        keyword_rows = keyword_intel.get("keywords") or []
        top_keywords = [row.get("keyword") for row in keyword_rows[:3] if row.get("keyword")]
        highlights = raw.get("highlights") or self._fact_highlights(facts) or [
            f"See the key details for {name}",
            "Use verified factual context while planning",
            "Keep logistics clear before booking",
        ]
        h1 = f"Discover {name}" if is_destination_level else f"{name} in {city}"
        meta_title = self._fit_text(
            f"Discover {name}: trusted travel planning" if is_destination_level else f"{name}: trusted travel details for {city}",
            60,
            75,
        )
        meta_description = self._fit_text(
            f"Plan {name} with verified details, practical highlights, and clear context for a confident Rosotravel booking decision.",
            140,
            160,
        )
        body = (
            f"{name} brings together Rosotravel's curated tours and destinations. "
            if is_destination_level
            else f"{name} is part of Rosotravel's governed travel content set for {city}. "
        )
        body += (
            f"{description} "
            "The draft uses raw supplier context and factual enrichment as separate inputs, "
            "so operational details remain traceable to the factual layer."
        )
        if top_keywords:
            body += f" Search demand context includes: {', '.join(top_keywords)}."
        faq = self._faq_from_facts(name, facts)
        return {
            "h1": h1,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "highlights": highlights[:7],
            "body": body,
            "faq": faq,
        }

    def _groq_draft(self, context: dict[str, Any]) -> dict[str, Any]:
        payload = self._chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You draft governed Rosotravel travel content. Return only valid JSON. "
                        "Never invent factual values; use provided resolved_facts for facts."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Create JSON with keys h1, meta_title, meta_description, highlights, body, faq. "
                        "highlights must be an array of 3-7 strings. faq must be 5-10 objects with question and answer. "
                        "meta_title must target 60-75 chars and meta_description 140-160 chars.\n"
                        f"Context:\n{json.dumps(context, default=str)}"
                    ),
                },
            ],
            max_tokens=1400,
        )
        return self._extract_json(payload)

    def _stub_variants(self, context: dict[str, Any], draft: dict[str, Any]) -> list[dict[str, str]]:
        name = context["raw_payload"].get("title") or context["raw_payload"].get("name")
        templates = {
            "first_time_visitor": f"Start with {name} using clear logistics and verified essentials.",
            "family_traveler": f"Plan {name} with simple pacing, practical details, and fewer surprises.",
            "couple_traveler": f"Make {name} feel polished, relaxed, and easy to choose together.",
            "comfort_easy_pace_traveler": f"Enjoy {name} at a comfortable pace with the key facts upfront.",
            "solo_social_traveler": f"Use {name} as a confident solo plan with clear context and options.",
            "interest_deep_dive_traveler": f"Go deeper into {name} with factual context and focused highlights.",
            "active_adventure_traveler": f"Fit {name} into an active day with practical planning details.",
        }
        return [{"audience": audience, "snippet_text": templates[audience]} for audience in AUDIENCES]

    def _groq_variants(self, context: dict[str, Any], draft: dict[str, Any]) -> list[dict[str, str]]:
        payload = self._chat_completion(
            [
                {
                    "role": "system",
                    "content": "Return only valid JSON. Do not invent facts.",
                },
                {
                    "role": "user",
                    "content": (
                        "Create exactly 7 audience snippets as JSON array objects with audience and snippet_text. "
                        f"Audiences: {', '.join(AUDIENCES)}. Each snippet 180-260 characters.\n"
                        f"Context: {json.dumps(context, default=str)}\nDraft: {json.dumps(draft, default=str)}"
                    ),
                },
            ],
            max_tokens=1200,
        )
        parsed = self._extract_json(payload)
        if isinstance(parsed, dict):
            parsed = parsed.get("variants", [])
        return [
            {"audience": item["audience"], "snippet_text": item["snippet_text"]}
            for item in parsed
            if item.get("audience") in AUDIENCES and item.get("snippet_text")
        ]

    def _normalize_draft(self, context: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
        fallback = self._stub_draft(context)
        normalized = {**fallback, **(draft or {})}
        normalized["h1"] = str(normalized.get("h1") or fallback["h1"])
        normalized["meta_title"] = self._fit_text(
            str(normalized.get("meta_title") or fallback["meta_title"]),
            60,
            75,
        )
        normalized["meta_description"] = self._fit_text(
            str(normalized.get("meta_description") or fallback["meta_description"]),
            140,
            160,
        )
        highlights = normalized.get("highlights")
        if not isinstance(highlights, list) or not highlights:
            highlights = fallback["highlights"]
        normalized["highlights"] = [str(item) for item in highlights if item][:7]
        faq = normalized.get("faq")
        if not isinstance(faq, list) or not faq:
            faq = fallback["faq"]
        normalized["faq"] = [
            {
                "question": str(item.get("question") or item.get("q") or ""),
                "answer": str(item.get("answer") or item.get("a") or ""),
            }
            for item in faq
            if isinstance(item, dict)
        ][:10]
        if not normalized["faq"]:
            normalized["faq"] = fallback["faq"]
        normalized["body"] = str(normalized.get("body") or fallback["body"])
        return normalized

    def _complete_variants(
        self,
        context: dict[str, Any],
        draft: dict[str, Any],
        variants: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        by_audience = {
            item["audience"]: item
            for item in variants
            if item.get("audience") in AUDIENCES and item.get("snippet_text")
        }
        for fallback in self._stub_variants(context, draft):
            by_audience.setdefault(fallback["audience"], fallback)
        return [by_audience[audience] for audience in AUDIENCES]

    def _chat_completion(self, messages: list[dict[str, str]], max_tokens: int) -> str:
        assert self.settings.groq_api_key is not None
        with httpx.Client(timeout=45) as client:
            attempts = 0
            while True:
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.groq_model,
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": max_tokens,
                        "response_format": {"type": "json_object"},
                    },
                )
                # Batch-drafting many entities back-to-back can trip Groq's
                # per-minute token rate limit (429) well before any daily
                # request quota - back off and retry a few times rather than
                # failing the whole draft outright.
                if response.status_code == 429 and attempts < 3:
                    # Cap at 60s regardless of what Retry-After says - a quota
                    # reset window can be minutes/hours away, and blocking a
                    # request thread for that long is worse than just failing
                    # fast and letting the caller retry later.
                    retry_after = response.headers.get("retry-after")
                    wait_seconds = min(float(retry_after), 60.0) if retry_after else 20.0 * (attempts + 1)
                    time.sleep(wait_seconds)
                    attempts += 1
                    continue
                response.raise_for_status()
                break
            return response.json()["choices"][0]["message"]["content"]

    def _extract_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}|\[.*\]", text, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    def _fact_highlights(self, facts: dict[str, Any]) -> list[str]:
        highlights = []
        if facts.get("formatted_address"):
            highlights.append(f"Address: {facts['formatted_address']}")
        if facts.get("opening_hours"):
            highlights.append("Opening hours available from the factual layer")
        if facts.get("official_website"):
            highlights.append("Official website captured for verification")
        if facts.get("sameAs"):
            highlights.append("Linked to external sameAs identifiers")
        return highlights

    def _faq_from_facts(self, name: str, facts: dict[str, Any]) -> list[dict[str, str]]:
        faq = [
            {
                "question": f"What should I know before visiting {name}?",
                "answer": f"Check the latest factual details for {name}, including address, hours, and official links where available.",
            }
        ]
        if facts.get("opening_hours"):
            faq.append(
                {
                    "question": f"What are the opening hours for {name}?",
                    "answer": "Opening hours are available in the factual layer and should be checked before publishing.",
                }
            )
        if facts.get("formatted_address"):
            faq.append(
                {
                    "question": f"Where is {name} located?",
                    "answer": f"The stored address is {facts['formatted_address']}.",
                }
            )
        faq.extend(
            [
                {
                    "question": f"Is {name} suitable for a first visit?",
                    "answer": "This draft is designed to help travelers make a clear first-pass decision.",
                },
                {
                    "question": f"Does Rosotravel invent facts about {name}?",
                    "answer": "No. Factual values must come from the governed factual layer or approved manual overrides.",
                },
            ]
        )
        return faq[:10]

    def _fit_text(self, text: str, minimum: int, maximum: int) -> str:
        if len(text) > maximum:
            return text[: maximum - 1].rstrip() + "."
        if len(text) >= minimum:
            return text
        suffix = " for confident planning"
        while len(text) < minimum:
            text += suffix
        return text[:maximum].rstrip()


def validate_draft(draft: dict[str, Any]) -> list[str]:
    errors = []
    for field in ["h1", "meta_title", "meta_description", "body"]:
        if not draft.get(field):
            errors.append(f"{field} is required")
    if not draft.get("highlights"):
        errors.append("highlights are required")
    if not draft.get("faq"):
        errors.append("faq is required")
    meta_title = draft.get("meta_title") or ""
    if meta_title and not 60 <= len(meta_title) <= 75:
        errors.append("meta_title must be 60-75 characters")
    meta_description = draft.get("meta_description") or ""
    if meta_description and not 140 <= len(meta_description) <= 160:
        errors.append("meta_description must be 140-160 characters")
    return errors


def _tokens(text: str) -> Counter[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return Counter(word for word in words if len(word) > 2)


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    common = set(a) & set(b)
    numerator = sum(a[word] * b[word] for word in common)
    a_norm = math.sqrt(sum(value * value for value in a.values()))
    b_norm = math.sqrt(sum(value * value for value in b.values()))
    if not a_norm or not b_norm:
        return 0.0
    return numerator / (a_norm * b_norm)


def similarity_band(score: float) -> str:
    if score >= 0.92:
        return "DUPLICATE"
    if score >= 0.78:
        return "VARIANT"
    if score >= 0.62:
        return "BORDERLINE"
    return "NEW_TOPIC"


def compute_similarity(db: Session, entity_id: str, body: str | None = None) -> dict[str, Any]:
    if body is None:
        latest = latest_content(db, entity_id)
        body = latest.body if latest else ""
    vector_result = vector_similarity.nearest_by_pgvector(db, entity_id, body or "")
    if vector_result is not None:
        return {
            **vector_result,
            "band": similarity_band(vector_result["score"]),
        }
    candidate = _tokens(body or "")
    nearest_entity_id = None
    score = 0.0
    drafts = db.scalars(select(DraftedContent).where(DraftedContent.entity_id != entity_id)).all()
    for draft in drafts:
        draft_score = _cosine(candidate, _tokens(draft.body))
        if draft_score > score:
            score = draft_score
            nearest_entity_id = draft.entity_id
    return {
        "entity_id": entity_id,
        "band": similarity_band(score),
        "score": round(score, 4),
        "nearest_entity_id": nearest_entity_id,
        "method": "tfidf_fallback",
    }


def latest_content(db: Session, entity_id: str) -> DraftedContent | None:
    return db.scalar(
        select(DraftedContent)
        .where(DraftedContent.entity_id == entity_id)
        .order_by(DraftedContent.version.desc(), DraftedContent.created_at.desc())
        .limit(1)
    )


def _content_out(db: Session, content: DraftedContent) -> dict[str, Any]:
    variants = db.scalars(
        select(AudienceVariant)
        .where(AudienceVariant.drafted_content_id == content.id)
        .order_by(AudienceVariant.audience.asc())
    ).all()
    return {
        "entity_id": content.entity_id,
        "version": content.version,
        "h1": content.h1,
        "meta_title": content.meta_title,
        "meta_description": content.meta_description,
        "highlights": content.highlights,
        "body": content.body,
        "faq": content.faq,
        "status": content.status,
        "validation_errors": content.validation_errors,
        "similarity": content.similarity,
        "created_at": content.created_at.isoformat(),
        "variants": [
            {"audience": variant.audience, "snippet_text": variant.snippet_text}
            for variant in variants
        ],
    }


def draft_entity(
    db: Session,
    entity_id: str,
    *,
    llm: LLMAdapter | None = None,
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    context = retrieve_context(db, entity_id)
    if context is None:
        return None, 404, f"Entity '{entity_id}' has no raw version"

    latest_diff = _latest_diff(db, entity_id)
    if latest_diff is None or latest_diff.severity != "MAJOR":
        return None, 409, "Latest diff is not MAJOR; AI drafting is skipped by policy"

    existing = db.scalar(
        select(DraftedContent).where(
            DraftedContent.entity_id == entity_id,
            DraftedContent.version == context["version"],
        )
    )
    if existing is not None:
        return _content_out(db, existing), None, None

    adapter = llm or LLMAdapter()
    draft = adapter.draft(context)
    errors = validate_draft(draft)
    status = "failed" if errors else "validated"
    similarity = compute_similarity(db, entity_id, draft.get("body", ""))

    content = DraftedContent(
        entity_id=entity_id,
        version=context["version"],
        h1=draft.get("h1") or "",
        meta_title=draft.get("meta_title") or "",
        meta_description=draft.get("meta_description") or "",
        highlights=draft.get("highlights") or [],
        body=draft.get("body") or "",
        faq=draft.get("faq") or [],
        status=status,
        validation_errors=errors,
        similarity=similarity,
    )
    db.add(content)
    db.flush()

    for variant in adapter.variants(context, draft)[: len(AUDIENCES)]:
        db.add(
            AudienceVariant(
                drafted_content_id=content.id,
                audience=variant["audience"],
                snippet_text=variant["snippet_text"],
            )
        )
    db.commit()
    vector_similarity.upsert_content_vector(db, content)
    db.commit()
    return _content_out(db, content), None, None


def get_content(db: Session, entity_id: str) -> dict[str, Any] | None:
    content = latest_content(db, entity_id)
    if content is None:
        return None
    return _content_out(db, content)
