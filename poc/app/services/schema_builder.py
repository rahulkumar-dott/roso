from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Attraction, Destination, EnrichedFact, Product

BASE_URL = "https://www.rosotravel.com"


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts)


def canonical_url(entity_type: str, entity: Destination | Product | Attraction) -> str:
    if entity_type in {"destination", "city"}:
        country = slugify(entity.country)
        city = slugify(entity.city or entity.name)
        return f"{BASE_URL}/en/{country}/{city}/"
    if entity_type == "attraction":
        country = slugify(entity.country or "destination")
        city = slugify(entity.city or "city")
        return f"{BASE_URL}/en/{country}/{city}/attractions/{slugify(entity.name)}/"
    product = entity
    city = "city"
    country = "destination"
    return f"{BASE_URL}/en/{country}/{city}/tours/{slugify(product.name)}/"


def country_canonical_url(country: str) -> str:
    return f"{BASE_URL}/en/{slugify(country)}/"


def entity_type_for_schema(entity_type: str) -> str:
    if entity_type in {"destination", "city", "country"}:
        return "TouristDestination"
    if entity_type == "attraction":
        return "TouristAttraction"
    return "TouristTrip"


def factual_sources(db: Session, entity_id: str) -> list[EnrichedFact]:
    return list(db.scalars(select(EnrichedFact).where(EnrichedFact.entity_id == entity_id)).all())


def factual_keys(facts: list[EnrichedFact]) -> set[str]:
    keys: set[str] = set()
    for fact in facts:
        keys.update(fact.fields.keys())
    return keys


def build_schema(
    db: Session,
    *,
    entity_id: str,
    entity_type: str,
    entity: Destination | Product | Attraction,
    content: dict[str, Any],
    facts: dict[str, Any],
    model_c_snapshot: dict[str, Any] | None = None,
    existing_schema_id: str | None = None,
) -> dict[str, Any]:
    canonical = content["canonical_url"]
    entity_id_iri = existing_schema_id or f"{canonical}#entity-{entity_type}-{entity_id}"
    page_id = f"{canonical}#webpage"

    main_entity: dict[str, Any] = {
        "@type": entity_type_for_schema(entity_type),
        "@id": entity_id_iri,
        "identifier": entity_id,
        "name": content["h1"],
        "url": canonical,
    }

    if facts.get("lat") is not None and facts.get("lng") is not None:
        main_entity["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": facts["lat"],
            "longitude": facts["lng"],
        }
    if facts.get("formatted_address"):
        main_entity["address"] = facts["formatted_address"]
    if facts.get("opening_hours"):
        main_entity["openingHoursSpecification"] = facts["opening_hours"]
    if facts.get("phone"):
        main_entity["telephone"] = facts["phone"]
    if facts.get("sameAs"):
        main_entity["sameAs"] = facts["sameAs"]
    if facts.get("rating") is not None and facts.get("review_count") is not None:
        main_entity["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": facts["rating"],
            "reviewCount": facts["review_count"],
            "bestRating": 5,
            "worstRating": 1,
        }

    intermediate_crumbs: list[tuple[str, str | None]] = []
    if entity_type == "city" and isinstance(entity, Destination):
        if entity.country:
            intermediate_crumbs.append((entity.country, country_canonical_url(entity.country)))
        # Region is optional per the WBS ("{{Region}} (optional)") - only add
        # it when the destination actually carries a distinct region value;
        # our demo cities store region == country (no real region page in
        # this POC), so we skip rather than fabricate a region crumb/URL.
        if entity.region and entity.region.strip().lower() != (entity.country or "").strip().lower():
            intermediate_crumbs.append((entity.region, None))

    graph: list[dict[str, Any]] = [
        {
            "@type": "WebPage",
            "@id": page_id,
            "url": canonical,
            "inLanguage": "en",
            "name": content["h1"],
            "description": content["meta_description"],
            "mainEntity": {"@id": entity_id_iri},
            "breadcrumb": {"@id": f"{canonical}#breadcrumb"},
        },
        _breadcrumb(
            canonical,
            content["h1"],
            include_destinations_crumb=entity_type in {"country", "city"},
            intermediate_crumbs=intermediate_crumbs,
        ),
        main_entity,
    ]

    if entity_type in {"country", "city"}:
        graph.append(
            {
                "@type": "Organization",
                "@id": f"{BASE_URL}/#organization",
                "name": "Rosotravel",
                "url": f"{BASE_URL}/",
            }
        )

    if entity_type == "country":
        top_cities = content.get("top_cities") or []
        if top_cities:
            graph.append(
                {
                    "@type": "ItemList",
                    "@id": f"{canonical}#top-cities",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": index,
                            "name": city["name"],
                            "item": city["canonical_url"],
                        }
                        for index, city in enumerate(top_cities, start=1)
                    ],
                }
            )

    if content.get("faq"):
        graph.append(
            {
                "@type": "FAQPage",
                "@id": f"{canonical}#faq",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": item["question"],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": item["answer"],
                        },
                    }
                    for item in content["faq"]
                ],
            }
        )

    if model_c_snapshot and model_c_snapshot.get("picks"):
        graph.append(
            {
                "@type": "ItemList",
                "@id": f"{canonical}#model-c-picks",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": index,
                        "name": pick["title"],
                        "item": pick["product_id"],
                    }
                    for index, pick in enumerate(model_c_snapshot["picks"], start=1)
                ],
            }
        )

    return {"@context": "https://schema.org", "@graph": graph}


def _breadcrumb(
    canonical: str,
    name: str,
    *,
    include_destinations_crumb: bool = False,
    intermediate_crumbs: list[tuple[str, str | None]] | None = None,
) -> dict[str, Any]:
    """Home > Destinations > ... > {name}. `intermediate_crumbs` lets city
    pages insert Country (and, when a real one exists, Region) crumbs between
    Destinations and the current page - each is (label, url|None); url is
    omitted from the ListItem when there's no dedicated page to link to
    (e.g. no Region page exists in this POC) rather than fabricating one.
    """
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE_URL}/en/"}]
    if include_destinations_crumb:
        items.append(
            {"@type": "ListItem", "position": 2, "name": "Destinations", "item": f"{BASE_URL}/en/"}
        )
    for crumb_name, crumb_url in intermediate_crumbs or []:
        entry: dict[str, Any] = {
            "@type": "ListItem",
            "position": len(items) + 1,
            "name": crumb_name,
        }
        if crumb_url:
            entry["item"] = crumb_url
        items.append(entry)
    items.append(
        {"@type": "ListItem", "position": len(items) + 1, "name": name, "item": canonical}
    )
    return {
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": items,
    }


def validate(
    *,
    schema_json: dict[str, Any],
    content: dict[str, Any],
    facts: dict[str, Any],
    source_facts: list[EnrichedFact],
) -> list[str]:
    errors: list[str] = []
    required = {
        "h1": content.get("h1"),
        "meta_description": content.get("meta_description"),
        "canonical_url": content.get("canonical_url"),
    }
    for field, value in required.items():
        if not value:
            errors.append(f"{field} is required")

    if schema_json.get("@context") != "https://schema.org":
        errors.append("schema_json @context must be https://schema.org")
    graph = schema_json.get("@graph")
    if not isinstance(graph, list) or not graph:
        errors.append("schema_json @graph is required")
        return errors

    for node in graph:
        if not node.get("@type"):
            errors.append("every JSON-LD node requires @type")
        if not node.get("@id"):
            errors.append("every JSON-LD node requires @id")

    page = next((node for node in graph if node.get("@type") == "WebPage"), None)
    if page is None:
        errors.append("WebPage node is required")
    elif not page.get("mainEntity"):
        errors.append("WebPage mainEntity is required")

    keys = factual_keys(source_facts)
    trace_map = {
        "geo": {"lat", "lng"},
        "address": {"formatted_address"},
        "openingHoursSpecification": {"opening_hours"},
        "telephone": {"phone"},
        "sameAs": {"sameAs"},
    }
    entity = next(
        (
            node
            for node in graph
            if node.get("@type") in {"TouristDestination", "TouristAttraction", "TouristTrip"}
        ),
        {},
    )
    for schema_field, fact_fields in trace_map.items():
        if schema_field in entity and not fact_fields <= keys:
            errors.append(f"{schema_field} must trace back to EnrichedFact")

    if "aggregateRating" in entity and not {"rating", "review_count"} <= keys:
        errors.append("aggregateRating must trace back to EnrichedFact rating/review_count")

    return errors
