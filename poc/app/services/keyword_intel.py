from __future__ import annotations

import csv
import io
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.entities import KeywordIntel, RawVersion


class SemrushConfigError(RuntimeError):
    pass


class SemrushClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.semrush_api_key:
            raise SemrushConfigError("SEMRUSH_API_KEY is not configured")
        self.base_url = self.settings.semrush_api_base_url

    def related_keywords(
        self,
        phrase: str,
        *,
        database: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self._report(
            {
                "type": "phrase_related",
                "phrase": phrase,
                "database": database or self.settings.semrush_database,
                "display_limit": limit,
                "display_sort": "nq_desc",
                "export_columns": "Ph,Nq,Cp,Co,Nr,Td,Rr,Fk",
            }
        )

    def phrase_questions(
        self,
        phrase: str,
        *,
        database: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return self._report(
            {
                "type": "phrase_questions",
                "phrase": phrase,
                "database": database or self.settings.semrush_database,
                "display_limit": limit,
                "display_sort": "nq_desc",
                "export_columns": "Ph,Nq,Cp,Co,Nr,Td",
            }
        )

    def _report(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        assert self.settings.semrush_api_key is not None
        query = {"key": self.settings.semrush_api_key, **params}
        with httpx.Client(timeout=45) as client:
            response = client.get(self.base_url, params=query)
            response.raise_for_status()
            text = response.text.strip()
        if text.startswith("ERROR"):
            if "NOTHING FOUND" in text:
                return []
            raise RuntimeError(text)
        return _parse_semrush_csv(text)


def _parse_semrush_csv(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return [_normalize_row(row) for row in reader]


def _normalize_row(row: dict[str, str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        normalized_key = _normalize_key(key)
        output[normalized_key] = _normalize_value(value)
    return output


def _normalize_key(key: str) -> str:
    return (
        key.strip()
        .lower()
        .replace(" ", "_")
        .replace("%", "percent")
        .replace(".", "")
        .replace("-", "_")
    )


def _normalize_value(value: str | None) -> Any:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    for parser in (int, float):
        try:
            return parser(value)
        except ValueError:
            pass
    return value


def _latest_raw_version(db: Session, entity_id: str) -> RawVersion | None:
    return db.scalar(
        select(RawVersion)
        .where(RawVersion.entity_id == entity_id)
        .order_by(RawVersion.version_number.desc())
        .limit(1)
    )


def target_phrase_for_entity(db: Session, entity_id: str) -> str | None:
    raw_version = _latest_raw_version(db, entity_id)
    if raw_version is None:
        return None
    payload = raw_version.payload
    return payload.get("title") or payload.get("name") or entity_id


def fetch_keyword_intel(
    db: Session,
    entity_id: str,
    *,
    phrase: str | None = None,
    database: str | None = None,
    limit: int = 10,
    client: SemrushClient | None = None,
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    target_phrase = phrase or target_phrase_for_entity(db, entity_id)
    if target_phrase is None:
        return None, 404, f"Entity '{entity_id}' has no raw version"

    settings = get_settings()
    selected_database = database or settings.semrush_database
    if settings.semrush_stub and client is None:
        return None, 400, "SEMRUSH_API_KEY is not configured"

    adapter = client or SemrushClient(settings)
    try:
        keywords = adapter.related_keywords(target_phrase, database=selected_database, limit=limit)
        questions = adapter.phrase_questions(target_phrase, database=selected_database, limit=limit)
    except Exception as exc:
        return None, 502, f"SEMrush keyword fetch failed: {exc}"

    record = db.scalar(
        select(KeywordIntel).where(
            KeywordIntel.entity_id == entity_id,
            KeywordIntel.target_phrase == target_phrase,
            KeywordIntel.database == selected_database,
        )
    )
    if record is None:
        record = KeywordIntel(
            entity_id=entity_id,
            target_phrase=target_phrase,
            database=selected_database,
        )
        db.add(record)
    record.keywords = keywords
    record.questions = questions
    record.raw_response = {
        "keyword_count": len(keywords),
        "question_count": len(questions),
    }
    db.commit()
    db.refresh(record)
    return keyword_intel_out(record), None, None


def latest_keyword_intel(db: Session, entity_id: str) -> KeywordIntel | None:
    return db.scalar(
        select(KeywordIntel)
        .where(KeywordIntel.entity_id == entity_id)
        .order_by(KeywordIntel.fetched_at.desc(), KeywordIntel.id.desc())
        .limit(1)
    )


def get_keyword_intel(db: Session, entity_id: str) -> dict[str, Any] | None:
    record = latest_keyword_intel(db, entity_id)
    if record is None:
        return None
    return keyword_intel_out(record)


def keyword_intel_out(record: KeywordIntel) -> dict[str, Any]:
    return {
        "entity_id": record.entity_id,
        "target_phrase": record.target_phrase,
        "database": record.database,
        "source": record.source,
        "keywords": record.keywords,
        "questions": record.questions,
        "fetched_at": record.fetched_at.isoformat(),
    }
