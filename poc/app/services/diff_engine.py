"""SOW System 1.3: hash-based Diff Engine across 5 domains.

Only MAJOR severity ever queues AI drafting downstream (Phase 3) - MINOR and
MEDIUM changes are applied without touching the content pipeline. This module
is pure functions over dicts so it's trivially unit-testable without a DB.
"""

import hashlib
import json
from typing import Any

# Field-to-domain mapping per SOW section 1.3. Destinations don't carry
# commercial offer data, so those domains are simply always-empty (stable) for
# that entity type - never flagged as changed.
DOMAIN_FIELDS: dict[str, dict[str, list[str]]] = {
    "product": {
        "content_hash": ["title", "description", "highlights"],
        "factual_hash": ["hours", "address", "lat", "lng", "phone", "rating", "review_count"],
        "media_hash": ["images", "videos"],
        "offer_hash": ["options", "inclusions", "cancellation_policy"],
        "realtime_offer_hash": ["price", "currency", "availability_slots"],
    },
    "destination": {
        "content_hash": ["name", "description"],
        "factual_hash": ["country", "region", "city", "lat", "lng"],
        "media_hash": ["images"],
        "offer_hash": [],
        "realtime_offer_hash": [],
    },
    "attraction": {
        "content_hash": ["name", "description"],
        "factual_hash": ["country", "city", "lat", "lng", "official_website"],
        "media_hash": ["images"],
        "offer_hash": [],
        "realtime_offer_hash": [],
    },
}

MAJOR_DOMAINS = {"content_hash", "factual_hash"}
MEDIUM_DOMAINS = {"media_hash", "offer_hash"}
MINOR_DOMAINS = {"realtime_offer_hash"}

ALL_DOMAINS = ["content_hash", "factual_hash", "media_hash", "offer_hash", "realtime_offer_hash"]


def _hash_domain(payload: dict[str, Any], fields: list[str]) -> str:
    domain_data = {f: payload.get(f) for f in fields}
    serialized = json.dumps(domain_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_hashes(entity_type: str, payload: dict[str, Any]) -> dict[str, str]:
    mapping = DOMAIN_FIELDS[entity_type]
    return {domain: _hash_domain(payload, fields) for domain, fields in mapping.items()}


def classify_severity(
    old_hashes: dict[str, str] | None, new_hashes: dict[str, str]
) -> tuple[str, list[str]]:
    """Returns (severity, changed_domains).

    First ingestion (old_hashes is None) is always MAJOR - it needs the
    one-time initial AI draft per SOW section 1.2.
    """
    if old_hashes is None:
        return "MAJOR", list(new_hashes.keys())

    changed = [d for d in ALL_DOMAINS if new_hashes.get(d) != old_hashes.get(d)]
    if not changed:
        return "NONE", []

    changed_set = set(changed)
    if changed_set & MAJOR_DOMAINS:
        return "MAJOR", changed
    if changed_set & MEDIUM_DOMAINS:
        return "MEDIUM", changed
    if changed_set & MINOR_DOMAINS:
        return "MINOR", changed
    return "NONE", changed
