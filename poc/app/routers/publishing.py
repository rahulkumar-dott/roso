from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import PublishListOut, PublishOut
from app.services import publisher

router = APIRouter(tags=["publishing"])


@router.post("/entities/{entity_id}/publish", response_model=PublishOut)
def publish_entity(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.publish_entity(db, entity_id)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/cities/{city_id}/publish", response_model=PublishOut)
def publish_city_page(city_id: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.publish_city_page(db, city_id)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/countries/{country}/publish", response_model=PublishOut)
def publish_country_page(country: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.publish_country_page(db, country)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.get("/published/{entity_id}", response_model=PublishOut)
def get_published(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result = publisher.get_published(db, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Published record '{entity_id}' not found")
    return result


@router.get("/published", response_model=PublishListOut)
def list_published(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    return publisher.list_published(db, limit=limit, offset=offset)


@router.get("/destinations/tree")
def destinations_tree(db: Session = Depends(get_db)) -> dict:
    return publisher.destinations_tree(db)
