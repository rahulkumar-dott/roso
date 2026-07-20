from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.entities import (
    CountryRollupOut,
    ModelCRecomputeOut,
    PicksOut,
    ProductExplainOut,
    SetMembershipRequest,
)
from app.services import model_c

router = APIRouter(tags=["model-c"])


@router.post("/model-c/recompute", response_model=ModelCRecomputeOut)
def recompute(db: Session = Depends(get_db)) -> dict:
    return model_c.recompute(db)


@router.post("/model-c/bulk-auto-confirm")
def bulk_auto_confirm(db: Session = Depends(get_db)) -> dict:
    return model_c.bulk_auto_confirm(db)


@router.post("/products/{product_id}/set")
def set_membership(
    product_id: str,
    payload: SetMembershipRequest,
    db: Session = Depends(get_db),
) -> dict:
    result = model_c.set_membership(
        db,
        product_id,
        in_set=payload.in_set,
        confirmed_by=payload.confirmed_by,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    if result.get("error"):
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@router.get("/cities/{city_id}/picks", response_model=PicksOut)
def city_picks(city_id: str, db: Session = Depends(get_db)) -> dict:
    return model_c.city_picks(db, city_id)


@router.get("/countries/{country}/picks", response_model=CountryRollupOut)
def country_rollup(country: str, db: Session = Depends(get_db)) -> dict:
    return model_c.country_rollup(db, country)


@router.get("/products/{product_id}/explain", response_model=ProductExplainOut)
def explain_product(product_id: str, db: Session = Depends(get_db)) -> dict:
    result = model_c.explain_product(db, product_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    return result
