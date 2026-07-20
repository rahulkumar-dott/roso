from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import CountryCreateRequest
from app.schemas.entities import RegionCreateRequest, CityCreateRequest, AttractionCreateRequest
from app.services import admin

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
