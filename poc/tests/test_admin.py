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


def test_admin_create_country_creates_internal_taxonomy_node():
    db = make_session()

    result = admin.create_country(db, "Austria", description="Austria travel planning.")
    destinations = admin.destinations(db)

    assert result["errors"] == []
    assert result["entity_id"] == "dest_country_austria"
    assert result["entity_type"] == "destination"
    assert destinations["countries"][0]["country"] == "Austria"
    assert destinations["countries"][0]["has_country_node"] is True
    assert destinations["countries"][0]["source"] == "internal"
    assert destinations["countries"][0]["cities"] == []


def test_admin_create_country_rejects_duplicate_country_node():
    db = make_session()

    admin.create_country(db, "Austria")
    duplicate = admin.create_country(db, " Austria ")

    assert duplicate["errors"] == ["Country 'Austria' already has a country taxonomy node"]
    assert duplicate["entity_id"] == "dest_country_austria"


def test_admin_create_region_city_and_attraction_taxonomy_nodes():
    db = make_session()

    region = admin.create_region(db, "Austria", "Vienna Region")
    city = admin.create_city(db, "Austria", "Vienna", region="Vienna Region")
    attraction = admin.create_attraction(
        db,
        "Schonbrunn Palace",
        destination_entity_id="dest_city_austria_vienna",
        official_website="https://www.schoenbrunn.at/",
    )
    destinations = admin.destinations(db)

    assert region["errors"] == []
    assert region["entity_id"] == "dest_region_austria_vienna-region"
    assert city["errors"] == []
    assert city["entity_id"] == "dest_city_austria_vienna"
    assert attraction["errors"] == []
    assert attraction["entity_id"] == "attr_internal_austria_vienna_schonbrunn-palace"
    assert destinations["countries"][0]["regions"][0]["name"] == "Vienna Region"
    assert destinations["countries"][0]["cities"][0]["name"] == "Vienna"
    assert destinations["countries"][0]["cities"][0]["attractions_count"] == 1


def test_admin_publishing_exposes_index_state():
    db = make_session()
    admin.create_country(db, "Austria")
    publisher.publish_country_page(db, "Austria")

    row = admin.publishing(db)["records"][0]

    assert row["entity_type"] == "country"
    assert row["index_state"] == "noindex"
