from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    Archetype,
    ArchetypeMembership,
    Destination,
    PoolMembership,
    Product,
    ProductQualityScore,
    RawVersion,
    SetMembership,
    WinnerSelection,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _latest_payload(db: Session, product_id: str) -> dict[str, Any]:
    raw = db.scalar(
        select(RawVersion)
        .where(RawVersion.entity_id == product_id)
        .order_by(RawVersion.version_number.desc())
        .limit(1)
    )
    return raw.payload if raw else {}


def _product_title(product: Product, payload: dict[str, Any]) -> str:
    return payload.get("title") or product.name


def _primary_image(payload: dict[str, Any]) -> str | None:
    images = payload.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        return str(first) if first else None
    return None


def _score_product(payload: dict[str, Any]) -> tuple[float, float, list[str]]:
    checks = {
        "has_description": bool(payload.get("description")),
        "has_highlights": bool(payload.get("highlights")),
        "has_image": bool(payload.get("images")),
        "has_valid_price": payload.get("price") is not None and payload.get("price", 0) > 0,
        "has_rating": payload.get("rating") is not None,
        "has_review_count": payload.get("review_count") is not None,
    }
    completeness_score = sum(checks.values()) / len(checks)
    rating = float(payload.get("rating") or 0)
    rating_score = min(rating / 5, 1)
    review_count = int(payload.get("review_count") or 0)
    review_score = min(review_count / 1000, 1)
    quality_score = round((0.55 * completeness_score) + (0.30 * rating_score) + (0.15 * review_score), 4)
    reasons = [key for key, ok in checks.items() if ok]
    if rating >= 4.5:
        reasons.append("top_rated")
    if review_count >= 100:
        reasons.append("strong_review_volume")
    return quality_score, round(completeness_score, 4), reasons


def _upsert_quality(
    db: Session, product_id: str, quality_score: float, completeness_score: float
) -> ProductQualityScore:
    row = db.scalar(select(ProductQualityScore).where(ProductQualityScore.product_id == product_id))
    if row is None:
        row = ProductQualityScore(
            product_id=product_id,
            quality_score=quality_score,
            completeness_score=completeness_score,
            computed_at=_utcnow(),
        )
        db.add(row)
    else:
        row.quality_score = quality_score
        row.completeness_score = completeness_score
        row.computed_at = _utcnow()
    db.flush()
    return row


def _upsert_pool(db: Session, product_id: str, in_pool: bool, reasons: list[str]) -> PoolMembership:
    row = db.scalar(select(PoolMembership).where(PoolMembership.product_id == product_id))
    if row is None:
        row = PoolMembership(
            product_id=product_id,
            in_pool=in_pool,
            reasons=reasons,
            computed_at=_utcnow(),
        )
        db.add(row)
    else:
        row.in_pool = in_pool
        row.reasons = reasons
        row.computed_at = _utcnow()
    db.flush()
    return row


def _slug_part(text: str) -> str:
    return "_".join(part for part in text.lower().replace("-", " ").split() if part)


def derive_archetype(product: Product, payload: dict[str, Any]) -> str:
    title = _product_title(product, payload).lower()
    signals = []
    if "skip" in title or "line" in title:
        signals.append("skip_the_line")
    if "private" in title:
        signals.append("private")
    if "small group" in title or "small-group" in title:
        signals.append("small_group")
    if "food" in title or "wine" in title:
        signals.append("food_wine")
    if "transfer" in title:
        signals.append("transfer")
    if "ticket" in title or "pass" in title:
        signals.append("ticket")
    if not signals:
        signals.append("standard")
    return f"{_slug_part(product.category_group)}__{'__'.join(signals)}"


def _get_or_create_archetype(db: Session, city_id: str, name: str) -> Archetype:
    row = db.scalar(select(Archetype).where(Archetype.city_id == city_id, Archetype.name == name))
    if row is None:
        row = Archetype(city_id=city_id, name=name)
        db.add(row)
        db.flush()
    return row


def _assign_archetype(db: Session, product: Product, payload: dict[str, Any]) -> None:
    if not product.destination_entity_id:
        return
    archetype = _get_or_create_archetype(
        db,
        product.destination_entity_id,
        derive_archetype(product, payload),
    )
    existing = db.scalar(
        select(ArchetypeMembership).where(
            ArchetypeMembership.product_id == product.entity_id,
            ArchetypeMembership.archetype_id == archetype.id,
        )
    )
    if existing is None:
        db.add(ArchetypeMembership(product_id=product.entity_id, archetype_id=archetype.id))


def recompute(db: Session) -> dict[str, int]:
    settings = get_settings()
    products = list(db.scalars(select(Product)).all())
    in_pool_count = 0
    for product in products:
        payload = _latest_payload(db, product.entity_id)
        quality_score, completeness_score, reasons = _score_product(payload)
        _upsert_quality(db, product.entity_id, quality_score, completeness_score)
        in_pool = quality_score >= settings.pool_min_quality_score
        if in_pool:
            in_pool_count += 1
            _assign_archetype(db, product, payload)
        _upsert_pool(db, product.entity_id, in_pool, reasons if in_pool else ["below_quality_threshold"])
    db.commit()
    archetype_count = db.scalar(select(Archetype).count()) if False else len(db.scalars(select(Archetype)).all())
    return {
        "products_scored": len(products),
        "products_in_pool": in_pool_count,
        "archetypes": archetype_count,
    }


def set_membership(
    db: Session,
    product_id: str,
    *,
    in_set: bool,
    confirmed_by: str | None,
) -> dict[str, Any] | None:
    product = db.scalar(select(Product).where(Product.entity_id == product_id))
    if product is None:
        return None
    pool = db.scalar(select(PoolMembership).where(PoolMembership.product_id == product_id))
    if in_set and (pool is None or not pool.in_pool):
        return {"error": "Product must be in Pool before it can enter Set"}
    row = db.scalar(select(SetMembership).where(SetMembership.product_id == product_id))
    if row is None:
        row = SetMembership(product_id=product_id)
        db.add(row)
    row.in_set = in_set
    row.confirmed_by = confirmed_by if in_set else None
    row.confirmed_at = _utcnow() if in_set else None
    db.commit()
    return {"product_id": product_id, "in_set": in_set, "confirmed_by": row.confirmed_by}


def bulk_auto_confirm(db: Session, confirmed_by: str = "dev_auto_confirm") -> dict[str, int]:
    pools = db.scalars(select(PoolMembership).where(PoolMembership.in_pool == True)).all()  # noqa: E712
    count = 0
    for pool in pools:
        set_membership(db, pool.product_id, in_set=True, confirmed_by=confirmed_by)
        count += 1
    return {"confirmed": count}


def _set_products_for_city(db: Session, city_id: str) -> list[tuple[Product, dict[str, Any]]]:
    products = db.scalars(select(Product).where(Product.destination_entity_id == city_id)).all()
    selected = []
    for product in products:
        membership = db.scalar(
            select(SetMembership).where(
                SetMembership.product_id == product.entity_id,
                SetMembership.in_set == True,  # noqa: E712
            )
        )
        if membership:
            selected.append((product, _latest_payload(db, product.entity_id)))
    return selected


def _quality(db: Session, product_id: str) -> ProductQualityScore | None:
    return db.scalar(select(ProductQualityScore).where(ProductQualityScore.product_id == product_id))


def _archetype_names(db: Session, product_id: str) -> list[str]:
    rows = db.scalars(
        select(ArchetypeMembership).where(ArchetypeMembership.product_id == product_id)
    ).all()
    return [row.archetype.name for row in rows]


def _reason_codes(payload: dict[str, Any], slot: str) -> list[str]:
    reasons = [slot]
    rating = float(payload.get("rating") or 0)
    review_count = int(payload.get("review_count") or 0)
    if rating >= 4.5:
        reasons.append("top_rated")
    if review_count >= 100:
        reasons.append("strong_review_volume")
    if payload.get("price"):
        reasons.append("price_available")
    if "private" in (payload.get("title") or "").lower():
        reasons.append("private_or_premium")
    return reasons


def _pick_out(
    db: Session,
    slot: str,
    product: Product,
    payload: dict[str, Any],
    *,
    score: float,
) -> dict[str, Any]:
    archetypes = _archetype_names(db, product.entity_id)
    return {
        "slot": slot,
        "product_id": product.entity_id,
        "title": _product_title(product, payload),
        "image_url": _primary_image(payload),
        "price_from": payload.get("price"),
        "currency": payload.get("currency"),
        "archetype": archetypes[0] if archetypes else "ungrouped",
        "score": round(score, 4),
        "reason_codes": _reason_codes(payload, slot),
    }


def _value_score(payload: dict[str, Any]) -> float:
    rating = float(payload.get("rating") or 0)
    review_boost = min(int(payload.get("review_count") or 0) / 1000, 1)
    price = float(payload.get("price") or 999999)
    return ((rating / 5) + (0.25 * review_boost)) / max(price, 1)


def _premium_score(payload: dict[str, Any]) -> float:
    title = (payload.get("title") or "").lower()
    premium_boost = 0.2 if "private" in title or "small" in title else 0
    return float(payload.get("rating") or 0) + premium_boost


def city_picks(db: Session, city_id: str) -> dict[str, Any]:
    settings = get_settings()
    candidates = _set_products_for_city(db, city_id)
    if len(candidates) < settings.set_sparse_threshold:
        return {
            "city_id": city_id,
            "suppressed": True,
            "reason": "set_below_sparse_threshold",
            "picks": [],
            "decision_proof": {},
        }

    used_archetypes: set[str] = set()
    picks: list[dict[str, Any]] = []

    best_value = max(candidates, key=lambda item: _value_score(item[1]))
    picks.append(_pick_out(db, "best_value", *best_value, score=_value_score(best_value[1])))
    used_archetypes.add(picks[-1]["archetype"])

    premium_candidates = [
        item
        for item in candidates
        if (_archetype_names(db, item[0].entity_id) or ["ungrouped"])[0] not in used_archetypes
    ]
    if premium_candidates:
        premium = max(premium_candidates, key=lambda item: _premium_score(item[1]))
        picks.append(_pick_out(db, "premium", *premium, score=_premium_score(premium[1])))
        used_archetypes.add(picks[-1]["archetype"])

    remaining = sorted(
        [
            item
            for item in candidates
            if (_archetype_names(db, item[0].entity_id) or ["ungrouped"])[0] not in used_archetypes
        ],
        key=lambda item: (_quality(db, item[0].entity_id).quality_score if _quality(db, item[0].entity_id) else 0),
        reverse=True,
    )
    for index, item in enumerate(remaining, start=1):
        picks.append(
            _pick_out(
                db,
                f"rail_{index}",
                *item,
                score=_quality(db, item[0].entity_id).quality_score if _quality(db, item[0].entity_id) else 0,
            )
        )
        used_archetypes.add(picks[-1]["archetype"])

    _replace_winners(db, city_id, picks)
    return {
        "city_id": city_id,
        "suppressed": False,
        "reason": None,
        "picks": picks,
        "decision_proof": _decision_proof(candidates, picks),
    }


def _replace_winners(db: Session, city_id: str, picks: list[dict[str, Any]]) -> None:
    db.execute(delete(WinnerSelection).where(WinnerSelection.city_id == city_id))
    for pick in picks:
        db.add(
            WinnerSelection(
                city_id=city_id,
                slot=pick["slot"],
                product_id=pick["product_id"],
                reason_codes=pick["reason_codes"],
                computed_at=_utcnow(),
            )
        )
    db.commit()


def _decision_proof(
    candidates: list[tuple[Product, dict[str, Any]]],
    picks: list[dict[str, Any]],
) -> dict[str, list[str] | str]:
    picked_ids = {pick["product_id"] for pick in picks}
    skipped = [
        _product_title(product, payload)
        for product, payload in candidates
        if product.entity_id not in picked_ids
    ][:4]
    return {
        "shortlist_reason": "Rosotravel shows Set-confirmed products only, then selects materially different winners by archetype.",
        "why_these_picks": [
            "Best value balances rating, review volume, and price.",
            "Premium favors higher comfort or private/small-group signals.",
            "Rails avoid repeating the same archetype.",
        ],
        "what_we_skipped": skipped or ["No eligible Set products were skipped."],
    }


def country_rollup(db: Session, country: str) -> dict[str, Any]:
    products = []
    cities: dict[str, dict[str, Any]] = {}
    # Distinct destination IDs only - city_picks was previously called once per
    # product sharing a destination, inflating pick_count and duplicating
    # top_products by a factor of however many products that city had.
    city_ids = {
        product.destination_entity_id
        for product in db.scalars(select(Product)).all()
        if product.destination_entity_id and _city_in_country(db, product.destination_entity_id, country)
    }
    for city_id in city_ids:
        picks = city_picks(db, city_id)
        if not picks["suppressed"]:
            cities[city_id] = {"city_id": city_id, "pick_count": len(picks["picks"])}
            products.extend(picks["picks"])

    if not cities:
        return {"country": country, "suppressed": True, "reason": "no_city_set_outputs", "top_cities": [], "top_products": []}

    top_cities = sorted(cities.values(), key=lambda item: item["pick_count"], reverse=True)[:6]
    top_products = sorted(products, key=lambda item: item["score"], reverse=True)[:6]
    return {
        "country": country,
        "suppressed": False,
        "reason": None,
        "top_cities": top_cities,
        "top_products": top_products,
    }


def _city_in_country(db: Session, city_id: str | None, country: str) -> bool:
    if not city_id:
        return False
    destination = db.scalar(select(Destination).where(Destination.entity_id == city_id))
    return bool(destination and destination.country.lower() == country.lower())


def explain_product(db: Session, product_id: str) -> dict[str, Any] | None:
    product = db.scalar(select(Product).where(Product.entity_id == product_id))
    if product is None:
        return None
    quality = _quality(db, product_id)
    pool = db.scalar(select(PoolMembership).where(PoolMembership.product_id == product_id))
    set_row = db.scalar(select(SetMembership).where(SetMembership.product_id == product_id))
    archetypes = _archetype_names(db, product_id)
    winners = db.scalars(select(WinnerSelection).where(WinnerSelection.product_id == product_id)).all()
    competitors = []
    if product.destination_entity_id:
        for other, _payload in _set_products_for_city(db, product.destination_entity_id):
            if other.entity_id != product_id and set(_archetype_names(db, other.entity_id)) & set(archetypes):
                competitors.append(other.entity_id)
    return {
        "product_id": product_id,
        "in_pool": bool(pool and pool.in_pool),
        "in_set": bool(set_row and set_row.in_set),
        "quality_score": quality.quality_score if quality else None,
        "completeness_score": quality.completeness_score if quality else None,
        "reasons": pool.reasons if pool else [],
        "archetypes": archetypes,
        "winner_slots": [winner.slot for winner in winners],
        "competed_against": competitors,
    }
