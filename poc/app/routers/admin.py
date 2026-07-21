from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import CountryCreateRequest, MergeDestinationRequest
from app.schemas.entities import RegionCreateRequest, CityCreateRequest, AttractionCreateRequest
from app.services import admin, audit
from app.services.viator import ViatorConfigError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return admin.overview(db)


@router.get("/destinations")
def destinations(db: Session = Depends(get_db)) -> dict:
    return admin.destinations(db)


@router.post("/countries")
def create_country(payload: CountryCreateRequest, db: Session = Depends(get_db)) -> dict:
    result = admin.create_country(
        db,
        payload.name,
        region=payload.region,
        description=payload.description,
        images=payload.images,
    )
    if result["errors"]:
        raise HTTPException(status_code=422, detail=result["errors"])
    return result


@router.post("/regions")
def create_region(payload: RegionCreateRequest, db: Session = Depends(get_db)) -> dict:
    result = admin.create_region(
        db,
        payload.country,
        payload.name,
        description=payload.description,
        images=payload.images,
    )
    if result["errors"]:
        raise HTTPException(status_code=422, detail=result["errors"])
    return result


@router.post("/cities")
def create_city(payload: CityCreateRequest, db: Session = Depends(get_db)) -> dict:
    result = admin.create_city(
        db,
        payload.country,
        payload.name,
        region=payload.region,
        description=payload.description,
        images=payload.images,
        lat=payload.lat,
        lng=payload.lng,
    )
    if result["errors"]:
        raise HTTPException(status_code=422, detail=result["errors"])
    return result


@router.post("/attractions")
def create_attraction(payload: AttractionCreateRequest, db: Session = Depends(get_db)) -> dict:
    result = admin.create_attraction(
        db,
        payload.name,
        destination_entity_id=payload.destination_entity_id,
        country=payload.country,
        city=payload.city,
        description=payload.description,
        official_website=payload.official_website,
        images=payload.images,
        lat=payload.lat,
        lng=payload.lng,
    )
    if result["errors"]:
        raise HTTPException(status_code=422, detail=result["errors"])
    return result


@router.get("/products")
def products(db: Session = Depends(get_db)) -> dict:
    return admin.products(db)


@router.get("/content")
def content(db: Session = Depends(get_db)) -> dict:
    return admin.content(db)


@router.get("/publishing")
def publishing(db: Session = Depends(get_db)) -> dict:
    return admin.publishing(db)


# --- Module 2: Destination Governance -------------------------------------


@router.post("/destinations/sync-viator")
def sync_viator_destinations(
    country: str | None = None,
    limit: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return admin.sync_viator_destinations(db, country=country, limit=limit)
    except ViatorConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/destinations/pending")
def pending_destinations(db: Session = Depends(get_db)) -> dict:
    return admin.pending_destinations(db)


@router.post("/destinations/{entity_id}/approve")
def approve_destination(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result = admin.approve_destination(db, entity_id)
    if result["errors"]:
        raise HTTPException(status_code=404, detail=result["errors"])
    return result


@router.post("/destinations/{entity_id}/reject")
def reject_destination(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result = admin.reject_destination(db, entity_id)
    if result["errors"]:
        raise HTTPException(status_code=404, detail=result["errors"])
    return result


@router.post("/destinations/{entity_id}/merge")
def merge_destination(
    entity_id: str,
    payload: MergeDestinationRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = admin.merge_destination(db, entity_id, payload.canonical_entity_id)
    if result["errors"]:
        raise HTTPException(status_code=422, detail=result["errors"])
    return result


# --- Module 4: Product Ops Debugging Panel --------------------------------


@router.get("/products/{entity_id}/debug")
def product_debug(entity_id: str, db: Session = Depends(get_db)) -> dict:
    return admin.product_debug(db, entity_id)


# --- Module 3: Canonical & Duplicate Inspector ----------------------------


@router.get("/content/similarity")
def content_similarity(db: Session = Depends(get_db)) -> dict:
    return admin.content_similarity(db)


# --- Module 8: Global Components Admin ------------------------------------


@router.get("/site-config")
def site_config(db: Session = Depends(get_db)) -> dict:
    return admin.site_config(db)


@router.post("/site-config/{key}")
def update_site_config(key: str, payload: Any = Body(...), db: Session = Depends(get_db)) -> dict:
    result = admin.update_site_config(db, key, payload)
    if result["errors"]:
        raise HTTPException(status_code=404, detail=result["errors"])
    return result


# --- Module 10: Audit Logging ----------------------------------------------


@router.get("/audit-log")
def audit_log(limit: int = 50, db: Session = Depends(get_db)) -> dict:
    return {"entries": audit.recent(db, limit=limit)}
