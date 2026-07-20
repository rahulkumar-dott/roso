from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings


DEFAULT_BASE_URL = "https://api.sandbox.viator.com/partner"


class ViatorConfigError(RuntimeError):
    pass


class ViatorClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.viator_api_key:
            raise ViatorConfigError("VIATOR_API_KEY is not configured")
        self.base_url = (settings.viator_api_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = settings.viator_api_key
        self.partner_id = settings.viator_partner_id

    @property
    def headers(self) -> dict[str, str]:
        return {
            "exp-api-key": self.api_key,
            "Accept": "application/json;version=2.0",
            "Accept-Language": "en-US",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=120) as client:
            response = client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()

    def destinations(self, limit: int | None = None) -> list[dict[str, Any]]:
        payload = self._get("/destinations")
        rows = _extract_list(payload, "destinations")
        if limit:
            rows = rows[:limit]
        return [_map_destination(row) for row in rows if _map_destination(row)]

    def _post(self, path: str, json_body: dict[str, Any]) -> dict[str, Any] | list[Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=120) as client:
            response = client.post(url, headers={**self.headers, "Content-Type": "application/json"}, json=json_body)
            response.raise_for_status()
            return response.json()

    def attractions_search(
        self,
        *,
        destination_id: int,
        top_x: str = "1-12",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._post(
            "/attractions/search",
            {"destinationId": destination_id, "topX": top_x},
        )
        rows = _extract_list(payload, "attractions")
        if limit:
            rows = rows[:limit]
        return [_map_attraction(row, destination_id) for row in rows if _map_attraction(row, destination_id)]

    def products_modified_since(
        self,
        *,
        count: int = 50,
        modified_since: str | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"count": min(max(count, 1), 500)}
        if modified_since:
            params["modified-since"] = modified_since
        if cursor:
            params["cursor"] = cursor
        if self.partner_id:
            params["campaign-value"] = self.partner_id

        payload = self._get("/products/modified-since", params=params)
        rows = _extract_list(payload, "products")
        if limit:
            rows = rows[:limit]
        return [_map_product(row) for row in rows if _map_product(row)]


def _extract_list(payload: dict[str, Any] | list[Any], preferred_key: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    value = payload.get(preferred_key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    for fallback in ("data", "items", "results"):
        value = payload.get(fallback)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _map_destination(row: dict[str, Any]) -> dict[str, Any]:
    destination_id = row.get("destinationId") or row.get("id")
    name = row.get("name") or row.get("destinationName")
    if not destination_id or not name:
        return {}

    center = row.get("center") if isinstance(row.get("center"), dict) else {}
    destination_type = (row.get("type") or "").upper()
    is_city_like = destination_type in {"CITY", "TOWN", "VILLAGE"}
    return {
        "entity_id": f"dest_viator_{destination_id}",
        "name": str(name),
        "country": _country_from_destination(row),
        "region": str(name) if destination_type == "REGION" else (row.get("region") or row.get("parentDestinationName")),
        "city": str(name) if is_city_like else None,
        "destination_level": destination_type or "CITY",
        "source": "viator",
        "description": row.get("description"),
        "images": [],
        "lat": center.get("latitude"),
        "lng": center.get("longitude"),
        "viator_destination_id": destination_id,
        "viator_destination_type": row.get("type"),
        "lookup_id": row.get("lookupId"),
        "default_currency_code": row.get("defaultCurrencyCode"),
        "time_zone": row.get("timeZone"),
        "raw_viator": row,
    }


def _country_from_destination(row: dict[str, Any]) -> str:
    if row.get("country"):
        return str(row["country"])
    if row.get("countryName"):
        return str(row["countryName"])
    if (row.get("type") or "").upper() == "COUNTRY" and row.get("name"):
        return str(row["name"])
    return "Unknown"


def _map_attraction(row: dict[str, Any], destination_id: int) -> dict[str, Any]:
    attraction_id = row.get("attractionId")
    name = row.get("name")
    if not attraction_id or not name:
        return {}

    center = row.get("center") if isinstance(row.get("center"), dict) else {}
    reviews = row.get("reviews") if isinstance(row.get("reviews"), dict) else {}
    images = row.get("images") if isinstance(row.get("images"), list) else []
    image_urls = [img.get("url") for img in images if isinstance(img, dict) and img.get("url")]

    return {
        "entity_id": f"attr_viator_{attraction_id}",
        "destination_entity_id": f"dest_viator_{destination_id}",
        "name": str(name),
        "source": "viator",
        "images": image_urls,
        "lat": center.get("latitude"),
        "lng": center.get("longitude"),
        "rating": reviews.get("combinedAverageRating"),
        "review_count": reviews.get("totalReviews"),
        "product_count": row.get("productCount"),
        "viator_attraction_id": attraction_id,
        "viator_product_codes": row.get("productCodes") or [],
    }


def _map_product(row: dict[str, Any]) -> dict[str, Any]:
    code = row.get("productCode") or row.get("code")
    title = row.get("title") or row.get("name")
    if not code or not title:
        return {}

    primary_destination = _primary_destination_ref(row.get("destinations"))
    images = _image_urls(row)
    rating, review_count = _rating(row)
    price, currency = _price(row)

    return {
        "entity_id": f"prod_viator_{code}",
        "destination_entity_id": f"dest_viator_{primary_destination}" if primary_destination else None,
        "name": str(title),
        "category_group": _category_group(row),
        "source": "viator",
        "title": title,
        "description": row.get("description"),
        "highlights": _highlights(row),
        "hours": None,
        "address": _address(row),
        "lat": None,
        "lng": None,
        "phone": None,
        "rating": rating,
        "review_count": review_count,
        "images": images,
        "videos": _video_urls(row),
        "options": row.get("productOptions") or [],
        "inclusions": _inclusions(row),
        "cancellation_policy": _cancellation_policy(row),
        "price": price,
        "currency": currency,
        "availability_slots": [],
        "viator_product_code": code,
        "viator_primary_destination_id": primary_destination,
        "viator_product_url": row.get("productUrl"),
        "status": row.get("status"),
        "last_ingested_at": datetime.now(UTC).isoformat(),
        "raw_viator": row,
    }


def _primary_destination_ref(destinations: Any) -> str | None:
    if not isinstance(destinations, list):
        return None
    for destination in destinations:
        if isinstance(destination, dict) and destination.get("primary"):
            return str(destination.get("ref")) if destination.get("ref") else None
    for destination in destinations:
        if isinstance(destination, dict) and destination.get("ref"):
            return str(destination["ref"])
    return None


def _category_group(row: dict[str, Any]) -> str:
    tags = row.get("tags") if isinstance(row.get("tags"), list) else []
    text = " ".join(str(tag).lower() for tag in tags) + " " + str(row.get("title", "")).lower()
    if "transfer" in text or "transport" in text:
        return "03_transfers"
    if "ticket" in text or "admission" in text:
        return "02_tickets"
    return "01_tours"


def _highlights(row: dict[str, Any]) -> list[str]:
    highlights = row.get("highlights")
    if isinstance(highlights, list):
        return [str(item) for item in highlights if item]
    return []


def _image_urls(row: dict[str, Any]) -> list[str]:
    images = row.get("images")
    if not isinstance(images, list):
        return []
    urls: list[str] = []
    for image in images:
        if isinstance(image, str):
            urls.append(image)
        elif isinstance(image, dict):
            url = image.get("url") or image.get("thumbnailURL")
            variants = image.get("variants")
            if not url and isinstance(variants, list) and variants:
                first = variants[0]
                if isinstance(first, dict):
                    url = first.get("url")
            if url:
                urls.append(str(url))
    return urls


def _video_urls(row: dict[str, Any]) -> list[str]:
    videos = row.get("videos")
    if not isinstance(videos, list):
        return []
    return [str(video.get("url") or video) for video in videos if video]


def _inclusions(row: dict[str, Any]) -> list[str]:
    inclusions = row.get("inclusions")
    if not isinstance(inclusions, list):
        return []
    output: list[str] = []
    for item in inclusions:
        if isinstance(item, str):
            output.append(item)
        elif isinstance(item, dict):
            text = item.get("description") or item.get("otherDescription") or item.get("category")
            if text:
                output.append(str(text))
    return output


def _cancellation_policy(row: dict[str, Any]) -> str | None:
    policy = row.get("cancellationPolicy")
    if isinstance(policy, str):
        return policy
    if isinstance(policy, dict):
        return policy.get("description") or policy.get("type")
    return None


def _rating(row: dict[str, Any]) -> tuple[float | None, int | None]:
    reviews = row.get("reviews") if isinstance(row.get("reviews"), dict) else {}
    rating = reviews.get("combinedAverageRating") or reviews.get("averageRating") or row.get("rating")
    count = reviews.get("totalReviews") or reviews.get("reviewCount") or row.get("reviewCount")
    try:
        parsed_rating = float(rating) if rating is not None else None
    except (TypeError, ValueError):
        parsed_rating = None
    try:
        parsed_count = int(count) if count is not None else None
    except (TypeError, ValueError):
        parsed_count = None
    return parsed_rating, parsed_count


def _price(row: dict[str, Any]) -> tuple[float | None, str | None]:
    pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
    summary = pricing.get("summary") if isinstance(pricing.get("summary"), dict) else {}
    amount = (
        summary.get("fromPrice")
        or summary.get("fromPriceBeforeDiscount")
        or pricing.get("fromPrice")
        or row.get("price")
    )
    currency = summary.get("currency") or pricing.get("currency") or row.get("currency")
    try:
        parsed_amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        parsed_amount = None
    return parsed_amount, str(currency) if currency else None


def _address(row: dict[str, Any]) -> str | None:
    logistics = row.get("logistics") if isinstance(row.get("logistics"), dict) else {}
    start = logistics.get("start") if isinstance(logistics.get("start"), list) else []
    if not start:
        return None
    location = start[0].get("location") if isinstance(start[0], dict) else None
    if not isinstance(location, dict):
        return None
    address = location.get("address")
    if isinstance(address, str):
        return address
    if isinstance(address, dict):
        return ", ".join(str(v) for v in address.values() if v)
    return None
