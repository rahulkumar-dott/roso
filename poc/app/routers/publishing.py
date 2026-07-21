from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import (
    PublishedContentEditRequest,
    PublishListOut,
    PublishOut,
    RegenerateFieldRequest,
    RevertFieldRequest,
)
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


@router.post("/countries/{country}/promote", response_model=PublishOut)
def promote_country_page(country: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.promote_country_page(db, country)
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


@router.post("/published/{entity_id}/content", response_model=PublishOut)
def edit_published_content(
    entity_id: str,
    payload: PublishedContentEditRequest,
    db: Session = Depends(get_db),
) -> dict:
    result, errors = publisher.edit_published_content(
        db,
        entity_id,
        updates=payload.updates,
        lock_fields=payload.lock_fields,
        unlock_fields=payload.unlock_fields,
        edited_by=payload.edited_by,
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/published/{entity_id}/regenerate", response_model=PublishOut)
def regenerate_field(
    entity_id: str,
    payload: RegenerateFieldRequest,
    db: Session = Depends(get_db),
) -> dict:
    result, errors = publisher.regenerate_field(db, entity_id, payload.field)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/published/{entity_id}/hero-image/regenerate", response_model=PublishOut)
def regenerate_hero_image(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.regenerate_hero_image(db, entity_id)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/published/{entity_id}/hero-image/upload", response_model=PublishOut)
async def upload_hero_image(
    entity_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    file_bytes = await file.read()
    result, errors = publisher.upload_hero_image(
        db, entity_id, file_bytes, file.content_type or ""
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/published/{entity_id}/candidates/{field}/accept", response_model=PublishOut)
def accept_candidate(entity_id: str, field: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.accept_candidate(db, entity_id, field)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/published/{entity_id}/candidates/{field}/reject", response_model=PublishOut)
def reject_candidate(entity_id: str, field: str, db: Session = Depends(get_db)) -> dict:
    result, errors = publisher.reject_candidate(db, entity_id, field)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.post("/published/{entity_id}/revert", response_model=PublishOut)
def revert_field(
    entity_id: str,
    payload: RevertFieldRequest,
    db: Session = Depends(get_db),
) -> dict:
    result, errors = publisher.revert_field(db, entity_id, payload.field)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert result is not None
    return result


@router.get("/published", response_model=PublishListOut)
def list_published(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> dict:
    return publisher.list_published(db, limit=limit, offset=offset)


@router.get("/destinations/tree")
def destinations_tree(db: Session = Depends(get_db)) -> dict:
    return publisher.destinations_tree(db)
