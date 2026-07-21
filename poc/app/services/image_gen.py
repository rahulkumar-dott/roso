"""Nano Banana Pro (Gemini image model on Vertex AI) hero image generation.

WBS Country_Page sheet, Hero Image row: "Use an AI-generated hero visual
(Nano-banana pro generated) as no curated image exists for countries."
Country / Region hero images are generated this way; City / Attraction /
Product images come from CMS media / OTA feeds instead (never this module).

SOW System 1.5 (Media Pipeline & Rights Governance) requires every media
asset to carry a source_class (A/B/C), rights_status, and indexable flag.
A Nano-Banana country hero has no underlying Viator/supplier photo, so it is
tagged Class A (Rosotravel-owned/cleared) - the one image type in the system
eligible to be indexable with AI-generated ALT text.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "hero_images"
IMAGE_MODEL = "gemini-3-pro-image"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _prompt_for_country(country_name: str) -> str:
    return (
        f"A wide, photorealistic travel hero banner representing {country_name} - an "
        "iconic, instantly recognisable real-world view of the country at golden hour, "
        "warm natural light, travel-brochure quality, no people close to camera, no text "
        "or logo overlays, landscape orientation suitable for a website hero background."
    )


def generate_country_hero_image(country_name: str) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (asset_dict, error). asset_dict is None iff error is set."""
    settings = get_settings()
    if settings.image_generation_stub:
        return None, (
            "Image generation is not configured (set VERTEX_PROJECT in poc/.env). "
            "Run poc/scripts/setup_vertex_auth.py once, then set the project."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, "google-genai package is not installed"

    try:
        client = genai.Client(
            vertexai=True,
            project=settings.vertex_project,
            location=settings.vertex_location,
        )
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=_prompt_for_country(country_name),
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the admin UI as a plain message
        return None, f"Image generation request failed: {exc}"

    candidate = response.candidates[0] if response.candidates else None
    if candidate is None or not candidate.content.parts:
        return None, "Image generation returned no content"

    image_part = next((part for part in candidate.content.parts if part.inline_data), None)
    if image_part is None:
        return None, "Image generation returned no image data"

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    extension = image_part.inline_data.mime_type.split("/")[-1]
    filename = f"{_slugify(country_name)}_{uuid.uuid4().hex[:10]}.{extension}"
    out_path = STATIC_DIR / filename
    out_path.write_bytes(image_part.inline_data.data)

    asset = {
        "url": f"/static/hero_images/{filename}",
        "alt_text": f"{country_name} - Rosotravel destination hero image",
        "source_class": "A",
        "rights_status": "owned",
        "indexable": True,
        "generator": "nano_banana_pro",
        "generated_at": _utcnow_iso(),
    }
    return asset, None


ALLOWED_UPLOAD_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def save_uploaded_hero_image(
    entity_name: str, file_bytes: bytes, content_type: str
) -> tuple[dict[str, Any] | None, str | None]:
    """WBS City_Page: hero image "Source: CMS media for the city" - a real
    admin-uploaded photo, never AI-generated. SOW System 1.5 Class A covers
    "admin-uploaded" images explicitly, so this gets the same source_class
    as the country's Nano-Banana output, just a different generator tag.
    """
    extension = ALLOWED_UPLOAD_TYPES.get(content_type)
    if extension is None:
        return None, f"Unsupported image type '{content_type}' - use PNG, JPEG, or WebP"
    if not file_bytes:
        return None, "Uploaded file is empty"

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_slugify(entity_name)}_{uuid.uuid4().hex[:10]}.{extension}"
    out_path = STATIC_DIR / filename
    out_path.write_bytes(file_bytes)

    asset = {
        "url": f"/static/hero_images/{filename}",
        "alt_text": f"{entity_name} - Rosotravel destination hero image",
        "source_class": "A",
        "rights_status": "owned",
        "indexable": True,
        "generator": "admin_upload",
        "generated_at": _utcnow_iso(),
    }
    return asset, None
