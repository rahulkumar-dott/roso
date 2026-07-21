from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.entities import Destination, Product
from app.services import admin, audit, ingestion, model_c, publisher


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


class _FakeViatorClient:
    """Stand-in for ViatorClient().destinations() in tests - no live API call."""

    def destinations(self):
        return [
            {
                "entity_id": "dest_viator_999",
                "name": "Rome",
                "country": "Italy",
                "region": None,
                "city": "Rome",
                "destination_level": "CITY",
                "source": "viator",
                "description": None,
                "images": [],
                "lat": 41.9,
                "lng": 12.5,
                "viator_destination_id": 999,
                "raw_viator": {"destinationId": 999, "name": "Rome", "type": "CITY", "parentDestinationId": 1},
            },
            {
                "entity_id": "dest_viator_1000",
                "name": "Newtown",
                "country": "Italy",
                "region": None,
                "city": "Newtown",
                "destination_level": "CITY",
                "source": "viator",
                "description": None,
                "images": [],
                "lat": 1.0,
                "lng": 1.0,
                "viator_destination_id": 1000,
                "raw_viator": {"destinationId": 1000, "name": "Newtown", "type": "CITY", "parentDestinationId": 1},
            },
        ]


def test_admin_sync_viator_flags_duplicate_and_pending_queue(monkeypatch):
    db = make_session()
    seed(db)  # creates dest_rome (Italy, CITY, approved) + a linked product

    monkeypatch.setattr("app.services.viator.ViatorClient", _FakeViatorClient)

    result = admin.sync_viator_destinations(db)

    assert result["synced"] == 2
    created_by_id = {row["entity_id"]: row for row in result["created"]}
    assert created_by_id["dest_viator_999"]["possible_duplicate_of"] == "dest_rome"
    assert created_by_id["dest_viator_1000"]["possible_duplicate_of"] is None

    pending = admin.pending_destinations(db)["pending"]
    assert {row["entity_id"] for row in pending} == {"dest_viator_999", "dest_viator_1000"}
    new_rome = db.scalar(select(Destination).where(Destination.entity_id == "dest_viator_999"))
    assert new_rome.review_status == "pending_review"


def test_admin_approve_reject_and_merge_destination(monkeypatch):
    db = make_session()
    seed(db)
    monkeypatch.setattr("app.services.viator.ViatorClient", _FakeViatorClient)
    admin.sync_viator_destinations(db)

    approved = admin.approve_destination(db, "dest_viator_1000")
    assert approved["review_status"] == "approved"

    rejected = admin.reject_destination(db, "dest_viator_999")
    assert rejected["review_status"] == "rejected"

    ingestion.ingest_product(
        db,
        {
            "entity_id": "prod_newtown_ticket",
            "destination_entity_id": "dest_viator_1000",
            "name": "Newtown Ticket",
            "category_group": "02_tickets",
            "source": "internal",
            "title": "Newtown Ticket",
            "description": "A ticket in Newtown.",
            "highlights": [],
            "images": [],
            "options": [],
            "inclusions": [],
            "price": 10,
            "currency": "EUR",
        },
    )

    merged = admin.merge_destination(db, "dest_viator_1000", "dest_rome")
    assert merged["errors"] == []
    assert merged["products_reassigned"] == 1

    moved_product = db.scalar(select(Product).where(Product.entity_id == "prod_newtown_ticket"))
    assert moved_product.destination_entity_id == "dest_rome"
    merged_destination = db.scalar(select(Destination).where(Destination.entity_id == "dest_viator_1000"))
    assert merged_destination.review_status == "rejected"

    actions = [entry["action"] for entry in audit.recent(db, limit=10)]
    assert "destination_approve" in actions
    assert "destination_reject" in actions
    assert "destination_merge" in actions


def test_admin_product_debug_and_content_similarity():
    db = make_session()
    seed(db)
    model_c.bulk_auto_confirm(db)

    debug = admin.product_debug(db, "prod_rome_ticket")
    assert debug["diff_history"][0]["to_version"] == 1
    assert debug["diff_history"][0]["severity"] == "MAJOR"

    ingestion.ingest_product(
        db,
        {
            "entity_id": "prod_rome_ticket",
            "destination_entity_id": "dest_rome",
            "name": "Rome Ticket",
            "category_group": "02_tickets",
            "source": "internal",
            "title": "Rome Ticket",
            "description": "A completely different revised description entirely for v2.",
            "highlights": ["Entry", "Updated logistics"],
            "images": ["ticket_v2.jpg"],
            "options": [{"name": "Standard"}],
            "inclusions": ["Ticket"],
            "price": 55,
            "currency": "EUR",
            "rating": 4.9,
            "review_count": 210,
            "availability_slots": ["09:00"],
        },
    )
    debug_v2 = admin.product_debug(db, "prod_rome_ticket")
    assert len(debug_v2["diff_history"]) == 2

    similarity = admin.content_similarity(db)
    assert isinstance(similarity["items"], list)


def test_admin_site_config_defaults_and_update():
    db = make_session()

    config = admin.site_config(db)
    assert config["cookie_consent_enabled"] is True
    assert len(config["header_nav_menu"]) == 5
    assert set(config["footer_sections"].keys()) == {"About", "Explore", "Support", "Legal"}

    result = admin.update_site_config(db, "cookie_consent_enabled", False)
    assert result["errors"] == []

    updated = admin.site_config(db)
    assert updated["cookie_consent_enabled"] is False

    entries = audit.recent(db, limit=5)
    assert entries[0]["action"] == "site_config_update"


def test_admin_update_site_config_rejects_unknown_key():
    db = make_session()

    result = admin.update_site_config(db, "not_a_real_key", "value")

    assert result["errors"] == ["Unknown site-config key 'not_a_real_key'"]
