from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Attraction, DiffResult, Destination, Product, RawVersion
from app.services import diff_engine

HASH_FIELDS = ["content_hash", "factual_hash", "media_hash", "offer_hash", "realtime_offer_hash"]


def _next_version_number(db: Session, entity_id: str) -> int:
    max_version = db.scalar(
        select(func.max(RawVersion.version_number)).where(RawVersion.entity_id == entity_id)
    )
    return (max_version or 0) + 1


def _latest_raw_version(db: Session, entity_id: str) -> RawVersion | None:
    return db.scalar(
        select(RawVersion)
        .where(RawVersion.entity_id == entity_id)
        .order_by(RawVersion.version_number.desc())
        .limit(1)
    )


def _get_or_create_destination(db: Session, payload: dict[str, Any]) -> Destination:
    dest = db.scalar(select(Destination).where(Destination.entity_id == payload["entity_id"]))
    if dest is None:
        dest = Destination(
            entity_id=payload["entity_id"],
            name=payload["name"],
            country=payload["country"],
            region=payload.get("region"),
            city=payload.get("city"),
            destination_level=payload.get("destination_level", "CITY"),
            source=payload.get("source", "viator"),
            status="inactive",
        )
        db.add(dest)
    else:
        dest.name = payload["name"]
        dest.country = payload["country"]
        dest.region = payload.get("region")
        dest.city = payload.get("city")
        dest.destination_level = payload.get("destination_level", dest.destination_level)
    db.flush()
    return dest


def _get_or_create_product(db: Session, payload: dict[str, Any]) -> Product:
    destination_entity_id = _existing_destination_id(db, payload.get("destination_entity_id"))
    prod = db.scalar(select(Product).where(Product.entity_id == payload["entity_id"]))
    if prod is None:
        prod = Product(
            entity_id=payload["entity_id"],
            destination_entity_id=destination_entity_id,
            name=payload["name"],
            category_group=payload["category_group"],
            source=payload.get("source", "viator"),
            status="inactive",
        )
        db.add(prod)
    else:
        prod.name = payload["name"]
        prod.category_group = payload["category_group"]
        if destination_entity_id:
            prod.destination_entity_id = destination_entity_id
    db.flush()
    return prod


def _existing_destination_id(db: Session, destination_entity_id: str | None) -> str | None:
    if not destination_entity_id:
        return None
    exists = db.scalar(select(Destination.entity_id).where(Destination.entity_id == destination_entity_id))
    return exists


def _get_or_create_attraction(db: Session, payload: dict[str, Any]) -> Attraction:
    attraction = db.scalar(select(Attraction).where(Attraction.entity_id == payload["entity_id"]))
    if attraction is None:
        attraction = Attraction(
            entity_id=payload["entity_id"],
            destination_entity_id=payload.get("destination_entity_id"),
            name=payload["name"],
            country=payload.get("country"),
            city=payload.get("city"),
            source=payload.get("source", "internal"),
            status="inactive",
        )
        db.add(attraction)
    else:
        attraction.name = payload["name"]
        attraction.country = payload.get("country")
        attraction.city = payload.get("city")
        if payload.get("destination_entity_id"):
            attraction.destination_entity_id = payload["destination_entity_id"]
    db.flush()
    return attraction


def _ingest(db: Session, entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    entity_id = payload["entity_id"]

    if entity_type == "destination":
        entity = _get_or_create_destination(db, payload)
    elif entity_type == "product":
        entity = _get_or_create_product(db, payload)
    else:
        entity = _get_or_create_attraction(db, payload)

    previous = _latest_raw_version(db, entity_id)
    old_hashes = {field: getattr(previous, field) for field in HASH_FIELDS} if previous else None

    new_hashes = diff_engine.compute_hashes(entity_type, payload)
    severity, changed_domains = diff_engine.classify_severity(old_hashes, new_hashes)

    version_number = _next_version_number(db, entity_id)
    raw_version = RawVersion(
        entity_type=entity_type,
        entity_id=entity_id,
        version_number=version_number,
        payload=payload,
        **new_hashes,
    )
    db.add(raw_version)

    diff_result = DiffResult(
        entity_id=entity_id,
        from_version=previous.version_number if previous else None,
        to_version=version_number,
        severity=severity,
        changed_domains=changed_domains,
    )
    db.add(diff_result)

    # SOW System 1.1: "a destination becomes active once at least one product
    # is linked to it" - simplified for the POC to "active once ingested",
    # since Phase 4's Model C is what governs real product-linkage semantics.
    entity.status = "active"

    db.commit()

    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "version_number": version_number,
        "severity": severity,
        "changed_domains": changed_domains,
    }


def ingest_destination(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    return _ingest(db, "destination", payload)


def ingest_product(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    return _ingest(db, "product", payload)


def ingest_attraction(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    return _ingest(db, "attraction", payload)
