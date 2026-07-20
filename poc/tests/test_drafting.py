from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import AudienceVariant
from app.services import drafting, ingestion


BASE_PRODUCT = {
    "entity_id": "prod_colosseum_skip",
    "destination_entity_id": "dest_rome",
    "name": "Colosseum Skip-the-Line Tour",
    "category_group": "02_tickets",
    "source": "viator",
    "title": "Colosseum Skip-the-Line Tour",
    "description": "Visit the Colosseum with priority access and clear meeting details.",
    "highlights": ["Priority access", "Central Rome meeting point", "Flexible start times"],
    "hours": "09:00-17:00",
    "address": "Piazza del Colosseo, Rome",
    "lat": 41.8902,
    "lng": 12.4922,
    "phone": "+39 06 3996 7700",
    "rating": 4.7,
    "review_count": 1000,
    "images": ["a.jpg"],
    "videos": [],
    "options": [{"name": "Standard"}],
    "inclusions": ["Ticket"],
    "cancellation_policy": "Free cancellation",
    "price": 69.0,
    "currency": "EUR",
    "availability_slots": ["09:00"],
}


class StubSettings:
    groq_api_key = None
    groq_model = "stub"


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_validate_draft_reports_structural_errors():
    errors = drafting.validate_draft(
        {
            "h1": "",
            "meta_title": "too short",
            "meta_description": "too short",
            "highlights": [],
            "body": "",
            "faq": [],
        }
    )

    assert "h1 is required" in errors
    assert "body is required" in errors
    assert "meta_title must be 60-75 characters" in errors
    assert "meta_description must be 140-160 characters" in errors


def test_stub_drafting_is_deterministic_and_creates_variants():
    db = make_session()
    ingestion.ingest_product(db, BASE_PRODUCT)

    llm = drafting.LLMAdapter(settings=StubSettings())
    first, status_code, error = drafting.draft_entity(db, "prod_colosseum_skip", llm=llm)
    second, second_status_code, second_error = drafting.draft_entity(
        db, "prod_colosseum_skip", llm=llm
    )

    assert status_code is None
    assert error is None
    assert second_status_code is None
    assert second_error is None
    assert first["status"] == "validated"
    assert first["h1"] == second["h1"]
    assert len(first["variants"]) == 7
    assert db.scalars(select(AudienceVariant)).all()


def test_live_draft_normalization_fixes_short_meta_and_missing_variants():
    class ShortLiveAdapter(drafting.LLMAdapter):
        @property
        def is_live(self):
            return True

        def _groq_draft(self, context):
            return {
                "h1": "Colosseum ticket",
                "meta_title": "Too short",
                "meta_description": "Also too short",
                "highlights": ["Priority access"],
                "body": "Body",
                "faq": [{"question": "Q?", "answer": "A."}],
            }

        def _groq_variants(self, context, draft):
            return []

    db = make_session()
    ingestion.ingest_product(db, BASE_PRODUCT)

    result, status_code, error = drafting.draft_entity(
        db,
        "prod_colosseum_skip",
        llm=ShortLiveAdapter(settings=StubSettings()),
    )

    assert status_code is None
    assert error is None
    assert result["status"] == "validated"
    assert 60 <= len(result["meta_title"]) <= 75
    assert 140 <= len(result["meta_description"]) <= 160
    assert len(result["variants"]) == 7


def test_non_major_latest_diff_is_rejected():
    db = make_session()
    ingestion.ingest_product(db, BASE_PRODUCT)
    ingestion.ingest_product(db, {**BASE_PRODUCT, "price": 79.0})

    result, status_code, error = drafting.draft_entity(db, "prod_colosseum_skip")

    assert result is None
    assert status_code == 409
    assert "Latest diff is not MAJOR" in error


def test_similarity_banding_detects_near_duplicate_body():
    db = make_session()
    first = {**BASE_PRODUCT, "entity_id": "prod_colosseum_a", "name": "Colosseum Tour A"}
    second = {**BASE_PRODUCT, "entity_id": "prod_colosseum_b", "name": "Colosseum Tour B"}
    ingestion.ingest_product(db, first)
    ingestion.ingest_product(db, second)

    llm = drafting.LLMAdapter(settings=StubSettings())
    first_result, _, _ = drafting.draft_entity(db, "prod_colosseum_a", llm=llm)
    second_result, _, _ = drafting.draft_entity(db, "prod_colosseum_b", llm=llm)

    assert first_result["status"] == "validated"
    assert second_result["similarity"]["nearest_entity_id"] == "prod_colosseum_a"
    assert second_result["similarity"]["band"] in {"VARIANT", "DUPLICATE"}
