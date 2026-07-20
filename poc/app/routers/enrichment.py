from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import EnrichRequest, EnrichResult, FactsOut
from app.services import enrichment

router = APIRouter(prefix="/entities", tags=["enrichment"])


@router.post("/{entity_id}/enrich", response_model=EnrichResult)
def enrich_entity(
    entity_id: str,
    payload: EnrichRequest | None = None,
    db: Session = Depends(get_db),
) -> dict:
    result = enrichment.enrich_entity(
        db,
        entity_id,
        manual_overrides=payload.manual_overrides if payload else None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return result


@router.get("/{entity_id}/facts", response_model=FactsOut)
def get_facts(entity_id: str, db: Session = Depends(get_db)) -> dict:
    result = enrichment.get_facts(db, entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return result
