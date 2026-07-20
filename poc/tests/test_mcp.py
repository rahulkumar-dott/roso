import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
from app.models.entities import McpToolAuditLog, PublishedRecord


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def add_published(db, entity_id="prod_published"):
    db.add(
        PublishedRecord(
            entity_id=entity_id,
            entity_type="product",
            canonical_url=f"https://www.rosotravel.com/en/italy/rome/tours/{entity_id}/",
            schema_json={
                "@context": "https://schema.org",
                "@graph": [
                    {
                        "@type": "TouristTrip",
                        "@id": f"urn:test:{entity_id}",
                        "name": "Rome Food Tour",
                        "aggregateRating": {
                            "@type": "AggregateRating",
                            "ratingValue": 4.7,
                            "reviewCount": 50,
                        },
                    }
                ],
            },
            content={
                "h1": "Rome Food Tour",
                "body": "A published food tour in Rome.",
                "highlights": ["Local food", "Small group"],
                "faq": [{"question": "Where?", "answer": "Rome."}],
                "price_from": 89.0,
                "currency": "EUR",
                "supplier_id": "must-not-leak",
            },
            version=1,
            status="published",
        )
    )
    db.commit()


def client_with_db(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_mcp_requires_agent_header():
    db = make_session()
    add_published(db)
    client = client_with_db(db)

    response = client.post("/mcp/search_tours", json={"city": "Rome"})

    app.dependency_overrides.clear()
    assert response.status_code == 401


def test_mcp_search_get_tour_and_availability_are_published_safe():
    db = make_session()
    add_published(db)
    client = client_with_db(db)
    headers = {"X-Agent-Key": "agent-test"}

    search = client.post("/mcp/search_tours", json={"city": "Rome"}, headers=headers)
    detail = client.post("/mcp/get_tour", json={"entity_id": "prod_published"}, headers=headers)
    availability = client.post(
        "/mcp/get_availability_link",
        json={"entity_id": "prod_published", "date": "2026-08-01"},
        headers=headers,
    )

    app.dependency_overrides.clear()
    assert search.status_code == 200
    assert search.json()["results"][0]["entity_id"] == "prod_published"
    assert detail.status_code == 200
    serialized_detail = json.dumps(detail.json())
    assert "supplier_id" not in serialized_detail
    assert "must-not-leak" not in serialized_detail
    assert availability.status_code == 200
    assert "date=2026-08-01" in availability.json()["booking_url"]
    assert len(db.scalars(select(McpToolAuditLog)).all()) == 3
