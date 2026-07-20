from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.services import ingestion, model_c


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def ingest_city(db):
    ingestion.ingest_destination(
        db,
        {
            "entity_id": "dest_rome",
            "name": "Rome",
            "country": "Italy",
            "region": "Lazio",
            "city": "Rome",
            "source": "viator",
            "description": "The Eternal City.",
            "images": ["rome.jpg"],
            "lat": 41.9028,
            "lng": 12.4964,
        },
    )


def product(entity_id, title, category, price, rating, review_count):
    return {
        "entity_id": entity_id,
        "destination_entity_id": "dest_rome",
        "name": title,
        "category_group": category,
        "source": "viator",
        "title": title,
        "description": f"{title} description.",
        "highlights": ["Clear logistics", "Strong reviews"],
        "images": [f"{entity_id}.jpg"],
        "price": price,
        "currency": "EUR",
        "rating": rating,
        "review_count": review_count,
        "options": [{"name": "Standard"}],
        "inclusions": ["Ticket"],
        "cancellation_policy": "Free cancellation",
        "availability_slots": ["09:00"],
    }


def ingest_products(db):
    items = [
        product("prod_skip_value", "Colosseum Skip-the-Line Ticket", "02_tickets", 40, 4.7, 800),
        product("prod_private", "Private Colosseum Guided Tour", "01_tours", 180, 4.9, 300),
        product("prod_food", "Rome Food and Wine Walk", "01_tours", 90, 4.8, 220),
        product("prod_weak", "Weak Rome Tour", "01_tours", 0, None, None),
    ]
    for item in items:
        ingestion.ingest_product(db, item)


def setup_model_c(db):
    ingest_city(db)
    ingest_products(db)
    return model_c.recompute(db)


def test_recompute_scores_pool_and_archetypes():
    db = make_session()
    result = setup_model_c(db)

    assert result["products_scored"] == 4
    assert result["products_in_pool"] == 3
    assert result["archetypes"] >= 3

    weak = model_c.explain_product(db, "prod_weak")
    assert weak["in_pool"] is False
    assert weak["reasons"] == ["below_quality_threshold"]


def test_city_picks_include_product_media_and_price_fields():
    db = make_session()
    setup_model_c(db)
    model_c.bulk_auto_confirm(db)

    picks = model_c.city_picks(db, "dest_rome")

    assert picks["picks"][0]["image_url"].endswith(".jpg")
    assert picks["picks"][0]["price_from"] is not None
    assert picks["picks"][0]["currency"] == "EUR"


def test_city_picks_require_set_membership_and_are_sparse_before_confirmation():
    db = make_session()
    setup_model_c(db)

    picks = model_c.city_picks(db, "dest_rome")

    assert picks["suppressed"] is True
    assert picks["reason"] == "set_below_sparse_threshold"


def test_city_picks_use_set_only_and_do_not_repeat_archetypes():
    db = make_session()
    setup_model_c(db)
    model_c.bulk_auto_confirm(db)

    picks = model_c.city_picks(db, "dest_rome")
    archetypes = [pick["archetype"] for pick in picks["picks"]]
    product_ids = {pick["product_id"] for pick in picks["picks"]}

    assert picks["suppressed"] is False
    assert "prod_weak" not in product_ids
    assert len(archetypes) == len(set(archetypes))
    assert picks["decision_proof"]["why_these_picks"]


def test_explain_product_reports_winner_slots_and_competitors():
    db = make_session()
    setup_model_c(db)
    model_c.bulk_auto_confirm(db)
    model_c.city_picks(db, "dest_rome")

    explanation = model_c.explain_product(db, "prod_skip_value")

    assert explanation["in_pool"] is True
    assert explanation["in_set"] is True
    assert explanation["quality_score"] is not None
    assert explanation["archetypes"]
    assert explanation["winner_slots"]


def test_country_rollup_uses_city_outputs():
    db = make_session()
    setup_model_c(db)
    model_c.bulk_auto_confirm(db)

    rollup = model_c.country_rollup(db, "Italy")

    assert rollup["suppressed"] is False
    assert rollup["top_cities"][0]["city_id"] == "dest_rome"
    assert rollup["top_products"]
