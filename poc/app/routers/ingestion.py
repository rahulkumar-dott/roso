import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.entities import AttractionIngest, DestinationIngest, IngestResult, ProductIngest
from app.services import ingestion
from app.services.viator import ViatorClient, ViatorConfigError

router = APIRouter(prefix="/ingest", tags=["ingestion"])

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> list[dict]:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@router.post("/destinations", response_model=list[IngestResult])
def ingest_destinations(
    payload: list[DestinationIngest] | None = None,
    fixture: str = "sample_viator_destinations.json",
    source: str = "fixture",
    limit: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Ingest destinations from body, fixture, or live Viator taxonomy."""
    if payload is not None:
        items = [d.model_dump() for d in payload]
    elif source == "viator":
        items = _load_viator_destinations(limit=limit)
    else:
        items = _load_fixture(fixture)
    return [ingestion.ingest_destination(db, item) for item in items]


@router.post("/products", response_model=list[IngestResult])
def ingest_products(
    payload: list[ProductIngest] | None = None,
    fixture: str = "sample_viator_products.json",
    source: str = "fixture",
    count: int = 50,
    modified_since: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Ingest products from body, fixture, or live Viator modified-since feed."""
    if payload is not None:
        items = [p.model_dump() for p in payload]
    elif source == "viator":
        items = _load_viator_products(
            count=count,
            modified_since=modified_since,
            cursor=cursor,
            limit=limit,
        )
    else:
        items = _load_fixture(fixture)
    return [ingestion.ingest_product(db, item) for item in items]


@router.post("/attractions", response_model=list[IngestResult])
def ingest_attractions(
    payload: list[AttractionIngest] | None = None,
    fixture: str = "sample_attractions.json",
    source: str = "fixture",
    viator_destination_id: int | None = None,
    top_x: str = "1-12",
    limit: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Ingest Attraction/POI entities from body, fixture, or live Viator attractions search."""
    if payload is not None:
        items = [a.model_dump() for a in payload]
    elif source == "viator":
        items = _load_viator_attractions(destination_id=viator_destination_id, top_x=top_x, limit=limit)
    else:
        items = _load_fixture(fixture)
    return [ingestion.ingest_attraction(db, item) for item in items]


def _load_viator_destinations(limit: int | None = None) -> list[dict]:
    settings = get_settings()
    if settings.viator_stub:
        raise HTTPException(status_code=400, detail="VIATOR_API_KEY is not configured")
    try:
        return ViatorClient().destinations(limit=limit)
    except ViatorConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Viator destinations fetch failed: {exc}") from exc


def _load_viator_attractions(
    *,
    destination_id: int | None,
    top_x: str,
    limit: int | None,
) -> list[dict]:
    settings = get_settings()
    if settings.viator_stub:
        raise HTTPException(status_code=400, detail="VIATOR_API_KEY is not configured")
    if not destination_id:
        raise HTTPException(status_code=400, detail="viator_destination_id is required for source=viator")
    try:
        return ViatorClient().attractions_search(destination_id=destination_id, top_x=top_x, limit=limit)
    except ViatorConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Viator attractions fetch failed: {exc}") from exc


def _load_viator_products(
    *,
    count: int,
    modified_since: str | None,
    cursor: str | None,
    limit: int | None,
) -> list[dict]:
    settings = get_settings()
    if settings.viator_stub:
        raise HTTPException(status_code=400, detail="VIATOR_API_KEY is not configured")
    try:
        return ViatorClient().products_modified_since(
            count=count,
            modified_since=modified_since,
            cursor=cursor,
            limit=limit,
        )
    except ViatorConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Viator products fetch failed: {exc}") from exc
