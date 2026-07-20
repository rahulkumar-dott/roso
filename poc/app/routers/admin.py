from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import CountryCreateRequest
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


@router.get("/products")
def products(db: Session = Depends(get_db)) -> dict:
    return admin.products(db)


@router.get("/content")
def content(db: Session = Depends(get_db)) -> dict:
    return admin.content(db)


@router.get("/publishing")
def publishing(db: Session = Depends(get_db)) -> dict:
    return admin.publishing(db)
