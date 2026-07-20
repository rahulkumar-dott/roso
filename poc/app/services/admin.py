from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Attraction,
    AudienceVariant,
    Destination,
    DiffResult,
    DraftedContent,
    PoolMembership,
    Product,
    ProductQualityScore,
    PublishedRecord,
    RawVersion,
    SetMembership,
)
from app.services import ingestion, model_c, schema_builder

CITY_LEVELS = {"CITY", "TOWN", "VILLAGE"}


def _clean_name(value: str) -> str:
    return " ".join(value.strip().split())


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
                "index_state": published_country.index_state if published_country else None,
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
                "index_state": record.index_state,
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
