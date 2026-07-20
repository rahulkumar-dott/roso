from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import DraftedContent, EnrichedFact, PublishedRecord
from app.services import enrichment, ingestion, model_c, publisher


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def ingest_attraction(db):
    ingestion.ingest_attraction(
        db,
        {
            "entity_id": "poi_colosseum",
            "name": "Colosseum",
            "country": "Italy",
            "city": "Rome",
            "source": "internal",
            "description": "Ancient amphitheatre in central Rome.",
            "images": ["colosseum.jpg"],
            "lat": 41.8902,
            "lng": 12.4922,
            "official_website": "https://colosseo.it",
        },
    )


def ingest_city_and_products(db):
    ingestion.ingest_destination(
        db,
        {
            "entity_id": "dest_rome",
            "name": "Rome",
            "country": "Italy",
            "region": "Lazio",
            "city": "Rome",
            "source": "internal",
            "description": "The Eternal City.",
            "images": ["rome.jpg"],
            "lat": 41.9028,
            "lng": 12.4964,
        },
    )
    products = [
        ("prod_colosseum_ticket", "Colosseum Skip-the-Line Ticket", "02_tickets", 45, 4.8, 1200),
        ("prod_rome_private", "Private Rome Highlights Tour", "01_tours", 180, 4.9, 450),
        ("prod_rome_food", "Rome Food and Wine Walk", "01_tours", 90, 4.7, 300),
    ]
    for entity_id, title, category, price, rating, review_count in products:
        ingestion.ingest_product(
            db,
            {
                "entity_id": entity_id,
                "destination_entity_id": "dest_rome",
                "name": title,
                "category_group": category,
                "source": "internal",
                "title": title,
                "description": f"{title} description.",
                "highlights": ["Clear logistics", "Strong reviews"],
                "images": [f"{entity_id}.jpg"],
                "options": [{"name": "Standard"}],
                "inclusions": ["Ticket"],
                "cancellation_policy": "Free cancellation",
                "price": price,
                "currency": "EUR",
                "rating": rating,
                "review_count": review_count,
                "availability_slots": ["09:00"],
            },
        )
    model_c.recompute(db)
    model_c.bulk_auto_confirm(db)


def add_valid_draft(db, entity_id="poi_colosseum", version=1):
    draft = DraftedContent(
        entity_id=entity_id,
        version=version,
        h1="Colosseum in Rome",
        meta_title="Colosseum in Rome: trusted visitor planning details",
        meta_description=(
            "Plan the Colosseum with verified visitor details, practical context, "
            "and clear Rosotravel guidance for a confident visit."
        ),
        highlights=["Verified location", "Official context", "Clear planning"],
        body="A governed draft for the Colosseum using factual enrichment.",
        faq=[
            {
                "question": "Where is the Colosseum?",
                "answer": "The Colosseum is in Rome.",
            }
        ],
        status="validated",
        validation_errors=[],
        similarity={"band": "NEW_TOPIC", "score": 0},
    )
    db.add(draft)
    db.commit()
    return draft


def add_fact(db):
    fields = {
        "formatted_address": "Piazza del Colosseo, Rome",
        "lat": 41.8902,
        "lng": 12.4922,
        "phone": "+39 06 3996 7700",
        "sameAs": ["https://www.wikidata.org/wiki/Q10285"],
        "rating": 4.7,
        "review_count": 100000,
    }
    db.add(
        EnrichedFact(
            entity_id="poi_colosseum",
            source="manual_override",
            fields=fields,
            factual_hash=enrichment.compute_factual_hash(fields),
            is_stub=False,
        )
    )
    db.commit()


def test_publish_creates_json_ld_record():
    db = make_session()
    ingest_attraction(db)
    add_fact(db)
    add_valid_draft(db)

    result, errors = publisher.publish_entity(db, "poi_colosseum")

    assert errors == []
    assert result["status"] == "published"
    assert result["schema_json"]["@context"] == "https://schema.org"
    assert any(node["@type"] == "TouristAttraction" for node in result["schema_json"]["@graph"])
    assert result["schema_json"]["@graph"][0]["mainEntity"]


def test_publish_product_content_includes_media_and_price():
    db = make_session()
    ingest_city_and_products(db)
    add_valid_draft(db, entity_id="prod_colosseum_ticket", version=1)

    result, errors = publisher.publish_entity(db, "prod_colosseum_ticket")

    assert errors == []
    assert result["content"]["primary_image"] == "prod_colosseum_ticket.jpg"
    assert result["content"]["images"] == ["prod_colosseum_ticket.jpg"]
    assert result["content"]["price_from"] == 45
    assert result["content"]["currency"] == "EUR"


def test_publish_requires_validated_draft_and_is_atomic():
    db = make_session()
    ingest_attraction(db)
    add_fact(db)

    result, errors = publisher.publish_entity(db, "poi_colosseum")

    assert result is None
    assert errors == ["validated drafted content is required"]
    assert db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == "poi_colosseum")) is None


def test_publish_reports_missing_meta_description_without_partial_record():
    db = make_session()
    ingest_attraction(db)
    add_fact(db)
    draft = add_valid_draft(db)
    draft.meta_description = ""
    db.commit()

    result, errors = publisher.publish_entity(db, "poi_colosseum")

    assert result is None
    assert "meta_description is required" in errors
    assert db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == "poi_colosseum")) is None


def test_republish_preserves_date_published_and_entity_id():
    db = make_session()
    ingest_attraction(db)
    add_fact(db)
    draft = add_valid_draft(db)

    first, first_errors = publisher.publish_entity(db, "poi_colosseum")
    draft.body = "Updated governed draft body."
    db.commit()
    second, second_errors = publisher.publish_entity(db, "poi_colosseum")

    first_entity_node = next(
        node for node in first["schema_json"]["@graph"] if node["@type"] == "TouristAttraction"
    )
    second_entity_node = next(
        node for node in second["schema_json"]["@graph"] if node["@type"] == "TouristAttraction"
    )

    assert first_errors == []
    assert second_errors == []
    assert first["date_published"] == second["date_published"]
    assert first["date_modified"] != second["date_modified"]
    assert first_entity_node["@id"] == second_entity_node["@id"]


def test_publish_city_page_creates_dedicated_city_record():
    db = make_session()
    ingest_city_and_products(db)

    result, errors = publisher.publish_city_page(db, "dest_rome")

    assert errors == []
    assert result["entity_type"] == "city"
    assert result["canonical_url"] == "https://www.rosotravel.com/en/italy/rome/"
    assert result["content"]["page_type"] == "city"
    assert result["content"]["model_c"]["suppressed"] is False
    assert any(node["@type"] == "TouristDestination" for node in result["schema_json"]["@graph"])
    assert any(node.get("@type") == "ItemList" for node in result["schema_json"]["@graph"])


def test_publish_country_page_creates_dedicated_country_record():
    db = make_session()
    ingest_city_and_products(db)

    result, errors = publisher.publish_country_page(db, "Italy")

    assert errors == []
    assert result["entity_id"] == "country_italy"
    assert result["entity_type"] == "country"
    assert result["canonical_url"] == "https://www.rosotravel.com/en/italy/"
    assert result["content"]["page_type"] == "country"
    assert result["content"]["top_cities"][0]["entity_id"] == "dest_rome"


def test_publish_country_requires_stored_destination():
    db = make_session()

    result, errors = publisher.publish_country_page(db, "Atlantis")

    assert result is None
    assert errors == ["Country 'Atlantis' has no stored destinations"]
