from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import EnrichedFact
from app.services import enrichment, ingestion


class StubSettings:
    google_places_stub = True
    google_places_api_key = None


class StaticAdapter:
    def __init__(self, source: str, fields: dict, is_stub: bool = False) -> None:
        self.source = source
        self.fields = fields
        self.is_stub = is_stub

    def fetch(self, entity):
        return self.fields, self.is_stub


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def create_colosseum(db):
    ingestion.ingest_attraction(
        db,
        {
            "entity_id": "poi-colosseum",
            "name": "Colosseum",
            "country": "Italy",
            "city": "Rome",
            "source": "internal",
        },
    )


def test_google_places_stub_is_deterministic():
    adapter = enrichment.GooglePlacesAdapter(settings=StubSettings())
    db = make_session()
    create_colosseum(db)
    _, entity = enrichment.find_entity(db, "poi-colosseum")

    first, first_is_stub = adapter.fetch(entity)
    second, second_is_stub = adapter.fetch(entity)

    assert first_is_stub is True
    assert second_is_stub is True
    assert first == second
    assert first["formatted_address"] == "Colosseum, Rome, Italy"


def test_factual_hash_is_stable_for_equivalent_fields():
    fields = {"lat": 41.8902, "lng": 12.4922, "official_website": "https://example.com"}
    same_fields_different_order = {
        "official_website": "https://example.com",
        "lng": 12.4922,
        "lat": 41.8902,
    }

    assert enrichment.compute_factual_hash(fields) == enrichment.compute_factual_hash(
        same_fields_different_order
    )


def test_manual_override_wins_over_source_facts():
    google = EnrichedFact(
        entity_id="poi-colosseum",
        source="google_places",
        fields={"phone": "+39 06 1111", "formatted_address": "Google Address"},
        factual_hash="google",
    )
    manual = EnrichedFact(
        entity_id="poi-colosseum",
        source="manual_override",
        fields={"phone": "+39 06 9999"},
        factual_hash="manual",
    )

    resolved = enrichment.resolve_fields([google, manual])

    assert resolved["phone"] == "+39 06 9999"
    assert resolved["formatted_address"] == "Google Address"


def test_enrich_stores_and_reports_unchanged_hashes():
    db = make_session()
    create_colosseum(db)
    adapters = [
        StaticAdapter(
            "google_places",
            {
                "formatted_address": "Piazza del Colosseo, Rome",
                "lat": 41.8902,
                "lng": 12.4922,
                "official_website": "https://colosseo.it",
                "rating": 4.7,
                "review_count": 100000,
            },
        ),
        StaticAdapter(
            "wikidata",
            {
                "entity_type": ["Q570116"],
                "sameAs": ["https://www.wikidata.org/wiki/Q10285"],
                "inception_year": 80,
            },
        ),
    ]

    first = enrichment.enrich_entity(
        db,
        "poi-colosseum",
        manual_overrides={"phone": "+39 06 3996 7700"},
        adapters=adapters,
    )
    second = enrichment.enrich_entity(
        db,
        "poi-colosseum",
        manual_overrides={"phone": "+39 06 3996 7700"},
        adapters=adapters,
    )

    assert first is not None
    assert second is not None
    assert first["resolved_fields"]["phone"] == "+39 06 3996 7700"
    assert first["resolved_fields"]["official_website"] == "https://colosseo.it"
    assert first["resolved_factual_hash"] == second["resolved_factual_hash"]
    assert {source["source"]: source["changed"] for source in first["sources"]} == {
        "google_places": True,
        "wikidata": True,
        "manual_override": True,
    }
    assert {source["source"]: source["changed"] for source in second["sources"]} == {
        "google_places": False,
        "wikidata": False,
        "manual_override": False,
    }
