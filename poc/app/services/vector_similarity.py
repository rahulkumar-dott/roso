from __future__ import annotations

import hashlib
import math
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import DraftedContent

EMBEDDING_DIM = 384


class EmbeddingAdapter(Protocol):
    model_name: str

    def embed(self, text_value: str) -> list[float]:
        ...


class SentenceTransformerAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.sentence_transformer_model
        self._model: Any | None = None

    def embed(self, text_value: str) -> list[float]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        vector = self._model.encode(text_value or "", normalize_embeddings=True)
        return [float(value) for value in vector.tolist()]


class HashEmbeddingAdapter:
    """Deterministic test fallback used only when sentence-transformers is unavailable."""

    model_name = "hash-fallback-384"

    def embed(self, text_value: str) -> list[float]:
        buckets = [0.0] * EMBEDDING_DIM
        for token in (text_value or "").lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIM
            buckets[index] += 1.0
        norm = math.sqrt(sum(value * value for value in buckets))
        if not norm:
            return buckets
        return [value / norm for value in buckets]


def default_embedding_adapter() -> EmbeddingAdapter:
    return SentenceTransformerAdapter()


def pgvector_available(db: Session) -> bool:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS content_vectors (
                    entity_id TEXT PRIMARY KEY,
                    draft_id INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    embedding VECTOR(384) NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values[:EMBEDDING_DIM]) + "]"


def nearest_by_pgvector(
    db: Session,
    entity_id: str,
    body: str,
    *,
    embedder: EmbeddingAdapter | None = None,
) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.vector_similarity_enabled or not pgvector_available(db):
        return None

    adapter = embedder or default_embedding_adapter()
    try:
        embedding = adapter.embed(body)
    except Exception:
        adapter = HashEmbeddingAdapter()
        embedding = adapter.embed(body)
    if len(embedding) != EMBEDDING_DIM:
        return None

    row = db.execute(
        text(
            """
            SELECT entity_id, 1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM content_vectors
            WHERE entity_id != :entity_id
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT 1
            """
        ),
        {"entity_id": entity_id, "embedding": vector_literal(embedding)},
    ).mappings().first()

    score = float(row["score"]) if row else 0.0
    return {
        "entity_id": entity_id,
        "score": round(score, 4),
        "nearest_entity_id": row["entity_id"] if row else None,
        "method": "pgvector_sentence_transformer",
        "embedding_model": adapter.model_name,
    }


def upsert_content_vector(
    db: Session,
    content: DraftedContent,
    *,
    embedder: EmbeddingAdapter | None = None,
) -> bool:
    settings = get_settings()
    if not settings.vector_similarity_enabled or not pgvector_available(db):
        return False

    adapter = embedder or default_embedding_adapter()
    try:
        embedding = adapter.embed(content.body)
    except Exception:
        adapter = HashEmbeddingAdapter()
        embedding = adapter.embed(content.body)
    if len(embedding) != EMBEDDING_DIM:
        return False

    db.execute(
        text(
            """
            INSERT INTO content_vectors (entity_id, draft_id, model, dim, embedding, updated_at)
            VALUES (:entity_id, :draft_id, :model, :dim, CAST(:embedding AS vector), now())
            ON CONFLICT (entity_id) DO UPDATE SET
                draft_id = EXCLUDED.draft_id,
                model = EXCLUDED.model,
                dim = EXCLUDED.dim,
                embedding = EXCLUDED.embedding,
                updated_at = now()
            """
        ),
        {
            "entity_id": content.entity_id,
            "draft_id": content.id,
            "model": adapter.model_name,
            "dim": len(embedding),
            "embedding": vector_literal(embedding),
        },
    )
    return True
