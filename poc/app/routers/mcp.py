from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import (
    AvailabilityLinkOut,
    AvailabilityLinkRequest,
    GetTourRequest,
    SearchToursOut,
    SearchToursRequest,
)
from app.services import visibility

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _agent_id(x_agent_key: str | None) -> str:
    if not x_agent_key:
        raise HTTPException(status_code=401, detail="X-Agent-Key header is required")
    return x_agent_key


@router.post("/search_tours", response_model=SearchToursOut)
def search_tours(
    payload: SearchToursRequest,
    x_agent_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    agent_id = _agent_id(x_agent_key)
    result = visibility.search_tours(
        db,
        country=payload.country,
        city=payload.city,
        categories=payload.categories,
        max_results=payload.max_results,
    )
    visibility.audit_tool_call(
        db,
        agent_id=agent_id,
        tool_name="search_tours",
        params=payload.model_dump(),
        response=result,
    )
    return result


@router.post("/get_tour")
def get_tour(
    payload: GetTourRequest,
    x_agent_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    agent_id = _agent_id(x_agent_key)
    result = visibility.get_tour(db, payload.entity_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Tour '{payload.entity_id}' not found")
    visibility.audit_tool_call(
        db,
        agent_id=agent_id,
        tool_name="get_tour",
        params=payload.model_dump(),
        response=result,
    )
    return result


@router.post("/get_availability_link", response_model=AvailabilityLinkOut)
def get_availability_link(
    payload: AvailabilityLinkRequest,
    x_agent_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    agent_id = _agent_id(x_agent_key)
    result = visibility.availability_link(payload.entity_id, payload.date)
    visibility.audit_tool_call(
        db,
        agent_id=agent_id,
        tool_name="get_availability_link",
        params=payload.model_dump(),
        response=result,
    )
    return result
