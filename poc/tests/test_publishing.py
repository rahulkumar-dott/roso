from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import Destination, DraftedContent, EnrichedFact, PublishedRecord
from app.services import audit, enrichment, ingestion, model_c, publisher


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


def ingest_france_city(db):
    ingestion.ingest_destination(
        db,
        {
            "entity_id": "dest_paris",
            "name": "Paris",
            "country": "France",
            "region": "Ile-de-France",
            "city": "Paris",
            "source": "internal",
            "description": "The City of Light.",
            "images": ["paris.jpg"],
            "lat": 48.8566,
            "lng": 2.3522,
        },
    )


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


def test_manual_content_edit_locks_field_against_republish():
    db = make_session()
    ingest_attraction(db)
    add_fact(db)
    draft = add_valid_draft(db)
    publisher.publish_entity(db, "poi_colosseum")

    edited, edit_errors = publisher.edit_published_content(
        db,
        "poi_colosseum",
        updates={"h1": "Manually Locked Colosseum Title"},
        lock_fields=[],
        unlock_fields=[],
        edited_by="editor",
    )
    draft.h1 = "Regenerated Colosseum Title"
    draft.version = 2
    db.commit()
    republished, publish_errors = publisher.publish_entity(db, "poi_colosseum")

    assert edit_errors == []
    assert edited["content"]["h1"] == "Manually Locked Colosseum Title"
    assert edited["content_locks"]["h1"]["locked"] is True
    assert publish_errors == []
    assert republished["content"]["h1"] == "Manually Locked Colosseum Title"


def test_manual_content_edit_rejects_unsupported_fields():
    db = make_session()
    ingest_attraction(db)
    add_fact(db)
    add_valid_draft(db)
    publisher.publish_entity(db, "poi_colosseum")

    result, errors = publisher.edit_published_content(
        db,
        "poi_colosseum",
        updates={"canonical_url": "https://example.com/unsafe"},
        lock_fields=[],
        unlock_fields=[],
    )

    assert result is None
    assert errors == ["Unsupported content fields: canonical_url"]


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


def test_promoting_one_country_does_not_index_other_countries():
    db = make_session()
    ingest_city_and_products(db)
    ingest_france_city(db)
    publisher.publish_country_page(db, "Italy")
    publisher.publish_country_page(db, "France")

    italy, italy_errors = publisher.promote_country_page(db, "Italy")
    france = publisher.get_published(db, "country_france")

    assert italy_errors == []
    assert italy["index_state"] == "indexed"
    assert france["index_state"] == "noindex"


def test_legacy_country_without_manual_promotion_marker_is_noindex():
    db = make_session()
    ingest_city_and_products(db)
    publisher.publish_country_page(db, "Italy")
    record = db.scalar(select(PublishedRecord).where(PublishedRecord.entity_id == "country_italy"))
    record.index_state = "indexed"
    db.commit()

    result = publisher.get_published(db, "country_italy")

    assert result["index_state"] == "noindex"


def test_publish_country_requires_stored_destination():
    db = make_session()

    result, errors = publisher.publish_country_page(db, "Atlantis")

    assert result is None
    assert errors == ["Country 'Atlantis' has no stored destinations"]


def test_publish_city_page_blocked_by_destination_activation_gate():
    db = make_session()
    ingestion.ingest_destination(
        db,
        {
            "entity_id": "dest_newcity",
            "name": "Newcity",
            "country": "Italy",
            "region": None,
            "city": "Newcity",
            "source": "viator",
            "description": "A new city.",
            "images": [],
            "lat": 1.0,
            "lng": 1.0,
        },
    )
    destination = db.scalar(select(Destination).where(Destination.entity_id == "dest_newcity"))
    destination.review_status = "pending_review"
    db.commit()

    result, errors = publisher.publish_city_page(db, "dest_newcity")
    assert result is None
    assert "not approved" in errors[0]

    destination.review_status = "approved"
    db.commit()

    result, errors = publisher.publish_city_page(db, "dest_newcity")
    assert result is None
    assert "no linked products" in errors[0]

    ingestion.ingest_product(
        db,
        {
            "entity_id": "prod_newcity_ticket",
            "destination_entity_id": "dest_newcity",
            "name": "Newcity Ticket",
            "category_group": "02_tickets",
            "source": "internal",
            "title": "Newcity Ticket",
            "description": "A ticket in Newcity.",
            "highlights": [],
            "images": [],
            "options": [],
            "inclusions": [],
            "price": 10,
            "currency": "EUR",
        },
    )
    model_c.recompute(db)

    result, errors = publisher.publish_city_page(db, "dest_newcity")
    assert errors == []
    assert result["entity_type"] == "city"


def test_existing_demo_style_destinations_are_unaffected_by_activation_gate():
    """Model default review_status='approved' means any destination created
    the way the existing demo dataset was (ingest_destination without setting
    review_status) keeps publishing exactly as before."""
    db = make_session()
    ingest_city_and_products(db)

    result, errors = publisher.publish_city_page(db, "dest_rome")
    assert errors == []
    assert result["entity_type"] == "city"

    country_result, country_errors = publisher.publish_country_page(db, "Italy")
    assert country_errors == []
    assert country_result["content"]["top_cities"][0]["entity_id"] == "dest_rome"


def test_regenerate_stores_candidate_without_overwriting_locked_value_then_accept():
    db = make_session()
    ingest_city_and_products(db)
    publisher.publish_city_page(db, "dest_rome")

    locked, errors = publisher.edit_published_content(
        db,
        "dest_rome",
        updates={},
        lock_fields=["overview"],
        unlock_fields=[],
        edited_by="editor",
    )
    assert errors == []
    assert locked["content_locks"]["overview"]["locked"] is True
    original_overview = locked["content"]["overview"]

    regenerated, errors = publisher.regenerate_field(db, "dest_rome", "overview")
    assert errors == []
    assert regenerated["content"]["overview"] == original_overview
    assert "overview" in regenerated["content_candidates"]

    candidate_value = regenerated["content_candidates"]["overview"]["value"]
    accepted, errors = publisher.accept_candidate(db, "dest_rome", "overview")
    assert errors == []
    assert accepted["content_candidates"] == {}
    assert accepted["content"]["overview"] == candidate_value


def test_reject_candidate_discards_without_changing_live_value():
    db = make_session()
    ingest_city_and_products(db)
    publisher.publish_city_page(db, "dest_rome")

    regenerated, errors = publisher.regenerate_field(db, "dest_rome", "highlights")
    assert errors == []
    assert "highlights" in regenerated["content_candidates"]
    live_before = regenerated["content"]["highlights"]

    rejected, errors = publisher.reject_candidate(db, "dest_rome", "highlights")
    assert errors == []
    assert rejected["content_candidates"] == {}
    assert rejected["content"]["highlights"] == live_before


def test_revert_restores_ai_value_and_clears_lock():
    db = make_session()
    ingest_city_and_products(db)
    publisher.publish_city_page(db, "dest_rome")

    edited, errors = publisher.edit_published_content(
        db,
        "dest_rome",
        updates={"highlights": ["Manually overridden highlight"]},
        lock_fields=[],
        unlock_fields=[],
        edited_by="editor",
    )
    assert errors == []
    assert edited["content"]["highlights"] == ["Manually overridden highlight"]
    assert edited["content_locks"]["highlights"]["locked"] is True

    reverted, errors = publisher.revert_field(db, "dest_rome", "highlights")
    assert errors == []
    assert reverted["content"]["highlights"] != ["Manually overridden highlight"]
    assert "highlights" not in reverted["content_locks"]


def test_revert_requires_field_to_be_locked():
    db = make_session()
    ingest_city_and_products(db)
    publisher.publish_city_page(db, "dest_rome")

    result, errors = publisher.revert_field(db, "dest_rome", "highlights")

    assert result is None
    assert "not currently locked" in errors[0]


def test_audit_log_records_lock_regenerate_accept_and_revert():
    db = make_session()
    ingest_city_and_products(db)
    publisher.publish_city_page(db, "dest_rome")

    publisher.edit_published_content(
        db, "dest_rome", updates={}, lock_fields=["overview"], unlock_fields=[], edited_by="editor"
    )
    publisher.regenerate_field(db, "dest_rome", "overview")
    publisher.accept_candidate(db, "dest_rome", "overview")
    publisher.edit_published_content(
        db, "dest_rome", updates={"body": "manual body"}, lock_fields=[], unlock_fields=[], edited_by="editor"
    )
    publisher.revert_field(db, "dest_rome", "body")

    actions = [entry["action"] for entry in audit.recent(db, limit=20)]
    assert "content_lock" in actions
    assert "regenerate" in actions
    assert "candidate_accept" in actions
    assert "revert" in actions
