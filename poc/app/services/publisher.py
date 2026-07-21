import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Attraction,
    Destination,
    DraftedContent,
    Product,
    PublishedRecord,
    RawVersion,
)
from app.services import audit, drafting, image_gen, model_c, schema_builder
from app.services.enrichment import find_entity, get_facts


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _latest_validated_content(db: Session, entity_id: str) -> DraftedContent | None:
    return db.scalar(
        select(DraftedContent)
        .where(DraftedContent.entity_id == entity_id, DraftedContent.status == "validated")
        .order_by(DraftedContent.version.desc(), DraftedContent.created_at.desc())
        .limit(1)
    )


def _primary_image(payload: dict[str, Any]) -> str | None:
    images = payload.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        return str(first) if first else None
    return None


def _content_snapshot(db: Session, content: DraftedContent, canonical_url: str) -> dict[str, Any]:
    variants = [
        {"audience": item["audience"], "snippet_text": item["snippet_text"]}
        for item in _variants(db, content.id)
    ]
    raw = _latest_raw_payload(db, content.entity_id)
    images = raw.get("images") if isinstance(raw.get("images"), list) else []
    return {
        "h1": content.h1,
        "meta_title": content.meta_title,
        "meta_description": content.meta_description,
        "canonical_url": canonical_url,
        "images": images,
        "primary_image": _primary_image(raw),
        "price_from": raw.get("price"),
        "currency": raw.get("currency"),
        "highlights": content.highlights,
        "body": content.body,
        "faq": content.faq,
        "variants": variants,
        "draft_version": content.version,
        "similarity": content.similarity,
    }


def _variants(db: Session, drafted_content_id: int) -> list[dict[str, str]]:
    from app.models.entities import AudienceVariant

    rows = db.scalars(
        select(AudienceVariant).where(AudienceVariant.drafted_content_id == drafted_content_id)
    ).all()
    return [{"audience": row.audience, "snippet_text": row.snippet_text} for row in rows]


def _model_c_snapshot(
    db: Session,
    entity_type: str,
    entity: Destination | Product | Attraction,
) -> dict[str, Any] | None:
    if entity_type == "destination":
        return model_c.city_picks(db, entity.entity_id)
    if entity_type == "product" and entity.destination_entity_id:
        return model_c.explain_product(db, entity.entity_id)
    return None


def _record_out(record: PublishedRecord) -> dict[str, Any]:
    return {
        "entity_id": record.entity_id,
        "entity_type": record.entity_type,
        "canonical_url": record.canonical_url,
        "schema_json": record.schema_json,
        "content": record.content,
        "date_published": record.date_published.isoformat(),
        "date_modified": record.date_modified.isoformat(),
        "version": record.version,
        "status": record.status,
        "index_state": _effective_index_state(record),
        "content_locks": record.content_locks or {},
        "content_candidates": record.content_candidates or {},
        "pending_batch": record.pending_batch,
    }


def _is_country_promoted(record: PublishedRecord) -> bool:
    return bool(record.entity_type == "country" and (record.content or {}).get("country_index_promoted") is True)


def _effective_index_state(record: PublishedRecord) -> str:
    if record.entity_type == "country" and not _is_country_promoted(record):
        return "noindex"
    return record.index_state


def _apply_content_locks(content: dict[str, Any], existing: PublishedRecord | None) -> dict[str, Any]:
    if not existing or not existing.content_locks:
        return content
    merged = dict(content)
    for field, meta in existing.content_locks.items():
        if isinstance(meta, dict) and meta.get("locked") and field in existing.content:
            merged[field] = existing.content[field]
    return merged


def _latest_raw_payload(db: Session, entity_id: str) -> dict[str, Any]:
    row = db.scalar(
        select(RawVersion)
        .where(RawVersion.entity_id == entity_id)
        .order_by(RawVersion.version_number.desc())
        .limit(1)
    )
    return row.payload if row else {}


def _fit_text(text: str, minimum: int, maximum: int) -> str:
    if len(text) > maximum:
        return text[: maximum - 1].rstrip() + "."
    while len(text) < minimum:
        text += " for confident Rosotravel planning"
    return text[:maximum].rstrip()


_TRAVEL_TYPE_LABELS: list[tuple[tuple[str, ...], str]] = [
    (("food", "wine", "tasting", "culinary"), "food & culture"),
    (("skip", "ticket", "pass", "landmark"), "top attractions"),
    (("private",), "private touring"),
    (("small group", "small-group"), "small-group touring"),
    (("transfer",), "smooth arrivals & transfers"),
    (("walk", "highlights", "tour", "sightseeing"), "history & culture"),
]


def _city_travel_type_phrase(db: Session, destination: Destination) -> str:
    """Heuristic 'dominant type of travel' for the H1 pattern
    ("Visit {City} - Your starting point for [type of travel]"). Derived
    deterministically from the city's own product data (its highest
    review_count product's title / category) rather than invented, since the
    WBS explicitly calls for the phrase to come from "dominant city type".
    """
    products = list(
        db.scalars(select(Product).where(Product.destination_entity_id == destination.entity_id)).all()
    )
    if not products:
        return "sightseeing & culture"

    def _score(product: Product) -> tuple[float, float]:
        payload = _latest_raw_payload(db, product.entity_id)
        return (float(payload.get("review_count") or 0), float(payload.get("rating") or 0))

    best = max(products, key=_score)
    payload = _latest_raw_payload(db, best.entity_id)
    title = (payload.get("title") or best.name or "").lower()
    for keywords, label in _TRAVEL_TYPE_LABELS:
        if any(keyword in title for keyword in keywords):
            return label
    return "sightseeing & culture"


def _city_structural_facts(db: Session, country: str) -> dict[str, Any]:
    """Real, non-invented country-level facts (currency/calling code/language)
    that a city inherits from its parent COUNTRY-level Destination row - same
    Viator raw payload source `_country_facts` uses, reused for city FAQs and
    local tips so we never fabricate city-level specifics we don't have.
    """
    country_row = db.scalar(
        select(Destination)
        .where(Destination.country.ilike(country), Destination.destination_level == "COUNTRY")
        .limit(1)
    )
    if country_row is None:
        return {}
    raw = _latest_raw_payload(db, country_row.entity_id).get("raw_viator") or {}
    return {
        "currency": raw.get("defaultCurrencyCode"),
        "calling_code": raw.get("countryCallingCode"),
        "languages": raw.get("languages"),
        "timezone": raw.get("timeZone"),
    }


def _city_food_pick_title(picks: dict[str, Any]) -> str | None:
    for pick in picks.get("picks", []):
        title = pick.get("title") or ""
        if any(word in title.lower() for word in ("food", "wine", "tasting", "culinary")):
            return title
    return None


def _city_faq(
    city_name: str,
    country_name: str,
    facts: dict[str, Any],
    food_pick_title: str | None,
) -> list[dict[str, str]]:
    """Exactly 9 city-level informational FAQs per the WBS City_Page sheet
    ("FAQ Block - Exactly 9"). Topics mirror the WBS's own examples (transport,
    best time, safety, local customs, food, getting around, day trips,
    language, budget). Uses real country-level facts (currency/language) and a
    real Model C pick where we have one; stays generic elsewhere instead of
    inventing city-specific claims (prices, named neighborhoods, etc).
    """
    currency = facts.get("currency")
    languages = facts.get("languages")
    return [
        {
            "question": f"How do I get to {city_name}?",
            "answer": (
                f"{city_name} is typically reached by regional flight, train, or road connections into "
                f"{country_name} - check current schedules from your starting point before booking tours."
            ),
        },
        {
            "question": f"How do I get around {city_name} once I've arrived?",
            "answer": "Rosotravel tours list a meeting point and any included transport in each listing, alongside standard local public transport and walking options.",
        },
        {
            "question": f"When is the best time to visit {city_name}?",
            "answer": f"The best time depends on the season you're targeting - check current travel advisories and typical local weather patterns for {country_name} before you go.",
        },
        {
            "question": f"Is {city_name} safe for tourists?",
            "answer": "Follow standard travel-safety precautions and check current official travel advisories before your trip.",
        },
        {
            "question": f"What local customs should I know before visiting {city_name}?",
            "answer": "Local etiquette varies by neighborhood and venue - our guided tours include practical context on customs so you don't have to guess.",
        },
        {
            "question": f"What food should I try in {city_name}?",
            "answer": (
                f"Rosotravel's \"{food_pick_title}\" is a curated way to sample well-reviewed local food and drink in {city_name} without needing prior research."
                if food_pick_title
                else f"Guided food and tasting experiences are a practical way to sample well-reviewed local spots in {city_name} without needing prior research."
            ),
        },
        {
            "question": f"Are day trips possible from {city_name}?",
            "answer": f"Day-trip feasibility depends on regional transport links from {city_name} - check current schedules, or look for a guided day tour if one is published for this city.",
        },
        {
            "question": f"What language is spoken in {city_name}?",
            "answer": (
                f"The primary language(s) in {country_name} are {', '.join(languages)}."
                if languages
                else f"Check current guidance for the primary language(s) spoken in {country_name}."
            ),
        },
        {
            "question": f"How much should I budget for tours in {city_name}?",
            "answer": (
                f"Tour prices in {city_name} are typically listed in {currency} - check each listing's runtime price for exact figures."
                if currency
                else f"Check each tour listing in {city_name} for its exact runtime price and currency."
            ),
        },
    ]


def _city_local_tips(city_name: str, country_name: str) -> list[str]:
    """3-5 short (160-260 char) Local Tips per the WBS, covering transport,
    safety, seasonality, etiquette, and money. Kept city-agnostic in the
    specific claims (no invented prices or safety statistics) while still
    naming the city so the tip reads as city-relevant, per the operational
    guidance not to fabricate unverifiable specifics.
    """
    raw_tips = [
        (
            f"Getting around {city_name}: check each Rosotravel tour listing for its exact meeting point and "
            "included transport, and confirm local public-transport options for the rest of your visit."
        ),
        (
            f"Safety in {city_name}: use standard travel-safety precautions, keep valuables secure in busy or "
            "crowded areas, and check current official government travel advisories before and during your trip."
        ),
        (
            f"Best time to visit {city_name}: consider the season you're targeting, since weather and crowd levels "
            f"in {country_name} can shift trip pacing - plan tour timings with some flexibility."
        ),
        (
            f"Local etiquette in {city_name}: dress codes and customs can vary by venue, especially at religious or "
            "historic sites - guided tours typically flag this in advance so you're not caught off guard."
        ),
        (
            f"Money in {city_name}: confirm which payment methods each venue accepts and what tipping is typical "
            "locally, since both vary by venue type and are rarely printed clearly anywhere for visitors."
        ),
    ]
    return [_fit_text(tip, 160, 260) for tip in raw_tips]


def _city_about_rosotravel(
    city_name: str,
    country_name: str,
    travel_type: str,
    highlights: list[str],
) -> str:
    """"About Rosotravel in {City}" per the WBS - a distinct brand-expertise
    section (kept concise for this POC rather than padded to the full
    350-700 word spec), separate from the Overview so the page doesn't repeat
    itself. Built from the same governed inputs (travel-type heuristic, drafted
    highlights) but framed around Rosotravel's role rather than the city.
    """
    highlight_line = f" Recent curated picks include {highlights[0].lower()}." if highlights else ""
    return (
        f"In {city_name}, Rosotravel's role is to turn a large, noisy supply of {country_name} tours and tickets "
        f"into a short, decision-ready list built around {travel_type}. Rather than listing every available "
        f"product, we apply the same Pool -> Set -> Winner selection used across every Rosotravel city page, so "
        f"the {city_name} picks you see are Set-confirmed and materially different from one another instead of "
        f"near-duplicates.{highlight_line} We don't operate every tour in {city_name} directly and we don't claim "
        f"a local office here - our job is the curation and decision layer on top of vetted supply, so you spend "
        f"less time comparing near-identical listings and more time deciding what actually fits your trip."
    )


def _city_content_snapshot(
    db: Session,
    destination: Destination,
    canonical: str,
    existing_content: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    city_name = destination.city or destination.name
    country_name = destination.country
    raw = _latest_raw_payload(db, destination.entity_id)
    picks = model_c.city_picks(db, destination.entity_id)
    pick_titles = [pick["title"] for pick in picks.get("picks", [])]
    description = raw.get("description") or f"Plan {city_name} with Rosotravel's curated decision system."
    travel_type = _city_travel_type_phrase(db, destination)
    facts = _city_structural_facts(db, country_name)

    # AI-drafted overview/highlights per WBS ("Generated during the city-level
    # 'Run AI Batch Processing'"), reusing the same generic draft_entity()
    # pipeline as countries/products against the city-level Destination row.
    # Falls back to a plain template if the city hasn't been enriched/drafted
    # yet - same fallback pattern as `_country_content_snapshot`.
    draft = drafting.latest_content(db, destination.entity_id)
    default_highlights = [
        "Decision-first city planning hub",
        "Curated top picks from Model C",
        "Controlled exploration instead of raw catalog overload",
    ]
    default_overview = (
        f"{city_name} is published as a decision-first Rosotravel city hub. {description} "
        "The page combines city context, governed shortlist logic, and structured next steps."
    )
    overview = draft.body if draft and draft.body else default_overview
    highlights = draft.highlights if draft and draft.highlights else default_highlights

    content = {
        "h1": f"Visit {city_name} – Your starting point for {travel_type}",
        "meta_title": _fit_text(f"Visit {city_name}: {travel_type} with Rosotravel", 60, 75),
        "meta_description": _fit_text(
            f"Plan {city_name} with curated Rosotravel picks, decision proof, practical city context, and clear next steps for confident travel booking.",
            140,
            160,
        ),
        "canonical_url": canonical,
        # Explicit name/country fields so consumers (e.g. the frontend's
        # destination tree) don't have to parse them back out of h1/body text.
        "city_name": city_name,
        "country_name": country_name,
        "country_slug": schema_builder.slugify(country_name),
        "overview": overview,
        "highlights": highlights,
        "body": (
            f"{city_name} is published as a decision-first Rosotravel city hub. {description} "
            "The page combines city context, governed shortlist logic, and structured next steps."
        ),
        "about_rosotravel": _city_about_rosotravel(
            city_name,
            country_name,
            travel_type,
            draft.highlights if draft and draft.highlights else [],
        ),
        "local_tips": _city_local_tips(city_name, country_name),
        "faq": _city_faq(city_name, country_name, facts, _city_food_pick_title(picks)),
        "model_c": picks,
        "top_pick_titles": pick_titles,
        # WBS City_Page: hero image source is "CMS media for the city" - a
        # real uploaded photo, never AI-generated. Carried forward the same
        # way as the country hero image, never recomputed by this snapshot.
        "hero_image": (existing_content or {}).get("hero_image"),
        "page_type": "city",
    }
    return content, picks


def destination_activation_error(db: Session, destination: Destination) -> str | None:
    """SOW System 1.1 activation gate: 'a destination becomes active once at
    least one product is linked to it', plus Module 2's added human-approval
    requirement. A destination is publishable only once BOTH conditions hold.

    Pre-existing/internal/demo-seeded destinations were migrated (or default)
    to review_status='approved', so this only blocks newly Viator-synced
    destinations that haven't been approved yet, or approved destinations
    with zero linked products - it does not retroactively break already
    -published demo city/country pages.
    """
    review_status = getattr(destination, "review_status", "approved") or "approved"
    if review_status != "approved":
        return (
            f"Destination '{destination.entity_id}' is not approved for publishing "
            f"(review_status='{review_status}')"
        )
    products_count = db.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.destination_entity_id == destination.entity_id)
    )
    if not products_count:
        return f"Destination '{destination.entity_id}' has no linked products and cannot be published"
    return None


def _country_destinations(db: Session, country: str) -> list[Destination]:
    return list(
        db.scalars(
            select(Destination)
            .where(Destination.country.ilike(country))
            .order_by(Destination.name.asc())
        ).all()
    )


CITY_LEVELS = {"CITY", "TOWN", "VILLAGE"}


def _country_facts(db: Session, destinations: list[Destination]) -> list[str]:
    """Real, non-AI-invented facts sourced from the Viator COUNTRY-level row's
    raw payload (currency, languages, calling code, timezone) plus resolved
    Wikidata facts (inception year, sameAs) - per the WBS's 'Facts &
    Curiosities must tie to a factual source, no hallucination' rule.
    """
    country_row = next((d for d in destinations if d.destination_level == "COUNTRY"), None)
    if country_row is None:
        return []
    raw = _latest_raw_payload(db, country_row.entity_id).get("raw_viator") or {}
    facts = []
    if raw.get("defaultCurrencyCode"):
        facts.append(f"Local currency: {raw['defaultCurrencyCode']}")
    if raw.get("countryCallingCode"):
        facts.append(f"International calling code: {raw['countryCallingCode']}")
    if raw.get("languages"):
        facts.append(f"Primary language(s): {', '.join(raw['languages'])}")
    if raw.get("timeZone"):
        facts.append(f"Time zone: {raw['timeZone']}")

    facts_payload = get_facts(db, country_row.entity_id)
    resolved = facts_payload["resolved_fields"] if facts_payload else {}
    if resolved.get("inception_year"):
        facts.append(f"Modern state established: {resolved['inception_year']} (per Wikidata)")
    if resolved.get("sameAs"):
        same_as = resolved["sameAs"]
        link = same_as[0] if isinstance(same_as, list) and same_as else same_as
        if link:
            facts.append(f"Reference: {link}")
    return facts


def _ranked_top_cities(content: dict[str, Any]) -> list[dict[str, str]]:
    """Cities ranked by real Model C pick_count (curated-winning product
    count per city) instead of the plain alphabetical `top_cities` list -
    used to select which cities' attractions ground the hero image prompt.
    Falls back to the alphabetical list if the country rollup is suppressed
    (e.g. no Set-confirmed products anywhere in the country yet).
    """
    name_by_id = {c["entity_id"]: c["name"] for c in content.get("top_cities") or []}
    ranked_ids = [c["city_id"] for c in (content.get("model_c") or {}).get("top_cities") or []]
    ranked = [{"entity_id": cid, "name": name_by_id[cid]} for cid in ranked_ids if cid in name_by_id]
    return ranked or (content.get("top_cities") or [])


def _top_attraction_names(db: Session, city_entity_ids: list[str], limit: int = 5) -> list[str]:
    """Real Viator-sourced attraction names for a handful of a country's top
    cities - used to ground the AI hero image prompt in concrete, real
    landmarks instead of leaving it to the model's own guess from the country
    name alone (no doc requirement either way, our own engineering choice).
    """
    if not city_entity_ids:
        return []
    rows = db.scalars(
        select(Attraction)
        .where(Attraction.destination_entity_id.in_(city_entity_ids[:3]))
        .order_by(Attraction.review_count.desc().nullslast(), Attraction.rating.desc().nullslast())
        .limit(limit)
    ).all()
    return [row.name for row in rows]


def _country_faq(country: str, facts_by_label: dict[str, str]) -> list[dict[str, str]]:
    """Exactly 7 fixed-topic FAQs per WBS Country_Page sheet. Uses real data
    where we have it (currency/calling code from Viator); stays generic and
    non-committal elsewhere rather than inventing specifics like visa rules.
    """
    currency = facts_by_label.get("currency")
    calling_code = facts_by_label.get("calling_code")
    return [
        {
            "question": f"Do I need a visa to visit {country}?",
            "answer": "Visa requirements depend on your nationality - check official government or embassy guidance before booking.",
        },
        {
            "question": f"What currency is used in {country}?",
            "answer": f"The local currency is {currency}." if currency else f"Check current guidance for the local currency used in {country}.",
        },
        {
            "question": f"Is {country} safe for tourists?",
            "answer": "Follow standard travel-safety precautions and check current official travel advisories before your trip.",
        },
        {
            "question": f"Is tipping expected in {country}?",
            "answer": "Tipping customs vary by region and service type - check local guidance for what's typical.",
        },
        {
            "question": f"How do I get around in {country}?",
            "answer": "Rosotravel tours typically include transport details in each listing, plus local public transport and transfer options.",
        },
        {
            "question": f"When is the best time to visit {country}?",
            "answer": "This depends on the specific region and season you're targeting - check each city page for local context.",
        },
        {
            "question": f"What cultural norms should I know before visiting {country}?",
            "answer": "Local customs vary by region - our guided tours include practical context on etiquette and cultural norms.",
        },
    ]


def _country_content_snapshot(
    db: Session,
    country: str,
    canonical: str,
    existing_content: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    destinations = _country_destinations(db, country)
    # Module 2 activation gate, applied to which cities surface on the country
    # page: only approved + product-linked destinations are eligible. Existing
    # demo cities pass this already (review_status='approved' by default plus
    # linked products), so this doesn't change today's published country pages.
    cities = [
        d
        for d in destinations
        if d.destination_level in CITY_LEVELS and destination_activation_error(db, d) is None
    ]
    regions = [d for d in destinations if d.destination_level == "REGION"]
    rollup = model_c.country_rollup(db, country)
    facts = _country_facts(db, destinations)
    country_row = next((d for d in destinations if d.destination_level == "COUNTRY"), None)
    raw = _latest_raw_payload(db, country_row.entity_id).get("raw_viator") if country_row else {}
    raw = raw or {}
    facts_by_label = {
        "currency": raw.get("defaultCurrencyCode"),
        "calling_code": raw.get("countryCallingCode"),
    }

    # AI-drafted overview/highlights per WBS ("Ownership: AI-drafted +
    # human-editable"), reusing the same generic draft_entity() pipeline as
    # products/cities against the country-level Destination row. Falls back
    # to a plain template if the country hasn't been enriched/drafted yet.
    draft = drafting.latest_content(db, country_row.entity_id) if country_row else None
    default_body = (
        f"{country} is published as a Rosotravel country discovery page. "
        "It routes travelers into the right city hubs and curated decision surfaces instead of raw listing pages."
    )
    default_highlights = [
        "Curated tours across the country's top cities",
        "Decision-first city hubs instead of raw catalog browsing",
        "Structured routes into city and product pages",
    ]
    overview = draft.body if draft and draft.body else default_body
    highlights = draft.highlights if draft and draft.highlights else default_highlights

    content = {
        "h1": f"Discover {country}",
        "meta_title": _fit_text(f"Discover {country}: tours, cities, and curated travel planning", 60, 75),
        "meta_description": _fit_text(
            f"Explore {country} with Rosotravel city hubs, curated tour picks, country-level travel context, and structured planning guidance.",
            140,
            160,
        ),
        "canonical_url": canonical,
        "country_name": country,
        "country_slug": schema_builder.slugify(country),
        "overview": overview,
        "highlights": highlights,
        "facts": facts,
        "body": default_body,
        "faq": _country_faq(country, facts_by_label),
        "model_c": rollup,
        "top_cities": [
            {
                "entity_id": dest.entity_id,
                "name": dest.city or dest.name,
                "canonical_url": schema_builder.canonical_url("city", dest),
            }
            for dest in cities[:12]
        ],
        "top_regions": [
            {
                "entity_id": dest.entity_id,
                "name": dest.name,
            }
            for dest in regions[:12]
        ],
        "top_city_names": [dest.city or dest.name for dest in cities[:6]],
        # WBS: "no curated image exists for countries" -> Nano Banana Pro
        # generated. Never regenerated as a side effect of a cheap snapshot
        # rebuild (every content edit republishes) - only carried forward
        # from whatever was last generated/accepted. See regenerate_hero_image().
        "hero_image": (existing_content or {}).get("hero_image"),
        "page_type": "country",
    }
    return content, rollup


def _upsert_published_record(
    db: Session,
    *,
    entity_id: str,
    entity_type: str,
    canonical: str,
    schema_json: dict[str, Any],
    content: dict[str, Any],
    version: int = 1,
    force_noindex_reason: str | None = None,
) -> PublishedRecord:
    existing = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    now = _utcnow()
    if existing is None:
        # Country pages are a WBS "Lite Page": noindex,follow until a human
        # manually promotes them (see promote_country_page below). No other
        # entity type has this gate - they publish straight to indexed.
        initial_index_state = "noindex" if entity_type == "country" else "indexed"
        record = PublishedRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_url=canonical,
            schema_json=schema_json,
            content=content,
            date_published=now,
            date_modified=now,
            version=version,
            status="published",
            index_state=initial_index_state,
        )
        db.add(record)
    else:
        record = existing
        record.entity_type = entity_type
        record.canonical_url = canonical
        locked_content = _apply_content_locks(content, existing)
        if entity_type == "country" and not _is_country_promoted(existing):
            record.index_state = "noindex"
        # Not a documented rule - inferred to stay consistent with the
        # existing "index_state is derived, never manual" pattern: a country
        # that has zero active cities (all gated out by
        # destination_activation_error) shouldn't stay indexed with an empty
        # city list. Only fires on a transition from indexed -> noindex, so
        # it's visible as a real demotion, not silent.
        if entity_type == "country" and force_noindex_reason and record.index_state == "indexed":
            record.index_state = "noindex"
            audit.log(
                db,
                action="auto_noindex",
                entity_id=entity_id,
                field="index_state",
                before="indexed",
                after=f"noindex ({force_noindex_reason})",
                actor="system_auto_publish",
            )
        record.schema_json = schema_json
        record.content = locked_content
        record.date_modified = now
        record.version = version
        record.status = "published"
        # index_state is intentionally left untouched on republish - promotion
        # is a one-time manual gate, not something content edits should reset.
    db.commit()
    return record


def publish_entity(db: Session, entity_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    found = find_entity(db, entity_id)
    if found is None:
        return None, [f"Entity '{entity_id}' not found"]
    entity_type, entity = found

    draft = _latest_validated_content(db, entity_id)
    if draft is None:
        return None, ["validated drafted content is required"]

    existing = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    canonical = schema_builder.canonical_url(entity_type, entity)
    facts_payload = get_facts(db, entity_id)
    facts = facts_payload["resolved_fields"] if facts_payload else {}
    source_facts = schema_builder.factual_sources(db, entity_id)
    model_snapshot = _model_c_snapshot(db, entity_type, entity)
    content = _content_snapshot(db, draft, canonical)
    if model_snapshot:
        content["model_c"] = model_snapshot
    content = _apply_content_locks(content, existing)

    existing_schema_id = None
    if existing:
        for node in existing.schema_json.get("@graph", []):
            if node.get("@type") in {"TouristDestination", "TouristAttraction", "TouristTrip"}:
                existing_schema_id = node.get("@id")
                break

    schema_json = schema_builder.build_schema(
        db,
        entity_id=entity_id,
        entity_type=entity_type,
        entity=entity,
        content=content,
        facts=facts,
        model_c_snapshot=model_snapshot if isinstance(model_snapshot, dict) else None,
        existing_schema_id=existing_schema_id,
    )
    errors = schema_builder.validate(
        schema_json=schema_json,
        content=content,
        facts=facts,
        source_facts=source_facts,
    )
    if errors:
        return None, errors

    now = _utcnow()
    if existing is None:
        record = PublishedRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_url=canonical,
            schema_json=schema_json,
            content=content,
            date_published=now,
            date_modified=now,
            version=draft.version,
            status="published",
        )
        db.add(record)
    else:
        record = existing
        record.entity_type = entity_type
        record.canonical_url = canonical
        record.schema_json = schema_json
        record.content = content
        record.date_modified = now
        record.version = draft.version
        record.status = "published"

    db.commit()
    return _record_out(record), []


def publish_city_page(db: Session, city_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    destination = db.scalar(select(Destination).where(Destination.entity_id == city_id))
    if destination is None:
        return None, [f"City destination '{city_id}' not found"]

    gate_error = destination_activation_error(db, destination)
    if gate_error:
        return None, [gate_error]

    canonical = schema_builder.canonical_url("city", destination)
    existing = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == city_id))
    content, model_snapshot = _city_content_snapshot(
        db, destination, canonical, existing_content=existing.content if existing else None
    )
    facts_payload = get_facts(db, city_id)
    facts = facts_payload["resolved_fields"] if facts_payload else {}
    source_facts = schema_builder.factual_sources(db, city_id)
    content = _apply_content_locks(content, existing)
    existing_schema_id = _existing_schema_entity_id(existing)
    schema_json = schema_builder.build_schema(
        db,
        entity_id=city_id,
        entity_type="city",
        entity=destination,
        content=content,
        facts=facts,
        model_c_snapshot=model_snapshot,
        existing_schema_id=existing_schema_id,
    )
    errors = schema_builder.validate(
        schema_json=schema_json,
        content=content,
        facts=facts,
        source_facts=source_facts,
    )
    if errors:
        return None, errors
    version = _latest_raw_payload(db, city_id).get("version_number") or 1
    record = _upsert_published_record(
        db,
        entity_id=city_id,
        entity_type="city",
        canonical=canonical,
        schema_json=schema_json,
        content=content,
        version=version,
    )
    return _record_out(record), []


def run_ai_batch(db: Session, city_id: str, actor: str = "admin_poc") -> tuple[dict[str, Any] | None, list[str]]:
    """SOW 2.11 + 2.10 ("template-sameness across batch", "batch held/batch
    regenerates") plus the "Core AI Batch Processing Concept" scope doc: a
    batch is a GROUP OF RECORD PAGES processed together for one city -
    Products (and Attractions/Near-pages, once those exist as their own page
    types) - explicitly NOT the city/destination page itself. That scope doc
    is explicit: "Pipeline View is NOT... a destination manager" and the two
    views (batch pipeline vs. destination content editing) "must never
    overlap in responsibility." The city page already has its own separate
    governance (lock/regenerate-as-candidate/revert on ContentLockForm) - this
    batch only covers the city's products. Additive: does not touch
    publish_city_page's existing instant-publish behavior.
    """
    destination = db.scalar(select(Destination).where(Destination.entity_id == city_id))
    if destination is None:
        return None, [f"City destination '{city_id}' not found"]

    gate_error = destination_activation_error(db, destination)
    if gate_error:
        return None, [gate_error]

    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == city_id))
    if record is None:
        return None, ["City must be published at least once before running a batch"]

    products = list(
        db.scalars(select(Product).where(Product.destination_entity_id == city_id)).all()
    )
    if not products:
        return None, [f"'{city_id}' has no products to batch (Pipeline View batches are records - Products/Attractions/Near-pages - not the destination page itself)"]

    batch_pages: list[dict[str, Any]] = [
        {"entity_id": product.entity_id, "page_type": "product", "name": product.name} for product in products
    ]

    # Every product in the batch needs a current AI draft to be reviewable
    # (no-op if a valid draft for the current version already exists).
    for product in products:
        drafting.draft_entity(db, product.entity_id)

    sample_size = max(1, round(0.04 * len(batch_pages)))
    sampled_pages = random.sample(batch_pages, min(sample_size, len(batch_pages)))
    sampled_entity_ids = sorted(p["entity_id"] for p in sampled_pages)

    record.pending_batch = {
        "pages": batch_pages,
        "sampled_entity_ids": sampled_entity_ids,
        "status": "pending_qa",
        "reviewed_by": None,
        "reviewed_at": None,
        "notes": None,
        "created_at": _utcnow().isoformat(),
    }
    audit.log(
        db,
        action="batch_run",
        entity_id=city_id,
        field=None,
        before=None,
        after={
            "batch_pages": [p["entity_id"] for p in batch_pages],
            "sampled": sampled_entity_ids,
        },
        actor=actor,
    )
    db.commit()
    return _record_out(record), []


def review_qa_sample(
    db: Session,
    city_id: str,
    decision: str,
    actor: str = "admin_poc",
    notes: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if decision not in ("pass", "fail"):
        return None, ["decision must be 'pass' or 'fail'"]

    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == city_id))
    if record is None:
        return None, [f"Published record '{city_id}' not found"]
    if not record.pending_batch:
        return None, [f"No pending batch for '{city_id}'"]

    pending = record.pending_batch
    pages = pending.get("pages", [])

    if decision == "fail":
        audit.log(
            db,
            action="batch_fail",
            entity_id=city_id,
            field=None,
            before=None,
            after=notes,
            actor=actor,
        )
        record.pending_batch = None
        db.commit()
        return _record_out(record), []

    # decision == "pass": publish every product page in the batch together,
    # reusing the existing, already-tested publish_entity() directly rather
    # than replaying a stored content snapshot. Products with no MAJOR diff
    # pending have nothing new to publish (the Diff Engine's hard rule: only
    # MAJOR triggers drafting) - skip those rather than failing the whole
    # batch over a page that hasn't changed.
    errors: list[str] = []
    for page in pages:
        if _latest_validated_content(db, page["entity_id"]) is not None:
            _, page_errors = publish_entity(db, page["entity_id"])
            if page_errors:
                errors.append(f"{page['entity_id']}: {'; '.join(page_errors)}")
    if errors:
        return None, errors

    audit.log(
        db,
        action="batch_pass",
        entity_id=city_id,
        field=None,
        before=None,
        after={"published_pages": [p["entity_id"] for p in pages]},
        actor=actor,
    )
    record.pending_batch = None
    db.commit()
    return _record_out(record), []


def publish_country_page(db: Session, country: str) -> tuple[dict[str, Any] | None, list[str]]:
    destinations = _country_destinations(db, country)
    if not destinations:
        return None, [f"Country '{country}' has no stored destinations"]

    normalized_country = destinations[0].country
    entity_id = f"country_{schema_builder.slugify(normalized_country)}"
    canonical = schema_builder.country_canonical_url(normalized_country)
    existing = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    content, model_snapshot = _country_content_snapshot(
        db, normalized_country, canonical, existing_content=existing.content if existing else None
    )
    if content.get("hero_image") is None:
        # WBS: hero image ownership is "AI + manual", same as h1/overview -
        # auto-generate once on first publish, same as every other AI field.
        # Never regenerated automatically again after that (see
        # _country_content_snapshot's carry-forward comment) - only via the
        # explicit admin "Regenerate hero image" action from here on.
        ranked_cities = _ranked_top_cities(content)
        top_city_names = [c["name"] for c in ranked_cities]
        top_city_ids = [c["entity_id"] for c in ranked_cities]
        top_attraction_names = _top_attraction_names(db, top_city_ids)
        asset, error = image_gen.generate_country_hero_image(
            normalized_country, top_cities=top_city_names, top_attractions=top_attraction_names
        )
        if asset:
            content["hero_image"] = asset
            audit.log(
                db,
                action="regenerate",
                entity_id=entity_id,
                field="hero_image",
                before=None,
                after=asset,
                actor="system_auto_publish",
            )
        elif error:
            # Publish must not fail just because the hero image couldn't be
            # made (e.g. not configured, transient API error) - but the
            # failure still needs to be visible somewhere, or an admin has no
            # way to know a country is silently missing its hero image.
            audit.log(
                db,
                action="regenerate_failed",
                entity_id=entity_id,
                field="hero_image",
                before=None,
                after=error,
                actor="system_auto_publish",
            )
    content = _apply_content_locks(content, existing)
    schema_json = schema_builder.build_schema(
        db,
        entity_id=entity_id,
        entity_type="country",
        entity=destinations[0],
        content=content,
        facts={},
        model_c_snapshot=model_snapshot,
        existing_schema_id=_existing_schema_entity_id(
            existing
        ),
    )
    errors = schema_builder.validate(
        schema_json=schema_json,
        content=content,
        facts={},
        source_facts=[],
    )
    if errors:
        return None, errors
    empty_country_reason = (
        "zero active cities" if not content.get("top_cities") else None
    )
    record = _upsert_published_record(
        db,
        entity_id=entity_id,
        entity_type="country",
        canonical=canonical,
        schema_json=schema_json,
        content=content,
        version=1,
        force_noindex_reason=empty_country_reason,
    )
    return _record_out(record), []


def promote_country_page(db: Session, country: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Manual promotion gate per WBS: a country page starts noindex,follow
    and only becomes indexable once a human explicitly promotes it here.
    """
    entity_id = f"country_{schema_builder.slugify(country)}"
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Country '{country}' has not been published yet"]
    if record.entity_type != "country":
        return None, [f"'{entity_id}' is not a country page"]
    content = dict(record.content or {})
    content["country_index_promoted"] = True
    record.content = content
    record.index_state = "indexed"
    audit.log(
        db,
        action="country_promote",
        entity_id=entity_id,
        before={"index_state": "noindex"},
        after={"index_state": "indexed"},
    )
    db.commit()
    return _record_out(record), []


def _schema_context_for_record(
    db: Session, record: PublishedRecord
) -> tuple[Any | None, dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    if record.entity_type == "country":
        country = record.content.get("country_name") or record.entity_id.removeprefix("country_").replace("-", " ")
        destinations = _country_destinations(db, country)
        return (destinations[0] if destinations else None), {}, [], record.content.get("model_c")

    found = find_entity(db, record.entity_id)
    if found is None:
        return None, {}, [], None
    _, entity = found
    facts_payload = get_facts(db, record.entity_id)
    facts = facts_payload["resolved_fields"] if facts_payload else {}
    source_facts = schema_builder.factual_sources(db, record.entity_id)
    model_snapshot = record.content.get("model_c")
    return entity, facts, source_facts, model_snapshot if isinstance(model_snapshot, dict) else None


def edit_published_content(
    db: Session,
    entity_id: str,
    updates: dict[str, Any],
    lock_fields: list[str],
    unlock_fields: list[str],
    edited_by: str | None = "admin",
) -> tuple[dict[str, Any] | None, list[str]]:
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]

    content = dict(record.content or {})
    locks = dict(record.content_locks or {})
    allowed_fields = {
        "h1",
        "meta_title",
        "meta_description",
        "overview",
        "body",
        "about_rosotravel",
        "highlights",
        "facts",
        "faq",
        "local_tips",
        "top_city_names",
        "top_pick_titles",
        "top_regions",
        "top_cities",
        "hero_image",
    }
    unknown_fields = sorted(set(updates) - allowed_fields)
    if unknown_fields:
        return None, [f"Unsupported content fields: {', '.join(unknown_fields)}"]

    now = _utcnow()
    for field, value in updates.items():
        before_value = content.get(field)
        content[field] = value
        locks[field] = {
            "locked": True,
            "edited_by": edited_by or "admin",
            "locked_at": now.isoformat(),
            "reason": "manual_cms_edit",
        }
        audit.log(
            db,
            action="content_lock",
            entity_id=entity_id,
            field=field,
            before=before_value,
            after=value,
            actor=edited_by or "admin",
        )
    for field in lock_fields:
        if field in content:
            locks[field] = {
                "locked": True,
                "edited_by": edited_by or "admin",
                "locked_at": now.isoformat(),
                "reason": "manual_lock",
            }
            audit.log(
                db,
                action="content_lock",
                entity_id=entity_id,
                field=field,
                before=content.get(field),
                after=content.get(field),
                actor=edited_by or "admin",
            )
    for field in unlock_fields:
        if locks.pop(field, None) is not None:
            audit.log(
                db,
                action="content_unlock",
                entity_id=entity_id,
                field=field,
                before=content.get(field),
                after=content.get(field),
                actor=edited_by or "admin",
            )

    entity, facts, source_facts, model_snapshot = _schema_context_for_record(db, record)
    if entity is not None:
        schema_json = schema_builder.build_schema(
            db,
            entity_id=record.entity_id,
            entity_type=record.entity_type,
            entity=entity,
            content=content,
            facts=facts,
            model_c_snapshot=model_snapshot,
            existing_schema_id=_existing_schema_entity_id(record),
        )
        errors = schema_builder.validate(
            schema_json=schema_json,
            content=content,
            facts=facts,
            source_facts=source_facts,
        )
        if errors:
            return None, errors
        record.schema_json = schema_json

    record.content = content
    record.content_locks = locks
    record.date_modified = now
    db.commit()
    return _record_out(record), []


def _fresh_content_for_record(db: Session, record: PublishedRecord) -> dict[str, Any] | None:
    """Recompute this record's full content snapshot from current source data,
    ignoring any existing content_locks - i.e. what the AI pipeline would
    produce right now if nothing were locked. This is the single definition
    of "latest AI-generated version" shared by both regenerate-as-candidate
    and revert, so the two actions can't drift out of sync with each other.
    """
    if record.entity_type == "country":
        country_name = record.content.get("country_name") or record.entity_id.removeprefix(
            "country_"
        ).replace("-", " ")
        destinations = _country_destinations(db, country_name)
        if not destinations:
            return None
        content, _ = _country_content_snapshot(
            db, destinations[0].country, record.canonical_url, existing_content=record.content
        )
        return content
    if record.entity_type == "city":
        destination = db.scalar(select(Destination).where(Destination.entity_id == record.entity_id))
        if destination is None:
            return None
        content, _ = _city_content_snapshot(
            db, destination, record.canonical_url, existing_content=record.content
        )
        return content

    # product / attraction / destination-node entity types published via
    # publish_entity() - freshest content is the latest validated draft.
    draft = _latest_validated_content(db, record.entity_id)
    if draft is None:
        return None
    content = _content_snapshot(db, draft, record.canonical_url)
    found = find_entity(db, record.entity_id)
    if found is not None:
        entity_type, entity = found
        model_snapshot = _model_c_snapshot(db, entity_type, entity)
        if model_snapshot:
            content["model_c"] = model_snapshot
    return content


def _revalidate_and_save(
    db: Session,
    record: PublishedRecord,
    content: dict[str, Any],
    locks: dict[str, Any],
) -> list[str]:
    """Shared schema rebuild/validate/save step used by accept_candidate and
    revert_field (edit_published_content keeps its own inline copy to avoid
    touching well-covered existing behavior)."""
    entity, facts, source_facts, model_snapshot = _schema_context_for_record(db, record)
    if entity is not None:
        schema_json = schema_builder.build_schema(
            db,
            entity_id=record.entity_id,
            entity_type=record.entity_type,
            entity=entity,
            content=content,
            facts=facts,
            model_c_snapshot=model_snapshot,
            existing_schema_id=_existing_schema_entity_id(record),
        )
        errors = schema_builder.validate(
            schema_json=schema_json,
            content=content,
            facts=facts,
            source_facts=source_facts,
        )
        if errors:
            return errors
        record.schema_json = schema_json
    record.content = content
    record.content_locks = locks
    record.date_modified = _utcnow()
    return []


def regenerate_field(
    db: Session,
    entity_id: str,
    field: str,
    actor: str = "admin_poc",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Module 1: a regenerate trigger produces a new AI draft stored as a
    CANDIDATE - it never overwrites the live content[field], locked or not.
    """
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]

    fresh = _fresh_content_for_record(db, record)
    if fresh is None or field not in fresh:
        return None, [f"Cannot regenerate field '{field}' for '{entity_id}'"]

    candidates = dict(record.content_candidates or {})
    candidates[field] = {"value": fresh[field], "generated_at": _utcnow().isoformat()}
    record.content_candidates = candidates
    audit.log(
        db,
        action="regenerate",
        entity_id=entity_id,
        field=field,
        before=(record.content or {}).get(field),
        after=fresh[field],
        actor=actor,
    )
    db.commit()
    return _record_out(record), []


def regenerate_hero_image(
    db: Session,
    entity_id: str,
    actor: str = "admin_poc",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Country-only. Unlike regenerate_field, this can't be produced by the
    cheap _fresh_content_for_record recompute - it's a real Nano Banana Pro
    call (WBS: "no curated image exists for countries"). Stored as a
    candidate through the same content_candidates mechanism as every other
    field, so accept_candidate/reject_candidate already work on it unchanged.
    """
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]
    if record.entity_type != "country":
        return None, ["Hero image generation is only defined for country pages (WBS Country_Page spec)"]

    country_name = record.content.get("country_name") or entity_id.removeprefix("country_").replace("-", " ")
    ranked_cities = _ranked_top_cities(record.content)
    top_city_names = [c["name"] for c in ranked_cities]
    top_city_ids = [c["entity_id"] for c in ranked_cities]
    top_attraction_names = _top_attraction_names(db, top_city_ids)
    asset, error = image_gen.generate_country_hero_image(
        country_name, top_cities=top_city_names, top_attractions=top_attraction_names
    )
    if error:
        return None, [error]

    candidates = dict(record.content_candidates or {})
    candidates["hero_image"] = {"value": asset, "generated_at": asset["generated_at"]}
    record.content_candidates = candidates
    audit.log(
        db,
        action="regenerate",
        entity_id=entity_id,
        field="hero_image",
        before=(record.content or {}).get("hero_image"),
        after=asset,
        actor=actor,
    )
    db.commit()
    return _record_out(record), []


def upload_hero_image(
    db: Session,
    entity_id: str,
    file_bytes: bytes,
    content_type: str,
    actor: str = "admin_poc",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Country or city. WBS City_Page: hero image source is "CMS media for
    the city" - a real photo, never AI-generated - so city can only ever get
    a hero image through this path. Country can also use this as a manual
    override of the Nano-Banana output. Sets the value and locks it directly
    (no candidate/accept step) - a human explicitly chose this file, there's
    no AI draft to review against.
    """
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]
    if record.entity_type not in ("country", "city"):
        return None, ["Hero image upload is only defined for country and city pages"]

    entity_name = (
        record.content.get("city_name")
        or record.content.get("country_name")
        or entity_id
    )
    asset, error = image_gen.save_uploaded_hero_image(entity_name, file_bytes, content_type)
    if error:
        return None, [error]

    return edit_published_content(
        db,
        entity_id,
        updates={"hero_image": asset},
        lock_fields=[],
        unlock_fields=[],
        edited_by=actor,
    )


def accept_candidate(
    db: Session,
    entity_id: str,
    field: str,
    actor: str = "admin_poc",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Module 1: moves a staged candidate into the live content[field]."""
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]

    candidates = dict(record.content_candidates or {})
    candidate = candidates.get(field)
    if candidate is None:
        return None, [f"No pending candidate for field '{field}' on '{entity_id}'"]

    content = dict(record.content or {})
    before_value = content.get(field)
    content[field] = candidate["value"]

    errors = _revalidate_and_save(db, record, content, dict(record.content_locks or {}))
    if errors:
        return None, errors

    candidates.pop(field, None)
    record.content_candidates = candidates
    audit.log(
        db,
        action="candidate_accept",
        entity_id=entity_id,
        field=field,
        before=before_value,
        after=candidate["value"],
        actor=actor,
    )
    db.commit()
    return _record_out(record), []


def reject_candidate(
    db: Session,
    entity_id: str,
    field: str,
    actor: str = "admin_poc",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Module 1: discards a staged candidate without touching live content."""
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]

    candidates = dict(record.content_candidates or {})
    if field not in candidates:
        return None, [f"No pending candidate for field '{field}' on '{entity_id}'"]

    discarded = candidates.pop(field)
    record.content_candidates = candidates
    audit.log(
        db,
        action="candidate_reject",
        entity_id=entity_id,
        field=field,
        before=discarded.get("value"),
        after=None,
        actor=actor,
    )
    db.commit()
    return _record_out(record), []


def revert_field(
    db: Session,
    entity_id: str,
    field: str,
    actor: str = "admin_poc",
) -> tuple[dict[str, Any] | None, list[str]]:
    """Module 1: restores a locked field to the most recent underlying
    AI-generated version and clears the manual lock - distinct from a plain
    unlock, which leaves the value untouched.
    """
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    if record is None:
        return None, [f"Published record '{entity_id}' not found"]

    locks = dict(record.content_locks or {})
    if not (isinstance(locks.get(field), dict) and locks[field].get("locked")):
        return None, [f"Field '{field}' is not currently locked; nothing to revert"]

    fresh = _fresh_content_for_record(db, record)
    if fresh is None or field not in fresh:
        return None, [f"Cannot revert field '{field}' for '{entity_id}'"]

    content = dict(record.content or {})
    before_value = content.get(field)
    content[field] = fresh[field]
    locks.pop(field, None)

    errors = _revalidate_and_save(db, record, content, locks)
    if errors:
        return None, errors

    candidates = dict(record.content_candidates or {})
    candidates.pop(field, None)
    record.content_candidates = candidates
    audit.log(
        db,
        action="revert",
        entity_id=entity_id,
        field=field,
        before=before_value,
        after=fresh[field],
        actor=actor,
    )
    db.commit()
    return _record_out(record), []


def _existing_schema_entity_id(existing: PublishedRecord | None) -> str | None:
    if not existing:
        return None
    for node in existing.schema_json.get("@graph", []):
        if node.get("@type") in {"TouristDestination", "TouristAttraction", "TouristTrip"}:
            return node.get("@id")
    return None


def get_published(db: Session, entity_id: str) -> dict[str, Any] | None:
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))
    return _record_out(record) if record else None


def list_published(db: Session, limit: int = 50, offset: int = 0) -> dict[str, list[dict[str, Any]]]:
    records = db.scalars(
        select(PublishedRecord)
        .order_by(PublishedRecord.date_modified.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {"records": [_record_out(record) for record in records]}


def destinations_tree(db: Session) -> dict[str, Any]:
    """Every published country with its published cities, driven entirely by
    what's actually in PublishedRecord - so publishing a new country/city
    makes it appear here automatically, with no frontend code change needed.
    """
    country_records = list(
        db.scalars(select(PublishedRecord).where(PublishedRecord.entity_type == "country")).all()
    )
    countries = []
    for record in sorted(country_records, key=lambda r: r.content.get("country_name") or r.entity_id):
        content = record.content
        # top_cities can carry stale/duplicate entries from earlier testing
        # (same city name ingested under multiple entity_ids) - dedupe by
        # lowercased name, preferring a canonical demo_/dest_ id over any
        # leftover *_e2e_* test entity.
        seen_names: dict[str, dict[str, Any]] = {}
        for city in content.get("top_cities", []):
            key = (city.get("name") or "").strip().lower()
            if not key:
                continue
            existing = seen_names.get(key)
            if existing is None or ("_e2e_" in existing["entity_id"] and "_e2e_" not in city["entity_id"]):
                seen_names[key] = city

        countries.append(
            {
                "entity_id": record.entity_id,
                "name": content.get("country_name") or record.entity_id,
                "slug": content.get("country_slug") or record.entity_id.removeprefix("country_"),
                "canonical_url": record.canonical_url,
                "cities": sorted(seen_names.values(), key=lambda c: c["name"]),
            }
        )
    return {"countries": countries}
