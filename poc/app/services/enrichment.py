import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import Attraction, Destination, EnrichedFact, Product

SOURCE_PRIORITY = ["viator", "wikidata", "google_places", "official_website", "manual_override"]

FACT_FIELDS = [
    "opening_hours",
    "formatted_address",
    "lat",
    "lng",
    "phone",
    "official_website",
    "rating",
    "review_count",
    "inception_year",
    "architectural_style",
    "entity_type",
    "sameAs",
    "isPartOf",
    "hasPart",
]


def compute_factual_hash(fields: dict[str, Any]) -> str:
    normalized = {key: fields.get(key) for key in sorted(fields)}
    payload = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def find_entity(db: Session, entity_id: str) -> tuple[str, Destination | Product | Attraction] | None:
    dest = db.scalar(select(Destination).where(Destination.entity_id == entity_id))
    if dest is not None:
        return "destination", dest
    product = db.scalar(select(Product).where(Product.entity_id == entity_id))
    if product is not None:
        return "product", product
    attraction = db.scalar(select(Attraction).where(Attraction.entity_id == entity_id))
    if attraction is not None:
        return "attraction", attraction
    return None


def _location_hint(entity: Destination | Product | Attraction) -> str | None:
    if isinstance(entity, Product):
        return None
    parts = [getattr(entity, "city", None), getattr(entity, "region", None), getattr(entity, "country", None)]
    return ", ".join(part for part in parts if part) or None


class GooglePlacesAdapter:
    source = "google_places"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def fetch(self, entity: Destination | Product | Attraction) -> tuple[dict[str, Any], bool]:
        if self.settings.google_places_stub:
            return self._stub_fields(entity), True
        return self._live_fields(entity), False

    def _stub_fields(self, entity: Destination | Product | Attraction) -> dict[str, Any]:
        digest = hashlib.sha256(entity.name.encode("utf-8")).hexdigest()
        rating = 4.0 + (int(digest[:2], 16) % 10) / 10
        review_count = 100 + int(digest[2:6], 16) % 9000
        lat = round(((int(digest[6:10], 16) % 1800000) / 10000) - 90, 6)
        lng = round(((int(digest[10:14], 16) % 3600000) / 10000) - 180, 6)
        location = _location_hint(entity) or "stub location"
        return {
            "opening_hours": ["Monday-Sunday 09:00-17:00"],
            "formatted_address": f"{entity.name}, {location}",
            "lat": lat,
            "lng": lng,
            "phone": f"+1 555 {int(digest[14:18], 16) % 10000:04d}",
            "official_website": f"https://example.com/{entity.entity_id}",
            "rating": round(min(rating, 5.0), 1),
            "review_count": review_count,
        }

    def _live_fields(self, entity: Destination | Product | Attraction) -> dict[str, Any]:
        query = entity.name
        location = _location_hint(entity)
        if location:
            query = f"{query}, {location}"

        key = self.settings.google_places_api_key
        assert key is not None

        with httpx.Client(timeout=20) as client:
            search = client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": key},
            )
            search.raise_for_status()
            search_payload = search.json()
            results = search_payload.get("results") or []
            if not results:
                return {}

            place_id = results[0]["place_id"]
            details = client.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={
                    "place_id": place_id,
                    "fields": ",".join(
                        [
                            "formatted_address",
                            "geometry",
                            "international_phone_number",
                            "opening_hours",
                            "rating",
                            "user_ratings_total",
                            "website",
                        ]
                    ),
                    "key": key,
                },
            )
            details.raise_for_status()
            result = details.json().get("result") or {}

        location_data = (result.get("geometry") or {}).get("location") or {}
        return {
            "opening_hours": (result.get("opening_hours") or {}).get("weekday_text"),
            "formatted_address": result.get("formatted_address"),
            "lat": location_data.get("lat"),
            "lng": location_data.get("lng"),
            "phone": result.get("international_phone_number"),
            "official_website": result.get("website"),
            "rating": result.get("rating"),
            "review_count": result.get("user_ratings_total"),
        }


class WikidataAdapter:
    source = "wikidata"

    def fetch(self, entity: Destination | Product | Attraction) -> tuple[dict[str, Any], bool]:
        query = entity.name
        with httpx.Client(timeout=20) as client:
            search = client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": query,
                    "language": "en",
                    "format": "json",
                    "limit": 1,
                },
                headers={"User-Agent": "RosotravelPhase2POC/0.1"},
            )
            search.raise_for_status()
            results = search.json().get("search") or []
            if not results:
                return {}, False

            qid = results[0]["id"]
            entity_data = client.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
                headers={"User-Agent": "RosotravelPhase2POC/0.1"},
            )
            entity_data.raise_for_status()
            wikidata_entity = entity_data.json()["entities"][qid]

        claims = wikidata_entity.get("claims") or {}
        fields: dict[str, Any] = {
            "sameAs": [
                f"https://www.wikidata.org/wiki/{qid}",
            ],
            "entity_type": self._entity_labels(claims, "P31"),
            "inception_year": self._year_claim(claims, "P571"),
            "architectural_style": self._entity_labels(claims, "P149"),
            "isPartOf": self._entity_labels(claims, "P361"),
            "hasPart": self._entity_labels(claims, "P527"),
        }
        coords = self._coords_claim(claims, "P625")
        if coords:
            fields.update(coords)
        wikipedia = wikidata_entity.get("sitelinks", {}).get("enwiki", {}).get("url")
        if wikipedia:
            fields["sameAs"].append(wikipedia)
        return {k: v for k, v in fields.items() if v not in (None, [], {})}, False

    def _claim_values(self, claims: dict[str, Any], prop: str) -> list[Any]:
        values = []
        for claim in claims.get(prop, []):
            mainsnak = claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            if "value" in datavalue:
                values.append(datavalue["value"])
        return values

    def _entity_labels(self, claims: dict[str, Any], prop: str) -> list[str]:
        labels = []
        for value in self._claim_values(claims, prop):
            if isinstance(value, dict) and value.get("id"):
                labels.append(value["id"])
        return labels

    def _year_claim(self, claims: dict[str, Any], prop: str) -> int | None:
        values = self._claim_values(claims, prop)
        if not values:
            return None
        raw_time = values[0].get("time") if isinstance(values[0], dict) else None
        if not raw_time:
            return None
        try:
            return int(raw_time[1:5])
        except ValueError:
            return None

    def _coords_claim(self, claims: dict[str, Any], prop: str) -> dict[str, float] | None:
        values = self._claim_values(claims, prop)
        if not values or not isinstance(values[0], dict):
            return None
        return {"lat": values[0].get("latitude"), "lng": values[0].get("longitude")}


def _upsert_fact(
    db: Session,
    entity_id: str,
    source: str,
    fields: dict[str, Any],
    *,
    is_stub: bool = False,
) -> tuple[EnrichedFact, bool]:
    clean_fields = {key: value for key, value in fields.items() if value is not None}
    new_hash = compute_factual_hash(clean_fields)
    fact = db.scalar(
        select(EnrichedFact).where(
            EnrichedFact.entity_id == entity_id,
            EnrichedFact.source == source,
        )
    )
    if fact is None:
        fact = EnrichedFact(
            entity_id=entity_id,
            source=source,
            fields=clean_fields,
            factual_hash=new_hash,
            is_stub=is_stub,
            fetched_at=_utcnow(),
        )
        db.add(fact)
        db.flush()
        return fact, True

    changed = fact.factual_hash != new_hash or fact.is_stub != is_stub
    if changed:
        fact.fields = clean_fields
        fact.factual_hash = new_hash
        fact.is_stub = is_stub
        fact.fetched_at = _utcnow()
        db.flush()
    return fact, changed


def _source_facts(db: Session, entity_id: str) -> list[EnrichedFact]:
    return list(
        db.scalars(
            select(EnrichedFact)
            .where(EnrichedFact.entity_id == entity_id)
            .order_by(EnrichedFact.source.asc())
        ).all()
    )


def resolve_fields(facts: list[EnrichedFact]) -> dict[str, Any]:
    by_source = {fact.source: fact.fields for fact in facts}
    resolved: dict[str, Any] = {}
    for source in SOURCE_PRIORITY:
        for key, value in by_source.get(source, {}).items():
            if value not in (None, "", [], {}):
                resolved[key] = value
    return {key: resolved[key] for key in FACT_FIELDS if key in resolved}


def _fact_out(fact: EnrichedFact, changed: bool = False) -> dict[str, Any]:
    return {
        "source": fact.source,
        "fields": fact.fields,
        "factual_hash": fact.factual_hash,
        "changed": changed,
        "is_stub": fact.is_stub,
        "fetched_at": fact.fetched_at.isoformat(),
    }


def enrich_entity(
    db: Session,
    entity_id: str,
    manual_overrides: dict[str, Any] | None = None,
    *,
    adapters: list[GooglePlacesAdapter | WikidataAdapter] | None = None,
) -> dict[str, Any] | None:
    found = find_entity(db, entity_id)
    if found is None:
        return None
    entity_type, entity = found

    changed_by_source: dict[str, bool] = {}
    adapters = adapters or [GooglePlacesAdapter(), WikidataAdapter()]
    for adapter in adapters:
        fields, is_stub = adapter.fetch(entity)
        fact, changed = _upsert_fact(db, entity_id, adapter.source, fields, is_stub=is_stub)
        changed_by_source[fact.source] = changed

    if manual_overrides:
        fact, changed = _upsert_fact(
            db,
            entity_id,
            "manual_override",
            manual_overrides,
            is_stub=False,
        )
        changed_by_source[fact.source] = changed

    db.commit()
    facts = _source_facts(db, entity_id)
    resolved = resolve_fields(facts)
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "resolved_fields": resolved,
        "resolved_factual_hash": compute_factual_hash(resolved),
        "sources": [_fact_out(fact, changed_by_source.get(fact.source, False)) for fact in facts],
    }


def get_facts(db: Session, entity_id: str) -> dict[str, Any] | None:
    found = find_entity(db, entity_id)
    if found is None:
        return None
    entity_type, _ = found
    facts = _source_facts(db, entity_id)
    resolved = resolve_fields(facts)
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "resolved_fields": resolved,
        "resolved_factual_hash": compute_factual_hash(resolved),
        "sources": [_fact_out(fact) for fact in facts],
    }
