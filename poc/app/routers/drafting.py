from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import DraftedContentOut, SimilarityOut
from app.services import drafting

router = APIRouter(prefix="/entities", tags=["drafting"])


@router.post("/{entity_id}/draft", response_model=DraftedContentOut)
def draft_entity(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result, status_code, error = drafting.draft_entity(db, entity_id)
    if error:
        raise HTTPException(status_code=status_code or 400, detail=error)
    assert result is not None
    return result


@router.get("/{entity_id}/content", response_model=DraftedContentOut)
def get_content(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result = drafting.get_content(db, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No drafted content for '{entity_id}'")
    return result


@router.get("/{entity_id}/similarity", response_model=SimilarityOut)
def get_similarity(entity_id: str, db: Session = Depends(get_db)) -> dict:
    return drafting.compute_similarity(db, entity_id)
