from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DestinationIngest(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    name: str
    country: str
    region: str | None = None
    city: str | None = None
    destination_level: str = "CITY"  # Viator type: COUNTRY | REGION | CITY | TOWN | ...
    source: str = "viator"
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None


class ProductIngest(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    destination_entity_id: str | None = None
    name: str
    category_group: str
    source: str = "viator"
    title: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    hours: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    phone: str | None = None
    rating: float | None = None
    review_count: int | None = None
    images: list[str] = Field(default_factory=list)
    videos: list[str] = Field(default_factory=list)
    options: list[dict[str, Any]] = Field(default_factory=list)
    inclusions: list[str] = Field(default_factory=list)
    cancellation_policy: str | None = None
    price: float | None = None
    currency: str | None = None
    availability_slots: list[str] = Field(default_factory=list)


class AttractionIngest(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    destination_entity_id: str | None = None
    name: str
    country: str | None = None
    city: str | None = None
    source: str = "internal"
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None
    official_website: str | None = None


class IngestResult(BaseModel):
    entity_id: str
    entity_type: str
    version_number: int
    severity: str
    changed_domains: list[str]


class VersionOut(BaseModel):
    version_number: int
    content_hash: str
    factual_hash: str
    media_hash: str
    offer_hash: str
    realtime_offer_hash: str
    created_at: str
    payload: dict[str, Any]


class DiffOut(BaseModel):
    entity_id: str
    from_version: int | None
    to_version: int
    severity: str
    changed_domains: list[str]
    created_at: str


class EntityOut(BaseModel):
    entity_id: str
    entity_type: str
    name: str
    status: str
    latest_version: int | None
    latest_severity: str | None


class CountryCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    region: str | None = None
    description: str | None = None
    images: list[str] = Field(default_factory=list)


class RegionCreateRequest(BaseModel):
    country: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    images: list[str] = Field(default_factory=list)


class CityCreateRequest(BaseModel):
    country: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=120)
    region: str | None = None
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None


class AttractionCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    destination_entity_id: str | None = None
    country: str | None = None
    city: str | None = None
    description: str | None = None
    official_website: str | None = None
    images: list[str] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None


class EnrichRequest(BaseModel):
    manual_overrides: dict[str, Any] = Field(default_factory=dict)


class FactSourceOut(BaseModel):
    source: str
    fields: dict[str, Any]
    factual_hash: str
    changed: bool
    is_stub: bool = False
    fetched_at: str


class EnrichResult(BaseModel):
    entity_id: str
    entity_type: str
    resolved_fields: dict[str, Any]
    resolved_factual_hash: str
    sources: list[FactSourceOut]


class FactsOut(BaseModel):
    entity_id: str
    entity_type: str
    resolved_fields: dict[str, Any]
    resolved_factual_hash: str
    sources: list[FactSourceOut]


class AudienceVariantOut(BaseModel):
    audience: str
    snippet_text: str


class KeywordIntelOut(BaseModel):
    entity_id: str
    target_phrase: str
    database: str
    source: str
    keywords: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    fetched_at: str


class DraftedContentOut(BaseModel):
    entity_id: str
    version: int
    h1: str
    meta_title: str
    meta_description: str
    highlights: list[str]
    body: str
    faq: list[dict[str, Any]]
    status: str
    validation_errors: list[str]
    similarity: dict[str, Any]
    created_at: str
    variants: list[AudienceVariantOut]


class SimilarityOut(BaseModel):
    entity_id: str
    band: str
    score: float
    nearest_entity_id: str | None = None


class SetMembershipRequest(BaseModel):
    in_set: bool = True
    confirmed_by: str | None = "product_ops"


class ModelCRecomputeOut(BaseModel):
    products_scored: int
    products_in_pool: int
    archetypes: int


class PickOut(BaseModel):
    slot: str
    product_id: str
    title: str
    image_url: str | None = None
    price_from: float | None = None
    currency: str | None = None
    archetype: str
    score: float
    reason_codes: list[str]


class PicksOut(BaseModel):
    city_id: str
    suppressed: bool
    reason: str | None = None
    picks: list[PickOut] = Field(default_factory=list)
    decision_proof: dict[str, list[str] | str] = Field(default_factory=dict)


class CountryRollupOut(BaseModel):
    country: str
    suppressed: bool
    reason: str | None = None
    top_cities: list[dict[str, Any]] = Field(default_factory=list)
    top_products: list[PickOut] = Field(default_factory=list)


class ProductExplainOut(BaseModel):
    product_id: str
    in_pool: bool
    in_set: bool
    quality_score: float | None
    completeness_score: float | None
    reasons: list[str]
    archetypes: list[str]
    winner_slots: list[str]
    competed_against: list[str]


class PublishOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_id: str
    entity_type: str
    canonical_url: str
    json_ld: dict[str, Any] = Field(alias="schema_json")
    content: dict[str, Any]
    date_published: str
    date_modified: str
    version: int
    status: str
    index_state: str = "indexed"
    content_locks: dict[str, Any] = Field(default_factory=dict)


class PublishedContentEditRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)
    lock_fields: list[str] = Field(default_factory=list)
    unlock_fields: list[str] = Field(default_factory=list)
    edited_by: str | None = "admin"


class PublishListOut(BaseModel):
    records: list[PublishOut]


class SearchToursRequest(BaseModel):
    country: str | None = None
    city: str | None = None
    categories: list[str] = Field(default_factory=list)
    max_results: int = 10


class TourSearchItem(BaseModel):
    entity_id: str
    name: str
    canonical_url: str
    price_from: float | None = None
    currency: str | None = None
    duration_minutes: int | None = None
    rating_average: float | None = None
    source_type: str = "published_record"


class SearchToursOut(BaseModel):
    results: list[TourSearchItem]


class GetTourRequest(BaseModel):
    entity_id: str


class AvailabilityLinkRequest(BaseModel):
    entity_id: str
    date: str | None = None


class AvailabilityLinkOut(BaseModel):
    entity_id: str
    booking_url: str
    note: str
