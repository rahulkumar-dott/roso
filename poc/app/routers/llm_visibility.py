from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import visibility

router = APIRouter(tags=["llm-visibility"])


@router.get("/llms.txt", response_class=Response)
def llms_txt() -> Response:
    return Response(content=visibility.llms_txt(), media_type="text/plain")


@router.get("/ai-summary.json")
def ai_summary(db: Session = Depends(get_db)) -> dict:
    return visibility.ai_summary(db)


@router.get("/ai-sitemap.xml", response_class=Response)
def ai_sitemap(db: Session = Depends(get_db)) -> Response:
    return Response(content=visibility.ai_sitemap_xml(db), media_type="application/xml")


@router.get("/api/tours/feed")
def tours_feed(cursor: int = 0, limit: int = 20, db: Session = Depends(get_db)) -> dict:
    return visibility.tours_feed(db, cursor=cursor, limit=limit)
