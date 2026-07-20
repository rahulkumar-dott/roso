from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.services import drafting, ingestion, keyword_intel


BASE_PRODUCT = {
    "entity_id": "prod_colosseum_skip",
    "destination_entity_id": "dest_rome",
    "name": "Colosseum Skip-the-Line Tour",
    "category_group": "02_tickets",
    "source": "viator",
    "title": "Colosseum Skip-the-Line Tour",
    "description": "Visit the Colosseum with priority access and clear meeting details.",
    "highlights": ["Priority access", "Central Rome meeting point", "Flexible start times"],
    "images": ["a.jpg"],
    "options": [{"name": "Standard"}],
    "inclusions": ["Ticket"],
    "price": 69.0,
    "currency": "EUR",
    "availability_slots": ["09:00"],
}


class StubSemrushClient:
    def related_keywords(self, phrase, *, database=None, limit=10):
        return [
            {
                "keyword": phrase.lower(),
                "search_volume": 1000,
                "cpc": 1.2,
                "competition": 0.4,
            }
        ][:limit]

    def phrase_questions(self, phrase, *, database=None, limit=10):
        return [{"keyword": f"is {phrase.lower()} worth it", "search_volume": 90}][:limit]


class StubSettings:
    groq_api_key = None
    groq_model = "stub"


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_parse_semrush_csv_normalizes_values():
    rows = keyword_intel._parse_semrush_csv(
        "Keyword;Search Volume;CPC;Competition\ncolosseum tickets;1000;1.25;0.48\n"
    )

    assert rows == [
        {
            "keyword": "colosseum tickets",
            "search_volume": 1000,
            "cpc": 1.25,
            "competition": 0.48,
        }
    ]


def test_semrush_nothing_found_is_empty_result(monkeypatch):
    class Response:
        text = "ERROR 50 :: NOTHING FOUND"

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url, params):
            return Response()

    class Settings:
        semrush_api_key = "key"
        semrush_api_base_url = "https://api.semrush.com/"
        semrush_database = "us"

    monkeypatch.setattr(keyword_intel.httpx, "Client", Client)

    assert keyword_intel.SemrushClient(Settings()).related_keywords("missing") == []


def test_fetch_keyword_intel_stores_stubbed_semrush_response():
    db = make_session()
    ingestion.ingest_product(db, BASE_PRODUCT)

    result, status_code, error = keyword_intel.fetch_keyword_intel(
        db,
        "prod_colosseum_skip",
        database="us",
        limit=5,
        client=StubSemrushClient(),
    )

    assert status_code is None
    assert error is None
    assert result["target_phrase"] == "Colosseum Skip-the-Line Tour"
    assert result["database"] == "us"
    assert result["keywords"][0]["search_volume"] == 1000
    assert result["questions"][0]["keyword"] == "is colosseum skip-the-line tour worth it"


def test_drafting_context_includes_keyword_intel():
    db = make_session()
    ingestion.ingest_product(db, BASE_PRODUCT)
    keyword_intel.fetch_keyword_intel(
        db,
        "prod_colosseum_skip",
        client=StubSemrushClient(),
    )

    result, _, _ = drafting.draft_entity(
        db,
        "prod_colosseum_skip",
        llm=drafting.LLMAdapter(settings=StubSettings()),
    )

    assert "Search demand context includes: colosseum skip-the-line tour." in result["body"]
