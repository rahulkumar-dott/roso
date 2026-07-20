"""Ingest real Viator COUNTRY and REGION destination rows for the 4 demo
countries, so the country page can show real Top Regions and real
Facts & Curiosities (currency/calling code/languages/timezone) instead of
inventing them. Cities are left as the existing demo_dest_* entities already
wired to Model C / published pages - this script only adds the country and
region levels above them.

Usage: uv run python scripts/seed_country_regions.py [base_url] [destinations_json_path]
"""

import json
import sys

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
DESTINATIONS_JSON = sys.argv[2] if len(sys.argv) > 2 else "/tmp/viator_destinations_raw.json"

COUNTRY_IDS = {
    "Italy": 57,
    "Spain": 67,
    "United Kingdom": 60457,
    "Austria": 44,
}


def _map(row: dict, *, level: str, country_name: str) -> dict:
    destination_id = row["destinationId"]
    center = row.get("center") or {}
    return {
        "entity_id": f"dest_viator_{destination_id}",
        "name": row["name"],
        "country": country_name,
        "region": row["name"] if level == "REGION" else None,
        "city": None,
        "destination_level": level,
        "source": "viator",
        "lat": center.get("latitude"),
        "lng": center.get("longitude"),
        "raw_viator": row,
    }


def main() -> None:
    with open(DESTINATIONS_JSON, encoding="utf-8") as f:
        rows = json.load(f)

    payload = []
    for country_name, country_id in COUNTRY_IDS.items():
        country_row = next(r for r in rows if r.get("type") == "COUNTRY" and r["destinationId"] == country_id)
        payload.append(_map(country_row, level="COUNTRY", country_name=country_name))

        regions = [r for r in rows if r.get("type") == "REGION" and r.get("parentDestinationId") == country_id]
        for region in regions:
            payload.append(_map(region, level="REGION", country_name=country_name))
        print(f"{country_name}: 1 country row + {len(regions)} region rows")

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        resp = client.post("/ingest/destinations", json=payload)
        resp.raise_for_status()
        print(f"\nIngested {len(resp.json())} country/region destination rows")


if __name__ == "__main__":
    main()
