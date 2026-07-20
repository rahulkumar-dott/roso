from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.entities import Attraction, DiffResult, Destination, Product, RawVersion
from app.schemas.entities import DiffOut, EntityOut, VersionOut

router = APIRouter(prefix="/entities", tags=["entities"])


def _find_entity(db: Session, entity_id: str) -> tuple[str, Destination | Product | Attraction] | None:
    dest = db.scalar(select(Destination).where(Destination.entity_id == entity_id))
    if dest is not None:
        return "destination", dest
    prod = db.scalar(select(Product).where(Product.entity_id == entity_id))
    if prod is not None:
        return "product", prod
    attraction = db.scalar(select(Attraction).where(Attraction.entity_id == entity_id))
    if attraction is not None:
        return "attraction", attraction
    return None


def _latest_version(db: Session, entity_id: str) -> RawVersion | None:
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


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(entity_id: str, db: Session = Depends(get_db)) -> dict:
    found = _find_entity(db, entity_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    entity_type, entity = found

    version = _latest_version(db, entity_id)
    diff = _latest_diff(db, entity_id)

    return {
        "entity_id": entity.entity_id,
        "entity_type": entity_type,
        "name": entity.name,
        "status": entity.status,
        "latest_version": version.version_number if version else None,
        "latest_severity": diff.severity if diff else None,
    }


@router.get("/{entity_id}/versions", response_model=list[VersionOut])
def get_entity_versions(entity_id: str, db: Session = Depends(get_db)) -> list[dict]:
    if _find_entity(db, entity_id) is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    versions = db.scalars(
        select(RawVersion)
        .where(RawVersion.entity_id == entity_id)
        .order_by(RawVersion.version_number.asc())
    ).all()

    return [
        {
            "version_number": v.version_number,
            "content_hash": v.content_hash,
            "factual_hash": v.factual_hash,
            "media_hash": v.media_hash,
            "offer_hash": v.offer_hash,
            "realtime_offer_hash": v.realtime_offer_hash,
            "created_at": v.created_at.isoformat(),
            "payload": v.payload,
        }
        for v in versions
    ]


@router.get("/{entity_id}/diff/latest", response_model=DiffOut)
def get_latest_diff(entity_id: str, db: Session = Depends(get_db)) -> dict:
    if _find_entity(db, entity_id) is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    diff = _latest_diff(db, entity_id)
    if diff is None:
        raise HTTPException(status_code=404, detail=f"No diff history for '{entity_id}' yet")

    return {
        "entity_id": diff.entity_id,
        "from_version": diff.from_version,
        "to_version": diff.to_version,
        "severity": diff.severity,
        "changed_domains": diff.changed_domains,
        "created_at": diff.created_at.isoformat(),
    }
