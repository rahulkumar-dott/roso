from app.services import diff_engine

BASE_PRODUCT = {
    "title": "Colosseum Tour",
    "description": "Skip the line.",
    "highlights": ["Guide included"],
    "hours": "09:00-17:00",
    "address": "Rome",
    "lat": 41.89,
    "lng": 12.49,
    "phone": "+39 06 0000",
    "rating": 4.7,
    "review_count": 100,
    "images": ["a.jpg"],
    "videos": [],
    "options": [{"name": "Standard"}],
    "inclusions": ["Guide"],
    "cancellation_policy": "Free cancellation",
    "price": 69.0,
    "currency": "EUR",
    "availability_slots": ["09:00"],
}


def test_first_ingestion_is_always_major():
    hashes = diff_engine.compute_hashes("product", BASE_PRODUCT)
    severity, changed = diff_engine.classify_severity(None, hashes)
    assert severity == "MAJOR"
    assert set(changed) == set(diff_engine.ALL_DOMAINS)


def test_no_change_is_none():
    hashes = diff_engine.compute_hashes("product", BASE_PRODUCT)
    severity, changed = diff_engine.classify_severity(hashes, hashes)
    assert severity == "NONE"
    assert changed == []


def test_description_change_is_major():
    old_hashes = diff_engine.compute_hashes("product", BASE_PRODUCT)
    new_product = {**BASE_PRODUCT, "description": "Completely rewritten description."}
    new_hashes = diff_engine.compute_hashes("product", new_product)

    severity, changed = diff_engine.classify_severity(old_hashes, new_hashes)
    assert severity == "MAJOR"
    assert "content_hash" in changed


def test_image_change_is_medium():
    old_hashes = diff_engine.compute_hashes("product", BASE_PRODUCT)
    new_product = {**BASE_PRODUCT, "images": ["a.jpg", "b.jpg"]}
    new_hashes = diff_engine.compute_hashes("product", new_product)

    severity, changed = diff_engine.classify_severity(old_hashes, new_hashes)
    assert severity == "MEDIUM"
    assert changed == ["media_hash"]


def test_price_change_is_minor():
    old_hashes = diff_engine.compute_hashes("product", BASE_PRODUCT)
    new_product = {**BASE_PRODUCT, "price": 79.0}
    new_hashes = diff_engine.compute_hashes("product", new_product)

    severity, changed = diff_engine.classify_severity(old_hashes, new_hashes)
    assert severity == "MINOR"
    assert changed == ["realtime_offer_hash"]


def test_major_wins_over_simultaneous_medium_and_minor_changes():
    old_hashes = diff_engine.compute_hashes("product", BASE_PRODUCT)
    new_product = {
        **BASE_PRODUCT,
        "description": "Rewritten.",
        "images": ["a.jpg", "b.jpg"],
        "price": 79.0,
    }
    new_hashes = diff_engine.compute_hashes("product", new_product)

    severity, changed = diff_engine.classify_severity(old_hashes, new_hashes)
    assert severity == "MAJOR"
    assert set(changed) == {"content_hash", "media_hash", "realtime_offer_hash"}


def test_destination_has_no_offer_domains():
    destination = {"name": "Rome", "description": "The Eternal City", "country": "Italy"}
    hashes = diff_engine.compute_hashes("destination", destination)
    same_hashes = diff_engine.compute_hashes(
        "destination", {**destination, "price": 999}  # unrelated field, ignored for destinations
    )
    assert hashes["offer_hash"] == same_hashes["offer_hash"]
    assert hashes["realtime_offer_hash"] == same_hashes["realtime_offer_hash"]
