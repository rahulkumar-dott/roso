from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import KeywordIntelOut
from app.services import keyword_intel

router = APIRouter(tags=["keyword-intel"])


@router.post("/entities/{entity_id}/keywords", response_model=KeywordIntelOut)
def fetch_entity_keywords(
    entity_id: str,
    phrase: str | None = None,
    database: str | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result, status_code, error = keyword_intel.fetch_keyword_intel(
        db,
        entity_id,
        phrase=phrase,
        database=database,
        limit=limit,
    )
    if error:
        raise HTTPException(status_code=status_code or 500, detail=error)
    assert result is not None
    return result


@router.get("/entities/{entity_id}/keywords", response_model=KeywordIntelOut)
def get_entity_keywords(entity_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    result = keyword_intel.get_keyword_intel(db, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' has no keyword intel")
    return result
