import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    # Viator's raw destination type (COUNTRY/REGION/CITY/TOWN/...). Distinguishes
    # a country-level or region-level Destination row from an actual bookable
    # city, since all three share this same table. Legacy rows default to CITY.
    destination_level: Mapped[str] = mapped_column(String, default="CITY")
    source: Mapped[str] = mapped_column(String, default="viator")  # viator | internal
    status: Mapped[str] = mapped_column(String, default="inactive")  # inactive | active
    # SOW System 1.1 governance: destinations are Viator-sourced + human
    # approved, not manually created. Existing/internal/demo-seeded rows
    # default to "approved" so this doesn't retroactively break the demo
    # dataset; newly Viator-synced rows are explicitly set to
    # "pending_review" by admin.sync_viator_destinations().
    review_status: Mapped[str] = mapped_column(
        String, default="approved"
    )  # pending_review | approved | rejected
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    destination_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.entity_id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String)
    category_group: Mapped[str] = mapped_column(String)  # 01_tours | 02_tickets | 03_transfers
    source: Mapped[str] = mapped_column(String, default="viator")  # viator | internal
    status: Mapped[str] = mapped_column(String, default="inactive")  # inactive | active
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    destination: Mapped[Destination | None] = relationship(foreign_keys=[destination_entity_id])


class Attraction(Base):
    __tablename__ = "attractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    destination_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("destinations.entity_id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, default="internal")
    status: Mapped[str] = mapped_column(String, default="inactive")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    destination: Mapped[Destination | None] = relationship(foreign_keys=[destination_entity_id])


class EnrichedFact(Base):
    """Governed factual layer rows, separate from AI-authored content."""

    __tablename__ = "enriched_facts"
    __table_args__ = (UniqueConstraint("entity_id", "source", name="uq_entity_fact_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)  # google_places | wikidata | manual_override
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    factual_hash: Mapped[str] = mapped_column(String)
    is_stub: Mapped[bool] = mapped_column(default=False)
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DraftedContent(Base):
    __tablename__ = "drafted_contents"
    __table_args__ = (UniqueConstraint("entity_id", "version", name="uq_entity_draft_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    h1: Mapped[str] = mapped_column(String)
    meta_title: Mapped[str] = mapped_column(String)
    meta_description: Mapped[str] = mapped_column(String)
    highlights: Mapped[list[str]] = mapped_column(JSON, default=list)
    body: Mapped[str] = mapped_column(String)
    faq: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | validated | failed
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list)
    similarity: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class KeywordIntel(Base):
    __tablename__ = "keyword_intel"
    __table_args__ = (UniqueConstraint("entity_id", "target_phrase", "database", name="uq_entity_keyword_intel"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    target_phrase: Mapped[str] = mapped_column(String)
    database: Mapped[str] = mapped_column(String, default="us")
    source: Mapped[str] = mapped_column(String, default="semrush")
    keywords: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fetched_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AudienceVariant(Base):
    __tablename__ = "audience_variants"
    __table_args__ = (
        UniqueConstraint("drafted_content_id", "audience", name="uq_draft_audience_variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    drafted_content_id: Mapped[int] = mapped_column(ForeignKey("drafted_contents.id"))
    audience: Mapped[str] = mapped_column(String)
    snippet_text: Mapped[str] = mapped_column(String)

    drafted_content: Mapped[DraftedContent] = relationship()


class ProductQualityScore(Base):
    __tablename__ = "product_quality_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    quality_score: Mapped[float] = mapped_column()
    completeness_score: Mapped[float] = mapped_column()
    computed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PoolMembership(Base):
    __tablename__ = "pool_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    in_pool: Mapped[bool] = mapped_column(default=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SetMembership(Base):
    __tablename__ = "set_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    in_set: Mapped[bool] = mapped_column(default=False)
    confirmed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Archetype(Base):
    __tablename__ = "archetypes"
    __table_args__ = (UniqueConstraint("city_id", "name", name="uq_city_archetype"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)


class ArchetypeMembership(Base):
    __tablename__ = "archetype_memberships"
    __table_args__ = (
        UniqueConstraint("product_id", "archetype_id", name="uq_product_archetype"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[str] = mapped_column(String, index=True)
    archetype_id: Mapped[int] = mapped_column(ForeignKey("archetypes.id"))

    archetype: Mapped[Archetype] = relationship()


class WinnerSelection(Base):
    __tablename__ = "winner_selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_id: Mapped[str] = mapped_column(String, index=True)
    slot: Mapped[str] = mapped_column(String)
    product_id: Mapped[str] = mapped_column(String, index=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    computed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PublishedRecord(Base):
    __tablename__ = "published_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String)
    canonical_url: Mapped[str] = mapped_column(String)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_locks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Module 1 governance: {field_name: {"value": ..., "generated_at": ...}}
    # staged AI regenerations awaiting human accept/reject - never applied to
    # `content` automatically, per SOW acceptance criteria.
    content_candidates: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    date_published: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    date_modified: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="published")  # published | held
    # WBS Country_Page "Lite Page" governance: countries default to
    # noindex,follow until a human manually promotes them; other entity
    # types have no such gate and are always "indexed".
    index_state: Mapped[str] = mapped_column(String, default="indexed")  # indexed | noindex


class AuditLog(Base):
    """Module 10: cross-cutting admin audit trail (destination approve/reject/
    merge, content lock/unlock, regenerate/accept/reject/revert, country
    promote, site-config updates, etc.)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String, default="admin_poc")
    action: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    before_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    after_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SiteConfig(Base):
    """Module 8: global site chrome config (header/footer menus, cookie
    consent, live chat toggle) - key/value, not per-entity."""

    __tablename__ = "site_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    value: Mapped[Any] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class McpToolAuditLog(Base):
    __tablename__ = "mcp_tool_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[str] = mapped_column(String, index=True)
    tool_name: Mapped[str] = mapped_column(String)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RawVersion(Base):
    """Every ingested payload, versioned, hash-fingerprinted per SOW System 1.3 Diff Engine."""

    __tablename__ = "raw_versions"
    __table_args__ = (UniqueConstraint("entity_id", "version_number", name="uq_entity_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String)  # destination | product
    entity_id: Mapped[str] = mapped_column(String, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)

    content_hash: Mapped[str] = mapped_column(String)
    factual_hash: Mapped[str] = mapped_column(String)
    media_hash: Mapped[str] = mapped_column(String)
    offer_hash: Mapped[str] = mapped_column(String)
    realtime_offer_hash: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DiffResult(Base):
    """Outcome of comparing two consecutive RawVersions for one entity."""

    __tablename__ = "diff_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    from_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_version: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String)  # NONE | MINOR | MEDIUM | MAJOR
    changed_domains: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
