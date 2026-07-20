from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.services import admin, ingestion, model_c, publisher


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def seed(db):
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
    ingestion.ingest_product(
        db,
        {
            "entity_id": "prod_rome_ticket",
            "destination_entity_id": "dest_rome",
            "name": "Rome Ticket",
            "category_group": "02_tickets",
            "source": "internal",
            "title": "Rome Ticket",
            "description": "A complete ticket product.",
            "highlights": ["Entry", "Clear logistics"],
            "images": ["ticket.jpg"],
            "options": [{"name": "Standard"}],
            "inclusions": ["Ticket"],
            "price": 50,
            "currency": "EUR",
            "rating": 4.8,
            "review_count": 200,
            "availability_slots": ["09:00"],
        },
    )
    model_c.recompute(db)


def test_admin_overview_and_destinations():
    db = make_session()
    seed(db)
    publisher.publish_city_page(db, "dest_rome")
    publisher.publish_country_page(db, "Italy")

    overview = admin.overview(db)
    destinations = admin.destinations(db)

    assert overview["destinations"] == 1
    assert overview["products"] == 1
    assert overview["published_records"] == 2
    assert destinations["countries"][0]["country"] == "Italy"
    assert destinations["countries"][0]["published"] is True
    assert destinations["countries"][0]["cities"][0]["published"] is True


def test_admin_products_exposes_product_ops_fields():
    db = make_session()
    seed(db)
    model_c.bulk_auto_confirm(db)

    products = admin.products(db)["products"]

    assert products[0]["entity_id"] == "prod_rome_ticket"
    assert products[0]["in_pool"] is True
    assert products[0]["in_set"] is True
    assert products[0]["image_url"] == "ticket.jpg"
    assert products[0]["price_from"] == 50
