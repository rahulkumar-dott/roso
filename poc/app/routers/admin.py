from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    return admin.overview(db)


@router.get("/destinations")
def destinations(db: Session = Depends(get_db)) -> dict:
    return admin.destinations(db)


@router.get("/products")
def products(db: Session = Depends(get_db)) -> dict:
    return admin.products(db)


@router.get("/content")
def content(db: Session = Depends(get_db)) -> dict:
    return admin.content(db)


@router.get("/publishing")
def publishing(db: Session = Depends(get_db)) -> dict:
    return admin.publishing(db)
