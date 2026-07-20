from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import Product
from app.services import ingestion
from app.services.viator import _map_destination, _map_product


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_map_viator_destination_to_ingest_shape():
    mapped = _map_destination(
        {
            "destinationId": 343,
            "name": "Bangkok",
            "type": "CITY",
            "parentDestinationName": "Thailand",
            "defaultCurrencyCode": "THB",
            "timeZone": "Asia/Bangkok",
            "center": {"latitude": 13.7563, "longitude": 100.5018},
        }
    )

    assert mapped["entity_id"] == "dest_viator_343"
    assert mapped["name"] == "Bangkok"
    assert mapped["city"] == "Bangkok"
    assert mapped["lat"] == 13.7563
    assert mapped["lng"] == 100.5018


def test_map_viator_product_keeps_supplier_destination_ref():
    mapped = _map_product(
        {
            "productCode": "196194P1",
            "title": "Try Dive Bangkok",
            "description": "Intro dive experience.",
            "destinations": [{"ref": "343", "primary": True}],
            "images": [{"variants": [{"url": "https://example.com/image.jpg"}]}],
            "reviews": {"combinedAverageRating": 4.8, "totalReviews": 12},
            "pricing": {"summary": {"fromPrice": 99.0, "currency": "USD"}},
            "inclusions": [{"description": "Instructor"}],
        }
    )

    assert mapped["entity_id"] == "prod_viator_196194P1"
    assert mapped["destination_entity_id"] == "dest_viator_343"
    assert mapped["viator_primary_destination_id"] == "343"
    assert mapped["images"] == ["https://example.com/image.jpg"]
    assert mapped["rating"] == 4.8
    assert mapped["review_count"] == 12
    assert mapped["price"] == 99.0
    assert mapped["currency"] == "USD"


def test_ingest_product_ignores_missing_destination_fk_but_keeps_raw_ref():
    db = make_session()
    payload = {
        "entity_id": "prod_viator_196194P1",
        "destination_entity_id": "dest_viator_343",
        "viator_primary_destination_id": "343",
        "name": "Try Dive Bangkok",
        "category_group": "01_tours",
        "source": "viator",
        "title": "Try Dive Bangkok",
        "description": "Intro dive experience.",
        "highlights": [],
        "images": [],
        "options": [],
        "inclusions": [],
        "price": 99.0,
        "currency": "USD",
        "availability_slots": [],
    }

    result = ingestion.ingest_product(db, payload)
    product = db.scalar(select(Product).where(Product.entity_id == "prod_viator_196194P1"))

    assert result["severity"] == "MAJOR"
    assert product is not None
    assert product.destination_entity_id is None
