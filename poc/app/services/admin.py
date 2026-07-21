from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Attraction,
    AudienceVariant,
    AuditLog,
    Destination,
    DiffResult,
    DraftedContent,
    PoolMembership,
    Product,
    ProductQualityScore,
    PublishedRecord,
    RawVersion,
    SetMembership,
    SiteConfig,
)
from app.services import audit, ingestion, model_c, schema_builder

CITY_LEVELS = {"CITY", "TOWN", "VILLAGE"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clean_name(value: str) -> str:
    return " ".join(value.strip().split())


def _effective_index_state(record: PublishedRecord | None) -> str | None:
    if record is None:
        return None
    if record.entity_type == "country" and not (record.content or {}).get("country_index_promoted"):
        return "noindex"
    return record.index_state


def _latest_raw(db: Session, entity_id: str) -> RawVersion | None:
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


def _latest_draft(db: Session, entity_id: str) -> DraftedContent | None:
    return db.scalar(
        select(DraftedContent)
        .where(DraftedContent.entity_id == entity_id)
        .order_by(DraftedContent.version.desc(), DraftedContent.created_at.desc())
        .limit(1)
    )


def _published(db: Session, entity_id: str) -> PublishedRecord | None:
    return db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == entity_id))


def _raw_payload(db: Session, entity_id: str) -> dict[str, Any]:
    raw = _latest_raw(db, entity_id)
    return raw.payload if raw else {}


def _product_row(db: Session, product: Product) -> dict[str, Any]:
    payload = _raw_payload(db, product.entity_id)
    destination = (
        db.scalar(select(Destination).where(Destination.entity_id == product.destination_entity_id))
        if product.destination_entity_id
        else None
    )
    quality = db.scalar(
        select(ProductQualityScore).where(ProductQualityScore.product_id == product.entity_id)
    )
    pool = db.scalar(select(PoolMembership).where(PoolMembership.product_id == product.entity_id))
    set_row = db.scalar(select(SetMembership).where(SetMembership.product_id == product.entity_id))
    draft = _latest_draft(db, product.entity_id)
    published = _published(db, product.entity_id)
    diff = _latest_diff(db, product.entity_id)
    images = payload.get("images") if isinstance(payload.get("images"), list) else []
    return {
        "entity_id": product.entity_id,
        "name": payload.get("title") or product.name,
        "city_id": product.destination_entity_id,
        "city": destination.city or destination.name if destination else None,
        "country": destination.country if destination else None,
        "category_group": product.category_group,
        "image_url": images[0] if images else None,
        "price_from": payload.get("price"),
        "currency": payload.get("currency"),
        "quality_score": quality.quality_score if quality else None,
        "completeness_score": quality.completeness_score if quality else None,
        "in_pool": bool(pool and pool.in_pool),
        "pool_reasons": pool.reasons if pool else [],
        "in_set": bool(set_row and set_row.in_set),
        "latest_severity": diff.severity if diff else None,
        "draft_status": draft.status if draft else None,
        "draft_errors": draft.validation_errors if draft else [],
        "similarity": draft.similarity if draft else None,
        "published": bool(published and published.status == "published"),
        "canonical_url": published.canonical_url if published else None,
        "explain": model_c.explain_product(db, product.entity_id),
    }


def overview(db: Session) -> dict[str, Any]:
    return {
        "destinations": db.scalar(select(func.count()).select_from(Destination)) or 0,
        "products": db.scalar(select(func.count()).select_from(Product)) or 0,
        "published_records": db.scalar(select(func.count()).select_from(PublishedRecord)) or 0,
        "drafts_validated": db.scalar(
            select(func.count()).select_from(DraftedContent).where(DraftedContent.status == "validated")
        )
        or 0,
        "drafts_failed": db.scalar(
            select(func.count()).select_from(DraftedContent).where(DraftedContent.status == "failed")
        )
        or 0,
        "pool_products": db.scalar(
            select(func.count()).select_from(PoolMembership).where(PoolMembership.in_pool == True)  # noqa: E712
        )
        or 0,
        "set_products": db.scalar(
            select(func.count()).select_from(SetMembership).where(SetMembership.in_set == True)  # noqa: E712
        )
        or 0,
    }


def destinations(db: Session) -> dict[str, Any]:
    rows = db.scalars(select(Destination).order_by(Destination.country.asc(), Destination.name.asc())).all()
    countries: dict[str, dict[str, Any]] = {}
    for destination in rows:
        published_country = _published(db, f"country_{schema_builder.slugify(destination.country)}")
        country = countries.setdefault(
            destination.country,
            {
                "country": destination.country,
                "entity_id": f"country_{schema_builder.slugify(destination.country)}",
                "published": bool(published_country),
                "index_state": _effective_index_state(published_country),
                "has_country_node": False,
                "source": destination.source,
                "regions": [],
                "cities": [],
            },
        )
        if destination.destination_level == "COUNTRY":
            country["has_country_node"] = True
            country["source"] = destination.source
            continue
        if destination.destination_level == "REGION":
            country["regions"].append(
                {
                    "entity_id": destination.entity_id,
                    "name": destination.region or destination.name,
                    "country": destination.country,
                    "published": bool(_published(db, destination.entity_id)),
                    "source": destination.source,
                }
            )
            continue
        if destination.destination_level not in CITY_LEVELS:
            continue
        products_count = db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.destination_entity_id == destination.entity_id)
        )
        attractions_count = db.scalar(
            select(func.count())
            .select_from(Attraction)
            .where(Attraction.destination_entity_id == destination.entity_id)
        )
        city_picks = model_c.city_picks(db, destination.entity_id)
        country["cities"].append(
            {
                "entity_id": destination.entity_id,
                "name": destination.city or destination.name,
                "country": destination.country,
                "region": destination.region,
                "published": bool(_published(db, destination.entity_id)),
                "products_count": products_count or 0,
                "attractions_count": attractions_count or 0,
                "picks_count": len(city_picks.get("picks", [])),
                "suppressed": city_picks.get("suppressed", True),
                "source": destination.source,
            }
        )
    return {"countries": list(countries.values())}


def create_country(db: Session, name: str, region: str | None = None, description: str | None = None, images: list[str] | None = None) -> dict[str, Any]:
    country_name = _clean_name(name)
    if not country_name:
        return {"errors": ["Country name is required"]}

    existing_country_node = db.scalar(
        select(Destination).where(
            Destination.destination_level == "COUNTRY",
            Destination.country.ilike(country_name),
        )
    )
    if existing_country_node:
        return {
            "errors": [f"Country '{country_name}' already has a country taxonomy node"],
            "entity_id": existing_country_node.entity_id,
        }

    payload = {
        "entity_id": f"dest_country_{schema_builder.slugify(country_name)}",
        "name": country_name,
        "country": country_name,
        "region": region,
        "city": None,
        "destination_level": "COUNTRY",
        "source": "internal",
        "description": description or f"{country_name} country taxonomy node.",
        "images": images or [],
    }
    result = ingestion.ingest_destination(db, payload)
    return {"errors": [], **result}


def create_region(db: Session, country: str, name: str, description: str | None = None, images: list[str] | None = None) -> dict[str, Any]:
    country_name = _clean_name(country)
    region_name = _clean_name(name)
    if not country_name or not region_name:
        return {"errors": ["Country and region name are required"]}

    entity_id = f"dest_region_{schema_builder.slugify(country_name)}_{schema_builder.slugify(region_name)}"
    if db.scalar(select(Destination).where(Destination.entity_id == entity_id)):
        return {"errors": [f"Region '{region_name}' already exists in {country_name}"], "entity_id": entity_id}

    result = ingestion.ingest_destination(
        db,
        {
            "entity_id": entity_id,
            "name": region_name,
            "country": country_name,
            "region": region_name,
            "city": None,
            "destination_level": "REGION",
            "source": "internal",
            "description": description or f"{region_name} region taxonomy node in {country_name}.",
            "images": images or [],
        },
    )
    return {"errors": [], **result}


def create_city(
    db: Session,
    country: str,
    name: str,
    region: str | None = None,
    description: str | None = None,
    images: list[str] | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    country_name = _clean_name(country)
    city_name = _clean_name(name)
    region_name = _clean_name(region) if region else None
    if not country_name or not city_name:
        return {"errors": ["Country and city name are required"]}

    entity_id = f"dest_city_{schema_builder.slugify(country_name)}_{schema_builder.slugify(city_name)}"
    if db.scalar(select(Destination).where(Destination.entity_id == entity_id)):
        return {"errors": [f"City '{city_name}' already exists in {country_name}"], "entity_id": entity_id}

    result = ingestion.ingest_destination(
        db,
        {
            "entity_id": entity_id,
            "name": city_name,
            "country": country_name,
            "region": region_name,
            "city": city_name,
            "destination_level": "CITY",
            "source": "internal",
            "description": description or f"{city_name} city taxonomy node in {country_name}.",
            "images": images or [],
            "lat": lat,
            "lng": lng,
        },
    )
    return {"errors": [], **result}


def create_attraction(
    db: Session,
    name: str,
    destination_entity_id: str | None = None,
    country: str | None = None,
    city: str | None = None,
    description: str | None = None,
    official_website: str | None = None,
    images: list[str] | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    attraction_name = _clean_name(name)
    if not attraction_name:
        return {"errors": ["Attraction name is required"]}

    destination = (
        db.scalar(select(Destination).where(Destination.entity_id == destination_entity_id))
        if destination_entity_id
        else None
    )
    if destination_entity_id and destination is None:
        return {"errors": [f"City destination '{destination_entity_id}' was not found"]}

    country_value = country or (destination.country if destination else "")
    city_value = city or (destination.city or destination.name if destination else "")
    country_name = _clean_name(country_value)
    city_name = _clean_name(city_value)
    if not country_name:
        return {"errors": ["Country is required when no city destination is selected"]}

    entity_id_parts = [
        "attr_internal",
        schema_builder.slugify(country_name),
        schema_builder.slugify(city_name) if city_name else "country",
        schema_builder.slugify(attraction_name),
    ]
    entity_id = "_".join(entity_id_parts)
    if db.scalar(select(Attraction).where(Attraction.entity_id == entity_id)):
        return {"errors": [f"Attraction '{attraction_name}' already exists"], "entity_id": entity_id}

    result = ingestion.ingest_attraction(
        db,
        {
            "entity_id": entity_id,
            "destination_entity_id": destination.entity_id if destination else None,
            "name": attraction_name,
            "country": country_name,
            "city": city_name or None,
            "source": "internal",
            "description": description or f"{attraction_name} attraction taxonomy node.",
            "official_website": official_website,
            "images": images or [],
            "lat": lat,
            "lng": lng,
        },
    )
    return {"errors": [], **result}


def products(db: Session) -> dict[str, Any]:
    rows = db.scalars(select(Product).order_by(Product.destination_entity_id.asc(), Product.name.asc())).all()
    return {"products": [_product_row(db, product) for product in rows]}


def content(db: Session) -> dict[str, Any]:
    rows = db.scalars(select(Product).order_by(Product.name.asc())).all()
    items = []
    for product in rows:
        draft = _latest_draft(db, product.entity_id)
        diff = _latest_diff(db, product.entity_id)
        items.append(
            {
                "entity_id": product.entity_id,
                "name": product.name,
                "latest_severity": diff.severity if diff else None,
                "draft_status": draft.status if draft else None,
                "draft_version": draft.version if draft else None,
                "validation_errors": draft.validation_errors if draft else [],
                "similarity": draft.similarity if draft else None,
                "variant_count": (
                    db.scalar(
                        select(func.count())
                        .select_from(AudienceVariant)
                        .where(AudienceVariant.drafted_content_id == draft.id)
                    )
                    if draft
                    else 0
                ),
                "published": bool(_published(db, product.entity_id)),
            }
        )
    return {"items": items}


def publishing(db: Session) -> dict[str, Any]:
    records = db.scalars(
        select(PublishedRecord).order_by(PublishedRecord.date_modified.desc()).limit(200)
    ).all()
    return {
        "records": [
            {
                "entity_id": record.entity_id,
                "entity_type": record.entity_type,
                "name": record.content.get("h1") or record.entity_id,
                "status": record.status,
                "index_state": _effective_index_state(record),
                "locked_fields": sorted(
                    field
                    for field, meta in (record.content_locks or {}).items()
                    if isinstance(meta, dict) and meta.get("locked")
                ),
                "canonical_url": record.canonical_url,
                "date_modified": record.date_modified.isoformat(),
                "json_ld_nodes": len(record.schema_json.get("@graph", [])),
            }
            for record in records
        ]
    }


# ---------------------------------------------------------------------------
# Module 2 - Destination Governance (Viator sync, pending review, duplicate
# detection, approve/reject/merge). Corrects the SOW System 1.1 deviation:
# destinations should be Viator-sourced + human-approved, not manually
# created. The manual create_country/create_region/create_city endpoints
# above are kept as-is for POC convenience.
# ---------------------------------------------------------------------------


def _bucket_level(level: str | None) -> str:
    if level in CITY_LEVELS:
        return "CITY"
    return level or "CITY"


def _is_possible_duplicate(candidate: Destination, destination: Destination) -> bool:
    if candidate.entity_id == destination.entity_id:
        return False
    if candidate.review_status != "approved":
        return False
    if _bucket_level(candidate.destination_level) != _bucket_level(destination.destination_level):
        return False
    if (candidate.country or "").strip().lower() != (destination.country or "").strip().lower():
        return False
    return (candidate.name or "").strip().lower() == (destination.name or "").strip().lower()


def _find_possible_duplicate(db: Session, destination: Destination) -> str | None:
    candidates = db.scalars(
        select(Destination)
        .where(
            Destination.review_status == "approved",
            Destination.entity_id != destination.entity_id,
        )
        .order_by(Destination.entity_id.asc())
    ).all()
    for candidate in candidates:
        if _is_possible_duplicate(candidate, destination):
            return candidate.entity_id
    return None


def _resolve_viator_country(by_id: dict[int, dict[str, Any]], raw_row: dict[str, Any]) -> str:
    """Viator's /destinations feed only puts a `country`/`countryName` field
    directly on COUNTRY-type rows; CITY/REGION rows only carry
    `parentDestinationId`. Walk the parent chain (using the raw payloads of
    the full destinations list already fetched) until we hit the COUNTRY
    ancestor, so duplicate-detection can compare on real country names
    instead of "Unknown".
    """
    current: dict[str, Any] | None = raw_row
    seen: set[int] = set()
    while isinstance(current, dict):
        if (current.get("type") or "").upper() == "COUNTRY":
            return str(current.get("name"))
        parent_id = current.get("parentDestinationId")
        if parent_id is None or parent_id in seen:
            break
        seen.add(parent_id)
        current = by_id.get(parent_id)
    return "Unknown"


def sync_viator_destinations(
    db: Session,
    country: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """SOW System 1.1: ingest destinations from the Viator feed as
    `pending_review`, not immediately active/approved. Raises
    ViatorConfigError if VIATOR_API_KEY isn't configured (caller maps to 503).
    """
    from app.services.viator import ViatorClient

    client = ViatorClient()
    mapped_rows = client.destinations()

    by_id = {
        row["viator_destination_id"]: row["raw_viator"]
        for row in mapped_rows
        if row.get("viator_destination_id") is not None
    }
    for row in mapped_rows:
        if row.get("country") == "Unknown":
            row["country"] = _resolve_viator_country(by_id, row.get("raw_viator") or {})

    if country:
        wanted = _clean_name(country).lower()
        mapped_rows = [row for row in mapped_rows if (row.get("country") or "").strip().lower() == wanted]

    created: list[dict[str, Any]] = []
    skipped_existing = 0
    for row in mapped_rows:
        if limit is not None and len(created) >= limit:
            break
        existing = db.scalar(select(Destination).where(Destination.entity_id == row["entity_id"]))
        if existing is not None:
            skipped_existing += 1
            continue
        ingestion.ingest_destination(db, row)
        destination = db.scalar(select(Destination).where(Destination.entity_id == row["entity_id"]))
        if destination is None:
            continue
        destination.review_status = "pending_review"
        db.commit()
        duplicate_of = _find_possible_duplicate(db, destination)
        created.append(
            {
                "entity_id": destination.entity_id,
                "name": destination.name,
                "country": destination.country,
                "destination_level": destination.destination_level,
                "possible_duplicate_of": duplicate_of,
            }
        )

    return {
        "synced": len(created),
        "skipped_existing": skipped_existing,
        "total_seen": len(mapped_rows),
        "created": created,
    }


def pending_destinations(db: Session) -> dict[str, Any]:
    rows = db.scalars(
        select(Destination)
        .where(Destination.review_status == "pending_review")
        .order_by(Destination.country.asc(), Destination.name.asc())
    ).all()
    return {
        "pending": [
            {
                "entity_id": destination.entity_id,
                "name": destination.name,
                "country": destination.country,
                "region": destination.region,
                "city": destination.city,
                "destination_level": destination.destination_level,
                "source": destination.source,
                "possible_duplicate_of": _find_possible_duplicate(db, destination),
            }
            for destination in rows
        ]
    }


def approve_destination(db: Session, entity_id: str, actor: str = "admin_poc") -> dict[str, Any]:
    destination = db.scalar(select(Destination).where(Destination.entity_id == entity_id))
    if destination is None:
        return {"errors": [f"Destination '{entity_id}' not found"]}
    before = destination.review_status
    destination.review_status = "approved"
    audit.log(
        db,
        action="destination_approve",
        entity_id=entity_id,
        before=before,
        after="approved",
        actor=actor,
    )
    db.commit()
    return {"errors": [], "entity_id": entity_id, "review_status": "approved"}


def reject_destination(db: Session, entity_id: str, actor: str = "admin_poc") -> dict[str, Any]:
    destination = db.scalar(select(Destination).where(Destination.entity_id == entity_id))
    if destination is None:
        return {"errors": [f"Destination '{entity_id}' not found"]}
    before = destination.review_status
    destination.review_status = "rejected"
    audit.log(
        db,
        action="destination_reject",
        entity_id=entity_id,
        before=before,
        after="rejected",
        actor=actor,
    )
    db.commit()
    return {"errors": [], "entity_id": entity_id, "review_status": "rejected"}


def merge_destination(
    db: Session,
    entity_id: str,
    canonical_entity_id: str,
    actor: str = "admin_poc",
) -> dict[str, Any]:
    if entity_id == canonical_entity_id:
        return {"errors": ["Cannot merge a destination into itself"]}
    destination = db.scalar(select(Destination).where(Destination.entity_id == entity_id))
    canonical = db.scalar(select(Destination).where(Destination.entity_id == canonical_entity_id))
    if destination is None:
        return {"errors": [f"Destination '{entity_id}' not found"]}
    if canonical is None:
        return {"errors": [f"Canonical destination '{canonical_entity_id}' not found"]}

    products_moved = db.scalars(
        select(Product).where(Product.destination_entity_id == entity_id)
    ).all()
    for product in products_moved:
        product.destination_entity_id = canonical_entity_id

    attractions_moved = db.scalars(
        select(Attraction).where(Attraction.destination_entity_id == entity_id)
    ).all()
    for attraction in attractions_moved:
        attraction.destination_entity_id = canonical_entity_id

    before = destination.review_status
    destination.review_status = "rejected"  # merged-away
    audit.log(
        db,
        action="destination_merge",
        entity_id=entity_id,
        before={"review_status": before},
        after={
            "review_status": "rejected",
            "merged_into": canonical_entity_id,
            "products_reassigned": len(products_moved),
            "attractions_reassigned": len(attractions_moved),
        },
        actor=actor,
    )
    db.commit()
    return {
        "errors": [],
        "entity_id": entity_id,
        "canonical_entity_id": canonical_entity_id,
        "products_reassigned": len(products_moved),
        "attractions_reassigned": len(attractions_moved),
    }


# ---------------------------------------------------------------------------
# Module 4 - Product Ops Debugging Panel
# ---------------------------------------------------------------------------


def product_debug(db: Session, entity_id: str) -> dict[str, Any]:
    diffs = db.scalars(
        select(DiffResult).where(DiffResult.entity_id == entity_id).order_by(DiffResult.to_version.asc())
    ).all()
    draft = _latest_draft(db, entity_id)
    return {
        "entity_id": entity_id,
        "diff_history": [
            {
                "from_version": diff.from_version,
                "to_version": diff.to_version,
                "severity": diff.severity,
                "changed_domains": diff.changed_domains,
                "created_at": diff.created_at.isoformat(),
            }
            for diff in diffs
        ],
        "latest_draft": (
            {
                "version": draft.version,
                "status": draft.status,
                "validation_errors": draft.validation_errors,
                "similarity_band": (draft.similarity or {}).get("band"),
                "similarity": draft.similarity,
            }
            if draft
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Module 3 - Canonical & Duplicate Inspector. Reuses the similarity band/score
# already computed and stored on each DraftedContent row by
# drafting.compute_similarity() at draft time - does not recompute.
# ---------------------------------------------------------------------------


def content_similarity(db: Session) -> dict[str, Any]:
    rows = db.scalars(
        select(DraftedContent).order_by(DraftedContent.entity_id.asc(), DraftedContent.version.asc())
    ).all()
    return {
        "items": [
            {
                "entity_id": row.entity_id,
                "version": row.version,
                "band": (row.similarity or {}).get("band"),
                "score": (row.similarity or {}).get("score"),
                "nearest_entity_id": (row.similarity or {}).get("nearest_entity_id"),
            }
            for row in rows
        ]
    }


# ---------------------------------------------------------------------------
# Module 8 - Global Components Admin (site-wide chrome config)
# ---------------------------------------------------------------------------

DEFAULT_SITE_CONFIG: dict[str, Any] = {
    "header_nav_menu": [
        {"label": "Destinations", "url": "/destinations"},
        {"label": "Experiences", "url": "/experiences"},
        {"label": "Travel Guides", "url": "/guides"},
        {"label": "Experts", "url": "/experts"},
        {"label": "Explore Map", "url": "/explore-map"},
    ],
    "footer_sections": {
        "About": [
            {"label": "About Rosotravel", "url": "/about"},
            {"label": "Careers", "url": "/careers"},
        ],
        "Explore": [
            {"label": "Destinations", "url": "/destinations"},
            {"label": "Travel Guides", "url": "/guides"},
        ],
        "Support": [
            {"label": "Help Center", "url": "/help"},
            {"label": "Contact Us", "url": "/contact"},
        ],
        "Legal": [
            {"label": "Terms of Service", "url": "/terms"},
            {"label": "Privacy Policy", "url": "/privacy"},
        ],
    },
    "cookie_consent_enabled": True,
    "live_chat_enabled": False,
}


def _ensure_site_config_defaults(db: Session) -> None:
    changed = False
    for key, value in DEFAULT_SITE_CONFIG.items():
        existing = db.scalar(select(SiteConfig).where(SiteConfig.key == key))
        if existing is None:
            db.add(SiteConfig(key=key, value=value))
            changed = True
    if changed:
        db.commit()


def site_config(db: Session) -> dict[str, Any]:
    _ensure_site_config_defaults(db)
    rows = db.scalars(select(SiteConfig)).all()
    return {row.key: row.value for row in rows}


def update_site_config(db: Session, key: str, value: Any, actor: str = "admin_poc") -> dict[str, Any]:
    _ensure_site_config_defaults(db)
    row = db.scalar(select(SiteConfig).where(SiteConfig.key == key))
    if row is None:
        return {"errors": [f"Unknown site-config key '{key}'"]}
    before = row.value
    row.value = value
    audit.log(
        db,
        action="site_config_update",
        entity_id=key,
        before=before,
        after=value,
        actor=actor,
    )
    db.commit()
    return {"errors": [], "key": key, "value": value}
