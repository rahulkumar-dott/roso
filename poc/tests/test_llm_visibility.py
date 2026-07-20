from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import PublishedRecord
from app.services import visibility


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def add_published(db, entity_id="prod_published", status="published"):
    record = PublishedRecord(
        entity_id=entity_id,
        entity_type="product",
        canonical_url=f"https://www.rosotravel.com/en/italy/rome/tours/{entity_id}/",
        schema_json={
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebPage",
                    "@id": f"https://www.rosotravel.com/en/italy/rome/tours/{entity_id}/#webpage",
                    "mainEntity": {"@id": f"urn:test:{entity_id}"},
                },
                {
                    "@type": "TouristTrip",
                    "@id": f"urn:test:{entity_id}",
                    "name": "Colosseum Tour",
                    "aggregateRating": {
                        "@type": "AggregateRating",
                        "ratingValue": 4.8,
                        "reviewCount": 100,
                    },
                },
            ],
        },
        content={
            "h1": "Colosseum Tour",
            "body": "A published tour summary for Rome.",
            "highlights": ["Priority access", "Clear meeting point"],
            "faq": [{"question": "Where?", "answer": "Rome."}],
            "currency": "EUR",
            "price_from": 69.0,
        },
        version=1,
        status=status,
    )
    db.add(record)
    db.commit()
    return record


def test_ai_summary_and_sitemap_include_only_published_records():
    db = make_session()
    add_published(db, "prod_published")
    add_published(db, "prod_held", status="held")

    summary = visibility.ai_summary(db)
    sitemap = visibility.ai_sitemap_xml(db)

    assert summary["count"] == 1
    assert summary["entities"][0]["entity_id"] == "prod_published"
    assert "prod_published" in sitemap
    assert "prod_held" not in sitemap


def test_tours_feed_is_allowlisted_and_published_only():
    db = make_session()
    add_published(db, "prod_published")
    add_published(db, "prod_held", status="held")

    feed = visibility.tours_feed(db)

    assert len(feed["items"]) == 1
    assert feed["items"][0]["entity_id"] == "prod_published"
    assert "supplier_id" not in feed["items"][0]
    assert "raw_payload" not in feed["items"][0]
