"""Seed fresh demo_-prefixed destinations/products so the frontend has real
published tour pages to render, independent of whatever else already exists
in the (shared, possibly stale) backend database.

Cities/countries mirror the real rosotravel.com nav (4 countries x 4 cities)
so the demo reads as plausible. Products per city are generated from a small
set of templates rather than hand-written, since the point is to exercise
the pipeline (ingest -> Model C -> draft -> publish), not to hand-author 48
unique product listings.

Usage: uv run python scripts/seed_demo.py [base_url]
"""

import re
import sys

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

# (country, city, lat, lng) - a subset of rosotravel.com's real nav.
CITIES = [
    ("Italy", "Rome", 41.9028, 12.4964),
    ("Italy", "Florence", 43.7696, 11.2558),
    ("Italy", "Venice", 45.4408, 12.3155),
    ("Italy", "Milan", 45.4642, 9.1900),
    ("Spain", "Barcelona", 41.3874, 2.1686),
    ("Spain", "Madrid", 40.4168, -3.7038),
    ("Spain", "Seville", 37.3891, -5.9845),
    ("Spain", "Malaga", 36.7213, -4.4214),
    ("United Kingdom", "London", 51.5074, -0.1278),
    ("United Kingdom", "Edinburgh", 55.9533, -3.1883),
    ("United Kingdom", "Manchester", 53.4808, -2.2426),
    ("United Kingdom", "Liverpool", 53.4084, -2.9916),
    ("Austria", "Vienna", 48.2082, 16.3738),
    ("Austria", "Salzburg", 47.8095, 13.0550),
    ("Austria", "Graz", 47.0707, 15.4395),
    ("Austria", "Linz", 48.3069, 14.2858),
]

# Product templates applied to every city. Keeps archetypes varied (standard
# walking tour / skip-the-line ticket / food & wine) so Model C has more than
# one archetype to pick winners across, matching the "rails never repeat an
# archetype" rule.
PRODUCT_TEMPLATES = [
    {
        "suffix": "highlights_walk",
        "title": "{city} Highlights Walking Tour",
        "category_group": "01_tours",
        "description": (
            "Explore the must-see landmarks of {city} on foot with a knowledgeable local "
            "guide, covering the city's history and best photo spots."
        ),
        "highlights": ["Local expert guide", "Small group walking tour", "Top landmarks covered"],
        "hours": "10:00-13:00",
        "inclusions": ["Local guide", "Walking route map"],
        "options": [{"name": "Standard", "group_size": "small"}],
        "cancellation_policy": "Free cancellation up to 24 hours before the experience starts",
        "base_price": 45.0,
        "availability_slots": ["10:00", "14:00"],
    },
    {
        "suffix": "skip_the_line",
        "title": "{city} Skip-the-Line Landmark Tour",
        "category_group": "02_tickets",
        "description": (
            "Skip the ticket lines at {city}'s most iconic landmark with guaranteed entry "
            "and a guided tour of the highlights."
        ),
        "highlights": ["Skip-the-line entry", "Guided commentary", "Photo stops included"],
        "hours": "09:00-17:00",
        "inclusions": ["Skip-the-line ticket", "Guide"],
        "options": [{"name": "Standard", "group_size": "medium"}],
        "cancellation_policy": "Non-refundable",
        "base_price": 65.0,
        "availability_slots": ["09:00", "11:00", "15:00"],
    },
    {
        "suffix": "food_wine",
        "title": "{city} Food & Wine Tasting Experience",
        "category_group": "01_tours",
        "description": (
            "Taste the best local food and wine in {city} on a small-group tasting walk "
            "through the city's favorite spots."
        ),
        "highlights": ["Multiple tastings", "Local wine pairing", "Small group"],
        "hours": "18:00-21:00",
        "inclusions": ["Food tastings", "Wine pairing", "Local guide"],
        "options": [{"name": "Standard", "group_size": "small"}],
        "cancellation_policy": "Free cancellation up to 24 hours before the experience starts",
        "base_price": 85.0,
        "availability_slots": ["18:00"],
    },
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _image_url(seed: str, width: int = 900, height: int = 600) -> str:
    return f"https://picsum.photos/seed/roso-{_slug(seed)}/{width}/{height}"


def build_destinations() -> list[dict]:
    destinations = []
    for country, city, lat, lng in CITIES:
        destinations.append(
            {
                "entity_id": f"demo_dest_{_slug(city)}",
                "name": city,
                "country": country,
                "region": country,
                "city": city,
                "source": "viator",
                "description": f"Discover {city}, {country} with Rosotravel's curated tours and tickets.",
                "images": [_image_url(f"{country}-{city}-hero", 1200, 700)],
                "lat": lat,
                "lng": lng,
            }
        )
    return destinations


def build_products() -> list[dict]:
    products = []
    index = 0
    for country, city, lat, lng in CITIES:
        dest_id = f"demo_dest_{_slug(city)}"
        for template in PRODUCT_TEMPLATES:
            rating = round(4.3 + (index % 5) * 0.1, 1)
            review_count = 400 + (index * 137) % 5000
            price = round(template["base_price"] + (index * 7) % 50, 2)
            products.append(
                {
                    "entity_id": f"demo_prod_{_slug(city)}_{template['suffix']}",
                    "destination_entity_id": dest_id,
                    "name": template["title"].format(city=city),
                    "category_group": template["category_group"],
                    "source": "viator",
                    "title": template["title"].format(city=city),
                    "description": template["description"].format(city=city),
                    "highlights": template["highlights"],
                    "hours": template["hours"],
                    "address": f"{city} city center, {country}",
                    "lat": lat,
                    "lng": lng,
                    "phone": "+1 555 0100",
                    "rating": rating,
                    "review_count": review_count,
                    "images": [_image_url(f"{city}-{template['suffix']}")],
                    "videos": [],
                    "options": template["options"],
                    "inclusions": template["inclusions"],
                    "cancellation_policy": template["cancellation_policy"],
                    "price": price,
                    "currency": "EUR",
                    "availability_slots": template["availability_slots"],
                }
            )
            index += 1
    return products


def main() -> None:
    destinations = build_destinations()
    products = build_products()

    # Drafting loads a local sentence-transformer model on first use and calls
    # live Groq/Google Places APIs when configured - both can take a while
    # the first time, hence the generous timeout.
    with httpx.Client(base_url=BASE_URL, timeout=120.0) as client:
        print(f"Ingesting {len(destinations)} destinations...")
        client.post("/ingest/destinations", json=destinations).raise_for_status()

        print(f"Ingesting {len(products)} products...")
        client.post("/ingest/products", json=products).raise_for_status()

        print("Recomputing Model C (Pool + archetypes)...")
        client.post("/model-c/recompute").raise_for_status()

        print("Bulk-confirming Pool -> Set for the demo...")
        client.post("/model-c/bulk-auto-confirm").raise_for_status()

        print("Publishing city pages...")
        for destination in destinations:
            publish_city = client.post(f"/cities/{destination['entity_id']}/publish")
            if publish_city.status_code != 200:
                print(f"  ! city publish failed: {destination['entity_id']} {publish_city.json()}")

        print("Publishing country pages...")
        for country in sorted({country for country, _city, _lat, _lng in CITIES}):
            publish_country = client.post(f"/countries/{country}/publish")
            if publish_country.status_code != 200:
                print(f"  ! country publish failed: {country} {publish_country.json()}")

        for i, product in enumerate(products, start=1):
            entity_id = product["entity_id"]
            print(f"[{i}/{len(products)}] drafting + publishing {entity_id}...")
            draft = client.post(f"/entities/{entity_id}/draft")
            if draft.status_code != 200:
                print(f"  ! draft skipped: {draft.json()}")
                continue
            publish = client.post(f"/entities/{entity_id}/publish")
            if publish.status_code != 200:
                print(f"  ! publish failed: {publish.json()}")

        print("\nDone. Try, e.g.:")
        print(f"  {BASE_URL}/published/country_italy")
        print(f"  {BASE_URL}/published/demo_dest_rome")
        print(f"  {BASE_URL}/cities/demo_dest_rome/picks")
        print(f"  {BASE_URL}/published/demo_prod_rome_highlights_walk")


if __name__ == "__main__":
    main()
