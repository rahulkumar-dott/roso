import hashlib
import json
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import McpToolAuditLog, PublishedRecord


def published_records(db: Session) -> list[PublishedRecord]:
    return list(
        db.scalars(
            select(PublishedRecord)
            .where(PublishedRecord.status == "published")
            .order_by(PublishedRecord.entity_id.asc())
        ).all()
    )


def llms_txt() -> str:
    return "\n".join(
        [
            "Rosotravel AI visibility entry point",
            "Published-only feeds:",
            "- /ai-summary.json",
            "- /ai-sitemap.xml",
            "- /api/tours/feed",
            "MCP-style REST tools:",
            "- POST /mcp/search_tours",
            "- POST /mcp/get_tour",
            "- POST /mcp/get_availability_link",
        ]
    )


def _entity_node(record: PublishedRecord) -> dict[str, Any]:
    graph = record.schema_json.get("@graph", [])
    return next(
        (
            node
            for node in graph
            if node.get("@type") in {"TouristDestination", "TouristAttraction", "TouristTrip"}
        ),
        {},
    )


def _webpage_node(record: PublishedRecord) -> dict[str, Any]:
    graph = record.schema_json.get("@graph", [])
    return next((node for node in graph if node.get("@type") == "WebPage"), {})


def _geo(record: PublishedRecord) -> dict[str, Any] | None:
    geo = _entity_node(record).get("geo")
    if not geo:
        return None
    return {
        "lat": geo.get("latitude"),
        "lng": geo.get("longitude"),
    }


def ai_summary(db: Session) -> dict[str, Any]:
    records = published_records(db)
    return {
        "generated_from": "published_records",
        "count": len(records),
        "entities": [
            {
                "entity_id": record.entity_id,
                "name": record.content.get("h1"),
                "url": record.canonical_url,
                "entity_type": record.entity_type,
                "summary_short": record.content.get("body", "")[:240],
                "highlights": record.content.get("highlights", [])[:5],
                "key_faq": record.content.get("faq", [])[:3],
                "geo": _geo(record),
                "lastmod": record.date_modified.isoformat(),
            }
            for record in records
        ],
    }


def ai_sitemap_xml(db: Session) -> str:
    records = published_records(db)
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for record in records:
        rows.extend(
            [
                "  <url>",
                f"    <loc>{escape(record.canonical_url)}</loc>",
                f"    <lastmod>{escape(record.date_modified.date().isoformat())}</lastmod>",
                f"    <entity_type>{escape(record.entity_type)}</entity_type>",
                "  </url>",
            ]
        )
    rows.append("</urlset>")
    return "\n".join(rows)


def tours_feed(db: Session, cursor: int = 0, limit: int = 20) -> dict[str, Any]:
    records = [
        record
        for record in published_records(db)
        if record.entity_type == "product"
    ]
    page = records[cursor : cursor + limit]
    next_cursor = cursor + limit if cursor + limit < len(records) else None
    return {
        "items": [_tour_item(record, include_summary=True) for record in page],
        "next_cursor": next_cursor,
    }


def _tour_item(record: PublishedRecord, *, include_summary: bool = False) -> dict[str, Any]:
    content = record.content
    entity = _entity_node(record)
    item = {
        "entity_id": record.entity_id,
        "name": content.get("h1") or entity.get("name") or record.entity_id,
        "canonical_url": record.canonical_url,
        "price_from": content.get("price_from"),
        "currency": content.get("currency"),
        "duration_minutes": content.get("duration_minutes"),
        "rating_average": (entity.get("aggregateRating") or {}).get("ratingValue"),
        "source_type": "published_record",
    }
    if include_summary:
        item.update(
            {
                "short_summary": content.get("body", "")[:240],
                "highlights": content.get("highlights", [])[:5],
                "key_faq": content.get("faq", [])[:3],
                "booking_url": booking_url(record.entity_id),
                "availability_state": "link_required",
            }
        )
    return item


def search_tours(
    db: Session,
    *,
    country: str | None = None,
    city: str | None = None,
    categories: list[str] | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    records = [record for record in published_records(db) if record.entity_type == "product"]
    categories = categories or []
    filtered = []
    for record in records:
        haystack = json.dumps(record.content, default=str).lower() + " " + record.canonical_url.lower()
        if country and country.lower() not in haystack:
            continue
        if city and city.lower() not in haystack:
            continue
        if categories and not any(category.lower() in haystack for category in categories):
            continue
        filtered.append(record)
    return {"results": [_tour_item(record) for record in filtered[:max_results]]}


def get_tour(db: Session, entity_id: str) -> dict[str, Any] | None:
    record = db.scalar(
        select(PublishedRecord).where(
            PublishedRecord.entity_id == entity_id,
            PublishedRecord.status == "published",
        )
    )
    if record is None:
        return None
    entity = _entity_node(record)
    return {
        "entity_id": record.entity_id,
        "entity_type": record.entity_type,
        "canonical_url": record.canonical_url,
        "name": record.content.get("h1") or entity.get("name"),
        "summary": record.content.get("body"),
        "highlights": record.content.get("highlights", []),
        "faq": record.content.get("faq", []),
        "geo": _geo(record),
        "rating_average": (entity.get("aggregateRating") or {}).get("ratingValue"),
        "booking_url": booking_url(record.entity_id),
    }


def booking_url(entity_id: str, date: str | None = None) -> str:
    url = f"https://www.rosotravel.com/booking/poc/{entity_id}"
    if date:
        url += f"?date={date}"
    return url


def availability_link(entity_id: str, date: str | None = None) -> dict[str, str]:
    return {
        "entity_id": entity_id,
        "booking_url": booking_url(entity_id, date),
        "note": "POC placeholder only. Date is treated as a routing hint, not live availability.",
    }


def audit_tool_call(
    db: Session,
    *,
    agent_id: str,
    tool_name: str,
    params: dict[str, Any],
    response: dict[str, Any],
) -> None:
    serialized = json.dumps(response, sort_keys=True, default=str)
    db.add(
        McpToolAuditLog(
            agent_id=agent_id,
            tool_name=tool_name,
            params=params,
            response_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        )
    )
    db.commit()
